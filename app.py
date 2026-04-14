# --- ADMIN ---
if st.session_state.logged_in and st.session_state.role == "admin":

    st.title("Admin Panel")

    # TOP ACTIONS
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Clear Submissions"):
            c.execute("DELETE FROM submissions")
            conn.commit()

    with col2:
        if st.button("Clear Results"):
            c.execute("DELETE FROM results")
            conn.commit()

    with col3:
        if st.button("Generate Test Submissions"):
            c.execute("DELETE FROM submissions")
            emps = get_employees()

            for _, emp in emps.iterrows():
                choices = random.sample(active_weeks, min(10, len(active_weeks)))
                choices += [""] * (10 - len(choices))

                c.execute(
                    "INSERT INTO submissions VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (emp["employee_id"], *choices)
                )

            conn.commit()

    st.markdown("---")

    # EMPLOYEE TABLE (THIS IS WHAT YOU WERE MISSING)
    st.subheader("Employees")

    emps = get_employees()
    st.dataframe(
        emps[["employee_id","first_name","last_name","hire_date","win_count"]],
        use_container_width=True
    )

    st.markdown("---")

    # ADD EMPLOYEE (INLINE, NOT UGLY FORM BLOCK)
    col1, col2, col3, col4, col5 = st.columns(5)

    eid = col1.text_input("ID")
    fn = col2.text_input("First")
    ln = col3.text_input("Last")
    hd = col4.date_input("Hire", key="hire_add")

    if col5.button("Add"):
        c.execute(
            "INSERT INTO employees VALUES (%s,%s,%s,%s,%s,%s)",
            (eid, fn, ln, hd, 0, None)
        )
        conn.commit()
        st.rerun()

    # RESET PASSWORD INLINE
    col1, col2 = st.columns(2)
    reset_id = col1.text_input("Reset ID")
    if col2.button("Reset PW"):
        c.execute("UPDATE employees SET password_hash=NULL WHERE employee_id=%s", (reset_id,))
        conn.commit()

    st.markdown("---")

    # WHO SUBMITTED
    st.subheader("Who Submitted")

    subs = pd.read_sql_query("SELECT employee_id FROM submissions", conn)
    view = subs.merge(emps, on="employee_id", how="left")

    st.dataframe(
        view[["first_name","last_name"]],
        use_container_width=True
    )

    st.markdown("---")

    # DETAILS
    st.subheader("Submission Details")

    subs_full = pd.read_sql_query("SELECT * FROM submissions", conn)
    full = subs_full.merge(emps, on="employee_id", how="left")

    def combine(r):
        return ", ".join([str(r[f"choice{i}"]) for i in range(1,11) if r[f"choice{i}"]])

    full["choices"] = full.apply(combine, axis=1)

    st.dataframe(
        full[["first_name","last_name","choices"]],
        use_container_width=True
    )

    st.markdown("---")

    # LOTTERY
    if st.button("Run Lottery"):
        c.execute("DELETE FROM results")

        emps = get_employees()
        subs = pd.read_sql_query("SELECT * FROM submissions", conn)

        emps = emps[emps["employee_id"].isin(subs["employee_id"])]
        emps = emps.sort_values(by=["win_count","hire_date"])

        taken = set()
        winners = []

        for _, emp in emps.iterrows():
            sub = subs[subs["employee_id"] == emp["employee_id"]].iloc[0]

            for i in range(1,11):
                ch = sub[f"choice{i}"]
                if ch and ch not in taken:
                    taken.add(ch)
                    winners.append(emp["employee_id"])
                    c.execute("INSERT INTO results VALUES (%s,%s)", (emp["employee_id"], ch))
                    break

        if winners:
            c.executemany(
                "UPDATE employees SET win_count = win_count + 1 WHERE employee_id=%s",
                [(w,) for w in winners]
            )

        conn.commit()

    st.markdown("---")

    # RESULTS
    res = pd.read_sql_query("SELECT * FROM results", conn)
    emps = get_employees()

    res = res.merge(emps, on="employee_id", how="left")

    st.dataframe(
        res[["first_name","last_name","assigned_week","win_count"]],
        use_container_width=True
    )

    st.download_button(
        "Download Results",
        res.to_csv(index=False).encode("utf-8"),
        "results.csv",
        "text/csv"
    )
