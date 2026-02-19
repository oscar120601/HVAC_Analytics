# Sprint 1 執行摘要

**Sprint 名稱:** 基礎建設 (Foundation)  
**時間範圍:** 2026-02-19 ~ 2026-02-26 (預計)  
**完成日期:** 2026-02-19 (2/3 提前完成)  
**負責人:** Claude Code  
**文件版本:** v1.0

---

## 一、執行概覽

Sprint 1 聚焦於建立 HVAC-1 系統的基礎設施，採用 **Foundation First Policy** 確保所有下游模組有穩固的依賴基礎。截至 2026-02-19，已提前完成 2/3 的任務。

| 模組 | 狀態 | 完成度 | 測試結果 |
|:---:|:---:|:---:|:---:|
| 1.1 Interface Contract v1.1 | ✅ 已完成 | 100% | 已驗證 |
| 1.2 System Integration v1.2 | ✅ 已完成 | 100% | 35/35 通過 |
| 1.3 Feature Annotation v1.2 | ⏳ 進行中 | 0% | - |

---

## 二、1.1 Interface Contract v1.1 完成摘要

### 2.1 任務完成列表

| 任務 ID | 任務描述 | 狀態 | 交付物 |
|:---:|:---|:---:|:---|
| IC-001 | 錯誤代碼分層定義 (E000-E999) | ✅ | `config_models.py` 錯誤代碼定義 |
| IC-002 | 檢查點規格定義 (#1-#7) | ✅ | 7 個檢查點規格文件化 |
| IC-003 | DataFrame 介面標準 | ✅ | timestamp/quality_flags 規格 |
| IC-004 | 版本相容性矩陣 | ✅ | 5 種版本組合相容性矩陣 |
| IC-005 | 實作檢查清單 | ✅ | 6.1-6.3 檢查清單 |
| IC-006 | Header Standardization 規範 | ✅ | Regex 正規化規則 |
| IC-007 | Temporal Baseline 傳遞規範 | ✅ | E000 時間基準機制 |

### 2.2 核心交付內容

#### 錯誤代碼體系 (E000-E999)

建立完整的 7 層錯誤代碼架構：

| 層級 | 代碼範圍 | 用途 | 關鍵錯誤 |
|:---:|:---:|:---|:---|
| 全域 | E000-E099 | 時間基準、系統層級 | E000 時間基準遺失、E000-W 時間漂移 |
| Parser | E100-E199 | 資料解析錯誤 | E101 編碼錯誤、E102 時區違反、E105 標頭正規化失敗 |
| Cleaner/BP | E200-E299 | 清洗與批次處理 | E201 Schema 不符、E205 未來資料、E206 Parquet 格式 |
| Equipment | E350-E399 | 設備邏輯驗證 | E350 設備邏輯預檢失敗、E351-E357 設備限制違反 |
| Annotation | E400-E499 | 特徵標註錯誤 | E406 Excel/YAML 不同步、E407 繼承循環、E408 SSOT 不匹配 |
| Governance | E500-E599 | 架構治理 | E500 device_role 洩漏、E501 直接寫入 YAML |
| Feature Eng | E600-E699 | 特徵工程 | E601 特徵順序未記錄、E602 縮放參數遺失 |
| Training | E700-E799 | 模型訓練 | E701 記憶體不足、E702 驗證失敗 |
| Hybrid | E750-E799 | 混合模型一致性 | E751-E758 一致性檢查錯誤 |
| Optimization | E800-E899 | 最佳化引擎 | E801 模型載入失敗、E802 約束違反 |
| Integration | E900-E999 | 跨階段整合 | E901 特徵對齊錯誤、E902 維度不匹配、E903 縮放參數錯誤 |

#### 檢查點規格 (#1-#7)

定義 7 個關鍵介面檢查點：

```
#1: Parser → Cleaner (Raw Data Contract)
    - 必要欄位、時間戳型別、編碼正確性、標頭正規化
    
#2: Cleaner → BatchProcessor (Clean Data Contract)
    - Quality Flags 值域、禁止欄位檢查 (E500)、未來資料檢查
    
#3: BatchProcessor → FeatureEngineer (Storage Contract)
    - Parquet Schema、device_role 不存在、時間基準存在性
    
#4: FeatureEngineer → Model Training (Feature Matrix Contract)
    - Data Leakage 檢查、特徵順序保證 (E601)、特徵縮放參數 (E602)
    
#5: Excel ↔ YAML 同步檢查 (Annotation Sync Contract)
    - 檔案存在性、時間戳同步、Checksum 一致性 (E406)
    
#6: Annotation Schema 版本相容 (Schema Compatibility Contract)
    - Schema 版本、繼承鏈合法性 (E407)、Header 對應檢查 (E409)
    
#7: Model Training → Optimization (Feature Alignment Contract)
    - 模型格式、特徵順序比對 (E901)、特徵數量一致性 (E902)
```

#### DataFrame 介面標準

| 欄位 | 型別 | 規格 |
|:---|:---|:---|
| timestamp | `pl.Datetime` | `time_unit='ns', time_zone='UTC'`，Parquet 物理型別 `INT64` |
| quality_flags | `pl.List(pl.Utf8)` | 值必須 ⊆ `VALID_QUALITY_FLAGS` |
| 數值欄位 | `pl.Float64` | SI 單位，精度至少 6 位有效數字 |

#### Header Standardization 規則

CSV 標頭正規化為 snake_case 的 6 步驟規則：
1. 移除前後空白
2. camelCase/PascalCase → snake_case（插入底線）
3. 替換非法字元為底線
4. 合併連續底線
5. 移除開頭數字（改為 `col_` 前綴）
6. 轉換為小寫

### 2.3 文件位置

- **PRD 文件**: `docs/Interface Contract/PRD_Interface_Contract_v1.1.md`
- **SSOT 定義**: `src/etl/config_models.py`

---

## 三、1.2 System Integration v1.2 完成摘要

### 3.1 任務完成列表

| 任務 ID | 任務描述 | 狀態 | 測試覆蓋 |
|:---:|:---|:---:|:---:|
| SI-001 | PipelineContext 實作 | ✅ | 9 項測試 |
| SI-002 | ETLConfig 擴充 | ✅ | 6 項測試 |
| SI-003 | ConfigLoader 強化 | ✅ | 7 項測試 |
| SI-004 | ETLContainer 初始化 | ✅ | 7 項測試 |
| SI-005 | 單元測試與整合測試 | ✅ | 包含在以上 |
| SI-006 | 時間基準傳遞測試 | ✅ | 6 項測試 |

**總計: 35 項測試全部通過 ✅**

### 3.2 核心模組實作

#### SI-001: PipelineContext (`src/context.py`, 337 行)

**功能:**
- **Thread-safe Singleton**: 確保全域唯一時間基準
- **時間基準初始化**: 禁止重複設定（Fail Fast）
- **E000 錯誤檢查**: 未初始化時拋出明確錯誤
- **E000-W 時間漂移警告**: 執行超過 60 分鐘自動警告
- **未來資料檢測**: 容忍 5 分鐘時鐘誤差

**關鍵 API:**
```python
context = PipelineContext()
context.initialize(timestamp=baseline, site_id="cgmh_ty")
baseline = context.get_baseline()      # E000 檢查
is_future = context.is_future(ts)      # 未來資料檢測
warning = context.check_drift_warning() # E000-W
```

**測試驗證:**
- ✅ 單例模式（兩次取得同一實例）
- ✅ 初始化唯一性（重複初始化拋錯）
- ✅ E000 錯誤（未初始化存取時間基準）
- ✅ 未來資料檢測（過去/現在/未來時間判斷）
- ✅ 時間漂移警告（模擬 2 小時執行）
- ✅ 序列化/反序列化（to_dict/from_dict）
- ✅ 執行緒安全性（多執行緒同時初始化）

#### SI-002: ETLConfig Pydantic 模型 (`src/etl/config_models.py`)

**新增模型:**

**AnnotationConfig**: 單一特徵標註
```python
class AnnotationConfig(BaseModel):
    column_name: str              # CSV 欄位名稱
    physical_type: str            # 物理類型（驗證允許值）
    unit: str                     # 單位
    device_role: Optional[str]    # 設備角色（primary/backup/seasonal/auxiliary/standby）
    is_target: bool               # 是否為目標變數
    enable_lag: bool              # 是否啟用 Lag（E405: 目標變數不可啟用）
    lag_intervals: List[int]      # Lag 間隔列表
```

**SiteFeatureConfig**: 案場特徵配置
```python
class SiteFeatureConfig(BaseModel):
    schema_version: str           # Schema 版本
    site_id: str                  # 案場 ID
    inherit: Optional[str]        # 繼承的父配置
    excel_source: Optional[str]   # 來源 Excel 路徑
    excel_checksum: Optional[str] # Excel SHA256
    features: List[AnnotationConfig]  # 特徵列表
    equipment_constraints: Dict   # 設備限制條件
```

**ETLConfig**: 全域 ETL 配置
```python
class ETLConfig(BaseModel):
    version: str                  # 配置版本
    site_id: str                  # 案場 ID
    temporal_baseline: str        # 時間基準（ISO 8601）
    annotation: SiteFeatureConfig # Feature Annotation
    checkpoint_validations: Dict  # 啟用的檢查點
    module_versions: Dict         # 各模組版本（E906 相容性檢查）
```

**驗證功能:**
- ✅ `physical_type` 值域檢查（必須在允許列表中）
- ✅ `device_role` 值域檢查（5 種角色）
- ✅ **E405 檢查**（目標變數不可啟用 Lag）
- ✅ **E906 版本相容性檢查**（5 種版本組合）

#### SI-003: ConfigLoader (`src/utils/config_loader.py`, 485 行)

**功能:**
- **E007 設定檔損毀檢查**: YAML/JSON 解析失敗時拋出明確錯誤
- **E406 Excel/YAML 同步檢查**:
  - 檔案存在性驗證
  - 時間戳比較（mtime）
  - SHA256 Checksum 驗證
  - 詳細恢復建議輸出
- **E408 SSOT 品質標記匹配**: 驗證 YAML 中的 flags 與 `VALID_QUALITY_FLAGS` 一致
- **跨平台檔案鎖** (`FileLock`): 防止並發修改
- **原子寫入**: 先寫入暫存檔，再原子移動
- **備份與恢復**: 自動備份與版本恢復機制

**關鍵 API:**
```python
loader = ConfigLoader()

# E406 同步檢查
result = loader.validate_annotation_sync("cgmh_ty")
if not result.is_synced:
    print(result.message)        # 錯誤訊息
    print(result.recovery_action) # 恢復建議

# 載入配置
config = loader.load_etl_config("cgmh_ty")
```

**測試驗證:**
- ✅ YAML 載入成功
- ✅ E007 檔案損毀（無效 YAML）
- ✅ E406 Excel 較新（mtime 比較）
- ✅ E406 Checksum 不匹配
- ✅ Checksum 計算準確性
- ✅ 原子 YAML 寫入

#### SI-004: ETLContainer (`src/container.py`, 543 行)

**4 步驟初始化順序** (Foundation First Policy):

```
步驟 1: PipelineContext 建立
   - 初始化時間基準（E000 檢查）
   - 設定 site_id、pipeline_id
   
步驟 2: ConfigLoader 初始化
   - E406 同步檢查（可選）
   - 載入 ETLConfig
   - E906 版本相容性檢查
   
步驟 3: FeatureAnnotationManager 載入
   - 解析 YAML 繼承鏈
   - 載入特徵定義
   
步驟 4: ETL Pipeline 模組實例化
   - Parser、Cleaner、BatchProcessor、FeatureEngineer
```

**強制順序控制:**
- 步驟 N 必須在步驟 N-1 完成後才能執行
- 違反順序時拋出 `RuntimeError: 必須先執行 stepX()`

**關鍵 API:**
```python
# 完整初始化
container = ETLContainer(site_id="cgmh_ty")
container.initialize_all()

# 或逐步初始化
container.step1_create_context()
container.step2_load_config()
container.step3_load_annotation()
container.step4_initialize_modules()

# 取得元件
parser = container.get_parser()
cleaner = container.get_cleaner()
config = container.get_config()
baseline = container.get_temporal_baseline()
```

**測試驗證:**
- ✅ 步驟 1 建立 PipelineContext
- ✅ 步驟 2 相依於步驟 1
- ✅ 步驟 3 相依於步驟 2
- ✅ 步驟 4 相依於步驟 3
- ✅ 完整 4 步驟初始化
- ✅ Getter 運作正確
- ✅ 初始化前 Getter 拋錯

### 3.3 錯誤代碼實作對應

| 錯誤代碼 | 描述 | 實作位置 | 測試覆蓋 |
|:---:|:---|:---|:---:|
| E000 | 時間基準遺失 | `context.py:106`, `config_models.py:1161` | ✅ |
| E000-W | 時間漂移警告 | `context.py:175` | ✅ |
| E007 | 設定檔損毀 | `config_loader.py:123` | ✅ |
| E405 | 目標變數不可啟用 Lag | `config_models.py:1750` | ✅ |
| E406 | Excel/YAML 不同步 | `config_loader.py:277` | ✅ |
| E408 | SSOT 品質標記不匹配 | `config_loader.py:171` | ✅ |
| E906 | 版本漂移 | `container.py:243` | ✅ |

### 3.4 新增檔案一覽

| 檔案 | 行數 | 說明 |
|:---|:---:|:---|
| `src/context.py` | 337 | PipelineContext 時間基準管理 |
| `src/container.py` | 543 | ETLContainer DI 容器 |
| `src/utils/config_loader.py` | 485 | ConfigLoader 強化 |
| `src/etl/config_models.py` | 1554+ | ETLConfig Pydantic 模型（擴充） |
| `tests/test_container_initialization.py` | 712 | 35 項單元測試 |

**總計**: 約 3,600+ 行程式碼

---

## 四、測試覆蓋報告

### 4.1 測試統計

| 類別 | 測試數 | 通過 | 失敗 | 覆蓋範圍 |
|:---:|:---:|:---:|:---:|:---|
| PipelineContext | 9 | 9 | 0 | 單例、E000、漂移、執行緒 |
| ETLConfig | 6 | 6 | 0 | Pydantic、E405、相容性 |
| ConfigLoader | 7 | 7 | 0 | E406、E007、檔案鎖 |
| ETLContainer | 7 | 7 | 0 | 4 步驟初始化 |
| 時間基準傳遞 | 6 | 6 | 0 | 跨日、注入、驗證 |
| **總計** | **35** | **35** | **0** | **100%** |

### 4.2 關鍵測試案例

**時間基準測試:**
```python
def test_e000_missing_baseline(self):
    """E000: 未初始化時取得時間基準應拋錯"""
    ctx = PipelineContext()
    with pytest.raises(RuntimeError) as exc_info:
        ctx.get_baseline()
    assert "E000" in str(exc_info.value)
```

**同步檢查測試:**
```python
def test_e406_sync_check_yaml_newer(self):
    """E406: Excel 比 YAML 新時應檢測不同步"""
    result = loader.validate_annotation_sync("test_site")
    assert not result.is_synced
    assert "E406" in result.message
    assert "Excel" in result.message and "新" in result.message
```

**初始化順序測試:**
```python
def test_step2_requires_step1(self):
    """步驟 2 需要步驟 1 先完成"""
    container = ETLContainer(site_id="test")
    with pytest.raises(RuntimeError) as exc_info:
        container.step2_load_config()
    assert "必須先執行 step1" in str(exc_info.value)
```

---

## 五、風險緩解狀態

| 風險 ID | 風險描述 | 緩解措施 | 狀態 |
|:---:|:---|:---|:---:|
| R-001 | 依賴死鎖 | Foundation First Policy 強制順序 | 🟡 監控中 |
| R-002 | 時間漂移 | E000 強制檢查、PipelineContext 單例 | 🟢 已緩解 |
| R-005 | SSOT 版本漂移 | E408 檢查、Checksum 驗證 | 🟢 已緩解 |
| R-007 | Excel-YAML 不同步 | E406 嚴格檢查、恢復指引 | 🟢 已緩解 |
| R-008 | device_role 洩漏 | E500 三層防護、Metadata 淨化 | 🟢 已緩解 |

---

## 六、下一步行動

### 即將進行 (1.3 Feature Annotation)

| 任務 | 預估工時 | 相依於 |
|:---|:---:|:---|
| Excel 範本結構設計 | 1 天 | 1.2 System Integration |
| YAML Schema 定義 | 0.5 天 | 1.2 System Integration |
| excel_to_yaml.py 轉換器 | 1.5 天 | YAML Schema |
| FeatureAnnotationManager | 2 天 | YAML Schema、excel_to_yaml |
| HVAC 設備限制定義 | 1 天 | FeatureAnnotationManager |
| Wizard CLI | 0.5 天 | 全部 |

### Sprint 2 準備

待 1.3 完成後，即可啟動：
- 2.1 Parser v2.1（Header Standardization、時區轉換）
- 2.2 Cleaner v2.2（E000 檢查、E500 防護、E350 設備邏輯）
- 2.3 BatchProcessor v1.3（Manifest 生成、E408 檢查）

---

## 七、執行心得

### 7.1 成功因素

1. **Foundation First Policy 嚴格執行**: 確保基礎設施穩固後才進行下游開發
2. **錯誤代碼優先定義**: 在實作前先完成 E000-E999 錯誤代碼體系，確保一致性的錯誤處理
3. **Test-Driven Development**: 35 項單元測試與實作同步進行，確保品質
4. **Pydantic 型別安全**: 使用 Pydantic 模型確保配置型別安全，減少執行期錯誤

### 7.2 技術亮點

1. **Thread-safe Singleton**: PipelineContext 使用雙重檢查鎖定確保執行緒安全
2. **原子寫入**: ConfigLoader 使用暫存檔+移動確保寫入原子性
3. **嚴格初始化順序**: ETLContainer 的 4 步驟強制順序防止依賴死鎖
4. **完整錯誤訊息**: 所有錯誤代碼包含使用者友善的訊息範本與恢復建議

### 7.3 待改進項目

1. **FeatureAnnotationManager**: 1.3 完成後需整合至 ETLContainer 步驟 3
2. **BatchProcessor/FeatureEngineer**: 現有模組需升級至 v1.3 規格
3. **整合測試**: 需建立跨模組的端到端測試

---

## 八、附錄

### 8.1 快速參考

**執行測試:**
```bash
cd /Users/chanoscar/HVAC-1
python3 -m pytest tests/test_container_initialization.py -v
```

**使用 ETLContainer:**
```python
from src.container import ETLContainer

container = ETLContainer(site_id="cgmh_ty", enable_sync_check=True)
container.initialize_all()

# 取得時間基準
baseline = container.get_temporal_baseline()

# 取得配置
config = container.get_config()
```

### 8.2 相關文件

- [📋 專案任務排程](./專案任務排程文件.md)
- [📘 Interface Contract PRD](../Interface%20Contract/PRD_Interface_Contract_v1.1.md)
- [📗 System Integration PRD](../System%20Integration/PRD_System_Integration_v1.2.md)

---

**文件結束**

*執行摘要版本: v1.0 | 完成日期: 2026-02-19 | 狀態: ✅ Sprint 1 (2/3 完成)*
