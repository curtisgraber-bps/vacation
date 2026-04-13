import streamlit as st
import pandas as pd

st.title("Vacation Scheduler")

df = pd.read_csv("employees.csv")

st.header("Select Your Vacation Weeks")

# Dropdown of employees
employee = st.selectbox(
    "Select Your Name",
    df["Employee First Name"] + " " + df["Employee Last Name"]
)

choice1 = st.text_input("First Choice")
choice2 = st.text_input("Second Choice")
choice3 = st.text_input("Third Choice")

if st.button("Submit"):
    st.success(f"Submitted for {employee}")

st.header("Employee List")
st.write(df)
