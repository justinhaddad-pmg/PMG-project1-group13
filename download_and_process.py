import os
import zipfile
import sys

# Set Kaggle credentials
os.environ['KAGGLE_USERNAME'] = "justinhaddad"
os.environ['KAGGLE_KEY'] = "KGAT_8e7a3b3a73fda9c8d824b3fbc3e0aefe"

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

# Unzip if downloaded as a zip
zip_path = 'US_youtube_trending_data.csv.zip'
if os.path.exists(zip_path):
    print("📦 Extracting dataset...")
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall('.')
        os.remove(zip_path)
        print("✅  Extraction complete.")
    except Exception as e:
        print(f"❌  Failed to extract zip file: {e}")
        sys.exit(1)
else:
    print("✅  US_youtube_trending_data.csv downloaded directly.")

# Process the data
print("📊 Processing data into historical_data.json...")
try:
    import process_youtube
    process_youtube.process('US_youtube_trending_data.csv', 'historical_data.json')
except Exception as e:
    print(f"❌  Failed during processing: {e}")
    sys.exit(1)
