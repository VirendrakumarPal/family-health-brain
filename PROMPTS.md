# Copy-paste prompts

Use these in the Claude desktop app (with the vault folder shared) or in Claude Code opened inside the `vault/` folder.
Claude follows the rules in `vault/CLAUDE.md`.

---

## 1. Add new things (run whenever you drop files in `raw/inbox/`)

```
Read CLAUDE.md first and follow it strictly.
Process every file in raw/inbox/ (photos, PDFs, text).
For each one: create or update the right notes in wiki/, link them with [[wikilinks]],
append readings to existing tables instead of making new notes,
mark anything unreadable as [UNCLEAR - please check],
then move the file to raw/processed/<today's date>/, update index.md and add a line to log.md.
Finally, show me a short list of what you changed.
```

## 2. Ask a question

```
Read CLAUDE.md and index.md. Answer this using only the notes in wiki/:
"Has Papa's BP gone up since Diwali?"
Show the relevant readings, medicines and the doctor's last advice.
Cite each fact with the [[note]] it came from. Do not give medical advice.
```

Other questions that work well:
- "What did the doctor say at Papa's last visit, and when is the next one?"
- "List all medicines Mummy is taking right now, exactly as prescribed."
- "Which reports should I carry to tomorrow's appointment?"
- "When does our health insurance renew?"

## 3. Before a doctor visit (1-page summary)

```
Read CLAUDE.md. Make a one-page summary for Papa's doctor visit:
recent readings (table), current medicines as prescribed, symptoms noted since the last visit,
and questions we wanted to ask. Keep it factual. Save it as wiki/health/<date> Papa visit prep.md
```

## 4. Weekly review (Sunday, 2 minutes)

```
Read CLAUDE.md, index.md and log.md. Review what changed this week:
- any readings trending up or down (just describe, no advice)
- upcoming visits, renewals or refills in the next 14 days
- notes that should be linked but are not
- anything marked [UNCLEAR - please check]
Fix the missing links yourself, then give me the list.
```
