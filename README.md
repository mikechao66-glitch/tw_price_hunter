# 台股價量獵人 📈

> **🎬 雲端展示版** - 全自動台股盤中監控應用
>
> 無需台新 API 憑證，使用模擬數據展示五種監控模式

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://streamlit.io)

---

## 🌟 核心特點

- **🎯 五種監控模式** - 開盤出量、漲跌停打開、回檔、尾盤鎖量、隔日沖
- **📊 實時展示** - 完整的 Streamlit UI 介面與互動表格
- **🚨 警戒股功能** - 特別警戒股設定、紅色標記、觸發音效
- **💾 資料持久化** - 自動保存觸發清單與警戒股設定
- **🔐 完全安全** - 無敏感資訊，可安全上傳 GitHub
- **☁️ 雲端就緒** - 一鍵部署到 Streamlit Cloud

---

## 🚀 快速開始

### 本地運行

```bash
# 1. 複製專案
git clone <your-github-url>
cd 台股價量獵人

# 2. 安裝依賴
pip install -r requirements.txt

# 3. 運行應用
streamlit run app.py
```

訪問 `http://localhost:8501` 查看應用。

### Streamlit Cloud 部署

詳見 [Streamlit Cloud 部署指南](#-部署指南) 章節。

---

## 📖 使用指南

### 五個監控區塊

#### ① 開盤出量
監控 09:05-09:30 的高成交量股票

#### ② 可能漲跌停打開
監控漲停/跌停鎖死後的出量突破

#### ③ 漲停打開回檔 4%
監控漲停打開後回檔超過 4% 的股票

#### ④ 尾盤漲停鎖量少
監控 12:30-13:25 漲停鎖死但掛單量少的股票

#### ⑤ 尾盤隔日沖
監控 12:30-13:30 符合隔日沖特徵的股票

### 特別警戒股設定

在左側邊欄輸入 4 位數股票代號設定警戒股：

- 警戒股觸發時會 **加紅色標記**
- 警戒股觸發時會 **播放音效**
- 設定會 **自動保存**（重開 app 保留）

---

## 🎬 展示版特性

### ✅ 已啟用
- 完整 UI 介面與五個監控區塊
- 特別警戒股功能
- 系統日誌檢視
- 資料持久化
- 警戒股音效
- 清除記錄功能

### ❌ 已停用（展示版無需）
- 台新 Nova API 連線
- WebSocket 即時訂閱
- Snapshot API 輪詢
- Telegram 推播

---

## 📁 專案結構

```
台股價量獵人/
├── app.py                      # 主應用程式
├── config.py                   # 配置（已移除敏感資訊）
├── api_client.py               # API 客戶端（Demo Mode 支援）
├── state.py                    # 全域狀態管理
├── websocket_manager.py        # WebSocket 管理
├── snapshot_poller.py          # Snapshot 輪詢
├── telegram_bot.py             # Telegram 推播
├── monitors/                   # 五個監控模組
│   ├── opening_volume.py       # 開盤出量
│   ├── limit_break.py          # 漲跌停打開
│   ├── limit_pullback.py       # 漲停回檔
│   ├── tail_thin_lock.py       # 尾盤鎖量少
│   └── tail_reversal.py        # 尾盤隔日沖
├── persist/
│   └── daily_state.json        # 展示數據（模擬觸發清單）
├── sound/
│   └── yisell_sound.mp3        # 警戒股觸發音效
├── .streamlit/
│   └── config.toml             # Streamlit 配置
├── docs/
│   ├── plan.md                 # 完整架構規劃
│   ├── api.md                  # API 文檔
│   └── README.md               # 技術文檔
├── README.md                   # 本檔案
├── DEMO_README.md              # 詳細使用指南
├── CHANGES.md                  # 修改記錄
├── requirements.txt            # Python 依賴
├── .gitignore                  # Git 忽略設定
└── CLAUDE.md                   # 開發者指南
```

---

## ⚙️ 配置

### 展示版（DEMO_MODE = True）
無需任何配置，直接運行即可。

### 升級至生產版本（DEMO_MODE = False）

編輯 `config.py`：

```python
DEMO_MODE = False

# 填入真實台新 API 憑證
TAISHIN_ID       = "A125519047"
TAISHIN_PASSWORD = "your_password"
CERT_PATH        = "C:/path/to/cert.pfx"
CERT_PASSWORD    = "your_cert_password"

# 填入 Telegram 信息（可選）
TELEGRAM_TOKEN   = "your_bot_token"
TELEGRAM_CHAT_ID = "your_chat_id"
```

然後安裝台新 SDK：
```bash
pip install taishin_sdk
```

---

## 📚 部署指南

### Streamlit Cloud 部署（推薦）

#### 前置條件
- GitHub 帳戶
- 專案已上傳至 GitHub

#### 部署步驟

1. **訪問 Streamlit Cloud**
   - 造訪 https://streamlit.io/cloud
   - 使用 GitHub 帳戶登入

2. **建立新應用**
   - 點擊「New app」
   - 選擇存放本專案的 GitHub 倉庫
   - 選擇「main」分支
   - 指定 `app.py` 為主程式

3. **部署**
   - 點擊「Deploy」
   - 應用將在數秒內啟動

4. **訪問**
   - 複製生成的公開 URL
   - 分享給他人使用

#### 自動更新
- 每次推送至 GitHub 時自動重新部署
- 可在 Streamlit Cloud 儀表板看到部署狀態

---

## 🔐 安全性

### ✅ 敏感資訊
- ❌ 無台新 API ID、密碼、憑證
- ❌ 無 Telegram Token 與 Chat ID
- ✅ 可安全上傳至公開 GitHub

### 💡 最佳實踐
- `.env` 檔案已在 `.gitignore` 中
- 本地敏感資訊使用 `.env.local`（不上傳）
- Streamlit Cloud 可使用 Secrets 管理敏感資訊

---

## 📖 文檔

| 文檔 | 內容 |
|-----|-----|
| [DEMO_README.md](DEMO_README.md) | 展示版完整指南 |
| [CHANGES.md](CHANGES.md) | 修改記錄與升級指南 |
| [docs/plan.md](docs/plan.md) | 完整架構規劃 |
| [docs/api.md](docs/api.md) | API 文檔 |
| [CLAUDE.md](CLAUDE.md) | 開發者指南 |

---

## 🎨 功能演示

### 警戒股設定
```
側邊欄 > ⚠️ 特別警戒股 > 輸入 4 位數代號 > Enter
```

### 清除記錄
```
> 清除所有觸發記錄 按鈕
```

### 檢視日誌
```
📋 系統日誌 (展開) > 查看最近 50 筆日誌
```

---

## 💻 技術棧

- **前端**: Streamlit 1.40+
- **後端**: Python 3.8+
- **資料**: JSON （持久化）
- **部署**: Streamlit Cloud

### 依賴列表
```
streamlit>=1.40.0
requests>=2.31.0
pandas>=2.0.0
```

---

## 🐛 常見問題

### Q: 為什麼看不到即時更新？
A: 這是展示版，所有數據來自 `persist/daily_state.json`。生產版本需升級至實際 API。

### Q: 如何添加自己的監控邏輯？
A: 編輯 `monitors/` 目錄下的相應模組，遵循既有結構擴展即可。

### Q: Streamlit Cloud 上如何使用實際 API？
A: 在 Streamlit Cloud 的 Secrets 管理頁面新增敏感資訊，在 `config.py` 中讀取。

---

## 📞 聯絡與反饋

- 📧 Email: mikechao66@gmail.com
- 🔗 GitHub: [您的倉庫連結]

---

## 📄 授權

本專案供學習與展示用途。

---

## 🙏 致謝

感謝台新證券提供 Nova API。

---

**最後更新**: 2026-06-17  
**版本**: 1.0 (Demo / Showcase)

---

**準備好開始了嗎？** 👉 [Streamlit Cloud 部署指南](#-部署指南)
