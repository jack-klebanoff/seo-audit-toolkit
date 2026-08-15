---
name: content-qc
description: Check whether generated content (an area/town page, a service page) actually stays faithful to its own declared source facts, or invents additional specific-sounding claims that aren't grounded in anything real. This is Layer 2 of content quality control — Layer 1 (content_bar_check.py, in wave-qa) checks structure; this checks fabrication risk and genuine local-specificity. Use before publishing any wave, or when asked to "check this content for fabrication," "is this page grounded," or "run content QC."
---

# Content QC (Layer 2 — Grounding & Fabrication Review)

**Validated 2026-08-14** against two constructed test cases before this
skill was considered done: one with two deliberately planted
fabrications (a fake historical event, a fake service-call statistic) —
both caught, both correctly quoted and flagged, the genuinely grounded
claims in the same paragraph correctly passed. A second, fully clean,
naturally-paraphrased example — zero false positives. This is evidence
the *process* works on constructed examples, not proof it's reliable at
production scale on real, more ambiguous content — treat accordingly,
same as `content_bar_check.py`'s own "synthetic data only" caveat.

This is the harder half of content quality control, flagged repeatedly
throughout 2026-08-14 as the real unsolved problem behind Junefruit's
whole trust strategy (see `junefruit-hq/CLAUDE.md` Section 2) — and
per the user directly: **this matters more than auditing a prospect's
site.** `prospect-audit` judges someone else's existing content;
this judges *ours*, before it ever reaches Google.

## What this actually checks — and what it deliberately does NOT

**Checks:** whether the written content stays faithful to a declared
list of source facts, or contains specific-sounding claims that aren't
traceable to anything provided. This is a fidelity check, not
independent fact-verification.

**Does NOT check:** whether the source facts themselves are true. No
tool available here can independently confirm "Wyncote's housing stock
is really 1920s-1960s" against reality — that has to come from a
trustworthy source (the client, someone with real local knowledge, a
verified data source) in the first place. **Garbage in, garbage out is
explicit and accepted**: this skill only catches a content-generation
step inventing *additional* detail beyond what it was actually given.
If the source facts themselves are wrong, this won't catch that — say
so plainly if asked, don't imply broader coverage than this has.

## Why this has to be advisory, not a hard gate

Unlike `wave_qa.py`'s six checks (deterministic, verified against real
pages), this is inherently a judgment call — the reviewer (an LLM,
possibly a dedicated subagent) reads prose and decides whether a claim
is grounded. That can be wrong in both directions: missing a real
fabrication, or flagging a legitimate paraphrase as unsupported. Treat
every output as **a flagged list for a human to actually look at**, the
same "advisory checklist" pattern `audit.py` already uses for Category
2/3 — never as a pass/fail gate the way Layer 1 is.

## Required input: `sourceFacts`

Extends the schema `content_bar_check.py` already documents. Each page
needs a `sourceFacts` array — short, specific factual statements the
content is allowed to draw from, e.g.:

```json
"sourceFacts": [
  "Ridgewood's rowhouses along Seneca Avenue and Fresh Pond Road date to the 1910s-1920s",
  "Many buildings in this era still run original cast iron waste lines",
  "The neighborhood sits near the old Ridgewood Reservoir",
  "Backflow prevention is a common concern given the area's older water infrastructure"
]
```

**This list must come from a real source** (the client, someone with
actual local knowledge, verified data) — never invented by whoever is
generating the page content. If it's unclear where a `sourceFacts` list
came from, ask before treating it as ground truth.

## What this skill does when invoked

1. **Get the content and its `sourceFacts` list.** Both required — if
   `sourceFacts` is missing, say so plainly and stop; reviewing content
   against nothing isn't a review, it's a guess.

2. **Read every specific/factual claim in the content** — not every
   sentence needs a citation (tone, transitions, and genuinely generic
   statements like "call us for a free estimate" aren't claims), but
   any statement that asserts something specific about the place, the
   housing stock, the business, or a practice needs to trace back to
   `sourceFacts`.

3. **Classify each claim:**
   - **Grounded** — clearly traceable to a specific source fact (quote
     which one).
   - **Ungrounded / fabrication risk** — a specific-sounding claim with
     no traceable source fact. Flag these individually, quote the exact
     sentence, and say plainly this needs human verification before
     publishing — don't soften it.
   - **Generic / non-claim** — not a factual assertion at all (tone,
     CTA, boilerplate). Not a problem on its own, but too much of this
     relative to grounded claims is itself a finding (see step 4).

4. **Assess grounding density** — roughly, what fraction of the
   substantive content is grounded vs. generic filler. A page that's
   90% generic-with-a-few-real-names-dropped-in is exactly the
   "technically unique but hollow" failure mode this whole layer exists
   to catch, even with zero outright fabrication.

5. **Report plainly, referencing the actual page:**
   - List every ungrounded claim, quoted directly, with a one-line note
     on why it reads as unsupported.
   - State the grounding density assessment in plain terms (e.g.
     "most of this paragraph ties directly to source facts" vs. "this
     reads as generic with borrowed local names").
   - Give a clear verdict — **ready**, **needs review** (some
     ungrounded claims or thin grounding), or **do not publish as-is**
     (multiple fabrication risks or mostly-generic content) — but frame
     it as a recommendation for the human to act on, not an automatic
     block.

6. **For a whole wave (multiple pages), consider spawning one review
   per page as a separate agent** (via the Agent tool) rather than
   reviewing serially in one context — matches the user's own stated
   expectation of "multiple agents with unique skills" for this kind of
   work, and keeps each review focused on one page's actual source
   facts instead of bleeding context between pages.

## What NOT to do

- Never treat this review's output as proof the content is accurate —
  it only proves internal consistency with a provided facts list, which
  itself might be wrong. Say this limitation out loud whenever reporting
  results, not just in this doc.
- Never invent a `sourceFacts` list to make a review possible — if one
  wasn't provided, stop and ask, don't fabricate the ground truth you're
  supposed to be checking against.
- Never treat "needs review" or "do not publish" as something to argue
  the content past — flag it, hand it to a human, move on.
- Don't skip step 6 for a large wave just because reviewing serially is
  easier to write — a single-context review of 10 pages risks the
  source facts blurring together across pages.
