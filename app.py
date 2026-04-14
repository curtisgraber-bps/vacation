import streamlit as st
import pandas as pd
import psycopg2
import datetime
import bcrypt
import random

ADMIN_PASSWORD = "admin123"

conn = psycopg2.connect(
    "postgresql://postgres.ugnxfszbikjuzaklsnji:BPApwisl33t@aws-1-ca-central-1.pooler.supabase.com:5432/postgres"
)
conn.autocommit = True
c = conn.cursor()

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
    return [f"{start + datetime.timedelta(weeks=i)} to {start + datetime.timedelta(days=7 + i*7)}" for i in range(52)]

def get_active_weeks():
    return pd.read_sql_query("SELECT week FROM weeks WHERE enabled = TRUE", conn)["week"].tolist()

if pd.read_sql_query("SELECT COUNT(*) c FROM weeks", conn)["c"][0] == 0:
    for w in generate_weeks():
        c.execute("INSERT INTO weeks VALUES (%s,%s)", (w, True))

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.role = None
    st.session_state.user_id = None

if not st.session_state.logged_in:
    st.title("Login")

    login_id = st.text_input("Employee ID")

    if login_id:
        emps = get_employees()
        emp = emps[emps["employee_id"] == login_id]

        if not emp.empty:
            emp = emp.iloc[0]

            if not emp["password_hash"] or pd.isna(emp["password_hash"]):
                pw = st.text_input("Create Password", type="password")
                if st.button("Set Password", key="set_pw") and pw:
                    c.execute("UPDATE employees SET password_hash=%s WHERE employee_id=%s",
                              (hash_pw(pw), login_id))
                    conn.commit()
            else:
                pw = st.text_input("Password", type="password")
                if st.button("Login", key="login_btn") and check_pw(pw, emp["password_hash"]):
                    st.session_state.logged_in = True
                    st.session_state.role = "user"
                    st.session_state.user_id = login_id
                    st.rerun()

    st.markdown("<br><br>", unsafe_allow_html=True)

    if st.checkbox("Admin login"):
        pw = st.text_input("Admin Password", type="password")
        if st.button("Admin Login", key="admin_login") and pw == ADMIN_PASSWORD:
            st.session_state.logged_in = True
            st.session_state.role = "admin"
            st.rerun()

if st.session_state.logged_in:
    if st.button("Logout", key="logout"):
        st.session_state.clear()
        st.rerun()

if st.session_state.logged_in and st.session_state.role == "user":
    st.title("Vacation Scheduler")

    weeks = get_active_weeks()
    eid = st.session_state.user_id

    existing = pd.read_sql_query("SELECT * FROM submissions WHERE employee_id=%s", conn, params=(eid,))

    if not existing.empty:
        st.success("Submitted")
        row = existing.iloc[0]
        for i in range(1,11):
            if row[f"choice{i}"]:
                st.write(f"{i}. {row[f'choice{i}']}")
    else:
        choices = [st.selectbox(f"Choice {i}", [""] + weeks, key=f"c{i}") for i in range(1,11)]

        if st.button("Submit", key="submit_choices"):
            c.execute("INSERT INTO submissions VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                      (eid, *choices))
            conn.commit()
            st.rerun()

if st.session_state.logged_in and st.session_state.role == "admin":

    st.title("Admin Panel")

    col1, col2, col3 = st.columns(3)

    if col1.button("Clear Submissions", key="clear_subs"):
        c.execute("DELETE FROM submissions")

    if col2.button("Clear Results", key="clear_results"):
        c.execute("DELETE FROM results")

    if col3.button("Generate Test Submissions", key="gen_test"):
        c.execute("DELETE FROM submissions")
        emps = get_employees()
        weeks = get_active_weeks()
        for _, emp in emps.iterrows():
            choices = random.sample(weeks, min(10, len(weeks)))
            choices += [""] * (10 - len(choices))
            c.execute("INSERT INTO submissions VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                      (emp["employee_id"], *choices))

    conn.commit()

    st.divider()

    st.subheader("Employees")

    emps = get_employees()

    edited = st.data_editor(
        emps[["employee_id","first_name","last_name","hire_date","win_count"]],
        use_container_width=True,
        num_rows="dynamic"
    )

    if st.button("Save Employee Changes", key="save_emp"):
        original = get_employees().set_index("employee_id")
        edited_df = edited.set_index("employee_id")

        for emp_id in edited_df.index:
            if emp_id not in original.index:
                continue
            new = edited_df.loc[emp_id]
            old = original.loc[emp_id]

            if (
                new["first_name"] != old["first_name"] or
                new["last_name"] != old["last_name"] or
                str(new["hire_date"]) != str(old["hire_date"]) or
                int(new["win_count"]) != int(old["win_count"])
            ):
                c.execute(
                    "UPDATE employees SET first_name=%s,last_name=%s,hire_date=%s,win_count=%s WHERE employee_id=%s",
                    (new["first_name"], new["last_name"], new["hire_date"], int(new["win_count"]), emp_id)
                )

        conn.commit()
        st.rerun()

    col1, col2, col3, col4 = st.columns(4)
    new_id = col1.text_input("New ID")
    new_fn = col2.text_input("First")
    new_ln = col3.text_input("Last")
    new_hd = col4.date_input("Hire Date")

    if st.button("Add Employee", key="add_emp"):
        c.execute("INSERT INTO employees VALUES (%s,%s,%s,%s,%s,%s)",
                  (new_id, new_fn, new_ln, new_hd, 0, None))
        conn.commit()
        st.rerun()

    col1, col2 = st.columns(2)
    reset_id = col1.text_input("Reset ID")
    if col2.button("Reset Password", key="reset_pw"):
        c.execute("UPDATE employees SET password_hash=NULL WHERE employee_id=%s", (reset_id,))
        conn.commit()

    st.divider()

st.subheader("Weeks")

col1, col2 = st.columns(2)

if col1.button("Select All Weeks", key="select_all"):
    c.execute("UPDATE weeks SET enabled=TRUE")
    conn.commit()
    st.rerun()

if col2.button("Deselect All Weeks", key="deselect_all"):
    c.execute("UPDATE weeks SET enabled=FALSE")
    conn.commit()
    st.rerun()

weeks_df = pd.read_sql_query("SELECT * FROM weeks", conn)

new_states = {}

for _, row in weeks_df.iterrows():
    new_states[row["week"]] = st.checkbox(
        row["week"],
        value=row["enabled"],
        key=f"week_{row['week']}"
    )

# APPLY CHANGES ONCE
if st.button("Save Week Changes", key="save_weeks"):
    for week, val in new_states.items():
        c.execute("UPDATE weeks SET enabled=%s WHERE week=%s", (val, week))
    conn.commit()
    st.rerun()

    st.divider()

    if st.button("Run Lottery", key="run_lottery"):
        c.execute("DELETE FROM results")

        emps = get_employees()
        subs = pd.read_sql_query("SELECT * FROM submissions", conn)

        emps = emps[emps["employee_id"].isin(subs["employee_id"])]
        emps = emps.sort_values(by=["win_count","hire_date"])

        taken = set()

        for _, emp in emps.iterrows():
            sub = subs[subs["employee_id"] == emp["employee_id"]].iloc[0]

            for i in range(1,11):
                ch = sub[f"choice{i}"]
                if ch and ch not in taken:
                    taken.add(ch)
                    c.execute("INSERT INTO results VALUES (%s,%s)", (emp["employee_id"], ch))
                    c.execute("UPDATE employees SET win_count = win_count + 1 WHERE employee_id=%s", (emp["employee_id"],))
                    break

        conn.commit()

    st.divider()

    res = pd.read_sql_query("SELECT * FROM results", conn)
    res = res.merge(get_employees(), on="employee_id")

    st.dataframe(res[["first_name","last_name","assigned_week","win_count"]])
