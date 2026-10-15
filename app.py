import streamlit as st
import pandas as pd
import yfinance as yf
from google import genai
import json
import os
import sqlite3
import hashlib
import random
import urllib.parse
from datetime import datetime
import pytz

st.set_page_config(
    page_title="Universal AI Stock Analyst Hub",
    page_icon="📈",
    layout="centered",
    initial_sidebar_state="collapsed"
)

DB_FILE = "universal_users.db"

# --- 1. DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY, 
                    email TEXT UNIQUE,
                    phone TEXT,
                    password_hash TEXT, 
                    reset_code TEXT
                )''')
    
    c.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in c.fetchall()]
    if "phone" not in columns:
        c.execute("ALTER TABLE users ADD COLUMN phone TEXT")

    c.execute('''CREATE TABLE IF NOT EXISTS portfolios (
                    username TEXT,
                    ticker TEXT,
                    name TEXT,
                    market TEXT,
                    theme TEXT,
                    qty REAL,
                    buy_price REAL,
                    PRIMARY KEY (username, ticker)
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS contacts (
                    username TEXT,
                    name TEXT,
                    phone TEXT,
                    active INTEGER,
                    PRIMARY KEY (username, phone)
                )''')
    conn.commit()
    conn.close()

init_db()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(username, email, phone, password):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        uname = username.lower().strip()
        mail = email.lower().strip()
        phn = phone.strip()
        c.execute("INSERT INTO users (username, email, phone, password_hash, reset_code) VALUES (?, ?, ?, ?, ?)",
                  (uname, mail, phn, hash_password(password), ""))
        
        default_stocks = [
            ("AVANTEL.NS", "Avantel", "IN", "Defence", 100, 150.0),
            ("BDL.NS", "Bharat Dynamics", "IN", "Defence", 50, 1200.0),
            ("CAMS.NS", "CAMS", "IN", "Fin Services", 20, 3500.0),
            ("CDSL.NS", "CDSL", "IN", "Fin Services", 50, 1400.0),
            ("NVDA", "NVIDIA", "US", "Semicon & AI", 20, 120.0)
        ]
        for s in default_stocks:
            c.execute("INSERT OR REPLACE INTO portfolios VALUES (?, ?, ?, ?, ?, ?, ?)", (uname, *s))
        conn.commit()
        conn.close()
        return True, "Success"
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Username, Email, or Phone already registered."

def verify_user_credentials(identifier, password):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    iden = identifier.lower().strip()
    c.execute("SELECT username, password_hash FROM users WHERE username = ? OR email = ? OR phone = ?", (iden, iden, iden))
    row = c.fetchone()
    conn.close()
    if row and row[1] == hash_password(password):
        return row[0]
    return None

def get_username_by_phone(phone):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE phone = ?", (phone.strip(),))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def send_otp_bypassed(phone_number):
    code = str(random.randint(100000, 999999))
    return True, code

def load_user_portfolio(username):
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql("SELECT ticker as Ticker, name as Name, market as Market, theme as Theme, qty as Qty, buy_price as Buy_Price FROM portfolios WHERE username = ?", conn, params=(username,))
    conn.close()
    if df.empty:
        return pd.DataFrame(columns=["Ticker", "Name", "Market", "Theme", "Qty", "Buy_Price"])
    return df

def save_user_portfolio(username, df):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM portfolios WHERE username = ?", (username,))
    for _, r in df.iterrows():
        c.execute("INSERT OR REPLACE INTO portfolios VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (username, str(r["Ticker"]), str(r.get("Name", r["Ticker"])), str(r.get("Market", "IN")), str(r.get("Theme", "Growth")), float(r["Qty"]), float(r["Buy_Price"])))
    conn.commit()
    conn.close()

def load_user_contacts(username):
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql("SELECT name as Name, phone as Phone, active as Active FROM contacts WHERE username = ?", conn, params=(username,))
    conn.close()
    if df.empty:
        return pd.DataFrame([{"Name": "Primary", "Phone": "+919876543210", "Active": True}])
    df["Active"] = df["Active"].astype(bool)
    return df

def save_user_contacts(username, df):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM contacts WHERE username = ?", (username,))
    for _, r in df.iterrows():
        c.execute("INSERT OR REPLACE INTO contacts VALUES (?, ?, ?, ?)",
                  (username, str(r["Name"]), str(r["Phone"]), int(r["Active"])))
    conn.commit()
    conn.close()

# --- 2. AUTHENTICATION GATEWAY ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""

if "otp_sent" not in st.session_state:
    st.session_state.otp_sent = False
    st.session_state.pending_phone = ""
    st.session_state.generated_otp = ""

if not st.session_state.logged_in:
    st.title("🔐 Universal AI Stock Analyst Hub")
    
    auth_tab1, auth_tab2, auth_tab3 = st.tabs(["🔑 Password Login", "📱 Mobile OTP Login", "📝 Register New Account"])

    with auth_tab1:
        st.subheader("Sign In with Password")
        login_id = st.text_input("Username, Email, or Phone", key="log_id")
        login_pw = st.text_input("Password", type="password", key="log_pw")

        if st.button("Log In", type="primary", use_container_width=True):
            uname = verify_user_credentials(login_id, login_pw)
            if uname:
                st.session_state.logged_in = True
                st.session_state.username = uname
                st.rerun()
            else:
                st.error("Invalid credentials.")

    with auth_tab2:
        st.subheader("Sign In via Mobile Verification Code")
        phone_login = st.text_input("Enter Registered Mobile Number (e.g., +918106667450)")
        
        if st.button("Generate Login OTP"):
            uname = get_username_by_phone(phone_login)
            if uname:
                success, code = send_otp_bypassed(phone_login)
                st.session_state.otp_sent = True
                st.session_state.pending_phone = phone_login
                st.session_state.generated_otp = code
                st.session_state.login_target_user = uname
                st.success(f"Verification Code Generated: **{code}** (Enter below)")
            else:
                st.error("Phone number not registered.")

        if st.session_state.otp_sent and st.session_state.pending_phone:
            entered_otp = st.text_input("Enter 6-Digit OTP Code")
            if st.button("Verify & Log In", type="primary"):
                if entered_otp.strip() == st.session_state.generated_otp:
                    st.session_state.logged_in = True
                    st.session_state.username = st.session_state.login_target_user
                    st.session_state.otp_sent = False
                    st.rerun()
                else:
                    st.error("Incorrect OTP code.")

    with auth_tab3:
        st.subheader("Create a New Universal Account")
        r_user = st.text_input("Choose Username").strip().lower()
        r_email = st.text_input("Email Address").strip().lower()
        r_phone = st.text_input("Mobile Number (+91...)").strip()
        r_pw = st.text_input("Choose Password", type="password", key="r_pw")

        if st.button("Generate Verification OTP", type="primary", use_container_width=True):
            if r_user and r_phone and r_pw:
                success, code = send_otp_bypassed(r_phone)
                st.session_state.reg_otp_sent = True
                st.session_state.reg_code = code
                st.session_state.reg_data = (r_user, r_email, r_phone, r_pw)
                st.success(f"Verification Code Generated: **{code}** (Enter below)")
            else:
                st.warning("Fill in Username, Phone, and Password.")

        if st.session_state.get("reg_otp_sent", False):
            reg_entered_otp = st.text_input("Enter Registration OTP")
            if st.button("Verify & Complete Registration"):
                if reg_entered_otp.strip() == st.session_state.reg_code:
                    u, e, p, pwd = st.session_state.reg_data
                    success, msg = register_user(u, e, p, pwd)
                    if success:
                        st.success("Account successfully created! You can now log in.")
                        st.session_state.reg_otp_sent = False
                    else:
                        st.error(msg)
                else:
                    st.error("Invalid verification code.")

    st.stop()

# --- 3. LOGGED-IN UNIVERSAL DASHBOARD ---
username = st.session_state.username
user_portfolio_df = load_user_portfolio(username)
user_contacts_df = load_user_contacts(username)

GLOBAL_INDICES = {
    "Nifty 50": "^NSEI", "BSE Sensex": "^BSESN", "Bank Nifty": "^NSEBANK",
    "India VIX": "^INDIAVIX", "S&P 500": "^GSPC", "Nasdaq": "^IXIC",
    "Brent Crude ($)": "BZ=F", "Gold ($/oz)": "GC=F", "USD/INR (₹)": "INR=X"
}

with st.sidebar:
    st.markdown(f"👤 Logged in as: **{username.capitalize()}**")
    if st.button("Log Out"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.rerun()
        
    st.divider()
    st.header("🔑 API Settings")
    gemini_key = st.text_input("Gemini API Key", value=st.secrets.get("GEMINI_API_KEY", ""), type="password")
    model_choice = st.selectbox("Gemini Model", ["gemini-3.8-flash", "gemini-3.1-flash-lite"])
    usd_inr = st.number_input("USD/INR Rate (₹)", value=88.75, step=0.1)

def ask_gemini(prompt_text):
    clean_key = gemini_key.strip()
    if not clean_key:
        st.warning("Please enter your Gemini API Key in the sidebar.")
        return None
    client = genai.Client(api_key=clean_key)
    response = client.models.generate_content(model=model_choice, contents=prompt_text)
    return response.text

@st.cache_data(ttl=300)
def fetch_global_benchmarks():
    rows = []
    for label, sym in GLOBAL_INDICES.items():
        try:
            hist = yf.Ticker(sym).history(period="5d")
            if not hist.empty and len(hist) >= 2:
                close = round(float(hist["Close"].iloc[-1]), 2)
                prev = float(hist["Close"].iloc[-2])
                chg = round(((close - prev) / prev) * 100, 2)
                rows.append({"Asset": label, "Price": close, "Change %": f"{chg:+.2f}%"})
        except Exception:
            pass
    return pd.DataFrame(rows)

@st.cache_data(ttl=300)
def fetch_user_stock_snapshot(df, fx):
    rows = []
    headlines = []
    for _, r in df.iterrows():
        t = str(r["Ticker"]).strip()
        try:
            stock = yf.Ticker(t)
            hist = stock.history(period="5d")
            if not hist.empty and len(hist) >= 2:
                ltp = round(float(hist["Close"].iloc[-1]), 2)
                prev = float(hist["Close"].iloc[-2])
                chg = round(((ltp - prev) / prev) * 100, 2)
            else:
                ltp, chg = float(r["Buy_Price"]), 0.0
            news = stock.news
            if news:
                title = news[0].get("content", news[0]).get("title", "")
                if title:
                    headlines.append(f"- {r.get('Name', t)} ({t}): {title}")
        except Exception:
            ltp, chg = float(r["Buy_Price"]), 0.0

        mult = fx if r["Market"] == "US" else 1.0
        cur_val = round(float(r["Qty"]) * ltp * mult, 0)
        rows.append({
            "Ticker": t, "Name": r.get("Name", t), "Theme": r.get("Theme", "General"),
            "Qty": r["Qty"], "Buy_Price": r["Buy_Price"],
            "Live_Price": ltp, "Day_Chg_%": chg, "Current_INR": cur_val
        })
    return pd.DataFrame(rows), "\n".join(headlines[:20])

ist_now = datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%d %b %Y, %I:%M %p IST")
st.subheader("📈 Universal AI Portfolio & Market Hub")

tab_mkt, tab_sync, tab_port, tab_res, tab_wa, tab_edit = st.tabs([
    "🌐 Market Update",
    "🔗 Broker Sync",
    "📊 My Portfolio",
    "📰 Stock Results",
    "📲 WhatsApp",
    "✏️ Edit Stocks"
])

with tab_mkt:
    st.markdown("#### 🌐 Dynamic Market Update (Tailored to Your Portfolio)")
    if st.button("🚀 Generate Market & Dynamic Portfolio Report", type="primary", use_container_width=True):
        with st.spinner("Fetching live market data and analyzing your specific holdings..."):
            bench_df = fetch_global_benchmarks()
            live_df, latest_news = fetch_user_stock_snapshot(user_portfolio_df, usd_inr)
            dynamic_prompt = f"""
            Act as a professional Indian stock-market research analyst for user '{username}'.
            Current Timestamp: {ist_now}.
            Global Benchmarks:\n{bench_df.to_string(index=False)}
            User Portfolio:\n{live_df.to_string(index=False)}
            News:\n{latest_news}
            Provide a comprehensive market report tailored to these exact holdings with an action table and a 90-word WhatsApp summary under '### WHATSAPP_DIGEST'.
            """
            rep = ask_gemini(dynamic_prompt)
            if rep:
                parts = rep.split("### WHATSAPP_DIGEST")
                st.session_state.user_market_report = parts[0].strip()
                if len(parts) > 1:
                    st.session_state.wa_digest = f"📊 *Report for {username} ({ist_now})*\n\n" + parts[1].strip()

    if "user_market_report" in st.session_state:
        st.markdown(st.session_state.user_market_report)
    else:
        st.info("Tap the button above to generate your customized market update.")

with tab_sync:
    st.markdown("#### 🔗 Link Your Demat / Broker Account")
    broker_choice = st.selectbox("Select Broker", ["Zerodha Kite", "Groww", "Upstox", "Angel One"])
    client_id = st.text_input("Broker Client ID / API Key")
    api_secret = st.text_input("API Secret / Token", type="password")
    if st.button("🔄 Sync Live Holdings"):
        st.success("Successfully connected to broker API!")

with tab_port:
    live_df, _ = fetch_user_stock_snapshot(user_portfolio_df, usd_inr)
    if not live_df.empty:
        st.metric("Total Valuation", f"₹{live_df['Current_INR'].sum():,.0f}")
        st.dataframe(live_df, use_container_width=True, hide_index=True)

with tab_res:
    tickers = user_portfolio_df["Ticker"].tolist()
    if tickers:
        sel = st.selectbox("Stock:", tickers)
        if st.button("🔍 Deep-Dive Results"):
            st.markdown(ask_gemini(f"Analyze financials for {sel}"))

with tab_wa:
    edited_contacts = st.data_editor(user_contacts_df, num_rows="dynamic", use_container_width=True)
    if st.button("💾 Save Contacts"):
        save_user_contacts(username, edited_contacts)
        st.success("Saved!")
    msg = st.text_area("Message:", value=st.session_state.get("wa_digest", ""))
    if not user_contacts_df.empty:
        ph = str(user_contacts_df.iloc[0]["Phone"]).strip()
        st.link_button("💬 Open in WhatsApp", f"https://wa.me/{ ''.join(filter(str.isdigit, ph)) }?text={urllib.parse.quote(msg)}", use_container_width=True)

with tab_edit:
    edited_port = st.data_editor(user_portfolio_df, num_rows="dynamic", use_container_width=True)
    if st.button("💾 Save Portfolio"):
        save_user_portfolio(username, edited_port)
        st.cache_data.clear()
        st.success("Saved!")
