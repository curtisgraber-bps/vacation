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

# -----------------------
# LOAD EMPLOYEES
# -----------------------
df = pd.read_csv("employees.csv")
df["full_name"] = df["first_name"] + " " + df["last_name"]

# -----------------------
# GENERATE SATURDAY WEEKS (2027)
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
# UI
# -----------------------
st.title("Vacation Scheduler")

st.header("Select Your Vacation Weeks (Up to 10 Choices)")

selected = st.selectbox("Select Your Name", df["full_name"])
employee_id = df[df["full_name"] == selected]["employee_id"].values[0]

# Check if already submitted
existing = c.execute(
    "SELECT 1 FROM submissions WHERE employee_id = ?",
    (employee_id,)
).fetchone()

if existing:
    st.warning("You have already submitted your selections.")
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
                INSERT INTO submissions (
                    employee_id, choice1, choice2, choice3, choice4,
                    choice5, choice6, choice7, choice8, choice9, choice10
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (employee_id, *choices))

            conn.commit()
            st.success("Submitted")

# -----------------------
# ADMIN VIEW
# -----------------------
st.header("Admin View")
rows = c.execute("SELECT * FROM submissions").fetchall()
st.write(rows)
