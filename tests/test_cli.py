from pathlib import Path

from click.testing import CliRunner

from bookfinder.cli import main
from bookfinder.adapters.base import BaseAdapter
from bookfinder.models import BookQuery


class _Adapter(BaseAdapter):
    def __init__(self, name: str):
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def base_url(self) -> str:
        return "https://example.com"

    async def search(self, query: BookQuery):
        return []


def test_cli_init_writes_config(monkeypatch, tmp_path: Path):
    expected = tmp_path / "config.toml"

    def _fake_write_default_config(path=None, force=False):
        expected.write_text("currency = 'USD'\n", encoding="utf-8")
        return expected

    monkeypatch.setattr("bookfinder.config.write_default_config", _fake_write_default_config)

    runner = CliRunner()
    result = runner.invoke(main, ["init"])

    assert result.exit_code == 0
    assert str(expected) in result.output


def test_cli_search_sources_filter(monkeypatch):
    runner = CliRunner()

    monkeypatch.setattr(
        "bookfinder.adapters.registry.get_all_adapters",
        lambda: [_Adapter("AbeBooks")],
    )

    async def _fake_search_all(query, adapters=None):
        return []

    monkeypatch.setattr("bookfinder.cli.search_all", _fake_search_all)

    result = runner.invoke(
        main,
        ["search", "Dune", "--sources", "AbeBooks,Nope", "--no-save"],
    )

    assert result.exit_code == 0
    assert "Unknown sources ignored" in result.output