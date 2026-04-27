
# ============================================================
# CELL 1: SETUP & INSTALLATION.
# ============================================================

import subprocess, sys


print('📦 Installing dependencies...')

packages = [
    'selenium',
    'beautifulsoup4',
    'requests',
    'pandas',
    'lxml',
    'webdriver-manager'
]

for pkg in packages:
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', pkg], check=True)

print(' Installing Chrome & ChromeDriver for Colab...')
subprocess.run(['apt-get', 'install', '-y', '-q', 'chromium-chromedriver'], check=True)

print(' All dependencies installed successfully!')
print(' Proceed to Cell 2.')
# ============================================================
# CELL 2: IMPORTS & LOGGING SETUP
# ============================================================

import re
import time
import json
import random
import logging
import requests
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, quote_plus
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# ── Logging configuration ──────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger('ScholarshipAI')

# ── Global constants ───────────────────────────────────────
HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

REQUEST_TIMEOUT = 12
MAX_RETRIES = 2
DELAY_MIN = 2.0
DELAY_MAX = 5.0

IRRELEVANT_DOMAINS = {
    'facebook.com', 'twitter.com', 'instagram.com', 'youtube.com',
    'reddit.com', 'quora.com', 'pinterest.com', 'linkedin.com',
    'wikipedia.org', 'amazon.com', 'ebay.com'
}

SCHOLARSHIP_KEYWORDS = [
    'scholarship', 'fellowship', 'grant', 'funded', 'bursary',
    'award', 'stipend', 'admission', 'apply', 'opportunity'
]

print('✅ Imports and constants loaded.')
# ============================================================
# CELL 3: SMART QUERY GENERATOR
# ============================================================

class SmartQueryGenerator:
    """
    Generates optimized search queries from user preferences.
    Covers Google search, direct site queries, and API-style parameters.
    """

    FUNDING_TEMPLATES = {
        'fully funded': 'fully funded scholarship {field} {country} {year}',
        'partial':      'partial scholarship {field} {country} {year}',
        'any':          'scholarship {field} {country} {year}',
    }

    BONUS_TERMS = [
        'international students',
        'deadline {year}',
        'application open',
        'tuition waiver',
        'stipend included',
    ]

    def __init__(self, field: str, country: str, funding_type: str = 'any', year: int = None):
        self.field = field.strip().lower()
        self.country = country.strip().lower()
        self.funding_type = funding_type.strip().lower()
        self.year = year or time.localtime().tm_year

    def _render(self, template: str) -> str:
        return template.format(
            field=self.field,
            country=self.country,
            year=self.year
        ).strip()

    def generate(self, max_queries: int = 6) -> list[str]:
        """Returns a list of distinct search query strings."""
        queries = []

        # Primary query from template
        template = self.FUNDING_TEMPLATES.get(self.funding_type, self.FUNDING_TEMPLATES['any'])
        queries.append(self._render(template))

        # Variations with bonus terms
        for bonus in self.BONUS_TERMS:
            bonus_rendered = bonus.format(year=self.year)
            q = f"{queries[0]} {bonus_rendered}"
            queries.append(q)
            if len(queries) >= max_queries:
                break

        # Site-specific query variants
        site_queries = [
            f'site:opportunitiescircle.com {self.funding_type} scholarship {self.field} {self.country}',
            f'site:scholarshipportal.com {self.field} scholarship {self.country}',
            f'site:daad.de scholarship {self.field} {self.country}',
        ]
        queries.extend(site_queries)

        return list(dict.fromkeys(queries))[:max_queries]  # deduplicate, cap


# ── Quick demo ─────────────────────────────────────────────
gen = SmartQueryGenerator(field='Computer Science', country='Germany', funding_type='fully funded')
sample_queries = gen.generate()
print(' Sample Generated Queries:')
for i, q in enumerate(sample_queries, 1):
    print(f'  {i}. {q}')
# ============================================================
# CELL 4: SELENIUM GOOGLE SCRAPER
# ============================================================

def build_colab_driver() -> webdriver.Chrome:
    """
    Builds a headless Chrome WebDriver configured for Google Colab.
    Uses system-installed Chromium (/usr/bin/chromium-browser).
    """
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-infobars')
    options.add_argument('--window-size=1920,1080')
    options.add_argument(f'user-agent={HEADERS["User-Agent"]}')
    options.binary_location = '/usr/bin/chromium-browser'

    service = Service('/usr/lib/chromium-browser/chromedriver')
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(20)
    return driver


def is_valid_scholarship_url(url: str) -> bool:
    """Filters out irrelevant URLs from Google results."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.replace('www.', '')
        if domain in IRRELEVANT_DOMAINS:
            return False
        path_lower = (parsed.path + url).lower()
        return any(kw in path_lower for kw in SCHOLARSHIP_KEYWORDS)
    except Exception:
        return False


def scrape_google_links(query: str, driver: webdriver.Chrome, max_links: int = 8) -> list[str]:
    """
    Uses Selenium to search Google and extract result URLs.
    Applies random delays to avoid rate-limiting.
    """
    links = []
    try:
        encoded = quote_plus(query)
        url = f'https://www.google.com/search?q={encoded}&num=10'
        driver.get(url)

        # Wait for results
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href]'))
        )
        time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

        anchors = driver.find_elements(By.CSS_SELECTOR, 'div.yuRUbf > div > span > a')
        if not anchors:
            # Fallback selector
            anchors = driver.find_elements(By.CSS_SELECTOR, 'a[jsname="UWckNb"]')

        for a in anchors:
            href = a.get_attribute('href')
            if href and href.startswith('http') and is_valid_scholarship_url(href):
                links.append(href)
            if len(links) >= max_links:
                break

        logger.info(f'Google → "{query[:50]}..." → {len(links)} valid links')

    except TimeoutException:
        logger.warning(f'Timeout on Google query: {query[:50]}')
    except WebDriverException as e:
        logger.error(f'WebDriver error: {e}')

    return links


def run_google_scraper(queries: list[str], max_per_query: int = 5) -> list[str]:
    """
    Runs Selenium Google scraping across all queries.
    Returns a deduplicated list of valid URLs.
    """
    all_links = []
    seen = set()
    driver = None

    try:
        driver = build_colab_driver()
        logger.info('Chrome WebDriver launched.')

        for i, q in enumerate(queries):
            logger.info(f'Query {i+1}/{len(queries)}: {q[:60]}')
            links = scrape_google_links(q, driver, max_links=max_per_query)
            for link in links:
                if link not in seen:
                    seen.add(link)
                    all_links.append(link)
            time.sleep(random.uniform(3, 6))  # inter-query delay

    except Exception as e:
        logger.error(f'Google scraper fatal error: {e}')
    finally:
        if driver:
            driver.quit()
            logger.info('WebDriver closed.')

    logger.info(f'Total unique Google links collected: {len(all_links)}')
    return all_links


print(' Selenium scraper functions defined.')
# ============================================================
# CELL 5: STATIC SITE SCRAPERS
# (OpportunitiesCircle, ScholarshipPortal, DAAD)
# ============================================================

def safe_get(url: str, retries: int = MAX_RETRIES) -> BeautifulSoup | None:
    """Robust HTTP GET with retry logic. Returns BeautifulSoup or None."""
    for attempt in range(1, retries + 1):
        try:
            time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, 'lxml')
        except requests.exceptions.HTTPError as e:
            logger.warning(f'HTTP {e.response.status_code} on {url} (attempt {attempt})')
        except requests.exceptions.ConnectionError:
            logger.warning(f'Connection error on {url} (attempt {attempt})')
        except requests.exceptions.Timeout:
            logger.warning(f'Timeout on {url} (attempt {attempt})')
        except Exception as e:
            logger.error(f'Unexpected error on {url}: {e}')
            break
    return None


# ── Opportunities Circle ───────────────────────────────────
def scrape_opportunities_circle(field: str = '', country: str = '') -> list[str]:
    """
    Scrapes OpportunitiesCircle.com for scholarship listing URLs.
    Uses search endpoint with keyword parameters.
    """
    links = []
    search_terms = f'{field} {country} scholarship'.strip()
    search_url = f'https://opportunitiescircle.com/?s={quote_plus(search_terms)}'

    soup = safe_get(search_url)
    if not soup:
        logger.warning('OpportunitiesCircle: could not fetch search page')
        return links

    for a in soup.select('article a[href]'):
        href = a.get('href', '')
        if href.startswith('http') and 'opportunitiescircle.com' in href:
            links.append(href)

    links = list(dict.fromkeys(links))[:10]
    logger.info(f'OpportunitiesCircle: {len(links)} links found')
    return links


# ── Scholarship Portal ─────────────────────────────────────
def scrape_scholarship_portal(field: str = '', country: str = '') -> list[str]:
    """
    Scrapes ScholarshipPortal.com listing pages.
    """
    links = []
    base = 'https://www.scholarshipportal.com'
    search_url = f'{base}/scholarships/search/?q={quote_plus(field + " " + country)}'

    soup = safe_get(search_url)
    if not soup:
        # Fallback to known listing page
        soup = safe_get(f'{base}/scholarships/')

    if not soup:
        logger.warning('ScholarshipPortal: could not fetch page')
        return links

    for a in soup.select('a[href*="/scholarships/"]'):
        href = a.get('href', '')
        if href.startswith('/'):
            href = urljoin(base, href)
        if href.startswith('http') and 'scholarshipportal.com' in href:
            links.append(href)

    links = list(dict.fromkeys(links))[:10]
    logger.info(f'ScholarshipPortal: {len(links)} links found')
    return links


# ── DAAD Germany ──────────────────────────────────────────
def scrape_daad(field: str = '', country: str = 'Germany') -> list[str]:
    """
    Scrapes DAAD.de scholarship listings.
    DAAD offers English-language pages under /en/
    """
    links = []
    base = 'https://www.daad.de'
    pages = [
        f'{base}/en/studying-in-germany/scholarships/',
        f'{base}/en/find-funding/graduate-funding/',
    ]

    for page_url in pages:
        soup = safe_get(page_url)
        if not soup:
            continue
        for a in soup.select('a[href]'):
            href = a.get('href', '')
            if '/en/' in href and ('scholarship' in href.lower() or 'funding' in href.lower()):
                full = urljoin(base, href) if href.startswith('/') else href
                if full.startswith('http'):
                    links.append(full)

    links = list(dict.fromkeys(links))[:10]
    logger.info(f'DAAD: {len(links)} links found')
    return links


def collect_static_links(field: str, country: str) -> list[str]:
    """Aggregates links from all static scrapers using multithreading."""
    all_links = []

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(scrape_opportunities_circle, field, country),
            executor.submit(scrape_scholarship_portal, field, country),
            executor.submit(scrape_daad, field, country),
        }

        for future in as_completed(futures):
            try:
                all_links.extend(future.result())
            except Exception as e:
                logger.error(f"Static scraper thread error: {e}")

    deduped = list(dict.fromkeys(all_links))
    logger.info(f'Static scrapers total unique links: {len(deduped)}')
    return deduped
# ============================================================
# CELL 6: WEB PAGE CONTENT EXTRACTOR
# ============================================================

# ── Date extraction patterns ───────────────────────────────
DATE_PATTERNS = [
    r'\b(\d{1,2}[\s/\-](?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
     r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
     r'[\s/\-]\d{4})\b',
    r'\b((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
     r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
     r'\s+\d{1,2},?\s+\d{4})\b',
    r'\b(\d{4}-\d{2}-\d{2})\b',
    r'\b(\d{2}/\d{2}/\d{4})\b',
]

# ── Funding classification patterns ───────────────────────
FULLY_FUNDED_PATTERNS = [
    r'fully[\s-]funded', r'full[\s-]scholarship', r'tuition.*waiver',
    r'all\s+expenses', r'100%\s+funded', r'covers?\s+all',
    r'stipend.*included', r'full\s+financial\s+support'
]
PARTIAL_PATTERNS = [
    r'partial[\s-]scholarship', r'partial[\s-]fund', r'partial\s+support',
    r'50%\s+tuition', r'tuition\s+reduction', r'merit\s+aid'
]


def extract_dates(text: str) -> tuple[str, str]:
    """Returns (opening_date, closing_date) from raw page text."""
    found = []
    for pat in DATE_PATTERNS:
        matches = re.findall(pat, text, re.IGNORECASE)
        found.extend(matches)

    # Look for deadline / closing context
    closing = 'Not Available'
    opening = 'Not Available'

    deadline_match = re.search(
        r'(?:deadline|closing date|apply by|due)[:\s]+([^\n<]{5,40})',
        text, re.IGNORECASE
    )
    if deadline_match:
        closing = deadline_match.group(1).strip()[:50]

    open_match = re.search(
        r'(?:open(?:ing)?(?:\s+date)?|start(?:ing)?\s+date)[:\s]+([^\n<]{5,40})',
        text, re.IGNORECASE
    )
    if open_match:
        opening = open_match.group(1).strip()[:50]

    # Fallback: use first two raw date matches
    if opening == 'Not Available' and len(found) >= 1:
        opening = found[0]
    if closing == 'Not Available' and len(found) >= 2:
        closing = found[1]

    return opening, closing


def classify_funding(text: str) -> str:
    """Classifies funding type from page text."""
    tl = text.lower()
    for pat in FULLY_FUNDED_PATTERNS:
        if re.search(pat, tl):
            return 'Fully Funded'
    for pat in PARTIAL_PATTERNS:
        if re.search(pat, tl):
            return 'Partial Funding'
    return 'Not Specified'


def extract_eligibility(text: str) -> str:
    """Extracts eligibility information from page text."""
    patterns = [
        r'eligib(?:ility|le)[:\s]+([^\n]{10,200})',
        r'requirement[s]?[:\s]+([^\n]{10,200})',
        r'who\s+can\s+apply[:\s]+([^\n]{10,200})',
        r'open\s+to[:\s]+([^\n]{10,200})',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()[:300]
    return 'Not Available'


def extract_country_from_text(text: str, fallback_url: str = '') -> str:
    """Infers country from page content."""
    COUNTRY_NAMES = [
        'Germany', 'USA', 'United States', 'UK', 'United Kingdom',
        'Canada', 'Australia', 'France', 'Japan', 'China', 'South Korea',
        'Netherlands', 'Sweden', 'Norway', 'Denmark', 'Switzerland',
        'Pakistan', 'India', 'Turkey', 'Egypt', 'Saudi Arabia', 'UAE',
        'New Zealand', 'Italy', 'Spain', 'Belgium', 'Finland', 'Austria'
    ]
    for c in COUNTRY_NAMES:
        if re.search(r'\b' + re.escape(c) + r'\b', text, re.IGNORECASE):
            return c
    return 'Not Available'


def extract_apply_link(soup: BeautifulSoup, base_url: str) -> str:
    """Finds the most relevant 'apply' or 'application' link on the page."""
    for a in soup.find_all('a', href=True):
        text = a.get_text(strip=True).lower()
        href = a['href']
        if any(kw in text for kw in ['apply now', 'apply here', 'apply online', 'application']):
            return urljoin(base_url, href) if href.startswith('/') else href
    return base_url  # fallback to the page itself


def extract_page_data(url: str) -> dict:
    """
    Core extractor. Downloads a page and extracts all scholarship fields.
    Returns a dict conforming to the output schema.
    """
    default = {
        'title': 'Not Available',
        'country': 'Not Available',
        'funding': 'Not Available',
        'deadline_open': 'Not Available',
        'deadline_close': 'Not Available',
        'eligibility': 'Not Available',
        'apply_link': url,
        'source': url,
    }

    soup = safe_get(url)
    if not soup:
        logger.warning(f'Could not fetch: {url}')
        return default

    # Title
    title_tag = soup.find('h1') or soup.find('title')
    title = title_tag.get_text(strip=True) if title_tag else 'Not Available'
    title = re.sub(r'\s+', ' ', title)[:200]

    # Full page text
    raw_text = soup.get_text(separator=' ', strip=True)
    raw_text = re.sub(r'\s+', ' ', raw_text)

    # Extract fields
    open_date, close_date = extract_dates(raw_text)
    funding = classify_funding(raw_text)
    eligibility = extract_eligibility(raw_text)
    country = extract_country_from_text(raw_text, url)
    apply_link = extract_apply_link(soup, url)

    # Source domain
    source_domain = urlparse(url).netloc.replace('www.', '')

    result = {
        'title': title,
        'country': country,
        'funding': funding,
        'deadline_open': open_date,
        'deadline_close': close_date,
        'eligibility': eligibility,
        'apply_link': apply_link,
        'source': source_domain,
    }

    logger.info(f'Extracted: "{title[:50]}" | {country} | {funding}')
    return result


def batch_extract(urls: list[str], max_workers: int = 8) -> list[dict]:
    """Extracts data from URLs in parallel using threading."""
    results = []

    def worker(url):
        try:
            logger.info(f'Extracting: {url[:70]}')
            data = extract_page_data(url)
            if data['title'] != 'Not Available':
                return data
        except Exception as e:
            logger.error(f'Worker error {url}: {e}')
        return None

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(worker, url) for url in urls]

        for future in as_completed(futures):
            res = future.result()
            if res:
                results.append(res)

    return results
# ============================================================
# CELL 7: DATA CLEANING & NORMALIZATION LAYER
# ============================================================

def normalize_text(text: str) -> str:
    """Cleans and normalizes a text string."""
    if not text or not isinstance(text, str):
        return 'Not Available'
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', text)  # control chars
    text = re.sub(r'\s+', ' ', text).strip()
    return text if text else 'Not Available'


def normalize_funding(funding: str) -> str:
    """Standardizes funding type labels."""
    fl = funding.lower()
    if 'full' in fl:
        return 'Fully Funded'
    if 'partial' in fl:
        return 'Partial Funding'
    return 'Not Specified'


def normalize_country(country: str) -> str:
    """Standardizes country names to ISO-friendly forms."""
    ALIASES = {
        'usa': 'United States',
        'us': 'United States',
        'america': 'United States',
        'uk': 'United Kingdom',
        'great britain': 'United Kingdom',
        'england': 'United Kingdom',
        'uae': 'United Arab Emirates',
    }
    cl = country.strip().lower()
    return ALIASES.get(cl, country.strip().title())


def remove_duplicates(records: list[dict]) -> list[dict]:
    """
    Deduplicates by apply_link (canonical URL).
    Keeps first occurrence of each unique link.
    """
    seen_links = set()
    seen_titles = set()
    unique = []

    for rec in records:
        link = rec.get('apply_link', '').strip().rstrip('/')
        title = rec.get('title', '').lower().strip()

        if link in seen_links or title in seen_titles:
            continue

        if link:
            seen_links.add(link)
        if title and title != 'not available':
            seen_titles.add(title)

        unique.append(rec)

    logger.info(f'Deduplication: {len(records)} → {len(unique)} records')
    return unique


def clean_record(rec: dict) -> dict:
    """Applies all normalizations to a single record."""
    return {
        'title':          normalize_text(rec.get('title', '')),
        'country':        normalize_country(rec.get('country', 'Not Available')),
        'funding':        normalize_funding(rec.get('funding', 'Not Specified')),
        'deadline_open':  normalize_text(rec.get('deadline_open', '')),
        'deadline_close': normalize_text(rec.get('deadline_close', '')),
        'eligibility':    normalize_text(rec.get('eligibility', '')),
        'apply_link':     rec.get('apply_link', 'Not Available'),
        'source':         rec.get('source', 'Not Available'),
    }


def clean_dataset(records: list[dict]) -> list[dict]:
    """Full cleaning pipeline: normalize + deduplicate."""
    cleaned = [clean_record(r) for r in records]
    cleaned = remove_duplicates(cleaned)
    cleaned = [r for r in cleaned if r['title'] != 'Not Available']
    logger.info(f'Clean dataset: {len(cleaned)} valid records')
    return cleaned


print('✅ Data cleaning layer defined.')
# ============================================================
# CELL 8: ANALYTICS & RECOMMENDATION ENGINE
# ============================================================

def group_by_country(df: pd.DataFrame) -> pd.DataFrame:
    """Groups scholarship count by country."""
    return (
        df.groupby('country')
        .agg(count=('title', 'count'), funding_types=('funding', lambda x: list(x.unique())))
        .reset_index()
        .sort_values('count', ascending=False)
    )


def group_by_funding(df: pd.DataFrame) -> pd.DataFrame:
    """Groups scholarship count by funding type."""
    return (
        df.groupby('funding')
        .size()
        .reset_index(name='count')
        .sort_values('count', ascending=False)
    )


def keyword_frequency(df: pd.DataFrame, top_n: int = 15) -> pd.DataFrame:
    """
    Analyzes word frequency across all scholarship titles.
    Filters out stopwords to surface meaningful field/domain terms.
    """
    STOPWORDS = {
        'the', 'a', 'an', 'for', 'in', 'of', 'to', 'and', 'or', 'is',
        'at', 'by', 'on', 'with', 'scholarship', 'fellowships', 'fellowship',
        'award', 'program', 'programme', 'university', 'international',
        'students', 'student', 'study', 'not', 'available', 'page'
    }
    all_words = []
    for title in df['title'].dropna():
        words = re.findall(r'\b[a-zA-Z]{3,}\b', title.lower())
        all_words.extend([w for w in words if w not in STOPWORDS])

    counter = Counter(all_words)
    return pd.DataFrame(counter.most_common(top_n), columns=['keyword', 'frequency'])


def recommend(
    df: pd.DataFrame,
    field: str = '',
    funding_type: str = '',
    country: str = '',
) -> pd.DataFrame:
    """
    Filters dataset by user preferences.
    All parameters are optional; empty string = no filter.
    """
    result = df.copy()

    if field.strip():
        result = result[
            result['title'].str.contains(field, case=False, na=False) |
            result['eligibility'].str.contains(field, case=False, na=False)
        ]

    if funding_type.strip() and funding_type.lower() != 'any':
        result = result[
            result['funding'].str.contains(funding_type, case=False, na=False)
        ]

    if country.strip():
        result = result[
            result['country'].str.contains(country, case=False, na=False)
        ]

    logger.info(f'Recommendation filter → {len(result)} matching records')
    return result.reset_index(drop=True)


def print_analytics(df: pd.DataFrame) -> None:
    """Prints a compact analytics summary to the notebook output."""
    print('\n' + '═'*60)
    print('📊  ANALYTICS SUMMARY')
    print('═'*60)

    print(f'\nTotal scholarships found: {len(df)}')

    print('\n── By Funding Type ──')
    print(group_by_funding(df).to_string(index=False))

    print('\n── By Country (Top 10) ──')
    print(group_by_country(df).head(10)[['country', 'count']].to_string(index=False))

    print('\n── Top Keywords in Titles ──')
    print(keyword_frequency(df, top_n=10).to_string(index=False))

    print('\n' + '═'*60)


print('✅ Analytics & recommendation engine defined.')
# ============================================================
# CELL 9: MAIN PIPELINE ORCHESTRATOR
# ── Configure your search preferences here ──
# ============================================================

# ┌─────────────────────────────────────────┐
# │         USER CONFIGURATION              │
# └─────────────────────────────────────────┘
USER_FIELD        = 'Artificial Intelligence'   # e.g., 'Computer Science', 'Engineering'
USER_COUNTRY      = 'Germany'                   # e.g., 'UK', 'USA', 'any'
USER_FUNDING_TYPE = 'fully funded'              # 'fully funded' | 'partial' | 'any'

# Control flags
USE_SELENIUM      = True   # Set False if Selenium setup failed
MAX_GOOGLE_LINKS  = 5      # Per query (keep low to avoid rate limiting)


# ── Pipeline ──────────────────────────────────────────────
def run_pipeline(
    field: str,
    country: str,
    funding_type: str,
    use_selenium: bool = True,
) -> tuple[list[dict], pd.DataFrame]:

    logger.info('=' * 55)
    logger.info('  AI Scholarship Intelligence System — Pipeline Start')
    logger.info(f'   Field: {field} | Country: {country} | Funding: {funding_type}')
    logger.info('=' * 55)

    # STEP 1: Generate queries
    logger.info('STEP 1: Generating search queries...')
    qgen = SmartQueryGenerator(field=field, country=country, funding_type=funding_type)
    queries = qgen.generate(max_queries=4)

    # STEP 2: Google scraping (Selenium)
    google_links = []
    if use_selenium:
        logger.info('STEP 2: Selenium Google scraping...')
        google_links = run_google_scraper(queries[:3], max_per_query=MAX_GOOGLE_LINKS)
    else:
        logger.info('STEP 2: Skipping Selenium (flag disabled).')

    # STEP 3: Static scrapers
    logger.info('STEP 3: Running static site scrapers...')
    static_links = collect_static_links(field, country)

    # STEP 4: Merge & deduplicate all links
    all_links = list(dict.fromkeys(google_links + static_links))
    logger.info(f'STEP 4: Total unique links to extract: {len(all_links)}')

    if not all_links:
        logger.warning('No links collected. Returning empty dataset.')
        return [], pd.DataFrame()

    # STEP 5: Extract page content
    logger.info('STEP 5: Extracting content from pages...')
    raw_records = batch_extract(all_links[:25])  # cap to avoid Colab timeout

    # STEP 6: Clean & normalize
    logger.info('STEP 6: Cleaning and normalizing data...')
    clean_records = clean_dataset(raw_records)

    # STEP 7: Build DataFrame
    df = pd.DataFrame(clean_records)

    logger.info(f' Pipeline complete. {len(clean_records)} scholarships found.')
    return clean_records, df


# ── RUN IT ────────────────────────────────────────────────
records, df = run_pipeline(
    field=USER_FIELD,
    country=USER_COUNTRY,
    funding_type=USER_FUNDING_TYPE,
    use_selenium=USE_SELENIUM,
)
# ============================================================
# CELL 10: OUTPUT DISPLAY & EXPORT
# ============================================================

from IPython.display import display, HTML
import json

if df.empty:
    print('⚠  No data collected. Try adjusting your search parameters or re-running the pipeline.')
else:
    # ── Analytics Summary ─────────────────────────────────
    print_analytics(df)

    # ── Recommendations (filter by user prefs) ────────────
    print('\n📌  RECOMMENDED RESULTS (filtered)')
    recommended = recommend(df, field=USER_FIELD, funding_type=USER_FUNDING_TYPE, country=USER_COUNTRY)

    if recommended.empty:
        print('No exact matches — showing all results instead.')
        recommended = df

    # ── Display as styled table ───────────────────────────
    display_cols = ['title', 'country', 'funding', 'deadline_close', 'apply_link', 'source']
    display(recommended[display_cols].head(20))

    # ── Full JSON output ──────────────────────────────────
    print('\n  JSON OUTPUT (first 5 records):')
    print(json.dumps(records[:5], indent=2, ensure_ascii=False))

    # ── Export to files ───────────────────────────────────
    json_path = '/content/scholarships_output.json'
    csv_path  = '/content/scholarships_output.csv'

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    df.to_csv(csv_path, index=False, encoding='utf-8')

    print(f'\n Exported:')
    print(f'   JSON → {json_path}')
    print(f'   CSV  → {csv_path}')
    print('\n Download via: Files panel (left sidebar) → Right-click → Download')

    # ── Download helper (Colab-native) ────────────────────
    try:
        from google.colab import files
        files.download(json_path)
        files.download(csv_path)
    except ImportError:
        print('(Running outside Colab — files saved to /content/ path above.)')
