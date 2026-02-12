# 同事重構建議審閱與優化分析

## 📋 總評

你同事的建議**方向正確**，核心觀點「提供乾淨的黑盒子給後端工程師」是對的。但基於你目前的**實際程式碼現況**，有些建議需要調整、有些已經部分存在但同事可能沒看到，還有一些重要的點被遺漏了。

以下逐條分析：

---

## ✅ 完全同意的建議

### 1. 建立 `interface.py`（對接層）— 最高優先級

> [!IMPORTANT]
> 這是最關鍵的缺失，你的 `main.py` 目前是 384 行的 CLI 類別 (`HVACAnalyticsCLI`)，用 Python Fire 驅動。後端工程師無法直接 `import` 使用。

你的程式碼其實已經有很好的 class 封裝（`ChillerEnergyModel`、`ChillerOptimizer`），但缺少一個**統一的 Facade**。建議建立 `src/interface.py`，內部組合這些類別：

```python
# src/interface.py
class HVACService:
    def load_model(self, path: str) -> None: ...
    def predict_energy(self, sensor_data: dict) -> float: ...
    def optimize(self, context: dict, constraints: dict = None) -> dict: ...
    def parse_and_clean(self, file_path: str, options: dict = None) -> dict: ...
```

### 2. 清理版本檔案 — 同意

你的 `src/config/` 目前有：
- `feature_mapping.py` (17KB)
- `feature_mapping_v1_backup.py` (13KB)
- `feature_mapping_v2.py` (32KB)
- `mapping_editor.py` (12KB)

**共 4 個檔案、75KB**，而且 `energy_model.py` 裡面 import 的是 `feature_mapping_v2`。這確實是版控災難。

### 3. 定義 `schemas.py`（Pydantic）— 同意

你的 `optimizer.py` 已經用 `@dataclass` 定義了 `OptimizationConstraints`、`OptimizationContext`、`OptimizationResult`，這些非常適合轉為 Pydantic `BaseModel`，一方面給後端使用，一方面自帶資料驗證。

---

## ⚠️ 需要調整的建議

### 4. 配置抽為 YAML — 需要更細緻的策略

同事建議把 `feature_mapping.py` 改為 YAML，但你的 feature mapping **不只是設定值**，它包含 Python 邏輯（`FeatureMapping` 類別有方法）。

**建議做法：**
- **靜態對應表**（欄位 alias → 標準名稱）→ 抽成 YAML/JSON（放 `configs/sites/`）
- **映射邏輯**（驗證、轉換方法）→ 保留 Python 類別，但只留一個檔案

```
configs/
├── base.yaml              # 系統通用參數（已存在於 config/settings.yaml）
└── sites/
    ├── cgmh_ty.yaml        # 長庚桃園案場欄位對應
    └── farglory.yaml       # 遠雄案場欄位對應
```

### 5. Model Artifacts 目錄 — 你已有 `models/`

同事建議新增 `artifacts/`，但你的專案**已經有 `models/` 目錄**（雖然目前是空的），而且 `.gitignore` 已經設定 `models/*.pkl` 和 `models/*.joblib`。

**建議：** 不需要另建 `artifacts/`，沿用 `models/` 即可，避免遷移成本。但可以加上子目錄區分：

```
models/
├── trained/              # 訓練好的模型檔
│   └── energy_model.joblib
└── metadata/             # 模型元資料（版本、metrics、訓練參數）
    └── energy_model_meta.json
```

### 6. Dockerfile — 優先級中等，非「CRITICAL」

> [!NOTE]
> Dockerfile 重要，但不是第一步。如果後端團隊有自己的容器化流程，他們可能更希望你提供乾淨的 `pyproject.toml` + 鎖定依賴版本，而不是你寫一個他們無法客製的 Dockerfile。

**建議順序：**
1. 先把 `requirements.txt` 升級為 `pyproject.toml`（標準化）
2. 鎖定版本（`pip freeze` 或 `uv lock`）
3. *再* 提供 Dockerfile 作為參考

---

## 🔴 同事遺漏的重要建議

### 7. 缺少 `__init__.py` — 模組匯入會爆炸

你的 `src/etl/` 和 `src/config/` 目錄**沒有 `__init__.py`**（只有 `src/models/` 和 `src/optimization/` 有）。這會導致後端做 `from src.etl import parser` 時失敗。

> [!CAUTION]
> 這是最容易被忽略但會直接導致整合失敗的問題。每個 `src/` 的子目錄都需要 `__init__.py`。

### 8. 缺少錯誤處理契約

`interface.py` 不只要定義「成功回什麼」，更要定義「失敗時丟什麼 Exception」。建議新增自定義例外：

```python
# src/exceptions.py
class HVACError(Exception): """Base exception"""
class DataValidationError(HVACError): """輸入資料格式錯誤"""
class ModelNotTrainedError(HVACError): """模型尚未訓練"""
class OptimizationFailedError(HVACError): """最佳化未收斂"""
```

### 9. 日誌規範化

同事提到 `logs/` 目錄但沒深入。你目前每個模組都用 `logging.basicConfig()` 自己設定，會導致多次初始化衝突。建議統一成一個 `src/utils/logger.py`，所有模組只做 `logger = logging.getLogger(__name__)`。

### 10. 根目錄有雜散檔案

- `md_to_html.py` (3KB)、`md_to_pdf.py` (6KB) — 這些是工具腳本，不是核心功能
- `hvac_feature_classification.json` (31KB) — 應該歸入 `configs/`
- `_backup_20260203/` — 應該刪除（已有 Git）

---

## 📐 建議的最終結構

```
HVAC_Analytics/
├── configs/                    # [RESTRUCTURE] 統一配置
│   ├── base.yaml               # 通用系統參數 (從 config/settings.yaml 搬入)
│   └── sites/                  # 各案場欄位映射 (從 feature_mapping 抽出)
│       └── cgmh_ty.yaml
├── models/                     # [KEEP] 模型產物（已在 .gitignore）
│   ├── trained/
│   └── metadata/
├── src/
│   ├── __init__.py             # [NEW] 必要
│   ├── interface.py            # [NEW] ★ Facade — 後端唯一入口
│   ├── schemas.py              # [NEW] Pydantic I/O 定義
│   ├── exceptions.py           # [NEW] 自定義例外
│   ├── etl/
│   │   ├── __init__.py         # [NEW] 必要
│   │   ├── parser.py
│   │   ├── cleaner.py
│   │   └── batch_processor.py
│   ├── models/
│   │   ├── __init__.py         # [KEEP]
│   │   └── energy_model.py
│   ├── optimization/
│   │   ├── __init__.py         # [KEEP]
│   │   ├── optimizer.py
│   │   └── history_tracker.py
│   ├── config/
│   │   ├── __init__.py         # [NEW] 必要
│   │   ├── feature_mapping.py  # [KEEP] 僅保留最新版，刪除 v1/v2
│   │   └── mapping_editor.py
│   └── utils/                  # [NEW]
│       ├── __init__.py
│       ├── config_loader.py    # 讀取 YAML
│       └── logger.py           # 統一日誌
├── tests/
├── scripts/                    # [NEW] 搬入 md_to_html.py、md_to_pdf.py
├── docs/
├── main.py                     # CLI 入口（保留給你自己測試用）
├── pyproject.toml              # [NEW] 取代 requirements.txt
├── Dockerfile                  # [LATER] 視後端團隊需求再加
└── .gitignore
```

---

## 🎯 執行優先級

| 優先級 | 項目 | 原因 |
|:---:|------|------|
| **P0** | 新增所有 `__init__.py` | 不做就無法 import |
| **P0** | 建立 `interface.py` | 後端整合的唯一入口 |
| **P1** | 建立 `schemas.py` | 定義 I/O 契約 |
| **P1** | 建立 `exceptions.py` | 錯誤處理標準化 |
| **P1** | 清理 feature_mapping 版本檔 | 減少混亂 |
| **P2** | 配置檔重整（YAML 化靜態對應） | 支援多案場 |
| **P2** | 統一日誌、清理根目錄雜散檔案 | 乾淨度 |
| **P3** | `pyproject.toml` + Dockerfile | 環境封裝 |
