import streamlit as st
import pandas as pd
import psycopg2
import datetime
import bcrypt

ADMIN_PASSWORD = "admin123"

conn = psycopg2.connect(st.secrets["DB_URL"])
conn.autocommit = True
c = conn.cursor()

# ---------- TABLES ----------
c.execute("""CREATE TABLE IF NOT EXISTS employees (
    employee_id TEXT PRIMARY KEY,
    first_name TEXT,
    last_name TEXT,
    hire_date DATE,
    win_count INTEGER DEFAULT 0,
    password_hash TEXT
)""")

c.execute("""CREATE TABLE IF NOT EXISTS submissions (
    employee_id TEXT PRIMARY KEY,
    choice1 TEXT, choice2 TEXT, choice3 TEXT, choice4 TEXT, choice5 TEXT,
    choice6 TEXT, choice7 TEXT, choice8 TEXT, choice9 TEXT, choice10 TEXT
)""")

c.execute("""CREATE TABLE IF NOT EXISTS results (
    employee_id TEXT,
    assigned_week TEXT
)""")

c.execute("""CREATE TABLE IF NOT EXISTS weeks (
    week TEXT PRIMARY KEY,
    enabled BOOLEAN
)""")

# ---------- HELPERS ----------
def hash_pw(pw):
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

def check_pw(pw, hashed):
    return bcrypt.checkpw(pw.encode(), hashed.encode())

def get_employees():
    return pd.read_sql_query("SELECT * FROM employees ORDER BY employee_id", conn)

def generate_weeks():
    start = datetime.date(2027, 1, 1)
    while start.weekday() != 5:
        start += datetime.timedelta(days=1)
    return [str(start + datetime.timedelta(weeks=i)) for i in range(52)]

def get_active_weeks():
    df = pd.read_sql_query("SELECT week FROM weeks WHERE enabled = TRUE ORDER BY week", conn)
    return df["week"].tolist() if not df.empty else []

# INIT WEEKS
if pd.read_sql_query("SELECT COUNT(*) c FROM weeks", conn)["c"][0] == 0:
    for w in generate_weeks():
        c.execute("INSERT INTO weeks VALUES (%s,%s)", (w, True))

# ---------- SESSION ----------
if "user" not in st.session_state:
    st.session_state.user = None
if "role" not in st.session_state:
    st.session_state.role = None

# ---------- LOGIN ----------
if not st.session_state.user:
    st.title("Login")

    st.write("You must be pre-approved. Contact admin if you don't have access.")

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    col1, col2 = st.columns(2)

    # LOGIN
    if col1.button("Login"):
        user = pd.read_sql_query(
            "SELECT * FROM employees WHERE employee_id=%s",
            conn,
            params=(email,)
        )

        if not user.empty and user.iloc[0]["password_hash"] and check_pw(password, user.iloc[0]["password_hash"]):
            st.session_state.user = {"email": email}
            st.session_state.role = "user"
            st.rerun()
        else:
            st.error("Invalid login")

    # SET PASSWORD (CONTROLLED ACCESS)
    if col2.button("Set Your Password"):
        if not email or not password:
            st.error("Enter email and password")
        else:
            existing = pd.read_sql_query(
                "SELECT * FROM employees WHERE employee_id=%s",
                conn,
                params=(email,)
            )

            if existing.empty:
                st.error("You are not authorized. Contact admin.")
            else:
                hashed = hash_pw(password)

                c.execute(
                    "UPDATE employees SET password_hash=%s WHERE employee_id=%s",
                    (hashed, email)
                )
                conn.commit()

                st.success("Password set. Now click Login.")

    # ADMIN LOGIN
    if st.checkbox("Admin login"):
        pw = st.text_input("Admin Password", type="password")
        if st.button("Admin Login"):
            if pw == ADMIN_PASSWORD:
                st.session_state.user = {"email": "admin"}
                st.session_state.role = "admin"
                st.rerun()

# ---------- LOGOUT ----------
if st.session_state.user:
    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()

# ---------- USER ----------
if st.session_state.user and st.session_state.role == "user":
    st.title("Vacation Scheduler")

    email = st.session_state.user["email"]
    weeks = get_active_weeks()

    existing = pd.read_sql_query(
        "SELECT * FROM submissions WHERE employee_id=%s",
        conn,
        params=(email,)
    )

    defaults = [""] * 10
    if not existing.empty:
        row = existing.iloc[0]
        defaults = [row[f"choice{i}"] or "" for i in range(1, 11)]

    choices = []
    for i in range(1, 11):
        idx = weeks.index(defaults[i-1]) + 1 if defaults[i-1] in weeks else 0
        choices.append(st.selectbox(f"Choice {i}", [""] + weeks, index=idx, key=f"c{i}"))

    if st.button("Save Choices"):
        c.execute("""
            INSERT INTO submissions VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (employee_id) DO UPDATE SET
                choice1=EXCLUDED.choice1,
                choice2=EXCLUDED.choice2,
                choice3=EXCLUDED.choice3,
                choice4=EXCLUDED.choice4,
                choice5=EXCLUDED.choice5,
                choice6=EXCLUDED.choice6,
                choice7=EXCLUDED.choice7,
                choice8=EXCLUDED.choice8,
                choice9=EXCLUDED.choice9,
                choice10=EXCLUDED.choice10
        """, (email, *choices))
        conn.commit()
        st.success("Saved")

# ---------- ADMIN ----------
if st.session_state.user and st.session_state.role == "admin":

    st.title("Admin Panel")

    col1, col2 = st.columns(2)

    if col1.button("Clear Submissions"):
        c.execute("DELETE FROM submissions")
        conn.commit()
        st.rerun()

    if col2.button("Clear Results"):
        c.execute("DELETE FROM results")
        conn.commit()
        st.rerun()

    # EMPLOYEES
    st.subheader("Employees")
    st.dataframe(get_employees())

    st.subheader("Add Employee")
    new_email = st.text_input("Email")
    new_pw = st.text_input("Password", type="password")

    if st.button("Add Employee"):
        hashed = hash_pw(new_pw)
        c.execute("""
            INSERT INTO employees (employee_id, password_hash, hire_date, win_count)
            VALUES (%s,%s,%s,%s)
            ON CONFLICT (employee_id)
            DO NOTHING
        """, (new_email, hashed, datetime.date.today(), 0))
        conn.commit()
        st.success("Employee added")

    st.subheader("Change Password")
    user_email = st.text_input("User Email")
    new_pw2 = st.text_input("New Password", type="password")

    if st.button("Update Password"):
        hashed = hash_pw(new_pw2)
        c.execute("UPDATE employees SET password_hash=%s WHERE employee_id=%s",
                  (hashed, user_email))
        conn.commit()
        st.success("Updated")

    # WEEKS
    st.subheader("Weeks")
    weeks_df = pd.read_sql_query("SELECT * FROM weeks ORDER BY week", conn)
    st.dataframe(weeks_df)

    # SUBMISSIONS
    st.subheader("Submissions")
    subs = pd.read_sql_query("SELECT * FROM submissions", conn)
    st.dataframe(subs)

    if not subs.empty:
        delete_user = st.selectbox("Delete submission", subs["employee_id"])
        if st.button("Delete Selected"):
            c.execute("DELETE FROM submissions WHERE employee_id=%s", (delete_user,))
            conn.commit()
            st.rerun()

    # LOTTERY
    if st.button("Run Lottery"):
        c.execute("DELETE FROM results")

        subs = pd.read_sql_query("SELECT * FROM submissions", conn)
        emps = get_employees().sort_values(by=["win_count","hire_date"])

        taken = set()

        for _, emp in emps.iterrows():
            sub = subs[subs["employee_id"] == emp["employee_id"]]
            if sub.empty:
                continue

            row = sub.iloc[0]

            for i in range(1,11):
                choice = row[f"choice{i}"]
                if choice and choice not in taken:
                    taken.add(choice)
                    c.execute("INSERT INTO results VALUES (%s,%s)",
                              (emp["employee_id"], choice))
                    c.execute("UPDATE employees SET win_count = win_count + 1 WHERE employee_id=%s",
                              (emp["employee_id"],))
                    break

        conn.commit()
        st.success("Lottery complete")

    # RESULTS
    st.subheader("Results")
    res = pd.read_sql_query("SELECT * FROM results", conn)
    st.dataframe(res)

    st.download_button("Download Results", res.to_csv(index=False), "results.csv")
