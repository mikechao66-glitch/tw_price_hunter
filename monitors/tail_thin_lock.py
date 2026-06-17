"""
模組4：尾盤漲停鎖量少
有效時段：12:30–13:25
觸發條件：漲停價當下的委買掛單量 (books.bids[0].size) < 當日累計總成交量 × 5%
"""

from datetime import datetime

import state
import websocket_manager

_TIME_START = "1230"
_TIME_END   = "1325"

_running = False

# 記錄已觸發（當日不重複）
_triggered_symbols: set = set()


def _on_aggregates(data: dict):
    """處理 aggregates 頻道訊息，偵測尾盤漲停鎖量少條件。"""
    if not _running:
        return

    hm = datetime.now().strftime("%H%M")
    if hm < _TIME_START or hm >= _TIME_END:
        return

    symbol = data.get("symbol", "")

    with state.lock:
        is_locked_up = symbol in state.locked_up_symbols

    if not is_locked_up:
        return

    if symbol in _triggered_symbols:
        return

    # 取得委買掛單量（漲停價的掛單）
    bids = data.get("bids", [])
    if not bids:
        return

    with state.lock:
        lup = state.limit_up_prices.get(symbol)

    if lup is None:
        return

    bid0_price = bids[0].get("price", 0)
    bid0_size  = bids[0].get("size", 0)

    # 確認 bids[0] 確實是漲停價
    if bid0_price != lup:
        return

    # 累計總成交量
    total = data.get("total") or {}
    trade_volume = total.get("tradeVolume", 0) or 0
    trade_volume_at_bid = total.get("tradeVolumeAtBid", 0) or 0

    if trade_volume <= 0:
        return

    # 觸發條件：漲停委買掛單量 < 累計總成交量 × 5%
    if bid0_size < trade_volume * 0.05:
        _triggered_symbols.add(symbol)
        name = data.get("name", symbol)
        price = data.get("closePrice") or data.get("lastPrice") or 0
        change_pct = data.get("changePercent") or 0
        now_str = datetime.now().strftime("%H:%M:%S")
        entry = {
            "symbol": symbol,
            "name": name,
            "price": price,
            "changePercent": change_pct,
            "bidSize": bid0_size,          # 漲停委買掛單量（張）
            "tradeVolume": trade_volume,   # 累計總成交量（張）
            "triggerTime": now_str,
        }
        with state.lock:
            state.triggered_tail_thin_lock.insert(0, entry)
        state.save_persist()


def start():
    global _running
    _running = True
    websocket_manager.register_aggregates_callback(_on_aggregates)


def stop():
    global _running
    _running = False
    _triggered_symbols.clear()
