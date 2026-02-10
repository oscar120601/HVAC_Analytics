# 批次處理特徵映射工作流程 (V3)

## 新功能概覽

在批次處理完成後，現在會自動顯示 **「🗺️ 特徵映射配置」** 區塊，支援：
- **13 個標準類別**（按 HVAC 物理系統分組）
- **四種配置方式**：自動識別 / 手動對應 / 萬用字元模式 / JSON 上傳
- **萬用字元模式**：使用 `*` 和 `?` 批量匹配欄位

---

## 工作流程步驟

### Step 1: 啟動 UI 並選擇批次處理模式

```bash
streamlit run etl_ui.py
```

1. 左側欄選擇 **「批次處理（整個資料夾）」**
2. 選擇檔案範圍（全部或日期範圍）
3. 點擊 **「🚀 開始批次處理」**

---

### Step 2: 批次處理完成後

處理完成會看到：

```
✅ 成功處理 30 個檔案

總列數: 15,234
總欄位數: 45
時間範圍: 30 days
```

然後會自動顯示 **🗺️ 特徵映射配置** 區塊

---

### Step 3: 特徵映射配置

#### 方式 A: 自動識別（推薦）

```
配置方式: ● 自動識別 (Auto-detect)  ○ 手動對應 (Manual Mapping)  ○ 萬用字元 (Wildcard)

[🤖 執行自動識別]  ← 點擊這個按鈕
```

系統會自動根據欄位名稱識別 **13 個類別**：

| 類別 | 識別模式 | 範例欄位 |
|-----|---------|---------|
| `chiller` | 包含 "CH_" + ("RT" 或 "KW") | `CH_0_RT`, `CH_1_KW` |
| `chw_pump` | 包含 "CHP" + "VFD" | `CHP_01_VFD_OUT` |
| `scp_pump` | 包含 "SCP" + "VFD" | `SCP_01_VFD_OUT` |
| `chw_temp` | 包含 "CH_" + ("SWT"/"RWT") | `CH_0_SWT`, `CH_0_RWT` |
| `chw_pressure` | 包含 "CHW" + "PRESSURE" | `CHW_SUPPLY_PRESSURE` |
| `chw_flow` | 包含 "CHW" + "FLOW" | `CHW_FLOW` |
| `cw_pump` | 包含 "CWP" + "VFD" | `CWP_01_VFD_OUT` |
| `cw_temp` | 包含 "CW_" + ("SWT"/"RWT") | `CW_SYS_SWT`, `CW_SYS_RWT` |
| `cw_pressure` | 包含 "CW" + "PRESSURE" | `CW_SUPPLY_PRESSURE` |
| `cw_flow` | 包含 "CW" + "FLOW" | `CW_FLOW` |
| `cooling_tower` | 包含 "CT_" + "VFD" | `CT_01_VFD_OUT` |
| `environment` | 包含 "OAT"/"OAH"/"WBT" | `CT_SYS_OAT`, `CT_SYS_OAH` |
| `system_level` | 包含 "TOTAL" + "KW" | `CH_SYS_TOTAL_KW` |

#### 方式 B: 萬用字元模式（大量欄位推薦）🆕

```
配置方式: ○ 自動識別 (Auto-detect)  ○ 手動對應 (Manual Mapping)  ● 萬用字元 (Wildcard)

🗺️ 萬用字元模式配置
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

❄️ 冰水側系統:
chiller:      [CH_*_RT, CH_*_KW          ]
chw_pump:     [CHP_*_VFD_OUT             ]
scp_pump:     [SCP_*_VFD_OUT             ]
chw_temp:     [CH_*_SWT, CH_*_RWT        ]
chw_pressure: [CHW_*_PRESSURE            ]
chw_flow:     [CHW_*FLOW*                ]

🔥 冷卻水側系統:
cw_pump:      [CWP_*_VFD_OUT             ]
cw_temp:      [CW_*_SWT, CW_*_RWT        ]
cw_pressure:  [CW_*_PRESSURE             ]
cw_flow:      [CW_*FLOW*                 ]

🏭 冷卻水塔:
cooling_tower:[CT_*_VFD_OUT, CT_*_KW     ]

🌍 環境參數:
environment:  [*OAT*, *OAH*, *WBT*       ]

⚡🎯 系統層級:
system_level: [*TOTAL*KW                 ]

[✨ 套用萬用字元規則]
```

**萬用字元語法：**
- `*` - 匹配任意字元序列（0個或多個）
- `?` - 匹配單一任意字元
- `,` - 分隔多個模式

#### 方式 C: 手動對應

```
配置方式: ○ 自動識別 (Auto-detect)  ● 手動對應 (Manual Mapping)  ○ 萬用字元 (Wildcard)

請在下方下拉式選單中，為每個欄位選擇適當的特徵類別

═══════════════════════════════════════════════════════════
❄️ 冰水側系統 (Chilled Water Side)
═══════════════════════════════════════════════════════════
• chiller (冰水機):
  [CH_0_RT    ▼] [CH_1_RT    ▼] [CH_0_KW    ▼]

• chw_pump (冰水泵):
  [CHP_01_VFD_OUT ▼] [CHP_02_VFD_OUT ▼]

• scp_pump (區域泵):
  [SCP_01_VFD_OUT ▼]

• chw_temp (冰水溫度):
  [CH_0_SWT ▼] [CH_0_RWT ▼]

• chw_pressure (冰水壓力):
  [CHW_S_PRESS ▼] [CHW_R_PRESS ▼]

• chw_flow (冰水流量):
  [CHW_FLOW ▼]

═══════════════════════════════════════════════════════════
🔥 冷卻水側系統 (Condenser Water Side)
═══════════════════════════════════════════════════════════
• cw_pump (冷卻水泵):
  [CWP_01_VFD_OUT ▼] [CWP_02_VFD_OUT ▼]

• cw_temp (冷卻水溫度):
  [CW_SYS_SWT ▼] [CW_SYS_RWT ▼]

• cw_pressure (冷卻水壓力):
  [CW_S_PRESS ▼] [CW_R_PRESS ▼]

• cw_flow (冷卻水流量):
  [CW_FLOW ▼]

═══════════════════════════════════════════════════════════
🏭 冷卻水塔系統 (Cooling Tower)
═══════════════════════════════════════════════════════════
• cooling_tower:
  [CT_01_VFD_OUT ▼] [CT_02_VFD_OUT ▼]

═══════════════════════════════════════════════════════════
🌍 環境參數 (Environment)
═══════════════════════════════════════════════════════════
• environment:
  [CT_SYS_OAT ☑] [CT_SYS_OAH ☑] [CT_SYS_WBT ☑]

═══════════════════════════════════════════════════════════
⚡🎯 系統層級 (System Level) - Target
═══════════════════════════════════════════════════════════
• system_level:
  [CH_SYS_TOTAL_KW ▼]

[💾 儲存手動配置]
```

**操作方式：**
- 每個類別使用 **multiselect** 多選下拉框
- 點擊下拉框會顯示所有未分配的欄位
- 勾選多個欄位後會顯示為 tags
- 可以隨時取消選擇移除

---

### Step 4: 查看與驗證映射

配置完成後會顯示（按物理系統分組）：

```
📋 查看/編輯當前映射

═══════════════════════════════════════════════════════════
❄️ 冰水側系統
═══════════════════════════════════════════════════════════
• chiller (冰水機): 4 欄位
  CH_0_RT, CH_1_RT, CH_2_RT, CH_3_RT
• chw_pump (冰水泵): 2 欄位
  CHP_01_VFD_OUT, CHP_02_VFD_OUT
• scp_pump (區域泵): 2 欄位
  SCP_01_VFD_OUT, SCP_02_VFD_OUT
• chw_temp (冰水溫度): 4 欄位
  CH_0_SWT, CH_0_RWT, CH_1_SWT, CH_1_RWT
• chw_pressure (冰水壓力): 2 欄位
  CHW_SUPPLY_PRESSURE, CHW_RETURN_PRESSURE
• chw_flow (冰水流量): 1 欄位
  CHW_FLOW

═══════════════════════════════════════════════════════════
🔥 冷卻水側系統
═══════════════════════════════════════════════════════════
• cw_pump (冷卻水泵): 2 欄位
  CWP_01_VFD_OUT, CWP_02_VFD_OUT
• cw_temp (冷卻水溫度): 2 欄位
  CW_SYS_SWT, CW_SYS_RWT
• cw_pressure (冷卻水壓力): 2 欄位
  CW_SUPPLY_PRESSURE, CW_RETURN_PRESSURE
• cw_flow (冷卻水流量): 1 欄位
  CW_FLOW

═══════════════════════════════════════════════════════════
🏭 冷卻水塔系統
═══════════════════════════════════════════════════════════
• cooling_tower: 2 欄位
  CT_01_VFD_OUT, CT_02_VFD_OUT

═══════════════════════════════════════════════════════════
🌍 環境參數
═══════════════════════════════════════════════════════════
• environment: 3 欄位
  CT_SYS_OAT, CT_SYS_OAH, CT_SYS_WBT

═══════════════════════════════════════════════════════════
⚡🎯 系統層級 (Target)
═══════════════════════════════════════════════════════════
• system_level: 1 欄位
  CH_SYS_TOTAL_KW

✅ 所有映射欄位都存在於資料中

[📥 匯出 JSON]
```

---

### Step 5: 資料分析與訓練

確認映射無誤後，繼續使用下方的標籤頁：

```
📋 資料預覽 | 🧹 清洗資料 | 📊 統計資訊 | 📈 時間序列 | 🔗 關聯矩陣 | 🎯 資料品質 | 💾 匯出
```

或在 **「⚡ 最佳化模擬」** 模式中使用此映射訓練模型。

---

## 重要提示

### 映射儲存位置

批次處理配置的映射會自動儲存在 `st.session_state.batch_feature_mapping`，會在：
- 同一個 session 的所有模式中共用
- 訓練模型時自動套用

### V3 欄位分類規則總表

| 特徵類別 | 父系統 | 識別模式 | 範例欄位 |
|---------|--------|---------|---------|
| chiller | ❄️ 冰水側 | 包含 "CH_" + ("RT" 或 "KW") | `CH_0_RT`, `CH_1_KW` |
| chw_pump | ❄️ 冰水側 | 包含 "CHP" + "VFD" | `CHP_01_VFD_OUT` |
| scp_pump | ❄️ 冰水側 | 包含 "SCP" + "VFD" | `SCP_01_VFD_OUT` |
| chw_temp | ❄️ 冰水側 | 包含 "CH_" + ("SWT"/"RWT") | `CH_0_SWT`, `CH_0_RWT` |
| chw_pressure | ❄️ 冰水側 | 包含 "CHW" + "PRESSURE" | `CHW_SUPPLY_PRESSURE` |
| chw_flow | ❄️ 冰水側 | 包含 "CHW" + "FLOW" | `CHW_FLOW` |
| cw_pump | 🔥 冷卻水側 | 包含 "CWP" + "VFD" | `CWP_01_VFD_OUT` |
| cw_temp | 🔥 冷卻水側 | 包含 "CW_" + ("SWT"/"RWT") | `CW_SYS_SWT` |
| cw_pressure | 🔥 冷卻水側 | 包含 "CW" + "PRESSURE" | `CW_SUPPLY_PRESSURE` |
| cw_flow | 🔥 冷卻水側 | 包含 "CW" + "FLOW" | `CW_FLOW` |
| cooling_tower | 🏭 冷卻水塔 | 包含 "CT_" + "VFD" | `CT_01_VFD_OUT` |
| environment | 🌍 環境 | 包含 "OAT"/"OAH"/"WBT" | `CT_SYS_OAT` |
| system_level | ⚡🎯 系統 | 包含 "TOTAL" + "KW" | `CH_SYS_TOTAL_KW` |

### 欄位未被識別？

如果使用自動識別後有些欄位沒有被分到正確類別：

1. 切換到 **「萬用字元模式」**
2. 輸入自訂的匹配規則（如 `CUSTOM_*_VFD`）
3. 點擊 **「✨ 套用萬用字元規則」**

或：

1. 切換到 **「手動對應」** 模式
2. 在每個類別的下拉框中手動選擇
3. 點擊 **「💾 儲存手動配置」**

---

## 快速檢查清單

- [ ] 批次處理完成，看到 ✅ 成功訊息
- [ ] 展開「🗺️ 特徵映射配置」區塊
- [ ] 選擇配置方式（自動識別/萬用字元/手動對應）
- [ ] **確認冰水側系統** (chiller/chw_pump/scp_pump/chw_temp/chw_pressure/chw_flow)
- [ ] **確認冷卻水側系統** (cw_pump/cw_temp/cw_pressure/cw_flow)
- [ ] **確認冷卻水塔** (cooling_tower)
- [ ] **確認環境參數** (OAT/OAH/WBT)
- [ ] **確認系統層級 Target** (TOTAL_KW 或 COP 或 kW/RT)
- [ ] 看到 ✅ 所有映射欄位都存在
- [ ] （可選）匯出 JSON 保存配置
- [ ] 繼續資料分析或模型訓練

---

## 常見問題

### Q: 為什麼有些欄位沒有出現在多選框中？
A: 欄位可能已經被分到其他類別，或不符合任何識別模式。使用萬用字元模式可以批量匹配所有欄位。

### Q: 萬用字元 `*` 和 `?` 有什麼區別？
A: 
- `*` 匹配任意長度的字元（包括空字串）
  - `CH_*_RT` 匹配 `CH_0_RT`, `CH_10_RT`, `CH_ABC_RT`
- `?` 只匹配單一字元
  - `CH?_RT` 匹配 `CH0_RT`, `CH1_RT`，但不匹配 `CH_0_RT`

### Q: 如何修改已儲存的映射？
A: 展開「📋 查看/編輯當前映射」，然後切換回「自動識別」、「萬用字元」或「手動對應」重新配置。

### Q: 訓練時會自動使用這個映射嗎？
A: 會！在「⚡ 最佳化模擬」模式訓練時，會優先使用 `batch_feature_mapping`，其次才使用側邊欄的映射設定。

### Q: 如何匯出映射給其他案場使用？
A: 點擊「📥 匯出 JSON」，下載的檔案可以在其他案場的 UI 中使用「上傳 JSON」載入，或作為萬用字元模式的模板。

### Q: V3 與 V2 的 JSON 格式相容嗎？
A: V3 可以讀取 V2 格式的 JSON，但會提示升級建議。匯出時會使用 V3 格式（包含物理系統分組資訊）。

---

## 萬用字元模式進階技巧

### 技巧 1: 使用多個模式
```
chiller: CH_*_RT, CH_*_KW, CHILLER_*_POWER
```

### 技巧 2: 匹配不同命名風格
```
chw_pump: CHP*_VFD*, CHP*_HZ*, PUMP*CHW*VFD*
```

### 技巧 3: 排除特定欄位
如果某些欄位被錯誤匹配，可以在手動模式中移除，或使用更精確的模式：
```
# 避免匹配到 TEST_CH_0_RT
chiller: CH_[0-9]_RT, CH_[0-9][0-9]_RT
```

---

**文件版本**: V3.0  
**更新日期**: 2026-02-10
