為了將您的 HVAC AI 引擎推向具備「空間拓樸感知」與「動態適應」的頂尖水準，基於您目前極度嚴謹的契約導向架構（HVAC-1 專案），我們不需要打掉重練，而是建議針對現有的 **3 份核心 PRD 進行版本升級（建議升級至 v1.4）**，並 **新增 1 份專屬 PRD** 來處理模型生命週期的新典範。  
以下是具體的修改藍圖與實作路徑：

### 1\. 需修改的 PRD：特徵標註系統

**📝 目標文件：** PRD\_Feature\_Annotation\_Specification\_V1.3.md 1**升級重點（升級至 v1.4）：**為了導入空間拓樸（Topology）與控制邊界，必須從源頭的 Excel 標註範本進行擴充：

* **修改 Excel Sheet 2: Columns 結構** 2：  
* 新增欄位 upstream\_equipment\_id（上游設備 ID）：例如冰水主機（CH-01）的上游標註為對應的冷卻水塔（CT-01）或水泵，以此建立設備間的實體有向圖（Directed Graph）3。  
* 新增欄位 point\_class（點位型態）：將特徵明確區分為 Sensor（感測器狀態）、Setpoint（設定值）、Command（控制指令）與 Alarm（警報）4。  
* **更新 Metadata 與分類本體** 5, 6：  
* 在 config/features/equipment\_taxonomy.yaml 中，正式對接國際 Brick Schema 或 Project Haystack 的標準命名空間 7, 8，使欄位的 physical\_type 與國際語意對齊。

### 2\. 需修改的 PRD：特徵工程規範

**📝 目標文件：** PRD\_FEATURE\_ENGINEER\_V1.3.md 9**升級重點（升級至 v1.4）：**特徵工程模組必須能夠消費（Consume）上述新增的拓樸與控制屬性，轉換為模型可讀的矩陣：

* **擴充語意感知群組策略 (Group Policy)** 10, 11：  
* 新增「**拓樸聚合特徵 (Topology Aggregation)**」策略。例如，當模型預測冰水主機耗電時，特徵工程應能自動讀取 upstream\_equipment\_id，並生成「關聯冷卻水塔的平均出水溫度」作為主機的新特徵 2, 3。  
* 新增「**控制偏差特徵 (Control Deviation)**」策略。自動將同一設備的 Sensor 數值減去 Setpoint 數值，生成 $\\Delta T$（如冰水出水溫度偏差）特徵，這對捕捉控制系統的穩定度極度有效 12。

### 3\. 需修改的 PRD：模型訓練管線

**📝 目標文件：** PRD\_Model\_Training\_v1.3.md 13**升級重點（升級至 v1.4）：**為了消化更複雜的時間與空間特徵，需要擴充訓練器的種類與機制：

* **引入圖神經網路 (Graph Neural Network, GNN) 訓練器** 3, 14：  
* 在現有的 XGBoostTrainer、LightGBMTrainer 與 RandomForestTrainer 之外 14，新增 GNNTrainer。GNN 能夠直接利用上述特徵工程建立的「設備連接矩陣」，讓模型自行學習冷卻水側到冰水側的熱力傳遞遞延效應 15。  
* **強化 Hybrid 模式 (模式 C) 的損失函數** 16, 17：  
* 將系統級（System-Level）與設備級（Component-Level）的耗電預測進行「聯合訓練」，把現行 PRD 中偵測耦合效應差異大於 5% 觸發警告的機制 16, 17，直接轉化為神經網絡訓練時的懲罰項（Penalty Term），強迫模型在訓練階段就達成物理守恆。

### 💡 建議新增的 PRD 文件

目前的系統架構高度著重於「批次離線訓練 (Batch Training)」與「離線優化」18, 19。但空調系統設備會隨時間老化（如熱交換器結垢），導致「概念漂移 (Concept Drift)」，使原本訓練好的模型準確度逐漸下降 20。  
為了讓系統具備線上自動進化的能力，強烈建議新增以下 PRD：  
**📝 新增文件：PRD\_Continual\_Learning\_Update\_v1.0.md (持續學習與模型線上更新)**

* **模組定位：** 介於現有的 Model Training 與 Optimization 之間，負責模型的「生命週期保鮮」。  
* **核心規範內容：**  
* **更新觸發機制**：定義何時需要更新模型。例如基於監控效能退化（Error Rate Strategy）或定期化觸發 21。  
* **引入 GEM (Gradient Episodic Memory) 演算法**：相較於現有的增量學習（Incremental Learning）容易導致模型忘記過去的工況（災難性遺忘），GEM 技術能在更新模型參數以適應新數據的同時，限制其改變以保留對舊有工況（如去年的極端高溫）的記憶 22, 23。  
* **運算資源管理策略**：由於線上更新的資源受限，規範如何動態調配 Kubernetes 或 Edge 設備的運算資源來執行輕量化模型微調 24。

**總結來說**：您的底層架構（如 SSOT、單向流程、檢查點 E000-E999）25, 26 已經打得非常穩固。下一步只需擴充上述 3 份 PRD 來捕捉\*\*「空間拓樸」與「控制語意」**，並新增 1 份 PRD 來打通**「時間維度的自我進化」\*\*，這套 HVAC AI 系統就能直接躍升至國際頂規的智慧建築大腦層級。  
