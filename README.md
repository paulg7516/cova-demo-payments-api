# cova-demo-payments-api

Demo FastAPI service used to showcase Cova's PR Guard. The `main` branch is intentionally minimal so that PRs adding new endpoints, databases, or external dependencies trigger Cova's PR comment.

## Run locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
```

## Endpoints

See `app/main.py`.
