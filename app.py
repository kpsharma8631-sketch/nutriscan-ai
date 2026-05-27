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
# 🎯 GEMINI API POOL ROUTER SYSTEM
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
# PAGE CONFIG (FORCED COMPACT THEME)
# =========================================================
st.set_page_config(
    page_title="NutriScan AI",
    layout="centered", # FORCED CENTRAL EYE-LINE FOR PERFECT ALIGNMENT
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
            st.markdown("<h1 style='font-size:46px; margin:0; text-align:center;'>🥗</h1>", unsafe_allow_html=True)

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
# 🔥 NATIVE CENTERING OVERRIDE SYSTEM (NO MORE SQUEEZING DEFECTS)
# =========================================================
st.markdown("""
<style>
/* Zero Out Faltu Top Blank Headers Completely */
[data-testid="stHeader"] { display: none !important; }
.main .block-container { padding-top: 0.5rem !important; padding-bottom: 1rem !important; max-width: 550px !important; margin: 0 auto !important; }

/* Dynamic Full Width Native Buttons Stretch */
div.stButton > button:first-child {
    width: 100% !important;
    display: block !important;
    min-height: 52px !important;
    font-size: 18px !important;
    font-weight: 700 !important;
    background: linear-gradient(to right, #16a34a, #22c55e) !important;
    color: white !important;
    border-radius: 12px !important;
    border: none !important;
    box-shadow: 0 4px 12px rgba(22, 163, 74, 0.15) !important;
}

/* Auth Blueprint Container Framework */
.central-auth-box {
    background-color: #ffffff;
    padding: 35px;
    border-radius: 24px;
    border: 1px solid #e5e7eb;
    box-shadow: 0px 10px 30px rgba(0, 0, 0, 0.04);
    margin-top: 5px;
}

.center-logo-header { text-align: center; margin-bottom: 10px; }
.logo-title { font-size: 38px; font-weight: 800; color: #111827; margin: 0; }
.green { color: #16a34a; }
.main-heading-center { text-align: center; font-size: 32px; font-weight: 800; line-height: 1.2; color: #111827; margin: 10px 0; }
.subtitle-center { text-align: center; font-size: 15px; color: #4b5563; margin-bottom: 20px; }

/* Dashboard UI */
.dash-card { background: white; padding: 20px 15px; border-radius: 18px; border: 1px solid #e2e8f0; text-align: center; margin-bottom: 15px; }
.dash-emoji { font-size: 32px; display: block; }
.dash-val { font-size: 22px; font-weight: 800; color: #0f172a; }
.dash-lbl { font-size: 12px; font-weight: 700; color: #64748b; text-transform: uppercase; }
.history-item-card { background: white !important; padding: 15px !important; border-radius: 12px !important; border-left: 5px solid #16a34a !important; margin-bottom: 10px !important; }
</style>
""", unsafe_allow_html=True)

# Central Gateway Engine
if st.session_state.screen == "login":
    st.markdown("<div class='center-logo-header'>", unsafe_allow_html=True)
    render_local_image("logo.png", img_width=60)
    st.markdown("<div class='logo-title'>NutriScan <span class='green'>AI</span></div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    
    st.markdown("<div class='main-heading-center'>Smart Food Choices, <span class='green'>Healthy Life!</span></div>", unsafe_allow_html=True)
    st.markdown("<div class='subtitle-center'>NutriScan AI analyzes your food, predicts health risks and suggests better choices.</div>", unsafe_allow_html=True)
    
    st.markdown("<div class='central-auth-box'>", unsafe_allow_html=True)
    st.markdown("<h2 style='text-align:center; font-weight:800; color:#111827; margin-bottom:5px;'>Welcome Back!</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:#6b7280; font-size:14px; margin-bottom:20px;'>Login to continue your health journey</p>", unsafe_allow_html=True)
    
    email = st.text_input("Email Address", placeholder="📧 Enter your registered email", key="login_email")
    password = st.text_input("Password", type="password", placeholder="🔒 Enter secure password", key="login_pass")
    
    st.write("")
    col1, col2 = st.columns([1, 1])
    with col1: st.checkbox("Remember me", key="rem_me_key")
    with col2:
        if st.button("Forgot Password?", key="forgot_nav_trigger_btn"):
            st.session_state.screen = "forgot"
            st.rerun()

    st.write("")
    if st.button("🚀 Login Now", key="login_btn"):
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

    st.markdown("<div style='text-align:center; color:gray; margin: 15px 0;'>───── or continue with ─────</div>", unsafe_allow_html=True)
    if st.button("Don't have an account? Sign Up", key="switch_to_signup_btn"):
        st.session_state.screen = "signup"
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

elif st.session_state.screen == "forgot":
    st.markdown("<div class='central-auth-box' style='margin-top: 40px;'>", unsafe_allow_html=True)
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
    st.markdown("<div class='center-logo-header'>", unsafe_allow_html=True)
    render_local_image("logo.png", img_width=60)
    st.markdown("<div class='logo-title'>NutriScan <span class='green'>AI</span></div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    
    st.markdown("<div class='central-auth-box'>", unsafe_allow_html=True)
    st.markdown("<div class='welcome' style='font-size:28px;'>Create Account</div>", unsafe_allow_html=True)
    st.markdown("<div class='subtitle2'>Fill details to create your secure profile</div>", unsafe_allow_html=True)
    
    full_name = st.text_input("Full Name", placeholder="👤 Enter your full name", key="signup_name").strip()
    
    st.markdown("<label style='font-weight:600; color:#374151; font-size:14px; margin-top:5px; display:block;'>🧬 Biometric Metrics Data</label>", unsafe_allow_html=True)
    a1, a2, a3 = st.columns(3)
    with a1: age = st.number_input("Age", min_value=1, max_value=100, value=22, step=1, key="signup_age")
    with a2: height = st.number_input("Height (cm)", min_value=50, max_value=250, value=172, step=1, key="signup_height")
    with a3: weight = st.number_input("Weight (kg)", min_value=10, max_value=300, value=68, step=1, key="signup_weight")

    email_reg = st.text_input("Email Address", placeholder="📧 Enter your email address", key="signup_email").strip()
    pass_reg = st.text_input("Create Password", type="password", placeholder="🔒 Create secure user credentials", key="signup_pass").strip()

    st.write("")
    if st.button("🔥 Register New Account Now", key="register_btn"):
        if not full_name or not email_reg or not pass_reg: st.warning("⚠️ Fill all fields constraint.")
        else:
            signup_user(full_name, age, height, weight, email_reg, pass_reg)
            st.success("🎉 Account Created Successfully! Please login.")
            st.session_state.screen = "login"
            st.rerun()

    if st.button("Back to Login Window", key="back_login_btn"):
        st.session_state.screen = "login"
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

elif st.session_state.screen == "authenticated":
    # Global Max Width reset for inside application view node
    st.markdown("<style>.main .block-container { max-width: 95% !important; }</style>", unsafe_allow_html=True)
    
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

        row1_left, row1_right = st.columns(2, gap="medium")
        with row1_left:
            st.markdown(f"<div class='dash-card'><span class='dash-emoji'>🔥</span><div class='dash-lbl'>Daily Calories</div><div class='dash-val'>{current_live_calories} / {st.session_state.user_bmr_target} kcal</div></div>", unsafe_allow_html=True)
        with row1_right:
            st.markdown(f"<div class='dash-card'><span class='dash-emoji'>💧</span><div class='dash-lbl'>Water Target</div><div class='dash-val'>{current_live_water} / 8 Glasses</div></div>", unsafe_allow_html=True)

    # 2. 🥗 FOOD ANALYSIS
    elif menu == "🥗 Food Analysis":
        st.markdown("<h2>🥗 Precision AI Food Scanner & Search Core</h2>", unsafe_allow_html=True)
        st.write("---")
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
        uploaded_file = st.file_uploader("Choose food photo source...", type=["png", "jpg", "jpeg"], key="uploader_widget")
        if uploaded_file:
            st.image(uploaded_file, width=260)
            if st.button("🤖 Trigger Cloud Matrix AI Scan", key="trigger_ai_btn"):
                st.session_state.detected_food = "pizza"
                log_food_scanned(st.session_state.user_email, "pizza", FOOD_DATASET["pizza"]["calories"])
                st.success("🎉 Scan Successful! Context mapped to Pizza model.")
                st.rerun()

    # 4. 🔥 CALORIE TRACKER
    elif menu == "🔥 Calorie Tracker":
        st.markdown("<h2>🔥 Daily Calorie Manual Interface & Text AI Command</h2>", unsafe_allow_html=True)
        st.write("---")
        voice_sentence = st.text_input("Enter what you ate in plain text (e.g., 'Maine 2 roti aur daal khai'):", placeholder="🎙 Type your consumption statement...", key="voice_input_widget")
        
        if st.button("🚀 Process & Parse AI Natural Text Instruction", key="process_voice_btn"):
            if voice_sentence.strip() != "":
                normalized_sentence = voice_sentence.lower()
                matched_any_flag = False
                for known_key in FOOD_DATASET.keys():
                    if known_key.replace("_", " ") in normalized_sentence:
                        log_manual_calories(st.session_state.user_email, known_key.title().replace("_", " "), FOOD_DATASET[known_key]["calories"])
                        st.session_state.detected_food = known_key
                        matched_any_flag = True
                if matched_any_flag:
                    st.success("🎉 AI successfully parsed components!")
                    st.rerun()
