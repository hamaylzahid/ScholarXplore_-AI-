"""
╔══════════════════════════════════════════════════════════════╗
║   AI Scholarship Intelligence System — FastAPI Backend       ║
║   File: api.py                                               ║
║                                ║
╚══════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import re
import time
import json
import random
import logging
import asyncio
import hashlib
from typing import Optional, List
from datetime import datetime
from functools import lru_cache
from collections import Counter

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, quote_plus

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

# ── Logging ────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ScholarshipAPI")

# ══════════════════════════════════════════════════════════════
# APP INIT
# ══════════════════════════════════════════════════════════════

app = FastAPI(
    title="AI Scholarship & Admission Intelligence API",
    description=(
        "Production-grade REST API for discovering global scholarships, "
        "fellowships, and university admissions. Powered by intelligent "
        "web scraping, NLP extraction, and real-time analytics."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ══════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

REQUEST_TIMEOUT = 12
MAX_RETRIES = 2

IRRELEVANT_DOMAINS = {
    "facebook.com", "twitter.com", "instagram.com", "youtube.com",
    "reddit.com", "quora.com", "pinterest.com", "linkedin.com",
    "wikipedia.org", "amazon.com", "ebay.com",
}

FULLY_FUNDED_PATTERNS = [
    r"fully[\s-]funded", r"full[\s-]scholarship", r"tuition.*waiver",
    r"all\s+expenses", r"100%\s+funded", r"covers?\s+all",
    r"stipend.*included", r"full\s+financial\s+support",
]
PARTIAL_PATTERNS = [
    r"partial[\s-]scholarship", r"partial[\s-]fund", r"partial\s+support",
    r"50%\s+tuition", r"tuition\s+reduction", r"merit\s+aid",
]

COUNTRY_NAMES = [
    "Germany", "USA", "United States", "UK", "United Kingdom", "Canada",
    "Australia", "France", "Japan", "China", "South Korea", "Netherlands",
    "Sweden", "Norway", "Denmark", "Switzerland", "Pakistan", "India",
    "Turkey", "Egypt", "Saudi Arabia", "UAE", "New Zealand", "Italy",
    "Spain", "Belgium", "Finland", "Austria", "Singapore", "Ireland",
]

# ══════════════════════════════════════════════════════════════
# PYDANTIC MODELS
# ══════════════════════════════════════════════════════════════

class SearchRequest(BaseModel):
    field: str = Field(..., example="Artificial Intelligence", description="Academic field")
    country: str = Field(..., example="Germany", description="Target country")
    funding_type: str = Field("any", example="fully funded", description="fully funded | partial | any")
    max_results: int = Field(20, ge=1, le=50, description="Max scholarships to return")

class ScholarshipRecord(BaseModel):
    id: str
    title: str
    country: str
    funding: str
    deadline_open: str
    deadline_close: str
    eligibility: str
    apply_link: str
    source: str
    scraped_at: str

class SearchResponse(BaseModel):
    status: str
    total: int
    field: str
    country: str
    funding_type: str
    scholarships: List[ScholarshipRecord]
    analytics: dict

class AnalyticsResponse(BaseModel):
    total: int
    by_funding: dict
    by_country: dict
    top_keywords: List[dict]

# ══════════════════════════════════════════════════════════════
# IN-MEMORY CACHE (simple KV store for Colab)
# ══════════════════════════════════════════════════════════════

_cache: dict[str, dict] = {}

def cache_key(field: str, country: str, funding_type: str) -> str:
    raw = f"{field.lower()}_{country.lower()}_{funding_type.lower()}"
    return hashlib.md5(raw.encode()).hexdigest()

def get_cached(key: str) -> Optional[list]:
    entry = _cache.get(key)
    if entry and (time.time() - entry["ts"]) < 3600:  # 1hr TTL
        logger.info(f"Cache HIT for key {key[:8]}")
        return entry["data"]
    return None

def set_cached(key: str, data: list) -> None:
    _cache[key] = {"data": data, "ts": time.time()}

# ══════════════════════════════════════════════════════════════
# SCRAPING UTILITIES
# ══════════════════════════════════════════════════════════════

def safe_get(url: str, retries: int = MAX_RETRIES) -> Optional[BeautifulSoup]:
    for attempt in range(1, retries + 1):
        try:
            time.sleep(random.uniform(1.5, 3.5))
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "lxml")
        except requests.exceptions.HTTPError as e:
            logger.warning(f"HTTP {e.response.status_code} on {url} (attempt {attempt})")
        except Exception as e:
            logger.warning(f"Error on {url} attempt {attempt}: {e}")
    return None


def scrape_opportunities_circle(field: str, country: str) -> list[str]:
    links = []
    url = f"https://opportunitiescircle.com/?s={quote_plus(field + ' ' + country + ' scholarship')}"
    soup = safe_get(url)
    if soup:
        for a in soup.select("article a[href]"):
            href = a.get("href", "")
            if href.startswith("http") and "opportunitiescircle.com" in href:
                links.append(href)
    return list(dict.fromkeys(links))[:8]


def scrape_scholarship_portal(field: str, country: str) -> list[str]:
    links = []
    base = "https://www.scholarshipportal.com"
    soup = safe_get(f"{base}/scholarships/search/?q={quote_plus(field + ' ' + country)}")
    if not soup:
        soup = safe_get(f"{base}/scholarships/")
    if soup:
        for a in soup.select('a[href*="/scholarships/"]'):
            href = a.get("href", "")
            if href.startswith("/"):
                href = urljoin(base, href)
            if "scholarshipportal.com" in href:
                links.append(href)
    return list(dict.fromkeys(links))[:8]


def scrape_daad() -> list[str]:
    links = []
    base = "https://www.daad.de"
    for page in [
        f"{base}/en/studying-in-germany/scholarships/",
        f"{base}/en/find-funding/graduate-funding/",
    ]:
        soup = safe_get(page)
        if soup:
            for a in soup.select("a[href]"):
                href = a.get("href", "")
                if "/en/" in href and ("scholarship" in href.lower() or "funding" in href.lower()):
                    full = urljoin(base, href) if href.startswith("/") else href
                    if full.startswith("http"):
                        links.append(full)
    return list(dict.fromkeys(links))[:8]


# ══════════════════════════════════════════════════════════════
# EXTRACTION UTILITIES
# ══════════════════════════════════════════════════════════════

def extract_dates(text: str) -> tuple[str, str]:
    opening = closing = "Not Available"
    dl = re.search(r"(?:deadline|closing date|apply by|due)[:\s]+([^\n<]{5,60})", text, re.IGNORECASE)
    if dl:
        closing = dl.group(1).strip()[:60]
    op = re.search(r"(?:open(?:ing)?(?:\s+date)?|start(?:ing)?\s+date)[:\s]+([^\n<]{5,60})", text, re.IGNORECASE)
    if op:
        opening = op.group(1).strip()[:60]
    if closing == "Not Available":
        m = re.search(
            r"\b(\d{1,2}[\s/\-](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*[\s/\-]\d{4})\b",
            text, re.IGNORECASE,
        )
        if m:
            closing = m.group(1)
    return opening, closing


def classify_funding(text: str) -> str:
    tl = text.lower()
    for p in FULLY_FUNDED_PATTERNS:
        if re.search(p, tl):
            return "Fully Funded"
    for p in PARTIAL_PATTERNS:
        if re.search(p, tl):
            return "Partial Funding"
    return "Not Specified"


def extract_eligibility(text: str) -> str:
    for pat in [
        r"eligib(?:ility|le)[:\s]+([^\n]{10,300})",
        r"requirement[s]?[:\s]+([^\n]{10,300})",
        r"who\s+can\s+apply[:\s]+([^\n]{10,300})",
        r"open\s+to[:\s]+([^\n]{10,300})",
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()[:300]
    return "Not Available"


def extract_country(text: str) -> str:
    for c in COUNTRY_NAMES:
        if re.search(r"\b" + re.escape(c) + r"\b", text, re.IGNORECASE):
            return c
    return "Not Available"


def make_record_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:12]


def extract_page(url: str) -> Optional[ScholarshipRecord]:
    soup = safe_get(url)
    if not soup:
        return None

    title_tag = soup.find("h1") or soup.find("title")
    title = re.sub(r"\s+", " ", title_tag.get_text(strip=True))[:200] if title_tag else None
    if not title:
        return None

    raw = re.sub(r"\s+", " ", soup.get_text(separator=" ", strip=True))
    open_d, close_d = extract_dates(raw)

    apply_link = url
    for a in soup.find_all("a", href=True):
        if any(k in a.get_text(strip=True).lower() for k in ["apply now", "apply here", "apply online"]):
            href = a["href"]
            apply_link = urljoin(url, href) if href.startswith("/") else href
            break

    return ScholarshipRecord(
        id=make_record_id(url),
        title=title,
        country=extract_country(raw),
        funding=classify_funding(raw),
        deadline_open=open_d,
        deadline_close=close_d,
        eligibility=extract_eligibility(raw),
        apply_link=apply_link,
        source=urlparse(url).netloc.replace("www.", ""),
        scraped_at=datetime.utcnow().isoformat() + "Z",
    )


# ══════════════════════════════════════════════════════════════
# ANALYTICS
# ══════════════════════════════════════════════════════════════

def build_analytics(records: list[ScholarshipRecord]) -> dict:
    by_funding: Counter = Counter()
    by_country: Counter = Counter()
    words: list[str] = []

    STOPWORDS = {
        "the","a","an","for","in","of","to","and","or","is","at","by","on",
        "with","scholarship","fellowship","award","program","university",
        "international","students","student","not","available","page",
    }

    for r in records:
        by_funding[r.funding] += 1
        by_country[r.country] += 1
        ws = re.findall(r"\b[a-zA-Z]{3,}\b", r.title.lower())
        words.extend(w for w in ws if w not in STOPWORDS)

    kw = Counter(words).most_common(15)
    return {
        "total": len(records),
        "by_funding": dict(by_funding),
        "by_country": dict(by_country.most_common(10)),
        "top_keywords": [{"word": w, "count": c} for w, c in kw],
    }


# ══════════════════════════════════════════════════════════════
# PIPELINE
# ══════════════════════════════════════════════════════════════

def run_pipeline(field: str, country: str, funding_type: str, max_results: int) -> list[ScholarshipRecord]:
    key = cache_key(field, country, funding_type)
    cached = get_cached(key)
    if cached:
        return cached[:max_results]

    logger.info(f"Pipeline: field={field}, country={country}, funding={funding_type}")

    all_links: list[str] = []
    all_links += scrape_opportunities_circle(field, country)
    all_links += scrape_scholarship_portal(field, country)
    all_links += scrape_daad()
    all_links = list(dict.fromkeys(all_links))[:30]

    logger.info(f"Collected {len(all_links)} unique links")

    records: list[ScholarshipRecord] = []
    seen_ids: set[str] = set()

    for url in all_links:
        try:
            rec = extract_page(url)
            if rec and rec.id not in seen_ids:
                # Optional funding filter
                if funding_type.lower() != "any":
                    if funding_type.lower() == "fully funded" and rec.funding != "Fully Funded":
                        continue
                    if funding_type.lower() == "partial" and rec.funding != "Partial Funding":
                        continue
                seen_ids.add(rec.id)
                records.append(rec)
        except Exception as e:
            logger.error(f"Failed to extract {url}: {e}")

        if len(records) >= max_results:
            break

    set_cached(key, records)
    logger.info(f"Pipeline complete: {len(records)} scholarships")
    return records


# ══════════════════════════════════════════════════════════════
# ROUTES
# ══════════════════════════════════════════════════════════════

@app.get("/", tags=["Health"])
async def root():
    return {
        "service": "AI Scholarship Intelligence API",
        "version": "2.0.0",
        "status": "online",
        "endpoints": ["/search", "/scholarships/stream", "/analytics", "/countries", "/docs"],
    }


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat() + "Z"}


@app.post("/search", response_model=SearchResponse, tags=["Search"])
async def search_scholarships(req: SearchRequest):
    """
    Main scholarship search endpoint.
    Scrapes multiple sources and returns structured, deduplicated results.
    """
    try:
        records = run_pipeline(req.field, req.country, req.funding_type, req.max_results)
        analytics = build_analytics(records)
        return SearchResponse(
            status="success",
            total=len(records),
            field=req.field,
            country=req.country,
            funding_type=req.funding_type,
            scholarships=records,
            analytics=analytics,
        )
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/search", response_model=SearchResponse, tags=["Search"])
async def search_get(
    field: str = Query(..., example="Computer Science"),
    country: str = Query(..., example="Germany"),
    funding_type: str = Query("any", example="fully funded"),
    max_results: int = Query(20, ge=1, le=50),
):
    """GET version of /search for easy browser/curl testing."""
    req = SearchRequest(field=field, country=country, funding_type=funding_type, max_results=max_results)
    return await search_scholarships(req)


@app.get("/scholarships/stream", tags=["Search"])
async def stream_scholarships(
    field: str = Query(...),
    country: str = Query(...),
    funding_type: str = Query("any"),
):
    """
    Server-Sent Events stream. Returns scholarships one-by-one as they are scraped.
    Connect with EventSource in the browser.
    """
    async def event_generator():
        all_links: list[str] = []
        all_links += scrape_opportunities_circle(field, country)
        all_links += scrape_scholarship_portal(field, country)
        all_links = list(dict.fromkeys(all_links))[:15]

        yield f"data: {json.dumps({'type': 'start', 'total_links': len(all_links)})}\n\n"

        count = 0
        for url in all_links:
            try:
                rec = extract_page(url)
                if rec:
                    count += 1
                    yield f"data: {json.dumps({'type': 'record', 'index': count, **rec.dict()})}\n\n"
                await asyncio.sleep(0.1)
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'url': url, 'msg': str(e)})}\n\n"

        yield f"data: {json.dumps({'type': 'done', 'total': count})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/analytics", response_model=AnalyticsResponse, tags=["Analytics"])
async def get_analytics(
    field: str = Query(...),
    country: str = Query(...),
    funding_type: str = Query("any"),
):
    """Returns only the analytics summary without full scholarship data."""
    records = run_pipeline(field, country, funding_type, max_results=50)
    a = build_analytics(records)
    return AnalyticsResponse(**a)


@app.get("/countries", tags=["Meta"])
async def list_countries():
    """Returns the list of supported/recognized countries."""
    return {"countries": sorted(COUNTRY_NAMES)}


@app.get("/funding-types", tags=["Meta"])
async def list_funding_types():
    return {"funding_types": ["fully funded", "partial", "any"]}


@app.delete("/cache", tags=["Admin"])
async def clear_cache():
    _cache.clear()
    return {"message": "Cache cleared", "timestamp": datetime.utcnow().isoformat() + "Z"}


