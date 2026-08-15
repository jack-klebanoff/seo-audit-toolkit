#!/usr/bin/env python3
"""
page_ratio_check.py

Compares a client's current page-type counts against a proven reference
ratio -- not "how many pages do you have" but "are your page TYPES
proportionally balanced the way a site that's actually working is
balanced." Built 2026-08-15 after counting All Seasons Home Inspection's
real sitemap (763 pages) and finding a site that's been operating a long
time keeps its page types in a fairly consistent ratio to each other:
roughly 1 area page : 3 service-per-town pages : 0.3 blog posts : 0.09
core/utility pages.

WHY THIS MATTERS: raw page count (22 vs 763) tells you the scale gap.
It doesn't tell you whether the pages you DO have are proportionally
where a proven site would have them. A site that's built 12 blog posts
and only 1 area page isn't "12/763 of the way there" on blog content --
relative to its own area-page count, it's already WAY ahead of the
proven ratio on blog, and WAY behind on service-per-town pages. That's
a real, actionable signal: the priority gap right now is service×town
coverage, not more blog content.

REFERENCE RATIO SOURCE: All Seasons Home Inspection (4allseasons.biz),
counted directly from their real, live sitemap.xml on 2026-08-15 (not
estimated) -- 174 area pages, 521 service×town pages (179 mold-testing +
179 air-quality + 163 home-inspection), 52 blog posts, 16 core/utility
pages. This is ONE reference site, not an industry standard -- treat the
ratio as a real, useful data point, not gospel. It will get more
trustworthy if/when a second real high-volume site is ever counted the
same way.

CAVEAT, IMPORTANT: ratios are unstable and can look dramatic at small
sample sizes. A site with 1 area page and 12 blog posts isn't
necessarily "40x over-indexed on blog" in any meaningful sense -- it's
too early for the ratio to mean much yet. This script flags that
explicitly rather than pretending a ratio computed from single-digit
counts carries the same weight as one computed from hundreds.

USAGE
    python page_ratio_check.py --area 1 --service-town 1 --blog 12 --core 8 \
        --site-name "WePipe" --out page-ratio-report.md

    Or from a JSON file:
    python page_ratio_check.py --data counts.json --out page-ratio-report.md

INPUT (--data JSON shape)
    {"site_name": "...", "area_pages": N, "service_town_pages": N,
     "blog_posts": N, "core_pages": N}
"""

import argparse
import json

REFERENCE = {
    "source": "All Seasons Home Inspection (4allseasons.biz) -- 763 total pages, counted from their real sitemap.xml, 2026-08-15",
    "area_pages": 174,
    "service_town_pages": 521,
    "blog_posts": 52,
    "core_pages": 16,
}

SMALL_SAMPLE_THRESHOLD = 10  # area-page count below which ratio findings get an explicit low-confidence flag


def compute_ratios(counts: dict) -> dict:
    area = counts["area_pages"]
    if area == 0:
        return {k: None for k in ("service_town_per_area", "blog_per_area", "core_per_area")}
    return {
        "service_town_per_area": counts["service_town_pages"] / area,
        "blog_per_area": counts["blog_posts"] / area,
        "core_per_area": counts["core_pages"] / area,
    }


def reference_ratios() -> dict:
    area = REFERENCE["area_pages"]
    return {
        "service_town_per_area": REFERENCE["service_town_pages"] / area,
        "blog_per_area": REFERENCE["blog_posts"] / area,
        "core_per_area": REFERENCE["core_pages"] / area,
    }


def build_report(counts: dict) -> str:
    site_name = counts.get("site_name", "Unknown site")
    actual = compute_ratios(counts)
    ref = reference_ratios()
    low_confidence = counts["area_pages"] < SMALL_SAMPLE_THRESHOLD

    lines = [
        f"# Page-Type Ratio Report — {site_name}",
        "",
        f"**Reference:** {REFERENCE['source']}",
        f"**Reference shape:** 1 area page : {ref['service_town_per_area']:.2f} service×town pages : "
        f"{ref['blog_per_area']:.2f} blog posts : {ref['core_per_area']:.2f} core/utility pages",
        "",
    ]

    if low_confidence:
        lines.append(
            f"⚠️ **Low-confidence flag:** {site_name} has only {counts['area_pages']} area page(s) — "
            f"below the {SMALL_SAMPLE_THRESHOLD}-page threshold where a ratio starts to mean much. "
            f"Treat the findings below as an early directional signal, not a precise gap measurement."
        )
        lines.append("")

    lines.append(f"**Current counts:** {counts['area_pages']} area, {counts['service_town_pages']} service×town, "
                  f"{counts['blog_posts']} blog, {counts['core_pages']} core")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Ratio comparison (per 1 area page)")
    lines.append("")
    lines.append("| Type | Reference ratio | Actual ratio | At reference ratio, expected count | Actual count | Signal |")
    lines.append("|---|---|---|---|---|---|")

    for key, label, count_key in [
        ("service_town_per_area", "Service×town pages", "service_town_pages"),
        ("blog_per_area", "Blog posts", "blog_posts"),
        ("core_per_area", "Core/utility pages", "core_pages"),
    ]:
        expected = ref[key] * counts["area_pages"]
        actual_count = counts[count_key]
        if actual == {} or actual[key] is None:
            signal = "n/a (0 area pages)"
        elif actual_count < expected * 0.7:
            signal = "🔴 under-indexed — priority gap"
        elif actual_count > expected * 1.5:
            signal = "⚠️ over-indexed relative to area-page count"
        else:
            signal = "✅ roughly in line"
        actual_display = f"{actual[key]:.2f}" if actual[key] is not None else "n/a"
        lines.append(
            f"| {label} | {ref[key]:.2f} | {actual_display} "
            f"| {expected:.1f} | {actual_count} | {signal} |"
        )

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        "**What this does NOT tell you:** whether any individual page is any good — that's "
        "`content_bar_check.py` and `content-qc`'s job, not this script's. This only measures "
        "whether the *mix* of page types is proportionally where a proven site's mix sits, given "
        "how many area pages currently exist. A site can be perfectly balanced by this ratio and "
        "still have thin or inaccurate content -- balance and quality are separate questions."
    )

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Compare a site's page-type counts against the All Seasons reference ratio.")
    parser.add_argument("--data", default=None, help="Path to a JSON file with site_name/area_pages/service_town_pages/blog_posts/core_pages")
    parser.add_argument("--site-name", default=None, help="Site name (if not using --data)")
    parser.add_argument("--area", type=int, default=None, help="Area page count (if not using --data)")
    parser.add_argument("--service-town", type=int, default=None, help="Service x town page count (if not using --data)")
    parser.add_argument("--blog", type=int, default=None, help="Blog/informational post count (if not using --data)")
    parser.add_argument("--core", type=int, default=None, help="Core/utility page count (if not using --data)")
    parser.add_argument("--out", default="page-ratio-report.md", help="Where to write the Markdown report")
    args = parser.parse_args()

    if args.data:
        with open(args.data, "r", encoding="utf-8") as f:
            counts = json.load(f)
    else:
        missing = [n for n, v in [("--site-name", args.site_name), ("--area", args.area), ("--service-town", args.service_town), ("--blog", args.blog), ("--core", args.core)] if v is None]
        if missing:
            parser.error(f"Either --data, or all of --site-name/--area/--service-town/--blog/--core are required. Missing: {', '.join(missing)}")
        counts = {
            "site_name": args.site_name,
            "area_pages": args.area,
            "service_town_pages": args.service_town,
            "blog_posts": args.blog,
            "core_pages": args.core,
        }

    report = build_report(counts)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Site: {counts.get('site_name', 'Unknown')}")
    print(f"Counts: area={counts['area_pages']}, service-town={counts['service_town_pages']}, blog={counts['blog_posts']}, core={counts['core_pages']}")
    print(f"Report written to {args.out}")


if __name__ == "__main__":
    main()
