import streamlit as st
import pandas as pd
import psycopg2
import datetime
import bcrypt
import random

ADMIN_PASSWORD = "admin123"

# SUPABASE CONNECTION
conn = psycopg2.connect(
    "postgresql://postgres.ugnxfszbikjuzaklsnji:BPApwisl33t@aws-1-ca-central-1.pooler.supabase.com:5432/postgres"
)
conn.autocommit = True
c = conn.cursor()

# TABLES
c.execute("""
CREATE TABLE IF NOT EXISTS employees (
    employee_id TEXT PRIMARY KEY,
    first_name TEXT,
    last_name TEXT,
    hire_date DATE,
    win_count INTEGER DEFAULT 0,
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
    enabled BOOLEAN
)
""")

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
count = pd.read_sql_query("SELECT COUNT(*) as c FROM weeks", conn)["c"][0]
if count == 0:
    for w in generate_weeks():
        c.execute("INSERT INTO weeks VALUES (%s, %s)", (w, True))

active_weeks = pd.read_sql_query("SELECT week FROM weeks WHERE enabled = TRUE", conn)["week"].tolist()

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
                            "UPDATE employees SET password_hash=%s WHERE employee_id=%s",
                            (h, str(login_id).strip())
                        )
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

    c.execute("SELECT * FROM submissions WHERE employee_id = %s", (employee_id,))
    existing = c.fetchone()

    if existing:
        st.success("Submission received")

        choices = [existing[i] for i in range(1, 11) if existing[i]]

        st.subheader("Your Selections")
        for i, choice in enumerate(choices, 1):
            st.write(f"{i}. {choice}")
    else:
        choices = [st.selectbox(f"Choice {i}", [""] + active_weeks, key=f"c{i}") for i in range(1, 11)]

        if st.button("Submit Choices"):
            if all(not c for c in choices):
                st.error("Select at least one week")
            else:
                c.execute(
                    "INSERT INTO submissions VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (employee_id, *choices)
                )
                st.success("Submitted")
                st.rerun()

# ADMIN VIEW
if st.session_state.logged_in and st.session_state.role == "admin":

    st.title("Admin Panel")

    if st.button("Clear Submissions"):
        c.execute("DELETE FROM submissions")

    if st.button("Clear Results"):
        c.execute("DELETE FROM results")

if st.button("Generate Test Submissions"):
    try:
        c.execute("DELETE FROM submissions")

        employees = get_employees()

        for _, emp in employees.iterrows():
            emp_id = emp["employee_id"]

            num_choices = random.randint(1, 10)
            choices = random.sample(active_weeks, min(num_choices, len(active_weeks)))
            choices += [""] * (10 - len(choices))

            c.execute(
                "INSERT INTO submissions VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (emp_id, *choices)
            )

        conn.commit()  # <-- THIS IS THE FIX

        st.success(f"Test submissions generated for {len(employees)} employees")

    except Exception as e:
        st.error(f"Error: {e}")

    # WHO SUBMITTED
    st.subheader("Who Has Submitted")

    subs = pd.read_sql_query("SELECT employee_id FROM submissions", conn)
    emps = get_employees()

    view = subs.merge(
        emps[["employee_id", "first_name", "last_name"]],
        on="employee_id",
        how="left"
    )

    st.write(view[["first_name", "last_name"]].sort_values(by="last_name"))

    # SUBMISSION DETAILS
    st.subheader("Submission Details")

    subs_full = pd.read_sql_query("SELECT * FROM submissions", conn)

    view_full = subs_full.merge(
        emps[["employee_id", "first_name", "last_name"]],
        on="employee_id",
        how="left"
    )

    def combine_choices(row):
        vals = []
        for i in range(1, 11):
            col = f"choice{i}"
            if col in row and pd.notna(row[col]) and row[col] != "":
                vals.append(str(row[col]))
        return ", ".join(vals)

    view_full["choices"] = view_full.apply(combine_choices, axis=1)

    st.write(view_full[["first_name", "last_name", "choices"]].sort_values(by="last_name"))

    # RUN LOTTERY
    st.subheader("Run Lottery")

    if st.button("Run Lottery"):
        c.execute("DELETE FROM results")

        employees = get_employees()
        subs = pd.read_sql_query("SELECT * FROM submissions", conn)

        employees = employees[employees["employee_id"].isin(subs["employee_id"])]
        employees = employees.sort_values(by=["win_count", "hire_date"])

        taken = set()
        winners = []

        for _, emp in employees.iterrows():
            sub = subs[subs["employee_id"] == emp["employee_id"]].iloc[0]

            for i in range(1, 11):
                choice = sub[f"choice{i}"]
                if choice and choice not in taken:
                    taken.add(choice)
                    winners.append(emp["employee_id"])
                    c.execute("INSERT INTO results VALUES (%s, %s)", (emp["employee_id"], choice))
                    break

        for emp_id in winners:
            c.execute("UPDATE employees SET win_count = win_count + 1 WHERE employee_id = %s", (emp_id,))

        st.success("Lottery Complete")

    # RESULTS
    results_df = pd.read_sql_query("SELECT * FROM results", conn)

    results_df = results_df.merge(
        emps[["employee_id", "first_name", "last_name", "win_count"]],
        on="employee_id",
        how="left"
    )

    st.write(results_df)

    csv = results_df.to_csv(index=False).encode("utf-8")

    st.download_button("Download Results", csv, "results.csv", "text/csv")
