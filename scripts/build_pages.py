#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Генератор страниц сайта: docs/index.html и docs/<сервис>-api.html.

Таблицы методов собираются из тех же каталогов, что грузит сервер
(`*/endpoints.yaml`), поэтому страница не может разойтись с кодом. Проза лежит
здесь, в PAGES: заголовки написаны под замеренные запросы Вордстата, а не «от
темы» (замер 11.09.2026, см. Projects/nishi-mcp-skills-2026-09-11).

    python3 scripts/build_pages.py            # записать
    python3 scripts/build_pages.py --check    # сверить, ничего не трогая (для CI)
"""
from __future__ import annotations

import argparse
import html
import importlib
import json
import os
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
# Каталоги уехали в репозитории серверов. Ищем их там, куда укажет
# MCP_NEIGHBOURS_DIR (так делает CI: checkout не умеет класть репозиторий выше
# рабочей папки), иначе рядом с зонтиком, иначе берём из установленного пакета.
NEIGHBOURS = Path(os.environ.get("MCP_NEIGHBOURS_DIR") or ROOT.parent)
SITE = "https://business-mcp-ru.aifrontier.tech"
DOMAIN = SITE.split("//", 1)[1]
REPO = "https://github.com/ilyautov/business-mcp-ru"
MARKETPLACES = "https://marketplaces-mcp-ru.aifrontier.tech/"
# Соседний набор. Считается из его каталогов, если репозиторий лежит рядом:
# число на главной иначе протухнет молча, как уже было с «793 метода» у Glama.
MARKETPLACE_CATALOGS = [
    ("Wildberries", "wb_mcp/endpoints.yaml", "wildberries-api.html"),
    ("Ozon", "ozon_mcp/endpoints.yaml", "ozon-api.html"),
    ("Ozon Performance", "ozon_mcp/perf_endpoints.yaml", "ozon-api.html"),
    ("Яндекс Маркет", "yandex_mcp/endpoints.yaml", "yandex-market-api.html"),
    ("Авито", "avito_mcp/endpoints.yaml", "avito-api.html"),
]
MARKETPLACE_TOTAL_FALLBACK = 1022
TODAY = date.today().isoformat()
# Картинка для соцсетей. Одна на весь сайт: страницы отличаются заголовком,
# а не обложкой, и пять почти одинаковых png только запутали бы.
SOCIAL = f"{SITE}/assets/social-preview.png"
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
VERSION_RE = re.compile(r'^version = "([^"]+)"', re.M)
# Запасная версия для schema.org: сюда доходит, только если pyproject рядом нет.
VERSION = "0.2.0"


def version_of(repo: str) -> str:
    """Версия для schema.org берётся из pyproject, а не из константы в коде.

    Константа тут уже разъехалась с релизами молча: страницы обещали 0.2.0,
    когда пакеты вышли как 0.2.3, а зонтик и вовсе опубликован как 0.1.0.
    """
    pyproject = (ROOT if repo == "business-mcp-ru" else NEIGHBOURS / repo) / "pyproject.toml"
    if pyproject.exists():
        m = VERSION_RE.search(pyproject.read_text(encoding="utf-8"))
        if m:
            return m.group(1)
    return VERSION


# Что Claude Desktop спросит в окне установки бандла. Слово разное: у СБИС это
# не токен, и обещать «токен» там значит отправить человека искать не то.
MCPB_SECRET = {"hh": "токен", "vk": "токен", "diadoc": "ключи",
               "sbis": "идентификатор сессии", "crpt": "токен"}

# Человеческие названия разделов каталога. Ключ — section в endpoints.yaml.
SECTION_NAMES: dict[str, dict[str, str]] = {
    "hh": {
        "vacancies": "Вакансии", "employers": "Работодатель и менеджеры",
        "negotiations": "Отклики и приглашения", "resumes": "Резюме",
        "saved_searches": "Сохранённые поиски", "suggests": "Подсказки",
        "common": "Общие справочники", "areas": "Регионы",
        "salary_statistics": "Статистика зарплат", "webhook": "Вебхуки",
        "applicant_comments": "Комментарии к соискателю", "calls": "Звонки",
        "token": "Токены", "me": "Текущий пользователь", "metro": "Метро",
        "dictionaries": "Словари", "industries": "Отрасли",
        "professional_roles": "Профессиональные роли", "languages": "Языки",
        "skills": "Навыки", "locales": "Локали", "clickme": "Clickme",
        "districts": "Районы", "message_templates": "Шаблоны сообщений",
        "educational_institutions": "Учебные заведения",
        "manager_accounts": "Аккаунты менеджеров",
        "vacancy_conditions": "Условия публикации вакансий",
    },
    "vk": {
        "market": "Товары и магазин", "groups": "Сообщества",
        "ads": "Реклама", "messages": "Диалоги", "stats": "Статистика",
        "wall": "Записи на стене", "photos": "Фотографии", "video": "Видео",
        "docs": "Документы", "board": "Обсуждения", "leadForms": "Лид-формы",
        "orders": "Заказы", "storage": "Хранилище приложения",
        "utils": "Утилиты", "users": "Пользователи", "donut": "VK Donut",
        "prettyCards": "Карточки в записях", "podcasts": "Подкасты",
        "notifications": "Уведомления", "pages": "Вики-страницы",
    },
    "diadoc": {
        "documents": "Документы", "docflow": "Документооборот",
        "counteragents": "Контрагенты", "signing": "Подписание",
        "power_of_attorney": "Машиночитаемая доверенность",
        "printforms": "Печатные формы", "organizations": "Организации и ящики",
        "users": "Сотрудники и пользователи", "events": "События",
        "messages": "Сообщения", "generation": "Генерация и разбор XML",
        "shelf": "Полка документов",
    },
    "sbis": {
        "documents": "Документы и этапы", "auth": "Аутентификация",
        "users": "Сотрудники", "signature": "Электронная подпись",
        "counteragents": "Контрагенты", "organizations": "Наши организации",
        "poa": "МЧД", "service": "Сервисные команды",
    },
    "crpt": {
        "cises": "Коды маркировки", "codes": "Проверка кодов",
        "orders": "Заказы на эмиссию", "documents": "Документы ГИС МТ",
        "products": "Товары и GTIN", "quality": "Отчёты о нанесении",
        "receipts": "Чеки", "auth": "Авторизация", "system": "Служебные",
    },
}

PAGES = [
    {
        "svc": "hh", "repo": "hh-mcp-ru", "card": "Вакансии, отклики и приглашения, резюме, справочники, статистика зарплат", "file": "hh-api.html", "entry": "hh-mcp",
        "title": "API hh.ru в ИИ-ассистенте: вакансии, отклики, резюме",
        "h1": "API hh.ru в ИИ-ассистенте",
        "desc": "MCP-сервер для API hh.ru: 133 метода официальной спеки. "
                "Вакансии, отклики и приглашения, резюме, справочники, "
                "статистика зарплат. Ставится двойным щелчком или одной "
                "командой, ключ из dev.hh.ru.",
        "source": "официальная спека <code>api.hh.ru/openapi/specification/public</code>",
        "env": "HH_TOKEN, HH_APP_NAME",
        "keys": "dev.hh.ru → Мои приложения → создать приложение → access token. "
                "HH_APP_NAME заполняется обязательно: hh отклоняет запросы без "
                "внятного User-Agent, и это первая причина непонятных ошибок 400.",
        "tasks": [
            "Выгрузить свои вакансии и отклики за период и свести в таблицу.",
            "Посмотреть статистику зарплат по роли перед публикацией вакансии.",
            "Найти вакансии конкурентов по региону и профессиональной роли.",
            "Ответить кандидатам шаблоном, показав список человеку до отправки.",
        ],
        "errors": [
            ("400 на любом запросе, хотя токен верный",
             "Первым делом проверьте <code>HH_APP_NAME</code>. hh отклоняет запросы без "
             "внятного заголовка <code>HH-User-Agent</code>, а туда подставляется имя "
             "приложения и контактный email. Без переменной сервер шлёт значение по "
             "умолчанию, и это самая частая причина непонятных четырёхсотых."),
            ("403 на методе, который открывается в кабинете",
             "У каждой записи каталога проставлен раздел доступа, и "
             "<code>hh_describe_method</code> его показывает. 403 почти всегда значит, что "
             "токен выдан на другой тип аккаунта: тридцать методов раздела «Работодатель "
             "и менеджеры» соискательским токеном не открываются."),
            ("Ответ обрывается на первых двадцати записях",
             "Это не обрыв, а страница. У методов с постраничной выдачей в каталоге "
             "указаны параметры пагинации, и <code>hh_fetch_all</code> проходит страницы "
             "сам. Если звать <code>hh_call_method</code> напрямую, страницу надо "
             "передавать руками."),
        ],
        "faq": [
            ("Как получить токен API hh.ru?",
             "dev.hh.ru, раздел «Мои приложения», создать приложение и взять access token. "
             "Вместе с токеном сразу заполните HH_APP_NAME: имя приложения и контактный "
             "email, без них hh отвечает 400."),
            ("Где документация API hh.ru?",
             "Официальная спека лежит открыто: api.hh.ru/openapi/specification/public. "
             "Каталог этого сервера собран из неё же, поэтому таблица разделов на этой "
             "странице и то, что сервер реально вызывает, это один и тот же файл."),
            ("Можно ли откликаться и писать кандидатам через API?",
             "Да, раздел «Отклики и приглашения» это умеет, и такие методы помечены как "
             "запись. Перед отправкой сервер обязан спросить подтверждение, поэтому "
             "случайной рассылки от лица агента не будет."),
            ("Сколько методов hh.ru поддерживает hh-mcp-ru?",
             "133, все с официального хоста api.hh.ru. У каждого метода указаны параметры, "
             "пагинация и класс доступа: 92 на чтение, 32 на запись, 9 необратимых."),
        ],
    },
    {
        "svc": "vk", "repo": "vk-mcp-ru", "card": "Товары магазина сообщества, посты, реклама и статистика, диалоги, лид-формы", "file": "vk-api.html", "entry": "vk-mcp",
        "title": "VK API в ИИ-ассистенте: товары, сообщества, реклама",
        "h1": "VK API в ИИ-ассистенте",
        "desc": "MCP-сервер для VK API: 373 метода по бизнес-разделам. "
                "Товары магазина сообщества, посты, рекламные кампании и "
                "статистика, диалоги с клиентами, лид-формы.",
        "source": "официальная схема <code>VKCOM/vk-api-schema</code>",
        "env": "VK_TOKEN",
        "keys": "dev.vk.com → приложение → сервисный ключ доступа, либо токен "
                "сообщества с правами market, messages, ads, stats. Запрашивайте "
                "только те права, которые реально нужны.",
        "tasks": [
            "Свести заказы и товары магазина сообщества в таблицу.",
            "Посмотреть статистику сообщества и постов за период.",
            "Собрать расходы и показатели рекламных кампаний VK Ads.",
            "Разобрать непрочитанные диалоги и подготовить ответы на согласование.",
        ],
        "errors": [
            ("Пришёл HTTP 200, а данных нет",
             "У VK ошибка лежит в теле ответа, а не в HTTP-коде: успешный запрос к "
             "серверу и неуспешный вызов метода это разные вещи. Смотрите объект "
             "<code>error</code> в ответе, там есть код и текст."),
            ("Метод отвечает иначе, чем в документации",
             "Скорее всего дело в версии API. Сервер пинует <code>v=5.199</code>, и это "
             "осознанно: старая версия не ругается, а молча отдаёт другой формат ответа. "
             "Если сверяете с примером из интернета, сверьте и версию, под которую он "
             "написан."),
            ("Кажется, что любой вызов это запись",
             "Не кажется, но и не так. Все 373 метода VK идут через POST, поэтому "
             "HTTP-глагол тут ничего не говорит о намерении. Класс доступа в каталоге "
             "проставлен по смыслу метода, и гейт подтверждения работает именно по нему, "
             "а не по глаголу."),
        ],
        "faq": [
            ("Как получить токен VK API?",
             "dev.vk.com, создать приложение и взять сервисный ключ доступа, либо выпустить "
             "токен сообщества. Права запрашивайте точечно: market для товаров, messages "
             "для диалогов, ads для рекламы, stats для статистики."),
            ("Чем сервисный ключ отличается от токена сообщества?",
             "Сервисный ключ работает от имени приложения и открывает публичные данные. "
             "Токен сообщества работает от имени группы и нужен для товаров, диалогов и "
             "статистики этой группы. Для магазина в сообществе нужен именно он."),
            ("Где документация VK API?",
             "dev.vk.com/method, а машиночитаемая схема лежит в репозитории VKCOM/vk-api-schema. "
             "Каталог собран из этой схемы, поэтому список методов не расходится с тем, "
             "что сервер умеет вызывать."),
            ("Сколько методов VK поддерживает vk-mcp-ru?",
             "373, сгруппированных по деловым разделам: товары и магазин, сообщества, "
             "реклама, диалоги, статистика, лид-формы. Агент ищет метод словами, а не "
             "листает список."),
        ],
    },
    {
        "svc": "diadoc", "repo": "diadoc-mcp-ru", "card": "Входящие и исходящие документы, статусы ЭДО, контрагенты, подписание, МЧД", "file": "diadoc-api.html", "entry": "diadoc-mcp",
        "title": "API Диадока в ИИ-ассистенте: ЭДО, документы, контрагенты",
        "h1": "API Диадока (Контур) в ИИ-ассистенте",
        "desc": "MCP-сервер для API Диадока: 114 методов. Входящие и исходящие "
                "документы, статусы документооборота, контрагенты и приглашения "
                "к ЭДО, подписание, МЧД, печатные формы.",
        "source": "документация <code>developer.kontur.ru/doc/diadoc-api</code>",
        "env": "DIADOC_CLIENT_ID, DIADOC_TOKEN",
        "keys": "Идентификатор приложения запрашивается у Контура письмом, для "
                "продуктива нужна лицензия, для проб есть тестовый контур. Токен "
                "пользователя выдаёт метод Authenticate по логину и паролю или "
                "по сертификату.",
        "tasks": [
            "Показать входящие документы, по которым нужно действие.",
            "Свести документооборот с контрагентом за период.",
            "Найти контрагента по ИНН и КПП и проверить, подключён ли он к ЭДО.",
            "Скачать печатную форму документа для бухгалтерии.",
        ],
        "errors": [
            ("401, хотя и client_id, и токен на месте",
             "Проверьте пробелы. Диадок ждёт заголовок вида "
             "<code>DiadocAuth ddauth_api_client_id=&lt;id&gt;,ddauth_token=&lt;token&gt;</code>, "
             "и он разбирается строкой: лишний пробел после запятой ломает авторизацию. "
             "Сервер собирает заголовок сам, но если вы проверяете curl-ом, это первое место, "
             "куда стоит смотреть."),
            ("Один секрет есть, другого нет",
             "Их действительно два, и они выдаются по-разному. Идентификатор приложения "
             "запрашивается у Контура письмом на diadoc-api@skbkontur.ru, а токен "
             "пользователя отдаёт метод Authenticate по логину с паролем или по сертификату. "
             "Один без другого не работает."),
            ("404 на методе из документации",
             "В API Диадока одновременно живут несколько версий пути, от V1 до V4, и у "
             "соседних методов они разные. Версия это часть пути, а не заголовок, поэтому "
             "при 404 сверяйте её раньше всего остального."),
        ],
        "faq": [
            ("Как получить доступ к API Диадока?",
             "Написать в Контур на diadoc-api@skbkontur.ru и получить идентификатор "
             "приложения. Для продуктива нужна лицензия, для проб есть тестовый контур. "
             "Токен пользователя дальше выдаёт метод Authenticate."),
            ("Можно ли подписывать документы через API?",
             "Методы подписания в каталоге есть и помечены как необратимые, то есть агент "
             "обязан спросить подтверждение. Сама подпись при этом делается средствами "
             "криптопровайдера на машине пользователя, закрытый ключ в сервер не попадает."),
            ("Где документация API Диадока?",
             "developer.kontur.ru/doc/diadoc-api. Каталог этого сервера собран оттуда, "
             "114 методов с разделами и классами доступа."),
            ("Чем Диадок отличается от СБИС в этом наборе?",
             "Это два разных оператора ЭДО, и серверы у них отдельные: разные хосты, разные "
             "схемы авторизации, разные каталоги. Если контрагенты у вас в обоих, ставьте "
             "оба, они не мешают друг другу."),
        ],
    },
    {
        "svc": "sbis", "repo": "sbis-mcp-ru", "card": "Документы и этапы, подписание вложений, сертификаты, сотрудники, контрагенты", "file": "sbis-api.html", "entry": "sbis-mcp",
        "title": "API СБИС (Saby) в ИИ-ассистенте: документы, подпись, ЭДО",
        "h1": "API СБИС (Saby) в ИИ-ассистенте",
        "desc": "MCP-сервер для API СБИС: 45 команд JSON-RPC. Документы и этапы "
                "документооборота, подписание вложений, сертификаты и МЧД, "
                "сотрудники, контрагенты, подразделения.",
        "source": "справка <code>saby.ru/help/integration/api</code>",
        "env": "SBIS_SESSION_ID",
        "keys": "Команда СБИС.Аутентифицировать по логину и паролю сотрудника с "
                "правами на API возвращает идентификатор сессии. Сессия живёт "
                "ограниченное время и обновляется той же командой, пароль в "
                "сервере не хранится.",
        "tasks": [
            "Выгрузить список документов нужного типа за период.",
            "Посмотреть, на каком этапе застряли исходящие документы.",
            "Проверить статус сертификатов подписи до того, как они истекут.",
            "Найти контрагента и его идентификатор участника ЭДО.",
        ],
        "errors": [
            ("Поиск по URL ничего не находит",
             "И не найдёт: у СБИС все 45 команд идут на один путь "
             "<code>/service/</code>, а имя команды лежит в теле запроса по JSON-RPC. "
             "Искать надо по смыслу через <code>sbis_search_methods</code>, а не по "
             "эндпоинту."),
            ("401 после перерыва в работе",
             "Сессия СБИС живёт ограниченное время. Идентификатор сессии передаётся "
             "заголовком <code>X-SBISSessionID</code>, и когда он протухает, лечится это "
             "повторным вызовом команды аутентификации. Пароль при этом в сервере не "
             "хранится."),
            ("Кажется, что все команды пишут",
             "Все 45 идут через POST, потому что так устроен JSON-RPC, а не потому что "
             "все они меняют данные. Класс доступа в каталоге проставлен по смыслу "
             "команды, и подтверждение спрашивается по нему."),
        ],
        "faq": [
            ("Как получить доступ к API СБИС?",
             "Нужен сотрудник с правами на интеграцию. Команда СБИС.Аутентифицировать по "
             "его логину и паролю возвращает идентификатор сессии, он и кладётся в "
             "SBIS_SESSION_ID."),
            ("Почему у СБИС один адрес на все команды?",
             "Потому что это JSON-RPC, а не REST. Адрес online.sbis.ru/service/ один, "
             "различаются команды в теле запроса. Для агента разницы нет: он всё равно "
             "ищет метод словами."),
            ("Где документация API СБИС?",
             "saby.ru/help/integration/api. Каталог собран оттуда: 45 команд по документам "
             "и этапам, подписи, сертификатам, сотрудникам и контрагентам."),
            ("Сколько методов СБИС поддерживает sbis-mcp-ru?",
             "45. Это меньше, чем у Диадока, потому что у СБИС публично описана меньшая "
             "часть API, а не потому что каталог неполный."),
        ],
    },
    {
        "svc": "crpt", "repo": "chestny-znak-mcp-ru", "card": "Коды маркировки, заказы на эмиссию в СУЗ, маршрут товара по GTIN, отчёты", "file": "chestny-znak-api.html", "entry": "crpt-mcp",
        "title": "API Честного знака в ИИ-ассистенте: коды маркировки и СУЗ",
        "h1": "API Честного знака (ГИС МТ) в ИИ-ассистенте",
        "desc": "MCP-сервер для ГИС МТ и СУЗ: 33 метода. Сведения о кодах "
                "маркировки, выгрузка по фильтру, маршрут товара по GTIN, заказы "
                "на эмиссию кодов, отчёты о нанесении, проверка подлинности.",
        "source": "открытые SDK True API и СУЗ",
        "env": "CRPT_TOKEN",
        "keys": "GET /api/v3/true-api/auth/key отдаёт случайные данные, их "
                "подписывают КЭП через КриптоПро на машине пользователя, а "
                "POST /api/v3/true-api/auth/simpleSignIn меняет подпись на токен. "
                "Токен живёт около 10 часов. Закрытый ключ в сервер не попадает.",
        "tasks": [
            "Проверить пачку кодов маркировки перед приёмкой товара.",
            "Посмотреть статус заказа на эмиссию кодов в СУЗ.",
            "Выгрузить коды, принадлежащие участнику оборота.",
            "Посмотреть маршрут товара по GTIN.",
        ],
        "caveat": "Документация ЦРПТ открывается только после входа по КЭП, "
                  "публичной спеки нет: <code>/api/v3/true-api/swagger.json</code> "
                  "отдаёт 401. Поэтому пути здесь взяты из открытых SDK и у каждой "
                  "записи каталога стоит <code>verified: false</code>. Это карта для "
                  "разведки: пути надёжные, глаголы и параметры нужно подтвердить на "
                  "живом контуре. Сервер показывает этот статус в describe_method, "
                  "чтобы агент не выдавал догадку за факт.",
        "errors": [
            ("Токен перестал работать через несколько часов",
             "Так и задумано: токен ГИС МТ живёт около десяти часов. Получается он в два "
             "шага, ответ метода auth/key подписывается КЭП, а auth/simpleSignIn меняет "
             "подпись на токен. Обновлять придётся регулярно."),
            ("Метод не находится на том хосте, где ищете",
             "Хостов два, и это не опечатка. ГИС МТ живёт на markirovka.crpt.ru, а станция "
             "управления заказами на suz.crpt.ru. Это разные системы: 16 методов каталога "
             "на первом хосте и 17 на втором."),
            ("Метод отвечает не тем, что описано в карточке",
             "Возможно. У всех 33 записей стоит пометка «не проверено», потому что "
             "публичной спеки у ЦРПТ нет. Пути взяты из открытых SDK и надёжны, а глаголы "
             "и параметры нужно подтверждать на живом контуре. Сервер показывает этот "
             "статус в describe_method, чтобы агент не выдавал догадку за факт."),
        ],
        "faq": [
            ("Как получить токен Честного знака?",
             "Нужна квалифицированная электронная подпись. GET /api/v3/true-api/auth/key "
             "отдаёт случайные данные, их подписывают КЭП на своей машине, а "
             "POST /api/v3/true-api/auth/simpleSignIn меняет подпись на токен."),
            ("Закрытый ключ подписи попадает в сервер?",
             "Нет. Подпись делается снаружи, средствами криптопровайдера, сервер получает "
             "уже подписанные данные и работает дальше с токеном."),
            ("Почему методы помечены непроверенными?",
             "Документация ЦРПТ открывается только после входа по КЭП, публичной спеки нет: "
             "/api/v3/true-api/swagger.json отдаёт 401. Поэтому каталог собран по открытым "
             "SDK, и честнее пометить его разведочным, чем выдать за спецификацию."),
            ("Чем ГИС МТ отличается от СУЗ?",
             "ГИС МТ это государственная система мониторинга: сведения о кодах, выгрузки, "
             "маршрут товара. СУЗ это станция управления заказами: заказ кодов на эмиссию и "
             "их статусы. Разные хосты, и в каталоге они разведены."),
        ],
    },
]

CSS = """:root{--bg:#fff;--fg:#16181d;--muted:#5b6472;--line:#e5e8ee;--accent:#2f6feb;--code:#f6f7f9}
@media (prefers-color-scheme:dark){:root{--bg:#12141a;--fg:#e8eaee;--muted:#9aa3b2;--line:#272b35;--accent:#6f9cff;--code:#1a1d25}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:880px;margin:0 auto;padding:32px 20px 64px}
header nav{display:flex;gap:18px;flex-wrap:wrap;font-size:14px;margin-bottom:28px}
a{color:var(--accent)}h1{font-size:30px;line-height:1.25;margin:.2em 0 .4em}
h2{font-size:21px;margin:2em 0 .6em}h3{font-size:17px;margin:1.4em 0 .4em}
.lead{font-size:18px;color:var(--muted)}
code{background:var(--code);padding:2px 5px;border-radius:4px;font-size:.9em}
pre{background:var(--code);padding:14px 16px;border-radius:8px;overflow-x:auto}
pre code{background:none;padding:0}
table{border-collapse:collapse;width:100%;font-size:15px}
.tw{overflow-x:auto;margin:1em 0}table{min-width:520px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line)}
th{font-weight:600;color:var(--muted);font-size:13px;text-transform:uppercase;letter-spacing:.04em}
td.num{text-align:right;font-variant-numeric:tabular-nums}
.cards{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));margin:1em 0}
.card{border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.card h3{margin:0 0 .3em;font-size:16px}.card p{margin:0;color:var(--muted);font-size:14px}
.note{border-left:3px solid var(--accent);padding:2px 0 2px 14px;color:var(--muted)}
.crumbs{font-size:14px;color:var(--muted);margin-bottom:8px}
footer{margin-top:48px;padding-top:20px;border-top:1px solid var(--line);color:var(--muted);font-size:14px}
"""


def marketplace_total() -> int:
    """Сколько методов в соседнем наборе.

    Читаем из его каталогов, когда репозиторий рядом (так делает локальная
    сборка и CI с MCP_NEIGHBOURS_DIR). Когда его нет, берём записанное число:
    цифра на главной важнее, чем падение сборки зонтика из-за соседа.
    """
    root = NEIGHBOURS / "marketplaces-mcp-ru"
    if not root.exists():
        root = NEIGHBOURS / "marketplace-mcp"
    total = 0
    for _, rel, _ in MARKETPLACE_CATALOGS:
        f = root / rel
        if not f.exists():
            return MARKETPLACE_TOTAL_FALLBACK
        total += len(yaml.safe_load(f.read_text(encoding="utf-8"))["endpoints"])
    return total


def methods(n: int) -> str:
    """«133 метода», «45 методов», «21 метод»: числительное на странице должно
    читаться, а не выдавать генератор."""
    tail = n % 100
    if 11 <= tail <= 14:
        word = "методов"
    else:
        word = {1: "метод", 2: "метода", 3: "метода", 4: "метода"}.get(n % 10, "методов")
    return f"{n} {word}"


def esc(s: str) -> str:
    return html.escape(s, quote=False)


def catalog_path(svc: str) -> Path:
    repo = next(p["repo"] for p in PAGES if p["svc"] == svc)
    local = NEIGHBOURS / repo / f"{svc}_mcp" / "endpoints.yaml"
    if local.exists():
        return local
    try:
        module = importlib.import_module(f"{svc}_mcp")
    except ImportError:
        raise SystemExit(
            f"каталог {svc} не найден: нет ни {local}, ни установленного пакета {repo}. "
            f"Склонируйте репозиторий рядом или поставьте пакет."
        )
    return Path(module.__file__).with_name("endpoints.yaml")


def load(svc: str) -> list[dict]:
    return yaml.safe_load(catalog_path(svc).read_text(encoding="utf-8"))["endpoints"]


def section_rows(svc: str) -> tuple[list[tuple[str, int, int, int, int]], int]:
    """Таблица «раздел → методов, чтение, запись, необратимое»."""
    rows_by_section: dict[str, list[dict]] = {}
    for r in load(svc):
        rows_by_section.setdefault(r["section"], []).append(r)

    names = SECTION_NAMES[svc]
    unknown = sorted(set(rows_by_section) - set(names))
    if unknown:
        raise SystemExit(
            f"{svc}: у разделов нет человеческого названия, поправь SECTION_NAMES: "
            + ", ".join(unknown)
        )

    out = []
    for section, rows in rows_by_section.items():
        c = Counter(r["safety"] for r in rows)
        out.append((names[section], len(rows), c["read"], c["write"], c["destructive"]))
    out.sort(key=lambda t: -t[1])
    total = sum(t[1] for t in out)
    assert total == len(load(svc)), "методы потерялись при группировке"
    return out, total


def head(title: str, desc: str, canonical: str, jsonld: dict) -> str:
    """Открывает документ целиком. Без charset страница на кириллице
    превращается в кракозябры всюду, где сервер не подставил заголовок сам."""
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<meta name="yandex-verification" content="d5488a184cbab7f7" /> <!-- pragma: allowlist secret, публичный код подтверждения прав -->
<meta name="description" content="{esc(desc)}" />
<link rel="canonical" href="{canonical}" />
<meta property="og:title" content="{esc(title)}" />
<meta property="og:description" content="{esc(desc)}" />
<meta property="og:url" content="{canonical}" />
<meta property="og:type" content="website" />
<meta property="og:image" content="{SOCIAL}" />
<meta property="og:image:width" content="1280" />
<meta property="og:image:height" content="640" />
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:image" content="{SOCIAL}" />
<title>{esc(title)}</title>
<style>{CSS}</style>
<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>
</head>
<body>
"""


def nav() -> str:
    """Навигация одна на все страницы, и в ней есть ссылка на соседний поддомен.

    Раньше она стояла только в подвале главной: девять серверов, два сайта, и
    человек, пришедший за API Ozon, не узнавал, что есть Диадок. Перелинковка
    односторонней быть не может, обратная ссылка живёт в marketplaces-mcp-ru.
    """
    items = "\n".join(
        f'  <a href="/{p["file"]}">{esc(p["h1"].split(" в ИИ")[0])}</a>' for p in PAGES
    )
    return (f'<header><nav>\n  <a href="/">business-mcp-ru</a>\n{items}\n'
            f'  <a href="{MARKETPLACES}">Маркетплейсы: WB, Ozon, Яндекс, Авито</a>\n'
            f'</nav></header>')


def service_page(p: dict) -> str:
    svc = p["svc"]
    rows, total = section_rows(svc)
    c = Counter(r["safety"] for r in load(svc))
    table = "\n".join(
        f"<tr><td>{esc(n)}</td><td class=num>{m}</td><td class=num>{r}</td>"
        f"<td class=num>{w}</td><td class=num>{d}</td></tr>"
        for n, m, r, w, d in rows
    )
    tasks = "\n".join(f"<li>{esc(t)}</li>" for t in p["tasks"])
    caveat = f'<p class="note">{p["caveat"]}</p>' if p.get("caveat") else ""
    # Заголовки ошибок и вопросов esc-ается, тела нет: там намеренная разметка
    # (<code> вокруг переменных и заголовков), и экранировать её значит
    # напечатать читателю теги.
    errors_html = "\n".join(
        f"<h3>{esc(h)}</h3><p>{body}</p>" for h, body in p["errors"])
    faq_html = "\n".join(f"<h3>{esc(q)}</h3><p>{esc(a)}</p>" for q, a in p["faq"])
    # Три типа в одном @graph: карточка приложения, хлебные крошки и FAQ.
    # Отдельными тегами Google их тоже съест, но графом связь между ними явная.
    jsonld = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "SoftwareApplication",
                "name": p["repo"],
                "applicationCategory": "DeveloperApplication",
                "operatingSystem": "macOS, Windows, Linux",
                "description": p["desc"],
                "url": f'{SITE}/{p["file"]}',
                "offers": {"@type": "Offer", "price": "0", "priceCurrency": "RUB"},
                "softwareVersion": version_of(p["repo"]),
                "license": "https://opensource.org/licenses/MIT",
                "codeRepository": f'https://github.com/ilyautov/{p["repo"]}',
            },
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "business-mcp-ru",
                     "item": SITE + "/"},
                    {"@type": "ListItem", "position": 2, "name": p["h1"],
                     "item": f'{SITE}/{p["file"]}'},
                ],
            },
            {
                "@type": "FAQPage",
                "mainEntity": [
                    {"@type": "Question", "name": q,
                     "acceptedAnswer": {"@type": "Answer", "text": a}}
                    for q, a in p["faq"]
                ],
            },
        ],
    }
    return f"""{head(p["title"] + " | business-mcp-ru", p["desc"], f'{SITE}/{p["file"]}', jsonld)}
<div class="wrap">
{nav()}
<p class="crumbs"><a href="/">business-mcp-ru</a> → {esc(p["h1"])}</p>
<h1>{esc(p["h1"])}</h1>
<p class="lead">{esc(p["desc"])}</p>
{caveat}

<h2>Установка</h2>
<h3>Без терминала</h3>
<p>Скачайте <code>{p["repo"]}-vX.Y.Z.mcpb</code> со <a href="https://github.com/ilyautov/{p["repo"]}/releases/latest">страницы релизов</a> и откройте двойным щелчком. Claude Desktop поставит расширение сам и спросит {MCPB_SECRET[svc]} в отдельном окне, в конфиг лезть не придётся.</p>
<h3>В терминале</h3>
<pre><code>uvx {p["repo"]}</code></pre>
<p>Переменные окружения: <code>{esc(p["env"])}</code>. Ключи можно не держать в
окружении: у сервера есть инструменты управления кабинетами, они кладут ключи в
локальный файл с правами 600.</p>

<h2>Где взять ключ</h2>
<p>{p["keys"]}</p>

<h2>Карта методов: {methods(total)}</h2>
<p>Таблица собрана из того же каталога, который сервер исполняет в рантайме
(источник: {p["source"]}). Класс доступа определяет поведение: чтение идёт сразу,
запись и необратимые действия требуют подтверждения.</p>
<div class="tw"><table>
<thead><tr><th>Раздел</th><th>Методов</th><th>Чтение</th><th>Запись</th><th>Необратимое</th></tr></thead>
<tbody>
{table}
<tr><td><b>Всего</b></td><td class=num><b>{total}</b></td><td class=num><b>{c["read"]}</b></td>
<td class=num><b>{c["write"]}</b></td><td class=num><b>{c["destructive"]}</b></td></tr>
</tbody></table></div>

<h2>Что обычно просят</h2>
<ul>
{tasks}
</ul>

<h2>Как это работает в чате</h2>
<pre><code>{svc}_search_methods("...")   поиск метода словами, а не по имени эндпоинта
{svc}_describe_method(...)   параметры, пагинация, класс доступа
{svc}_call_method(...)       чтение: идёт сразу, без подтверждения
{svc}_write_method(...)      запись: нужен confirm_write
{svc}_delete_method(...)     удаление: нужны оба подтверждения</code></pre>

<h2>Частые ошибки и что они значат</h2>
{errors_html}

<h2>Частые вопросы</h2>
{faq_html}

<footer>
<p>Исходный код: <a href="https://github.com/ilyautov/{p["repo"]}">github.com/ilyautov/{p["repo"]}</a>.
Соседние серверы и общий список: <a href="/">business-mcp-ru</a>. Лицензия MIT. <a href="/privacy.html">Политика конфиденциальности</a>.
Обновлено {TODAY}.</p>
<p>Проект лаборатории <a href="https://aifrontier.tech/">AI Frontier</a>. Остальные инструменты: <a href="https://ilyautov.github.io/">ilyautov.github.io</a>.</p>
</footer>
</div>
</body>
</html>
"""


def index_page() -> str:
    cards = []
    grand = 0
    rows = []
    for p in PAGES:
        n = len(load(p["svc"]))
        grand += n
        c = Counter(r["safety"] for r in load(p["svc"]))
        cards.append(
            f'<div class="card"><h3><a href="/{p["file"]}">{esc(p["h1"].split(" в ИИ")[0])}</a></h3>'
            f'<p>{methods(n)}. {esc(p["card"])}.</p></div>'
        )
        rows.append(
            f'<tr><td><a href="/{p["file"]}">{esc(p["h1"].split(" в ИИ")[0])}</a></td>'
            f'<td class=num>{n}</td><td class=num>{c["read"]}</td><td class=num>{c["write"]}</td>'
            f'<td class=num>{c["destructive"]}</td><td><code>uvx {p["repo"]}</code></td>'
            f'<td><a href="https://github.com/ilyautov/{p["repo"]}/releases/latest">.mcpb</a></td></tr>'
        )
    table = "\n".join(rows)
    mp = marketplace_total()
    total_all = grand + mp

    # Таблица «что нужно, чтобы начать»: у сервисов разная цена входа, и это
    # первое, обо что человек спотыкается. Порядок от простого к сложному.
    access = [
        ("hh.ru", "Аккаунт на dev.hh.ru", "Сразу, бесплатно"),
        ("VK", "Приложение или токен сообщества на dev.vk.com", "Сразу, бесплатно"),
        ("СБИС", "Сотрудник с правами на интеграцию", "Нужен действующий договор с СБИС"),
        ("Диадок", "Письмо в Контур за идентификатором приложения", "Для продуктива нужна лицензия"),
        ("Честный знак", "Квалифицированная электронная подпись", "КЭП и криптопровайдер на машине"),
    ]
    access_html = "\n".join(
        f"<tr><td>{esc(a)}</td><td>{esc(b)}</td><td>{esc(c)}</td></tr>" for a, b, c in access)

    faq = [
        ("Чем это отличается от обёртки над OpenAPI?",
         "Обёртка отдаёт агенту сотни функций и надеется, что он разберётся. Здесь "
         "методы лежат каталогом: поиск словами, у каждого метода описание, "
         "пагинация и класс доступа. Перед записью агент обязан спросить."),
        ("Почему восемнадцать инструментов, а не по одному на метод?",
         f"Потому что {grand} описаний не помещаются в контекст и мешают модели думать. "
         "Сервер показывает 18 инструментов независимо от размера каталога: поиск "
         "метода, карточка метода, отдельно чтение, запись и удаление, работа с "
         "произвольным путём, карта разделов и кабинеты. Каталог при этом "
         "остаётся полным."),
        ("Ключи уходят куда-то на сервер?",
         "Нет. Сервер работает на машине пользователя, ключи лежат локально с "
         "правами 600. У каждого сервера список разрешённых доменов, и заголовок "
         "авторизации не покидает домен сервиса даже при вызове произвольного пути."),
        ("Что мешает агенту удалить что-нибудь важное?",
         "Класс доступа у каждого метода. Чтение идёт сразу, запись и необратимые "
         "действия требуют явного подтверждения. Классы проставлены в каталоге, а не "
         "угадываются по HTTP-глаголу: у VK и СБИС через POST идёт и чтение тоже."),
        ("Нужен ли программист, чтобы это поставить?",
         "Нужна одна команда и ключ сервиса. Сложность не в установке, а в получении "
         "доступа: у hh и VK ключ выдаётся сразу, у Диадока нужна лицензия, у "
         "Честного знака электронная подпись."),
        ("Почему у Честного знака методы помечены непроверенными?",
         "Документация ЦРПТ открывается только после входа по КЭП, публичной спеки "
         "нет. Пути взяты из открытых SDK, и сервер честно показывает этот статус, "
         "вместо того чтобы выдавать догадку за факт."),
        ("Можно поставить только один сервис?",
         "Так и задумано. Каждый сервис это отдельный пакет и отдельная команда "
         "установки: рекрутёру не нужен каталог маркировки, бухгалтеру не нужен "
         "каталог вакансий. Общее у них только ядро, и оно вынесено в отдельный пакет."),
        ("Где серверы для маркетплейсов?",
         f"Wildberries, Ozon, Яндекс Маркет и Авито живут отдельным набором на "
         f"marketplaces-mcp-ru.aifrontier.tech, там ещё {methods(mp)}. Устроены так же, "
         "каталогом и тремя инструментами. По одному маркетплейсу ставятся отдельные "
         "пакеты: ozon-mcp-ru, wildberries-mcp-ru, yandex-market-mcp-ru, avito-mcp-ru."),
        ("С какими клиентами это работает?",
         "С любым, который умеет MCP по stdio: Claude Desktop, Claude Code, Cursor, "
         "VS Code, Codex. Настройка это одна команда и переменные окружения."),
        ("Сколько это стоит?",
         "Серверы бесплатны, лицензия MIT, исходники открыты. Платить может "
         "потребоваться самому сервису: у Диадока лицензия, у Честного знака "
         "электронная подпись."),
    ]
    faq_html = "\n".join(f"<h3>{esc(q)}</h3><p>{esc(a)}</p>" for q, a in faq)
    jsonld = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "SoftwareApplication",
                "name": "business-mcp-ru",
                "applicationCategory": "DeveloperApplication",
                "operatingSystem": "macOS, Windows, Linux",
                "description": (f"Пять MCP-серверов для российских деловых сервисов, "
                                f"{methods(grand)} в каталогах."),
                "url": SITE + "/",
                "offers": {"@type": "Offer", "price": "0", "priceCurrency": "RUB"},
                "softwareVersion": version_of("business-mcp-ru"),
                "license": "https://opensource.org/licenses/MIT",
                "codeRepository": REPO,
                "author": {"@type": "Person", "name": "Илья Утов",
                           "url": "https://github.com/ilyautov"},
            },
            {
                "@type": "FAQPage",
                "mainEntity": [
                    {"@type": "Question", "name": q,
                     "acceptedAnswer": {"@type": "Answer", "text": a}}
                    for q, a in faq
                ],
            },
        ],
    }
    desc = (f"MCP-серверы для российских деловых сервисов: hh.ru, VK, Диадок, "
            f"СБИС и Честный знак. {grand} методов в каталоге, у каждого описание "
            f"и класс доступа. Ставится двойным щелчком или одной командой.")
    return f"""{head("MCP для российского бизнеса: hh.ru, VK, Диадок, СБИС, Честный знак", desc, SITE + "/", jsonld)}
<div class="wrap">
{nav()}
<h1>MCP-серверы для российских деловых сервисов</h1>
<p class="lead">{esc(desc)}</p>

<p>Ставится двумя способами: файлом <code>.mcpb</code> двойным щелчком, без терминала, или одной командой в терминале. Ссылки на бандлы в таблице ниже.</p>
<pre><code>uvx hh-mcp-ru</code></pre>

<h2>Пять сервисов</h2>
<div class="cards">
{chr(10).join(cards)}
</div>

<h2>Что где лежит</h2>
<p>Таблица собрана из тех же каталогов, которые серверы исполняют в рантайме,
поэтому разойтись с кодом она не может. Класс доступа определяет поведение:
чтение идёт сразу, запись и необратимые действия требуют подтверждения.</p>
<div class="tw"><table>
<thead><tr><th>Сервис</th><th>Методов</th><th>Чтение</th><th>Запись</th><th>Необратимое</th><th>Установка</th><th>Бандл</th></tr></thead>
<tbody>
{table}
<tr><td><b>Всего</b></td><td class=num><b>{grand}</b></td><td colspan=5></td></tr>
</tbody></table></div>
<p>Рядом живёт второй набор, под маркетплейсы:
<a href="{MARKETPLACES}">Wildberries, Ozon, Яндекс Маркет и Авито</a>, ещё {methods(mp)}.
Вместе это {methods(total_all)} российских деловых API, разложенных одинаково.</p>

<h2>Зачем каталог, если есть OpenAPI</h2>
<p>Обычный путь это одна функция на эндпоинт. На {grand} методах он ломается:
описания занимают контекст, модель начинает путать похожие методы, а стоимость
запроса растёт на каждом вызове, даже когда нужен один метод из пятисот.</p>
<p>Здесь каталог лежит файлом рядом с сервером, а инструментов всегда 18,
сколько бы методов в каталоге ни было. Агент сначала ищет метод словами, потом
читает его карточку, потом вызывает. Это три шага вместо одного, зато они не
зависят от размера API. Чтение, запись и удаление разведены по разным
инструментам, поэтому чтение идёт без подтверждения, а запись без него не
уходит.</p>
<pre><code>hh_search_methods("статистика зарплат")   поиск словами, не по имени эндпоинта
hh_describe_method(...)                   параметры, пагинация, класс доступа
hh_call_method(...)                       чтение: идёт сразу, без подтверждения
hh_write_method(...)                      запись: нужен confirm_write
hh_delete_method(...)                     удаление: нужны оба подтверждения</code></pre>

<h2>Что нужно, чтобы начать</h2>
<p>Установка одинаковая везде, а вот доступ у сервисов стоит по-разному. Это
первое, обо что спотыкаются, поэтому вот честный порядок от простого к сложному.</p>
<div class="tw"><table>
<thead><tr><th>Сервис</th><th>Что нужно</th><th>Цена входа</th></tr></thead>
<tbody>
{access_html}
</tbody></table></div>

<h2>Безопасность</h2>
<p>Сервер работает на машине пользователя, ключи наружу не уходят. Их можно не
держать в переменных окружения: кабинеты кладут ключи в
<code>~/.ru-mcp/cabinets.json</code> с правами 600, вне репозитория, и ни один
инструмент их не возвращает.</p>
<p>У каждого сервера свой список разрешённых доменов, и заголовок авторизации
не покидает домен сервиса даже при вызове произвольного пути. Класс доступа
проставлен в каталоге, а не угадывается по HTTP-глаголу: у VK все методы идут
через POST, у СБИС тоже, и глагол там не говорит о намерении ничего.</p>

<h2>Частые вопросы</h2>
{faq_html}

<footer>
<p>Исходный код: <a href="{REPO}">{REPO}</a>. Лицензия MIT. <a href="/privacy.html">Политика конфиденциальности</a>. Обновлено {TODAY}.</p>
<p>Маркетплейсы (Wildberries, Ozon, Яндекс Маркет, Авито) живут отдельно:
<a href="{MARKETPLACES}">marketplaces-mcp-ru</a>.</p>
<p>Складской и торговый учёт в МойСкладе: <a href="https://moysklad-mcp-ru.aifrontier.tech/">moysklad-mcp-ru</a>.</p>
<p>Проект лаборатории <a href="https://aifrontier.tech/">AI Frontier</a>. Остальные инструменты: <a href="https://ilyautov.github.io/">ilyautov.github.io</a>.</p>
</footer>
</div>
</body>
</html>
"""


def sitemap() -> str:
    # Политика конфиденциальности редко меняется и веса ей не нужно, но в карте
    # она обязана быть: каталог коннекторов Claude проверяет её доступность.
    urls = ([(SITE + "/", "weekly", "1.0")]
            + [(f'{SITE}/{p["file"]}', "weekly", "0.8") for p in PAGES]
            + [(f"{SITE}/privacy.html", "monthly", "0.3")])
    body = "\n".join(
        f"  <url>\n    <loc>{u}</loc>\n    <lastmod>{TODAY}</lastmod>\n"
        f"    <changefreq>{freq}</changefreq>\n    <priority>{pri}</priority>\n  </url>"
        for u, freq, pri in urls
    )
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{body}\n</urlset>\n")


def robots() -> str:
    return f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="сверить с тем, что на диске, и выйти с 1 при расхождении")
    a = ap.parse_args()

    DOCS.mkdir(exist_ok=True)
    # CNAME рождается из SITE, а не пишется руками: иначе поддомен и sitemap
    # однажды разъедутся, и Pages начнёт отдавать 404 на адрес из бейджей.
    files = {"index.html": index_page(), "sitemap.xml": sitemap(),
             "robots.txt": robots(), "CNAME": DOMAIN + "\n"}
    for p in PAGES:
        files[p["file"]] = service_page(p)

    if a.check:
        # Дату из сравнения выбрасываем: иначе проверка краснеет назавтра после
        # коммита, хотя ничего не разошлось. Ловим расхождение содержимого,
        # а не ход календаря.
        norm = lambda t: DATE_RE.sub("ДАТА", t)
        diff = [n for n, body in files.items()
                if not (DOCS / n).exists()
                or norm((DOCS / n).read_text(encoding="utf-8")) != norm(body)]
        if diff:
            print("расходятся с каталогом:", ", ".join(sorted(diff)))
            sys.exit(1)
        print("страницы совпадают с каталогами")
        return

    for name, body in files.items():
        (DOCS / name).write_text(body, encoding="utf-8")
    print(f"записано: {', '.join(sorted(files))}")


if __name__ == "__main__":
    main()
