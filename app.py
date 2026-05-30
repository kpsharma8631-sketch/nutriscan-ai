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
# 🎯 5 MULTI-API KEY FAILOVER POOL ROUTER SYSTEM
# =========================================================
# 💡 GitHub pe daalne se pehle real keys mat likhna, environment variables use karna best hai.
GEMINI_KEYS_POOL = [
    # Tumhari API Keys yahan aayengi
]

def get_live_gemini_client():
    for idx, key in enumerate(GEMINI_KEYS_POOL):
        if key and not key.startswith("YOUR_API"):
            try:
                [span_0](start_span)st.session_state[f"key_status_{idx}"] = "Active"[span_0](end_span)
                [span_1](start_span)return genai.Client(api_key=key)[span_1](end_span)
            except:
                [span_2](start_span)st.session_state[f"key_status_{idx}"] = "Exhausted"[span_2](end_span)
                continue
    [span_3](start_span)return genai.Client(api_key=GEMINI_KEYS_POOL[0])[span_3](end_span)

# =========================================================
# DATABASE SETUP & SCHEMA MAPPING (RELATIVE PATH FOR GITHUB)
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
[span_4](start_span)""")[span_4](end_span)

cursor.execute("""
CREATE TABLE IF NOT EXISTS food_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_email TEXT, food_name TEXT, calories INTEGER, date_time TEXT
)
[span_5](start_span)""")[span_5](end_span)

cursor.execute("""
CREATE TABLE IF NOT EXISTS calorie_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_email TEXT, meal_type TEXT, calories INTEGER, log_date TEXT
)
[span_6](start_span)""")[span_6](end_span)

cursor.execute("""
CREATE TABLE IF NOT EXISTS water_logs (
    [span_7](start_span)id INTEGER PRIMARY KEY AUTOINCREMENT,[span_7](end_span)
    user_email TEXT, glasses INTEGER, log_date TEXT
)
[span_8](start_span)""")[span_8](end_span)
conn.commit()

# =========================================================
# DATABASE OPERATIONS
# =========================================================
def signup_user(name, age, height, weight, email, password):
    cursor.execute(
        "INSERT INTO users (name, age, height, weight, email, password) VALUES (?, ?, ?, ?, ?, ?)",
        (name, age, height, weight, email, password)
    [span_9](start_span))
    conn.commit()[span_9](end_span)

def login_user(email, password):
    [span_10](start_span)cursor.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password))[span_10](end_span)
    [span_11](start_span)data = cursor.fetchone()[span_11](end_span)
    [span_12](start_span)return data[span_12](end_span)

def recover_user_password(email):
    [span_13](start_span)cursor.execute("SELECT password FROM users WHERE email=?", (email,))[span_13](end_span)
    [span_14](start_span)res = cursor.fetchone()[span_14](end_span)
    [span_15](start_span)return res[0] if res else None[span_15](end_span)

def update_user_metrics_in_db(email, new_weight, new_height):
    cursor.execute("UPDATE users SET weight=?, height=? WHERE email=?",
                   (float(new_weight)[span_16](start_span), float(new_height), str(email)))[span_16](end_span)
    [span_17](start_span)conn.commit()[span_17](end_span)

def update_user_password_in_db(email, new_password):
    [span_18](start_span)cursor.execute("UPDATE users SET password=? WHERE email=?", (str(new_password), str(email)))[span_18](end_span)
    [span_19](start_span)conn.commit()[span_19](end_span)

def log_food_scanned(email, food_name, calories):
    [span_20](start_span)now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")[span_20](end_span)
    cursor.execute("INSERT INTO food_history (user_email, food_name, calories, date_time) VALUES (?, ?, ?, ?)",
                   (str(email)[span_21](start_span), str(food_name), int(calories), str(now)))[span_21](end_span)
    [span_22](start_span)conn.commit()[span_22](end_span)

def log_manual_calories(email, meal_type, calories):
    [span_23](start_span)today = datetime.date.today().strftime("%Y-%m-%d")[span_23](end_span)
    cursor.execute("INSERT INTO calorie_logs (user_email, meal_type, calories, log_date) VALUES (?, ?, ?, ?)",
                   (str(email)[span_24](start_span), str(meal_type), int(calories), str(today)))[span_24](end_span)
    [span_25](start_span)conn.commit()[span_25](end_span)

def get_daily_total_calories(email):
    [span_26](start_span)today = datetime.date.today().strftime("%Y-%m-%d")[span_26](end_span)
    [span_27](start_span)cursor.execute("SELECT SUM(calories) FROM calorie_logs WHERE user_email=? AND log_date=?", (email, today))[span_27](end_span)
    [span_28](start_span)res1 = cursor.fetchone()[0] or 0[span_28](end_span)
    cursor.execute("SELECT SUM(calories) FROM food_history WHERE user_email=? AND date_time LIKE ?",
                   (email, f"{today}%")[span_29](start_span))
    res2 = cursor.fetchone()[0] or 0[span_29](end_span)
    [span_30](start_span)return res1 + res2[span_30](end_span)

def get_last_scanned_food_from_db(email):
    try:
        cursor.execute("SELECT food_name, calories FROM food_history WHERE user_email=? ORDER BY id DESC LIMIT 1",
                       (email,)[span_31](start_span))
        res = cursor.fetchone()[span_31](end_span)
        [span_32](start_span)if res: return str(res[0]), int(res[1])[span_32](end_span)
    except:
        pass
    [span_33](start_span)return None, 0[span_33](end_span)

def fetch_weekly_calorie_trend_from_db(email):
    trend_data = {}
    [span_34](start_span)today = datetime.date.today()[span_34](end_span)
    [span_35](start_span)for i in range(6, -1, -1):[span_35](end_span)
        [span_36](start_span)d_str = (today - datetime.timedelta(days=i)).strftime("%Y-%m-%d")[span_36](end_span)
        [span_37](start_span)trend_data[d_str] = 0[span_37](end_span)
    try:
        cursor.execute("SELECT log_date, SUM(calories) FROM calorie_logs WHERE user_email=? GROUP BY log_date",
                       (email,)[span_38](start_span))
        for row in cursor.fetchall():[span_38](end_span)
            [span_39](start_span)if row[0] in trend_data: trend_data[row[0]] += int(row[1])[span_39](end_span)
        cursor.execute(
            "SELECT SUBSTR(date_time, 1, 10), SUM(calories) FROM food_history WHERE user_email=? GROUP BY SUBSTR(date_time, 1, 10)",
            (email,)[span_40](start_span))
        for row in cursor.fetchall():[span_40](end_span)
            [span_41](start_span)if row[0] in trend_data: trend_data[row[0]] += int(row[1])[span_41](end_span)
    except:
        pass
    [span_42](start_span)return list(trend_data.keys()), list(trend_data.values())[span_42](end_span)

def get_daily_water_glasses(email):
    [span_43](start_span)today = datetime.date.today().strftime("%Y-%m-%d")[span_43](end_span)
    [span_44](start_span)cursor.execute("SELECT glasses FROM water_logs WHERE user_email=? AND log_date=?", (email, today))[span_44](end_span)
    [span_45](start_span)res = cursor.fetchone()[span_45](end_span)
    [span_46](start_span)return int(res[0]) if res else 0[span_46](end_span)

def update_daily_water_glasses(email, delta_val):
    [span_47](start_span)today = datetime.date.today().strftime("%Y-%m-%d")[span_47](end_span)
    [span_48](start_span)current_glasses = get_daily_water_glasses(email)[span_48](end_span)
    [span_49](start_span)new_glasses = max(0, current_glasses + delta_val)[span_49](end_span)

    [span_50](start_span)cursor.execute("SELECT id FROM water_logs WHERE user_email=? AND log_date=?", (email, today))[span_50](end_span)
    [span_51](start_span)exists = cursor.fetchone()[span_51](end_span)
    if exists:
        [span_52](start_span)cursor.execute("UPDATE water_logs SET glasses=? WHERE user_email=? AND log_date=?", (new_glasses, email, today))[span_52](end_span)
    else:
        cursor.execute("INSERT INTO water_logs (user_email, glasses, log_date) VALUES (?, ?, ?)",
                       (email, new_glasses, today)[span_53](start_span))
    conn.commit()[span_53](end_span)
    [span_54](start_span)return new_glasses[span_54](end_span)

# =========================================================
# SESSION STATE MANAGEMENT
# =========================================================
[span_55](start_span)if "screen" not in st.session_state: st.session_state.screen = "login"[span_55](end_span)
[span_56](start_span)if "user_name" not in st.session_state: st.session_state.user_name = "User"[span_56](end_span)
[span_57](start_span)if "user_email" not in st.session_state: st.session_state.user_email = ""[span_57](end_span)
[span_58](start_span)if "detected_food" not in st.session_state: st.session_state.detected_food = None[span_58](end_span)
[span_59](start_span)if "multimodal_results" not in st.session_state: st.session_state.multimodal_results = None[span_59](end_span)
[span_60](start_span)if "user_bmi" not in st.session_state: st.session_state.user_bmi = 22.0[span_60](end_span)
[span_61](start_span)if "user_bmr_target" not in st.session_state: st.session_state.user_bmr_target = 2000[span_61](end_span)
[span_62](start_span)if "selected_goal_calories" not in st.session_state: st.session_state.selected_goal_calories = 2000[span_62](end_span)
[span_63](start_span)if "custom_target_enabled" not in st.session_state: st.session_state.custom_target_enabled = False[span_63](end_span)
[span_64](start_span)if "activity_multiplier" not in st.session_state: st.session_state.activity_multiplier = 1.2[span_64](end_span)
[span_65](start_span)if "chat_history" not in st.session_state: st.session_state.chat_history = [][span_65](end_span)

# =========================================================
# HELPER FUNCTION: SAFE IMAGE RENDERER
# =========================================================
def render_local_image(image_name, img_width=None, use_column=False):
    if os.path.exists(image_name):
        if use_column:
            [span_66](start_span)st.image(image_name, width="stretch")[span_66](end_span)
        else:
            [span_67](start_span)st.image(image_name, width=img_width)[span_67](end_span)
    else:
        if "logo" in image_name:
            [span_68](start_span)st.markdown("<h1 style='font-size:50px; margin:0;'>🥗</h1>", unsafe_allow_html=True)[span_68](end_span)
        else:
            st.markdown(
                "<div style='background:#f0fdf4; height:200px; border-radius:18px; display:flex; align-items:center; justify-content:center; color:#16a34a;'><b>[ NutriScan AI Graphic Asset ]</b></div>",
                [span_69](start_span)unsafe_allow_html=True)[span_69](end_span)

# =========================================================
# 🚨 BULLETPROOF EXACT DATASET KEY-MAPPER
# =========================================================
def get_clean_macro_integer(macros_dict, key_name):
    [span_70](start_span)if key_name == "protein" and "Protein" in macros_dict: return int(macros_dict["Protein"])[span_70](end_span)
    [span_71](start_span)if key_name == "carbs" and "Carbs" in macros_dict: return int(macros_dict["Carbs"])[span_71](end_span)
    [span_72](start_span)if key_name == "fat" and "Fats" in macros_dict: return int(macros_dict["Fats"])[span_72](end_span)
    [span_73](start_span)if key_name == "protein" and "protein" in macros_dict: return int(macros_dict["protein"])[span_73](end_span)
    [span_74](start_span)if key_name == "carbs" and "carbs" in macros_dict: return int(macros_dict["carbs"])[span_74](end_span)
    [span_75](start_span)if key_name == "fat" and "fat" in macros_dict: return int(macros_dict["fat"])[span_75](end_span)
    [span_76](start_span)return 0[span_76](end_span)

def find_best_matching_db_key(input_food_string):
    [span_77](start_span)clean_target = str(input_food_string).lower().strip()[span_77](end_span)
    [span_78](start_span)if "thali (" in clean_target:[span_78](end_span)
        [span_79](start_span)for db_key in FOOD_DATASET.keys():[span_79](end_span)
            [span_80](start_span)if db_key.replace("_", " ") in clean_target:[span_80](end_span)
                [span_81](start_span)return db_key[span_81](end_span)
    [span_82](start_span)for db_key in FOOD_DATASET.keys():[span_82](end_span)
        [span_83](start_span)clean_db_key = db_key.replace("_", " ")[span_83](end_span)
        [span_84](start_span)if clean_db_key in clean_target or clean_target in clean_db_key:[span_84](end_span)
             [span_85](start_span)return db_key[span_85](end_span)
    [span_86](start_span)return None[span_86](end_span)

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
div.stButton > button { background: linear-gradient(to right, #15803d, #22c55e) !important; color: white !important; border-radius: 12px !important; border: none !important; font-weight: 700 !important; height: 50px !important; width: 100% !important; box-shadow: 0px 4px 12px rgba(22, 163, 74, 0.15) !important; }
div.stButton > button:hover { transform: translateY(-1px) !important; box-shadow: 0px 6px 18px rgba(22,163,74,0.25) !important; }
div.stButton > button[key*="trigger_ai_btn"], div.stButton > button[key*="execute_ai_btn"], div.stButton > button[key*="bmi_calc_btn"] { background: linear-gradient(to right, #1e3a8a, #3b82f6) !important; }
div.stButton > button[key*="process_voice_btn"], div.stButton > button[key*="calorie_log_btn"], div.stButton > button[key*="official_download_stream_btn"] { background: linear-gradient(to right, #ea580c, #f97316) !important; }
div.stButton > button[key*="purge_btn"] { background: linear-gradient(to right, #dc2626, #ef4444) !important; box-shadow: none !important; }
div.stButton > button[key*="switch"], div.stButton > button[key*="back"], div.stButton > button[key*="logout"], div.stButton > button[key*="forgot_nav"] { background: #f0fdf4 !important; color: #16a34a !important; border: 1px solid #bbf7d0 !important; }
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
        with text_col: st.markdown("<div class='logo-text'>NutriScan <span class='green'>AI</span></div>", unsafe_allow_html=True)
        [span_87](start_span)st.markdown("<div class='main-heading'>Smart Food Choices,<br><span class='green'>Healthy Life!</span></div>", unsafe_allow_html=True)[span_87](end_span)
        [span_88](start_span)st.markdown("<div class='subtitle'>NutriScan AI analyzes your food, predicts health risks and suggests better choices.</div>", unsafe_allow_html=True)[span_88](end_span)
        st.write("")
        c1, c2, c3, c4 = st.columns(4)
        [span_89](start_span)c1.markdown("<div class='feature-card'>🧠<br><br><b>AI Food<br>Analysis</b></div>", unsafe_allow_html=True)[span_89](end_span)
        [span_90](start_span)c2.markdown("<div class='feature-card'>❤️<br><br><b>Disease<br>Prediction</b></div>", unsafe_allow_html=True)[span_90](end_span)
        [span_91](start_span)c3.markdown("<div class='feature-card'>📋<br><br><b>Personalized<br>Recs</b></div>", unsafe_allow_html=True)[span_91](end_span)
        [span_92](start_span)c4.markdown("<div class='feature-card'>📈<br><br><b>Health<br>Tracking</b></div>", unsafe_allow_html=True)[span_92](end_span)
        st.write("")
        render_local_image("hero.png", use_column=True)

    with right:
        st.markdown("<div class='login-container'>", unsafe_allow_html=True)
        st.markdown("<div class='welcome'>Welcome Back!</div>", unsafe_allow_html=True)
        st.markdown("<div class='subtitle2'>Login to continue your health journey</div>", unsafe_allow_html=True)
        [span_93](start_span)st.markdown("<div class='avatar-wrapper'><img class='avatar-img' src='https://cdn-icons-png.flaticon.com/512/3135/3135715.png'></div>", unsafe_allow_html=True)[span_93](end_span)

        [span_94](start_span)email = st.text_input("User Email Address String", placeholder="📧 Enter your email", label_visibility="collapsed", key="login_email").strip()[span_94](end_span)
        [span_95](start_span)password = st.text_input("User Secure Credential Key String", type="password", placeholder="🔒 Enter your password", label_visibility="collapsed", key="login_pass").strip()[span_95](end_span)

        col1, col2 = st.columns([1, 1])
        with col1:
            [span_96](start_span)st.checkbox("Remember me", key="rem_me_key")[span_96](end_span)
        with col2:
            if st.button("Forgot Password?", key="forgot_nav_trigger_btn"):
                [span_97](start_span)st.session_state.screen = "forgot"[span_97](end_span)
                [span_98](start_span)st.rerun()[span_98](end_span)

        if st.button("🚀 Login", width="stretch", key="login_btn"):
            if not email or not password:
                [span_99](start_span)st.error("⚠️ Access Denied: Enter credentials!")[span_99](end_span)
            else:
                [span_100](start_span)user = login_user(email, password)[span_100](end_span)
                if user:
                    [span_101](start_span)st.session_state.user_name = user[1][span_101](end_span)
                    [span_102](start_span)st.session_state.user_email = str(email)[span_102](end_span)
                    [span_103](start_span)st.session_state.u_age_static = int(user[2] or 22)[span_103](end_span)
                    [span_104](start_span)st.session_state.u_height_live = float(user[3] or 172.0)[span_104](end_span)
                    [span_105](start_span)st.session_state.u_weight_live = float(user[4] or 68.0)[span_105](end_span)
                    [span_106](start_span)h_m = st.session_state.u_height_live / 100.0[span_106](end_span)
                    [span_107](start_span)st.session_state.user_bmi = round(st.session_state.u_weight_live / (h_m * h_m), 1)[span_107](end_span)
                    [span_108](start_span)base_bmr = int(10 * st.session_state.u_weight_live + 6.25 * st.session_state.u_height_live - 5 * st.session_state.get('u_age_static', 22) + 5)[span_108](end_span)

                    [span_109](start_span)if not st.session_state.custom_target_enabled:[span_109](end_span)
                        [span_110](start_span)st.session_state.user_bmr_target = int(base_bmr * st.session_state.activity_multiplier)[span_110](end_span)
                    else:
                        [span_111](start_span)st.session_state.user_bmr_target = st.session_state.selected_goal_calories[span_111](end_span)

                    [span_112](start_span)st.session_state.screen = "authenticated"[span_112](end_span)
                    [span_113](start_span)st.rerun()[span_113](end_span)
                else:
                    [span_114](start_span)st.error("❌ Invalid Email or Password. Please try again.")[span_114](end_span)

        [span_115](start_span)st.markdown("<div style='text-align:center; color:gray; margin-top:12px; margin-bottom:5px;'>───── or continue with ─────</div>", unsafe_allow_html=True)[span_115](end_span)
        if st.button("Don't have an account? Sign Up", width="stretch", key="switch_to_signup_btn"):
            [span_116](start_span)st.session_state.screen = "signup"[span_116](end_span)
            [span_117](start_span)st.rerun()[span_117](end_span)
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
    [span_118](start_span)st.markdown("<div style='max-width:550px; margin: 80px auto;' class='login-container'>", unsafe_allow_html=True)[span_118](end_span)
    [span_119](start_span)st.markdown("<h2 style='text-align:center; font-weight:800; color:#111827;'>🔒 Account Recovery Terminal</h2>", unsafe_allow_html=True)[span_119](end_span)
    st.write("---")
    [span_120](start_span)recover_target = st.text_input("Enter your registered email address:", placeholder="📧 e.g., keshav@example.com")[span_120](end_span)
    st.write("")

    col_b1, col_b2 = st.columns(2)
    with col_b1:
        if st.button("🔍 Recover Password Key", key="execute_recovery_btn"):
            [span_121](start_span)if not recover_target.strip():[span_121](end_span)
                [span_122](start_span)st.warning("⚠️ Please provide a valid email query.")[span_122](end_span)
            else:
                [span_123](start_span)found_pass = recover_user_password(recover_target.strip())[span_123](end_span)
                if found_pass:
                    [span_124](start_span)st.success(f"🎉 **Match Discovered!** Key decryption sequence: `{found_pass}`")[span_124](end_span)
                else:
                    [span_125](start_span)st.error("❌ Resource Error: Token not found.")[span_125](end_span)
    with col_b2:
        if st.button("🔙 Return to Login Page", key="back_login_nav_switch_btn"):
            [span_126](start_span)st.session_state.screen = "login"[span_126](end_span)
            [span_127](start_span)st.rerun()[span_127](end_span)
    st.markdown("</div>", unsafe_allow_html=True)

elif st.session_state.screen == "signup":
    left, right = st.columns([1.0, 1.0], gap="large")
    with left:
        [span_128](start_span)logo_col_s, text_col_s = st.columns([0.15, 0.85])[span_128](end_span)
        [span_129](start_span)with logo_col_s: render_local_image("logo.png", img_width=65)[span_129](end_span)
        [span_130](start_span)with text_col_s: st.markdown("<div class='logo-text' style='font-size:38px;'>NutriScan <span class='green'>AI</span></div>", unsafe_allow_html=True)[span_130](end_span)
        [span_131](start_span)st.markdown("<div class='main-heading' style='font-size:48px;'>Join Us For A<br><span class='green'>Healthy Journey!</span></div>", unsafe_allow_html=True)[span_131](end_span)
        st.write("")
        render_local_image("hero.png", use_column=True)

    with right:
        st.markdown("<div class='signup-container-card'>", unsafe_allow_html=True)
        [span_132](start_span)st.markdown("<h2 style='text-align:center; font-weight:800; color:#111827;'>Create Account</h2>", unsafe_allow_html=True)[span_132](end_span)

        [span_133](start_span)full_name = st.text_input("Full Name Field", placeholder="👤 Enter your full name", label_visibility="collapsed", key="signup_name").strip()[span_133](end_span)
        st.write("")
        [span_134](start_span)st.markdown("<label style='font-weight:600; color:#374151; font-size:14px;'>🧬 Biometric Metrics Data</label>", unsafe_allow_html=True)[span_134](end_span)
        a1, a2, a3 = st.columns(3)
        with a1:
            [span_135](start_span)age = st.number_input("Age", min_value=1, max_value=100, value=22, step=1, key="signup_age")[span_135](end_span)
        with a2:
            [span_136](start_span)height = st.number_input("Height (cm)", min_value=50, max_value=250, value=172, step=1, key="signup_height")[span_136](end_span)
        with a3:
            [span_137](start_span)weight = st.number_input("Weight (kg)", min_value=10, max_value=300, value=68, step=1, key="signup_weight")[span_137](end_span)

        st.write("")
        [span_138](start_span)email_reg = st.text_input("Email Reg Field", placeholder="📧 Enter your email", label_visibility="collapsed", key="signup_email").strip()[span_138](end_span)
        [span_139](start_span)pass_reg = st.text_input("Pass Reg Field", type="password", placeholder="🔒 Create password", label_visibility="collapsed", key="signup_pass").strip()[span_139](end_span)

        if st.button("🔥 Register New Account Now", width="stretch", key="register_btn"):
            if not full_name or not email_reg or not pass_reg:
                [span_140](start_span)st.warning("⚠️ Access Denied: Fill constraints.")[span_140](end_span)
            else:
                [span_141](start_span)signup_user(full_name, age, height, weight, email_reg, pass_reg)[span_141](end_span)
                [span_142](start_span)st.success("🎉 Account Created Successfully! Please login.")[span_142](end_span)
                [span_143](start_span)st.session_state.screen = "login"[span_143](end_span)
                [span_144](start_span)st.rerun()[span_144](end_span)

        if st.button("🔙 Back to Secure Login Window", width="stretch", key="back_login_btn"):
            [span_145](start_span)st.session_state.screen = "login"[span_145](end_span)
            [span_146](start_span)st.rerun()[span_146](end_span)
        st.markdown("</div>", unsafe_allow_html=True)

elif st.session_state.screen == "authenticated":
    with st.sidebar:
        [span_147](start_span)st.markdown(f"### 🛡️ NutriScan AI System\n👤 **User Active:** `{st.session_state.user_name}`")[span_147](end_span)
        st.write("---")
        menu = st.radio("Navigation Menu",
                        ["🏠 Home Dashboard", "🥗 Food Analysis", "🧮 BMI Calculator", "🔥 Calorie Tracker",
                         [span_148](start_span)"💧 Water Tracker", "💔 Disease Risk", "🩺 Symptoms & Tests", "💊 Medicines", "📊 Health Analytics",[span_148](end_span)
                         [span_149](start_span)"📜 Food History", "🤖 AI Chatbot", "⚙️ Settings"])[span_149](end_span)
        st.write("---")
        if st.button("🚪 Terminate Session & Logout", width="stretch", key="logout_btn"):
            [span_150](start_span)st.session_state.screen = "login"[span_150](end_span)
            [span_151](start_span)st.session_state.user_name = "User"[span_151](end_span)
            [span_152](start_span)st.session_state.detected_food = None[span_152](end_span)
            [span_153](start_span)st.session_state.multimodal_results = None[span_153](end_span)
            [span_154](start_span)st.rerun()[span_154](end_span)

    [span_155](start_span)current_live_calories = get_daily_total_calories(st.session_state.user_email)[span_155](end_span)
    [span_156](start_span)current_live_water = get_daily_water_glasses(st.session_state.user_email)[span_156](end_span)

    is_new_user_flag = False
    db_last_food, db_logged_calories = None, 0
    [span_157](start_span)db_fetch_res = get_last_scanned_food_from_db(st.session_state.user_email)[span_157](end_span)
    if db_fetch_res:
        [span_158](start_span)db_last_food, db_logged_calories = db_fetch_res[span_158](end_span)

    if st.session_state.detected_food:
        [span_159](start_span)session_focus_food = find_best_matching_db_key(st.session_state.detected_food)[span_159](end_span)
    elif db_last_food:
        [span_160](start_span)session_focus_food = find_best_matching_db_key(db_last_food)[span_160](end_span)
    else:
        session_focus_food = None
        is_new_user_flag = True

    if session_focus_food and session_focus_food not in FOOD_DATASET:
        [span_161](start_span)session_focus_food = "pizza"[span_161](end_span)

    # Health Score Engine
    [span_162](start_span)calculated_health_score = 80[span_162](end_span)
    [span_163](start_span)score_msg = "Good"[span_163](end_span)
    [span_164](start_span)if st.session_state.user_bmi < 18.5 or st.session_state.user_bmi > 25.0:[span_164](end_span)
        [span_165](start_span)calculated_health_score -= 15[span_165](end_span)
    else:
        [span_166](start_span)calculated_health_score += 5[span_166](end_span)
    [span_167](start_span)calculated_health_score += min(current_live_water * 2, 15)[span_167](end_span)
    [span_168](start_span)if current_live_calories > st.session_state.user_bmr_target: calculated_health_score -= 15[span_168](end_span)
    [span_169](start_span)calculated_health_score = max(min(calculated_health_score, 100), 10)[span_169](end_span)

    if calculated_health_score >= 85:
        [span_170](start_span)score_msg = "Excellent"[span_170](end_span)
    elif calculated_health_score >= 70:
        [span_171](start_span)score_msg = "Good"[span_171](end_span)
    else:
        [span_172](start_span)score_msg = "Needs Attention"[span_172](end_span)

    # 1. 🏠 HOME DASHBOARD
    [span_173](start_span)if menu == "🏠 Home Dashboard":[span_173](end_span)
        [span_174](start_span)st.markdown("<div class='auth-header-space'></div>", unsafe_allow_html=True)[span_174](end_span)
        [span_175](start_span)st.markdown(f"<h1>Hello, {st.session_state.user_name} 👋</h1><p style='color:#64748b; font-size:16px; margin-top:-10px;'>Welcome to your central health control hub.</p>", unsafe_allow_html=True)[span_175](end_span)
        st.write("---")

        if current_live_calories > st.session_state.user_bmr_target:
            [span_176](start_span)st.error(f"🛑 **CRITICAL CALORIC EXCEEDED ALERT:** Target Limit Cap is breached! Intake is currently over the restricted threshold boundary by `{current_live_calories - st.session_state.user_bmr_target} kcal`.")[span_176](end_span)

        [span_177](start_span)r1_c1, r1_c2 = st.columns(2, gap="large")[span_177](end_span)
        with r1_c1:
            [span_178](start_span)st.markdown(f"<div class='dash-card'><span class='dash-emoji'>🔥</span><div class='dash-lbl'>Daily Calories</div><div class='dash-val'>{current_live_calories} / {st.session_state.user_bmr_target} kcal</div></div>", unsafe_allow_html=True)[span_178](end_span)
        with r1_c2:
            [span_179](start_span)st.markdown(f"<div class='dash-card'><span class='dash-emoji'>💧</span><div class='dash-lbl'>Water Target</div><div class='dash-val'>{current_live_water} / 8 Glasses</div></div>", unsafe_allow_html=True)[span_179](end_span)
        st.write("")
        [span_180](start_span)r2_c1, r2_c2 = st.columns(2, gap="large")[span_180](end_span)
        with r2_c1:
            [span_181](start_span)st.markdown(f"<div class='dash-card'><span class='dash-emoji'>📈</span><div class='dash-lbl'>Your BMI</div><div class='dash-val'>{st.session_state.user_bmi}</div></div>", unsafe_allow_html=True)[span_181](end_span)
        with r2_c2:
            [span_182](start_span)st.markdown(f"<div class='dash-card'><span class='dash-emoji'>❤️</span><div class='dash-lbl'>Health Score</div><div class='dash-val'>{calculated_health_score} / 100 {score_msg}</div></div>", unsafe_allow_html=True)[span_182](end_span)
        st.write("---")

        st.write("#### 🛡️ Load Balancer Security Ledger Status:")
        [span_183](start_span)k_cols = st.columns(5)[span_183](end_span)
        [span_184](start_span)for i in range(5):[span_184](end_span)
            [span_185](start_span)status_node = st.session_state.get(f"key_status_{i}", "Standby / Ready")[span_185](end_span)
            [span_186](start_span)k_cols[i].info(f"🔑 Node {i + 1}: {status_node}")[span_186](end_span)

    # 2. 🥗 FOOD ANALYSIS (ONLY MULTIMODAL SCANNER RETAINED)
    elif menu == "🥗 Food Analysis":
        [span_187](start_span)st.markdown("<div class='auth-header-space'></div>", unsafe_allow_html=True)[span_187](end_span)
        [span_188](start_span)st.markdown("<h2>🥗 Precision AI Food Scanner & Multimodal Thali Core</h2>", unsafe_allow_html=True)[span_188](end_span)
        st.write("---")
        [span_189](start_span)st.markdown("<div class='scanner-card'>", unsafe_allow_html=True)[span_189](end_span)
        [span_190](start_span)uploaded_file = st.file_uploader("Choose food photo source...", type=["png", "jpg", "jpeg"], key="uploader_widget")[span_190](end_span)
        if uploaded_file:
            st.write("")
            [span_191](start_span)ul, ur = st.columns([0.4, 0.6])[span_191](end_span)
            with ul:
                [span_192](start_span)st.image(uploaded_file, width=320)[span_192](end_span)
            with ur:
                [span_193](start_span)st.write("#### Neural Core Diagnostics")[span_193](end_span)
                st.info("✨ Plate Scanner Target Active: Multimodal Thali Mode Enabled")
                
                if st.button("🤖 Trigger Gemini Multimodal Plate AI Scan", width="stretch", key="trigger_ai_btn"):
                    temp_dir = os.path.join(os.getcwd(), "app_uploads")
                    os.makedirs(temp_dir, exist_ok=True)
                    [span_194](start_span)temp_image_path = os.path.join(temp_dir, uploaded_file.name)[span_194](end_span)
                    with open(temp_image_path, "wb") as f:
                        [span_195](start_span)f.write(uploaded_file.getbuffer())[span_195](end_span)

                    [span_196](start_span)with st.spinner("✨ Initializing Gemini Multimodal Plate Architecture..."):[span_196](end_span)
                        try:
                            [span_197](start_span)client = get_live_gemini_client()[span_197](end_span)
                            with open(temp_image_path, "rb") as img_f:
                                [span_198](start_span)img_bytes = img_f.read()[span_198](end_span)
                            thali_prompt = (
                                [span_199](start_span)"Analyze this meal plate photo. Identify all separate food items. Return output strictly in valid JSON format: "[span_199](end_span)
                                [span_200](start_span)'{"total_calories": 400, "items": [{"name": "idli", "qty": "3 pieces", "calories": 210}, {"name": "tomato_chutney", "qty": "1 bowl", "calories": 80}, {"name": "coconut_chutney", "qty": "1 bowl", "calories": 110}]}'[span_200](end_span)
                            )
                            response = client.models.generate_content(
                                [span_201](start_span)model='gemini-2.5-flash',[span_201](end_span)
                                [span_202](start_span)contents=[{'inline_data': {'mime_type': 'image/jpeg', 'data': img_bytes}}, thali_prompt][span_202](end_span)
                            )
                            [cite_start]clean_txt = response.text.strip().replace("
http://googleusercontent.com/immersive_entry_chip/0
http://googleusercontent.com/immersive_entry_chip/1

### 💡 Kuch zaroori batein jo yaad rakhna:
1. **No Absolute Paths**: Code me jo `temp_dir` local folder tha, usko maine relative bana diya hai (`os.getcwd()`). Ab ye kisi bhi computer par chalega bina crash hue.
2. **Database Platform Agnostic**: Database path ko bhi relative bana diya hai, taaki Windows aur Linux dono par chal sake.
3. **`.gitignore` banana mat bhulna**: GitHub par project upload karne se pehle ek `.gitignore` file banakar usme `users.db` aur `app_uploads/` daal dena, taaki user ka data ya images publically leak na hon.
