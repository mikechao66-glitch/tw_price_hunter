"""
模組2：可能漲跌停打開
有效時段：09:00–13:25
監控流程：
  - 每3分鐘用 snapshot.movers 掃描漲跌停候選股
  - 對新進成員取得 limitUpPrice / limitDownPrice 並訂閱 WebSocket
  - 即時偵測四個條件（出量 / 掛單量突減）
  - 觸發時推播 Telegram（同支間隔 >= 1 分鐘）
"""

import threading
import time
from datetime import datetime

import state
import api_client
import websocket_manager
import snapshot_poller
import telegram_bot

_running = False
_scan_thread = None

# 目前已訂閱的漲跌停股票集合
_subscribed: set = set()
_sub_lock = threading.Lock()

# 記錄每支股票上次「出量」觸發時的成交時間，用於去重複
# {symbol: 成交時間字串}
_last_trade_time: dict = {}
_trade_time_lock = threading.Lock()

# 記錄每支股票上次顯示於頁面的時間，10 分鐘內不重複顯示
# {symbol: datetime}
_last_display_time: dict = {}
_display_lock = threading.Lock()

# 快取各股最新資料（由 aggregates 頻道更新）
_latest_change_pct: dict = {}
_latest_price: dict = {}
_latest_name: dict = {}
_cache_lock = threading.Lock()

# 特別警戒股代碼集合（由 app.py 側邊欄寫入，當日有效）
alert_symbols: set = set()


# ── WebSocket 回呼 ─────────────────────────────────────────────────────────────

def _on_aggregates(data: dict):
    """快取各股最新漲跌幅、成交價、名稱，供 trades/books 觸發時使用。"""
    symbol = data.get("symbol", "")
    if not symbol:
        return
    cp    = data.get("changePercent")
    price = data.get("closePrice") or data.get("lastPrice")
    name  = data.get("name") or data.get("shortName")
    with _cache_lock:
        if cp is not None:
            _latest_change_pct[symbol] = cp
        if price is not None:
            _latest_price[symbol] = price
        if name:
            _latest_name[symbol] = name


def _on_trades(data: dict):
    """處理 trades 頻道訊息，偵測條件A/C（單筆出量）。"""
    if not _running:
        return
    symbol = data.get("symbol", "")
    size = data.get("size", 0) or 0
    if not size:
        return

    # 比對成交時間，避免 WebSocket 重送同一筆成交造成重複觸發
    trade_time = data.get("time") or data.get("tradeTime") or ""
    with _trade_time_lock:
        if trade_time and _last_trade_time.get(symbol) == trade_time:
            return
        _last_trade_time[symbol] = trade_time

    with state.lock:
        is_locked_up   = symbol in state.locked_up_symbols
        is_locked_down = symbol in state.locked_down_symbols
        bid_size = state.prev_bid_sizes.get(symbol, 0)
        ask_size = state.prev_ask_sizes.get(symbol, 0)

    if is_locked_up and bid_size > 0:
        if size > bid_size * 0.10:
            _trigger(symbol, "出量", data)

    if is_locked_down and ask_size > 0:
        if size > ask_size * 0.10:
            _trigger(symbol, "出量", data)


def _on_books(data: dict):
    """處理 books 頻道訊息，更新掛單量並偵測條件B/D（掛單量突減）。"""
    if not _running:
        return
    symbol = data.get("symbol", "")
    bids = data.get("bids", [])
    asks = data.get("asks", [])

    with state.lock:
        is_locked_up   = symbol in state.locked_up_symbols
        is_locked_down = symbol in state.locked_down_symbols
        limit_up   = state.limit_up_prices.get(symbol)
        limit_down = state.limit_down_prices.get(symbol)

    # 取得 aggregates 快取的實際成交價，用於排除分盤交易試撮期誤判
    with _cache_lock:
        actual_price = _latest_price.get(symbol, 0)

    # 確認 bids[0] 是否為漲停價
    if bids and limit_up is not None:
        bid0_price = bids[0].get("price", 0)
        bid0_size  = bids[0].get("size", 0)
        # 額外確認實際成交價已接近漲停價（>=99%），排除分盤試撮期誤判
        price_confirmed = (actual_price <= 0) or (actual_price >= limit_up * 0.99)
        if bid0_price == limit_up and bid0_size > 0 and price_confirmed:
            with state.lock:
                prev = state.prev_bid_sizes.get(symbol, 0)
                state.prev_bid_sizes[symbol] = bid0_size
                if not is_locked_up:
                    state.locked_up_symbols.add(symbol)
                state.ever_locked_up_symbols.add(symbol)
            if prev > 0 and bid0_size < prev * 0.80:  # 減少20%以上
                _trigger(symbol, "掛單量突然減少", data)
        else:
            # bids[0] 不再是漲停價，或成交價尚未到位 → 確保不在鎖死集合內
            with state.lock:
                state.locked_up_symbols.discard(symbol)
                state.prev_bid_sizes.pop(symbol, None)

    # 確認 asks[0] 是否為跌停價
    if asks and limit_down is not None:
        ask0_price = asks[0].get("price", 0)
        ask0_size  = asks[0].get("size", 0)
        price_confirmed = (actual_price <= 0) or (actual_price <= limit_down * 1.01)
        if ask0_price == limit_down and ask0_size > 0 and price_confirmed:
            with state.lock:
                prev = state.prev_ask_sizes.get(symbol, 0)
                state.prev_ask_sizes[symbol] = ask0_size
                if not is_locked_down:
                    state.locked_down_symbols.add(symbol)
            if prev > 0 and ask0_size < prev * 0.80:
                _trigger(symbol, "掛單量突然減少", data)
        else:
            with state.lock:
                state.locked_down_symbols.discard(symbol)
                state.prev_ask_sizes.pop(symbol, None)


def _trigger(symbol: str, trigger_type: str, data: dict):
    """觸發，加入觸發清單並發送 Telegram。同一支股票 20 分鐘內不重複顯示於頁面。"""
    now = datetime.now()

    # 20 分鐘頁面冷卻
    with _display_lock:
        last = _last_display_time.get(symbol)
        if last and (now - last).total_seconds() < 1200:
            return
        _last_display_time[symbol] = now

    now_str = now.strftime("%H:%M:%S")

    # 從 aggregates 快取取漲跌幅、成交價、名稱（trades/books 訊息本身不含這些欄位）
    with _cache_lock:
        change_pct = _latest_change_pct.get(symbol, 0)
        price      = _latest_price.get(symbol) or data.get("price") or data.get("closePrice") or 0
        name       = _latest_name.get(symbol) or symbol

    is_alert = symbol in alert_symbols

    entry = {
        "symbol": symbol,
        "name": name,
        "price": price,
        "changePercent": change_pct,
        "triggerCondition": trigger_type,
        "triggerTime": now_str,
        "isAlert": is_alert,
    }
    with state.lock:
        state.triggered_limit_break.insert(0, entry)
    state.save_persist()

    if is_alert:
        telegram_bot.notify_limit_break(symbol, name, price, change_pct, trigger_type)


# ── 漲跌停清單掃描 ────────────────────────────────────────────────────────────

def _scan_limit_stocks():
    """每3分鐘掃描漲跌停候選股，對新成員取得漲跌停價並訂閱 WebSocket。"""
    new_symbols = set()

    for market in ["TSE", "OTC"]:
        for direction in ["up", "down"]:
            snapshot_poller.wait_for_quota()
            data = api_client.get_snapshot_movers(market, direction)
            for item in data:
                cp = abs(item.get("changePercent", 0) or 0)
                symbol = item.get("symbol", "")
                if cp >= 9.5 and symbol and len(symbol) == 4 and symbol.isdigit():
                    new_symbols.add(symbol)

    with _sub_lock:
        to_add = new_symbols - _subscribed

    for symbol in to_add:
        snapshot_poller.wait_for_quota()
        ticker = api_client.get_intraday_ticker(symbol)
        if not ticker:
            continue
        lup   = ticker.get("limitUpPrice")
        ldown = ticker.get("limitDownPrice")
        if lup is None and ldown is None:
            continue
        with state.lock:
            if lup is not None:
                state.limit_up_prices[symbol] = lup
            if ldown is not None:
                state.limit_down_prices[symbol] = ldown

        websocket_manager.subscribe_symbol(symbol)
        with _sub_lock:
            _subscribed.add(symbol)

    state.add_error(f"[漲跌停] 掃描完成，新增 {len(to_add)} 支，總計 {len(_subscribed)} 支")


def _scan_loop():
    """每3分鐘執行一次漲跌停清單掃描，09:00–13:25 有效。"""
    while _running:
        hm = datetime.now().strftime("%H%M")

        if hm < "0900":
            time.sleep(5)
            continue

        if hm >= "1325":
            state.add_error("[漲跌停] 13:25 後停止掃描")
            break

        _scan_limit_stocks()
        for _ in range(36):
            if not _running:
                return
            if datetime.now().strftime("%H%M") >= "1325":
                state.add_error("[漲跌停] 13:25 後停止掃描")
                return
            time.sleep(5)


def start():
    """啟動模組，並向 WebSocket Manager 註冊回呼。"""
    global _running, _scan_thread

    # 從持久化清單重建冷卻記錄，避免重開 app 後重複顯示
    with state.lock:
        for entry in state.triggered_limit_break:
            sym = entry.get("symbol")
            t_str = entry.get("triggerTime", "")
            if sym and t_str:
                try:
                    t = datetime.strptime(t_str, "%H:%M:%S").replace(
                        year=datetime.now().year,
                        month=datetime.now().month,
                        day=datetime.now().day,
                    )
                    with _display_lock:
                        if sym not in _last_display_time:
                            _last_display_time[sym] = t
                except Exception:
                    pass

    _running = True
    websocket_manager.register_trades_callback(_on_trades)
    websocket_manager.register_books_callback(_on_books)
    websocket_manager.register_aggregates_callback(_on_aggregates)
    _scan_thread = threading.Thread(target=_scan_loop, daemon=True, name="LimitBreakScanner")
    _scan_thread.start()


def stop():
    global _running
    _running = False
