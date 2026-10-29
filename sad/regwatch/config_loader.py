from pathlib import Path
import yaml


class ConfigLoader:

    @staticmethod
    def load_yaml(path: str) -> dict:

        path_obj = Path(path)

        if not path_obj.exists():
            raise FileNotFoundError(
                f"Missing configuration file: {path}"
            )

        with open(path_obj, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    @staticmethod
    def load_settings() -> dict:
        return ConfigLoader.load_yaml(
            "config/settings.yaml"
        )

    @staticmethod
    def load_sources() -> dict:
        return ConfigLoader.load_yaml(
            "config/sources.yaml"
        )

    @staticmethod
    def load_taxonomy() -> dict:
        return ConfigLoader.load_yaml(
            "config/taxonomy.yaml"
        )