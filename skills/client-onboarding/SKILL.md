---
name: client-onboarding
description: Scaffold a new client project — repo, project-brain (CLAUDE.md + wiki), an internal access checklist, a scope-of-work doc, and a client-facing onboarding kit (intro one-pager, plain-language access walkthrough, draft protection agreement). Use when taking on a new client (including friends/family handing over an existing site), so every client gets the same proven discipline instead of starting from scratch each time.
---

# Client Onboarding

Everything here is templated directly from the WePipe project (2026-08),
the first real client run through this whole process end-to-end — real
site built, real bugs found and fixed via the audit toolkit, real
deploy verified live. This skill exists so the next client (starting
with friends/family "hot leads") gets that same proven discipline
without rebuilding it from memory each time.

## What this skill does when invoked

1. **Gather the essentials first** — don't scaffold blind. Ask for
   (or use whatever's already provided in the invocation):
   - Client/business name, real contact info (phone, email, address)
   - What they actually do (services, service area)
   - Current site status: do they have one already (handing over an
     existing site) or starting fresh?
   - Who's involved and what they own (see Roles in the CLAUDE.md
     template — adapt the names/roles, don't just copy Jack/Miles)
   - Rough scope: is this a full rebuild, an audit + fix pass, ongoing
     SEO work, or something else? This shapes the scope-of-work doc.

2. **Create the project.** New folder under wherever the user's
   projects live (ask if unclear — don't assume `C:\Users\kierk\Projects\`
   is universal). `git init` it.

3. **Scaffold the project brain** from `templates/CLAUDE.md.template`
   and `templates/wiki/*.template` — fill in the placeholders (marked
   `{{LIKE_THIS}}`) with real info gathered in step 1. Don't leave
   placeholder brackets in the final files — either fill them in or
   explicitly mark them `[TBD — ask client]` if genuinely unknown yet,
   same convention WePipe's own CLAUDE.md used for the
   `[mock / real — update once live]` line before that got resolved.

4. **Create `SESSION-LOG.md`** with one dated entry noting the project
   brain was set up (see WePipe's `SESSION-LOG.md` 2026-08-04 entry for
   the reference format) and **`lessons.json`** with the empty
   `{"lessons": []}` shell.

5. **Generate the internal access checklist** from
   `templates/ACCESS-CHECKLIST.md` — this is for *us*, to track what's
   been sorted and what's still open. It is not client-facing (too much
   internal framing/jargon) — see step 5b for what actually goes to the
   client.

5b. **Generate the client-facing onboarding kit** — three documents,
   meant to actually be sent, not just exist:
   - `templates/WHAT-WE-DO.md` — a short, plain-language intro: who
     Junefruit is, the two service tracks (refresh existing site vs.
     full rebuild), what the client can expect from us.
   - `templates/ACCESS-WALKTHROUGH.md` — step-by-step, client-facing
     (not the internal checklist from step 5) instructions for GBP,
     GA4, GSC, and domain/DNS access. Plain language, no jargon, real
     click-paths. Fill in `{{YOUR_TEAM_EMAIL}}` with the real address
     access requests should go to before sending.
   - `templates/CLIENT-PROTECTION-AGREEMENT.md` — plain-language terms
     covering what we commit to (won't touch what's working without
     sign-off, never fabricate content, access not ownership, which
     service track applies). **This one carries a permanent warning
     that it's a draft, not a finished legal document** — never remove
     that warning, and always tell the user it needs an actual
     attorney's review before anyone signs it, even if they seem eager
     to skip that step.

6. **Generate a scope-of-work doc** from
   `templates/SCOPE-OF-WORK.md` — even for a free/discounted
   friends-and-family job, get *something* in writing: what's being
   done, rough timeline, who owns what. This is what prevents scope
   creep and protects the relationship, not a formality. This is a
   different document from the Client Protection Agreement (step 5b) —
   that one covers trust/access, this one covers deliverables/timeline/
   cost. Both matter; don't treat one as covering the other.

7. **If they already have a live site** (handoff scenario, not a
   fresh build): recommend running `audit.py` (from this repo) against
   their current site as literally the first real step — it becomes
   both a diagnostic and the actual initial scope-of-work content, same
   as it would for a cold prospect.

## What NOT to do

- Don't silently invent NAP data, service details, or scope — if
  something's genuinely unknown, mark it `[TBD]` and flag it back to
  the user, same discipline as WePipe's schema/testimonials work.
- Don't skip the access checklist or scope doc because "it's just a
  friend" — that's exactly the situation where an unwritten
  understanding causes the most damage later.
- Don't copy WePipe's actual business specifics (We Pipe LLC's real
  phone/address/roles) into a new client's files — those templates have
  the real content stripped to placeholders on purpose.
- Never strip or soften the legal-review warning at the top of
  `CLIENT-PROTECTION-AGREEMENT.md`, and never tell a user it's ready to
  sign as-is. A confident-sounding draft with a real gap in it (missed
  liability, IP, or termination language) is worse than no document at
  all — that warning is what keeps this template from becoming that.

## Stack default

Astro (static-first) + Cloudflare Pages, same as WePipe — proven
end-to-end tonight (build → GitHub → Cloudflare auto-deploy → verified
live). Don't re-litigate this choice per client unless there's a real
reason to (e.g. the client needs a CMS a static site can't reasonably
serve) — ask if genuinely uncertain, don't assume silently either way.
