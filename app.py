
import os
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text

DEFAULT_SQLITE_URL = "sqlite:///data/crm.db"
DB_URL = os.environ.get("POSTGRES_URL", DEFAULT_SQLITE_URL)
engine = create_engine(DB_URL, future=True)

st.set_page_config(page_title="Rockland Concrete CRM", layout="wide", initial_sidebar_state="expanded")

LOGO_PATH = "rockland_logo.png"
c1, c2 = st.columns([1, 6])
with c1:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, use_column_width=True)
with c2:
    st.title("Rockland Concrete — CRM")
    st.caption("SQLite by default • Set POSTGRES_URL for multi-user PostgreSQL")

def q(sql, params=None):
    with engine.begin() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})

def exec_sql(sql, params=None):
    with engine.begin() as conn:
        conn.execute(text(sql), params or {})

page = st.sidebar.radio("Go to", ["Dashboard", "Accounts", "Contacts", "Opportunities", "Quotes", "Activities", "Reports", "Settings"])

if page == "Dashboard":
    st.subheader("Pipeline at a glance")
    try:
        opps = q("SELECT stage, COALESCE(SUM(value),0) as total FROM opportunities GROUP BY stage ORDER BY total DESC")
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
            """INSERT INTO accounts(name, type, region, credit_limit, payment_terms, risk_rating)
                    VALUES (:name,:type,:region,:cl,:terms,:risk)""" ,
            {"name":name, "type":a_type, "region":region, "cl":credit_limit, "terms":terms, "risk":risk}
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
            """INSERT INTO contacts(account_id, name, role, email, phone)
                    VALUES (:aid,:name,:role,:email,:phone)""" ,
            {"aid": acct_name_to_id[acct], "name": name, "role": role, "email": email, "phone": phone}
        )
        st.success("Saved.")
    st.divider()
    st.subheader("All Contacts")
    st.dataframe(q(
        """SELECT c.id, a.name AS account, c.name, c.role, c.email, c.phone
              FROM contacts c LEFT JOIN accounts a ON a.id=c.account_id
              ORDER BY c.id DESC"""
    ), use_container_width=True)

elif page == "Opportunities":
    st.subheader("Add Opportunity")
    accounts = q("SELECT id, name FROM accounts ORDER BY name")
    acct_name_to_id = dict(zip(accounts["name"], accounts["id"])) if not accounts.empty else {}
    with st.form("opp"):
        acct = st.selectbox("Account*", list(acct_name_to_id.keys()) if acct_name_to_id else [])
        name = st.text_input("Opportunity Name*")
        stage = st.selectbox("Stage", ["Lead","Qualified","Estimating","Bid Submitted","Negotiation","Awarded","In Production","Delivered","Closed Won","Closed Lost"], index=2)
        expected_close_date = st.date_input("Expected Close Date").isoformat()
        value = st.number_input("Value (£)", 0.0, 1e9, 0.0, step=5000.0)
        product_type = st.text_input("Product Type", value="Precast panels")
        region = st.text_input("Region")
        probability = st.slider("Probability", 0.0, 1.0, 0.3, 0.05)
        source = st.text_input("Source", value="Direct")
        save = st.form_submit_button("Save")
    if save and acct and name:
        exec_sql(
            """INSERT INTO opportunities(account_id, name, stage, expected_close_date, value, product_type, region, probability, source)
                    VALUES (:aid,:name,:stage,:ecd,:val,:ptype,:region,:prob,:src)""" ,
            {"aid":acct_name_to_id[acct], "name":name, "stage":stage, "ecd":expected_close_date,
             "val":value, "ptype":product_type, "region":region, "prob":probability, "src":source}
        )
        st.success("Saved.")
    st.divider()
    st.subheader("Board (by Stage)")
    opps = q(
        """SELECT o.id, a.name AS account, o.name, o.stage, o.value, o.expected_close_date
               FROM opportunities o LEFT JOIN accounts a ON a.id=o.account_id ORDER BY o.id DESC"""
    )
    if opps.empty:
        st.info("No opportunities yet.")
    else:
        for stg in opps["stage"].unique():
            st.markdown(f"### {stg}")
            st.dataframe(opps[opps["stage"]==stg], use_container_width=True)

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
            """INSERT INTO quotes(opportunity_id, quote_number, date, status, total_value, currency, price_index_clause)
                    VALUES (:oid,:qnum,:date,:status,:total,:curr,:pic)""" ,
            {"oid":opp_name_to_id[opp], "qnum":qnum, "date":qdate, "status":status,
             "total":total_value, "curr":currency, "pic": 1 if price_index else 0}
        )
        st.success("Saved.")
    st.divider()
    st.subheader("Quotes")
    st.dataframe(q(
        """SELECT q.id, o.name AS opportunity, q.quote_number, q.date, q.status, q.total_value, q.currency, q.price_index_clause
               FROM quotes q LEFT JOIN opportunities o ON o.id=q.opportunity_id ORDER BY q.id DESC"""
    ), use_container_width=True)

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
            """INSERT INTO activities(account_id, opportunity_id, type, subject, due_date, owner, notes, completed)
                    VALUES (:aid,:oid,:type,:subject,:due,:owner,:notes,:done)""" ,
            {"aid":acct_name_to_id.get(account), "oid":opp_name_to_id.get(opportunity),
             "type":a_type, "subject":subject, "due":due_date, "owner":owner, "notes":notes, "done": 1 if completed else 0}
        )
        st.success("Saved.")
    st.divider()
    st.subheader("Open Activities")
    st.dataframe(q("SELECT * FROM activities WHERE completed=0 ORDER BY due_date ASC"), use_container_width=True)

elif page == "Reports":
    st.subheader("Pipeline by Stage")
    opps = q("SELECT stage, COALESCE(SUM(value),0) as total FROM opportunities GROUP BY stage ORDER BY total DESC")
    st.bar_chart(opps, x="stage", y="total")
    st.subheader("Overdue Expected Close (risk)")
    opps2 = q("SELECT * FROM opportunities")
    if not opps2.empty:
        opps2["expected_close_date"] = pd.to_datetime(opps2["expected_close_date"], errors="coerce").dt.date
        overdue = opps2[(~opps2["stage"].isin(["Closed Won","Closed Lost"])) & (opps2["expected_close_date"].notna()) & (opps2["expected_close_date"] < pd.Timestamp.today().date())]
        st.dataframe(overdue, use_container_width=True)
    else:
        st.info("No data yet.")

elif page == "Settings":
    st.subheader("Export CSV")
    for table in ["accounts","contacts","opportunities","quotes","quote_items","activities"]:
        try:
            df = q(f"SELECT * FROM {table}")
            st.download_button(f"Download {table}.csv", df.to_csv(index=False).encode("utf-8"), file_name=f"{table}.csv", mime="text/csv")
        except Exception as e:
            st.warning(f"Could not export {table}: {e}")
    st.markdown("### Switch to PostgreSQL (optional)")
    st.write("Set a **secrets variable** named `POSTGRES_URL` in Streamlit Cloud to a connection string like:")
    st.code("postgresql+psycopg2://USER:PASSWORD@HOST:5432/DBNAME")
    st.caption("After saving the secret, redeploy the app and it will use PostgreSQL automatically.")
