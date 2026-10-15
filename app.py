import streamlit as st
import pandas as pd
import yfinance as yf
from google import genai
from twilio.rest import Client
import json
import os
import urllib.parse
from datetime import datetime
import pytz

st.set_page_config(
    page_title="My AI Stock Analyst",
    page_icon="🧠",
    layout="centered",
    initial_sidebar_state="collapsed"
)

PORTFOLIO_FILE = "my_portfolio.json"
CONTACTS_FILE = "phone_numbers.json"

DEFAULT_PORTFOLIO = [
    {"Ticker": "AVANTEL.NS", "Name": "Avantel", "Market": "IN", "Theme": "Defence", "Qty": 100, "Buy_Price": 150.0},
    {"Ticker": "BDL.NS", "Name": "Bharat Dynamics", "Market": "IN", "Theme": "Defence", "Qty": 50, "Buy_Price": 1200.0},
    {"Ticker": "CAMS.NS", "Name": "CAMS", "Market": "IN", "Theme": "Fin Services", "Qty": 20, "Buy_Price": 3500.0},
    {"Ticker": "CDSL.NS", "Name": "CDSL", "Market": "IN", "Theme": "Fin Services", "Qty": 50, "Buy_Price": 1400.0},
    {"Ticker": "KAYNES.NS", "Name": "Kaynes Tech", "Market": "IN", "Theme": "Semicon & EMS", "Qty": 15, "Buy_Price": 4200.0},
    {"Ticker": "KPITTECH.NS", "Name": "KPIT Tech", "Market": "IN", "Theme": "Auto Tech", "Qty": 40, "Buy_Price": 1500.0},
    {"Ticker": "LEMONTREE.NS", "Name": "Lemon Tree", "Market": "IN", "Theme": "Hotels", "Qty": 200, "Buy_Price": 130.0},
    {"Ticker": "MOSCHIP.NS", "Name": "MosChip Tech", "Market": "IN", "Theme": "Semicon & EMS", "Qty": 150, "Buy_Price": 210.0},
    {"Ticker": "OLAELEC.NS", "Name": "Ola Electric", "Market": "IN", "Theme": "EV / Auto", "Qty": 200, "Buy_Price": 95.0},
    {"Ticker": "PGEL.NS", "Name": "PG Electroplast", "Market": "IN", "Theme": "Semicon & EMS", "Qty": 80, "Buy_Price": 600.0},
    {"Ticker": "TATACAP.NS", "Name": "Tata Capital", "Market": "IN", "Theme": "NBFC / Fin", "Qty": 100, "Buy_Price": 350.0},
    {"Ticker": "VAML.NS", "Name": "Vedanta Aluminium", "Market": "IN", "Theme": "Commodities", "Qty": 100, "Buy_Price": 280.0},
    {"Ticker": "VBL.NS", "Name": "Varun Beverages", "Market": "IN", "Theme": "Consumer", "Qty": 60, "Buy_Price": 600.0},
    {"Ticker": "VEDL.NS", "Name": "Vedanta Ltd", "Market": "IN", "Theme": "Commodities", "Qty": 100, "Buy_Price": 450.0},
    {"Ticker": "DIXON.NS", "Name": "Dixon Tech", "Market": "IN", "Theme": "Semicon & EMS", "Qty": 10, "Buy_Price": 12000.0},
    {"Ticker": "EIHOTEL.NS", "Name": "EIH Oberoi", "Market": "IN", "Theme": "Hotels", "Qty": 80, "Buy_Price": 380.0},
    {"Ticker": "ETERNAL.NS", "Name": "Eternal (Zomato)", "Market": "IN", "Theme": "Quick Commerce", "Qty": 250, "Buy_Price": 240.0},
    {"Ticker": "HAL.NS", "Name": "HAL", "Market": "IN", "Theme": "Defence", "Qty": 25, "Buy_Price": 4200.0},
    {"Ticker": "INDIGO.NS", "Name": "IndiGo", "Market": "IN", "Theme": "Aviation", "Qty": 15, "Buy_Price": 4300.0},
    {"Ticker": "KALYANKJIL.NS", "Name": "Kalyan Jewellers", "Market": "IN", "Theme": "Consumer", "Qty": 60, "Buy_Price": 550.0},
    {"Ticker": "MSTR", "Name": "Strategy Inc", "Market": "US", "Theme": "Crypto Proxy", "Qty": 10, "Buy_Price": 180.0},
    {"Ticker": "ACN", "Name": "Accenture", "Market": "US", "Theme": "IT / AI Services", "Qty": 8, "Buy_Price": 330.0},
    {"Ticker": "NVDA", "Name": "NVIDIA", "Market": "US", "Theme": "Semicon & AI", "Qty": 20, "Buy_Price": 120.0}
]

GLOBAL_INDICES = {
    "Nifty 50": "^NSEI",
    "BSE Sensex": "^BSESN",
    "Bank Nifty": "^NSEBANK",
    "India VIX": "^INDIAVIX",
    "S&P 500": "^GSPC",
    "Nasdaq": "^IXIC",
    "Dow Jones": "^DJI",
    "Brent Crude ($)": "BZ=F",
    "Gold ($/oz)": "GC=F",
    "USD/INR (₹)": "INR=X"
}

def load_json(file_path, default_data):
    if os.path.exists(file_path):
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except Exception:
            return default_data
    return default_data

def save_json(file_path, data):
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)

if "portfolio" not in st.session_state:
    st.session_state.portfolio = pd.DataFrame(load_json(PORTFOLIO_FILE, DEFAULT_PORTFOLIO))

if "contacts" not in st.session_state:
    st.session_state.contacts = load_json(CONTACTS_FILE, [
        {"Name": "My Primary Number", "Phone": "+919876543210", "Active": True}
    ])

with st.sidebar:
    st.header("🔑 API Settings")
    default_key = st.secrets.get("GEMINI_API_KEY", "") if hasattr(st, "secrets") else ""
    gemini_key = st.text_input("Gemini API Key", value=default_key, type="password")
    model_choice = st.selectbox(
        "Gemini Model",
        ["gemini-3.8-flash", "gemini-3.1-flash-lite"]
    )
    usd_inr = st.number_input("USD/INR Rate (₹)", value=88.75, step=0.1)

    st.divider()
    st.subheader("Optional Twilio Auto-Sender")
    twilio_sid = st.text_input("Twilio SID", value=st.secrets.get("TWILIO_SID", "") if hasattr(st, "secrets") else "")
    twilio_token = st.text_input("Twilio Auth Token", value=st.secrets.get("TWILIO_TOKEN", "") if hasattr(st, "secrets") else "", type="password")
    twilio_from = st.text_input("Twilio WhatsApp/SMS From", value="whatsapp:+14155238886")

def ask_gemini(prompt_text):
    clean_key = gemini_key.strip()
    if not clean_key:
        st.warning("Tap the `>` arrow at the top-left to paste your Gemini API Key first!")
        return None
    client = genai.Client(api_key=clean_key)
    response = client.models.generate_content(
        model=model_choice,
        contents=prompt_text
    )
    return response.text

@st.cache_data(ttl=300)
def fetch_global_market_benchmarks():
    rows = []
    for label, sym in GLOBAL_INDICES.items():
        try:
            hist = yf.Ticker(sym).history(period="5d")
            if not hist.empty and len(hist) >= 2:
                close = round(float(hist["Close"].iloc[-1]), 2)
                prev = float(hist["Close"].iloc[-2])
                high = round(float(hist["High"].iloc[-1]), 2)
                low = round(float(hist["Low"].iloc[-1]), 2)
                abs_chg = round(close - prev, 2)
                pct_chg = round((abs_chg / prev) * 100, 2)
                rows.append({
                    "Index / Asset": label, "Last Price": close,
                    "Change": f"{abs_chg:+.2f}", "Change %": f"{pct_chg:+.2f}%",
                    "Intraday High": high, "Intraday Low": low
                })
        except Exception:
            pass
    return pd.DataFrame(rows)

@st.cache_data(ttl=300)
def fetch_live_snapshot_and_news(df, fx):
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
                first_item = news[0].get("content", news[0])
                title = first_item.get("title", "")
                if title:
                    headlines.append(f"- {r['Name']} ({t}): {title}")
        except Exception:
            ltp, chg = float(r["Buy_Price"]), 0.0

        mult = fx if r["Market"] == "US" else 1.0
        cur_val = round(float(r["Qty"]) * ltp * mult, 0)
        rows.append({
            "Ticker": t, "Name": r["Name"], "Theme": r["Theme"],
            "Qty": r["Qty"], "Buy_Price": r["Buy_Price"],
            "Live_Price": ltp, "Day_Chg_%": chg, "Current_INR": cur_val
        })
    return pd.DataFrame(rows), "\n".join(headlines[:20])

ist_now = datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%d %b %Y, %I:%M %p IST")
st.subheader("🧠 Personal Stock Market Research Hub")
st.caption(f"Live Data Timestamp: {ist_now}")

# --- 5 TABS INCLUDING DEDICATED DAILY SHARE MARKET UPDATE TAB ---
tab_mkt, tab_port, tab_res, tab_wa, tab_edit = st.tabs([
    "🌐 Market Update",
    "📊 My Portfolio",
    "📰 Stock Results",
    "📲 WhatsApp/SMS",
    "✏️ Edit Stocks"
])

# ==============================================================================
# TAB 1: DEDICATED DAILY SHARE MARKET UPDATE (9-SECTION INSTITUTIONAL REPORT)
# ==============================================================================
with tab_mkt:
    st.markdown("#### 🌐 Daily Indian & Global Share Market Research Report")
    if st.button("🚀 Generate Full 9-Point Market & Portfolio Report for Today", type="primary", use_container_width=True):
        with st.spinner("Fetching Sensex, Nifty, VIX, Global Macros & Portfolio News..."):
            bench_df = fetch_global_market_benchmarks()
            live_df, latest_news = fetch_live_snapshot_and_news(st.session_state.portfolio, usd_inr)

            full_prompt = f"""
            Act as my professional Indian stock-market research analyst.
            Current Timestamp: {ist_now}. Investment Horizon: 3-5 Years. Risk Tolerance: High.

            1. VERIFIED LIVE / CLOSING BENCHMARK DATA (Sensex, Nifty, Bank Nifty, VIX, US Markets, Crude, Gold, USD/INR):
            {bench_df.to_string(index=False)}

            2. MY 23 PORTFOLIO HOLDINGS (LIVE PRICES & 1-DAY CHANGE):
            {live_df.to_string(index=False)}

            3. LATEST NEWS HEADLINES ACROSS MY HOLDINGS:
            {latest_news if latest_news else "No breaking feed headlines."}

            Prepare a comprehensive, evidence-based market report with an Executive Summary followed by:
            1. Indian Market Overview (Sensex, Nifty 50, Bank Nifty, India VIX, intraday highs/lows, technical support/resistance).
            2. Global Markets & Macroeconomic Developments (US S&P 500, Nasdaq, Dow, Brent crude, Gold, USD/INR, Fed/RBI cues, AI/Semicon trends).
            3. Sector-Wise Analysis (Strongest/weakest sectors and catalysts).
            4. My Personal Portfolio Analysis (Stock-by-stock Action Table with Price, 1D %, Thesis Impact, Support/Resistance, and Hold/Accumulate/Reduce/Review recommendation).
            5. Portfolio Risk Assessment (Concentration, crude/rate/INR sensitivity).
            6. Tomorrow's Market Outlook (Bullish, Base Case, and Bearish scenarios with key index triggers).
            7. Actionable Conclusion (5 top developments, 3 biggest risks, 5 stocks/sectors to watch, action checklist).
            8. At the very end under '### WHATSAPP_DIGEST', write a 90-word summary for my daily WhatsApp alert.
            """
            try:
                rep = ask_gemini(full_prompt)
                if rep:
                    parts = rep.split("### WHATSAPP_DIGEST")
                    st.session_state.daily_market_report = parts[0].strip()
                    if len(parts) > 1:
                        st.session_state.wa_digest = f"📊 *Market & Portfolio Report ({ist_now})*\n\n" + parts[1].strip()
            except Exception as e:
                st.error(f"Error: {e}")

    if "daily_market_report" in st.session_state:
        st.markdown(st.session_state.daily_market_report)
    else:
        st.info("Tap the button above to run today's complete Indian & Global Share Market Update.")

# ==============================================================================
# TAB 2: QUICK PORTFOLIO ANALYSIS
# ==============================================================================
with tab_port:
    user_change_note = st.text_input("Mention any recent trade or specific portfolio question:")
    if st.button("⚡ Analyze Only My Portfolio Holdings", type="primary", use_container_width=True):
        with st.spinner("Analyzing your 23 stocks..."):
            live_df, latest_news = fetch_live_snapshot_and_news(st.session_state.portfolio, usd_inr)
            p_prompt = f"""
            Timestamp: {ist_now}. Horizon: 3-5 yrs.
            Portfolio Data:\n{live_df.to_string(index=False)}
            Recent News:\n{latest_news}
            User Note: {user_change_note}
            Provide a focused Portfolio Concentration Audit, Stock-by-Stock Action Table, and Top 3 Portfolio Risks.
            """
            res = ask_gemini(p_prompt)
            if res:
                st.session_state.clean_analysis = res
    if "clean_analysis" in st.session_state:
        st.markdown(st.session_state.clean_analysis)

# ==============================================================================
# TAB 3: STOCK RESULTS & QUARTERLY FINANCIALS
# ==============================================================================
with tab_res:
    tickers_list = st.session_state.portfolio["Ticker"].tolist()
    selected_stock = st.selectbox("Choose a Portfolio Stock:", tickers_list)
    if st.button("🔍 Deep-Dive Selected Stock Results & News", type="primary", use_container_width=True):
        with st.spinner(f"Pulling quarterly financials & news for {selected_stock}..."):
            st_obj = yf.Ticker(selected_stock)
            q_stmt = st_obj.quarterly_income_stmt
            q_str = q_stmt.to_string() if (q_stmt is not None and not q_stmt.empty) else "Not in feed"
            s_news = st_obj.news
            news_titles = [n.get("content", n).get("title", "") for n in s_news[:5]] if s_news else []
            q_prompt = f"Analyze {selected_stock} quarterly results, margins, order book, and 3-5 yr thesis using:\nFinancials:\n{q_str[:3000]}\nNews:\n{news_titles}"
            res_text = ask_gemini(q_prompt)
            if res_text:
                st.markdown(res_text)

# ==============================================================================
# TAB 4: WHATSAPP & SMS REMINDER MANAGER
# ==============================================================================
with tab_wa:
    edited_contacts = st.data_editor(pd.DataFrame(st.session_state.contacts), num_rows="dynamic", use_container_width=True)
    if st.button("💾 Save Phone Numbers", use_container_width=True):
        st.session_state.contacts = edited_contacts.to_dict(orient="records")
        save_json(CONTACTS_FILE, st.session_state.contacts)
        st.success("Phone numbers saved!")

    default_wa = st.session_state.get("wa_digest", f"📊 *Portfolio Update ({ist_now})*")
    msg_box = st.text_area("Daily Message to Send:", value=default_wa, height=150)

    active_nums = [str(c["Phone"]).strip() for c in st.session_state.contacts if c.get("Active", True)]
    if active_nums:
        encoded_msg = urllib.parse.quote(msg_box)
        first_clean = "".join(filter(str.isdigit, active_nums[0]))
        all_sms_nums = ",".join(active_nums)
        c_wa, c_sms = st.columns(2)
        with c_wa:
            st.link_button("💬 Open in WhatsApp App", f"https://wa.me/{first_clean}?text={encoded_msg}", use_container_width=True)
        with c_sms:
            st.link_button("📩 Open in Phone SMS App", f"sms:{all_sms_nums}?body={encoded_msg}", use_container_width=True)

# ==============================================================================
# TAB 5: EDIT PORTFOLIO HOLDINGS
# ==============================================================================
with tab_edit:
    edited_port = st.data_editor(st.session_state.portfolio, num_rows="dynamic", use_container_width=True)
    if st.button("💾 Save Portfolio Changes", type="primary", use_container_width=True):
        st.session_state.portfolio = edited_port
        save_json(PORTFOLIO_FILE, edited_port.to_dict(orient="records"))
        st.cache_data.clear()
        st.success("✅ Portfolio updated!")
