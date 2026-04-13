import streamlit as st
import pandas as pd
import sqlite3
import datetime

ADMIN_PASSWORD = "admin123"

conn = sqlite3.connect("data.db", check_same_thread=False)
conn.row_factory = sqlite3.Row
c = conn.cursor()

# -----------------------
# TABLES
# -----------------------
c.execute("""
CREATE TABLE IF NOT EXISTS employees (
    employee_id TEXT PRIMARY KEY,
    first_name TEXT,
    last_name TEXT,
    hire_date TEXT,
    win_count INTEGER
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS submissions (
    employee_id TEXT PRIMARY KEY,
    choice1 TEXT,
    choice2 TEXT,
    choice3 TEXT,
    choice4 TEXT,
    choice5 TEXT,
    choice6 TEXT,
    choice7 TEXT,
    choice8 TEXT,
    choice9 TEXT,
    choice10 TEXT
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS results (
    employee_id TEXT,
    assigned_week TEXT
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS weeks (
    week TEXT PRIMARY KEY,
    enabled INTEGER
)
""")

# -----------------------
# LOAD CSV INTO DB (ONCE)
# -----------------------
if c.execute("SELECT COUNT(*) FROM employees").fetchone()[0] == 0:
    df = pd.read_csv("employees.csv")
    df["employee_id"] = df["employee_id"].astype(str)

    for _, row in df.iterrows():
        c.execute("""
            INSERT INTO employees VALUES (?, ?, ?, ?, ?)
        """, (
            row["employee_id"],
            row["first_name"],
            row["last_name"],
            row["hire_date"],
            row["win_count"]
        ))

    conn.commit()

# -----------------------
# LOAD EMPLOYEES FROM DB
# -----------------------
employees_df = pd.read_sql_query("SELECT * FROM employees", conn)

# -----------------------
# GENERATE WEEKS
# -----------------------
def generate_weeks(year=2027):
    start = datetime.date(year, 1, 1)
    while start.weekday() != 5:
        start += datetime.timedelta(days=1)

    weeks = []
    for i in range(52):
        s = start + datetime.timedelta(weeks=i)
        e = s + datetime.timedelta(days=7)
        weeks.append(f"{s} to {e}")
    return weeks

all_weeks = generate_weeks()

if c.execute("SELECT COUNT(*) FROM weeks").fetchone()[0] == 0:
    for w in all_weeks:
        c.execute("INSERT INTO weeks VALUES (?, ?)", (w, 1))
    conn.commit()

active_weeks = pd.read_sql_query(
    "SELECT week FROM weeks WHERE enabled = 1", conn
)["week"].tolist()

# -----------------------
# LOGIN
# -----------------------
st.title("Vacation Scheduler")

login_id = st.text_input("Employee ID")
login_last = st.text_input("Last Name")

employee = None

if login_id and login_last:
    match = employees_df[
        (employees_df["employee_id"] == login_id) &
        (employees_df["last_name"].str.lower() == login_last.lower())
    ]

    if not match.empty:
        employee = match.iloc[0]
        st.success(f"Welcome {employee['first_name']}")
    else:
        st.error("Invalid login")

# -----------------------
# SUBMIT
# -----------------------
if employee is not None:

    employee_id = employee["employee_id"]

    existing = c.execute(
        "SELECT 1 FROM submissions WHERE employee_id = ?",
        (employee_id,)
    ).fetchone()

    if existing:
        st.warning("Already submitted")
    else:
        choices = []
        for i in range(1, 11):
            choice = st.selectbox(f"Choice {i}", [""] + active_weeks, key=f"c{i}")
            choices.append(choice)

        if st.button("Submit"):
            if all(not c for c in choices):
                st.error("Select at least one week")
            else:
                c.execute(
                    "INSERT INTO submissions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (employee_id, *choices)
                )
                conn.commit()
                st.success("Submitted")

# -----------------------
# ADMIN
# -----------------------
admin = st.text_input("Admin Password", type="password") == ADMIN_PASSWORD

if admin:

    st.success("Admin")

    if st.button("Run Lottery"):
        c.execute("DELETE FROM results")

        employees = pd.read_sql_query("SELECT * FROM employees", conn)

        subs_rows = c.execute("SELECT * FROM submissions").fetchall()
        subs_dict = {row["employee_id"]: row for row in subs_rows}

        employees = employees[employees["employee_id"].isin(subs_dict.keys())]
        employees = employees.sort_values(by=["win_count", "hire_date"])

        taken = set()
        winners = []

        for _, emp in employees.iterrows():
            emp_id = emp["employee_id"]
            sub = subs_dict[emp_id]

            for i in range(1, 11):
                choice = sub[f"choice{i}"]
                if choice and choice not in taken:
                    taken.add(choice)
                    winners.append((emp_id, choice))
                    break

        for emp_id, week in winners:
            c.execute("INSERT INTO results VALUES (?, ?)", (emp_id, week))

            # UPDATE WIN COUNT IN DB
            c.execute(
                "UPDATE employees SET win_count = win_count + 1 WHERE employee_id = ?",
                (emp_id,)
            )

        conn.commit()
        st.success("Lottery Complete + Persisted")

    results = pd.read_sql_query("SELECT * FROM results", conn)
    st.write(results)
