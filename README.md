# Garmin → Notion Running Analyzer

這是一個在 Windows 本機執行的 Python 專案。它會從 Garmin Connect 抓取指定日期至今天的跑步活動，先將活動摘要、逐圈資料與完整詳細 JSON 寫入 Notion，再計算跑步分析並寫回 Notion。專案使用 **VS Code、uv、Git**，本文件假設你是第一次使用這些工具。

## 一、你最後會得到什麼

Notion 中會有四個資料庫。前三個保存原始資料，第四個保存分析結果。原始資料與分析結果分開，可以讓你日後修改分析方法而不破壞 Garmin 原始紀錄。

| Database 名稱 | 內容 | 一筆資料代表什麼 |
|---|---|---|
| `Garmin Raw Activities` | 活動摘要 | 一次 Garmin 活動 |
| `Garmin Raw Laps` | 逐圈／逐公里資料 | 一次活動中的一圈 |
| `Garmin Raw Detail JSON` | 完整活動詳細 JSON | 一次活動的完整 raw payload |
| `Garmin Running Analysis` | 分析結果 | 一次活動的衍生分析 |

程式中的 `src/main.py` 會以 `Activity ID` 或 `Activity ID-lap-圈次` 去重；重複執行不應產生重複活動頁面。

## 二、先安裝三個 Windows 工具

本版本使用最新版 `python-garminconnect`，目前需要 Python 3.12 或更新版本；你目前的 Python 3.10.10 需要先升級。請安裝 Python 3.12、VS Code，以及 uv。Python 從 [python.org](https://www.python.org/downloads/) 安裝，安裝畫面務必勾選 **Add Python to PATH**。VS Code 從 [code.visualstudio.com](https://code.visualstudio.com/) 安裝；開啟 VS Code 後，在 Extensions 安裝 Microsoft 的 **Python** 擴充套件。uv 可從 PowerShell 安裝：

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

關閉並重新開啟 PowerShell，確認兩個工具都可使用：

```powershell
python --version
uv --version
```

如果 `python` 找不到，可以改用 `py --version`；如果 `uv` 找不到，重新開啟 VS Code 與 PowerShell，讓 PATH 更新。

## 三、下載專案並在 VS Code 開啟

解壓縮附件 `garmin_notion_analyzer.zip`。建議放在不含中文字元與空格的路徑，例如 `C:\Projects\garmin_notion_analyzer`。在 PowerShell 執行：

```powershell
mkdir C:\Projects -ErrorAction SilentlyContinue
cd C:\Projects
# 將解壓縮後的 garmin_notion_analyzer 放在此處
cd .\garmin_notion_analyzer
code .
```

VS Code 開啟後，左側 Explorer 應看到 `src`、`README.md`、`pyproject.toml`、`.env.example` 與 `.gitignore`。如果沒有 `code` 指令，可以直接開啟 VS Code，選擇 **File → Open Folder**，再選取 `C:\Projects\garmin_notion_analyzer`。

## 四、使用 uv 建立環境與安裝套件

在 VS Code 選擇 **Terminal → New Terminal**，確認終端機目前位於專案根目錄，也就是可以看到 `pyproject.toml` 的資料夾。執行：

```powershell
uv sync
```

這會讀取 `pyproject.toml`，建立 `.venv` 並安裝所有依賴。之後執行程式時，優先使用 `uv run`，不需要手動啟用虛擬環境：

```powershell
uv run python src\main.py
```

若想讓 VS Code 的執行與型別檢查使用專案環境，按 `Ctrl+Shift+P`，執行 **Python: Select Interpreter**，選擇 `.venv\Scripts\python.exe`。

## 五、建立 Notion Integration

本專案要區分兩種 ID：**database ID 是寫入既有資料庫時使用的 ID；parent page ID 只是在程式自動建立資料庫時，指定資料庫要放在哪個父頁面。** 因為你會先手動建立 database，所以實際執行時只需要四個 database ID，不需要 `NOTION_PARENT_PAGE_ID`。

在 Notion 開啟 **Settings → Connections → Develop or manage integrations → New integration**，建立一個 Internal Integration，例如命名為 `Garmin Running Sync`。建立後複製 Token。Token 只放在本機 `.env`，不要貼到 GitHub、截圖或對話中。

接著在 Notion 建立一個父頁面，例如 `Garmin Running Data`。開啟父頁面右上角的 `•••`，選擇 **Connections → Connect to**，將 `Garmin Running Sync` 加入。沒有完成這一步時，Token 即使正確，程式仍可能收到 403 權限錯誤。

## 六、Notion Database schema：請逐欄建立

請在 `Garmin Running Data` 父頁面下手動建立以下四個 **Table – Full page**。每個資料庫都保留一個預設的 `Name` 欄位，Notion 類型必須是 **Title**，這是每個 database 唯一必需的標題欄位。建立完成後，從每個 database 的 URL 複製 database ID，填入第七節的四個環境變數。

### 6.1 `Garmin Raw Activities`

一列代表一次 Garmin 活動。建立 database 後，第一欄 `Name` 使用 Title 類型，其餘欄位依下表新增。

| 屬性名稱（完全一致） | Notion Property type | 建議格式／選項 | 必填 | 用途 |
|---|---|---|---|---|
| `Name` | Title | 例如 `東區 跑步` | 是 | 活動名稱 |
| `Activity ID` | Text | — | 是 | Garmin 活動唯一識別碼，用來去重 |
| `Start Date` | Date | 日期 | 是 | 活動本地日期 |
| `Activity Type` | Select | `running`、`treadmill`、`other` | 是 | 活動類型；依 Garmin metadata 區分戶外／室內跑步機 |
| `Distance km` | Number | Number | 否 | 活動距離，公里 |
| `Duration min` | Number | Number | 否 | 活動總時間，分鐘 |
| `Avg HR` | Number | Number | 否 | 平均心率，bpm |
| `Avg Pace min/km` | Number | Number | 否 | 平均配速，分鐘／公里 |
| `Raw Synced` | Checkbox | — | 否 | 是否已保存 raw data |
| `Raw JSON Hash` | Text | — | 否 | raw 詳細資料的 SHA-256 指紋 |

### 6.2 `Garmin Raw Laps`

一列代表一次活動中的一圈。Garmin 的 lap 可能是每公里，也可能是手動按圈或裝置自動分圈。

| 屬性名稱（完全一致） | Notion Property type | 建議格式／選項 | 必填 | 用途 |
|---|---|---|---|---|
| `Name` | Title | 例如 `24166120488-lap-1` | 是 | 活動 ID 與圈次組合鍵 |
| `Activity ID` | Text | — | 是 | 對應活動 |
| `Lap Index` | Number | Integer | 是 | 第幾圈 |
| `Lap Date` | Date | 日期 | 否 | 該圈日期 |
| `Distance m` | Number | Number | 否 | 該圈距離，公尺 |
| `Duration sec` | Number | Number | 否 | 該圈時間，秒 |
| `Avg Speed m/s` | Number | Number | 否 | 平均速度，m/s |
| `Avg HR` | Number | Number | 否 | 該圈平均心率 |
| `Cadence` | Number | Number | 否 | 步頻，steps/min |
| `Power W` | Number | Number | 否 | 跑步功率，瓦 |
| `Ground Contact ms` | Number | Number | 否 | 觸地時間，毫秒 |
| `Stride m` | Number | Number | 否 | 步幅，公尺 |
| `Vertical Osc cm` | Number | Number | 否 | 垂直振幅，公分 |
| `Raw JSON` | Text | — | 否 | 該圈未加工 JSON（顯示前 2,000 字元） |

### 6.3 `Garmin Raw Detail JSON`

一列代表一次活動的完整詳細 raw payload。完整 JSON 不放在欄位中，而是放在該 Notion page 的 code block 內容，避免單一 Text property 的字數限制。

| 屬性名稱（完全一致） | Notion Property type | 建議格式／選項 | 必填 | 用途 |
|---|---|---|---|---|
| `Name` | Title | 例如 `24166120488-detail` | 是 | raw payload 名稱 |
| `Activity ID` | Text | — | 是 | 對應活動 |
| `Start Date` | Date | 日期 | 否 | 活動日期 |
| `Measurement Count` | Number | Integer | 否 | Garmin detail measurement 數量 |
| `Metrics Count` | Number | Integer | 否 | Garmin metrics 數量 |
| `Raw JSON Hash` | Text | — | 否 | raw payload 指紋 |

### 6.4 `Garmin Running Analysis`

一列代表一次活動的分析結果。數值欄位全部使用 Notion **Number**，百分比欄位程式會寫入數值，例如 `5.2` 代表 5.2%。

| 屬性名稱（完全一致） | Notion Property type | 單位／意義 |
|---|---|---|
| `Name` | Title | 分析頁名稱 |
| `Activity ID` | Text | Garmin 活動 ID |
| `Date` | Date | 活動日期 |
| `Activity Type` | Select | `running`＝戶外／一般跑步、`treadmill`＝室內跑步機、`other`＝無法判定 |
| `Duration min` | Number | 活動時間，分鐘 |
| `Distance km` | Number | 距離，公里 |
| `Pace min/km` | Number | 平均配速，分鐘／公里 |
| `Pace CV %` | Number | 逐圈配速變異係數，百分比 |
| `Pace Range %` | Number | 最快與最慢分段相對平均配速的百分比全距 |
| `Half Split Diff %` | Number | 後半與前半配速差，百分比；正值代表後半較慢 |
| `MRS %` | Number | 後半程掉速率；正值代表後半較慢 |
| `Avg HR` | Number | 平均心率，bpm |
| `HR Drift %` | Number | 後半與前半心率變化代理值 |
| `HR Decoupling %` | Number | 前後半程速度／心率效率的變化率；正值代表後半效率下降 |
| `Garmin RPE` | Number | Garmin 原始 Perceived Effort；常見為 0–100，例如 50 代表 RPE 5 |
| `TRIMP` | Number | 由活動時間、平均 HR、MAX_HR、REST_HR 計算 |
| `sRPE Load` | Number | 從 detail 的 `summaryDTO.directWorkoutRpe` 自動轉成 RPE 後乘以活動分鐘 |
| `7d Load` | Number | 當日往前 7 天 Garmin Training Load 合計 |
| `28d Load` | Number | 當日往前 28 天 Garmin Training Load 合計 |
| `Cadence Change %` | Number | 逐圈首尾步頻變化 |
| `GCT Change %` | Number | 逐圈首尾觸地時間變化 |
| `Power W/kg` | Number | 從摘要、detail 或逐圈功率取得平均功率後除以 WEIGHT_KG |
| `Temperature C` | Number | 從摘要或 detail 溫度欄位取得平均攝氏溫度 |
| `Training Load` | Number | Garmin 活動訓練負荷 |
| `Body Battery Diff` | Number | Garmin 活動前後 Body Battery 差值 |
| `Notes` | Text | 欄位缺失或計算備註 |

### 6.5 新增欄位的計算定義

`Pace Range %` 是最快與最慢分段相對平均配速的百分比全距：`(平均配速−最快配速)/平均配速×100 + (最慢配速−平均配速)/平均配速×100`。數值越大表示分段配速越不均勻。

`MRS %` 是後半程掉速率：`(後半程平均秒數−前半程平均秒數)/前半程平均秒數×100`。正值表示後半程變慢，負值表示後半程加速。

`HR Decoupling %` 是前後半程速度／心率效率的變化率。效率定義為 `平均速度（m/s）/平均心率（bpm）`，公式是 `(前半程效率−後半程效率)/前半程效率×100`。正值表示後半程在每一下心跳所產生的速度效率下降。

目前程式會依 Garmin 的 `activityType`、`eventType` 與活動名稱判斷 `Activity Type`。包含 `treadmill`、`indoor` 或「跑步機」時分類為 `treadmill`；包含跑步相關 metadata 時分類為 `running`；其餘為 `other`。分類依賴 Garmin metadata，不是根據 GPS 是否存在推測，因此若 Garmin metadata 本身不正確，仍需人工修正 Notion Select 值。

> **重要：屬性名稱要完全一致，包括大小寫、空格、底線與單位。** 程式會依這些名稱傳送 Notion API property；名稱不同時會出現 `property not found` 或 `body failed validation`。

## 七、取得四個 database ID 與設定 `.env`

開啟每個 Notion database 的完整頁面，複製瀏覽器 URL。若 URL 類似 `https://www.notion.so/workspace/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx?v=...`，請複製 `?v=` 前面的 32 個英數字元；這就是 database ID。連字號可保留，程式會自動移除。請分別取得四個 database 的 ID：`Garmin Raw Activities`、`Garmin Raw Laps`、`Garmin Raw Detail JSON` 與 `Garmin Running Analysis`。

在 VS Code Explorer 右鍵 `.env.example`，選擇 **Copy**，再右鍵空白處選擇 **Paste**，將副本改名為 `.env`。Windows 可能會隱藏副檔名，請確認檔案名稱是 `.env` 而不是 `.env.txt`。填入：

```dotenv
GARMIN_EMAIL=你的Garmin Connect登入Email
GARMIN_PASSWORD=你的Garmin Connect密碼
GARMINTOKENS=%USERPROFILE%\\.garminconnect
NOTION_TOKEN=你的NotionIntegrationToken
NOTION_RAW_ACTIVITIES_DB_ID=Garmin Raw Activities的database ID
NOTION_RAW_LAPS_DB_ID=Garmin Raw Laps的database ID
NOTION_RAW_DETAIL_DB_ID=Garmin Raw Detail JSON的database ID
NOTION_ANALYSIS_DB_ID=Garmin Running Analysis的database ID
NOTION_PARENT_PAGE_ID=
START_DATE=2026-06-01
END_DATE=
NOTION_VERSION=2022-06-28
STORE_DETAIL_JSON_BLOCKS=true
MAX_HR=你的最大心率
REST_HR=你的靜息心率
WEIGHT_KG=你的體重公斤
```

`END_DATE` 留白會使用今天。`MAX_HR`、`REST_HR` 與 `WEIGHT_KG` 用來計算 TRIMP 與 W/kg；sRPE Load 會自動讀取 Garmin detail 的 `summaryDTO.directWorkoutRpe`。Garmin 常見格式是 0–100，例如 30 代表 RPE 3，程式會自動除以 10；若回傳值已是 0–10，則直接使用。若不確定個人最大心率或靜息心率，請先留白，不要使用不可靠的估計值。`GARMINTOKENS` 指向 token 儲存資料夾；如果你要直接貼 JSON，請將完整 `garmin_tokens.json` 壓縮成單行後貼到 `GARMIN_TOKEN_JSON=`。程式啟動時會先驗證 JSON，寫入 `%USERPROFILE%\\.garminconnect\\garmin_tokens.json`，再使用它恢復登入。若你原本已有 token 檔案，建議只使用其中一種來源，不要讓 `.env` 的舊 JSON 覆蓋新 token。Garmin 密碼只在 token 不存在或失效時作為 fallback，不會寫入 Notion。請不要把 `.env` 或 token 檔案加入 Git。

## 八、第一次執行

回到 VS Code Terminal，執行：

```powershell
uv sync
uv run python src\main.py
```

第一次執行時，程式會優先讀取 `.env` 中的四個 database ID，直接使用你手動建立的 database，並把 ID 保存到 `data\notion_databases.json`。四個 ID 必須全部填寫；若沒有填寫，程式才會嘗試使用 `NOTION_PARENT_PAGE_ID` 自動建立 database。

程式流程是：先登入 Garmin、取得日期範圍內的跑步活動、取得每筆活動的詳細資料與逐圈資料、先寫入三個 raw database、等全部活動讀取完成後計算 7 日／28 日負荷，最後才寫入 `Garmin Running Analysis`。

## 九、Git 版本控制：第一次設定

先在專案根目錄確認 `.gitignore` 存在，內容至少要包含 `.env`、`.venv/`、`__pycache__/`、`data/*.json` 與 `logs/`。接著執行：

```powershell
git init
git add .
git status
git commit -m "Initial Garmin Notion analyzer project"
```

`git status` 應該看不到 `.env`、`.venv` 或個人 raw data。若你想放到 GitHub，先在 GitHub 建立一個新的空白 repository，不要勾選自動建立 README，然後執行：

```powershell
git branch -M main
git remote add origin https://github.com/你的帳號/你的repository.git
git push -u origin main
```

日後修改程式的標準流程是：

```powershell
git status
git add .
git commit -m "Describe your change"
git push
```

不要執行 `git add .env`。如果不小心把 Token 提交過，立即在 Notion Integration 頁面重新產生 Token，因為單純刪除 Git commit 不代表秘密已經安全。

## 十、常見錯誤

`401 Unauthorized` 通常表示 Notion Token 錯誤；請重新複製 Token 並確認 `.env` 沒有多餘引號或空格。`403 restricted_resource` 通常表示父頁面尚未透過 **Connections** 分享給 Integration。`404 object_not_found` 通常表示 database ID 錯誤，或 Integration 沒有該 database 權限。`401/403` 的 Garmin 登入錯誤則先確認 Garmin Connect 網頁能登入、帳號 Email 正確，並注意兩步驟驗證或地區登入限制。

如果看到 `property not found`，請檢查 Notion 欄位名稱與第六節逐字相同，特別是 `Avg HR`、`Ground Contact ms`、`Power W/kg` 和百分比欄位。若看到 Notion rate limit，可稍後重新執行；程式已有基本間隔，但大量逐圈資料仍可能需要分批同步。

## 十二、Garmin token JSON、tokenstore 與 429 限流注意事項

新版套件會優先使用 `GARMINTOKENS` 指向的本地 tokenstore；Windows 的預設值是 `%USERPROFILE%\\.garminconnect`。若使用 `GARMIN_TOKEN_JSON`，請把 `garmin_tokens.json` 內容壓縮成一行，例如在 PowerShell 執行 `Get-Content .\\garmin_tokens.json -Raw | ConvertFrom-Json | ConvertTo-Json -Compress`，再將輸出完整貼到 `.env` 的 `GARMIN_TOKEN_JSON=` 後面。程式會在啟動時把它寫入 tokenstore，再呼叫 `g.login(tokenstore)`。這個 token 等同密碼，請勿提交到 GitHub、寄給他人或放入 Notion；`.gitignore` 已忽略 `.env`。

程式在每一筆活動的 detail 與 splits 請求前，預設加入 30–45 秒隨機延遲，可用 `GARMIN_JITTER_MIN_SECONDS` 與 `GARMIN_JITTER_MAX_SECONDS` 調整。這是降低請求突發量的保護，不是保證能繞過 Garmin 或 Cloudflare 限流。若收到 HTTP 429，請停止重試並等待數小時至 24 小時；反覆登入會讓限流更久。程式不會自動用密碼反覆重試。

你目前是 Python 3.10.10；因官方最新版 `python-garminconnect` 已要求 Python 3.12+，請在 PowerShell 執行：

```powershell
uv python install 3.12
uv python pin 3.12
uv sync
uv run python src\\main.py
```

如果 `uv python install` 不可用，請從 python.org 安裝 Python 3.12，再重新開啟 VS Code。

## 十三、目前分析範圍與限制

目前可由 Garmin 活動摘要、detail 與逐圈資料計算平均配速、配速變異係數、前後半程配速差、心率漂移代理值、步頻變化、觸地時間變化、平均溫度、Garmin Training Load、7 日／28 日滾動負荷、Body Battery 變化、簡化 TRIMP、sRPE Load 與 Power W/kg。TRIMP 由 `MAX_HR`、`REST_HR` 計算；sRPE Load 由 Garmin detail 的 `summaryDTO.directWorkoutRpe` 自動計算；W/kg 由功率與 `WEIGHT_KG` 計算。若 Garmin 沒有回傳 Perceived Effort，該筆會保持空值並在 Notes 說明。

GPS、心率、步頻、觸地時間、垂直振幅與跑步功率都可能含有裝置與演算法誤差。這個專案適合個人縱向比較，不應把單次 Garmin 分數視為實驗室測量、醫療診斷或受傷判定。請不要把 Garmin 密碼、Notion Token、精確 GPS 路線或原始個資提交到公開 repository。

## 十四、每日自動同步

完成 6 月 1 日的歷史資料補抓後，不需要每天再次設定 6 月 1 日。建議將 `.env` 改成每日增量模式：

```dotenv
START_DATE=auto
END_DATE=auto
SYNC_DAYS_BACK=2
```

`START_DATE=auto` 會以今天往前推算，`END_DATE=auto` 會使用今天；`SYNC_DAYS_BACK=2` 代表每次抓取最近 2 天到今天。保留 2 天重疊範圍是為了處理 Garmin 活動延遲同步，程式會依 Activity ID 更新，不會產生重複頁面。若你每天固定在 Garmin 活動完成後才執行，也可以改成 `SYNC_DAYS_BACK=1`；若常常隔幾天才開電腦，建議改成 3–7。

專案內的 `run_daily.ps1` 是 Windows PowerShell 啟動腳本。請先用 VS Code 開啟它，把 `$Project` 改成你的實際專案路徑，例如：

```powershell
$Project = "C:\Python\Python310.10\garmin_notion_analyzer"
```

先手動測試：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\run_daily.ps1
```

確認成功後建立 Windows 工作排程器。從 Windows 開始功能表搜尋「工作排程器」，選擇「建立基本工作」，名稱輸入 `Garmin Notion Daily Sync`，觸發程序選「每天」，時間建議設定在 Garmin 活動同步完成後，例如每天 23:30。動作選「啟動程式」，程式輸入：

```text
powershell.exe
```

引數輸入：

```text
-NoProfile -ExecutionPolicy Bypass -File "C:\Python\Python310.10\garmin_notion_analyzer\run_daily.ps1"
```

完成後，在工作排程器中找到該工作，按右鍵選「執行」測試。請確認電腦在排程時間開機並已連線網路；若希望電腦喚醒後執行，可在工作內容的「條件」頁面啟用「喚醒電腦以執行此工作」。

每日同步的兩種方式比較如下：

| 作法 | 優點 | 缺點 | 適用情況 |
|---|---|---|---|
| 手動執行 `uv run python src\\main.py` | 最容易診斷錯誤，不需設定 Windows 排程 | 必須自己記得執行 | 先測試、偶爾使用 |
| Windows 工作排程器執行 `run_daily.ps1` | 每天自動執行，使用本機 token 與 `.env` | 電腦必須開機且有網路；429 時仍需等待 | 日常固定同步 |

每日程式流程是：使用本地 Garmin token 恢復登入、查詢最近幾天活動、取得新活動的 detail 與 splits、先更新 Notion raw data，再以 Activity ID 更新分析結果。若 Garmin 沒有新活動，程式會完成同步而不應產生重複資料。由於 Garmin 可能延遲同步，建議不要把 `SYNC_DAYS_BACK` 設成 0。


## 十三、負荷欄位與 Notion 趨勢圖

### sRPE Load 與 Garmin Training Load 的差異

`Garmin RPE` 是 Garmin API 回傳的原始 Perceived Effort，常見尺度是 0–100；例如 50 代表一般 0–10 尺度的 RPE 5。程式會保留這個原始數值在 `Garmin RPE` 欄位，再將它標準化為 0–10 計算 `sRPE Load`。`sRPE Load` 是活動後主觀感受的內在負荷，公式為 `標準化 RPE × 活動分鐘`。它反映你主觀感受到的整體壓力，包含心肺、肌肉、睡眠、心理與環境等影響。Garmin `Training Load` 則是 Garmin 的專有演算法估計值，主要依活動強度、心率、時間及裝置可取得的生理資料計算。兩者不是同一個尺度，不應直接相加，也不應期待數值一樣。

目前程式的 `7d Load` 與 `28d Load` 是依每筆活動的 Garmin `Training Load` 加總：`7d Load` 是活動日期當天往前 6 天至當天的 Training Load 總和；`28d Load` 是當天往前 27 天至當天的 Training Load 總和。它們不是 sRPE Load 的滾動加總。如果你想比較主觀與 Garmin 負荷，可以另外在 Notion 建立公式或由程式增加 `sRPE 7d Load`、`sRPE 28d Load`，不要混用兩種尺度。

`Garmin Running Analysis` 建議至少包含以下三個 Garmin 負荷欄位：`Training Load`、`7d Load`、`28d Load`。三者都使用 Notion **Number**。新版程式在使用既有 database 時會嘗試自動補上缺少的三個欄位；若自動補欄位受到 Notion 權限限制，也可以手動建立同名 Number properties。

### 建議建立的 Notion 折線圖

Notion 的圖表功能若可用，建議以 `Date` 為 X 軸、以數值欄位為 Y 軸；若你的工作區沒有適用的圖表視圖，也可以將 database 匯出 CSV，再用 Excel、Google Sheets 或 Python 繪圖。不要把不同單位的指標放在同一條 Y 軸上。

| 圖表 | X 軸 | Y 軸 | 趨勢意義 |
|---|---|---|---|
| Garmin 負荷趨勢 | Date | Training Load、7d Load、28d Load | Training Load 是單次刺激；7d Load 上升代表短期負荷增加；28d Load 反映近期累積背景。7d 明顯高於 28d 的平常水準，應檢查是否突然增加。 |
| 主觀與演算法負荷 | Date | sRPE Load、Training Load | 兩者同向上升表示主觀與 Garmin 都認為負荷增加；sRPE 明顯高於平常而 Training Load 沒升，可能反映睡眠、肌肉疲勞、炎熱或心理壓力。 |
| 跑量與時間 | Date | Distance km、Duration min | 觀察週期化與恢復日。距離和時間連續多週上升，應同步看 7d／28d Load，不要只看單次距離。 |
| 配速穩定度 | Date | Pace CV %、Pace Range % | 兩者同時下降代表均速控制變好；Pace CV 低但 Pace Range 高，表示可能只有少數極端分段，應查看 Raw Laps。 |
| 後段耐力 | Date | MRS %、Half Split Diff % | 正值持續升高代表後半程掉速增加；若長跑反覆高於個人基準，先放慢前半程並檢查補水、氣溫與恢復。 |
| 心率效率 | Date | HR Drift %、HR Decoupling % | 兩者同時上升代表後半程心率成本增加、速度效率下降；若只在高溫活動上升，先按 Temperature C 分組比較。 |
| 跑步經濟性代理 | Date | Power W/kg、Pace min/km、Avg HR | 在相近路線與溫度下，若同配速需要更高 W/kg 與更高 HR，可能代表當日疲勞或經濟性下降；不要跨裝置直接比較絕對功率。 |
| 環境與心率 | Date | Temperature C、HR Drift % | 溫度上升伴隨 HR Drift 上升，較支持環境壓力解釋；應以相近溫度的活動比較。 |
| 恢復與負荷 | Date | Body Battery Diff、7d Load、sRPE Load | Body Battery 消耗變大且 7d Load、sRPE 同時上升，代表恢復壓力累積；可安排低強度或休息日。 |

建議優先建立三張圖：第一張是 `Training Load`、`7d Load`、`28d Load`；第二張是 `MRS %`、`HR Drift %`、`HR Decoupling %`；第三張是 `Pace min/km`、`Avg HR`、`Power W/kg`。第三張最好分開不同單位或使用雙軸，因為分鐘／公里、bpm 與 W/kg 不能直接用同一尺度判讀。

這些趨勢是訓練監控指標，不是疾病診斷。單日異常先檢查路線、溫度、睡眠、補水、裝置品質與活動類型；連續數週在相似條件下出現惡化，才適合調整訓練量或尋求專業評估。


## 十四、Garmin Weekly Running Analysis 每週資料庫

本專案現在可以從既有的 `Garmin Running Analysis` daily database 重新彙總，寫入另一個 `Garmin Weekly Running Analysis` database。Weekly database 不會重新呼叫 Garmin，也不會取代 daily database；它只整理 daily analysis 的結果。每次同步完成 daily analysis 後，程式會查詢整個 daily database 並更新每週頁面。

請先在 Notion 建立一個 `Table – Full page` database，名稱建議為 `Garmin Weekly Running Analysis`，第一欄保留 `Name`（Title），再建立以下 properties：

| Property | Notion type | 意義 |
|---|---|---|
| `Week Key` | Text | 週一日期，例如 `2026-09-01`，用來去重 |
| `Week Start` | Date | 該週週一 |
| `Week End` | Date | 該週週日 |
| `Training Sessions` | Number | 該週跑步活動次數 |
| `Training Frequency CV` | Number | 最近最多 4 週訓練次數的變異係數，`標準差／平均值` |
| `Training Frequency Class` | Select | `高度規律`、`中度規律`、`波動較大` |
| `Distance km` | Number | 該週跑步距離合計 |
| `Duration min` | Number | 該週活動時間合計 |
| `Training Load` | Number | 該週 Garmin Training Load 合計 |
| `sRPE Load` | Number | 該週 sRPE Load 合計 |
| `Avg HR` | Number | 該週活動平均心率的平均值 |
| `Avg Pace min/km` | Number | 該週活動平均配速的平均值 |
| `HR Efficiency Slope` | Number | 最近最多 6 週速度／心率效率的線性回歸斜率 |
| `HR Efficiency Trend` | Select | `持續進步`、`持平`、`下滑` |
| `Recovery Burden Ratio` | Number | `−Body Battery Diff 合計／Training Load 合計` |
| `Recovery Burden Change` | Number | 近期恢復負擔比平均減早期恢復負擔比平均 |
| `Recovery Resilience Trend` | Select | `恢復韌性提升`、`持平`、`恢復韌性下降` |
| `MRS Avg %` | Number | 該週 MRS 平均值 |
| `HR Drift Avg %` | Number | 該週 HR Drift 平均值 |
| `HR Decoupling Avg %` | Number | 該週 HR Decoupling 平均值 |
| `Temperature Avg C` | Number | 該週活動溫度平均值 |
| `Notes` | Text | 資料不足或解讀限制 |

訓練頻率 CV 的分類為：`CV < 0.3` 是高度規律、`0.3 ≤ CV < 0.6` 是中度規律、`CV ≥ 0.6` 是波動較大。CV 會把沒有跑步的週視為 0 次，因此不會因為缺少活動而忽略空週。

HR Efficiency Slope 使用每週平均配速與平均心率先計算速度／心率效率：`效率 = 1000 ÷（平均配速 min/km × 60）÷ 平均 HR`。程式對最近最多 6 個有有效效率值的週次做線性回歸，斜率大於 `0.001` 分類為「持續進步」，介於 `-0.001` 與 `0.001` 分類為「持平」，小於 `-0.001` 分類為「下滑」。斜率單位是每週效率變化，不能與百分比欄位直接比較。

恢復負擔比定義為 `−Body Battery Diff 合計 ÷ Training Load 合計`。例如一週 Body Battery Diff 合計為 `−30`，Training Load 合計為 `150`，恢復負擔比為 `0.20`。`Recovery Burden Change` 是近期最多 3 週平均減去較早最多 3 週平均：小於 `−0.05` 分類為「恢復韌性提升」、介於 `−0.05` 與 `0.05` 分類為「持平」、大於 `0.05` 分類為「恢復韌性下降」。少於 4 週資料時，程式會在 Notes 提醒這只是初步值。

在 `.env` 增加第五個 database ID：

```dotenv
NOTION_WEEKLY_DB_ID=Garmin Weekly Running Analysis 的 database ID
```

然後執行：

```powershell
uv sync
uv run python src\main.py
```

程式會先更新 daily database，再查詢完整的 `Garmin Running Analysis`，最後以 `Week Key` 更新或建立每週頁面。若尚未設定 `NOTION_WEEKLY_DB_ID`，daily analysis 仍會正常執行，但終端機會顯示略過每週彙總。若週資料庫缺少欄位，程式會嘗試透過 Notion API 自動補上。


## 十五、Weekly 歷史補算與日常更新的分工

如果 `Garmin Running Analysis` daily database 已經有歷史資料，請不要為了建立 weekly database 而把 Garmin 主程式從 6/1 重新執行。專案現在提供兩個不同用途的指令：

| 指令 | 用途 | 是否呼叫 Garmin |
|---|---|---|
| `uv run python src\\weekly_backfill.py` | 第一次建立或重建所有歷史週資料 | 否，只查詢 Notion daily database |
| `uv run python src\\main.py` | 每日抓最近活動、更新 daily，再更新 weekly | 是，但只依 `START_DATE`／`SYNC_DAYS_BACK` 抓指定日期 |

第一次使用 weekly database 時，先在 `.env` 填入：

```dotenv
NOTION_WEEKLY_DB_ID=Garmin Weekly Running Analysis 的 database ID
```

接著執行歷史補算：

```powershell
cd C:\Python\Python310.10\garmin_notion_analyzer
uv sync
uv run python src\\weekly_backfill.py
```

執行時應看到：

```text
開始 weekly backfill：只讀取 Notion Garmin Running Analysis，不呼叫 Garmin。
Weekly Analysis：已更新 N 週資料。
weekly backfill 完成。
```

完成歷史補算後，日常仍使用：

```powershell
uv run python src\\main.py
```

日常流程是先以 `START_DATE=auto` 與 `SYNC_DAYS_BACK=2` 抓最近 2 天 Garmin 活動，更新 daily database，然後再從完整 daily database 重新計算 weekly database。由於 weekly 計算只查詢 Notion daily database，不會為了 weekly 歷史資料重新呼叫 Garmin。

如果某一週的 daily 資料後來被修正，重新執行 `weekly_backfill.py` 即可重新整理所有週；它會以 `Week Key` 更新既有頁面，不會新增重複週頁面。


## 十六、使用 GitHub Actions 每日執行

專案提供 `.github/workflows/notion_analyzer.yml`。它會在每天台灣時間 20:00 執行，並可從 GitHub Actions 頁面使用 `workflow_dispatch` 手動執行。GitHub Actions workflow 的排程現在可以在 cron 旁指定 IANA timezone，因此 YAML 使用：

```yaml
- cron: "0 20 * * *"
  timezone: "Asia/Taipei"
```

即使排程使用台灣時區，程式本身仍必須明確指定 `APP_TIMEZONE=Asia/Taipei`。新版主程式在 `START_DATE=auto` 或 `END_DATE=auto` 時，會使用 `Asia/Taipei` 的日期計算，不依賴 GitHub runner 的系統時區。活動與逐圈頁面的日期仍優先使用 Garmin 的 `startTimeLocal`，Weekly database 則使用已寫入 daily database 的 local date。

請把以下內容加入 GitHub repository 的 **Settings → Secrets and variables → Actions → New repository secret**。Secret 名稱必須完全一致：

| Secret | 內容 |
|---|---|
| `NOTION_TOKEN` | Notion Internal Integration token |
| `NOTION_RAW_ACTIVITIES_DB_ID` | Raw Activities database ID |
| `NOTION_RAW_LAPS_DB_ID` | Raw Laps database ID |
| `NOTION_RAW_DETAIL_DB_ID` | Raw Detail JSON database ID |
| `NOTION_ANALYSIS_DB_ID` | Garmin Running Analysis database ID |
| `NOTION_WEEKLY_DB_ID` | Garmin Weekly Running Analysis database ID |
| `GARMIN_TOKEN_JSON` | 完整、有效的 `garmin_tokens.json` JSON 內容；可保留換行 |
| `GARMIN_EMAIL` | Garmin Connect email，只有 token 失效時作為 fallback |
| `GARMIN_PASSWORD` | Garmin Connect password，只有 token 失效時作為 fallback |
| `MAX_HR` | 個人最大心率，例如 `177` |
| `REST_HR` | 個人靜息心率，例如 `57` |
| `WEIGHT_KG` | 體重公斤，例如 `77` |

`GARMIN_TOKEN_JSON` 與 Garmin 密碼都是高敏感憑證，不要放在 repository 檔案，不要寫入 Notion，也不要在 workflow log 中 `echo`。Workflow 會把 token JSON 傳給程式，程式在 runner 暫存環境寫入 `.garminconnect/garmin_tokens.json` 後使用 token 優先登入；`.garminconnect` 不會被 commit 回 repository。

GitHub Actions runner 的執行流程為：先 checkout、安裝 Python 3.12 與 uv、使用 `uv sync --frozen` 安裝 lock 檔依賴、印出 UTC 與台灣時間供診斷，最後執行：

```text
uv run python src/main.py
```

程式的每日模式為 `START_DATE=auto`、`END_DATE=auto`、`SYNC_DAYS_BACK=2`，因此每天會抓今天往前兩天至今天的資料，先更新 daily databases，再從 Notion daily database 更新 Weekly database。這個重疊區間是為了吸收 Garmin 延遲同步，不是要重新抓取全部歷史活動。

### 時區與日期的注意事項

排程時間與資料日期是兩個不同問題。`timezone: Asia/Taipei` 決定 workflow 何時啟動；`APP_TIMEZONE=Asia/Taipei` 決定程式在自動日期模式下把「今天」判定為哪一天；Garmin `startTimeLocal` 決定個別活動與 Raw Laps 的 local date。三者同時設定，才能避免台灣午夜前後因 UTC 日期不同而造成日期錯置。

Workflow 執行開始時會輸出：

```text
GitHub runner UTC: ...
Taiwan local time: ...
Application date: YYYY-MM-DD
```

若三者顯示的台灣日期正確，9/4 這類活動的 `Date` 與 `Lap Date` 應沿用 Garmin local date，而不會因 GitHub runner 使用 UTC 被改成前一天。

## References

[5]: https://github.blog/changelog/2026-03-19-github-actions-late-march-2026-updates/ "GitHub Actions: Timezone support for scheduled workflows"
[6]: https://docs.github.com/actions/using-workflows/events-that-trigger-workflows "GitHub Actions events that trigger workflows"
