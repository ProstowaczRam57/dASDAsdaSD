from pathlib import Path

# Repository layout: <root>/sad/regwatch/paths.py
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_DIR = PROJECT_ROOT / "config"


def resolve_path(value: str, base: Path = PROJECT_ROOT) -> Path:
    """Resolve a config path, keeping absolute paths untouched."""

    path = Path(value).expanduser()

    if path.is_absolute():
        return path

    return (base / path).resolve()
