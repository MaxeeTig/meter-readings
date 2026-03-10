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

## Примечания
- Источник даты: EXIF -> имя файла `IMG_YYYYMMDD_HHMMSS` -> текущее время сервера.
- Формат файлов: `jpg/jpeg/png/webp/heic`.
