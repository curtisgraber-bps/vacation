import streamlit as st
import pandas as pd
import sqlite3
import datetime

# -----------------------
# DATABASE SETUP
# -----------------------
conn = sqlite3.connect("data.db", check_same_thread=False)
c = conn.cursor()

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

# -----------------------
# LOAD EMPLOYEES
# -----------------------
df = pd.read_csv("employees.csv")

# FORCE employee_id to string
df["employee_id"] = df["employee_id"].astype(str)

df["full_name"] = df["first_name"] + " " + df["last_name"]

# -----------------------
# GENERATE WEEKS
# -----------------------
def generate_weeks(year=2027):
    start = datetime.date(year, 1, 1)
    while start.weekday() != 5:
        start += datetime.timedelta(days=1)

    weeks = []
    for i in range(52):
        week_start = start + datetime.timedelta(weeks=i)
        week_end = week_start + datetime.timedelta(days=7)
        weeks.append(f"{week_start} to {week_end}")

    return weeks

weeks = generate_weeks()

# -----------------------
# UI - SUBMISSIONS
# -----------------------
st.title("Vacation Scheduler")

st.header("Submit Your Choices")

selected = st.selectbox("Select Your Name", df["full_name"])
employee_id = df[df["full_name"] == selected]["employee_id"].values[0]

existing = c.execute(
    "SELECT 1 FROM submissions WHERE employee_id = ?",
    (employee_id,)
).fetchone()

if existing:
    st.warning("Already submitted")
else:
    choices = []
    for i in range(1, 11):
        choice = st.selectbox(f"Choice {i}", [""] + weeks, key=f"choice_{i}")
        choices.append(choice)

    if st.button("Submit"):
        if all(not c for c in choices):
            st.error("Select at least one week")
        else:
            c.execute("""
                INSERT INTO submissions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (employee_id, *choices))
            conn.commit()
            st.success("Submitted")

# -----------------------
# RUN ALLOCATION
# -----------------------
st.header("Admin: Run Allocation")

if st.button("Run Lottery"):
    c.execute("DELETE FROM results")

    employees = pd.read_csv("employees.csv")
    employees["employee_id"] = employees["employee_id"].astype(str)

    subs = pd.read_sql_query("SELECT * FROM submissions", conn)
    subs["employee_id"] = subs["employee_id"].astype(str)

    merged = pd.merge(employees, subs, on="employee_id")

    merged = merged.sort_values(by=["win_count", "hire_date"])

    taken_weeks = set()

    for _, row in merged.iterrows():
        assigned = None

        for i in range(1, 11):
            choice = row[f"choice{i}"]
            if choice and choice not in taken_weeks:
                assigned = choice
                taken_weeks.add(choice)
                break

        if assigned:
            c.execute(
                "INSERT INTO results (employee_id, assigned_week) VALUES (?, ?)",
                (row["employee_id"], assigned)
            )

    conn.commit()
    st.success("Lottery Complete")

# -----------------------
# VIEW RESULTS
# -----------------------
st.header("Results")
results = c.execute("SELECT * FROM results").fetchall()
st.write(results)
