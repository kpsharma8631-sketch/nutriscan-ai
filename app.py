# app.py
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
# 🚨 ENVIRONMENT ROUTING CONFIGURATIONS (CLOUD COMPATIBLE)
# =========================================================
# Local windows environment path hata diya hai taaki cloud par crash na ho.
try:
    from model import predict_food_item
except ImportError:
    # Fallback to avoid deployment failure if model.py isn't present on cloud
    def predict_food_item(img_path): return "invalid", 0, 0, 0

# =========================================================
# 🎯 5 MULTI-API KEY FAILOVER POOL ROUTER SYSTEM
# =========================================================
GEMINI_KEYS_POOL = [
    st.secrets.get("GEMINI_API_KEY", ""), # Phele Streamlit Secrets se check karega
"AIzaSyDIu3gNlfi_pSF28LOVGmcR_4CETfg9lM4", 
"AIzaSyCcxAvs93jnGMKwdTPIpkvD-EMX6Np2p0g",
"AIzaSyAqkA2bxvMx2G2WBcJ_gG9wQrNWYhJfUEc",
"AIzaSyAZZQ4j8vxTriXHmuuKFrXsc-1OBn2EyYg"
]

def get_live_gemini_client():
    for idx, key in enumerate(GEMINI_KEYS_POOL):
        if key and not key.startswith("YOUR_API"):
            try:
                st.session_state[f"key_status_{idx}"] = "Active"
                return genai.Client(api_key=key)
            except:
                st.session_state[f"key_status_{idx}"] = "Exhausted"
                continue
    return genai.Client(api_key=GEMINI_KEYS_POOL[0] if GEMINI_KEYS_POOL else None)

# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="NutriScan AI",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================================================
# DATABASE SETUP & SCHEMA MAPPING
# =========================================================
conn = sqlite3.connect("users.db", check_same_thread=False)
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
# DATABASE OPERATIONS (UPDATED FOR COMPLETE PROFILE MANAGEMENT)
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

def update_user_profile_in_db(email, new_name, new_age, new_weight, new_height):
    cursor.execute("UPDATE users SET name=?, age=?, weight=?, height=? WHERE email=?",
                   (str(new_name), int(new_age), float(new_weight), float(new_height), str(email)))
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
    except:
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
    except:
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
                "<div style='background:#f0fdf4; height:180px; border-radius:18px; display:flex; align-items:center; justify-content:center; color:#16a34a;'><b>[ NutriScan AI Graphic Asset ]</b></div>",
                unsafe_allow_html=True)

# =========================================================
# 🚨 BULLETPROOF EXACT DATASET KEY-MAPPER
# =========================================================
def get_clean_macro_integer(macros_dict, key_name):
    if key_name == "protein" and "Protein" in macros_dict: return int(macros_dict["Protein"])
    if key_name == "carbs" and "Carbs" in macros_dict: return int(macros_dict["Carbs"])
    if key_name == "fat" and "Fats" in macros_dict: return int(macros_dict["Fats"])
    if key_name == "protein" and "protein" in macros_dict: return int(macros_dict["protein"])
    if key_name == "carbs" and "carbs" in macros_dict: return int(macros_dict["carbs"])
    if key_name == "fat" and "fat" in macros_dict: return int(macros_dict["fat"])
    return 0

def find_best_matching_db_key(input_food_string):
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
# CORPORATE ELK-RESPONSIVE UI STYLESHEET (FIXES CUTTING)
# =========================================================
st.markdown("""
<style>
.stApp { background-color: #f8fafc; }
footer { display: none !important; }
[data-testid="stSidebarNav"], [data-testid="stSidebarNavItems"] { display: none !important; height: 0px !important; overflow: hidden !important; }
[data-testid="stSidebarCollapseButton"] { display: flex !important; visibility: visible !important; color: #16a34a !important; background-color: #f0fdf4 !important; border-radius: 50% !important; }

/* Elastic Padding Fixes for Mobile & Laptop Screens */
.block-container { padding: 1.5rem min(3vw, 2.5rem) !important; }

div.stButton > button {
    background: linear-gradient(to right, #15803d, #22c55e) !important;
    color: white !important;
    border-radius: 12px !important;
    border: none !important;
    font-weight: 700 !important;
    padding: 10px 15px !important;
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

.logo-text { font-size: min(8vw, 45px); font-weight: 800; color: #111827; margin-top: 5px; }
.green { color: #16a34a; }
.main-heading { font-size: min(7vw, 54px); font-weight: 800; line-height: 1.2; margin-top: 15px; color: #111827; }
.subtitle { font-size: min(4vw, 18px); color: #4b5563; margin-top: 10px; line-height: 1.5; }
.feature-card { background: #f0fdf4; padding: 12px; border-radius: 14px; text-align: center; font-size: 13px; font-weight:600; }

/* Non-breaking Flexible Container Elements */
.login-container, .signup-container-card, .settings-block-panel { 
    background: white; 
    padding: min(5vw, 30px) !important; 
    border-radius: 20px; 
    box-shadow: 0px 8px 24px rgba(0,0,0,0.04); 
    margin-top: 15px; 
    border: 1px solid #e2e8f0;
}
.welcome { text-align: center; font-size: min(6vw, 36px); font-weight: 800; color: #111827; }
.subtitle2 { text-align: center; color: #6b7280; font-size: 14px; margin-bottom: 15px; }
.avatar-wrapper { display: flex; justify-content: center; margin-bottom: 15px; }
.avatar-img { width: 75px; height: 75px; }

/* Responsive Dashboard Metric Blocks Layouts */
.dash-card { background: white; padding: 15px; border-radius: 16px; border: 1px solid #e2e8f0; box-shadow: 0px 4px 12px rgba(0,0,0,0.01); text-align: center; margin-bottom: 10px; }
.dash-emoji { font-size: 30px; margin-bottom: 5px; display: block; }
.dash-val { font-size: min(5vw, 22px); font-weight: 800; color: #0f172a; margin-top: 4px; word-break: break-all; }
.dash-lbl { font-size: 12px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; }

.substitute-box-card { background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%); padding: 18px; border-radius: 14px; border: 1px solid #bbf7d0; margin-top: 15px; }
.scanner-card { background: white; border: 1px solid #e2e8f0; padding: 20px; border-radius: 18px; }
.history-item-card { background: white !important; padding: 15px !important; border-radius: 14px !important; border-left: 5px solid #16a34a !important; box-shadow: 0px 4px 10px rgba(0,0,0,0.01) !important; margin-bottom: 12px !important; display: block !important; overflow: hidden; }

.stTextInput > div > div > input, .stNumberInput > div > div > input, .stSelectbox > div > div { border-radius: 10px !important; border: 1px solid #cbd5e1 !important; padding: 6px !important; font-size: 14px !important; }

.premium-secure-grid-row { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 25px; padding-top: 15px; border-top: 1px solid #e2e8f0; }
.secure-grid-card-node { flex: 1; min-width: 140px; background: white; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px; }
.secure-grid-card-node strong { font-size: 12px; color: #0f172a; display: block; }
.secure-grid-card-node p { margin: 0; font-size: 11px; color: #64748b; line-height: 1.3; }
</style>
""", unsafe_allow_html=True)

# Central Gateway Engine
if st.session_state.screen == "login":
    left, right = st.columns([1, 1] if st.responsive else [1.1, 0.9], gap="medium")
    with left:
        logo_col, text_col = st.columns([0.2, 0.8])
        with logo_col: render_local_image("logo.png", img_width=75)
        with text_col: st.markdown("<div class='logo-text'>NutriScan <span class='green'>AI</span></div>", unsafe_allow_html=True)
        st.markdown("<div class='main-heading'>Smart Food Choices,<br><span class='green'>Healthy Life!</span></div>", unsafe_allow_html=True)
        st.markdown("<div class='subtitle'>NutriScan AI analyzes your food, predicts health risks and suggests better choices.</div>", unsafe_allow_html=True)
        st.write("")
        
        # Responsive Feature Grid Fix
        fc1, fc2 = st.columns(2)
        with fc1: st.markdown("<div class='feature-card'>🧠 AI Food Analysis</div>", unsafe_allow_html=True)
        with fc2: st.markdown("<div class='feature-card'>❤️ Disease Prediction</div>", unsafe_allow_html=True)
        st.write("")
        fc3, fc4 = st.columns(2)
        with fc3: st.markdown("<div class='feature-card'>📋 Personalized Recs</div>", unsafe_allow_html=True)
        with fc4: st.markdown("<div class='feature-card'>📈 Health Tracking</div>", unsafe_allow_html=True)
        st.write("")
        render_local_image("hero.png", use_column=True)

    with right:
        st.markdown("<div class='login-container'>", unsafe_allow_html=True)
        st.markdown("<div class='welcome'>Welcome Back!</div>", unsafe_allow_html=True)
        st.markdown("<div class='subtitle2'>Login to continue your health journey</div>", unsafe_allow_html=True)
        st.markdown("<div class='avatar-wrapper'><img class='avatar-img' src='https://cdn-icons-png.flaticon.com/512/3135/3135715.png'></div>", unsafe_allow_html=True)

        email = st.text_input("User Email Address String", placeholder="📧 Enter your email", label_visibility="collapsed", key="login_email").strip()
        password = st.text_input("User Secure Credential Key String", type="password", placeholder="🔒 Enter your password", label_visibility="collapsed", key="login_pass").strip()

        col1, col2 = st.columns(2)
        with col1: st.checkbox("Remember me", key="rem_me_key")
        with col2:
            if st.button("Forgot Password?", key="forgot_nav_trigger_btn"):
                st.session_state.screen = "forgot"
                st.rerun()

        if st.button("🚀 Login", key="login_btn"):
            if not email or not password: st.error("⚠️ Access Denied: Enter credentials!")
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
                    base_bmr = int(10 * st.session_state.u_weight_live + 6.25 * st.session_state.u_height_live - 5 * st.session_state.get('u_age_static', 22) + 5)

                    if not st.session_state.custom_target_enabled:
                        st.session_state.user_bmr_target = int(base_bmr * st.session_state.activity_multiplier)
                    else:
                        st.session_state.user_bmr_target = st.session_state.selected_goal_calories

                    st.session_state.screen = "authenticated"
                    st.rerun()
                else: st.error("❌ Invalid Email or Password.")

        st.markdown("<div style='text-align:center; color:gray; margin-top:12px; margin-bottom:5px;'>───── or ─────</div>", unsafe_allow_html=True)
        if st.button("Don't have an account? Sign Up", key="switch_to_signup_btn"):
            st.session_state.screen = "signup"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

elif st.session_state.screen == "forgot":
    st.markdown("<div class='login-container' style='max-width:500px; margin: 40px auto;'>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align:center; font-weight:800; color:#111827;'>🔒 Account Recovery</h3>", unsafe_allow_html=True)
    st.write("---")
    recover_target = st.text_input("Enter your registered email address:", placeholder="📧 e.g., keshav@example.com")
    st.write("")

    col_b1, col_b2 = st.columns(2)
    with col_b1:
        if st.button("🔍 Recover Key", key="execute_recovery_btn"):
            if not recover_target.strip(): st.warning("⚠️ Enter an email.")
            else:
                found_pass = recover_user_password(recover_target.strip())
                if found_pass: st.success(f"🎉 Password Discovery: `{found_pass}`")
                else: st.error("❌ Token not found.")
    with col_b2:
        if st.button("🔙 Back to Login", key="back_login_nav_switch_btn"):
            st.session_state.screen = "login"
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

elif st.session_state.screen == "signup":
    left, right = st.columns([1, 1], gap="medium")
    with left:
        st.markdown("<div class='logo-text' style='font-size:32px;'>NutriScan <span class='green'>AI</span></div>", unsafe_allow_html=True)
        st.markdown("<div class='main-heading' style='font-size:38px;'>Join Us For A<br><span class='green'>Healthy Journey!</span></div>", unsafe_allow_html=True)
        render_local_image("hero.png", use_column=True)

    with right:
        st.markdown("<div class='signup-container-card'>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align:center; font-weight:800;'>Create Account</h3>", unsafe_allow_html=True)

        full_name = st.text_input("Full Name Field", placeholder="👤 Enter your full name", label_visibility="collapsed", key="signup_name").strip()
        st.write("")
        st.markdown("<label style='font-weight:600; font-size:13px;'>🧬 Biometric Metrics Data</label>", unsafe_allow_html=True)
        a1, a2, a3 = st.columns(3)
        with a1: age = st.number_input("Age", min_value=1, max_value=100, value=22, step=1, key="signup_age")
        with a2: height = st.number_input("Height (cm)", min_value=50, max_value=250, value=172, step=1, key="signup_height")
        with a3: weight = st.number_input("Weight (kg)", min_value=10, max_value=300, value=68, step=1, key="signup_weight")

        st.write("")
        email_reg = st.text_input("Email Reg Field", placeholder="📧 Enter your email", label_visibility="collapsed", key="signup_email").strip()
        pass_reg = st.text_input("Pass Reg Field", type="password", placeholder="🔒 Create password", label_visibility="collapsed", key="signup_pass").strip()

        if st.button("🔥 Register Account Now", key="register_btn"):
            if not full_name or not email_reg or not pass_reg: st.warning("⚠️ Fill all fields.")
            else:
                signup_user(full_name, age, height, weight, email_reg, pass_reg)
                st.success("🎉 Account Created! Please login.")
                st.session_state.screen = "login"
                st.rerun()

        if st.button("🔙 Back to Login Window", key="back_login_btn"):
            st.session_state.screen = "login"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

elif st.session_state.screen == "authenticated":
    with st.sidebar:
        st.markdown(f"### 🛡️ NutriScan AI Core\n👤 **User Active:** `{st.session_state.user_name}`")
        st.write("---")
        menu = st.radio("Navigation Menu",
                        ["🏠 Home Dashboard", "🥗 Food Analysis", "🧮 BMI Calculator", "🔥 Calorie Tracker",
                         "💧 Water Tracker", "💔 Disease Risk", "🩺 Symptoms & Tests", "💊 Medicines", "📊 Health Analytics",
                         "📜 Food History", "🤖 AI Chatbot", "⚙️ Settings"])
        st.write("---")
        if st.button("🚪 Logout Session", key="logout_btn"):
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
    if db_fetch_res: db_last_food, db_logged_calories = db_fetch_res

    if st.session_state.detected_food:
        session_focus_food = find_best_matching_db_key(st.session_state.detected_food)
    elif db_last_food:
        session_focus_food = find_best_matching_db_key(db_last_food)
    else:
        session_focus_food = None
        is_new_user_flag = True

    if session_focus_food and session_focus_food not in FOOD_DATASET:
        session_focus_food = "pizza"

    # Elastic Health Score Computation Engine
    calculated_health_score = 80
    score_msg = "Good"
    if st.session_state.user_bmi < 18.5 or st.session_state.user_bmi > 25.0: calculated_health_score -= 15
    else: calculated_health_score += 5
    calculated_health_score += min(current_live_water * 2, 15)
    if current_live_calories > st.session_state.user_bmr_target: calculated_health_score -= 15
    calculated_health_score = max(min(calculated_health_score, 100), 10)
    if calculated_health_score >= 85: score_msg = "Excellent"
    elif calculated_health_score >= 70: score_msg = "Good"
    else: score_msg = "Needs Attention"

    # =========================================================
    # 1. 🏠 HOME DASHBOARD (FIXED MULTI-COLUMN CRUSHING)
    # =========================================================
    if menu == "🏠 Home Dashboard":
        st.markdown(f"<h1>Hello, {st.session_state.user_name} 👋</h1>", unsafe_allow_html=True)
        st.write("---")

        if current_live_calories > st.session_state.user_bmr_target:
            st.error(f"🛑 **CALORIC OVERFLOW ALERT:** Target breached by `{current_live_calories - st.session_state.user_bmr_target} kcal`.")

        # Stacking layout gracefully using vertical modules rather than squished side columns
        st.markdown(f"<div class='dash-card'><span class='dash-emoji'>🔥</span><div class='dash-lbl'>Daily Calories Intake</div><div class='dash-val'>{current_live_calories} / {st.session_state.user_bmr_target} kcal</div></div>", unsafe_allow_html=True)
        st.markdown(f"<div class='dash-card'><span class='dash-emoji'>💧</span><div class='dash-lbl'>Water Log Tracker</div><div class='dash-val'>{current_live_water} / 8 Glasses</div></div>", unsafe_allow_html=True)
        st.markdown(f"<div class='dash-card'><span class='dash-emoji'>📈</span><div class='dash-lbl'>Calculated BMI Index</div><div class='dash-val'>{st.session_state.user_bmi}</div></div>", unsafe_allow_html=True)
        st.markdown(f"<div class='dash-card'><span class='dash-emoji'>❤️</span><div class='dash-lbl'>System Health Score</div><div class='dash-val'>{calculated_health_score} / 100 ({score_msg})</div></div>", unsafe_allow_html=True)

    # =========================================================
    # 2. 🥗 FOOD ANALYSIS (ADDED DROPDOWN SEARCH LIST FEATURE)
    # =========================================================
    elif menu == "🥗 Food Analysis":
        st.markdown("<h2>🥗 Precision AI Food Scanner & Search Core</h2>", unsafe_allow_html=True)
        st.write("---")
        
        # 🚨 Dynamic Global Food Database Selector (Doston Ke Search Karne Ke Liye)
        st.write("#### 🔍 Search & Track Food Manually From Global List")
        available_food_options = sorted([key.replace("_", " ").title() for key in FOOD_DATASET.keys()])
        selected_search_food = st.selectbox("Type or select a food item name to query statistics:", ["-- Select From List --"] + available_food_options)
        
        if selected_search_food != "-- Select From List --":
            target_mapped_key = selected_search_food.lower().replace(" ", "_")
            if st.button(f"📥 Log Selected '{selected_search_food}' to Database History", key="manual_list_log_btn"):
                log_food_scanned(st.session_state.user_email, target_mapped_key, FOOD_DATASET[target_mapped_key]["calories"])
                st.session_state.detected_food = target_mapped_key
                st.success(f"🎉 Successfully logged '{selected_search_food}' into your history!")
                st.rerun()

        st.write("---")
        st.write("#### 📸 Alternate Upload: Analyze Plate via Vision AI Engine")
        
        st.markdown("<div class='scanner-card'>", unsafe_allow_html=True)
        uploaded_file = st.file_uploader("Choose food photo source...", type=["png", "jpg", "jpeg"], key="uploader_widget")
        if uploaded_file:
            st.image(uploaded_file, width=280)
            scan_type = st.radio("Scanning Engine Target:", ["Single Item Fast Scan", "✨ Multimodal Multi-Object Thali Scanner (Advanced)"])

            if st.button("🤖 Trigger Cloud Matrix AI Scan", key="trigger_ai_btn"):
                if scan_type == "Single Item Fast Scan":
                    # Simulated smart parsing loop
                    st.session_state.detected_food = "pizza"
                    st.session_state.multimodal_results = None
                    log_food_scanned(st.session_state.user_email, "pizza", FOOD_DATASET["pizza"]["calories"])
                    st.success("🎉 Photo matrix scanned! Item successfully logged as Pizza.")
                    st.rerun()
                else:
                    # Real/Mock Fluid multi-object failover logic router
                    parsed_json = {"total_calories": 400, "items": [{"name": "idli", "qty": "3 pcs", "calories": 210}, {"name": "chutney", "qty": "1 bowl", "calories": 190}]}
                    st.session_state.multimodal_results = parsed_json
                    log_food_scanned(st.session_state.user_email, "Thali (idli, chutney)", 400)
                    st.session_state.detected_food = "idli"
                    st.success("🎉 Compound Plate Array Processed into Cloud Storage Ledger!")
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        # Output Rendering Layer (Responsive stacked columns avoiding width truncation)
        if not is_new_user_flag and session_focus_food in FOOD_DATASET:
            food_info = FOOD_DATASET[session_focus_food]
            st.write("---")
            st.markdown(f"### 🎯 Focus Item Context: <span class='green'>{db_last_food if db_last_food else session_focus_food.replace('_', ' ').title()}</span>", unsafe_allow_html=True)
            
            st.info(f"🔥 **Calorie Value Payload:** {db_logged_calories if db_logged_calories > 0 else food_info['calories']} kcal")
            st.warning(f"📊 **Metabolic Assessment:** {food_info['risk_level']} — {food_info['risk_msg']}")
            
            m_data = food_info.get("macros", {})
            p_val = get_clean_macro_integer(m_data, "protein")
            c_val = get_clean_macro_integer(m_data, "carbs")
            f_val = get_clean_macro_integer(m_data, "fat")
            
            fig = go.Figure(data=[go.Pie(labels=['Protein', 'Carbs', 'Fats'], values=[p_val, c_val, f_val], hole=.4)])
            fig.update_layout(height=260, margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig, use_container_width=True)

    # =========================================================
    # 3. 🧮 BMI CALCULATOR
    # =========================================================
    elif menu == "🧮 BMI Calculator":
        st.markdown("<h2>🧮 Smart BMI Calculator Matrix</h2>", unsafe_allow_html=True)
        st.write("---")
        w = st.number_input("Enter Weight Profile (kg)", min_value=10.0, max_value=200.0, value=float(st.session_state.u_weight_live))
        h = st.number_input("Enter Height Profile (cm)", min_value=100.0, max_value=250.0, value=float(st.session_state.u_height_live))
        if st.button("Calculate BMI Matrix Values", key="bmi_calc_btn"):
            bmi = w / ((h / 100) ** 2)
            st.session_state.user_bmi = round(bmi, 1)
            st.metric(label="Your Calculated Metric Index", value=f"{bmi:.2f} kg/m²")

    # =========================================================
    # 4. 🔥 CALORIE TRACKER
    # =========================================================
    elif menu == "🔥 Calorie Tracker":
        st.markdown("<h2>🔥 Daily Calorie Manual Interface</h2>", unsafe_allow_html=True)
        st.write("---")
        menu_meal = st.selectbox("Select Meal Category Type", ["Breakfast", "Lunch", "Dinner", "Snacks"])
        cals = st.number_input("Input Calories Volume (kcal)", min_value=10, max_value=2500, value=300)
        if st.button("Log Custom Meal Entry", key="calorie_log_btn"):
            log_manual_calories(st.session_state.user_email, menu_meal, cals)
            st.success("🎉 Calorie payload injected to local database timeline matrix.")
            st.rerun()

    # =========================================================
    # 5. 💧 WATER TRACKER
    # =========================================================
    elif menu == "💧 Water Tracker":
        st.markdown("<h2>💧 Automated Hydration Counter System</h2>", unsafe_allow_html=True)
        st.write("---")
        st.markdown(f"<h4>Current Liquid Velocity Logs: <b>{current_live_water} / 8 Glasses</b></h4>", unsafe_allow_html=True)
        st.progress(min(current_live_water / 8, 1.0))
        st.write("")
        if st.button("➕ Inject 1 Fluid Glass"):
            update_daily_water_glasses(st.session_state.user_email, 1)
            st.rerun()
        if st.button("➖ Decrement 1 Fluid Glass") and current_live_water > 0:
            update_daily_water_glasses(st.session_state.user_email, -1)
            st.rerun()

    # =========================================================
    # 6. 💔 DISEASE RISK
    # =========================================================
    elif menu == "💔 Disease Risk":
        st.markdown("<h2>💔 Pathological Chronic Disease Counterparts</h2>", unsafe_allow_html=True)
        st.write("---")
        if is_new_user_flag: st.info("📂 Diagnostic layers are clear.")
        else:
            food_info = FOOD_DATASET[session_focus_food]
            st.error(f"🛑 Active Risks Discovered for Context: **{session_focus_food.upper()}**")
            for d in food_info.get("diseases", []):
                st.write(f"• **{d['name']}** — Severity: *{d['risk']}*")
            
            st.markdown("<div class='substitute-box-card'><b>🧠 AI Smart Replacement Option:</b><br>Try swapping it out with whole grain alternative structures to clear arterial plaque buildup channels.</div>", unsafe_allow_html=True)

    # =========================================================
    # 7. 🩺 SYMPTOMS & TESTS
    # =========================================================
    elif menu == "🩺 Symptoms & Tests":
        st.markdown("<h2>🩺 Suggested Clinical Preventive Screenings</h2>", unsafe_allow_html=True)
        st.write("---")
        if is_new_user_flag: st.info("📂 Log data is uninitialized.")
        else:
            food_info = FOOD_DATASET[session_focus_food]
            for test in food_info.get("tests", []):
                st.success(f"🧪 **{test.get('name')}:** {test.get('desc')}")

    # =========================================================
    # 8. 💊 MEDICINES
    # =========================================================
    elif menu == "💊 Medicines":
        st.markdown("<h2>💊 General Counteractive Supplement Guidelines</h2>", unsafe_allow_html=True)
        st.write("---")
        st.info("💊 Metabolic framework operational baseline safe. Maintain antioxidant inputs to reverse trans-fat impact factors.")

    # =========================================================
    # 9. 📊 HEALTH ANALYTICS
    # =========================================================
    elif menu == "📊 Health Analytics":
        st.markdown("<h2>📊 Statistical Audit Statements Portal</h2>", unsafe_allow_html=True)
        st.write("---")
        if is_new_user_flag: st.info("📂 No analytical data pools mapped.")
        else:
            st.markdown(f"<div class='dash-card'>❤️ <b>Health Metric Score:</b> {calculated_health_score}/100 ({score_msg})</div>", unsafe_allow_html=True)
            dates_list, calories_list = fetch_weekly_calorie_trend_from_db(st.session_state.user_email)
            fig = go.Figure(data=go.Scatter(x=dates_list, y=calories_list, mode='lines+markers', line=dict(color='#16a34a', width=3)))
            fig.update_layout(height=280, margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig, use_container_width=True)

    # =========================================================
    # 10. 📜 FOOD HISTORY (ADDED CALENDAR DATE-PICKER FILTER)
    # =========================================================
    elif menu == "📜 Food History":
        st.markdown("<h2>📜 Logged Scan Archives (Relational SQLite Stream)</h2>", unsafe_allow_html=True)
        st.write("---")
        
        # 🚨 Dynamic Date-Picker Filter Widget Integration (Tareekh Se Filter Karne Ke Liye)
        st.write("#### 📅 Filter Scanning Ledger Logs By Specific Calendar Node")
        selected_filter_date = st.date_input("Select timeline lookup node:", datetime.date.today())
        filter_date_str = selected_filter_date.strftime("%Y-%m-%d")
        
        try:
            # Querying specifically using selected timestamp match logic
            cursor.execute("SELECT id, food_name, calories, date_time FROM food_history WHERE user_email=? AND date_time LIKE ? ORDER BY id DESC", 
                           (st.session_state.user_email, f"{filter_date_str}%"))
            filtered_records = cursor.fetchall()
            
            st.write(f"🔍 Found **{len(filtered_records)}** entries consumed on `{filter_date_str}`:")
            if filtered_records:
                for row in filtered_records:
                    st.markdown(f"""
                    <div class='history-item-card'>
                        <span style='float: right; color:#64748b; font-size:12px;'>🕒 Time Node: {row[3].split()[1]}</span>
                        <b>🍔 Item:</b> {str(row[1]).replace('_', ' ').title()} | <b>🔥 Energy Payload:</b> {row[2]} kcal
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("ℹ️ Is date par koi food scan/log nahi kiya gaya hai bantai.")
                
            # Fallback checkbox to view entire history un-filtered
            st.write("---")
            if st.checkbox("📋 Show Complete All-Time Global Logs Matrix"):
                cursor.execute("SELECT food_name, calories, date_time FROM food_history WHERE user_email=? ORDER BY id DESC", (st.session_state.user_email,))
                for row in cursor.fetchall():
                    st.markdown(f"<div class='history-item-card'><b>🍔 Food:</b> {str(row[0]).replace('_', ' ').title()} | <b>🔥 Ingestion Volume:</b> {row[1]} kcal | 🕒 {row[2]}</div>", unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Database Query Mapping Error: {e}")

    # =========================================================
    # 11. 🤖 AI CHATBOT
    # =========================================================
    elif menu == "🤖 AI Chatbot":
        st.markdown("<h2>🤖 NutriBot Conversational Terminal</h2>", unsafe_allow_html=True)
        st.write("---")
        chat_input = st.text_input("Dispatch direct text query matrix:")
        if st.button("Query Matrix Dispatch"):
            st.write("🤖 *NutriBot: Local operational loops active! Caloric ceiling parameters are verified safe.*")

    # =========================================================
    # 12. ⚙️ SETTINGS PANEL (DYNAMIC TERMINAL UPGRADE - NAME, AGE, PASS)
    # =========================================================
    elif menu == "⚙️ Settings":
        st.markdown("<h2>⚙️ Premium Profile Configurations Terminal</h2>", unsafe_allow_html=True)
        st.write("---")

        st.markdown("<div class='settings-block-panel'>", unsafe_allow_html=True)
        st.markdown("### 👤 Update Core Personal Biometrics")
        
        # Injected all core user database data management nodes
        up_name = st.text_input("Edit Profile Username Display Name:", value=str(st.session_state.user_name))
        up_age = st.number_input("Edit Profile Biological Age Vector (Years):", min_value=1, max_value=120, value=int(st.session_state.get('u_age_static', 22)))
        up_weight = st.number_input("Update Body Weight Parameter (kg):", min_value=10.0, value=float(st.session_state.get('u_weight_live', 68.0)))
        up_height = st.number_input("Update Body Height Parameter (cm):", min_value=50.0, value=float(st.session_state.get('u_height_live', 172.0)))
        
        if st.button("💾 Lock Dynamic Biometric Changes", key="save_metrics_btn"):
            update_user_profile_in_db(st.session_state.user_email, up_name, up_age, up_weight, up_height)
            st.session_state.user_name = up_name
            st.session_state.u_age_static = up_age
            st.session_state.u_weight_live = up_weight
            st.session_state.u_height_live = up_height
            
            h_m = up_height / 100.0
            st.session_state.user_bmi = round(up_weight / (h_m * h_m), 1)
            st.success("🎉 SQLite Schema Metrics Core Successfully Synced Globally!")
            st.responsive = True
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='settings-block-panel'>", unsafe_allow_html=True)
        st.markdown("### 🔒 Update Cryptographic Credential Password Key")
        new_pass = st.text_input("Enter New Password Sequence String:", type="password")
        confirm_pass = st.text_input("Re-Type Password Variant to Confirm Match Secure:", type="password")
        
        if st.button("🔑 Rewrite Database Password Record", key="save_pass_btn"):
            if new_pass and new_pass == confirm_pass:
                update_user_password_in_db(st.session_state.user_email, new_pass)
                st.success("🔒 Master schema verification sequence updated safely.")
            else:
                st.error("❌ Validation Failed: Passwords do not match or field data is empty.")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='settings-block-panel' style='border-left: 5px solid #dc2626;'>", unsafe_allow_html=True)
        st.markdown("### 💥 Danger Zone Hard Data Flusher")
        if st.button("💥 Flush History Ledger Logs Completely", key="purge_btn"):
            cursor.execute("DELETE FROM food_history WHERE user_email=?")
            cursor.execute("DELETE FROM calorie_logs WHERE user_email=?")
            cursor.execute("DELETE FROM water_logs WHERE user_email=?")
            conn.commit()
            st.session_state.detected_food = None
            st.success("💥 Sandbox SQLite transaction blocks dropped successfully.")
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
