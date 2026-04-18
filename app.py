"""
港股分析工具 - DeepSeek 風格界面
優化版：支援回車觸發分析 + 可調買入價折扣
"""

import streamlit as st
import yfinance as yf
import pandas as pd

# ==================== 頁面配置 ====================
st.set_page_config(
    page_title="港股分析工具",
    page_icon="📈",
    layout="centered",
    initial_sidebar_state="auto"
)

hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stApp {margin-bottom: 80px;}
    .stTextInput > div > div > input {
        border-radius: 20px;
        padding: 12px 16px;
        font-size: 16px;
    }
    .stButton > button {
        border-radius: 20px;
        padding: 10px 24px;
        font-weight: 600;
    }
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# ==================== 側邊欄參數設置 ====================
with st.sidebar:
    st.markdown("### ⚙️ 分析參數")
    max_discount = st.slider(
        "買入價最低折扣",
        min_value=0.70,
        max_value=0.95,
        value=0.85,
        step=0.01,
        help="建議買入價不得低於現價的此比例。\n例如 0.85 表示最多只能低於現價 15%。"
    )
    st.markdown("---")
    st.caption("數據源：Yahoo Finance")
    st.caption("更新頻率：每日收市後")

# ==================== 數據獲取函數 ====================
@st.cache_data(ttl=3600)
def fetch_hk_stock_data(stock_code: str):
    ticker_symbol = f"{stock_code.zfill(4)}.HK"
    try:
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info
        stock_name = info.get('longName', '') or info.get('shortName', stock_code)
        
        hist = ticker.history(period="5d")
        if hist.empty:
            return None
        
        latest = hist.iloc[-1]
        latest_close = latest['Close']
        latest_date = hist.index[-1].strftime('%Y-%m-%d')
        
        hist_3m = ticker.history(period="3mo")
        
        return {
            'code': stock_code,
            'name': stock_name,
            'close': round(latest_close, 2),
            'date': latest_date,
            'hist_3m': hist_3m,
            'success': True
        }
    except Exception as e:
        st.error(f"數據獲取失敗：{str(e)}")
        return None

# ==================== 價格計算函數（含折扣保護）====================
def calculate_trade_prices(current_price: float, hist_data: pd.DataFrame, max_discount: float = 0.85):
    if len(hist_data) >= 20:
        recent_data = hist_data.tail(20)
    else:
        recent_data = hist_data
    
    recent_low = recent_data['Low'].min()
    recent_high = recent_data['High'].max()
    
    if len(hist_data) >= 20:
        ma_20 = hist_data['Close'].tail(20).mean()
    else:
        ma_20 = hist_data['Close'].mean()
    
    # 建議買入價（技術支撐位）
    support_level = min(recent_low, ma_20)
    suggested_buy = support_level * 0.98
    
    # 若計算出的買入價高於現價，則改用現價小幅折扣
    if suggested_buy > current_price:
        suggested_buy = current_price * 0.97
    
    # ★ 新增下限保護：不低於現價的 max_discount
    floor_price = current_price * max_discount
    if suggested_buy < floor_price:
        suggested_buy = floor_price
    
    # 建議賣出價
    suggested_sell = max(recent_high, current_price * 1.05)
    
    # 止蝕價（買入價下方 7%）
    stop_loss = suggested_buy * 0.93
    
    # 止賺價（賣出價上方 8%）
    take_profit = suggested_sell * 1.08
    
    # 計算指標
    potential_profit_pct = (suggested_sell / suggested_buy - 1) * 100
    risk_amount = suggested_buy - stop_loss
    reward_amount = suggested_sell - suggested_buy
    risk_reward_ratio = reward_amount / risk_amount if risk_amount > 0 else 0
    
    return {
        'buy_price': round(suggested_buy, 2),
        'sell_price': round(suggested_sell, 2),
        'stop_loss': round(stop_loss, 2),
        'take_profit': round(take_profit, 2),
        'current_price': round(current_price, 2),
        'potential_profit_pct': round(potential_profit_pct, 2),
        'risk_reward_ratio': round(risk_reward_ratio, 2)
    }

# ==================== 主界面 ====================
def main():
    st.markdown("<h1 style='text-align: center; margin-bottom: 10px;'>📊 港股分析工具</h1>", 
                unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #888; margin-bottom: 30px;'>輸入港股代號，按 Enter 獲取交易建議</p>", 
                unsafe_allow_html=True)
    
    result_placeholder = st.empty()
    
    if 'last_result' not in st.session_state:
        st.session_state.last_result = None
    
    # ===== 使用 st.form 實現回車觸發（注意縮排！）=====
    with st.form(key="stock_form", clear_on_submit=False):
        col1, col2, col3 = st.columns([8, 2, 1])
        with col1:
            stock_code = st.text_input(
                label="股票代號",
                placeholder="輸入港股代號，例如：0005（匯豐）、0700（騰訊）",
                label_visibility="collapsed",
                key="stock_input"
            )
        with col2:
            analyze_btn = st.form_submit_button("🔍 分析", type="primary", use_container_width=True)
        with col3:
            clear_btn = st.form_submit_button("🗑️", use_container_width=True, help="清空結果")
    
    # 處理表單提交
    if analyze_btn and stock_code:
        stock_code = stock_code.strip().upper()
        with st.spinner(f"正在分析 {stock_code} ..."):
            data = fetch_hk_stock_data(stock_code)
            if data and data['success']:
                prices = calculate_trade_prices(data['close'], data['hist_3m'], max_discount)
                prices['data_date'] = data['date']
                prices['stock_name'] = data['name']
                prices['stock_code'] = data['code']
                st.session_state.last_result = prices
            else:
                st.error("❌ 無法獲取股票數據，請確認代號是否正確")
                st.session_state.last_result = None
    
    # 處理清空按鈕
    if clear_btn:
        st.session_state.last_result = None
        result_placeholder.empty()
        st.rerun()
    
    # 顯示結果
    if st.session_state.last_result:
        prices = st.session_state.last_result
        with result_placeholder.container():
            st.markdown("---")
            st.markdown(f"### {prices['stock_name']} ({prices['stock_code']}.HK)")
            st.caption(f"📅 數據日期：{prices['data_date']} | 最後收市價：**HK${prices['current_price']}**")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric(
                    label="💰 建議買入價",
                    value=f"HK${prices['buy_price']}",
                    delta=f"低於現價 {round((1 - prices['buy_price']/prices['current_price'])*100, 2)}%"
                )
            with col2:
                st.metric(
                    label="📈 建議賣出價",
                    value=f"HK${prices['sell_price']}",
                    delta=f"高於買入價 {round((prices['sell_price']/prices['buy_price']-1)*100, 2)}%"
                )
            with col3:
                st.metric(
                    label="🎯 止賺價",
                    value=f"HK${prices['take_profit']}",
                    delta=f"+{round((prices['take_profit']/prices['buy_price']-1)*100, 2)}%"
                )
            with col4:
                st.metric(
                    label="🛡️ 止蝕價",
                    value=f"HK${prices['stop_loss']}",
                    delta=f"-{round((1 - prices['stop_loss']/prices['buy_price'])*100, 2)}%"
                )
            
            st.info(
                f"📊 **潛在回報率**：{prices['potential_profit_pct']}%  |  "
                f"**風險回報比**：1:{prices['risk_reward_ratio']}  |  "
                f"**現價偏離買入價**：{round((prices['current_price']/prices['buy_price']-1)*100, 2)}%"
            )
            
            st.warning(
                "⚠️ **風險提示**：以上建議僅供參考，基於歷史數據和技術指標計算，不構成實際投資建議。"
                "投資涉及風險，請根據自身情況謹慎決策。"
            )
    
    else:
        with result_placeholder.container():
            st.markdown("<br><br>", unsafe_allow_html=True)
            st.markdown(
                "<p style='text-align: center; color: #aaa;'>👆 在下方輸入股票代號，按 Enter 開始分析</p>",
                unsafe_allow_html=True
            )

if __name__ == "__main__":
    main()
