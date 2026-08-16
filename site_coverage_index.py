#!/usr/bin/env python3
"""
site_coverage_index.py

Companion to wave_qa.py, but for BEFORE a page gets built, not after.
wave_qa.py fetches live URLs and flags cross-page duplicate content
across an already-published wave; this script reads a client's local
content data files (the JSON that feeds Astro's `areas`/`serviceAreas`
collections, or any similarly-shaped content directory) and answers two
questions before any new page is proposed: (1) does this exact
town x service page already exist -- a real duplicate, not a maybe, and
(2) is any existing page's narrative suspiciously similar to another's
under a different slug -- the "duplicate content under varied slugs"
failure mode named directly in CLAUDE.md and in Mario's own audit
methodology notes.

This is also the first real implementation of the "service x area
matrix" concept from Mario's methodology (LIVE/QUEUED/GAP/N/A per cell)
-- deliberately a narrower slice of it: this script can only report
what's actually built (LIVE) vs not (MISSING). QUEUED/GAP/N/A require
knowing business intent and demand this script has no way to infer --
that's a human judgment layered on top of this raw inventory, not
something to fake here.

USAGE
    Coverage/inventory mode (default) -- run before proposing any new
    pages, to see the current matrix and catch existing problems:
        python site_coverage_index.py --content-dir src/content \
            --out site-coverage-report.md

    Pre-check mode -- run before building ONE specific new page, to
    check it wouldn't be a real or near-duplicate of something that
    already exists:
        python site_coverage_index.py --content-dir src/content \
            --check-town ridgewood --check-service hvac-systems
        python site_coverage_index.py --content-dir src/content \
            --check-town ridgewood --check-text-file draft-narrative.txt

INPUT
    Expects `<content-dir>/areas/*.json` and/or
    `<content-dir>/service-areas/*.json`, matching the shape WePipe's
    `areas`/`serviceAreas` collections already use (slug, name/townName,
    townSlug, service, serviceName, introParagraph1, introParagraph2,
    ...). Missing fields degrade gracefully rather than crashing --
    a page just shows up with blanks, not a stack trace.

OUTPUT
    Coverage mode: a Markdown report with the town x service matrix,
    any slug collisions found, and any duplicate-content pairs found.
    Pre-check mode: prints directly to stdout, no file written --
    meant to be a quick yes/no before writing a new content file.

EXIT CODE
    0 -- no slug collisions, no duplicate-content pairs (coverage mode);
         no exact-duplicate cell and no high-similarity match (pre-check mode)
    1 -- a real problem found in either mode
"""

import argparse
import difflib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.stdout.encoding is None or sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

DUPLICATE_SIMILARITY_THRESHOLD = 0.85  # same threshold as wave_qa.py's live-page check, for consistency
# Re-validated 2026-08-15 against real WePipe content -- see the matching
# note in wave_qa.py for the actual numbers. Same threshold, same margin.


@dataclass
class PageEntry:
    kind: str  # "area" or "service-area"
    file_path: str
    slug: str
    town_slug: str
    town_name: str
    service: str | None  # None for area pages
    service_name: str | None
    narrative_text: str


def load_pages(content_dir: Path) -> list:
    """Never raises on a malformed file -- prints a warning and skips it,
    since one bad JSON file shouldn't stop the whole coverage check from
    running (the other pages are still worth reporting on)."""
    pages = []

    for kind, subdir in (("area", "areas"), ("service-area", "service-areas")):
        d = content_dir / subdir
        if not d.exists():
            continue
        for f in sorted(d.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                print(f"  ! Skipping {f}: {e}", file=sys.stderr)
                continue

            narrative = " ".join(filter(None, [data.get("introParagraph1", ""), data.get("introParagraph2", "")])).strip()

            if kind == "area":
                pages.append(PageEntry(
                    kind="area", file_path=str(f),
                    slug=data.get("slug", ""), town_slug=data.get("slug", ""),
                    town_name=data.get("name", ""), service=None, service_name=None,
                    narrative_text=narrative,
                ))
            else:
                pages.append(PageEntry(
                    kind="service-area", file_path=str(f),
                    slug=data.get("slug", ""), town_slug=data.get("townSlug", ""),
                    town_name=data.get("townName") or data.get("name", ""),
                    service=data.get("service"), service_name=data.get("serviceName"),
                    narrative_text=narrative,
                ))

    return pages


def find_slug_collisions(pages: list) -> list:
    """Area slugs and service-area slugs are different namespaces by
    design (e.g. 'ridgewood' vs 'plumbing-ridgewood'), so collisions are
    only checked within each kind, not across both."""
    by_kind = {}
    for p in pages:
        by_kind.setdefault(p.kind, {}).setdefault(p.slug, []).append(p.file_path)

    collisions = []
    for kind, slugs in by_kind.items():
        for slug, files in slugs.items():
            if len(files) > 1:
                collisions.append((f"{kind}:{slug}", files))
    return collisions


def similarity(a: str, b: str) -> float:
    """autojunk=False is required here, not optional: SequenceMatcher's
    default autojunk=True treats any character appearing in >1% of a
    string over ~200 chars as "popular junk" and excludes it from
    matching -- for real prose text (not the diff-tool line-comparison
    case it was designed for), this silently deflates scores badly.
    Verified directly: two 211-char strings differing by one character
    scored 0.68 with the default, 0.995 with autojunk=False -- the true
    similarity."""
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def find_duplicate_content(pages: list) -> list:
    """Pairwise narrative similarity across ALL pages regardless of kind
    or service -- catches the exact failure mode named in CLAUDE.md:
    'duplicate content under varied slugs.' Skips pages with no
    narrative text (a page that hasn't had real content written yet
    shouldn't false-positive as a duplicate of another empty page)."""
    duplicates = []
    for i in range(len(pages)):
        for j in range(i + 1, len(pages)):
            a, b = pages[i], pages[j]
            if not a.narrative_text or not b.narrative_text:
                continue
            sim = similarity(a.narrative_text, b.narrative_text)
            if sim >= DUPLICATE_SIMILARITY_THRESHOLD:
                duplicates.append((a, b, round(sim, 3)))
    return duplicates


def build_matrix(pages: list) -> tuple:
    """Returns (towns_dict, sorted_service_list). The service axis is
    derived from whatever services actually appear in the data, not a
    hardcoded list -- keeps this script portable to any future client
    with a different set of services, not just WePipe's four."""
    towns = {}
    services = set()

    for p in pages:
        entry = towns.setdefault(p.town_slug, {"town_name": p.town_name, "area": None, "services": {}})
        if p.town_name and not entry["town_name"]:
            entry["town_name"] = p.town_name
        if p.kind == "area":
            entry["area"] = p
        else:
            entry["services"][p.service] = p
            if p.service:
                services.add(p.service)

    return towns, sorted(services)


def check_candidate(pages: list, town_slug: str, service: str | None, candidate_text: str | None) -> dict:
    exact_duplicate = None
    for p in pages:
        is_area_match = service is None and p.kind == "area" and p.town_slug == town_slug
        is_service_match = service is not None and p.town_slug == town_slug and p.service == service
        if is_area_match or is_service_match:
            exact_duplicate = p.file_path
            break

    similar_to = []
    if candidate_text:
        for p in pages:
            if not p.narrative_text:
                continue
            sim = similarity(candidate_text, p.narrative_text)
            if sim >= DUPLICATE_SIMILARITY_THRESHOLD:
                similar_to.append((p.file_path, round(sim, 3)))

    return {"exact_duplicate": exact_duplicate, "similar_to": similar_to}


def render_report(pages: list, collisions: list, duplicates: list, towns: dict, services: list) -> str:
    lines = [
        "# Site Coverage Index",
        "",
        f"**Pages scanned:** {len(pages)} ({sum(1 for p in pages if p.kind == 'area')} area, "
        f"{sum(1 for p in pages if p.kind == 'service-area')} service×area)  ",
        f"**Towns covered:** {len(towns)}  ",
        f"**Slug collisions:** {len(collisions)}  ",
        f"**Duplicate-content pairs:** {len(duplicates)}",
        "",
        "---",
        "",
        "## Service × Town Matrix",
        "",
        "LIVE = page exists. MISSING = no page found for that cell. This "
        "script only reports what's actually built -- QUEUED/GAP/N/A "
        "(per Mario's methodology) requires knowing business intent this "
        "script can't infer, layer that judgment on top of this raw view.",
        "",
    ]

    if towns:
        header = "| Town | Area Page | " + " | ".join(services) + " |"
        sep = "|---|---|" + "---|" * len(services)
        lines.append(header)
        lines.append(sep)
        for town_slug in sorted(towns):
            t = towns[town_slug]
            row = [t["town_name"] or town_slug]
            row.append("LIVE" if t["area"] else "MISSING")
            for svc in services:
                row.append("LIVE" if t["services"].get(svc) else "MISSING")
            lines.append("| " + " | ".join(row) + " |")
    else:
        lines.append("No pages found in the given content directory.")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Slug Collisions")
    lines.append("")
    if collisions:
        for slug, files in collisions:
            lines.append(f"- **{slug}** appears in {len(files)} files: {', '.join(files)}")
    else:
        lines.append("None found.")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Duplicate Content (under varied slugs)")
    lines.append("")
    if duplicates:
        lines.append(
            f"Pairs with narrative-text similarity >= {DUPLICATE_SIMILARITY_THRESHOLD} "
            "-- same threshold wave_qa.py uses for live pages, applied here to "
            "content before it's ever published."
        )
        lines.append("")
        for a, b, sim in duplicates:
            lines.append(f"- **{sim}** similarity: `{a.file_path}` vs `{b.file_path}`")
    else:
        lines.append("None found.")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Check existing content coverage before proposing new pages.")
    parser.add_argument("--content-dir", required=True, help="Path to the content directory, e.g. src/content (expects areas/ and/or service-areas/ subfolders)")
    parser.add_argument("--out", default="site-coverage-report.md", help="Where to write the Markdown report (coverage mode only)")
    parser.add_argument("--check-town", help="Pre-check mode: town slug for a proposed new page")
    parser.add_argument("--check-service", help="Pre-check mode: service value for a proposed new service×area page (omit for an area page)")
    parser.add_argument("--check-text-file", help="Pre-check mode: path to a text file with the proposed page's narrative, to check similarity against existing pages")
    args = parser.parse_args()

    content_dir = Path(args.content_dir)
    if not content_dir.exists():
        print(f"Content directory not found: {content_dir}", file=sys.stderr)
        sys.exit(1)

    pages = load_pages(content_dir)

    if args.check_town:
        candidate_text = None
        if args.check_text_file:
            candidate_text = Path(args.check_text_file).read_text(encoding="utf-8")

        result = check_candidate(pages, args.check_town, args.check_service, candidate_text)

        label = f"{args.check_service} × {args.check_town}" if args.check_service else f"area page × {args.check_town}"
        print(f"Checking: {label}")

        if result["exact_duplicate"]:
            print(f"EXACT DUPLICATE -- this page already exists: {result['exact_duplicate']}")
        else:
            print("No exact duplicate -- this cell is currently MISSING, safe to build.")

        if result["similar_to"]:
            print(f"\n{len(result['similar_to'])} existing page(s) are suspiciously similar to the provided text:")
            for path, sim in result["similar_to"]:
                print(f"  - {sim} similarity: {path}")
        elif candidate_text:
            print("No high-similarity matches against existing narrative content.")

        sys.exit(1 if (result["exact_duplicate"] or result["similar_to"]) else 0)

    # Coverage mode
    collisions = find_slug_collisions(pages)
    duplicates = find_duplicate_content(pages)
    towns, services = build_matrix(pages)

    report = render_report(pages, collisions, duplicates, towns, services)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Pages scanned: {len(pages)}")
    print(f"Towns covered: {len(towns)}")
    print(f"Slug collisions: {len(collisions)}")
    print(f"Duplicate-content pairs: {len(duplicates)}")
    print(f"Report written to {args.out}")

    sys.exit(1 if (collisions or duplicates) else 0)


if __name__ == "__main__":
    main()
