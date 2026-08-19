# ADR-0001: Routing Service — заменяемая абстракция провайдеров маршрутов

- Статус: **accepted**
- Дата: 2026-08-19
- Ветка: feature/routing-providers
- Связано: `.planning/phases/v4-routing/PLAN.md` (M4)

## Контекст

Расчёт маршрутов был жёстко привязан к HERE Routing v8 (backend/routing.py):
один провайдер, один формат ответа, транспортные ключи `car/rail/air/bus/ferry/
bike/foot` захардкожены в моделях HERE. Фронтенд не мог получить маршрут без
HERE-ключа и был неявно связан с HERE-специфичной семантикой (только road
маршруты для всех типов, включая air/rail — некорректно).

## Решение

Ввести **Routing Service** — абстракцию `RoutingProvider` + `RouteResult` и
цепочку провайдеров с фолбэком:

- `backend/routing/base.py` — `RouteResult` (transport, distance_km, duration_min,
  geometry, provider, provider_info), интерфейс `RoutingProvider` и иерархия
  ошибок (`RoutingError` → `ProviderConfigurationError`,
  `ProviderUnavailableError`, `ProviderNoRouteError`, `UnsupportedTransportError`).
- `backend/routing/here.py` — HERE Routing v8 + Matrix v8 (перенесено из
  старого routing.py без изменения поведения; matrix-фолбэк внутри провайдера).
- `backend/routing/osrm.py` — OSRM (профили driving/cycling/walking).
- `backend/routing/graphhopper.py` — GraphHopper (car/bike/foot).
- `backend/routing/fallback.py` — great-circle (Гаверсин + дуга большого круга),
  всегда доступен.
- `backend/routing/factory.py` — сборка цепочки по `ROUTING_PROVIDER_ORDER`
  (`auto` = HERE,OSRM,GRAPHHOPPER,GREAT_CIRCLE), фильтрация ненастроенных
  провайдеров, `ROUTING_FALLBACK_ENABLED` (strict mode при `false`),
  диагностика `describe_providers()`.

`route_segment()` сохраняет обратную совместимость: пайплайн, GeoJSON и БД не
меняют формат; сегменты дополнительно получают `provider` и (при фолбэке)
`provider_fallback`.

Транспортная модель: `TransportType` (CAR/TRAIN/PLANE/WALK/BICYCLE/BUS/FERRY)
со значениями = внутренние ключи (`car/rail/air/foot/bike/bus/ferry`), поэтому
сохранённые маршруты и GeoJSON совместимы. `coerce_transport()` принимает и
`"CAR"`, и `"train"`; неизвестный тип → 422 в API.

Новый API: `POST /api/routes` (расчёт по координатам без сохранения) и
`GET /api/providers` (диагностика цепочки). Фронтенд: узор линии по типу
транспорта (dasharray match), провайдер в карточке сегмента и в сводке.

## Последствия

Плюсы:

- Провайдер подключается добавлением одного модуля в `backend/routing/` и
  одной строки в `factory._provider_available/_make_provider` + документации.
- Фронтенд не знает о провайдерах; GeoJSON несёт `provider` только для
  диагностики.
- Без внешних ключей приложение полностью работоспособно (great-circle).
- HERE не удалён: его логика изолирована за абстракцией.

Минусы/риски:

- OSRM/GraphHopper покрывают только surface-транспорт; air/rail всегда идут
  через great-circle (авиа- и ж/д-роутинга в открытых API нет) — это осознанный
  честный фолбэк, а не имитация дорожного маршрута.
- Публичные демо-серверы OSRM/GraphHopper не гарантируют SLA — при продакшене
  нужны self-hosted инстансы.
- Strict mode (`ROUTING_FALLBACK_ENABLED=false`) ломает старую гарантию
  «всегда есть результат» — это намеренное поведение для жёсткой диагностики.
