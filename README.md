# Family Health Brain 🧠

**Your family's health memory, in one place, that organises itself.**

"Doctor ne poocha, pichhli baar kaunsi dawai di thi?" and the whole family is scrolling WhatsApp.
BP readings in a notebook, prescriptions in a family group, reports in email. Everything exists, nothing is connected.

This kit turns those scattered bits into a linked notebook that answers questions like:

- "Has Papa's BP gone up since Diwali?"
- "What did the doctor say last time, and when is the next visit?"
- "Which medicines is Mummy taking right now, exactly as prescribed?"
- "When does our health insurance renew?"

It is inspired by Andrej Karpathy's "LLM wiki" idea (you drop raw material in, the AI writes and maintains a linked wiki)
and classic Zettelkasten note-linking.

---

## How it works (the loop)

```
 photo of prescription ─┐
 voice-note transcript ──┼─▶  raw/inbox/  ─▶  FILTER  ─▶  WRITER  ─▶  wiki/  (linked notes)
 lab report PDF ────────┘                    keep/skip?    Claude writes      Papa ↔ BP ↔ medicine ↔ visit
                                              (cheap model)  only what matters
                                                                     │
                                         you ask a question ◀────────┘  answer with sources
```

1. **Drop** anything into `vault/raw/inbox/`: a prescription photo, a report PDF, a typed note or voice-note transcript.
2. **Filter**: a cheap, fast model decides if it's worth keeping (forwards and greetings are skipped).
3. **Write**: Claude writes a short clean note, adds readings to the right table, and links everything with `[[wikilinks]]`.
4. **Ask**: open Obsidian and browse the graph, or ask a question and get an answer that cites the notes.

The `vault/` folder already contains **demo notes** (fictional "Papa" and "Mummy") so you can see the result before adding your own.

---

## Option A — No code (15 minutes)

1. Install **Obsidian** (free): https://obsidian.md → "Open folder as vault" → choose the `vault/` folder.
2. Open the **Claude desktop app** (https://claude.ai/download) and let it work on the `vault/` folder
   (add the Filesystem extension in Settings → Extensions and point it at `vault/`).
   Simpler alternative: create a Claude Project, upload `CLAUDE.md` and your notes, and paste Claude's answers back into Obsidian.
3. Drop a prescription photo or a typed note into `vault/raw/inbox/`.
4. Copy prompt **#1 from `PROMPTS.md`** into Claude. It will read `CLAUDE.md` (the rules) and update the notes.
5. Look at the graph in Obsidian. Ask questions with prompt **#2**.

Helpful add-ons:
- **obsidian-skills** teaches Claude Obsidian's note formats: https://github.com/kepano/obsidian-skills
- **claudesidian** is a ready Claude Code starter vault (PARA structure): https://github.com/heyitsnoah/claudesidian

## Option B — Automatic, with the script

Requires Python 3.10+ and an Anthropic API key (https://console.anthropic.com).

```bash
pip install -r requirements.txt
cp .env.example .env          # put your ANTHROPIC_API_KEY in .env

python brain.py ingest --dry-run   # see what it would do
python brain.py ingest             # process everything in vault/raw/inbox/
python brain.py ask "Has Papa's BP gone up since Diwali?"
python brain.py review             # weekly review: trends, upcoming visits, missing links
```

- Photos (`.jpg .png .webp`), PDFs and `.txt`/`.md` files are supported.
- Processed inputs move to `vault/raw/processed/<date>/`. Failed ones stay in the inbox.
- The script can only write inside `vault/wiki/`, `index.md` and `log.md`.
- Run `ingest` every night with Task Scheduler (Windows) or cron (Mac/Linux) and "the vault keeps thinking after you close the laptop".

**Models** (change in `.env`):
- `WRITER_MODEL` — writes the notes. Default `claude-opus-5-5` (best quality). A Sonnet model is cheaper.
- `FILTER_MODEL` — cheap keep/skip check. Default `claude-haiku-4-5`.
- Optional **Jev** (TypeSafe AI, https://typesafe.ai) as the filter for text inputs: `pip install typesafe-sdk`,
  set `USE_JEV=1` and `TYPESAFE_API_KEY`. If Jev fails for any reason, the script falls back to the Claude filter.

**Cost**: roughly a few rupees per prescription or report with Opus, less with Sonnet. A family adding a few items a week
usually stays well under the price of one doctor's visit per month.

---

## Please read: safety and privacy

- **This is a memory, not a doctor.** It summarises what your family recorded. It never suggests medicines or doses.
  When readings look concerning it adds "Please discuss this with the doctor."
- **Check medicine names.** Reading handwriting from a photo can go wrong. Unclear words are marked
  `[UNCLEAR - please check]`. Always confirm against the original prescription.
- **Where your data goes.** The vault is plain files on your own computer. When Claude processes a note, that content is
  sent to Anthropic's servers to generate the answer. Don't put Aadhaar, PAN, bank or card numbers in it
  (the rules tell Claude to leave them out anyway).
- **Back it up.** It's just a folder: keep a copy on your drive or a USB stick.

---

## What's inside

```
family-health-brain/
├── README.md          ← this file
├── PROMPTS.md         ← copy-paste prompts (no-code path)
├── brain.py           ← automation script (ingest / ask / review)
├── requirements.txt
├── .env.example
└── vault/             ← open this folder in Obsidian
    ├── CLAUDE.md      ← the rules Claude follows (safety rules included)
    ├── index.md       ← table of contents (Claude keeps it updated)
    ├── log.md         ← history of changes
    ├── raw/inbox/     ← drop new things here
    ├── raw/processed/ ← originals are kept here, never edited
    ├── wiki/          ← Claude writes here: people/, health/, finance/, concepts/
    └── templates/
```

Made by Virendra Pal · @viren4ai — share it with anyone managing a parent's health.
