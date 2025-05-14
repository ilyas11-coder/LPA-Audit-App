# import os
import yagmail
from fpdf import FPDF
import streamlit as st
import pandas as pd
from datetime import datetime

# Email settings
SENDER_EMAIL = "ilyaswork.11@gmail.com"
SENDER_PASSWORD = "estk iyov khoo tjio"  # Use Gmail app password
RECEIVER_EMAIL = "ilyaswork.11@gmail.com"  # Email to receive reports

# Load planning and checklist from Excel
planning = pd.read_excel("planning.xlsx")
checklist_data = pd.read_excel("checklist.xlsx")

# User login info
users = {
    "auditor1": {"password": "123", "role": "auditor"},
    "auditor2": {"password": "123", "role": "auditor"},
    "admin": {"password": "admin", "role": "admin"}
}

# Login state
if "user" not in st.session_state:
    st.session_state.user = None

# ---------- FUNCTIONS ---------- #


def login():
    st.title("🔐 LPA Audit Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if username in users and users[username]["password"] == password:
            st.session_state.user = username
            st.session_state.role = users[username]["role"]
            st.success("Login successful")
        else:
            st.error("Invalid login")


def action_plan_ui(q):
    st.warning(f"⚠ Action Plan for: {q}")
    issue = st.text_input(f"Issue detected - {q}", key=f"{q}_issue")
    action = st.text_input(f"Action to take - {q}", key=f"{q}_action")
    responsible = st.text_input(f"Responsible - {q}", key=f"{q}_resp")
    deadline = st.date_input(f"Deadline - {q}", key=f"{q}_date")
    return {
        "issue": issue,
        "action": action,
        "responsible": responsible,
        "deadline": str(deadline)
    }


def show_checklist(zone, name):
    st.subheader(f"📋 Checklist for {zone}")
    questions = checklist_data[checklist_data["zone"] == zone]["question"].tolist()
    actions = []

    for q in questions:
        answer = st.radio(q, ["C", "NC", "NCC", "NA"], key=q)
        if answer == "NC":
            action_data = action_plan_ui(q)
            action_data.update({
                "auditor": name,
                "zone": zone,
                "date": datetime.today().strftime("%Y-%m-%d"),
                "question": q
            })
            actions.append(action_data)

    if st.button("✅ Submit Audit"):
        planning.loc[(planning["name"] == name) & (planning["zone"] == zone), "checklist_done"] = "Yes"
        planning.to_excel("planning.xlsx", index=False)
        st.success("Audit saved.")

        if actions:
            try:
                old_actions = pd.read_excel("action_plans.xlsx")
                combined = pd.concat([old_actions, pd.DataFrame(actions)], ignore_index=True)
            except FileNotFoundError:
                combined = pd.DataFrame(actions)

            combined.to_excel("action_plans.xlsx", index=False)
            st.success("Action Plans saved to action_plans.xlsx")

        generate_and_send_pdf(name)
        st.success("📤 PDF sent by email.")


def show_dashboard():
    st.title("📊 Dashboard")
    total = len(planning)
    done = len(planning[planning["checklist_done"] == "Yes"])
    percent = int((done / total) * 100) if total else 0
    st.metric("Audits Done", f"{percent}%")
    st.metric("Open Actions", str(total - done))
    st.metric("Closed Actions", str(done))


def admin_panel():
    st.title("🛠 Admin Panel")
    st.subheader("Current Planning:")
    st.dataframe(planning)

    st.subheader("Checklist Questions:")
    st.dataframe(checklist_data)

    st.info("To update planning or checklist, just replace the Excel files and reload the app.")


def send_late_emails():
    try:
        df = pd.read_excel("action_plans.xlsx")
        today = pd.to_datetime(datetime.today().date())
        df["deadline"] = pd.to_datetime(df["deadline"])

        late = df[df["deadline"] < today]
        if late.empty:
            st.success("No late actions.")
            return

        yag = yagmail.SMTP(SENDER_EMAIL, SENDER_PASSWORD)
        for _, row in late.iterrows():
            message = (
                f"⚠ LATE ACTION ALERT\n\n"
                f"Responsible: {row['responsible']}\n"
                f"Zone: {row['zone']}\n"
                f"Question: {row['question']}\n"
                f"Issue: {row['issue']}\n"
                f"Action: {row['action']}\n"
                f"Deadline: {row['deadline'].strftime('%Y-%m-%d')}\n"
            )
            try:
                yag.send(to="ilyashtouch.sayli@gmail.com", subject="LPA Late Action", contents=message)
            except Exception as e:
                st.error(f"Email failed: {e}")

        st.success("Late action emails sent.")
    except FileNotFoundError:
        st.error("action_plans.xlsx not found.")


def generate_and_send_pdf(name):
    try:
        df = pd.read_excel("action_plans.xlsx")
        user_data = df[df["auditor"] == name]
        if user_data.empty:
            return

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt=f"Audit Report - {name}", ln=True, align='C')
        pdf.ln(10)

        for _, row in user_data.iterrows():
            pdf.multi_cell(0, 10, txt=(
                f"Zone: {row['zone']}\n"
                f"Date: {row['date']}\n"
                f"Question: {row['question']}\n"
                f"Issue: {row['issue']}\n"
                f"Action: {row['action']}\n"
                f"Responsible: {row['responsible']}\n"
                f"Deadline: {row['deadline']}\n"
                "------------------------"
            ))

        filename = f"report_{name}.pdf"
        pdf.output(filename)

        yag = yagmail.SMTP(SENDER_EMAIL, SENDER_PASSWORD)
        yag.send(
            to=RECEIVER_EMAIL,
            subject=f"LPA Audit Report from {name}",
            contents=f"Please find attached the audit report from {name}.",
            attachments=filename
        )
    except Exception as e:
        st.error(f"❌ Failed to generate/send PDF: {e}")

# ---------- APP FLOW ---------- #


if st.session_state.user is None:
    login()
else:
    st.sidebar.title(f"Welcome, {st.session_state.user}")
    if st.sidebar.button("Logout"):
        st.session_state.user = None
        st.rerun()

    role = st.session_state.role
    name = st.session_state.user

    if role == "auditor":
        st.title("🗓 Your Audit Tasks")
        my_rows = planning[(planning["name"] == name) & (planning["checklist_done"] == "No")]
        if my_rows.empty:
            st.info("✅ You have no pending audits.")
        else:
            for _, row in my_rows.iterrows():
                st.subheader(f"{row['date']} - {row['zone']}")
                show_checklist(row["zone"], name)

    elif role == "admin":
        show_dashboard()
        st.markdown("---")
        admin_panel()

    st.subheader("📧 Send Emails for Late Actions")
    if st.button("Send Late Emails"):
        send_late_emails()
