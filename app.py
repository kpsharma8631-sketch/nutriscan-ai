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
st.set_page_config(
    page_title="NutriScan AI",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stApp { margin-top: -80px; }
</style>
""", unsafe_allow_html=True)

# [... DATABASE OPERATIONS & SESSION STATE MANAGEMENT SAME AS PREVIOUS CODE ...]

# =========================================================
# 🔥 MASTER UI CSS - PRODUCTION READY
# =========================================================
st.markdown("""
<style>
header { visibility: hidden !important; display: none !important; }
[data-testid="stHeader"], [data-testid="stToolbar"] { display: none !important; }
.main { padding-top: 0rem !important; }
section[data-testid="stSidebar"] { top: 0 !important; }
.block-container { padding-top: 1rem !important; padding-left: 2rem !important; padding-right: 2rem !important; max-width: 100% !important; }

/* Buttons */
div.stButton > button {
    background: linear-gradient(to right, #15803d, #22c55e) !important;
    color: white !important;
    border-radius: 12px !important;
    height: 50px !important;
    width: 100% !important;
    font-weight: 700 !important;
}

/* Forgot Password Text Link Style */
div.stButton > button[key="forgot_nav_trigger_btn"] {
    background: transparent !important;
    color: #16a34a !important;
    border: none !important;
    box-shadow: none !important;
    font-weight: 600 !important;
    text-align: right !important;
    padding: 0 !important;
    height: auto !important;
}

/* Sign Up Text Link Style */
div.stButton > button[key="switch_to_signup_btn"] {
    background: transparent !important;
    color: #16a34a !important;
    border: none !important;
    box-shadow: none !important;
    font-weight: 700 !important;
    font-size: 18px !important;
    margin-top: -8px !important;
    height: auto !important;
}

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
</style>
""", unsafe_allow_html=True)

# =========================================================
# LOGIN SCREEN
# =========================================================
if st.session_state.screen == "login":
    left, right = st.columns([1.25, 0.75], gap="small")
    with right:
        st.markdown("<div class='login-container'>", unsafe_allow_html=True)
        st.markdown("<div class='welcome'>Welcome Back!</div>", unsafe_allow_html=True)
        
        email = st.text_input("Email", placeholder="📧 Enter email", key="login_email").strip()
        password = st.text_input("Password", type="password", placeholder="🔒 Enter password", key="login_pass").strip()

        col1, col2 = st.columns([1, 1])
        with col1: st.checkbox("Remember me", key="rem_me_key")
        with col2:
            if st.button("Forgot Password?", key="forgot_nav_trigger_btn"):
                st.session_state.screen = "forgot"
                st.rerun()

        if st.button("🚀 Login", key="login_btn"):
            user = login_user(email, password)
            if user:
                st.session_state.user_name = user[1]
                st.session_state.user_email = str(email)
                st.session_state.screen = "authenticated"
                st.rerun()
            else: st.error("❌ Invalid Credentials")

        st.markdown("<div style='text-align:center; margin-top:15px; font-size:17px; color:#374151;'>Don't have an account?</div>", unsafe_allow_html=True)
        if st.button("Sign Up", key="switch_to_signup_btn"):
            st.session_state.screen = "signup"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

# ... (baaki logic waisa hi hai)
