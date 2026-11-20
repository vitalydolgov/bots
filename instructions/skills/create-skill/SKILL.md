---
name: create-skill
description: Use this when the user asks you to create, update, or delete a skill.
---

To create a skill for this agent:

Write the skill into your workspace, under .agents/skills/<skill-name>/SKILL.md. Paths passed to the file tools are relative to the workspace root, so use exactly `.agents/skills/<skill-name>/SKILL.md`. Skills are loaded when the agent starts, so a skill you write now is available from the next run, not this one.

Structure:
A skill is a directory, not a single file. Keep SKILL.md for instructions and put everything else beside it:

my-skill/
├── SKILL.md          # required: metadata + instructions
├── scripts/          # executable code the agent runs
├── references/       # documentation loaded on demand
└── assets/           # templates, data files

- Do not inline scripts or long reference material in SKILL.md. Put code in scripts/ and reference it by relative path (scripts/foo.py); put detailed docs in references/.
- SKILL.md is loaded whole when the skill activates — keep it under 500 lines. Move detail to references/ and link it.
- Reference files relative to the skill root, one level deep. Avoid nested reference chains.
- scripts/ should be self-contained or document their dependencies, with helpful error messages and edge cases handled.

SKILL.md starts with YAML frontmatter, then the body:

---
name: refund-policy
description: The refund rules. Use when a customer asks for a refund.
---

Refund a customer only when the order is under 30 days old.

Rules:
- name: lowercase letters, digits and hyphens, at most 64 characters. The directory name must match the skill name.
- description: what the skill is and when to use it. The model sees only the name and description until it loads the skill, so write it as a trigger, not a summary. At most 1024 characters.
- The body is the procedure the model follows once it decides the skill applies. Keep it focused; it is loaded on demand with the load_skill tool.
- Files beside SKILL.md stay in place and are available to you.

Update a skill by editing its SKILL.md in place; keep the diff minimal. Delete a skill by removing its whole directory, not just SKILL.md. Skills you write are picked up from the next run.
