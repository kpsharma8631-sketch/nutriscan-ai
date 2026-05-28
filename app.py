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

# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="NutriScan AI",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================================================
# DATABASE SETUP (EMBEDDED)
# =========================================================
FOOD_DATASET = {
    "pizza": {"calories": 285, "risk_level": "High Risk", "risk_msg": "High saturated fats. Limit intake.", "macros": {"Protein": 12, "Carbs": 36, "Fats": 10}, "diseases": [{"name": "Obesity", "risk": "High"}, {"name": "Heart Disease", "risk": "Medium"}], "tests": [{"name": "Lipid Profile", "desc": "Check LDL/HDL levels"}]},
    "burger": {"calories": 350, "risk_level": "High Risk", "risk_msg": "Processed meats & high sodium.", "macros": {"Protein": 20, "Carbs": 30, "Fats": 15}, "diseases": [{"name": "Hypertension", "risk": "High"}, {"name": "Diabetes", "risk": "Medium"}], "tests": [{"name": "Blood Sugar", "desc": "Fasting glucose"}]},
    "idli": {"calories": 150, "risk_level": "Low Risk", "risk_msg": "Low calorie, fermented, good for gut.", "macros": {"Protein": 5, "Carbs": 30, "Fats": 1}, "diseases": [], "tests": []},
    "dosa": {"calories": 220, "risk_level": "Low Risk", "risk_msg": "Rice-based, better than deep fried.", "macros": {"Protein": 6, "Carbs": 35, "Fats": 6}, "diseases": [], "tests": []},
    "samosa": {"calories": 260, "risk_level": "High Risk", "risk_msg": "Deep fried refined flour.", "macros": {"Protein": 5, "Carbs": 30, "Fats": 14}, "diseases": [{"name": "Diabetes", "risk": "Medium"}, {"name": "Heart Disease", "risk": "Medium"}], "tests": [{"name": "ECG", "desc": "Heart rhythm check"}]},
    "thali": {"calories": 600, "risk_level": "Medium Risk", "risk_msg": "Balanced but heavy portion.", "macros": {"Protein": 20, "Carbs": 80, "Fats": 20}, "diseases": [{"name": "Obesity", "risk": "Low"}], "tests": []},
    "salad": {"calories": 50, "risk_level": "Low Risk", "risk_msg": "Healthy choice.", "macros": {"Protein": 2, "Carbs": 10, "Fats": 0}, "diseases": [], "tests": []},
    "dal_chawal": {"calories": 350, "risk_level": "Low Risk", "risk_msg": "Good protein source.", "macros": {"Protein": 15, "Carbs": 50, "Fats": 8}, "diseases": [], "tests": []},
    "paneer": {"calories": 320, "risk_level": "Medium Risk", "risk_msg": "High protein but heavy fat.", "macros": {"Protein": 25, "Carbs": 5, "Fats": 25}, "diseases": [], "tests": []},
    "biryani": {"calories": 450, "risk_level": "Medium Risk", "risk_msg": "Spicy & oily.", "macros": {"Protein": 15, "Carbs": 60, "Fats": 18}, "diseases": [{"name": "Acidity", "risk": "Medium"}], "tests": []}
}

# =========================================================
# GOOGLE GENAI CLIENT
# =========================================================
def get_gemini_client():
    try:
        # Try to get key from Streamlit Secrets (Recommended for GitHub)
        api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            st.error("API Key not found! Please set GEMINI_API_KEY in .streamlit/secrets.toml or environment variables.")
            return None
        return genai.Client(api_key=api_key)
    except Exception as e:
        st.error(f"Client Error: {e}")
        return None

# =========================================================
# DATABASE CONNECTIONS
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
# DB FUNCTIONS
# =========================================================
def signup_user(name, age, height, weight, email, password):
    cursor.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?)", (name, age, height, weight, email, password))
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

def update_user_password_in_db(email, new_password):
    cursor.execute("UPDATE users SET password=? WHERE email=?", (str(new_password), str(email)))
    conn.commit()

def log_food_scanned(email, food_name, calories):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO food_history (user_email, food_name, calories, date_time) VALUES (?,?,?,?)",
                   (str(email), str(food_name), int(calories), str(now)))
    conn.commit()

def log_manual_calories(email, meal_type, calories):
    today = datetime.date.today().strftime("%Y-%m-%d")
    cursor.execute("INSERT INTO calorie_logs (user_email, meal_type, calories, log_date) VALUES (?,?,?,?)",
                   (str(email), str(meal_type), int(calories), str(today)))
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
        cursor.execute("INSERT INTO water_logs (user_email, glasses, log_date) VALUES (?, ?, ?)", (email, new_glasses, today))
    conn.commit()
    return new_glasses

# =========================================================
# SESSION STATE
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
# HELPER FUNCTIONS
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
    for db_key in FOOD_DATASET.keys():
        clean_db_key = db_key.replace("_", " ")
        if clean_db_key in clean_target or clean_target in clean_db_key:
            return db_key
    return None

# =========================================================
# CSS STYLES
# =========================================================
st.markdown("""
<style>
.stApp { background-color: #f8fafc; }
footer { display: none !important; }
[data-testid="stSidebarCollapseButton"] { display: flex !important; color: #16a34a !important; }
div.stButton > button {
    background: linear-gradient(to right, #15803d, #22c55e) !important;
    color: white !important; border-radius: 12px !important; border: none !important;
    font-weight: 700 ! important; height: 50px !important; width: 100% !important;
}
div.stButton > button:hover { transform: translateY(-1px) !important; }
.login-container { background: white; padding: 35px; border-radius: 24px; box-shadow: 0px 10px 30px rgba(0,0,0,0.05); margin-top: 10px; border: 1px solid #f1f5f9; }
.logo-text { font-size: 45px; font-weight: 800; color: #111827; }
.green { color: #16a34a; }
.main-heading { font-size: 60px; font-weight: 800; line-height: 1.1; margin-top: 15px; color: #111827; }
.feature-card { background: #f0fdf4; padding: 20px; border-radius: 18px; text-align: center; box-shadow: 0px 4px 12px rgba(0,0,0,0.03); }
.dash-card { background: white; padding: 25px; border-radius: 24px; border: 1px solid #e2e8f0; box-shadow: 0px 10px 25px rgba(0,0,0,0.02); text-align: center; }
.dash-emoji { font-size: 40px; margin-bottom: 12px; }
.dash-val { font-size: 24px; font-weight: 800; color: #0f172a; margin-top: 6px; }
.dash-lbl { font-size: 13px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.8px; }
.history-item-card { background: white !important; padding: 18px 24px !important; border-radius: 16px !important; border-left: 5px solid #16a34a !important; box-shadow: 0px 4px 12px rgba(0,0,0,0.02) !important; margin-bottom: 12px !important; }
.scanner-card { background: white; border: 1px solid #e2e8f0; padding: 25px; border-radius: 24px; box-shadow: 0px 4px 20px rgba(0,0,0,0.02); }
.settings-block-panel { background: white; border: 1px solid #e2e8f0; padding: 30px; border-radius: 24px; box-shadow: 0px 4px 18px rgba(0,0,0,0.01); margin-bottom: 25px; }
.chat-bubble-user { background-color: #e2e8f0; padding: 12px 16px; border-radius: 16px 16px 0px 16px; margin-bottom: 10px; text-align: right; }
.chat-bubble-bot { background-color: #f0fdf4; padding: 12px 16px; border-radius: 16px 16px 16px 0px; margin-bottom: 10px; border: 1px solid #bbf7d0; }
</style>
""", unsafe_allow_html=True)

# =========================================================
# MAIN LOGIC
# =========================================================
if st.session_state.screen == "login":
    left, right = st.columns([1.1, 0.9], gap="large")
    with left:
        st.markdown("<div class='logo-text'>NutriScan <span class='green'>AI</span></div>", unsafe_allow_html=True)
        st.markdown("<div class='main-heading'>Smart Food Choices,<br><span class='green'>Healthy Life!</span></div>", unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown("<div class='feature-card'>🤖<br><b>AI Food<br>Analysis</b></div>", unsafe_allow_html=True)
        c2.markdown("<div class='feature-card'>❤️<br><b>Disease<br>Prediction</b></div>", unsafe_allow_html=True)
        c3.markdown("<div class='feature-card'>📃<br><b>Personalized<br>Recs</b></div>", unsafe_allow_html=True)
        c4.markdown("<div class='feature-card'>📈<br><b>Health<br>Tracking</b></div>", unsafe_allow_html=True)

    with right:
        st.markdown("<div class='login-container'>", unsafe_allow_html=True)
        st.markdown("<h2 style='text-align:center;'>Welcome Back!</h2>")
        email = st.text_input("Email", placeholder="Enter your email", key="login_email").strip()
        password = st.text_input("Password", type="password", placeholder="Enter password", key="login_pass").strip()
        
        col1, col2 = st.columns([1,1])
        with col2:
            if st.button("Forgot Password?", key="forgot_nav"):
                st.session_state.screen = "forgot"; st.rerun()
        
        if st.button("🚀 Login", key="login_btn"):
            if not email or not password: st.error("
