import streamlit as st
import pandas as pd
import psycopg2
import datetime
import random
from supabase import create_client

ADMIN_PASSWORD = "admin123"

# SUPABASE
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# DB
conn = psycopg2.connect(st.secrets["DB_URL"])
conn.autocommit = True
c = conn.cursor()

# TABLES
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

# HELPERS
def get_employees():
    df = pd.read_sql_query("SELECT * FROM employees", conn)
    df["employee_id"] = df["employee_id"].astype(str).str.strip()
    df["win_count"] = pd.to_numeric(df["win_count"], errors="coerce").fillna(0).astype(int)
    df["hire_date"] = pd.to_datetime(df["hire_date"], errors="coerce")
    return df

def generate_weeks():
    start = datetime.date(2027, 1, 1)
    while start.weekday() != 5:
        start += datetime.timedelta(days=1)
    return [f"{start + datetime.timedelta(weeks=i)} to {start + datetime.timedelta(days=7 + i*7)}" for i in range(52)]

def get_active_weeks():
    return pd.read_sql_query("""
        SELECT week FROM weeks
        WHERE enabled = TRUE
        ORDER BY TO_DATE(split_part(week, ' to ', 1), 'YYYY-MM-DD')
    """, conn)["week"].tolist()

# INIT
if pd.read_sql_query("SELECT COUNT(*) c FROM weeks", conn)["c"][0] == 0:
    for w in generate_weeks():
        c.execute("INSERT INTO weeks VALUES (%s,%s)", (w, True))

# SESSION
if "user" not in st.session_state:
    st.session_state.user = None
if "role" not in st.session_state:
    st.session_state.role = None

# LOGIN
if not st.session_state.user:
    st.title("Login")

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    col1, col2 = st.columns(2)

    if col1.button("Login"):
        res = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        if res.user:
            st.session_state.user = res.user
            st.session_state.role = "user"
            st.rerun()
        else:
            st.error("Invalid login")

    if col2.button("Sign Up"):
        res = supabase.auth.sign_up({
            "email": email,
            "password": password
        })
        if res.user:
            st.success("Account created")

    if st.button("Forgot Password"):
        supabase.auth.reset_password_for_email(email)
        st.success("Password reset email sent")

    if st.checkbox("Admin login"):
        pw = st.text_input("Admin Password", type="password")
        if st.button("Admin Login"):
            if pw == ADMIN_PASSWORD:
                st.session_state.user = {"email": "admin"}
                st.session_state.role = "admin"
                st.rerun()

# LOGOUT
if st.session_state.user:
    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()

# USER
if st.session_state.user and st.session_state.role == "user":
    st.title("Vacation Scheduler")

    email = st.session_state.user.email
    eid = email
    emps = get_employees()

if eid not in emps["employee_id"].values:
    st.error("You are not set up in the system. Contact admin.")
    st.stop()

    weeks = get_active_weeks()

    existing = pd.read_sql_query(
        "SELECT * FROM submissions WHERE employee_id=%s",
        conn,
        params=(eid,)
    )

    if not existing.empty:
        row = existing.iloc[0]
        for i in range(1, 11):
            if row[f"choice{i}"]:
                st.write(f"{i}. {row[f'choice{i}']}")
    else:
        choices = [st.selectbox(f"Choice {i}", [""] + weeks, key=f"c{i}") for i in range(1, 11)]

        if st.button("Submit"):
            c.execute(
                "INSERT INTO submissions VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (eid, *choices)
            )
            conn.commit()
            st.success("Submitted")

# ADMIN
if st.session_state.user and st.session_state.role == "admin":

    st.title("Admin Panel")

    # EMPLOYEES
    st.subheader("Employees")
    emps = get_employees()
    st.dataframe(emps)

    # ADD EMPLOYEE
    st.subheader("Add Employee")
    new_id = st.text_input("Email (Employee ID)")
    new_fn = st.text_input("First Name")
    new_ln = st.text_input("Last Name")
    new_hd = st.date_input("Hire Date")

    if st.button("Add Employee"):
        c.execute("INSERT INTO employees VALUES (%s,%s,%s,%s,%s)",
                  (new_id.strip(), new_fn, new_ln, new_hd, 0))
        conn.commit()
        st.success("Added")

    st.markdown("---")

    # ADMIN CREATE SUBMISSION
    st.subheader("Create / Edit Submission")

    users = emps["employee_id"].tolist()
    selected = st.selectbox("Select User", users)

    weeks = get_active_weeks()
    choices = [st.selectbox(f"Choice {i}", [""] + weeks, key=f"a{i}") for i in range(1, 11)]

    if st.button("Save Submission"):
        c.execute("DELETE FROM submissions WHERE employee_id=%s", (selected,))
        c.execute(
            "INSERT INTO submissions VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (selected, *choices)
        )
        conn.commit()
        st.success("Saved")

    st.markdown("---")

    # WEEKS
    st.subheader("Weeks")

    col1, col2 = st.columns(2)

    if col1.button("Select All Weeks"):
        c.execute("UPDATE weeks SET enabled=TRUE")
        conn.commit()
        st.rerun()

    if col2.button("Deselect All Weeks"):
        c.execute("UPDATE weeks SET enabled=FALSE")
        conn.commit()
        st.rerun()

    weeks_df = pd.read_sql_query("SELECT * FROM weeks", conn)

    updates = []
    for _, row in weeks_df.iterrows():
        val = st.checkbox(row["week"], value=row["enabled"])
        if val != row["enabled"]:
            updates.append((val, row["week"]))

    if updates:
        for val, week in updates:
            c.execute("UPDATE weeks SET enabled=%s WHERE week=%s", (val, week))
        conn.commit()

    st.markdown("---")

    # LOTTERY
    if st.button("Run Lottery"):
        c.execute("DELETE FROM results")

        subs = pd.read_sql_query("SELECT * FROM submissions", conn)
        emps = get_employees()

        emps = emps[emps["employee_id"].isin(subs["employee_id"])]
        emps = emps.sort_values(by=["win_count","hire_date"])

        taken = set()

        for _, emp in emps.iterrows():
            sub = subs[subs["employee_id"] == emp["employee_id"]].iloc[0]

            for i in range(1,11):
                ch = sub[f"choice{i}"]
                if ch and ch not in taken:
                    taken.add(ch)
                    c.execute("INSERT INTO results VALUES (%s,%s)", (emp["employee_id"], ch))
                    break

        conn.commit()

    res = pd.read_sql_query("SELECT * FROM results", conn)
    st.dataframe(res)

    st.download_button(
        "Download Results",
        res.to_csv(index=False).encode("utf-8"),
        "results.csv",
        "text/csv"
    )
