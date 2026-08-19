---
name: generate-area-pages
description: Research and write a real, non-templated area page (and its per-service pages) for one town or neighborhood, following the content-bar hard rules and the boiled-down, business-connection-first style. Use when asked to "build out [neighborhood]," "add an area page for X," or to continue a named rollout order across multiple neighborhoods.
---

# Generate Area Pages

Built 2026-08-19, after manually building 25 real pages across 5 NYC
neighborhoods for WePipe (Ridgewood, Bushwick, Bed-Stuy, Williamsburg,
Greenpoint) using a consistent process, by hand, one neighborhood at a
time. This packages that proven process into a repeatable skill,
closing a gap flagged independently by two sources the same week: the
Junefruit Operating Framework document and a real client meeting with
Mario, both naming "a repeatable skill that builds truly unique area
page content" as the actual bottleneck to solve before scaling.

This is the WePipe implementation of a client-agnostic idea. The exact
schema fields below (`introParagraph1Entities`, `sourceFacts`, etc.)
match WePipe's `content.config.ts`. A future client with a different
schema needs the same *process*, adapted to their actual field names,
not a copy-paste of WePipe's exact JSON shape.

## Before starting: confirm cadence, don't assume it

Ask (or recall from context) how the user wants this sequenced if
multiple neighborhoods are queued: one full neighborhood (area hub +
every service page) before starting the next, or some other order.
Don't default to bulk parallel generation for the research-and-write
step itself, judgment calls about what makes each neighborhood
genuinely distinct are being made live here, and a batch run risks
baking the same mistake into every page before anyone catches it. See
`junefruit-hq/CLAUDE.md`'s "copy-reference-site-verbatim" lesson and
the parallel-spawning discussion logged in WePipe's own session
history, 2026-08-18, for the reasoning. Mechanical cleanup passes
(like a retroactive style-rule fix) are a different case and do
parallelize fine.

## What this skill does when invoked

1. **Real research, two focused searches minimum.** One for housing
   stock, building era, and architectural history relevant to the
   trade (plumbing/HVAC/mechanical work cares about construction
   materials and building type, not general trivia). One for real
   boundaries, landmarks, and named streets. A third search for any
   *recent* landmark designation (a historic district named in the
   last few years) is worth doing every time, it tends to produce the
   single strongest, most citable, most specific hook a page can have.

2. **Find the genuinely distinguishing angle before writing anything.**
   Compare against every neighborhood already built. The whole point
   is that no two pages should tell the same story. Real examples from
   this project: Ridgewood is one uniform rowhouse boom; Bushwick adds
   a second building type (converted industrial lofts) on top of
   rowhouses; Bed-Stuy is older and taller (English-basement brownstones)
   than either; Williamsburg has three real building types including
   new construction; Greenpoint's real story is that building quality
   varies block to block *within* one historic district, not a single
   uniform era. If the honest research doesn't turn up a genuine
   difference, say so rather than force one.

3. **Write boiled down, not a history essay.** Real, cited facts only,
   but every sentence should tie back to what the building type or era
   actually means for plumbing, HVAC, or mechanical work, not general
   neighborhood trivia for its own sake. This was a direct correction
   from the user mid-project (2026-08-18): early drafts leaned too hard
   into Dutch-settlement-era history that had nothing to do with the
   business. Keep narrative length well above the 750-character floor
   but don't pad it back toward that length with filler.

4. **Never use em dashes, en dashes, or double-hyphens ("--").** Strict
   rule as of 2026-08-18 (`CLAUDE.md` Section 9, `lessons.json`), applies
   to every field that renders on the page (direct answer, meta
   description, both intro paragraphs, every FAQ question and answer).
   `sourceFacts` and `_status` are internal notes never rendered, they
   don't need to follow this, but keeping them clean too is good
   practice. Restructure with a period, a comma, or a colon instead,
   never fabricate urgency or filler to avoid a dash, just write the
   sentence the way a person actually would.

5. **Hit the hard floors, with margin, from the start.** 15+ named
   local entities and 8+ FAQs (4 evergreen: cost/scope/timing/who-performs,
   then 4+ town-specific) are hard gates in `content_bar_check.py`. The
   entity count is the sum of `introParagraph1Entities` and
   `introParagraph2Entities`, not deduplicated, and only counts entities
   that are actually present in the paragraph text, a declared entity
   the checker can't find in the prose is flagged as an unverified
   claim, not silently ignored. Aim for 16-18 combined and 8-9 FAQs on
   the first draft rather than the bare minimum. Every entity must be
   real and traceable to `sourceFacts`, never invented to pad the count.

6. **Same pattern for every service page (plumbing, HVAC, mechanical,
   green solutions) within the neighborhood.** Each one needs its own
   distinct angle *within* the neighborhood's overall story, not a
   re-skin of the area hub page with the service name swapped in.
   Reuse the neighborhood's real, already-sourced entities across the
   service pages rather than researching each one from scratch, cite
   `already cited in <town>.json` in `sourceFacts` when doing so.

7. **Run the checks in this order, fix and re-check before moving on:**
   - `content_bar_check.py --data <file> --out <name>-cb.md` from
     `seo-audit-toolkit`, for every file. If it fails on entity count
     or FAQ count, add back real entities already in `sourceFacts`
     (weave them into the actual sentence, not just the array) or add
     a real town-specific FAQ, don't invent new facts to pad it.
   - A content-qc style self-review: does every specific claim trace to
     a `sourceFacts` entry? Flag anything that doesn't, the same
     standard the `content-qc` skill applies, run that skill directly
     for a wave if it's large enough to risk source facts blurring
     together in one context.
   - `grep -c -- '--' <file>` on every file, confirm zero.
   - `npm run build` (or the client's equivalent), confirm it compiles
     clean and the new routes actually appear in the output.
   - `site_coverage_index.py --content-dir <path>` from
     `seo-audit-toolkit`, confirm zero slug collisions and zero
     duplicate-content pairs against the whole site, not just the new
     pages.

8. **Confirm hub-linking, don't assume it's automatic.** On WePipe,
   `/areas` and each service's index page are dynamically generated
   from the content collection, so a new town appears automatically
   with no manual edit. Verify this is actually true for whatever
   site is being worked on rather than assuming every site is built
   this way, an orphaned page is a real, previously-logged failure
   mode (`no-orphan-area-pages` in `lessons.json`).

9. **Report back plainly**, which neighborhood, how many pages, the
   real distinguishing angle used and why, pass/fail on every check,
   and don't claim something is done until it's actually been built
   and verified, not just written.

## What NOT to do

- Don't fan out multiple neighborhoods' research-and-write step in
  parallel by default, see the cadence note above.
- Don't reuse a previous neighborhood's angle just because it's easier,
  a page that's technically unique but tells the same kind of story as
  the last one is exactly the "generic with borrowed local names"
  failure `content-qc` exists to catch.
- Don't invent entities, statistics, or trade claims to hit the hard
  floors. Every fact traces to real research or is explicitly,
  honestly labeled as general trade knowledge, never presented as
  independently cited when it isn't.
- Don't skip the build/coverage checks because the content_bar_check
  passed, structure passing and the page actually working are two
  different checks.
- Don't treat the strict no-dash rule as optional or as only applying
  to new content going forward, it was applied retroactively to every
  existing page the same night it was introduced.
