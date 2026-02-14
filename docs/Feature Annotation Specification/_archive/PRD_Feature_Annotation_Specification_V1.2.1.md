以下是基于 **PRD_Feature_Annotation_Specification_V1.2** 的完整更新文档，专门针对您的 HVAC 系统设备与测点规格进行扩充：

---

```markdown
# PRD v1.2.1-HVAC: 特徵標註系統規範 (HVAC 擴充版)
# 設備分類、物理類型擴充與冰水主機房專用約束

**文件版本:** v1.2.1-HVAC (Extension for Chiller Plant & AHU Systems)  
**基礎版本:** v1.2-Contract-Aligned  
**日期:** 2026-02-14  
**負責人:** [您的姓名]  
**適用案場:** 冰水主機房(BAS)、空調箱系統(AHU)、變頻設備監控  
**更新範圍:** 
- 新增 11 個 Physical Types（含效率、閥門、電力品質等）
- 定義 6 大設備類別的標準化命名規則
- 建立 HVAC 專用 Equipment Constraints（互鎖、啟停序列）
- 擴充 Group Policies（依設備類型自動套用 Lag 策略）

---

## 1. 設備分類架構 (Equipment Taxonomy)

### 1.1 設備類別對照表 (Device Category Mapping)

為統一欄位命名與 Group Policy 自動匹配，建立以下設備前綴規範：

| 設備中文名 | 英文代碼 | 欄位前綴範例 | Device Role 建議 |
|-----------|---------|-------------|-----------------|
| **冰水主機** | CH (Chiller) | `chiller_01_`, `ch_1_` | primary/backup |
| **冰水一次泵** | CHW-P (Primary) | `chw_pri_pump_01_`, `chwp1_` | primary |
| **冰水區域泵** | CHW-S (Secondary) | `chw_sec_pump_01_`, `chws1_` | primary |
| **冷卻水一次泵** | CW-P (Pump) | `cw_pump_01_`, `cwp1_` | primary |
| **冷卻水塔** | CT (Cooling Tower) | `ct_01_`, `cooling_tower_1_` | primary/backup |
| **空調箱** | AHU | `ahu_01_`, `ahu_north_` | primary |

### 1.2 元件類型對照表 (Component Type Mapping)

| 元件中文名 | 英文代碼 | 測點類型 | Physical Type 建議 | 單位 |
|-----------|---------|---------|-------------------|------|
| **冰水進水溫度** | CHWRT | 溫度計 | `temperature` | °C |
| **冰水回水溫度** | CHWST | 溫度計 | `temperature` | °C |
| **冷卻水進水溫度** | CWRT | 溫度計 | `temperature` | °C |
| **冷卻水回水溫度** | CWST | 溫度計 | `temperature` | °C |
| **冰水閥** | CHWV | 閥門 | `valve_position` | % |
| **變頻器** | VFD | 控制器 | `frequency` | Hz |
| **壓力計** | P | 壓力 | `pressure` | kPa |
| **壓差計** | DP | 壓差 | `pressure_differential` | kPa |

---

## 2. 擴充 Physical Types 定義 (SSOT 層更新)

於 `config/features/physical_types.yaml` 新增以下類型（保留原有類型，新增至檔案後段）：

```yaml
# ==========================================
# HVAC 擴充物理類型 (v1.2.1 新增)
# ==========================================

cooling_capacity:
  description: "冷凍能力/冷凍噸 (Refrigeration Tonnage)"
  unit: "RT"
  si_unit: "ton_of_refrigeration"
  valid_range: [0.0, 2000.0]        # 依案場主機容量調整
  agg_method: "sum"                 # 多台主機可相加
  distribution_check:
    expected_mean_range: [100, 800]
    max_std_threshold: 500
    zero_ratio_warning: 0.2         # 部分負載運轉時允許較高零值

efficiency:
  description: "效率指標 (COP, kW/RT, 或綜合效率)"
  unit: "COP"                       # 或 kW/RT，建議統一使用 COP 或註記於 description
  si_unit: "coefficient_of_performance"
  valid_range: [0.0, 10.0]          # COP 通常 3-6，異常值 >10 或 <0 視為錯誤
  agg_method: "mean"                # 效率通常取平均
  distribution_check:
    expected_mean_range: [3.0, 6.0]
    max_std_threshold: 2.0
    zero_ratio_warning: 0.1

energy:
  description: "累積電能/用電量 (電表讀數，需單調遞增)"
  unit: "kWh"
  si_unit: "kilowatt_hour"
  valid_range: [0.0, 999999999.0]   # 累積值，定期歸零時需處理
  agg_method: "last"                # 關鍵：取時段最末值，非平均
  distribution_check:
    check_monotonic: true           # 強制檢查單調遞增（防電表倒轉）
    max_reverse_delta: 0.01         # 允許 1% 回退（電表重置或精度誤差）
    expected_mean_range: null       # 累積值無固定範圍
    zero_ratio_warning: 0.0         # 累積值不應有零（除非重置）

valve_position:
  description: "閥門開度/閥位反饋"
  unit: "%"
  si_unit: "percent"
  valid_range: [0.0, 100.0]
  agg_method: "mean"
  distribution_check:
    expected_mean_range: [10, 90]   # 長期 0% 或 100% 可能表示閥門故障或選型錯誤
    max_std_threshold: 50
    zero_ratio_warning: 0.3         # 二通閥可能長期全關

frequency:
  description: "頻率/轉速控制信號（變頻器輸出）"
  unit: "Hz"
  si_unit: "hertz"
  valid_range: [0.0, 60.0]          # 台灣電網 60Hz，部分設備 50Hz
  agg_method: "mean"
  distribution_check:
    expected_mean_range: [30, 60]   # 正常運轉頻率範圍
    max_std_threshold: 20
    zero_ratio_warning: 0.5         # 設備停機時為 0Hz，允許高零值

rotational_speed:
  description: "實際轉速回授（RPM）"
  unit: "RPM"
  si_unit: "revolutions_per_minute"
  valid_range: [0.0, 3000.0]        # 依泵浦/風扇類型調整
  agg_method: "mean"
  distribution_check:
    expected_mean_range: [500, 1800]
    max_std_threshold: 1000

current:
  description: "電流（三相平均或單相）"
  unit: "A"
  si_unit: "ampere"
  valid_range: [0.0, 1000.0]        # 依斷路器容量調整
  agg_method: "mean"
  distribution_check:
    expected_mean_range: [10, 500]
    max_std_threshold: 300
    zero_ratio_warning: 0.4         # 備用設備可能長期 0A

voltage:
  description: "電壓（線電壓或相電壓）"
  unit: "V"
  si_unit: "volt"
  valid_range: [0.0, 500.0]         # 380V/220V/110V 系統
  agg_method: "mean"
  distribution_check:
    expected_mean_range: [200, 400] # 依電壓等級調整
    max_std_threshold: 50
    zero_ratio_warning: 0.1         # 停電時應觸發警告而非視為正常

power_factor:
  description: "功率因數（PF）"
  unit: "PF"
  si_unit: "dimensionless"
  valid_range: [0.0, 1.0]
  agg_method: "mean"
  distribution_check:
    expected_mean_range: [0.7, 1.0] # 功率因數過低需補償
    max_std_threshold: 0.3

pressure_differential:
  description: "壓差（過濾器、熱交換器兩端）"
  unit: "kPa"
  si_unit: "kilopascal"
  valid_range: [0.0, 500.0]
  agg_method: "mean"
  distribution_check:
    expected_mean_range: [10, 100]
    max_std_threshold: 100

operating_status:
  description: "運轉狀態（布林或 0/1）"
  unit: "status"
  si_unit: "boolean"
  valid_range: [0, 1]
  agg_method: "max"                 # 時段內只要曾運轉即視為運轉
  distribution_check:
    expected_mean_range: [0, 1]     # 無特定範圍
    max_std_threshold: 1
    zero_ratio_warning: null        # 由 device_role 控制（backup 允許長期 0）
```

---

## 3. Excel 範本更新規格 (Columns Sheet)

### 3.1 Physical Type 下拉選單擴充

**Sheet: Columns** 的 B 欄（Physical Type）下拉選項更新為：
```
temperature, pressure, flow_rate, power, chiller_load, status, gauge,
cooling_capacity, efficiency, energy, valve_position, frequency, 
rotational_speed, current, voltage, power_factor, pressure_differential, 
operating_status
```

### 3.2 單位選項擴充 (Unit Column)

**Sheet: Columns** 的 C 欄（Unit）靜態選單依物理類型分群：

| 物理類型 | 可選單位 |
|---------|---------|
| cooling_capacity | RT, kW (冷凍噸或千瓦冷量) |
| efficiency | COP, kW/RT |
| energy | kWh |
| valve_position | % |
| frequency | Hz |
| rotational_speed | RPM |
| current | A |
| voltage | V |
| power_factor | PF (無單位，顯示為 PF) |
| pressure_differential | kPa, Pa, bar |
| operating_status | - (無單位) |

### 3.3 完整標註範例 (Excel 實際填寫內容)

| 欄位名稱 (A) | 物理類型 (B) | 單位 (C) | 設備角色 (D) | 是否目標 (E) | 啟用 Lag (F) | Lag 間隔 (G) | 忽略警告 (H) | 描述 (I) | 狀態 (J) |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| chiller_01_chwst | temperature | °C | primary | FALSE | TRUE | 1,4,96 | - | 一號機冰水回水溫度 | confirmed |
| chiller_01_chwrt | temperature | °C | primary | FALSE | TRUE | 1,4,96 | - | 一號機冰水進水溫度 | confirmed |
| chiller_01_cwst | temperature | °C | primary | FALSE | TRUE | 1,4 | - | 一號機冷卻水回水溫度 | confirmed |
| chiller_01_cwrt | temperature | °C | primary | FALSE | TRUE | 1,4 | - | 一號機冷卻水進水溫度 | confirmed |
| chiller_01_status | operating_status | - | primary | FALSE | FALSE | - | - | 一號機運轉狀態 | confirmed |
| chiller_01_kw | power | kW | primary | TRUE | FALSE | - | - | 一號機功率（目標變數） | confirmed |
| chiller_01_kwh | energy | kWh | primary | FALSE | FALSE | - | - | 一號機累積用電 | confirmed |
| chiller_01_cop | efficiency | COP | primary | FALSE | TRUE | 4,96 | - | 一號機即時效率 | confirmed |
| chiller_01_rt | cooling_capacity | RT | primary | FALSE | TRUE | 1,4 | - | 一號機冷凍噸數 | confirmed |
| chw_pri_pump_01_hz | frequency | Hz | primary | FALSE | TRUE | 1,4 | - | 冰水泵 01 頻率 | confirmed |
| chw_pri_pump_01_a | current | A | primary | FALSE | TRUE | 1,4 | - | 冰水泵 01 電流 | confirmed |
| ct_01_fan_hz | frequency | Hz | primary | FALSE | TRUE | 1,4 | W403 | 冷卻水塔 01 風扇頻率（備援季節性允許零值） | confirmed |
| ahu_01_chwv | valve_position | % | primary | FALSE | TRUE | 1,4,96 | - | 空調箱 01 冰水閥開度 | confirmed |
| ahu_01_dp | pressure_differential | kPa | primary | FALSE | TRUE | 1 | - | 空調箱 01 過濾器壓差 | confirmed |
| ahu_01_pf | power_factor | PF | primary | FALSE | TRUE | 4 | - | 空調箱 01 功率因數 | confirmed |

---

## 4. Group Policies 擴充 (HVAC 專用策略)

於 `Sheet: Group Policies` 新增以下策略，針對不同設備類型自動套用特徵工程規則：

| 策略名稱 | 匹配類型 | 匹配值 | 物理類型 | 預設樣板 | 自定義 Lag |
|:---:|:---:|:---:|:---:|:---:|:---:|
| chillers | prefix | chiller_ | temperature | Standard_Chiller | 1,4,96 |
| chillers_power | prefix | chiller_ | power | Power_High_Freq | 1,4 |
| chillers_efficiency | prefix | chiller_ | efficiency | Efficiency_Smooth | 4,96 |
| pumps_flow | prefix | pump_ | frequency | VFD_Control | 1,4 |
| pumps_elec | prefix | pump_ | current | Electrical_Monitor | 1,4 |
| cooling_towers | prefix | ct_ | frequency | CT_Fan_Control | 1,4 |
| ahu_valves | prefix | ahu_ | valve_position | Valve_Position | 1,96 |
| ahu_pressure | prefix | ahu_ | pressure_differential | Filter_DP | 1 |

### 4.1 樣板定義 (Template Definitions)

於 YAML 中定義樣板細節：

```yaml
group_policies:
  Standard_Chiller:
    description: "冰水主機溫度測點標準策略"
    rules:
      lag_intervals: [1, 4, 96]      # 15分鐘、1小時、24小時延遲
      rolling_windows: [4, 96]       # 1小時、24小時滾動統計
      enable_rolling_stats: ["mean", "std", "min", "max"]
      
  Power_High_Freq:
    description: "功率監測高頻策略"
    rules:
      lag_intervals: [1, 4]          # 功率變化快，縮短延遲
      rolling_windows: [4, 12]       # 1小時、3小時統計
      
  Efficiency_Smooth:
    description: "效率計算平滑策略"
    rules:
      lag_intervals: [4, 96]         # 效率變化慢，減少高頻雜訊
      rolling_windows: [96]          # 僅日統計
      outlier_clip: [0, 10]          # COP 異常值剪裁
      
  VFD_Control:
    description: "變頻器控制策略"
    rules:
      lag_intervals: [1, 4]
      rolling_windows: [4]
      zero_handling: "interpolate"   # 停機零值不納入統計
      
  CT_Fan_Control:
    description: "冷卻水塔風扇策略（備援設備適用）"
    rules:
      lag_intervals: [1, 4]
      rolling_windows: [4, 96]
      backup_device_adjustment:      # 設備角色為 backup 時啟用
        extend_window: true          # 窗口放大
        ignore_zero_warnings: true   # 忽略 W403
```

---

## 5. Equipment Constraints 擴充 (HVAC 互鎖邏輯)

於 YAML 新增 `equipment_constraints` 區段，定義冰水主機房專用邏輯：

```yaml
equipment_constraints:
  # ==========================================
  # 冰水主機系統互鎖 (Chiller Interlocks)
  # ==========================================
  
  chiller_pump_interlock:
    description: "冰水主機開啟時必須有對應冰水泵運轉"
    check_type: "requires"
    check_phase: "precheck"
    trigger_status: ["chiller_01_status", "chiller_02_status"]
    required_status: ["chw_pri_pump_01_status", "chw_pri_pump_02_status"]
    severity: "critical"
    applicable_roles: ["primary", "backup"]
    error_code: "E350"
    
  chiller_cw_pump_interlock:
    description: "冰水主機開啟時必須有對應冷卻水泵運轉"
    check_type: "requires"
    check_phase: "precheck"
    trigger_status: ["chiller_01_status"]
    required_status: ["cw_pump_01_status", "cw_pump_02_status"]
    severity: "critical"
    applicable_roles: ["primary", "backup"]
    
  chiller_ct_interlock:
    description: "冰水主機開啟時必須有對應冷卻水塔運轉"
    check_type: "requires"
    check_phase: "precheck"
    trigger_status: ["chiller_01_status"]
    required_status: ["ct_01_status", "ct_02_status"]
    severity: "critical"
    
  chiller_temperature_protection:
    description: "冰水出水溫度過低保護（防凍）"
    check_type: "range_check"
    check_phase: "precheck"
    target_column: "chiller_01_chwst"
    min_value: 4.0                    # °C，低於 4 度視為異常
    max_value: 15.0
    severity: "critical"
    applicable_roles: ["primary", "backup"]
    
  # ==========================================
  # 運轉時間限制 (Runtime Constraints)
  # ==========================================
  
  chiller_min_runtime:
    description: "主機開啟後最少運轉 15 分鐘（防止頻繁啟停）"
    check_type: "min_duration"
    check_phase: "optimization"
    applies_to: ["chiller_01_status", "chiller_02_status"]
    min_duration_minutes: 15
    severity: "warning"
    
  chiller_min_downtime:
    description: "主機關閉後最少停機 10 分鐘（壓縮機保護）"
    check_type: "min_downtime"
    check_phase: "optimization"
    applies_to: ["chiller_01_status", "chiller_02_status"]
    min_duration_minutes: 10
    severity: "warning"
    
  # ==========================================
  # 容量與負載限制 (Capacity Constraints)
  # ==========================================
  
  chiller_load_min_limit:
    description: "主機低載保護（低於 20% 建議停機）"
    check_type: "threshold"
    check_phase: "optimization"
    target_column: "chiller_01_rt"
    reference_column: "chiller_01_rated_rt"  # 額定容量
    min_ratio: 0.2                           # 20%
    severity: "warning"
    suggestion: "建議關閉此主機，改由其他主機承載"
    
  # ==========================================
  # 空調箱互鎖 (AHU Interlocks)
  # ==========================================
  
  ahu_valve_flow_interlock:
    description: "空調箱風機運轉時才允許開啟冰水閥"
    check_type: "requires"
    check_phase: "precheck"
    trigger_status: ["ahu_01_chwv"]
    trigger_threshold: 5                    # 閥位 > 5%
    required_status: ["ahu_01_status"]      # 風機必須運轉
    severity: "warning"
    
  ahu_filter_dp_alarm:
    description: "過濾器壓差過高警告（需更換）"
    check_type: "threshold"
    check_phase: "precheck"
    target_column: "ahu_01_dp"
    max_value: 0.5                          # 0.5 kPa 或依設計
    severity: "warning"
    maintenance_trigger: true               # 觸發維護工單標記
```

---

## 6. FeatureAnnotationManager API 擴充

為支援新類型，API 新增以下方法（保留原有方法，新增查詢介面）：

```python
class FeatureAnnotationManager:
    # ... 原有方法 ...
    
    def get_columns_by_physical_type(self, physical_type: str) -> List[str]:
        """
        依物理類型取得所有欄位（如取得所有 frequency 測點）
        
        Usage:
            # 取得所有變頻器頻率測點進行統計
            freq_columns = manager.get_columns_by_physical_type("frequency")
        """
        return [
            name for name, anno in self._annotations.items()
            if anno.physical_type == physical_type
        ]
    
    def get_electrical_columns(self) -> Dict[str, List[str]]:
        """
        取得所有電力相關欄位分類（電流、電壓、功率、功率因數）
        
        Returns:
            {
                "power": ["chiller_01_kw", ...],
                "current": ["chiller_01_a", ...],
                "voltage": ["chiller_01_v", ...],
                "pf": ["chiller_01_pf", ...],
                "energy": ["chiller_01_kwh", ...]
            }
        """
        electrical_types = ["power", "current", "voltage", "power_factor", "energy"]
        return {
            ptype: self.get_columns_by_physical_type(ptype)
            for ptype in electrical_types
        }
    
    def validate_monotonic_energy(self, df: pl.DataFrame) -> List[str]:
        """
        驗證累積用電量（kWh）是否單調遞增（E351 錯誤碼）
        
        Returns:
            違反單調性的欄位列表
        """
        violations = []
        energy_cols = self.get_columns_by_physical_type("energy")
        
        for col in energy_cols:
            if col in df.columns:
                # 檢查是否有遞減（排除重置點的小幅回退）
                diff = df[col].diff()
                significant_drop = (diff < -0.01).sum()  # 允許 1% 精度誤差
                
                if significant_drop > 0:
                    violations.append({
                        "column": col,
                        "drops_count": int(significant_drop),
                        "error_code": "E351",
                        "message": f"累積用電量 {col} 發生非預期遞減，可能電表故障或重置"
                    })
        
        return violations
    
    def get_efficiency_baseline(self, chiller_id: str) -> Dict[str, float]:
        """
        取得特定主機的效率基準範圍（供 Cleaner 異常檢測使用）
        
        Returns:
            {"cop_min": 3.0, "cop_max": 6.0, "kw_per_rt_max": 1.2}
        """
        # 從 physical_types.efficiency.distribution_check 讀取
        ptype_config = self._cache.get("physical_types", {}).get("efficiency", {})
        mean_range = ptype_config.get("distribution_check", {}).get("expected_mean_range", [3.0, 6.0])
        
        return {
            "cop_min": mean_range[0],
            "cop_max": mean_range[1],
            "kw_per_rt_max": 3.517 / mean_range[0]  # COP = 3.517 / (kW/RT) 換算
        }
```

---

## 7. 錯誤代碼擴充表 (HVAC 專用)

| 代碼 | 名稱 | 層級 | 觸發條件 | 處理方式 |
|:---:|:---|:---:|:---|:---|
| **E350** | `CHILLER_PUMP_INTERLOCK_VIOLATION` | Error | 主機開但無對應水泵運轉 | 標記資料品質旗標，觸發設備檢查 |
| **E351** | `ENERGY_MONOTONICITY_VIOLATION` | Error | kWh 電表讀數遞減 | 檢查電表重置或故障，分段處理 |
| **E352** | `EFFICIENCE_OUT_OF_RANGE` | Warning | COP < 2 或 > 8（物理異常）| 標記異常，建議檢查溫度/流量感測器 |
| **E353** | `LOW_DELTA_T_SYNDROME` | Warning | 冰水進回水溫差 < 1°C（低溫差症候群）| 建議清洗熱交換器或檢查流量 |
| **E354** | `VALVE_POSITION_STUCK` | Warning | 閥位連續 4 小時無變化（卡閥）| 建議檢查閥門執行器 |
| **W406** | `FREQUENCY_ZERO_WHILE_RUNNING` | Warning | 運轉狀態=1 但頻率=0（變頻器異常）| 檢查 VFD 回授信號 |
| **W407** | `POWER_FACTOR_LOW` | Warning | PF < 0.8 持續超過 1 小時 | 建議檢查電容器或馬達狀態 |

---

## 8. 交付物清單 (v1.2.1-HVAC Update)

### 8.1 配置文件更新
1. `config/features/physical_types.yaml` - 新增 11 個 HVAC 物理類型（第 2 章內容）
2. `config/features/sites/{site_id}.yaml` - 案場標註（依第 3 章 Excel 範例生成）
3. `.gitignore` - 不變（仍排除 .xlsx）

### 8.2 Excel 工具鏈更新
4. `tools/features/templates/Feature_Template_v1.2.1.xlsx` - 更新下拉選單（新增 frequency, energy 等）
5. `tools/features/excel_to_yaml.py` - 新增單調性檢查（kWh）、效率範圍檢查
6. `tools/features/migrate_excel.py` - 支援 v1.2 → v1.2.1 遷移（新增欄位自動補預設值）

### 8.3 Python API 更新
7. `src/features/annotation_manager.py` - 新增第 6 章方法（get_electrical_columns, validate_monotonic_energy 等）
8. `src/features/hvac_validator.py` - **新增**：HVAC 專用驗證器（實作 E350-E354 檢查邏輯）

### 8.4 文件更新
9. `docs/features/FEATURE_ANNOTATION_v1.2.1-HVAC.md` - **本文件**
10. `docs/features/HVAC_TUTORIAL.md` - 空調技師操作手冊（如何標註冰水主機、如何設定互鎖）

---

## 9. 實作建議順序

1. **Day 1**: 更新 `physical_types.yaml`（第 2 章內容）與 Excel 範本（第 3 章）
2. **Day 2**: 更新 `annotation_manager.py` API（第 6 章）
3. **Day 3**: 實作 `hvac_validator.py` 與互鎖檢查（第 5 章、第 7 章錯誤碼）
4. **Day 4**: 測試與驗證（使用您的實際案場資料驗證 E350-E354）

---

**文件結束**
```

這份更新文件完整涵蓋了您提到的所有設備類型、測點類型與單位，並針對 HVAC 系統的特性（如主機-水泵互鎖、累積電量單調性、效率計算等）擴充了對應的邏輯與錯誤碼。建議直接以此作為 v1.2.1 版本的實作依據。