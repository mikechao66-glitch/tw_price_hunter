import time
import state
import config

sdk = None
reststock = None


def init_sdk():
    """
    登入台新 Nova API，建立行情連線。回傳 True 代表成功。
    展示版 (DEMO_MODE=True) 時直接傳回 True，不執行實際登入。
    """
    global sdk, reststock

    # 展示版模式：略過真實登入，直接傳回成功
    if config.DEMO_MODE:
        state.add_error("[展示版] Demo Mode 已啟用，不連接實際 API")
        return True

    # 生產版本：執行實際登入
    try:
        from taishin_sdk import TaishinSDK
        sdk = TaishinSDK()
        accounts = sdk.login(
            config.TAISHIN_ID,
            config.TAISHIN_PASSWORD,
            config.CERT_PATH,
            config.CERT_PASSWORD,
        )
        sdk.init_realtime(accounts[0])
        reststock = sdk.marketdata.rest_client.stock
        return True
    except Exception as e:
        state.add_error(f"[登入失敗] {e}")
        return False


def get_websocket_stock():
    """
    回傳 WebSocket stock 物件，供 websocket_manager 使用。
    展示版時傳回 None（不使用 WebSocket）。
    """
    if config.DEMO_MODE:
        return None
    return sdk.marketdata.websocket_client.stock if sdk else None


# ── 速率限制輔助 ──────────────────────────────────────────────────────────────

def _call_with_retry(fn, *args, max_retries=3, **kwargs):
    """
    執行 API 呼叫，遇到 429 時等待 61 秒後重試，最多重試 max_retries 次。
    每次成功呼叫後更新 state.api_quota_used。
    展示版時直接傳回 None（不實際呼叫）。
    """
    if config.DEMO_MODE:
        return None

    for attempt in range(max_retries + 1):
        try:
            result = fn(*args, **kwargs)
            with state.lock:
                state.api_quota_used += 1
            return result
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "Rate limit" in err_str:
                if attempt < max_retries:
                    state.add_error(f"[API 429] 等待 61 秒後重試（第{attempt+1}次）")
                    time.sleep(61)
                else:
                    state.add_error(f"[API 429] 已達最大重試次數，放棄本次呼叫")
                    return None
            else:
                state.add_error(f"[API 錯誤] {fn.__name__}: {e}")
                return None


# ── Snapshot API ──────────────────────────────────────────────────────────────

def get_snapshot_quotes(market: str):
    """
    取得全市場行情快照。
    market: 'TSE'（上市）或 'OTC'（上櫃）
    回傳 list of dict，每筆含 symbol, name, openPrice, closePrice,
    changePercent, tradeVolume 等欄位。
    """
    result = _call_with_retry(reststock.snapshot.quotes, market=market)
    if result and "data" in result:
        return result["data"]
    return []


def get_snapshot_movers(market: str, direction: str):
    """
    取得漲跌幅排行快照。
    direction: 'up'（上漲）或 'down'（下跌）
    回傳 list of dict。
    """
    result = _call_with_retry(
        reststock.snapshot.movers,
        market=market,
        direction=direction,
        change="percent",
    )
    if result and "data" in result:
        return result["data"]
    return []


# ── Intraday API ──────────────────────────────────────────────────────────────

def get_intraday_ticker(symbol: str) -> dict:
    """
    取得單支股票的基本資料，包含 limitUpPrice、limitDownPrice。
    回傳 dict 或 None。
    """
    return _call_with_retry(reststock.intraday.ticker, symbol=symbol)


def get_intraday_quote(symbol: str) -> dict:
    """
    取得單支股票的即時報價，含 amplitude、bids、asks 等。
    回傳 dict 或 None。
    """
    return _call_with_retry(reststock.intraday.quote, symbol=symbol)


# ── Historical API ────────────────────────────────────────────────────────────

def get_historical_candles(symbol: str, from_date: str, to_date: str, timeframe: str = "D") -> list:
    """
    取得歷史 K 線。
    from_date / to_date 格式：'YYYY-MM-DD'
    timeframe: 'D'（日K）、'1'、'5'... 等
    回傳 list of dict（含 date, open, high, low, close, volume）。
    """
    result = _call_with_retry(
        reststock.historical.candles,
        **{"symbol": symbol, "from": from_date, "to": to_date, "timeframe": timeframe},
    )
    if result and "data" in result:
        return result["data"]
    return []


def get_five_day_high(symbol: str) -> float | None:
    """
    取得近五個交易日的最高價（日K high 的最大值）。
    回傳 float 或 None。
    """
    from datetime import date, timedelta
    today = date.today()
    # to_date 排除今日，避免今日高點混入前五日計算
    from_date = (today - timedelta(days=14)).strftime("%Y-%m-%d")
    to_date = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    candles = get_historical_candles(symbol, from_date, to_date, timeframe="D")
    if not candles:
        return None
    highs = [c.get("high") for c in candles if c.get("high") is not None]
    if not highs:
        return None
    return max(highs[-5:]) if len(highs) >= 5 else max(highs)
