"""
Download WaveFake dataset (free research dataset for voice cloning detection).

WaveFake: Detecting Voice Spoofing Attacks using Biometric Audio
https://github.com/interactiveaudiolab/WaveFake

Size: ~1GB
License: CC BY-NC-SA 4.0 (free for research)
"""

import os
import subprocess
from pathlib import Path
import urllib.request

DATASET_DIR = Path("/data/datasets/wavefake")
DATASET_DIR.mkdir(exist_ok=True, parents=True)

repo_url = "https://github.com/interactiveaudiolab/WaveFake.git"

print("Downloading WaveFake dataset...")
print("Note: This is a large dataset (~1GB)")
print("")

# Clone the repo with just the dataset
try:
    subprocess.run(
        ["git", "clone", "--depth", "1", repo_url, str(DATASET_DIR)],
        check=True,
        capture_output=True
    )
    print("✅ WaveFake dataset downloaded")
except Exception as e:
    print(f"⚠️  Could not auto-download: {e}")
    print("Manual download instructions:")
    print("1. Visit: https://github.com/interactiveaudiolab/WaveFake")
    print("2. Download release")
    print("3. Extract to: /data/datasets/wavefake/")