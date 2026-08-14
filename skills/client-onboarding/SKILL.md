---
name: client-onboarding
description: Scaffold a new client project — repo, project-brain (CLAUDE.md + wiki), access checklist, and a simple scope-of-work doc. Use when taking on a new client (including friends/family handing over an existing site), so every client gets the same proven discipline instead of starting from scratch each time.
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

5. **Generate the access checklist** from
   `templates/ACCESS-CHECKLIST.md` — this becomes something to actually
   send the client (or walk through with them if it's a friend/family
   handoff). Don't skip this even for friends/family — access logistics
   were the single biggest source of friction/delay on WePipe (GBP
   verification stuck for weeks, DNS not cut over, GA4/GSC access not
   in hand) and that gets *worse*, not better, in an informal handoff
   where nobody wrote down what's needed.

6. **Generate a scope-of-work doc** from
   `templates/SCOPE-OF-WORK.md` — even for a free/discounted
   friends-and-family job, get *something* in writing: what's being
   done, rough timeline, who owns what. This is what prevents scope
   creep and protects the relationship, not a formality.

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

## Stack default

Astro (static-first) + Cloudflare Pages, same as WePipe — proven
end-to-end tonight (build → GitHub → Cloudflare auto-deploy → verified
live). Don't re-litigate this choice per client unless there's a real
reason to (e.g. the client needs a CMS a static site can't reasonably
serve) — ask if genuinely uncertain, don't assume silently either way.
