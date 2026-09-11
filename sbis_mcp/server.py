#!/usr/bin/env python3
"""sbis_mcp — MCP-сервер для API Saby (СБИС).

Каталог собран по официальной справке saby.ru/help/integration/api: 45 команд
по документообороту, подписи, сотрудникам, контрагентам, МЧД и организациям.

Транспорт у Saby непривычный: единственный HTTP-адрес `/service/`, а имя
команды («СБИС.СписокДокументов») едет в теле JSON-RPC. Поэтому в каталоге у
всех записей одинаковый path, а различает их поле params.body.

Авторизация: идентификатор сессии в заголовке `X-SBISSessionID`. Сессию выдаёт
команда СБИС.Аутентифицировать по логину и паролю; сам пароль сервер не хранит.

Запуск:
    SBIS_SESSION_ID=... python -m sbis_mcp.server
"""
from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from core.client import MarketplaceClient, ServiceConfig
from core.entities import EntityIndex
from core.registry import Catalog
from core.tools import register_cabinet_tools, register_generic_tools
from core.transport import run as run_transport

CATALOG_PATH = Path(__file__).with_name("endpoints.yaml")


def _build_headers(creds: dict[str, str]) -> dict[str, str]:
    return {
        "X-SBISSessionID": creds.get("session_id", ""),
        "Content-Type": "application/json-rpc; charset=utf-8",
    }


SBIS_CONFIG = ServiceConfig(
    name="sbis",
    scheme="https",
    fields=["session_id"],
    env_map={"session_id": "SBIS_SESSION_ID"},
    build_headers=_build_headers,
    allowed_host_suffixes=[".sbis.ru", ".saby.ru"],
)

mcp = FastMCP("sbis_mcp")
entities = EntityIndex.load()
catalog = Catalog.from_yaml(CATALOG_PATH, entities=entities)
client = MarketplaceClient(SBIS_CONFIG)

register_generic_tools(
    mcp, svc="sbis", client=client, catalog=catalog, entities=entities,
    key_help="Идентификатор сессии выдаёт команда СБИС.Аутентифицировать "
             "(логин и пароль сотрудника с правами на API). Положите его в "
             "SBIS_SESSION_ID; сессия живёт ограниченное время и обновляется той же командой.",
)
register_cabinet_tools(mcp, svc="sbis", client=client, catalog=catalog)


def main() -> None:
    run_transport(mcp)


if __name__ == "__main__":
    main()
