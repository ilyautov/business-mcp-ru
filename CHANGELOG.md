# Changelog

## [0.1.0] — 2026-09-11

Зонтик над пятью серверами. Кода здесь нет: пакет ставит пять серверов одной
строкой, репозиторий держит страницы сайта и общий список.

- пять серверов разъехались по своим репозиториям: [hh-mcp-ru], [vk-mcp-ru],
  [diadoc-mcp-ru], [sbis-mcp-ru], [chestny-znak-mcp-ru];
- ядро вынесено в пакет [schema-mcp-core], серверы делят его, а не копируют;
- страницы `docs/` собираются из каталогов соседних репозиториев, режим
  `--check` в CI падает при расхождении.

[hh-mcp-ru]: https://github.com/ilyautov/hh-mcp-ru
[vk-mcp-ru]: https://github.com/ilyautov/vk-mcp-ru
[diadoc-mcp-ru]: https://github.com/ilyautov/diadoc-mcp-ru
[sbis-mcp-ru]: https://github.com/ilyautov/sbis-mcp-ru
[chestny-znak-mcp-ru]: https://github.com/ilyautov/chestny-znak-mcp-ru
[schema-mcp-core]: https://github.com/ilyautov/schema-mcp-core
