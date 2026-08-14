---
name: site-maintenance
description: Recurring health check for a client whose site is already live — re-run audit.py, diff against the last check with diff_audit.py, flag stale content, and log it in the client's own wiki. Not for prospects (use prospect-audit for that). Use for periodic/scheduled site upkeep, or when asked to "check on [client]'s site," "run maintenance," or "is anything broken on [client]'s site."
---

# Site Maintenance

`prospect-audit` is for selling — a one-shot check on someone who isn't a
client yet. This is the opposite job: an existing, already-live client,
checked on a recurring basis, where what matters isn't the score in
isolation but **what changed since last time.** Built 2026-08-14, the
same day as `prospect-audit`, once it became clear "audit the site" and
"maintain the site" are different enough jobs to need different homes for
their output — a prospect's audit data should never live anywhere near
this repo, but a client's own maintenance history absolutely belongs in
*their* project, tracked over time like any other real record.

## The one rule that matters: where data lives

This is the opposite of `prospect-audit`'s rule, on purpose:

- **`prospect-audit`** output stays local and gitignored in *this* repo —
  the lead isn't a client, there's nothing to track long-term yet.
- **`site-maintenance`** output goes into the *client's own project repo*
  — `wiki/maintenance/` — and gets committed there like any other real
  project record, the same way `SESSION-LOG.md` and `wiki/
  analytics-insights.md` already are. This is their site's health
  history, not prospect data passing through.

If it's unclear whether a given site is "a client" (tracked, committed)
or "a prospect" (gitignored, disposable) — ask. Don't guess either way.

## What this skill does when invoked

1. **Confirm the client and locate their project repo** — e.g.
   `wiki/maintenance/` inside `C:\Users\kierk\Projects\<client-repo>`.
   Create the `wiki/maintenance/` directory if this is the first run for
   this client.

2. **Get the live URL list.** Check `wiki/page-inventory.md` first if the
   client project has one populated; otherwise ask. Same "homepage plus
   a few key pages" guidance as `prospect-audit` — more pages checked is
   more thorough, but don't demand an exhaustive crawl.

3. **Find the last snapshot, if any.** List `wiki/maintenance/*-audit.json`
   in the client repo, sorted by date. If one exists, that's `--old` for
   the diff step later. If this is the first run, say so plainly — a
   baseline with nothing to compare against is a normal, expected state,
   not a problem.

4. **Run the audit**, from this repo, against the client's real live
   site:
   ```
   python audit.py --urls <client>-urls.txt --name "<Client Name>" \
       --out <YYYY-MM-DD>-audit.md --json-out <YYYY-MM-DD>-audit.json \
       [--phone "..."] [--address "..."]
   ```
   Then move both output files into the client repo's
   `wiki/maintenance/` — this repo's own `.gitignore` patterns
   (`*-audit.md`, `*-audit.json`) exist so prospect data doesn't leak in
   here; they'd also swallow a client's maintenance record if it were
   left sitting in this repo, which is exactly why it doesn't stay here.

5. **Diff against the last snapshot**, if one existed (step 3):
   ```
   python diff_audit.py --old wiki/maintenance/<prev-date>-audit.json \
       --new wiki/maintenance/<YYYY-MM-DD>-audit.json \
       --out wiki/maintenance/<YYYY-MM-DD>-diff.md
   ```
   **Lead with anything in "pages that stopped loading" — that's the
   single most urgent signal `diff_audit.py` produces**, more urgent
   than the score. Report the full diff summary back in chat: score
   delta, new findings, worsened findings, resolved findings. Don't just
   say "ran the check, see the file."

6. **Run remediation on anything new and auto-fixable:**
   ```
   python remediate.py --audit-json wiki/maintenance/<YYYY-MM-DD>-audit.json \
       --out wiki/maintenance/<YYYY-MM-DD>-remediation.md [--business-type <Type>]
   ```
   Same rule as always: this generates paste-in fixes for a human to
   apply, never applies them itself, never fabricates a placeholder
   value.

7. **Check content staleness — mechanically, not by guessing.** Use
   `git log -1 --format=%ad -- <content-directory>` in the client repo
   (e.g. `src/content/` for an Astro project) to find when content was
   last actually touched. If it's been longer than a reasonable
   threshold (60-90 days is a reasonable default; ask if the client has
   a different cadence in mind), flag it as **"worth considering a new
   post"** — a nudge based on a real, checkable fact (time since last
   content commit), not an invented topic suggestion. Don't generate
   specific blog post ideas here; that needs real judgment about what
   the business should say, which this mechanical check can't provide.

8. **Stub the credentialed checks honestly.** GA4, GSC, Google Business
   Profile, and true external backlink monitoring (who links *to* the
   client, not the same-domain outbound links `audit.py` already checks)
   all need real API access this toolkit doesn't have for any client yet.
   Include a clearly-labeled section in the maintenance summary noting
   each one as **"not yet — needs [GA4 API access / GSC API access / GBP
   API access / a backlink data source]"** rather than omitting them
   silently or faking a check. This keeps the report's shape ready for
   when access exists, without pretending it exists now.

9. **Log it.** Append a dated entry to the client's `wiki/
   analytics-insights.md` (it's already scoped as "every data pull,
   dated" — a technical health pull fits) summarizing: score delta,
   anything urgent (pages down), new/resolved/worsened findings, the
   staleness flag, and the stub section from step 8. Keep it as short as
   the format the rest of that file already uses — this is a log entry,
   not a full report dump.

10. **Commit the client repo's own changes** (the new maintenance
    snapshot files, the diff/remediation reports, the wiki update) —
    unlike `prospect-audit`, this data is *meant* to be tracked. Follow
    normal commit discipline: show the diff, write a real commit
    message, don't push without confirming (same as any other commit in
    this project).

## Cadence

This skill doesn't schedule itself. For actual recurring, unattended
runs, use the `schedule` skill (or `/loop` for a session you're keeping
open) to invoke this on a cadence — weekly is reasonable for an active
site, monthly for a stable one. Don't build custom scheduling logic here;
the scheduling primitives already exist, this skill just needs to be
invocable on demand.

## What NOT to do

- Don't write maintenance output into *this* repo (`seo-audit-toolkit`)
  — see "The one rule that matters" above. If a run accidentally leaves
  files here, move them to the client repo and clean up before
  finishing, don't just leave them for `.gitignore` to catch.
- Don't fabricate GA4/GSC/GBP/backlink data, and don't invent specific
  blog-post topics — the staleness check is a time-since-last-content
  fact, not a content strategy.
- Don't silently apply `remediate.py`'s generated fixes to the client's
  live code — same human-review rule as everywhere else in this toolkit.
- Don't skip surfacing "pages now failing" prominently — a site that
  went down between checks is the entire reason this skill exists,
  don't let it get buried under a routine score delta.
- Don't push the client repo's commit without explicit confirmation,
  even though committing is expected here (see step 10) — pushing is
  still a separate, confirmed action per this project's own norms.
