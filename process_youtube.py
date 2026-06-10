#!/usr/bin/env python3
"""
process_youtube.py — Cultural Pulse Historical Data Processor
=============================================================
Takes the Kaggle YouTube US Trending dataset CSV and outputs
historical_data.json with daily 0–100 scores per pillar.

Dataset: https://www.kaggle.com/datasets/rsrishav/youtube-trending-video-dataset
Download the US file: US_youtube_trending_data.csv (~200MB)

Usage:
  pip install pandas
  python3 process_youtube.py --input US_youtube_trending_data.csv --output historical_data.json

Output format:
  {
    "2024-03-15": {
      "Politics": 72,
      "Sports": 85,
      "Entertainment": 64,
      "Sci & Tech": 48,
      "Business": 37,
      "Lifestyle": 56
    },
    ...
  }
"""

import argparse
import json
import sys
import pandas as pd
from datetime import datetime

# ── YouTube category ID → pillar mapping ──────────────────────────────────────
# Full list: https://developers.google.com/youtube/v3/docs/videoCategories/list
CATEGORY_MAP = {
    # Politics & Civic Life
    25: "Politics",   # News & Politics

    # Sports
    17: "Sports",     # Sports

    # Entertainment & Pop Culture
    24: "Entertainment",  # Entertainment
    10: "Entertainment",  # Music
    23: "Entertainment",  # Comedy
     1: "Entertainment",  # Film & Animation
    43: "Entertainment",  # Shows

    # Science & Technology
    28: "Sci & Tech",   # Science & Technology
    20: "Entertainment",   # Gaming (tech-adjacent)

    # Business & Finance — no dedicated YT category, filter by keyword
    # (handled separately below)

    # Lifestyle & Wellness
    26: "Lifestyle",  # Howto & Style
    22: "Lifestyle",  # People & Blogs
    19: "Lifestyle",  # Travel & Events
    29: "Lifestyle",  # Nonprofits & Activism (wellness overlap)

    # Catch-all for Education → Sci & Tech
    27: "Sci & Tech",  # Education
}

# Business keywords to reclassify News & Politics videos
BUSINESS_KEYWORDS = [
    "stock", "market", "nasdaq", "dow", "crypto", "bitcoin",
    "inflation", "fed", "federal reserve", "economy", "gdp",
    "earnings", "ipo", "startup", "recession", "finance",
    "wall street", "interest rate", "layoff", "unemployment",
]


def classify_pillar(category_id, title):
    """Map a video to a pillar, with keyword override for Business."""
    title_lower = str(title).lower()

    # Check business keywords first (override News category)
    if any(kw in title_lower for kw in BUSINESS_KEYWORDS):
        return "Business"

    return CATEGORY_MAP.get(int(category_id), None)


def score_video(row):
    """
    Engagement-weighted score for a single video.
    Formula: view_count * (1 + engagement_rate)
    where engagement_rate = (likes + comment_count) / max(view_count, 1)
    """
    views    = max(int(row.get("view_count", 0) or 0), 1)
    likes    = int(row.get("likes", 0) or 0)
    comments = int(row.get("comment_count", 0) or 0)
    engagement = (likes + comments) / views
    return views * (1 + engagement)


def normalize(series):
    """Min-max normalize a pandas Series to 0–100."""
    mn, mx = series.min(), series.max()
    if mx == mn:
        return series.map(lambda _: 50.0)
    return ((series - mn) / (mx - mn) * 100).round(1)


def process(input_path, output_path):
    print(f"📂 Loading {input_path}...")
    try:
        df = pd.read_csv(
            input_path,
            usecols=["trending_date", "categoryId", "view_count", "likes", "comment_count", "title"],
            on_bad_lines="skip",
            low_memory=False,
            encoding="utf-8",
            encoding_errors="replace"
        )
    except FileNotFoundError:
        print(f"❌  File not found: {input_path}")
        print("    Download from: https://www.kaggle.com/datasets/rsrishav/youtube-trending-video-dataset")
        sys.exit(1)

    print(f"   Loaded {len(df):,} rows.")

    # ── Parse date ────────────────────────────────────────────────────────────
    # Kaggle column may be 'trending_date' in various formats
    date_col = None
    for col in ["trending_date", "publishedAt", "publish_time"]:
        if col in df.columns:
            date_col = col
            break

    if date_col is None:
        print("❌  Could not find a date column. Columns found:", list(df.columns))
        sys.exit(1)

    # Parse date column as timezone-naive datetime objects
    df["parsed_date"] = pd.to_datetime(df[date_col], errors="coerce").dt.tz_localize(None)
    df = df.dropna(subset=["parsed_date"])

    if len(df) == 0:
        print("❌  No valid dates found in dataset.")
        sys.exit(1)

    # Shifting the dataset timeline so it lines up with the requested date range:
    # 1 year of data ending on June 17th, 2026 (backwards to June 17th, 2025).
    max_csv_date = df["parsed_date"].max()
    target_max_date = pd.to_datetime("2026-06-17")
    delta = target_max_date - max_csv_date
    print(f"🔄 Shifting dataset dates by {delta.days} days to align with presentation year (max date: {max_csv_date.strftime('%Y-%m-%d')} -> 2026-06-17)...")

    df["parsed_date"] = df["parsed_date"] + delta
    df["date"] = df["parsed_date"].dt.strftime("%Y-%m-%d")

    # Filter to one year of data ending on June 17th, 2026 (backwards to June 17th, 2025)
    df = df[(df["date"] >= "2025-06-17") & (df["date"] <= "2026-06-17")]

    if len(df) == 0:
        print("❌  No data left after date filtering.")
        sys.exit(1)

    # ── Classify pillars ──────────────────────────────────────────────────────
    print("🗂  Classifying videos into pillars...")
    df["pillar"] = df.apply(
        lambda r: classify_pillar(r.get("categoryId", r.get("category_id", 0)), r.get("title", "")),
        axis=1
    )
    df = df.dropna(subset=["pillar"])

    # ── Compute per-video score ───────────────────────────────────────────────
    df["raw_score"] = df.apply(score_video, axis=1)

    # ── Aggregate: sum raw scores per date+pillar ─────────────────────────────
    print("📊 Aggregating daily scores...")
    daily = (
        df.groupby(["date", "pillar"])["raw_score"]
        .sum()
        .reset_index()
    )

    # ── Normalize per date ────────────────────────────────────────────────────
    # Normalize so the highest pillar on each day = 100, lowest = 0
    results = {}
    for date, group in daily.groupby("date"):
        scores = group.set_index("pillar")["raw_score"]
        normed = normalize(scores)
        results[date] = normed.to_dict()

    # Ensure all dates have all 6 pillars (fill missing with 0)
    all_pillars = ["Politics", "Sports", "Entertainment", "Sci & Tech", "Business", "Lifestyle"]
    for date in results:
        for p in all_pillars:
            if p not in results[date]:
                results[date][p] = 0.0

    # Sort chronologically
    results = dict(sorted(results.items()))

    # ── Also build top-5 topics per pillar per date ───────────────────────────
    print("🔥 Extracting top topics per day...")
    top_topics = {}
    for date, group in df.groupby("date"):
        top_topics[date] = {}
        for pillar in all_pillars:
            pillar_vids = group[group["pillar"] == pillar].nlargest(5, "raw_score")
            top_topics[date][pillar] = pillar_vids["title"].tolist()

    output = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "scores": results,
        "topics": top_topics,
    }

    print(f"💾 Writing {output_path}...")
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    date_count = len(results)
    print(f"\n✅  Done! {date_count} days of data written to {output_path}")
    print(f"   Date range: {min(results.keys())} → {max(results.keys())}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process YouTube trending data for Cultural Pulse")
    parser.add_argument("--input",  default="US_youtube_trending_data.csv", help="Path to Kaggle CSV")
    parser.add_argument("--output", default="historical_data.json",         help="Output JSON path")
    args = parser.parse_args()
    process(args.input, args.output)
