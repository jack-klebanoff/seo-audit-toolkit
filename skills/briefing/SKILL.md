---
name: briefing
description: Give a plain-language status narrative — where things stand, what's being worked on, and where we're genuinely stuck. Use at the start of a session to get oriented, or at the end to wrap up. Not a bullet dump of files changed — a briefing a non-technical person could read and actually understand.
---

# Briefing

Produce a short, plain-language narrative status update, delivered directly
in chat — never as a saved file unless the user explicitly asks for one.
This is a spoken-style briefing, not documentation.

## Origin

This pattern came from a real status email drafted for "Mario" (a client's
mentor/methodology author) during the WePipe project on 2026-08-13. The
user's reaction: "that's the type of thing I'd like to read before we work...
and maybe another similar passage when we're wrapping up." That's the whole
spec — read it if you want the reference tone. It's in that project's
`SESSION-LOG.md` under the 2026-08-13 entries, and `CLAUDE.md` Section 6
wires this skill into that project's own session triggers.

## Two modes

Infer which mode from context (args, or where we are in the conversation) —
don't ask unless genuinely ambiguous.

**`start`** (forward-looking, used at the beginning of a work session):
- Where things stand right now
- What's actively in progress
- What's genuinely blocked or uncertain — not just "blocked," the real
  friction: an unresolved design question, an external dependency, a
  judgment call that hasn't been validated

**`wrap-up`** (backward-looking, used at the end of a work session):
- What actually got done this session
- What's still open
- Where we struggled, guessed, or made a judgment call worth flagging —
  don't sand this down to sound cleaner than it was

## Voice — this is the part that matters

- Write like you're catching a smart colleague up over coffee, not filing a
  report. Short sentences. Contractions are fine.
- No jargon dumps. If a technical thing matters, explain what it means in
  practice, not just its name (e.g. not "fixed the canonical tag issue" —
  "fixed a bug where every page was missing a technical tag that helps
  Google avoid seeing it as duplicate content").
- Structure loosely (a few labeled sections is fine, like the Mario email
  had "WePipe" / "The audit tool" / "Where we're struggling") but don't
  over-format into a rigid template every time — read like it was actually
  written for this specific update, not generated from a fixed shape.
- Always include genuine friction, not just wins. A briefing that's all
  good news isn't a briefing, it's a highlight reel. If nothing is
  genuinely uncertain or struggling, it's fine to say so plainly — don't
  manufacture a problem to seem balanced.
- Keep it tight. This is meant to be read in under a minute, not a full
  report — if there's a lot of ground to cover, pick what actually matters
  for getting oriented (or for wrapping up), not everything that happened.

## Sourcing the content

Pull from whatever's actually available and relevant — don't fabricate
status. In rough order of preference:
- If the current project has a `CLAUDE.md`/wiki system (active-priorities,
  SESSION-LOG, etc.), read those for real current state
- `git status` / `git log` for what's actually changed and uncommitted
- The live conversation itself — what's been discussed, decided, built,
  or left hanging this session
- If something is genuinely unknown (e.g. "did the other session finish
  X?"), say that plainly rather than guessing

## What this is NOT

- Not a replacement for `SESSION-LOG.md` or any other durable written
  record — those still get updated normally; this is a spoken-style
  layer on top, for a human, not a database.
- Not a place to ask "should I proceed?" or seek approval — it's a status
  narrative, not a checkpoint gate.
- Not something to save to disk by default — chat only, unless asked.
