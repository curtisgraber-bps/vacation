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
    employee_id TEXT,
    choice1 TEXT,
    choice2 TEXT,
    choice3 TEXT
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

    # Find first Saturday
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

st.header("Select Your Vacation Weeks")

selected = st.selectbox("Select Your Name", df["full_name"])
employee_id = df[df["full_name"] == selected]["employee_id"].values[0]

choice1 = st.selectbox("First Choice", [""] + weeks)
choice2 = st.selectbox("Second Choice", [""] + weeks)
choice3 = st.selectbox("Third Choice", [""] + weeks)

# -----------------------
# SUBMIT
# -----------------------
if st.button("Submit"):
    if not choice1 and not choice2 and not choice3:
        st.error("Select at least one week")
    else:
        c.execute(
            "INSERT INTO submissions (employee_id, choice1, choice2, choice3) VALUES (?, ?, ?, ?)",
            (employee_id, choice1, choice2, choice3)
        )
        conn.commit()
        st.success("Submitted")

# -----------------------
# ADMIN VIEW
# -----------------------
st.header("Admin View")
rows = c.execute("SELECT * FROM submissions").fetchall()
st.write(rows)
