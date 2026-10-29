from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from regwatch.models import Source
from regwatch.paths import DEFAULT_CONFIG_DIR

REQUIRED_SOURCE_FIELDS = (
    "id",
    "name",
    "jurisdiction",
    "category",
    "type",
    "url",
)

SUPPORTED_SOURCE_TYPES = {"page", "html", "rss", "json"}


class ConfigError(ValueError):
    """Raised when configuration is missing or invalid."""


class ConfigLoader:
    """Loads and validates the YAML configuration files.

    Paths are resolved relative to ``config_dir`` (not the current working
    directory), so the tool can be started from anywhere.
    """

    def __init__(self, config_dir: Optional[str] = None):
        self.config_dir = (
            Path(config_dir).expanduser().resolve()
            if config_dir
            else DEFAULT_CONFIG_DIR
        )

    def load_yaml(self, name: str) -> Dict[str, Any]:
        path = self.config_dir / name

        if not path.exists():
            raise ConfigError(f"Missing configuration file: {path}")

        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle)
        except yaml.YAMLError as exc:
            raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc

        if not isinstance(data, dict):
            raise ConfigError(f"Expected a mapping at the top level of {path}")

        return data

    def load_settings(self) -> Dict[str, Any]:
        settings = self.load_yaml("settings.yaml")

        for section in (
            "database",
            "crawler",
            "monitoring",
        ):
            if not isinstance(settings.get(section), dict):
                raise ConfigError(
                    f"settings.yaml: missing '{section}' section"
                )

        if not settings["database"].get("path"):
            raise ConfigError("settings.yaml: database.path is required")

        settings.setdefault("logging", {})
        settings.setdefault("storage", {})
        settings.setdefault("reporting", {})
        settings.setdefault("scoring", {})
        settings.setdefault("severity", {})

        return settings

    def load_sources(self) -> List[Source]:
        config = self.load_yaml("sources.yaml")

        raw_sources = config.get("sources")

        if not isinstance(raw_sources, list):
            raise ConfigError("sources.yaml: missing 'sources' list")

        sources: List[Source] = []
        seen_ids = set()

        for index, raw in enumerate(raw_sources):
            if not isinstance(raw, dict):
                raise ConfigError(
                    f"sources.yaml: source #{index} is not a mapping"
                )

            missing = [
                field
                for field in REQUIRED_SOURCE_FIELDS
                if not raw.get(field)
            ]

            if missing:
                label = raw.get("id") or f"#{index}"
                raise ConfigError(
                    f"sources.yaml: source {label} is missing "
                    f"{', '.join(missing)}"
                )

            source_type = str(raw["type"]).lower()

            if source_type not in SUPPORTED_SOURCE_TYPES:
                raise ConfigError(
                    f"sources.yaml: source {raw['id']} has unsupported "
                    f"type '{raw['type']}' "
                    f"(expected one of {sorted(SUPPORTED_SOURCE_TYPES)})"
                )

            source_id = str(raw["id"])

            if source_id in seen_ids:
                raise ConfigError(
                    f"sources.yaml: duplicate source id '{source_id}'"
                )

            seen_ids.add(source_id)

            sources.append(
                Source(
                    id=source_id,
                    name=str(raw["name"]),
                    jurisdiction=str(raw["jurisdiction"]),
                    category=str(raw["category"]),
                    type=source_type,
                    url=str(raw["url"]),
                    state=(
                        str(raw["state"])
                        if raw.get("state") is not None
                        else None
                    ),
                    enabled=bool(raw.get("enabled", True)),
                )
            )

        return sources

    def load_taxonomy(self) -> Dict[str, Any]:
        taxonomy = self.load_yaml("taxonomy.yaml")

        if not isinstance(taxonomy.get("domains"), dict):
            raise ConfigError("taxonomy.yaml: missing 'domains' mapping")

        if not isinstance(taxonomy.get("action_types"), dict):
            raise ConfigError("taxonomy.yaml: missing 'action_types' mapping")

        return taxonomy

    def load_runtime_options(self) -> Dict[str, Any]:
        """Options that live in sources.yaml next to the source list."""

        config = self.load_yaml("sources.yaml")

        return {
            "request_delay_s": float(config.get("request_delay_s", 0.0)),
            "default_tracking": config.get("default_tracking") or {},
        }
