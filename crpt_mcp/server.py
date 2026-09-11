#!/usr/bin/env python3
"""crpt_mcp — MCP-сервер для ГИС МТ («Честный знак») и СУЗ.

Каталог: 33 метода по кодам маркировки, заказам на эмиссию, документам и
проверке подлинности. Источник путей — открытые SDK, а не документация ЦРПТ:
она открывается только после входа по КЭП, и публичной спеки нет. Поэтому у
каждой записи стоит `verified: false`, и describe_method это показывает: на
живом контуре глагол и параметры надо подтвердить.

Авторизация: токен ГИС МТ, заголовок `Authorization: Bearer <token>`. Токен
живёт около 10 часов и выдаётся в обмен на подписанные КЭП данные
(auth/key → подпись → auth/simpleSignIn). Подписание идёт вне сервера: с
закрытым ключом работает КриптоПро на машине пользователя.

Запуск:
    CRPT_TOKEN=... python -m crpt_mcp.server
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
    return {"Authorization": f"Bearer {creds.get('token', '')}"}


CRPT_CONFIG = ServiceConfig(
    name="crpt",
    scheme="https",
    fields=["token"],
    env_map={"token": "CRPT_TOKEN"},
    build_headers=_build_headers,
    allowed_host_suffixes=[".crpt.ru"],
)

mcp = FastMCP("crpt_mcp")
entities = EntityIndex.load()
catalog = Catalog.from_yaml(CATALOG_PATH, entities=entities)
client = MarketplaceClient(CRPT_CONFIG)

register_generic_tools(
    mcp, svc="crpt", client=client, catalog=catalog, entities=entities,
    key_help="Токен ГИС МТ: GET /api/v3/true-api/auth/key отдаёт случайные данные, "
             "их надо подписать КЭП (КриптоПро) и обменять через "
             "POST /api/v3/true-api/auth/simpleSignIn. Готовый токен кладётся в CRPT_TOKEN "
             "и живёт около 10 часов.",
)
register_cabinet_tools(mcp, svc="crpt", client=client, catalog=catalog)


def main() -> None:
    run_transport(mcp)


if __name__ == "__main__":
    main()
