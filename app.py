import streamlit as st
import pandas as pd

st.title("Vacation Scheduler")

st.header("Employee List")

df = pd.read_csv("employees.csv")
st.write(df)
