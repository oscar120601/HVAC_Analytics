# Feature Mapping V3 使用說明

## 啟動方式

```powershell
cd "d:\DeltaBox\oscar.chang\OneDrive - Delta Electronics, Inc\HVAC_Analytics"
streamlit run etl_ui.py
```

---

## UI 介面位置

### 側邊欄 > 🗺️ 特徵映射 (Feature Mapping)

在左側設定區塊的最下方，你會看到：

```
┌─────────────────────────────────────┐
│  🗺️ 特徵映射 (Feature Mapping)       │
│                                     │
│  選擇映射配置 ▼                     │
│  • 使用預設 (Use Default)          │
│  • 使用預定義 (Predefined)          │
│  • 上傳 JSON (Upload JSON)          │
│  • 萬用字元模式 (Wildcard) 🆕      │
│                                     │
│  [查看當前映射 ▼]                   │
│                                     │
├─────────────────────────────────────┤
│  HVAC Analytics | Spec-Kit          │
└─────────────────────────────────────┘
```

---

## 四種使用方式

### 方式一：使用預設映射（最簡單）

1. **選擇** `使用預設 (Use Default)`
2. 系統自動載入包含環境參數的預設映射：
   - `CT_SYS_OAT` - 外氣溫度
   - `CT_SYS_OAH` - 外氣濕度
   - `CT_SYS_WBT` - 濕球溫度

3. **查看詳情**：點擊「查看當前映射」展開
   ```
   ⚡🎯 目標: CH_SYS_TOTAL_KW
   
   ❄️ 冰水側系統:
   • 冰水機 (chiller): 4 欄位
   • 冰水泵 (chw_pump): 5 欄位
   • 區域泵 (scp_pump): 2 欄位
   • 冰水溫度 (chw_temp): 4 欄位
   • 冰水壓力 (chw_pressure): 2 欄位
   • 冰水流量 (chw_flow): 1 欄位
   
   🔥 冷卻水側系統:
   • 冷卻水泵 (cw_pump): 5 欄位
   • 冷卻水溫度 (cw_temp): 2 欄位
   • 冷卻水壓力 (cw_pressure): 2 欄位
   • 冷卻水流量 (cw_flow): 1 欄位
   
   🏭 冷卻水塔系統:
   • 冷卻水塔 (cooling_tower): 4 欄位
   
   🌍 環境參數:
   • 環境 (environment): 3 欄位
     - CT_SYS_OAT, CT_SYS_OAH, CT_SYS_WBT
   ```

### 方式二：使用其他預定義映射

1. **選擇** `使用預定義 (Predefined)`
2. **選擇預設映射**：
   - `default` - 預設配置（含環境參數）
   - `cgmh_ty` - 長庚桃園案場配置
   - `alternative_01` - 替代命名範例

### 方式三：上傳自定義 JSON

1. **選擇** `上傳 JSON (Upload JSON)`
2. **上傳檔案**：選擇你的 `feature_mapping.json`
3. 系統會自動載入並套用

**JSON 格式範例（V3 格式）：**
```json
{
  "version": "3.0",
  "chilled_water_side": {
    "chiller": ["CH_0_RT", "CH_1_RT"],
    "chw_pump": ["CHP_01_VFD_OUT", "CHP_02_VFD_OUT"],
    "scp_pump": ["SCP_01_VFD_OUT"],
    "chw_temp": ["CH_0_SWT", "CH_0_RWT"],
    "chw_pressure": ["CHW_S_PRESSURE", "CHW_R_PRESSURE"],
    "chw_flow": ["CHW_FLOW"]
  },
  "condenser_water_side": {
    "cw_pump": ["CWP_01_VFD_OUT", "CWP_02_VFD_OUT"],
    "cw_temp": ["CW_SYS_SWT", "CW_SYS_RWT"],
    "cw_pressure": ["CW_S_PRESSURE", "CW_R_PRESSURE"],
    "cw_flow": ["CW_FLOW"]
  },
  "cooling_tower": {
    "cooling_tower": ["CT_01_VFD_OUT", "CT_02_VFD_OUT"]
  },
  "environment": {
    "environment": ["CT_SYS_OAT", "CT_SYS_OAH", "CT_SYS_WBT"]
  },
  "system_level": {
    "system_level": ["CH_SYS_TOTAL_KW"]
  }
}
```

### 方式四：萬用字元模式 (Wildcard Mode) 🆕

適用於有大量相似命名欄位的案場，使用 `*` 和 `?` 進行批量匹配：

1. **選擇** `萬用字元模式 (Wildcard)`
2. **輸入萬用字元規則**：

```
┌──────────────────────────────────────────────────────────────┐
│ 🗺️ 萬用字元模式配置                                          │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ❄️ chiller:        CH_*_RT, CH_*_KW          [匹配所有冰水機] │
│  💧 chw_pump:       CHP_*_VFD_OUT             [匹配所有冰水泵] │
│  🔄 scp_pump:       SCP_*_VFD_OUT             [匹配所有區域泵] │
│  🌡️ chw_temp:       CH_*_SWT, CH_*_RWT        [匹配冰水溫度]  │
│  📊 chw_pressure:   CHW_*_PRESSURE            [匹配冰水壓力]  │
│  🌊 chw_flow:       CHW_*FLOW*                [匹配冰水流量]  │
│                                                              │
│  🔥 cw_pump:        CWP_*_VFD_OUT             [匹配冷卻水泵]  │
│  🌡️ cw_temp:        CW_*_SWT, CW_*_RWT        [匹配冷卻水溫]  │
│  📊 cw_pressure:    CW_*_PRESSURE             [匹配冷卻水壓]  │
│  🌊 cw_flow:        CW_*FLOW*                 [匹配冷卻水流]  │
│                                                              │
│  🏭 cooling_tower:  CT_*_VFD_OUT, CT_*_KW     [匹配冷卻水塔]  │
│  🌍 environment:    *_OAT, *_OAH, *_WBT       [匹配環境參數]  │
│  ⚡🎯 system_level:  *_TOTAL_KW, SYS_COP      [匹配系統層級] │
│                                                              │
│              [✨ 套用萬用字元規則]                            │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**萬用字元語法：**
| 符號 | 說明 | 範例 |
|-----|------|------|
| `*` | 匹配任意字元序列（0個或多個） | `CH_*_RT` 匹配 `CH_0_RT`, `CH_1_RT` |
| `?` | 匹配單一任意字元 | `CH?_RT` 匹配 `CH0_RT`, `CH1_RT` |
| `,` | 分隔多個模式 | `CH_*_RT, CH_*_KW` |

---

## 按物理系統分組的顯示

V3 的 UI 會按照 HVAC 物理系統分組顯示：

```
📋 查看/編輯當前映射

═══════════════════════════════════════════════════════════════
❄️ 冰水側系統 (Chilled Water Side)
═══════════════════════════════════════════════════════════════
• chiller (冰水機): 4 欄位
  CH_0_RT, CH_1_RT, CH_2_RT, CH_3_RT
• chw_pump (冰水泵): 4 欄位
  CHP_01_VFD_OUT, CHP_02_VFD_OUT, ...
• scp_pump (區域泵): 2 欄位
  SCP_01_VFD_OUT, SCP_02_VFD_OUT
• chw_temp (冰水溫度): 4 欄位
  CH_0_SWT, CH_0_RWT, CH_1_SWT, CH_1_RWT
• chw_pressure (冰水壓力): 2 欄位
  CHW_SUPPLY_PRESSURE, CHW_RETURN_PRESSURE
• chw_flow (冰水流量): 1 欄位
  CHW_FLOW

═══════════════════════════════════════════════════════════════
🔥 冷卻水側系統 (Condenser Water Side)
═══════════════════════════════════════════════════════════════
• cw_pump (冷卻水泵): 4 欄位
  CWP_01_VFD_OUT, CWP_02_VFD_OUT, ...
• cw_temp (冷卻水溫度): 2 欄位
  CW_SYS_SWT, CW_SYS_RWT
• cw_pressure (冷卻水壓力): 2 欄位
  CW_SUPPLY_PRESSURE, CW_RETURN_PRESSURE
• cw_flow (冷卻水流量): 1 欄位
  CW_FLOW

═══════════════════════════════════════════════════════════════
🏭 冷卻水塔系統 (Cooling Tower)
═══════════════════════════════════════════════════════════════
• cooling_tower: 4 欄位
  CT_01_VFD_OUT, CT_02_VFD_OUT, CT_01_KW, CT_02_KW

═══════════════════════════════════════════════════════════════
🌍 環境參數 (Environment)
═══════════════════════════════════════════════════════════════
• environment: 3 欄位
  CT_SYS_OAT, CT_SYS_OAH, CT_SYS_WBT

═══════════════════════════════════════════════════════════════
⚡🎯 系統層級 (System Level)
═══════════════════════════════════════════════════════════════
• system_level (Target): 1 欄位
  CH_SYS_TOTAL_KW
```

---

## Target 選擇說明

在 V3 中，Target（預測目標）可以是以下類型：

| Target 類型 | 圖示 | 說明 | 典型欄位 | 應用場景 |
|------------|-----|------|---------|---------|
| **總用電功率** | ⚡ | 系統總功耗 | `CH_SYS_TOTAL_KW` | 能耗預測與優化 |
| **COP** | 📈 | 性能係數 (製冷量/功耗) | `SYS_COP`, `CH_0_COP` | 效率優化 |
| **kW/RT** | 🎯 | 單位冷噸能耗 | `SYS_KW_RT` | 效率基準比較 |

```
┌──────────────────────────────────────────────────────────────┐
│ ⚡🎯 目標變數 (Target)                                        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  選擇 Target 類型:                                           │
│  ○ 總用電功率 (kW)                                           │
│  ○ COP (性能係數)                                            │
│  ● kW/RT (單位冷噸能耗)                                      │
│                                                              │
│  選擇欄位: [SYS_KW_RT ▼]                                     │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 訓練模型時自動套用

設定好 Feature Mapping 後，在「⚡ 最佳化模擬」模式中訓練新模型時：

```
🔧 訓練新模型
━━━━━━━━━━━━━━━━━━━━
✅ 所有必要欄位都存在
📋 使用 Feature Mapping V3: 26 個特徵
   ❄️ 冰水側: 12 個特徵
   🔥 冷卻水側: 8 個特徵
   🏭 冷卻水塔: 3 個特徵
   🌍 環境: 3 個特徵
⚡🎯 Target: CH_SYS_TOTAL_KW
進度條 [████████████████] 100%
✅ 訓練完成！
```

系統會自動使用你在側邊欄設定的映射配置！

---

## 工作流程建議

### 第一次使用（推薦步驟）

```
1. 啟動 UI
   streamlit run etl_ui.py

2. 選擇處理模式
   [單一檔案] 或 [批次處理]

3. 設定 Feature Mapping（側邊欄最下方）
   → 選擇「使用預設」
   → 或選擇「萬用字元模式」輸入規則
   → 展開「查看當前映射」確認配置

4. 確認物理系統分組正確
   → 冰水側、冷卻水側、冷卻水塔、環境、系統層級

5. 執行資料處理/訓練
   系統會自動使用設定的映射
```

### 切換不同案場

```
1. 側邊欄 > 🗺️ 特徵映射
2. 選擇「上傳 JSON」或「萬用字元模式」
3. 載入案場專屬配置
4. 繼續處理資料
```

---

## 環境參數說明

| 參數名稱 | 說明 | 單位 | 所屬類別 |
|---------|------|------|---------|
| `CT_SYS_OAT` | 外氣溫度 (Outdoor Air Temperature) | °C | environment |
| `CT_SYS_OAH` | 外氣濕度 (Outdoor Air Humidity) | % | environment |
| `CT_SYS_WBT` | 外氣濕球溫度 (Wet Bulb Temperature) | °C | environment |

這些環境參數會被納入模型訓練，影響特徵重要性分析結果！

---

## 驗證是否生效

訓練完成後，查看特徵重要性：

```
📊 特徵重要性分析
═══════════════════════════════════════════════════
❄️ 冰水側系統:
1. CH_0_RT: 0.2847
2. CHP_01_VFD_OUT: 0.1563
3. CH_0_SWT: 0.0891

🔥 冷卻水側系統:
4. CWP_01_VFD_OUT: 0.1123
5. CW_SYS_SWT: 0.0654

🏭 冷卻水塔系統:
6. CT_01_VFD_OUT: 0.0789

🌍 環境參數:
7. CT_SYS_OAT: 0.0891    ← 環境參數出現了！
8. CT_SYS_WBT: 0.0765    ← 環境參數出現了！
```

如果看到物理系統分組和環境參數正確顯示，表示 V3 設定成功！

---

## 故障排除

### 問題：環境欄位沒有出現在特徵重要性中

**解決方法：**
1. 檢查側邊欄的「查看當前映射」是否有顯示環境欄位
2. 確認你的 CSV 檔案真的有這些欄位名稱
3. 如果欄位名稱不同，使用「上傳 JSON」或「萬用字元模式」自定義映射

### 問題：訓練時出現「缺少必要欄位」錯誤

**解決方法：**
1. 切換到「使用預設」映射
2. 或使用「萬用字元模式」提供符合你資料的映射
3. 檢查「查看當前映射」中的欄位是否都存在於 CSV

### 問題：萬用字元沒有匹配到預期的欄位

**解決方法：**
1. 檢查欄位名稱是否有空格或特殊字元
2. 使用 `*` 代替不確定的部分，例如 `CH*RT` 會匹配 `CH_0_RT` 和 `CH0_RT`
3. 點擊「預覽匹配結果」查看哪些欄位被匹配

---

**文件版本**: V3.0  
**更新日期**: 2026-02-10
