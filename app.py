"""
港股分析工具 - DeepSeek 風格界面
數據源：yfinance（Yahoo Finance）
界面：Streamlit
"""

import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

# ==================== 頁面配置 ====================
st.set_page_config(
    page_title="港股分析工具",
    page_icon="📈",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# 隱藏 Streamlit 默認的頁腳和漢堡菜單，使界面更簡潔
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

# ==================== 數據獲取函數 ====================
@st.cache_data(ttl=3600)  # 緩存1小時，減少 API 調用
def fetch_hk_stock_data(stock_code: str):
    """
    從 Yahoo Finance 獲取港股數據
    
    參數:
        stock_code: 用戶輸入的代號（如 '0005'）
    
    返回:
        dict: 包含股票名稱、最新收市價、數據日期、歷史數據等
    """
    # 格式化為 yfinance 港股格式（4位數字 + .HK）
    ticker_symbol = f"{stock_code.zfill(4)}.HK"
    
    try:
        ticker = yf.Ticker(ticker_symbol)
        
        # 獲取股票基本信息
        info = ticker.info
        stock_name = info.get('longName', '')
        if not stock_name:
            stock_name = info.get('shortName', stock_code)
        
        # 獲取最近5個交易日數據（確保至少有一個交易日）
        hist = ticker.history(period="5d")
        if hist.empty:
            return None
        
        # 最新收市價及日期
        latest = hist.iloc[-1]
        latest_close = latest['Close']
        latest_date = hist.index[-1].strftime('%Y-%m-%d')
        
        # 獲取近3個月歷史數據（用於計算支撐阻力位）
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


# ==================== 價格計算函數 ====================
def calculate_trade_prices(current_price: float, hist_data: pd.DataFrame):
    """
    根據當前價格和歷史數據計算建議買入價、賣出價、止賺價、止蝕價
    
    計算邏輯：
    - 買入價：近期低位與20日均線的較低者，並給予2%緩衝
    - 賣出價：近期高位或當前價格上浮5%的較高者
    - 止蝕價：買入價下方7%
    - 止賺價：賣出價上方8%
    """
    # 提取近期數據（20個交易日）
    if len(hist_data) >= 20:
        recent_data = hist_data.tail(20)
    else:
        recent_data = hist_data
    
    # 計算近期高低位
    recent_low = recent_data['Low'].min()
    recent_high = recent_data['High'].max()
    
    # 計算20日移動平均線（若數據足夠）
    if len(hist_data) >= 20:
        ma_20 = hist_data['Close'].tail(20).mean()
    else:
        ma_20 = hist_data['Close'].mean()
    
    # 建議買入價：取近期低位和20日均線的較低者，再給予2%緩衝
    support_level = min(recent_low, ma_20)
    suggested_buy = support_level * 0.98
    
    # 若建議買入價高於當前價格，則以當前價格97%作為買入價
    if suggested_buy > current_price:
        suggested_buy = current_price * 0.97
    
    # 建議賣出價：取近期高位或當前價格上浮5%
    suggested_sell = max(recent_high, current_price * 1.05)
    
    # 止蝕價：買入價下方7%
    stop_loss = suggested_buy * 0.93
    
    # 止賺價：賣出價上方8%
    take_profit = suggested_sell * 1.08
    
    # 計算潛在回報率及風險回報比
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


# ==================== 界面渲染 ====================
def main():
    # 標題區
    st.markdown("<h1 style='text-align: center; margin-bottom: 10px;'>📊 港股分析工具</h1>", 
                unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #888; margin-bottom: 30px;'>輸入港股代號，獲取智能交易建議</p>", 
                unsafe_allow_html=True)
    
    # 主要內容區域（用於顯示分析結果）
    result_placeholder = st.empty()
    
    # 初始化 session_state 用於保存上一次分析的結果
    if 'last_result' not in st.session_state:
        st.session_state.last_result = None
    
    # 底部固定輸入欄（模擬 DeepSeek 風格）
    st.markdown("---")
    
    # 使用 columns 實現輸入框 + 按鈕的組合
    col1, col2, col3 = st.columns([8, 2, 1])
    with col1:
        stock_code = st.text_input(
            label="股票代號",
            placeholder="輸入港股代號，例如：0005（匯豐）、0700（騰訊）、9988（阿里巴巴）",
            label_visibility="collapsed",
            key="stock_input"
        )
    with col2:
        analyze_btn = st.button("🔍 分析", type="primary", use_container_width=True)
    with col3:
        # 清空按鈕（可選）
        if st.button("🗑️", use_container_width=True, help="清空結果"):
            st.session_state.last_result = None
            result_placeholder.empty()
            st.rerun()
    
    # 處理分析請求
    if analyze_btn and stock_code:
        # 移除可能的空格
        stock_code = stock_code.strip().upper()
        
        with st.spinner(f"正在分析 {stock_code} ..."):
            # 獲取數據
            data = fetch_hk_stock_data(stock_code)
            
            if data and data['success']:
                # 計算價位
                prices = calculate_trade_prices(data['close'], data['hist_3m'])
                prices['data_date'] = data['date']
                prices['stock_name'] = data['name']
                prices['stock_code'] = data['code']
                
                # 保存結果到 session_state
                st.session_state.last_result = prices
            else:
                st.error("❌ 無法獲取股票數據，請確認代號是否正確（無需輸入 .HK）")
                st.session_state.last_result = None
    
    # 顯示上次分析結果（如果存在）
    if st.session_state.last_result:
        prices = st.session_state.last_result
        with result_placeholder.container():
            st.markdown("---")
            st.markdown(f"### {prices['stock_name']} ({prices['stock_code']}.HK)")
            st.caption(f"📅 數據日期：{prices['data_date']} | 最後收市價：**HK${prices['current_price']}**")
            
            # 四個核心指標卡片
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
            
            # 額外信息欄
            st.info(
                f"📊 **潛在回報率**：{prices['potential_profit_pct']}%  |  "
                f"**風險回報比**：1:{prices['risk_reward_ratio']}  |  "
                f"**現價偏離買入價**：{round((prices['current_price']/prices['buy_price']-1)*100, 2)}%"
            )
            
            # 風險提示
            st.warning(
                "⚠️ **風險提示**：以上建議僅供參考，基於歷史數據和技術指標計算，不構成實際投資建議。"
                "投資涉及風險，請根據自身情況謹慎決策。"
            )
    
    # 若無任何結果，顯示歡迎信息
    if not st.session_state.last_result:
        with result_placeholder.container():
            st.markdown("<br><br>", unsafe_allow_html=True)
            st.markdown(
                "<p style='text-align: center; color: #aaa;'>👆 在下方輸入股票代號開始分析</p>",
                unsafe_allow_html=True
            )


if __name__ == "__main__":
    main()