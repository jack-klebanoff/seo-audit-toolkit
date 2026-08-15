---
name: prospect-audit
description: Run a complete cold-outreach SEO audit on a prospect's website — audit.py, then remediate.py, then a drafted outreach email and/or cold-call script, then logging the lead in junefruit-hq's pipeline tracker — as one process instead of chaining it all by hand each time. Use when starting outreach on a new prospect/lead, or asked to "audit this site," "run the toolkit on X," "check out a prospect," or "give me something to say on a call."
---

# Prospect Audit

Turns the two standalone scripts in this repo (`audit.py`, `remediate.py`)
into one repeatable process with a deliverable at the end: a scored
report, a remediation plan, and a draft outreach email and/or cold-call
script — not just two files sitting in a folder. Built 2026-08-14, after
`remediate.py` reached schema + canonical + broken-link coverage, because
the scripts themselves were solid but running them was still a manual,
easy-to-forget-a-flag routine. The cold-call script was added the same
day, once it became clear phone outreach needed the same "never overclaim
beyond what the audit found" discipline as the email.

## Where the scripts live

`audit.py` and `remediate.py` are at the root of this repo
(`seo-audit-toolkit`). This skill file may get copied to
`~/.claude/skills/prospect-audit/` on a given machine — that copy does
NOT include the scripts. If the toolkit repo's location on this machine
isn't already known from context, ask, don't assume
`C:\Users\kierk\Projects\seo-audit-toolkit` is universal (same rule as
`client-onboarding`'s "don't assume the projects folder" note).

## What this skill does when invoked

1. **Gather the essentials — don't run blind.**
   - Business name.
   - Target URLs: homepage at minimum, plus a few key interior pages
     (a service page, a location page) if the user has them handy. More
     pages checked = a more credible report, but one page is enough to
     start.
   - Phone / address — **only if the user already has them on hand.**
     Do not look these up or guess them. If not provided, skip
     `--phone`/`--address` entirely and let Category 2 (NAP) stay a
     blank manual checklist item, same as `audit.py` does on its own
     when those flags are omitted.
   - A rough sense of the business's trade (Plumber, HVACBusiness,
     etc.) if known — improves the schema fix's `@type` later. Default
     to the always-valid `LocalBusiness` if unknown; don't guess a
     specific subtype.

2. **Write the URL list** to a `<slug>-urls.txt` file (one URL per
   line) — this naming pattern is already covered by `.gitignore`
   (`*-urls.txt`), so it's safe to write at the repo root without risk
   of committing prospect data.

3. **Run the audit:**
   ```
   python audit.py --urls <slug>-urls.txt --name "<Business Name>" \
       --out <slug>-audit.md --json-out <slug>-audit.json \
       [--phone "..."] [--address "..."]
   ```
   Check first whether `playwright` is installed
   (`python -c "import playwright"`). If not, mention to the user that
   installing it (`pip install playwright && playwright install
   chromium`) enables the raw-vs-rendered content check — per
   `audit.py`'s own docstring, this is "often the single most
   persuasive finding for a prospect whose site leans on JavaScript
   frameworks." Don't block on it — just flag it, once.

4. **Surface the real findings in chat before moving on** — don't just
   silently generate files and move to remediation. Read the JSON
   output and report back: the Category 1 score, and the 2-3 most
   significant findings (Immediate severity first). This is the point
   of wrapping the scripts — the human running this should know what
   was found, not just where the file landed.

5. **Run remediation:**
   ```
   python remediate.py --audit-json <slug>-audit.json \
       --out <slug>-remediation.md [--business-type <Type>]
   ```
   Report back the counts (schema fixes / canonical fixes / broken
   links flagged / other findings) the script itself prints.

6. **Draft the outreach** — don't just point at the files, write
   something usable. Ask whether the user wants an email, a cold-call
   script, or both (default to email if they don't say — it's the
   lower-friction ask). Either way, start from the same source: the
   `cold_outreach_snippet` field already in the audit JSON (Category 1
   only, deliberately worded not to overclaim), plus the real score and
   real top issue surfaced in steps 4-5.
   - Email: expand into a short, sendable message using
     `templates/outreach-email.template`.
   - Cold-call script: fill in `templates/cold-call-script.template` —
     it's a talk-through guide with an opener, the hook, common
     objections, a voicemail branch, and a close, not a word-for-word
     read. The only goal of the call is a confirmed email address to
     send the real report to, not a sale on the phone — the script is
     built around that, don't rewrite it into a harder pitch.
   - Either format: never invent a finding that isn't in the report,
     never state a specific number (score, page count) that isn't the
     one the tool actually produced, never fabricate urgency or a
     competitor comparison the audit didn't actually surface.

7. **Remind, don't gate:** Category 2 (Local Signals) and Category 3
   (Content, Trust & Depth) are still blank manual checklists in the
   report — they're two-thirds of the real methodology. Mention this
   once so the user can decide whether to spend a few minutes on a
   manual pass before sending, or send the Category-1-only outreach
   now and offer the full breakdown as the follow-up (which is exactly
   how the built-in snippet is worded). Don't insist on either — it's
   their call.

8. **Tell the user where everything landed** and remind them these are
   local-only, gitignored files (`*-audit.md`, `*-audit.json`,
   `*-remediation.md`, `*-urls.txt`) — normal, not an oversight, per
   this repo's "no client/prospect data lives in this repo" rule. If
   asked to commit or push, stop and flag that this would break that
   rule rather than doing it.

9. **Log the lead in the pipeline.** This is what turns a one-off audit
   into a tracked sales process. Find `junefruit-hq`'s `wiki/leads.md`
   (ask for the location if it's not already known from context — don't
   assume a path). Add a new row (or update an existing one if this
   business was already in the pipeline) with the real business name,
   contact info if known, source, status **Audited**, the real Category
   1 score, today's date, and a next action (e.g. "send outreach
   email"). This file is meant to be tracked in git and holds real
   contact info — unlike this repo's gitignored prospect data, don't
   avoid committing it there; that's `junefruit-hq`'s own convention to
   follow (private repo once it has a remote — see that file's own
   sensitivity note).

## What NOT to do

- Never fabricate a phone number, address, business type, or specific
  finding that isn't literally in the audit's own output — same
  never-fabricate discipline `remediate.py` follows for schema
  placeholders and broken-link comments.
- Never auto-send the outreach draft, and never make or dial a call.
  This produces material for the human to use themselves — same as
  `remediate.py`'s output is something a human pastes in, not something
  this tooling publishes or acts on.
- Don't overclaim in the outreach draft (email or call script) beyond
  what Category 1 alone supports — the tool's own snippet is worded
  that way on purpose (see `generate_outreach_snippet` in `audit.py`);
  don't "improve" it into a stronger claim the data doesn't back. This
  goes double for the call script's objection-handling lines — don't
  turn them into harder-sell pitches than what's drafted.
- Don't skip step 4 (surfacing findings in chat) just because the files
  exist — a folder of reports nobody read isn't the deliverable this
  skill exists to produce.
- Don't commit or push the generated prospect files — see step 8.
- Don't skip step 9 — an audit that never makes it into `wiki/leads.md`
  is invisible to the pipeline, which defeats the point of tracking it
  at all.
