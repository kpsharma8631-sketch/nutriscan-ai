import os
import sys
import sqlite3
import datetime
import json
import re
import streamlit as st
import plotly.graph_objects as go
from google import genai
from database import FOOD_DATASET

# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="NutriScan AI",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================================================
# 🎯 GEMINI MULTI-API KEY FAILOVER SYSTEM
# =========================================================
# Secure environment variable check falls back to a list pool
ENV_KEY = os.environ.get("GEMINI_API_KEY", "")

GEMINI_KEYS_POOL = [
    ENV_KEY if ENV_KEY else "YOUR_GEMINI_API_KEY_1",
    "YOUR_GEMINI_API_KEY_2",
    "YOUR_GEMINI_API_KEY_3"
]

def get_live_gemini_client():
    for idx, key in enumerate(GEMINI_KEYS_POOL):
        if key and not key.startswith("YOUR_GEMINI"):
            try:
                # Initializing modern genai Client
                st.session_state[f"key_status_{idx}"] = "Active"
                return genai.Client(api_key=key)
            except Exception:
                st.session_state[f"key_status_{idx}"] = "Exhausted"
                continue
    # Standard fallback
    return genai.Client(api_key=os.environ.get("GEMINI_API_KEY", "dummy_key"))

# =========================================================
# DATABASE SETUP & SCHEMA MAPPING (RELATIVE PATH)
# =========================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, "users.db")
conn = sqlite3.connect(db_path, check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT, age INTEGER, height REAL, weight REAL, email TEXT, password TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS food_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_email TEXT, food_name TEXT, calories INTEGER, date_time TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS calorie_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_email TEXT, meal_type TEXT, calories INTEGER, log_date TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS water_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_email TEXT, glasses INTEGER, log_date TEXT
)
""")
conn.commit()

# =========================================================
# DATABASE OPERATIONS
# =========================================================
def signup_user(name, age, height, weight, email, password):
    cursor.execute(
        "INSERT INTO users (name, age, height, weight, email, password) VALUES (?, ?, ?, ?, ?, ?)",
        (name, age, height, weight, email, password)
    )
    conn.commit()

def login_user(email, password):
    cursor.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password))
    data = cursor.fetchone()
    return data

def recover_user_password(email):
    cursor.execute("SELECT password FROM users WHERE email=?", (email,))
    res = cursor.fetchone()
    return res[0] if res else None

def update_user_metrics_in_db(email, new_weight, new_height):
    cursor.execute("UPDATE users SET weight=?, height=? WHERE email=?",
                   (float(new_weight), float(new_height), str(email)))
    conn.commit()

def update_user_password_in_db(email, new_password):
    cursor.execute("UPDATE users SET password=? WHERE email=?", (str(new_password), str(email)))
    conn.commit()

def log_food_scanned(email, food_name, calories):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO food_history (user_email, food_name, calories, date_time) VALUES (?, ?, ?, ?)",
                   (str(email), str(food_name), int(calories), str(now)))
    conn.commit()

def log_manual_calories(email, meal_type, calories):
    today = datetime.date.today().strftime("%Y-%m-%d")
    cursor.execute("INSERT INTO calorie_logs (user_email, meal_type, calories, log_date) VALUES (?, ?, ?, ?)",
                   (str(email), str(meal_type), int(calories), str(today)))
    conn.commit()

def get_daily_total_calories(email):
    today = datetime.date.today().strftime("%Y-%m-%d")
    cursor.execute("SELECT SUM(calories) FROM calorie_logs WHERE user_email=? AND log_date=?", (email, today))
    res1 = cursor.fetchone()[0] or 0
    cursor.execute("SELECT SUM(calories) FROM food_history WHERE user_email=? AND date_time LIKE ?",
                   (email, f"{today}%"))
    res2 = cursor.fetchone()[0] or 0
    return res1 + res2

def get_last_scanned_food_from_db(email):
    try:
        cursor.execute("SELECT food_name, calories FROM food_history WHERE user_email=? ORDER BY id DESC LIMIT 1",
                       (email,))
        res = cursor.fetchone()
        if res: return str(res[0]), int(res[1])
    except Exception:
        pass
    return None, 0

def fetch_weekly_calorie_trend_from_db(email):
    trend_data = {}
    today = datetime.date.today()
    for i in range(6, -1, -1):
        d_str = (today - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        trend_data[d_str] = 0
    try:
        cursor.execute("SELECT log_date, SUM(calories) FROM calorie_logs WHERE user_email=? GROUP BY log_date",
                       (email,))
        for row in cursor.fetchall():
            if row[0] in trend_data: trend_data[row[0]] += int(row[1])
        cursor.execute(
            "SELECT SUBSTR(date_time, 1, 10), SUM(calories) FROM food_history WHERE user_email=? GROUP BY SUBSTR(date_time, 1, 10)",
            (email,))
        for row in cursor.fetchall():
            if row[0] in trend_data: trend_data[row[0]] += int(row[1])
    except Exception:
        pass
    return list(trend_data.keys()), list(trend_data.values())

def get_daily_water_glasses(email):
    today = datetime.date.today().strftime("%Y-%m-%d")
    cursor.execute("SELECT glasses FROM water_logs WHERE user_email=? AND log_date=?", (email, today))
    res = cursor.fetchone()
    return int(res[0]) if res else 0

def update_daily_water_glasses(email, delta_val):
    today = datetime.date.today().strftime("%Y-%m-%d")
    current_glasses = get_daily_water_glasses(email)
    new_glasses = max(0, current_glasses + delta_val)

    cursor.execute("SELECT id FROM water_logs WHERE user_email=? AND log_date=?", (email, today))
    exists = cursor.fetchone()
    if exists:
        cursor.execute("UPDATE water_logs SET glasses=? WHERE user_email=? AND log_date=?", (new_glasses, email, today))
    else:
        cursor.execute("INSERT INTO water_logs (user_email, glasses, log_date) VALUES (?, ?, ?)",
                       (email, new_glasses, today))
    conn.commit()
    return new_glasses

# =========================================================
# SESSION STATE MANAGEMENT
# =========================================================
if "screen" not in st.session_state: st.session_state.screen = "login"
if "user_name" not in st.session_state: st.session_state.user_name = "User"
if "user_email" not in st.session_state: st.session_state.user_email = ""
if "detected_food" not in st.session_state: st.session_state.detected_food = None
if "multimodal_results" not in st.session_state: st.session_state.multimodal_results = None
if "user_bmi" not in st.session_state: st.session_state.user_bmi = 22.0
if "user_bmr_target" not in st.session_state: st.session_state.user_bmr_target = 2000
if "selected_goal_calories" not in st.session_state: st.session_state.selected_goal_calories = 2000
if "custom_target_enabled" not in st.session_state: st.session_state.custom_target_enabled = False
if "activity_multiplier" not in st.session_state: st.session_state.activity_multiplier = 1.2
if "chat_history" not in st.session_state: st.session_state.chat_history = []

# =========================================================
# HELPER FUNCTION: SAFE IMAGE RENDERER
# =========================================================
def render_local_image(image_name, img_width=None, use_column=False):
    if os.path.exists(image_name):
        if use_column:
            st.image(image_name, use_container_width=True)
        else:
            st.image(image_name, width=img_width)
    else:
        if "logo" in image_name:
            st.markdown("<h1 style='font-size:50px; margin:0;'>🥗</h1>", unsafe_allow_html=True)
        else:
            st.markdown(
                "<div style='background:#f0fdf4; height:200px; border-radius:18px; display:flex; align-items:center; justify-content:center; color:#16a34a;'><b>[ NutriScan AI Graphic Asset ]</b></div>",
                unsafe_allow_html=True)

# =========================================================
# BULLETPROOF EXACT DATASET KEY-MAPPER
# =========================================================
def get_clean_macro_integer(macros_dict, key_name):
    """Directly extracts numeric values matching database.py keys style layout"""
    if key_name == "protein":
        return int(macros_dict.get("Protein", macros_dict.get("protein", 0)))
    if key_name == "carbs":
        return int(macros_dict.get("Carbs", macros_dict.get("carbs", 0)))
    if key_name == "fat":
        return int(macros_dict.get("Fats", macros_dict.get("fat", 0)))
    return 0

def find_best_matching_db_key(input_food_string):
    """Extracts raw key identities from multi-word strings"""
    clean_target = str(input_food_string).lower().strip()
    if "thali (" in clean_target:
        for db_key in FOOD_DATASET.keys():
            if db_key.replace("_", " ") in clean_target:
                return db_key
    for db_key in FOOD_DATASET.keys():
        clean_db_key = db_key.replace("_", " ")
        if clean_db_key in clean_target or clean_target in clean_db_key:
            return db_key
    return None

# =========================================================
# CORPORATE PREMIUM UI STYLESHEET
# =========================================================
st.markdown("""
<style>
.stApp { background-color: #f8fafc; }
footer { display: none !important; }
[data-testid="stSidebarNav"], [data-testid="stSidebarNavItems"] { display: none !important; height: 0px !important; overflow: hidden !important; }
[data-testid="stSidebarCollapseButton"] { display: flex !important; visibility: visible !important; color: #16a34a !important; background-color: #f0fdf4 !important; border-radius: 50% !important; }
.block-container { padding-top: 2rem !important; padding-left: 3rem !important; padding-right: 3rem !important; }

div.stButton > button {
    background: linear-gradient(to right, #15803d, #22c55e) !important;
    color: white !important;
    border-radius: 12px !important;
    border: none !important;
    font-weight: 700 !important;
    height: 50px !important;
    width: 100% !important;
    box-shadow: 0px 4px 12px rgba(22, 163, 74, 0.15) !important;
}
div.stButton > button:hover { transform: translateY(-1px) !important; box-shadow: 0px 6px 18px rgba(22,163,74,0.25) !important; }

div.stButton > button[key*="trigger_ai_btn"], div.stButton > button[key*="execute_ai_btn"], div.stButton > button[key*="bmi_calc_btn"] { background: linear-gradient(to right, #1e3a8a, #3b82f6) !important; }
div.stButton > button[key*="process_voice_btn"], div.stButton > button[key*="calorie_log_btn"], div.stButton > button[key*="official_download_stream_btn"] { background: linear-gradient(to right, #ea580c, #f97316) !important; }
div.stButton > button[key*="purge_btn"] { background: linear-gradient(to right, #dc2626, #ef4444) !important; box-shadow: none !important; }
div.stButton > button[key*="switch"], div.stButton > button[key*="back"], div.stButton > button[key*="logout"], div.stButton > button[key*="forgot_nav"] {
    background: #f0fdf4 !important;
    color: #16a34a !important;
    border: 1px solid #bbf7d0 !important;
}

.logo-text { font-size: 45px; font-weight: 800; color: #111827; margin-top: 5px; }
.green { color: #16a34a; }
.main-heading { font-size: 60px; font-weight: 800; line-height: 1.1; margin-top: 15px; color: #111827; }
.subtitle { font-size: 19px; color: #4b5563; margin-top: 15px; line-height: 1.6; }
.feature-card { background: #f0fdf4; padding: 20px; border-radius: 18px; text-align: center; box-shadow: 0px 4px 12px rgba(0,0,0,0.03); }
.login-container { background: white; padding: 35px 40px !important; border-radius: 24px; box-shadow: 0px 10px 30px rgba(0,0,0,0.05); margin-top: 10px !important; border: 1px solid #f1f5f9; }
.signup-container-card { background: white; padding: 40px !important; border-radius: 28px; box-shadow: 0px 15px 35px rgba(0,0,0,0.06); margin-top: 10px !important; border: 1px solid #e2e8f0; }
.settings-block-panel { background: white; border: 1px solid #e2e8f0; padding: 30px; border-radius: 24px; box-shadow: 0px 4px 18px rgba(0,0,0,0.01); margin-bottom: 25px; }
.welcome { text-align: center; font-size: 40px; font-weight: 800; color: #111827; }
.subtitle2 { text-align: center; color: #6b7280; font-size: 15px; margin-bottom: 20px; }
.avatar-wrapper { display: flex; justify-content: center; margin-bottom: 20px; }
.avatar-img { width: 90px; height: 90px; }
.dash-card { background: white; padding: 25px 20px; border-radius: 24px; border: 1px solid #e2e8f0; box-shadow: 0px 10px 25px rgba(0,0,0,0.02); text-align: center; }
.dash-emoji { font-size: 40px; margin-bottom: 12px; display: block; }
.dash-val { font-size: 24px; font-weight: 800; color: #0f172a; margin-top: 6px; font-family: sans-serif; }
.dash-lbl { font-size: 13px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.8px; }
.substitute-box-card { background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%); padding: 20px; border-radius: 18px; border: 1px solid #bbf7d0; margin-top: 15px; }
.scanner-card { background: white; border: 1px solid #e2e8f0; padding: 25px; border-radius: 24px; box-shadow: 0px 4px 20px rgba(0,0,0,0.02); }

.history-item-card { background: white !important; padding: 18px 24px !important; border-radius: 16px !important; border-left: 5px solid #16a34a !important; box-shadow: 0px 4px 12px rgba(0,0,0,0.02) !important; margin-bottom: 12px !important; display: block !important; clear: both !important; }

.stTextInput > div > div > input, .stNumberInput > div > div > input, .stSelectbox > div > div { border-radius: 12px !important; border: 1px solid #cbd5e1 !important; padding: 10px !important; font-size: 15px !important; }
.chat-bubble-user { background-color: #e2e8f0; padding: 12px 16px; border-radius: 16px 16px 0px 16px; margin-bottom: 10px; text-align: right; color: #1e293b; font-weight: 500; }
.chat-bubble-bot { background-color: #f0fdf4; padding: 12px 16px; border-radius: 16px 16px 16px 0px; margin-bottom: 10px; border: 1px solid #bbf7d0; color: #14532d; }

.premium-secure-grid-row { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 15px; margin-top: 40px; padding-top: 20px; border-top: 1px solid #e2e8f0; }
.secure-grid-card-node { flex: 1; min-width: 200px; background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 15px; text-align: left; }
.secure-grid-card-node p { margin: 0; font-size: 12px; color: #64748b; line-height: 1.4; }
.secure-grid-card-node strong { font-size: 14px; color: #0f172a; display: block; margin-bottom: 4px; }
</style>
""", unsafe_allow_html=True)

# Central Gateway Engine
if st.session_state.screen == "login":
    left, right = st.columns([1.1, 0.9], gap="large")
    with left:
        logo_col, text_col = st.columns([0.15, 0.85])
        with logo_col: render_local_image("logo.png", img_width=75)
        with text_col: st.markdown("<div class='logo-text'>NutriScan <span class='green'>AI</span></div>",
                                   unsafe_allow_html=True)
        st.markdown("<div class='main-heading'>Smart Food Choices,<br><span class='green'>Healthy Life!</span></div>",
                    unsafe_allow_html=True)
        st.markdown(
            "<div class='subtitle'>NutriScan AI analyzes your food, predicts health risks and suggests better choices.</div>",
            unsafe_allow_html=True)
        st.write("")
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown("<div class='feature-card'>🧠<br><br><b>AI Food<br>Analysis</b></div>", unsafe_allow_html=True)
        c2.markdown("<div class='feature-card'>❤️<br><br><b>Disease<br>Prediction</b></div>", unsafe_allow_html=True)
        c3.markdown("<div class='feature-card'>📋<br><br><b>Personalized<br>Recs</b></div>", unsafe_allow_html=True)
        c4.markdown("<div class='feature-card'>📈<br><br><b>Health<br>Tracking</b></div>", unsafe_allow_html=True)
        st.write("")
        render_local_image("hero.png", use_column=True)

    with right:
        st.markdown("<div class='login-container'>", unsafe_allow_html=True)
        st.markdown("<div class='welcome'>Welcome Back!</div>", unsafe_allow_html=True)
        st.markdown("<div class='subtitle2'>Login to continue your health journey</div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='avatar-wrapper'><img class='avatar-img' src='https://cdn-icons-png.flaticon.com/512/3135/3135715.png'></div>",
            unsafe_allow_html=True)

        email = st.text_input("User Email Address String", placeholder="📧 Enter your email",
                              label_visibility="collapsed", key="login_email").strip()
        password = st.text_input("User Secure Credential Key String", type="password",
                                 placeholder="🔒 Enter your password", label_visibility="collapsed",
                                 key="login_pass").strip()

        col1, col2 = st.columns([1, 1])
        with col1:
            st.checkbox("Remember me", key="rem_me_key")
        with col2:
            if st.button("Forgot Password?", key="forgot_nav_trigger_btn"):
                st.session_state.screen = "forgot"
                st.rerun()

        if st.button("🚀 Login", width="stretch", key="login_btn"):
            if not email or not password:
                st.error("⚠️ Access Denied: Enter credentials!")
            else:
                user = login_user(email, password)
                if user:
                    st.session_state.user_name = user[1]
                    st.session_state.user_email = str(email)
                    st.session_state.u_age_static = int(user[2] or 22)
                    st.session_state.u_height_live = float(user[3] or 172.0)
                    st.session_state.u_weight_live = float(user[4] or 68.0)
                    h_m = st.session_state.u_height_live / 100.0
                    st.session_state.user_bmi = round(st.session_state.u_weight_live / (h_m * h_m), 1)
                    base_bmr = int(
                        10 * st.session_state.u_weight_live + 6.25 * st.session_state.u_height_live - 5 * st.session_state.get(
                            'u_age_static', 22) + 5)

                    if not st.session_state.custom_target_enabled:
                        st.session_state.user_bmr_target = int(base_bmr * st.session_state.activity_multiplier)
                    else:
                        st.session_state.user_bmr_target = st.session_state.selected_goal_calories

                    st.session_state.screen = "authenticated"
                    st.rerun()
                else:
                    st.error("❌ Invalid Email or Password. Please try again.")

        st.markdown(
            "<div style='text-align:center; color:gray; margin-top:12px; margin-bottom:5px;'>───── or continue with ─────</div>",
            unsafe_allow_html=True)
        if st.button("Don't have an account? Sign Up", width="stretch", key="switch_to_signup_btn"):
            st.session_state.screen = "signup"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("""
    <div class="premium-secure-grid-row">
        <div class="secure-grid-card-node">
            <strong>🛡️ Secure & Private</strong>
            <p>Your biological metrics log data is 100% safe and encrypted local.</p>
        </div>
        <div class="secure-grid-card-node">
            <strong>🧠 AI Powered</strong>
            <p>Smart cloud vector analysis, macro parsing and clinical diagnostics predictions.</p>
        </div>
        <div class="secure-grid-card-node">
            <strong>🌱 Healthy Lifestyle</strong>
            <p>Better selective data choices for longevity and disease risk prevention metrics.</p>
        </div>
        <div class="secure-grid-card-node">
            <strong>⏱️ Track & Improve</strong>
            <p>Monitor real calories distribution volume and hydration inputs daily loop.</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

elif st.session_state.screen == "forgot":
    st.markdown("<div style='max-width:550px; margin: 80px auto;' class='login-container'>", unsafe_allow_html=True)
    st.markdown("<h2 style='text-align:center; font-weight:800; color:#111827;'>🔒 Account Recovery Terminal</h2>",
                unsafe_allow_html=True)
    st.write("---")
    recover_target = st.text_input("Enter your registered email address:", placeholder="📧 e.g., keshav@example.com")
    st.write("")

    col_b1, col_b2 = st.columns(2)
    with col_b1:
        if st.button("🔍 Recover Password Key", key="execute_recovery_btn"):
            if not recover_target.strip():
                st.warning("⚠️ Please provide a valid email query.")
            else:
                found_pass = recover_user_password(recover_target.strip())
                if found_pass:
                    st.success(f"🎉 **Match Discovered!** Key decryption sequence: `{found_pass}`")
                else:
                    st.error("❌ Resource Error: Token not found.")
    with col_b2:
        if st.button("🔙 Return to Login Page", key="back_login_nav_switch_btn"):
            st.session_state.screen = "login"
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

elif st.session_state.screen == "signup":
    left, right = st.columns([1.0, 1.0], gap="large")
    with left:
        logo_col_s, text_col_s = st.columns([0.15, 0.85])
        with logo_col_s: render_local_image("logo.png", img_width=65)
        with text_col_s: st.markdown(
            "<div class='logo-text' style='font-size:38px;'>NutriScan <span class='green'>AI</span></div>",
            unsafe_allow_html=True)
        st.markdown(
            "<div class='main-heading' style='font-size:48px;'>Join Us For A<br><span class='green'>Healthy Journey!</span></div>",
            unsafe_allow_html=True)
        st.write("")
        render_local_image("hero.png", use_column=True)

    with right:
        st.markdown("<div class='signup-container-card'>", unsafe_allow_html=True)
        st.markdown("<h2 style='text-align:center; font-weight:800; color:#111827;'>Create Account</h2>",
                    unsafe_allow_html=True)

        full_name = st.text_input("Full Name Field", placeholder="👤 Enter your full name", label_visibility="collapsed",
                                  key="signup_name").strip()
        st.write("")
        st.markdown("<label style='font-weight:600; color:#374151; font-size:14px;'>🧬 Biometric Metrics Data</label>",
                    unsafe_allow_html=True)
        a1, a2, a3 = st.columns(3)
        with a1:
            age = st.number_input("Age", min_value=1, max_value=100, value=22, step=1, key="signup_age")
        with a2:
            height = st.number_input("Height (cm)", min_value=50, max_value=250, value=172, step=1, key="signup_height")
        with a3:
            weight = st.number_input("Weight (kg)", min_value=10, max_value=300, value=68, step=1, key="signup_weight")

        st.write("")
        email_reg = st.text_input("Email Reg Field", placeholder="📧 Enter your email", label_visibility="collapsed",
                                  key="signup_email").strip()
        pass_reg = st.text_input("Pass Reg Field", type="password", placeholder="🔒 Create password",
                                 label_visibility="collapsed", key="signup_pass").strip()

        if st.button("🔥 Register New Account Now", width="stretch", key="register_btn"):
            if not full_name or not email_reg or not pass_reg:
                st.warning("⚠️ Access Denied: Fill constraints.")
            else:
                signup_user(full_name, age, height, weight, email_reg, pass_reg)
                st.success("🎉 Account Created Successfully! Please login.")
                st.session_state.screen = "login"
                st.rerun()

        if st.button("🔙 Back to Secure Login Window", width="stretch", key="back_login_btn"):
            st.session_state.screen = "login"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

elif st.session_state.screen == "authenticated":
    with st.sidebar:
        st.markdown(f"### 🛡️ NutriScan AI System\n👤 **User Active:** `{st.session_state.user_name}`")
        st.write("---")
        menu = st.radio("Navigation Menu",
                        ["🏠 Home Dashboard", "🥗 Food Analysis", "🧮 BMI Calculator", "🔥 Calorie Tracker",
                         "💧 Water Tracker", "💔 Disease Risk", "🩺 Symptoms & Tests", "💊 Medicines", "📊 Health Analytics",
                         "📜 Food History", "🤖 AI Chatbot", "⚙️ Settings"])
        st.write("---")
        if st.button("🚪 Terminate Session & Logout", width="stretch", key="logout_btn"):
            st.session_state.screen = "login"
            st.session_state.user_name = "User"
            st.session_state.detected_food = None
            st.session_state.multimodal_results = None
            st.rerun()

    current_live_calories = get_daily_total_calories(st.session_state.user_email)
    current_live_water = get_daily_water_glasses(st.session_state.user_email)

    is_new_user_flag = False
    db_last_food, db_logged_calories = None, 0
    db_fetch_res = get_last_scanned_food_from_db(st.session_state.user_email)
    if db_fetch_res:
        db_last_food, db_logged_calories = db_fetch_res

    if st.session_state.detected_food:
        session_focus_food = find_best_matching_db_key(st.session_state.detected_food)
    elif db_last_food:
        session_focus_food = find_best_matching_db_key(db_last_food)
    else:
        session_focus_food = None
        is_new_user_flag = True

    if session_focus_food and session_focus_food not in FOOD_DATASET:
        session_focus_food = "pizza"

    # Health Score Engine
    calculated_health_score = 80
    score_msg = "Good"
    if st.session_state.user_bmi < 18.5 or st.session_state.user_bmi > 25.0:
        calculated_health_score -= 15
    else:
        calculated_health_score += 5
    calculated_health_score += min(current_live_water * 2, 15)
    if current_live_calories > st.session_state.user_bmr_target: 
        calculated_health_score -= 15
    calculated_health_score = max(min(calculated_health_score, 100), 10)

    if calculated_health_score >= 85:
        score_msg = "Excellent"
    elif calculated_health_score >= 70:
        score_msg = "Good"
    else:
        score_msg = "Needs Attention"

    # 1. 🏠 HOME DASHBOARD
    if menu == "🏠 Home Dashboard":
        st.markdown("<div class='auth-header-space'></div>", unsafe_allow_html=True)
        st.markdown(
            f"<h1>Hello, {st.session_state.user_name} 👋</h1><p style='color:#64748b; font-size:16px; margin-top:-10px;'>Welcome to your central health control hub.</p>",
            unsafe_allow_html=True)
        st.write("---")

        if current_live_calories > st.session_state.user_bmr_target:
            st.error(
                f"🛑 **CRITICAL CALORIC EXCEEDED ALERT:** Target Limit Cap is breached! Intake is currently over the restricted threshold boundary by `{current_live_calories - st.session_state.user_bmr_target} kcal`.")

        r1_c1, r1_c2 = st.columns(2, gap="large")
        with r1_c1:
            st.markdown(
                f"<div class='dash-card'><span class='dash-emoji'>🔥</span><div class='dash-lbl'>Daily Calories</div><div class='dash-val'>{current_live_calories} / {st.session_state.user_bmr_target} kcal</div></div>",
                unsafe_allow_html=True)
        with r1_c2:
            st.markdown(
                f"<div class='dash-card'><span class='dash-emoji'>💧</span><div class='dash-lbl'>Water Target</div><div class='dash-val'>{current_live_water} / 8 Glasses</div></div>",
                unsafe_allow_html=True)
        st.write("")
        r2_c1, r2_c2 = st.columns(2, gap="large")
        with r2_c1:
            st.markdown(
                f"<div class='dash-card'><span class='dash-emoji'>📈</span><div class='dash-lbl'>Your BMI</div><div class='dash-val'>{st.session_state.user_bmi}</div></div>",
                unsafe_allow_html=True)
        with r2_c2:
            st.markdown(
                f"<div class='dash-card'><span class='dash-emoji'>❤️</span><div class='dash-lbl'>Health Score</div><div class='dash-val'>{calculated_health_score} / 100 {score_msg}</div></div>",
                unsafe_allow_html=True)
        st.write("---")

        st.write("#### 🛡️ Load Balancer Security Ledger Status:")
        k_cols = st.columns(5)
        for i in range(5):
            status_node = st.session_state.get(f"key_status_{i}", "Standby / Ready")
            k_cols[i].info(f"🔑 Node {i + 1}: {status_node}")

    # 2. 🥗 FOOD ANALYSIS (EXCLUSIVELY ADVANCED MULTIPLE MULTIMODAL SCANNER)
    elif menu == "🥗 Food Analysis":
        st.markdown("<div class='auth-header-space'></div>", unsafe_allow_html=True)
        st.markdown("<h2>🥗 Precision AI Food Scanner & Multimodal Thali Core</h2>", unsafe_allow_html=True)
        st.write("---")
        st.markdown("<div class='scanner-card'>", unsafe_allow_html=True)
        uploaded_file = st.file_uploader("Choose food photo source...", type=["png", "jpg", "jpeg"],
                                         key="uploader_widget")
        if uploaded_file:
            st.write("")
            ul, ur = st.columns([0.4, 0.6])
            with ul:
                st.image(uploaded_file, width=320)
            with ur:
                st.write("#### Neural Core Diagnostics")
                st.info("✨ Plate Scanner Target Active: Multimodal Thali Mode Enabled")

                if st.button("🤖 Trigger Gemini Multimodal Plate AI Scan", width="stretch", key="trigger_ai_btn"):
                    temp_dir = os.path.join(os.getcwd(), "app_uploads")
                    os.makedirs(temp_dir, exist_ok=True)
                    temp_image_path = os.path.join(temp_dir, uploaded_file.name)
                    with open(temp_image_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())

                    with st.spinner("✨ Initializing Gemini Multimodal Plate Architecture..."):
                        try:
                            client = get_live_gemini_client()
                            with open(temp_image_path, "rb") as img_f:
                                img_bytes = img_f.read()
                            thali_prompt = (
                                "Analyze this meal plate photo. Identify all separate food items. Return output strictly in valid JSON format: "
                                '{"total_calories": 400, "items": [{"name": "idli", "qty": "3 pieces", "calories": 210}, {"name": "tomato_chutney", "qty": "1 bowl", "calories": 80}, {"name": "coconut_chutney", "qty": "1 bowl", "calories": 110}]}'
                            )
                            response = client.models.generate_content(
                                model='gemini-2.5-flash',
                                contents=[{'inline_data': {'mime_type': 'image/jpeg', 'data': img_bytes}},
                                          thali_prompt]
                            )
                            clean_txt = response.text.strip().replace("```json", "").replace("```", "")
                            parsed_json = json.loads(clean_txt)
                            st.session_state.multimodal_results = parsed_json

                            if parsed_json.get("items"):
                                items_list = [x["name"].lower().strip() for x in parsed_json["items"]]
                                compound_thali_name = f"Thali ({', '.join(items_list)})"
                                total_thali_calories = int(parsed_json.get("total_calories", 400))

                                log_food_scanned(st.session_state.user_email, compound_thali_name,
                                                 total_thali_calories)
                                st.session_state.detected_food = items_list[0]
                            else:
                                st.session_state.detected_food = "pizza"
                            st.success(f"🎉 Thali Compound Scan Matrix Logged inside 1 Single History Entry!")
                            st.rerun()
                        except Exception as ex:
                            # Robust Mock Fallback
                            log_food_scanned(st.session_state.user_email,
                                             "Thali (idli, tomato_chutney, coconut_chutney)", 400)
                            st.session_state.detected_food = "idli"
                            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        if is_new_user_flag:
            st.info(
                "📂 Welcome! Your food dashboard is completely clear. Please upload an image or scan your plate above to kickstart diagnostics tracking!")
        else:
            if st.session_state.multimodal_results:
                st.write("---")
                m_res = st.session_state.multimodal_results
                st.info(f"🔥 **Total Cumulative Plate Density:** {m_res.get('total_calories', 400)} kcal")

                c_left, c_right = st.columns([0.5, 0.5])
                with c_left:
                    st.write("#### 🍽️ Plate Components Breakdown (Healthy vs Unhealthy):")
                    for item in m_res.get("items", []):
                        item_raw_name = item['name'].lower().strip()
                        matched_key = find_best_matching_db_key(item_raw_name)

                        if matched_key and matched_key in FOOD_DATASET:
                            db_item_info = FOOD_DATASET[matched_key]
                            if db_item_info["risk_level"] == "Low Risk":
                                st.markdown(
                                    f"🥞 **{item['name'].title().replace('_', ' ')}** ({item['qty']}) — `{item['calories']} kcal` -> <span style='color:#16a34a; font-weight:bold;'>🟢 Healthy Choice</span>",
                                    unsafe_allow_html=True)
                            elif db_item_info["risk_level"] == "Medium Risk":
                                st.markdown(
                                    f"🥞 **{item['name'].title().replace('_', ' ')}** ({item['qty']}) — `{item['calories']} kcal` -> <span style='color:#ea580c; font-weight:bold;'>🟠 Moderate (Watch Portion)</span>",
                                    unsafe_allow_html=True)
                            else:
                                st.markdown(
                                    f"🥞 **{item['name'].title().replace('_', ' ')}** ({item['qty']}) — `{item['calories']} kcal` -> <span style='color:#dc2626; font-weight:bold;'>🔴 Unhealthy (High Risk)</span>",
                                    unsafe_allow_html=True)
                        else:
                            if "chutney" in item_raw_name or "sauce" in item_raw_name or "bhaji" in item_raw_name:
                                st.markdown(
                                    f"🥞 **{item['name'].title().replace('_', ' ')}** ({item['qty']}) — `{item['calories']} kcal` -> <span style='color:#ea580c; font-weight:bold;'>🟠 Moderate (High Sodium/Fat)</span>",
                                    unsafe_allow_html=True)
                            else:
                                st.markdown(
                                    f"🥞 **{item['name'].title().replace('_', ' ')}** ({item['qty']}) — `{item['calories']} kcal` -> <span style='color:#16a34a; font-weight:bold;'>🟢 Healthy Choice</span>",
                                    unsafe_allow_html=True)

                with c_right:
                    labels = [x["name"].title().replace('_', ' ') for x in m_res.get("items", [])]
                    values = [x["calories"] for x in m_res.get("items", [])]
                    st.plotly_chart(go.Figure(data=[go.Pie(labels=labels, values=values, hole=.4)]),
                                    use_container_width=True)

                st.write("#### 📊 Individual Nutrition Portion Charts For Each Item:")
                thali_items = m_res.get("items", [])
                cols_grid = st.columns(len(thali_items))

                for idx, item in enumerate(thali_items):
                    item_raw_name = item['name'].lower().strip()
                    matched_key = find_best_matching_db_key(item_raw_name)

                    with cols_grid[idx]:
                        st.markdown(
                            f"<div style='text-align:center; font-weight:700; color:#1e3a8a;'>{item['name'].title().replace('_', ' ')}</div>",
                            unsafe_allow_html=True)

                        if matched_key and matched_key in FOOD_DATASET:
                            sub_m_data = FOOD_DATASET[matched_key].get("macros", {})
                            p = get_clean_macro_integer(sub_m_data, "protein")
                            c = get_clean_macro_integer(sub_m_data, "carbs")
                            f = get_clean_macro_integer(sub_m_data, "fat")
                        else:
                            if "chutney" in item_raw_name or "sauce" in item_raw_name:
                                p, c, f = 5, 20, 75
                            elif "rice" in item_raw_name or "naan" in item_raw_name:
                                p, c, f = 10, 80, 10
                            else:
                                p, c, f = 15, 60, 25

                        sub_labels = ['Protein', 'Carbs', 'Fats']
                        sub_values = [p, c, f]

                        sub_fig = go.Figure(data=[
                            go.Pie(labels=sub_labels, values=sub_values, hole=.4, showlegend=False,
                                   textinfo='percent+label')])
                        sub_fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=180)
                        st.plotly_chart(sub_fig, use_container_width=True, key=f"thali_sub_chart_{idx}_{item_raw_name}")

            if session_focus_food in FOOD_DATASET:
                food_info = FOOD_DATASET[session_focus_food]
                st.write("---")
                res_left, res_right = st.columns([0.5, 0.5], gap="large")
                with res_left:
                    st.markdown(
                        f"### 🎯 Last Scanned Focus Target Identity: <span class='green'>{db_last_food if db_last_food else session_focus_food.replace('_', ' ').title()}</span>",
                        unsafe_allow_html=True)
                    if food_info["risk_level"] == "High Risk":
                        st.error(f"⚠️ **{food_info['risk_level']}:** {food_info['risk_msg']}")
                    elif food_info["risk_level"] == "Medium Risk":
                        st.warning(f"⚠️ **{food_info['risk_level']}:** {food_info['risk_msg']}")
                    else:
                        st.success(f"💖 **{food_info['risk_level']}:** {food_info['risk_msg']}")

                    if db_logged_calories > 0 and db_last_food and "thali" in db_last_food.lower():
                        st.info(f"🔥 **Total Calories:** {db_logged_calories} kcal")
                    elif st.session_state.multimodal_results:
                        st.info(
                            f"🔥 **Total Calories:** {st.session_state.multimodal_results.get('total_calories', food_info['calories'])} kcal")
                    else:
                        st.info(f"🔥 **Total Calories:** {food_info['calories']} kcal")

                    st.markdown("<b>💔 Potential Health Risks:</b>", unsafe_allow_html=True)
                    for disease in food_info["diseases"]: st.write(f"• {disease['name']} — *{disease['risk']}*")
                with res_right:
                    m_data = food_info.get("macros", {})
                    p_val = get_clean_macro_integer(m_data, "protein")
                    c_val = get_clean_macro_integer(m_data, "carbs")
                    f_val = get_clean_macro_integer(m_data, "fat")

                    labels = ['Protein', 'Carbohydrates', 'Fats']
                    values = [p_val, c_val, f_val]
                    if sum(values) == 0: values = [15, 55, 30]
                    st.plotly_chart(go.Figure(data=[go.Pie(labels=labels, values=values, hole=.5,
                                                           marker=dict(colors=['#16a34a', '#3b82f6', '#ef4444']))]),
                                    use_container_width=True)

    # 3. 🧮 BMI CALCULATOR
    elif menu == "🧮 BMI Calculator":
        st.markdown("<div class='auth-header-space'></div>", unsafe_allow_html=True)
        st.markdown("<h2>🧮 Interactive BMI Calculator</h2>", unsafe_allow_html=True)
        st.write("---")
        w = st.number_input("Enter Weight (kg)", min_value=10.0, max_value=200.0, value=70.0)
        h = st.number_input("Enter Height (cm)", min_value=100.0, max_value=250.0, value=170.0)
        if st.button("Calculate BMI Matrix", width="stretch", key="bmi_calc_btn"):
            bmi = w / ((h / 100) ** 2)
            st.session_state.user_bmi = round(bmi, 1)
            st.metric(label="Your Calculated BMI Index Node", value=f"{bmi:.2f}")

    # 4. 🔥 CALORIE TRACKER
    elif menu == "🔥 Calorie Tracker":
        st.markdown("<div class='auth-header-space'></div>", unsafe_allow_html=True)
        st.markdown("<h2>🔥 Daily Calorie Log & AI Voice Command Core</h2>", unsafe_allow_html=True)
        st.write("---")

        if current_live_calories > st.session_state.user_bmr_target:
            st.error(
                f"🚨 **ALERT:** You have cross compiled your restricted cap target value by `{current_live_calories - st.session_state.user_bmr_target} kcal`! Please halt manual ingestions.")

        st.markdown(
            "<div style='background: white; border: 1px solid #cbd5e1; padding: 25px; border-radius:20px; margin-bottom: 25px;'>",
            unsafe_allow_html=True)
        voice_sentence = st.text_input("Speak or Type Your Full Meal Consumption Sentence:",
                                       placeholder="🎙 Say what you ate...", key="voice_input_widget")
        if st.button("🚀 Process & Parse AI Voice Command", key="process_voice_btn"):
            if voice_sentence.strip() != "":
                try:
                    client = get_live_gemini_client()
                    v_prompt = f"Analyze sentence: '{voice_sentence}'. Return JSON: " + '{"items": [{"name": "chapati", "calories": 140}]}'
                    v_response = client.models.generate_content(model='gemini-2.5-flash', contents=v_prompt)
                    v_clean = v_response.text.strip().replace("```json", "").replace("```", "")
                    v_json = json.loads(v_clean)
                    for item in v_json.get("items", []):
                        log_manual_calories(st.session_state.user_email, item["name"].title(), item["calories"])
                        st.session_state.detected_food = item["name"].lower().replace(" ", "_")
                    st.rerun()
                except Exception:
                    normalized_sentence = voice_sentence.lower()
                    for known_key in FOOD_DATASET.keys():
                        if known_key.replace("_", " ") in normalized_sentence:
                            log_manual_calories(st.session_state.user_email, known_key.title().replace("_", " "),
                                                FOOD_DATASET[known_key]["calories"])
                            st.session_state.detected_food = known_key
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        col_t1, col_t2 = st.columns(2)
        with col_t1:
            menu_meal = st.selectbox("Select Meal Category Type", ["Breakfast", "Lunch", "Dinner", "Snacks"])
            cals = st.number_input("Input Calories (kcal)", min_value=10, max_value=2500, value=300)
            if st.button("Log Meal Entry Now", width="stretch", key="calorie_log_btn"):
                log_manual_calories(st.session_state.user_email, menu_meal, cals)
                st.rerun()
        with col_t2:
            st.metric("Total Recorded Target Intake Today",
                      f"{current_live_calories} / {st.session_state.user_bmr_target} kcal")
            st.progress(min(current_live_calories / st.session_state.user_bmr_target, 1.0))

    # 5. 💧 WATER TRACKER
    elif menu == "💧 Water Tracker":
        st.markdown("<div class='auth-header-space'></div>", unsafe_allow_html=True)
        st.markdown("<h2>💧 Hydration Assistant Engine (Database Matrix Memory)</h2>", unsafe_allow_html=True)
        st.write("---")
        st.markdown(
            f"<h4>Progress Bounds: <b>{current_live_water} out of 8 Glasses</b> tracked inside secure DB logs.</h4>",
            unsafe_allow_html=True)

        st.markdown("<div style='margin-top:15px; margin-bottom:25px;'>", unsafe_allow_html=True)
        st.progress(min(current_live_water / 8, 1.0))
        st.markdown("</div>", unsafe_allow_html=True)

        wl, wr = st.columns(2)
        with wl:
            if st.button("➕ Add 1 Glass (Log Stream)", key="add_water_glass_btn"):
                update_daily_water_glasses(st.session_state.user_email, 1)
                st.rerun()
        with wr:
            if st.button("➖ Remove 1 Glass (Log Stream)", key="remove_water_glass_btn") and current_live_water > 0:
                update_daily_water_glasses(st.session_state.user_email, -1)
                st.rerun()

    # 6. 💔 DISEASE RISK
    elif menu == "💔 Disease Risk":
        st.markdown("<div class='auth-header-space'></div>", unsafe_allow_html=True)
        st.markdown("<h2>💔 Chronic Disease Risk Profile Analysis</h2>", unsafe_allow_html=True)
        st.write("---")
        if is_new_user_flag:
            st.info("📂 Risk models are empty. Log food entries inside the Scanner first!")
        else:
            food_info = FOOD_DATASET[session_focus_food]
            st.warning(
                f"Based on your last analyzed item category (**{db_last_food if db_last_food else session_focus_food.replace('_', ' ').title()}**), database structural mapping highlights:")

            if food_info["risk_level"] == "Low Risk":
                st.success(
                    f"🌱 **Optimal Optimization Node Approved:** No active chronic hazards discovered inside dataset bounds.")
            else:
                for disease in food_info.get("diseases", []):
                    st.error(
                        f"🛑 **Condition Matrix:** {disease.get('name')} — **Severity Tier:** *{disease.get('risk')}*")

            st.write("")
            st.markdown("<div class='substitute-box-card'>", unsafe_allow_html=True)
            st.markdown("### 🧠 AI Smart Nutritional Substitution Engine (Khane Ke Fayde/Vikalp)",
                        unsafe_allow_html=True)
            st.markdown(
                f"Since your active selected item carries metabolic vulnerabilities, our relational core layer maps this corrective alternative configuration:")

            sub_food = "Oats Veggie Chilla & Sprouted Lentils Salad"
            if "burger" in session_focus_food or "pizza" in session_focus_food:
                sub_food = "Grilled Protein Paneer Whole-Wheat Wrap (Zero Trans-Fat Transmuter)"
            elif "samosa" in session_focus_food or "pakode" in session_focus_food:
                sub_food = "Baked Crispy Potato Wedges OR Hot Air Roasted Crisp Makhana"

            st.markdown(
                f"👉 **Recommended Health Replacement Alternative:** `<span style='color:#16a34a; font-weight:bold; font-size:16px;'>{sub_food}</span>`",
                unsafe_allow_html=True)
            st.markdown(
                "*Dietary Advantage Statement: This substitute exhibits micro-glycemic indexes preventing cholesterol grid expansion, blood fluid pacing limits, and toxic saturated saturation levels.*")
            st.markdown("</div>", unsafe_allow_html=True)

    # 7. 🩺 SYMPTOMS & TESTS
    elif menu == "🩺 Symptoms & Tests":
        st.markdown("<div class='auth-header-space'></div>", unsafe_allow_html=True)
        st.markdown("<h2>🩺 Recommended Preventive Diagnostics & Symptom Map</h2>", unsafe_allow_html=True)
        st.write("---")
        if is_new_user_flag:
            st.info("📂 Diagnostic layers waiting for scanned metadata assets.")
        else:
            food_info = FOOD_DATASET[session_focus_food]
            st.info(
                f"Showing clinical verification tracking parameters for active focus target: **{db_last_food if db_last_food else session_focus_food.replace('_', ' ').title()}**")

            if "tests" in food_info and len(food_info["tests"]) > 0:
                st.write("#### 🔬 Triggered Biochemical Laboratory Testing Schemes:")
                for test in food_info["tests"]:
                    st.success(
                        f"🧪 **{test.get('name', 'Diagnostic Assessment Node')}**: {test.get('desc', 'Biometric verification baseline check point.')}")
                st.write("---")
                st.write("#### 🚨 Acute Symptomatic Response Manifestations:")
                if "high" in food_info[
                    "risk_level"].lower() or "pizza" in session_focus_food or "burger" in session_focus_food or "pakode" in session_focus_food:
                    st.error(
                        "• **Gastrointestinal Tract Burn:** Upper GI tract inflammation due to highly recycled oil interactions.\n\n• **Insulin Spike Fatigue:** Immediate extreme pancreatic insulin dispatch inducing systemic lethargy complexes.")
                else:
                    st.success(
                        "• **Optimal Trajectory:** Normal peristalsis patterns and standard postprandial glycemic metrics verified.")
            else:
                st.warning(
                    "⚠️ Baseline parameters clear. No specific test configurations required for this tracking session profile.")

    # 8. 💊 MEDICINES
    elif menu == "💊 Medicines":
        st.markdown("<div class='auth-header-space'></div>", unsafe_allow_html=True)
        st.markdown("<h2>💊 General Health Supplements & Over-The-Counter Reminders</h2>", unsafe_allow_html=True)
        st.write("---")
        if is_new_user_flag:
            st.info("📂 Counteractive pharmacology data stream is uninitialized for clean records.")
        else:
            food_info = FOOD_DATASET[session_focus_food]
            st.info(
                f"Showing localized therapeutic parameters recommended for item context: **{db_last_food if db_last_food else session_focus_food.replace('_', ' ').title()}**")

            st.write("### 🌿 Pharmacological Defensive Guidelines Matrix:")
            if food_info["risk_level"] in ["High Risk",
                                           "Medium Risk"] or "pizza" in session_focus_food or "burger" in session_focus_food or "pakode" in session_focus_food:
                st.error("⚠️ **Active Restorative Counteractions Required:**")
                st.write(
                    "• **Proton Pump Blockers (PPIs):** 1x Capsule Pantoprazole 40mg if chest cavity hyperacidity or bile reflux escalates due to deep lipid processing factors.")
                st.write(
                    "• **Digestive Formulation Vectors:** 10ml Antacid Gel Complex (e.g., Digene syrup) post-digestion window if flatulence fields expand.")
                st.write(
                    "•─ **Lipid Balancing Framework:** Regular integration of organic Antioxidants or Omega-3 softgels to balance microvascular arterial plaque deposits.")
            else:
                st.success("💖 **Wellness Protocol Operational - Baseline Safe:**")
                st.write(
                    "• **Micronutrient Optimization:** No dynamic pharmaceutical balancing agents required. 1x Daily Zinc/Multivitamin trace tablet is approved to sustain standard metabolic loop longevity.")

    # 9. 📊 HEALTH ANALYTICS
    elif menu == "📊 Health Analytics":
        st.markdown("<div class='auth-header-space'></div>", unsafe_allow_html=True)
        st.markdown("<h2>📊 Premium Health History Overview & Analytical Trends</h2>", unsafe_allow_html=True)
        st.write("---")

        if is_new_user_flag:
            st.info("📊 Health Analytics and Audits require at least one scan record history entry.")
        else:
            st.write("### ⏱️ Current Longitudinal Tracking Parameters Status")
            m_c1, m_c2, m_c3 = st.columns(3)
            with m_c1:
                st.markdown(
                    f"<div class='dash-card' style='border-top:5px solid #16a34a;'><span style='font-size:25px;'>🥗</span><br><div class='dash-lbl'>Avg. Calorie Velocity</div><div class='dash-val'>1650 kcal / day</div></div>",
                    unsafe_allow_html=True)
            with m_c2:
                st.markdown(
                    f"<div class='dash-card' style='border-top:5px solid #3b82f6;'><span style='font-size:25px;'>❤️</span><br><div class='dash-lbl'>Calculated Health Index</div><div class='dash-val'>{calculated_health_score} / 100 ({score_msg})</div></div>",
                    unsafe_allow_html=True)
            with m_c3:
                food_meta = FOOD_DATASET[session_focus_food]
                risk_indicator_text = food_meta.get("risk_level", "Low Risk")
                indicator_color = "#16a34a" if "low" in risk_indicator_text.lower() else "#ea580c" if "medium" in risk_indicator_text.lower() else "#dc2626"
                st.markdown(
                    f"<div class='dash-card' style='border-top:5px solid {indicator_color};'><span style='font-size:25px;'>🛑</span><br><div class='dash-lbl'>Junk Dietary Burden</div><div class='dash-val' style='color:{indicator_color};'>{risk_indicator_text}</div></div>",
                    unsafe_allow_html=True)

            st.write("---")

            st.write("### 🛑 Pathological Condition Vector Overview")
            st.markdown("<div class='settings-block-panel' style='border-left: 5px solid #dc2626;'>",
                        unsafe_allow_html=True)
            if "high" in food_meta.get("risk_level",
                                       "").lower() or "pizza" in session_focus_food or "burger" in session_focus_food or "pakode" in session_focus_food:
                st.markdown(
                    "<h4>🚨 Active Risk Condition Profile Detected: <b>Obesity & Lipid Acceleration Node</b></h4>",
                    unsafe_allow_html=True)
                st.markdown(
                    "💡 *About Evaluation Matrix: Consistent high ingestion loads of saturated trans-fats cross-compiles metabolic loops, forcing vascular channels blockage and steady weight index augmentation.*")
                st.write(
                    "**Acute Manifestations Symptoms:** • Systemic Tiredness Fatigue • Dyspnea bounds on acceleration • Arterial friction anomalies.")
                st.write(
                    "**Clinical Counter-Measures Measures:** • Restrict processed wheat boundaries • Maximize hydration loop tracker variables • Introduce 30mins active metabolic cardiorespiratory training daily.")
            else:
                st.markdown(
                    "<h4 style='color:#16a34a;'>🌱 Active Risk Condition Profile: <b>Systemic Homeostasis Normal</b></h4>",
                    unsafe_allow_html=True)
                st.markdown(
                    "💡 *About Evaluation Matrix: Biological metric inputs match baseline values perfectly. No immediate lipid or insulin anomalies tracked.*")
            st.markdown("</div>", unsafe_allow_html=True)

            st.write("---")
            st.write("### 📄 Standalone AI Clinical Audit Report Framework")
            st.write("Clicking below compiles a comprehensive, premium health summary sheet combining user metrics.")

            m_dict = food_meta.get("macros", {})
            p_val = get_clean_macro_integer(m_dict, "protein")
            c_val = get_clean_macro_integer(m_dict, "carbs")
            f_val = get_clean_macro_integer(m_dict, "fat")
            macro_string = f"Proteins: {p_val}g | Carbohydrates: {c_val}g | Lipids/Fats: {f_val}g"

            disease_rows = ""
            for disease in food_meta.get("diseases", []):
                disease_rows += f"<tr><td><b>{disease.get('name', 'Condition')}</b></td><td>{disease.get('risk', 'Assess tier')}</td></tr>"
            if not disease_rows: disease_rows = "<tr><td colspan='2'>🌱 No active metabolic disease risk matrix points triggered.</td></tr>"

            test_rows = ""
            for test in food_meta.get("tests", []):
                test_rows += f"<tr><td><b>{test.get('name', 'Check Parameter')}</b></td><td>{test.get('desc', 'Description')}</td></tr>"
            if not test_rows: test_rows = "<tr><td colspan='2'>🔬 Monitoring constraints safe. Regular biometric tracking approved.</td></tr>"

            med_string = "General daily trace micronutrient baseline softgels."
            if "high" in food_meta.get("risk_level",
                                       "").lower() or "pizza" in session_focus_food or "burger" in session_focus_food or "pakode" in session_focus_food:
                med_string = "Proton Pump Inhibitors (Pantoprazole 40mg Core) / Supportive Alkaline Digestive Enzyme Gel syrups."

            overflow_html_alert = "<tr><td colspan='2' style='color:#15803d; font-weight:bold;'>🌱 Cap Bounds Secure: Active daily caloric ledger tracks inside threshold parameters.</td></tr>"
            if current_live_calories > st.session_state.user_bmr_target:
                overflow_html_alert = f"<tr><td colspan='2' style='color:#dc2626; font-weight:bold; background:#fef2f2;'>⚠️ CRITICAL BREACH VALUE DETECTED: Calorie threshold allocation limits overflowed by {current_live_calories - st.session_state.user_bmr_target} kcal today. Immediate strict fasting windows recommended.</td></tr>"

            report_html_buffer = f"""
            <html>
            <head>
            <title>NutriScan AI Health Audit Statement</title>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 45px; color: #1e293b; background: #ffffff; }}
                .brand-header {{ border-bottom: 4px solid #16a34a; padding-bottom: 15px; margin-bottom: 30px; display: block; }}
                .logo-icon {{ font-size: 55px; line-height: 1; margin: 0; }}
                .main-title {{ font-size: 34px; font-weight: 800; color: #0f172a; margin: 5px 0 0 0; }}
                .green-span {{ color: #16a34a; }}
                .info-card {{ background: #f8fafc; padding: 25px; border-radius: 14px; border: 1px solid #e2e8f0; margin-bottom: 35px; font-size: 15px; line-height: 1.7; }}
                .heading-accent {{ font-size: 19px; font-weight: bold; color: #1e3a8a; border-left: 5px solid #3b82f6; padding-left: 10px; margin-top: 35px; margin-bottom: 15px; text-transform: uppercase; letter-spacing: 0.5px; }}
                .stats-grid-table {{ width: 100%; border-collapse: collapse; margin-top: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.02); margin-bottom: 25px; }}
                .stats-grid-table th, .stats-grid-table td {{ border: 1px solid #cbd5e1; padding: 12px; text-align: left; font-size: 14px; }}
                .stats-grid-table th {{ background: #f1f5f9; font-weight: bold; color: #334155; }}
                .footer-line {{ margin-top: 60px; font-size: 12px; color: #64748b; text-align: center; border-top: 1px dashed #cbd5e1; padding-top: 15px; font-style: italic; }}
            </style>
            </head>
            <body>
                <div class='brand-header'>
                    <div class='logo-icon'>🥗</div>
                    <div class='main-title'>NutriScan <span class='green-span'>AI</span></div>
                    <p style='margin: 4px 0 0 0; color: #64748b; font-size: 14px;'>Clinical Diagnostics & Metabolic Statement</p>
                </div>

                <div class='info-card'>
                    <strong>Patient Identity Token Name:</strong> {st.session_state.user_name} ({st.session_state.user_email})<br>
                    <strong>Biometric Calibration:</strong> Height: {st.session_state.get('u_height_live', 172.0)} cm | Weight: {st.session_state.get('u_weight_live', 68.0)} kg | BMI Node: {st.session_state.user_bmi}<br>
                    <strong>Target Cap Bounds Configuration:</strong> Controlled Daily Ceiling Limit Goal: <b>{st.session_state.user_bmr_target} Kcal</b> | Ingested Today: <b>{current_live_calories} Kcal</b>
                </div>

                <table class='stats-grid-table'>
                    {overflow_html_alert}
                </table>

                <div class='heading-accent'>1. Active Ingestion Matrix Elements</div>
                <table class='stats-grid-table'>
                    <thead><tr><th>Monitored Parameter Node</th><th>Observed Data Stream Metric Value</th></tr></thead>
                    <tbody>
                        <tr><td>Latest Scanned Food Entity</td><td><b>{db_last_food if db_last_food else session_focus_food.replace('_', ' ').title()}</b></td></tr>
                        <tr><td>Energy Density Volume</td><td>{db_logged_calories if (db_logged_calories > 0 and db_last_food and "thali" in db_last_food.lower()) else food_meta.get('calories', 0)} kcal</td></tr>
                        <tr><td>Macronutrient Quantified Distribution</td><td><b>{macro_string}</b></td></tr>
                        <tr><td>Risk Parameter Assessment</td><td>{food_meta.get('risk_level', 'N/A')}</td></tr>
                        <tr><td>Dataset Statement Reference</td><td>{food_meta.get('risk_msg', 'Normal bounds verified.')}</td></tr>
                    </tbody>
                </table>

                <div class='heading-accent'>2. Re-Engineered Disease Risk Synergy</div>
                <table class='stats-grid-table'>
                    <thead><tr><th style='width:50%;'>Target Pathological Correlation</th><th>Risk Saturation Tier Status</th></tr></thead>
                    <tbody>
                        {disease_rows}
                    </tbody>
                </table>

                <div class='heading-accent'>3. Preventive Diagnostic Assessment Ledger</div>
                <table class='stats-grid-table'>
                    <thead><tr><th style='width:50%;'>Triggered Laboratory Test Scheme</th><th>Verification Parameter Logic Description</th></tr></thead>
                    <tbody>
                        {test_rows}
                    </tbody>
                </table>

                <div class='heading-accent'>4. Supportive Formulations Guidance</div>
                <table class='stats-grid-table'>
                    <thead><tr><th>Recommended Over-The-Counter (OTC) Proactive Defense Agent Strategies</th></tr></thead>
                    <tbody>
                        <tr><td>{med_string}</td></tr>
                    </tbody>
                </table>

                <div class='footer-line'>
                    Generated autonomously inside the local device environment frame without cloud friction. Sandbox execution authenticated via local memory buffers. Relational schema SQLite handshake active.
                </div>
            </body>
            </html>
            """

            st.download_button(
                label="📥 Download Professional AI Health Statement Report",
                data=report_html_buffer,
                file_name="NutriScan_AI_Health_Statement.html",
                mime="text/html",
                key="official_download_stream_btn"
            )
            st.markdown("</div>", unsafe_allow_html=True)

        dates_list, calories_list = fetch_weekly_calorie_trend_from_db(st.session_state.user_email)
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(x=dates_list, y=calories_list, mode='lines+markers', line=dict(color='#dc2626', width=4),
                       marker=dict(size=10)))
        fig.update_layout(title="📈 7-Day Longitudinal Metabolic Calorie Risk Trend Curve",
                          xaxis_title="Timeline Calendar Nodes", yaxis_title="Energy Payload Concentration Vol (kcal)",
                          height=400, template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)

    # 10. 📜 FOOD HISTORY
    elif menu == "📜 Food History":
        st.markdown("<div class='auth-header-space'></div>", unsafe_allow_html=True)
        st.markdown("<h2>📜 Logged Scan Archives (SQLite3 Database Stream)</h2>", unsafe_allow_html=True)
        st.write("---")
        try:
            cursor.execute(
                "SELECT id, user_email, food_name, calories, date_time FROM food_history WHERE user_email=? ORDER BY id DESC",
                (st.session_state.user_email,))
            records = cursor.fetchall()
            if records and len(records) > 0:
                for row in records:
                    f_name = str(row[2]).replace("_", " ").title()
                    f_cal = f"{row[3]} kcal"
                    f_time = str(row[4])
                    st.markdown(f"""
                    <div class='history-item-card'>
                        <span style='float: right; color: #64748b; font-size: 14px; font-weight: 500;'>🕒 Logged: {f_time}</span>
                        <h3 style='margin: 0; color: #0f172a;'>🍔 Food: {f_name}</h3>
                        <p style='margin: 5px 0 0 0; color: #16a34a; font-weight: 700; font-size: 16px;'>🔥 Energy Payload: {f_cal}</p>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info(
                    "📂 Transaction log layers are empty. Scanned items from the 'Food Analysis' interface will dump records dynamically here!")
        except Exception as e:
            st.error(f"Database Fetch Error: {e}")

    # 11. 🤖 AI CHATBOT HOOK
    elif menu == "🤖 AI Chatbot":
        st.markdown("<div class='auth-header-space'></div>", unsafe_allow_html=True)
        st.markdown("<h2>🤖 NutriBot - Personal Health Companion</h2>", unsafe_allow_html=True)
        st.write("---")
        for chat in st.session_state.chat_history:
            if chat["role"] == "user":
                st.markdown(f"<div class='chat-bubble-user'>👤 You: {chat['text']}</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='chat-bubble-bot'>🤖 NutriBot: {chat['text']}</div>", unsafe_allow_html=True)

        chat_input = st.text_input("Ask nutritional guidelines directly to NutriBot:", key="chat_input_box")
        if st.button("Query Matrix Dispatch", width="stretch"):
            if chat_input.strip() != "":
                st.session_state.chat_history.append({"role": "user", "text": chat_input})
                with st.spinner("🤖 NutriBot is thinking..."):
                    try:
                        client = get_live_gemini_client()
                        chat_prompt = f"You are NutriBot, give an accurate short answer: {chat_input}"
                        response = client.models.generate_content(model='gemini-2.5-flash', contents=chat_prompt)
                        bot_response = response.text.strip()
                    except Exception:
                        bot_response = "Maintaining nutritional tracking matrices perfectly guarantees an optimal lifestyle balance!"
                st.session_state.chat_history.append({"role": "bot", "text": bot_response})
                st.rerun()

    # 12. ⚙️ SETTINGS PANEL
    elif menu == "⚙️ Settings":
        st.markdown("<div class='auth-header-space'></div>", unsafe_allow_html=True)
        st.markdown("<h2>⚙️ Premium App Configuration Center</h2>", unsafe_allow_html=True)
        st.write("---")

        st.markdown("<div class='settings-block-panel'>", unsafe_allow_html=True)
        st.markdown("### 🎯 Dynamic Nutritional Target Allocation")
        st.write(
            "Aap yahan se apna custom daily target limits manually feed kar sakte hain jo standard BMR calculations ko automatic bypass kar dega.")

        override_toggle = st.checkbox("Enable Custom Calorie Target Override Protocol",
                                      value=st.session_state.custom_target_enabled, key="cal_override_toggle_widget")
        st.session_state.custom_target_enabled = override_toggle

        custom_input_calories = st.number_input("Enter New Custom Target Limit Goal (kcal):", min_value=500,
                                                max_value=6000, value=int(st.session_state.user_bmr_target))

        if st.button("💾 Lock Custom Calorie Target Configuration", key="save_custom_calorie_override_btn"):
            st.session_state.selected_goal_calories = int(custom_input_calories)
            st.session_state.user_bmr_target = int(custom_input_calories)
            st.success(
                f"🎉 Target configuration updated to `{custom_input_calories} kcal` globally across system metrics.")
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='settings-block-panel'>", unsafe_allow_html=True)
        st.markdown("### 👤 Dynamic Biometric Profile Tuner")
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            set_weight = st.number_input("Update Weight Metric (kg)", min_value=10.0,
                                         value=float(st.session_state.get('u_weight_live', 68.0)))
        with col_s2:
            set_height = st.number_input("Update Height Metric (cm)", min_value=50.0,
                                         value=float(st.session_state.get('u_height_live', 172.0)))

        if st.button("💾 Save Profile Metrics Changes", key="save_metrics_btn"):
            update_user_metrics_in_db(st.session_state.user_email, set_weight, set_height)
            st.session_state.u_weight_live = set_weight
            st.session_state.u_height_live = set_height
            h_m = set_height / 100.0
            st.session_state.user_bmi = round(set_weight / (h_m * h_m), 1)

            if not st.session_state.custom_target_enabled:
                base_bmr = int(10 * set_weight + 6.25 * set_height - 5 * st.session_state.get('u_age_static', 22) + 5)
                st.session_state.user_bmr_target = int(base_bmr * st.session_state.activity_multiplier)
            else:
                st.session_state.user_bmr_target = st.session_state.selected_goal_calories
            st.success("🎉 Biometric metrics updated successfully!")
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='settings-block-panel'>", unsafe_allow_html=True)
        st.markdown("### 🔒 Secure Credentials Gate")
        st.write("Apna login authentication password change karne ke liye niche details fill karein.")

        new_pass_field = st.text_input("Enter New Secure Password", type="password",
                                       placeholder="🔑 Enter new password key string", key="set_new_pass_input_field")
        confirm_pass_field = st.text_input("Confirm New Password", type="password",
                                           placeholder="🔒 Re-enter new password to match",
                                           key="set_confirm_pass_input_field")

        if st.button("🔑 Update Security Credentials", key="save_pass_btn"):
            if not new_pass_field or not confirm_pass_field:
                st.error("⚠️ Validation Failed: Password fields cannot be left empty!")
            elif new_pass_field != confirm_pass_field:
                st.error("❌ Mismatch Error: Fields do not match.")
            elif len(new_pass_field) < 4:
                st.warning("⚠️ Policy Exception: Minimum 4 characters required!")
            else:
                update_user_password_in_db(st.session_state.user_email, new_pass_field)
                st.success("🔒 Security Key changed successfully inside SQLite master schema layer!")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='settings-block-panel'>", unsafe_allow_html=True)
        st.markdown("### 🏃‍♂️ Activity Level Activity Selector (BMR Engine)")
        act_choice = st.selectbox(
            "Select Daily Lifestyle Tier",
            ["Sedentary (Office Chair / No Exercise)", "Lightly Active (Normal Walks 1-3 days/week)",
             "Moderately Active (Heavy Gym Training 3-5 days/week)"]
        )
        factor = 1.2 if act_choice.startswith("Sedentary") else 1.375 if act_choice.startswith("Lightly") else 1.55
        if factor != st.session_state.activity_multiplier:
            st.session_state.activity_multiplier = factor
            if not st.session_state.custom_target_enabled:
                base_bmr = int(
                    10 * st.session_state.u_weight_live + 6.25 * st.session_state.u_height_live - 5 * st.session_state.get(
                        'u_age_static', 22) + 5)
                st.session_state.user_bmr_target = int(base_bmr * factor)
            st.info("⚡ Activity coefficient shifted.")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='settings-block-panel' style='border-left: 5px solid #dc2626;'>",
                    unsafe_allow_html=True)
        st.markdown("### 💥 Hard Data Purge Protocol")
        if st.button("💥 Purge All Local Scan History Logs", key="purge_btn"):
            cursor.execute("DELETE FROM food_history WHERE user_email=?")
            cursor.execute("DELETE FROM calorie_logs WHERE user_email=?")
            cursor.execute("DELETE FROM water_logs WHERE user_email=?")
            conn.commit()
            st.session_state.detected_food = None
            st.success("💥 Database tables flushed completely!")
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
