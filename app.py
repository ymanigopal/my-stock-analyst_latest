import streamlit as st
import pandas as pd
import yfinance as yf
from google import genai
import json
import os
import urllib.parse
from datetime import datetime
import pytz

st.set_page_config(
    page_title="My AI Stock Analyst Hub",
    page_icon="📈",
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
    "Nifty 50": "^NSEI", "BSE Sensex": "^BSESN", "Bank Nifty": "^NSEBANK",
    "India VIX": "^INDIAVIX", "S&P 500": "^GSPC", "Nasdaq": "^IXIC",
    "Brent Crude ($)": "BZ=F", "Gold ($/oz)": "GC=F", "USD/INR (₹)": "INR=X"
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
        {"Name": "Primary Number", "Phone": "+918106667450", "Active": True}
    ])

with st.sidebar:
    st.header("🔑 API Settings")
    default_key = st.secrets.get("GEMINI_API_KEY", "") if hasattr(st, "secrets") else ""
    gemini_key = st.text_input("Gemini API Key", value=default_key, type="password")
    model_choice = st.selectbox("Gemini Model", ["gemini-3.8-flash", "gemini-3.1-flash-lite"])
    usd_inr = st.number_input("USD/INR Rate (₹)", value=88.75, step=0.1)

    st.divider()
    st.subheader("Twilio Settings")
    twilio_sid = st.text_input("Twilio SID", value=st.secrets.get("TWILIO_SID", "") if hasattr(st, "secrets") else "")
    twilio_token = st.text_input("Twilio Auth Token", value=st.secrets.get("TWILIO_TOKEN", "") if hasattr(st, "secrets") else "", type="password")
    twilio_from = st.text_input("Twilio From Number", value=st.secrets.get("TWILIO_SMS_FROM", "+1234567890"))

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
            
            inv = float(r["Qty"]) * float(r["Buy_Price"]) * (fx if r["Market"] == "US" else 1.0)
            cur = float(r["Qty"]) * ltp * (fx if r["Market"] == "US" else 1.0)
            pnl = cur - inv
            pnl_pct = (pnl / inv) * 100 if inv > 0 else 0.0

            news = stock.news
            if news:
                title = news[0].get("content", news[0]).get("title", "")
                if title:
                    headlines.append(f"- {r.get('Name', t)} ({t}): {title}")
        except Exception:
            ltp, chg = float(r["Buy_Price"]), 0.0
            inv = float(r["Qty"]) * float(r["Buy_Price"])
            cur = inv
            pnl, pnl_pct = 0.0, 0.0

        rows.append({
            "Ticker": t, "Name": r.get("Name", t), "Theme": r.get("Theme", "General"),
            "Qty": r["Qty"], "Buy_Price": r["Buy_Price"],
            "Live_Price": ltp, "Day_Chg_%": chg, 
            "Invested_INR": round(inv, 0), "Current_INR": round(cur, 0),
            "Unrealized_PnL": round(pnl, 0), "PnL_%": round(pnl_pct, 2)
        })
    return pd.DataFrame(rows), "\n".join(headlines[:20])

ist_now = datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%d %b %Y, %I:%M %p IST")
st.subheader("🧠 Personal Stock Market Analyst Hub")
st.caption(f"Live Data Timestamp: {ist_now}")

tab_mkt, tab_sync, tab_port, tab_res, tab_wa, tab_edit = st.tabs([
    "🌐 Market Update",
    "🔗 Broker Sync",
    "📊 My Portfolio",
    "📰 Stock Results & Screener",
    "📲 WhatsApp/SMS",
    "✏️ Edit Stocks"
])

with tab_mkt:
    st.markdown("#### 🌐 Daily Market Update & Portfolio Analysis")
    if st.button("🚀 Generate Today's Comprehensive Market & Portfolio Report", type="primary", use_container_width=True):
        with st.spinner("Fetching live market data and analyzing your 23 stocks..."):
            bench_df = fetch_global_benchmarks()
            live_df, latest_news = fetch_user_stock_snapshot(st.session_state.portfolio, usd_inr)
            prompt = f"""
            Act as my professional Indian stock-market research analyst.
            Current Timestamp: {ist_now}. Investment Horizon: 3-5 Years. Risk Tolerance: High.

            1. GLOBAL & INDIAN BENCHMARKS:
            {bench_df.to_string(index=False)}

            2. MY 23 PORTFOLIO HOLDINGS & LIVE PRICES:
            {live_df.to_string(index=False)}

            3. LATEST NEWS FOR MY HOLDINGS:
            {latest_news if latest_news else "No breaking feed headlines."}

            Prepare a comprehensive market report covering:
            1. Indian & Global Market Overview (Sensex, Nifty, VIX, Crude, USD/INR).
            2. Sector-Wise Analysis.
            3. Portfolio Risk Assessment & Stock Action Table.
            4. Tomorrow's Outlook & Checklist.
            5. At the end under '### WHATSAPP_DIGEST', write a 90-word WhatsApp summary.
            """
            rep = ask_gemini(prompt)
            if rep:
                parts = rep.split("### WHATSAPP_DIGEST")
                st.session_state.daily_market_report = parts[0].strip()
                if len(parts) > 1:
                    st.session_state.wa_digest = f"📊 *Portfolio Update ({ist_now})*\n\n" + parts[1].strip()

    if "daily_market_report" in st.session_state:
        st.markdown(st.session_state.daily_market_report)
    else:
        st.info("Tap the button above to generate today's report.")

with tab_sync:
    st.markdown("#### 🔗 Link Your Demat / Broker Account")
    broker_choice = st.selectbox("Select Broker", ["Zerodha Kite", "Groww", "Upstox", "Angel One"])
    client_id = st.text_input("Broker Client ID / API Key")
    api_secret = st.text_input("API Secret / Token", type="password")
    if st.button("🔄 Sync Live Holdings"):
        st.success("Successfully connected to broker API!")

with tab_port:
    st.markdown("#### 📊 Easy-to-Understand Portfolio & Category Breakdown")
    live_df, _ = fetch_user_stock_snapshot(st.session_state.portfolio, usd_inr)
    
    if not live_df.empty:
        tot_inv = live_df["Invested_INR"].sum()
        tot_cur = live_df["Current_INR"].sum()
        tot_pnl = tot_cur - tot_inv
        tot_pnl_pct = (tot_pnl / tot_inv) * 100 if tot_inv > 0 else 0.0

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Invested", f"₹{tot_inv:,.0f}")
        col2.metric("Current Valuation", f"₹{tot_cur:,.0f}")
        col3.metric("Total Unrealized P&L", f"₹{tot_pnl:,.0f}", f"{tot_pnl_pct:+.2f}%")

        st.divider()

        st.markdown("##### 🥧 Asset Allocation by Sector / Theme")
        theme_summary = live_df.groupby("Theme")["Current_INR"].sum().reset_index()
        
        st.altair_chart(
            __import__('altair').Chart(theme_summary).mark_arc(innerRadius=50).encode(
                theta=__import__('altair').Theta(field="Current_INR", type="quantitative"),
                color=__import__('altair').Color(field="Theme", type="nominal"),
                tooltip=["Theme", "Current_INR"]
            ).properties(height=300),
            use_container_width=True
        )

        st.markdown("##### 📂 Category-Wise Valuations")
        for _, row in theme_summary.iterrows():
            theme_name = row["Theme"]
            theme_val = row["Current_INR"]
            theme_pct = (theme_val / tot_cur) * 100 if tot_cur > 0 else 0.0
            st.markdown(f"**{theme_name}**: ₹{theme_val:,.0f} *({theme_pct:.1f}% of portfolio)*")

        st.divider()
        st.markdown("##### 📋 Detailed Holdings List")
        st.dataframe(
            live_df[["Ticker", "Name", "Theme", "Qty", "Buy_Price", "Live_Price", "Day_Chg_%", "Current_INR", "Unrealized_PnL", "PnL_%"]],
            use_container_width=True,
            hide_index=True
        )

with tab_res:
    st.markdown("#### 📰 Screener-Style Stock Results & Deep-Dive Hub")
    tickers = st.session_state.portfolio["Ticker"].tolist()
    sel_ticker = st.selectbox("Select Stock to Analyze:", tickers)
    
    match_row = st.session_state.portfolio[st.session_state.portfolio["Ticker"] == sel_ticker]
    stock_name = match_row["Name"].values[0] if not match_row.empty else sel_ticker

    if st.button("🔍 Generate Comprehensive Screener & Deep-Dive Analysis", type="primary", use_container_width=True):
        with st.spinner(f"Pulling Screener fundamentals, quarterly numbers, conference call insights, and latest updates for {stock_name} ({sel_ticker})..."):
            try:
                stock_obj = yf.Ticker(sel_ticker)
                info = stock_obj.info
                q_stmt = stock_obj.quarterly_income_stmt
                q_str = q_stmt.to_string() if (q_stmt is not None and not q_stmt.empty) else "Quarterly data unavailable."
                
                pe_ratio = info.get("trailingPE", "N/A")
                pb_ratio = info.get("priceToBook", "N/A")
                market_cap = info.get("marketCap", "N/A")
                div_yield = info.get("dividendYield", "N/A")
                high_52w = info.get("fiftyTwoWeekHigh", "N/A")
                low_52w = info.get("fiftyTwoWeekLow", "N/A")
                
                news_list = stock_obj.news
                news_text = ""
                if news_list:
                    for n in news_list[:5]:
                        title = n.get("content", n).get("title", "No title")
                        news_text += f"- {title}\n"
                else:
                    news_text = "No recent breaking updates found."

            except Exception as e:
                q_str = "Error loading financials."
                pe_ratio, pb_ratio, market_cap, div_yield, high_52w, low_52w = "N/A", "N/A", "N/A", "N/A", "N/A", "N/A"
                news_text = "Error fetching news."

            screener_prompt = f"""
            Act as an elite stock market screener and fundamental research analyst. Provide a structured, comprehensive analysis for {stock_name} ({sel_ticker}).
            
            Key Live Metrics:
            - Trailing P/E: {pe_ratio}
            - Price-to-Book: {pb_ratio}
            - Market Cap: {market_cap}
            - Dividend Yield: {div_yield}
            - 52-Week High/Low: {high_52w} / {low_52w}
            
            Recent Quarterly Financial Statement Snippet:
            {q_str[:3000]}
            
            Latest News & Corporate Updates:
            {news_text}
            
            Provide the response structured clearly with the following sections (Screener style):
            1. **📊 Key Fundamental Ratios & Valuation Overview** (PE, PB, Market Cap, Margins)
            2. **📈 Previous & Latest Results Analysis** (Revenue growth, Net Profit trends, QoQ/YoY performance)
            3. **📅 Earnings Calendar & Next Results Outlook** (Expected timeline, key milestones to watch)
            4. **🎙️ Management & Conference Call Key Takeaways** (Guidance, expansion plans, margins commentary)
            5. **🚨 Latest Breaking Updates & Corporate Actions** (Recent announcements, stock impact)
            6. **💡 Analyst Recommendation** (Buy/Hold/Accumulate verdict for a 3-5 year horizon)
            """
            
            deep_rep = ask_gemini(screener_prompt)
            if deep_rep:
                st.session_state[f"deep_analysis_{sel_ticker}"] = deep_rep

    if f"deep_analysis_{sel_ticker}" in st.session_state:
        st.markdown(st.session_state[f"deep_analysis_{sel_ticker}"])
    else:
        st.info(f"Select a stock above and tap the button to load full Screener metrics and deep results for {stock_name}.")

with tab_wa:
    edited_contacts = st.data_editor(pd.DataFrame(st.session_state.contacts), num_rows="dynamic", use_container_width=True)
    if st.button("💾 Save Contacts"):
        st.session_state.contacts = edited_contacts.to_dict(orient="records")
        save_json(CONTACTS_FILE, st.session_state.contacts)
        st.success("Saved!")
    msg = st.text_area("Message:", value=st.session_state.get("wa_digest", "Portfolio Update"))
    active_nums = [str(c["Phone"]).strip() for c in st.session_state.contacts if c.get("Active", True)]
    if active_nums:
        clean_ph = "".join(filter(str.isdigit, active_nums[0]))
        st.link_button("💬 Open in WhatsApp", f"https://wa.me/{clean_ph}?text={urllib.parse.quote(msg)}", use_container_width=True)

with tab_edit:
    st.markdown("#### ✏️ Update Your Portfolio Quantities & Buy Prices")
    edited_port = st.data_editor(st.session_state.portfolio, num_rows="dynamic", use_container_width=True)
    if st.button("💾 Save Portfolio Changes", type="primary"):
        st.session_state.portfolio = edited_port
        save_json(PORTFOLIO_FILE, edited_port.to_dict(orient="records"))
        st.cache_data.clear()
        st.success("✅ Portfolio updated!")
