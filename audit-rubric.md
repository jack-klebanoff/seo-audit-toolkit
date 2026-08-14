# Audit Scoring Rubric

## The three categories
Every audit scores three categories, each starting at 10.0:
1. Rendering & Technical Foundation
2. Local Signals (NAP/GBP)
3. Content, Trust & Depth

## Point deductions/additions
- Immediate (critical) finding: -1.5
- Needs Work finding: -0.6
- Confirmed Strength: +0.5

Overall score = average of the 3 category scores, clamped at a 10.0 ceiling
if the raw math exceeds it.

## What each category actually checks

**Rendering & Technical:** raw-vs-rendered content gap (JS-hidden content),
schema (JSON-LD) presence and validity, meta title/description hygiene
(length, no placeholders, no typos), robots.txt validity (no leftover
placeholder domains), heading structure, broken links, indexing status.

**Local Signals (NAP/GBP):** NAP consistency — compare the phone/address
shown on the site against the Google Business Profile and any third-party
citations (BBB, etc.). Map pack presence — search "[service] [city]" for
every real market served, note if they appear in the 3-pack. Review count
and rating, pulled from GBP directly. Listing accuracy (hours, categories,
duplicate/conflicting listings).

**Content, Trust & Depth:** named owner/credentials present (E-E-A-T), FAQ
content covering real buyer questions, page depth and uniqueness (spot-check
several location/service pages for templated "swap the town name" content
vs. genuine local detail), pricing transparency, real photography vs. stock.

## Finding format
Every finding gets written as:
- Title + location/scope tag + point delta
- A "Plain English" one-line translation for a non-technical owner
- Impact: what it's actually costing them
- Action: the specific fix
- (Once we have a real completed client story, add a "What We Did For
  [Client]" line on comparable findings — not yet, we don't have one)

## Competitive table
Pull review counts for 3-5 named local competitors in the same market,
listed alongside the prospect's own count — this is usually the single
most persuasive part of the report.

## Priorities section
Group open findings into blocks ordered by leverage, not by calendar date.
"Stop the bleeding" first (things capping every other fix), then the
highest-ROI lever, then content, then deeper structural work. Each block
gets a one-line "why this matters."

## Strengths section
Include a "what's already working" section (+0.5 each) so the report
doesn't read as pure criticism.
