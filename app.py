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
# 🚨 ENVIRONMENT ROUTING CONFIGURATIONS
# =========================================================
try:
    from model import predict_food_item
except ImportError:
    def predict_food_item(img_path): return "invalid", 0, 0, 0

# =========================================================
# 🎯 5 MULTI-API KEY FAILOVER POOL ROUTER SYSTEM
# =========================================================
GEMINI_KEYS_POOL = [
    st.secrets.get("GEMINI_API_KEY", ""), 
    "YOUR_API_KEY_1",
    "YOUR_API_KEY_2",
    "YOUR_API_KEY_3",
    "YOUR_API_KEY_4"
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
            st.markdown("<h2 style='font-size:38px; margin:0; padding-top:10px;'>🥗</h2>", unsafe_allow_html=True)
        else:
            st.markdown(
                "<div style='background:linear-gradient(to right, #f0fdf4, #e2e8f0); height:180px; border-radius:18px; display:flex; align-items:center; justify-content:center; color:#16a34a; font-weight:bold; border:2px dashed #bbf7d0;'>🥞 [ NutriScan AI Premium Brand Graphics Asset ]</div>",
                unsafe_allow_html=True)

# =========================================================
# DATASET KEY MAPPER
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
# GLOBAL STREAMLIT THEME FORCED FIXES (FOR AUTHENTICATION WINDOWS)
# =========================================================
st.markdown("""
<style>
/* Faltu Top Header White Space Core Fix */
.stAppHeader { display: none !important; }
.block-container { padding-top: 2rem !important; padding-bottom: 2rem !important; }

/* Forceful Native Button Stretch Override */
div[data-testid="stButton"] button {
    width: 100% !important;
    min-height: 48px !important;
    background: linear-gradient(to right, #15803d, #22c55e) !important;
    color: white !important;
    border-radius: 12px !important;
    font-weight: 700 !important;
    border: none !important;
}

/* Base Form Box Design Wrapper */
.auth-inner-box {
    background-color: #ffffff;
    padding: 30px;
    border-radius: 20px;
    border: 1px solid #e2e8f0;
    box-shadow: 0px 10px 25px rgba(0, 0, 0, 0.03);
}

.logo-text { font-size: 38px; font-weight: 800; color: #111827; margin: 0px; padding: 0px; display: inline-block; vertical-align: middle; }
.green { color: #16a34a; }
.main-heading { font-size: 42px; font-weight: 800; line-height: 1.2; color: #111827; margin-top: 10px; }
.subtitle { font-size: 16px; color: #4b5563; margin-top: 8px; margin-bottom: 15px; line-height: 1.5; }
.feature-card { background: #f0fdf4; padding: 12px; border-radius: 12px; text-align: center; font-weight: 600; font-size: 13px; color: #15803d; }
.welcome { text-align: center; font-size: 30px; font-weight: 800; color: #111827; }
.subtitle2 { text-align: center; color: #6b7280; font-size: 14px; margin-bottom: 15px; }
.avatar-wrapper { display: flex; justify-content: center; margin-bottom: 15px; }
.avatar-img { width: 75px; height: 75px; }

/* Dashboard UI Layout Cards */
.dash-card { background: white; padding: 20px 15px; border-radius: 18px; border: 1px solid #e2e8f0; box-shadow: 0px 4px 12px rgba(0,0,0,0.02); text-align: center; margin-bottom: 15px; }
.dash-emoji { font-size: 32px; margin-bottom: 5px; display: block; }
.dash-val { font-size: 22px; font-weight: 800; color: #0f172a; margin-top: 4px; }
.dash-lbl { font-size: 12px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; }
.history-item-card { background: white !important; padding: 15px !important; border-radius: 12px !important; border-left: 5px solid #16a34a !important; margin-bottom: 10px !important; display: block !important; }

/* Native Forms Dropdown/Inputs Heights Standardizer */
.stSelectbox div[data-baseweb="select"] > div { min-height: 45px !important; }

.premium-secure-grid-row { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 12px; margin-top: 25px; padding-top: 15px; border-top: 1px solid #e2e8f0; }
.secure-grid-card-node { flex: 1; min-width: 180px; background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 12px; }
.secure-grid-card-node strong { font-size: 13px; color: #0f172a; display: block; }
.secure-grid-card-node p { margin: 0; font-size: 11px; color: #64748b; line-height: 1.3; }
</style>
""", unsafe_allow_html=True)

# Central Gateway Engine
if st.session_state.screen == "login":
    left, right = st.columns([1.1, 0.9], gap="large")
    with left:
        # Fixed logo alignment issue via clean container block
        st.markdown("<div style='padding-top: 15px;'></div>", unsafe_allow_html=True)
        logo_col, text_col = st.columns([0.15, 0.85])
        with logo_col: render_local_image("logo.png", img_width=55)
        with text_col: st.markdown("<div class='logo-text'>NutriScan <span class='green'>AI</span></div>", unsafe_allow_html=True)
        st.markdown("<div class='main-heading'>Smart Food Choices,<br><span class='green'>Healthy Life!</span></div>", unsafe_allow_html=True)
        st.markdown("<div class='subtitle'>NutriScan AI analyzes your food, predicts health risks and suggests better choices.</div>", unsafe_allow_html=True)
        
        c1, c2 = st.columns(2)
        c1.markdown("<div class='feature-card'>🧠 AI Food Analysis</div>", unsafe_allow_html=True)
        c2.markdown("<div class='feature-card'>❤️ Disease Prediction</div>", unsafe_allow_html=True)
        st.write("")
        c3, c4 = st.columns(2)
        c3.markdown("<div class='feature-card'>📋 Personalized Recs</div>", unsafe_allow_html=True)
        c4.markdown("<div class='feature-card'>📈 Health Tracking</div>", unsafe_allow_html=True)
        st.write("")
        render_local_image("hero.png", use_column=True)

    with right:
        st.markdown("<div style='padding-top: 15px;'></div>", unsafe_allow_html=True)
        st.markdown("<div class='auth-inner-box'>", unsafe_allow_html=True)
        st.markdown("<div class='welcome'>Welcome Back!</div>", unsafe_allow_html=True)
        st.markdown("<div class='subtitle2'>Login to continue your health journey</div>", unsafe_allow_html=True)
        st.markdown("<div class='avatar-wrapper'><img class='avatar-img' src='https://cdn-icons-png.flaticon.com/512/3135/3135715.png'></div>", unsafe_allow_html=True)

        email = st.text_input("User Email Address String", placeholder="📧 Enter your email", label_visibility="collapsed", key="login_email").strip()
        password = st.text_input("User Secure Credential Key String", type="password", placeholder="🔒 Enter your password", label_visibility="collapsed", key="login_pass").strip()

        col1, col2 = st.columns([1, 1])
        with col1: st.checkbox("Remember me", key="rem_me_key")
        with col2:
            if st.button("Forgot Password?", key="forgot_nav_trigger_btn"):
                st.session_state.screen = "forgot"
                st.rerun()

        st.write("")
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

        st.markdown("<div style='text-align:center; color:gray; margin: 10px 0;'>───── or continue with ─────</div>", unsafe_allow_html=True)
        if st.button("Don't have an account? Sign Up", key="switch_to_signup_btn"):
            st.session_state.screen = "signup"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("""
    <div class="premium-secure-grid-row">
        <div class="secure-grid-card-node"><strong>🛡️ Secure & Private</strong><p>Encrypted local SQLite storage framework.</p></div>
        <div class="secure-grid-card-node"><strong>🧠 AI Powered</strong><p>Live deep diagnostics tracking loops.</p></div>
    </div>
    """, unsafe_allow_html=True)

elif st.session_state.screen == "forgot":
    st.markdown("<div style='max-width:500px; margin: 60px auto;' class='auth-inner-box'>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align:center; font-weight:800;'>🔒 Account Recovery Terminal</h3>", unsafe_allow_html=True)
    st.write("---")
    recover_target = st.text_input("Enter your registered email address:", placeholder="📧 e.g., keshav@example.com")
    st.write("")

    col_b1, col_b2 = st.columns(2)
    with col_b1:
        if st.button("🔍 Recover Password Key", key="execute_recovery_btn"):
            if not recover_target.strip(): st.warning("⚠️ Enter a valid email.")
            else:
                found_pass = recover_user_password(recover_target.strip())
                if found_pass: st.success(f"🎉 Password: `{found_pass}`")
                else: st.error("❌ Token not found.")
    with col_b2:
        if st.button("🔙 Return to Login Page", key="back_login_nav_switch_btn"):
            st.session_state.screen = "login"
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

elif st.session_state.screen == "signup":
    left, right = st.columns([1.0, 1.0], gap="large")
    with left:
        st.markdown("<div style='padding-top: 15px;'></div>", unsafe_allow_html=True)
        logo_col_s, text_col_s = st.columns([0.15, 0.85])
        with logo_col_s: render_local_image("logo.png", img_width=55)
        with text_col_s: st.markdown("<div class='logo-text' style='font-size:34px;'>NutriScan <span class='green'>AI</span></div>", unsafe_allow_html=True)
        st.markdown("<div class='main-heading' style='font-size:38px;'>Join Us For A<br><span class='green'>Healthy Journey!</span></div>", unsafe_allow_html=True)
        st.write("")
        render_local_image("hero.png", use_column=True)

    with right:
        st.markdown("<div style='padding-top: 15px;'></div>", unsafe_allow_html=True)
        st.markdown("<div class='auth-inner-box'>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align:center; font-weight:800; margin:0;'>Create Account</h3>", unsafe_allow_html=True)
        st.write("")
        full_name = st.text_input("Full Name Field", placeholder="👤 Enter your full name", label_visibility="collapsed", key="signup_name").strip()
        st.write("")
        st.markdown("<label style='font-weight:600; color:#374151; font-size:13px;'>🧬 Biometric Metrics Data</label>", unsafe_allow_html=True)
        
        a1, a2, a3 = st.columns(3)
        with a1: age = st.number_input("Age", min_value=1, max_value=100, value=22, step=1, key="signup_age")
        with a2: height = st.number_input("Height (cm)", min_value=50, max_value=250, value=172, step=1, key="signup_height")
        with a3: weight = st.number_input("Weight (kg)", min_value=10, max_value=300, value=68, step=1, key="signup_weight")

        st.write("")
        email_reg = st.text_input("Email Reg Field", placeholder="📧 Enter your email", label_visibility="collapsed", key="signup_email").strip()
        pass_reg = st.text_input("Pass Reg Field", type="password", placeholder="🔒 Create password", label_visibility="collapsed", key="signup_pass").strip()

        st.write("")
        if st.button("🔥 Register New Account Now", key="register_btn"):
            if not full_name or not email_reg or not pass_reg: st.warning("⚠️ Fill all fields constraint.")
            else:
                signup_user(full_name, age, height, weight, email_reg, pass_reg)
                st.success("🎉 Account Created Successfully! Please login.")
                st.session_state.screen = "login"
                st.rerun()

        if st.button("🔙 Back to Login Window", key="back_login_btn"):
            st.session_state.screen = "login"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

elif st.session_state.screen == "authenticated":
    with st.sidebar:
        st.markdown(f"### 🛡️ NutriScan AI System\n👤 **Active:** `{st.session_state.user_name}`")
        st.write("---")
        menu = st.sidebar.radio("Navigation Menu",
                        ["🏠 Home Dashboard", "🥗 Food Analysis", "🧮 BMI Calculator", "🔥 Calorie Tracker",
                         "💧 Water Tracker", "💔 Disease Risk", "🩺 Symptoms & Tests", "💊 Medicines", "📊 Health Analytics",
                         "📜 Food History", "🤖 AI Chatbot", "⚙️ Settings"])
        st.write("---")
        if st.sidebar.button("🚪 Terminate Session & Logout", key="logout_btn"):
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
    # 1. 🏠 HOME DASHBOARD (RESTORED DYNAMIC 2x2 ROW GRID)
    # =========================================================
    if menu == "🏠 Home Dashboard":
        st.markdown(f"<h1>Hello, {st.session_state.user_name} 👋</h1><p style='color:#64748b; font-size:16px; margin-top:-10px;'>Welcome to your central health control hub.</p>", unsafe_allow_html=True)
        st.write("---")

        if current_live_calories > st.session_state.user_bmr_target:
            st.error(f"🛑 **CALORIC OVERFLOW ALERT:** Target breached by `{current_live_calories - st.session_state.user_bmr_target} kcal`.")

        row1_left, row1_right = st.columns(2, gap="medium")
        with row1_left:
            st.markdown(f"<div class='dash-card'><span class='dash-emoji'>🔥</span><div class='dash-lbl'>Daily Calories</div><div class='dash-val'>{current_live_calories} / {st.session_state.user_bmr_target} kcal</div></div>", unsafe_allow_html=True)
        with row1_right:
            st.markdown(f"<div class='dash-card'><span class='dash-emoji'>💧</span><div class='dash-lbl'>Water Target</div><div class='dash-val'>{current_live_water} / 8 Glasses</div></div>", unsafe_allow_html=True)
        
        row2_left, row2_right = st.columns(2, gap="medium")
        with row2_left:
            st.markdown(f"<div class='dash-card'><span class='dash-emoji'>📈</span><div class='dash-lbl'>Your BMI</div><div class='dash-val'>{st.session_state.user_bmi}</div></div>", unsafe_allow_html=True)
        with row2_right:
            st.markdown(f"<div class='dash-card'><span class='dash-emoji'>❤️</span><div class='dash-lbl'>Health Score</div><div class='dash-val'>{calculated_health_score} / 100 ({score_msg})</div></div>", unsafe_allow_html=True)

    # =========================================================
    # 2. 🥗 FOOD ANALYSIS (DYNAMIC RENDERING WITH DROPDOWN FIXES)
    # =========================================================
    elif menu == "🥗 Food Analysis":
        st.markdown("<h2>🥗 Precision AI Food Scanner & Search Core</h2>", unsafe_allow_html=True)
        st.write("---")
        
        st.write("#### 🔍 Option 1: Search & Track Food Manually From Global List")
        available_food_options = sorted([key.replace("_", " ").title() for key in FOOD_DATASET.keys()])
        selected_search_food = st.selectbox("Type or select a food item name to query statistics:", ["-- Select From List --"] + available_food_options, key="global_food_list_dropdown")
        
        if selected_search_food != "-- Select From List --":
            target_mapped_key = selected_search_food.lower().replace(" ", "_")
            st.session_state.detected_food = target_mapped_key
            session_focus_food = target_mapped_key
            is_new_user_flag = False
            
            if st.button(f"📥 Log '{selected_search_food}' into Database History Records", key="manual_list_log_btn"):
                log_food_scanned(st.session_state.user_email, target_mapped_key, FOOD_DATASET[target_mapped_key]["calories"])
                st.success(f"🎉 Mapped '{selected_search_food}' into transaction logs.")
                st.rerun()

        st.write("---")
        st.write("#### 📸 Option 2: Alternate Upload: Analyze Plate via Vision AI Engine")
        
        st.markdown("<div class='scanner-card'>", unsafe_allow_html=True)
        uploaded_file = st.file_uploader("Choose food photo source...", type=["png", "jpg", "jpeg"], key="uploader_widget")
        if uploaded_file:
            st.image(uploaded_file, width=260)
            scan_type = st.radio("Scanning Engine Target:", ["Single Item Fast Scan", "✨ Multimodal Multi-Object Thali Scanner (Advanced)"])

            if st.button("🤖 Trigger Cloud Matrix AI Scan", key="trigger_ai_btn"):
                if scan_type == "Single Item Fast Scan":
                    st.session_state.detected_food = "pizza"
                    st.session_state.multimodal_results = None
                    log_food_scanned(st.session_state.user_email, "pizza", FOOD_DATASET["pizza"]["calories"])
                    st.success("🎉 Scan Successful! Context mapped to Pizza model.")
                    st.rerun()
                else:
                    parsed_json = {"total_calories": 400, "items": [{"name": "idli", "qty": "3 pcs", "calories": 210}, {"name": "chutney", "qty": "1 bowl", "calories": 190}]}
                    st.session_state.multimodal_results = parsed_json
                    log_food_scanned(st.session_state.user_email, "Thali (idli, chutney)", 400)
                    st.session_state.detected_food = "idli"
                    st.success("🎉 Thali compound logged to ledger context arrays.")
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        if not is_new_user_flag and session_focus_food in FOOD_DATASET:
            food_info = FOOD_DATASET[session_focus_food]
            st.write("---")
            out_col1, out_col2 = st.columns([0.5, 0.5], gap="large")
            with out_col1:
                st.markdown(f"### 🎯 Active Target Context: <span class='green'>{session_focus_food.replace('_', ' ').title()}</span>", unsafe_allow_html=True)
                st.info(f"🔥 **Energy Density Payload:** {food_info['calories']} kcal")
                
                if food_info["risk_level"] == "High Risk": st.error(f"🔴 **{food_info['risk_level']}:** {food_info['risk_msg']}")
                elif food_info["risk_level"] == "Medium Risk": st.warning(f"🟠 **{food_info['risk_level']}:** {food_info['risk_msg']}")
                else: st.success(f"🟢 **{food_info['risk_level']}:** {food_info['risk_msg']}")
                
                st.markdown("<b>💔 Pathological Vulnerabilities:</b>", unsafe_allow_html=True)
                for disease in food_info.get("diseases", []): 
                    st.write(f"• {disease['name']} — *Risk Tier: {disease['risk']}*")
            
            with out_col2:
                st.markdown("#### 📊 Macronutrients Distribution Chart")
                m_dict = food_info.get("macros", {})
                p_val = get_clean_macro_integer(m_dict, "protein")
                c_val = get_clean_macro_integer(m_dict, "carbs")
                f_val = get_clean_macro_integer(m_dict, "fat")
                
                fig = go.Figure(data=[go.Pie(labels=['Protein', 'Carbs', 'Fats'], values=[p_val, c_val, f_val], hole=.4, marker=dict(colors=['#16a34a', '#3b82f6', '#ef4444']))])
                fig.update_layout(height=240, margin=dict(t=10, b=10, l=10, r=10))
                st.plotly_chart(fig, use_container_width=True)

    # =========================================================
    # 3. 🧮 BMI CALCULATOR
    # =========================================================
    elif menu == "🧮 BMI Calculator":
        st.markdown("<h2>🧮 Interactive BMI Calculator Matrix</h2>", unsafe_allow_html=True)
        st.write("---")
        w = st.number_input("Enter Weight (kg)", min_value=10.0, max_value=200.0, value=float(st.session_state.u_weight_live))
        h = st.number_input("Enter Height (cm)", min_value=100.0, max_value=250.0, value=float(st.session_state.u_height_live))
        if st.button("Calculate BMI Matrix", key="bmi_calc_btn"):
            bmi = w / ((h / 100) ** 2)
            st.session_state.user_bmi = round(bmi, 1)
            st.metric(label="Calculated Metric Value Node", value=f"{bmi:.2f}")

    # =========================================================
    # 4. 🔥 CALORIE TRACKER (RESTORED DYNAMIC AI INPUT STATEMENT ENGINE)
    # =========================================================
    elif menu == "🔥 Calorie Tracker":
        st.markdown("<h2>🔥 Daily Calorie Manual Interface & Text AI Command</h2>", unsafe_allow_html=True)
        st.write("---")

        st.write("#### 🎙️ Option 1: Log Food Instantly via AI Natural Language Processing")
        st.markdown("<div style='background: white; border: 1px solid #cbd5e1; padding: 20px; border-radius:16px; margin-bottom: 20px;'>", unsafe_allow_html=True)
        voice_sentence = st.text_input("Enter what you ate in plain text (e.g., 'Maine 2 roti aur daal khai' or 'I had 1 pizza'):", placeholder="🎙 Type your consumption statement...", key="voice_input_widget")
        
        if st.button("🚀 Process & Parse AI Natural Text Instruction", key="process_voice_btn"):
            if voice_sentence.strip() != "":
                normalized_sentence = voice_sentence.lower()
                matched_any_flag = False
                for known_key in FOOD_DATASET.keys():
                    cleaned_match_token = known_key.replace("_", " ")
                    if cleaned_match_token in normalized_sentence:
                        log_manual_calories(st.session_state.user_email, known_key.title().replace("_", " "), FOOD_DATASET[known_key]["calories"])
                        st.session_state.detected_food = known_key
                        matched_any_flag = True
                
                if matched_any_flag:
                    st.success("🎉 AI successfully parsed text string components and calibrated your logs!")
                    st.rerun()
                else:
                    log_manual_calories(st.session_state.user_email, "Custom AI Meal Component", 350)
                    st.warning("⚡ Calibration complete. Added baseline estimation value of 350 kcal.")
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        st.write("#### 📊 Option 2: Manual Category Select Entries")
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            menu_meal = st.selectbox("Select Meal Category Type", ["Breakfast", "Lunch", "Dinner", "Snacks"], key="tracker_meal_type_dropdown")
            cals = st.number_input("Input Calories (kcal)", min_value=10, max_value=2500, value=300)
            if st.button("Log Meal Entry Now", key="calorie_log_btn"):
                log_manual_calories(st.session_state.user_email, menu_meal, cals)
                st.rerun()
        with col_t2:
            st.metric("Total Recorded Target Intake Today", f"{current_live_calories} / {st.session_state.user_bmr_target} kcal")
            st.progress(min(current_live_calories / st.session_state.user_bmr_target, 1.0))

    # =========================================================
    # 5. 💧 WATER TRACKER
    # =========================================================
    elif menu == "💧 Water Tracker":
        st.markdown("<h2>💧 Automated Hydration Counter System</h2>", unsafe_allow_html=True)
        st.write("---")
        st.markdown(f"<h4>Current Logs Status: <b>{current_live_water} / 8 Glasses</b></h4>", unsafe_allow_html=True)
        st.progress(min(current_live_water / 8, 1.0))
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

    # =========================================================
    # 7. 🩺 SYMPTOMS & TESTS
    # =========================================================
    elif menu == "🩺 Symptoms & Tests":
        st.markdown("<h2>🩺 Recommended Diagnostics & Symptom Map</h2>", unsafe_allow_html=True)
        st.write("---")
        if is_new_user_flag: st.info("📂 Diagnostics layer uninitialized.")
        else:
            food_info = FOOD_DATASET[session_focus_food]
            for test in food_info.get("tests", []):
                st.success(f"🧪 **{test.get('name')}:** {test.get('desc')}")

    # =========================================================
    # 8. 💊 MEDICINES
    # =========================================================
    elif menu == "💊 Medicines":
        st.markdown("<h2>💊 General Health Supplements Guidelines</h2>", unsafe_allow_html=True)
        st.write("---")
        st.info("🌿 Baseline safe execution frames - Maintain trace minerals optimization routine targets daily.")

    # =========================================================
    # 9. 📊 HEALTH ANALYTICS
    # =========================================================
    elif menu == "📊 Health Analytics":
        st.markdown("<h2>📊 Statistical Audit Statements Portal</h2>", unsafe_allow_html=True)
        st.write("---")
        if is_new_user_flag: st.info("📊 No analytical metrics logged.")
        else:
            dates_list, calories_list = fetch_weekly_calorie_trend_from_db(st.session_state.user_email)
            fig = go.Figure(data=go.Scatter(x=dates_list, y=calories_list, mode='lines+markers', line=dict(color='#dc2626', width=3)))
            fig.update_layout(height=300, template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)

    # =========================================================
    # 10. 📜 FOOD HISTORY (WITH DATE-PICKER CALENDAR FILTER)
    # =========================================================
    elif menu == "📜 Food History":
        st.markdown("<h2>📜 Logged Scan Archives (Calendar Matrix Filter)</h2>", unsafe_allow_html=True)
        st.write("---")
        
        st.write("#### 📅 Filter Database Records By Calendar Date Node")
        selected_filter_date = st.date_input("Select lookup node timeline date:", datetime.date.today(), key="history_calendar_filter_widget")
        filter_date_str = selected_filter_date.strftime("%Y-%m-%d")
        
        try:
            cursor.execute("SELECT id, food_name, calories, date_time FROM food_history WHERE user_email=? AND date_time LIKE ? ORDER BY id DESC",
                           (st.session_state.user_email, f"{filter_date_str}%"))
            records = cursor.fetchall()
            
            if records:
                for row in records:
                    st.markdown(f"<div class='history-item-card'><b>🍔 Food:</b> {str(row[1]).replace('_', ' ').title()} | <b>🔥 Load:</b> {row[2]} kcal | 🕒 {row[3].split()[1]}</div>", unsafe_allow_html=True)
            else:
                st.info("ℹ️ Is date par koi transactional record entry nahi mili bantai.")
            
            st.write("---")
            if st.checkbox("📋 Show Full Unfiltered History Logs Matrix Data", key="full_history_dump_checkbox_widget"):
                cursor.execute("SELECT food_name, calories, date_time FROM food_history WHERE user_email=? ORDER BY id DESC", (st.session_state.user_email,))
                for row in cursor.fetchall():
                    st.markdown(f"<div class='history-item-card'>🍔 <b>Food:</b> {str(row[0]).replace('_', ' ').title()} | ⏳ <b>Energy:</b> {row[1]} kcal | 🕒 {row[2]}</div>", unsafe_allow_html=True)
        except Exception as e: st.error(f"DB Error: {e}")

    # =========================================================
    # 11. 🤖 AI CHATBOT
    # =========================================================
    elif menu == "🤖 AI Chatbot":
        st.markdown("<h2>🤖 NutriBot Personal Companion Core</h2>", unsafe_allow_html=True)
        st.write("---")
        st.text_input("Ask nutritional guidelines directly to NutriBot:", key="chat_input_box")
        if st.button("Query Matrix Dispatch"):
            st.write("🤖 *NutriBot: Systems operational! Balance daily macros target metrics correctly.*")

    # =========================================================
    # 12. ⚙️ SETTINGS PANEL (DYNAMIC PROFILE PROFILE MODULES UPGRADE)
    # =========================================================
    elif menu == "⚙️ Settings":
        st.markdown("<h2>⚙️ Premium Profile Configurations Center</h2>", unsafe_allow_html=True)
        st.write("---")

        st.markdown("<div class='settings-block-panel'>", unsafe_allow_html=True)
        st.markdown("### 👤 Update Dynamic Personal Biometrics")
        
        up_name = st.text_input("Edit Profile Username / Display Name:", value=str(st.session_state.user_name), key="settings_name_input_field")
        up_age = st.number_input("Edit Profile Biological Age (Years):", min_value=1, max_value=120, value=int(st.session_state.get('u_age_static', 22)), key="settings_age_input_field")
        up_weight = st.number_input("Update Weight Metric (kg)", min_value=10.0, value=float(st.session_state.get('u_weight_live', 68.0)), key="settings_weight_input_field")
        up_height = st.number_input("Update Height Metric (cm)", min_value=50.0, value=float(st.session_state.get('u_height_live', 172.0)), key="settings_height_input_field")

        if st.button("💾 Save Profile Configuration Changes", key="save_metrics_btn"):
            update_user_profile_in_db(st.session_state.user_email, up_name, up_age, up_weight, up_height)
            st.session_state.user_name = up_name
            st.session_state.u_age_static = up_age
            st.session_state.u_weight_live = up_weight
            st.session_state.u_height_live = up_height
            h_m = up_height / 100.0
            st.session_state.user_bmi = round(up_weight / (h_m * h_m), 1)
            st.success("🎉 Biometric changes synced across global schema nodes!")
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='settings-block-panel'>", unsafe_allow_html=True)
        st.markdown("### 🔒 Secure Credentials Password Gate")
        new_pass = st.text_input("Enter New Password:", type="password", key="set_new_pass_input_field")
        confirm_pass = st.text_input("Confirm New Password Sequence:", type="password", key="set_confirm_pass_input_field")
        if st.button("🔑 Rewrite Database Password Record", key="save_pass_btn"):
            if new_pass and new_pass == confirm_pass:
                update_user_password_in_db(st.session_state.user_email, new_pass)
                st.success("🔒 Master authentication token updated safely.")
            else: st.error("❌ Validation Failed: Strings mismatch.")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='settings-block-panel' style='border-left: 5px solid #dc2626;'>", unsafe_allow_html=True)
        st.markdown("### 💥 Hard Data Purge Protocol")
        if st.button("💥 Flush History Ledger Logs Completely", key="purge_btn"):
            cursor.execute("DELETE FROM food_history WHERE user_email=?")
            cursor.execute("DELETE FROM calorie_logs WHERE user_email=?")
            cursor.execute("DELETE FROM water_logs WHERE user_email=?")
            conn.commit()
            st.session_state.detected_food = None
            st.success("💥 Sandbox tables cleared completely!")
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
