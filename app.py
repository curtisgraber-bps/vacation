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
# ADMIN LOGIN
# -----------------------
st.header("Admin Login")

admin_input = st.text_input("Enter Admin Password", type="password")

is_admin = admin_input == ADMIN_PASSWORD

# -----------------------
# ADMIN SECTION (LOCKED)
# -----------------------
if is_admin:

    st.success("Admin Access Granted")

    # -----------------------
    # RUN ALLOCATION
    # -----------------------
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

        # update win counts
        for emp_id in winners:
            df.loc[df["employee_id"] == emp_id, "win_count"] += 1

        df.drop(columns=["full_name"]).to_csv("employees.csv", index=False)

        st.success("Lottery Complete")

    # -----------------------
    # EDIT EMPLOYEES
    # -----------------------
    st.subheader("Edit Employees")

    edit_df = st.data_editor(df, num_rows="dynamic")

    if st.button("Save Employee Changes"):
        edit_df.drop(columns=["full_name"]).to_csv("employees.csv", index=False)
        st.success("Employee data updated")

    # -----------------------
    # EDIT RESULTS
    # -----------------------
    st.subheader("Edit Results")

    results_df = pd.read_sql_query("SELECT * FROM results", conn)
    edited_results = st.data_editor(results_df, num_rows="dynamic")

    if st.button("Save Result Changes"):
        c.execute("DELETE FROM results")

        for _, row in edited_results.iterrows():
            c.execute(
                "INSERT INTO results (employee_id, assigned_week) VALUES (?, ?)",
                (row["employee_id"], row["assigned_week"])
            )

        conn.commit()
        st.success("Results updated")

    # -----------------------
    # VIEW RESULTS
    # -----------------------
    st.subheader("Final Results")
    final = c.execute("SELECT * FROM results").fetchall()
    st.write([dict(r) for r in final])

else:
    st.info("Enter admin password to access admin controls")
