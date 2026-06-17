"""
Telegram 推播模組
推播規則：
- 僅對「可能漲跌停打開」的特別警戒股推播
- 同一支警戒股間隔 >= 5 分鐘才能再次推播
"""

import requests
from datetime import datetime
import state
import config


def _send(text: str):
    """
    發送 Telegram 訊息。
    展示版 (DEMO_MODE=True) 時不發送。
    """
    # 展示版模式：不推播
    if config.DEMO_MODE:
        return

    if not config.TELEGRAM_TOKEN or not config.TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": config.TELEGRAM_CHAT_ID, "text": text}, timeout=10)
    except Exception as e:
        state.add_error(f"[Telegram] 推播失敗: {e}")


def notify_limit_break(symbol: str, name: str, price: float, change_percent: float, trigger: str):
    """
    推播「可能漲跌停打開」特別警戒股通知。
    同一支股票間隔 >= 5 分鐘才能再次推播。
    """
    now = datetime.now()
    with state.lock:
        last = state.telegram_last_sent.get(symbol)
        if last and (now - last).total_seconds() < 300:
            return
        state.telegram_last_sent[symbol] = now

    direction = "漲停" if change_percent > 0 else "跌停"
    text = (
        f"🚨 【警戒股】可能{direction}打開\n"
        f"{symbol} {name}\n"
        f"現價：{price}　漲跌幅：{change_percent:+.2f}%\n"
        f"觸發：{trigger}\n"
        f"時間：{now.strftime('%H:%M:%S')}"
    )
    _send(text)
