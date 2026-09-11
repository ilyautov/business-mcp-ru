"""Упаковка: версии, точки входа и скиллы.

Версия живёт в двух местах, и они расходятся молча: pyproject уезжает при
релизе, server.json забывают. Поэтому сверяем их тестом, а не глазами.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ["hh", "vk", "diadoc", "sbis", "crpt"]


def pyproject() -> str:
    return (ROOT / "pyproject.toml").read_text(encoding="utf-8")


def test_version_matches_everywhere():
    version = re.search(r'^version = "([^"]+)"', pyproject(), re.M).group(1)
    server = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))
    assert server["version"] == version, "server.json отстал от pyproject"
    assert server["packages"][0]["version"] == version, "версия пакета в server.json отстала"
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"[{version}]" in changelog, "в changelog нет раздела под эту версию"


def test_every_service_has_an_entry_point():
    text = pyproject()
    for svc in SERVICES:
        assert f"{svc}-mcp = \"{svc}_mcp.server:main\"" in text, f"нет точки входа для {svc}"


def test_every_service_ships_its_catalog():
    """Каталог должен попасть в пакет: без package-data колесо соберётся, а
    сервер упадёт при первом запуске у пользователя."""
    text = pyproject()
    for svc in SERVICES:
        assert f"{svc}_mcp = [\"*.yaml\"]" in text, f"каталог {svc} не попадёт в пакет"
        assert (ROOT / f"{svc}_mcp" / "endpoints.yaml").exists()


def test_skills_frontmatter_is_valid():
    """Спека Agent Skills: только name и description, description до 1024
    символов. Лишнее поле — отказ при установке."""
    for skill in sorted((ROOT / "skills").iterdir()):
        text = (skill / "SKILL.md").read_text(encoding="utf-8")
        assert text.startswith("---\n"), f"{skill.name}: нет фронтматтера"
        front = yaml.safe_load(text.split("---", 2)[1])
        assert set(front) == {"name", "description"}, \
            f"{skill.name}: лишние поля {set(front) - {'name', 'description'}}"
        assert front["name"] == skill.name, f"{skill.name}: имя во фронтматтере другое"
        assert len(front["description"]) <= 1024, f"{skill.name}: описание длиннее 1024"


def test_pages_exist_and_are_listed_in_sitemap():
    """Страница без ссылки в sitemap для поиска не существует."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "build_pages", ROOT / "scripts" / "build_pages.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    sitemap = (ROOT / "docs" / "sitemap.xml").read_text(encoding="utf-8")
    for page in mod.PAGES:
        assert (ROOT / "docs" / page["file"]).exists(), page["file"]
        assert page["file"] in sitemap, f'{page["file"]} нет в sitemap.xml'
    assert len(mod.PAGES) == 5
