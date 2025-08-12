# app.py — Rockland Concrete CRM (Streamlit Cloud-ready)
# - Uses Postgres if POSTGRES_URL is set; else SQLite in a writable path
# - Auto-creates tables on startup
# - Safe logo loading; simple CRM pages

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
if "authenticated" not in st.session_state:
    pwd = st.text_input("Enter password", type="password")
    if pwd == os.getenv("APP_PASSWORD"):
        st.session_state.authenticated = True
        st.experimental_rerun()
    elif pwd:
        st.error("Wrong password")
    st.stop()

# -----------------------------
# Streamlit page config
# -----------------------------
st.set_page_config(
    page_title="Rockland Concrete — CRM",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------
# Database URL: Postgres (secret) or SQLite in a writable spot
# -----------------------------
pg_url = os.environ.get("POSTGRES_URL", "").strip()

if pg_url:
    DB_URL = pg_url  # e.g. postgresql+psycopg2://USER:PASS@HOST:5432/DB?sslmode=require
else:
    data_root = Path("/mount/data")
    if data_root.is_dir() and os.access(data_root, os.W_OK):
        db_file = data_root / "crm.db"
    else:
        # Fallback: guaranteed writable per-process temp dir (no mkdir needed)
        db_file = Path(tempfile.gettempdir()) / "crm.db"
    DB_URL = f"sqlite:///{db_file.as_posix()}"

engine = create_engine(DB_URL, future=True)

# -----------------------------
# Schema (Postgres vs SQLite)
# -----------------------------
SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS accounts(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  type TEXT,
  region TEXT,
  credit_limit REAL,
  payment_terms TEXT,
  risk_rating TEXT
);
CREATE TABLE IF NOT EXISTS contacts(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  account_id INTEGER,
  name TEXT,
  role TEXT,
  email TEXT,
  phone TEXT,
  FOREIGN KEY(account_id) REFERENCES accounts(id)
);
CREATE TABLE IF NOT EXISTS opportunities(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  account_id INTEGER,
  name TEXT,
  stage TEXT,
  expected_close_date TEXT,
  value REAL,
  product_type TEXT,
  region TEXT,
  probability REAL,
  source TEXT,
  FOREIGN KEY(account_id) REFERENCES accounts(id)
);
CREATE TABLE IF NOT EXISTS quotes(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  opportunity_id INTEGER,
  quote_number TEXT,
  date TEXT,
  status TEXT,
  total_value REAL,
  currency TEXT,
  price_index_clause INTEGER DEFAULT 0,
  FOREIGN KEY(opportunity_id) REFERENCES opportunities(id)
);
CREATE TABLE IF NOT EXISTS quote_items(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  quote_id INTEGER,
  description TEXT,
  unit TEXT,
  qty REAL,
  unit_price REAL,
  lead_time_days INTEGER,
  FOREIGN KEY(quote_id) REFERENCES quotes(id)
);
CREATE TABLE IF NOT EXISTS activities(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  account_id INTEGER,
  opportunity_id INTEGER,
  type TEXT,
  subject TEXT,
  due_date TEXT,
  owner TEXT,
  notes TEXT,
  completed INTEGER DEFAULT 0,
  FOREIGN KEY(account_id) REFERENCES accounts(id),
  FOREIGN KEY(opportunity_id) REFERENCES opportunities(id)
);
"""

SCHEMA_PG = """
CREATE TABLE IF NOT EXISTS accounts(
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  type TEXT,
  region TEXT,
  credit_limit REAL,
  payment_terms TEXT,
  risk_rating TEXT
);
CREATE TABLE IF NOT EXISTS contacts(
  id SERIAL PRIMARY KEY,
  account_id INTEGER REFERENCES accounts(id),
  name TEXT,
  role TEXT,
  email TEXT,
  phone TEXT
);
CREATE TABLE IF NOT EXISTS opportunities(
  id SERIAL PRIMARY KEY,
  account_id INTEGER REFERENCES accounts(id),
  name TEXT,
  stage TEXT,
  expected_close_date DATE,
  value REAL,
  product_type TEXT,
  region TEXT,
  probability REAL,
  source TEXT
);
CREATE TABLE IF NOT EXISTS quotes(
  id SERIAL PRIMARY KEY,
  opportunity_id INTEGER REFERENCES opportunities(id),
  quote_number TEXT,
  date DATE,
  status TEXT,
  total_value REAL,
  currency TEXT,
  price_index_clause INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS quote_items(
  id SERIAL PRIMARY KEY,
  quote_id INTEGER REFERENCES quotes(id),
  description TEXT,
  unit TEXT,
  qty REAL,
  unit_price REAL,
  lead_time_days INTEGER
);
CREATE TABLE IF NOT EXISTS activities(
  id SERIAL PRIMARY KEY,
  account_id INTEGER REFERENCES accounts(id),
  opportunity_id INTEGER REFERENCES opportunities(id),
  type TEXT,
  subject TEXT,
  due_date DATE,
  owner TEXT,
  notes TEXT,
  completed INTEGER DEFAULT 0
);
"""

def init_schema() -> None:
    """Create tables for the active backend; safe to call repeatedly."""
    is_pg = DB_URL.startswith("postgresql+")
    ddl = SCHEMA_PG if is_pg else SCHEMA_SQLITE
    # Execute statements one by one
    for stmt in ddl.strip().split(";"):
        s = stmt.strip()
        if s:
            with engine.begin() as con:
                con.execute(text(s))

# Initialize schema on startup
try:
    init_schema()
    st.sidebar.caption("DB init: OK")
except Exception as e:
    st.sidebar.error(f"DB init error: {e}")

# -----------------------------
# Safe logo header
# -----------------------------
LOGO_PATH = "rockland_logo.png"
col_logo, col_title = st.columns([1, 6])
with col_logo:
    try:
        if os.path.exists(LOGO_PATH) and os.path.getsize(LOGO_PATH) > 0:
            from PIL import Image  # lazy import to avoid hard dependency if no logo
            st.image(Image.open(LOGO_PATH), use_column_width=True)
    except Exception:
        st.warning("Logo couldn't be loaded; continuing without it.")
with col_title:
    st.title("Rockland Concrete — CRM")
    mode = "PostgreSQL" if DB_URL.startswith("postgresql+") else "SQLite"
    st.caption(f"Database: {mode}")

# -----------------------------
# DB helpers
# -----------------------------
def q(sql: str, params: dict | None = None) -> pd.DataFrame:
    with engine.begin() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})

def exec_sql(sql: str, params: dict | None = None) -> None:
    with engine.begin() as conn:
        conn.execute(text(sql), params or {})

# -----------------------------
# Navigation
# -----------------------------
page = st.sidebar.radio(
    "Go to",
    ["Dashboard", "Accounts", "Contacts", "Opportunities", "Quotes", "Activities", "Reports", "Settings"],
)

# -----------------------------
# Pages
# -----------------------------
if page == "Dashboard":
    st.subheader("Pipeline at a glance")
    try:
        opps = q("SELECT stage, COALESCE(SUM(value),0) AS total FROM opportunities GROUP BY stage ORDER BY total DESC")
        if opps.empty:
            st.info("No opportunities yet. Add some in the Opportunities tab.")
        else:
            st.bar_chart(opps, x="stage", y="total")
    except Exception as e:
        st.error(f"DB error: {e}")

elif page == "Accounts":
    st.subheader("Add / Update Account")
    with st.form("acct"):
        name = st.text_input("Account Name*")
        a_type = st.selectbox("Type", ["Main Contractor","Subcontractor","Developer","Architect","Other"])
        region = st.text_input("Region")
        credit_limit = st.number_input("Credit Limit (£)", 0.0, 1e9, 0.0, step=1000.0)
        terms = st.text_input("Payment Terms", value="30 days")
        risk = st.selectbox("Risk Rating", ["Low","Medium","High"])
        save = st.form_submit_button("Save")
    if save and name:
        exec_sql(
            """
            INSERT INTO accounts(name, type, region, credit_limit, payment_terms, risk_rating)
            VALUES (:name,:type,:region,:cl,:terms,:risk)
            """,
            {"name": name, "type": a_type, "region": region, "cl": credit_limit, "terms": terms, "risk": risk},
        )
        st.success("Saved.")
    st.divider()
    st.subheader("Accounts")
    try:
        st.dataframe(q("SELECT * FROM accounts ORDER BY id DESC"), use_container_width=True)
    except Exception as e:
        st.error(f"DB error: {e}")

elif page == "Contacts":
    st.subheader("Add Contact")
    accounts = q("SELECT id, name FROM accounts ORDER BY name")
    acct_name_to_id = dict(zip(accounts["name"], accounts["id"])) if not accounts.empty else {}
    with st.form("contact"):
        acct = st.selectbox("Account*", list(acct_name_to_id.keys()) if acct_name_to_id else [])
        name = st.text_input("Name*")
        role = st.text_input("Role")
        email = st.text_input("Email")
        phone = st.text_input("Phone")
        save = st.form_submit_button("Save")
    if save and acct and name:
        exec_sql(
            "INSERT INTO contacts(account_id, name, role, email, phone) VALUES (:aid,:name,:role,:email,:phone)",
            {"aid": acct_name_to_id[acct], "name": name, "role": role, "email": email, "phone": phone},
        )
        st.success("Saved.")
    st.divider()
    st.subheader("All Contacts")
    st.dataframe(
        q(
            """
            SELECT c.id, a.name AS account, c.name, c.role, c.email, c.phone
            FROM contacts c LEFT JOIN accounts a ON a.id=c.account_id
            ORDER BY c.id DESC
            """
        ),
        use_container_width=True,
    )

elif page == "Opportunities":
    st.subheader("Add Opportunity")
    accounts = q("SELECT id, name FROM accounts ORDER BY name")
    acct_name_to_id = dict(zip(accounts["name"], accounts["id"])) if not accounts.empty else {}
    with st.form("opp"):
        acct = st.selectbox("Account*", list(acct_name_to_id.keys()) if acct_name_to_id else [])
        name = st.text_input("Opportunity Name*")
        stage = st.selectbox(
            "Stage",
            ["Lead","Qualified","Estimating","Bid Submitted","Negotiation","Awarded","In Production","Delivered","Closed Won","Closed Lost"],
            index=2,
        )
        expected_close_date = st.date_input("Expected Close Date").isoformat()
        value = st.number_input("Value (£)", 0.0, 1e9, 0.0, step=5000.0)
        product_type = st.text_input("Product Type", value="Precast panels")
        region = st.text_input("Region")
        probability = st.slider("Probability", 0.0, 1.0, 0.3, 0.05)
        source = st.text_input("Source", value="Direct")
        save = st.form_submit_button("Save")
    if save and acct and name:
        exec_sql(
            """
            INSERT INTO opportunities(account_id, name, stage, expected_close_date, value, product_type, region, probability, source)
            VALUES (:aid,:name,:stage,:ecd,:val,:ptype,:region,:prob,:src)
            """,
            {
                "aid": acct_name_to_id[acct],
                "name": name,
                "stage": stage,
                "ecd": expected_close_date,
                "val": value,
                "ptype": product_type,
                "region": region,
                "prob": probability,
                "src": source,
            },
        )
        st.success("Saved.")
    st.divider()
    st.subheader("Board (by Stage)")
    opps = q(
        """
        SELECT o.id, a.name AS account, o.name, o.stage, o.value, o.expected_close_date
        FROM opportunities o LEFT JOIN accounts a ON a.id=o.account_id
        ORDER BY o.id DESC
        """
    )
    if opps.empty:
        st.info("No opportunities yet.")
    else:
        for stg in opps["stage"].unique():
            st.markdown(f"### {stg}")
            st.dataframe(opps[opps["stage"] == stg], use_container_width=True)

elif page == "Quotes":
    st.subheader("Add Quote")
    opps = q("SELECT id, name FROM opportunities ORDER BY id DESC")
    opp_name_to_id = dict(zip(opps["name"], opps["id"])) if not opps.empty else {}
    with st.form("quote"):
        opp = st.selectbox("Opportunity*", list(opp_name_to_id.keys()) if opp_name_to_id else [])
        qnum = st.text_input("Quote Number*", value="Q-0001")
        qdate = st.date_input("Quote Date").isoformat()
        status = st.selectbox("Status", ["Draft","Submitted","Accepted","Rejected","Revised"])
        total_value = st.number_input("Total Value (£)", 0.0, 1e9, 0.0, step=5000.0)
        currency = st.selectbox("Currency", ["GBP","EUR"])
        price_index = st.checkbox("Include price-index clause")
        save = st.form_submit_button("Save")
    if save and opp and qnum:
        exec_sql(
            """
            INSERT INTO quotes(opportunity_id, quote_number, date, status, total_value, currency, price_index_clause)
            VALUES (:oid,:qnum,:date,:status,:total,:curr,:pic)
            """,
            {
                "oid": opp_name_to_id[opp],
                "qnum": qnum,
                "date": qdate,
                "status": status,
                "total": total_value,
                "curr": currency,
                "pic": 1 if price_index else 0,
            },
        )
        st.success("Saved.")
    st.divider()
    st.subheader("Quotes")
    st.dataframe(
        q(
            """
            SELECT q.id, o.name AS opportunity, q.quote_number, q.date, q.status, q.total_value, q.currency, q.price_index_clause
            FROM quotes q LEFT JOIN opportunities o ON o.id=q.opportunity_id
            ORDER BY q.id DESC
            """
        ),
        use_container_width=True,
    )

elif page == "Activities":
    st.subheader("Activities / Tasks")
    accounts = q("SELECT id, name FROM accounts ORDER BY name")
    opps = q("SELECT id, name FROM opportunities ORDER BY id DESC")
    acct_name_to_id = dict(zip(accounts["name"], accounts["id"])) if not accounts.empty else {}
    opp_name_to_id = dict(zip(opps["name"], opps["id"])) if not opps.empty else {}
    with st.form("act"):
        account = st.selectbox("Account", [""] + list(acct_name_to_id.keys()))
        opportunity = st.selectbox("Opportunity", [""] + list(opp_name_to_id.keys()))
        a_type = st.selectbox("Type", ["Call","Site Visit","Bid Due","Follow-up","Delivery Coordination","Other"], index=2)
        subject = st.text_input("Subject")
        due_date = st.date_input("Due Date").isoformat()
        owner = st.text_input("Owner", value="Sales")
        notes = st.text_area("Notes")
        completed = st.checkbox("Completed?")
        save = st.form_submit_button("Save Activity")
    if save:
        exec_sql(
            """
            INSERT INTO activities(account_id, opportunity_id, type, subject, due_date, owner, notes, completed)
            VALUES (:aid,:oid,:type,:subject,:due,:owner,:notes,:done)
            """,
            {
                "aid": acct_name_to_id.get(account),
                "oid": opp_name_to_id.get(opportunity),
                "type": a_type,
                "subject": subject,
                "due": due_date,
                "owner": owner,
                "notes": notes,
                "done": 1 if completed else 0,
            },
        )
        st.success("Saved.")
    st.divider()
    st.subheader("Open Activities")
    st.dataframe(q("SELECT * FROM activities WHERE completed=0 ORDER BY due_date ASC"), use_container_width=True)

elif page == "Reports":
    st.subheader("Pipeline by Stage")
    opps = q("SELECT stage, COALESCE(SUM(value),0) AS total FROM opportunities GROUP BY stage ORDER BY total DESC")
    st.bar_chart(opps, x="stage", y="total")
    st.subheader("Overdue Expected Close (risk)")
    opps2 = q("SELECT * FROM opportunities")
    if not opps2.empty:
        opps2["expected_close_date"] = pd.to_datetime(opps2["expected_close_date"], errors="coerce").dt.date
        overdue = opps2[
            (~opps2["stage"].isin(["Closed Won","Closed Lost"]))
            & (opps2["expected_close_date"].notna())
            & (opps2["expected_close_date"] < pd.Timestamp.today().date())
        ]
        st.dataframe(overdue, use_container_width=True)
    else:
        st.info("No data yet.")

elif page == "Settings":
    st.subheader("Export CSV")
    for table in ["accounts","contacts","opportunities","quotes","quote_items","activities"]:
        try:
            df = q(f"SELECT * FROM {table}")
            st.download_button(
                f"Download {table}.csv",
                df.to_csv(index=False).encode("utf-8"),
                file_name=f"{table}.csv",
                mime="text/csv",
            )
        except Exception as e:
            st.warning(f"Could not export {table}: {e}")

    st.markdown("### Database info")
    st.code(DB_URL)
    st.caption("Using Postgres if POSTGRES_URL is set; otherwise SQLite (writable temp or /mount/data/crm.db).")

    st.markdown("### (Optional) Recreate/verify tables")
    if st.button("Create/verify tables now"):
        try:
            init_schema()
            st.success("Schema created/verified.")
        except Exception as e:
            st.error(f"Error: {e}")
