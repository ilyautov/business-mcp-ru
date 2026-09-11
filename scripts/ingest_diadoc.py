#!/usr/bin/env python3
"""Собрать каталог методов Диадока (Контур) из официальной документации.

Машиночитаемой спеки у Диадока нет, зато есть страница «Список методов», а на
странице каждого метода стоит строка вида `GET /GetBox` и описание. Отсюда и
берём: имя, глагол, путь, назначение.

    python3 scripts/ingest_diadoc.py --catalog diadoc_mcp/endpoints.yaml --apply

Аддитивно и идемпотентно: записи с существующим operation_id не перезаписываются.
"""
from __future__ import annotations

import argparse
import html
import re
import time
import urllib.request
from collections import Counter
from pathlib import Path

import yaml

BASE = "https://developer.kontur.ru/doc/diadoc-api/"
UA = {"User-Agent": "Mozilla/5.0 (business-mcp-ru catalog builder)"}

# Разделы каталога методов: по ним разложим методы, чтобы поиск по каталогу
# отвечал на «контрагенты», «подписание», «печатные формы», а не на имена.
SECTION_BY_PREFIX: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"Counteragent", re.I), "counteragents"),
    (re.compile(r"PowerOfAttorney|Poa", re.I), "power_of_attorney"),
    (re.compile(r"PrintForm|DocumentProtocol|DocumentZip", re.I), "printforms"),
    (re.compile(r"Sign|Certificate|Dss", re.I), "signing"),
    (re.compile(r"Docflow", re.I), "docflow"),
    (re.compile(r"Employee|User|Department", re.I), "users"),
    (re.compile(r"Organization|Box|Roaming|Fns", re.I), "organizations"),
    (re.compile(r"Event|Subscription", re.I), "events"),
    (re.compile(r"Message|Template|Patch", re.I), "messages"),
    (re.compile(r"Xml|Parse|Generate", re.I), "generation"),
    (re.compile(r"Shelf|Entity|Content", re.I), "shelf"),
]

# Необратимое — только удаление. Restore возвращает документ, это запись.
DESTRUCTIVE = re.compile(r"^(Delete|Recycle|Break)", re.I)
# Чтение по глаголу имени: у Диадока много POST, которые ничего не меняют
# (Generate* строит печатную форму, Parse* разбирает XML, Can* проверяет право).
READ_VERB = re.compile(r"^(Get|Search|Can|Detect|Parse|Generate|Prevalidate|Extended)", re.I)


def section_of(name: str) -> str:
    for rx, sec in SECTION_BY_PREFIX:
        if rx.search(name):
            return sec
    return "documents"


def safety(verb: str, name: str) -> str:
    if DESTRUCTIVE.match(name):
        return "destructive"
    if verb == "GET":
        return "read"
    # POST, дальше решает глагол имени: см. комментарий у READ_VERB.
    return "read" if READ_VERB.match(name) else "write"


def snake(s: str) -> str:
    s = re.sub(r"(?<!^)(?=[A-Z])", "_", s)
    return re.sub(r"_+", "_", s).lower()


def get(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def text_of(page: str) -> str:
    body = page.split('class="document" itemscope')[-1]
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", body)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="для отладки")
    a = ap.parse_args()

    index = get(BASE + "methods.html")
    body = index.split('class="document" itemscope')[-1]
    links = re.findall(r'href="(http/[^"]+\.html)"', body)
    links = list(dict.fromkeys(links))
    if a.limit:
        links = links[: a.limit]

    path = Path(a.catalog)
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    rows: list[dict] = doc.get("endpoints", []) or []
    seen = {r["operation_id"] for r in rows}

    added, skipped = 0, []
    stats: Counter[str] = Counter()
    for i, href in enumerate(links, 1):
        try:
            txt = text_of(get(BASE + href))
        except Exception as exc:  # страница может быть переименована
            skipped.append(f"{href}: {exc}")
            continue
        m = re.search(r"\b(GET|POST|PUT|DELETE)\s+(/[A-Za-z0-9_/{}\-]+)", txt)
        if not m:
            skipped.append(f"{href}: не нашёл строку запроса")
            continue
        verb, http_path = m.group(1), m.group(2)
        name = href.split("/")[-1].replace(".html", "").split("_")[0]
        oid = "diadoc_" + snake(name)
        if oid in seen:
            continue
        # Описание: предложение между заголовком и строкой запроса.
        head = txt.split(m.group(0))[0]
        summary = head.split(name, 1)[-1].strip(" >–-")
        # Заголовок страницы несёт версию метода: «(V3) Отправляет...». Версия
        # уже видна в пути, в описании она только мешает поиску по каталогу.
        summary = re.sub(r"^\(V\d+\)\s*", "", summary)[:280] or name
        row = {
            "operation_id": oid,
            "section": section_of(name),
            "method": verb,
            "host": "diadoc-api.kontur.ru",
            "path": http_path,
            "scope": "diadoc",
            "safety": safety(verb, name),
            "summary": summary,
            "doc": BASE + href,
            "pagination": "none",
        }
        rows.append(row)
        seen.add(oid)
        added += 1
        stats[row["safety"]] += 1
        time.sleep(0.2)

    doc["default_host"] = "diadoc-api.kontur.ru"
    doc["endpoints"] = rows
    print(f"страниц: {len(links)} | new: {added} | catalog: {len(rows)}")
    print("safety:", dict(stats))
    if skipped:
        print("пропущено:", len(skipped))
        for s in skipped[:5]:
            print("   ", s)
    if a.apply:
        path.write_text(
            yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=100),
            encoding="utf-8",
        )
        print("WRITTEN", path)


if __name__ == "__main__":
    main()
