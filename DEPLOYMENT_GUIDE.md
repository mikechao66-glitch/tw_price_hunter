# 📚 完整部署與設定指南

本指南提供詳細的上傳、部署及設定步驟。

---

## 目錄

1. [GitHub 上傳](#1-github-上傳)
2. [Streamlit Cloud 部署](#2-streamlit-cloud-部署)
3. [本地測試](#3-本地測試)
4. [Streamlit Cloud 設定](#4-streamlit-cloud-設定)
5. [常見問題](#5-常見問題)

---

## 1. GitHub 上傳

### 步驟 1.1：建立 GitHub 倉庫

#### 方式 A：線上建立（推薦新手）

1. 訪問 https://github.com/new
2. 填寫倉庫名稱：
   ```
   台股價量獵人
   或
   taiwan-stock-price-hunter
   ```
3. 選擇描述：
   ```
   Taiwan Stock Price Volume Hunter - Demo Version
   ```
4. 選擇 `Public`（公開，便於分享）
5. 勾選 `Add a README file`
6. 點擊 `Create repository`

#### 方式 B：命令行建立（推薦有 Git 基礎）

```bash
# 1. 初始化本地倉庫
cd "c:\Users\mikec\Desktop\台股監控app\台股價量獵人(雲端展示版)"
git init

# 2. 配置 Git（若尚未配置）
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"

# 3. 新增所有檔案
git add .

# 4. 建立初始提交
git commit -m "Initial commit: Taiwan Stock Price Volume Hunter Demo Version"

# 5. 重命名主分支為 main（GitHub 預設）
git branch -M main
```

### 步驟 1.2：連接遠程倉庫並推送

#### 使用 HTTPS（推薦新手，無需 SSH 金鑰）

```bash
# 1. 在 GitHub 上建立空倉庫後，複製 HTTPS URL
# 格式: https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git

# 2. 新增遠程倉庫
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git

# 3. 推送至 GitHub
git push -u origin main

# 系統可能要求輸入 GitHub Token（不是密碼）
# GitHub Token 獲取方式：
# - 訪問 https://github.com/settings/tokens
# - 點擊「Generate new token」
# - 選擇「Generate new token (classic)」
# - 勾選 repo 權限
# - 複製 token，貼到命令行
```

#### 使用 SSH（推薦有經驗的開發者）

```bash
# 1. 若尚未設定 SSH 金鑰，執行：
ssh-keygen -t ed25519 -C "your.email@example.com"

# 2. 新增公鑰至 GitHub
# 訪問 https://github.com/settings/keys
# 點擊「New SSH key」，貼入 ~/.ssh/id_ed25519.pub 的內容

# 3. 新增遠程倉庫（SSH 格式）
git remote add origin git@github.com:YOUR_USERNAME/YOUR_REPO_NAME.git

# 4. 推送至 GitHub
git push -u origin main
```

### 步驟 1.3：驗證上傳

訪問你的 GitHub 倉庫 URL：
```
https://github.com/YOUR_USERNAME/YOUR_REPO_NAME
```

確認以下檔案已上傳：
- ✅ `app.py`
- ✅ `config.py`（已清空敏感資訊）
- ✅ `requirements.txt`
- ✅ `README.md`
- ✅ `DEMO_README.md`
- ✅ `persist/daily_state.json`
- ✅ `monitors/` 目錄

---

## 2. Streamlit Cloud 部署

### 步驟 2.1：訪問 Streamlit Cloud

1. 訪問 https://streamlit.io/cloud
2. 點擊右上角 `Sign in`
3. 使用 GitHub 帳戶登入（或建立新帳戶）

### 步驟 2.2：授權 GitHub 存取

首次登入時，GitHub 會要求授權 Streamlit Cloud 存取你的倉庫：

1. 點擊 `Authorize streamlit`
2. 輸入 GitHub 密碼確認
3. 選擇授權方式：
   - **推薦：All repositories**（允許部署任何倉庫）
   - 或 **Select repositories**（只允許特定倉庫）

### 步驟 2.3：建立新應用

1. 登入後進入 Streamlit Cloud 儀表板
2. 點擊左上角 `New app`
3. 填寫應用資訊：

```
Repository:  YOUR_USERNAME/YOUR_REPO_NAME
Branch:      main
File path:   app.py
```

4. 點擊 `Deploy`

### 步驟 2.4：等待部署完成

- 首次部署耗時 3-5 分鐘
- 點擊「View logs」查看部署進度
- 部署完成後會看到綠色「✓ Your app is live」提示

### 步驟 2.5：訪問應用

部署完成後，Streamlit Cloud 會為應用分配公開 URL，格式：
```
https://appname.streamlit.app
```

複製此 URL 可分享給他人使用。

---

## 3. 本地測試

### 步驟 3.1：驗證依賴

確保已安裝所有依賴：

```bash
cd "c:\Users\mikec\Desktop\台股監控app\台股價量獵人(雲端展示版)"

# 安裝依賴
pip install -r requirements.txt

# 驗證安裝
pip list | findstr streamlit
```

### 步驟 3.2：本地運行應用

```bash
# 進入應用目錄
cd "c:\Users\mikec\Desktop\台股監控app\台股價量獵人(雲端展示版)"

# 運行 Streamlit
streamlit run app.py
```

預期結果：
```
  You can now view your Streamlit app in your browser.

  Local URL: http://localhost:8501
  Network URL: http://192.168.x.x:8501
```

### 步驟 3.3：測試應用功能

在瀏覽器中訪問 `http://localhost:8501`，驗證：

- ✅ 頁面標題「📈 台股價量獵人」正常顯示
- ✅ 頁面頂部黃色「🎬 展示版」警告標誌正常顯示
- ✅ 五個監控區塊（開盤出量、漲跌停打開等）顯示資料
- ✅ 左側邊欄「⚠️ 特別警戒股」輸入框正常
- ✅ 「📋 系統日誌」展開後有日誌訊息
- ✅ 「清除所有觸發記錄」按鈕正常

### 步驟 3.4：測試互動功能

1. **添加警戒股**
   - 在「特別警戒股」輸入框輸入 `2330`（台積電代號）
   - 按 Enter
   - 驗證警戒股出現在下方清單

2. **清除警戒股**
   - 點擊警戒股旁的「移除」按鈕
   - 驗證警戒股被移除

3. **清除觸發記錄**
   - 點擊「清除所有觸發記錄」按鈕
   - 驗證所有區塊變為「尚無觸發標的」

4. **檢視日誌**
   - 展開「📋 系統日誌」
   - 驗證日誌訊息可見（例如「[展示版] Demo Mode 已啟用」）

### 步驟 3.5：停止本地應用

在終端機按 `Ctrl+C` 停止 Streamlit 伺服器。

---

## 4. Streamlit Cloud 設定

### 步驟 4.1：應用設定（可選）

登入 Streamlit Cloud 後，點擊應用名稱進入設定：

#### 基本資訊
- **App name**: 修改應用顯示名稱
- **URL**: 自動生成，無法修改
- **Visibility**: 保持 `Public`（公開）

#### 部署設定
- **Repository**: 選擇 GitHub 倉庫
- **Branch**: 選擇 `main`（推薦）
- **File path**: 確認為 `app.py`

#### 環境變數（若需要生產版本）
1. 點擊「Advanced settings」
2. 在「Secrets」區塊輸入敏感資訊：

```toml
# 僅當升級至生產版本時填寫
[api_config]
TAISHIN_ID = "A125519047"
TAISHIN_PASSWORD = "your_password"
CERT_PATH = "/path/to/cert.pfx"
CERT_PASSWORD = "your_cert_password"

[telegram]
TELEGRAM_TOKEN = "your_bot_token"
TELEGRAM_CHAT_ID = "your_chat_id"
```

然後修改 `config.py` 讀取這些值：
```python
import toml
try:
    secrets = toml.load(".streamlit/secrets.toml")
    DEMO_MODE = False
    TAISHIN_ID = secrets["api_config"]["TAISHIN_ID"]
    # ... 其他配置
except:
    DEMO_MODE = True
    TAISHIN_ID = ""
```

### 步驟 4.2：自動部署設定

Streamlit Cloud 預設自動部署：
- **觸發**: 每當推送到 `main` 分支時
- **延遲**: 約 5-10 秒後開始部署
- **耗時**: 2-3 分鐘

無需額外設定。

### 步驟 4.3：監控部署狀態

1. 進入應用設定
2. 點擊「Activity」標籤
3. 查看部署歷史與狀態：
   - 🟢 Green: 部署成功
   - 🟡 Yellow: 部署中
   - 🔴 Red: 部署失敗

### 步驟 4.4：查看應用日誌

1. 進入應用設定
2. 點擊「Logs」標籤
3. 查看應用執行日誌（包括錯誤訊息）

---

## 5. 常見問題

### Q: 部署失敗，錯誤訊息說「no module named 'taishin_sdk'」

**A:** 展示版不需要 `taishin_sdk`。檢查：
1. `requirements.txt` 中 `taishin_sdk` 是否被註解
2. 若不是，編輯 `requirements.txt`，將 `taishin_sdk` 行改為註解：
   ```
   # taishin_sdk  # 生產版本可選
   ```
3. 推送至 GitHub，Streamlit Cloud 會自動重新部署

### Q: 應用在 Streamlit Cloud 上運行很慢

**A:** 常見原因與解決方案：
1. **首次訪問時慢** - 正常，Streamlit 初始化需時間
2. **每次互動都很慢** - 檢查網路連線
3. **所有應用都慢** - 可能是 Streamlit Cloud 伺服器負載高，稍等後重試

### Q: 如何修改應用後重新部署？

**A:** 非常簡單：
1. 編輯本地程式碼
2. 推送至 GitHub：
   ```bash
   git add .
   git commit -m "Update: your changes description"
   git push origin main
   ```
3. Streamlit Cloud 自動檢測變更並重新部署（約 5-10 秒）

### Q: 如何分享應用？

**A:** 複製應用 URL 並分享：
```
https://appname.streamlit.app
```

任何人都可以訪問（無需 Streamlit 帳戶或安裝）。

### Q: 如何升級至生產版本（使用真實 API）？

**A:** 三個步驟：
1. 修改 `config.py`：
   ```python
   DEMO_MODE = False
   TAISHIN_ID = "A125519047"
   # ... 填寫其他敏感資訊
   ```
2. 在 Streamlit Cloud 設定中填寫 Secrets（推薦）
3. 安裝 `taishin_sdk`：
   ```
   # 在 requirements.txt 中取消註解：
   taishin_sdk
   ```
4. 推送至 GitHub

### Q: 應用無法連接到台新 API（生產版本）

**A:** 檢查清單：
1. ✅ `DEMO_MODE = False`
2. ✅ `TAISHIN_ID`, `TAISHIN_PASSWORD`, `CERT_PATH`, `CERT_PASSWORD` 已填入正確值
3. ✅ 憑證檔案 (`.pfx`) 在正確路徑
4. ✅ 網路連線正常
5. ✅ 台新 API 伺服器狀態正常

### Q: 能否在手機或平板上使用？

**A:** 可以！Streamlit Cloud 完全響應式設計，支援：
- 📱 iPhone / iPad
- 📱 Android 手機 / 平板
- 💻 桌機 / 筆記本

只需訪問應用 URL 即可，無需安裝應用。

### Q: 如何與他人協作開發？

**A:** 使用 GitHub 協作：
1. 邀請協作者進入 GitHub 倉庫
   - 倉庫設定 → Collaborators → Add people
2. 每位協作者克隆倉庫：
   ```bash
   git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
   ```
3. 建立功能分支進行開發：
   ```bash
   git checkout -b feature/your-feature-name
   ```
4. 推送至 GitHub 並建立 Pull Request
5. 審核並合併至 `main` 分支

---

## 📋 快速檢查清單

### 上傳前
- ✅ `config.py` 已清空敏感資訊
- ✅ `.gitignore` 已配置
- ✅ `requirements.txt` 已建立
- ✅ 本地測試通過
- ✅ 所有檔案已 `git add`

### 上傳時
- ✅ GitHub 倉庫已建立
- ✅ 本地倉庫已連接遠程
- ✅ 已推送至 `main` 分支
- ✅ GitHub 網頁確認檔案已上傳

### 部署前
- ✅ GitHub 倉庫為 Public
- ✅ 應用名稱、描述已填
- ✅ Repository、Branch、File path 已正確設定

### 部署後
- ✅ 部署狀態為綠色（成功）
- ✅ 應用 URL 可訪問
- ✅ 功能測試通過
- ✅ URL 已分享

---

## 🎯 故障排除流程

遇到問題時，按此順序檢查：

1. **檢查本地**
   ```bash
   streamlit run app.py
   ```
   若本地運行正常，問題可能在 Streamlit Cloud 配置

2. **檢查 GitHub**
   - 確認檔案已上傳
   - 確認 `requirements.txt` 正確
   - 確認敏感資訊已移除

3. **檢查 Streamlit Cloud 部署日誌**
   - 進入應用設定
   - 點擊「Logs」查看錯誤訊息
   - 根據錯誤訊息調整配置或程式碼

4. **強制重新部署**
   - 進入應用設定
   - 點擊「Reboot app」按鈕
   - 等待重新部署完成

5. **聯絡支援**
   - Streamlit Community: https://discuss.streamlit.io
   - GitHub Issues: 在倉庫建立 Issue 描述問題

---

## 📞 聯絡資訊

- 📧 Email: mikechao66@gmail.com
- 🔗 GitHub: https://github.com/YOUR_USERNAME
- 💬 Streamlit Community: https://discuss.streamlit.io

---

**祝部署順利！** 🚀

最後更新: 2026-06-17  
版本: 1.0 Demo
