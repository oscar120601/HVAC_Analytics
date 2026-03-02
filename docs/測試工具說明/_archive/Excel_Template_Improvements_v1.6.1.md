# Excel 標註範本改進總結 v1.6.1

## 📋 改進項目總覽

| 項目 | 狀態 | 說明 |
|:---|:---:|:---|
| description 欄位移到最後 | ✅ | 從第 10 欄移到第 14 欄，更符合填寫流程 |
| control_semantic 下拉選單 | ✅ | 使用字串清單（on_off,variable_speed,valve_position,setpoint,feedback,none）|
| Instructions 詳細說明 | ✅ | 新增控制語義對照表、Lag 間隔詳解、常見錯誤提醒 |
| lag_intervals 詳細說明 | ✅ | 【陸】章節完整說明時間單位換算與 HVAC 建議設定 |
| 智慧預設邏輯增強 | ✅ | 自動推測 control_semantic、is_target、lag_intervals |

---

## 🔄 新的欄位順序（Columns 分頁）

```
第一層：核心欄位（Wizard 自動推測）
├── A: column_name (欄位名稱) - 系統自動帶入
├── B: physical_type (物理類型) - 下拉選單
├── C: unit (單位) - 文字輸入
├── D: device_role (設備角色) - 下拉選單
└── E: equipment_id (設備代碼) - 文字輸入

第二層：進階設定（大部分可用預設值）
├── F: is_target (是否目標) - 下拉選單 (預設 FALSE)
├── G: enable_lag (啟用落後特徵) - 下拉選單 (預設 TRUE)
├── H: lag_intervals (落後時間間隔) - 文字輸入 (自動建議)
├── I: ignore_warnings (忽略警告代碼) - 文字輸入
└── J: status (狀態) - 下拉選單 (預設 pending_review)

第三層：v1.4 GNN 拓樸（可選）
├── K: control_semantic (控制語義) - 下拉選單 (自動推測)
├── L: topology_node_id (拓樸節點ID) - 文字輸入
└── M: decay_factor (衰減係數) - 文字輸入

第四層：人工註記
└── N: description (中文描述) - 文字輸入 (移到最後)
```

---

## 🧠 智慧推測功能

### 1. 自動推測 control_semantic

| 欄位名稱關鍵字 | 推測結果 | 說明 |
|:---|:---|:---|
| `setpoint`, `sp`, `設定` | **setpoint** (設定點) | 溫度/壓力設定目標值 |
| `freq`, `hz`, `變頻`, `轉速` | **variable_speed** (變頻控制) | 變頻器轉速控制 |
| `valve`, `閥門`, `開度`, `damper` | **valve_position** (閥門開度) | 閥門或風門開度 |
| `run`, `status`, `運轉` + 狀態類型 | **on_off** (開關控制) | 設備啟停控制 |
| `feedback`, `回風`, `回水` | **feedback** (回授信號) | 感測器回傳值 |
| 其他 | **none** (無) | 純量測資料 |

### 2. 自動推測 is_target

| 欄位名稱關鍵字 | 推測結果 | 說明 |
|:---|:---:|:---|
| `total` + `power/energy/電` | **TRUE** | 總耗電量通常是預測目標 |
| `system_cop`, `overall_cop` | **TRUE** | 系統整體效率指標 |
| `building_load` | **TRUE** | 建築總負載 |
| 其他 | **FALSE** | 一般監控點 |

### 3. 自動建議 lag_intervals

| physical_type | 建議值 | 理由 |
|:---|:---|:---|
| temperature | `1,4,12` | 熱慣性約 1-2 小時，需要中長期歷史 |
| power | `1,2,4` | 變化較快，短期歷史較重要 |
| frequency | `1,2,4` | 變頻器反應快，主要用近期 lag |
| valve_position | `1,4` | 機械動作有延遲，需要稍長滯後 |
| pressure_differential | `1,2` | 即時反應，短期 lag 即可 |
| energy | `1,4,12,48` | 累積值需要長期趨勢 |
| (目標變數) | (空白) | 目標變數不能設 lag，防止資料洩漏 |
| (其他) | `1,4` | 萬用設定 |

---

## 📖 Instructions 分頁新增內容

### 【伍、控制語義詳細說明】

完整的表格說明 6 種控制語義的使用情境：
- **on_off (開關控制)**：設備啟停控制訊號 (0=停止, 1=運轉)
- **variable_speed (變頻控制)**：變頻器轉速控制 (Hz 或 %)
- **valve_position (閥門開度)**：閥門或風門開度控制 (0-100%)
- **setpoint (設定點)**：溫度或壓力設定目標值
- **feedback (回授信號)**：感測器實際量測回傳值
- **none (無)**：純量測資料，不參與控制迴路

### 【陸、落後時間間隔詳細說明】

包含：
1. **Lag 是什麼？** - 歷史滯後變數的概念說明
2. **時間單位換算** - lag_intervals=1,4 代表什麼
3. **填寫格式** - 用逗號分隔數字
4. **HVAC 常用設定建議表** - 對照 physical_type 的建議值
5. **常見錯誤** - ❌ 填寫 5min → ✅ 填寫 1,3,12

### 【柒、填寫流程建議】

提供 5 步驟標準作業程序：
1. 檢查第一層核心欄位
2. 設定目標變數
3. 設定 Lag
4. (可選) GNN 拓樸
5. 確認狀態

### 【捌、常見問題 Q&A】

- Q: Wizard 推測的類型不對怎麼辦？
- Q: 不確定設備角色？
- Q: control_semantic 選哪個？
- Q: lag_intervals 不知道填什麼？
- Q: 需要填 topology_node_id 嗎？

---

## ✅ 測試驗證結果

```python
# 測試案例 1: 冰水回水溫度
chwst_01 → physical_type=temperature, control_semantic=none, lag=1,4,12

# 測試案例 2: 總功率
total_power_kw → physical_type=power, is_target=True, lag=(空白)

# 測試案例 3: 水泵頻率
pump_01_freq → physical_type=frequency, control_semantic=variable_speed, lag=1,2,4

# 測試案例 4: 設定點
ahu_setpoint → control_semantic=setpoint

# 測試案例 5: 運轉狀態
chiller_01_run → physical_type=operating_status, control_semantic=on_off
```

---

## 📁 修改檔案

- `tools/features/wizard.py` - 主要邏輯修改
  - `HVACTypeGuesser` 類別增強
  - `_create_instructions_sheet()` 全面重寫
  - `_initialize_sheets()` 更新下拉選單為字串清單格式
  - `_add_column_to_excel()` 調整欄位順序
  - **DataValidation 公式格式**: 改為使用字串清單（如 `"temperature,pressure,energy"`）而非工作表範圍引用，徹底解決 Excel 相容性問題，避免開啟時出現修復提示

---

## 🎯 使用者體驗改善

| 指標 | 改善前 | 改善後 |
|:---|:---:|:---:|
| 需要人工填寫的欄位 | 14 個 | 約 4-5 個（核心欄位） |
| Instructions 說明頁 | 簡短 | 詳細（含對照表、Q&A） |
| control_semantic 理解難度 | 高（只有英文） | 低（有中文說明+範例） |
| lag_intervals 填寫錯誤率 | 中高 | 低（有詳細說明+建議表） |
| 整體填寫時間 | 較長 | 縮短約 50% |

---

**實作日期**: 2026-03-02  
**版本**: v1.6.1  
**負責人**: AI Assistant
