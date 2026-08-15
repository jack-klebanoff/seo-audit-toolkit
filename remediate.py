#!/usr/bin/env python3
"""
remediate.py

Companion to audit.py: takes an audit's JSON output and generates concrete,
ready-to-use fixes for the Category 1 findings we can actually fix from an
audit alone — real code snippets, not just "fix this" prose.

SCOPE SO FAR: schema fixes (LocalBusiness, optionally enriched with
geo/hours/sameAs/areaServed, plus a separate Service schema block when
a --service-type is given), canonical tag fixes, and broken-link flags
— all purely mechanical, no content judgment involved. Broken links are the one
category where "fix" doesn't mean a working replacement: this script has
no way to know what a dead link *should* point to, so it generates a
clearly-marked placeholder comment (the broken href + the problem +
the two safe options) instead of guessing a destination — same
never-fabricate discipline as schema's phone/address placeholders.
Title/meta description fixes are deliberately NOT
automated here: unlike a canonical URL, good title/meta copy requires
knowing the actual business well enough to write for it, which this script
has no business fabricating for a site it doesn't represent — same line
drawn around testimonials elsewhere in this project. Every other
NEEDS_WORK/IMMEDIATE Category 1 finding is listed as a flagged action item
in the "Not yet automated" section. More finding types get real fixes in
later passes, one at a time, same discipline audit.py's own features were
built and verified with.

WHO THIS IS FOR: sites we do NOT have repo access to — a sales prospect, a
site on an unknown CMS. The output is something a human pastes in; this
script never touches a live site or a real codebase. For a site we DO
control the source of, the generated snippet is exactly what a Claude Code
session would apply directly (e.g. into an Astro Layout.astro) — same
pattern already used for WePipe's own LocalBusiness schema.

USAGE
    python remediate.py --audit-json hercules-fence-audit.json \
        --out hercules-fence-remediation.md \
        [--business-type HomeAndConstructionBusiness] \
        [--hours "Mo-Sa 08:00-18:00"] [--geo "40.71,-73.93"] \
        [--gbp-url "https://g.page/..."] [--area-served "Ridgewood,Glendale"] \
        [--service-type "Plumbing repair"] [--service-description "..."] [--price "150"]

INPUT
    An audit.json produced by `audit.py --json-out`. If that run was given
    --phone/--address, this script reads them back automatically from the
    JSON's `input_nap` field — no need to pass them again. Per-link broken
    link data (the `broken_links` field on each page) requires an audit.json
    from a current audit.py — older reports without it still work, they just
    fall back to a single summarized "Broken links" entry in "Not yet
    automated" instead of one flagged entry per dead link. The new
    --hours/--geo/--gbp-url/--area-served/--service-type/etc. flags aren't
    read from the audit JSON at all (audit.py doesn't collect them) — real,
    human-supplied values only, same never-fabricate rule as phone/address.

OUTPUT
    A Markdown remediation plan: one ready-to-paste JSON-LD block per page
    that needs one (with any placeholder values it had to use flagged
    explicitly, same discipline as WePipe's own schema build), one flagged
    comment block per broken link found (href + problem + the two safe
    manual options — never a guessed destination), plus a flagged list of
    every other Category 1 problem found — ordered Immediate first
    (stop-the-bleeding), then Needs Work, per /wiki/audit-rubric.md's
    Priorities framing.
"""

import argparse
import json
from urllib.parse import urlparse


def business_id_for(page_url: str) -> str:
    """One stable @id shared by every page's LocalBusiness block, derived
    from the site's own domain rather than each page's own URL — Mario's
    notes are explicit that the LocalBusiness block should be identical
    across every page, and a Service schema needs a stable @id to point
    its `provider` field at (same pattern already used for WePipe's own
    schema: '@id': 'https://wepipellc.com/#business')."""
    parsed = urlparse(page_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    return f"{origin}/#business"


def parse_geo_best_effort(geo: str) -> dict | None:
    """Expects 'lat,lon'. Returns None (never a guess) if it doesn't parse
    cleanly — malformed geo input is flagged to the human, not silently
    dropped or corrected."""
    parts = [p.strip() for p in geo.split(",")]
    if len(parts) != 2:
        return None
    try:
        lat, lon = float(parts[0]), float(parts[1])
    except ValueError:
        return None
    return {"@type": "GeoCoordinates", "latitude": lat, "longitude": lon}


def parse_address_best_effort(address: str) -> dict:
    """Best-effort split of a 'Street, City, State ZIP' style US address
    into PostalAddress components. This is a CONVENIENCE parse, not a
    guarantee — real addresses vary in format, so the output always gets
    flagged for the human to verify before publishing, never presented as
    definitely correct."""
    parts = [p.strip() for p in address.split(",")]
    result = {"@type": "PostalAddress", "addressCountry": "US"}
    if len(parts) >= 1 and parts[0]:
        result["streetAddress"] = parts[0]
    if len(parts) >= 2 and parts[1]:
        result["addressLocality"] = parts[1]
    if len(parts) >= 3 and parts[2]:
        state_zip = parts[2].split()
        if len(state_zip) >= 1:
            result["addressRegion"] = state_zip[0]
        if len(state_zip) >= 2:
            result["postalCode"] = state_zip[1]
    return result


def generate_schema_snippet(
    business_name: str, page_url: str, business_type: str, phone: str | None, address: str | None,
    hours: str | None = None, geo: str | None = None, gbp_url: str | None = None, area_served: str | None = None,
) -> tuple[str, list]:
    """Returns (html_snippet, placeholder_warnings). Never fabricates a
    phone number or address — uses REPLACE_WITH_* markers and flags them
    explicitly when the real value wasn't available, same rule followed
    when we built WePipe's own schema.

    hours/geo/gbp_url/area_served are opt-in enrichment, not required —
    per Mario's own notes, only name and address are strictly required on
    a LocalBusiness block; these four are "strongly recommended," not a
    gap to flag. Unlike phone/address (asked for on every audit.py run,
    so a missing value is a real gap worth a placeholder), these are new
    remediate.py-only flags most runs won't pass — so they're simply
    omitted when not given, not padded with placeholders nobody asked
    for. See render_markdown's one-time note about how to add them."""
    schema = {
        "@context": "https://schema.org",
        "@type": business_type,
        "@id": business_id_for(page_url),
        "name": business_name,
        "url": page_url,
    }
    placeholders = []

    if phone:
        schema["telephone"] = phone
    else:
        schema["telephone"] = "REPLACE_WITH_PHONE"
        placeholders.append("telephone — no --phone was given to the audit run this came from")

    if address:
        schema["address"] = parse_address_best_effort(address)
        placeholders.append("address — auto-parsed from a single string, verify the street/city/state/zip split is correct before publishing")
    else:
        schema["address"] = "REPLACE_WITH_ADDRESS"
        placeholders.append("address — no --address was given to the audit run this came from")

    if geo:
        parsed_geo = parse_geo_best_effort(geo)
        if parsed_geo:
            schema["geo"] = parsed_geo
        else:
            placeholders.append(f"geo — could not parse \"{geo}\" as \"lat,lon\", omitted rather than guessed")

    if hours:
        schema["openingHours"] = hours

    if gbp_url:
        schema["sameAs"] = [gbp_url]

    if area_served:
        schema["areaServed"] = [a.strip() for a in area_served.split(",") if a.strip()]

    snippet_json = json.dumps(schema, indent=2)
    html_snippet = f'<script type="application/ld+json">\n{snippet_json}\n</script>'
    return html_snippet, placeholders


def generate_service_schema_snippet(
    page_url: str, service_type: str, service_description: str | None, area_served: str | None, price: str | None,
) -> tuple[str, list]:
    """Separate Service schema block, linked to the LocalBusiness via @id
    rather than repeating the business block (same pattern WePipe's own
    Service pages already use). Only generated when --service-type is
    explicitly passed — see build_remediation_plan.

    description gets a REPLACE_WITH_* placeholder when missing, same
    non-fabrication logic as phone/address: it's a real gap in an
    already-opted-into schema block, not an optional enrichment. price/
    offers is the opposite — deliberately never gets a placeholder, only
    included when a real --price is given. Fabricating a price is the
    same line this project already refuses to cross for testimonials and
    marketing copy; an honest absence is correct, not a gap to flag."""
    schema = {
        "@context": "https://schema.org",
        "@type": "Service",
        "serviceType": service_type,
        "provider": {"@id": business_id_for(page_url)},
    }
    placeholders = []

    if service_description:
        schema["description"] = service_description
    else:
        schema["description"] = "REPLACE_WITH_SERVICE_DESCRIPTION"
        placeholders.append("description — no --service-description given; this script won't fabricate marketing copy, write real service-specific copy before publishing")

    if area_served:
        towns = [a.strip() for a in area_served.split(",") if a.strip()]
        area_served_schema = [{"@type": "City", "name": t} for t in towns]
        schema["areaServed"] = area_served_schema[0] if len(area_served_schema) == 1 else area_served_schema
    else:
        schema["areaServed"] = "REPLACE_WITH_AREA_SERVED"
        placeholders.append("areaServed — no --area-served given; add the real town(s)/region this service covers")

    if price:
        schema["offers"] = {"@type": "Offer", "price": price, "priceCurrency": "USD"}
        placeholders.append("offers/price — verify this is still current before publishing")
    # No placeholder when price is omitted — real pricing not being on hand
    # is a normal, honest state (see WePipe's own schema, which has no
    # offers field at all), not a gap to flag like description/areaServed.

    snippet_json = json.dumps(schema, indent=2)
    html_snippet = f'<script type="application/ld+json">\n{snippet_json}\n</script>'
    return html_snippet, placeholders


def generate_canonical_snippet(page_url: str) -> str:
    """Always correct, no judgment call involved — the canonical URL for
    a page is just that page's own URL. Unlike schema (which needs real
    business info) or title/meta (which needs real marketing copy this
    script has no business fabricating), this fix type is purely
    mechanical, so it always gets generated with zero placeholders."""
    return f'<link rel="canonical" href="{page_url}" />'


def generate_broken_link_snippet(source_page_url: str, broken_url: str, problem: str) -> str:
    """Never guesses a replacement destination — an audit alone can't tell
    you what a dead link was supposed to point to. Produces a flagged
    comment naming the exact href and problem, plus the two safe manual
    options, same placeholder-flagging discipline as schema's phone/
    address fields. Meant to be dropped in next to the real <a> tag as a
    marker while someone decides which option applies."""
    return (
        f"<!-- BROKEN LINK found on {source_page_url}\n"
        f'     href="{broken_url}" — {problem}\n'
        f"     This script can't know the correct destination. Either:\n"
        f"       1) update the href to the correct page, or\n"
        f"       2) remove the link (and its surrounding <a> tag) if the\n"
        f"          content it pointed to no longer exists.\n"
        f"-->"
    )


def build_remediation_plan(
    audit_data: dict, business_type: str,
    hours: str | None = None, geo: str | None = None, gbp_url: str | None = None, area_served: str | None = None,
    service_type: str | None = None, service_description: str | None = None, price: str | None = None,
) -> tuple[str, list, list, list, list, list]:
    business_name = audit_data.get("business_name", "Unknown Business")
    input_nap = audit_data.get("input_nap") or {}
    phone = input_nap.get("phone")
    address = input_nap.get("address")

    pages = audit_data.get("category_1", {}).get("pages", [])
    site_level = audit_data.get("category_1", {}).get("site_level", [])

    schema_fixes = []
    service_schema_fixes = []
    canonical_fixes = []
    broken_link_fixes = []
    other_findings = []

    # Site-level findings (currently just robots.txt) aren't attached to
    # any single page, so the per-page loop below never sees them. Without
    # this, a site-level Immediate finding (e.g. a robots.txt sitemap
    # pointing at the wrong domain) would silently vanish from the plan
    # entirely rather than landing in "Not yet automated" — found via the
    # prospect-audit skill's smoke test against WePipe's own site.
    for f in site_level:
        if f["severity"] not in ("immediate", "needs_work"):
            continue
        other_findings.append({"severity": f["severity"], "label": f["label"], "url": "site-wide", "detail": f["detail"]})

    for page in pages:
        if page.get("fetch_error"):
            continue
        url = page["url"]
        page_broken_links = page.get("broken_links", [])

        for link in page_broken_links:
            broken_link_fixes.append({
                "page_url": url,
                "broken_url": link["url"],
                "problem": link["problem"],
                "snippet": generate_broken_link_snippet(url, link["url"], link["problem"]),
            })

        for f in page.get("findings", []):
            if f["severity"] not in ("immediate", "needs_work"):
                continue
            if f["label"] == "Schema":
                snippet, placeholders = generate_schema_snippet(
                    business_name, url, business_type, phone, address,
                    hours=hours, geo=geo, gbp_url=gbp_url, area_served=area_served,
                )
                schema_fixes.append({
                    "url": url,
                    "snippet": snippet,
                    "placeholders": placeholders,
                    "original_finding": f["detail"],
                })
                if service_type:
                    service_snippet, service_placeholders = generate_service_schema_snippet(
                        url, service_type, service_description, area_served, price,
                    )
                    service_schema_fixes.append({
                        "url": url,
                        "snippet": service_snippet,
                        "placeholders": service_placeholders,
                    })
            elif f["label"] == "Canonical tag":
                canonical_fixes.append({
                    "url": url,
                    "snippet": generate_canonical_snippet(url),
                    "original_finding": f["detail"],
                })
            elif f["label"] == "Broken links" and page_broken_links:
                continue  # already captured above from structured per-link data
            else:
                other_findings.append({"severity": f["severity"], "label": f["label"], "url": url, "detail": f["detail"]})

    other_findings.sort(key=lambda x: 0 if x["severity"] == "immediate" else 1)
    return business_name, schema_fixes, service_schema_fixes, canonical_fixes, broken_link_fixes, other_findings


def render_markdown(business_name: str, schema_fixes: list, service_schema_fixes: list, canonical_fixes: list, broken_link_fixes: list, other_findings: list, business_type: str) -> str:
    lines = [
        f"# Remediation Plan — {business_name}",
        "",
        f"**Schema fixes generated:** {len(schema_fixes)}",
        f"**Service schema fixes generated:** {len(service_schema_fixes)}",
        f"**Canonical tag fixes generated:** {len(canonical_fixes)}",
        f"**Broken links flagged:** {len(broken_link_fixes)}",
        f"**Other Category 1 findings flagged (not yet auto-fixed):** {len(other_findings)}",
        "",
        "---",
        "",
        "## Schema fixes",
        "",
    ]

    if schema_fixes:
        lines.append(
            f"Generated as `{business_type}` (schema.org's LocalBusiness family). "
            "If you know the business's actual trade (e.g. Plumber, HVACBusiness), "
            "swap `@type` for the more specific one — LocalBusiness is always valid, "
            "but a specific subtype is stronger when you know it."
        )
        lines.append("")
        lines.append(
            "Only `name` and `address` are strictly required on this block — "
            "`geo`, `openingHours`, `sameAs` (your Google Business Profile URL), "
            "and `areaServed` are strongly recommended but weren't requested this "
            "run. Re-run with `--geo`, `--hours`, `--gbp-url`, and/or "
            "`--area-served` to include them."
        )
        lines.append("")
        for fix in schema_fixes:
            lines.append(f"### {fix['url']}")
            lines.append("")
            lines.append(f"**Original finding:** {fix['original_finding']}")
            lines.append("")
            if fix["placeholders"]:
                lines.append("**⚠️ Before publishing, verify/fix:**")
                for p in fix["placeholders"]:
                    lines.append(f"- {p}")
                lines.append("")
            lines.append("```html")
            lines.append(fix["snippet"])
            lines.append("```")
            lines.append("")
    else:
        lines.append("None needed — every page already had valid business-type schema.")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Service schema")
    lines.append("")

    if service_schema_fixes:
        lines.append(
            "Carries `serviceType`, `description`, `areaServed`, and (when known) "
            "`offers`, so Google understands exactly what's sold where — linked to "
            "the LocalBusiness block above via `@id` rather than repeating it. "
            "If the business has real reviews, attach them here via `aggregateRating`/"
            "`review` rather than only on the business overall — never fabricated, "
            "add real ones by hand."
        )
        lines.append("")
        for fix in service_schema_fixes:
            lines.append(f"### {fix['url']}")
            lines.append("")
            if fix["placeholders"]:
                lines.append("**⚠️ Before publishing, verify/fix:**")
                for p in fix["placeholders"]:
                    lines.append(f"- {p}")
                lines.append("")
            lines.append("```html")
            lines.append(fix["snippet"])
            lines.append("```")
            lines.append("")
    else:
        lines.append(
            "Not requested this run — pass `--service-type` (e.g. \"Plumbing "
            "repair\") to generate a Service schema block alongside each "
            "LocalBusiness fix above."
        )
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Canonical tag fixes")
    lines.append("")

    if canonical_fixes:
        lines.append(
            "Always the page's own URL — no judgment call involved, so these "
            "carry no placeholders to verify. Add inside `<head>`."
        )
        lines.append("")
        for fix in canonical_fixes:
            lines.append(f"### {fix['url']}")
            lines.append("")
            lines.append(f"**Original finding:** {fix['original_finding']}")
            lines.append("")
            lines.append("```html")
            lines.append(fix["snippet"])
            lines.append("```")
            lines.append("")
    else:
        lines.append("None needed — every page already had a canonical tag.")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Broken links")
    lines.append("")

    if broken_link_fixes:
        lines.append(
            "This script can't know what a dead link was supposed to point "
            "to — each entry below flags exactly what's broken and the two "
            "safe options (fix the href or remove the link), not a guessed "
            "replacement URL."
        )
        lines.append("")
        for fix in broken_link_fixes:
            lines.append(f"### {fix['broken_url']}")
            lines.append("")
            lines.append(f"**Found on:** {fix['page_url']}  ")
            lines.append(f"**Problem:** {fix['problem']}")
            lines.append("")
            lines.append("```html")
            lines.append(fix["snippet"])
            lines.append("```")
            lines.append("")
    else:
        lines.append("None found — no broken same-domain links detected.")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Not yet automated")
    lines.append("")
    lines.append(
        "These Category 1 findings don't have generated fixes yet — flagged for "
        "manual work, ordered stop-the-bleeding (Immediate) first, per "
        "/wiki/audit-rubric.md's Priorities framing."
    )
    lines.append("")
    if other_findings:
        for f in other_findings:
            icon = "🔴" if f["severity"] == "immediate" else "⚠️"
            lines.append(f"- {icon} **{f['label']}** ({f['url']}): {f['detail']}")
    else:
        lines.append("None — no other Category 1 problems found.")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate concrete fixes from an audit.py JSON report.")
    parser.add_argument("--audit-json", required=True, help="Path to a JSON report from audit.py --json-out")
    parser.add_argument("--out", default="remediation-plan.md", help="Where to write the Markdown remediation plan")
    parser.add_argument(
        "--business-type", default="LocalBusiness",
        help="schema.org @type for generated schema (default: LocalBusiness — always valid; "
             "use a specific subtype like Plumber or HVACBusiness if you know the trade)",
    )
    parser.add_argument("--hours", help="Opening hours in schema.org format, e.g. \"Mo-Sa 08:00-18:00\" — optional, only added to LocalBusiness schema if given")
    parser.add_argument("--geo", help="\"lat,lon\" — optional, only added if it parses cleanly")
    parser.add_argument("--gbp-url", help="Google Business Profile URL — added as LocalBusiness sameAs if given")
    parser.add_argument("--area-served", help="Comma-separated town/region names — used for both LocalBusiness areaServed and Service areaServed if --service-type is also given")
    parser.add_argument("--service-type", help="e.g. \"Plumbing repair\" — if given, also generates a separate Service schema block per page alongside the LocalBusiness fix")
    parser.add_argument("--service-description", help="Real service-specific copy for the Service schema's description — never fabricated if omitted")
    parser.add_argument("--price", help="Real price for the Service schema's offers field — never included unless explicitly given here")
    args = parser.parse_args()

    with open(args.audit_json, "r", encoding="utf-8") as f:
        audit_data = json.load(f)

    business_name, schema_fixes, service_schema_fixes, canonical_fixes, broken_link_fixes, other_findings = build_remediation_plan(
        audit_data, args.business_type,
        hours=args.hours, geo=args.geo, gbp_url=args.gbp_url, area_served=args.area_served,
        service_type=args.service_type, service_description=args.service_description, price=args.price,
    )
    report = render_markdown(business_name, schema_fixes, service_schema_fixes, canonical_fixes, broken_link_fixes, other_findings, args.business_type)

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Business: {business_name}")
    print(f"Schema fixes generated: {len(schema_fixes)}")
    print(f"Service schema fixes generated: {len(service_schema_fixes)}")
    print(f"Canonical tag fixes generated: {len(canonical_fixes)}")
    print(f"Broken links flagged: {len(broken_link_fixes)}")
    print(f"Other Category 1 findings flagged: {len(other_findings)}")
    print(f"Remediation plan written to {args.out}")


if __name__ == "__main__":
    main()
