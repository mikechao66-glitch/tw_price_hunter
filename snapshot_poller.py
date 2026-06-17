"""
Snapshot 輪詢排程管理員
- 統一排程所有模組的 Snapshot / Intraday API 呼叫
- 追蹤每分鐘配額使用量（上限 600 次/分鐘）
- 提供每日昨量 CSV 下載功能
"""

import os
import threading
import time
from datetime import datetime, date, timedelta

import requests
import state
import config

# ── 昨日成交量：CSV 下載 ──────────────────────────────────────────────────────

_TWSE_CSV_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?response=csv&date={date}&type=ALLBUT0999"
_OTC_CSV_URL  = "https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotes?date={date}&response=csv"


def _prev_trading_date() -> date:
    """
    取得前一個交易日日期（簡易版：跳過週六、週日）。
    台灣假日需使用者留意，若遇假日前一日也是假日，可能需手動處理。
    """
    d = date.today() - timedelta(days=1)
    while d.weekday() >= 5:  # 5=週六, 6=週日
        d -= timedelta(days=1)
    return d


def download_yesterday_volumes():
    """
    下載證交所（上市）與櫃買中心（上櫃）昨日成交量，
    存入 state.yesterday_volumes = {symbol: 昨量(張)}。
    展示版 (DEMO_MODE=True) 時不下載，使用空字典。
    """
    # 展示版模式：不下載昨量
    if config.DEMO_MODE:
        state.add_error("[展示版] 昨量下載已略過（使用模擬資料）")
        return

    prev_date = _prev_trading_date()
    twse_date_str = prev_date.strftime("%Y%m%d")
    otc_date_str  = prev_date.strftime("%Y-%m-%d")

    result = {}
    errors = []

    # ── 證交所 ──
    # 標題列欄位名稱：「證券代號」、「成交股數」（單位：股）
    try:
        url = _TWSE_CSV_URL.format(date=twse_date_str)
        resp = requests.get(url, timeout=30)
        text = resp.content.decode("ms950", errors="replace")
        lines = text.splitlines()
        header_idx = None
        for i, line in enumerate(lines):
            if "證券代號" in line and "成交股數" in line:
                header_idx = i
                break
        if header_idx is not None:
            import csv
            reader = csv.DictReader(lines[header_idx:])
            for row in reader:
                raw_sym = row.get("證券代號")
                raw_vol = row.get("成交股數")
                if raw_sym is None or raw_vol is None:
                    continue
                symbol  = raw_sym.strip().strip('"').strip("=")
                vol_str = raw_vol.strip().strip('"').replace(",", "")
                if symbol and len(symbol) == 4 and symbol.isdigit() and vol_str.isdigit():
                    result[symbol] = int(vol_str) // 1000  # 股 → 張
        else:
            errors.append("[昨量] 證交所：找不到標題列（證券代號/成交股數）")
    except Exception as e:
        errors.append(f"[昨量] 證交所下載失敗: {e}")

    # ── 櫃買中心 ──
    # 標題列欄位名稱：「代號」、「成交股數」（單位：股）
    try:
        url = _OTC_CSV_URL.format(date=otc_date_str)
        resp = requests.get(url, timeout=30)
        text = resp.content.decode("ms950", errors="replace")
        lines = text.splitlines()
        header_idx = None
        for i, line in enumerate(lines):
            if "代號" in line and "成交股數" in line:
                header_idx = i
                break
        if header_idx is not None:
            import csv
            reader = csv.DictReader(lines[header_idx:])
            for row in reader:
                raw_sym = row.get("代號")
                raw_vol = row.get("成交股數")
                if raw_sym is None or raw_vol is None:
                    continue
                symbol  = raw_sym.strip().strip('"').strip("=")
                vol_str = raw_vol.strip().strip('"').replace(",", "")
                if symbol and len(symbol) == 4 and symbol.isdigit() and vol_str.isdigit():
                    result[symbol] = int(vol_str) // 1000
        else:
            errors.append("[昨量] 櫃買中心：找不到標題列（代號/成交股數）")
    except Exception as e:
        errors.append(f"[昨量] 櫃買中心下載失敗: {e}")

    for err in errors:
        state.add_error(err)

    with state.lock:
        state.yesterday_volumes.update(result)

    state.add_error(f"[昨量] 載入完成，共 {len(result)} 支（{prev_date}）")

    # 將昨量明細寫入檔案，供事後查驗
    try:
        log_dir = os.path.join(os.path.dirname(__file__), "persist")
        os.makedirs(log_dir, exist_ok=True)
        vol_file = os.path.join(log_dir, f"yesterday_volumes_{prev_date}.json")
        with open(vol_file, "w", encoding="utf-8") as f:
            import json
            json.dump(result, f, ensure_ascii=False)
    except Exception:
        pass


# ── 配額追蹤 ──────────────────────────────────────────────────────────────────

_quota_lock = threading.Lock()
_quota_count = 0
_quota_reset_time = datetime.now()


def _check_and_count() -> bool:
    """
    檢查本分鐘配額是否還有餘量。有則計數並回傳 True，否則回傳 False。
    """
    global _quota_count, _quota_reset_time
    now = datetime.now()
    with _quota_lock:
        if (now - _quota_reset_time).total_seconds() >= 60:
            _quota_count = 0
            _quota_reset_time = now
        if _quota_count >= 580:  # 預留20次緩衝
            state.add_error(f"[配額] 本分鐘已達 {_quota_count} 次，暫停呼叫")
            return False
        _quota_count += 1
        with state.lock:
            state.api_quota_used = _quota_count
        return True


def wait_for_quota():
    """若配額耗盡，阻塞等待至下一分鐘重置。"""
    while not _check_and_count():
        time.sleep(5)


# ── 定時任務排程 ──────────────────────────────────────────────────────────────

_tasks: list = []  # [(interval_sec, last_run_time, fn)]
_scheduler_running = False
_scheduler_thread = None


def register_task(interval_sec: int, fn):
    """
    登記一個定時輪詢任務。
    interval_sec：執行間隔（秒）
    fn：無參數的呼叫函數
    """
    _tasks.append([interval_sec, 0.0, fn])


def _scheduler_loop():
    while _scheduler_running:
        now = time.time()
        for task in _tasks:
            interval, last_run, fn = task
            if now - last_run >= interval:
                task[1] = now
                try:
                    fn()
                except Exception as e:
                    state.add_error(f"[排程] 任務 {fn.__name__} 執行錯誤: {e}")
        time.sleep(1)


def start():
    """
    啟動排程執行緒。
    展示版 (DEMO_MODE=True) 時不啟動排程。
    """
    global _scheduler_running, _scheduler_thread

    # 展示版模式：不啟動排程
    if config.DEMO_MODE:
        return

    _scheduler_running = True
    _scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True)
    _scheduler_thread.start()


def stop():
    """停止排程執行緒。"""
    global _scheduler_running
    _scheduler_running = False
