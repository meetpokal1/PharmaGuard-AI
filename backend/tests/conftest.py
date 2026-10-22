import sys
from pathlib import Path

# Ensure backend/app is always on sys.path for test collection across all platforms
app_dir = str(Path(__file__).resolve().parents[1] / "app")
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)
