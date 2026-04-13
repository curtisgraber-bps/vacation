import streamlit as st
import pandas as pd
import sqlite3
import datetime

# -----------------------
# CONFIG
# -----------------------
ADMIN_PASSWORD = "admin123"

# -----------------------
# DATABASE
# -----------------------
conn = sqlite3.connect("data.db", check_same_thread=False)
conn.row_factory = sqlite3.Row
c = conn.cursor()

# tables
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
        s = start + datetime.timedelta(weeks=i)
        e = s + datetime.timedelta(days=7)
        weeks.append(f"{s} to {e}")
    return weeks

all_weeks = generate_weeks()

# -----------------------
# INIT WEEKS
# -----------------------
existing_weeks = c.execute("SELECT week FROM weeks").fetchall()
if not existing_weeks:
    for w in all_weeks:
        c.execute("INSERT INTO weeks VALUES (?, ?)", (w, 1))
    conn.commit()

# -----------------------
# ACTIVE WEEKS
# -----------------------
weeks_df = pd.read_sql_query("SELECT * FROM weeks", conn)
active_weeks = weeks_df[weeks_df["enabled"] == 1]["week"].tolist()

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
# SUBMISSION
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
            choice = st.selectbox(f"Choice {i}", [""] + active_weeks, key=f"choice_{i}")
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
# ADMIN LOGIN
# -----------------------
st.header("Admin Login")

admin_input = st.text_input("Admin Password", type="password")
is_admin = admin_input == ADMIN_PASSWORD

# -----------------------
# ADMIN PANEL
# -----------------------
if is_admin:

    st.success("Admin Access Granted")

    # -----------------------
    # RESET CONTROLS
    # -----------------------
    st.subheader("Reset Data (Testing Only)")

    if st.button("Clear All Submissions"):
        c.execute("DELETE FROM submissions")
        conn.commit()
        st.success("All submissions cleared")

    if st.button("Clear Results"):
        c.execute("DELETE FROM results")
        conn.commit()
        st.success("Results cleared")

    # -----------------------
    # MANAGE WEEKS
    # -----------------------
    st.subheader("Manage Weeks")

    weeks_df = pd.read_sql_query("SELECT * FROM weeks", conn)
    edited_weeks = st.data_editor(weeks_df)

    if st.button("Save Week Changes"):
        c.execute("DELETE FROM weeks")
        for _, row in edited_weeks.iterrows():
            c.execute(
                "INSERT INTO weeks VALUES (?, ?)",
                (row["week"], int(row["enabled"]))
            )
        conn.commit()
        st.success("Weeks updated")

    # -----------------------
    # RUN LOTTERY
    # -----------------------
    st.subheader("Run Lottery")

    if st.button("Run Lottery"):
        c.execute("DELETE FROM results")

        employees = pd.read_csv("employees.csv")
        employees["employee_id"] = employees["employee_id"].astype(str)

        subs_rows = c.execute("SELECT * FROM submissions").fetchall()
        subs_dict = {row["employee_id"]: row for row in subs_rows}

        employees = employees[employees["employee_id"].isin(subs_dict.keys())]
        employees = employees.sort_values(by=["win_count", "hire_date"])

        active_weeks = pd.read_sql_query(
            "SELECT week FROM weeks WHERE enabled = 1", conn
        )["week"].tolist()

        taken_weeks = set()
        winners = []

        for _, emp in employees.iterrows():
            emp_id = emp["employee_id"]
            sub = subs_dict[emp_id]

            for i in range(1, 11):
                choice = sub[f"choice{i}"]
                if choice and choice not in taken_weeks and choice in active_weeks:
                    taken_weeks.add(choice)
                    winners.append((emp_id, choice))
                    break

        for emp_id, week in winners:
            c.execute(
                "INSERT INTO results VALUES (?, ?)",
                (emp_id, week)
            )

        conn.commit()
        st.success("Lottery Complete")

    # -----------------------
    # RESULTS + EXPORT
    # -----------------------
    st.subheader("Results")

    results_df = pd.read_sql_query("SELECT * FROM results", conn)

    results_df = results_df.merge(
        df[["employee_id", "first_name", "last_name"]],
        on="employee_id",
        how="left"
    )

    results_df = results_df[
        ["employee_id", "first_name", "last_name", "assigned_week"]
    ]

    st.write(results_df)

    csv = results_df.to_csv(index=False).encode("utf-8")

    st.download_button(
        "Download Results CSV",
        data=csv,
        file_name="vacation_results.csv",
        mime="text/csv"
    )

else:
    st.info("Enter admin password to access admin controls")
