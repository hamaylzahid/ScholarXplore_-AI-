
import re
import time
import json
import random
import hashlib
import requests
import pandas as pd
import streamlit as st
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, quote_plus
from collections import Counter
from datetime import datetime

# ══════════════════════════════════════════════════════════════
# PAGE CONFIG — must be first Streamlit call
# ══════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="ScholarAI — Global Scholarship Intelligence",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ══════════════════════════════════════════════════════════════
# GLOBAL STYLES
# ══════════════════════════════════════════════════════════════

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;700;800&family=Instrument+Serif:ital@0;1&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── Root ── */
:root {
    --bg:        #0A0C10;
    --surface:   #111318;
    --surface2:  #181C24;
    --border:    rgba(255,255,255,0.07);
    --border2:   rgba(255,255,255,0.14);
    --accent:    #4AFFA4;
    --accent2:   #4AC8FF;
    --accent3:   #FFB84A;
    --text:      #F0F2F8;
    --muted:     #7A8099;
    --danger:    #FF5A6E;
    --fully:     #4AFFA4;
    --partial:   #4AC8FF;
    --unknown:   #7A8099;
    --font-head: 'Syne', sans-serif;
    --font-body: 'Instrument Serif', serif;
    --font-mono: 'JetBrains Mono', monospace;
}
html, body, [class*="css"] {
    background-color: var(--bg) !important;
}
/* ── Hide Streamlit chrome ── */
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }
section[data-testid="stSidebar"] > div:first-child { background: var(--surface) !important; }

/* ── App background ── */
.stApp {
    background-color: #0A0C10;
    color: white;
}

.stButton > button {
    background-color: #4AFFA4;
    color: black;
    font-weight: bold;
}

.stSelectbox div, .stTextInput input {
    background-color: #181C24 !important;
    color: white !important;
}

.stApp { background: var(--bg) !important; }
.main .block-container { padding: 2rem 2rem 4rem; max-width: 1400px; }

/* ── Typography ── */
h1, h2, h3, h4 { font-family: var(--font-head) !important; color: var(--text) !important; }
p, li, span, div { color: var(--text); }

/* ── Hero header ── */
.hero-wrap {
    background: linear-gradient(135deg, #0d1117 0%, #111827 50%, #0d1520 100%);
    border: 1px solid var(--border2);
    border-radius: 20px;
    padding: 3rem 3rem 2.5rem;
    margin-bottom: 2.5rem;
    position: relative;
    overflow: hidden;
}
.hero-wrap::before {
    content: '';
    position: absolute;
    top: -80px; right: -80px;
    width: 300px; height: 300px;
    background: radial-gradient(circle, rgba(74,255,164,0.08) 0%, transparent 70%);
    border-radius: 50%;
}
.hero-wrap::after {
    content: '';
    position: absolute;
    bottom: -60px; left: -60px;
    width: 250px; height: 250px;
    background: radial-gradient(circle, rgba(74,200,255,0.06) 0%, transparent 70%);
    border-radius: 50%;
}
.hero-eyebrow {
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.18em;
    color: var(--accent);
    text-transform: uppercase;
    margin-bottom: 1rem;
}
.hero-title {
    font-family: var(--font-head);
    font-size: clamp(2.2rem, 4vw, 3.4rem);
    font-weight: 800;
    line-height: 1.05;
    color: var(--text);
    margin-bottom: 1rem;
}
.hero-title em {
    font-style: italic;
    color: var(--accent);
    font-family: var(--font-body);
}
.hero-sub {
    font-family: var(--font-body);
    font-size: 1.15rem;
    font-style: italic;
    color: var(--muted);
    max-width: 600px;
    line-height: 1.7;
}
.hero-stats {
    display: flex;
    gap: 2.5rem;
    margin-top: 2rem;
    padding-top: 2rem;
    border-top: 1px solid var(--border);
}
.hero-stat-label {
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.1em;
    color: var(--muted);
    text-transform: uppercase;
    margin-bottom: 4px;
}
.hero-stat-value {
    font-family: var(--font-head);
    font-size: 1.6rem;
    font-weight: 700;
    color: var(--text);
}

/* ── Sidebar inputs ── */
.stSelectbox > div > div,
.stTextInput > div > div > input {
    background: var(--surface2) !important;
    border: 1px solid var(--border2) !important;
    border-radius: 10px !important;
    color: var(--text) !important;
    font-family: var(--font-head) !important;
}
.stSelectbox label, .stTextInput label, .stSlider label, .stRadio label {
    font-family: var(--font-mono) !important;
    font-size: 11px !important;
    letter-spacing: 0.1em;
    text-transform: uppercase !important;
    color: var(--muted) !important;
}

/* ── Main search button ── */
.stButton > button {
    background: var(--accent) !important;
    color: #0A0C10 !important;
    font-family: var(--font-head) !important;
    font-weight: 700 !important;
    font-size: 15px !important;
    border: none !important;
    border-radius: 12px !important;
    padding: 0.75rem 2rem !important;
    width: 100% !important;
    letter-spacing: 0.04em !important;
    transition: all 0.2s ease !important;
}
.stButton > button:hover {
    background: #2DFFB8 !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 30px rgba(74,255,164,0.25) !important;
}

/* ── Metric cards ── */
.metric-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-bottom: 2rem;
}
.metric-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 1.25rem 1.5rem;
    position: relative;
    overflow: hidden;
    transition: border-color 0.2s ease, transform 0.2s ease;
}
.metric-card:hover { border-color: var(--border2); transform: translateY(-2px); }
.metric-card-accent { border-top: 2px solid var(--accent); }
.metric-card-blue   { border-top: 2px solid var(--accent2); }
.metric-card-gold   { border-top: 2px solid var(--accent3); }
.metric-card-red    { border-top: 2px solid var(--danger); }
.metric-label {
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 8px;
}
.metric-value {
    font-family: var(--font-head);
    font-size: 2.2rem;
    font-weight: 800;
    color: var(--text);
    line-height: 1;
}
.metric-sub {
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--muted);
    margin-top: 6px;
}

/* ── Scholarship cards ── */
.s-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 1.5rem 1.75rem;
    margin-bottom: 1rem;
    transition: border-color 0.25s, transform 0.25s, box-shadow 0.25s;
    position: relative;
}
.s-card:hover {
    border-color: rgba(74,255,164,0.3);
    transform: translateY(-3px);
    box-shadow: 0 12px 40px rgba(0,0,0,0.4);
}
.s-card-top {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
    margin-bottom: 1rem;
}
.s-title {
    font-family: var(--font-head);
    font-size: 1.1rem;
    font-weight: 700;
    color: var(--text);
    line-height: 1.3;
    flex: 1;
}
.badge {
    display: inline-block;
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.08em;
    padding: 4px 10px;
    border-radius: 20px;
    white-space: nowrap;
    flex-shrink: 0;
}
.badge-full    { background: rgba(74,255,164,0.12); color: var(--fully); border: 1px solid rgba(74,255,164,0.25); }
.badge-partial { background: rgba(74,200,255,0.12); color: var(--partial); border: 1px solid rgba(74,200,255,0.25); }
.badge-unknown { background: rgba(122,128,153,0.12); color: var(--unknown); border: 1px solid rgba(122,128,153,0.2); }
.s-meta {
    display: flex;
    gap: 1.5rem;
    flex-wrap: wrap;
    margin-bottom: 0.9rem;
}
.s-meta-item {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--muted);
}
.s-meta-item span { color: var(--text); margin-left: 4px; }
.s-eligibility {
    font-family: var(--font-body);
    font-style: italic;
    font-size: 0.93rem;
    color: var(--muted);
    line-height: 1.6;
    border-left: 2px solid var(--border2);
    padding-left: 0.9rem;
    margin-top: 0.75rem;
    margin-bottom: 1rem;
}
.s-apply-btn {
    display: inline-block;
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.06em;
    color: var(--accent);
    border: 1px solid rgba(74,255,164,0.3);
    border-radius: 8px;
    padding: 7px 16px;
    text-decoration: none;
    transition: all 0.2s ease;
}
.s-apply-btn:hover {
    background: rgba(74,255,164,0.1);
    color: var(--accent);
    text-decoration: none;
}
.s-source {
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--muted);
    margin-top: 8px;
}

/* ── Analytics section ── */
.section-header {
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--accent);
    margin-bottom: 1.25rem;
    padding-bottom: 0.75rem;
    border-bottom: 1px solid var(--border);
}

/* ── Bar chart (custom) ── */
.bar-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 10px;
}
.bar-label {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--muted);
    width: 140px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    flex-shrink: 0;
}
.bar-track {
    flex: 1;
    height: 6px;
    background: var(--surface2);
    border-radius: 3px;
    overflow: hidden;
}
.bar-fill {
    height: 100%;
    border-radius: 3px;
    transition: width 0.6s ease;
}
.bar-count {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--text);
    width: 28px;
    text-align: right;
    flex-shrink: 0;
}

/* ── Empty / error states ── */
.empty-state {
    text-align: center;
    padding: 4rem 2rem;
    color: var(--muted);
    font-family: var(--font-body);
    font-style: italic;
    font-size: 1.2rem;
    border: 1px dashed var(--border2);
    border-radius: 16px;
    margin: 2rem 0;
}

/* ── Loading indicator ── */
.stSpinner > div { border-top-color: var(--accent) !important; }

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: var(--surface) !important;
    border-radius: 12px !important;
    gap: 4px !important;
    padding: 4px !important;
}
.stTabs [data-baseweb="tab"] {
    font-family: var(--font-mono) !important;
    font-size: 11px !important;
    letter-spacing: 0.06em !important;
    color: var(--muted) !important;
    border-radius: 8px !important;
    padding: 8px 18px !important;
}
.stTabs [aria-selected="true"] {
    background: var(--surface2) !important;
    color: var(--text) !important;
}
/* ── FIX: Selectbox dropdown options visibility ── */
div[data-baseweb="select"] * {
    color: var(--text) !important;
}

div[data-baseweb="popover"] {
    background-color: var(--surface2) !important;
}

ul[role="listbox"] {
    background-color: var(--surface2) !important;
    color: var(--text) !important;
}

li[role="option"] {
    background-color: var(--surface2) !important;
    color: var(--text) !important;
}

li[role="option"]:hover {
    background-color: rgba(74,255,164,0.15) !important;
    color: var(--text) !important;
}/* Fix unexpected white blocks */
a, a:visited, a:hover {
    color: var(--accent) !important;
    text-decoration: none !important;
}


/* Fix markdown containers */
.stMarkdown {
    background: transparent !important;
}

/* Remove white box around raw HTML */
pre, code {
    background: transparent !important;
}


/* ── DataFrame ── */
.stDataFrame { border-radius: 12px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# CONSTANTS & SCRAPING ENGINE
# ══════════════════════════════════════════════════════════════

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

COUNTRY_LIST = [
    "Any", "Germany", "USA", "UK", "Canada", "Australia", "France", "Japan",
    "Netherlands", "Sweden", "Norway", "Switzerland", "South Korea", "Singapore",
    "New Zealand", "Italy", "Spain", "Belgium", "Finland", "Austria", "Ireland",
    "Denmark", "China", "India", "Turkey", "UAE", "Saudi Arabia", "Egypt", "Pakistan",
]

FULLY_FUNDED_PATTERNS = [
    r"fully[\s-]funded", r"full[\s-]scholarship", r"tuition.*waiver",
    r"all\s+expenses", r"100%\s+funded", r"full\s+financial\s+support",
    r"stipend.*included",
]
PARTIAL_PATTERNS = [
    r"partial[\s-]scholarship", r"partial[\s-]fund", r"50%\s+tuition",
    r"tuition\s+reduction", r"merit\s+aid",
]

COUNTRY_NAMES = [
    "Germany","USA","United States","UK","United Kingdom","Canada","Australia",
    "France","Japan","China","South Korea","Netherlands","Sweden","Norway",
    "Denmark","Switzerland","Pakistan","India","Turkey","Egypt","Saudi Arabia",
    "UAE","New Zealand","Italy","Spain","Belgium","Finland","Austria","Singapore","Ireland",
]

STOPWORDS = {
    "the","a","an","for","in","of","to","and","or","is","at","by","on","with",
    "scholarship","fellowship","award","program","programme","university",
    "international","students","student","study","not","available","page",
}


def safe_get(url: str) -> BeautifulSoup | None:
    for attempt in range(2):
        try:
            time.sleep(random.uniform(1.2, 2.8))
            r = requests.get(url, headers=HEADERS, timeout=12)
            r.raise_for_status()
            return BeautifulSoup(r.text, "lxml")
        except Exception:
            pass
    return None


def scrape_links(field: str, country: str) -> list[str]:
    links = []

    # OpportunitiesCircle
    q = quote_plus(f"{field} {country} scholarship")
    soup = safe_get(f"https://opportunitiescircle.com/?s={q}")
    if soup:
        for a in soup.select("article a[href]"):
            href = a.get("href", "")
            if "opportunitiescircle.com" in href:
                links.append(href)

    # ScholarshipPortal
    base = "https://www.scholarshipportal.com"
    soup = safe_get(f"{base}/scholarships/search/?q={quote_plus(field + ' ' + country)}")
    if soup:
        for a in soup.select('a[href*="/scholarships/"]'):
            href = a.get("href", "")
            full = urljoin(base, href) if href.startswith("/") else href
            if "scholarshipportal.com" in full:
                links.append(full)

    # DAAD
    for page in [
        "https://www.daad.de/en/studying-in-germany/scholarships/",
        "https://www.daad.de/en/find-funding/graduate-funding/",
    ]:
        soup = safe_get(page)
        if soup:
            for a in soup.select("a[href]"):
                href = a.get("href", "")
                if "/en/" in href and ("scholarship" in href.lower() or "funding" in href.lower()):
                    full = urljoin("https://www.daad.de", href) if href.startswith("/") else href
                    if full.startswith("http"):
                        links.append(full)

    return list(dict.fromkeys(links))[:30]


def classify_funding(text: str) -> str:
    tl = text.lower()
    for p in FULLY_FUNDED_PATTERNS:
        if re.search(p, tl):
            return "Fully Funded"
    for p in PARTIAL_PATTERNS:
        if re.search(p, tl):
            return "Partial Funding"
    return "Not Specified"


def extract_dates(text: str) -> tuple[str, str]:
    opening = closing = "Not Available"
    dl = re.search(r"(?:deadline|closing date|apply by|due)[:\s]+([^\n<]{5,60})", text, re.IGNORECASE)
    if dl:
        closing = dl.group(1).strip()[:60]
    op = re.search(r"(?:open(?:ing)?(?:\s+date)?|start(?:ing)?\s+date)[:\s]+([^\n<]{5,60})", text, re.IGNORECASE)
    if op:
        opening = op.group(1).strip()[:60]
    return opening, closing


def extract_eligibility(text: str) -> str:
    for pat in [
        r"eligib(?:ility|le)[:\s]+([^\n]{10,300})",
        r"requirement[s]?[:\s]+([^\n]{10,300})",
        r"who\s+can\s+apply[:\s]+([^\n]{10,300})",
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()[:280]
    return "Not Available"


def extract_country(text: str) -> str:
    for c in COUNTRY_NAMES:
        if re.search(r"\b" + re.escape(c) + r"\b", text, re.IGNORECASE):
            return c
    return "Not Available"


def extract_page(url: str) -> dict | None:
    soup = safe_get(url)
    if not soup:
        return None
    title_tag = soup.find("h1") or soup.find("title")
    title = re.sub(r"\s+", " ", title_tag.get_text(strip=True))[:200] if title_tag else None
    if not title or title.lower() == "not available":
        return None
    raw = re.sub(r"\s+", " ", soup.get_text(separator=" ", strip=True))
    open_d, close_d = extract_dates(raw)
    apply_link = url
    for a in soup.find_all("a", href=True):
        if any(k in a.get_text(strip=True).lower() for k in ["apply now", "apply here", "apply online"]):
            href = a["href"]
            apply_link = urljoin(url, href) if href.startswith("/") else href
            break
    return {
        "title": title,
        "country": extract_country(raw),
        "funding": classify_funding(raw),
        "deadline_open": open_d,
        "deadline_close": close_d,
        "eligibility": extract_eligibility(raw),
        "apply_link": apply_link,
        "source": urlparse(url).netloc.replace("www.", ""),
    }


@st.cache_data(ttl=3600, show_spinner=False)
def run_pipeline(field: str, country: str, funding_type: str) -> list[dict]:
    links = scrape_links(field, country if country != "Any" else "")
    records = []
    seen = set()
    for url in links:
        rec = extract_page(url)
        if rec and rec["title"] not in seen:
            if funding_type != "Any":
                if funding_type == "Fully Funded" and rec["funding"] != "Fully Funded":
                    continue
                if funding_type == "Partial Funding" and rec["funding"] != "Partial Funding":
                    continue
            seen.add(rec["title"])
            records.append(rec)
    return records


def build_analytics(records: list[dict]) -> dict:
    by_funding: Counter = Counter()
    by_country: Counter = Counter()
    words: list[str] = []
    for r in records:
        by_funding[r["funding"]] += 1
        by_country[r["country"]] += 1
        ws = re.findall(r"\b[a-zA-Z]{3,}\b", r["title"].lower())
        words.extend(w for w in ws if w not in STOPWORDS)
    return {
        "by_funding": dict(by_funding),
        "by_country": dict(by_country.most_common(10)),
        "top_keywords": Counter(words).most_common(12),
    }


# ══════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════

if "results" not in st.session_state:
    st.session_state.results = []
if "searched" not in st.session_state:
    st.session_state.searched = False
if "search_meta" not in st.session_state:
    st.session_state.search_meta = {}

# ══════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("""
    <div style='padding: 1.5rem 0 1rem;'>
        <div style='font-family:var(--font-mono);font-size:10px;letter-spacing:0.15em;
                    text-transform:uppercase;color:var(--accent);margin-bottom:6px;'>
            ScholarAI v2.0
        </div>
        <div style='font-family:var(--font-head);font-size:1.4rem;font-weight:800;
                    color:var(--text);line-height:1.1;'>
            Scholarship<br>Intelligence
        </div>
    </div>
    <hr style='border-color:rgba(255,255,255,0.07);margin:1rem 0 1.5rem;'/>
    """, unsafe_allow_html=True)

    st.markdown("** Search Parameters**")

    field = st.text_input(
        "ACADEMIC FIELD",
        value="Artificial Intelligence",
        placeholder="e.g. Computer Science, Engineering...",
    )

    country = st.selectbox(
        "TARGET COUNTRY",
        options=COUNTRY_LIST,
        index=1,
    )

    funding_type = st.radio(
        "FUNDING TYPE",
        options=["Any", "Fully Funded", "Partial Funding"],
        index=0,
    )

    st.markdown("<br>", unsafe_allow_html=True)

    search_clicked = st.button("  Find Scholarships", use_container_width=True)

    st.markdown("""
    <hr style='border-color:rgba(255,255,255,0.07);margin:1.5rem 0;'/>
    <div style='font-family:var(--font-mono);font-size:10px;color:var(--muted);line-height:1.8;'>
        SOURCES<br>
        <span style='color:var(--text);'>• OpportunitiesCircle</span><br>
        <span style='color:var(--text);'>• ScholarshipPortal</span><br>
        <span style='color:var(--text);'>• DAAD Germany</span>
    </div>
    <hr style='border-color:rgba(255,255,255,0.07);margin:1.5rem 0;'/>
    <div style='font-family:var(--font-mono);font-size:10px;color:var(--muted);'>
        DATA FRESHNESS<br>
        <span style='color:var(--accent);'>Live — 1hr cache</span>
    </div>
    """, unsafe_allow_html=True)

    # Filter panel (shown after search)
    if st.session_state.searched and st.session_state.results:
        st.markdown("""
        <hr style='border-color:rgba(255,255,255,0.07);margin:1.5rem 0;'/>
        <div style='font-family:var(--font-mono);font-size:10px;letter-spacing:0.1em;
                    text-transform:uppercase;color:var(--accent2);margin-bottom:1rem;'>
            Filter Results
        </div>
        """, unsafe_allow_html=True)

        countries_found = sorted(set(r["country"] for r in st.session_state.results))
        filter_country = st.multiselect(
            "FILTER BY COUNTRY",
            options=countries_found,
            default=[],
        )
        filter_keyword = st.text_input("KEYWORD IN TITLE", placeholder="e.g. STEM, Research...")

        if filter_country or filter_keyword:
            filtered = st.session_state.results
            if filter_country:
                filtered = [r for r in filtered if r["country"] in filter_country]
            if filter_keyword:
                filtered = [r for r in filtered if filter_keyword.lower() in r["title"].lower()]
            st.session_state.display_results = filtered
        else:
            st.session_state.display_results = st.session_state.results
    else:
        st.session_state.display_results = st.session_state.results


# ══════════════════════════════════════════════════════════════
# MAIN CONTENT
# ══════════════════════════════════════════════════════════════

# ── Hero ──────────────────────────────────────────────────────
st.markdown("""
<div class="hero-wrap">
    <div class="hero-eyebrow">// AI-Powered Intelligence System</div>
    <h1 class="hero-title">
        Discover your<br><em>scholarship path</em>
    </h1>
    <p class="hero-sub">
        Real-time intelligence across global scholarship databases.
        Structured, deduplicated, and ready to act on.
    </p>
    <div class="hero-stats">
        <div>
            <div class="hero-stat-label">Sources Scraped</div>
            <div class="hero-stat-value">3</div>
        </div>
        <div>
            <div class="hero-stat-label">Countries</div>
            <div class="hero-stat-value">30+</div>
        </div>
        <div>
            <div class="hero-stat-label">Fields Covered</div>
            <div class="hero-stat-value">∞</div>
        </div>
        <div>
            <div class="hero-stat-label">Cache TTL</div>
            <div class="hero-stat-value">1h</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Handle search ─────────────────────────────────────────────
if search_clicked:
    if not field.strip():
        st.error("Please enter an academic field to search.")
    else:
        with st.spinner(f"Scraping scholarships for **{field}** in **{country}**…"):
            results = run_pipeline(field, country, funding_type)
            st.session_state.results = results
            st.session_state.display_results = results
            st.session_state.searched = True
            st.session_state.search_meta = {
                "field": field,
                "country": country,
                "funding_type": funding_type,
                "timestamp": datetime.now().strftime("%H:%M · %d %b %Y"),
            }

# ── Results area ──────────────────────────────────────────────
if st.session_state.searched:
    display = getattr(st.session_state, "display_results", st.session_state.results)
    all_results = st.session_state.results
    meta = st.session_state.search_meta

    # ── Metric cards ──────────────────────────────────────────
    fully = sum(1 for r in all_results if r["funding"] == "Fully Funded")
    partial = sum(1 for r in all_results if r["funding"] == "Partial Funding")
    countries_count = len(set(r["country"] for r in all_results if r["country"] != "Not Available"))

    st.markdown(f"""
    <div class="metric-grid">
        <div class="metric-card metric-card-accent">
            <div class="metric-label">Total Found</div>
            <div class="metric-value">{len(all_results)}</div>
            <div class="metric-sub">{meta.get('field','')} · {meta.get('country','')}</div>
        </div>
        <div class="metric-card metric-card-blue">
            <div class="metric-label">Fully Funded</div>
            <div class="metric-value">{fully}</div>
            <div class="metric-sub">100% coverage scholarships</div>
        </div>
        <div class="metric-card metric-card-gold">
            <div class="metric-label">Partial Funding</div>
            <div class="metric-value">{partial}</div>
            <div class="metric-sub">Merit & tuition aid</div>
        </div>
        <div class="metric-card metric-card-red">
            <div class="metric-label">Countries</div>
            <div class="metric-value">{countries_count}</div>
            <div class="metric-sub">Unique destinations</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Tabs ──────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs([
        "🎓  Scholarships",
        "📊  Analytics",
        "📋  Data Table",
        "💾  Export",
    ])

    # ════════════════════════════════════════════════════════
    # TAB 1: SCHOLARSHIP CARDS
    # ════════════════════════════════════════════════════════
    with tab1:
        st.markdown(f"""
        <div style='font-family:var(--font-mono);font-size:11px;color:var(--muted);
                    margin-bottom:1.5rem;'>
            Showing <span style='color:var(--text);font-weight:500;'>{len(display)}</span>
            of {len(all_results)} results · {meta.get('timestamp','')}
        </div>
        """, unsafe_allow_html=True)

        if not display:
            st.markdown("""
            <div class="empty-state">
                No scholarships match your current filters.<br>
                Try broadening the country or keyword filter.
            </div>
            """, unsafe_allow_html=True)
        else:
            for rec in display:
                funding_badge_class = (
                    "badge-full" if rec["funding"] == "Fully Funded"
                    else "badge-partial" if rec["funding"] == "Partial Funding"
                    else "badge-unknown"
                )
                elig = rec["eligibility"]
                elig_html = (
                    f'<div class="s-eligibility">{elig[:220]}{"…" if len(elig)>220 else ""}</div>'
                    if elig != "Not Available" else ""
                )
                deadline_str = rec["deadline_close"] if rec["deadline_close"] != "Not Available" else "—"
                country_str  = rec["country"] if rec["country"] != "Not Available" else "—"

                st.markdown(f"""
                <div class="s-card">
                    <div class="s-card-top">
                        <div class="s-title">{rec['title']}</div>
                        <span class="badge {funding_badge_class}">{rec['funding']}</span>
                    </div>
                    <div class="s-meta">
                        <div class="s-meta-item">📍 Country<span>{country_str}</span></div>
                        <div class="s-meta-item">⏰ Deadline<span>{deadline_str}</span></div>
                        <div class="s-meta-item">🌐 Source<span>{rec['source']}</span></div>
                    </div>
                    {elig_html}
                    <a href="{rec['apply_link']}" target="_blank" class="s-apply-btn">
                        Apply Now →
                    </a>
                </div>
                """, unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════
    # TAB 2: ANALYTICS
    # ════════════════════════════════════════════════════════
    with tab2:
        analytics = build_analytics(all_results)

        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown('<div class="section-header">Funding Distribution</div>', unsafe_allow_html=True)
            total_f = sum(analytics["by_funding"].values()) or 1
            FUND_COLORS = {
                "Fully Funded":   "#4AFFA4",
                "Partial Funding": "#4AC8FF",
                "Not Specified":  "#7A8099",
            }
            for label, count in analytics["by_funding"].items():
                pct = count / total_f * 100
                color = FUND_COLORS.get(label, "#7A8099")
                st.markdown(f"""
                <div class="bar-row">
                    <div class="bar-label">{label}</div>
                    <div class="bar-track">
                        <div class="bar-fill" style="width:{pct:.0f}%;background:{color};"></div>
                    </div>
                    <div class="bar-count">{count}</div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown('<br><div class="section-header">Top Keywords</div>', unsafe_allow_html=True)
            if analytics["top_keywords"]:
                max_kw = analytics["top_keywords"][0][1] or 1
                for word, cnt in analytics["top_keywords"]:
                    pct = cnt / max_kw * 100
                    st.markdown(f"""
                    <div class="bar-row">
                        <div class="bar-label">{word}</div>
                        <div class="bar-track">
                            <div class="bar-fill" style="width:{pct:.0f}%;background:#FFB84A;"></div>
                        </div>
                        <div class="bar-count">{cnt}</div>
                    </div>
                    """, unsafe_allow_html=True)

        with col_b:
            st.markdown('<div class="section-header">Country Distribution</div>', unsafe_allow_html=True)
            if analytics["by_country"]:
                max_c = max(analytics["by_country"].values()) or 1
                for ctry, cnt in analytics["by_country"].items():
                    pct = cnt / max_c * 100
                    st.markdown(f"""
                    <div class="bar-row">
                        <div class="bar-label">{ctry}</div>
                        <div class="bar-track">
                            <div class="bar-fill" style="width:{pct:.0f}%;background:#B97BFF;"></div>
                        </div>
                        <div class="bar-count">{cnt}</div>
                    </div>
                    """, unsafe_allow_html=True)

            st.markdown('<br><div class="section-header">Quick Insights</div>', unsafe_allow_html=True)
            fully_pct = (fully / len(all_results) * 100) if all_results else 0
            st.markdown(f"""
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
                <div class="metric-card" style="padding:1rem;">
                    <div class="metric-label">Fully Funded %</div>
                    <div class="metric-value" style="font-size:1.8rem;">{fully_pct:.0f}%</div>
                </div>
                <div class="metric-card" style="padding:1rem;">
                    <div class="metric-label">With Deadline</div>
                    <div class="metric-value" style="font-size:1.8rem;">
                        {sum(1 for r in all_results if r['deadline_close'] != 'Not Available')}
                    </div>
                </div>
                <div class="metric-card" style="padding:1rem;">
                    <div class="metric-label">Unique Sources</div>
                    <div class="metric-value" style="font-size:1.8rem;">
                        {len(set(r['source'] for r in all_results))}
                    </div>
                </div>
                <div class="metric-card" style="padding:1rem;">
                    <div class="metric-label">With Eligibility</div>
                    <div class="metric-value" style="font-size:1.8rem;">
                        {sum(1 for r in all_results if r['eligibility'] != 'Not Available')}
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════
    # TAB 3: DATA TABLE
    # ════════════════════════════════════════════════════════
    with tab3:
        df = pd.DataFrame(display)
        if df.empty:
            st.markdown('<div class="empty-state">No data to display.</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="section-header">Full Dataset</div>', unsafe_allow_html=True)

            col_order = ["title", "country", "funding", "deadline_close", "source", "apply_link"]
            col_order = [c for c in col_order if c in df.columns]
            st.dataframe(
                df[col_order].rename(columns={
                    "title": "Title",
                    "country": "Country",
                    "funding": "Funding",
                    "deadline_close": "Deadline",
                    "source": "Source",
                    "apply_link": "Apply Link",
                }),
                use_container_width=True,
                height=420,
            )

    # ════════════════════════════════════════════════════════
    # TAB 4: EXPORT
    # ════════════════════════════════════════════════════════
    with tab4:
        st.markdown('<div class="section-header">Export Your Data</div>', unsafe_allow_html=True)

        if all_results:
            df_export = pd.DataFrame(all_results)

            col_e1, col_e2 = st.columns(2)

            with col_e1:
                st.markdown("""
                <div class="metric-card" style="padding:1.5rem;margin-bottom:1rem;">
                    <div class="metric-label">JSON Export</div>
                    <div style="font-family:var(--font-body);font-style:italic;
                                color:var(--muted);font-size:0.9rem;margin:8px 0;">
                        Structured records with all fields. Ideal for API integration.
                    </div>
                </div>
                """, unsafe_allow_html=True)
                json_str = json.dumps(all_results, indent=2, ensure_ascii=False)
                st.download_button(
                    label="⬇  Download JSON",
                    data=json_str,
                    file_name=f"scholarships_{field.replace(' ','_')}_{country}.json",
                    mime="application/json",
                    use_container_width=True,
                )

            with col_e2:
                st.markdown("""
                <div class="metric-card" style="padding:1.5rem;margin-bottom:1rem;">
                    <div class="metric-label">CSV Export</div>
                    <div style="font-family:var(--font-body);font-style:italic;
                                color:var(--muted);font-size:0.9rem;margin:8px 0;">
                        Spreadsheet-ready format. Open in Excel or Google Sheets.
                    </div>
                </div>
                """, unsafe_allow_html=True)
                csv_str = df_export.to_csv(index=False, encoding="utf-8")
                st.download_button(
                    label="⬇  Download CSV",
                    data=csv_str,
                    file_name=f"scholarships_{field.replace(' ','_')}_{country}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

            st.markdown('<br><div class="section-header">Preview (JSON)</div>', unsafe_allow_html=True)
            st.code(json.dumps(all_results[:3], indent=2, ensure_ascii=False), language="json")
        else:
            st.markdown('<div class="empty-state">No results to export yet.</div>', unsafe_allow_html=True)

else:
    # ── Landing state ─────────────────────────────────────
    st.markdown("""
    <div class="empty-state" style="padding:5rem 2rem;">
        <div style="font-size:3rem;margin-bottom:1rem;"></div>
        <div style="font-family:var(--font-head);font-size:1.4rem;font-weight:700;
                    color:var(--text);margin-bottom:0.75rem;">
            Ready to discover opportunities
        </div>
        Configure your search in the sidebar and click
        <span style="color:var(--accent);font-family:var(--font-mono);font-size:12px;">
            Find Scholarships
        </span>
        to begin.
    </div>
    """, unsafe_allow_html=True)
