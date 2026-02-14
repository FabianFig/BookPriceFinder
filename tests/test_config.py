from pathlib import Path

from bookfinder import config as cfg


def test_write_default_config_creates_file(tmp_path: Path):
    target = tmp_path / "config.toml"

    written = cfg.write_default_config(path=target)

    assert written == target
    assert target.exists()
    assert target.read_text(encoding="utf-8").strip()


def test_write_default_config_respects_force(tmp_path: Path):
    target = tmp_path / "config.toml"
    target.write_text("currency = 'EUR'\n", encoding="utf-8")

    cfg.write_default_config(path=target, force=False)
    assert "EUR" in target.read_text(encoding="utf-8")

    cfg.write_default_config(path=target, force=True)
    assert "EUR" not in target.read_text(encoding="utf-8")