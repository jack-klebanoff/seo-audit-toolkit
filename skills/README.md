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
| [`client-onboarding`](client-onboarding/SKILL.md) | Scaffold a new client project — repo, CLAUDE.md + wiki, an internal access checklist, a scope-of-work doc, and a client-facing onboarding kit (a "what we do" one-pager, a plain-language access walkthrough, and a draft protection agreement). Use for every new client, including friends/family handoffs. Built 2026-08-13, onboarding kit added 2026-08-14. |
| [`prospect-audit`](prospect-audit/SKILL.md) | Run `audit.py` then `remediate.py` then draft an outreach email and/or cold-call script, then log the lead in `junefruit-hq`'s pipeline tracker, as one process instead of chaining it all by hand. Use for cold-outreach on a new prospect/lead. Built 2026-08-14. |
| [`site-maintenance`](site-maintenance/SKILL.md) | Recurring health check on an *already-live* client — re-audit, diff against the last check, flag stale content, log to that client's own wiki. Never for prospects. Built 2026-08-14. |
| [`wave-qa`](wave-qa/SKILL.md) | Verify a bulk page launch ("wave") against six hard gates (HTTP status, schema, sitemap, hub-linking, meta uniqueness, duplicate content) before it ships, plus a content-bar structure check for area/town pages (`content_bar_check.py` — entity count, FAQ structure, narrative length; verified against synthetic data only so far). Promoted from WePipe's own `post-wave-qa.py`. Built 2026-08-14. |
| [`content-qc`](content-qc/SKILL.md) | Checks whether generated content stays faithful to its own declared `sourceFacts`, or invents specific-sounding claims with no real backing — advisory fabrication/grounding review, not a hard gate. Validated against constructed test cases (catches planted fabrication, no false positives on clean paraphrasing) but not proven at production scale. Built 2026-08-14. |
| [`juney-wake-up`](juney-wake-up/SKILL.md) | The "Juney wake up" morning-startup phrase — reads HQ + all active clients' state, runs a real live check (not just old notes) via `site-maintenance`, delivers it through `briefing`. GBP/GA4/live-tracking explicitly stubbed as "not yet" on purpose. Built 2026-08-15. |
| [`generate-area-pages`](generate-area-pages/SKILL.md) | Research and write a real, non-templated area page and its per-service pages for one town, following the content-bar hard rules and boiled-down, business-connection-first style. Packages the process proven manually across 25 real WePipe pages (5 NYC neighborhoods). Built 2026-08-19. |

## Editing a skill

Edit the copy here, then re-copy it over the live version at
`~/.claude/skills/<name>/` (or wherever it's installed) to update it.
Keep this folder as the source of truth going forward — if you edit the
live version directly, copy the change back here too.
