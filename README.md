# Meter Readings Service

Локальный сервис для распознавания и хранения показаний счетчиков:
- backend: FastAPI API
- frontend: React/Vite в `meterface/`

## Возможности
- Загрузка фото счетчика с телефона через браузер
- OCR через OpenRouter vision модель на сервере
- Обязательное подтверждение/редактирование перед сохранением
- Хранение в одном JSON файле
- График расхода (дельта между соседними показаниями)
- Удаление загруженного фото после успешного сохранения записи
- Отправка подтвержденных показаний в портал Мосэнергосбыт из карточки Upload & Verify

## Быстрый старт (API)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# заполнить OPENROUTER_API_KEY
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Проверка API: `http://<host>:8000/api/readings`

## Frontend

```bash
cd meterface
npm i
npm run dev
```

## Переменные окружения
См. `.env.example`.

Важно: после изменения `.env` перезапустите `uvicorn`, чтобы приложение перечитало ключи.

## API
- `POST /api/ocr` - загрузить фото, получить черновик OCR
- `POST /api/readings` - сохранить подтвержденную запись
- `GET /api/readings` - список записей
- `GET /api/reports/line` - дельта-данные для графика
- `GET /api/providers/mosenergosbyt/status` - статус авторизации в портале
- `POST /api/providers/mosenergosbyt/login` - логин в портал (может вернуть OTP-required)
- `POST /api/providers/mosenergosbyt/otp/send` - отправить OTP-код
- `POST /api/providers/mosenergosbyt/otp/verify` - подтвердить OTP и завершить логин
- `POST /api/providers/mosenergosbyt/disconnect` - сбросить сессию (токен устройства сохраняется)
- `GET /api/providers/mosenergosbyt/meters` - получить список счетчиков из портала
- `POST /api/providers/mosenergosbyt/submit` - отправить показания в портал (по выбранному счетчику)

## Примечания
- Источник даты: EXIF -> имя файла `IMG_YYYYMMDD_HHMMSS` -> текущее время сервера.
- Формат файлов: `jpg/jpeg/png/webp/heic`.

## Mosenergosbyt: отправка показаний
- Отправка выполняется из карточки Upload & Verify по значению, отредактированному пользователем.
- Кнопка «Submit to Portal» активна только при авторизации в портале и наличии подходящего счетчика по типу.
- Источник формы для портала задается через `MOSENERGOSBYT_ID_SOURCE` (по умолчанию `15418`).

## NUC routing note
- На рабочем NUC доступ к `my.mosenergosbyt.ru` вынесен в прямой WAN-маршрут без Amnezia VPN, потому что портал недоступен с зарубежного egress.
- При этом остальные внешние запросы сервиса `meter-readings` могут идти через VPN; split tunneling настроен на уровне хоста, а не внутри FastAPI-приложения.
- Детали этой настройки хранятся в deployment/ops репозитории NUC, а не в коде самого приложения.
