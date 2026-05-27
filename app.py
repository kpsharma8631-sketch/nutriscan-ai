# app.py
import os
import sqlite3
import datetime
import json
import streamlit as st
import plotly.graph_objects as go
from google import genai
from database import FOOD_DATASET

# =========================================================
# 🚨 ENVIRONMENT ROUTING
# =========================================================
try:
    from model import predict_food_item
except ImportError:
    def predict_food_item(img_path): return "invalid", 0, 0, 0

# =========================================================
# 🎯 API KEY ROUTER
# =========================================================
GEMINI_KEYS_POOL = [st.secrets.get("GEMINI_API_KEY", ""), "YOUR_API_KEY_1", "YOUR_API_KEY_2"]

def get_live_gemini_client():
    valid_keys = [k for k in GEMINI_KEYS_POOL if k.strip()]
    if not valid_keys: return None
    for idx, key in enumerate(valid_keys):
        try:
            return genai.Client(api_key=key)
        except: continue
    return None

# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(page_title="NutriScan AI", layout="wide", initial_sidebar_state="expanded")

# =========================================================
# 🔥 FINAL PERFECT CSS (NO WHITE SPACE + PROFESSIONAL UI)
# =========================================================
st.markdown("""
<style>
header { visibility: hidden !important; }
[data-testid="stHeader"] { display: none !important; }
[data-testid="stToolbar"] { display: none !important; }

.block-container {
    padding-top: 1rem !important;
    padding-bottom: 0rem !important;
    max-width: 100% !important;
}

.main { padding-top: 0rem !important; }

div.stButton > button {
    width: 100% !important;
    display: block !important;
    background: linear-gradient(to right, #15803d, #22c55e) !important;
    color: white !important;
    border-radius: 12px !important;
    height: 44px !important;
    font-weight: 700 !important;
    border: none !important;
    box-shadow: 0px 4px 12px rgba(22, 163, 74, 0.15) !important;
}

.stTextInput input, .stNumberInput input {
    height: 50px !important;
    border-radius: 12px !important;
}

.login-container {
    background: white;
    padding: 20px 28px !important;
    border-radius: 22px;
    box-shadow: 0px 8px 24px rgba(0,0,0,0.05);
    margin-top: -20px !important;
    border: 1px solid #f1f5f9;
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# DATABASE SETUP & OPERATIONS (Same as your verified logic)
# =========================================================
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, age INTEGER, height REAL, weight REAL, email TEXT, password TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS food_history (id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT, food_name TEXT, calories INTEGER, date_time TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS calorie_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT, meal_type TEXT, calories INTEGER, log_date TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS water_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT, glasses INTEGER, log_date TEXT)")
conn.commit()

def login_user(email, password):
    cursor.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password))
    return cursor.fetchone()

# =========================================================
# SESSION STATE & GATEWAY
# =========================================================
if "screen" not in st.session_state: st.session_state.screen = "login"

def render_local_image(image_name, img_width=None, use_column=False):
    if os.path.exists(image_name):
        if use_column: st.image(image_name, use_container_width=True)
        else: st.image(image_name, width=img_width)

if st.session_state.screen == "login":
    left, right = st.columns([1.25, 0.75], gap="small")
    with left:
        st.markdown("<div style='margin-top:60px;'></div>", unsafe_allow_html=True)
        logo_col, text_col = st.columns([0.15, 0.85])
        with logo_col: render_local_image("logo.png", img_width=75)
        with text_col: st.markdown("<div style='font-size:45px; font-weight:800;'>NutriScan <span style='color:#16a34a;'>AI</span></div>", unsafe_allow_html=True)
        st.markdown("<div style='font-size:52px; font-weight:800; margin-top:10px;'>Smart Food Choices,<br><span style='color:#16a34a;'>Healthy Life!</span></div>", unsafe_allow_html=True)
        st.markdown("<div style='font-size:19px; color:#4b5563; margin-top:15px;'>NutriScan AI analyzes your food, predicts health risks and suggests better choices.</div>", unsafe_allow_html=True)
        
        st.markdown("<div style='margin-left:-40px; margin-top:-20px;'>", unsafe_allow_html=True)
        render_local_image("hero.png", img_width=520)
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown("<div class='login-container'>", unsafe_allow_html=True)
        st.markdown("<h2 style='text-align:center;'>Welcome Back!</h2>", unsafe_allow_html=True)
        email = st.text_input("Email", placeholder="📧 Enter email")
        password = st.text_input("Password", type="password", placeholder="🔒 Enter password")
        
        # Forgot Password Logic
        if st.button("Forgot Password?", key="forgot_nav_trigger_btn"):
            st.session_state.screen = "forgot"
            st.rerun()

        if st.button("🚀 Login", key="login_btn"):
            user = login_user(email, password)
            if user:
                st.session_state.user_name = user[1]
                st.session_state.user_email = email
                st.session_state.screen = "authenticated"
                st.rerun()
            else: st.error("❌ Invalid Credentials")

        if st.button("Sign Up", key="switch_to_signup_btn"):
            st.session_state.screen = "signup"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

elif st.session_state.screen == "authenticated":
    # Sidebar & Dashboard logic here
    st.sidebar.title("Navigation")
    if st.sidebar.button("Logout"):
        st.session_state.screen = "login"
        st.rerun()
    st.write("Dashboard Active")
