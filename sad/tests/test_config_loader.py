import pytest
import yaml
from regwatch.config_loader import ConfigError, ConfigLoader


def test_loads_shipped_configuration():
    loader = ConfigLoader()
    settings = loader.load_settings()
    sources = loader.load_sources()
    taxonomy = loader.load_taxonomy()

    assert settings["database"]["path"]
    assert sources
    assert all(source.id for source in sources)
    assert taxonomy["domains"]


def test_missing_file_raises(tmp_path):
    loader = ConfigLoader(str(tmp_path))

    with pytest.raises(ConfigError, match="Missing configuration file"):
        loader.load_settings()


def test_invalid_yaml_raises(tmp_path):
    (tmp_path / "settings.yaml").write_text("a: [unclosed", encoding="utf-8")

    with pytest.raises(ConfigError, match="Invalid YAML"):
        ConfigLoader(str(tmp_path)).load_settings()


def test_missing_required_source_field_raises(tmp_path):
    _write_sources(
        tmp_path,
        [
            {
                "id": "x",
                "name": "X",
                "jurisdiction": "US",
                "category": "environment",
                "type": "page",
            }
        ],
    )

    with pytest.raises(ConfigError, match="missing url"):
        ConfigLoader(str(tmp_path)).load_sources()


def test_duplicate_source_id_raises(tmp_path):
    source = {
        "id": "duplicate",
        "name": "X",
        "jurisdiction": "US",
        "category": "environment",
        "type": "page",
        "url": "https://example.gov/",
    }
    _write_sources(tmp_path, [source, dict(source)])

    with pytest.raises(ConfigError, match="duplicate source id"):
        ConfigLoader(str(tmp_path)).load_sources()


def test_unsupported_source_type_raises(tmp_path):
    _write_sources(
        tmp_path,
        [
            {
                "id": "x",
                "name": "X",
                "jurisdiction": "US",
                "category": "environment",
                "type": "carrier-pigeon",
                "url": "https://example.gov/",
            }
        ],
    )

    with pytest.raises(ConfigError, match="unsupported type"):
        ConfigLoader(str(tmp_path)).load_sources()


def _write_sources(tmp_path, sources):
    (tmp_path / "sources.yaml").write_text(
        yaml.safe_dump({"sources": sources}),
        encoding="utf-8",
    )
