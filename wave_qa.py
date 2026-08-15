#!/usr/bin/env python3
"""
wave_qa.py

Runs once after a bulk page launch (a "wave" — see junefruit-hq/CLAUDE.md
Section 2 for why waves exist at all: building density of trustworthy,
crawler-legible pages fast, per Mario's methodology) to verify every new
page meets the standard before it's considered done. Applies six checks
as HARD GATES — a failure on any check means the page is rejected, not
just flagged:

    1. HTTP 200 status
    2. Schema (JSON-LD) presence + valid JSON
    3. Sitemap inclusion
    4. Hub linking (new page is linked from at least one hub/parent page)
    5. Meta title/description uniqueness across the wave
    6. Cross-page duplicate content (near-duplicate detection)

Originally built inside the WePipe project (as post-wave-qa.py) and
promoted here 2026-08-14 once it became clear it was already
client-agnostic (fully parameterized via CLI flags, no hardcoded paths
or content) -- same story as audit.py/remediate.py's own promotion.

SCOPE, HONESTLY: fetches are raw HTTP requests, no JS execution. This is
the right fidelity for a static-first build (what WePipe is), but will
silently under-report for a client on a JS-heavy stack -- audit.py
solved the equivalent problem with an optional playwright-based
raw-vs-rendered check; this script doesn't have that fallback yet. Know
your client's stack before trusting a clean wave_qa run at face value.

This script does NOT judge whether the actual prose content is accurate
or genuinely locally-specific vs. generic -- only mechanical checks
(links, schema, uniqueness-by-text-similarity). Real content quality
control is a separate, harder, still-unsolved problem -- see
junefruit-hq/CLAUDE.md Section 7's gap entry.

USAGE
    pip install requests beautifulsoup4

    python wave_qa.py \
        --urls wave-urls.txt \
        --sitemap https://example.com/sitemap.xml \
        --hubs hub-urls.txt \
        --out wave-qa-report.md

INPUT FILES
    wave-urls.txt   One URL per line -- the new pages launched this wave.
    hub-urls.txt    One URL per line -- the hub/parent pages that SHOULD
                    link to the new pages (e.g. a service hub, an
                    "Emergency Service" hub, a town-cluster hub page).

EXIT CODE
    0  -- every page in the wave passed all six checks
    1  -- at least one page failed at least one check (the wave should
         not be considered shippable until this is 0)
"""

import argparse
import difflib
import json
import re
import sys
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup

TIMEOUT = 15
USER_AGENT = "Junefruit-QA-Bot/1.0 (+internal SEO wave QA script)"
DUPLICATE_SIMILARITY_THRESHOLD = 0.85  # >= this ratio between two pages' body text = flagged as duplicate content


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------

@dataclass
class PageResult:
    url: str
    http_ok: bool = False
    status_code: int | None = None
    schema_ok: bool = False
    schema_errors: list = field(default_factory=list)
    sitemap_ok: bool = False
    hub_linked: bool = False
    title: str | None = None
    description: str | None = None
    meta_unique: bool = True
    duplicate_of: list = field(default_factory=list)
    fetch_error: str | None = None

    @property
    def passed(self) -> bool:
        if self.fetch_error:
            return False
        return all([
            self.http_ok,
            self.schema_ok,
            self.sitemap_ok,
            self.hub_linked,
            self.meta_unique,
            not self.duplicate_of,
        ])


# --------------------------------------------------------------------------
# Fetching
# --------------------------------------------------------------------------

def fetch(url: str) -> tuple[requests.Response | None, str | None]:
    """Raw HTTP GET, no JS. Returns (response, error_message)."""
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT,
            allow_redirects=True,
        )
        return resp, None
    except requests.RequestException as e:
        return None, str(e)


def fetch_text(url: str) -> tuple[str | None, str | None]:
    """Fetch a plaintext resource (sitemap.xml, hub page HTML). Returns (text, error)."""
    resp, err = fetch(url)
    if err:
        return None, err
    if resp.status_code != 200:
        return None, f"HTTP {resp.status_code}"
    return resp.text, None


# --------------------------------------------------------------------------
# Individual checks
# --------------------------------------------------------------------------

def check_http_status(url: str, resp: requests.Response) -> tuple[bool, int]:
    return resp.status_code == 200, resp.status_code


def check_schema(html: str) -> tuple[bool, list]:
    """Confirms at least one valid JSON-LD block exists on the page."""
    soup = BeautifulSoup(html, "html.parser")
    scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
    errors = []

    if not scripts:
        return False, ["No <script type='application/ld+json'> block found"]

    valid_found = False
    for i, tag in enumerate(scripts):
        raw = tag.string or tag.get_text()
        try:
            json.loads(raw)
            valid_found = True
        except (json.JSONDecodeError, TypeError) as e:
            errors.append(f"Schema block {i} is invalid JSON: {e}")

    return valid_found, errors


def parse_sitemap_urls(sitemap_xml: str) -> set:
    """Extracts every <loc> URL from a sitemap.xml (handles sitemap index files too)."""
    soup = BeautifulSoup(sitemap_xml, "xml")
    return {loc.get_text().strip() for loc in soup.find_all("loc")}


def check_sitemap_inclusion(url: str, sitemap_urls: set) -> bool:
    normalized = url.rstrip("/")
    return normalized in {u.rstrip("/") for u in sitemap_urls} or url in sitemap_urls


def check_hub_linking(url: str, hub_link_targets: set) -> bool:
    normalized = url.rstrip("/")
    return normalized in {u.rstrip("/") for u in hub_link_targets}


def extract_meta(html: str) -> tuple[str | None, str | None]:
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("title")
    title = title_tag.get_text().strip() if title_tag else None

    desc_tag = soup.find("meta", attrs={"name": "description"})
    description = desc_tag.get("content", "").strip() if desc_tag else None

    return title, description


def extract_body_text(html: str) -> str:
    """Pulls main readable text for duplicate-content comparison.
    Strips nav/header/footer/script/style so shared site chrome doesn't
    inflate the similarity score between unrelated pages."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def similarity(a: str, b: str) -> float:
    """autojunk=False is required here, not optional: SequenceMatcher's
    default autojunk=True treats any character appearing in >1% of a
    string over ~200 chars as "popular junk" and excludes it from
    matching -- for real page-body prose (not the diff-tool
    line-comparison case autojunk was designed for), this silently
    deflates scores badly. Found 2026-08-15 while building
    site_coverage_index.py and testing it against a real positive case:
    two 211-char near-identical strings scored 0.68 with the default,
    0.995 with autojunk=False. This means DUPLICATE_SIMILARITY_THRESHOLD
    (0.85) has likely been under-detecting real duplicate content in
    every wave_qa.py run before this fix -- the threshold itself hasn't
    been re-validated against real data with the corrected metric yet."""
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


# --------------------------------------------------------------------------
# Main orchestration
# --------------------------------------------------------------------------

def load_lines(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


def collect_hub_link_targets(hub_urls: list) -> set:
    """Fetches every hub page and collects the absolute hrefs it links to."""
    targets = set()
    for hub_url in hub_urls:
        html, err = fetch_text(hub_url)
        if err:
            print(f"  ! Could not fetch hub page {hub_url}: {err}", file=sys.stderr)
            continue
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("http"):
                targets.add(href)
            elif href.startswith("/"):
                # Resolve relative to the hub's own origin
                base = re.match(r"^(https?://[^/]+)", hub_url)
                if base:
                    targets.add(base.group(1) + href)
    return targets


def run_qa(urls: list, sitemap_source: str, hub_urls: list) -> list:
    print(f"Fetching sitemap: {sitemap_source}")
    sitemap_text, sm_err = fetch_text(sitemap_source) if sitemap_source.startswith("http") else (open(sitemap_source, encoding="utf-8").read(), None)
    if sm_err:
        print(f"  ! Could not fetch sitemap: {sm_err}", file=sys.stderr)
        sitemap_urls = set()
    else:
        sitemap_urls = parse_sitemap_urls(sitemap_text)
        print(f"  {len(sitemap_urls)} URLs found in sitemap")

    print(f"Fetching {len(hub_urls)} hub page(s) to build the linking index...")
    hub_link_targets = collect_hub_link_targets(hub_urls)
    print(f"  {len(hub_link_targets)} unique outbound links found across hub pages")

    results = []
    page_bodies = {}  # url -> body text, for cross-page duplicate check

    print(f"\nChecking {len(urls)} page(s) in this wave...\n")
    for url in urls:
        r = PageResult(url=url)
        resp, err = fetch(url)

        if err or resp is None:
            r.fetch_error = err or "Unknown fetch error"
            results.append(r)
            print(f"  ✗ {url} — FETCH FAILED ({r.fetch_error})")
            continue

        r.http_ok, r.status_code = check_http_status(url, resp)

        if r.http_ok:
            html = resp.text
            r.schema_ok, r.schema_errors = check_schema(html)
            r.sitemap_ok = check_sitemap_inclusion(url, sitemap_urls)
            r.hub_linked = check_hub_linking(url, hub_link_targets)
            r.title, r.description = extract_meta(html)
            page_bodies[url] = extract_body_text(html)

        results.append(r)
        status = "PASS (pending duplicate/meta cross-check)" if r.http_ok else f"FAIL (HTTP {r.status_code})"
        print(f"  {'✓' if r.http_ok else '✗'} {url} — {status}")

    # --- Cross-page checks: meta uniqueness ---
    title_map: dict = {}
    desc_map: dict = {}
    for r in results:
        if r.title:
            title_map.setdefault(r.title, []).append(r.url)
        if r.description:
            desc_map.setdefault(r.description, []).append(r.url)

    for r in results:
        if r.title and len(title_map.get(r.title, [])) > 1:
            r.meta_unique = False
        if r.description and len(desc_map.get(r.description, [])) > 1:
            r.meta_unique = False

    # --- Cross-page checks: duplicate content ---
    urls_with_body = list(page_bodies.keys())
    for i, url_a in enumerate(urls_with_body):
        for url_b in urls_with_body[i + 1:]:
            sim = similarity(page_bodies[url_a], page_bodies[url_b])
            if sim >= DUPLICATE_SIMILARITY_THRESHOLD:
                a_result = next(r for r in results if r.url == url_a)
                b_result = next(r for r in results if r.url == url_b)
                a_result.duplicate_of.append((url_b, round(sim, 3)))
                b_result.duplicate_of.append((url_a, round(sim, 3)))

    return results


def build_report(results: list) -> str:
    passed = [r for r in results if r.passed]
    failed = [r for r in results if not r.passed]

    lines = [
        "# Wave QA Report",
        "",
        f"**Pages checked:** {len(results)}  ",
        f"**Passed:** {len(passed)}  ",
        f"**Failed:** {len(failed)}",
        "",
        "---",
        "",
    ]

    if failed:
        lines.append("## ❌ Failed pages (must fix before this wave ships)\n")
        for r in failed:
            lines.append(f"### {r.url}")
            if r.fetch_error:
                lines.append(f"- **Fetch error:** {r.fetch_error}")
            else:
                if not r.http_ok:
                    lines.append(f"- **HTTP status:** {r.status_code} (expected 200)")
                if not r.schema_ok:
                    lines.append(f"- **Schema:** missing or invalid — {'; '.join(r.schema_errors)}")
                if not r.sitemap_ok:
                    lines.append("- **Sitemap:** URL not found in sitemap.xml")
                if not r.hub_linked:
                    lines.append("- **Hub linking:** no hub page links to this URL")
                if not r.meta_unique:
                    lines.append(f"- **Meta uniqueness:** title or description duplicated elsewhere in the wave")
                if r.duplicate_of:
                    dupes = ", ".join(f"{u} ({sim*100:.1f}% similar)" for u, sim in r.duplicate_of)
                    lines.append(f"- **Duplicate content:** too similar to {dupes}")
            lines.append("")

    if passed:
        lines.append("## ✅ Passed pages\n")
        for r in passed:
            lines.append(f"- {r.url}")
        lines.append("")

    return "\n".join(lines)


def main():
    # Windows consoles often default to a codepage (e.g. cp1252) that
    # can't encode the check/cross marks this script prints -- crashes
    # mid-run otherwise. Force UTF-8 stdout/stderr defensively rather
    # than stripping the marks, so future non-ASCII output doesn't
    # silently reopen this same crash.
    if sys.stdout.encoding is None or sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Post-wave SEO QA for a batch of newly launched pages.")
    parser.add_argument("--urls", required=True, help="Path to a text file, one new page URL per line")
    parser.add_argument("--sitemap", required=True, help="Sitemap URL (https://...) or local path to sitemap.xml")
    parser.add_argument("--hubs", required=True, help="Path to a text file, one hub/parent page URL per line")
    parser.add_argument("--out", default="wave-qa-report.md", help="Where to write the Markdown report")
    args = parser.parse_args()

    urls = load_lines(args.urls)
    hub_urls = load_lines(args.hubs)

    results = run_qa(urls, args.sitemap, hub_urls)
    report = build_report(results)

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(report)

    failed_count = sum(1 for r in results if not r.passed)
    print(f"\n{'='*60}")
    print(f"Report written to {args.out}")
    print(f"{len(results) - failed_count}/{len(results)} pages passed all six checks.")
    print(f"{'='*60}")

    sys.exit(1 if failed_count else 0)


if __name__ == "__main__":
    main()
