"""Зонтик: список серверов в одном месте расходится с другим молча.

Здесь проверяется ровно это: пять репозиториев перечислены и в зависимостях
пакета, и в README, и в страницах, и числа методов везде одни и те же.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def pages():
    spec = importlib.util.spec_from_file_location("bp", ROOT / "scripts" / "build_pages.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_five_servers_everywhere():
    bp = pages()
    repos = [p["repo"] for p in bp.PAGES]
    assert len(repos) == 5 and len(set(repos)) == 5

    deps = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for repo in repos:
        assert f'"{repo}>=' in deps, f"{repo} нет в зависимостях мета-пакета"
        assert repo in readme, f"{repo} нет в README"


def test_method_counts_in_readme_match_the_catalogs():
    """README обещает число методов. Каталог может уехать, README нет."""
    bp = pages()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    total = 0
    for p in bp.PAGES:
        n = len(bp.load(p["svc"]))
        total += n
        assert f"| {n} |" in readme, f'{p["repo"]}: в README нет «{n}»'
    assert f"Всего {total} методов" in readme


def test_pages_are_in_sitemap():
    bp = pages()
    sitemap = (ROOT / "docs" / "sitemap.xml").read_text(encoding="utf-8")
    for p in bp.PAGES:
        assert (ROOT / "docs" / p["file"]).exists(), p["file"]
        assert p["file"] in sitemap


def test_no_code_ships_in_the_hub():
    """Зонтик это сайт и список. Код уехал в репозитории серверов, и если он
    вернётся сюда копией, разойдётся с оригиналом."""
    stray = [d.name for d in ROOT.iterdir()
             if d.is_dir() and (d.name.endswith("_mcp") or d.name == "core")]
    assert not stray, f"в зонтике снова лежит код сервера: {stray}"
