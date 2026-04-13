import streamlit as st
import pandas as pd
import sqlite3
import datetime

# -----------------------
# CONFIG
# -----------------------
ADMIN_PASSWORD = "admin123"  # change this

# -----------------------
# DATABASE SETUP
# -----------------------
conn = sqlite3.connect("data.db", check_same_thread=False)
conn.row_factory = sqlite3.Row
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
df["employee_id"] = df["employee_id"].astype(str)

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
# EMPLOYEE LOGIN
# -----------------------
st.title("Vacation Scheduler")

st.header("Employee Login")

login_id = st.text_input("Employee ID")
login_last = st.text_input("Last Name")

employee = None

if login_id and login_last:
    match = df[
        (df["employee_id"] == login_id) &
        (df["last_name"].str.lower() == login_last.lower())
    ]

    if not match.empty:
        employee = match.iloc[0]
        st.success(f"Welcome {employee['first_name']}")
    else:
        st.error("Invalid login")

# -----------------------
# SUBMISSION UI (ONLY IF LOGGED IN)
# -----------------------
if employee is not None:

    employee_id = employee["employee_id"]

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
                    INSERT INTO submissions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (employee_id, *choices))
                conn.commit()
                st.success("Submitted")

# -----------------------
# ADMIN LOGIN
# -----------------------
st.header("Admin Login")

admin_input = st.text_input("Enter Admin Password", type="password")
is_admin = admin_input == ADMIN_PASSWORD

# -----------------------
# ADMIN SECTION
# -----------------------
if is_admin:

    st.success("Admin Access Granted")

    st.subheader("Run Allocation")

    if st.button("Run Lottery"):
        c.execute("DELETE FROM results")

        employees = pd.read_csv("employees.csv")
        employees["employee_id"] = employees["employee_id"].astype(str)

        subs_rows = c.execute("SELECT * FROM submissions").fetchall()
        subs_dict = {row["employee_id"]: row for row in subs_rows}

        employees = employees[employees["employee_id"].isin(subs_dict.keys())]
        employees = employees.sort_values(by=["win_count", "hire_date"])

        taken_weeks = set()
        winners = []

        for _, emp in employees.iterrows():
            emp_id = emp["employee_id"]
            sub = subs_dict[emp_id]

            assigned = None

            for i in range(1, 11):
                choice = sub[f"choice{i}"]
                if choice and choice not in taken_weeks:
                    assigned = choice
                    taken_weeks.add(choice)
                    break

            if assigned:
                winners.append(emp_id)
                c.execute(
                    "INSERT INTO results (employee_id, assigned_week) VALUES (?, ?)",
                    (emp_id, assigned)
                )

        conn.commit()

        for emp_id in winners:
            df.loc[df["employee_id"] == emp_id, "win_count"] += 1

        df.to_csv("employees.csv", index=False)

        st.success("Lottery Complete")

    st.subheader("Results")
    results = c.execute("SELECT * FROM results").fetchall()
    st.write([dict(r) for r in results])

else:
    st.info("Enter admin password to access admin controls")
