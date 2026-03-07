# Deployment Guide (Local Home Server)

This file is written for an AI assistant operating on the server.

## Goal

Deploy **Meter Readings** as:
- FastAPI backend (`/api/*`) via `uvicorn` + `systemd`
- React frontend (`meterface`) as static files via `nginx`

Use placeholders and replace everywhere:
- `<APP_USER>`: Linux user running app service (recommended: dedicated user)
- `<APP_GROUP>`: Linux group for app files (often same as user)
- `<APP_DIR>`: absolute project path on server

## 1. Prepare project

```bash
cd <APP_DIR>
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp -n .env.example .env
mkdir -p data tmp_uploads
```

If using dedicated service user (recommended):

```bash
sudo useradd --system --create-home --shell /usr/sbin/nologin <APP_USER> || true
sudo chown -R <APP_USER>:<APP_GROUP> <APP_DIR>
```

Edit `.env` and set at minimum:
- `OPENROUTER_API_KEY`
- optional: `OPENROUTER_MODEL`, `APP_PORT`, `DATA_FILE`, `UPLOAD_DIR`

## 2. Build frontend (`meterface`)

```bash
cd <APP_DIR>/meterface
npm i
npm run build
```

Build output: `meterface/dist`

## 3. Create systemd service for API

Create `/etc/systemd/system/meter-readings.service`:

```ini
[Unit]
Description=Meter Readings FastAPI Service
After=network.target

[Service]
User=<APP_USER>
Group=<APP_GROUP>
WorkingDirectory=<APP_DIR>
EnvironmentFile=<APP_DIR>/.env
ExecStart=<APP_DIR>/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now meter-readings
sudo systemctl status meter-readings --no-pager
```

## 4. Configure nginx

Create `/etc/nginx/sites-available/meter-readings`:

```nginx
server {
    listen 80;
    server_name _;

    root <APP_DIR>/meterface/dist;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # SPA fallback
    location / {
        try_files $uri /index.html;
    }
}
```

Enable site:

```bash
sudo ln -sf /etc/nginx/sites-available/meter-readings /etc/nginx/sites-enabled/meter-readings
sudo nginx -t
sudo systemctl reload nginx
```

## 5. Validate

```bash
curl -I http://127.0.0.1/api/readings
curl -I http://127.0.0.1/
```

In browser:
- open server IP
- verify upload -> OCR -> save works
- verify history + charts load

## 6. Update procedure

When code changes:

```bash
cd <APP_DIR>
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart meter-readings

cd meterface
npm i
npm run build
sudo systemctl reload nginx
```

## 7. Logs and troubleshooting

API logs:

```bash
sudo journalctl -u meter-readings -n 200 --no-pager
sudo journalctl -u meter-readings -f
```

Nginx logs:

```bash
sudo tail -n 200 /var/log/nginx/error.log
sudo tail -n 200 /var/log/nginx/access.log
```

Common issues:
- `502 Bad Gateway`: API service is down or wrong port in nginx.
- `OCR failed`: missing/invalid `OPENROUTER_API_KEY`.
- empty UI data: check `/api/readings` response and file path in `DATA_FILE`.
