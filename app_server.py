#!/usr/bin/env python3
import json
import hashlib
import math
import os
import random
import time
import re
import calendar
from datetime import date, datetime, time as datetime_time, timedelta
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlencode, urlparse, parse_qs
from urllib.request import urlopen, Request
from zoneinfo import ZoneInfo
from pytrends.request import TrendReq


PILLARS = ["Politics", "Sports", "Entertainment", "Sci & Tech", "Business", "Lifestyle"]
WIKI_TOP_BASE = "https://wikimedia.org/api/rest_v1/metrics/pageviews/top/en.wikipedia/all-access"
YT_BASE = "https://www.googleapis.com/youtube/v3/videos"
YT_SEARCH_BASE = "https://www.googleapis.com/youtube/v3/search"
CACHE_FILE = "historical_cache.json"
LIVE_CACHE_FILE = "youtube_live_cache.json"
GOOGLE_TRENDS_CACHE_FILE = "google_trends_cache.json"
WIKI_CACHE_FILE = "wikipedia_cache.json"
ANALYSIS_CACHE_FILE = "analysis_cache.json"
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")
OLLAMA_TIMEOUT_SECONDS = int(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "90"))
WIKI_DAILY_MAX_RANGE_DAYS = 7
WIKI_MIN_REQUEST_DELAY_SECONDS = 0.3
WIKI_MAX_RETRIES = 3
RANGE_CACHE = None
GOOGLE_TRENDS_BASELINE_DAYS = 90
GOOGLE_TRENDS_THEMES_PER_PILLAR = 2
GOOGLE_TRENDS_UNCACHED_MAX_PER_REQUEST = 6
GOOGLE_TRENDS_ERROR_CACHE_TTL_SECONDS = 6 * 60 * 60
GOOGLE_TRENDS_MIN_DELAY_SECONDS = 4.0
GOOGLE_TRENDS_MAX_DELAY_SECONDS = 7.0
GOOGLE_TRENDS_MAX_RETRIES = 3
YOUTUBE_LIVE_LOOKBACK_HOURS = 36
LIVE_CACHE = None
LIVE_CACHE_TTL_SECONDS = 3600
LIVE_STALE_CACHE_SECONDS = 86400
YOUTUBE_SEARCHES_PER_REFRESH = 3

PILLAR_KEYWORDS = {
    "Politics": ["election", "congress", "senate", "president", "white house", "supreme court", "policy", "vote", "protest", "government", "trump", "biden"],
    "Sports": [
        "sports", "nfl", "nba", "wnba", "mlb", "nhl", "soccer", "football", "basketball", "baseball",
        "olympics", "world cup", "ufc", "game", "finals", "final four", "march madness", "ncaa tournament",
        "college basketball", "women's basketball", "womens basketball", "women's college basketball",
        "womens college basketball", "ncaa women's basketball", "ncaa womens basketball", "ncaaw",
        "women's final four", "womens final four", "women's march madness", "womens march madness",
        "wnba draft", "wnba season", "wnba standings",
    ],
    "Entertainment": ["movie", "film", "music", "album", "celebrity", "streaming", "netflix", "disney", "actor", "singer", "concert", "meme", "viral"],
    "Sci & Tech": ["technology", "tech", "science", "ai", "artificial intelligence", "nasa", "space", "apple", "google", "microsoft", "tesla", "robot", "startup"],
    "Business": ["market", "stocks", "economy", "inflation", "crypto", "bitcoin", "federal reserve", "earnings", "tariff", "recession", "layoff", "wall street"],
    "Lifestyle": ["health", "wellness", "fashion", "travel", "food", "relationship", "fitness", "beauty", "recipe", "wedding", "home", "diet"],
}

GOOGLE_TRENDS_THEMES = [
    {
        "pillar": "Politics",
        "theme": "Elections",
        "keywords": {
            "Presidential Election": 1.0,
            "Election Results": 0.9,
            "Presidential Debate": 0.9,
            "Voting": 0.8,
            "Electoral College": 0.7,
        },
    },
    {
        "pillar": "Politics",
        "theme": "Policy Debates",
        "keywords": {
            "Immigration Policy": 1.0,
            "Healthcare Policy": 0.9,
            "Tax Policy": 0.9,
            "Climate Policy": 0.8,
            "Student Loan Forgiveness": 0.8,
        },
    },
    {
        "pillar": "Politics",
        "theme": "National News",
        "keywords": {
            "Breaking News": 1.0,
            "Supreme Court": 0.9,
            "Congress": 0.8,
            "Government Shutdown": 0.8,
            "Protest": 0.7,
        },
    },
    {
        "pillar": "Sports",
        "theme": "Women's Basketball",
        "keywords": {
            "WNBA Draft": 1.0,
            "Women's March Madness": 1.0,
            "NCAA women's basketball": 1.0,
            "Women's Final Four": 0.9,
            "WNBA": 0.9,
        },
    },
    {
        "pillar": "Sports",
        "theme": "NBA & WNBA",
        "keywords": {
            "NBA Finals": 1.0,
            "NBA Playoffs": 0.9,
            "WNBA": 0.9,
            "Caitlin Clark": 0.8,
            "LeBron James": 0.7,
        },
    },
    {
        "pillar": "Sports",
        "theme": "Super Bowl",
        "keywords": {
            "Super Bowl": 1.0,
            "NFL Playoffs": 0.9,
            "AFC Championship": 0.8,
            "NFC Championship": 0.8,
            "Halftime Show": 0.7,
        },
    },
    {
        "pillar": "Sports",
        "theme": "March Madness",
        "keywords": {
            "March Madness": 1.0,
            "NCAA Tournament": 0.9,
            "Final Four": 0.8,
            "Bracket": 0.7,
            "College Basketball": 0.7,
        },
    },
    {
        "pillar": "Sports",
        "theme": "Global Sports",
        "keywords": {
            "Club World Cup": 1.0,
            "FIFA Club World Cup": 1.0,
            "World Cup": 0.6,
            "Team USA": 0.5,
            "Lionel Messi": 0.5,
        },
    },
    {
        "pillar": "Entertainment",
        "theme": "Music Culture",
        "keywords": {
            "Taylor Swift": 1.0,
            "Drake": 0.9,
            "Beyonce": 0.9,
            "Spotify": 0.8,
            "New Music Friday": 0.7,
        },
    },
    {
        "pillar": "Entertainment",
        "theme": "Awards Shows",
        "keywords": {
            "Oscars": 1.0,
            "Grammy Awards": 0.9,
            "Emmy Awards": 0.8,
            "Golden Globes": 0.8,
            "Red Carpet": 0.7,
        },
    },
    {
        "pillar": "Entertainment",
        "theme": "Viral Culture",
        "keywords": {
            "TikTok Trends": 1.0,
            "Memes": 0.9,
            "Viral Video": 0.9,
            "Internet Trends": 0.8,
            "Social Media Trend": 0.8,
        },
    },
    {
        "pillar": "Sci & Tech",
        "theme": "AI Breakthroughs",
        "keywords": {
            "ChatGPT": 1.0,
            "OpenAI": 0.9,
            "Artificial Intelligence": 0.9,
            "AI Tools": 0.8,
            "Generative AI": 0.8,
        },
    },
    {
        "pillar": "Sci & Tech",
        "theme": "Technology Launches",
        "keywords": {
            "Apple Event": 1.0,
            "iPhone Launch": 0.9,
            "WWDC": 0.9,
            "Nvidia": 0.8,
            "Consumer Electronics": 0.7,
        },
    },
    {
        "pillar": "Sci & Tech",
        "theme": "Consumer Tech Culture",
        "keywords": {
            "Headphones": 1.0,
            "Wearable Technology": 0.9,
            "Gaming Console": 0.8,
            "Virtual Reality": 0.8,
            "Smart Glasses": 0.7,
        },
    },
    {
        "pillar": "Business",
        "theme": "Markets & Economy",
        "keywords": {
            "Stock Market": 1.0,
            "S&P 500": 0.9,
            "Federal Reserve": 0.9,
            "Recession": 0.8,
            "Jobs Report": 0.8,
        },
    },
    {
        "pillar": "Business",
        "theme": "Taxes & Personal Finance",
        "keywords": {
            "Tax Refund": 1.0,
            "IRS": 0.9,
            "Tax Filing": 0.9,
            "TurboTax": 0.8,
            "Personal Finance": 0.8,
        },
    },
    {
        "pillar": "Business",
        "theme": "Small Business & Entrepreneurship",
        "keywords": {
            "Small Business": 1.0,
            "Entrepreneurship": 0.9,
            "Business Loan": 0.8,
            "QuickBooks": 0.8,
            "Self Employed": 0.7,
        },
    },
    {
        "pillar": "Lifestyle",
        "theme": "Fitness & Performance",
        "keywords": {
            "Running Shoes": 1.0,
            "Workout": 0.9,
            "Marathon Training": 0.8,
            "Fitness Tracker": 0.8,
            "Athleisure": 0.7,
        },
    },
    {
        "pillar": "Lifestyle",
        "theme": "Fashion & Style",
        "keywords": {
            "Fashion Trends": 1.0,
            "Sneakers": 0.9,
            "Streetwear": 0.8,
            "Outfit Ideas": 0.8,
            "Summer Fashion": 0.7,
        },
    },
    {
        "pillar": "Lifestyle",
        "theme": "Travel",
        "keywords": {
            "Summer Travel": 1.0,
            "Vacation": 0.9,
            "Travel Deals": 0.8,
            "Flights": 0.8,
            "Hotels": 0.7,
        },
    },
]

UTC = ZoneInfo("UTC")
CENTRAL = ZoneInfo("America/Chicago")

CAT_TO_PILLAR = {
    25: "Politics", 17: "Sports", 24: "Entertainment", 10: "Entertainment",
    23: "Entertainment", 1: "Entertainment", 43: "Entertainment",
    28: "Sci & Tech", 27: "Sci & Tech", 20: "Entertainment",
    26: "Lifestyle", 22: "Lifestyle", 19: "Lifestyle",
}

PILLAR_TO_YT_CATEGORY = {
    "Politics": "25",
    "Sports": "17",
    "Entertainment": "24",
    "Sci & Tech": "28",
    "Lifestyle": "26",
}

YOUTUBE_CORE_QUERIES = [
    "NBA Finals",
    "business news",
]

YOUTUBE_ROTATING_QUERIES = [
    "NBA highlights",
    "breaking news",
    "sports highlights",
    "music video",
    "tech news",
    "stock market",
]

def read_json_url(url):
    req = Request(url, headers={"User-Agent": "CulturalPulsePrototype/1.0"})
    with urlopen(req, timeout=20) as res:
        return json.loads(res.read().decode("utf-8"))


def blank_raw():
    return {pillar: 0 for pillar in PILLARS}


def empty_topics():
    return {pillar: [] for pillar in PILLARS}


def normalize(raw):
    positive = [value for value in raw.values() if value > 0]
    if not positive:
        return {pillar: 0 for pillar in raw}

    prior = 0.5
    smoothed = {pillar: value + prior for pillar, value in raw.items()}
    max_value = max(smoothed.values()) or 1
    max_log = math.log1p(max_value)
    floor = 8
    return {
        pillar: round(floor + (100 - floor) * (math.log1p(value) / max_log))
        for pillar, value in smoothed.items()
    }


def classify(text):
    haystack = str(text or "").lower().replace("_", " ")
    best, best_score = None, 0
    for pillar, keywords in PILLAR_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword_matches(haystack, keyword))
        if score > best_score:
            best, best_score = pillar, score
    return best


def keyword_matches(haystack, keyword):
    if " " in keyword:
        return keyword in haystack
    return re.search(rf"\b{re.escape(keyword)}\b", haystack) is not None


def matched_keywords(text, pillar, limit=4):
    haystack = str(text or "").lower().replace("_", " ")
    matches = [
        keyword
        for keyword in PILLAR_KEYWORDS.get(pillar, [])
        if keyword_matches(haystack, keyword)
    ]
    return matches[:limit]


def parse_iso_date(date_str):
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def central_day_bounds(date_str):
    local_day = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=CENTRAL)
    start = local_day.astimezone(UTC)
    end = (local_day + timedelta(days=1)).astimezone(UTC)
    return start, end


def central_range_bounds(start_date_str, end_date_str):
    local_start = datetime.strptime(start_date_str, "%Y-%m-%d").replace(tzinfo=CENTRAL)
    local_end = datetime.strptime(end_date_str, "%Y-%m-%d").replace(tzinfo=CENTRAL) + timedelta(days=1)
    return local_start.astimezone(UTC), local_end.astimezone(UTC)


def iter_utc_date_weights(start_utc, end_utc):
    total = (end_utc - start_utc).total_seconds() or 1
    cursor_date = start_utc.date()
    end_date = end_utc.date()
    while cursor_date <= end_date:
        day_start = datetime.combine(cursor_date, datetime_time.min, tzinfo=UTC)
        day_end = day_start + timedelta(days=1)
        overlap_start = max(start_utc, day_start)
        overlap_end = min(end_utc, day_end)
        if overlap_end > overlap_start:
            yield cursor_date, (overlap_end - overlap_start).total_seconds() / total
        cursor_date += timedelta(days=1)


def wiki_http_rate_limited(exc):
    message = str(exc).lower()
    return "429" in message or "too many requests" in message


def load_wiki_cache():
    try:
        with open(WIKI_CACHE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_wiki_cache(cache):
    tmp = f"{WIKI_CACHE_FILE}.tmp"
    with open(tmp, "w") as f:
        json.dump(cache, f)
    os.replace(tmp, WIKI_CACHE_FILE)


def fetch_wiki_articles(url):
    last_exc = None
    for attempt in range(WIKI_MAX_RETRIES):
        try:
            time.sleep(WIKI_MIN_REQUEST_DELAY_SECONDS)
            data = read_json_url(url)
            return data.get("items", [{}])[0].get("articles", [])
        except Exception as exc:
            last_exc = exc
            if wiki_http_rate_limited(exc) and attempt < WIKI_MAX_RETRIES - 1:
                backoff = (attempt + 1) * 2 + random.uniform(0.5, 1.5)
                print(f"Wikipedia rate limited, retrying in {backoff:.1f}s...")
                time.sleep(backoff)
                continue
            raise
    raise last_exc


def cached_wiki_articles(cache_key, url, wiki_cache):
    cached = wiki_cache.get(cache_key)
    if cached is not None:
        return cached

    articles = fetch_wiki_articles(url)
    wiki_cache[cache_key] = articles
    save_wiki_cache(wiki_cache)
    return articles


def iter_wiki_month_slices(start_date, end_date):
    start = parse_iso_date(start_date)
    end = parse_iso_date(end_date)
    year, month = start.year, start.month

    while date(year, month, 1) <= end:
        days_in_month = calendar.monthrange(year, month)[1]
        month_start = date(year, month, 1)
        month_end = date(year, month, days_in_month)
        slice_start = max(start, month_start)
        slice_end = min(end, month_end)
        if slice_start <= slice_end:
            days_in_slice = (slice_end - slice_start).days + 1
            yield year, month, days_in_slice / days_in_month
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1


def accumulate_wiki_articles(raw, candidates, articles, weight):
    for page in articles:
        title = page.get("article", "")
        if title == "Main_Page" or title.startswith("Special:"):
            continue
        pillar = classify(title)
        if not pillar:
            continue
        views = page.get("views", 0)
        weighted_views = views * weight
        raw[pillar] += math.log10(weighted_views + 1)
        readable_title = title.replace("_", " ")
        current = candidates[pillar].setdefault(title, {
            "name": readable_title,
            "views": 0,
            "url": f"https://en.wikipedia.org/wiki/{title}",
            "keywords": matched_keywords(title, pillar),
        })
        current["views"] += weighted_views


def wiki_signal(start_date, end_date=None):
    raw, topics = blank_raw(), empty_topics()
    end_date = end_date or start_date
    start = parse_iso_date(start_date)
    end = parse_iso_date(end_date)
    range_days = (end - start).days + 1
    today_utc = datetime.now(UTC).date()
    candidates = {pillar: {} for pillar in PILLARS}
    wiki_cache = load_wiki_cache()

    if range_days <= WIKI_DAILY_MAX_RANGE_DAYS:
        start_utc, end_utc = central_range_bounds(start_date, end_date)
        for utc_day, weight in iter_utc_date_weights(start_utc, end_utc):
            if utc_day > today_utc:
                continue
            cache_key = utc_day.isoformat()
            url = f"{WIKI_TOP_BASE}/{utc_day:%Y/%m/%d}"
            try:
                articles = cached_wiki_articles(cache_key, url, wiki_cache)
                accumulate_wiki_articles(raw, candidates, articles, weight)
            except Exception as exc:
                print(f"Wikipedia unavailable for {utc_day}: {exc}")
    else:
        for year, month, weight in iter_wiki_month_slices(start_date, end_date):
            if date(year, month, 1) > today_utc:
                continue
            cache_key = f"{year}-{month:02d}-all-days"
            url = f"{WIKI_TOP_BASE}/{year}/{month:02d}/all-days"
            try:
                articles = cached_wiki_articles(cache_key, url, wiki_cache)
                accumulate_wiki_articles(raw, candidates, articles, weight)
            except Exception as exc:
                print(f"Wikipedia unavailable for {year}-{month:02d}: {exc}")

    if not any(candidates[pillar] for pillar in PILLARS):
        raise RuntimeError("Wikipedia returned no pageview data for this date window")

    for pillar in PILLARS:
        top = sorted(candidates[pillar].values(), key=lambda item: item["views"], reverse=True)[:5]
        topics[pillar] = [
            {
                "name": item["name"],
                "heat": f"{round(item['views'] / 1000)}k views",
                "source": "Wikipedia",
                "url": item["url"],
                "description": f"Wikipedia pageviews for {item['name']} during this date window.",
                "signalType": "Public curiosity",
                "sourceDetail": "Wikipedia Pageviews measures how often people opened this article.",
                "why": f"Ranked because it accumulated about {round(item['views'] / 1000)}k weighted pageviews during the selected window.",
                "keywords": item["keywords"],
            }
            for item in top
        ]
    return {"scores": normalize(raw), "topics": topics}

def historical_trends_configs():
  """Pick themes round-robin so the first uncached pass covers every pillar."""
  by_pillar = {pillar: [] for pillar in PILLARS}
  for config in GOOGLE_TRENDS_THEMES:
    pillar = config["pillar"]
    if len(by_pillar.get(pillar, [])) < GOOGLE_TRENDS_THEMES_PER_PILLAR:
      by_pillar[pillar].append(config)

  selected = []
  for theme_index in range(GOOGLE_TRENDS_THEMES_PER_PILLAR):
    for pillar in PILLARS:
      pillar_configs = by_pillar.get(pillar, [])
      if theme_index < len(pillar_configs):
        selected.append(pillar_configs[theme_index])
  return selected


def google_trends_timeframe(start_date, end_date):
  start = parse_iso_date(start_date)
  end = parse_iso_date(end_date)
  baseline_start = start - timedelta(days=GOOGLE_TRENDS_BASELINE_DAYS)
  return f"{baseline_start.isoformat()} {end.isoformat()}"


def google_trends_cache_key(theme, start_date, end_date):
  return f"trends-v3|{theme}|{start_date}|{end_date}"


def load_google_trends_cache():
  try:
    with open(GOOGLE_TRENDS_CACHE_FILE, "r") as f:
      return json.load(f)
  except Exception:
    return {}


def save_google_trends_cache(cache):
  tmp = f"{GOOGLE_TRENDS_CACHE_FILE}.tmp"
  with open(tmp, "w") as f:
    json.dump(cache, f)
  os.replace(tmp, GOOGLE_TRENDS_CACHE_FILE)


def trends_rate_limited(exc):
  message = str(exc).lower()
  return "429" in message or "too many requests" in message or "rate limit" in message


def fetch_trends_interest(pytrends, keywords, timeframe):
  last_exc = None
  for attempt in range(GOOGLE_TRENDS_MAX_RETRIES):
    try:
      pytrends.build_payload(keywords, timeframe=timeframe, geo="US")
      return pytrends.interest_over_time()
    except Exception as exc:
      last_exc = exc
      if trends_rate_limited(exc) and attempt < GOOGLE_TRENDS_MAX_RETRIES - 1:
        backoff = (attempt + 1) * 12 + random.uniform(2.0, 5.0)
        print(f"Google Trends rate limited, retrying in {backoff:.1f}s...")
        time.sleep(backoff)
        continue
      raise
  raise last_exc


def google_trends_cached_row(config, start_date, end_date, trends_cache):
    cache_key = google_trends_cache_key(config["theme"], start_date, end_date)
    cached = trends_cache.get(cache_key)
    if not cached:
        return None

    if cached.get("error"):
        try:
            failed_at = datetime.fromisoformat(cached.get("failed_at", "")).astimezone(UTC)
            if (datetime.now(UTC) - failed_at).total_seconds() < GOOGLE_TRENDS_ERROR_CACHE_TTL_SECONDS:
                return {"cached_error": True}
        except Exception:
            return {"cached_error": True}
        trends_cache.pop(cache_key, None)
        save_google_trends_cache(trends_cache)
        return None

    return {
        "pillar": config["pillar"],
        "theme": config["theme"],
        **cached,
    }


def score_trends_theme(data, keywords, weights, start_date, end_date):
  if data.empty:
    return None

  if "isPartial" in data.columns:
    data = data.drop(columns=["isPartial"])

  weighted_score = sum(
    data[keyword] * weights[keyword]
    for keyword in keywords
  ) / sum(weights.values())

  start = parse_iso_date(start_date)
  end = parse_iso_date(end_date)
  baseline_end = start - timedelta(days=1)
  baseline_start = baseline_end - timedelta(days=GOOGLE_TRENDS_BASELINE_DAYS)

  window_mask = (weighted_score.index.date >= start) & (weighted_score.index.date <= end)
  baseline_mask = (
    (weighted_score.index.date >= baseline_start)
    & (weighted_score.index.date <= baseline_end)
  )

  window_series = weighted_score[window_mask] if window_mask.any() else weighted_score.tail(1)
  baseline_mean = float(weighted_score[baseline_mask].mean()) if baseline_mask.any() else float(weighted_score.mean()) or 1
  window_mean = float(window_series.mean())
  normalized_value = window_mean / baseline_mean if baseline_mean else 0

  peak_date = window_series.idxmax()
  top_keywords = (
    data.loc[peak_date]
    .sort_values(ascending=False)
    .head(3)
    .index
    .tolist()
  )

  return {
    "score": normalized_value,
    "closest_date": peak_date.isoformat(),
    "top_keywords": top_keywords,
  }


def fetch_trend_theme_row(pytrends, config, start_date, end_date, trends_cache):
    pillar = config["pillar"]
    theme = config["theme"]
    keywords = list(config["keywords"].keys())
    weights = config["keywords"]
    cache_key = google_trends_cache_key(theme, start_date, end_date)

    timeframe = google_trends_timeframe(start_date, end_date)
    try:
        data = fetch_trends_interest(pytrends, keywords, timeframe)
        scored = score_trends_theme(data, keywords, weights, start_date, end_date)
        if not scored:
            return None

        trends_cache[cache_key] = scored
        save_google_trends_cache(trends_cache)
        return {"pillar": pillar, "theme": theme, **scored}
    except Exception as exc:
        trends_cache[cache_key] = {
            "error": str(exc),
            "failed_at": datetime.now(UTC).isoformat(),
        }
        save_google_trends_cache(trends_cache)
        raise


def google_trends_signal(start_date=None, end_date=None):
    """
    Google Trends historical signal.

    Fetches up to two themes per pillar with disk caching. To avoid
    Google Trends rate limits, each request only warms a small number
    of uncached themes and reuses cached themes immediately.
    """
    start_date = start_date or date.today().isoformat()
    end_date = end_date or start_date

    pytrends = TrendReq(hl="en-US", tz=360)
    trends_cache = load_google_trends_cache()

    raw = blank_raw()
    topics = empty_topics()
    theme_rows = []
    rate_limit_hit = False
    uncached_fetches = 0

    for config in historical_trends_configs():
        pillar = config["pillar"]
        theme = config["theme"]
        cached_row = google_trends_cached_row(config, start_date, end_date, trends_cache)
        if cached_row:
            if not cached_row.get("cached_error"):
                raw[pillar] += cached_row["score"]
                theme_rows.append(cached_row)
            continue

        if uncached_fetches >= GOOGLE_TRENDS_UNCACHED_MAX_PER_REQUEST:
            print("Google Trends uncached fetch cap reached; remaining themes will load from cache on later requests.")
            break

        if rate_limit_hit:
            delay = GOOGLE_TRENDS_MAX_DELAY_SECONDS + random.uniform(3.0, 6.0)
        else:
            delay = random.uniform(GOOGLE_TRENDS_MIN_DELAY_SECONDS, GOOGLE_TRENDS_MAX_DELAY_SECONDS)
        time.sleep(delay)

        try:
            row = fetch_trend_theme_row(pytrends, config, start_date, end_date, trends_cache)
            uncached_fetches += 1
            if not row:
                continue
            raw[pillar] += row["score"]
            theme_rows.append(row)
        except Exception as exc:
            uncached_fetches += 1
            if trends_rate_limited(exc):
                rate_limit_hit = True
            print(f"Google Trends unavailable for {pillar} → {theme}: {exc}")
            continue

    theme_counts = {pillar: 0 for pillar in PILLARS}
    for row in theme_rows:
        theme_counts[row["pillar"]] += 1

    for pillar in PILLARS:
        if theme_counts[pillar]:
            raw[pillar] = raw[pillar] / theme_counts[pillar]

    scores = normalize(raw)
    window_label = start_date if start_date == end_date else f"{start_date} to {end_date}"

    for pillar in PILLARS:
        top = sorted(
            [row for row in theme_rows if row["pillar"] == pillar],
            key=lambda row: row["score"],
            reverse=True,
        )[:5]

        topics[pillar] = [
            {
                "name": row["theme"],
                "heat": f"{row['score']:.1f}x baseline",
                "source": "Google Trends",
                "url": "",
                "description": (
                    f"Google Trends theme signal for {row['theme']} during {window_label}."
                ),
                "signalType": "Search interest",
                "sourceDetail": (
                    f"Google Trends compared to the prior {GOOGLE_TRENDS_BASELINE_DAYS}-day baseline."
                ),
                "why": (
                    f"Ranked because {row['theme']} was "
                    f"{row['score']:.1f}x its normal Google search baseline."
                ),
                "keywords": row["top_keywords"],
            }
            for row in top
        ]

    return {"scores": scores, "topics": topics}

def youtube_key():
    if os.environ.get("YOUTUBE_API_KEY"):
        return os.environ["YOUTUBE_API_KEY"].strip()
    try:
        with open("config.local.json") as f:
            return json.load(f).get("youtubeApiKey", "").strip()
    except Exception:
        return ""


def parse_youtube_datetime(value):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def format_views(value):
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M views"
    if value >= 1_000:
        return f"{round(value / 1_000)}k views"
    return f"{value} views"


def format_age(published_at, now):
    hours = max(0, round((now - published_at).total_seconds() / 3600))
    return f"{hours}h old"


def short_text(value, limit=180):
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit] + ("..." if len(text) > limit else "")


def youtube_item_score(item, now):
    stats = item.get("statistics", {})
    views = int(stats.get("viewCount", 0) or 0)
    likes = int(stats.get("likeCount", 0) or 0)
    comments = int(stats.get("commentCount", 0) or 0)
    published_at = parse_youtube_datetime(item.get("snippet", {}).get("publishedAt"))
    engagement = (likes + comments) / views if views else 0
    age_hours = ((now - published_at).total_seconds() / 3600) if published_at else YOUTUBE_LIVE_LOOKBACK_HOURS
    recency_boost = 1 + max(0, (YOUTUBE_LIVE_LOOKBACK_HOURS - age_hours) / YOUTUBE_LIVE_LOOKBACK_HOURS)
    return views * (1 + engagement) * recency_boost


def youtube_pillar(item):
    snippet = item.get("snippet", {})
    title = snippet.get("title", "")
    cat_id = int(snippet.get("categoryId", 0) or 0)
    title_lower = title.lower()
    if any(k in title_lower for k in PILLAR_KEYWORDS["Business"]):
        return "Business"
    return classify(title) or CAT_TO_PILLAR.get(cat_id)


def youtube_video_details(ids, key):
    items = []
    for index in range(0, len(ids), 50):
        params = {
            "part": "snippet,statistics",
            "id": ",".join(ids[index:index + 50]),
            "key": key,
        }
        data = read_json_url(f"{YT_BASE}?{urlencode(params)}")
        items.extend(data.get("items", []))
    return items


def youtube_live_queries(now):
    remaining = max(0, YOUTUBE_SEARCHES_PER_REFRESH - len(YOUTUBE_CORE_QUERIES))
    if remaining == 0:
        return YOUTUBE_CORE_QUERIES[:YOUTUBE_SEARCHES_PER_REFRESH]
    slot = int(now.timestamp() // LIVE_CACHE_TTL_SECONDS)
    rotating = [
        YOUTUBE_ROTATING_QUERIES[(slot + offset) % len(YOUTUBE_ROTATING_QUERIES)]
        for offset in range(remaining)
    ]
    return [*YOUTUBE_CORE_QUERIES, *rotating]


def youtube_recent_search_ids(key, cutoff, now):
    ids = []
    published_after = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
    searches = [{"q": query} for query in youtube_live_queries(now)]
    for search in searches:
        params = {
            "part": "snippet",
            "type": "video",
            "order": "viewCount",
            "regionCode": "US",
            "relevanceLanguage": "en",
            "publishedAfter": published_after,
            "maxResults": "10",
            "key": key,
        }
        params.update(search)
        data = read_json_url(f"{YT_SEARCH_BASE}?{urlencode(params)}")
        ids.extend(
            item.get("id", {}).get("videoId")
            for item in data.get("items", [])
            if item.get("id", {}).get("videoId")
        )
    return ids


def youtube_signal():
    key = youtube_key()
    if not key:
        return None
    now = datetime.now(UTC)
    cutoff = now - timedelta(hours=YOUTUBE_LIVE_LOOKBACK_HOURS)
    raw, topics = blank_raw(), empty_topics()
    candidates = {pillar: [] for pillar in PILLARS}
    seen = set()

    def add_item(item):
        video_id = item.get("id")
        if not video_id or video_id in seen:
            return
        seen.add(video_id)
        snippet = item.get("snippet", {})
        published_at = parse_youtube_datetime(snippet.get("publishedAt"))
        if not published_at or published_at < cutoff:
            return
        title = snippet.get("title", "")
        pillar = youtube_pillar(item)
        if not pillar:
            return
        score = youtube_item_score(item, now)
        raw[pillar] += score
        views = int(item.get("statistics", {}).get("viewCount", 0) or 0)
        candidates[pillar].append({
            "name": title[:60] + ("..." if len(title) > 60 else ""),
            "heat": f"{format_views(views)} · {format_age(published_at, now)}",
            "source": snippet.get("channelTitle", "YouTube"),
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "description": short_text(snippet.get("description")),
            "score": score,
        })

    page_token = None
    for _ in range(2):
        params = {
            "part": "snippet,statistics",
            "chart": "mostPopular",
            "regionCode": "US",
            "maxResults": "50",
            "key": key,
        }
        if page_token:
            params["pageToken"] = page_token
        data = read_json_url(f"{YT_BASE}?{urlencode(params)}")
        for item in data.get("items", []):
            add_item(item)
        page_token = data.get("nextPageToken")
        if not page_token:
            break

    recent_ids = list(dict.fromkeys(youtube_recent_search_ids(key, cutoff, now)))
    for item in youtube_video_details(recent_ids, key):
        add_item(item)

    for pillar in PILLARS:
        top = sorted(candidates[pillar], key=lambda item: item["score"], reverse=True)[:5]
        topics[pillar] = [
            {
                "name": item["name"],
                "heat": item["heat"],
                "source": item["source"],
                "url": item["url"],
                "description": item["description"],
            }
            for item in top
        ]
    return {"scores": normalize(raw), "topics": topics}


def blend(signals):
    active = [signal for signal in signals if signal.get("data")]
    total = sum(signal["weight"] for signal in active) or 1
    scores = blank_raw()
    for signal in active:
        for pillar in PILLARS:
            scores[pillar] += signal["data"]["scores"].get(pillar, 0) * (signal["weight"] / total)
    return {pillar: round(value) for pillar, value in scores.items()}


def merge_topics(*topic_sets):
    merged = empty_topics()
    for topic_set in topic_sets:
        if not topic_set:
            continue
        for pillar in PILLARS:
            merged[pillar].extend(topic_set.get(pillar, []))
            merged[pillar] = merged[pillar][:5]
    return merged


def wikipedia_url(title):
    return f"https://en.wikipedia.org/wiki/{str(title or '').replace(' ', '_')}"


def normalize_topic(topic, fallback_source=""):
    item = dict(topic or {})
    name = item.get("name", "Untitled topic")
    source = item.get("source") or fallback_source
    item["name"] = name
    item["source"] = source
    item.setdefault("heat", "")
    if source == "Wikipedia":
        item.setdefault("url", wikipedia_url(name))
        item.setdefault("description", f"High Wikipedia pageview attention for {name}.")
        item.setdefault("signalType", "Public curiosity")
        item.setdefault("sourceDetail", "Wikipedia Pageviews measures article visits during the selected window.")
        item.setdefault("why", f"Ranked because {name} drew elevated Wikipedia pageview attention in this pillar.")
    else:
        item.setdefault("url", "")
        item.setdefault("description", f"Trending item from {source or 'the historical signal set'}.")
        item.setdefault("signalType", "News coverage")
        item.setdefault("sourceDetail", f"Coverage signal from {source or 'the historical signal set'}.")
        item.setdefault("why", f"Ranked because {name} appeared in the matched historical signal set for this pillar.")
    item.setdefault("keywords", [])
    return item


def normalize_result(result):
    if not isinstance(result, dict):
        return result
    fallback_source = result.get("source", "")
    topics = result.get("topics") or {}
    normalized = {}
    for pillar in PILLARS:
        normalized[pillar] = [
            normalize_topic(topic, fallback_source)
            for topic in topics.get(pillar, [])
        ]
    result["topics"] = normalized
    source_breakdown = result.get("sourceBreakdown") or {}
    normalized_breakdown = {}
    for key, source_result in source_breakdown.items():
        if not isinstance(source_result, dict):
            continue
        source_topics = source_result.get("topics") or {}
        normalized_breakdown[key] = {
            **source_result,
            "topics": {
                pillar: [
                    normalize_topic(topic, source_result.get("label") or source_result.get("source") or fallback_source)
                    for topic in source_topics.get(pillar, [])
                ]
                for pillar in PILLARS
            },
        }
    if normalized_breakdown:
        result["sourceBreakdown"] = normalized_breakdown
    return result


def load_analysis_cache():
    try:
        with open(ANALYSIS_CACHE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_analysis_cache(cache):
    tmp = f"{ANALYSIS_CACHE_FILE}.tmp"
    with open(tmp, "w") as f:
        json.dump(cache, f)
    os.replace(tmp, ANALYSIS_CACHE_FILE)


def compact_topics_for_analysis(topics):
    compact = {}
    topics = topics or {}
    for pillar in PILLARS:
        compact[pillar] = []
        for item in topics.get(pillar, [])[:4]:
            compact[pillar].append({
                "name": str(item.get("name", ""))[:120],
                "heat": str(item.get("heat", ""))[:80],
                "source": str(item.get("source", ""))[:80],
                "description": str(item.get("description", ""))[:220],
            })
    return compact


def compact_analysis_payload(payload):
    payload = payload or {}
    scores = payload.get("scores") or {}
    compact_scores = {
        pillar: int(round(float(scores.get(pillar, 0) or 0)))
        for pillar in PILLARS
    }
    return {
        "mode": str(payload.get("mode") or "historical")[:30],
        "source": str(payload.get("source") or "Unknown")[:160],
        "window": payload.get("window") if isinstance(payload.get("window"), dict) else None,
        "scores": compact_scores,
        "topics": compact_topics_for_analysis(payload.get("topics")),
        "warnings": [str(warning)[:220] for warning in (payload.get("warnings") or [])[:5]],
    }


def analysis_cache_key(payload):
    stable = {
        "model": OLLAMA_MODEL,
        "payload": compact_analysis_payload(payload),
    }
    encoded = json.dumps(stable, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def top_analysis_pillars(payload, limit=3):
    scores = payload.get("scores") or {}
    return sorted(PILLARS, key=lambda pillar: scores.get(pillar, 0), reverse=True)[:limit]


def fallback_analysis(payload, reason="Ollama is not available right now"):
    compact = compact_analysis_payload(payload)
    top_pillars = top_analysis_pillars(compact)
    first = top_pillars[0] if top_pillars else "the dashboard"
    source = compact.get("source") or "the loaded data"
    summary = (
        f"{first} is the strongest visible signal in this view. "
        f"The readout is based on {source}, using the scores and topic lists already loaded in the dashboard."
    )
    bullets = []
    for pillar in top_pillars:
        topic_names = [
            topic["name"]
            for topic in compact["topics"].get(pillar, [])
            if topic.get("name")
        ][:3]
        topic_text = ", ".join(topic_names) if topic_names else "no specific topics listed"
        bullets.append(f"{pillar} scored {compact['scores'].get(pillar, 0)} with drivers including {topic_text}.")
    caveats = compact.get("warnings") or []
    if reason:
        caveats = [reason, *caveats]
    return {
        "headline": f"{first} is leading the cultural mix",
        "summary": summary,
        "bullets": bullets[:4],
        "caveats": caveats[:3],
        "provider": "template",
        "model": "fallback",
    }


def build_analysis_prompt(payload):
    compact = compact_analysis_payload(payload)
    return f"""
You are a strategic analyst for a cultural trend dashboard used by brand marketers.

Use only the provided dashboard data. Do not invent facts, dates, links, or outside context.
If any source is missing or a warning exists, mention it clearly in caveats.

Your job is to:
- Explain what is trending in a way that is useful for brand strategy.
- Highlight why each trend matters for audience attention, relevance, and campaign timing.
- Call out brand implications such as sponsorship opportunities, message fit, and audience segments when supported by the data.
- When the selected window is in March 2026 or the data shows sports-related topics, explicitly look for women's sports signals and explain why they may matter for brands.
- Prefer clear, specific, practical language over generic commentary.

Return valid JSON only, with this exact shape:
{{
  "headline": "short, punchy headline",
  "summary": "2-3 short sentences that explain the trend story and brand relevance",
  "bullets": ["4-5 concise takeaways, each with a strategic brand lens"],
  "caveats": ["0-2 caveats about missing/limited data"]
}}

Dashboard data:
{json.dumps(compact, indent=2)}
""".strip()


def parse_ollama_json(text):
    text = (text or "").strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return json.loads(text[start:end + 1])
    raise ValueError("Ollama did not return JSON")


def sanitize_analysis(analysis):
    analysis = analysis or {}
    headline = str(analysis.get("headline") or "Cultural pulse readout").strip()[:140]
    summary = str(analysis.get("summary") or "").strip()[:900]
    bullets = analysis.get("bullets") if isinstance(analysis.get("bullets"), list) else []
    caveats = analysis.get("caveats") if isinstance(analysis.get("caveats"), list) else []
    return {
        "headline": headline,
        "summary": summary,
        "bullets": [str(item).strip()[:320] for item in bullets if str(item).strip()][:5],
        "caveats": [str(item).strip()[:240] for item in caveats if str(item).strip()][:3],
        "provider": analysis.get("provider") or "ollama",
        "model": analysis.get("model") or OLLAMA_MODEL,
    }


def ollama_analysis(payload):
    prompt = build_analysis_prompt(payload)
    body = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_predict": 650,
        },
    }).encode("utf-8")
    request = Request(
        f"{OLLAMA_BASE_URL}/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=OLLAMA_TIMEOUT_SECONDS) as response:
        data = json.loads(response.read().decode("utf-8"))
    analysis = parse_ollama_json(data.get("response", ""))
    analysis["provider"] = "ollama"
    analysis["model"] = OLLAMA_MODEL
    return sanitize_analysis(analysis)


def analyze_pulse(payload):
    cache_key = analysis_cache_key(payload)
    cache = load_analysis_cache()
    cached = cache.get(cache_key)
    if cached:
        cached["cached"] = True
        return cached

    try:
        result = ollama_analysis(payload)
    except Exception as exc:
        result = fallback_analysis(payload, f"Ollama unavailable: {exc}")
    result["cached"] = False
    if result.get("provider") == "ollama":
        cache[cache_key] = result
        save_analysis_cache(cache)
    return result


def load_cache():
    try:
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_cache(cache):
    tmp = f"{CACHE_FILE}.tmp"
    with open(tmp, "w") as f:
        json.dump(cache, f)
    os.replace(tmp, CACHE_FILE)


def load_live_cache():
    try:
        with open(LIVE_CACHE_FILE, "r") as f:
            cached = json.load(f)
        cached["fetched_at"] = datetime.fromisoformat(cached["fetched_at"]).astimezone(UTC)
        return cached
    except Exception:
        return None


def save_live_cache(cache):
    payload = {
        "fetched_at": cache["fetched_at"].isoformat(),
        "result": cache["result"],
    }
    tmp = f"{LIVE_CACHE_FILE}.tmp"
    with open(tmp, "w") as f:
        json.dump(payload, f)
    os.replace(tmp, LIVE_CACHE_FILE)


def probe_wiki_available(date_str):
    url = f"{WIKI_TOP_BASE}/{datetime.strptime(date_str, '%Y-%m-%d'):%Y/%m/%d}"
    try:
        data = read_json_url(url)
        return bool(data.get("items"))
    except Exception:
        return False


def latest_available_historical_date():
    global RANGE_CACHE
    if RANGE_CACHE:
        return RANGE_CACHE

    latest = date.today() - timedelta(days=1)
    earliest = date.today() - timedelta(days=365)
    cache_dates = []
    for key in load_cache():
        parts = key.split(":")
        for part in parts:
            try:
                cache_dates.append(parse_iso_date(part))
            except Exception:
                pass
    if cache_dates:
        earliest = min(earliest, min(cache_dates))
        latest = max(cache_dates)
        RANGE_CACHE = {"earliest": earliest.isoformat(), "latest": latest.isoformat()}
        return RANGE_CACHE

    cursor = latest
    while cursor >= earliest:
        try:
            wiki_signal(cursor.isoformat())
            RANGE_CACHE = {"earliest": earliest.isoformat(), "latest": cursor.isoformat()}
            return RANGE_CACHE
        except Exception:
            pass
        cursor -= timedelta(days=1)

    RANGE_CACHE = {"earliest": earliest.isoformat(), "latest": earliest.isoformat()}
    return RANGE_CACHE


def resolve_historical_window(window, date_str, start_date, end_date):
    range_info = latest_available_historical_date()
    earliest = parse_iso_date(range_info["earliest"])
    latest = parse_iso_date(range_info["latest"])
    window = window or "day"

    if window == "custom":
        if not start_date or not end_date:
            raise ValueError("Custom range requires start and end dates")
        start = parse_iso_date(start_date)
        end = parse_iso_date(end_date)
    elif window == "week":
        end = latest
        start = end - timedelta(days=end.weekday())
    elif window == "month":
        end = latest
        start = end.replace(day=1)
    else:
        end = parse_iso_date(date_str or latest.isoformat())
        start = end

    if start < earliest:
        start = earliest
    if end > latest:
        end = latest
    if start > end:
        raise ValueError(f"Historical start date must be on or before end date")
    if start < earliest or end > latest:
        raise ValueError(f"Historical date must be between {earliest.isoformat()} and {latest.isoformat()}")

    label = start.isoformat() if start == end else f"{start.isoformat()} to {end.isoformat()}"
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "label": label,
        "window": window,
        "earliest": earliest.isoformat(),
        "latest": latest.isoformat(),
    }


def pulse(mode, date_str, window="day", start_date=None, end_date=None):
    global LIVE_CACHE
    window_info = None
    cache_key = None
    cache = load_cache() if mode == "historical" else None
    if mode == "historical":
        window_info = resolve_historical_window(window, date_str, start_date, end_date)
        cache_key = f"{window_info['start']}:{window_info['end']}:sources=wiki-trends-v3"
        if cache is not None and cache_key in cache:
            cached = cache[cache_key]
            if not any("unavailable" in warning.lower() for warning in cached.get("warnings", [])):
                return normalize_result(cached)

    warnings = []

    if mode == "live":
        now = datetime.now(UTC)
        if LIVE_CACHE is None:
            LIVE_CACHE = load_live_cache()
        if LIVE_CACHE and (now - LIVE_CACHE["fetched_at"]).total_seconds() < LIVE_CACHE_TTL_SECONDS:
            return LIVE_CACHE["result"]
        try:
            yt = youtube_signal()
        except Exception as exc:
            warnings.append(f"YouTube unavailable: {exc}")
            yt = None
        if not yt and LIVE_CACHE and (now - LIVE_CACHE["fetched_at"]).total_seconds() < LIVE_STALE_CACHE_SECONDS:
            cached = dict(LIVE_CACHE["result"])
            cached["warnings"] = [*cached.get("warnings", []), *warnings, "Using last successful YouTube refresh"]
            return cached
        if not yt:
            raise RuntimeError("; ".join(warnings) or "YouTube live data unavailable")
        scores = yt["scores"]
        topics = yt["topics"]
        source = "YouTube"
        source_breakdown = {
            "youtube": {
                "label": "YouTube",
                "scores": yt["scores"],
                "topics": yt["topics"],
            }
        }
    else:
        try:
            wiki = wiki_signal(window_info["start"], window_info["end"])
        except Exception as exc:
            warnings.append(f"Wikipedia unavailable: {exc}")
            wiki = None
        try:
            trends = google_trends_signal(window_info["start"], window_info["end"])
        except Exception as exc:
            warnings.append(f"Google Trends unavailable: {exc}")
            trends = None
        if not wiki and not trends:
            raise RuntimeError("; ".join(warnings) or "Historical data unavailable")
        scores = blend([
            {"data": trends, "weight": 60},
            {"data": wiki, "weight": 40},
        ])
        topics = merge_topics(
            trends["topics"] if trends else None,
            wiki["topics"] if wiki else None,
        )
        source = " + ".join([
            name for name, data in [
                ("Google Trends", trends),
                ("Wikipedia", wiki),
        ]
    if data
])
        source_breakdown = {}
        if trends:
            source_breakdown["googleTrends"] = {
                "label": "Google Trends",
                "scores": trends["scores"],
                "topics": trends["topics"],
            }
        if wiki:
            source_breakdown["wikipedia"] = {
                "label": "Wikipedia",
                "scores": wiki["scores"],
                "topics": wiki["topics"],
            }

    result = {
        "scores": scores,
        "topics": topics,
        "source": source,
        "sourceBreakdown": source_breakdown,
        "warnings": warnings,
        "window": window_info,
    }

    if cache is not None and not any("unavailable" in warning.lower() for warning in warnings):
        cache[cache_key] = result
        save_cache(cache)
    elif mode == "live":
        LIVE_CACHE = {"fetched_at": datetime.now(UTC), "result": result}
        save_live_cache(LIVE_CACHE)

    return normalize_result(result)


class Handler(SimpleHTTPRequestHandler):
    def send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/range":
            try:
                self.send_json(200, latest_available_historical_date())
            except Exception as exc:
                self.send_json(500, {"error": str(exc)})
            return
        if parsed.path != "/api/pulse":
            return super().do_GET()
        try:
            qs = parse_qs(parsed.query)
            mode = qs.get("mode", ["live"])[0]
            date_str = qs.get("date", [date.today().isoformat()])[0]
            window = qs.get("window", ["day"])[0]
            start_date = qs.get("start", [None])[0]
            end_date = qs.get("end", [None])[0]
            self.send_json(200, pulse(mode, date_str, window, start_date, end_date))
        except Exception as exc:
            self.send_json(500, {"error": str(exc)})

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/analysis":
            self.send_json(404, {"error": "Not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 1_000_000:
                self.send_json(413, {"error": "Analysis payload is too large"})
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            self.send_json(200, analyze_pulse(payload))
        except Exception as exc:
            self.send_json(500, {"error": str(exc)})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "4174"))
    print(f"Serving Cultural Pulse at http://127.0.0.1:{port}/")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
