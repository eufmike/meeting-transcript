---
name: meeting-notes
description: Generate a human-readable meeting notes markdown file from a transcript CSV and analysis JSON
---

# Meeting Notes Generator

You are generating a structured, human-readable meeting notes document from two
source files produced by the `meeting-transcript` pipeline:

- A **transcript CSV** — columns: `start, end, speaker, text`
- An **analysis JSON** — keys: `summary`, `action_items`, `unresolved`
- The **template** at `references/templates/meeting-notes.md`

## Steps

1. **Locate the files.** The user will provide paths, or look for the most recent
   files under `data/recordings/`. The transcript CSV and analysis JSON share the
   same directory.

2. **Read both files in full.** Do not summarize or truncate either file.

3. **Identify speakers.** The CSV uses anonymous labels (`SPEAKER_00`, `SPEAKER_01`,
   etc.). Ask the user to confirm the mapping before writing the notes, unless the
   user has already provided names. Use real names everywhere in the output.

4. **Identify discussion topics.** Scan the transcript for natural topic breaks —
   look for phrases that introduce a new subject (e.g. "再來是", "下一個", "接下來",
   "Next", "Let's talk about"). Group utterances under each topic. Use the
   analysis `summary` items as a cross-check.

5. **Fill in the template** at `references/templates/meeting-notes.md`:
   - `{{title}}` — from the analysis `transcript_id` or ask the user
   - `{{date}}` — from `transcript_id` or filename
   - `{{attendees}}` — real names from step 3, comma-separated
   - `{{duration}}` — last timestamp in the transcript CSV
   - `{{summary}}` — each item from analysis `summary`, one bullet per line
   - `{{topics}}` — one `###` section per discussion topic with key points as bullets
   - `{{action_items}}` — table rows from analysis `action_items`; use real names;
     if `deadline` is null write `—`; flag any deadline year that doesn't match
     the meeting year as a likely inference error
   - `{{unresolved}}` — each item from analysis `unresolved`, one bullet per line
   - `{{utterances}}` — all rows from the transcript CSV, speaker replaced with
     real name; escape any pipe characters `|` in the text column with `\|`

6. **Write the output** to the same directory as the source files, named
   `meeting-notes.md`.

7. **Report** the output path and flag anything that looked wrong
   (mis-identified speakers, garbled text, suspicious deadlines, etc.).

## Quality rules

- Keep the language of the notes consistent with the source material — if the
  meeting was in Chinese, keep Chinese in the transcript section; use English for
  the structural labels (Summary, Action Items, etc.).
- Do not invent or infer information not present in the source files.
- Action item owners must be real names, not speaker IDs.
- If a deadline year is more than one year away from the meeting date, flag it
  with a ⚠ comment in the table.
