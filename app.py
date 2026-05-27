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
    valid_keys = [k for k in GEMINI_KEYS_POOL if k.strip()]
    if not valid_keys: return None
    for idx, key in enumerate(valid_keys):
        try:
            st.session_state[f"key_status_{idx}"] = "Active"
            return genai.Client(api_key=key)
        except:
            st.session_state[f"key_status_{idx}"] = "Exhausted"
    return None

# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(page_title="NutriScan AI", layout="wide", initial_sidebar_state="expanded")

# =========================================================
# DATABASE SETUP
# =========================================================
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, age INTEGER, height REAL, weight REAL, email TEXT, password TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS food_history (id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT, food_name TEXT, calories INTEGER, date_time TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS calorie_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT, meal_type TEXT, calories INTEGER, log_date TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS water_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT, glasses INTEGER, log_date TEXT)")
conn.commit()

# =========================================================
# DATABASE OPERATIONS
# =========================================================
def signup_user(name, age, height, weight, email, password):
    cursor.execute("INSERT INTO users (name, age, height, weight, email, password) VALUES (?, ?, ?, ?, ?, ?)", (name, age, height, weight, email, password))
    conn.commit()

def login_user(email, password):
    cursor.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password))
    return cursor.fetchone()

def recover_user_password(email):
    cursor.execute("SELECT password FROM users WHERE email=?", (email,))
    res = cursor.fetchone()
    return res[0] if res else None

def update_user_metrics_in_db(email, new_weight, new_height):
    cursor.execute("UPDATE users SET weight=?, height=? WHERE email=?", (float(new_weight), float(new_height), str(email)))
    conn.commit()

def log_food_scanned(email, food_name, calories):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO food_history (user_email, food_name, calories, date_time) VALUES (?, ?, ?, ?)", (str(email), str(food_name), int(calories), str(now)))
    conn.commit()

def log_manual_calories(email, meal_type, calories):
    today = datetime.date.today().strftime("%Y-%m-%d")
    cursor.execute("INSERT INTO calorie_logs (user_email, meal_type, calories, log_date) VALUES (?, ?, ?, ?)", (str(email), str(meal_type), int(calories), str(today)))
    conn.commit()

def get_daily_total_calories(email):
    today = datetime.date.today().strftime("%Y-%m-%d")
    cursor.execute("SELECT SUM(calories) FROM calorie_logs WHERE user_email=? AND log_date=?", (email, today))
    res1 = cursor.fetchone()[0] or 0
    cursor.execute("SELECT SUM(calories) FROM food_history WHERE user_email=? AND date_time LIKE ?", (email, f"{today}%"))
    res2 = cursor.fetchone()[0] or 0
    return res1 + res2

def get_last_scanned_food_from_db(email):
    try:
        cursor.execute("SELECT food_name, calories FROM food_history WHERE user_email=? ORDER BY id DESC LIMIT 1", (email,))
        res = cursor.fetchone()
        if res: return str(res[0]), int(res[1])
    except: pass
    return None, 0

def fetch_weekly_calorie_trend_from_db(email):
    trend_data = {}
    today = datetime.date.today()
    for i in range(6, -1, -1):
        d_str = (today - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        trend_data[d_str] = 0
    cursor.execute("SELECT log_date, SUM(calories) FROM calorie_logs WHERE user_email=? GROUP BY log_date", (email,))
    for row in cursor.fetchall():
        if row[0] in trend_data: trend_data[row[0]] += int(row[1])
    cursor.execute("SELECT SUBSTR(date_time, 1, 10), SUM(calories) FROM food_history WHERE user_email=? GROUP BY SUBSTR(date_time, 1, 10)", (email,))
    for row in cursor.fetchall():
        if row[0] in trend_data: trend_data[row[0]] += int(row[1])
    return list(trend_data.keys()), list(trend_data.values())

def get_daily_water_glasses(email):
    today = datetime.date.today().strftime("%Y-%m-%d")
    cursor.execute("SELECT glasses FROM water_logs WHERE user_email=? AND log_date=?", (email, today))
    res = cursor.fetchone()
    return int(res[0]) if res else 0

def update_daily_water_glasses(email, delta_val):
    today = datetime.date.today().strftime("%Y-%m-%d")
    current = get_daily_water_glasses(email)
    new_glasses = max(0, current + delta_val)
    cursor.execute("SELECT id FROM water_logs WHERE user_email=? AND log_date=?", (email, today))
    exists = cursor.fetchone()
    if exists: cursor.execute("UPDATE water_logs SET glasses=? WHERE user_email=? AND log_date=?", (new_glasses, email, today))
    else: cursor.execute("INSERT INTO water_logs (user_email, glasses, log_date) VALUES (?, ?, ?)", (email, new_glasses, today))
    conn.commit()
    return new_glasses

# =========================================================
# SESSION STATE & HELPERS
# =========================================================
if "screen" not in st.session_state: st.session_state.screen = "login"
if "user_name" not in st.session_state: st.session_state.user_name = "User"
if "user_email" not in st.session_state: st.session_state.user_email = ""
if "detected_food" not in st.session_state: st.session_state.detected_food = None
if "multimodal_results" not in st.session_state: st.session_state.multimodal_results = None
if "user_bmi" not in st.session_state: st.session_state.user_bmi = 22.0
if "user_bmr_target" not in st.session_state: st.session_state.user_bmr_target = 2000
if "chat_history" not in st.session_state: st.session_state.chat_history = []

def render_local_image(image_name, img_width=None, use_column=False):
    if os.path.exists(image_name):
        if use_column: st.image(image_name, use_container_width=True)
        else: st.image(image_name, width=img_width)
    else:
        if "logo" in image_name: st.markdown("<h1 style='font-size:50px; margin:0;'>🥗</h1>", unsafe_allow_html=True)

def find_best_matching_db_key(input_food_string):
    clean_target = str(input_food_string).lower().strip()
    for db_key in FOOD_DATASET.keys():
        clean_db_key = db_key.replace("_", " ")
        if clean_db_key in clean_target or clean_target in clean_db_key: return db_key
    return None

# =========================================================
# 🔥 ULTIMATE COMBINED MASTER PRECISE CSS THEME
# =========================================================
st.markdown("""
<style>
/* CSS Reset and Structural Spacing */
header { visibility: hidden !important; display: none !important; }
[data-testid="stHeader"], [data-testid="stToolbar"] { display: none !important; }
.stApp { background-color: #f8fafc; }
footer { display: none !important; }

/* 🚨 4. PAGE WIDTH FIX */
.block-container {
    max-width: 1450px !important;
    padding-top: 1rem !important;
    padding-bottom: 1rem !important;
}

/* 🚨 2. BUTTON & UI PREMIUM STYLING */
div.stButton > button {
    border-radius: 14px !important;
    height: 52px !important;
    font-size: 18px !important;
    font-weight: 700 !important;
    background: linear-gradient(to right, #15803d, #22c55e) !important;
    color: white !important;
    width: 100% !important;
    display: block !important;
    border: none !important;
    box-shadow: 0px 4px 15px rgba(22, 163, 74, 0.2) !important;
}
div.stButton > button:hover { transform: translateY(-3px) !important; box-shadow: 0px 6px 20px rgba(22,163,74,0.3) !important; }

/* 🚨 DESIGNED FORGOT PASSWORD TEXT LINK STYLE */
div.stButton > button[key*="forgot_nav"] {
    background: transparent !important;
    color: #6b7280 !important;
    border: none !important;
    box-shadow: none !important;
    font-weight: 500 !important;
    font-size: 14px !important;
}

/* 🚨 PREMIUM GLASSMORPHISM LOGIN CONTAINER */
.login-container {
    background: rgba(255,255,255,0.88);
    backdrop-filter: blur(14px);
    padding: 35px !important;
    border-radius: 28px;
    box-shadow: 0px 10px 40px rgba(0,0,0,0.06);
    border: 1px solid #e5e7eb;
    margin-top: 10px;
    width: 100%;
    max-width: 500px;
    margin: auto;
}

.signup-container-card {
    background: rgba(255,255,255,0.88);
    backdrop-filter: blur(14px);
    padding: 35px !important;
    border-radius: 28px;
    box-shadow: 0px 10px 40px rgba(0,0,0,0.06);
    border: 1px solid #e5e7eb;
    margin-top: 10px;
    width: 100%;
    max-width: 500px;
    margin: auto;
}

/* Typography & Visuals */
.logo-text { font-size: 58px; font-weight: 800; color: #111827; }
.green { color: #16a34a; }
.main-heading { font-size: 68px; font-weight: 800; line-height: 1.1; color: #111827; margin-top: 20px; }
.subtitle { font-size: 24px; color: #4b5563; line-height: 1.6; margin-top: 18px; }
.feature-card { background: #f4f8f2; padding: 22px; border-radius: 22px; text-align: center; box-shadow: 0px 4px 15px rgba(0,0,0,0.04); transition: 0.3s; }
.feature-card:hover { transform: translateY(-5px); }
.welcome { text-align: center; font-size: 38px; font-weight: 800; color: #111827; }
.subtitle2 { text-align: center; color: #6b7280; font-size: 15px; margin-bottom: 20px; }
.avatar-img { width: 95px; height: 95px; }
.history-item-card { background: white !important; padding: 18px 24px !important; border-radius: 16px !important; border-left: 5px solid #16a34a !important; }
</style>
""", unsafe_allow_html=True)

# Central Gateway Engine
if st.session_state.screen == "login":
    left, right = st.columns([1.25, 0.75], gap="small")
    with left:
        # 🚨 1. LOGO POSITIONED
        st.markdown("<div style='margin-top:60px;'></div>", unsafe_allow_html=True)
        logo_col, text_col = st.columns([0.15, 0.85])
        with logo_col: render_local_image("logo.png", img_width=75)
        with text_col: st.markdown("<div class='logo-text'>NutriScan <span class='green'>AI</span></div>", unsafe_allow_html=True)
        
        st.markdown("<div class='main-heading'>Smart Food Choices,<br><span class='green'>Healthy Life!</span></div>", unsafe_allow_html=True)
        st.markdown("<div class='subtitle'>NutriScan AI analyzes your food, predicts health risks and suggests better choices.</div>", unsafe_allow_html=True)
        
        # 🚨 3. FEATURE BOXES SHIFTED LEFT
        st.markdown("<div style='margin-top:30px; margin-left:-20px;'>", unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown("<div class='feature-card'>🧠<br><b>AI Analysis</b></div>", unsafe_allow_html=True)
        c2.markdown("<div class='feature-card'>❤️<br><b>Disease Risk</b></div>", unsafe_allow_html=True)
        c3.markdown("<div class='feature-card'>📋<br><b>Health Recs</b></div>", unsafe_allow_html=True)
        c4.markdown("<div class='feature-card'>📈<br><b>Tracking</b></div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        
        # 🚨 3. HERO IMAGE FLOATING
        st.markdown("<div style='margin-left:-40px; margin-top:-20px;'>", unsafe_allow_html=True)
        render_local_image("hero.png", img_width=760)
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown("<div class='login-container'>", unsafe_allow_html=True)
        st.markdown("<div class='welcome'>Welcome Back!</div>", unsafe_allow_html=True)
        st.markdown("<div class='subtitle2'>Login to continue your journey</div>", unsafe_allow_html=True)
        st.markdown("<div class='avatar-wrapper'><img class='avatar-img' src='https://cdn-icons-png.flaticon.com/512/3135/3135715.png'></div>", unsafe_allow_html=True)

        email = st.text_input("Email", placeholder="📧 Enter your email", label_visibility="collapsed", key="login_email").strip()
        password = st.text_input("Password", type="password", placeholder="🔒 Enter your password", label_visibility="collapsed", key="login_pass").strip()

        if st.button("Forgot Password?", key="forgot_nav_trigger_btn", use_container_width=True):
            st.session_state.screen = "forgot"
            st.rerun()

        if st.button("🚀 Login", key="login_btn", use_container_width=True):
            user = login_user(email, password)
            if user:
                st.session_state.user_name = user[1]
                st.session_state.user_email = str(email)
                st.session_state.screen = "authenticated"
                st.rerun()
            else: st.error("❌ Invalid Credentials")

        if st.button("Don't have an account? Sign Up", key="switch_to_signup_btn", use_container_width=True):
            st.session_state.screen = "signup"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

elif st.session_state.screen == "authenticated":
    # ... Rest of Dashboard logic remains identical ...
    st.write("Dashboard Active")
