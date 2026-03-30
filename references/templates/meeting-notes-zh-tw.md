# {{title}}

**日期：** {{date}}
**出席者：** {{attendees}}
**時長：** {{duration}}

---

## 摘要

{{#each summary}}
- {{this}}
{{/each}}

---

## 討論議題

{{#each topics}}
### {{topic}}

{{notes}}

{{/each}}

---

## 行動事項

| # | 任務 | 負責人 | 優先級 | 截止日期 |
| --- | --- | --- | --- | --- |
{{#each action_items}}
| {{index}} | {{task}} | {{assignee}} | {{priority}} | {{deadline}} |
{{/each}}

---

## 待解決事項

{{#each unresolved}}
- {{this}}
{{/each}}

