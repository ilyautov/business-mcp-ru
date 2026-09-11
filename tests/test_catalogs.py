"""Каталоги — источник правды сервера, поэтому проверяем именно их.

Тесты намеренно не ходят в сеть: они читают YAML и смотрят на то, что агент
увидит в describe_method. Самое важное здесь — класс доступа: ошибка в нём
либо мучает человека лишними подтверждениями, либо (хуже) пропускает запись
без спроса.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CATALOGS = {
    "hh": ROOT / "hh_mcp" / "endpoints.yaml",
    "vk": ROOT / "vk_mcp" / "endpoints.yaml",
    "diadoc": ROOT / "diadoc_mcp" / "endpoints.yaml",
    "sbis": ROOT / "sbis_mcp" / "endpoints.yaml",
    "crpt": ROOT / "crpt_mcp" / "endpoints.yaml",
}

# Хосты, за пределы которых сервис не имеет права отправить заголовок авторизации.
ALLOWED = {
    "hh": (".hh.ru",),
    "vk": (".vk.com", "api.vk.com"),
    "diadoc": (".kontur.ru",),
    "sbis": (".sbis.ru", ".saby.ru"),
    "crpt": (".crpt.ru",),
}

SAFETY = {"read", "write", "destructive"}


def load(name: str) -> list[dict]:
    return yaml.safe_load(CATALOGS[name].read_text(encoding="utf-8"))["endpoints"]


@pytest.mark.parametrize("name", sorted(CATALOGS))
def test_catalog_loads_through_the_engine(name):
    """Каталог должен читаться движком, а не только глазами: лишнее поле в
    записи роняет EndpointSpec(**rec) уже на старте сервера."""
    from core.registry import Catalog

    catalog = Catalog.from_yaml(CATALOGS[name])
    assert catalog.all(), f"{name}: пустой каталог"


@pytest.mark.parametrize("name", sorted(CATALOGS))
def test_operation_ids_unique(name):
    ids = [r["operation_id"] for r in load(name)]
    dupes = {i for i in ids if ids.count(i) > 1}
    assert not dupes, f"{name}: повторяющиеся operation_id: {sorted(dupes)}"


@pytest.mark.parametrize("name", sorted(CATALOGS))
def test_safety_values_are_known(name):
    for r in load(name):
        assert r["safety"] in SAFETY, f"{name}/{r['operation_id']}: {r['safety']}"


@pytest.mark.parametrize("name", sorted(CATALOGS))
def test_hosts_stay_inside_the_allowlist(name):
    """Хост из каталога обязан попадать в allowlist сервиса, иначе сервер
    откажет в вызове на старте, и метод в каталоге будет мёртвым грузом."""
    allowed = ALLOWED[name]
    for r in load(name):
        host = r["host"].lower()
        assert any(host == a.lstrip(".") or host.endswith(a) for a in allowed), \
            f"{name}/{r['operation_id']}: хост {host} вне allowlist {allowed}"


@pytest.mark.parametrize("name", sorted(CATALOGS))
def test_every_record_explains_itself(name):
    """Пустое описание делает метод невидимым для поиска по каталогу: агент
    ищет словами, а не идентификаторами."""
    for r in load(name):
        assert len(r.get("summary", "").strip()) >= 10, \
            f"{name}/{r['operation_id']}: описание пустое или слишком куцее"


READ_TAIL = re.compile(r"/(list|get|info|search|suggest|dictionaries)$", re.I)


def test_hh_read_tail_is_not_marked_write():
    """У hh много GET-путей с читающим хвостом; если такой помечен записью,
    агент будет просить подтверждение на обычную выборку."""
    bad = [r["operation_id"] for r in load("hh")
           if r["method"] == "GET" and r["safety"] != "read"]
    assert not bad, f"GET, помеченные не как чтение: {bad}"


def test_vk_verbs_match_safety():
    """VK не размечает намерение глаголом HTTP: всё POST. Единственный сигнал —
    имя метода, и именно его проверяем на известных примерах."""
    idx = {r["path"].split("/method/")[1]: r["safety"] for r in load("vk")}
    expected = {
        "market.get": "read", "market.edit": "write", "market.delete": "destructive",
        "messages.send": "write", "groups.getBanned": "read", "groups.ban": "destructive",
        "groups.unban": "write", "stats.get": "read", "wall.post": "write",
        "ads.getStatistics": "read",
    }
    wrong = {k: (idx.get(k), v) for k, v in expected.items() if idx.get(k) != v}
    assert not wrong, f"класс доступа разошёлся: {wrong}"


def test_sbis_destroy_is_destructive():
    """«Уничтожить» у Saby удаляет без восстановления. Такой метод обязан
    требовать подтверждения."""
    idx = {r["operation_id"]: r["safety"] for r in load("sbis")}
    destroy = [k for k in idx if "unichtozhit" in k]
    assert destroy, "не нашёл команду уничтожения — изменилось имя?"
    for k in destroy:
        assert idx[k] == "destructive", f"{k}: {idx[k]}"


def test_crpt_records_are_marked_unverified():
    """Каталог ЦРПТ собран по открытым SDK, а не по документации (она за КЭП).
    Флаг должен стоять у всех записей, иначе агент выдаст догадку за факт."""
    rows = load("crpt")
    unverified = [r for r in rows if r.get("verified") is False]
    assert len(unverified) == len(rows), \
        f"без пометки осталось {len(rows) - len(unverified)} записей"


def test_catalog_sizes_are_stated_honestly():
    """README называет числа методов. Расхождение с каталогом — это ложь в
    витрине, поэтому оно ломает сборку."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for name, path in CATALOGS.items():
        n = len(load(name))
        assert f"{n}" in readme, f"README не упоминает {n} методов для {name}"
