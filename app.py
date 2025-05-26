import streamlit as st
import gspread

# --- PAGE CONFIG ---
st.set_page_config(page_title="LPA Audit App", layout="wide")

st.title("🔍 LPA Audit App")

# --- Connect to Google Sheets ---
@st.cache_resource
def get_gspread_client():
    return gspread.service_account_from_dict(st.secrets["gcp_service_account"])

client = get_gspread_client()

# --- LOGIN FORM ---
if "user_email" not in st.session_state:
    with st.form("login_form"):
        st.subheader("🔐 Login")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

        if submitted:
            try:
                users_sheet = client.open("LPA_Users").worksheet("Sheet1")  # Replace "Sheet1" if needed
                users = users_sheet.get_all_records()

                matched_user = next((u for u in users if u["email"] == email and u["password"] == password), None)

                if matched_user:
                    st.session_state["user_email"] = email
                    st.session_state["user_name"] = matched_user["name"]
                    st.success(f"Welcome {matched_user['name']}!")
                    st.experimental_rerun()
                else:
                    st.error("Invalid email or password.")
            except Exception as e:
                st.error(f"Failed to access user sheet: {e}")
else:
    st.success(f"✅ Logged in as: {st.session_state['user_email']}")

    # --- Load All Sheets Securely ---
    try:
        users_sheet = client.open("LPA_Users").worksheet("Sheet1")
    except Exception as e:
        st.error(f"❌ Error loading LPA_Users: {e}")
        st.stop()

    try:
        planning_sheet = client.open("LPA_Planning").worksheet("Sheet1")
    except Exception as e:
        st.error(f"❌ Error loading LPA_Planning: {e}")
        st.stop()

    try:
        checklist_sheet = client.open("LPA_Checklist").worksheet("Sheet1")
    except Exception as e:
        st.error(f"❌ Error loading LPA_Checklist: {e}")
        st.stop()

    try:
        audit_results_sheet = client.open("LPA_Audit_Results").worksheet("Sheet1")
    except Exception as e:
        st.error(f"❌ Error loading LPA_Audit_Results: {e}")
        st.stop()

    try:
        action_plans_sheet = client.open("LPA_ActionPlans").worksheet("Sheet1")
    except Exception as e:
        st.error(f"❌ Error loading LPA_ActionPlans: {e}")
        st.stop()

    # --- Main Dashboard / Checklist Logic Placeholder ---
    st.subheader("📋 Checklist / Audit Area")

    # Example zones or audit content here
    st.info("✅ All sheets loaded. Now continue your app logic here.")

    # Example logout button
    if st.button("Logout"):
        st.session_state.clear()
        st.experimental_rerun()
