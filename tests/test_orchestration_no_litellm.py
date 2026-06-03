"""Garante que orchestration/ não importa litellm."""

from pathlib import Path


def test_orchestration_modules_do_not_import_litellm() -> None:
    root = Path(__file__).resolve().parents[1] / "config" / "litellm" / "orchestration"
    for path in root.glob("*.py"):
        if path.name == "__init__.py":
            continue
        source = path.read_text(encoding="utf-8")
        assert "import litellm" not in source
        assert "from litellm" not in source
