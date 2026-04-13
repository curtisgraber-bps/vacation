import streamlit as st
import pandas as pd
import sqlite3
import datetime
import bcrypt

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
    win_count INTEGER,
    password_hash TEXT
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

# INITIAL LOAD
if c.execute("SELECT COUNT(*) FROM employees").fetchone()[0] == 0:
    df = pd.read_csv("employees.csv")
    df["employee_id"] = df["employee_id"].astype(str).str.strip()
    df["win_count"] = pd.to_numeric(df["win_count"], errors="coerce").fillna(0).astype(int)

    for _, row in df.iterrows():
        c.execute(
            "INSERT INTO employees (employee_id, first_name, last_name, hire_date, win_count) VALUES (?, ?, ?, ?, ?)",
            tuple(row)
        )
    conn.commit()

# HELPERS
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
    return [f"{start + datetime.timedelta(weeks=i)} to {start + datetime.timedelta(weeks=i, days=7)}" for i in range(52)]

# INIT WEEKS
if c.execute("SELECT COUNT(*) FROM weeks").fetchone()[0] == 0:
    for w in generate_weeks():
        c.execute("INSERT INTO weeks VALUES (?, ?)", (w, 1))
    conn.commit()

active_weeks = pd.read_sql_query("SELECT week FROM weeks WHERE enabled = 1", conn)["week"].tolist()

# SESSION
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.role = None
    st.session_state.user_id = None

# LOGIN
if not st.session_state.logged_in:

    st.title("Login")

    login_id = st.text_input("Employee ID")

    if login_id:
        employees_df = get_employees()
        emp = employees_df[employees_df["employee_id"] == str(login_id).strip()]

        if emp.empty:
            st.error("Employee not found")

        else:
            emp = emp.iloc[0]

            if not emp["password_hash"] or pd.isna(emp["password_hash"]):
                st.info("First time login – create your password")

                new_pw = st.text_input("Create Password", type="password")

                if st.button("Set Password"):
                    if not new_pw:
                        st.error("Enter a password")
                    else:
                        h = hash_pw(new_pw)
                        c.execute(
                            "UPDATE employees SET password_hash=? WHERE employee_id=?",
                            (h, str(login_id).strip())
                        )
                        conn.commit()
                        st.success("Password set. Log in now.")

            else:
                pw = st.text_input("Password", type="password")

                if st.button("Login"):
                    if check_pw(pw, emp["password_hash"]):
                        st.session_state.logged_in = True
                        st.session_state.role = "user"
                        st.session_state.user_id = str(login_id).strip()
                        st.rerun()
                    else:
                        st.error("Invalid password")

    st.markdown("---")
    st.markdown(" ")

    is_admin = st.checkbox("Admin login")

    if is_admin:
        admin_pw = st.text_input("Admin Password", type="password")

        if st.button("Admin Login"):
            if admin_pw == ADMIN_PASSWORD:
                st.session_state.logged_in = True
                st.session_state.role = "admin"
                st.rerun()
            else:
                st.error("Invalid admin password")

# LOGOUT
if st.session_state.logged_in:
    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()

# USER VIEW
if st.session_state.logged_in and st.session_state.role == "user":

    st.title("Vacation Scheduler")

    employee_id = st.session_state.user_id

    existing = c.execute(
        "SELECT 1 FROM submissions WHERE employee_id = ?", (employee_id,)
    ).fetchone()

    if existing:
        st.warning("Already submitted")
    else:
        choices = [st.selectbox(f"Choice {i}", [""] + active_weeks, key=f"c{i}") for i in range(1, 11)]

        if st.button("Submit Choices"):
            if all(not c for c in choices):
                st.error("Select at least one week")
            else:
                c.execute(
                    "INSERT INTO submissions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (employee_id, *choices)
                )
                conn.commit()
                st.success("Submitted")

# ADMIN VIEW
if st.session_state.logged_in and st.session_state.role == "admin":

    st.title("Admin Panel")

    if st.button("Clear Submissions"):
        c.execute("DELETE FROM submissions")
        conn.commit()

    if st.button("Clear Results"):
        c.execute("DELETE FROM results")
        conn.commit()

    # RESET INDIVIDUAL PASSWORD
    st.subheader("Reset Individual Password")

    emp_list = get_employees()
    emp_options = emp_list["employee_id"] + " - " + emp_list["first_name"] + " " + emp_list["last_name"]

    selected = st.selectbox("Select Employee", emp_options)

    if st.button("Reset Password"):
        emp_id = selected.split(" - ")[0]

        c.execute(
            "UPDATE employees SET password_hash=NULL WHERE employee_id=?",
            (emp_id,)
        )
        conn.commit()
        st.success("Password reset")

    # ADD EMPLOYEE
    st.subheader("Add Employee")

    with st.form("add_employee_form"):
        new_id = st.text_input("Employee ID")
        new_first = st.text_input("First Name")
        new_last = st.text_input("Last Name")
        new_hire = st.date_input("Hire Date")

        submitted = st.form_submit_button("Add Employee")

        if submitted:
            if not new_id or not new_first or not new_last:
                st.error("All fields required")
            else:
                try:
                    c.execute(
                        "INSERT INTO employees (employee_id, first_name, last_name, hire_date, win_count, password_hash) VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            str(new_id).strip(),
                            new_first,
                            new_last,
                            str(new_hire),
                            0,
                            None
                        )
                    )
                    conn.commit()
                    st.success("Employee added")
                except:
                    st.error("Employee ID exists")

    # EDIT EMPLOYEES
    st.subheader("Edit Employees")
    edit_df = st.data_editor(get_employees())

    if st.button("Save Employee Changes"):
        edit_df["employee_id"] = edit_df["employee_id"].astype(str).str.strip()
        edit_df["win_count"] = pd.to_numeric(edit_df["win_count"], errors="coerce").fillna(0).astype(int)

        c.execute("DELETE FROM employees")

        for _, row in edit_df.iterrows():
            c.execute(
                "INSERT INTO employees VALUES (?, ?, ?, ?, ?, ?)",
                (
                    row["employee_id"],
                    row["first_name"],
                    row["last_name"],
                    str(row["hire_date"]),
                    int(row["win_count"]),
                    row["password_hash"]
                )
            )

        conn.commit()
        st.success("Employees updated")

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

            for i in range(1, 11):
                choice = sub[f"choice{i}"]
                if choice and choice not in taken:
                    taken.add(choice)
                    winners.append(emp_id)
                    c.execute("INSERT INTO results VALUES (?, ?)", (emp_id, choice))
                    break

        for emp_id in winners:
            c.execute(
                "UPDATE employees SET win_count = CAST(win_count AS INTEGER) + 1 WHERE employee_id = ?",
                (emp_id,)
            )

        conn.commit()
        st.success("Lottery Complete")

    results_df = pd.read_sql_query("SELECT * FROM results", conn)
    fresh = get_employees()

    results_df = results_df.merge(
        fresh[["employee_id", "first_name", "last_name", "win_count"]],
        on="employee_id",
        how="left"
    )

    st.write(results_df)
