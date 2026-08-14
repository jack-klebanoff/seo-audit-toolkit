# SEO Audit Toolkit

A reusable, client-agnostic toolkit for two jobs:

1. **`audit.py`** — points at any live website (no repo access, no login,
   no permission needed) and scores it against a 3-category rubric. Two
   uses: cold-outreach sales ("here's exactly what's costing you leads")
   and ongoing QA on sites we've already built.
2. **`remediate.py`** — takes an `audit.py` JSON report and generates
   concrete, ready-to-paste fixes for whatever it can fix reliably (schema,
   canonical tags, and broken-link flags so far — more finding types over
   time).

See **`audit-rubric.md`** for the full scoring methodology this is built
on. No client/prospect data lives in this repo — it's a template and a
pair of scripts, meant to be pointed at whichever site you're working on
that day.

This repo has grown into the general home for reusable, cross-client
tooling — see **[`skills/`](skills/README.md)** for reusable Claude Code
Skills/processes (not just SEO-audit-specific ones), backed up here so
they're not stranded on one machine.

## Setup

```
pip install -r requirements.txt
# optional, enables the raw-vs-rendered content check in audit.py:
pip install playwright && playwright install chromium
```

## Usage

### Audit a site

```
python audit.py --urls prospect-urls.txt --name "Acme Plumbing" \
    --out acme-audit.md --json-out acme-audit.json \
    --phone "(555) 123-4567" --address "123 Main St, Anytown, ST 00000"
```

- `--urls` — a text file, one page URL per line (homepage + a few key
  interior pages)
- `--phone` / `--address` — optional; the business's *real* phone/address
  enables an automated on-site presence check for Category 2 (NAP)
- `--json-out` — optional; writes a machine-readable twin of the report,
  used as `remediate.py`'s input

### Generate fixes from an audit

```
python remediate.py --audit-json acme-audit.json \
    --out acme-remediation.md --business-type Plumber
```

- `--business-type` — the schema.org `@type` to generate (defaults to
  the always-valid `LocalBusiness`; use a specific subtype like
  `Plumber` or `HVACBusiness` when you know the trade)
- Reads `--phone`/`--address` back automatically from the audit JSON's
  `input_nap` field — no need to pass them twice

## Scope, honestly

- `audit.py` Category 1 (Rendering & Technical) is real, automated, and
  verified. Categories 2 (Local Signals) and 3 (Content, Trust & Depth)
  are mostly manual checklists — some items have automated presence
  hints (FAQ schema detection, cross-page content-similarity, NAP
  on-site presence), but genuine judgment calls (is this content
  actually good, does this business really have the reviews it claims)
  stay human on purpose.
- `remediate.py` currently generates schema and canonical tag fixes, plus
  a flagged entry per broken link. Broken links are a special case: the
  script has no way to know what a dead link *should* point to, so
  instead of a working replacement it generates a clearly-marked
  placeholder comment (the broken href, the problem, and the two safe
  manual options — fix the href or remove the link) — same
  never-fabricate discipline as schema's phone/address placeholders.
  Title/meta description are deliberately NOT auto-generated — that's
  real marketing copy, not markup, and this tool has no business
  fabricating it for a site it doesn't represent. Everything else gets
  flagged as a prioritized action item, not silently skipped.
- Neither script can touch Google Business Profile, review counts, or
  map-pack rankings — those need real Google API access this toolkit
  doesn't have, or in GBP's case, actual business-owner verification no
  tool can substitute for.

## Origin

Built while developing the WePipe project (`github.com/jack-klebanoff/wepipe`),
then moved here since it's meant to be used across every client, not just
one. Both scripts were verified against a real live site (Hercules Fence)
before and after every change, not just written and assumed correct.
