"""User configuration loaded from a TOML file."""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_EXAMPLE_CONFIG = _PROJECT_ROOT / "config.example.toml"

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "bookfinder" / "config.toml"


@dataclass
class SiteConfig:
    name: str
    base_url: str
    search_url_template: str


@dataclass
class Config:
    currency: str = "USD"
    max_results: int = 10
    custom_sites: list[SiteConfig] = field(default_factory=list)


def load_config(path: Path | None = None) -> Config:
    """Load config from TOML file, falling back to defaults."""
    path = path or DEFAULT_CONFIG_PATH

    if not path.exists():
        return Config()

    with open(path, "rb") as f:
        data = tomllib.load(f)

    custom_sites = [
        SiteConfig(
            name=site["name"],
            base_url=site["base_url"],
            search_url_template=site["search_url_template"],
        )
        for site in data.get("sites", [])
    ]

    return Config(
        currency=data.get("currency", "USD"),
        max_results=data.get("max_results", 10),
        custom_sites=custom_sites,
    )


def write_default_config(path: Path | None = None, force: bool = False) -> Path:
    """Write a default config file if missing.

    Args:
        path: Optional path to write the config.
        force: Overwrite existing file if True.

    Returns:
        Path to the written (or existing) config file.
    """
    path = path or DEFAULT_CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists() and not force:
        return path

    if _EXAMPLE_CONFIG.exists():
        content = _EXAMPLE_CONFIG.read_text(encoding="utf-8")
    else:
        content = "# BookPriceFinder configuration\n"

    path.write_text(content, encoding="utf-8")
    return path
