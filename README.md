# Rockland Concrete CRM (Streamlit Cloud–ready)

**SQLite by default, PostgreSQL-ready.**

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy to Streamlit Cloud
1. Push this folder to a GitHub repo (e.g., `rockland-crm`).
2. Go to https://share.streamlit.io and create a new app:
   - Repo: your `rockland-crm`
   - Main file: `app.py`
3. Deploy. Share the link with your team.

### Switch to PostgreSQL (recommended for multi-user)
1. Create a PostgreSQL DB (e.g., ElephantSQL free tier).
2. In Streamlit Cloud → **App → Settings → Secrets**, add:
```
POSTGRES_URL="postgresql+psycopg2://USER:PASSWORD@HOST:5432/DBNAME"
```
3. Redeploy the app. It will use PostgreSQL automatically.
