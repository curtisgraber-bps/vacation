import streamlit as st
import pandas as pd
import psycopg2
import datetime
import random
import bcrypt
import uuid

ADMIN_PASSWORD = "admin123"

conn = psycopg2.connect(st.secrets["DB_URL"])
conn.autocommit = True
c = conn.cursor()

# ---------- TABLES ----------
c.execute("""CREATE TABLE IF NOT EXISTS employees (
    employee_id TEXT PRIMARY KEY,
    first_name TEXT,
    last_name TEXT,
    hire_date DATE,
    win_count INTEGER DEFAULT 0,
    password_hash TEXT,
    reset_token TEXT,
    reset_expiry TIMESTAMP
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

def hash_pw(pw):
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

def check_pw(pw, hashed):
    return bcrypt.checkpw(pw.encode(), hashed.encode())

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

# ---------- RESET ----------
params = st.query_params
if "token" in params:
    token = params["token"]

    user = pd.read_sql_query(
        "SELECT * FROM employees WHERE reset_token=%s",
        conn,
        params=(token,)
    )

    if user.empty:
        st.error("Invalid token")
        st.stop()

    if user.iloc[0]["reset_expiry"] and user.iloc[0]["reset_expiry"] < datetime.datetime.utcnow():
        st.error("Token expired")
        st.stop()

    st.title("Reset Password")
    new_pw = st.text_input("New Password", type="password")

    if st.button("Set Password"):
        hashed = hash_pw(new_pw)
        c.execute(
            "UPDATE employees SET password_hash=%s, reset_token=NULL, reset_expiry=NULL WHERE employee_id=%s",
            (hashed, user.iloc[0]["employee_id"])
        )
        conn.commit()
        st.success("Password updated")

    st.stop()

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
        user = pd.read_sql_query(
            "SELECT * FROM employees WHERE employee_id=%s",
            conn,
            params=(email,)
        )

        if not user.empty and user.iloc[0]["password_hash"] and check_pw(password, user.iloc[0]["password_hash"]):
            st.session_state.user = {"email": email}
            st.session_state.role = "user"
            st.rerun()
        else:
            st.error("Invalid login")

    if col2.button("Create Account"):
        hashed = hash_pw(password)
        c.execute(
            "INSERT INTO employees (employee_id, password_hash, hire_date, win_count) VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            (email, hashed, datetime.date.today(), 0)
        )
        conn.commit()
        st.success("Account created")

    if st.button("Forgot Password"):
        token = str(uuid.uuid4())
        expiry = datetime.datetime.utcnow() + datetime.timedelta(hours=1)

        c.execute(
            "UPDATE employees SET reset_token=%s, reset_expiry=%s WHERE employee_id=%s",
            (token, expiry, email)
        )
        conn.commit()

        st.code(f"https://bpa-wellness.streamlit.app/?token={token}")

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

    email = st.session_state.user["email"]
    weeks = get_active_weeks()

    existing = pd.read_sql_query(
        "SELECT * FROM submissions WHERE employee_id=%s",
        conn,
        params=(email,)
    )

    default_choices = [""] * 10
    if not existing.empty:
        row = existing.iloc[0]
        default_choices = [row[f"choice{i}"] or "" for i in range(1, 11)]
        st.info("You have already submitted. You can update your choices.")

    choices = []
    for i in range(1, 11):
        idx = weeks.index(default_choices[i-1]) + 1 if default_choices[i-1] in weeks else 0
        choice = st.selectbox(f"Choice {i}", [""] + weeks, index=idx, key=f"c{i}")
        choices.append(choice)

    if st.button("Save Choices"):
        c.execute(
            """
            INSERT INTO submissions VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (employee_id) DO UPDATE SET
                choice1=EXCLUDED.choice1,
                choice2=EXCLUDED.choice2,
                choice3=EXCLUDED.choice3,
                choice4=EXCLUDED.choice4,
                choice5=EXCLUDED.choice5,
                choice6=EXCLUDED.choice6,
                choice7=EXCLUDED.choice7,
                choice8=EXCLUDED.choice8,
                choice9=EXCLUDED.choice9,
                choice10=EXCLUDED.choice10
            """,
            (email, *choices)
        )
        conn.commit()
        st.success("Saved")

# ---------- ADMIN ----------
if st.session_state.user and st.session_state.role == "admin":
    st.title("Admin Panel")

    if st.button("Clear Submissions"):
        c.execute("DELETE FROM submissions")
        conn.commit()
        st.rerun()

    st.subheader("Employees")
    st.dataframe(get_employees())

    st.subheader("Change User Password")
    user_email = st.text_input("User Email")
    new_pw = st.text_input("New Password", type="password")

    if st.button("Update Password"):
        hashed = hash_pw(new_pw)
        c.execute(
            "UPDATE employees SET password_hash=%s WHERE employee_id=%s",
            (hashed, user_email)
        )
        conn.commit()
        st.success("Password updated")

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

    st.download_button("Download Results", res.to_csv(index=False), "results.csv")
