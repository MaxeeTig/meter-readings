# Mosenergosbyt portal — трассировка запросов (auth + API)

**Цель:** воспроизвести отправку показаний на уровне HTTP (токен, cookie, вызовы API).

## Шаг 1. Захват запросов при авторизации

1. Откройте https://my.mosenergosbyt.ru/auth в Chrome или Firefox.
2. Откройте DevTools: **F12** → вкладка **Network** (Сеть).
3. Включите **Preserve log** (Сохранять журнал).
4. При необходимости нажмите **Clear** (Очистить), затем выполните вход шаг за шагом (логин, пароль, СМС/подтверждение — как у вас на портале).
5. После успешного входа не закрывайте вкладку и не очищайте Network.

## Что сохранить для анализа

- **HAR-файл:** в Network → правый клик по списку запросов → **Save all as HAR with content** → сохраните как `auth-trace.har` в `docs/` или пришлите фрагменты.
- Либо выберите и скопируйте в этот файл (в секции ниже) ключевые запросы:
  - первый запрос на `/auth` (GET/POST);
  - запрос, после которого появляется успешный вход (логин/пароль, возможно отдельно 2FA);
  - ответы с **Set-Cookie**, **Authorization**, или телом с `token`/`access_token`/`session`.

## Зафиксированные данные (по HAR)

### 1. Авторизация (логин)

- **URL:** `POST https://my.mosenergosbyt.ru/gate_lkcomu?action=auth&query=login`
- **Content-Type:** `application/x-www-form-urlencoded`
- **Тело запроса (form):**
  - `login` — номер телефона/ЛК (например 9161514707)
  - `psw` — пароль
  - `vl_device_info` — JSON строка: `{"appver":"1.42.0","type":"browser","userAgent":"..."}`
  - `vl_tfa_device_token` — UUID устройства (можно генерировать один раз и хранить)
- **Ответ:** JSON, в `data[0].session` приходит **session token** (строка, например `IYQOG3OZSX6LS7BVZSPLQW-FS-6OFVQ8S5C46CB6`). При успехе `success: true`, `kd_result: 0`.

**Для воспроизведения на уровне HTTP:** один POST на этот URL с телом — получаем в ответе `session`; заголовки `Origin: https://my.mosenergosbyt.ru`, `Referer: https://my.mosenergosbyt.ru/auth` желательны.

### 2. Сессия и последующие API-вызовы

- **Токен:** строка `session` из ответа логина. В запросах передаётся **в query**: `session=<token>`.
- **Базовый паттерн:** `POST https://my.mosenergosbyt.ru/gate_lkcomu?action=sql&query=<QueryName>&session=<SESSION_TOKEN>`
- Тело: обычно `application/x-www-form-urlencoded`; для многих запросов пустое (например `Init`, `MenuSettings`, `LSList`).

Примеры `query` из трассы: `Init`, `MenuSettings`, `NoticeRoutine`, `GetAdElementsPopUp`, `GetProfileShowOnboarding`, `CheckNeedPhoneConfirm`, `GetCriticalNotice`, `LSList`, `GetPaspDetailsFailed`, `GetMultipleLSPayVisibility`, `GetSectionElementsDtCache`, `GetPowSupProviders`, `GetProfileAttributesValues`, `CrmGetPowerSupplyContractHist`, `PowerSupplyInfoVisibility`, `LSListEditable`.

### 3. Куки (из скриншотов)

- Для **портала** важна сессия в URL (`session=...`); куки с ваших скриншотов:
  - **Портал/сессия:** `session-cookie` (вероятно дублирует или дополняет `session` в URL).
  - **Сторонние (для воспроизведения не обязательны):** Google (`SID`, `HSID`, `NID`, `SAPISID`, `SIDCC`, `SSID`, `APISID`, `_Secure-*`), Yandex (`yandexuid`, `yabs-sid`, `yashr`, `ymex`, `yuidss`, `_ym_*`, `_yasc`). Используются для аналитики/рекапчи.
- Для скриптового воспроизведения достаточно: **получить `session` из ответа логина и подставлять в URL** всех вызовов `gate_lkcomu`.

### 4. Следующий шаг

- Найти в портале или в следующей трассе вызов, который **отправляет показания** (поиск по названию раздела «Показания» / «Передача показаний» в UI или по новому HAR с действием «отправить»).
- Записать его `query=...` и тело POST — тогда можно будет описать отправку показаний на уровне HTTP. 
