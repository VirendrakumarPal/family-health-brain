#!/usr/bin/env python3
"""
Family Health Brain — a Karpathy-style LLM wiki for your family's health notes.

  python brain.py ingest              # process everything in vault/raw/inbox/
  python brain.py ask "Has Papa's BP gone up since Diwali?"
  python brain.py review              # weekly review
  python brain.py ingest --dry-run    # show what would happen, no API calls

Loop: a cheap filter reads each new input first (keep / skip, which person, which kind),
then the writer model writes only the lines worth keeping into wiki/ and links them.

Needs: ANTHROPIC_API_KEY. Optional: TYPESAFE_API_KEY + USE_JEV=1 to use Jev as the filter.
"""
import argparse
import base64
import datetime as dt
import json
import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VAULT = Path(os.environ.get("BRAIN_VAULT", ROOT / "vault")).resolve()
INBOX = VAULT / "raw" / "inbox"
PROCESSED = VAULT / "raw" / "processed"
WIKI = VAULT / "wiki"

WRITER_MODEL = os.environ.get("WRITER_MODEL", "claude-opus-5-5")
FILTER_MODEL = os.environ.get("FILTER_MODEL", "claude-haiku-4-5")
USE_JEV = os.environ.get("USE_JEV", "0") == "1"

TEXT_EXT = {".txt", ".md"}
IMAGE_EXT = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
PDF_EXT = {".pdf"}
SKIP_NAMES = {"README.md", ".gitkeep", ".DS_Store"}


# ---------------------------------------------------------------- helpers
def load_dotenv():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


def wiki_listing() -> str:
    """Titles of existing notes, so the model links to real notes instead of inventing names."""
    notes = sorted(p.relative_to(VAULT).as_posix() for p in WIKI.rglob("*.md"))
    return "\n".join(notes) or "(empty)"


def extract_json(text: str):
    """Pull the first JSON object out of a model reply (tolerates ```json fences)."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError(f"No JSON in model reply:\n{text[:500]}")
    return json.loads(m.group(0))


def safe_wiki_path(rel: str) -> Path:
    """Only allow writes inside wiki/ (or index.md / log.md)."""
    rel = rel.strip().lstrip("/").replace("\\", "/")
    if not rel.endswith(".md"):
        rel += ".md"
    p = (VAULT / rel).resolve()
    allowed = p == (VAULT / "index.md").resolve() or p == (VAULT / "log.md").resolve() or WIKI in p.parents
    if not allowed:
        raise ValueError(f"Refusing to write outside wiki/: {rel}")
    return p


def input_blocks(path: Path):
    """Turn a raw file into Claude content blocks (text, image or PDF)."""
    ext = path.suffix.lower()
    if ext in TEXT_EXT:
        return [{"type": "text", "text": f"FILE {path.name}:\n{read(path)}"}]
    data = base64.standard_b64encode(path.read_bytes()).decode()
    if ext in IMAGE_EXT:
        return [{"type": "text", "text": f"FILE {path.name} (photo):"},
                {"type": "image", "source": {"type": "base64", "media_type": IMAGE_EXT[ext], "data": data}}]
    if ext in PDF_EXT:
        return [{"type": "text", "text": f"FILE {path.name} (PDF):"},
                {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": data}}]
    raise ValueError(f"Unsupported file type: {path.name}")


# ---------------------------------------------------------------- model calls
class Claude:
    def __init__(self):
        import anthropic  # pip install anthropic
        self.client = anthropic.Anthropic()

    def ask(self, model, system, content, max_tokens=4000):
        r = self.client.messages.create(model=model, max_tokens=max_tokens, system=system,
                                        messages=[{"role": "user", "content": content}])
        return "".join(b.text for b in r.content if getattr(b, "type", "") == "text")


FILTER_PROMPT = """You are a fast filter for a family health notebook.
Decide if this input is worth keeping. Reply ONLY with JSON:
{"keep": true/false, "kind": "prescription|reading|report|visit|insurance|bill|general|junk",
 "person": "name or unknown", "reason": "one short line"}
Keep: prescriptions, readings, lab reports, doctor advice, symptoms, insurance or medical bills.
Skip: forwards, greetings, ads, memes, duplicates of the same content."""


def filter_with_claude(claude, path):
    text = claude.ask(FILTER_MODEL, FILTER_PROMPT, input_blocks(path), max_tokens=300)
    return extract_json(text)


def filter_with_jev(path):
    """Optional: TypeSafe Jev as the cheap filter (text inputs only). Falls back to Claude on any error.
    Check https://typesafe.ai docs if the SDK interface changes."""
    from typesafe_sdk import Choice, Noul, TypeSafeClient  # pip install typesafe-sdk
    if path.suffix.lower() not in TEXT_EXT:
        raise RuntimeError("Jev filter handles text only; photos/PDFs go to Claude.")
    with TypeSafeClient() as client:
        r = client.system_one(
            state={"message": read(path)[:8000]},
            questions={
                "keep": Noul("Is this message worth keeping in a family health notebook "
                             "(prescription, reading, report, doctor advice, symptom, insurance, medical bill)?"),
                "kind": Choice("What kind of health information is this?", {
                    "prescription": "medicines and doses", "reading": "BP, sugar, weight or similar values",
                    "report": "lab or scan report", "visit": "doctor visit or advice",
                    "insurance": "insurance or medical bill", "junk": "forward, greeting, ad or unrelated"}),
            },
        )
    return {"keep": bool(r.nouls["keep"].noul), "kind": r.choices["kind"].choice,
            "person": "unknown", "reason": "jev"}


WRITER_SYSTEM = """You maintain a family's health notebook (an Obsidian vault). Follow these rules exactly:

{rules}

Existing notes (link to these, reuse them, do not duplicate):
{listing}

Current index.md:
{index}

Relevant existing notes (full text):
{related}

Today is {today}. The raw file will be stored at: {source}

Reply ONLY with JSON:
{{"changes": [{{"path": "wiki/health/Note name.md", "mode": "create|append|replace", "content": "markdown"}}],
  "index_md": "full new index.md (or empty string if unchanged)",
  "log_line": "YYYY-MM-DD — what changed — [[notes]]",
  "summary": "one or two lines for the user",
  "doctor_flag": true/false}}
- To add a row to a table (readings, medicines), use "replace" with the WHOLE updated note,
  keeping every existing row and the Related line at the end.
- Use "append" only for notes without tables (content = only the new lines). Use "create" for new notes.
- Write only the lines worth keeping. Never give medical advice. Never invent values."""


def write_notes(claude, path, today, verdict=None):
    source = f"raw/processed/{today}/{path.name}"
    hint = " ".join(str((verdict or {}).get(k, "")) for k in ("person", "kind"))
    if path.suffix.lower() in TEXT_EXT:
        hint += " " + read(path)[:2000]
    related = gather_context(hint, limit_chars=30000).split("\n", 1)[-1] if hint.strip() else "(none)"
    system = WRITER_SYSTEM.format(rules=read(VAULT / "CLAUDE.md"), listing=wiki_listing(),
                                  index=read(VAULT / "index.md"), related=related or "(none)",
                                  today=today, source=source)
    text = claude.ask(WRITER_MODEL, system, input_blocks(path), max_tokens=6000)
    return extract_json(text)


def apply_changes(plan):
    written, safe = [], []
    for ch in plan.get("changes", []):          # validate everything before touching any file
        try:
            safe.append((safe_wiki_path(ch["path"]), ch))
        except (ValueError, KeyError) as e:
            print(f"  ! skipped unsafe change: {e}")
    for p, ch in safe:
        p.parent.mkdir(parents=True, exist_ok=True)
        mode = ch.get("mode", "create")
        body = ch.get("content", "").rstrip() + "\n"
        if mode == "append" and p.exists():
            with p.open("a", encoding="utf-8") as f:
                f.write("\n" + body)
        elif mode == "create" and p.exists():
            with p.open("a", encoding="utf-8") as f:  # never silently overwrite an existing note
                f.write("\n" + body)
        else:
            p.write_text(body, encoding="utf-8")
        written.append(p.relative_to(VAULT).as_posix())
    if plan.get("index_md"):
        (VAULT / "index.md").write_text(plan["index_md"].rstrip() + "\n", encoding="utf-8")
    if plan.get("log_line"):
        with (VAULT / "log.md").open("a", encoding="utf-8") as f:
            f.write(plan["log_line"].strip() + "\n")
    return written


def inbox_files():
    return sorted(p for p in INBOX.iterdir()
                  if p.is_file() and p.name not in SKIP_NAMES
                  and (p.suffix.lower() in TEXT_EXT | set(IMAGE_EXT) | PDF_EXT))


# ---------------------------------------------------------------- commands
def cmd_ingest(dry_run=False, claude=None):
    files = inbox_files()
    if not files:
        print("Inbox is empty. Drop photos, PDFs or .txt notes into vault/raw/inbox/.")
        return
    today = dt.date.today().isoformat()
    claude = None if dry_run else (claude or Claude())
    for path in files:
        print(f"\n▶ {path.name}")
        if dry_run:
            print("  would: filter → write notes → move to", f"raw/processed/{today}/")
            continue
        try:
            verdict = None
            if USE_JEV and os.environ.get("TYPESAFE_API_KEY"):
                try:
                    verdict = filter_with_jev(path)
                except Exception as e:  # fall back to Claude filter
                    print(f"  (Jev skipped: {e})")
            verdict = verdict or filter_with_claude(claude, path)
            print(f"  filter: keep={verdict.get('keep')} kind={verdict.get('kind')} — {verdict.get('reason', '')}")
            dest = PROCESSED / today
            dest.mkdir(parents=True, exist_ok=True)
            if not verdict.get("keep"):
                shutil.move(str(path), str(dest / path.name))
                continue
            plan = write_notes(claude, path, today, verdict)
            written = apply_changes(plan)
            shutil.move(str(path), str(dest / path.name))
            print("  wrote:", ", ".join(written) or "(nothing)")
            print("  " + plan.get("summary", ""))
            if plan.get("doctor_flag"):
                print("  ⚠️  Something here should be discussed with the doctor.")
        except Exception as e:
            print(f"  ✗ failed, file left in inbox: {e}")


def gather_context(question, limit_chars=60000):
    """Simple retrieval: index + notes whose name or body shares words with the question."""
    words = {w for w in re.findall(r"[\w']+", question.lower()) if len(w) > 2}
    scored = []
    for p in WIKI.rglob("*.md"):
        body = read(p)
        hay = (p.stem + " " + body).lower()
        score = sum(hay.count(w) for w in words)
        if score:
            scored.append((score, p, body))
    scored.sort(key=lambda s: -s[0])
    parts, total = [], 0
    for _, p, body in scored:
        chunk = f"\n=== [[{p.stem}]] ({p.relative_to(VAULT).as_posix()}) ===\n{body}"
        if total + len(chunk) > limit_chars:
            break
        parts.append(chunk)
        total += len(chunk)
    return read(VAULT / "index.md") + "\n" + "".join(parts)


ASK_SYSTEM = """Answer the family's question using ONLY the notes provided.
Cite every fact with its [[note]]. If the notes do not contain the answer, say so.
You are not a doctor: describe what was recorded, never advise on medicines or treatment,
and suggest discussing with the doctor when readings or symptoms look concerning.
Answer in simple language; Hinglish is fine if the question is in Hinglish."""


def cmd_ask(question, claude=None):
    claude = claude or Claude()
    ctx = gather_context(question)
    print(claude.ask(WRITER_MODEL, ASK_SYSTEM, [{"type": "text", "text": f"NOTES:\n{ctx}\n\nQUESTION: {question}"}],
                     max_tokens=1500))


def cmd_review(claude=None):
    claude = claude or Claude()
    ctx = read(VAULT / "index.md") + "\n" + read(VAULT / "log.md") + "\n" + "".join(
        f"\n=== [[{p.stem}]] ===\n{read(p)}" for p in sorted(WIKI.rglob("*.md")))
    prompt = ("Weekly review. List: (1) readings trending up or down, described not advised; "
              "(2) visits, renewals or refills due in the next 14 days; (3) notes that should be linked; "
              "(4) anything marked [UNCLEAR - please check].")
    print(claude.ask(WRITER_MODEL, ASK_SYSTEM, [{"type": "text", "text": f"NOTES:\n{ctx[:150000]}\n\n{prompt}"}],
                     max_tokens=1500))


def main():
    load_dotenv()
    ap = argparse.ArgumentParser(description="Family Health Brain")
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("ingest", help="process vault/raw/inbox/")
    i.add_argument("--dry-run", action="store_true")
    a = sub.add_parser("ask", help="ask a question")
    a.add_argument("question")
    sub.add_parser("review", help="weekly review")
    args = ap.parse_args()
    for d in (INBOX, PROCESSED, WIKI):
        d.mkdir(parents=True, exist_ok=True)
    if args.cmd != "ingest" or not args.dry_run:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            sys.exit("Set ANTHROPIC_API_KEY (in your shell or a .env file next to brain.py).")
    if args.cmd == "ingest":
        cmd_ingest(dry_run=args.dry_run)
    elif args.cmd == "ask":
        cmd_ask(args.question)
    else:
        cmd_review()


if __name__ == "__main__":
    main()
