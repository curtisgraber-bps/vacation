import streamlit as st
import pandas as pd
import sqlite3
import datetime

ADMIN_PASSWORD = "admin123"

conn = sqlite3.connect("data.db", check_same_thread=False)
conn.row_factory = sqlite3.Row
c = conn.cursor()

# TABLES
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

# LOAD CSV ONCE
if c.execute("SELECT COUNT(*) FROM employees").fetchone()[0] == 0:
    df = pd.read_csv("employees.csv")
    df["employee_id"] = df["employee_id"].astype(str).str.strip()
    df["win_count"] = pd.to_numeric(df["win_count"], errors="coerce").fillna(0).astype(int)

    for _, row in df.iterrows():
        c.execute("INSERT INTO employees VALUES (?, ?, ?, ?, ?)", tuple(row))
    conn.commit()

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
    return [f"{start + datetime.timedelta(weeks=i)} to {start + datetime.timedelta(weeks=i, days=7)}" for i in range(52)]

if c.execute("SELECT COUNT(*) FROM weeks").fetchone()[0] == 0:
    for w in generate_weeks():
        c.execute("INSERT INTO weeks VALUES (?, ?)", (w, 1))
    conn.commit()

active_weeks = pd.read_sql_query("SELECT week FROM weeks WHERE enabled = 1", conn)["week"].tolist()

# LOGIN
st.title("Vacation Scheduler")

login_id = st.text_input("Employee ID")
login_last = st.text_input("Last Name")

employees_df = get_employees()
employee = None

if login_id and login_last:
    match = employees_df[
        (employees_df["employee_id"] == str(login_id).strip()) &
        (employees_df["last_name"].str.lower() == login_last.lower())
    ]
    if not match.empty:
        employee = match.iloc[0]
        st.success(f"Welcome {employee['first_name']}")
    else:
        st.error("Invalid login")

# SUBMISSION
if employee is not None:
    emp_id = str(employee["employee_id"]).strip()

    existing = c.execute("SELECT 1 FROM submissions WHERE employee_id = ?", (emp_id,)).fetchone()

    if existing:
        st.warning("Already submitted")
    else:
        choices = [st.selectbox(f"Choice {i}", [""] + active_weeks, key=f"c{i}") for i in range(1,11)]

        if st.button("Submit"):
            if all(not c for c in choices):
                st.error("Select at least one week")
            else:
                c.execute("INSERT INTO submissions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (emp_id, *choices))
                conn.commit()
                st.success("Submitted")

# ADMIN
admin = st.text_input("Admin Password", type="password") == ADMIN_PASSWORD

if admin:
    st.success("Admin Access")

    if st.button("Clear Submissions"):
        c.execute("DELETE FROM submissions")
        conn.commit()

    if st.button("Clear Results"):
        c.execute("DELETE FROM results")
        conn.commit()

    st.subheader("Run Lottery")

    if st.button("Run Lottery"):
        c.execute("DELETE FROM results")

        employees = get_employees()
        subs = {str(r["employee_id"]).strip(): r for r in c.execute("SELECT * FROM submissions")}

        employees = employees[employees["employee_id"].isin(subs.keys())]
        employees = employees.sort_values(by=["win_count", "hire_date"])

        taken = set()
        winners = []

        for _, emp in employees.iterrows():
            emp_id = emp["employee_id"]
            sub = subs[emp_id]

            for i in range(1,11):
                choice = sub[f"choice{i}"]
                if choice and choice not in taken:
                    taken.add(choice)
                    winners.append(emp_id)
                    c.execute("INSERT INTO results VALUES (?, ?)", (emp_id, choice))
                    break

        # CRITICAL FIX: only increment ONCE per run
        for emp_id in winners:
            c.execute("UPDATE employees SET win_count = CAST(win_count AS INTEGER) + 1 WHERE employee_id = ?", (emp_id,))

        conn.commit()
        st.success("Lottery Complete")

    # RESULTS
    results_df = pd.read_sql_query("SELECT * FROM results", conn)
    fresh = get_employees()

    results_df = results_df.merge(
        fresh[["employee_id","first_name","last_name","win_count"]],
        on="employee_id",
        how="left"
    )

    st.write(results_df)
