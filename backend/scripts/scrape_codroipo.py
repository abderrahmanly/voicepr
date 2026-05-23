"""Scrape municipal-service descriptions from comune.codroipo.ud.it.

The site is an Angular SPA backed by the regional KPAX CMS (https://backoffice-comuni.regione.fvg.it).
The HTML returned for any service URL is just the SPA shell — the content
arrives via an authenticated JSON API that requires a session token.

Strategy used here:
  1. Pull the public sitemap.xml to discover all service pages.
  2. For each URL, hit the SPA — works only if the page exposes
     server-rendered metadata. Most pages don't, so the fallback is
     a Playwright headless render (off by default to keep the prod
     container small).
  3. Merge any successfully extracted content into the curated
     `data/services.json` baseline.

Run:
    python -m scripts.scrape_codroipo                  # baseline only
    python -m scripts.scrape_codroipo --with-playwright  # also try live extraction

Output: writes/overwrites backend/data/services.json with the merged result.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

BASE = "https://www.comune.codroipo.ud.it"
SITEMAP = f"{BASE}/sitemap.xml"
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
OUT_FILE = DATA_DIR / "services.json"
BASELINE_FILE = DATA_DIR / "services.baseline.json"

# Service-relevant URL segments — we only crawl pages likely to describe a service
SERVICE_SEGMENTS = (
    "anagrafe", "stato-civile", "tributi", "elettorale", "edilizia",
    "urbanistica", "scuola", "sociali", "protocollo", "polizia",
    "carta-d-identita", "passaporto", "residenza", "servizi-",
)


def fetch_sitemap_urls() -> list[str]:
    resp = httpx.get(SITEMAP, timeout=20, headers={"User-Agent": "voicepr-scraper/0.1"})
    resp.raise_for_status()
    urls = re.findall(r"<loc>([^<]+)</loc>", resp.text)
    log.info("Sitemap returned %d urls", len(urls))
    return urls


def filter_service_urls(urls: list[str]) -> list[str]:
    out: list[str] = []
    for u in urls:
        path = urlparse(u).path.lower()
        if any(seg in path for seg in SERVICE_SEGMENTS):
            out.append(u)
    return out


def extract_with_httpx(url: str) -> dict | None:
    """Try server-rendered metadata. Works only if the SPA leaks any.

    Returns None on any extraction failure; the caller will fall back to
    Playwright or skip.
    """
    try:
        resp = httpx.get(url, timeout=20, headers={"User-Agent": "voicepr-scraper/0.1"})
    except httpx.HTTPError as e:
        log.warning("GET %s failed: %s", url, e)
        return None
    if resp.status_code != 200 or "text/html" not in resp.headers.get("content-type", ""):
        return None

    soup = BeautifulSoup(resp.text, "lxml")
    title_meta = soup.find("meta", property="og:title")
    desc_meta = soup.find("meta", property="og:description")
    title = (title_meta.get("content") if title_meta else "") or ""
    body = (desc_meta.get("content") if desc_meta else "") or ""

    if not title.strip() or not body.strip():
        return None  # SPA shell — no useful content rendered

    return {
        "id": _slug_from_url(url),
        "title": title.strip(),
        "url": url,
        "office": _guess_office(url),
        "content": body.strip(),
        "source": "http",
    }


def extract_with_playwright(url: str) -> dict | None:
    """Render the SPA with a headless browser and extract main content.

    Imports playwright lazily so it's only required when --with-playwright is set.
    """
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError:
        log.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
        sys.exit(1)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            ctx = browser.new_context(user_agent="voicepr-scraper/0.1")
            page = ctx.new_page()
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_selector("main, app-root", timeout=15000)
            html = page.content()
        except Exception as e:  # noqa: BLE001
            log.warning("Playwright failed on %s: %s", url, e)
            return None
        finally:
            browser.close()

    soup = BeautifulSoup(html, "lxml")
    main = soup.find("main") or soup.find("app-root")
    title_el = soup.find("h1") or soup.find("title")
    title = title_el.get_text(" ", strip=True) if title_el else ""
    if not main:
        return None
    # Drop nav, footer, scripts, styles
    for sel in main.select("nav, footer, script, style, .breadcrumb, .skip-link"):
        sel.decompose()
    text = " ".join(main.get_text(" ", strip=True).split())
    if len(text) < 80:
        return None
    return {
        "id": _slug_from_url(url),
        "title": title or _slug_from_url(url),
        "url": url,
        "office": _guess_office(url),
        "content": text[:4000],
        "source": "playwright",
    }


def _slug_from_url(url: str) -> str:
    path = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]
    return re.sub(r"-\d+$", "", path) or path


def _guess_office(url: str) -> str:
    path = urlparse(url).path.lower()
    mapping = {
        "anagrafe": "anagrafe",
        "stato-civile": "stato_civile",
        "tributi": "tributi",
        "elettorale": "ufficio_elettorale",
        "edilizia": "ufficio_tecnico",
        "urbanistica": "ufficio_tecnico",
        "sociali": "servizi_sociali",
        "protocollo": "protocollo",
    }
    for needle, office in mapping.items():
        if needle in path:
            return office
    return ""


def merge(baseline: list[dict], extracted: list[dict]) -> list[dict]:
    """Curated baseline wins on conflicts; live extraction adds new entries."""
    by_id = {s["id"]: s for s in baseline}
    for item in extracted:
        if item["id"] not in by_id:
            by_id[item["id"]] = item
    return list(by_id.values())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--with-playwright",
        action="store_true",
        help="Also render pages with Playwright. Slower; requires browser install.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Max number of pages to fetch from the live site.",
    )
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    baseline: list[dict] = []
    if BASELINE_FILE.exists():
        baseline = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
        log.info("Loaded %d baseline services", len(baseline))
    else:
        log.warning("No baseline file at %s — starting empty.", BASELINE_FILE)

    extracted: list[dict] = []
    try:
        urls = filter_service_urls(fetch_sitemap_urls())[: args.limit]
        log.info("Will try %d candidate service urls", len(urls))
        for url in urls:
            item = extract_with_httpx(url)
            if item is None and args.with_playwright:
                item = extract_with_playwright(url)
            if item:
                log.info("  ✓ extracted: %s", item["title"])
                extracted.append(item)
    except Exception as e:  # noqa: BLE001
        log.warning("Live scrape failed (%s) — falling back to baseline only.", e)

    merged = merge(baseline, extracted)
    OUT_FILE.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log.info("Wrote %d services to %s", len(merged), OUT_FILE)


if __name__ == "__main__":
    main()
