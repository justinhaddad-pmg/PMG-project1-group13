#!/usr/bin/env python3
import json
import math
import os
import re
from datetime import date, datetime, time, timedelta
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlencode, urlparse, parse_qs
from urllib.request import urlopen, Request
from zoneinfo import ZoneInfo

PILLARS = ["Politics", "Sports", "Entertainment", "Sci & Tech", "Business", "Lifestyle"]
GDELT_BASE = "https://api.gdeltproject.org/api/v2/doc/doc"
WIKI_TOP_BASE = "https://wikimedia.org/api/rest_v1/metrics/pageviews/top/en.wikipedia/all-access"
YT_BASE = "https://www.googleapis.com/youtube/v3/videos"
CACHE_FILE = "historical_cache.json"
RANGE_CACHE = None

PILLAR_KEYWORDS = {
    "Politics": ["election", "congress", "senate", "president", "white house", "supreme court", "policy", "vote", "protest", "government", "trump", "biden"],
    "Sports": ["sports", "nfl", "nba", "mlb", "nhl", "soccer", "football", "basketball", "baseball", "olympics", "world cup", "ufc", "game", "finals"],
    "Entertainment": ["movie", "film", "music", "album", "celebrity", "streaming", "netflix", "disney", "actor", "singer", "concert", "meme", "viral"],
    "Sci & Tech": ["technology", "tech", "science", "ai", "artificial intelligence", "nasa", "space", "apple", "google", "microsoft", "tesla", "robot", "startup"],
    "Business": ["market", "stocks", "economy", "inflation", "crypto", "bitcoin", "federal reserve", "earnings", "tariff", "recession", "layoff", "wall street"],
    "Lifestyle": ["health", "wellness", "fashion", "travel", "food", "relationship", "fitness", "beauty", "recipe", "wedding", "home", "diet"],
}

UTC = ZoneInfo("UTC")
CENTRAL = ZoneInfo("America/Chicago")

CAT_TO_PILLAR = {
    25: "Politics", 17: "Sports", 24: "Entertainment", 10: "Entertainment",
    23: "Entertainment", 1: "Entertainment", 43: "Entertainment",
    28: "Sci & Tech", 27: "Sci & Tech", 20: "Entertainment",
    26: "Lifestyle", 22: "Lifestyle", 19: "Lifestyle",
}

GDELT_QUERY = " OR ".join(
    f'"{term}"' if " " in term else term
    for term in sorted({term for terms in PILLAR_KEYWORDS.values() for term in terms})
)


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


def yyyymmddhh(date_str, end=False):
    return date_str.replace("-", "") + ("235959" if end else "000000")


def central_day_bounds(date_str):
    local_day = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=CENTRAL)
    start = local_day.astimezone(UTC)
    end = (local_day + timedelta(days=1)).astimezone(UTC)
    return start, end


def iter_utc_date_weights(start_utc, end_utc):
    total = (end_utc - start_utc).total_seconds() or 1
    cursor_date = start_utc.date()
    end_date = end_utc.date()
    while cursor_date <= end_date:
        day_start = datetime.combine(cursor_date, time.min, tzinfo=UTC)
        day_end = day_start + timedelta(days=1)
        overlap_start = max(start_utc, day_start)
        overlap_end = min(end_utc, day_end)
        if overlap_end > overlap_start:
            yield cursor_date, (overlap_end - overlap_start).total_seconds() / total
        cursor_date += timedelta(days=1)


def gdelt_signal(date_str=None):
    params = {
        "query": f"({GDELT_QUERY}) sourcecountry:US",
        "mode": "artlist",
        "format": "json",
        "maxrecords": "250",
        "sort": "datedesc",
    }
    if date_str:
        start_utc, end_utc = central_day_bounds(date_str)
        params["STARTDATETIME"] = start_utc.strftime("%Y%m%d%H%M%S")
        params["ENDDATETIME"] = (end_utc - timedelta(seconds=1)).strftime("%Y%m%d%H%M%S")
    else:
        params["timespan"] = "24h"

    data = read_json_url(f"{GDELT_BASE}?{urlencode(params)}")
    raw, topics = blank_raw(), empty_topics()
    for article in data.get("articles", []):
        title = article.get("title", "")
        pillar = classify(f"{title} {article.get('domain', '')}")
        if not pillar:
            continue
        raw[pillar] += 1
        if len(topics[pillar]) < 5:
            topics[pillar].append({
                "name": title[:60] + ("..." if len(title) > 60 else ""),
                "heat": article.get("domain") or "News",
            })
    return {"scores": normalize(raw), "topics": topics}


def wiki_signal(date_str):
    raw, topics = blank_raw(), empty_topics()
    start_utc, end_utc = central_day_bounds(date_str)
    today_utc = datetime.now(UTC).date()

    for utc_day, weight in iter_utc_date_weights(start_utc, end_utc):
        if utc_day > today_utc:
            continue
        url = f"{WIKI_TOP_BASE}/{utc_day:%Y/%m/%d}"
        data = read_json_url(url)
        for page in data.get("items", [{}])[0].get("articles", []):
            title = page.get("article", "")
            if title == "Main_Page" or title.startswith("Special:"):
                continue
            pillar = classify(title)
            if not pillar:
                continue
            views = page.get("views", 0)
            weighted_views = views * weight
            raw[pillar] += math.log10(weighted_views + 1)
            if len(topics[pillar]) < 5:
                topics[pillar].append({
                    "name": title.replace("_", " "),
                    "heat": f"{round(weighted_views / 1000)}k views",
                })
    return {"scores": normalize(raw), "topics": topics}


def youtube_key():
    if os.environ.get("YOUTUBE_API_KEY"):
        return os.environ["YOUTUBE_API_KEY"].strip()
    try:
        with open("config.local.json") as f:
            return json.load(f).get("youtubeApiKey", "").strip()
    except Exception:
        return ""


def youtube_signal():
    key = youtube_key()
    if not key:
        return None
    raw, topics = blank_raw(), empty_topics()
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
            title = item.get("snippet", {}).get("title", "")
            cat_id = int(item.get("snippet", {}).get("categoryId", 0) or 0)
            stats = item.get("statistics", {})
            views = int(stats.get("viewCount", 0) or 0)
            likes = int(stats.get("likeCount", 0) or 0)
            comments = int(stats.get("commentCount", 0) or 0)
            score = views * (1 + ((likes + comments) / views if views else 0))
            pillar = "Business" if any(k in title.lower() for k in PILLAR_KEYWORDS["Business"]) else CAT_TO_PILLAR.get(cat_id) or classify(title)
            if not pillar:
                continue
            raw[pillar] += score
            topics[pillar].append({"name": title[:60] + ("..." if len(title) > 60 else ""), "heat": "Video"})
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    for pillar in PILLARS:
        topics[pillar] = topics[pillar][:5]
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


def pulse(mode, date_str):
    cache = load_cache() if mode == "historical" else None
    if cache is not None and date_str in cache:
        return cache[date_str]

    warnings = []
    try:
        gdelt = gdelt_signal(None if mode == "live" else date_str)
    except Exception as exc:
        warnings.append(f"GDELT unavailable: {exc}")
        gdelt = None
    try:
        wiki = wiki_signal(date_str)
    except Exception as exc:
        warnings.append(f"Wikipedia unavailable: {exc}")
        wiki = None
    try:
        yt = youtube_signal() if mode == "live" else None
    except Exception as exc:
        warnings.append(f"YouTube unavailable: {exc}")
        yt = None

    if not gdelt and not wiki and not yt:
        raise RuntimeError("; ".join(warnings) or "No data sources available")

    scores = blend([
        {"data": gdelt, "weight": 45 if yt else 60},
        {"data": wiki, "weight": 30 if yt else 40},
        {"data": yt, "weight": 25},
    ])
    result = {
        "scores": scores,
        "topics": merge_topics(
            gdelt["topics"] if gdelt else None,
            wiki["topics"] if wiki else None,
            yt["topics"] if yt else None,
        ),
        "source": " + ".join([
            name for name, data in [("GDELT", gdelt), ("Wikipedia", wiki), ("YouTube", yt)]
            if data
        ]),
        "warnings": warnings,
    }

    if cache is not None:
        cache[date_str] = result
        save_cache(cache)

    return result


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/range":
            try:
                body = json.dumps(latest_available_historical_date()).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
            except Exception as exc:
                body = json.dumps({"error": str(exc)}).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            return
        if parsed.path != "/api/pulse":
            return super().do_GET()
        try:
            qs = parse_qs(parsed.query)
            mode = qs.get("mode", ["live"])[0]
            date_str = qs.get("date", [date.today().isoformat()])[0]
            if mode == "historical":
                range_info = latest_available_historical_date()
                earliest = range_info["earliest"]
                latest = range_info["latest"]
                if date_str < earliest or date_str > latest:
                    raise ValueError(f"Historical date must be between {earliest} and {latest}")
            body = json.dumps(pulse(mode, date_str)).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:
            body = json.dumps({"error": str(exc)}).encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "4174"))
    print(f"Serving Cultural Pulse at http://127.0.0.1:{port}/")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
