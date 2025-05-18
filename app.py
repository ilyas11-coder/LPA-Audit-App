import yagmail
from fpdf import FPDF
import streamlit as st
import pandas as pd
from datetime import datetime
import hashlib
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ---------- CONFIG ---------- #
ADMIN_EMAIL = "i.htouch@miamaroc.com"
ADMIN_PASSWORD = "admin123"

SENDER_EMAIL = "ilyaswork.11@gmail.com"
SENDER_PASSWORD = "estk iyov khoo tjio"
RECEIVER_EMAIL = "ilyaswork.11@gmail.com"

# ---------- Google Sheets Setup ---------- #
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

try:
    service_account_info = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, scope)
    client = gspread.authorize(creds)
except Exception as e:
    st.error(f"❌ Failed to authorize Google Sheets: {e}")
    st.stop()

# Connect to Google Sheets
users_sheet = client.open("LPA_Users").sheet1
action_plan_sheet = client.open("LPA_ActionPlans").sheet1
audit_results_sheet = client.open("LPA_Audit_Results").sheet1

def load_planning():
    sheet = client.open("LPA_Planning").sheet1
    data = sheet.get_all_records()
    return pd.DataFrame(data)

def save_planning(df):
    sheet = client.open("LPA_Planning").sheet1
    sheet.clear()
    sheet.update([df.columns.values.tolist()] + df.values.tolist())

def load_checklist():
    try:
        sheet = client.open("LPA_Checklist").sheet1
        raw = sheet.get_all_values()
        st.write("✅ Checklist raw data:", raw)
        return pd.DataFrame(raw[1:], columns=raw[0])
    except Exception as e:
        st.error(f"❌ Failed to load checklist: {e}")
        return pd.DataFrame()

# ---------- FUNCTIONS ---------- #
def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def register():
    st.title("📝 Register")
    name = st.text_input("Full Name")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    department = st.selectbox("Department", [
        "Management", "Quality", "Human Ressources", "Engineering", "Production", "Logistics", "Maintenance"
    ])

    if st.button("Register"):
        if name and email and password and department:
            all_emails = [row[1] for row in users_sheet.get_all_values()[1:]]
            if email in all_emails:
                st.error("Email already registered.")
            else:
                users_sheet.append_row([name, email, hash_password(password), department])
                st.success("✅ Registered successfully. You can now log in.")
        else:
            st.warning("⚠ Please fill in all fields.")

def login():
    st.title("🔐 Login")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
            st.session_state.user = "Admin"
            st.session_state.role = "admin"
        else:
            user_records = users_sheet.get_all_records()
            df = pd.DataFrame(user_records)
            row = df[df['email'] == email]
            if not row.empty and row.iloc[0]['password'] == hash_password(password):
                st.session_state.user = row.iloc[0]['name']
                st.session_state.role = "auditor"
                st.session_state.department = row.iloc[0]['department']
            else:
                st.error("Invalid email or password")

    if st.button("Register Instead"):
        st.session_state.page = "register"

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

def show_auditor_view(name):
    global planning
    planning = load_planning()

    st.title("🗓 Your Assigned Audits")
    normalized_name = name.strip().lower()
    planning["name_clean"] = planning["name"].str.strip().str.lower()
    my_rows = planning[(planning["name_clean"] == normalized_name) & (planning["checklist_done"].str.lower() != "yes")]

    if my_rows.empty:
        st.info("✅ You have no pending audits.")
        return

    zones_to_do = my_rows["zone"].tolist()
    if not zones_to_do:
        st.info("✅ All checklists completed.")
        return

    tabs = st.tabs(zones_to_do)
    for i, zone in enumerate(zones_to_do):
        with tabs[i]:
            show_checklist_with_sections(zone, name)

def show_checklist_with_sections(zone, name):
    st.subheader(f"📋 Checklist for {zone}")
    zone_checklist = checklist_data[checklist_data["zone"] == zone]
    sections = zone_checklist["section"].unique()
    actions = []

    for section in sections:
        st.markdown(f"### {section}")
        section_questions = zone_checklist[zone_checklist["section"] == section]
        for _, row in section_questions.iterrows():
            q = row["question"]
            answer = st.radio(q, ["C", "NC", "NCC", "NA"], key=f"{zone}_{section}_{q}")
            if answer == "NC":
                action_data = action_plan_ui(q)
                action_data.update({
                    "auditor": name,
                    "zone": zone,
                    "date": datetime.today().strftime("%Y-%m-%d"),
                    "question": q
                })
                actions.append(action_data)

    if st.button(f"✅ Submit Audit for {zone}"):
        planning.loc[(planning["name"] == name) & (planning["zone"] == zone), "checklist_done"] = "Yes"
        save_planning(planning)
        st.success(f"Audit for {zone} saved.")
        save_audit_result(name, zone)

        if actions:
            headers = ["auditor", "zone", "date", "question", "issue", "action", "responsible", "deadline"]
            existing = action_plan_sheet.get_all_values()
            if not existing or existing[0] != headers:
                action_plan_sheet.insert_row(headers, 1)
            for action in actions:
                row_data = [action.get(col, "") for col in headers]
                action_plan_sheet.append_row(row_data)
            st.success(f"✅ Action Plans for {zone} saved.")

        generate_and_send_pdf(name)
        st.success("📤 PDF sent by email.")

def save_audit_result(auditor, zone):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    headers = ["auditor", "zone", "timestamp"]
    existing = audit_results_sheet.get_all_values()
    if not existing or existing[0] != headers:
        audit_results_sheet.insert_row(headers, 1)
    audit_results_sheet.append_row([auditor, zone, now])

def generate_and_send_pdf(name):
    try:
        records = action_plan_sheet.get_all_records()
        df = pd.DataFrame(records)
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
        yag.send(to=RECEIVER_EMAIL, subject=f"LPA Audit Report from {name}",
                 contents=f"Please find attached the audit report from {name}.", attachments=filename)
    except Exception as e:
        st.error(f"❌ Failed to generate/send PDF: {e}")

def send_late_emails():
    try:
        records = action_plan_sheet.get_all_records()
        df = pd.DataFrame(records)
        df["deadline"] = pd.to_datetime(df["deadline"], errors='coerce')
        today = pd.to_datetime(datetime.today().date())
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
    except Exception as e:
        st.error(f"❌ Failed to load or send late actions: {e}")

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

    st.subheader("Registered Users:")
    user_data = users_sheet.get_all_records()
    st.dataframe(pd.DataFrame(user_data))

    st.subheader("Current Planning:")
    st.dataframe(planning)

    st.subheader("Checklist Questions:")
    st.dataframe(checklist_data)

    st.subheader("📄 Submitted Audits")
    data = audit_results_sheet.get_all_records()
    if data:
        df = pd.DataFrame(data)
        st.dataframe(df)
    else:
        st.info("No audit submissions yet.")

# ---------- MAIN APP ---------- #
if "user" not in st.session_state:
    st.session_state.user = None
if "page" not in st.session_state:
    st.session_state.page = "login"

if st.session_state.user is None:
    if st.session_state.page == "register":
        register()
    else:
        login()
else:
    st.sidebar.title(f"Welcome, {st.session_state.user}")
    if st.sidebar.button("Logout"):
        st.session_state.user = None
        st.session_state.page = "login"
        st.rerun()

    role = st.session_state.role
    name = st.session_state.user

    if role == "auditor":
        show_auditor_view(name)
    elif role == "admin":
        show_dashboard()
        st.markdown("---")
        admin_panel()

    st.subheader("📧 Send Emails for Late Actions")
    if st.button("Send Late Emails"):
        send_late_emails()
