"""
模組3：漲停打開回檔4%以上
有效時段：09:00–13:25
監控流程：
  - 從 aggregates 頻道即時偵測漲停打開後的漲跌幅
  - 觸發條件：changePercent < 6%
  - 漲停「打開」的判定：實際成交價 < limitUpPrice × 99%（與模組2一致，排除分盤試撮誤判）
  - 觸發後從 WebSocket 移除，當日每支只觸發一次
"""

from datetime import datetime

import state
import websocket_manager

_running = False


def _on_aggregates(data: dict):
    """處理 aggregates 頻道訊息。"""
    if not _running:
        return

    symbol = data.get("symbol", "")
    change_pct = data.get("changePercent")
    if change_pct is None:
        return

    with state.lock:
        is_locked_up   = symbol in state.locked_up_symbols
        ever_locked_up = symbol in state.ever_locked_up_symbols
        limit_up       = state.limit_up_prices.get(symbol)

    # 必須曾被 books 頻道確認過漲停鎖死（且成交價已到位），才納入此模組監控
    if not ever_locked_up:
        return

    # 取得實際成交價
    actual_price = data.get("closePrice") or data.get("lastPrice") or 0

    # 當前仍在漲停鎖死（books 確認中）→ 不處理
    if is_locked_up:
        return

    # 漲停「打開」判定：實際成交價必須已明顯低於漲停價（< 99%）
    # 避免分盤交易 / 瞬間價格穩定措施試撮期間誤判
    if limit_up is not None and actual_price > 0:
        if actual_price >= limit_up * 0.99:
            # 成交價仍接近漲停價，尚未真正打開
            return

    # 標記為已打開
    with state.lock:
        state.limit_opened_symbols.add(symbol)

    # 觸發條件：漲幅縮小至 6% 以下
    if change_pct < 6.0:
        with state.lock:
            already_triggered = any(
                e["symbol"] == symbol for e in state.triggered_limit_pullback
            )
        if already_triggered:
            return

        name = data.get("name", symbol)
        price = actual_price
        now_str = datetime.now().strftime("%H:%M:%S")
        entry = {
            "symbol": symbol,
            "name": name,
            "price": price,
            "changePercent": change_pct,
            "triggerTime": now_str,
        }
        with state.lock:
            state.triggered_limit_pullback.insert(0, entry)
        state.save_persist()

        # 移出 WebSocket
        websocket_manager.unsubscribe_symbol(symbol)
        with state.lock:
            state.limit_opened_symbols.discard(symbol)
            state.locked_up_symbols.discard(symbol)


def start():
    global _running
    _running = True
    websocket_manager.register_aggregates_callback(_on_aggregates)


def stop():
    global _running
    _running = False
