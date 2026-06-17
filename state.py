import json
import os
import threading
from datetime import date, datetime

# ── 執行緒鎖，所有模組讀寫 state 前須取得此鎖 ──
lock = threading.Lock()

# ── 持久化檔案路徑 ──
_PERSIST_DIR = os.path.join(os.path.dirname(__file__), "persist")
_PERSIST_FILE = os.path.join(_PERSIST_DIR, "daily_state.json")

# ── 觸發清單（各監控模組的觸發結果，由新至舊） ──
triggered_opening_volume  = []   # 開盤出量
triggered_limit_break     = []   # 可能漲跌停打開
triggered_limit_pullback  = []   # 漲停打開回檔4%以上
triggered_tail_thin_lock  = []   # 尾盤漲停鎖量少
triggered_tail_reversal   = []   # 尾盤隔日沖

# ── 開盤出量：昨日成交量 ──
yesterday_volumes = {}   # {symbol: 昨量(張)}

# ── 漲跌停價格快取 ──
limit_up_prices   = {}   # {symbol: 漲停價}
limit_down_prices = {}   # {symbol: 跌停價}

# ── 漲跌停鎖死狀態追蹤 ──
locked_up_symbols   = set()   # 目前漲停鎖死的股票代號
locked_down_symbols = set()   # 目前跌停鎖死的股票代號

# ── 掛單量變化追蹤（用於掛單量突然減少判斷） ──
prev_bid_sizes = {}   # {symbol: 上次漲停委買掛單量}
prev_ask_sizes = {}   # {symbol: 上次跌停委賣掛單量}

# ── 漲停打開回檔4%：已打開漲停但尚未觸發4%的股票 ──
limit_opened_symbols  = set()   # 已從漲停打開的股票代號
ever_locked_up_symbols = set()  # 當日曾確認漲停鎖死（books 確認）的股票代號

# ── Telegram 推播紀錄 ──
telegram_sent_today  = {}   # {symbol: True}，漲停打開回檔4%當日已推播
telegram_last_sent   = {}   # {symbol: datetime}，可能漲跌停打開最後推播時間

# ── 系統狀態 ──
ws_subscription_count = 0    # WebSocket 目前訂閱數
api_quota_used        = 0    # 本分鐘 Snapshot/Intraday API 呼叫次數
api_quota_reset_time  = None # 本分鐘配額重置時間

error_log = []               # 錯誤日誌，每筆為 {"time": str, "msg": str}
MAX_ERROR_LOG = 200          # 最多保留幾筆錯誤訊息

# ── 日期追蹤（用於跨日清除） ──
last_run_date = None         # 上次執行日期，date 物件

# ── 警戒股（持久化） ──
alert_symbols_persist: set = set()   # 當日有效，重開 app 保留


def add_error(msg: str):
    """新增一筆錯誤訊息至錯誤日誌。"""
    with lock:
        error_log.insert(0, {"time": datetime.now().strftime("%H:%M:%S"), "msg": msg})
        if len(error_log) > MAX_ERROR_LOG:
            error_log.pop()
    save_persist()


def reset_daily():
    """每日清除前一日的觸發清單與推播記錄。"""
    with lock:
        triggered_opening_volume.clear()
        triggered_limit_break.clear()
        triggered_limit_pullback.clear()
        triggered_tail_thin_lock.clear()
        triggered_tail_reversal.clear()
        telegram_sent_today.clear()
        telegram_last_sent.clear()
        limit_opened_symbols.clear()
        ever_locked_up_symbols.clear()
        yesterday_volumes.clear()
        limit_up_prices.clear()
        limit_down_prices.clear()
        locked_up_symbols.clear()
        locked_down_symbols.clear()
        prev_bid_sizes.clear()
        prev_ask_sizes.clear()
        error_log.clear()
        alert_symbols_persist.clear()
    _delete_persist()


# ── 持久化：儲存與讀取 ────────────────────────────────────────────────────────

def save_persist():
    """將觸發清單、日誌、警戒股寫入 JSON 檔案。"""
    os.makedirs(_PERSIST_DIR, exist_ok=True)
    try:
        data = {
            "date": date.today().isoformat(),
            "triggered_opening_volume": triggered_opening_volume,
            "triggered_limit_break": triggered_limit_break,
            "triggered_limit_pullback": triggered_limit_pullback,
            "triggered_tail_thin_lock": triggered_tail_thin_lock,
            "triggered_tail_reversal": triggered_tail_reversal,
            "error_log": error_log,
            "alert_symbols": list(alert_symbols_persist),
        }
        tmp = _PERSIST_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, _PERSIST_FILE)
    except Exception:
        pass


def load_persist() -> bool:
    """
    從 JSON 檔案讀回資料。
    回傳 True 表示成功讀取且日期符合今日，False 表示無資料或已過期。
    """
    if not os.path.exists(_PERSIST_FILE):
        return False
    try:
        with open(_PERSIST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("date") != date.today().isoformat():
            return False
        with lock:
            triggered_opening_volume[:] = data.get("triggered_opening_volume", [])
            triggered_limit_break[:]    = data.get("triggered_limit_break", [])
            triggered_limit_pullback[:] = data.get("triggered_limit_pullback", [])
            triggered_tail_thin_lock[:] = data.get("triggered_tail_thin_lock", [])
            triggered_tail_reversal[:]  = data.get("triggered_tail_reversal", [])
            error_log[:]                = data.get("error_log", [])
            alert_symbols_persist.clear()
            alert_symbols_persist.update(data.get("alert_symbols", []))
        return True
    except Exception:
        return False


def _delete_persist():
    """刪除持久化檔案（跨日清除時使用）。"""
    try:
        if os.path.exists(_PERSIST_FILE):
            os.remove(_PERSIST_FILE)
    except Exception:
        pass
