#!/usr/bin/env python3
"""
audit.py

The cold-outreach sales weapon: "I ran a free audit on your site — here's
what's costing you leads." Points this at ANY live prospect site (no repo
access, no login, no permission needed) and produces a scored, plain-English
report you can lead an outreach email or call with.

Scope is deliberately limited to what's checkable from the outside, since
Miles already owns the GA4/GSC-connected analytics side of things — this
script never needs those credentials.

SCORING — three-category rubric (Mario's methodology, see
/wiki/audit-rubric.md for the full writeup):

    1. Rendering & Technical Foundation
    2. Local Signals (NAP/GBP)
    3. Content, Trust & Depth

Each category starts at 10.0. Every finding applies a flat delta:
    Immediate (critical) finding : -1.5
    Needs Work finding           : -0.6
    Confirmed Strength           : +0.5
Category score is clamped to [0.0, 10.0]. Overall score = average of the
three category scores.

IMPORTANT: this script can only compute Category 1 (Rendering & Technical).
Category 2 (Local Signals — NAP consistency, map-pack presence, GBP review
count) and Category 3 (Content, Trust & Depth — named owner/credentials,
FAQ quality, genuine-vs-templated page depth, pricing transparency, real
photography) both require manual research a script cannot do from the
outside — no anonymous, credential-free way to query a competitor's Google
Business Profile or judge whether a paragraph is genuinely locally-specific
vs. templated. So this script outputs:

    - A real, computed score for Category 1
    - A blank fill-in-by-hand checklist for Categories 2 and 3, structured
      to match /wiki/audit-rubric.md exactly

The "Overall score" is NOT computed by this script — it can't be, until a
human fills in Categories 2 and 3. The report says so explicitly rather
than faking a number.

CHECKS (Category 1 — Rendering & Technical Foundation):

    1. Raw-vs-rendered content gap — fetches the page two ways: once with
       a raw HTTP request (roughly what a crawler's first pass sees) and
       once through a headless browser (what a human/JS-executing crawler
       sees). A big gap means real content is invisible to search engines
       on first pass.
    2. Schema (JSON-LD) presence + validity
    3. Title tag — present, length, uniqueness across the pages checked
    4. Meta description — present, length, uniqueness
    5. H1 — present, exactly one
    6. Indexability — no accidental noindex, canonical tag present
    7. robots.txt validity — fetchable, and no leftover placeholder domain
       in its Sitemap: line
    8. Broken links — same-domain links found on each page, checked for
       4xx/5xx

USAGE
    pip install requests beautifulsoup4
    # Optional but recommended — enables the raw-vs-rendered check:
    pip install playwright && playwright install chromium

    python audit.py --urls prospect-urls.txt --name "Acme Plumbing" --out acme-audit.md

INPUT
    prospect-urls.txt   One URL per line — homepage + a few key interior
                         pages (service page, an area/location page if any).

OUTPUT
    A Markdown report: a computed Category 1 score with per-page findings,
    blank Category 2 / Category 3 checklists to fill in by hand, and a
    ready-to-paste cold-outreach paragraph (Category 1 only, worded to not
    overclaim a full audit).
"""

import argparse
import datetime
import json
import re
import sys
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

TIMEOUT = 15
USER_AGENT = "FirstDribble-AuditBot/1.0 (+prospect SEO audit)"
RENDER_GAP_THRESHOLD = 0.30  # rendered word count > raw word count by more than this % = flagged
MAX_LINKS_CHECKED = 15  # cap per-page broken-link checks — be a polite crawler, not a hammer
SHINGLE_SIZE = 5  # word n-gram size for cross-page content-similarity detection
SIMILARITY_NOTABLE_THRESHOLD = 0.20  # below this, not worth mentioning in the report
SIMILARITY_HIGH_THRESHOLD = 0.55  # above this, flag as likely-templated — spot-check it

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


# --------------------------------------------------------------------------
# Scoring primitives (rubric: /wiki/audit-rubric.md)
# --------------------------------------------------------------------------

IMMEDIATE = "immediate"
NEEDS_WORK = "needs_work"
STRENGTH = "strength"  # reserved for the manual Category 2/3 checklists — see note below
PASS = "pass"  # routine passing check — automated Category 1 checks use this, not STRENGTH
INFO = "info"  # not scored — e.g. "check skipped, playwright not installed"

# BUG FIX (2026): score_technical() originally awarded STRENGTH (+0.5) for
# every routine passing check. With ~7 checks per page, enough passes
# (+0.5 each) silently swamped a real NEEDS_WORK/-0.6 deduction once the
# 10.0-ceiling clamp kicked in — e.g. 6 passes + 1 warning nets 12.4,
# clamped to 10.0, so the warning never showed up in the score at all.
# Fix: automated Category 1 checks now use PASS (delta 0.0) for routine
# passing state. Only actual problems (IMMEDIATE/NEEDS_WORK) move the
# score. STRENGTH stays defined and still carries +0.5 per the rubric,
# but is only meant for the human-judgment Category 2/3 checklists, where
# a genuine standout positive is a deliberate call, not an automatic one.
SEVERITY_DELTA = {
    IMMEDIATE: -1.5,
    NEEDS_WORK: -0.6,
    STRENGTH: 0.5,
    PASS: 0.0,
}

SEVERITY_ICON = {
    IMMEDIATE: "🔴",
    NEEDS_WORK: "⚠️",
    STRENGTH: "✅",
    PASS: "✅",
    INFO: "ℹ️",
}


@dataclass
class Finding:
    label: str
    severity: str  # IMMEDIATE | NEEDS_WORK | PASS | STRENGTH | INFO
    detail: str


def category_score(findings: list) -> float:
    """10.0 start, flat deltas per finding, clamped to [0, 10] — per the
    rubric's point system, not a weighted/possible-points fraction."""
    score = 10.0 + sum(SEVERITY_DELTA.get(f.severity, 0.0) for f in findings)
    return round(max(0.0, min(10.0, score)), 1)


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------

@dataclass
class PageAudit:
    url: str
    fetch_error: str | None = None

    raw_word_count: int = 0
    rendered_word_count: int = 0
    render_gap_pct: float | None = None
    render_checked: bool = False
    body_shingles: set = field(default_factory=set)

    phone_found: bool | None = None  # None = --phone not provided, not checked
    address_match_pct: float | None = None  # None = --address not provided, not checked

    has_schema: bool = False
    schema_valid: bool = False
    schema_types: list = field(default_factory=list)

    has_faq_schema: bool = False
    faq_question_count: int = 0

    title: str | None = None
    title_len: int = 0

    description: str | None = None
    description_len: int = 0

    h1_count: int = 0

    noindex: bool = False
    has_canonical: bool = False

    broken_links: list = field(default_factory=list)  # list of (url, status_or_error)
    links_checked: int = 0

    findings: list = field(default_factory=list)  # list[Finding]
    technical_score: float = 0.0


# --------------------------------------------------------------------------
# Fetching
# --------------------------------------------------------------------------

def fetch_raw(url: str) -> tuple[str | None, str | None]:
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
        if resp.status_code != 200:
            return None, f"HTTP {resp.status_code}"
        return resp.text, None
    except requests.RequestException as e:
        return None, str(e)


def fetch_rendered(url: str) -> tuple[str | None, str | None]:
    """Fetches the page through a real headless browser, so JS-injected
    content is present. Requires playwright + chromium installed."""
    if not PLAYWRIGHT_AVAILABLE:
        return None, "playwright not installed"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(user_agent=USER_AGENT)
            page.goto(url, timeout=TIMEOUT * 1000, wait_until="networkidle")
            html = page.content()
            browser.close()
            return html, None
    except Exception as e:
        return None, str(e)


def extract_body_text(html: str) -> str:
    """Visible body text, stripped of script/style/nav/header/footer —
    excluding the latter three matters for cross-page similarity, since
    shared nav/footer boilerplate would otherwise make every page on a
    site look artificially similar to every other page."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    return re.sub(r"\s+", " ", text).strip()


def word_count(html: str) -> int:
    text = extract_body_text(html)
    return len(text.split()) if text else 0


def content_shingles(html: str, n: int = SHINGLE_SIZE) -> set:
    """Word n-gram ('shingle') set for near-duplicate/templated-content
    detection. Two pages sharing most of their sentences verbatim (e.g.
    a location page template with just the town name swapped) will still
    share the vast majority of their shingles, since only the shingles
    that actually contain the swapped word change."""
    text = extract_body_text(html)
    words = re.findall(r"[a-z0-9']+", text.lower())
    if not words:
        return set()
    if len(words) < n:
        return {" ".join(words)}
    return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}


def jaccard_similarity(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    union = a | b
    return len(a & b) / len(union) if union else 0.0


# --------------------------------------------------------------------------
# Individual checks
# --------------------------------------------------------------------------

def _extract_types(node) -> list:
    """Pulls @type out of a single JSON-LD node. Handles the very common
    Yoast-style output where the real content lives in a top-level
    @graph array rather than @type on the outer object."""
    found = []
    if isinstance(node, dict):
        t = node.get("@type")
        if t:
            found.append(t if isinstance(t, str) else ", ".join(t))
        graph = node.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                found.extend(_extract_types(item))
    elif isinstance(node, list):
        for item in node:
            found.extend(_extract_types(item))
    return found


def _find_nodes_by_type(node, type_name: str) -> list:
    """Recursively finds JSON-LD nodes (handling @graph wrapping) whose
    @type matches type_name (case-insensitive; @type may be a string or
    a list of strings)."""
    found = []
    if isinstance(node, dict):
        t = node.get("@type")
        type_list = [t] if isinstance(t, str) else (t if isinstance(t, list) else [])
        if any(isinstance(x, str) and x.lower() == type_name.lower() for x in type_list):
            found.append(node)
        graph = node.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                found.extend(_find_nodes_by_type(item, type_name))
    elif isinstance(node, list):
        for item in node:
            found.extend(_find_nodes_by_type(item, type_name))
    return found


def check_faq_schema(html: str) -> tuple[bool, int]:
    """Detects FAQPage schema and counts its Question entities.

    This is a PRESENCE-only signal for Category 3's manual 'FAQ content
    covers real buyer questions' checklist item. It deliberately does NOT
    feed the automated Category 1 score — FAQ content quality is a
    Category 3 (Content, Trust & Depth) concern per /wiki/audit-rubric.md,
    and this script can detect that FAQPage schema exists, not whether the
    questions actually cover what real buyers ask. That judgment stays
    manual on purpose."""
    soup = BeautifulSoup(html, "html.parser")
    scripts = soup.find_all("script", attrs={"type": "application/ld+json"})

    found_faqpage = False
    question_count = 0
    for tag in scripts:
        raw = tag.string or tag.get_text()
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        for faq_node in _find_nodes_by_type(data, "FAQPage"):
            found_faqpage = True
            main_entity = faq_node.get("mainEntity")
            if isinstance(main_entity, list):
                question_count += len(main_entity)
            elif isinstance(main_entity, dict):
                question_count += 1

    return found_faqpage, question_count


def check_schema(html: str) -> tuple[bool, bool, list]:
    soup = BeautifulSoup(html, "html.parser")
    scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
    if not scripts:
        return False, False, []

    types, any_valid = [], False
    for tag in scripts:
        raw = tag.string or tag.get_text()
        try:
            data = json.loads(raw)
            any_valid = True
            types.extend(_extract_types(data))
        except (json.JSONDecodeError, TypeError):
            continue
    return True, any_valid, types


BUSINESS_SCHEMA_HINTS = ("localbusiness", "service", "organization", "business")
GENERIC_SCHEMA_TYPES = {
    "webpage", "breadcrumblist", "website", "webapplication",
    "collectionpage", "itemlist", "imageobject", "person", "article",
    "blogposting", "searchaction",
}


def has_business_schema_type(types: list) -> bool:
    """True if LocalBusiness, Service, Organization, or a recognizable
    subtype (e.g. HomeAndConstructionBusiness, ProfessionalService) is
    present among the extracted @type values."""
    for t in types:
        for part in t.split(", "):
            if any(hint in part.lower() for hint in BUSINESS_SCHEMA_HINTS):
                return True
    return False


def all_types_generic(types: list) -> bool:
    """True only if every extracted @type is a known generic/boilerplate
    type (Yoast's default WebPage/BreadcrumbList/WebSite output, etc.)
    and at least one type was found at all."""
    parts = [p.strip().lower() for t in types for p in t.split(", ")]
    return bool(parts) and all(p in GENERIC_SCHEMA_TYPES for p in parts)


def check_meta(html: str) -> tuple[str | None, str | None]:
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("title")
    title = title_tag.get_text().strip() if title_tag else None
    desc_tag = soup.find("meta", attrs={"name": "description"})
    description = desc_tag.get("content", "").strip() if desc_tag else None
    return title, description


def check_h1(html: str) -> int:
    soup = BeautifulSoup(html, "html.parser")
    return len(soup.find_all("h1"))


def check_indexability(html: str) -> tuple[bool, bool]:
    soup = BeautifulSoup(html, "html.parser")
    robots_tag = soup.find("meta", attrs={"name": "robots"})
    noindex = bool(robots_tag and "noindex" in robots_tag.get("content", "").lower())
    canonical_tag = soup.find("link", attrs={"rel": "canonical"})
    return noindex, canonical_tag is not None


# --------------------------------------------------------------------------
# NAP (Name/Address/Phone) consistency — Category 2, opt-in via --phone /
# --address CLI flags. Deliberately checks the FULL raw HTML (not the
# nav/header/footer-stripped body text used for content similarity),
# because NAP info most commonly lives in exactly those excluded spots —
# and get_text() on the unstripped document also picks up phone/address
# text embedded inside JSON-LD <script> blocks, which is a real place
# it legitimately lives too.
# --------------------------------------------------------------------------

def normalize_phone_digits(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]  # drop a leading US country code
    return digits


def check_phone_presence(html: str, expected_phone: str) -> bool:
    """Digit-sequence match, format-agnostic — (646) 338-0828, 646-338-0828,
    6463380828, and tel:+16463380828 all normalize to the same digits, so
    this catches the number regardless of how it's formatted on the page."""
    expected_digits = normalize_phone_digits(expected_phone)
    if not expected_digits:
        return False
    page_digits = re.sub(r"\D", "", html)
    return expected_digits in page_digits


def normalize_address_tokens(address: str) -> list:
    text = re.sub(r"[^\w\s]", " ", address.lower())
    return [t for t in text.split() if t]


def check_address_presence(html: str, expected_address: str) -> float:
    """Loose word-overlap heuristic, NOT exact-match — real addresses are
    formatted too many ways (St vs Street, line breaks, unit numbers) for
    substring matching to be reliable. Returns the fraction of the
    expected address's tokens found anywhere in the page's text. Always
    worth a manual glance at the flagged page, not a pass/fail on its own."""
    tokens = normalize_address_tokens(expected_address)
    if not tokens:
        return 0.0
    page_text = re.sub(r"[^\w\s]", " ", BeautifulSoup(html, "html.parser").get_text().lower())
    page_words = set(page_text.split())
    found = sum(1 for t in tokens if t in page_words)
    return found / len(tokens)


PLACEHOLDER_DOMAIN_PATTERNS = [
    "example.com", "example.org", "yourdomain", "yoursite",
    "localhost", "REPLACE_", "TODO", "domain.com",
]


def check_robots_txt(site_root: str) -> Finding:
    """Site-level check (not per-page): robots.txt fetchable, and its
    Sitemap: line (if any) doesn't point at a leftover placeholder domain."""
    robots_url = urljoin(site_root, "/robots.txt")
    try:
        resp = requests.get(robots_url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    except requests.RequestException as e:
        return Finding("robots.txt", NEEDS_WORK, f"Could not fetch {robots_url}: {e}")

    if resp.status_code != 200:
        return Finding("robots.txt", NEEDS_WORK, f"{robots_url} returned HTTP {resp.status_code}")

    body = resp.text
    sitemap_lines = [line for line in body.splitlines() if line.strip().lower().startswith("sitemap:")]

    for line in sitemap_lines:
        lowered = line.lower()
        if any(p.lower() in lowered for p in PLACEHOLDER_DOMAIN_PATTERNS):
            return Finding(
                "robots.txt",
                IMMEDIATE,
                f"Sitemap line points at a placeholder/leftover domain: \"{line.strip()}\" — "
                "search engines following this find nothing, or the wrong site entirely.",
            )
        sitemap_netloc = urlparse(line.split(":", 1)[1].strip()).netloc
        root_netloc = urlparse(site_root).netloc
        if sitemap_netloc and root_netloc and sitemap_netloc != root_netloc:
            return Finding(
                "robots.txt",
                IMMEDIATE,
                f"Sitemap line points at a different domain ({sitemap_netloc}) than the "
                f"site being audited ({root_netloc}) — likely a copy-pasted config that was "
                "never updated for this domain.",
            )

    if not sitemap_lines:
        return Finding("robots.txt", NEEDS_WORK, "robots.txt exists but has no Sitemap: line")

    return Finding("robots.txt", PASS, "robots.txt fetchable and its Sitemap: line matches this domain")


def check_broken_links(html: str, page_url: str) -> tuple[list, int]:
    """Same-domain links only, capped at MAX_LINKS_CHECKED — polite, not a
    full crawl. Returns (list of (url, problem_description), count_checked)."""
    soup = BeautifulSoup(html, "html.parser")
    page_netloc = urlparse(page_url).netloc

    candidates = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        absolute = urljoin(page_url, href)
        if urlparse(absolute).netloc != page_netloc:
            continue  # external links out of scope — this is a technical-foundation check, not a full link audit
        if absolute in seen:
            continue
        seen.add(absolute)
        candidates.append(absolute)
        if len(candidates) >= MAX_LINKS_CHECKED:
            break

    broken = []
    for link in candidates:
        try:
            resp = requests.head(link, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT, allow_redirects=True)
            if resp.status_code >= 400:
                # some servers mishandle HEAD — confirm with GET before flagging
                resp = requests.get(link, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT, allow_redirects=True)
            if resp.status_code >= 400:
                broken.append((link, f"HTTP {resp.status_code}"))
        except requests.RequestException as e:
            broken.append((link, str(e)))

    return broken, len(candidates)


# --------------------------------------------------------------------------
# Category 1 scoring — Rendering & Technical Foundation (the only category
# this script can actually compute — see module docstring)
# --------------------------------------------------------------------------

def score_technical(pa: PageAudit) -> None:
    findings = []

    # Indexability — the single most catastrophic failure if wrong
    if pa.noindex:
        findings.append(Finding("Indexability", IMMEDIATE, "Page is set to noindex — invisible to Google regardless of everything else"))
    else:
        findings.append(Finding("Indexability", PASS, "Page is indexable"))

    if pa.has_canonical:
        findings.append(Finding("Canonical tag", PASS, "Present"))
    else:
        findings.append(Finding("Canonical tag", NEEDS_WORK, "Missing — risk of duplicate-content confusion"))

    # Schema — presence AND type both matter. A page can have perfectly
    # valid JSON-LD that's still useless for local SEO if it's only the
    # generic boilerplate a plugin drops in by default (Yoast's WebPage/
    # BreadcrumbList/WebSite trio is the classic case) with no actual
    # LocalBusiness/Service/Organization entity anywhere in it.
    if pa.has_schema and pa.schema_valid:
        if has_business_schema_type(pa.schema_types):
            findings.append(Finding("Schema", PASS, f"LocalBusiness/Service/Organization-type schema present ({', '.join(pa.schema_types)})"))
        elif all_types_generic(pa.schema_types):
            findings.append(Finding(
                "Schema", NEEDS_WORK,
                f"Generic schema only — no LocalBusiness/Service schema found "
                f"(found: {', '.join(pa.schema_types)} — looks like an SEO plugin's default output, e.g. Yoast)",
            ))
        else:
            findings.append(Finding(
                "Schema", NEEDS_WORK,
                f"Schema present but no LocalBusiness/Service/Organization type found "
                f"(found: {', '.join(pa.schema_types) or 'type unknown'})",
            ))
    elif pa.has_schema:
        findings.append(Finding("Schema", NEEDS_WORK, "Schema block present but invalid JSON"))
    else:
        findings.append(Finding("Schema", IMMEDIATE, "No schema (JSON-LD) found — missing out on rich results and AI Overview eligibility"))

    # Title
    if pa.title:
        if 10 <= pa.title_len <= 70:
            findings.append(Finding("Title tag", PASS, f"Present, {pa.title_len} chars"))
        else:
            findings.append(Finding("Title tag", NEEDS_WORK, f"Present but {pa.title_len} chars — outside the effective ~10-70 char range"))
    else:
        findings.append(Finding("Title tag", IMMEDIATE, "Missing entirely — this is the single biggest lever on the page"))

    # Meta description
    if pa.description:
        if 50 <= pa.description_len <= 165:
            findings.append(Finding("Meta description", PASS, f"Present, {pa.description_len} chars"))
        else:
            findings.append(Finding("Meta description", NEEDS_WORK, f"Present but {pa.description_len} chars — outside the effective range"))
    else:
        findings.append(Finding("Meta description", NEEDS_WORK, "Missing — Google will auto-generate a snippet instead of the one you'd choose"))

    # H1
    if pa.h1_count == 1:
        findings.append(Finding("H1", PASS, "Exactly one H1"))
    elif pa.h1_count == 0:
        findings.append(Finding("H1", NEEDS_WORK, "No H1 found on the page"))
    else:
        findings.append(Finding("H1", NEEDS_WORK, f"{pa.h1_count} H1 tags found — should be exactly one"))

    # Raw-vs-rendered content gap
    if pa.render_checked:
        if pa.render_gap_pct is not None and pa.render_gap_pct <= RENDER_GAP_THRESHOLD:
            findings.append(Finding("Crawler-visible content", PASS, f"Raw HTML carries the real content (gap: {pa.render_gap_pct*100:.0f}%)"))
        else:
            gap_display = f"{pa.render_gap_pct*100:.0f}%" if pa.render_gap_pct is not None else "unmeasured"
            findings.append(Finding(
                "Crawler-visible content", IMMEDIATE,
                f"Raw HTML has {pa.raw_word_count} words vs. {pa.rendered_word_count} rendered — "
                f"a {gap_display} gap. Real content may be invisible on a crawler's first pass.",
            ))
    else:
        findings.append(Finding("Crawler-visible content", INFO, "Not checked — install playwright to enable this check"))

    # Broken links
    if pa.broken_links:
        sample = ", ".join(f"{url} ({problem})" for url, problem in pa.broken_links[:3])
        more = f" (+{len(pa.broken_links) - 3} more)" if len(pa.broken_links) > 3 else ""
        findings.append(Finding("Broken links", NEEDS_WORK, f"{len(pa.broken_links)} of {pa.links_checked} checked same-domain links are broken: {sample}{more}"))
    elif pa.links_checked > 0:
        findings.append(Finding("Broken links", PASS, f"All {pa.links_checked} checked same-domain links resolve cleanly"))
    else:
        findings.append(Finding("Broken links", INFO, "No same-domain links found to check"))

    pa.findings = findings
    pa.technical_score = category_score(findings)


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def audit_page(url: str, expected_phone: str | None = None, expected_address: str | None = None) -> PageAudit:
    pa = PageAudit(url=url)
    html, err = fetch_raw(url)
    if err:
        pa.fetch_error = err
        return pa

    pa.raw_word_count = word_count(html)
    pa.body_shingles = content_shingles(html)
    pa.has_schema, pa.schema_valid, pa.schema_types = check_schema(html)
    pa.has_faq_schema, pa.faq_question_count = check_faq_schema(html)
    if expected_phone:
        pa.phone_found = check_phone_presence(html, expected_phone)
    if expected_address:
        pa.address_match_pct = check_address_presence(html, expected_address)
    pa.title, pa.description = check_meta(html)
    pa.title_len = len(pa.title) if pa.title else 0
    pa.description_len = len(pa.description) if pa.description else 0
    pa.h1_count = check_h1(html)
    pa.noindex, pa.has_canonical = check_indexability(html)
    pa.broken_links, pa.links_checked = check_broken_links(html, url)

    if PLAYWRIGHT_AVAILABLE:
        rendered_html, r_err = fetch_rendered(url)
        if rendered_html and not r_err:
            pa.rendered_word_count = word_count(rendered_html)
            pa.render_checked = True
            if pa.raw_word_count > 0:
                pa.render_gap_pct = max(0.0, (pa.rendered_word_count - pa.raw_word_count) / pa.raw_word_count)
            else:
                pa.render_gap_pct = 1.0 if pa.rendered_word_count > 0 else 0.0

    score_technical(pa)
    return pa


def check_cross_page_uniqueness(pages: list) -> None:
    titles, descs = {}, {}
    for pa in pages:
        if pa.title:
            titles.setdefault(pa.title, []).append(pa.url)
        if pa.description:
            descs.setdefault(pa.description, []).append(pa.url)

    for pa in pages:
        added = []
        if pa.title and len(titles.get(pa.title, [])) > 1:
            added.append(Finding("Title uniqueness", NEEDS_WORK, "Duplicated on another checked page — Google needs each page to say something different"))
        if pa.description and len(descs.get(pa.description, [])) > 1:
            added.append(Finding("Meta description uniqueness", NEEDS_WORK, "Duplicated on another checked page"))
        if added:
            pa.findings.extend(added)
            pa.technical_score = category_score(pa.findings)


def compute_content_similarity(pages: list) -> list:
    """Pairwise shingle-based body-text similarity across all
    successfully-fetched pages. Returns (url_a, url_b, similarity)
    tuples at or above SIMILARITY_NOTABLE_THRESHOLD, highest first.

    PRESENCE/MEASUREMENT only — this is Category 3's 'page depth &
    uniqueness' concern per /wiki/audit-rubric.md, not Category 1. It
    surfaces which page pairs are worth a close read for templated
    ('swap the town name') content; it doesn't judge on its own whether
    that similarity is actually a problem — genuinely similar service
    pages can legitimately share structure, and this script can't tell
    the difference between that and lazy templating. That judgment
    stays manual on purpose."""
    valid = [p for p in pages if not p.fetch_error and p.body_shingles]
    pairs = []
    for i in range(len(valid)):
        for j in range(i + 1, len(valid)):
            sim = jaccard_similarity(valid[i].body_shingles, valid[j].body_shingles)
            if sim >= SIMILARITY_NOTABLE_THRESHOLD:
                pairs.append((valid[i].url, valid[j].url, sim))
    pairs.sort(key=lambda x: x[2], reverse=True)
    return pairs


def content_similarity_hint(pages: list) -> str:
    valid = [p for p in pages if not p.fetch_error and p.body_shingles]
    if len(valid) < 2:
        return "only 1 page checked — need at least 2 to compare for duplicate/templated content"

    pairs = compute_content_similarity(pages)
    if not pairs:
        return f"no notable cross-page text overlap detected among the {len(valid)} pages checked"

    shown = pairs[:5]
    parts = []
    for url_a, url_b, sim in shown:
        flag = " — likely templated, worth a close read" if sim >= SIMILARITY_HIGH_THRESHOLD else ""
        parts.append(f"{url_a} vs {url_b}: {sim*100:.0f}% overlap{flag}")
    more = f" (+{len(pairs) - 5} more pair(s) above {int(SIMILARITY_NOTABLE_THRESHOLD*100)}%)" if len(pairs) > 5 else ""
    return "; ".join(parts) + more


def generate_outreach_snippet(business_name: str, pages: list, technical_avg: float) -> str:
    valid_pages = [p for p in pages if not p.fetch_error]
    if not valid_pages:
        return "Could not generate outreach snippet — no pages were successfully fetched."

    worst_issues = []
    for p in valid_pages:
        for f in p.findings:
            if f.severity in (IMMEDIATE, NEEDS_WORK):
                worst_issues.append(f.label)
    top_issue = max(set(worst_issues), key=worst_issues.count) if worst_issues else None

    lines = [
        f"Hi — I ran a quick technical scan on {business_name}'s site "
        f"({len(valid_pages)} page{'s' if len(valid_pages) != 1 else ''} checked) and it's scoring "
        f"{technical_avg}/10 on the technical fundamentals search engines and AI answer "
        f"engines check first (full audit also covers local search signals and content depth).",
    ]
    if top_issue:
        lines.append(f"The biggest recurring gap is {top_issue.lower()} — happy to send the full breakdown if useful.")
    return " ".join(lines)


# --------------------------------------------------------------------------
# Category 2 / 3 — manual checklist templates (see /wiki/audit-rubric.md)
#
# ONE data source (CATEGORY_2_ITEMS / CATEGORY_3_ITEMS + the hint
# functions) feeds BOTH the Markdown report and the --json-out export.
# This used to be two separately-hardcoded copies of the same checklist
# text — a real risk of the two formats silently drifting apart. Never
# add a checklist item to only one of the two output formats again.
# --------------------------------------------------------------------------

CATEGORY_2_ITEMS = [
    ("nap_consistency", "NAP consistency",
     "Compare phone/address shown on-site vs. GBP vs. third-party citations "
     "(BBB, etc.) by hand — the automated hint only checks on-site presence."),
    ("map_pack_presence", "Map pack presence",
     'Search "[service] [city]" for every real market served; note 3-pack appearance.'),
    ("review_count_rating", "Review count & rating", "Pulled directly from GBP."),
    ("listing_accuracy", "Listing accuracy", "Hours, categories, duplicate/conflicting listings."),
]

CATEGORY_3_ITEMS = [
    ("named_owner_credentials", "Named owner/credentials present (E-E-A-T)", ""),
    ("faq_content_quality", "FAQ content covers real buyer questions",
     "Read the questions found and judge whether they cover real buyer questions — presence alone isn't quality."),
    ("page_depth_uniqueness", "Page depth & uniqueness",
     'Spot-check flagged pairs for templated "swap the town name" content vs. '
     "genuine local detail — legitimate similar service pages exist too, so "
     "high overlap alone isn't automatically a problem."),
    ("pricing_transparency", "Pricing transparency", ""),
    ("real_photography", "Real photography vs. stock", ""),
]


def nap_hint(pages: list, expected_phone: str | None, expected_address: str | None) -> str:
    valid = [p for p in pages if not p.fetch_error]
    if not expected_phone and not expected_address:
        return "no --phone/--address given — re-run with those flags for an automated on-site presence check"
    if not valid:
        return "no pages successfully fetched to check"

    parts = []
    if expected_phone:
        found_on = [p.url for p in valid if p.phone_found]
        if found_on:
            parts.append(f"phone ({expected_phone}) found on {len(found_on)} of {len(valid)} page(s)")
        else:
            parts.append(f"phone ({expected_phone}) NOT found on ANY of the {len(valid)} page(s) checked — verify it's published anywhere on the site at all")
    if expected_address:
        scored = [(p.url, p.address_match_pct) for p in valid if p.address_match_pct is not None]
        if scored:
            best_url, best_pct = max(scored, key=lambda x: x[1])
            parts.append(f"address word-overlap: best match {best_pct*100:.0f}% on {best_url} (loose heuristic, not exact — verify manually)")

    checked_only = "on-site presence only — this doesn't check GBP or third-party citations, that part stays manual"
    return f"{'; '.join(parts)} ({checked_only})"


def faq_schema_hint(pages: list) -> str:
    """Presence-only automated hint for the manual FAQ checklist item.
    Detects FAQPage schema + counts Question entities; does NOT judge
    whether the questions are actually good — that stays human."""
    valid_pages = [p for p in pages if not p.fetch_error]
    if not valid_pages:
        return "no pages successfully fetched to check"

    with_faq = [p for p in valid_pages if p.has_faq_schema]
    if not with_faq:
        return f"no FAQPage schema detected on any of the {len(valid_pages)} page(s) checked"

    parts = [f"{p.url} ({p.faq_question_count} question{'s' if p.faq_question_count != 1 else ''})" for p in with_faq]
    return f"FAQPage schema detected on {len(with_faq)} of {len(valid_pages)} page(s) — {', '.join(parts)}. Read them and judge whether they cover real buyer questions."


def build_category_2_checklist(pages: list, expected_phone: str | None, expected_address: str | None) -> list:
    hints = {"nap_consistency": nap_hint(pages, expected_phone, expected_address)}
    return [
        {"key": key, "label": label, "description": desc, "automated_hint": hints.get(key), "finding": None, "delta": None}
        for key, label, desc in CATEGORY_2_ITEMS
    ]


def build_category_3_checklist(pages: list) -> list:
    hints = {
        "faq_content_quality": faq_schema_hint(pages),
        "page_depth_uniqueness": content_similarity_hint(pages),
    }
    return [
        {"key": key, "label": label, "description": desc, "automated_hint": hints.get(key), "finding": None, "delta": None}
        for key, label, desc in CATEGORY_3_ITEMS
    ]


def render_checklist_markdown(heading: str, intro: str, items: list) -> str:
    lines = [f"## {heading}", "", intro, ""]
    for item in items:
        line = f"- [ ] **{item['label']}**"
        if item["description"]:
            line += f" — {item['description']}"
        lines.append(line)
        if item["automated_hint"]:
            lines.append(f"  Automated hint: {item['automated_hint']}")
        lines.append("  Finding + delta: _______")
    lines.append("")
    short_name = heading.split("—")[0].strip()
    lines.append(f"**{short_name} score (manual):** _______ / 10.0")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------

def build_report(business_name: str, pages: list, robots_finding: Finding, expected_phone: str | None = None, expected_address: str | None = None) -> str:
    valid_pages = [p for p in pages if not p.fetch_error]
    failed_pages = [p for p in pages if p.fetch_error]

    # Technical category score = average of all page technical scores plus
    # the one site-level robots.txt check, weighted equally.
    robots_score = category_score([robots_finding])
    all_technical_scores = [p.technical_score for p in valid_pages] + [robots_score]
    technical_avg = round(sum(all_technical_scores) / len(all_technical_scores), 1) if all_technical_scores else 0.0

    lines = [
        f"# SEO Audit — {business_name}",
        "",
        f"**Pages checked:** {len(pages)}  ",
        f"**Category 1 (Rendering & Technical Foundation): {technical_avg}/10** — computed",
        "**Category 2 (Local Signals):** not computed — see manual checklist below",
        "**Category 3 (Content, Trust & Depth):** not computed — see manual checklist below",
        "",
        "**Overall score:** not yet computable. Fill in Categories 2 and 3 below, "
        "then Overall = average of all three category scores (ceiling 10.0). "
        "See `/wiki/audit-rubric.md` for the full methodology.",
        "",
        "---",
        "",
        "## Category 1 — Rendering & Technical Foundation",
        "",
        f"### Site-level: robots.txt — {SEVERITY_ICON[robots_finding.severity]} {robots_finding.detail}",
        "",
    ]

    if failed_pages:
        lines.append("### Could not fetch\n")
        for p in failed_pages:
            lines.append(f"- {p.url} — {p.fetch_error}")
        lines.append("")

    for p in valid_pages:
        lines.append(f"### {p.url} — {p.technical_score}/10\n")
        for f in p.findings:
            lines.append(f"- {SEVERITY_ICON[f.severity]} **{f.label}:** {f.detail}")
        lines.append("")

    cat2_items = build_category_2_checklist(pages, expected_phone, expected_address)
    cat3_items = build_category_3_checklist(pages)

    lines.append("---\n")
    lines.append(render_checklist_markdown(
        "Category 2 — Local Signals (NAP/GBP)",
        "**Not computed by this script — no anonymous/credential-free way to query a "
        "GBP listing or third-party citations. Fill in by hand, starting from 10.0.**",
        cat2_items,
    ))
    lines.append("---\n")
    lines.append(render_checklist_markdown(
        "Category 3 — Content, Trust & Depth",
        "**Not computed by this script — requires human judgment (e.g. genuine vs. "
        "templated content, real photography vs. stock). Fill in by hand, starting "
        "from 10.0.**",
        cat3_items,
    ))
    lines.append("---\n")

    lines.append("## Cold-outreach snippet (Category 1 only — don't overclaim)\n")
    lines.append(generate_outreach_snippet(business_name, pages, technical_avg))
    lines.append("")

    if not PLAYWRIGHT_AVAILABLE:
        lines.append(
            "\n_Note: the raw-vs-rendered content check was skipped because playwright "
            "isn't installed. Run `pip install playwright && playwright install chromium` "
            "to enable it — this is often the single most persuasive finding for a prospect "
            "whose site leans on JavaScript frameworks._"
        )

    return "\n".join(lines)


def build_json_report(business_name: str, pages: list, robots_finding: Finding, expected_phone: str | None = None, expected_address: str | None = None) -> dict:
    """Machine-readable twin of build_report() — same underlying data
    (build_category_2/3_checklist, technical scores/findings), structured
    for a downstream tool to consume directly instead of parsing the
    Markdown report's prose. This is the intended foundation for a future
    remediation tool: each Category 1 finding carries a real severity +
    delta a builder could act on; Category 2/3 checklist items carry
    whatever automated hint exists plus null finding/delta slots for a
    human (or a human-reviewed AI pass) to fill in."""
    valid_pages = [p for p in pages if not p.fetch_error]

    robots_score = category_score([robots_finding])
    all_technical_scores = [p.technical_score for p in valid_pages] + [robots_score]
    technical_avg = round(sum(all_technical_scores) / len(all_technical_scores), 1) if all_technical_scores else 0.0

    def finding_dict(f: Finding) -> dict:
        return {"label": f.label, "severity": f.severity, "delta": SEVERITY_DELTA.get(f.severity, 0.0), "detail": f.detail}

    similarity_pairs = [
        {"url_a": a, "url_b": b, "similarity_pct": round(sim * 100, 1), "likely_templated": sim >= SIMILARITY_HIGH_THRESHOLD}
        for a, b, sim in compute_content_similarity(pages)
    ]

    return {
        "business_name": business_name,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "pages_checked": len(pages),
        "rubric_reference": "/wiki/audit-rubric.md",
        "input_nap": {"phone": expected_phone, "address": expected_address},
        "category_1": {
            "label": "Rendering & Technical Foundation",
            "computed": True,
            "score": technical_avg,
            "site_level": [finding_dict(robots_finding)],
            "pages": [
                {
                    "url": p.url,
                    "fetch_error": p.fetch_error,
                    "score": p.technical_score if not p.fetch_error else None,
                    "findings": [finding_dict(f) for f in p.findings],
                }
                for p in pages
            ],
        },
        "category_2": {
            "label": "Local Signals (NAP/GBP)",
            "computed": False,
            "score": None,
            "checklist": build_category_2_checklist(pages, expected_phone, expected_address),
        },
        "category_3": {
            "label": "Content, Trust & Depth",
            "computed": False,
            "score": None,
            "checklist": build_category_3_checklist(pages),
            "content_similarity_pairs": similarity_pairs,
        },
        "overall_score": None,
        "overall_score_note": "Not computable until Category 2 and 3 scores are filled in manually — overall = average of all three, ceiling 10.0.",
        "cold_outreach_snippet": generate_outreach_snippet(business_name, pages, technical_avg),
    }


def main():
    parser = argparse.ArgumentParser(description="Cold-outreach SEO audit for any live prospect site.")
    parser.add_argument("--urls", required=True, help="Path to a text file, one page URL per line")
    parser.add_argument("--name", required=True, help="Business name, used in the report and outreach snippet")
    parser.add_argument("--out", default="audit-report.md", help="Where to write the Markdown report")
    parser.add_argument("--json-out", default=None, help="Optional path to also write a machine-readable JSON report (same data, structured for downstream tooling)")
    parser.add_argument("--phone", default=None, help="Business's real phone number — enables an automated on-site presence check for Category 2 (NAP)")
    parser.add_argument("--address", default=None, help="Business's real street address — enables an automated on-site word-overlap check for Category 2 (NAP)")
    args = parser.parse_args()

    with open(args.urls, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    if not urls:
        print("No URLs found in the input file.", file=sys.stderr)
        sys.exit(1)

    print(f"Auditing {len(urls)} page(s) for {args.name}...")
    if not PLAYWRIGHT_AVAILABLE:
        print("  (playwright not installed — raw-vs-rendered check will be skipped)")
    if not args.phone and not args.address:
        print("  (no --phone/--address given — NAP consistency will be a blank manual checklist item)")

    pages = []
    for url in urls:
        print(f"  Checking {url}...")
        pages.append(audit_page(url, expected_phone=args.phone, expected_address=args.address))

    check_cross_page_uniqueness([p for p in pages if not p.fetch_error])

    site_root = f"{urlparse(urls[0]).scheme}://{urlparse(urls[0]).netloc}/"
    print(f"  Checking robots.txt at {site_root}...")
    robots_finding = check_robots_txt(site_root)

    report = build_report(args.name, pages, robots_finding, args.phone, args.address)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(report)

    if args.json_out:
        json_report = build_json_report(args.name, pages, robots_finding, args.phone, args.address)
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(json_report, f, indent=2)

    valid = [p for p in pages if not p.fetch_error]
    robots_score = category_score([robots_finding])
    technical_avg = round((sum(p.technical_score for p in valid) + robots_score) / (len(valid) + 1), 1) if valid else robots_score
    print(f"\n{'='*60}")
    print(f"Category 1 (Rendering & Technical): {technical_avg}/10")
    print("Categories 2 & 3: manual — see checklists in the report")
    print(f"Report written to {args.out}")
    if args.json_out:
        print(f"JSON report written to {args.json_out}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
