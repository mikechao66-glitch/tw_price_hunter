"""
模組5：尾盤隔日沖
有效時段：12:30–13:25，每3分鐘掃描一次
觸發條件（三項全符合）：
  1. 漲幅 3%–6%
  2. 當日振幅 > 4%
  3. 成交價距離當日最高價在五檔價差內
  4. 成交價 > 前五個交易日最高價（即時查 Historical API）
"""

import threading
import time
from datetime import datetime

import state
import api_client
import snapshot_poller

_running = False
_thread = None

# 記錄已觸發及觸發時間（10 分鐘冷卻，防同一次掃描或下一輪重複顯示）
# {symbol: datetime}
_triggered_times: dict = {}


# ── 五檔價差計算 ──────────────────────────────────────────────────────────────

def _tick_size(price: float) -> float:
    if price < 10:
        return 0.01
    elif price < 50:
        return 0.05
    elif price < 100:
        return 0.1
    elif price < 500:
        return 0.5
    elif price < 1000:
        return 1.0
    else:
        return 5.0


def _five_tick_range(price: float) -> float:
    return _tick_size(price) * 5


# ── 主掃描邏輯 ────────────────────────────────────────────────────────────────

def _scan():
    """掃描全市場，篩選符合尾盤隔日沖條件的股票。"""
    candidates = []
    seen_symbols: set = set()  # 防止 TSE+OTC 同一 symbol 重複進入 candidates

    for market in ["TSE", "OTC"]:
        snapshot_poller.wait_for_quota()
        data = api_client.get_snapshot_quotes(market)
        for item in data:
            cp = item.get("changePercent", 0) or 0
            if not (3.0 <= cp <= 6.0):
                continue
            symbol   = item.get("symbol", "")
            name     = item.get("name", "")
            close    = item.get("closePrice", 0) or 0
            high     = item.get("highPrice", 0) or 0
            low      = item.get("lowPrice", 0) or 0
            open_p   = item.get("openPrice", 0) or 0

            if not symbol or not (len(symbol) == 4 and symbol.isdigit()):
                continue
            if close <= 0 or high <= 0:
                continue
            if symbol in seen_symbols:
                continue
            seen_symbols.add(symbol)

            candidates.append({
                "symbol": symbol, "name": name,
                "close": close, "high": high, "low": low,
                "openPrice": open_p, "changePercent": cp,
            })

    for c in candidates:
        if not _running:
            return
        symbol = c["symbol"]
        now = datetime.now()
        last = _triggered_times.get(symbol)
        if last and (now - last).total_seconds() < 1200:
            continue

        close = c["close"]
        high  = c["high"]
        low   = c["low"]

        # 條件一：振幅 > 4%
        # amplitude = (high - low) / previousClose * 100
        # snapshot.quotes 不直接回傳 amplitude，改用 intraday.quote 取得
        snapshot_poller.wait_for_quota()
        quote = api_client.get_intraday_quote(symbol)
        if not quote:
            continue

        amplitude = quote.get("amplitude", 0) or 0
        if amplitude <= 4.0:
            continue

        # 取得內盤第一檔委買價（bids[0].price）
        bids = quote.get("bids") or []
        bid_price = bids[0].get("price", 0) if bids else 0
        if bid_price <= 0:
            bid_price = close  # 無委買資料時退回收盤價

        # 條件二：內盤第一檔委買價距離當日最高價
        # 13:25–13:30 改為二檔，其餘時間為五檔
        if now.strftime("%H%M") >= "1325":
            tick_range = _tick_size(bid_price) * 2
        else:
            tick_range = _five_tick_range(bid_price)
        if (high - bid_price) > tick_range:
            continue

        # 條件三：內盤第一檔委買價 > 前五個交易日最高價
        five_day_high = api_client.get_five_day_high(symbol)
        if five_day_high is None:
            continue
        if bid_price <= five_day_high:
            continue

        # 三條件全符合，觸發
        _triggered_times[symbol] = now
        now_str = now.strftime("%H:%M:%S")
        entry = {
            "symbol": symbol,
            "name": c["name"],
            "price": close,
            "changePercent": c["changePercent"],
            "triggerTime": now_str,
        }
        with state.lock:
            state.triggered_tail_reversal.insert(0, entry)
        state.save_persist()

    state.add_error(f"[尾盤隔日沖] 掃描完成，候選 {len(candidates)} 支")


def _monitor_loop():
    while _running:
        hm = datetime.now().strftime("%H%M")

        if hm < "1230":
            # 12:30 前等待
            time.sleep(5)
            continue

        if hm >= "1330":
            # 13:30 後停止
            state.add_error("[尾盤隔日沖] 13:30 後停止監控")
            break

        _scan()
        # 每3分鐘掃描一次
        for _ in range(36):
            if not _running:
                return
            if datetime.now().strftime("%H%M") >= "1330":
                state.add_error("[尾盤隔日沖] 13:30 後停止監控")
                return
            time.sleep(5)


def start():
    global _running, _thread
    # 從持久化清單重建冷卻記錄，避免重開 app 後重複顯示
    # 清單由新至舊排列，第一筆即為最新觸發時間
    with state.lock:
        for entry in state.triggered_tail_reversal:
            sym = entry.get("symbol")
            t_str = entry.get("triggerTime", "")
            if sym and t_str:
                try:
                    t = datetime.strptime(t_str, "%H:%M:%S").replace(
                        year=datetime.now().year,
                        month=datetime.now().month,
                        day=datetime.now().day,
                    )
                    if sym not in _triggered_times:
                        _triggered_times[sym] = t
                except Exception:
                    pass
    _running = True
    _thread = threading.Thread(target=_monitor_loop, daemon=True, name="TailReversalMonitor")
    _thread.start()


def stop():
    global _running
    _running = False
    _triggered_times.clear()
