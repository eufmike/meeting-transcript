# {{title}}

**Date:** {{date}}
**Attendees:** {{attendees}}
**Duration:** {{duration}}

---

## Summary

{{#each summary}}
- {{this}}
{{/each}}

---

## Discussion Topics

{{#each topics}}
### {{topic}}

{{notes}}

{{/each}}

---

## Action Items

| # | Task | Owner | Priority | Deadline |
| --- | --- | --- | --- | --- |
{{#each action_items}}
| {{index}} | {{task}} | {{assignee}} | {{priority}} | {{deadline}} |
{{/each}}

---

## Unresolved

{{#each unresolved}}
- {{this}}
{{/each}}

---

## Full Transcript

<details>
<summary>Expand transcript</summary>

| Time | Speaker | Text |
| --- | --- | --- |
{{#each utterances}}
| {{start}} | **{{speaker}}** | {{text}} |
{{/each}}

</details>
