from pathlib import Path

from paper_api.assistant import history


def test_source_history_uses_research_data_directory(monkeypatch) -> None:
    monkeypatch.delenv("CRYPTOPAPERLAB_DATA_DIR", raising=False)
    monkeypatch.delattr(history.sys, "frozen", raising=False)

    path = history.history_path()

    assert path.name == "assistant_history.json"
    assert path.parent.name == "data"
    assert path.parent.parent.name == "research_engine"


def test_data_directory_override_is_used_for_history(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "user-data"
    monkeypatch.setenv("CRYPTOPAPERLAB_DATA_DIR", str(target))

    assert history.history_path() == target / "assistant_history.json"


def test_frozen_history_uses_per_user_writable_directory(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("CRYPTOPAPERLAB_DATA_DIR", raising=False)
    monkeypatch.setattr(history.sys, "frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert history.history_path() == tmp_path / "CryptoPaperLab" / "assistant_history.json"
