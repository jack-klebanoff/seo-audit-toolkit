---
name: juney-wake-up
description: The standing session-start routine for Junefruit — triggered by the phrase "Juney wake up" (or equivalent, e.g. "what's the status," starting a session at junefruit-hq). Reads current state across HQ and active clients, runs a real live check against any live client sites (not just yesterday's notes), and delivers a plain-language briefing. Use at the start of a work session, or whenever asked "where are we," "what's broken," "catch me up."
---

# Juney Wake Up

**Naming, for the record:** the assistant here is Claude Code — "Claudey"
to the user. "Junefruit" is the company (named after a friend's dog,
June). "Juney wake up" doesn't mean the assistant's name is Juney — it
means "Claudey and I start working on Junefruit." Built 2026-08-15,
end of a long session, at the user's explicit request for a repeatable
morning-startup routine instead of re-deriving context by hand each time.

This composes existing pieces rather than reinventing them: `briefing`
for the narrative delivery, `site-maintenance` for the real live check,
the existing `CLAUDE.md` session-start conventions for what state to
read. The new thing this adds is doing all three *together*, as one
named trigger, with a real health check instead of just reading
yesterday's log and hoping it's still accurate.

## What this skill does when invoked

1. **Read HQ state.** `junefruit-hq/CLAUDE.md` (conventions, client
   roster, skills index), the last few entries of its `SESSION-LOG.md`,
   and `wiki/leads.md` (pipeline status).

2. **Read each active client's own state.** For every client in the
   roster (currently: WePipe), that client's own `SESSION-LOG.md` and
   `wiki/active-priorities.md` — same as normal session start, just
   done for every active client in one pass instead of one at a time.

3. **Run a real live check — this is the actual point of "wake up"
   rather than just "read the notes."** For any client with a
   `wiki/maintenance/` history (site-maintenance has run before), run
   `site-maintenance` again now: real diff against the last snapshot,
   not a static report. This is what makes "what's broken" mean *right
   now*, not *as of whenever someone last happened to check*. If a
   client has no maintenance history yet, say so plainly rather than
   skipping the client silently.

4. **GBP / GA4 / other live tracking data — explicitly stubbed, not
   built.** The user is getting real API access sorted separately;
   don't build toward credentials that don't exist yet. When invoked,
   note plainly: "GBP/GA4 not yet connected for any client — this
   section will pull [review counts / traffic trends / whatever the
   real access ends up supporting] once real access exists." Do not
   fabricate or estimate anything here — an honest "not yet" beats a
   guessed number.

5. **Deliver it as an actual briefing, not a file dump.** Invoke the
   `briefing` skill (start mode) to narrate all of the above in plain
   language — what's good, what's broken, what happened last session,
   what's next. Don't just print steps 1-4's raw output.

## What NOT to do

- Don't skip step 3 (the live check) and just summarize old logs —
  that's a regular session start, not "wake up." The live check is the
  entire point of the distinction.
- Don't build any real GBP/GA4/tracking integration yet, even a small
  one — explicitly deferred until real access exists. A stub that's
  honest about being empty is correct; a guessed number is not.
- Don't log every "wake up" as its own `SESSION-LOG.md` entry — this is
  a read-and-report routine, not a state change. Normal end-of-session
  logging discipline still applies separately, at wrap-up.
- Don't treat this as HQ-only if invoked from inside a client repo —
  recognize the phrase either way and pull in HQ context regardless of
  which repo the session started in.
