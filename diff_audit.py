#!/usr/bin/env python3
"""
diff_audit.py

Companion to audit.py, for maintenance rather than cold outreach: compares
two audit.json snapshots of the SAME site (same URL set, different dates)
and reports what actually changed — new problems, resolved problems,
problems that got worse, and pages that stopped loading entirely. A
one-off audit score is a snapshot; a maintenance check only matters if it
tells you what moved since last time.

SCOPE: purely mechanical set comparison over the two JSON reports' own
findings — no re-fetching, no new judgment calls, nothing fabricated.
Findings are matched by (page_url, label) as the identity key, since
that's the same granularity remediate.py already uses.

USAGE
    python diff_audit.py --old 2026-08-01-audit.json --new 2026-09-01-audit.json \
        --out maintenance-diff.md

INPUT
    Two audit.json files from audit.py --json-out. Should be the same
    business/site audited at two different times — this script doesn't
    check that they match, so pass the right pair.

OUTPUT
    A Markdown summary: score delta, any page that started or stopped
    failing to load (the single most urgent maintenance signal), new
    findings, resolved findings, and findings that got worse (e.g.
    Needs Work -> Immediate).
"""

import argparse
import json


SEVERITY_RANK = {"immediate": 2, "needs_work": 1, "pass": 0, "strength": 0, "info": 0}


def _findings_by_key(pages: list) -> dict:
    """Maps (page_url, label) -> finding dict, immediate/needs_work only —
    PASS/STRENGTH/INFO findings aren't maintenance-relevant on their own,
    only their absence (a resolved problem) or appearance (a new one)."""
    out = {}
    for page in pages:
        if page.get("fetch_error"):
            continue
        url = page["url"]
        for f in page.get("findings", []):
            if f["severity"] in ("immediate", "needs_work"):
                out[(url, f["label"])] = f
    return out


def _site_level_by_key(site_level: list) -> dict:
    return {f["label"]: f for f in site_level if f["severity"] in ("immediate", "needs_work")}


def _diff_finding_sets(old: dict, new: dict) -> tuple[list, list, list]:
    """Returns (new_findings, resolved_findings, worsened_findings)."""
    new_findings, resolved_findings, worsened_findings = [], [], []

    for key, f in new.items():
        if key not in old:
            new_findings.append(f)
        elif SEVERITY_RANK[f["severity"]] > SEVERITY_RANK[old[key]["severity"]]:
            worsened_findings.append({
                "label": f["label"],
                "old_severity": old[key]["severity"],
                "new_severity": f["severity"],
                "detail": f["detail"],
            })

    for key, f in old.items():
        if key not in new:
            resolved_findings.append(f)

    return new_findings, resolved_findings, worsened_findings


def build_diff(old_data: dict, new_data: dict) -> dict:
    old_pages = {p["url"]: p for p in old_data.get("category_1", {}).get("pages", [])}
    new_pages = {p["url"]: p for p in new_data.get("category_1", {}).get("pages", [])}

    # The single most urgent maintenance signal: a page that used to load
    # and now doesn't (or vice versa) — worth surfacing before anything
    # else, since every other finding on that page is moot if it's down.
    pages_now_failing = [
        {"url": url, "error": new_pages[url]["fetch_error"]}
        for url in new_pages
        if new_pages[url].get("fetch_error") and url in old_pages and not old_pages[url].get("fetch_error")
    ]
    pages_now_recovered = [
        url for url in new_pages
        if not new_pages[url].get("fetch_error") and url in old_pages and old_pages[url].get("fetch_error")
    ]
    pages_added = [url for url in new_pages if url not in old_pages]
    pages_removed = [url for url in old_pages if url not in new_pages]

    old_findings = _findings_by_key(list(old_pages.values()))
    new_findings_map = _findings_by_key(list(new_pages.values()))
    new_findings, resolved_findings, worsened_findings = _diff_finding_sets(old_findings, new_findings_map)

    old_site = _site_level_by_key(old_data.get("category_1", {}).get("site_level", []))
    new_site = _site_level_by_key(new_data.get("category_1", {}).get("site_level", []))
    site_new, site_resolved, site_worsened = _diff_finding_sets(old_site, new_site)

    old_score = old_data.get("category_1", {}).get("score")
    new_score = new_data.get("category_1", {}).get("score")
    score_delta = round(new_score - old_score, 1) if old_score is not None and new_score is not None else None

    return {
        "business_name": new_data.get("business_name", old_data.get("business_name", "Unknown Business")),
        "old_generated_at": old_data.get("generated_at"),
        "new_generated_at": new_data.get("generated_at"),
        "old_score": old_score,
        "new_score": new_score,
        "score_delta": score_delta,
        "pages_now_failing": pages_now_failing,
        "pages_now_recovered": pages_now_recovered,
        "pages_added": pages_added,
        "pages_removed": pages_removed,
        "new_findings": [
            {"page_url": url, "label": f["label"], "severity": f["severity"], "detail": f["detail"]}
            for (url, label), f in new_findings_map.items() if f in new_findings
        ],
        "resolved_findings": [
            {"page_url": url, "label": f["label"], "severity": f["severity"], "detail": f["detail"]}
            for (url, label), f in old_findings.items() if f in resolved_findings
        ],
        "worsened_findings": worsened_findings,
        "site_new_findings": site_new,
        "site_resolved_findings": site_resolved,
        "site_worsened_findings": site_worsened,
    }


def render_markdown(diff: dict) -> str:
    lines = [
        f"# Maintenance Check — {diff['business_name']}",
        "",
        f"**Previous audit:** {diff['old_generated_at']}  ",
        f"**This audit:** {diff['new_generated_at']}  ",
        f"**Category 1 score:** {diff['old_score']} → {diff['new_score']} "
        f"({'+' if (diff['score_delta'] or 0) >= 0 else ''}{diff['score_delta']})",
        "",
        "---",
        "",
    ]

    if diff["pages_now_failing"]:
        lines.append("## 🔴 Pages that stopped loading — check these first")
        lines.append("")
        for p in diff["pages_now_failing"]:
            lines.append(f"- {p['url']} — {p['error']}")
        lines.append("")

    if diff["pages_now_recovered"]:
        lines.append("## Pages that came back")
        lines.append("")
        for url in diff["pages_now_recovered"]:
            lines.append(f"- {url}")
        lines.append("")

    if diff["pages_added"] or diff["pages_removed"]:
        lines.append("## URL list changed since last check")
        lines.append("")
        for url in diff["pages_added"]:
            lines.append(f"- + added: {url}")
        for url in diff["pages_removed"]:
            lines.append(f"- − no longer checked: {url}")
        lines.append("")

    lines.append("## New findings since last check")
    lines.append("")
    all_new = diff["new_findings"] + [{"page_url": "site-wide", **f} for f in diff["site_new_findings"]]
    if all_new:
        for f in sorted(all_new, key=lambda x: 0 if x["severity"] == "immediate" else 1):
            icon = "🔴" if f["severity"] == "immediate" else "⚠️"
            lines.append(f"- {icon} **{f['label']}** ({f['page_url']}): {f['detail']}")
    else:
        lines.append("None — no new problems since the last check.")
    lines.append("")

    lines.append("## Got worse since last check")
    lines.append("")
    all_worsened = diff["worsened_findings"] + diff["site_worsened_findings"]
    if all_worsened:
        for f in all_worsened:
            lines.append(f"- ⚠️ **{f['label']}**: {f['old_severity']} → {f['new_severity']} — {f['detail']}")
    else:
        lines.append("None.")
    lines.append("")

    lines.append("## Resolved since last check")
    lines.append("")
    all_resolved = diff["resolved_findings"] + [{"page_url": "site-wide", **f} for f in diff["site_resolved_findings"]]
    if all_resolved:
        for f in all_resolved:
            lines.append(f"- ✅ **{f['label']}** ({f['page_url']}): {f['detail']}")
    else:
        lines.append("None.")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Diff two audit.py JSON reports for the same site.")
    parser.add_argument("--old", required=True, help="Path to the earlier audit.json")
    parser.add_argument("--new", required=True, help="Path to the more recent audit.json")
    parser.add_argument("--out", default="maintenance-diff.md", help="Where to write the Markdown diff report")
    args = parser.parse_args()

    with open(args.old, "r", encoding="utf-8") as f:
        old_data = json.load(f)
    with open(args.new, "r", encoding="utf-8") as f:
        new_data = json.load(f)

    diff = build_diff(old_data, new_data)
    report = render_markdown(diff)

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Business: {diff['business_name']}")
    print(f"Score: {diff['old_score']} -> {diff['new_score']}")
    print(f"Pages now failing: {len(diff['pages_now_failing'])}")
    print(f"New findings: {len(diff['new_findings']) + len(diff['site_new_findings'])}")
    print(f"Resolved findings: {len(diff['resolved_findings']) + len(diff['site_resolved_findings'])}")
    print(f"Diff report written to {args.out}")


if __name__ == "__main__":
    main()
