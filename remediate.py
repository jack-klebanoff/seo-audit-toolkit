#!/usr/bin/env python3
"""
remediate.py

Companion to audit.py: takes an audit's JSON output and generates concrete,
ready-to-use fixes for the Category 1 findings we can actually fix from an
audit alone — real code snippets, not just "fix this" prose.

SCOPE OF THIS FIRST VERSION: schema fixes only (missing or generic-only
LocalBusiness/Service schema — the most common finding in practice, and the
one with the clearest, most reliable fix). Every other NEEDS_WORK/IMMEDIATE
Category 1 finding is listed as a flagged action item, not yet auto-fixed —
see the "Not yet automated" section of the output. More finding types get
real fixes in later passes, one at a time, same discipline audit.py's own
three features were built and verified with.

WHO THIS IS FOR: sites we do NOT have repo access to — a sales prospect, a
site on an unknown CMS. The output is something a human pastes in; this
script never touches a live site or a real codebase. For a site we DO
control the source of, the generated snippet is exactly what a Claude Code
session would apply directly (e.g. into an Astro Layout.astro) — same
pattern already used for WePipe's own LocalBusiness schema.

USAGE
    python remediate.py --audit-json hercules-fence-audit.json \
        --out hercules-fence-remediation.md \
        [--business-type HomeAndConstructionBusiness]

INPUT
    An audit.json produced by `audit.py --json-out`. If that run was given
    --phone/--address, this script reads them back automatically from the
    JSON's `input_nap` field — no need to pass them again.

OUTPUT
    A Markdown remediation plan: one ready-to-paste JSON-LD block per page
    that needs one (with any placeholder values it had to use flagged
    explicitly, same discipline as WePipe's own schema build), plus a
    flagged list of every other Category 1 problem found — ordered
    Immediate first (stop-the-bleeding), then Needs Work, per
    /wiki/audit-rubric.md's Priorities framing.
"""

import argparse
import json


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


def generate_schema_snippet(business_name: str, page_url: str, business_type: str, phone: str | None, address: str | None) -> tuple[str, list]:
    """Returns (html_snippet, placeholder_warnings). Never fabricates a
    phone number or address — uses REPLACE_WITH_* markers and flags them
    explicitly when the real value wasn't available, same rule followed
    when we built WePipe's own schema."""
    schema = {
        "@context": "https://schema.org",
        "@type": business_type,
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

    snippet_json = json.dumps(schema, indent=2)
    html_snippet = f'<script type="application/ld+json">\n{snippet_json}\n</script>'
    return html_snippet, placeholders


def build_remediation_plan(audit_data: dict, business_type: str) -> tuple[str, list, list]:
    business_name = audit_data.get("business_name", "Unknown Business")
    input_nap = audit_data.get("input_nap") or {}
    phone = input_nap.get("phone")
    address = input_nap.get("address")

    pages = audit_data.get("category_1", {}).get("pages", [])

    schema_fixes = []
    other_findings = []

    for page in pages:
        if page.get("fetch_error"):
            continue
        url = page["url"]
        for f in page.get("findings", []):
            if f["severity"] not in ("immediate", "needs_work"):
                continue
            if f["label"] == "Schema":
                snippet, placeholders = generate_schema_snippet(business_name, url, business_type, phone, address)
                schema_fixes.append({
                    "url": url,
                    "snippet": snippet,
                    "placeholders": placeholders,
                    "original_finding": f["detail"],
                })
            else:
                other_findings.append({"severity": f["severity"], "label": f["label"], "url": url, "detail": f["detail"]})

    other_findings.sort(key=lambda x: 0 if x["severity"] == "immediate" else 1)
    return business_name, schema_fixes, other_findings


def render_markdown(business_name: str, schema_fixes: list, other_findings: list, business_type: str) -> str:
    lines = [
        f"# Remediation Plan — {business_name}",
        "",
        f"**Schema fixes generated:** {len(schema_fixes)}",
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
    args = parser.parse_args()

    with open(args.audit_json, "r", encoding="utf-8") as f:
        audit_data = json.load(f)

    business_name, schema_fixes, other_findings = build_remediation_plan(audit_data, args.business_type)
    report = render_markdown(business_name, schema_fixes, other_findings, args.business_type)

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Business: {business_name}")
    print(f"Schema fixes generated: {len(schema_fixes)}")
    print(f"Other Category 1 findings flagged: {len(other_findings)}")
    print(f"Remediation plan written to {args.out}")


if __name__ == "__main__":
    main()
