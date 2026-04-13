import streamlit as st
import pandas as pd
import sqlite3

# Connect DB
conn = sqlite3.connect("data.db", check_same_thread=False)
c = conn.cursor()

# Create table
c.execute("""
CREATE TABLE IF NOT EXISTS submissions (
    employee_id TEXT,
    choice1 TEXT,
    choice2 TEXT,
    choice3 TEXT
)
""")

st.title("Vacation Scheduler")

df = pd.read_csv("employees.csv")

st.header("Select Your Vacation Weeks")

# Show names, keep index for ID mapping
df["full_name"] = df["first_name"] + " " + df["last_name"]

selected = st.selectbox("Select Your Name", df["full_name"])

# Get employee_id from selection
employee_id = df[df["full_name"] == selected]["employee_id"].values[0]

choice1 = st.text_input("First Choice")
choice2 = st.text_input("Second Choice")
choice3 = st.text_input("Third Choice")

if st.button("Submit"):
    c.execute(
        "INSERT INTO submissions (employee_id, choice1, choice2, choice3) VALUES (?, ?, ?, ?)",
        (employee_id, choice1, choice2, choice3)
    )
    conn.commit()
    st.success("Submitted")

# Admin view
st.header("Admin View")
rows = c.execute("SELECT * FROM submissions").fetchall()
st.write(rows)
