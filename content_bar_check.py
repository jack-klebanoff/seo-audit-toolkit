#!/usr/bin/env python3
"""
content_bar_check.py

Mechanically enforces the "hard rules" for area/town pages documented in
a client's own CLAUDE.md (Module 9 schema) -- BEFORE this script existed,
these were only checked by a human eyeballing the content. Nothing here
judges whether the content is actually GOOD (accurate, genuinely locally
specific vs. generic-with-names-swapped) -- that's a separate, harder,
still-unsolved problem (see junefruit-hq/CLAUDE.md Section 7's content-QC
gap). This is the objective, unambiguous layer: word counts, character
counts, required structure, internal consistency.

STATUS AS OF 2026-08-14: built and tested only against SYNTHETIC data
built to match the documented schema -- no real client has reached the
area-page rollout phase yet, so no real content exists in this format to
test against. Treat accordingly: this is verified to be internally
correct, not yet proven against a real production wave.

SCHEMA (matches WePipe's CLAUDE.md Section 7, "Town / service data file
schema", PLUS two additions this script needs to make the hard rules
mechanically checkable -- flagged explicitly since they're not in the
original documented schema verbatim):

    {
      "slug": "example-town",
      "name": "Example Town",
      "county": "Example County",
      "eraBucket": "post1960",
      "introDirectAnswer": "40-60 word answer-first paragraph",
      "introParagraph1": "~1,500 chars of real narrative",
      "introParagraph1Entities": ["Named Street", "Named Landmark", ...],
      "introParagraph2": "~1,500 chars, practitioner voice + cross-link",
      "introParagraph2Entities": [...],
      "faqs": [
        {"q": "...", "a": "...", "role": "cost"},
        {"q": "...", "a": "...", "role": "scope"},
        {"q": "...", "a": "...", "role": "timing"},
        {"q": "...", "a": "...", "role": "who-performs"},
        {"q": "...", "a": "...", "role": "town-specific"},
        ...
      ],
      "nearbyAreas": ["adjacent-town-1", "adjacent-town-2"],
      "sourceFacts": ["Short, specific, human-verified factual statement", ...]
    }

NOTE on "sourceFacts": not used by THIS script -- it's read by the
separate `content-qc` skill (Layer 2: does the prose actually stay
faithful to real, human-provided facts, or does it invent additional
specific-sounding claims). Documented here anyway so the two layers
share one schema instead of drifting into two different JSON shapes for
the same page.

ADDITIONS, why they exist:
    - *Entities fields: the "15+ named local entities" rule can't be
      checked against free text without either a gazetteer (heavy,
      imprecise, and this toolkit has no real-world geographic
      knowledge to check TRUE local facts against anyway) or requiring
      the content author to declare what they used. This script does
      the latter, and verifies each declared entity actually appears
      in the narrative -- catching a padded, unused entity list, not
      just counting a number someone typed in. This same declared list
      is designed to double as the "source facts" a future content-QC
      judgment layer checks the prose against for fabrication.
    - faqs[].role: the rule requires 4 EVERGREEN FAQs (cost/scope/
      timing/who-performs) at FIXED POSITIONS first, then town-specific
      ones. Checking FAQ *content* against those categories via
      keyword-matching would be unreliable and could produce false
      failures -- requiring an explicit role tag makes this exact
      instead of guessed.

CHECKS (all HARD GATES per the source CLAUDE.md's own framing -- a
failure means regenerate/reject, not just a note):
    1. Required fields present
    2. introDirectAnswer: 40-60 words
    3. Named entities: each declared entity must actually appear in its
       paragraph (case-insensitive substring match); of the ones that
       verify, <10 = IMMEDIATE (regenerate), 10-14 = NEEDS_WORK
       (borderline), 15+ = PASS
    4. Combined narrative length (introParagraph1 + introParagraph2) >=
       ~750 chars -- below that is doorway-page risk, per the source
       rule's own wording. Also a non-blocking INFO note if either
       paragraph is well under its ~1,500 char target.
    5. FAQs: 8-12 total: first 4 must have role
       cost/scope/timing/who-performs in that exact order; the rest
       must be tagged town-specific
    6. Trust-claim phrase: only checked if --trust-claim is passed (it
       is NOT finalized in WePipe as of 2026-08-14 -- see
       wiki/seo-strategy.md; skipped with an INFO note if not provided,
       never guessed)
    7. Nearby-area cross-link: introParagraph2 should name at least one
       town from nearbyAreas

USAGE
    python content_bar_check.py --data town-pages.json \
        --out content-bar-report.md [--trust-claim "exact phrase"]

INPUT
    town-pages.json: either one town object, or a JSON array of them
    (a whole wave, checked together).

EXIT CODE
    0 -- every page passed every hard gate
    1 -- at least one page failed at least one hard gate
"""

import argparse
import json
import sys
from dataclasses import dataclass, field

IMMEDIATE = "immediate"
NEEDS_WORK = "needs_work"
PASS = "pass"
INFO = "info"

SEVERITY_ICON = {IMMEDIATE: "🔴", NEEDS_WORK: "⚠️", PASS: "✅", INFO: "ℹ️"}

REQUIRED_FIELDS = [
    "slug", "name", "county", "eraBucket", "introDirectAnswer",
    "introParagraph1", "introParagraph2", "faqs", "nearbyAreas",
]

EVERGREEN_ROLES = ["cost", "scope", "timing", "who-performs"]

NARRATIVE_MIN_CHARS = 750
PARAGRAPH_TARGET_CHARS = 1500
PARAGRAPH_TARGET_WARN_RATIO = 0.70  # below 70% of target = flagged, non-blocking

DIRECT_ANSWER_MIN_WORDS = 40
DIRECT_ANSWER_MAX_WORDS = 60

ENTITY_FAIL_THRESHOLD = 10   # fewer than this verified entities = IMMEDIATE
ENTITY_WARN_THRESHOLD = 15   # fewer than this (but >= fail threshold) = NEEDS_WORK

FAQ_MIN_TOTAL = 8   # 4 evergreen + at least 4 town-specific
FAQ_MAX_TOTAL = 12  # 4 evergreen + at most 8 town-specific


@dataclass
class Finding:
    label: str
    severity: str
    detail: str


@dataclass
class PageResult:
    slug: str
    findings: list = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not any(f.severity == IMMEDIATE for f in self.findings)


def word_count(text: str) -> int:
    return len(text.split())


def check_required_fields(page: dict) -> list:
    findings = []
    missing = [f for f in REQUIRED_FIELDS if f not in page or page[f] in (None, "", [])]
    if missing:
        findings.append(Finding(
            "Required fields", IMMEDIATE,
            f"Missing or empty: {', '.join(missing)}",
        ))
    return findings


def check_direct_answer(page: dict) -> list:
    text = page.get("introDirectAnswer", "")
    wc = word_count(text)
    if DIRECT_ANSWER_MIN_WORDS <= wc <= DIRECT_ANSWER_MAX_WORDS:
        return [Finding("Direct answer length", PASS, f"{wc} words")]
    return [Finding(
        "Direct answer length", NEEDS_WORK,
        f"{wc} words -- target is {DIRECT_ANSWER_MIN_WORDS}-{DIRECT_ANSWER_MAX_WORDS}",
    )]


def check_named_entities(page: dict) -> list:
    findings = []
    p1 = page.get("introParagraph1", "")
    p2 = page.get("introParagraph2", "")
    p1_entities = page.get("introParagraph1Entities", [])
    p2_entities = page.get("introParagraph2Entities", [])

    verified = []
    unverified = []
    for entity in p1_entities:
        if entity.lower() in p1.lower():
            verified.append(entity)
        else:
            unverified.append((entity, "introParagraph1"))
    for entity in p2_entities:
        if entity.lower() in p2.lower():
            verified.append(entity)
        else:
            unverified.append((entity, "introParagraph2"))

    if unverified:
        detail = "; ".join(f'"{e}" claimed but not found in {loc}' for e, loc in unverified)
        findings.append(Finding(
            "Named entities -- unverified claims", NEEDS_WORK,
            f"{len(unverified)} declared entit{'y' if len(unverified) == 1 else 'ies'} "
            f"not actually present in the narrative (padded list, or the text changed "
            f"after the list was written): {detail}",
        ))

    verified_count = len(verified)
    if verified_count < ENTITY_FAIL_THRESHOLD:
        findings.append(Finding(
            "Named entities -- count", IMMEDIATE,
            f"Only {verified_count} verified local entities (need 15+, regenerate if under 10)",
        ))
    elif verified_count < ENTITY_WARN_THRESHOLD:
        findings.append(Finding(
            "Named entities -- count", NEEDS_WORK,
            f"{verified_count} verified local entities -- borderline (target 15+)",
        ))
    else:
        findings.append(Finding(
            "Named entities -- count", PASS,
            f"{verified_count} verified local entities",
        ))
    return findings


def check_narrative_length(page: dict) -> list:
    findings = []
    p1 = page.get("introParagraph1", "")
    p2 = page.get("introParagraph2", "")
    combined = len(p1) + len(p2)

    if combined < NARRATIVE_MIN_CHARS:
        findings.append(Finding(
            "Narrative length", IMMEDIATE,
            f"Combined narrative is {combined} chars -- below the {NARRATIVE_MIN_CHARS}-char "
            f"floor, doorway-page risk per the content-bar rule",
        ))
    else:
        findings.append(Finding("Narrative length", PASS, f"{combined} chars combined"))

    for label, text in [("introParagraph1", p1), ("introParagraph2", p2)]:
        target_floor = PARAGRAPH_TARGET_CHARS * PARAGRAPH_TARGET_WARN_RATIO
        if len(text) < target_floor:
            findings.append(Finding(
                f"{label} -- below target", INFO,
                f"{len(text)} chars, well under the ~{PARAGRAPH_TARGET_CHARS}-char target "
                f"(not a hard rule, just a heads-up)",
            ))
    return findings


def check_faqs(page: dict) -> list:
    findings = []
    faqs = page.get("faqs", [])
    total = len(faqs)

    if total < FAQ_MIN_TOTAL or total > FAQ_MAX_TOTAL:
        findings.append(Finding(
            "FAQ count", IMMEDIATE,
            f"{total} FAQs -- expected {FAQ_MIN_TOTAL}-{FAQ_MAX_TOTAL} "
            f"(4 evergreen + 4-8 town-specific)",
        ))
        return findings  # positional checks below aren't meaningful if count is wrong

    first_four_roles = [f.get("role") for f in faqs[:4]]
    if first_four_roles != EVERGREEN_ROLES:
        findings.append(Finding(
            "FAQ evergreen positions", IMMEDIATE,
            f"First 4 FAQs must be roles {EVERGREEN_ROLES} in that exact order, "
            f"got {first_four_roles}",
        ))
    else:
        findings.append(Finding("FAQ evergreen positions", PASS, "Correct order and roles"))

    rest_roles = [f.get("role") for f in faqs[4:]]
    mistagged = [i + 4 for i, r in enumerate(rest_roles) if r != "town-specific"]
    if mistagged:
        findings.append(Finding(
            "FAQ town-specific tagging", NEEDS_WORK,
            f"FAQ(s) at position(s) {mistagged} not tagged role=town-specific",
        ))
    else:
        findings.append(Finding("FAQ town-specific tagging", PASS, f"{len(rest_roles)} correctly tagged"))

    return findings


def check_trust_claim(page: dict, trust_claim: str | None) -> list:
    if not trust_claim:
        return [Finding(
            "Trust-claim phrase", INFO,
            "Not checked -- no --trust-claim provided (not yet finalized as of 2026-08-14, "
            "see wiki/seo-strategy.md)",
        )]
    all_text = " ".join([
        page.get("introDirectAnswer", ""),
        page.get("introParagraph1", ""),
        page.get("introParagraph2", ""),
        " ".join(f.get("a", "") for f in page.get("faqs", [])),
    ])
    if trust_claim in all_text:
        return [Finding("Trust-claim phrase", PASS, "Present, exact match")]
    return [Finding(
        "Trust-claim phrase", IMMEDIATE,
        f'Exact phrase "{trust_claim}" not found anywhere on this page',
    )]


def check_nearby_cross_link(page: dict) -> list:
    p2 = page.get("introParagraph2", "")
    nearby = page.get("nearbyAreas", [])
    if not nearby:
        return [Finding("Nearby-area cross-link", NEEDS_WORK, "No nearbyAreas declared to cross-link to")]

    mentioned = [town for town in nearby if town.lower().replace("-", " ") in p2.lower()]
    if mentioned:
        return [Finding("Nearby-area cross-link", PASS, f"References {', '.join(mentioned)}")]
    return [Finding(
        "Nearby-area cross-link", NEEDS_WORK,
        f"introParagraph2 doesn't name any of the declared nearbyAreas ({', '.join(nearby)})",
    )]


def check_page(page: dict, trust_claim: str | None) -> PageResult:
    slug = page.get("slug", "(missing slug)")
    result = PageResult(slug=slug)

    result.findings.extend(check_required_fields(page))
    if any(f.severity == IMMEDIATE for f in result.findings):
        # Required fields missing -- other checks would just KeyError/misreport, skip them.
        return result

    result.findings.extend(check_direct_answer(page))
    result.findings.extend(check_named_entities(page))
    result.findings.extend(check_narrative_length(page))
    result.findings.extend(check_faqs(page))
    result.findings.extend(check_trust_claim(page, trust_claim))
    result.findings.extend(check_nearby_cross_link(page))
    return result


def build_report(results: list) -> str:
    passed = [r for r in results if r.passed]
    failed = [r for r in results if not r.passed]

    lines = [
        "# Content Bar Report",
        "",
        f"**Pages checked:** {len(results)}  ",
        f"**Passed:** {len(passed)}  ",
        f"**Failed:** {len(failed)}",
        "",
        "---",
        "",
    ]

    for r in results:
        status = "PASS" if r.passed else "FAIL"
        lines.append(f"## {r.slug} — {status}")
        lines.append("")
        for f in r.findings:
            lines.append(f"- {SEVERITY_ICON[f.severity]} **{f.label}:** {f.detail}")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Check area/town page data against the documented content-bar hard rules.")
    parser.add_argument("--data", required=True, help="Path to a JSON file: one town object, or an array of them")
    parser.add_argument("--out", default="content-bar-report.md", help="Where to write the Markdown report")
    parser.add_argument("--trust-claim", default=None, help="Exact trust-claim phrase to check for, if finalized")
    args = parser.parse_args()

    with open(args.data, "r", encoding="utf-8") as f:
        data = json.load(f)

    pages = data if isinstance(data, list) else [data]

    results = [check_page(page, args.trust_claim) for page in pages]
    report = build_report(results)

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(report)

    failed_count = sum(1 for r in results if not r.passed)
    print(f"Pages checked: {len(results)}")
    print(f"Passed: {len(results) - failed_count}")
    print(f"Failed: {failed_count}")
    print(f"Report written to {args.out}")

    sys.exit(1 if failed_count else 0)


if __name__ == "__main__":
    main()
