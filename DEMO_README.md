# 🎬 台股價量獵人 — 展示版 (Demo Version)

## 概述

本專案為 **「台股價量獵人」應用的雲端展示版本**。

✅ **所有數據均為模擬示意**，不涉及實際交易  
✅ **無需真實台新 API 憑證**，可直接在 Streamlit Cloud 上運行  
✅ **完整展示五種監控模式的 UI 介面與功能**  
✅ **保留所有互動功能**（警戒股設定、資料刷新等）

---

## 📦 本地運行

### 前置需求
- Python 3.8+
- pip

### 安裝與啟動

```bash
# 1. 複製或下載本專案
git clone <repository-url>
cd 台股價量獵人

# 2. 建立虛擬環境（可選）
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. 安裝依賴（展示版不需要 taishin_sdk）
pip install -r requirements.txt

# 4. 運行 Streamlit 應用
streamlit run app.py
```

應用將在 `http://localhost:8501` 開啟。

---

## ☁️ 在 Streamlit Cloud 上部署

### 步驟 1: 上傳至 GitHub

```bash
# 初始化 git（若尚未做過）
git init
git add .
git commit -m "Initial commit: Taiwan Stock Price Volume Hunter Demo"
git branch -M main
git remote add origin <your-github-repo-url>
git push -u origin main
```

### 步驟 2: 在 Streamlit Cloud 上部署

1. 造訪 [Streamlit Cloud](https://streamlit.io/cloud)，使用 GitHub 帳戶登入
2. 點擊 「New app」
3. 選擇存放本專案的 GitHub 倉庫、分支、並指定 `app.py` 為主程式
4. 點擊 「Deploy」

應用將在數秒內啟動並可透過公開 URL 訪問。

---

## 🎨 功能介紹

本應用展示五種台股監控模式：

### ① 開盤出量 (Opening Volume)
監控 09:05-09:30 的高成交量股票

### ② 可能漲跌停打開 (Limit Up/Down Breakout)
監控漲停/跌停鎖死後的出量突破，含特別警戒股功能

### ③ 漲停打開回檔 4% 以上 (Limit Up Pullback)
監控漲停打開後回檔超過 4% 的股票

### ④ 尾盤漲停鎖量少 (Tail Thin Lock)
監控 12:30-13:25 漲停鎖死但掛單量少的股票

### ⑤ 尾盤隔日沖 (Tail Reversal)
監控 12:30-13:30 符合隔日沖特徵的股票

---

## ⚙️ 展示版特性

### ✅ 已啟用
- ✨ 完整的 Streamlit UI 介面
- 📊 五個監控區塊的展示資料表格
- 🚨 特別警戒股設定（側邊欄）
- 📋 系統日誌檢視
- 💾 資料持久化（`persist/daily_state.json`）
- 🎵 警戒股觸發音效（若音效檔存在）

### ❌ 已停用
- ❌ 台新 Nova API 連線（無需登入）
- ❌ WebSocket 即時訂閱（無後台監控）
- ❌ Snapshot API 輪詢（無實時數據更新）
- ❌ Telegram 推播通知（無推播）

---

## 📝 配置說明

### `config.py`

```python
DEMO_MODE = True  # 展示版開關（True = 使用模擬數據）

# 以下欄位在展示版中保留為空，若要啟用生產版本請填入
TAISHIN_ID       = ""
TAISHIN_PASSWORD = ""
CERT_PATH        = ""
CERT_PASSWORD    = ""
TELEGRAM_TOKEN   = ""
TELEGRAM_CHAT_ID = ""
```

#### 從展示版升級到生產版本

將 `DEMO_MODE = False` 並填入真實的台新 API 憑證：

```python
DEMO_MODE = False
TAISHIN_ID       = "A125519047"
TAISHIN_PASSWORD = "your_password"
CERT_PATH        = "C:/path/to/your/cert.pfx"
CERT_PASSWORD    = "your_cert_password"
TELEGRAM_TOKEN   = "your_bot_token"
TELEGRAM_CHAT_ID = "your_chat_id"
```

---

## 📊 展示資料來源

所有觸發的股票資料來自 `persist/daily_state.json`，包含：

- **triggered_opening_volume**: 開盤出量觸發清單
- **triggered_limit_break**: 漲跌停打開觸發清單
- **triggered_limit_pullback**: 漲停回檔觸發清單
- **triggered_tail_thin_lock**: 尾盤鎖量少觸發清單
- **triggered_tail_reversal**: 尾盤隔日沖觸發清單
- **alert_symbols**: 當前設定的警戒股清單
- **error_log**: 系統日誌

這些資料在應用啟動時自動載入，並在進行操作（如新增警戒股、清除記錄）時實時更新。

---

## 📁 檔案結構

```
台股價量獵人(雲端展示版)/
├── app.py                      # 主應用程式
├── config.py                   # 配置文件（已移除敏感資訊）
├── api_client.py               # API 客戶端（Demo Mode 支援）
├── state.py                    # 全域狀態管理
├── websocket_manager.py        # WebSocket 管理（Demo Mode 停用）
├── snapshot_poller.py          # Snapshot 輪詢（Demo Mode 停用）
├── telegram_bot.py             # Telegram 推播（Demo Mode 停用）
├── monitors/                   # 五個監控模組
│   ├── opening_volume.py
│   ├── limit_break.py
│   ├── limit_pullback.py
│   ├── tail_thin_lock.py
│   └── tail_reversal.py
├── persist/
│   └── daily_state.json        # 展示資料（示例觸發清單）
├── sound/
│   └── yisell_sound.mp3        # 警戒股觸發音效（可選）
├── docs/
│   ├── plan.md                 # 完整架構規劃
│   ├── api.md                  # API 文檔
│   └── README.md               # 技術文檔
├── DEMO_README.md              # 本檔案
├── requirements.txt            # 依賴列表
├── .gitignore                  # Git 忽略設定
└── CLAUDE.md                   # 開發者指南
```

---

## 🔐 安全性

### ✅ 已移除的敏感資訊

- ❌ 台新 API ID 與密碼
- ❌ 憑證檔案路徑與密碼
- ❌ Telegram Bot Token 與 Chat ID

所有敏感欄位已清空，可安全上傳至公開 GitHub 倉庫。

### 📌 建議

若要在本地保存真實憑證，建議：

1. 建立 `.env.local` 檔案（已在 `.gitignore` 中）
2. 使用 `python-dotenv` 從環境變數讀取敏感資訊
3. 設定 `.gitignore` 防止意外上傳

---

## 📞 支援與反饋

如有任何問題或建議，歡迎提交 Issue 或 Pull Request：

- 📧 Email: `mikechao66@gmail.com`
- 🔗 GitHub: [您的倉庫連結]

---

## 📄 授權

本專案供學習與展示用途。詳見 LICENSE 檔案（若有）。

---

## 相關文件

- [完整架構規劃](docs/plan.md)
- [API 文檔](docs/api.md)
- [開發者指南](CLAUDE.md)

---

**最後更新**: 2026-06-17

**版本**: 1.0 (Demo / Showcase)
