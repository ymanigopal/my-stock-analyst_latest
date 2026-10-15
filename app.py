import streamlit as st
import pandas as pd
import yfinance as yf
from google import genai
from google.genai import types
from twilio.rest import Client
import json
import os
import urllib.parse
from datetime import datetime

# --- CLEAN MOBILE-FIRST PAGE CONFIG ---
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

# --- SIDEBAR: CLOUD SECRETS OR MANUAL KEY ---
with st.sidebar:
    st.header("🔑 API Settings")
    default_key = st.secrets.get("GEMINI_API_KEY", "") if hasattr(st, "secrets") else ""
    gemini_key = st.text_input("Gemini API Key", value=default_key, type="password")
    model_choice = st.selectbox(
        "Latest Gemini Model",
        ["gemini-2.5-flash", "gemini-2.5-pro"]
    )
    use_search = st.checkbox("Enable Live Google Search Grounding", value=True)
    usd_inr = st.number_input("USD/INR Rate (₹)", value=88.75, step=0.1)

    st.divider()
    st.subheader("Optional Twilio Auto-Sender")
    twilio_sid = st.text_input("Twilio SID", value=st.secrets.get("TWILIO_SID", "") if hasattr(st, "secrets") else "")
    twilio_token = st.text_input("Twilio Auth Token", value=st.secrets.get("TWILIO_TOKEN", "") if hasattr(st, "secrets") else "", type="password")
    twilio_from = st.text_input("Twilio WhatsApp/SMS From", value="whatsapp:+14155238886")

# --- HELPER: CALL LATEST GEMINI SDK WITH GOOGLE SEARCH GROUNDING ---
def ask_gemini(prompt_text):
    if not gemini_key:
        st.warning("Tap the `>` arrow at the top-left to paste your Gemini API Key first!")
        return None
    client = genai.Client(api_key=gemini_key)
    config = types.GenerateContentConfig(
        tools=[{"google_search": {}}] if use_search else None,
        temperature=0.2
    )
    response = client.models.generate_content(
        model=model_choice,
        contents=prompt_text,
        config=config
    )
    return response.text

@st.cache_data(ttl=300)
def fetch_live_snapshot(df, fx):
    rows = []
    for _, r in df.iterrows():
        t = str(r["Ticker"]).strip()
        try:
            hist = yf.Ticker(t).history(period="5d")
            if not hist.empty and len(hist) >= 2:
                ltp = round(float(hist["Close"].iloc[-1]), 2)
                prev = float(hist["Close"].iloc[-2])
                chg = round(((ltp - prev) / prev) * 100, 2)
            else:
                ltp, chg = float(r["Buy_Price"]), 0.0
        except Exception:
            ltp, chg = float(r["Buy_Price"]), 0.0
        mult = fx if r["Market"] == "US" else 1.0
        cur_val = round(float(r["Qty"]) * ltp * mult, 0)
        rows.append({
            "Ticker": t, "Name": r["Name"], "Theme": r["Theme"],
            "Qty": r["Qty"], "Buy_Price": r["Buy_Price"],
            "Live_Price": ltp, "Day_Chg_%": chg, "Current_INR": cur_val
        })
    return pd.DataFrame(rows)

# --- APP HEADER & CLEAN 4-TAB NAVIGATION ---
st.subheader("🧠 My Personal Stock Market Analyst")
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Daily Analysis",
    "📰 Stock Results",
    "📲 WhatsApp / SMS",
    "✏️ Edit Portfolio"
])

# ==============================================================================
# TAB 1: PURE ANALYSIS VIEW (SHOWS ONLY YOUR ANALYSIS)
# ==============================================================================
with tab1:
    user_change_note = st.text_input(
        "Mention any change in your portfolio or ask a question (optional):",
        placeholder="e.g., Added 30 shares of KAYNES today. Check my risk exposure."
    )

    if st.button("⚡ Generate Today's Live Portfolio Analysis", type="primary", use_container_width=True):
        with st.spinner(f"Running {model_choice} with live market grounding across your 23 stocks..."):
            live_df = fetch_live_snapshot(st.session_state.portfolio, usd_inr)
            prompt = f"""
            Act as my personal stock market analyst. Investment horizon: 3-5 years. Risk tolerance: High.
            Today's Date: {datetime.now().strftime('%d %b %Y')}
            My current portfolio with live prices and INR values:
            {live_df.to_markdown(index=False)}

            User Portfolio Update / Note: {user_change_note}

            Provide a clean, high-signal daily executive report with these exact sections:
            1. Overall India & US Market Summary + Macro Drivers (Crude, USD/INR, FII flows).
            2. Important News Affecting My Holdings Today.
            3. Stock-by-Stock Action Table (Columns: Stock | Live Price & 1D % | Status (Positive/Neutral/Negative) | Action (Hold/Review/Consider Reducing) | Fundamental Trigger).
            4. Portfolio Concentration & Overlapping Theme Risk (Semiconductors/EMS, Defence, AI, Crypto proxy).
            5. Top 3 Immediate Risks & Upcoming Events to Watch.
            6. Changes to Long-Term Investment Thesis.
            7. At the very end under '### WHATSAPP_DIGEST', write a 90-word summary formatted for my daily WhatsApp alert.
            """
            try:
                full_report = ask_gemini(prompt)
                if full_report:
                    parts = full_report.split("### WHATSAPP_DIGEST")
                    st.session_state.clean_analysis = parts[0].strip()
                    if len(parts) > 1:
                        st.session_state.wa_digest = f"📊 *Daily AI Portfolio Update ({datetime.now().strftime('%d %b')})*\n\n" + parts[1].strip()
            except Exception as e:
                st.error(f"Error: {e}")

    if "clean_analysis" in st.session_state:
        st.markdown(st.session_state.clean_analysis)
    else:
        st.info("Tap **Generate Today's Live Portfolio Analysis** above to view your clean daily report.")

# ==============================================================================
# TAB 2: STOCK RESULTS & LATEST UPDATES
# ==============================================================================
with tab2:
    st.markdown("#### 📰 Quarterly Earnings, Order Books & Filings")
    tickers_list = st.session_state.portfolio["Ticker"].tolist()
    selected_stock = st.selectbox("Choose a Portfolio Stock:", tickers_list)

    c1, c2 = st.columns(2)
    with c1:
        check_one = st.button("🔍 Check Selected Stock", type="primary", use_container_width=True)
    with c2:
        check_all = st.button("⚡ Scan All 23 Results", use_container_width=True)

    if check_one or check_all:
        with st.spinner("Searching latest NSE/BSE/SEC filings, quarterly results, and order wins..."):
            q_prompt = (
                f"Summarize the latest quarterly financial results (revenue growth, profit, margins), order book updates, and key announcements across all my holdings: {', '.join(tickers_list)}."
                if check_all else
                f"Provide a deep-dive on the latest quarterly results, revenue growth, profit margins, debt, cash flow, recent order wins, and 3-5 year thesis check for {selected_stock}."
            )
            try:
                res_text = ask_gemini(q_prompt)
                if res_text:
                    st.markdown(res_text)
            except Exception as e:
                st.error(f"Error: {e}")

# ==============================================================================
# TAB 3: WHATSAPP & SMS REMINDER MANAGER (ADD/CHANGE EXTRA NUMBERS)
# ==============================================================================
with tab3:
    st.markdown("#### 📲 Manage Phone Numbers for Daily Updates")
    st.caption("Tap any cell to change a number or tap the `+` row at the bottom to add extra phone numbers.")

    edited_contacts = st.data_editor(
        pd.DataFrame(st.session_state.contacts),
        num_rows="dynamic",
        use_container_width=True,
        key="contacts_editor"
    )

    if st.button("💾 Save Phone Numbers", use_container_width=True):
        st.session_state.contacts = edited_contacts.to_dict(orient="records")
        save_json(CONTACTS_FILE, st.session_state.contacts)
        st.success("Phone numbers saved!")

    st.divider()
    default_wa = st.session_state.get(
        "wa_digest",
        f"📊 *Portfolio Reminder ({datetime.now().strftime('%d %b %Y')})*\nGenerate today's analysis in Tab 1 to auto-fill AI insights here."
    )
    msg_box = st.text_area("Daily Message to Send:", value=default_wa, height=150)

    # Instant 1-Tap Mobile WhatsApp & SMS Links (Zero Twilio Required)
    active_nums = [str(c["Phone"]).strip() for c in st.session_state.contacts if c.get("Active", True)]
    if active_nums:
        encoded_msg = urllib.parse.quote(msg_box)
        first_clean = "".join(filter(str.isdigit, active_nums[0]))
        all_sms_nums = ",".join(active_nums)

        col_wa, col_sms = st.columns(2)
        with col_wa:
            st.link_button("💬 Open in WhatsApp App", f"https://wa.me/{first_clean}?text={encoded_msg}", use_container_width=True)
        with col_sms:
            st.link_button("📩 Open in Phone SMS App", f"sms:{all_sms_nums}?body={encoded_msg}", use_container_width=True)

    if st.button("🚀 Auto-Broadcast via Twilio API to All Active Numbers", use_container_width=True):
        if not twilio_sid or not twilio_token:
            st.warning("Add your Twilio SID & Token in the left sidebar, or use the instant WhatsApp/SMS buttons above!")
        else:
            client_tw = Client(twilio_sid, twilio_token)
            for num in active_nums:
                try:
                    to_target = f"whatsapp:{num}" if "whatsapp:" in twilio_from else num
                    m = client_tw.messages.create(body=msg_box, from_=twilio_from, to=to_target)
                    st.success(f"Sent to {num} (SID: {m.sid})")
                except Exception as e:
                    st.error(f"Failed for {num}: {e}")

# ==============================================================================
# TAB 4: EDIT PORTFOLIO HOLDINGS (HIDDEN FROM MAIN ANALYSIS VIEW)
# ==============================================================================
with tab4:
    st.markdown("#### ✏️ Update Your Portfolio Quantities & Buy Prices")
    st.caption("Whenever you buy or sell a stock, update it here and tap **Save Portfolio**. Tab 1 will automatically analyze your updated holdings.")

    edited_port = st.data_editor(
        st.session_state.portfolio,
        num_rows="dynamic",
        use_container_width=True,
        key="port_editor"
    )

    if st.button("💾 Save Portfolio Changes", type="primary", use_container_width=True):
        st.session_state.portfolio = edited_port
        save_json(PORTFOLIO_FILE, edited_port.to_dict(orient="records"))
        st.cache_data.clear()
        st.success("✅ Portfolio updated! Switch to Tab 1 to run your fresh analysis.")
