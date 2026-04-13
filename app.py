import streamlit as st
import sqlite3

conn = sqlite3.connect("data.db", check_same_thread=False)
c = conn.cursor()

# Create table
c.execute("""
CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT,
    choice1 TEXT,
    choice2 TEXT,
    choice3 TEXT
)
""")

st.title("Vacation Week Selection")

employee_id = st.text_input("Employee ID")
choice1 = st.text_input("First Choice")
choice2 = st.text_input("Second Choice")
choice3 = st.text_input("Third Choice")

if st.button("Submit"):
    c.execute("INSERT INTO submissions (employee_id, choice1, choice2, choice3) VALUES (?, ?, ?, ?)",
              (employee_id, choice1, choice2, choice3))
    conn.commit()
    st.success("Submitted")

st.subheader("Admin View")
rows = c.execute("SELECT * FROM submissions").fetchall()
st.write(rows)
