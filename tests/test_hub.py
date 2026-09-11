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
    assert f"Всего {total} методов в пяти серверах" in readme


def test_marketplaces_are_listed_too():
    """Маркетплейсы это соседний проект, но читателю он виден как часть семьи:
    пропустить его строкой значит спрятать 1 022 метода."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "marketplaces-mcp-ru" in readme
    assert "1 022" in readme


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


def test_schema_version_matches_the_packages():
    """`softwareVersion` в schema.org это обещание поисковику.

    Оно уже один раз разошлось: на страницах стояло 0.1.0, когда пакеты давно
    выпустились как 0.2.0. Глазами такое не ловится, там нет ни ошибки, ни
    падения, просто число живёт своей жизнью.
    """
    bp = pages()
    for p in bp.PAGES:
        pyproject = bp.NEIGHBOURS / p["repo"] / "pyproject.toml"
        if not pyproject.exists():          # соседей нет, проверять нечего
            continue
        m = re.search(r'^version = "([^"]+)"', pyproject.read_text(encoding="utf-8"), re.M)
        assert m, f'{p["repo"]}: в pyproject нет версии'
        assert m.group(1) == bp.VERSION, (
            f'{p["repo"]} выпущен как {m.group(1)}, а страницы пишут {bp.VERSION}')


def test_both_subdomains_link_to_each_other():
    """Девять серверов на двух поддоменах. Односторонняя перелинковка значит,
    что половина из них для пришедшего человека не существует."""
    bp = pages()
    for name in ["index.html"] + [p["file"] for p in bp.PAGES]:
        page = (ROOT / "docs" / name).read_text(encoding="utf-8")
        assert bp.MARKETPLACES in page, f"{name}: нет ссылки на соседний набор"


def test_service_pages_carry_errors_and_faq():
    """Страница сервиса это справочник, а не карточка товара: хвост запросов
    у всех четырёх кластеров одинаковый и состоит из «где ключ», «где
    документация», «почему не работает»."""
    bp = pages()
    for p in bp.PAGES:
        assert len(p["errors"]) >= 3, f'{p["repo"]}: мало разборов ошибок'
        assert len(p["faq"]) >= 4, f'{p["repo"]}: мало вопросов'
        page = (ROOT / "docs" / p["file"]).read_text(encoding="utf-8")
        assert "Частые ошибки" in page and "Частые вопросы" in page
        assert '"FAQPage"' in page and '"BreadcrumbList"' in page
