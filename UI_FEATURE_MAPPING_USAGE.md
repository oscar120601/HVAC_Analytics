# 整合後的 Feature Mapping 使用說明

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
│                                     │
│  [查看當前映射 ▼]                   │
│                                     │
├─────────────────────────────────────┤
│  HVAC Analytics | Spec-Kit          │
└─────────────────────────────────────┘
```

---

## 三種使用方式

### 方式一：使用預設映射（最簡單）

1. **選擇** `使用預設 (Use Default)`
2. 系統自動載入包含環境參數的預設映射：
   - `CT_SYS_OAT` - 外氣溫度
   - `CT_SYS_OAH` - 外氣濕度
   - `CT_SYS_WBT` - 濕球溫度

3. **查看詳情**：點擊「查看當前映射」展開
   ```
   目標: CH_SYS_TOTAL_KW
   負載: 4 欄位
   冷凍泵: 5 欄位
   冷卻泵: 5 欄位
   冷卻塔: 5 欄位
   溫度: 4 欄位
   環境: 3 欄位
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

**JSON 格式範例：**
```json
{
  "load_cols": ["CH_0_RT", "CH_1_RT"],
  "chw_pump_hz_cols": ["CHP_01_VFD_OUT"],
  "cw_pump_hz_cols": ["CWP_01_VFD_OUT"],
  "ct_fan_hz_cols": ["CT_01_VFD_OUT"],
  "temp_cols": ["CH_0_SWT", "CH_0_RWT"],
  "env_cols": ["CT_SYS_OAT", "CT_SYS_OAH", "CT_SYS_WBT"],
  "target_col": "CH_SYS_TOTAL_KW"
}
```

---

## 訓練模型時自動套用

設定好 Feature Mapping 後，在「⚡ 最佳化模擬」模式中訓練新模型時：

```
🔧 訓練新模型
━━━━━━━━━━━━━━━━━━━━
✅ 所有必要欄位都存在
📋 使用 Feature Mapping: 26 個特徵  ← 顯示在這裡
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
   → 展開「查看當前映射」確認環境欄位有包含

4. 執行資料處理/訓練
   系統會自動使用設定的映射
```

### 切換不同案場

```
1. 側邊欄 > 🗺️ 特徵映射
2. 選擇「上傳 JSON」
3. 上傳案場專屬的映射檔
4. 繼續處理資料
```

---

## 環境參數說明

| 參數名稱 | 說明 | 單位 |
|---------|------|------|
| `CT_SYS_OAT` | 外氣溫度 (Outdoor Air Temperature) | °C |
| `CT_SYS_OAH` | 外氣濕度 (Outdoor Air Humidity) | % |
| `CT_SYS_WBT` | 外氣濕球溫度 (Wet Bulb Temperature) | °C |

這些環境參數會被納入模型訓練，影響特徵重要性分析結果！

---

## 驗證是否生效

訓練完成後，查看特徵重要性：

```
📊 特徵重要性分析
1. CH_0_RT: 0.2847
2. CT_01_VFD_OUT: 0.1123
3. CT_SYS_OAT: 0.0891    ← 環境參數出現了！
4. CT_SYS_WBT: 0.0765    ← 環境參數出現了！
```

如果看到 `CT_SYS_OAT`, `CT_SYS_OAH`, `CT_SYS_WBT` 出現在重要性列表，表示設定成功！

---

## 故障排除

### 問題：環境欄位沒有出現在特徵重要性中

**解決方法：**
1. 檢查側邊欄的「查看當前映射」是否有顯示環境欄位
2. 確認你的 CSV 檔案真的有這些欄位名稱
3. 如果欄位名稱不同，使用「上傳 JSON」自定義映射

### 問題：訓練時出現「缺少必要欄位」錯誤

**解決方法：**
1. 切換到「使用預設」映射
2. 或使用「上傳 JSON」提供符合你資料的映射
3. 檢查「查看當前映射」中的欄位是否都存在於 CSV
