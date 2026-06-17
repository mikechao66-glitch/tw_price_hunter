"""
台股價量獵人 — 主程式
執行方式：streamlit run app.py

🎬 本程式為「雲端展示版」，所有數據均為模擬示意，不涉及實際交易。
"""

import threading
import time
from datetime import datetime, date

import streamlit as st

import state
import api_client
import config
import websocket_manager
import snapshot_poller

from monitors import opening_volume, limit_break, limit_pullback, tail_thin_lock, tail_reversal
import random

# ── 展示版模擬資料 ────────────────────────────────────────────────────────────

# 模擬股票資料池
_MOCK_STOCKS = [
    {"symbol": "2330", "name": "台積電", "basePrice": 550},
    {"symbol": "2454", "name": "聯發科", "basePrice": 850},
    {"symbol": "3008", "name": "華立", "basePrice": 45},
    {"symbol": "3037", "name": "欣興", "basePrice": 800},
    {"symbol": "5483", "name": "中美晶", "basePrice": 180},
    {"symbol": "6770", "name": "力積電", "basePrice": 70},
    {"symbol": "2458", "name": "義隆", "basePrice": 150},
    {"symbol": "2345", "name": "智邦", "basePrice": 2500},
    {"symbol": "3450", "name": "聯鈞", "basePrice": 500},
    {"symbol": "2327", "name": "國巨", "basePrice": 950},
    {"symbol": "9910", "name": "豐泰", "basePrice": 70},
    {"symbol": "6141", "name": "柏承", "basePrice": 35},
    {"symbol": "2478", "name": "大毅", "basePrice": 200},
    {"symbol": "3224", "name": "福貿", "basePrice": 180},
    {"symbol": "3231", "name": "緯創", "basePrice": 65},
]

def _generate_mock_trigger():
    """每次重新整理時生成新的模擬觸發訊息（每次刷新都產生，不額外節流）。"""
    now = datetime.now()
    stock = random.choice(_MOCK_STOCKS)
    return {
        "symbol": stock["symbol"],
        "name": stock["name"],
        "price": round(stock["basePrice"] * random.uniform(0.98, 1.05), 2),
        "changePercent": round(random.uniform(-10, 10), 2),
        "triggerTime": now.strftime("%H:%M:%S"),
    }

def _add_mock_triggers():
    """在展示版中定期添加模擬觸發訊息。"""
    new_trigger = _generate_mock_trigger()
    if new_trigger:
        with state.lock:
            # 隨機添加到某個監控清單
            choice = random.randint(0, 4)
            if choice == 0 and len(state.triggered_opening_volume) < 20:
                state.triggered_opening_volume.insert(0, {
                    **new_trigger,
                    "tradeVolume": random.randint(100, 5000),
                    "yesterdayVolume": random.randint(50, 2000),
                })
            elif choice == 1 and len(state.triggered_limit_break) < 20:
                state.triggered_limit_break.insert(0, {
                    **new_trigger,
                    "triggerCondition": random.choice(["出量", "掛單量突然減少"]),
                    "isAlert": False,
                })
            elif choice == 2 and len(state.triggered_limit_pullback) < 20:
                state.triggered_limit_pullback.insert(0, new_trigger)
            elif choice == 3 and len(state.triggered_tail_thin_lock) < 20:
                state.triggered_tail_thin_lock.insert(0, {
                    **new_trigger,
                    "bidSize": random.randint(10, 500),
                    "tradeVolume": random.randint(1000, 20000),
                })
            elif choice == 4 and len(state.triggered_tail_reversal) < 20:
                state.triggered_tail_reversal.insert(0, new_trigger)

            # 每筆觸發後保存狀態
            state.save_persist()

# ── 頁面設定 ──────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="台股價量獵人",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 隱藏音效播放器
st.markdown(
    """
    <style>
    audio {
        display: none;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── 數值格式化輔助 ─────────────────────────────────────────────────────────────

def _fmt(val) -> str:
    """將數值去除尾部多餘的零，非數值原樣回傳。"""
    try:
        f = float(val)
        # 移除尾部零，例如 5.20 → 5.2，5.00 → 5，5.10 → 5.1
        return f"{f:g}"
    except (TypeError, ValueError):
        return str(val) if val is not None else ""


# ── 啟動初始化（只執行一次） ──────────────────────────────────────────────────

def _engine_started() -> bool:
    return st.session_state.get("engine_started", False)


def _start_engine():
    """
    初始化 SDK、下載昨量、啟動 WebSocket 與監控模組。
    展示版 (DEMO_MODE=True) 時只載入持久化資料，跳過所有後台服務。
    """
    st.session_state["engine_started"] = True
    st.session_state["start_time"] = datetime.now().strftime("%H:%M:%S")

    # 1. 跨日檢查：先從持久化檔案讀回，若日期不符今日（或無檔案）則清除
    today = date.today()
    loaded = state.load_persist()   # 回傳 True 表示今日資料，False 表示過期或無檔案
    if not loaded:
        state.reset_daily()
    state.last_run_date = today

    # 同步警戒股到 limit_break 模組
    limit_break.alert_symbols.update(state.alert_symbols_persist)

    # 展示版模式：只載入持久化資料，不啟動後台服務
    if config.DEMO_MODE:
        state.add_error("[展示版] 已載入模擬數據，無須登入 API")
        return

    # 2. 登入台新 SDK（生產版本）
    ok = api_client.init_sdk()
    if not ok:
        st.session_state["init_error"] = "台新 SDK 登入失敗，請檢查 config.py 設定"
        return

    # 3. 下載昨日成交量
    def _download_bg():
        snapshot_poller.download_yesterday_volumes()
    threading.Thread(target=_download_bg, daemon=True).start()

    # 4. 啟動 WebSocket
    websocket_manager.start()
    time.sleep(1)

    # 5. 啟動 Snapshot 排程
    snapshot_poller.start()

    # 6. 啟動各監控模組（依時段自動啟停由各模組自行管理）
    limit_break.start()
    limit_pullback.start()

    # 開盤出量 09:05 後才需要，tail 模組 12:30 後才需要，
    # 但提前 start() 讓它們自己等待時間點
    opening_volume.start()
    tail_thin_lock.start()
    tail_reversal.start()


if not _engine_started():
    if "init_error" not in st.session_state:
        _start_engine()

# ── 側邊欄：特別警戒股設定 ────────────────────────────────────────────────────

def _on_alert_input():
    """alert_input 的 on_change callback，在 widget 值變更時處理加入邏輯。"""
    code = st.session_state.get("alert_input", "").strip()
    if not code:
        return
    if len(code) == 4 and code.isdigit():
        if code not in limit_break.alert_symbols:
            limit_break.alert_symbols.add(code)
            state.alert_symbols_persist.add(code)
            state.save_persist()
            websocket_manager.subscribe_symbol_force(code, limit_break.alert_symbols)
        # callback 內可直接清空 widget value
        st.session_state["alert_input"] = ""
    else:
        st.session_state["alert_input"] = ""


with st.sidebar:
    st.header("⚠️ 特別警戒股")
    st.caption("輸入需要特別警戒的漲跌停鎖死股票代號（當日有效）")

    st.text_input(
        "加入警戒股（輸入4位代號後按Enter）",
        key="alert_input",
        placeholder="例：2330",
        on_change=_on_alert_input,
    )

    if limit_break.alert_symbols:
        st.write("**目前警戒股：**")
        for _sym in sorted(limit_break.alert_symbols):
            col_s, col_del = st.columns([3, 1])
            col_s.write(_sym)
            if col_del.button("移除", key=f"del_{_sym}"):
                limit_break.alert_symbols.discard(_sym)
                state.alert_symbols_persist.discard(_sym)
                state.save_persist()
                st.rerun()
    else:
        st.caption("尚未設定警戒股")

# ── 標題與狀態列 ──────────────────────────────────────────────────────────────

st.markdown(
    "<h1>📈 台股價量獵人 "
    "<span style='font-size:0.45em; font-weight:400; color:#999;'>"
    "🎬 展示版—所有數據均為模擬示意</span></h1>",
    unsafe_allow_html=True,
)

init_err = st.session_state.get("init_error", "")
if init_err:
    st.error(init_err)
    st.stop()

# 狀態列（展示版也顯示模擬的訂閱數和配額）
col1, col2, col3 = st.columns(3)

if config.DEMO_MODE:
    # 展示版：模擬數字跳動
    demo_ws_count = st.session_state.get("demo_ws_count", random.randint(50, 150))
    demo_api_quota = st.session_state.get("demo_api_quota", random.randint(100, 400))
    st.session_state["demo_ws_count"] = demo_ws_count
    st.session_state["demo_api_quota"] = demo_api_quota
else:
    # 生產版本：真實數字
    demo_ws_count = state.ws_subscription_count
    demo_api_quota = state.api_quota_used

with col1:
    st.metric("WebSocket 訂閱數", f"{demo_ws_count} / 300")
with col2:
    st.metric("API 配額（本分鐘）", f"{demo_api_quota} / 600")
with col3:
    start_time = st.session_state.get("start_time", "--")
    st.metric("啟動時間", start_time)

# ── 錯誤日誌 ──────────────────────────────────────────────────────────────────

with st.expander("📋 系統日誌", expanded=False):
    with state.lock:
        logs = list(state.error_log[:50])
    if logs:
        for log in logs:
            st.text(f"[{log['time']}] {log['msg']}")
    else:
        st.text("無日誌")

col_btn, _ = st.columns([1, 5])
with col_btn:
    if st.button("清除所有觸發記錄"):
        with state.lock:
            state.triggered_opening_volume.clear()
            state.triggered_limit_break.clear()
            state.triggered_limit_pullback.clear()
            state.triggered_tail_thin_lock.clear()
            state.triggered_tail_reversal.clear()
        state.save_persist()
        st.rerun()

st.divider()

# ── 各監控區塊 ────────────────────────────────────────────────────────────────

def _render_table(rows: list, columns: list, col_map: dict, fmt_cols: list = None):
    """通用渲染函數：將觸發清單渲染成 st.dataframe。fmt_cols 指定需格式化的欄位名稱。"""
    if not rows:
        st.caption("尚無觸發標的")
        return
    import pandas as pd
    fmt_cols = fmt_cols or []
    display_rows = []
    for row in rows:
        r = {col: row.get(col_map[col], "") for col in columns}
        for col in fmt_cols:
            if col in r:
                r[col] = _fmt(r[col])
        display_rows.append(r)
    df = pd.DataFrame(display_rows, columns=columns)
    st.dataframe(df, use_container_width=True, hide_index=True)


# ① 開盤出量
with st.container():
    st.subheader("① 開盤出量")
    with state.lock:
        rows_ov = list(state.triggered_opening_volume)
    cols_ov = ["股票代號", "名稱", "當前價", "漲跌幅%", "成交量(張)", "昨量(張)", "觸發時間"]
    map_ov  = {
        "股票代號": "symbol", "名稱": "name", "當前價": "price",
        "漲跌幅%": "changePercent", "成交量(張)": "tradeVolume",
        "昨量(張)": "yesterdayVolume", "觸發時間": "triggerTime",
    }
    _render_table(rows_ov, cols_ov, map_ov, fmt_cols=["當前價", "漲跌幅%"])

st.divider()

# ② 可能漲跌停打開
with st.container():
    st.subheader("② 可能漲跌停打開")
    with state.lock:
        rows_lb = list(state.triggered_limit_break)

    if not rows_lb:
        st.caption("尚無觸發標的")
    else:
        import pandas as pd

        _display_cols = ["股票代號", "名稱", "當前價", "漲跌幅%", "觸發條件", "觸發時間"]
        _lb_display = []
        _is_alert_flags = []
        for r in rows_lb:
            _lb_display.append({
                "股票代號": r.get("symbol", ""),
                "名稱":     r.get("name", ""),
                "當前價":   _fmt(r.get("price", "")),
                "漲跌幅%":  _fmt(r.get("changePercent", "")),
                "觸發條件": r.get("triggerCondition", ""),
                "觸發時間": r.get("triggerTime", ""),
            })
            _is_alert_flags.append(r.get("isAlert", False))
        _df_lb = pd.DataFrame(_lb_display, columns=_display_cols)

        def _highlight_alert(row):
            idx = row.name
            styles = [""] * len(row)
            if idx < len(_is_alert_flags) and _is_alert_flags[idx]:
                col_idx = _display_cols.index("股票代號")
                styles[col_idx] = "background-color: #ff4444; color: white"
            return styles

        _styled = _df_lb.style.apply(_highlight_alert, axis=1).hide(axis="index")
        st.dataframe(_styled, use_container_width=True, hide_index=True)

        # 播放音效：只在警戒股觸發筆數增加時播一次
        _alert_count = sum(1 for r in rows_lb if r.get("isAlert"))
        _prev_alert_count = st.session_state.get("prev_alert_count", 0)
        if _alert_count > _prev_alert_count:
            st.session_state["prev_alert_count"] = _alert_count
            _sound_path = "sound/yisell_sound.mp3"
            try:
                import base64
                with open(_sound_path, "rb") as _f:
                    _audio_b64 = base64.b64encode(_f.read()).decode()
                st.markdown(
                    f'<audio autoplay><source src="data:audio/mp3;base64,{_audio_b64}" type="audio/mp3"></audio>',
                    unsafe_allow_html=True,
                )
            except Exception:
                pass

st.divider()

# ③ 漲停打開回檔4%以上
with st.container():
    st.subheader("③ 漲停打開回檔4%以上")
    with state.lock:
        rows_lp = list(state.triggered_limit_pullback)
    cols_lp = ["股票代號", "名稱", "當前價", "漲跌幅%", "觸發時間"]
    map_lp  = {
        "股票代號": "symbol", "名稱": "name", "當前價": "price",
        "漲跌幅%": "changePercent", "觸發時間": "triggerTime",
    }
    _render_table(rows_lp, cols_lp, map_lp, fmt_cols=["當前價", "漲跌幅%"])

st.divider()

# ④ 尾盤漲停鎖量少
with st.container():
    st.subheader("④ 尾盤漲停鎖量少")
    with state.lock:
        rows_tl = list(state.triggered_tail_thin_lock)
    cols_tl = ["股票代號", "名稱", "當前價", "漲跌幅%", "委買掛單量(張)", "成交量(張)", "觸發時間"]
    map_tl  = {
        "股票代號": "symbol", "名稱": "name", "當前價": "price",
        "漲跌幅%": "changePercent", "委買掛單量(張)": "bidSize",
        "成交量(張)": "tradeVolume", "觸發時間": "triggerTime",
    }
    _render_table(rows_tl, cols_tl, map_tl, fmt_cols=["當前價", "漲跌幅%"])

st.divider()

# ⑤ 尾盤隔日沖
with st.container():
    st.subheader("⑤ 尾盤隔日沖")
    with state.lock:
        rows_tr = list(state.triggered_tail_reversal)
    cols_tr = ["股票代號", "名稱", "當前價", "漲跌幅%", "觸發時間"]
    map_tr  = {
        "股票代號": "symbol", "名稱": "name", "當前價": "price",
        "漲跌幅%": "changePercent", "觸發時間": "triggerTime",
    }
    _render_table(rows_tr, cols_tr, map_tr, fmt_cols=["當前價", "漲跌幅%"])

# ── 頁面底部分隔線與版權宣告 ──────────────────────────────────────────────────

st.divider()
st.markdown("<div style='text-align: center; color: #888; font-size: 14px; margin-top: 20px;'>© 2026 Built by 趙志軒</div>", unsafe_allow_html=True)

# ── 收盤後停止所有監控並停止自動刷新 ─────────────────────────────────────────

if config.DEMO_MODE:
    # 展示版：不受收盤時間限制，持續產生模擬資料並刷新頁面
    _add_mock_triggers()
    st.session_state["demo_ws_count"] = random.randint(50, 150)
    st.session_state["demo_api_quota"] = random.randint(100, 400)
    time.sleep(5)
    st.rerun()
else:
    _hm = datetime.now().strftime("%H%M")
    _after_market = _hm >= "1330" or _hm < "0830"

    if _after_market:
        if not st.session_state.get("modules_stopped", False):
            limit_pullback.stop()
            tail_thin_lock.stop()
            snapshot_poller.stop()
            st.session_state["modules_stopped"] = True
        st.info("收盤時段，監控已暫停。觸發記錄保留至明日開盤前。")
    else:
        st.session_state["modules_stopped"] = False
        time.sleep(5)
        st.rerun()
