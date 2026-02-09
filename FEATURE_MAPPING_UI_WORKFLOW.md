# Feature Mapping UI 工作順序與使用指南

## 工作順序總覽

| 順序 | 任務 | 狀態 |
|:---:|------|:----:|
| **1** | 更新 FeatureMapping 支援環境參數 (env_cols) | ✅ 完成 |
| **2** | 更新 ModelConfig 和 ChillerEnergyModel | ✅ 完成 |
| **3** | 建立 CLI 映射編輯器 | ✅ 完成 |
| **4** | 建立 Streamlit Web UI | ✅ 完成 |
| **5** | 驗證與測試 | ✅ 完成 |

---

## 新增功能

### 1. 環境參數支援

新增 `env_cols` 類別，包含以下監控點：

| 欄位名稱 | 說明 |
|---------|------|
| `CT_SYS_OAT` | 外氣溫度 (Outdoor Air Temperature) |
| `CT_SYS_OAH` | 外氣濕度 (Outdoor Air Humidity) |
| `CT_SYS_WBT` | 外氣濕球溫度 (Wet Bulb Temperature) |

### 2. 三種使用方式

#### 方式 A: CLI 互動編輯器
```bash
# 啟動互動式編輯器
python -m src.config.mapping_editor

# 或帶入 CSV 自動分析
python -m src.config.mapping_editor data/sample.csv
```

#### 方式 B: Streamlit Web UI
```bash
# 啟動網頁介面
streamlit run mapping_editor_ui.py
```

#### 方式 C: Python API
```python
from src.models.energy_model import ChillerEnergyModel

# 使用預設映射（包含環境參數）
model = ChillerEnergyModel(feature_mapping='default')

# 或使用自定義 JSON
model = ChillerEnergyModel(feature_mapping='my_mapping.json')
```

---

## 快速使用指南

### 第一次使用

#### Step 1: 啟動 Web UI
```bash
streamlit run mapping_editor_ui.py
```

#### Step 2: 上傳 CSV 檔案
- 在左側欄位點擊 "Upload CSV"
- 選擇你的資料檔案
- 點擊 "Load CSV"

#### Step 3: 自動產生映射
- 點擊 "自動產生映射 (Auto-create)"
- 系統會自動識別欄位類別

#### Step 4: 檢查環境參數
- 確認 "環境參數 (Environment)" 區塊包含：
  - CT_SYS_OAT (外氣溫度)
  - CT_SYS_OAH (外氣濕度)
  - CT_SYS_WBT (濕球溫度)

#### Step 5: 儲存設定
- 輸入檔案名稱（如 `cgmh_mapping.json`）
- 點擊 "下載 JSON"

#### Step 6: 用於訓練
```bash
python main.py train data/CGMH-TY --mapping cgmh_mapping.json
```

---

## 配置文件範例

### 完整的 feature_mapping.json

```json
{
  "load_cols": [
    "CH_0_RT",
    "CH_1_RT",
    "CH_2_RT",
    "CH_3_RT"
  ],
  "chw_pump_hz_cols": [
    "CHP_01_VFD_OUT",
    "CHP_02_VFD_OUT",
    "CHP_03_VFD_OUT",
    "CHP_04_VFD_OUT",
    "CHP_05_VFD_OUT"
  ],
  "cw_pump_hz_cols": [
    "CWP_01_VFD_OUT",
    "CWP_02_VFD_OUT",
    "CWP_03_VFD_OUT",
    "CWP_04_VFD_OUT",
    "CWP_05_VFD_OUT"
  ],
  "ct_fan_hz_cols": [
    "CT_01_VFD_OUT",
    "CT_02_VFD_OUT",
    "CT_03_VFD_OUT",
    "CT_04_VFD_OUT",
    "CT_05_VFD_OUT"
  ],
  "temp_cols": [
    "CH_0_SWT",
    "CH_0_RWT",
    "CW_SYS_SWT",
    "CW_SYS_RWT"
  ],
  "env_cols": [
    "CT_SYS_OAT",
    "CT_SYS_OAH",
    "CT_SYS_WBT"
  ],
  "target_col": "CH_SYS_TOTAL_KW",
  "custom_features": null
}
```

---

## 建立的新檔案

| 檔案 | 說明 |
|------|------|
| `src/config/feature_mapping.py` | 特徵映射核心模組（已更新含 env_cols） |
| `src/config/mapping_editor.py` | CLI 互動編輯器 |
| `mapping_editor_ui.py` | Streamlit Web UI |
| `config/examples/my_site_mapping.json` | 完整範例配置（含環境參數） |
| `config/FEATURE_MAPPING_GUIDE.md` | 詳細使用指南 |

---

## 驗證結果

```
[OK] Default mapping loaded
Environment cols: ['CT_SYS_OAT', 'CT_SYS_OAH', 'CT_SYS_WBT']

[OK] FeatureMapping created with env_cols

[OK] Model created with environment features

[OK] All tests passed!
```

---

## 下一步建議

1. **啟動 Web UI** 嘗試視覺化編輯
   ```bash
   streamlit run mapping_editor_ui.py
   ```

2. **測試訓練** 使用新的映射配置
   ```bash
   python main.py train data/CGMH-TY --mapping default
   ```

3. **觀察特徵重要性** 查看環境參數的影響程度
   - CT_SYS_OAT/OAH/WBT 應該會出現在重要性排名中
