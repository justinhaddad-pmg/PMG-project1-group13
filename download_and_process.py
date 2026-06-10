import os
import shutil
import tempfile
import zipfile
import sys

from env import load_env

if not load_env():
    print("❌  No .env file found. Copy .env.example to .env and add your credentials.")
    sys.exit(1)

username = os.environ.get("KAGGLE_USERNAME", "").strip()
api_key = os.environ.get("KAGGLE_KEY", "").strip()
if not username or not api_key:
    print("❌  Missing KAGGLE_USERNAME or KAGGLE_KEY in .env")
    sys.exit(1)

try:
    import kaggle
except ImportError:
    print("❌  kaggle package not found. Install it with: pip3 install kaggle")
    sys.exit(1)

print("🔑 Authenticating with Kaggle API...")
kaggle.api.authenticate()

print("📥 Downloading US_youtube_trending_data.csv from Kaggle (~200MB)...")
try:
    kaggle.api.dataset_download_file(
        dataset='rsrishav/youtube-trending-video-dataset',
        file_name='US_youtube_trending_data.csv',
        path='.'
    )
except Exception as e:
    print(f"❌  Failed to download file from Kaggle: {e}")
    sys.exit(1)

CSV_PATH = "US_youtube_trending_data.csv"


def ensure_csv_extracted(path):
    """Kaggle sometimes saves a zip as .csv or as .csv.zip — extract if needed."""
    for candidate in (path, f"{path}.zip"):
        if not os.path.exists(candidate):
            continue
        with open(candidate, "rb") as f:
            is_zip = f.read(2) == b"PK"
        if not is_zip:
            if candidate == path:
                print(f"✅  {path} downloaded directly.")
            return path

        print(f"📦 Extracting {candidate}...")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                with zipfile.ZipFile(candidate, "r") as zip_ref:
                    members = zip_ref.namelist()
                    zip_ref.extractall(tmp)
                extracted = os.path.join(tmp, os.path.basename(path))
                if not os.path.exists(extracted):
                    extracted = os.path.join(tmp, members[0])
                shutil.move(extracted, path)
            if candidate != path:
                os.remove(candidate)
            print("✅  Extraction complete.")
            return path
        except Exception as e:
            print(f"❌  Failed to extract zip file: {e}")
            sys.exit(1)

    print(f"❌  Could not find {path} after download.")
    sys.exit(1)


ensure_csv_extracted(CSV_PATH)

# Process the data
print("📊 Processing data into historical_data.json...")
try:
    import process_youtube
    process_youtube.process(CSV_PATH, "historical_data.json")
except Exception as e:
    print(f"❌  Failed during processing: {e}")
    sys.exit(1)
