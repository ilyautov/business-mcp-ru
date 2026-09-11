#!/usr/bin/env python3
"""hh_mcp — MCP-сервер для API hh.ru.

Каталог собран из официальной спеки api.hh.ru/openapi/specification/public:
133 метода, вакансии, отклики, резюме, справочники, статистика зарплат.

Авторизация: один токен приложения, заголовок `Authorization: Bearer <token>`.
Токен выдаётся в кабинете разработчика dev.hh.ru → Мои приложения.

Запуск:
    HH_TOKEN=... python -m hh_mcp.server
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
    # hh требует и User-Agent с контактом приложения, иначе отвечает 400:
    # это его правило, а не общая практика.
    return {
        "Authorization": f"Bearer {creds.get('token', '')}",
        "HH-User-Agent": creds.get("app_name", "business-mcp-ru (support@example.com)"),
    }


HH_CONFIG = ServiceConfig(
    name="hh",
    scheme="https",
    fields=["token", "app_name"],
    env_map={"token": "HH_TOKEN", "app_name": "HH_APP_NAME"},
    build_headers=_build_headers,
    allowed_host_suffixes=[".hh.ru"],
    whoami=("hh_get_me", ["first_name", "last_name", "email"]),
)

mcp = FastMCP("hh_mcp")
entities = EntityIndex.load()
catalog = Catalog.from_yaml(CATALOG_PATH, entities=entities)
client = MarketplaceClient(HH_CONFIG)

register_generic_tools(
    mcp, svc="hh", client=client, catalog=catalog, entities=entities,
    key_help="dev.hh.ru → Мои приложения → создать приложение, взять access token. "
             "В HH_APP_NAME укажите имя приложения и контактный email: hh отклоняет "
             "запросы без внятного User-Agent.",
)
register_cabinet_tools(mcp, svc="hh", client=client, catalog=catalog)


def main() -> None:
    run_transport(mcp)


if __name__ == "__main__":
    main()
