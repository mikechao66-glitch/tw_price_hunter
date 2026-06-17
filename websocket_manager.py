"""
WebSocket 管理員
台新 SDK 只有一個 websocket_client.stock 物件（單一連線），
但規劃中的「連線1」和「連線2」概念在此以同一連線實現，
同時訂閱 trades、books、aggregates 頻道。
訂閱上限：300 個頻道訂閱（trades+books+aggregates = 每支3個）。
"""

import json
import threading
import time
import state
import api_client
import config

MAX_SUBSCRIPTIONS = 300

# ── 訂閱紀錄 ──────────────────────────────────────────────────────────────────
# subs: {symbol: {"trades": channel_id, "books": channel_id, "aggregates": channel_id}}
subs: dict = {}
_subs_lock = threading.Lock()

_stock = None  # websocket_client.stock


def _total_sub_count() -> int:
    """目前總訂閱數（每支股票的每個頻道算1個）。"""
    with _subs_lock:
        count = sum(len(v) for v in subs.values())
    return count


def _update_sub_count():
    with state.lock:
        state.ws_subscription_count = _total_sub_count()


# ── 訊息處理 ──────────────────────────────────────────────────────────────────

def _handle_message(raw_msg):
    """統一處理所有頻道的 WebSocket 訊息。"""
    try:
        msg = raw_msg if isinstance(raw_msg, dict) else json.loads(raw_msg)
        event = msg.get("event")
        if event == "subscribed":
            _on_subscribed(msg)
        elif event == "data":
            channel = msg.get("channel")
            data = msg.get("data", {})
            if channel == "trades":
                _dispatch_trades(data)
            elif channel == "books":
                _dispatch_books(data)
            elif channel == "aggregates":
                _dispatch_aggregates(data)
        elif event == "error":
            state.add_error(f"[WS 伺服器錯誤] {msg.get('data', {})}")
    except Exception as e:
        state.add_error(f"[WS 訊息解析錯誤] {e}")


def _on_subscribed(msg):
    """收到訂閱確認後，記錄 channel_id。"""
    data = msg.get("data")
    if not data:
        return
    items = data if isinstance(data, list) else [data]
    with _subs_lock:
        for item in items:
            cid = item.get("id")
            channel = item.get("channel")
            symbol = item.get("symbol")
            if not (cid and channel and symbol):
                continue
            if symbol not in subs:
                subs[symbol] = {}
            subs[symbol][channel] = cid
    _update_sub_count()


# ── 訊息分派（由各監控模組設定回呼） ─────────────────────────────────────────

_trades_callbacks: list = []
_books_callbacks: list = []
_aggregates_callbacks: list = []


def register_trades_callback(fn):
    _trades_callbacks.append(fn)


def register_books_callback(fn):
    _books_callbacks.append(fn)


def register_aggregates_callback(fn):
    _aggregates_callbacks.append(fn)


def _dispatch_trades(data: dict):
    for fn in _trades_callbacks:
        try:
            fn(data)
        except Exception as e:
            state.add_error(f"[trades callback 錯誤] {e}")


def _dispatch_books(data: dict):
    for fn in _books_callbacks:
        try:
            fn(data)
        except Exception as e:
            state.add_error(f"[books callback 錯誤] {e}")


def _dispatch_aggregates(data: dict):
    for fn in _aggregates_callbacks:
        try:
            fn(data)
        except Exception as e:
            state.add_error(f"[aggregates callback 錯誤] {e}")


# ── 訂閱 / 取消訂閱 ──────────────────────────────────────────────────────────

def subscribe_symbol(symbol: str):
    """
    將一支股票訂閱 trades、books、aggregates 三個頻道。
    若訂閱數已達300，先執行移除邏輯再嘗試。
    """
    with _subs_lock:
        already = symbol in subs
    if already:
        return
    if _total_sub_count() + 3 > MAX_SUBSCRIPTIONS:
        _evict_one()

    _stock.subscribe({"channel": "trades", "symbol": symbol})
    _stock.subscribe({"channel": "books", "symbol": symbol})
    _stock.subscribe({"channel": "aggregates", "symbol": symbol})


def subscribe_symbol_force(symbol: str, alert_symbols: set):
    """
    強制訂閱特別警戒股。
    若訂閱數已達300，隨機移除一支非警戒股（不移除 locked 或其他警戒股）。
    """
    import random
    with _subs_lock:
        already = symbol in subs
    if already:
        return
    if _total_sub_count() + 3 > MAX_SUBSCRIPTIONS:
        with _subs_lock:
            candidates = list(subs.keys())
        evict_pool = [s for s in candidates if s not in alert_symbols]
        if not evict_pool:
            evict_pool = candidates
        if evict_pool:
            target = random.choice(evict_pool)
            unsubscribe_symbol(target)
            state.add_error(f"[WS] 警戒股強制訂閱，已移除 {target}")

    _stock.subscribe({"channel": "trades", "symbol": symbol})
    _stock.subscribe({"channel": "books", "symbol": symbol})
    _stock.subscribe({"channel": "aggregates", "symbol": symbol})


def unsubscribe_symbol(symbol: str):
    """取消一支股票的所有頻道訂閱。"""
    with _subs_lock:
        ids_to_remove = list(subs.get(symbol, {}).values())
        if symbol in subs:
            del subs[symbol]

    if ids_to_remove and _stock:
        _stock.unsubscribe({"ids": ids_to_remove})

    _update_sub_count()


def _evict_one():
    """
    訂閱超量時移除策略：
    1. 優先移除「漲停已打開但尚未觸發4%回檔條件」的標的
    2. 若無，則從目前訂閱清單中隨機移除一個非鎖死標的
    """
    import random
    with _subs_lock:
        candidates = list(subs.keys())

    with state.lock:
        opened = list(state.limit_opened_symbols)
        locked = list(state.locked_up_symbols | state.locked_down_symbols)

    evict_pool = [s for s in opened if s in candidates]
    if not evict_pool:
        evict_pool = [s for s in candidates if s not in locked]
    if not evict_pool:
        evict_pool = candidates

    if evict_pool:
        target = random.choice(evict_pool)
        unsubscribe_symbol(target)
        state.add_error(f"[WS] 訂閱超量，已移除 {target}")


# ── 重連邏輯 ──────────────────────────────────────────────────────────────────

def _on_disconnect(code, message):
    state.add_error(f"[WS斷線] code={code}, msg={message}，嘗試重連...")
    _do_reconnect()


def _do_reconnect(max_retries: int = 10):
    with _subs_lock:
        symbols_to_resub = list(subs.keys())
        subs.clear()

    delay = 5
    for attempt in range(1, max_retries + 1):
        try:
            _stock.connect()
            time.sleep(2)
            for sym in symbols_to_resub:
                for ch in ["trades", "books", "aggregates"]:
                    _stock.subscribe({"channel": ch, "symbol": sym})
            state.add_error(f"[WS] 重連成功，已重新訂閱 {len(symbols_to_resub)} 支")
            return
        except Exception as e:
            state.add_error(f"[WS] 第{attempt}次重連失敗: {e}，{delay}秒後再試")
            time.sleep(delay)
            delay = min(delay * 2, 60)
    state.add_error("[WS] 已達最大重連次數，放棄")


# ── 初始化與啟動 ──────────────────────────────────────────────────────────────

def start():
    """
    初始化並啟動 WebSocket 連線。
    必須在 api_client.init_sdk() 之後呼叫。
    展示版 (DEMO_MODE=True) 時不連接 WebSocket。
    """
    global _stock

    # 展示版模式：不連接 WebSocket
    if config.DEMO_MODE:
        return

    _stock = api_client.get_websocket_stock()
    if not _stock:
        return
    _stock.on("message", _handle_message)
    _stock.on("disconnect", _on_disconnect)
    _stock.on("error", lambda e: state.add_error(f"[WS錯誤] {e}"))
    _stock.connect()
    state.add_error("[WS] WebSocket 已啟動")
