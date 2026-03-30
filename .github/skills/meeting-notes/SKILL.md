---
name: meeting-notes
description: Generate a human-readable meeting notes markdown file from a transcript CSV and analysis JSON
---

# Meeting Notes Generator

You are generating a structured, human-readable meeting notes document from two
source files produced by the `meeting-transcript` pipeline:

- A **transcript CSV** — columns: `start, end, speaker, text`
- An **analysis JSON** — keys: `summary`, `action_items`, `unresolved`
- The **template** matching the detected language (see Language Detection below)

## Language Detection

Determine the output language using this priority order:

1. **Explicit `--lang` option** (if provided by the caller):
   - `zh-TW` → Traditional Chinese throughout (use `references/templates/meeting-notes-zh-tw.md`)
   - `en` → English throughout (use `references/templates/meeting-notes.md`)
   - `auto` → proceed to step 2

2. **Auto-detect from transcript content**:
   - Sample the first 20 non-empty `text` values from the CSV.
   - If the majority of characters are CJK (Unicode blocks 4E00–9FFF), set language to `zh-TW`.
   - Otherwise set language to `en`.

3. **Apply language to the entire document**:
   - All structural labels (section headings, table headers, metadata keys) must
     match the detected language — do **not** mix English labels into a Chinese document.
   - The transcript `text` column is always preserved verbatim regardless of language.
   - For `zh-TW`: use Traditional Chinese characters, **not** Simplified Chinese.

## Steps

1. **Locate the files.** The user will provide paths, or look for the most recent
   files under `data/recordings/`. The transcript CSV and analysis JSON share the
   same directory.

2. **Read both files in full.** Do not summarize or truncate either file.

3. **Detect language** as described above and select the correct template.

4. **Identify speakers.** The CSV uses anonymous labels (`SPEAKER_00`, `SPEAKER_01`,
   etc.). Ask the user to confirm the mapping before writing the notes, unless the
   user has already provided names. Use real names everywhere in the output.

5. **Identify discussion topics.** Scan the transcript for natural topic breaks —
   look for phrases that introduce a new subject (e.g. "再來是", "下一個", "接下來",
   "Next", "Let's talk about"). Group utterances under each topic. Use the
   analysis `summary` items as a cross-check.

6. **Fill in the template** selected in step 3:
   - `{{title}}` — from the analysis `transcript_id` or ask the user
   - `{{date}}` — from `transcript_id` or filename
   - `{{attendees}}` — real names from step 4, comma-separated
   - `{{duration}}` — last timestamp in the transcript CSV
   - `{{summary}}` — each item from analysis `summary`, one bullet per line;
     **translate to the detected language if needed**
   - `{{topics}}` — one `###` section per discussion topic with key points as bullets;
     **write topic headings and bullet text in the detected language**
   - `{{action_items}}` — table rows from analysis `action_items`; use real names;
     if `deadline` is null write `—`; flag any deadline year that doesn't match
     the meeting year as a likely inference error;
     **translate task descriptions to the detected language if needed**
   - `{{unresolved}}` — each item from analysis `unresolved`, one bullet per line;
     **translate to the detected language if needed**

   Do **not** include a full transcript section — the notes should be concise.

7. **Write the output** to the same directory as the source files, named
   `meeting-notes.md`.

8. **Report** the output path, detected language, and flag anything that looked wrong
   (mis-identified speakers, garbled text, suspicious deadlines, etc.).

## Quality rules

- For `zh-TW` output: section headings, metadata labels, summary bullets, topic
  headings, and action item descriptions must all be in Traditional Chinese.
- Do not invent or infer information not present in the source files.
- Action item owners must be real names, not speaker IDs.
- If a deadline year is more than one year away from the meeting date, flag it
  with a ⚠ comment in the table.
- Preserve the source transcript verbatim in the Full Transcript section.
