"""
模組1：開盤出量
有效時段：09:05–09:30
監控流程：
  1. 09:05 / 09:15 / 09:30 三個時間點各重建全市場監控清單
  2. 篩選「漲幅1%-5%且成交價>開盤價」的4位數標的
  3. 每批60檔、每10秒持續查詢成交量，觸發條件成立則加入觸發清單
  4. 09:30 的清單查完後完全停止
"""

import time
import threading
from datetime import datetime

import state
import api_client
import snapshot_poller

# 內部監控清單：{symbol: {"name": str, "昨量": int}}
_watchlist: dict = {}
_watchlist_lock = threading.Lock()

# 記錄已觸發（當日不重複）
_triggered_symbols: set = set()

# 目前所在的時段（決定觸發門檻）
_current_phase: str = ""   # "0905" / "0915" / "0930"

_running = False
_thread = None


def _get_threshold(phase: str) -> float:
    return {"0905": 0.20, "0915": 0.50, "0930": 1.00}.get(phase, 0)


def _scan_market_and_build_watchlist(phase: str):
    """掃描全市場，建立漲幅1%-5%且成交價>開盤價的監控清單。"""
    global _current_phase
    _current_phase = phase

    new_watchlist = {}
    for market in ["TSE", "OTC"]:
        snapshot_poller.wait_for_quota()
        data = api_client.get_snapshot_quotes(market)
        for item in data:
            cp = item.get("changePercent", 0) or 0
            close = item.get("closePrice") or 0
            open_p = item.get("openPrice") or 0
            symbol = item.get("symbol", "")
            name = item.get("name", "")
            if not symbol or not (len(symbol) == 4 and symbol.isdigit()):
                continue
            if 1.0 <= cp <= 5.0 and close > open_p > 0:
                昨量 = state.yesterday_volumes.get(symbol, 0)
                new_watchlist[symbol] = {
                    "name": name,
                    "昨量": 昨量,
                    "openPrice": open_p,
                }

    with _watchlist_lock:
        _watchlist.clear()
        _watchlist.update(new_watchlist)

    state.add_error(f"[開盤出量] {phase} 建立監控清單，共 {len(new_watchlist)} 支")


def _check_watchlist_once():
    """
    對監控清單中的股票逐批查詢成交量，觸發條件成立則加入觸發清單。
    每批60檔之間等待10秒。回傳時表示本輪查詢完畢。
    """
    with _watchlist_lock:
        symbols = list(_watchlist.items())

    threshold = _get_threshold(_current_phase)
    batch_size = 60

    for i in range(0, len(symbols), batch_size):
        if not _running:
            return
        batch = symbols[i:i + batch_size]

        for symbol, info in batch:
            if symbol in _triggered_symbols:
                continue
            snapshot_poller.wait_for_quota()
            data = api_client.get_intraday_quote(symbol)
            if not data:
                continue

            vol = (data.get("total") or {}).get("tradeVolume") or 0
            昨量 = info["昨量"]
            if 昨量 <= 0:
                continue

            now_price = data.get("closePrice") or data.get("lastPrice") or 0
            change_pct = data.get("changePercent") or 0

            if vol >= 昨量 * threshold:
                _triggered_symbols.add(symbol)
                now_str = datetime.now().strftime("%H:%M:%S")
                entry = {
                    "symbol": symbol,
                    "name": info["name"],
                    "price": now_price,
                    "changePercent": change_pct,
                    "tradeVolume": vol,
                    "yesterdayVolume": 昨量,
                    "triggerTime": now_str,
                }
                with state.lock:
                    state.triggered_opening_volume.insert(0, entry)
                state.save_persist()

        if i + batch_size < len(symbols):
            # 批次間等待10秒，但每秒確認 _running 是否仍為 True
            for _ in range(10):
                if not _running:
                    return
                time.sleep(1)


def _monitor_loop():
    """
    主監控迴圈。
    僅在 09:05 / 09:15 / 09:30 三個時間點各掃描並查詢一次，不持續輪詢。
    """
    phases_done = set()

    while _running:
        hm = datetime.now().strftime("%H%M")

        if hm < "0905":
            time.sleep(5)
            continue

        for phase, start_hm in [("0905", "0905"), ("0915", "0915"), ("0930", "0930")]:
            if phase not in phases_done and hm >= start_hm:
                phases_done.add(phase)
                _scan_market_and_build_watchlist(phase)
                _check_watchlist_once()
                if phase == "0930":
                    state.add_error("[開盤出量] 09:30 查詢完畢，停止監控")
                    _running_stop()
                    return

        time.sleep(5)


def _running_stop():
    global _running
    _running = False


def start():
    """啟動開盤出量監控（背景執行緒）。09:30 後啟動則直接略過。"""
    global _running, _thread
    if datetime.now().strftime("%H%M") >= "0930":
        state.add_error("[開盤出量] 已超過 09:30，略過本模組")
        return
    _running = True
    _thread = threading.Thread(target=_monitor_loop, daemon=True, name="OpeningVolumeMonitor")
    _thread.start()


def stop():
    global _running
    _running = False
