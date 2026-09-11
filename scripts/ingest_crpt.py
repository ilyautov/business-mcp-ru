#!/usr/bin/env python3
"""Собрать каталог ГИС МТ («Честный знак») и СУЗ из scripts/crpt_endpoints.tsv.

Документация ЦРПТ открывается только после входа по КЭП, машиночитаемой спеки
публично нет (`/api/v3/true-api/swagger.json` отдаёт 401). Поэтому пути ведутся
в TSV рядом и взяты из открытых SDK, а каждая запись помечается признаком
`verified: false`: на живом контуре глагол и параметры надо подтвердить.

    python3 scripts/ingest_crpt.py --catalog crpt_mcp/endpoints.yaml --apply
"""
from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path

import yaml

SRC = Path(__file__).with_name("crpt_endpoints.tsv")


def oid(host: str, path: str) -> str:
    svc = "suz" if host.startswith("suz") else "gis"
    tail = re.sub(r"\{[^}]+\}", "by_id", path)
    tail = re.sub(r"^/api/v\d+/(true-api/)?", "", tail)
    tail = re.sub(r"[^A-Za-z0-9]+", "_", tail).strip("_").lower()
    return f"crpt_{svc}_{tail}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    path = Path(a.catalog)
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    rows: list[dict] = doc.get("endpoints", []) or []
    seen = {r["operation_id"] for r in rows}

    added = 0
    stats: Counter[str] = Counter()
    for line in SRC.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        host, section, method, http_path, safety, summary = line.split("\t")
        o = oid(host, http_path)
        if o in seen:
            continue
        rows.append({
            "operation_id": o,
            "section": section,
            "method": method,
            "host": host,
            "path": http_path,
            "scope": "suz" if host.startswith("suz") else "gis-mt",
            "safety": safety,
            "summary": summary,
            "doc": "https://markirovka.crpt.ru/api-docs",
            "pagination": "none",
            # Источник — открытые SDK, а не документация ЦРПТ: она за КЭП.
            # Флаг едет в каталог, чтобы агент честно показывал статус метода.
            "verified": False,
        })
        seen.add(o)
        added += 1
        stats[safety] += 1

    doc["default_host"] = "markirovka.crpt.ru"
    doc["endpoints"] = rows
    print(f"new: {added} | catalog: {len(rows)}")
    print("safety:", dict(stats))
    if a.apply:
        path.write_text(
            yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=100),
            encoding="utf-8",
        )
        print("WRITTEN", path)


if __name__ == "__main__":
    main()
