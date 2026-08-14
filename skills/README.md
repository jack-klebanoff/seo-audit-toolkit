# Skills

Backed-up source copies of every reusable Claude Code Skill (process/
workflow) built while working on client projects. Standing convention as
of 2026-08-13: any process worth reusing gets saved here with clear
naming, not left living only on one machine.

## Why this exists

Claude Code Skills have to physically live at `~/.claude/skills/<name>/`
(user-level) or `<project>/.claude/skills/<name>/` (project-level) on
whatever machine is using them — that's just how Claude Code finds and
runs them. This folder is **not** that live location; it's the backup and
source of truth, so:
- Nothing is lost if a machine changes
- Anyone else on the team (Jack, Miles) can pick up the same skill
- Skills can be revisited and edited later without hunting through
  whichever machine originally built them

## How to actually use a skill from here

Copy the skill's folder to your own `~/.claude/skills/`:

```
cp -r skills/<skill-name> ~/.claude/skills/<skill-name>
```

Then it's available in Claude Code on your machine as `/<skill-name>`.

## Current skills

| Skill | Purpose |
|---|---|
| [`briefing`](briefing/SKILL.md) | Plain-language status narrative — before starting work (oriented) or wrapping up (recap). Not a file dump; a human-readable briefing. Built 2026-08-13 during the WePipe project. |

## Editing a skill

Edit the copy here, then re-copy it over the live version at
`~/.claude/skills/<name>/` (or wherever it's installed) to update it.
Keep this folder as the source of truth going forward — if you edit the
live version directly, copy the change back here too.
