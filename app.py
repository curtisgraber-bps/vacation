import streamlit as st
import pandas as pd
import psycopg2
import datetime
import random
import requests

ADMIN_PASSWORD = "admin123"

SUPABASE_URL = "https://ugnxfszbikjuzaklsnji.supabase.co"
SUPABASE_KEY = "sb_secret_-AlKPxmMHwnuMjIlfMI7Wg_5LNS6YVr"

conn = psycopg2.connect(st.secrets["DB_URL"])
conn.autocommit = True
c = conn.cursor()

# ---------- TABLES ----------
c.execute("""CREATE TABLE IF NOT EXISTS employees (
    employee_id TEXT PRIMARY KEY,
    first_name TEXT,
    last_name TEXT,
    hire_date DATE,
    win_count INTEGER DEFAULT 0
)""")

c.execute("""CREATE TABLE IF NOT EXISTS submissions (
    employee_id TEXT PRIMARY KEY,
    choice1 TEXT, choice2 TEXT, choice3 TEXT, choice4 TEXT, choice5 TEXT,
    choice6 TEXT, choice7 TEXT, choice8 TEXT, choice9 TEXT, choice10 TEXT
)""")

c.execute("""CREATE TABLE IF NOT EXISTS results (
    employee_id TEXT,
    assigned_week TEXT
)""")

c.execute("""CREATE TABLE IF NOT EXISTS weeks (
    week TEXT PRIMARY KEY,
    enabled BOOLEAN
)""")

# ---------- HELPERS ----------
def get_employees():
    return pd.read_sql_query("SELECT * FROM employees", conn)

def generate_weeks():
    start = datetime.date(2027, 1, 1)
    while start.weekday() != 5:
        start += datetime.timedelta(days=1)
    return [f"{start + datetime.timedelta(weeks=i)} to {start + datetime.timedelta(days=7 + i*7)}" for i in range(52)]

def get_active_weeks():
    return pd.read_sql_query("SELECT week FROM weeks WHERE enabled = TRUE", conn)["week"].tolist()

# INIT WEEKS
if pd.read_sql_query("SELECT COUNT(*) c FROM weeks", conn)["c"][0] == 0:
    for w in generate_weeks():
        c.execute("INSERT INTO weeks VALUES (%s,%s)", (w, True))

# ---------- SESSION ----------
if "user" not in st.session_state:
    st.session_state.user = None
if "role" not in st.session_state:
    st.session_state.role = None

# ---------- LOGIN ----------
if not st.session_state.user:
    st.title("Login")

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    col1, col2 = st.columns(2)

    if col1.button("Login"):
        res = requests.post(
            f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
            headers={"apikey": SUPABASE_KEY, "Content-Type": "application/json"},
            json={"email": email, "password": password}
        )
        if res.status_code == 200:
            st.session_state.user = res.json()
            st.session_state.role = "user"
            st.rerun()
        else:
            st.error("Invalid login")

    if col2.button("Sign Up"):
        requests.post(
            f"{SUPABASE_URL}/auth/v1/signup",
            headers={"apikey": SUPABASE_KEY, "Content-Type": "application/json"},
            json={"email": email, "password": password}
        )
        st.success("Account created")

    if st.button("Forgot Password"):
        requests.post(
            f"{SUPABASE_URL}/auth/v1/recover",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json"
            },
            json={"email": email}
        )
        st.success("Reset email sent. Check your inbox.")

    if st.checkbox("Admin login"):
        pw = st.text_input("Admin Password", type="password")
        if st.button("Admin Login"):
            if pw == ADMIN_PASSWORD:
                st.session_state.user = {"email": "admin"}
                st.session_state.role = "admin"
                st.rerun()

# ---------- LOGOUT ----------
if st.session_state.user:
    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()

# ---------- USER ----------
if st.session_state.user and st.session_state.role == "user":
    st.title("Vacation Scheduler")

    email = st.session_state.user["user"]["email"]

    emps = get_employees()

    if email not in emps["employee_id"].values:
        c.execute("INSERT INTO employees VALUES (%s,%s,%s,%s,%s)",
                  (email, "", "", datetime.date.today(), 0))
        conn.commit()
        st.rerun()

    weeks = get_active_weeks()

    choices = [st.selectbox(f"Choice {i}", [""] + weeks, key=f"c{i}") for i in range(1, 11)]

    if st.button("Submit"):
        c.execute("DELETE FROM submissions WHERE employee_id=%s", (email,))
        c.execute(
            "INSERT INTO submissions VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (email, *choices)
        )
        conn.commit()
        st.success("Submitted")

# ---------- ADMIN ----------
if st.session_state.user and st.session_state.role == "admin":

    st.title("Admin Panel")

    if st.button("Clear Submissions"):
        c.execute("DELETE FROM submissions")
        conn.commit()
        st.rerun()

    st.subheader("Employees")
    st.dataframe(get_employees())

    st.subheader("Submissions")
    subs = pd.read_sql_query("SELECT * FROM submissions", conn)
    st.dataframe(subs)

    if not subs.empty:
        user_to_delete = st.selectbox("Delete submission", subs["employee_id"])
        if st.button("Delete Selected Submission"):
            c.execute("DELETE FROM submissions WHERE employee_id=%s", (user_to_delete,))
            conn.commit()
            st.rerun()

    if st.button("Run Lottery"):
        c.execute("DELETE FROM results")
        conn.commit()

    res = pd.read_sql_query("SELECT * FROM results", conn)
    st.dataframe(res)

    st.download_button(
        "Download Results",
        res.to_csv(index=False),
        "results.csv"
    )
