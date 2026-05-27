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
                "<div style='background:#f0fdf4; height:200px; border-radius:18px; display:flex; align-items:center; justify-content:center; color:#16a34a;'><b>[ NutriScan AI Graphic Asset ]</b></div>",
                unsafe_allow_html=True)

# =========================================================
# DATASET KEY-MAPPER
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
# 🔥 SOLID NATIVE STREAMLIT BUTTON STRETCH & PADDING FIX
# =========================================================
st.markdown("""
<style>
.stApp { background-color: #f8fafc; }
footer { display: none !important; }
[data-testid="stSidebarNav"], [data-testid="stSidebarNavItems"] { display: none !important; height: 0px !important; overflow: hidden !important; }
[data-testid="stSidebarCollapseButton"] { display: flex !important; visibility: visible !important; color: #16a34a !important; background-color: #f0fdf4 !important; border-radius: 50% !important; }

/* 🚨 Brutal Top Blank Padding Header Fix */
[data-testid="stHeader"] { display: none !important; }
.main .block-container { padding-top: 1rem !important; padding-bottom: 1rem !important; }

/* 🚨 100% Wide Button Force Engine */
div.stButton > button {
    background: linear-gradient(to right, #15803d, #22c55e) !important;
    color: white !important;
    border-radius: 12px !important;
    border: none !important;
    font-weight: 700 !important;
    height: 52px !important;
    width: 100% !important;
    display: block !important;
    box-shadow: 0px 4px 12px rgba(22, 163, 74, 0.15) !important;
}

div.stButton > button[key*="switch"], div.stButton > button[key*="back"], div.stButton > button[key*="logout"], div.stButton > button[key*="forgot_nav"] {
    background: #f0fdf4 !important;
    color: #16a34a !important;
    border: 1px solid #bbf7d0 !important;
}

.logo-text { font-size: 45px; font-weight: 800; color: #111827; margin-top: 5px; }
.green { color: #16a34a; }
.main-heading { font-size: 55px; font-weight: 800; line-height: 1.1; margin-top: 15px; color: #111827; }
.subtitle { font-size: 18px; color: #4b5563; margin-top: 15px; line-height: 1.6; }
.feature-card { background: #f0fdf4; padding: 15px; border-radius: 14px; text-align: center; box-shadow: 0px 4px 12px rgba(0,0,0,0.02); }
.login-container { background: white; padding: 35px 40px !important; border-radius: 24px; box-shadow: 0px 10px 30px rgba(0,0,0,0.04); border: 1px solid #f1f5f9; }
.signup-container-card { background: white; padding: 40px !important; border-radius: 28px; box-shadow: 0px 15px 35px rgba(0,0,0,0.05); border: 1px solid #e2e8f0; }
.welcome { text-align: center; font-size: 38px; font-weight: 800; color: #111827; }
.subtitle2 { text-align: center; color: #6b7280; font-size: 15px; margin-bottom: 20px; }
.avatar-wrapper { display: flex; justify-content: center; margin-bottom: 20px; }
.avatar-img { width: 90px; height: 90px; }
.dash-card { background: white; padding: 25px 20px; border-radius: 24px; border: 1px solid #e2e8f0; text-align: center; }
.dash-emoji { font-size: 40px; margin-bottom: 12px; display: block; }
.dash-val { font-size: 24px; font-weight: 800; color: #0f172a; margin-top: 6px; }
.dash-lbl { font-size: 13px; font-weight: 700; color: #64748b; text-transform: uppercase; }
.history-item-card { background: white !important; padding: 18px 24px !important; border-radius: 16px !important; border-left: 5px solid #16a34a !important; margin-bottom: 12px !important; }
.premium-secure-grid-row { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 15px; margin-top: 40px; padding-top: 20px; border-top: 1px solid #e2e8f0; }
.secure-grid-card-node { flex: 1; min-width: 200px; background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 15px; }
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
        with text_col: st.markdown("<div class='logo-text'>NutriScan <span class='green'>AI</span></div>", unsafe_allow_html=True)
        st.markdown("<div class='main-heading'>Smart Food Choices,<br><span class='green'>Healthy Life!</span></div>", unsafe_allow_html=True)
        st.markdown("<div class='subtitle'>NutriScan AI analyzes your food, predicts health risks and suggests better choices.</div>", unsafe_allow_html=True)
        st.write("")
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown("<div class='feature-card'>🧠<br><b>AI Food Analysis</b></div>", unsafe_allow_html=True)
        c2.markdown("<div class='feature-card'>❤️<br><b>Disease Prediction</b></div>", unsafe_allow_html=True)
        c3.markdown("<div class='feature-card'>📋<br><b>Personalized Recs</b></div>", unsafe_allow_html=True)
        c4.markdown("<div class='feature-card'>📈<br><b>Health Tracking</b></div>", unsafe_allow_html=True)
        st.write("")
        render_local_image("hero.png", use_column=True)

    with right:
        st.markdown("<div class='login-container'>", unsafe_allow_html=True)
        st.markdown("<div class='welcome'>Welcome Back!</div>", unsafe_allow_html=True)
        st.markdown("<div class='subtitle2'>Login to continue your health journey</div>", unsafe_allow_html=True)
        st.markdown("<div class='avatar-wrapper'><img class='avatar-img' src='https://cdn-icons-png.flaticon.com/512/3135/3135715.png'></div>", unsafe_allow_html=True)

        # 🚨 FIX DETECTED: Removed crash argument "display_text" from inputs
        email = st.text_input("Email", placeholder="Enter your registered email", label_visibility="visible", key="login_email").strip()
        password = st.text_input("Password", type="password", placeholder="Enter your password", label_visibility="visible", key="login_pass").strip()

        st.write("")
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
                else: st.error("❌ Invalid Email or Password. Please try again.")

        st.markdown("<div style='text-align:center; color:gray; margin-top:12px; margin-bottom:5px;'>───── or continue with ─────</div>", unsafe_allow_html=True)
        if st.button("Don't have an account? Sign Up", key="switch_to_signup_btn"):
            st.session_state.screen = "signup"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("""
    <div class="premium-secure-grid-row">
        <div class="secure-grid-card-node"><strong>🛡️ Secure & Private</strong><p>Your biological metrics log data is 100% safe.</p></div>
        <div class="secure-grid-card-node"><strong>🧠 AI Powered</strong><p>Smart cloud vector analysis and clinical diagnostics predictions.</p></div>
        <div class="secure-grid-card-node"><strong>🌱 Healthy Lifestyle</strong><p>Better selective data choices for longevity.</p></div>
        <div class="secure-grid-card-node"><strong>⏱️ Track & Improve</strong><p>Monitor real calories distribution volume daily.</p></div>
    </div>
    """, unsafe_allow_html=True)

elif st.session_state.screen == "forgot":
    st.markdown("<div style='max-width:550px; margin: 80px auto;' class='login-container'>", unsafe_allow_html=True)
    st.markdown("<h2 style='text-align:center; font-weight:800; color:#111827;'>🔒 Account Recovery Terminal</h2>", unsafe_allow_html=True)
    st.write("---")
    recover_target = st.text_input("Enter your registered email address:", placeholder="📧 e.g., keshav@example.com")
    st.write("")

    col_b1, col_b2 = st.columns(2)
    with col_b1:
        if st.button("🔍 Recover Password Key", key="execute_recovery_btn"):
            if not recover_target.strip(): st.warning("⚠️ Please provide a valid email query.")
            else:
                found_pass = recover_user_password(recover_target.strip())
                if found_pass: st.success(f"🎉 **Decrypted Key Sequence:** `{found_pass}`")
                else: st.error("❌ Token not found.")
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
        with text_col_s: st.markdown("<div class='logo-text' style='font-size:38px;'>NutriScan <span class='green'>AI</span></div>", unsafe_allow_html=True)
        st.markdown("<div class='main-heading' style='font-size:48px;'>Join Us For A<br><span class='green'>Healthy Journey!</span></div>", unsafe_allow_html=True)
        st.write("")
        render_local_image("hero.png", use_column=True)

    with right:
        st.markdown("<div class='signup-container-card'>", unsafe_allow_html=True)
        st.markdown("<h2 style='text-align:center; font-weight:800; color:#111827;'>Create Account</h2>", unsafe_allow_html=True)

        full_name = st.text_input("Full Name", placeholder="👤 Enter your full name", key="signup_name").strip()
        st.write("")
        st.markdown("<label style='font-weight:600; color:#374151; font-size:14px;'>🧬 Biometric Metrics Data</label>", unsafe_allow_html=True)
        a1, a2, a3 = st.columns(3)
        with a1: age = st.number_input("Age", min_value=1, max_value=100, value=22, step=1, key="signup_age")
        with a2: height = st.number_input("Height (cm)", min_value=50, max_value=250, value=172, step=1, key="signup_height")
        with a3: weight = st.number_input("Weight (kg)", min_value=10, max_value=300, value=68, step=1, key="signup_weight")

        st.write("")
        email_reg = st.text_input("Email Address", placeholder="📧 Enter your email", key="signup_email").strip()
        pass_reg = st.text_input("Create Password", type="password", placeholder="🔒 Create password", key="signup_pass").strip()

        st.write("")
        if st.button("🔥 Register New Account Now", key="register_btn"):
            if not full_name or not email_reg or not pass_reg: st.warning("⚠️ Access Denied: Fill constraints.")
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
        st.markdown(f"### 🛡️ NutriScan AI System\n👤 **User Active:** `{st.session_state.user_name}`")
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

    # 1. 🏠 HOME DASHBOARD
    if menu == "🏠 Home Dashboard":
        st.markdown(f"<h1>Hello, {st.session_state.user_name} 👋</h1><p style='color:#64748b; font-size:16px; margin-top:-10px;'>Welcome to your central health control hub.</p>", unsafe_allow_html=True)
        st.write("---")

        r1_c1, r1_c2 = st.columns(2, gap="large")
        with r1_c1: st.markdown(f"<div class='dash-card'><span class='dash-emoji'>🔥</span><div class='dash-lbl'>Daily Calories</div><div class='dash-val'>{current_live_calories} / {st.session_state.user_bmr_target} kcal</div></div>", unsafe_allow_html=True)
        with r1_c2: st.markdown(f"<div class='dash-card'><span class='dash-emoji'>💧</span><div class='dash-lbl'>Water Target</div><div class='dash-val'>{current_live_water} / 8 Glasses</div></div>", unsafe_allow_html=True)

    # 2. 🥗 FOOD ANALYSIS
    elif menu == "🥗 Food Analysis":
        st.markdown("<h2>🥗 Precision AI Food Scanner & Search</h2>", unsafe_allow_html=True)
        st.write("---")
        available_food_options = sorted([key.replace("_", " ").title() for key in FOOD_DATASET.keys()])
        selected_search_food = st.selectbox("Select food manually:", ["-- Select From List --"] + available_food_options)
        
        if selected_search_food != "-- Select From List --":
            target_mapped_key = selected_search_food.lower().replace(" ", "_")
            st.session_state.detected_food = target_mapped_key
            if st.button(f"📥 Log entry", key="manual_list_log_btn"):
                log_food_scanned(st.session_state.user_email, target_mapped_key, FOOD_DATASET[target_mapped_key]["calories"])
                st.rerun()

    # 4. 🔥 CALORIE TRACKER
    elif menu == "🔥 Calorie Tracker":
        st.markdown("<h2>🔥 Daily Calorie Log Interface</h2>", unsafe_allow_html=True)
        voice_sentence = st.text_input("Enter plain text statement:", placeholder="Type what you ate...", key="voice_input_widget")
        if st.button("🚀 Process text context", key="process_voice_btn"):
            if voice_sentence.strip() != "":
                normalized_sentence = voice_sentence.lower()
                for known_key in FOOD_DATASET.keys():
                    if known_key.replace("_", " ") in normalized_sentence:
                        log_manual_calories(st.session_state.user_email, known_key.title().replace("_", " "), FOOD_DATASET[known_key]["calories"])
                st.rerun()
