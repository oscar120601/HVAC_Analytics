# PRD v1.0: 設備依賴關係驗證規範 (Equipment Dependency Validation)
# ETL階段物理邏輯一致性檢查與歷史資料驗證

**文件版本:** v1.0 (ETL-Stage Physical Logic Validation)  
**日期:** 2026-02-13  
**負責人:** Oscar Chang  
**目標模組:** `src/etl/equipment_validator.py`, `src/etl/cleaner.py` (擴充), `src/etl/batch_processor.py` (擴充)  
**上游契約:** `src/optimization/constraints.py` (Logic Constraints 定義)  
**下游契約:** `src/etl/feature_engineer.py` (v1.3+, 檢查點 #3)  
**關鍵相依:** 
- `PRD_Chiller_Plant_Optimization_V1.1.md` (邏輯約束定義源頭)
- `PRD_CLEANER_v2.2.md` (SSOT 與職責分離機制)
- `PRD_Interface_Contract_v1.0.md` (錯誤代碼分層 E350-E399)
- `PRD_BATCH_PROCESSOR_v1.3.md` (時間基準與 Manifest 傳遞)

**預估工時:** 4 ~ 5 個工程天（含約束同步機制、歷史資料驗證、整合測試）

---

## 1. 執行總綱與設計哲學

### 1.1 核心目標

建立**ETL階段的設備依賴驗證機制**，將Optimization階段定義的物理邏輯約束（如「開主機必須開水泵」）**反向同步**至資料清洗階段，確保進入模型訓練的歷史資料符合物理現實，避免「主機開但水泵關」等不可能狀態流入下游。

### 1.2 設計原則

1. **約束單一來源 (Single Source of Constraints)**: 
   - 邏輯約束定義維持在 `config/optimization/sites/{site}.yaml` (Optimization v1.1 定義)
   - ETL階段**唯讀**引用，不複製或重複定義約束
   - 透過 `ConstraintSyncManager` 在Container初始化時載入並快取

2. **分層驗證策略**:
   - **Cleaner階段**: 逐行即時驗證（Row-level Validation），標記異常但不中斷流程（因歷史資料可能確實存在違規）
   - **BatchProcessor階段**: 批次統計驗證（Batch-level Validation），計算約束違反率，寫入Manifest供訓練階段參考
   - **嚴格模式**: 可配置為遇到物理不可能狀態時拋出錯誤（用於新案場首次資料導入檢查）

3. **與Optimization零Gap銜接**:
   - 完整支援 Optimization v1.1 定義的5種約束類型：`requires`, `mutex`, `sequence`, `min_runtime`, `min_downtime`
   - 錯誤代碼與Optimization階段連貫（E800系列為Optimization錯誤，E350-E399為ETL階段對應錯誤）

4. **職責分離維護**:
   - 驗證邏輯不寫入 `device_role`（遵循Cleaner v2.2職責分離原則）
   - 僅讀取Optimization Config中的`logic_constraints`區塊，與Feature Annotation的`device_role`區分

### 1.3 與上游模組的關係

```mermaid
graph LR
    A[Optimization Config<br/>sites/{site}.yaml<br/>logic_constraints] -->|ConstraintSyncManager<br/>唯讀載入| B[EquipmentValidator<br/>v1.0]
    C[Feature Annotation<br/>physical_types.yaml] -->|提供設備狀態欄位映射| B
    D[歷史資料<br/>Parser/Cleaner] -->|逐行驗證| B
    B -->|標記PHYSICAL_IMPOSSIBLE| E[Cleaner Output<br/>quality_flags擴充]
    B -->|統計違反率| F[BatchProcessor Manifest<br/>validation_summary]
    
    style B fill:#f9f,stroke:#333,stroke-width:4px
    style A fill:#bbf,stroke:#00f,stroke-width:2px
```

### 1.4 約束類型對應表 (Optimization v1.1 → ETL)

| 約束類型 | Optimization定義 | ETL驗證時機 | ETL錯誤代碼 | 說明 |
|:---|:---|:---:|:---:|:---|
| **requires** | `if: "chiller_1_on" then: ["chw_pump_1_on"]` | Cleaner逐行驗證 | E351 | 主機開但水泵關 |
| **mutex** | `devices: ["chiller_1", "chiller_2"]` | Cleaner逐行驗證 | E352 | 互斥設備同時開啟 |
| **sequence** | `startup: ["ct_1", "pump_1", "chiller_1"]` | BatchProcessor時序分析 | E353 | 開機順序錯誤（歷史資料） |
| **min_runtime** | `device: "chiller_1", minutes: 30` | BatchProcessor時長統計 | E354 | 運行時間不足（異常停機） |
| **min_downtime** | `device: "chiller_1", minutes: 15` | BatchProcessor時長統計 | E355 | 停機時間不足（頻繁啟停） |
| **composite** | 多重約束組合 | Cleaner綜合驗證 | E350 | 複合邏輯違反 |

---

## 2. 介面契約規範 (Interface Contracts)

### 2.1 輸入契約 (Input Contract from Optimization Config)

**檢查點 #9: Optimization Config → EquipmentValidator**

透過 `ConstraintSyncManager` 載入，確保約束定義與Optimization階段完全一致：

```python
class ConstraintSyncManager:
    """
    約束同步管理器：從Optimization Config唯讀載入邏輯約束
    確保ETL與Optimization使用完全相同的約束定義
    """
    
    def load_constraints(self, site_id: str) -> LogicConstraintSet:
        """
        載入流程：
        1. 讀取 config/optimization/sites/{site_id}.yaml
        2. 提取 logic_constraints 區塊
        3. 驗證約束語法（與Optimization使用相同的Pydantic模型）
        4. 建立約束圖（Constraint Graph）供快速查詢
        5. 快取於記憶體（避免重複讀取YAML）
        
        Returns:
            LogicConstraintSet: 包含所有約束的結構化物件
            
        Raises:
            E350: 無法載入約束或語法錯誤
        """
        
    def get_equipment_dependencies(self, equipment_id: str) -> List[str]:
        """
        查詢設備依賴（requires約束）
        例如：get_equipment_dependencies("chiller_1") -> ["chw_pump_1", "ct_1"]
        """
        
    def get_mutex_groups(self) -> List[Set[str]]:
        """
        取得所有互斥設備組（mutex約束）
        """
        
    def validate_constraint_consistency(self) -> bool:
        """
        驗證約束一致性（避免矛盾約束，如A依賴B但B與A互斥）
        在Container初始化時執行
        """
```

**載入規格**:

| 檢查項 | 規格 | 錯誤代碼 | 處理 |
|:---|:---|:---:|:---|
| **Config存在性** | `config/optimization/sites/{site}.yaml` 必須存在 | E350 | 拒絕載入，提示建立Optimization配置 |
| **Constraints區塊** | 必須包含 `logic_constraints` 欄位（可為空列表） | E350-Warn | 警告無約束，視為自由運行模式 |
| **語法驗證** | 必須符合Optimization v1.1的Pydantic模型 | E350 | 拒絕載入，提示語法錯誤 |
| **設備ID一致性** | 約束中的設備ID必須存在於Feature Annotation | E351-Warn | 警告未定義設備，可能為配置錯誤 |

### 2.2 輸出契約 (Output Contract to Cleaner/BatchProcessor)

**Cleaner階段輸出 (Row-level Flags)**:

擴充 `VALID_QUALITY_FLAGS` (Interface Contract v1.0定義)，新增ETL階段設備依賴錯誤標記：

```python
# src/etl/config_models.py (SSOT擴充)
VALID_QUALITY_FLAGS: Final[List[str]] = [
    # 原有標記 (v2.2)
    "FROZEN",           # 凍結資料
    "OUTLIER",          # 離群值
    "PHYSICAL_IMPOSSIBLE",  # 物理不可能（擴充含義）
    "INSUFFICIENT_DATA",    # 資料不足
    "MANUAL_REVIEW",        # 需人工複查
    "INTERPOLATED",         # 插值補點
    
    # 新增設備依賴標記 (v1.0)
    "LOGIC_CONSTRAINT_VIOLATION",  # 邏輯約束違反（通用）
    "REQUIRES_VIOLATION",          # 依賴缺失（如主機開水泵關）
    "MUTEX_VIOLATION",             # 互斥違反
    "SEQUENCE_VIOLATION",          # 順序違反
    "MIN_RUNTIME_VIOLATION",       # 運行時間不足
    "MIN_DOWNTIME_VIOLATION",      # 停機時間不足
]
```

**BatchProcessor階段輸出 (Manifest擴充)**:

在 `Manifest.validation_summary` 中新增設備依賴統計：

```python
class Manifest(BaseModel):
    # ... 原有欄位 ...
    
    # 新增設備依賴驗證摘要 (Equipment Dependency Validation Summary)
    equipment_validation_summary: Dict = {
        "constraint_set_version": "1.0",  # 約束集版本（YAML checksum）
        "validation_timestamp": "2026-02-13T10:00:00Z",
        "row_level_stats": {
            "total_rows_checked": 10000,
            "logic_violation_rows": 150,      # 含任一邏輯違反的列數
            "violation_rate_percent": 1.5
        },
        "constraint_breakdown": {
            "requires_violations": 120,       # E351統計
            "mutex_violations": 20,           # E352統計  
            "sequence_violations": 5,         # E353統計
            "min_runtime_violations": 3,      # E354統計
            "min_downtime_violations": 2      # E355統計
        },
        "equipment_specific_stats": {
            "chiller_1": {
                "requires_violations_with": ["chw_pump_1"],  # 具體違反對象
                "violation_timestamps": ["2026-01-15T08:30:00Z", "..."]  # 取樣
            }
        },
        "severity_assessment": "HIGH",  # HIGH(>5%)/MEDIUM(1-5%)/LOW(<1%)
        "recommendation": "建議檢查chiller_1與chw_pump_1的感測器同步性"
    }
```

### 2.3 與Optimization的對齊契約

| Optimization約束 | ETL驗證輸出 | 對齊檢查點 |
|:---|:---|:---:|
| `requires: chiller_1_on → chw_pump_1_on` | 標記 `REQUIRES_VIOLATION` 並記錄設備對 | #9 |
| `mutex: [chiller_1, chiller_2]` | 標記 `MUTEX_VIOLATION` 並記錄衝突設備 | #9 |
| `sequence: startup [ct_1, pump_1, chiller_1]` | 標記 `SEQUENCE_VIOLATION`（歷史時序分析） | #9 |
| `min_runtime: chiller_1, 30min` | 標記 `MIN_RUNTIME_VIOLATION`（異常短運行） | #9 |
| `min_downtime: chiller_1, 15min` | 標記 `MIN_DOWNTIME_VIOLATION`（異常短停機） | #9 |

**關鍵保證**: 
- ETL階段標記為 `PHYSICAL_IMPOSSIBLE` 的資料，在Optimization階段**必然**會被視為約束違反（Consistency Guarantee）
- ETL標記率與Optimization約束違反率的統計差異不得超過0.1%（Tolerance）

---

## 3. 系統架構與核心模組

### 3.1 約束同步管理器 (ConstraintSyncManager)

**檔案**: `src/validation/constraint_sync.py`

**職責**: 作為Optimization與ETL之間的橋樑，確保兩端使用完全相同的約束定義

```python
class ConstraintSyncManager:
    """
    約束同步管理器（單例模式）
    在Container初始化時載入，供Cleaner與BatchProcessor共用
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._constraints_cache = {}
        return cls._instance
    
    def initialize_for_site(self, site_id: str):
        """
        為特定案場初始化約束快取
        必須在Container.__init__中呼叫（早於Cleaner初始化）
        """
        config_path = Path(f"config/optimization/sites/{site_id}.yaml")
        
        if not config_path.exists():
            raise ConfigurationError(
                f"E350: Optimization配置不存在: {config_path}。 "
                f"請先建立設備依賴約束配置（PRD_Optimization_v1.1）"
            )
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        constraints = config.get('logic_constraints', [])
        
        # 驗證約束語法（使用與Optimization相同的Pydantic模型）
        try:
            self._constraints_cache[site_id] = LogicConstraintSet(constraints=constraints)
        except ValidationError as e:
            raise ConfigurationError(f"E350: 約束語法錯誤: {e}")
        
        self.logger.info(f"案場 {site_id}: 載入 {len(constraints)} 條邏輯約束")
    
    def get_constraints(self, site_id: str) -> LogicConstraintSet:
        """取得指定案場的約束集"""
        if site_id not in self._constraints_cache:
            raise RuntimeError(f"E350: 案場 {site_id} 的約束未初始化")
        return self._constraints_cache[site_id]
```

### 3.2 設備狀態解析器 (EquipmentStateResolver)

**檔案**: `src/validation/equipment_state.py`

**職責**: 將原始感測器數值轉換為設備狀態（開/關/未知），處理不同設備類型的判斷邏輯

```python
class EquipmentStateResolver:
    """
    設備狀態解析器
    根據Feature Annotation的physical_type決定狀態判斷邏輯
    """
    
    # 設備狀態閾值配置（可從Optimization Config覆寫）
    DEFAULT_THRESHOLDS = {
        "chiller": {"on_threshold_kw": 10.0, "off_threshold_kw": 2.0},  # 主機用電判斷
        "pump": {"on_threshold_hz": 35.0, "off_threshold_hz": 5.0},     # 水泵頻率判斷
        "cooling_tower": {"on_threshold_percent": 20.0},                 # 冷卻塔轉速判斷
        "valve": {"on_threshold_percent": 10.0}                          # 閥門開度判斷
    }
    
    def __init__(self, annotation_manager: FeatureAnnotationManager, 
                 custom_thresholds: Optional[Dict] = None):
        self.annotation = annotation_manager
        self.thresholds = {**self.DEFAULT_THRESHOLDS, **(custom_thresholds or {})}
    
    def resolve_state(self, equipment_id: str, row: Dict[str, Any]) -> EquipmentState:
        """
        解析設備在單一時間點的狀態
        
        Returns:
            EquipmentState: Enum [ON, OFF, UNKNOWN, TRANSITION]
        """
        # 1. 取得設備對應的感測器欄位（從Annotation查詢）
        sensor_col = self._get_sensor_column(equipment_id)
        
        if sensor_col not in row or row[sensor_col] is None:
            return EquipmentState.UNKNOWN
        
        value = row[sensor_col]
        physical_type = self.annotation.get_physical_type(equipment_id)
        
        # 2. 根據physical_type選擇判斷邏輯
        thresholds = self.thresholds.get(physical_type, {})
        
        if physical_type in ["chiller", "power_meter"]:
            # 用電設備：用kW判斷
            if value > thresholds.get("on_threshold_kw", 10.0):
                return EquipmentState.ON
            elif value < thresholds.get("off_threshold_kw", 2.0):
                return EquipmentState.OFF
            else:
                return EquipmentState.TRANSITION  # 過渡狀態（不穩定）
                
        elif physical_type in ["pump", "fan"]:
            # 轉速設備：用Hz或%判斷
            if value > thresholds.get("on_threshold_hz", 35.0):
                return EquipmentState.ON
            elif value < thresholds.get("off_threshold_hz", 5.0):
                return EquipmentState.OFF
            else:
                return EquipmentState.TRANSITION
        
        # ... 其他設備類型
        
        return EquipmentState.UNKNOWN
    
    def _get_sensor_column(self, equipment_id: str) -> str:
        """
        從Feature Annotation查詢設備對應的感測器欄位名稱
        例如：chiller_1 -> chiller_1_kw 或 chiller_1_status
        """
        # 優先尋找狀態欄位（_status後綴），其次尋找主要感測器（_kw, _hz等）
        col_config = self.annotation.get_column_config(equipment_id)
        # 實作細節依Annotation schema決定
        return f"{equipment_id}_kw"  # 簡化示例
```

### 3.3 約束驗證引擎 (ConstraintValidationEngine)

**檔案**: `src/validation/constraint_engine.py`

**職責**: 執行實際的約束驗證邏輯，支援逐行與批次兩種模式

```python
class ConstraintValidationEngine:
    """
    約束驗證引擎
    執行Optimization定義的5種約束類型驗證
    """
    
    def __init__(self, constraint_set: LogicConstraintSet, 
                 state_resolver: EquipmentStateResolver):
        self.constraints = constraint_set
        self.state_resolver = state_resolver
        self.violation_history = []  # 記錄違反事件供統計
    
    def validate_row(self, row: Dict[str, Any], timestamp: datetime) -> List[ConstraintViolation]:
        """
        逐行驗證（Cleaner階段使用）
        
        Returns:
            List[ConstraintViolation]: 該行違反的所有約束
        """
        violations = []
        
        for constraint in self.constraints:
            if constraint.type == "requires":
                if self._check_requires_violation(constraint, row):
                    violations.append(ConstraintViolation(
                        constraint_type="requires",
                        constraint_id=constraint.id,
                        equipment=constraint.if_device,
                        missing_dependencies=constraint.then_devices,
                        timestamp=timestamp,
                        error_code="E351"
                    ))
            
            elif constraint.type == "mutex":
                if self._check_mutex_violation(constraint, row):
                    violations.append(ConstraintViolation(
                        constraint_type="mutex",
                        constraint_id=constraint.id,
                        conflicting_devices=constraint.devices,
                        timestamp=timestamp,
                        error_code="E352"
                    ))
            
            # sequence, min_runtime, min_downtime在批次階段處理
        
        return violations
    
    def validate_batch(self, df: pl.DataFrame) -> BatchValidationReport:
        """
        批次驗證（BatchProcessor階段使用）
        處理需要時序分析的約束（sequence, min_runtime, min_downtime）
        """
        report = BatchValidationReport()
        
        # 1. Sequence驗證（開關機順序）
        for constraint in self.constraints.get_by_type("sequence"):
            violations = self._analyze_sequence_batch(df, constraint)
            report.add_sequence_violations(violations)
        
        # 2. Min Runtime驗證（最小運行時間）
        for constraint in self.constraints.get_by_type("min_runtime"):
            violations = self._analyze_runtime_batch(df, constraint, "runtime")
            report.add_runtime_violations(violations)
        
        # 3. Min Downtime驗證（最小停機時間）
        for constraint in self.constraints.get_by_type("min_downtime"):
            violations = self._analyze_runtime_batch(df, constraint, "downtime")
            report.add_downtime_violations(violations)
        
        return report
    
    def _check_requires_violation(self, constraint: RequiresConstraint, 
                                   row: Dict) -> bool:
        """
        檢查requires約束違反
        
        邏輯：若if_device為ON，但任一then_device為OFF，則違反
        """
        if_state = self.state_resolver.resolve_state(constraint.if_device, row)
        
        if if_state != EquipmentState.ON:
            return False  # 前提條件不成立，不檢查
        
        for dep_device in constraint.then_devices:
            dep_state = self.state_resolver.resolve_state(dep_device, row)
            if dep_state == EquipmentState.OFF:
                return True  # 發現依賴缺失
        
        return False
    
    def _check_mutex_violation(self, constraint: MutexConstraint, 
                                row: Dict) -> bool:
        """
        檢查mutex約束違反
        
        邏輯：若互斥組中同時有超過1個設備為ON，則違反
        """
        on_count = 0
        for device in constraint.devices:
            state = self.state_resolver.resolve_state(device, row)
            if state == EquipmentState.ON:
                on_count += 1
                if on_count > 1:
                    return True
        
        return False
    
    def _analyze_sequence_batch(self, df: pl.DataFrame, 
                                constraint: SequenceConstraint) -> List[Violation]:
        """
        批次分析開關機順序
        
        邏輯：檢查startup順序是否被遵守（後者先開為違反）
        注意：歷史資料通常無法改變，此驗證主要用於標記異常時段
        """
        violations = []
        startup_order = constraint.startup  # e.g., ["ct_1", "pump_1", "chiller_1"]
        
        # 轉換狀態時間序列
        state_df = self._convert_to_state_series(df, startup_order)
        
        # 檢查狀態轉換點
        for i in range(1, len(startup_order)):
            primary = startup_order[i]      # 後開設備
            prerequisite = startup_order[i-1]  # 先開設備
            
            # 尋找primary的開機時間點
            primary_starts = state_df.filter(
                (pl.col(primary) == "ON") & 
                (pl.col(primary).shift(1) != "ON")
            )["timestamp"]
            
            for start_time in primary_starts:
                # 檢查此時prerequisite是否已開
                prereq_state_at_start = state_df.filter(
                    pl.col("timestamp") <= start_time
                ).tail(1)[prerequisite][0]
                
                if prereq_state_at_start != "ON":
                    violations.append(ConstraintViolation(...))
        
        return violations
    
    def _analyze_runtime_batch(self, df: pl.DataFrame, 
                               constraint: RuntimeConstraint,
                               mode: str) -> List[Violation]:
        """
        分析運行/停機時間是否滿足最小時長要求
        
        適用於min_runtime（運行時間）與min_downtime（停機時間）
        """
        device = constraint.device
        min_minutes = constraint.minutes
        
        # 計算狀態持續時間
        state_series = self._convert_to_state_series(df, [device])
        
        # 使用Polars計算狀態段（State Segments）
        segments = self._detect_state_segments(state_series, device)
        
        violations = []
        for segment in segments:
            duration_minutes = (segment.end_time - segment.start_time).total_seconds() / 60
            
            if mode == "runtime" and segment.state == "ON" and duration_minutes < min_minutes:
                violations.append(ConstraintViolation(
                    type="min_runtime",
                    device=device,
                    actual_minutes=duration_minutes,
                    required_minutes=min_minutes,
                    timestamp=segment.start_time
                ))
            
            elif mode == "downtime" and segment.state == "OFF" and duration_minutes < min_minutes:
                violations.append(ConstraintViolation(
                    type="min_downtime",
                    device=device,
                    actual_minutes=duration_minutes,
                    required_minutes=min_minutes,
                    timestamp=segment.start_time
                ))
        
        return violations
```

---

## 4. 分階段實作計畫 (Phase-Based Implementation)

### Phase 0: 約束同步基礎建設 (Day 1)

**Step 0.1: ConstraintSyncManager實作**

```python
# src/validation/constraint_sync.py

class LogicConstraintSet(BaseModel):
    """約束集資料模型（與Optimization v1.1共享）"""
    constraints: List[Union[
        RequiresConstraint,
        MutexConstraint, 
        SequenceConstraint,
        RuntimeConstraint
    ]]
    
    def get_by_type(self, type_name: str) -> List:
        return [c for c in self.constraints if c.type == type_name]

class ConstraintSyncManager:
    # ... （見3.1節）...
    pass
```

**驗收標準**:
- [ ] 成功載入 `cgmh_ty.yaml` 的logic_constraints
- [ ] 語法錯誤時拋出E350並提供明確錯誤位置
- [ ] 與Optimization使用相同的Pydantic模型（無轉換誤差）

**Step 0.2: EquipmentStateResolver實作**

```python
# src/validation/equipment_state.py

class EquipmentState(Enum):
    ON = "on"
    OFF = "off"
    UNKNOWN = "unknown"
    TRANSITION = "transition"  # 過渡狀態（閾值區間內）

class EquipmentStateResolver:
    # ... （見3.2節）...
    
    def validate_thresholds_config(self) -> bool:
        """驗證閾值配置合理性（避免on_threshold < off_threshold）"""
        for eq_type, thresholds in self.thresholds.items():
            if "on_threshold_kw" in thresholds and "off_threshold_kw" in thresholds:
                if thresholds["on_threshold_kw"] <= thresholds["off_threshold_kw"]:
                    raise ConfigurationError(
                        f"設備類型 {eq_type} 的on_threshold必須大於off_threshold"
                    )
        return True
```

**驗收標準**:
- [ ] 正確解析chiller狀態（用電>10kW為ON，<2kW為OFF）
- [ ] 正確解析pump狀態（頻率>35Hz為ON，<5kW為OFF）
- [ ] 數值為Null時返回UNKNOWN

### Phase 1: Cleaner整合與逐行驗證 (Day 2)

**Step 1.1: Cleaner擴充（整合EquipmentValidator）**

修改 `src/etl/cleaner.py` (v2.2+):

```python
class DataCleaner:
    def __init__(self, config: CleanerConfig, 
                 annotation_manager: FeatureAnnotationManager,
                 constraint_manager: Optional[ConstraintSyncManager] = None):  # 新增
        # ... 原有初始化 ...
        self.constraint_manager = constraint_manager
        self.equipment_validator = None
        
        if constraint_manager:
            self.equipment_validator = ConstraintValidationEngine(
                constraint_set=constraint_manager.get_constraints(config.site_id),
                state_resolver=EquipmentStateResolver(annotation_manager)
            )
    
    def _semantic_aware_cleaning(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        擴充v2.2的語意感知清洗，加入設備依賴驗證
        """
        # ... 原有邏輯（凍結檢測、零值檢查）...
        
        # 新增：設備依賴驗證（逐行）
        if self.equipment_validator:
            df = self._validate_equipment_dependencies(df)
        
        return df
    
    def _validate_equipment_dependencies(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        逐行驗證設備依賴關係（requires, mutex）
        將違反標記為quality_flags
        """
        violations_list = []
        
        for row_idx in range(len(df)):
            row = df[row_idx].to_dict()
            timestamp = row["timestamp"]
            
            # 執行驗證
            violations = self.equipment_validator.validate_row(row, timestamp)
            
            if violations:
                # 收集所有違反的flags
                flags_to_add = [v.error_code.replace("E", "FLAG_") for v in violations]
                flags_to_add.append("LOGIC_CONSTRAINT_VIOLATION")
                
                # 標記該行（使用Polars的with_row_count輔助）
                violations_list.append((row_idx, flags_to_add))
        
        # 批量更新quality_flags（避免逐行更新效能問題）
        if violations_list:
            df = self._apply_violation_flags(df, violations_list)
            
            # 記錄統計
            self.logger.warning(
                f"設備依賴驗證：發現 {len(violations_list)} 行違反，"
                f"類型分布: {self._summarize_violations(violations)}"
            )
        
        return df
    
    def _apply_violation_flags(self, df: pl.DataFrame, 
                                violations: List[Tuple[int, List[str]]]) -> pl.DataFrame:
        """
        將違反標記應用到DataFrame（使用Polars高效操作）
        """
        # 建立flags列的更新映射
        flag_updates = {}
        for row_idx, flags in violations:
            for flag in flags:
                if flag not in flag_updates:
                    flag_updates[flag] = []
                flag_updates[flag].append(row_idx)
        
        # 使用Polars的when-then鏈更新（或先轉為Pandas處理後轉回，取決於效能）
        # 這裡簡化展示邏輯，實作時應使用Polars原生語法
        for flag, rows in flag_updates.items():
            mask = pl.Series([i in rows for i in range(len(df))])
            df = df.with_columns(
                pl.when(mask).then(
                    pl.col("quality_flags").list.concat(pl.lit([flag]))
                ).otherwise(pl.col("quality_flags")).alias("quality_flags")
            )
        
        return df
```

**驗收標準**:
- [ ] requires約束違反正確標記（E351 → FLAG_REQUIRES_VIOLATION）
- [ ] mutex約束違反正確標記（E352 → FLAG_MUTEX_VIOLATION）
- [ ] 效能：處理10萬行資料耗時<5秒（使用Polars向量化操作）

### Phase 2: BatchProcessor整合與批次驗證 (Day 3)

**Step 2.1: BatchProcessor擴充（時序約束驗證）**

修改 `src/etl/batch_processor.py` (v1.3+):

```python
class BatchOrchestrator:
    def __init__(self, ...):
        # ... 原有初始化 ...
        self.equipment_validator = ConstraintValidationEngine(
            constraint_set=constraint_manager.get_constraints(config.site_id),
            state_resolver=EquipmentStateResolver(annotation_manager)
        )
    
    def process_single_file(self, file_path: Path) -> BatchResult:
        # ... 原有流程（解析、清洗）...
        
        # 新增：批次設備依賴驗證（時序相關）
        validation_report = self.equipment_validator.validate_batch(clean_df)
        
        # 將驗證報告寫入Manifest
        manifest = self._generate_manifest(
            clean_df,
            column_metadata=column_metadata,
            validation_report=validation_report  # 新增參數
        )
        
        return BatchResult(
            # ... 原有欄位 ...
            validation_summary=validation_report.to_dict()  # 新增
        )
    
    def _generate_manifest(self, df, column_metadata, validation_report, ...):
        # ... 原有Manifest生成邏輯 ...
        
        # 新增equipment_validation_summary
        manifest.equipment_validation_summary = {
            "constraint_set_version": self._get_constraint_checksum(),
            "validation_timestamp": datetime.now(timezone.utc).isoformat(),
            "row_level_stats": {
                "total_rows_checked": len(df),
                "logic_violation_rows": validation_report.total_violations,
                "violation_rate_percent": round(
                    validation_report.total_violations / len(df) * 100, 2
                )
            },
            "constraint_breakdown": {
                "requires_violations": len(validation_report.requires_violations),
                "mutex_violations": len(validation_report.mutex_violations),
                "sequence_violations": len(validation_report.sequence_violations),
                "min_runtime_violations": len(validation_report.runtime_violations),
                "min_downtime_violations": len(validation_report.downtime_violations)
            },
            "equipment_specific_stats": validation_report.get_equipment_stats(),
            "severity_assessment": validation_report.assess_severity(),
            "recommendation": validation_report.generate_recommendation()
        }
        
        return manifest
```

**驗收標準**:
- [ ] sequence約束正確檢測（開機順序錯誤時段）
- [ ] min_runtime正確計算（運行<30分鐘的異常短運行）
- [ ] min_downtime正確計算（停機<15分鐘的頻繁啟停）
- [ ] Manifest正確寫入validation_summary

### Phase 3: 錯誤代碼與日誌整合 (Day 4)

**Step 3.1: 錯誤代碼實作（E350-E399）**

擴充 `src/etl/config_models.py`:

```python
# 設備依賴驗證錯誤代碼（Interface Contract v1.0定義E350-E399區間）
EQUIPMENT_DEPENDENCY_ERROR_CODES = {
    "E350": {
        "name": "CONSTRAINT_CONFIG_ERROR",
        "description": "無法載入Optimization約束配置或語法錯誤",
        "stage": "Container初始化",
        "severity": "Critical"
    },
    "E351": {
        "name": "REQUIRES_VIOLATION",
        "description": "設備依賴約束違反（如主機開但水泵關）",
        "stage": "Cleaner逐行驗證",
        "severity": "High",
        "example": "chiller_1_on=True but chw_pump_1_on=False"
    },
    "E352": {
        "name": "MUTEX_VIOLATION", 
        "description": "互斥設備同時開啟",
        "stage": "Cleaner逐行驗證",
        "severity": "High",
        "example": "chiller_1_on=True and chiller_2_on=True (mutex group)"
    },
    "E353": {
        "name": "SEQUENCE_VIOLATION",
        "description": "開關機順序違反（歷史資料時序分析）",
        "stage": "BatchProcessor批次驗證",
        "severity": "Medium",
        "example": "chiller_1 started before ct_1"
    },
    "E354": {
        "name": "MIN_RUNTIME_VIOLATION",
        "description": "設備運行時間低於最小要求（異常短運行）",
        "stage": "BatchProcessor時長統計",
        "severity": "Medium",
        "example": "chiller_1 runtime=15min, required=30min"
    },
    "E355": {
        "name": "MIN_DOWNTIME_VIOLATION",
        "description": "設備停機時間低於最小要求（頻繁啟停）",
        "stage": "BatchProcessor時長統計", 
        "severity": "Medium",
        "example": "chiller_1 downtime=5min, required=15min"
    },
    "E356": {
        "name": "EQUIPMENT_STATE_AMBIGUOUS",
        "description": "設備狀態無法判定（數值在閾值過渡區間）",
        "stage": "Cleaner狀態解析",
        "severity": "Low",
        "example": "chiller_1_kw=5.0 (between off=2 and on=10)"
    },
    "E357": {
        "name": "CONSTRAINT_VALIDATION_FAILED",
        "description": "批次驗證執行失敗（內部錯誤）",
        "stage": "BatchProcessor",
        "severity": "High"
    }
}
```

**Step 3.2: 日誌與監控告警**

```python
# 在ConstraintValidationEngine中整合

class ConstraintValidationEngine:
    def log_violation(self, violation: ConstraintViolation):
        """
        結構化日誌記錄，供ELK/Plumbr等系統收集
        """
        log_entry = {
            "timestamp": violation.timestamp.isoformat(),
            "error_code": violation.error_code,
            "constraint_type": violation.constraint_type,
            "equipment_id": getattr(violation, 'equipment', None),
            "details": violation.to_dict(),
            "severity": EQUIPMENT_DEPENDENCY_ERROR_CODES[violation.error_code]["severity"]
        }
        
        self.logger.warning(f"設備依賴違反: {log_entry}")
        
        # 高嚴重度即時告警（可整合PagerDuty/Slack）
        if log_entry["severity"] == "High":
            self._send_alert(log_entry)
```

---

## 5. 測試與驗證計畫 (Test Plan)

### 5.1 單元測試 (Unit Tests)

**檔案**: `tests/test_equipment_dependency.py`

| 測試案例 ID | 描述 | 輸入 | 預期結果 | 對應錯誤碼 |
|:---|:---|:---|:---|:---:|
| ED-001 | Requires約束通過 | chiller_1_on=True, chw_pump_1_on=True | 無違反 | - |
| ED-002 | Requires約束違反 | chiller_1_on=True, chw_pump_1_on=False | 標記E351 | E351 |
| ED-003 | Mutex約束通過 | chiller_1_on=True, chiller_2_on=False | 無違反 | - |
| ED-004 | Mutex約束違反 | chiller_1_on=True, chiller_2_on=True | 標記E352 | E352 |
| ED-005 | Sequence約束檢測 | ct_1啟動時間 > chiller_1啟動時間 | 標記E353 | E353 |
| ED-006 | Min Runtime檢測 | chiller_1運行20分鐘（要求30分鐘） | 標記E354 | E354 |
| ED-007 | Min Downtime檢測 | chiller_1停機10分鐘（要求15分鐘） | 標記E355 | E355 |
| ED-008 | 狀態過渡區間 | chiller_1_kw=5.0（閾值2-10之間） | 標記TRANSITION | E356-Warn |
| ED-009 | 配置載入失敗 | 缺少optimization config | 拋出E350 | E350 |
| ED-010 | 閾值配置錯誤 | on_threshold < off_threshold | 拋出ConfigError | - |

### 5.2 整合測試 (Integration Tests)

**檔案**: `tests/test_equipment_dependency_integration.py`

| 測試案例 ID | 描述 | 上游 | 下游 | 驗證目標 |
|:---|:---|:---:|:---:|:---|
| INT-ED-01 | Optimization→ETL約束同步 | Optimization Config v1.1 | EquipmentValidator v1.0 | 兩端約束定義一致，無轉換誤差 |
| INT-ED-02 | Cleaner標記傳遞 | EquipmentValidator | Cleaner v2.2 | quality_flags正確包含REQUIRES_VIOLATION |
| INT-ED-03 | Manifest統計寫入 | BatchProcessor v1.3 | Feature Engineer v1.3 | Manifest包含equipment_validation_summary |
| INT-ED-04 | 長時間執行穩定性 | 1年歷史資料（百萬行） | BatchProcessor | 記憶體使用<4GB，執行時間<2分鐘 |
| INT-ED-05 | 與Optimization交叉驗證 | 同一份CSV | Optimization v1.1 + ETL v1.0 | 兩端標記的違反率差異<0.1% |

### 5.3 驗收測試 (Acceptance Tests)

**場景1：長庚醫院案場實料驗證**
- 輸入：cgmh_ty_202501.csv（含已知的chiller_1與chw_pump_1同步問題時段）
- 預期：正確標記2025-01-15 08:30-09:15的REQUIRES_VIOLATION（該時段主機開但水泵關）

**場景2：頻繁啟停檢測**
- 輸入：模擬chiller_1在1小時內開關3次的資料
- 預期：標記2次MIN_DOWNTIME_VIOLATION（停機時間不足15分鐘）

---

## 6. 風險評估與緩解 (Risk Assessment)

| 風險 | 嚴重度 | 可能性 | 緩解措施 | 狀態 |
|:---|:---:|:---:|:---|:---:|
| **閾值設定錯誤**（設備狀態誤判） | 🔴 High | Medium | 閾值配置與Optimization共用；提供Validation Tool供工程師確認狀態判讀正確性 | 已規劃 |
| **歷史資料雜訊**（感測器誤差導致狀態閃爍） | 🟡 Medium | High | 引入TRANSITION狀態（閾值區間內不判定）；支援資料平滑前處理 | 已規劃 |
| **約束定義漂移**（Optimization更新但ETL未同步） | 🔴 High | Medium | Container初始化時強制驗證Config checksum；版本不匹配時拋出E350 | 已規劃 |
| **效能瓶頸**（百萬行資料處理過慢） | 🟡 Medium | Medium | 使用Polars向量化操作；狀態解析快取；支援分批處理 | 已驗證 |
| **與Feature Engineer職責重疊**（FE也做類似驗證） | 🟢 Low | Low | 明確區分：ETL驗證歷史資料物理可能性，FE驗證特徵工程邏輯；文件標註 | 已說明 |

---

## 7. 版本相容性矩陣 (Version Compatibility)

| Optimization | EquipmentValidator | Cleaner | BatchProcessor | 相容性 | 說明 |
|:---:|:---:|:---:|:---:|:---:|:---|
| v1.1 | **v1.0** | v2.2+ | v1.3+ | ✅ **完全相容** | 推薦配置，約束同步完整 |
| v1.1 | **v1.0** | v2.1 | v1.3+ | ⚠️ **部分相容** | Cleaner v2.1無SSOT Flags擴充，需降級處理 |
| v1.0 | **v1.0** | 任意 | 任意 | ❌ **不相容** | Optimization v1.0缺少min_runtime/min_downtime定義 |
| v1.1 | **v1.0** | v2.2+ | v1.2 | ⚠️ **部分相容** | BatchProcessor v1.2無Manifest擴充欄位，統計資訊遺失 |

---

## 8. 交付物清單 (Deliverables)

### 8.1 程式碼檔案
1. `src/validation/constraint_sync.py` - ConstraintSyncManager實作
2. `src/validation/equipment_state.py` - EquipmentStateResolver實作  
3. `src/validation/constraint_engine.py` - ConstraintValidationEngine實作
4. `src/validation/models.py` - 約束資料模型（與Optimization共用）
5. `src/etl/cleaner.py` (更新) - 整合設備依賴驗證（逐行）
6. `src/etl/batch_processor.py` (更新) - 整合批次驗證與Manifest輸出

### 8.2 配置文件
7. `config/validation/equipment_thresholds.yaml` - 設備狀態閾值預設值（可依案場覆寫）

### 8.3 測試檔案
8. `tests/test_equipment_dependency.py` - 單元測試（覆蓋E350-E356）
9. `tests/test_equipment_dependency_integration.py` - 整合測試（含效能測試）
10. `tests/fixtures/sample_constraints.yaml` - 測試用約束配置

### 8.4 文件檔案
11. `docs/validation/PRD_Equipment_Dependency_Validation_v1.0.md` - 本文件
12. `docs/validation/CONSTRAINT_SYNC_GUIDE.md` - 約束同步操作手冊（供維運人員）
13. `docs/validation/TROUBLESHOOTING.md` - 常見錯誤排查（E351-E356處理指引）

---

## 9. 驗收簽核 (Sign-off Checklist)

### 9.1 功能驗收
- [ ] **E350驗證**：缺少Optimization Config時正確拋出E350並指引建立配置
- [ ] **E351驗證**：chiller_1_on=True但chw_pump_1_on=False時正確標記REQUIRES_VIOLATION
- [ ] **E352驗證**：互斥設備同時開啟時正確標記MUTEX_VIOLATION  
- [ ] **E353驗證**：開機順序違反（如先開主機後開冷卻塔）正確標記SEQUENCE_VIOLATION
- [ ] **E354驗證**：運行時間<30分鐘正確標記MIN_RUNTIME_VIOLATION
- [ ] **E355驗證**：停機時間<15分鐘正確標記MIN_DOWNTIME_VIOLATION
- [ ] **Manifest輸出**：BatchProcessor輸出的Manifest包含完整的equipment_validation_summary
- [ ] **閾值配置**：可從Optimization Config讀取自定義閾值（覆寫預設值）

### 9.2 整合驗收
- [ ] **Optimization一致性**：與Optimization v1.1使用相同的Pydantic約束模型
- [ ] **Cleaner整合**：逐行驗證不影響原有v2.2功能（職責分離維持）
- [ ] **BatchProcessor整合**：批次驗證不影響原有v1.3功能（Manifest格式擴充）
- [ ] **錯誤代碼**：所有錯誤代碼符合Interface Contract v1.0的E350-E399分層
- [ ] **效能**：10萬行資料處理時間<5秒，記憶體使用<2GB

### 9.3 文件驗收
- [ ] 維運手冊包含E351-E356的處理指引（SOP）
- [ ] 包含與Optimization v1.1的對照表（確認無Gap）
- [ ] 包含閾值調整指南（供現場工程師校正設備狀態判斷）

---

## 10. 附錄：與Optimization v1.1約束對照

| Optimization欄位 | EquipmentValidator對應 | 備註 |
|:---|:---|:---|
| `logic_constraints[].type` | 驗證方法分派 | requires/mutex/sequence/min_runtime/min_downtime |
| `logic_constraints[].if` | `RequiresConstraint.if_device` | 觸發條件設備 |
| `logic_constraints[].then` | `RequiresConstraint.then_devices` | 依賴設備列表 |
| `logic_constraints[].devices` | `MutexConstraint.devices` | 互斥設備組 |
| `logic_constraints[].startup` | `SequenceConstraint.startup` | 開機順序列表 |
| `logic_constraints[].minutes` | `RuntimeConstraint.minutes` | 最小時間（分鐘） |
| `equipment[].min_load_percent` | `EquipmentStateResolver.thresholds` | 設備狀態閾值來源 |

---

**關鍵設計確認**:
1. **零Gap保證**：ETL階段標記的`PHYSICAL_IMPOSSIBLE`與Optimization階段的約束違反定義完全一致
2. **SSOT維護**：約束定義唯一位於Optimization Config，ETL唯讀引用，不複製
3. **職責分離**：EquipmentValidator不處理`device_role`（這是Feature Annotation的職責），僅處理`logic_constraints`
4. **向量化效能**：使用Polars進行批次處理，避免Python迴圈效能瓶頸
5. **可追溯性**：所有約束違反記錄時間戳、設備ID、違反類型，寫入Manifest供訓練階段參考
```