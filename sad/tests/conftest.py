import sys
from pathlib import Path

# Make the ``regwatch`` package importable when pytest runs from the repo root.
SAD_DIR = Path(__file__).resolve().parents[1]

if str(SAD_DIR) not in sys.path:
    sys.path.insert(0, str(SAD_DIR))
