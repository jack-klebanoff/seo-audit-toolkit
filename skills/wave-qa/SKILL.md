---
name: wave-qa
description: Verify a batch of newly-launched pages (a "wave") meets the six hard-gate standard before it ships — HTTP status, schema, sitemap inclusion, hub linking, meta uniqueness, cross-page duplicate content. Use after a bulk page launch (the area-page fan-out from Module 9/10), or when asked to "check this wave," "run wave QA," or "is this batch ready to ship."
---

# Wave QA

Promoted 2026-08-14 from WePipe's own `scripts/post-wave-qa.py` into
`seo-audit-toolkit` as `wave_qa.py` — same story as `audit.py`'s own
promotion: it was already fully client-agnostic (parameterized via CLI
flags, no hardcoded paths), just sitting in one client's repo instead of
the shared toolkit. See `junefruit-hq/CLAUDE.md` Section 2 for *why*
waves matter at all — this skill is the mechanical gate, not the
strategy.

**Why hard gates, not warnings:** a wave is a batch of pages launched
together specifically to build density of trustworthy pages fast. A
wave that ships with broken links, missing schema, or duplicate content
doesn't just fail one page — it undermines the credibility of the whole
batch, and there's no quiet do-over once Google's indexed it. That's why
`wave_qa.py` treats all six checks as pass/fail, not advisory.

## Where the script lives

`wave_qa.py` is at the root of this repo (`seo-audit-toolkit`). Same
rule as every other skill here: if the toolkit repo's location on this
machine isn't already known from context, ask — don't assume
`C:\Users\kierk\Projects\seo-audit-toolkit` is universal.

## What this skill does when invoked

1. **Gather the wave.** From the user or the client's own project:
   - The new page URLs launched this wave (homepage-relative or full
     URLs — one per line, real URLs, never guessed).
   - The hub/parent page(s) that should link to them (a service hub, a
     town-cluster hub — whatever the client's own hub-linking pattern
     is).
   - The sitemap URL (or local path).
   If any of these is unclear, ask — don't assume a URL pattern from
   the client's other pages.

2. **Run the check:**
   ```
   python wave_qa.py --urls wave-urls.txt --sitemap <sitemap> \
       --hubs hub-urls.txt --out wave-qa-report.md
   ```

3. **Surface the real result in chat, not just the exit code.** Report
   the pass/fail count, and for any failure, which of the six checks
   it failed and why — pulled from the actual report, not summarized
   away. A wave with failures is **not shippable** until it's 0 —
   state that plainly, don't soften it into "mostly good."

4. **This is real client history — log it, don't discard it.** Unlike
   `prospect-audit`'s gitignored scratch output, a wave-QA result for an
   existing client belongs in *that client's own repo*, tracked in git
   — same "client data stays with the client" rule `site-maintenance`
   follows. Save the report to `wiki/waves/<YYYY-MM-DD>-wave-qa.md` in
   the client's project (create the folder if it's the first wave
   checked there). If the client's `.gitignore` has broad `*-report.md`
   patterns that would swallow it, add a narrow carve-out — same fix
   already applied for `site-maintenance`'s `wiki/maintenance/`.

5. **If it fails, don't re-run blindly after a fix without re-verifying
   everything.** A fix for one check (e.g. adding a missing schema
   block) can't be assumed not to affect another (e.g. it could change
   page length enough to trip the duplicate-content threshold in an
   unrelated way). Re-run the full check after any fix, not just the
   specific failed item.

## What NOT to do

- Don't treat a failing wave as shippable with a caveat — the whole
  point of hard gates is that "mostly passed" isn't a passing wave.
- Don't fabricate hub URLs, sitemap locations, or page URLs — same
  never-guess discipline as every other skill here.
- Don't save wave-QA output into *this* repo (`seo-audit-toolkit`) —
  it's real client history, it belongs in that client's own project,
  same reasoning as `site-maintenance`.
- Don't silently skip re-verification after a fix (see step 5) — a
  partial re-check can miss a check that regressed from the fix itself.
