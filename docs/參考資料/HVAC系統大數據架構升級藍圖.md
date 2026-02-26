身為空調能源大數據分析專家，我非常樂意為您梳理這份升級藍圖。  
在您的 HVAC-1 系統架構中，非常強調 **「契約優先 (Contract-First)」** 與 **「基礎優先策略 (Foundation First Policy)」** 1-3。這意味著上游的資料規格必須先確立，下游的資料消費模組才能依循開發，否則極易產生模組間的依賴死鎖（Dependency Deadlock）2。  
根據您專案排程文件顯示，目前 Sprint 2（核心 ETL）已全部完成，即將進入 Sprint 3（特徵與模型）4。因此，現在正是修改這幾份 PRD 的最佳時機。  
以下是我為您排定的 PRD 修改優先順序，完全契合您現有的單向資料流（Single Source of Truth, SSOT）架構：

### 🥇 優先級 1：特徵標註系統規範 (定義資料源頭)

**📝 目標文件：PRD\_Feature\_Annotation\_Specification\_V1.3.md 升級至 v1.4**

* **為何排第一：** 在您的 SSOT 架構中，Excel 標註是所有下游模組的唯一真相源（Single Source of Truth）5, 6。如果不先在 Excel 範本與 YAML Schema 中定義好「空間拓樸」與「控制語意」的欄位，下游的特徵工程就無資料可讀。  
* **修改行動綱領：**  
* 擴充第 3 章的 Excel 範本結構，新增 upstream\_equipment\_id（建立 GNN 所需的有向圖邊界）7。  
* 新增 point\_class（區分 Sensor, Setpoint, Command）7。  
* 更新 Schema 驗證邏輯，確保新增的欄位具備防呆檢查（例如：檢查上游設備 ID 是否真的存在於案場中）。

### 🥈 優先級 2：特徵工程規範 (消費標註並產生特徵)

**📝 目標文件：PRD\_FEATURE\_ENGINEER\_V1.3.md 升級至 v1.4**

* **為何排第二：** 當標註系統 (Annotation) 提供拓樸與控制屬性後，特徵工程模組必須負責「消費」這些 Metadata，並將其轉換成模型可以吃的特徵矩陣（Feature Matrix）8, 9。此模組的輸出直接決定了模型訓練的上限。  
* **修改行動綱領：**  
* 擴充第 3 章的「語意感知 Group Policy」10, 11。  
* 定義「拓樸聚合特徵（Topology Aggregation）」演算法：如何自動抓取上游冷卻水塔的溫度作為冰水主機的新特徵。  
* 定義「控制偏差特徵（Control Deviation）」演算法：如何自動對齊並相減 Setpoint 與 Sensor 的數值。

### 🥉 優先級 3：模型訓練管線 (訓練先進模型)

**📝 目標文件：PRD\_Model\_Training\_v1.3.md 升級至 v1.4**

* **為何排第三：** 只有當特徵工程（優先級 2）確定能產出包含拓樸關係的特徵矩陣與特徵清單（Feature Manifest）後 12，訓練管線才能引入對應的先進演算法。  
* **修改行動綱領：**  
* 在第 6 章的「模型訓練器」中，新增 GNNTrainer（圖神經網路訓練器）的實作細節 13。  
* 強化第 1 章的 Hybrid 模式（模式 C）14，定義如何將設備耦合效應差異（Copula effect）轉化為損失函數的懲罰項（Penalty Term）加入訓練過程中。

### 🏅 優先級 4：新增持續學習規範 (上線後的保鮮機制)

**📝 新增文件：PRD\_Continual\_Learning\_Update\_v1.0.md**

* **為何排第四：** 這屬於模型生命週期管理（MLOps）進階範疇。它必須建立在基礎模型（Priority 3）已經成功訓練、並具備完善的資源管理（如記憶體預估、Kubernetes 資源配置）基礎之上 14, 15。  
* **修改行動綱領：**  
* 定義觸發模型更新的條件（定期觸發 vs. 性能退化觸發 Error Rate Strategy）。  
* 定義梯度情境記憶（GEM）演算法的資料暫存機制（Episodic Memory Buffer）。  
* 規範線上微調（Fine-tuning）時的運算資源管理與 OOM（Out of Memory）防護策略。

**💡 專家執行建議：**由於您的團隊正準備啟動 **Sprint 3 (第 6-9 週)** 16，我建議您 **本週先專注於修改「優先級 1」與「優先級 2」的 PRD**。這樣可以確保資料工程師能無縫接軌，開始實作新的特徵萃取邏輯；而「優先級 3」與「優先級 4」則可以在 ML 工程師處理完基礎 XGBoost/LightGBM 模型建置後，作為後續的強化模組引入。  
如果您準備好了，我們可以先從 PRD\_Feature\_Annotation\_Specification\_V1.3.md 的具體 Excel 欄位擴充與 Schema 修改開始著手！  
