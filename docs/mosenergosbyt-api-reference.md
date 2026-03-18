# Mosenergosbyt portal — API reference (HTTP-level)

По результатам разбора `mosenergosbyt-auth-trace.har`, `mosenergosbyt-auth-trace_readings.har`, `mosenergosbyt-auth-trace_readings_submit_hot_water.har` (отправка показаний ГВС, 14.03.2026) и `my.mosenergosbyt.ru_otp_auth.har` (OTP при входе с нового устройства). Для воспроизведения запросов из скрипта (curl, Python requests и т.д.).

---

## Straightforward flow: authorize → get list of meters

Минимальная последовательность для одного скрипта: авторизация и получение списка счётчиков без отправки показаний.

### Flow overview

| Step | Purpose | Required |
|------|---------|----------|
| 1 | **Login** | Yes — get `session` (and optionally `id_profile`) |
| 2 | **Init** | Recommended — portal does it right after login |
| 3 | **LSList** or **LSListEditable** | Yes — get accounts; each has `id_abonent` for step 4 |
| 4 | **smorodinaTransProxy** (AbonentEquipment) | Yes — get list of meters per account |
| 5 | **AbonentSaveIndication** | For submitting readings — one request per meter/reading (see §4) |

Calls from section 2 such as `MenuSettings`, `GetSectionMetadata`, `GetSectionElementsDtCache`, `IndicationIsFloat`, `GetPowSupProviders`, `GetProfileAttributesValues`, etc. are used by the portal for UI (menu, form metadata, cache, float-indication check) and are **not required** just to authorize and get the list of meters.

### Parameters to store in a single script

| Where | Parameter | Use |
|-------|------------|-----|
| **Login response** | `session` | Add to every subsequent request: `?action=sql&query=...&session=<SESSION>` |
| **Login response** | `id_profile` | Optional; useful for logging or future APIs; required for OTP flow (SendTfa) |
| **Login response** | `vl_tfa_device_token` | After OTP login or first login without OTP: store and send on next login to avoid OTP (see §1.1) |
| **LSList / LSListEditable response** | For each account: `id_abonent` | Pass as `vl_provider={"id_abonent": <id_abonent>}` to AbonentEquipment |
| **AbonentEquipment response** | `data[]` | List of meters; each has `id_counter`, `id_service`, `nn_ind_receive_start`, `nn_ind_receive_end`, etc. |

### Step-by-step

**1. Authorize (login)**

- `POST /gate_lkcomu?action=auth&query=login` with body: `login`, `psw`, `vl_device_info`, `vl_tfa_device_token`.
- From response: `data[0].session` → **SESSION**, optionally `data[0].id_profile` → **ID_PROFILE**.

**2. Init (recommended)**

- `POST /gate_lkcomu?action=sql&query=Init&session=<SESSION>`.
- Body: empty. No parameters to store; just establishes session for SQL API.

**3. Get accounts (LS list)**

- `POST /gate_lkcomu?action=sql&query=LSList&session=<SESSION>`.
- Body: empty.
- Response: `data` = array of accounts. When non-empty, each account object is expected to contain **id_abonent** (and possibly an id used in the portal URL, e.g. for `/accounts/<id>/transfer-indications`). Store each **id_abonent** for step 4.

  If `LSList` returns empty, try **LSListEditable** the same way (`query=LSListEditable`, empty body); use its `data[]` and **id_abonent** the same way.

**4. Get list of meters (per account)**

- For each **id_abonent** from step 3:
  - `POST /gate_lkcomu?action=sql&query=smorodinaTransProxy&session=<SESSION>`.
  - Body (form):  
    `plugin=smorodinaTransProxy`  
    `proxyquery=AbonentEquipment`  
    `vl_provider=<URL-encoded JSON>` where JSON is `{"id_abonent": <id_abonent>}`.
- Response: `data` = array of meter objects (see section 3.4 below for fields). No extra intermediate parameters needed for “list only”; store the meter list as needed.

**Optional (not needed for “authorize + list meters”)**

- **GetSectionMetadata** — form metadata for “transfer indications” UI (e.g. labels, patterns). Uses `kd_provider`, `kd_section`, `nm_service=AbonentEquipment`; needed only when building the submit form.
- **GetSectionElementsDtCache** — cache invalidation by section; not needed for listing meters.
- **IndicationIsFloat** — whether a service accepts decimal indications; needs `id_service` (per meter). Useful when submitting, not for listing.

---

## Base URL

```
https://my.mosenergosbyt.ru
```

## 1. Login (получение session)

**Request**

```http
POST /gate_lkcomu?action=auth&query=login HTTP/1.1
Host: my.mosenergosbyt.ru
Content-Type: application/x-www-form-urlencoded
Origin: https://my.mosenergosbyt.ru
Referer: https://my.mosenergosbyt.ru/auth

login=<PHONE_OR_ACCOUNT>&psw=<PASSWORD>&vl_device_info=<ESCAPED_JSON>&vl_tfa_device_token=<UUID>
```

- `vl_device_info` — URL-encoded JSON, например:  
  `{"appver":"1.42.0","type":"browser","userAgent":"Mozilla/5.0 (...)"}`
- `vl_tfa_device_token` — UUID устройства (опционально). Если передан и принят сервером — логин без OTP. Если не передан или не распознан — сервер возвращает `kd_result: 1053` и запрашивает OTP (см. раздел 1.1). После успешного OTP-логина в ответе приходит новый токен — его нужно сохранить и передавать при следующих входах.

**Response (200, JSON)**

```json
{
  "success": true,
  "total": 1,
  "data": [{
    "kd_result": 0,
    "nm_result": "Ошибок нет",
    "id_profile": "<uuid>",
    "session": "IYQOG3OZSX6LS7BVZSPLQW-FS-6OFVQ8S5C46CB6"
  }]
}
```

Сессию для дальнейших запросов берём из `data[0].session`.

**Когда портал запрашивает OTP (новое устройство):** если при логине не передан или не принят сервером `vl_tfa_device_token`, ответ будет с `kd_result: 1053` (без сессии), и в ответе появятся поля для двухфакторной проверки. См. раздел 1.1 ниже.

---

## 1.1. Вход с нового устройства (OTP / TFA)

По трассе `my.mosenergosbyt.ru_otp_auth.har`: при первом входе с устройства, для которого нет сохранённого `vl_tfa_device_token`, портал возвращает запрос на подтверждение по коду (SMS, flashcall или e-mail). Последовательность вызовов и параметры ниже.

### Что приводит к запросу OTP?

| Фактор | Роль |
|--------|------|
| **vl_tfa_device_token** | **Основной.** Если параметр не передан или токен не распознан сервером (новое устройство, очищенное хранилище), сервер возвращает `kd_result: 1053` и требует OTP. После успешного ввода кода в ответе приходит новый `vl_tfa_device_token` — его нужно сохранить и передавать при следующих логинах с этого устройства. |
| **vl_device_info (браузер)** | Может использоваться для отпечатка устройства. Резкое изменение (другой userAgent/тип устройства) при том же логине может дополнительно влиять на решение о запросе OTP; в трассе OTP-сценария токен не передавался вовсе. Для скриптов: при повторном использовании одного и того же `vl_tfa_device_token` разумно сохранять тот же `vl_device_info`. |

Итог: к запросу OTP приводит в первую очередь **отсутствие или невалидность `vl_tfa_device_token`**; изменение только браузерных параметров при сохранённом токене в этой трассе не проверялось.

### Шаг 1. Первый login (без сессии, без device token)

Запрос как в разделе 1, но **без** `vl_tfa_device_token` (или с неизвестным токеном).

```http
POST /gate_lkcomu?action=auth&query=login HTTP/1.1
Host: my.mosenergosbyt.ru
Content-Type: application/x-www-form-urlencoded
Origin: https://my.mosenergosbyt.ru
Referer: https://my.mosenergosbyt.ru/auth

login=<PHONE_OR_ACCOUNT>&psw=<PASSWORD>&vl_device_info=<ESCAPED_JSON>
```

**Ответ (200, OTP требуется):**

```json
{
  "success": true,
  "total": 1,
  "data": [{
    "kd_result": 1053,
    "nm_result": "Уважаемый клиент! Мы сделали личный кабинет еще безопаснее...",
    "id_profile": "<uuid>",
    "cnt_auth": 0,
    "new_token": null,
    "pr_change_method_tfa": true,
    "method_tfa": [
      { "kd_tfa": 1, "nm_tfa": "flashcall", "pr_active": true, "nn_contact": "7916***4707" },
      { "kd_tfa": 2, "nm_tfa": "sms", "pr_active": false, "nn_contact": "7916***4707" },
      { "kd_tfa": 3, "nm_tfa": "e-mail", "pr_active": false, "nn_contact": "*****20@yandex.ru" }
    ],
    "vl_tfa_auth_token": "636db36e-ac69-4272-8824-3cee09babb02",
    "vl_tfa_device_token": null,
    "pr_show_captcha": null
  }]
}
```

Сохранить из ответа: **id_profile**, **vl_tfa_auth_token**. По **method_tfa** выбрать способ доставки кода и соответствующий **kd_tfa** (1 — flashcall, 2 — sms, 3 — e-mail).

### Шаг 2. Отправка кода (SendTfa)

Вызов **без** сессии (пользователь ещё не авторизован). Отправляет код на выбранный канал.

```http
POST /gate_lkcomu?action=sql&query=SendTfa HTTP/1.1
Host: my.mosenergosbyt.ru
Content-Type: application/x-www-form-urlencoded
Origin: https://my.mosenergosbyt.ru
Referer: https://my.mosenergosbyt.ru/auth

id_profile=<ID_PROFILE>&kd_tfa=<KD_TFA>&vl_tfa_auth_token=<VL_TFA_AUTH_TOKEN>
```

| Параметр | Значение |
|----------|----------|
| id_profile | Из ответа шага 1 (`data[0].id_profile`) |
| kd_tfa | 1 = flashcall, 2 = sms, 3 = e-mail |
| vl_tfa_auth_token | Из ответа шага 1 (`data[0].vl_tfa_auth_token`) |

**Ответ (200):**

```json
{
  "success": true,
  "total": 1,
  "data": [{
    "kd_result": 0,
    "nm_result": "На Ваш телефон выслан код подтверждения",
    "nn_suop_session": 41320876,
    "vl_tfa_auth_token": "b6bcaf73-484b-40cd-8210-54350074d8cb",
    "vl_timeout": 60
  }]
}
```

При необходимости можно использовать обновлённый **vl_tfa_auth_token** из этого ответа (в трассе второй login использовался токен с шага 1 — поведение может зависеть от таймингов).

### Шаг 3. Повторный login с кодом OTP

Тот же URL логина, в теле добавляются код и способ TFA. **vl_tfa_device_token** по-прежнему не передаётся.

```http
POST /gate_lkcomu?action=auth&query=login HTTP/1.1
Host: my.mosenergosbyt.ru
Content-Type: application/x-www-form-urlencoded
Origin: https://my.mosenergosbyt.ru
Referer: https://my.mosenergosbyt.ru/auth

login=<PHONE>&psw=<PASSWORD>&vl_device_info=<ESCAPED_JSON>&nn_tfa_code=<CODE>&kd_tfa=<KD_TFA>
```

| Параметр | Значение |
|----------|----------|
| nn_tfa_code | Код из SMS / flashcall / e-mail (например 4621) |
| kd_tfa | Тот же, что в SendTfa (2 для sms) |

**Ответ при успехе (200):**

```json
{
  "success": true,
  "total": 1,
  "data": [{
    "kd_result": 0,
    "nm_result": "Ошибок нет",
    "id_profile": "<uuid>",
    "session": "AECGFWEA9IMJBDPE3HHBT-KCGRE6OVE4S5C570ED",
    "vl_tfa_device_token": "dff3fd9f-af47-4583-87e9-dcb33cdee951",
    "vl_tfa_auth_token": null,
    "pr_change_method_tfa": null,
    "method_tfa": null,
    "pr_show_captcha": null
  }]
}
```

Из ответа сохранить: **session** для последующих запросов и **vl_tfa_device_token** для следующих логинов с этого устройства (передавать в запросе login как в разделе 1), чтобы не запрашивать OTP каждый раз.

### Дополнительно после входа (по трассе)

После успешного OTP-логина портал вызывает, в частности:

- `CheckNeedPhoneConfirm` — `POST /gate_lkcomu?action=sql&query=CheckNeedPhoneConfirm&session=<SESSION>`, тело пустое. Ответ: `pr_need_phone_confirm: false`.

---

## 2. API после входа (action=sql)

Все вызовы — POST, сессия передаётся в query.

**Pattern**

```http
POST /gate_lkcomu?action=sql&query=<QueryName>&session=<SESSION_TOKEN> HTTP/1.1
Host: my.mosenergosbyt.ru
Content-Type: application/x-www-form-urlencoded
Referer: https://my.mosenergosbyt.ru/auth
```

Тело — при необходимости, form-urlencoded (для многих запросов пустое).

**Для сценария «авторизация + список счётчиков» нужны только:**

- **Init** — инициализация сессии после логина.
- **LSList** или **LSListEditable** — получить список ЛС и `id_abonent` по каждому.
- **smorodinaTransProxy** (proxyquery=AbonentEquipment) — список приборов учёта по `id_abonent`.

Остальные вызовы из таблицы ниже используются порталом для меню, форм, кэша и уведомлений и для получения списка счётчиков не обязательны.

**Примеры query из трассы (полный перечень)**

| query | Назначение (по контексту) | Нужен для «auth + список счётчиков»? |
|-------|---------------------------|--------------------------------------|
| Init | Инициализация сессии | Да (рекомендуется) |
| LSList | Список ЛС (лицевых счетов) | Да |
| LSListEditable | Редактируемый список ЛС | Да (если LSList пустой) |
| smorodinaTransProxy (AbonentEquipment) | Список счётчиков по id_abonent | Да |
| MenuSettings | Настройки меню | Нет |
| GetProfileAttributesValues | Атрибуты профиля | Нет |
| GetPowSupProviders | Поставщики электроэнергии | Нет |
| GetSectionElementsDtCache | Кэш элементов разделов | Нет |
| GetSectionMetadata | Метаданные секции (форма показаний и др.) | Нет |
| IndicationIsFloat | Признак дробных показаний по id_service | Нет (для отправки — да) |
| AbonentSaveIndication | Отправка показаний по счётчику | Да (для submit) |
| GetCriticalNotice | Критические уведомления | Нет |
| SendTfa | Отправка кода OTP (SMS/flashcall/e-mail) при входе с нового устройства | Да (в сценарии OTP, без session) |
| CheckNeedPhoneConfirm | Проверка необходимости подтверждения телефона | Нет |
| ... | см. portal-trace-guide.md | — |

---

## 3. Раздел «Передать показания» (список счётчиков и период приёма)

По трассе `mosenergosbyt-auth-trace_readings.har` (переход в меню «Передать показания»; период приёма может быть ещё не открыт). Порядок вызовов и полезные данные:

### 3.1 GetSectionMetadata

Метаданные секции формы (поля, шаблоны подписей ПУ).

```http
POST /gate_lkcomu?action=sql&query=GetSectionMetadata&session=<SESSION>
Content-Type: application/x-www-form-urlencoded

kd_provider=2&kd_section=11&nm_service=AbonentEquipment
```

### 3.2 GetSectionElementsDtCache

Время последнего изменения кэша секции (для инвалидации).

```http
POST /gate_lkcomu?action=sql&query=GetSectionElementsDtCache&session=<SESSION>

kd_section=25
```

### 3.3 IndicationIsFloat

Проверка, принимает ли счётчик дробные показания (для конкретного типа услуги).

```http
POST /gate_lkcomu?action=sql&query=IndicationIsFloat&session=<SESSION>

id_service=23868602
```

**Ответ:** `{"success":true,"data":[{"pr_float":true}]}` — если `pr_float: true`, показание можно передавать с дробной частью.

### 3.4 smorodinaTransProxy (proxyquery=AbonentEquipment) — список счётчиков

Возвращает список приборов учёта и период приёма показаний.

```http
POST /gate_lkcomu?action=sql&query=smorodinaTransProxy&session=<SESSION>

plugin=smorodinaTransProxy&proxyquery=AbonentEquipment&vl_provider=%7B%22id_abonent%22%3A%209439925%7D
```

`vl_provider` — URL-encoded JSON: `{"id_abonent": 9439925}` (id абонента, из контекста ЛК).

**Ответ:** массив объектов по одному на счётчик. Ключевые поля:

| Поле | Описание |
|------|----------|
| id_counter | ID счётчика (нужен для отправки показания) |
| id_pu | ID прибора учёта |
| id_service | ID услуги (для IndicationIsFloat и, возможно, для submit) |
| nm_counter, nm_factory | Наименование счётчика |
| nm_service | Тип услуги (например «ГОРЯЧЕЕ В/С (НОСИТЕЛЬ)») |
| nm_measure_unit | Единица измерения (м³ и т.д.) |
| vl_indication / vl_last_indication | Текущее/последнее переданное показание |
| dt_indication / dt_last_indication | Дата показания |
| **nn_ind_receive_start** | День начала приёма показаний (число месяца, например 14) |
| **nn_ind_receive_end** | День окончания приёма (например 19) |
| id_billing_counter | ID в биллинге |
| pr_state, nm_no_access_reason | Доступность передачи (если нет доступа — причина в nm_no_access_reason) |

**Период приёма:** приём разрешён только с `nn_ind_receive_start` по `nn_ind_receive_end` число каждого месяца. Если текущая дата вне этого интервала, кнопка отправки неактивна («срок для приёма ещё не наступил» или уже прошёл).

---

## 4. Отправка показаний (submit) — AbonentSaveIndication

По трассе `mosenergosbyt-auth-trace_readings_submit_hot_water.har` (14.03.2026): отправка выполняется отдельным запросом **AbonentSaveIndication**. Один запрос — одно показание по одному счётчику; для нескольких счётчиков нужны отдельные вызовы.

### 4.1 Запрос

```http
POST /gate_lkcomu?action=sql&query=AbonentSaveIndication&session=<SESSION> HTTP/1.1
Host: my.mosenergosbyt.ru
Content-Type: application/x-www-form-urlencoded
Origin: https://my.mosenergosbyt.ru
Referer: https://my.mosenergosbyt.ru/accounts/<id_service>/transfer-indications

dt_indication=<ISO_DATETIME>&id_counter=<ID_COUNTER>&id_counter_zn=<ID_COUNTER_ZN>&id_source=<ID_SOURCE>&plugin=propagateMoeInd&pr_skip_anomaly=0&pr_skip_err=0&vl_indication=<VALUE>&vl_provider=<URL_ENCODED_JSON>
```

**Тело (form-urlencoded):**

| Параметр | Описание | Пример (из трассы) |
|----------|----------|---------------------|
| dt_indication | Дата/время показания (ISO 8601, с таймзоной) | `2026-03-14T08:59:59+03:00` |
| id_counter | ID счётчика (из AbonentEquipment) | `35738177` |
| id_counter_zn | Значение счётчика/зоны (из AbonentEquipment, обычно `"1"`) | `1` |
| id_source | ID источника/секции формы (из метаданных портала) | `15418` |
| plugin | Фиксированное значение | `propagateMoeInd` |
| pr_skip_anomaly | Проверка аномалий (0 = проверять) | `0` |
| pr_skip_err | Проверка ошибок (0 = проверять) | `0` |
| vl_indication | Передаваемое показание (число, целое или дробное по IndicationIsFloat) | `368` |
| vl_provider | URL-encoded JSON: `{"id_abonent": <id_abonent>}` | `%7B%22id_abonent%22%3A%209439925%7D` |

Все перечисленные параметры в трассе присутствовали; `id_source` может зависеть от поставщика/секции (в трассе — ГВС, МосОблЕИРЦ).

### 4.2 Ответ при успехе (200, JSON)

```json
{
  "success": true,
  "total": 1,
  "data": [{
    "kd_result": 1000,
    "nm_result": "Показания успешно переданы"
  }],
  "metaData": { "responseTime": 0.033 }
}
```

- **kd_result: 1000** — успешная передача показаний.
- **nm_result** — текст сообщения для пользователя.

### 4.3 Порядок вызовов для submit

1. **Login** → **Init** → **LSList** (или LSListEditable) → **smorodinaTransProxy** (AbonentEquipment) — как в разделе «Straightforward flow», чтобы получить `id_abonent` и список счётчиков с `id_counter`, `id_counter_zn`.
2. При необходимости: **GetSectionMetadata** (для меток/валидации формы), **IndicationIsFloat** (чтобы знать, допускаются ли дробные показания).
3. **AbonentSaveIndication** — для каждого счётчика и каждого передаваемого показания, с телом по п. 4.1.
4. После успешной отправки портал может повторно вызвать **smorodinaTransProxy** (AbonentEquipment), чтобы обновить список (в т.ч. последнее показание).

Передавать показания можно только в период приёма: с `nn_ind_receive_start` по `nn_ind_receive_end` число месяца (см. раздел 3.4).

---

## 5. Пример: curl (flow «авторизация + список счётчиков»)

```bash
# 1) Login — получаем SESSION (и при необходимости id_profile)
SESSION=$(curl -s -X POST 'https://my.mosenergosbyt.ru/gate_lkcomu?action=auth&query=login' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -H 'Origin: https://my.mosenergosbyt.ru' \
  -H 'Referer: https://my.mosenergosbyt.ru/auth' \
  -d 'login=PHONE&psw=PASSWORD&vl_device_info=%7B%22appver%22%3A%221.42.0%22%2C%22type%22%3A%22browser%22%7D&vl_tfa_device_token=1ecfd14d-7636-4fe3-a52c-6d9a4fda0ba3' \
  | jq -r '.data[0].session')

# 2) Init — инициализация сессии
curl -s -X POST "https://my.mosenergosbyt.ru/gate_lkcomu?action=sql&query=Init&session=$SESSION" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -H 'Referer: https://my.mosenergosbyt.ru/auth'

# 3) LSList — список ЛС; из data[] брать id_abonent по каждому счёту
curl -s -X POST "https://my.mosenergosbyt.ru/gate_lkcomu?action=sql&query=LSList&session=$SESSION" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -H 'Referer: https://my.mosenergosbyt.ru/auth' \
  | jq '.data'

# 4) Список счётчиков по одному id_abonent (подставить ID_ABONENT из шага 3)
ID_ABONENT=9439925
VL_PROVIDER=$(echo "{\"id_abonent\": $ID_ABONENT}" | jq -sRr @uri)
curl -s -X POST "https://my.mosenergosbyt.ru/gate_lkcomu?action=sql&query=smorodinaTransProxy&session=$SESSION" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -H 'Referer: https://my.mosenergosbyt.ru/auth' \
  -d "plugin=smorodinaTransProxy&proxyquery=AbonentEquipment&vl_provider=$VL_PROVIDER" \
  | jq '.data'
```

После шага 4 в `data` — массив счётчиков (поля см. в разделе 3.4). Для нескольких ЛС шаг 4 повторять для каждого `id_abonent` из шага 3.

**Отправка одного показания (после шагов 1–4):**

```bash
# Переменные: SESSION, ID_ABONENT, id_counter, id_counter_zn, vl_indication, id_source (из метаданных/трассы — напр. 15418)
VL_PROVIDER=$(echo "{\"id_abonent\": $ID_ABONENT}" | jq -sRr @uri)
DT_INDICATION=$(date -Iseconds)   # или фиксированная дата в периоде приёма
curl -s -X POST "https://my.mosenergosbyt.ru/gate_lkcomu?action=sql&query=AbonentSaveIndication&session=$SESSION" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -H 'Referer: https://my.mosenergosbyt.ru/accounts/23868602/transfer-indications' \
  -d "dt_indication=$DT_INDICATION&id_counter=35738177&id_counter_zn=1&id_source=15418&plugin=propagateMoeInd&pr_skip_anomaly=0&pr_skip_err=0&vl_indication=368&vl_provider=$VL_PROVIDER" \
  | jq .
# Успех: data[0].kd_result == 1000, nm_result "Показания успешно переданы"
```

---

## 6. Example response dumps (real test run)

Ниже — пример вывода реального тестового скрипта (авторизация + список ЛС + список счётчиков). Нужен для проверки формата ответов и полей. Сессия одноразовая, в примере приведена только для наглядности.

**Login + Init**

```
Authorization successful!
Session: 7ZCUJI73LOKYB9TVUBWITRP6MIES60SYS5C53MFD
Profile ID: 61bbf663-9cba-4bf6-995c-14c8c2de2631
Session initialized successfully.
```

**LSList (accounts)**

```
Accounts list retrieved successfully.
Found accounts: [
  {
    "nn_ls": "82955422",
    "nm_street": "УЛ НЕКРАСОВА, д.2, кв.175",
    "nm_ls_group_full": "143968, МОСКОВСКАЯ ОБЛ., ...",
    "nm_type": "ЕПД",
    "nm_provider": "ООО \"МосОблЕИРЦ\"",
    "kd_provider": 2,
    "vl_provider": "{\"id_abonent\": 9439925}",
    "id_service": 23868602,
    "nm_ls_group": "УЛ НЕКРАСОВА, д.2, кв.175",
    "data": { "id_tu": 18978, "nm_street": "...", "nn_ls_disp": "82955422", "KD_LS_OWNER_TYPE": 1 },
    "pr_ls_group_edit": true,
    "nm_lock_msg": null,
    "kd_status": 1,
    "kd_service_type": 2,
    "nm_ls_description": null,
    "pr_power_dis": false
  }
]
```

Для шага 4 «список счётчиков» из каждой записи берём **id_abonent**: он может быть в поле `vl_provider` (строка с JSON `{"id_abonent": 9439925}`) или в отдельном поле — в этом примере из `vl_provider` получаем `9439925`. Поле **id_service** (23868602) совпадает с id в URL портала `/accounts/23868602/transfer-indications`.

**AbonentEquipment (meters for id_abonent=9439925)**

```
Meters list for account 9439925 retrieved successfully.
Meters for account 82955422 (id_abonent=9439925):
```

| Поле | Счётчик 1 (ГВС) | Счётчик 2 (ХВС) |
|------|------------------|------------------|
| id_counter | 35738177 | 31039410 |
| id_pu | 125885 | 165127 |
| nm_counter / nm_factory | Г 49065 | Х 24692 |
| id_service | 3740 | 29508 |
| nm_service | ГОРЯЧЕЕ В/С (НОСИТЕЛЬ) | ХОЛОДНОЕ В/С |
| nm_pu | ООО «Р-СЕТЕВАЯ КОМПАНИЯ» (дог. 812680320) | МУП «Реутовский водоканал» |
| nm_measure_unit | м3 | куб. м. |
| vl_indication / vl_last_indication | 364 | 522 |
| dt_indication / dt_last_indication | 2026-02-15 00:00:00.0 | 2026-02-15 00:00:00.0 |
| nn_ind_receive_start | 14 | 14 |
| nn_ind_receive_end | 19 | 19 |
| id_billing_counter | 3100014511975 | 3100014511974 |
| pr_state | 1 | 1 |

Полный JSON одного счётчика (для справки):

```json
{
  "id_counter": 35738177,
  "id_pu": 125885,
  "nm_counter": "Г 49065",
  "id_indication": null,
  "vl_indication": 364,
  "dt_indication": "2026-02-15 00:00:00.0",
  "id_counter_zn": "1",
  "nm_factory": "Г 49065",
  "id_service": 3740,
  "nm_service": "ГОРЯЧЕЕ В/С (НОСИТЕЛЬ)",
  "nn_pu": 738326,
  "nm_pu": "ООО «Р-СЕТЕВАЯ КОМПАНИЯ» (дог. 812680320)",
  "nm_measure_unit": "м3",
  "vl_last_indication": 364,
  "dt_last_indication": "2026-02-15 00:00:00.0",
  "nn_ind_receive_start": 14,
  "nn_ind_receive_end": 19,
  "id_billing_counter": 3100014511975,
  "vl_sh_znk": 5.3,
  "nm_no_access_reason": null,
  "dt_mpi": "2027-06-22 00:00:00.0",
  "vl_tarif": null,
  "pr_state": 1,
  "pr_remotely": 0
}
```
