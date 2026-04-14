import streamlit as st
import pandas as pd
import psycopg2
import datetime
import bcrypt
import random

ADMIN_PASSWORD = "admin123"

conn = psycopg2.connect(
    "postgresql://postgres.ugnxfszbikjuzaklsnji:BarriePoliceAssociation2026@aws-1-ca-central-1.pooler.supabase.com:5432/postgres"
)
conn.autocommit = True
c = conn.cursor()

# TABLES
c.execute("""CREATE TABLE IF NOT EXISTS employees (
    employee_id TEXT PRIMARY KEY,
    first_name TEXT,
    last_name TEXT,
    hire_date DATE,
    win_count INTEGER DEFAULT 0,
    password_hash TEXT
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

def get_employees():
    df = pd.read_sql_query("SELECT * FROM employees", conn)
    df["employee_id"] = df["employee_id"].astype(str).str.strip()
    df["win_count"] = pd.to_numeric(df["win_count"], errors="coerce").fillna(0).astype(int)
    df["hire_date"] = pd.to_datetime(df["hire_date"], errors="coerce")
    return df

def hash_pw(pw):
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

def check_pw(pw, hashed):
    if not hashed or pd.isna(hashed):
        return False
    return bcrypt.checkpw(pw.encode(), hashed.encode())

def generate_weeks():
    start = datetime.date(2027, 1, 1)
    while start.weekday() != 5:
        start += datetime.timedelta(days=1)
    return [f"{start + datetime.timedelta(weeks=i)} to {start + datetime.timedelta(days=7 + i*7)}" for i in range(52)]

def get_active_weeks():
    return pd.read_sql_query("""
        SELECT week
        FROM weeks
        WHERE enabled = TRUE
        ORDER BY TO_DATE(split_part(week, ' to ', 1), 'YYYY-MM-DD')
    """, conn)["week"].tolist()

# INIT
if pd.read_sql_query("SELECT COUNT(*) c FROM weeks", conn)["c"][0] == 0:
    for w in generate_weeks():
        c.execute("INSERT INTO weeks VALUES (%s,%s)", (w, True))

# SESSION
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.role = None
    st.session_state.user_id = None

# LOGIN
if not st.session_state.logged_in:
    st.title("Login")

    login_id = st.text_input("Employee ID", key="login_id")

    if login_id:
        emps = get_employees()
        emp = emps[emps["employee_id"] == login_id]

        if not emp.empty:
            emp = emp.iloc[0]

            if not emp["password_hash"] or pd.isna(emp["password_hash"]):
                pw = st.text_input("Create Password", type="password", key="create_pw")
                if st.button("Set Password", key="set_pw"):
                    c.execute("UPDATE employees SET password_hash=%s WHERE employee_id=%s",
                              (hash_pw(pw), login_id))
                    conn.commit()
            else:
                pw = st.text_input("Password", type="password", key="login_pw")
                if st.button("Login", key="login_btn"):
                    if check_pw(pw, emp["password_hash"]):
                        st.session_state.logged_in = True
                        st.session_state.role = "user"
                        st.session_state.user_id = login_id
                        st.rerun()

    if st.checkbox("Admin login", key="admin_toggle"):
        pw = st.text_input("Admin Password", type="password", key="admin_pw")
        if st.button("Admin Login", key="admin_login_btn"):
            if pw == ADMIN_PASSWORD:
                st.session_state.logged_in = True
                st.session_state.role = "admin"
                st.rerun()

# LOGOUT
if st.session_state.logged_in:
    if st.button("Logout", key="logout"):
        st.session_state.clear()
        st.rerun()

# USER
if st.session_state.logged_in and st.session_state.role == "user":
    st.title("Vacation Scheduler")

    weeks = get_active_weeks()
    eid = st.session_state.user_id

    existing = pd.read_sql_query(
        "SELECT * FROM submissions WHERE employee_id=%s", conn, params=(eid,)
    )

    if not existing.empty:
        row = existing.iloc[0]
        for i in range(1, 11):
            if row[f"choice{i}"]:
                st.write(f"{i}. {row[f'choice{i}']}")
    else:
        choices = [st.selectbox(f"Choice {i}", [""] + weeks, key=f"c{i}") for i in range(1, 11)]

        if st.button("Submit", key="submit"):
            c.execute("INSERT INTO submissions VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                      (eid, *choices))
            conn.commit()
            st.rerun()

# ADMIN
if st.session_state.logged_in and st.session_state.role == "admin":

    st.title("Admin Panel")

    # --- WEEKS ---
    st.subheader("Weeks")

    col1, col2 = st.columns(2)
    select_all = col1.button("Select All Weeks", key="select_all")
    deselect_all = col2.button("Deselect All Weeks", key="deselect_all")

    if select_all:
        c.execute("UPDATE weeks SET enabled=TRUE")
        conn.commit()
        st.rerun()

    if deselect_all:
        c.execute("UPDATE weeks SET enabled=FALSE")
        conn.commit()
        st.rerun()

    st.markdown("---")

    weeks_df = pd.read_sql_query("""
        SELECT *
        FROM weeks
        ORDER BY TO_DATE(split_part(week, ' to ', 1), 'YYYY-MM-DD')
    """, conn)

    for _, row in weeks_df.iterrows():
        key = f"week_{row['week']}"

        val = st.checkbox(row["week"], value=row["enabled"], key=key)

        if val != row["enabled"]:
            c.execute(
                "UPDATE weeks SET enabled=%s WHERE week=%s",
                (val, row["week"])
            )
            conn.commit()
            st.rerun()

    st.markdown("---")

    # --- LOTTERY ---
    if st.button("Run Lottery", key="run_lottery"):
        c.execute("DELETE FROM results")

        emps = get_employees()
        subs = pd.read_sql_query("SELECT * FROM submissions", conn)

        emps = emps[emps["employee_id"].isin(subs["employee_id"])]
        emps = emps.sort_values(by=["win_count", "hire_date"])

        taken = set()

        for _, emp in emps.iterrows():
            sub = subs[subs["employee_id"] == emp["employee_id"]].iloc[0]

            for i in range(1, 11):
                ch = sub[f"choice{i}"]
                if ch and ch not in taken:
                    taken.add(ch)
                    c.execute("INSERT INTO results VALUES (%s,%s)", (emp["employee_id"], ch))
                    c.execute("UPDATE employees SET win_count = win_count + 1 WHERE employee_id=%s",
                              (emp["employee_id"],))
                    break

        conn.commit()
        st.rerun()
