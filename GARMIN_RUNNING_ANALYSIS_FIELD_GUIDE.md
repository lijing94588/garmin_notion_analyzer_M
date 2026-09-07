# Garmin Running Analysis 欄位詳細說明

> 本文件對應目前 Python 專案寫入 Notion 的 `Garmin Running Analysis` database。每個欄位均說明資料來源、計算方式、範例、數值意義、判讀方式與主要限制。除非特別註明，百分比欄位寫入的是數值，例如 `5.2` 代表 `5.2%`。

## 一、先了解資料分層

本分析表同時包含三種資料。第一種是 Garmin 原始或近似原始資料，例如 `Activity ID`、`Avg HR`、`Training Load`、`Garmin RPE`。第二種是程式根據逐圈資料推導出的指標，例如 `Pace CV %`、`MRS %` 與 `HR Decoupling %`。第三種是跨日期累積指標，例如 `7d Load` 與 `28d Load`。

不同來源的欄位不能混為同一種尺度。尤其 `Garmin RPE`、`sRPE Load` 與 `Training Load` 的數值意義不同；`7d Load` 與 `28d Load` 目前是根據 Garmin `Training Load` 計算，不是根據 `sRPE Load` 計算。

## 二、基本識別與活動條件欄位

| 欄位 | 數值／資料怎麼算出來 | 範例 | 數值代表什麼意義／怎麼解讀 |
|---|---|---|---|
| `Name` | 取 Garmin 活動名稱；若沒有則使用預設名稱 `Garmin Analysis`。 | `Morning Run` | 方便辨識活動，不參與數值分析。名稱可能由使用者在 Garmin Connect 修改。 |
| `Activity ID` | 直接取 Garmin 的活動唯一識別碼。 | `24230374024` | 用來把 Garmin、Raw Activities、Raw Laps、Raw Detail JSON 與 Analysis 對在一起，也是程式更新 Notion 頁面及避免重複的主要鍵值。 |
| `Date` | 優先取 Garmin `startTimeLocal` 的日期部分。 | `2026-09-04` | 活動發生地的本地日期。與 UTC 日期不同；跨午夜活動應以此欄位歸類。 |
| `Activity Type` | 讀取 Garmin `activityType`、`eventType` 與活動名稱。包含 `treadmill`、`indoor` 或「跑步機」時分類為 `treadmill`；其他跑步 metadata 分類為 `running`。 | `running`、`treadmill` | 用來分開戶外跑與室內跑步機。比較配速、GPS、溫度與功率時應先按活動類型分組；室內與戶外不宜直接混成一條基準線。 |
| `Duration min` | `duration` 秒數除以 60。 | `70` 秒數代表 `70 分鐘` | 活動總時間。搭配 `Distance km` 可觀察跑量與平均速度；也用於 TRIMP 與 sRPE Load。 |
| `Distance km` | Garmin 距離公尺除以 1,000。 | `8.10` | 活動總距離。應與活動類型、地形及 GPS 品質一起解讀；跑步機距離可能與戶外 GPS 距離有不同誤差特性。 |

## 三、配速與分段穩定度

| 欄位 | 數值／資料怎麼算出來 | 範例 | 數值代表什麼意義／怎麼解讀 |
|---|---|---|---|
| `Pace min/km` | Garmin 平均速度 `m/s` 轉成分鐘／公里：`1000 ÷ 平均速度 ÷ 60`。數值越小代表越快。 | `8.64` 代表 `8:38 min/km` | 整場平均配速。適合和相同活動類型、相近路線及相近溫度的活動比較，不宜單獨判斷能力。 |
| `Pace CV %` | 對逐圈平均配速求平均與標準差：`標準差 ÷ 平均配速 × 100`。 | `3.10%` | 配速相對變異程度。低值通常表示分段較均勻；高值可能來自變速、坡度、紅綠燈、GPS 異常或圈數太少。實務上可先把 `<5%` 視為相對穩定、`5–10%` 視為有變化、`>10%` 視為需要查看 Raw Laps 的訊號，但不是普遍醫學門檻。 |
| `Pace Range %` | 取最快與最慢分段相對平均配速的百分比全距：`(平均−最快)/平均×100 + (最慢−平均)/平均×100`。等價於 `(最慢−最快)/平均×100`。 | 平均 `600 秒/km`、最快 `570`、最慢 `630`：`(30/600×100)+(30/600×100)=10%` | 補充 CV 的極端值資訊。低值代表最快與最慢分段接近；高值代表配速全距大。`<5%` 可視為集中，`5–10%` 表示可見變化，`>10%` 先檢查是否為間歇、坡度或 GPS 異常。 |
| `Half Split Diff %` | 前半程與後半程平均配速的差：`(後半平均秒數−前半平均秒數) ÷ 前半平均秒數 × 100`。 | 前半 `590 秒/km`、後半 `620 秒/km`：`5.08%` | 正值代表後半程變慢，負值代表後半程變快。適合看整體 pacing strategy；短活動或圈數少時不穩定。 |
| `MRS %` | 與 `Half Split Diff %` 使用相同公式：`(後半程平均秒數−前半程平均秒數) ÷ 前半程平均秒數 × 100`。 | 前半 `600`、後半 `630`：`5%` | MRS 是明確命名的後半程掉速率。`-3% 至 +3%` 可視為大致均速，`+3% 至 +8%` 為輕中度掉速，`>+8%` 為值得檢查的掉速；若是刻意漸速跑，負值可能是正常策略。 |

### 配速欄位的綜合例子

如果一場 8 km 跑的 `Pace CV = 3%`、`Pace Range = 12%`、`MRS = +2%`，表示大部分圈數可能很穩定，但最快與最慢之間仍有一個或數個極端分段。此時應打開 Raw Laps 查看是否有紅綠燈、補水、坡度或 GPS 問題，而不是直接認定整場配速失控。

## 四、心率與有氧效率

| 欄位 | 數值／資料怎麼算出來 | 範例 | 數值代表什麼意義／怎麼解讀 |
|---|---|---|---|
| `Avg HR` | Garmin 活動平均心率，通常來自 `averageHR` 或 detail summary。 | `126 bpm` | 整場平均心率。是內在負荷指標，但不能只靠 bpm 判定 Zone 2；應使用個人最大心率、靜息心率或乳酸閾值設定。 |
| `HR Drift %` | 目前程式以逐圈前後半程平均心率作簡化代理：`(後半平均 HR−前半平均 HR) ÷ 前半平均 HR × 100`。 | 前半 `124`、後半 `136`：`9.68%` | 正值表示後半心率上升。`<5%` 可視為穩定，`5–10%` 需注意，`>10%` 在均速長跑中值得檢查溫度、補水、前段配速與疲勞。它不是完整的實驗室 aerobic decoupling。 |
| `HR Decoupling %` | 先算前後半程效率：`效率 = 平均速度（m/s）÷ 平均心率（bpm）`；再算 `(前半效率−後半效率) ÷ 前半效率 × 100`。 | 前半效率 `0.0180`、後半 `0.0162`：`10%` | 正值表示後半每一下心跳產生的速度效率下降。`<5%` 通常穩定，`5–10%` 需觀察，`>10%` 表示後半效率明顯下降。應只比較相近距離、地形、氣溫與均速活動。 |
| `TRIMP` | 先算心率儲備：`HRR=(Avg HR−REST_HR)/(MAX_HR−REST_HR)`；再用簡化公式：`Duration min × HRR × exp(1.92×HRR)`。需要 `.env` 的 `MAX_HR` 與 `REST_HR`。 | 70 分鐘、Avg HR 126、靜息 60、最大 180：HRR=`0.55`，TRIMP 約 `110.7 AU` | 心率與時間的內在負荷估計。最適合和自己的 4–6 週中位數比較，不宜直接與 Garmin Training Load 當成相同單位。最大心率設定錯誤會讓所有 TRIMP 系統性偏高或偏低。 |

### 心率綜合例子

如果 `HR Drift = 12%`、`HR Decoupling = 14%`，而 `Temperature C` 也高於平常，較合理的第一個解釋是環境與補水壓力，而不是立即判定心肺能力下降。如果在相近氣溫、相同路線下連續數週仍出現相同趨勢，才適合檢討長跑前段配速與恢復安排。

## 五、主觀負荷與 Garmin 負荷

| 欄位 | 數值／資料怎麼算出來 | 範例 | 數值代表什麼意義／怎麼解讀 |
|---|---|---|---|
| `Garmin RPE` | 讀取 Garmin Perceived Effort，優先從 detail 或單筆活動摘要的 `summaryDTO.directWorkoutRpe` 取得。Garmin 常見原始格式為 0–100。 | `50` | 原始 Garmin 主觀用力值。通常 `50` 對應一般 0–10 尺度的 RPE 5。此欄位保留原始值，不要和 `sRPE Load` 混為同一個數值。 |
| `sRPE Load` | 先把 Garmin RPE 標準化：若原始值大於 10，`RPE=Garmin RPE÷10`；再算 `RPE×Duration min`。 | Garmin RPE `50`、70 分鐘：`RPE=5`，sRPE Load=`350 AU` | 主觀內在訓練負荷。可反映睡眠、肌肉疲勞、心理壓力與高溫等 Garmin 心率演算法未必完整反映的因素。建議用自己的歷史中位數比較。 |
| `Training Load` | 直接取 Garmin 的活動訓練負荷，例如 `activityTrainingLoad` 或 detail summary 的同名欄位。 | `56.67` | Garmin 專有演算法的單次活動負荷。它不是 sRPE Load，也沒有必要和 sRPE Load 數值相等；適合用同一 Garmin 裝置做縱向比較。 |
| `7d Load` | 對活動日期往前 6 天至當天，將每筆 Garmin `Training Load` 加總。 | 當天前 7 天活動 Training Load 為 `30+55+60`：`145` | 短期累積負荷。上升代表近期訓練刺激增加；若突然高於自己的平常基準，隔日可安排恢復或低強度活動。 |
| `28d Load` | 對活動日期往前 27 天至當天，將每筆 Garmin `Training Load` 加總。 | 28 天內 Training Load 合計 `620` | 中期累積負荷背景。可用來判斷近期是否建立足夠訓練基礎；必須抓取完整歷史日期，否則起始期間會低估。 |
| `Body Battery Diff` | Garmin 活動前後 Body Battery 差值；通常為活動後值減活動前值。 | `-13` | 負值代表活動後 Body Battery 下降。與 `7d Load`、sRPE Load 同時變差時，較支持恢復壓力累積；單日負值不能單獨判定過度訓練。 |

### 三種負荷不要混用

`Garmin RPE` 是原始主觀評分；`sRPE Load` 是主觀評分乘以時間；`Training Load` 是 Garmin 演算法負荷；`7d Load` 與 `28d Load` 目前是 Garmin Training Load 的滾動加總。這四種類型應分開看，不能把它們直接相加成一個總分。

## 六、跑步姿勢與跑步經濟性代理

| 欄位 | 數值／資料怎麼算出來 | 範例 | 數值代表什麼意義／怎麼解讀 |
|---|---|---|---|
| `Cadence Change %` | 逐圈步頻首尾變化：`(最後一圈步頻−第一圈步頻) ÷ 第一圈步頻 × 100`。 | 第一圈 `170`、最後 `166`：`-2.35%` | 負值代表後段步頻下降，可能與疲勞、上坡或刻意放慢有關。不要單獨用固定步頻標準判斷好壞，優先比較相同配速與路線。 |
| `GCT Change %` | 逐圈觸地時間首尾變化：`(最後一圈 GCT−第一圈 GCT) ÷ 第一圈 GCT × 100`。 | 第一圈 `250 ms`、最後 `260 ms`：`+4%` | 正值代表後段觸地時間增加，可能與疲勞、速度下降、坡度或地面條件有關。若與 MRS、HR Decoupling 同時升高，疲勞解釋較有支持。 |
| `Power W/kg` | `平均跑步功率（W）÷ WEIGHT_KG`。功率優先從活動摘要、detail summary 或 power measurement stream 取得。 | `210 W ÷ 70 kg = 3.0 W/kg` | 以體重標準化的跑步功率代理。適合同一裝置、相近路線與相近速度的個人縱向比較，不宜直接跨品牌比較。 |

## 七、環境欄位

| 欄位 | 數值／資料怎麼算出來 | 範例 | 數值代表什麼意義／怎麼解讀 |
|---|---|---|---|
| `Temperature C` | 優先使用活動摘要溫度；若沒有，依 Garmin `metricDescriptors` 找到 `directAirTemperature` 的 measurement stream，計算有效溫度的平均值。 | `28.0°C` | 活動記錄中的環境／空氣溫度代理，不是人體核心溫度。`15–25°C` 通常較適合做配速與解耦比較；`25–30°C` 要注意補水與 HR Drift；`>30°C` 不宜只用配速評估表現。 |
| `Notes` | 程式將缺少 MAX_HR、REST_HR、RPE、功率、體重或溫度等資訊組合成文字備註。 | `TRIMP需設定MAX_HR與REST_HR` | 不是分析指標，而是資料品質與缺值診斷。重新同步前先看此欄位，避免把缺資料誤解成 0。 |

## 八、如何用一筆活動做整體判讀

假設一筆 70 分鐘戶外跑的結果是：`Pace CV=3%`、`Pace Range=6%`、`MRS=+4%`、`HR Drift=8%`、`HR Decoupling=7%`、`Garmin RPE=50`、`sRPE Load=350`、`Training Load=57`、`Temperature C=28°C`。合理解讀是：配速大致穩定，但後半程有輕度掉速與心率效率下降；高溫可能是部分原因。這不是立刻減量的證據，但下一次可在相近路線下前段放慢、補水，並比較 MRS 與 HR Decoupling 是否下降。

如果另一筆活動的 `Pace CV=3%` 但 `Pace Range=15%`，先查 Raw Laps 是否有單圈停等或 GPS 異常；如果 `Training Load`、`sRPE Load`、`7d Load` 與 `Body Battery` 消耗同時升高，則把後續一天安排為恢復或低強度，比單看任何一個欄位更合理。

## 九、重要限制

這些指標是訓練監控與個人縱向比較工具，不是醫療診斷。單次異常值應先檢查活動類型、路線、坡度、溫度、風、補水、睡眠、GPS 及感測器品質。只有在相似條件下連續數週出現同方向變化，才適合調整訓練規劃；若出現胸痛、暈厥、異常心悸、呼吸困難或持續疼痛，應停止訓練並尋求合格醫療專業評估。

## References

[1]: https://developer.garmin.com/gc-developer-program/activity-api/ "Garmin Health API Activity API"

[2]: https://pmc.ncbi.nlm.nih.gov/articles/PMC6409702/ "Monitoring Training Load, Well-Being, Heart Rate Variability, and Competitive Performance"

[3]: https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2022.860888/full "Acute and Chronic Workload Ratios of Perceived Exertion in Elite Athletes"

[4]: https://pmc.ncbi.nlm.nih.gov/articles/PMC7696724/ "Mechanical Power in Endurance Running: A Scoping Review"


## 十、Garmin Weekly Running Analysis 每週資料庫

`Garmin Running Analysis` 是 daily database；`Garmin Weekly Running Analysis` 是從 daily database 彙總出的 weekly database。Weekly database 不會重新呼叫 Garmin API，而是讀取已經寫入 Notion 的每日資料，因此適合用來觀察訓練規律性、負荷與恢復趨勢。

### Weekly database 欄位總表

| 欄位 | 數值／資料怎麼算出來 | 範例 | 數值代表什麼意義／怎麼解讀 |
|---|---|---|---|
| `Name` | 程式產生 `Week YYYY-MM-DD`，日期是該週週一。 | `Week 2026-09-01` | Weekly page 的標題；不參與數值計算。 |
| `Week Key` | 取該週週一的 ISO 日期。 | `2026-09-01` | 每週唯一鍵。程式以此更新既有週頁面，避免重複建立。 |
| `Week Start` | 該週週一。程式以 Monday 為每週起點。 | `2026-09-01` | 週資料的開始日期。 |
| `Week End` | `Week Start + 6 天`。 | `2026-09-07` | 週資料的結束日期。 |
| `Training Sessions` | 該週 daily database 中 `Activity Type` 為 `running` 或 `treadmill` 的活動筆數。 | `3` | 每週訓練次數。應與訓練頻率 CV 一起看；沒有活動的週會補成 0 次。 |
| `Training Frequency CV` | 最近最多 4 週的每週訓練次數計算 `標準差 ÷ 平均值`。 | 4 週次數 `2,3,3,2`：平均 `2.5`、標準差約 `0.5`，CV=`0.20` | 訓練頻率規律性的代理指標。越低代表每週次數越穩定，但它不是訓練品質或能力的直接指標。 |
| `Training Frequency Class` | 依 CV 分級：`CV < 0.3`、`0.3 ≤ CV < 0.6`、`CV ≥ 0.6`。 | `0.20 → 高度規律` | `高度規律`：紀律度代理指標佳；`中度規律`：一般水準；`波動較大`：可能受動機、壓力或生活變動影響，應檢查近期是否有壓力源。 |
| `Distance km` | 將該週 daily 的 `Distance km` 加總。 | `7.5+8.2+10.0=25.7 km` | 每週總跑量。連續快速上升時，應同時觀察 `Training Load`、`sRPE Load`、MRS 與恢復狀態。 |
| `Duration min` | 將該週 daily 的 `Duration min` 加總。 | `45+50+70=165 min` | 每週訓練時間。可與距離交叉檢查跑量與強度變化。 |
| `Training Load` | 將該週 daily 的 Garmin `Training Load` 加總。 | `40+55+70=165` | Garmin 演算法的每週外部／生理負荷代理。這不是 sRPE Load；兩者應分開觀察。 |
| `sRPE Load` | 將該週 daily 的 `sRPE Load` 加總。 | `180+210+350=740 AU` | 主觀內在負荷的週累積。若它比 Training Load 上升更快，可能表示恢復、睡眠、溫度或肌肉疲勞增加。 |
| `Avg HR` | 該週 daily `Avg HR` 的平均值，不是把所有心跳樣本重新加權平均。 | `(125+130+128)/3=127.7 bpm` | 週平均活動心率。應按活動類型、配速與溫度分層解讀。 |
| `Avg Pace min/km` | 該週 daily `Pace min/km` 的平均值。 | `(8.0+7.5+8.2)/3=7.90 min/km` | 週平均活動配速。不同距離、地形與跑步機／戶外活動混合時，解讀要保守。 |
| `HR Efficiency Slope` | 每週效率先算為 `速度（m/s）÷ 平均心率（bpm）`，再用最近最多 6 週的週效率做線性回歸斜率。 | 6 週效率由 `0.014` 升至 `0.016`，斜率可為 `+0.0004／週` | 正斜率表示相同心率下速度效率逐步提高；負斜率表示效率下降。只有在相近活動類型、配速、路線與溫度下比較才有意義。 |
| `HR Efficiency Trend` | 依斜率判斷：`>0.001` 為持續進步；`-0.001 至 0.001` 為持平；`<-0.001` 為下滑。 | `-0.0015 → 下滑` | `持續進步`：有氧效率可能改善；`持平`：目前沒有明顯方向；`下滑`：留意過度訓練、恢復不足或環境條件。少於兩個有效週次時無法可靠計算。 |
| `Recovery Burden Ratio` | `−Body Battery Diff 合計 ÷ Training Load 合計`。例如 Body Battery Diff 合計 `−30`、Training Load `150`，結果為 `0.20`。 | `0.20` | 每一單位 Garmin Training Load 對應的 Body Battery 消耗代理。越高代表同樣訓練負荷帶來的恢復成本可能越大；它不是醫學上的恢復指標。 |
| `Recovery Burden Change` | 近期最多 3 週恢復負擔比平均值減去較早最多 3 週平均值。 | 近期 `0.22`、早期 `0.15`：變化=`+0.07` | 正值代表近期每單位 Training Load 的恢復成本上升；負值代表下降。至少需要約 4 週資料才有早期與近期可比較區間。 |
| `Recovery Resilience Trend` | 依變化分級：`<−0.05`、`−0.05 至 0.05`、`>0.05`。 | `+0.07 → 恢復韌性下降` | `恢復韌性提升`：相同負荷下恢復成本下降；`持平`：沒有明顯改變；`恢復韌性下降`：留意疲勞累積、睡眠、疾病前兆或壓力。 |
| `MRS Avg %` | 該週 daily `MRS %` 的平均值。 | `(2%+5%+3%)/3=3.3%` | 週平均後半程掉速率。持續偏高表示長跑後段控制或耐力需要觀察。 |
| `HR Drift Avg %` | 該週 daily `HR Drift %` 的平均值。 | `6%` | 週平均後半心率上升代理。要搭配溫度、補水與前段配速解讀。 |
| `HR Decoupling Avg %` | 該週 daily `HR Decoupling %` 的平均值。 | `7%` | 週平均速度／心率效率下降程度。正值持續升高時，需檢查後半程效率與恢復狀況。 |
| `Temperature Avg C` | 該週 daily `Temperature C` 的平均值。 | `27.5°C` | 該週活動環境溫度平均。高溫週不宜直接與涼爽週比較配速與心率效率。 |
| `Notes` | 程式記錄資料不足，例如週數不足、恢復負擔比沒有早期資料。 | `恢復負擔比變化需至少4週資料` | 用來區分「真正的趨勢」與「因資料不足而不穩定的初步值」。 |

### Weekly 指標的整體解讀範例

假設某週有 3 次跑步，`Training Frequency CV=0.20`、`Distance km=27`、`Training Load=165`、`sRPE Load=740`、`HR Efficiency Slope=-0.0015`、`Recovery Burden Change=+0.08`。這代表訓練次數本身很規律，但近期效率下滑、主觀負荷與恢復成本可能偏高。此時不應因為「每週訓練很規律」就繼續增加訓練量；比較合理的處理是維持或降低一週內高強度活動，安排恢復跑與睡眠／補水檢查，並觀察接下來 1–2 週是否回到持平。

相反地，如果 `Training Frequency CV=0.20`、`HR Efficiency Slope=+0.0015`、`Recovery Burden Change=-0.08`，可解讀為訓練安排穩定、速度／心率效率改善且單位負荷恢復成本下降。這支持維持目前訓練結構，但仍不代表可以單靠這三個值立即大幅增加訓練量。

## 十一、Weekly 歷史補算與每日更新

第一次建立 Weekly database，或要重新整理已存在的所有歷史週資料時，應使用 Notion-only backfill：

```powershell
uv run python src\\weekly_backfill.py
```

也可以在 Windows 執行：

```powershell
.\\backfill_weekly.ps1
```

這個 backfill 程式只讀取既有的 `Garmin Running Analysis` daily database，不會登入 Garmin、不會呼叫 activity API、不會重新抓 detail 或 Raw Laps，也不會觸發 Garmin 429。

完成歷史補算後，日常才使用：

```powershell
uv run python src\\main.py
```

日常主程式會先抓取最近幾天 Garmin 活動並更新 daily database，接著從 Notion daily database 計算 weekly database。也就是：

```text
Garmin 最近活動 → daily Analysis → Notion daily database → weekly Analysis
```

如果只修正了 daily database 的歷史欄位，重新執行 `weekly_backfill.py` 即可；不需要從 6/1 重新呼叫 Garmin。所有週頁面以 `Week Key` 去重，因此重跑會更新原頁面，不會新增重複週資料。
