---
name: save-that
description: Immediately captures whatever was just discussed — a strategy decision, a standing preference, a project fact — into durable storage the moment it's said, instead of waiting for end-of-session wrap-up. Triggered by "save that," "remember that," "make sure that's saved," "log that," or equivalent phrasing pointing at the preceding exchange. Use whenever the user flags something mid-conversation as worth keeping.
---

# Save That

Built 2026-08-15, at the user's explicit request, after he described the
real problem this solves: "I need to know that every time I talk to you,
you are saving it. Otherwise I'm going to end up saying the same stuff a
bunch of times." Existing end-of-session discipline (`SESSION-LOG.md`,
`wiki/active-priorities.md`, the `briefing` skill's wrap-up mode) already
captures a lot — but only at the END of a session. This closes the gap:
immediate capture, the moment something worth keeping gets said, not
whenever the session happens to wrap up (which might not happen the way
you expect, or might get compacted/summarized before it does).

## Two separate destinations — this is the core judgment call

Junefruit's memory isn't one system, it's two, and this skill's real job
is picking the right one (or both):

1. **This repo's own wiki / SESSION-LOG** — for anything specific to the
   project this session is running in: a decision, a fact, a deadline, a
   piece of strategy that only makes sense in context of this client or
   this codebase. Only visible to sessions that start in this repo.
2. **Claude Code's own cross-session memory** (`~/.claude/projects/<id>/memory/`,
   documented in this environment's own system instructions) — for
   anything about the user himself, a standing preference/feedback rule,
   or a fact that should follow him regardless of which repo or project
   he's working in next. This is the layer that actually solves "I don't
   want to repeat myself" for things that aren't project-specific.

Many things are genuinely both — e.g. "always sequence rollout phased,
one service at a time" is both a fact about why this project's phased
rollout works AND a standing preference about how the user likes to
work in general. Save to both when that's true; don't force a single
choice when the content doesn't fit one.

## What this skill does when invoked

1. **Identify what "that" refers to.** Default: the most recent
   substantive exchange (the point the user just made, or the point
   right before their "save that"). If the conversation has covered
   several distinct things since the last save point and it's genuinely
   ambiguous which one they mean, ask — one quick question, not a menu.
   Don't guess wrong and save the wrong thing silently.

2. **Decide if there's actually something durable here.** Per the
   existing memory system's own exclusion list: not code patterns
   derivable from reading the repo, not git history, not ephemeral
   in-progress task state. If "save that" points at something that's
   already obvious from the code or that won't matter next session, say
   so plainly rather than manufacturing an entry to seem responsive.

3. **Classify: repo-local, cross-session memory, or both** (see above).

4. **Check for an existing entry to update first**, in whichever
   destination(s) apply — same rule the memory system already states
   explicitly ("check if there is an existing memory you can update
   before writing a new one"), extended here to wiki files too. Don't
   create a near-duplicate wiki page next to an existing one just
   because it's faster than reading the existing one first.

5. **Write it:**
   - Repo-local → the right wiki page (per that repo's own `CLAUDE.md`
     wiki map) if it's a standing fact/strategy, or a dated
     `SESSION-LOG.md` entry if it's a this-session event/decision. Some
     things are both — a decision AND a fact that should persist past
     this session's log entry.
   - Cross-session → follow the memory system's own format exactly:
     frontmatter (`name`, `description`, `metadata.type`), one of the
     four real types (user / feedback / project / reference — not a
     fifth invented category), a body that leads with the rule/fact
     then **Why:** and **How to apply:** lines where those apply, and an
     index line added to `MEMORY.md`.

6. **Confirm back, concretely.** Not just "saved" — say *where*
   ("saved to `wiki/seo-strategy.md` and as a standing feedback memory
   about rollout pacing") so the user can actually verify the thing
   he's anxious about — that it really happened — without having to go
   check himself.

## What NOT to do

- Don't wait for "end session" / wrap-up to do this — that's the whole
  problem this skill exists to solve. Act immediately when triggered.
- Don't invent a memory or wiki entry when there's nothing genuinely
  durable in what was just said — an honest "nothing new to capture
  there, that's already covered in X" is correct, not a failure to be
  responsive.
- Don't silently pick only one destination when something is genuinely
  both project-specific and a standing personal preference — under-saving
  recreates the exact problem this skill exists to fix.
- Don't create a duplicate wiki file or memory entry when an existing
  one already covers the topic — update it instead, same as every other
  skill in this toolkit is expected to.
- Don't over-format a quick capture into a big production — this is
  meant to be low-friction, the same "capture stays frictionless"
  principle `process the inbox` already runs on.
