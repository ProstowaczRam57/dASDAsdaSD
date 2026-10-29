"""Allow ``python -m sad`` from the repository root."""

import sys
from pathlib import Path

# ``regwatch`` lives inside this directory, which is not on sys.path when the
# repository root is the working directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from regwatch.main import main  # noqa: E402

raise SystemExit(main())
