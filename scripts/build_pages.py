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
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
# Каталоги уехали в репозитории серверов. Ищем их рядом (обычная раскладка на
# машине), а если папки нет, берём из установленного пакета: так страницу можно
# пересобрать и там, где склонирован только зонтик.
NEIGHBOURS = ROOT.parent
SITE = "https://business-mcp-ru.aifrontier.tech"
REPO = "https://github.com/ilyautov/business-mcp-ru"
TODAY = date.today().isoformat()
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

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
                "статистика зарплат. Установка одной командой, ключ из dev.hh.ru.",
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
<meta name="description" content="{esc(desc)}" />
<link rel="canonical" href="{canonical}" />
<meta property="og:title" content="{esc(title)}" />
<meta property="og:description" content="{esc(desc)}" />
<meta property="og:url" content="{canonical}" />
<meta property="og:type" content="website" />
<title>{esc(title)}</title>
<style>{CSS}</style>
<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>
</head>
<body>
"""


def nav() -> str:
    items = "\n".join(
        f'  <a href="/{p["file"]}">{esc(p["h1"].split(" в ИИ")[0])}</a>' for p in PAGES
    )
    return f'<header><nav>\n  <a href="/">business-mcp-ru</a>\n{items}\n</nav></header>'


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
    jsonld = {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": p["repo"],
        "applicationCategory": "DeveloperApplication",
        "operatingSystem": "macOS, Windows, Linux",
        "description": p["desc"],
        "url": f'{SITE}/{p["file"]}',
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "RUB"},
        "softwareVersion": "0.1.0",
    }
    return f"""{head(p["title"] + " | business-mcp-ru", p["desc"], f'{SITE}/{p["file"]}', jsonld)}
<div class="wrap">
{nav()}
<p class="crumbs"><a href="/">business-mcp-ru</a> → {esc(p["h1"])}</p>
<h1>{esc(p["h1"])}</h1>
<p class="lead">{esc(p["desc"])}</p>
{caveat}

<h2>Установка</h2>
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
{svc}_call_method(...)       вызов; запись спрашивает подтверждение</code></pre>

<footer>
<p>Исходный код: <a href="https://github.com/ilyautov/{p["repo"]}">github.com/ilyautov/{p["repo"]}</a>.
Соседние серверы и общий список: <a href="/">business-mcp-ru</a>. Лицензия MIT.
Обновлено {TODAY}.</p>
</footer>
</div>
</body>
</html>
"""


def index_page() -> str:
    cards = []
    grand = 0
    for p in PAGES:
        n = len(load(p["svc"]))
        grand += n
        cards.append(
            f'<div class="card"><h3><a href="/{p["file"]}">{esc(p["h1"].split(" в ИИ")[0])}</a></h3>'
            f'<p>{methods(n)}. {esc(p["card"])}.</p></div>'
        )
    faq = [
        ("Чем это отличается от обёртки над OpenAPI?",
         "Обёртка отдаёт агенту сотни функций и надеется, что он разберётся. Здесь "
         "методы лежат каталогом: поиск словами, у каждого метода описание, "
         "пагинация и класс доступа. Перед записью агент обязан спросить."),
        ("Ключи уходят куда-то на сервер?",
         "Нет. Сервер работает на машине пользователя, ключи лежат локально с "
         "правами 600. У каждого сервера список разрешённых доменов, и заголовок "
         "авторизации не покидает домен сервиса даже при вызове произвольного пути."),
        ("Почему у Честного знака методы помечены непроверенными?",
         "Документация ЦРПТ открывается только после входа по КЭП, публичной спеки "
         "нет. Пути взяты из открытых SDK, и сервер честно показывает этот статус, "
         "вместо того чтобы выдавать догадку за факт."),
        ("Нужен ли программист, чтобы это поставить?",
         "Нужна одна команда и ключ сервиса. Сложность не в установке, а в получении "
         "доступа: у hh и VK ключ выдаётся сразу, у Диадока нужна лицензия, у "
         "Честного знака электронная подпись."),
    ]
    faq_html = "\n".join(
        f"<h3>{esc(q)}</h3><p>{esc(a)}</p>" for q, a in faq
    )
    jsonld = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": a}}
            for q, a in faq
        ],
    }
    desc = (f"MCP-серверы для российских деловых сервисов: hh.ru, VK, Диадок, "
            f"СБИС и Честный знак. {grand} методов в каталоге, у каждого описание "
            f"и класс доступа. Установка одной командой.")
    return f"""{head("MCP для российского бизнеса: hh.ru, VK, Диадок, СБИС, Честный знак", desc, SITE + "/", jsonld)}
<div class="wrap">
{nav()}
<h1>MCP-серверы для российских деловых сервисов</h1>
<p class="lead">{esc(desc)}</p>

<pre><code>uvx hh-mcp-ru</code></pre>

<h2>Пять сервисов</h2>
<div class="cards">
{chr(10).join(cards)}
</div>

<h2>Частые вопросы</h2>
{faq_html}

<footer>
<p>Исходный код: <a href="{REPO}">{REPO}</a>. Лицензия MIT. Обновлено {TODAY}.</p>
<p>Маркетплейсы (Wildberries, Ozon, Яндекс Маркет, Авито) живут отдельно:
<a href="https://marketplaces-mcp-ru.aifrontier.tech/">marketplaces-mcp-ru</a>.</p>
</footer>
</div>
</body>
</html>
"""


def sitemap() -> str:
    urls = [SITE + "/"] + [f'{SITE}/{p["file"]}' for p in PAGES]
    body = "\n".join(
        f"  <url>\n    <loc>{u}</loc>\n    <lastmod>{TODAY}</lastmod>\n"
        f"    <changefreq>weekly</changefreq>\n    <priority>{'1.0' if i == 0 else '0.8'}</priority>\n  </url>"
        for i, u in enumerate(urls)
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
    files = {"index.html": index_page(), "sitemap.xml": sitemap(), "robots.txt": robots()}
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
