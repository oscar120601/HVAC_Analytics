# HVAC Analytics - Core Engine

> 空調節能系統核心引擎 - 資料清洗與能源最佳化建議

**專案狀態**: ✅ Phase 0 Retrofit 完成 | Sprint 3-5 開發就緒  
**最後更新**: 2026-03-02

---

## 📊 專案概覽

HVAC-1 是一個專注於資料清洗與離線能源最佳化建議的空調節能系統，採用嚴格契約導向設計與 SSOT 原則。

### 核心資料流

```
Raw Data → Parser → Cleaner → BatchProcessor → FeatureEngineer → ModelTraining → Optimization
                ↑              ↑                                      ↓              ↓
        Feature Annotation    Topology Context                  Model Registry    Continual Learning
        (Excel → YAML SSOT)   (GNN Adjacency)                   Index             (GEM + Drift Detection)
```

### 設計原則

| 原則 | 說明 |
|:-----|:-----|
| **契約導向設計** | 嚴格定義模組間介面與檢查點 (E000-E999) |
| **單一真相源** | 所有配置與常數集中管理 |
| **Foundation First** | 基礎設施優先，確保下游模組有穩固依賴 |
| **Fail Fast** | 寧可終止流程，也不傳遞可疑資料 |

---

## 🎯 功能狀態

| 階段 | 模組 | 狀態 | 測試 |
|:---:|:---|:---:|:---:|
| Sprint 1 | Interface Contract v1.2 | ✅ 已完成 | 35/35 通過 |
| Sprint 1 | System Integration v1.2 | ✅ 已完成 | 35/35 通過 |
| Sprint 1 | Feature Annotation v1.4 | ✅ PRD 完成 | 拓樸感知 |
| Sprint 2 | Parser v2.2 | ✅ 已完成 | 29/29 通過 |
| Sprint 2 | Cleaner v2.2 | ✅ 已完成 | 26/26 通過 🟢 A級 |
| Sprint 2 | BatchProcessor v1.3 | ✅ 已完成 | 32/32 通過 |
| **Phase 0** | **v1.4 Retrofit** | ✅ **已完成** | ETL 拓樸貫通 |
| Sprint 3 | Feature Engineer v1.4 | ⏳ 待開發 | GNN 輸出 |
| Sprint 3 | Model Training v1.4 | ⏳ 待開發 | Physics Loss |
| Sprint 4 | Continual Learning v1.1 | ⏳ 待開發 | GEM + Drift |
| Sprint 4 | Optimization v1.2 | ⏳ 待開發 | CL 整合 |

**累計測試**: 140+ 項全部通過 ✅

---

## 🚀 快速開始

### 安裝依賴

```bash
pip install -r requirements.txt
```

### 執行互動式 ETL 測試工具

```bash
# 1. 啟動後端伺服器
uvicorn tools.demo.test_server:app --reload --port 8000

# 2. 用瀏覽器開啟 tools/demo/tester.html
# 3. 依序執行 Step 1 → Step 2 → Step 3 → Step 4
```

### 程式化使用

```python
from src.container import ETLContainer

# 初始化完整 ETL 管道
container = ETLContainer(site_id="demo_site")
container.initialize_all()

# 取得元件
parser = container.get_parser()
cleaner = container.get_cleaner()
config = container.get_config()
```

---

## 📁 專案結構

```
HVAC-1/
├── src/                        # 核心源碼
│   ├── container.py            # ETLContainer DI 容器
│   ├── context.py              # PipelineContext 時間基準
│   ├── features/               # Feature Annotation v1.4
│   ├── etl/                    # ETL 管道
│   │   ├── parser/             # Parser V2.2 模組化
│   │   ├── cleaner.py          # DataCleaner v2.2
│   │   ├── batch_processor.py  # BatchProcessor v1.3
│   │   └── config_models.py    # SSOT 配置模型
│   └── utils/                  # 工具函式
├── config/                     # 配置檔案
│   ├── features/               # Feature Annotation YAML
│   └── site_templates.yaml     # 案場範本
├── tools/                      # 工具鏈
│   ├── demo/                   # 互動測試 UI
│   │   ├── tester.html         # ETL 測試網頁
│   │   └── test_server.py      # FastAPI 後端
│   └── features/               # Feature Annotation 工具
│       ├── wizard.py           # Wizard CLI
│       └── excel_to_yaml.py    # 轉換器
├── tests/                      # 單元測試
├── docs/                       # 專案文件
│   ├── 專案任務排程/           # 任務排程與執行摘要
│   ├── Interface Contract/     # Interface Contract v1.2
│   ├── 測試工具說明/           # 互動測試工具說明
│   ├── Feature Annotation/     # Feature Annotation v1.4
│   ├── feature_engineering/    # Feature Engineer v1.4
│   ├── Model_Training/         # Model Training v1.4
│   └── Continual_Learning/     # Continual Learning v1.1
└── main.py                     # CLI 主程式
```

---

## 📚 文件索引

| 文件 | 說明 |
|:-----|:-----|
| [📋 完整任務排程](docs/專案任務排程/專案任務排程文件.md) | Sprint 1-5 詳細任務與時程 |
| [📋 Sprint 2 審查報告](docs/專案任務排程/Sprint_2_Review_Report.md) | Parser/Cleaner/BatchProcessor 審查結果 |
| [📖 Interface Contract v1.2](docs/Interface%20Contract/PRD_Interface_Contract_v1.2.md) | 錯誤代碼體系 E000-E999 |
| [📖 Feature Annotation v1.4](docs/Feature%20Annotation%20Specification/PRD_Feature_Annotation_Specification_V1.4.md) | 拓樸感知規格 |
| [📖 互動測試工具說明](docs/測試工具說明/Interactive_ETL_Tester.md) | tester.html 使用指南 |
| [🎨 Demo 展示](tools/demo/index.html) | Sprint 1 & 2 成果展示 |

---

## 🛠️ 核心功能

### Parser V2.2 - 模組化解析

支援多格式 CSV 解析，採用 Strategy Pattern 架構：

```python
from src.etl.parser import ParserFactory

# 自動偵測格式
parser = ParserFactory.auto_detect("data.csv")
df = parser.parse_file("data.csv")

# 明確指定 Siemens Scheduler 格式
parser = ParserFactory.create_parser("siemens_scheduler")
```

**支援格式**: 通用 CSV | Siemens Scheduler Report | 自動偵測

### Cleaner V2.2 - 語意感知清洗

- **時區強制轉換**: 輸出必為 UTC/ns
- **語意感知清洗**: 依 device_role 調整閾值
- **設備邏輯預檢**: E350 設備違規檢測
- **Schema 淨化**: E500 防護確保敏感欄位不外洩

### Feature Annotation v1.4

Excel → YAML 單向轉換，支援拓樸註記：

```bash
# 產生 Excel 範本
python tools/features/wizard.py --site demo_site --csv data.csv --excel features.xlsx

# 轉換為 YAML
python tools/features/excel_to_yaml.py --input features.xlsx --output config/features/sites/demo_site.yaml
```

---

## 🧪 測試

```bash
# 執行所有測試
pytest tests/ -v

# 執行特定模組測試
pytest tests/test_parser_v21.py -v
pytest tests/test_cleaner_v22.py -v
pytest tests/test_batch_processor_v13.py -v
```

---

## 🔗 錯誤代碼速查

| 範圍 | 類別 |
|:---:|:---|
| E000-E099 | 系統級錯誤 (時間基準、上下文) |
| E100-E199 | Parser 錯誤 (編碼、時區、標頭) |
| E200-E299 | 資料品質錯誤 (缺漏、異常、未來資料) |
| E300-E399 | Feature Annotation 錯誤 |
| E350-E399 | 設備驗證錯誤 (E350 設備邏輯違規) |
| E400-E499 | 配置錯誤 (SSOT、同步檢查) |
| E500-E599 | 安全錯誤 (device_role 外洩) |
| E600-E699 | 特徵工程錯誤 |
| E700-E799 | 模型訓練錯誤 |
| **E750-E759** | **GNN 拓樸錯誤** 🆕 v1.4 |
| **E800-E829** | **持續學習錯誤** 🆕 v1.4 |
| **E840-E859** | **最佳化錯誤** 🆕 v1.4 |
| E900-E999 | 整合錯誤 (特徵對齊、契約違反) |

---

## 📅 近期更新

### [v1.6.0] - 2026-03-02
- ✅ Phase 0 Retrofit 完成 - ETL 管線拓樸貫通
- ✅ Interactive ETL Tester v1.6 - 新增 GNN 拓樸摘要面板
- ✅ 錯誤代碼重分配 - E750-E759 (GNN), E800-E829 (CL), E840-E859 (OPT)

### [v1.5.0] - 2026-02-25
- ✅ Parser V2.2 模組化重構完成
- ✅ Interactive ETL Tester V1.5 - Step 1→2 無縫整合

---

## 👥 貢獻

本專案採用嚴格的程式碼審查流程，所有變更需通過：
1. 單元測試 (>80% 覆蓋率)
2. 整合測試
3. 程式碼審查 (A級標準)

---

## 📄 授權

[License Information]
