"""
HVAC-1 DataCleaner v2.2-Contract-Aligned

版本變更摘要 (v2.1 → v2.2):
- Temporal Context 強制注入: 未接收時拋出 E000
- FeatureAnnotationManager 整合: 語意感知清洗與設備邏輯預檢
- 設備邏輯預檢 (E350): 主機開+水泵關檢測，標記 PHYSICAL_IMPOSSIBLE
- 時間基準一致性: 所有時間檢查使用 pipeline_origin_timestamp，禁止 now()
- Metadata 強制淨化 (E500): 輸出絕對不含 device_role
- 設備稽核軌跡: 產生 equipment_validation_audit 供 BatchProcessor 寫入 Manifest

設計原則:
1. Gatekeeper: 髒數據絕不進入下游，設備邏輯違規提前標記
2. SSOT 嚴格遵守: 引用 config_models.py 的常數與限制條件
3. 職責分離: 讀取 device_role 進行語意感知清洗，但絕對禁止寫入輸出
4. 時間基準一致性: 所有時間相關驗證使用傳入的 pipeline_origin_timestamp
5. 物理邏輯一致性: 與 Optimization 共享 EQUIPMENT_VALIDATION_CONSTRAINTS

相依模組:
- src/etl/config_models.py (SSOT 常數)
- src/etl/parser.py (上游，輸出 UTC)
- src/features/annotation_manager.py (device_role 查詢)
- src/context.py (PipelineContext 時間基準)
- src/exceptions.py (例外類別)

交付物:
- src/etl/cleaner.py (本檔案)
- tests/test_cleaner_v22.py (單元測試)
"""

from typing import Dict, List, Optional, Tuple, Any, Set, Union
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
import logging
import re

import polars as pl
import numpy as np

# SSOT 引用
from src.etl.config_models import (
    VALID_QUALITY_FLAGS,
    VALID_QUALITY_FLAGS_SET,
    TIMESTAMP_CONFIG,
    EQUIPMENT_VALIDATION_CONSTRAINTS,
)
from src.exceptions import (
    ContractViolationError,
    DataValidationError,
    ConfigurationError,
)
from src.context import PipelineContext

logger = logging.getLogger(__name__)


# =============================================================================
# 常數定義
# =============================================================================

# 允許的 Metadata 鍵（白名單機制）
# 🆕 v1.4: 擴充支援 GNN 拓樸欄位
ALLOWED_METADATA_KEYS: Set[str] = frozenset({
    'physical_type', 'unit', 'description', 'column_name',
    'topology_node_id',      # 🆕 GNN 節點 ID
    'control_semantic',      # 🆕 控制語意
    'decay_factor',          # 🆕 衰減係數
})

# 禁止輸出的欄位（E500 防護）
FORBIDDEN_COLS: Set[str] = frozenset({
    'device_role', 'ignore_warnings', 'is_target', 'role',
    'device_type', 'annotation_role', 'col_role', 'feature_role'
})

# 設備角色閾值調整（語意感知清洗用）
DEVICE_ROLE_THRESHOLDS: Dict[str, Dict[str, float]] = {
    "primary": {
        "frozen_threshold_multiplier": 1.0,
        "zero_ratio_warning_threshold": 0.1,
        "outlier_z_score": 3.0
    },
    "backup": {
        "frozen_threshold_multiplier": 3.0,  # 備用設備放寬閾值
        "zero_ratio_warning_threshold": 0.8,  # 備用設備允許更多零值
        "outlier_z_score": 4.0
    },
    "seasonal": {
        "frozen_threshold_multiplier": 2.0,
        "zero_ratio_warning_threshold": 0.5,
        "outlier_z_score": 3.5
    }
}

# 預檢限制條件（Cleaner 階段執行）
PRECHECK_CONSTRAINTS: Dict[str, Dict[str, Any]] = {
    k: v for k, v in EQUIPMENT_VALIDATION_CONSTRAINTS.items()
    if v.get("check_phase") == "precheck" or k in ["chiller_pump_mutex", "pump_redundancy"]
}


# 設備類型識別模式（集中管理，避免硬編碼）
EQUIPMENT_TYPE_PATTERNS: Dict[str, List[str]] = {
    "chiller_status": [
        "chiller_1_status", "chiller_01_status", "ch_1_status",
        "chiller_2_status", "chiller_02_status", "ch_2_status",
        "ch1_run", "ch2_run", "chiller1_status", "chiller2_status"
    ],
    "chw_pump_status": [
        "chw_pump_1_status", "chw_pump_2_status",
        "chwp_1_status", "chwp_2_status",
        "chilled_water_pump_1", "chilled_water_pump_2"
    ],
    "cw_pump_status": [
        "cw_pump_1_status", "cw_pump_2_status",
        "cwp_1_status", "cwp_2_status",
        "cooling_water_pump_1", "cooling_water_pump_2"
    ],
    "pump_status": [
        "pump_1_status", "pump_2_status", "pump1_status", "pump2_status"
    ],
    "ct_status": [
        "ct_1_status", "ct_2_status", "ct1_status", "ct2_status",
        "cooling_tower_1_status", "cooling_tower_2_status"
    ]
}


# =============================================================================
# 配置類別
# =============================================================================

@dataclass
class CleanerConfig:
    """Cleaner 配置類別"""
    resample_interval: str = "5m"
    cop_min: float = 2.0
    cop_max: float = 8.0
    
    # Feature Annotation 整合
    use_device_role_from_annotation: bool = True
    unannotated_column_policy: str = "warn"  # error, skip, warn
    
    # 設備邏輯預檢
    enforce_equipment_validation_sync: bool = True
    
    # 時間檢查
    future_data_tolerance_minutes: int = 5
    future_data_behavior: str = "reject"  # "reject" | "filter" | "flag_only"
    
    # 凍結資料檢測
    frozen_data_window: int = 6
    frozen_data_min_periods: int = 1  # 滾動計算最小樣本數
    frozen_data_std_threshold: float = 0.001
    
    # 重採樣策略
    cumulative_agg_strategy: str = "last"  # last value for counters
    status_agg_strategy: str = "max"       # max for status (0/1)
    instant_agg_strategy: str = "mean"     # mean for measurements


# =============================================================================
# 主要類別
# =============================================================================

class DataCleaner:
    """
    HVAC-1 DataCleaner v2.2-Contract-Aligned
    
    功能:
    - Temporal Context 注入 (E000 檢查)
    - FeatureAnnotationManager 整合 (語意感知清洗)
    - 時間戳標準化 (UTC 強制)
    - 未來資料檢查 (E102) - 使用 pipeline_origin_timestamp
    - 設備邏輯預檢 (E350) - 標記 PHYSICAL_IMPOSSIBLE
    - 重採樣與缺漏處理
    - Metadata 強制淨化 (E500)
    - 設備稽核軌跡產生
    
    使用範例:
        context = PipelineContext()
        context.initialize()
        
        config = CleanerConfig()
        annotation_manager = FeatureAnnotationManager("site_id")
        
        cleaner = DataCleaner(
            config=config,
            annotation_manager=annotation_manager,
            pipeline_context=context
        )
        
        df_clean, metadata, audit = cleaner.clean(df_input)
    """
    
    def __init__(
        self,
        config: Optional[CleanerConfig] = None,
        annotation_manager: Optional[Any] = None,
        pipeline_context: Optional[PipelineContext] = None,
        site_id: Optional[str] = None
    ):
        """
        初始化 DataCleaner
        
        Args:
            config: Cleaner 配置
            annotation_manager: FeatureAnnotationManager 實例
            pipeline_context: PipelineContext 實例（強制要求，E000 檢查）
            site_id: 案場 ID（用於載入預設 Annotation）
            
        Raises:
            RuntimeError: E000 未提供 PipelineContext
        """
        self.config = config or CleanerConfig()
        self.annotation = annotation_manager
        self.site_id = site_id
        
        # E000: Temporal Context 強制檢查
        if pipeline_context is None:
            raise RuntimeError(
                "E000: DataCleaner 必須接收 PipelineContext，禁止自行產生時間戳。 "
                "請確保 Container 正確傳遞 pipeline_origin_timestamp。"
            )
        
        self.pipeline_context = pipeline_context
        self.pipeline_origin_timestamp = pipeline_context.get_baseline()
        
        # 設備稽核軌跡（由設備邏輯預檢產生）
        self._equipment_validation_audit: Dict[str, Any] = {
            "validation_enabled": False,
            "constraints_applied": [],
            "violations_detected": 0,
            "violation_details": []
        }
        
        # 執行時狀態
        self._skipped_columns: Set[str] = set()
        
        logger.info(
            f"DataCleaner v2.2 初始化完成 ("
            f"site_id={site_id}, "
            f"temporal_baseline={self.pipeline_origin_timestamp.isoformat()}, "
            f"equipment_validation={self.config.enforce_equipment_validation_sync}"
            f")"
        )
    
    # =========================================================================
    # 核心公開方法
    # =========================================================================
    
    def clean(
        self,
        df: pl.DataFrame,
        input_metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[pl.DataFrame, Dict[str, Any], Dict[str, Any]]:
        """
        主要清洗流程
        
        方法呼叫鏈:
        1. _validate_temporal_baseline - E000 檢查
        2. _validate_columns_annotated - E402, E409 檢查
        3. _normalize_timestamp - 時間戳標準化 (UTC)
        4. _check_future_data - 未來資料檢查 (E102)
        5. _init_quality_flags - 初始化品質標記
        6. _semantic_aware_cleaning - 語意感知清洗
        7. _apply_equipment_validation_precheck - 設備邏輯預檢 (E350)
        8. _resample_and_fill - 重採樣與缺漏處理
        9. _validate_output_contract - 輸出契約驗證
        10. _build_column_metadata - Metadata 建構
        
        Args:
            df: 輸入 DataFrame（來自 Parser v2.1）
            input_metadata: 輸入中繼資料
            
        Returns:
            Tuple of (clean_df, column_metadata, equipment_validation_audit)
            
        Raises:
            ContractViolationError: 契約違反時
            DataValidationError: 資料驗證失敗時
        """
        logger.info(f"開始清洗流程: {df.shape[0]} 行 x {df.shape[1]} 列")
        
        # Step 0: 時間基準驗證
        self._validate_temporal_baseline(input_metadata)
        
        # Step 0.5: 欄位標註驗證
        df = self._validate_columns_annotated(df)
        
        # Step 1: 時間戳標準化
        df = self._normalize_timestamp(df)
        
        # Step 2: 未來資料檢查 (E102)
        df = self._check_future_data(df)
        
        # Step 3: 初始化品質標記
        df = self._init_quality_flags(df)
        
        # Step 4: 語意感知清洗
        df = self._semantic_aware_cleaning(df)
        
        # Step 5: 設備邏輯預檢 (E350)
        df = self._apply_equipment_validation_precheck(df)
        
        # Step 6: 重採樣與缺漏處理
        df = self._resample_and_fill(df)
        
        # Step 7: 輸出契約驗證
        df = self._validate_output_contract(df)
        
        # Step 8: 建構 Metadata 與稽核軌跡
        column_metadata = self._build_column_metadata(df)
        
        logger.info(
            f"清洗完成: {df.shape[0]} 行 x {df.shape[1]} 列, "
            f"違規檢測: {self._equipment_validation_audit['violations_detected']} 筆"
        )
        
        return df, column_metadata, self._equipment_validation_audit
    
    # =========================================================================
    # 驗證方法
    # =========================================================================
    
    def _validate_temporal_baseline(self, input_metadata: Optional[Dict]) -> None:
        """驗證時間基準存在 (E000)"""
        if self.pipeline_origin_timestamp is None:
            raise DataValidationError(
                "E000: PipelineContext 未初始化，無法取得時間基準。"
                "請先執行 PipelineContext.initialize()"
            )
        
        # 驗證輸入 metadata 也有時間基準（一致性檢查）
        if input_metadata:
            metadata_ts = input_metadata.get('pipeline_origin_timestamp')
            if metadata_ts:
                # 允許微小差異（<1秒）
                if isinstance(metadata_ts, str):
                    metadata_ts = datetime.fromisoformat(metadata_ts.replace('Z', '+00:00'))
                
                diff = abs((self.pipeline_origin_timestamp - metadata_ts).total_seconds())
                if diff > 1:
                    logger.warning(
                        f"時間基準差異: Context={self.pipeline_origin_timestamp.isoformat()}, "
                        f"Metadata={metadata_ts.isoformat()}, 差異={diff:.2f}秒"
                    )
    
    def _validate_columns_annotated(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        驗證所有欄位已在 Annotation 中定義 (E402)
        並驗證標頭已正規化（E409）
        """
        if not self.annotation or not self.config.use_device_role_from_annotation:
            return df
        
        unannotated = []
        non_standardized = []
        
        for col in df.columns:
            if col == "timestamp":
                continue
            
            # E402 檢查：欄位是否已定義於 Annotation
            if not self.annotation.is_column_annotated(col):
                unannotated.append(col)
            else:
                # E409 檢查：驗證標頭為 snake_case
                if not self._is_snake_case(col):
                    non_standardized.append(col)
        
        # 處理未定義欄位
        if unannotated:
            policy = self.config.unannotated_column_policy
            if policy == "error":
                raise DataValidationError(
                    f"E402: 以下欄位未定義於 Feature Annotation: {unannotated}"
                )
            elif policy == "skip":
                logger.warning(f"E402 (Skip): 跳過未定義欄位: {unannotated}")
                self._skipped_columns = set(unannotated)
                df = df.drop(*unannotated)
            elif policy == "warn":
                logger.warning(f"E402 (Warn): 未定義欄位使用保守預設: {unannotated}")
        
        # 處理非正規化標頭
        if non_standardized:
            logger.warning(
                f"E409-Warning: 以下欄位未使用 snake_case: {non_standardized}"
            )
        
        return df
    
    def _validate_output_contract(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        最終輸出驗證 (Interface Contract Enforcement)
        
        驗證項目:
        1. 時間戳時區與精度
        2. 時間基準傳遞 (E000)
        3. Schema 淨化 (移除 FORBIDDEN_COLS)
        4. device_role 不存在 (E500)
        5. Quality Flags 合法性
        """
        errors = []
        
        # 1. 時間戳檢查
        if "timestamp" not in df.columns:
            errors.append("缺少必要欄位 'timestamp'")
        else:
            ts_dtype = df["timestamp"].dtype
            if not isinstance(ts_dtype, pl.Datetime):
                errors.append(f"timestamp 必須為 Datetime，得到 {ts_dtype}")
            else:
                if str(ts_dtype.time_zone) != "UTC":
                    errors.append(f"E102: timestamp 時區必須為 UTC，得到 {ts_dtype.time_zone}")
                if ts_dtype.time_unit != "ns":
                    errors.append(f"E102: timestamp 精度必須為 nanoseconds")
        
        # 2. 時間基準傳遞檢查
        if self.pipeline_origin_timestamp is None:
            errors.append("E000: 遺失 pipeline_origin_timestamp")
        
        # 3. Schema 淨化 - 移除禁止欄位
        df = self._enforce_schema_sanitization(df)
        
        # 4. device_role 不存在檢查（E500）
        for forbidden_col in FORBIDDEN_COLS:
            if forbidden_col in df.columns:
                errors.append(f"E500: 輸出包含禁止欄位 '{forbidden_col}'")
        
        # 5. Quality Flags 檢查
        if "quality_flags" in df.columns:
            invalid_flags = self._validate_quality_flags_column(df["quality_flags"])
            if invalid_flags:
                errors.append(f"E202: 非法品質標記: {invalid_flags}")
        
        # 6. 未來資料二次確認
        if self.pipeline_origin_timestamp:
            threshold = self.pipeline_origin_timestamp + timedelta(
                minutes=self.config.future_data_tolerance_minutes
            )
            if (df["timestamp"] > threshold).any():
                errors.append("E102: 輸出仍包含未來資料")
        
        if errors:
            raise ContractViolationError(
                f"Cleaner 輸出契約驗證失敗 ({len(errors)} 項):\n" + 
                "\n".join(f"  - {e}" for e in errors)
            )
        
        return df
    
    def _validate_quality_flags_column(self, flags_series: pl.Series) -> Set[str]:
        """驗證品質標記欄位的所有值是否合法"""
        all_flags = set()
        for flags in flags_series:
            # 修復: 避免直接使用 if flags 造成 Series 真值歧義
            # flags 是 List[str] 類型，檢查是否為 None 且長度 > 0
            if flags is not None and len(flags) > 0:
                # 過濾掉 None 值，只加入有效的字串標記
                valid_flags = [f for f in flags if f is not None]
                all_flags.update(valid_flags)
        return all_flags - VALID_QUALITY_FLAGS_SET
    
    # =========================================================================
    # 時間相關方法
    # =========================================================================
    
    def _normalize_timestamp(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        時間戳標準化 (UTC 強制)
        
        確保:
        - 時區為 UTC
        - 精度為 nanoseconds
        """
        if "timestamp" not in df.columns:
            raise DataValidationError("輸入資料缺少必要欄位 'timestamp'")
        
        ts_col = df["timestamp"]
        
        # 檢查類型
        if not isinstance(ts_col.dtype, pl.Datetime):
            raise DataValidationError(f"timestamp 欄位類型錯誤: {ts_col.dtype}")
        
        # 時區處理
        current_tz = ts_col.dtype.time_zone
        if current_tz is None:
            logger.warning("timestamp 無時區資訊，假設為 UTC")
            df = df.with_columns(
                pl.col("timestamp").dt.replace_time_zone("UTC").alias("timestamp")
            )
        elif str(current_tz) != "UTC":
            logger.warning(f"E101: 偵測到非 UTC 時區 {current_tz}，自動轉換")
            df = df.with_columns(
                pl.col("timestamp").dt.convert_time_zone("UTC").alias("timestamp")
            )
        
        # 確保精度為 nanosecond
        if ts_col.dtype.time_unit != "ns":
            df = df.with_columns(
                pl.col("timestamp").cast(
                    pl.Datetime(time_unit="ns", time_zone="UTC")
                ).alias("timestamp")
            )
        
        return df
    
    def _check_future_data(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        未來資料檢查 (E102)
        
        【關鍵】使用 self.pipeline_origin_timestamp 而非 datetime.now()
        
        根據 future_data_behavior 設定採取不同策略：
        - "reject": 拋出 DataValidationError（預設，生產環境）
        - "filter": 標記並移除未來資料，繼續處理
        - "flag_only": 標記但不移除
        
        Returns:
            處理後的 DataFrame（根據設定可能已移除未來資料）
        """
        threshold = self.pipeline_origin_timestamp + timedelta(
            minutes=self.config.future_data_tolerance_minutes
        )
        
        future_mask = df["timestamp"] > threshold
        future_count = future_mask.sum()
        
        if future_count == 0:
            logger.debug(f"未來資料檢查通過（基準: {self.pipeline_origin_timestamp.isoformat()}）")
            return df
        
        behavior = self.config.future_data_behavior
        future_samples = df.filter(future_mask)["timestamp"].head(3).to_list()
        
        if behavior == "reject":
            # 生產環境預設：嚴格拒絕
            raise DataValidationError(
                f"E102: 偵測到 {future_count} 筆未來資料（>{threshold.isoformat()}）。"
                f"樣本: {future_samples}。 "
                f"Pipeline 時間基準: {self.pipeline_origin_timestamp.isoformat()}。 "
                f"請檢查資料來源時鐘或時間基準傳遞。"
            )
        
        elif behavior == "filter":
            # 開發/測試環境：標記並移除，繼續處理
            logger.warning(
                f"E102: 偵測到 {future_count} 筆未來資料，標記並移除。"
                f"樣本: {future_samples}"
            )
            df = df.with_columns(
                pl.when(future_mask)
                .then(
                    pl.col("quality_flags").list.concat(pl.lit(["FUTURE_DATA"]))
                )
                .otherwise(pl.col("quality_flags"))
                .alias("quality_flags")
            )
            df = df.filter(~future_mask)
            logger.info(f"已移除 {future_count} 筆未來資料，剩餘 {len(df)} 筆")
            return df
        
        elif behavior == "flag_only":
            # 僅標記但不移除
            logger.warning(
                f"E102: 偵測到 {future_count} 筆未來資料，僅標記不移除。"
                f"樣本: {future_samples}"
            )
            df = df.with_columns(
                pl.when(future_mask)
                .then(
                    pl.col("quality_flags").list.concat(pl.lit(["FUTURE_DATA"]))
                )
                .otherwise(pl.col("quality_flags"))
                .alias("quality_flags")
            )
            return df
        
        else:
            raise ConfigurationError(
                f"未知的 future_data_behavior: {behavior}。"
                f"有效值: 'reject', 'filter', 'flag_only'"
            )
    
    # =========================================================================
    # 語意感知清洗
    # =========================================================================
    
    def _init_quality_flags(self, df: pl.DataFrame) -> pl.DataFrame:
        """初始化 quality_flags 欄位"""
        if "quality_flags" not in df.columns:
            df = df.with_columns(
                pl.lit([]).cast(pl.List(pl.Utf8)).alias("quality_flags")
            )
        return df
    
    def _semantic_aware_cleaning(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        語意感知清洗（讀取 device_role，但絕不寫入輸出）
        
        維持邏輯:
        - 凍結資料偵測（角色感知閾值）
        - 零值比例檢查（角色感知警告抑制）
        - 物理限制檢查
        """
        if not self.annotation:
            logger.debug("未啟用 Annotation 整合，跳過語意感知清洗")
            return df
        
        logger.info("啟動語意感知清洗（device_role 感知，輸出隔離）...")
        
        # 1. 凍結資料偵測（角色感知閾值）
        df = self._detect_frozen_data_semantic(df)
        
        # 2. 零值比例檢查（角色感知警告抑制）
        df = self._check_zero_ratio_semantic(df)
        
        # 3. 物理限制檢查
        df = self._apply_physical_constraints_semantic(df)
        
        return df
    
    def _detect_frozen_data_semantic(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        凍結資料偵測（角色感知閾值調整）
        
        邏輯:
        - 計算滾動標準差
        - 標準差接近 0 表示資料凍結
        - 閾值依 device_role 調整（備用設備放寬）
        
        邊界條件防護:
        - 資料行數 < window 時輸出警告並跳過偵測
        - 使用 min_periods 允許較少樣本計算
        """
        window = self.config.frozen_data_window
        min_periods = getattr(self.config, 'frozen_data_min_periods', 1)
        threshold = self.config.frozen_data_std_threshold
        
        # 資料量不足防護
        if df.height < window:
            logger.warning(
                f"資料行數 ({df.height}) < 凍結偵測視窗 ({window})，"
                f"凍結資料偵測可能不準確"
            )
            # 繼續處理，但使用更小的 window
            effective_window = min(df.height, window)
            if effective_window < 2:
                logger.warning(f"資料行數不足 ({df.height})，無法進行凍結資料偵測")
                return df
        else:
            effective_window = window
        
        for col in df.columns:
            if col in ["timestamp", "quality_flags"]:
                continue
            
            # 跳過非數值欄位
            if df[col].dtype not in [pl.Float64, pl.Float32, pl.Int64, pl.Int32]:
                continue
            
            # 取得 device_role 調整閾值
            device_role = self._get_device_role(col)
            multiplier = DEVICE_ROLE_THRESHOLDS.get(
                device_role, DEVICE_ROLE_THRESHOLDS["primary"]
            )["frozen_threshold_multiplier"]
            
            adjusted_threshold = threshold * multiplier
            
            # 計算滾動標準差（使用 min_periods 允許較少樣本）
            df = df.with_columns(
                pl.col(col).rolling_std(
                    window_size=effective_window,
                    min_periods=min_periods
                ).alias(f"_{col}_std")
            )
            
            # 標記凍結資料（前 min_periods-1 個值若為 null 則視為非凍結）
            is_frozen = (pl.col(f"_{col}_std") < adjusted_threshold).fill_null(False)
            
            # 更新 quality_flags
            df = df.with_columns(
                pl.when(is_frozen)
                .then(
                    pl.col("quality_flags").list.concat(pl.lit(["FROZEN_DATA"]))
                )
                .otherwise(pl.col("quality_flags"))
                .alias("quality_flags")
            )
            
            # 清理臨時欄位
            df = df.drop(f"_{col}_std")
        
        return df
    
    def _check_zero_ratio_semantic(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        零值比例檢查（角色感知警告抑制）
        
        邏輯:
        - 計算欄位零值比例
        - 主設備 (>10%) 警告，備用設備 (>80%) 警告
        """
        total_rows = df.height
        
        for col in df.columns:
            if col in ["timestamp", "quality_flags"]:
                continue
            
            # 跳過非數值欄位
            if df[col].dtype not in [pl.Float64, pl.Float32, pl.Int64, pl.Int32]:
                continue
            
            # 取得 device_role 閾值
            device_role = self._get_device_role(col)
            warning_threshold = DEVICE_ROLE_THRESHOLDS.get(
                device_role, DEVICE_ROLE_THRESHOLDS["primary"]
            )["zero_ratio_warning_threshold"]
            
            # 計算零值比例
            zero_count = (df[col] == 0).sum()
            zero_ratio = zero_count / total_rows if total_rows > 0 else 0
            
            # 超過閾值時標記
            if zero_ratio > warning_threshold:
                logger.warning(
                    f"E212: 欄位 '{col}' 零值比例 {zero_ratio:.1%} "
                    f"超過閾值 {warning_threshold:.1%} (role={device_role})"
                )
                
                # 標記該欄位為零值的行
                df = df.with_columns(
                    pl.when(pl.col(col) == 0)
                    .then(
                        pl.col("quality_flags").list.concat(pl.lit(["ZERO_VALUE_EXCESS"]))
                    )
                    .otherwise(pl.col("quality_flags"))
                    .alias("quality_flags")
                )
        
        return df
    
    def _apply_physical_constraints_semantic(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        物理限制檢查（基於 physical_type）
        
        檢查項目:
        - 溫度範圍 (-40°C ~ 100°C)
        - 壓力範圍 (0 ~ 10 bar)
        - 功率範圍 (>= 0)
        """
        if not self.annotation:
            return df
        
        # 溫度限制
        temp_cols = self._get_columns_by_physical_type("temperature")
        for col in temp_cols:
            if col in df.columns:
                # 標記超出範圍的值
                df = df.with_columns(
                    pl.when((pl.col(col) < -40) | (pl.col(col) > 100))
                    .then(
                        pl.col("quality_flags").list.concat(pl.lit(["PHYSICAL_LIMIT_VIOLATION"]))
                    )
                    .otherwise(pl.col("quality_flags"))
                    .alias("quality_flags")
                )
        
        # 功率限制（必須 >= 0）
        power_cols = self._get_columns_by_physical_type("power")
        for col in power_cols:
            if col in df.columns:
                df = df.with_columns(
                    pl.when(pl.col(col) < 0)
                    .then(
                        pl.col("quality_flags").list.concat(pl.lit(["PHYSICAL_LIMIT_VIOLATION"]))
                    )
                    .otherwise(pl.col("quality_flags"))
                    .alias("quality_flags")
                )
        
        return df
    
    # =========================================================================
    # 設備邏輯預檢 (E350)
    # =========================================================================
    
    def _apply_equipment_validation_precheck(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        設備邏輯預檢（對齊 Interface Contract v1.1 檢查點 #2）

        檢查基礎設備邏輯違規:
        - 主機開啟時水泵不可全關（chiller_pump_mutex）
        - 主機開啟時冷卻水塔不可全關（pump_redundancy）

        違規資料標記為 PHYSICAL_IMPOSSIBLE 或 EQUIPMENT_VIOLATION

        驅動機制: PRECHECK_CONSTRAINTS（集中定義於常數區塊，符合 SSOT 原則）
        新增 constraint 只需在 EQUIPMENT_VALIDATION_CONSTRAINTS 標記
        check_phase="precheck" 並在下方 _CONSTRAINT_HANDLERS 登記 handler 即可。
        """
        if not self.config.enforce_equipment_validation_sync:
            self._equipment_validation_audit = {
                "validation_enabled": False,
                "constraints_applied": [],
                "violations_detected": 0,
                "violation_details": [],
                "precheck_timestamp": self.pipeline_origin_timestamp.isoformat(),
                "audit_generated_at": datetime.now(timezone.utc).isoformat()
            }
            return df

        logger.info("執行設備邏輯預檢（Equipment Validation Precheck）...")

        violations = []
        df_result = df

        # 取得欄位名稱映射（嘗試多種命名模式）
        col_map = self._detect_equipment_status_columns(df)

        # ── SSOT 分派表：PRECHECK_CONSTRAINTS 鍵 → 具體檢查函數 ──────────────
        # 僅需於此登記；PRECHECK_CONSTRAINTS 的鍵集合決定「哪些 constraint 被執行」
        _CONSTRAINT_HANDLERS: Dict[str, Any] = {
            "chiller_pump_mutex": lambda df_in: (
                self._check_chiller_pump_mutex(
                    df_in,
                    col_map.get("chiller_status", []),
                    col_map.get("pump_status", [])
                )
                if col_map.get("chiller_status") and col_map.get("pump_status")
                else (df_in, None)
            ),
            "pump_redundancy": lambda df_in: (
                self._check_pump_redundancy(
                    df_in,
                    col_map.get("chiller_status", []),
                    col_map.get("chw_pump_status", []),
                    col_map.get("cw_pump_status", [])
                )
                if col_map.get("chiller_status") and col_map.get("chw_pump_status")
                else (df_in, None)
            ),
        }
        # ─────────────────────────────────────────────────────────────────────

        # 依據 PRECHECK_CONSTRAINTS 鍵逐一執行對應 handler（SSOT 驅動）
        applied_constraints = list(PRECHECK_CONSTRAINTS.keys())
        for constraint_id in applied_constraints:
            handler = _CONSTRAINT_HANDLERS.get(constraint_id)
            if handler is None:
                logger.warning(
                    f"PRECHECK_CONSTRAINTS 包含 '{constraint_id}' 但尚未登記 handler，跳過"
                )
                continue
            df_result, violation = handler(df_result)
            if violation:
                violations.append(violation)

        # 記錄稽核軌跡（constraints_applied 反映 PRECHECK_CONSTRAINTS 實際鍵集）
        self._equipment_validation_audit = {
            "validation_enabled": True,
            "constraints_applied": applied_constraints,
            "violations_detected": sum(v["count"] for v in violations),
            "violation_details": violations,
            "precheck_timestamp": self.pipeline_origin_timestamp.isoformat(),
            "audit_generated_at": datetime.now(timezone.utc).isoformat(),
            "column_mapping_used": col_map
        }

        if violations:
            logger.warning(
                f"E350: 設備邏輯預檢發現 {len(violations)} 項違規: "
                f"{[v['constraint_id'] for v in violations]}"
            )

        return df_result
    
    def _detect_equipment_status_columns(self, df: pl.DataFrame) -> Dict[str, List[str]]:
        """
        自動偵測設備狀態欄位
        
        支援多種命名模式:
        - 主機: chiller_1_status, chiller_01_status, ch_1_status, ch1_run
        - 水泵: pump_1_status, chw_pump_1_status, chwp_1_status
        """
        result = {
            "chiller_status": [],
            "pump_status": [],
            "chw_pump_status": [],
            "cw_pump_status": [],
            "ct_status": []
        }
        
        # 使用集中管理的模式識別（SSOT 原則）
        # 優先嘗試從 AnnotationManager 取得設備類型
        for col in df.columns:
            col_lower = col.lower()
            
            # 嘗試從 annotation 取得設備類型（更精確）
            equipment_type = None
            if self.annotation:
                equipment_type = self.annotation.get_equipment_type(col)
            
            # 若有設備類型資訊，直接使用
            if equipment_type == "chiller":
                result["chiller_status"].append(col)
                continue
            elif equipment_type == "chw_pump":
                result["chw_pump_status"].append(col)
                result["pump_status"].append(col)
                continue
            elif equipment_type == "cw_pump":
                result["cw_pump_status"].append(col)
                result["pump_status"].append(col)
                continue
            elif equipment_type == "cooling_tower":
                result["ct_status"].append(col)
                continue
            
            # 若無 annotation 或無設備類型，使用模式匹配（向後相容）
            # 主機狀態
            if any(pattern in col_lower for pattern in EQUIPMENT_TYPE_PATTERNS["chiller_status"]):
                result["chiller_status"].append(col)
            
            # 冷凍水泵
            elif any(pattern in col_lower for pattern in EQUIPMENT_TYPE_PATTERNS["chw_pump_status"]):
                result["chw_pump_status"].append(col)
                result["pump_status"].append(col)
            
            # 冷卻水泵
            elif any(pattern in col_lower for pattern in EQUIPMENT_TYPE_PATTERNS["cw_pump_status"]):
                result["cw_pump_status"].append(col)
                result["pump_status"].append(col)
            
            # 一般水泵
            elif any(pattern in col_lower for pattern in EQUIPMENT_TYPE_PATTERNS["pump_status"]):
                result["pump_status"].append(col)
            
            # 冷卻水塔
            elif any(pattern in col_lower for pattern in EQUIPMENT_TYPE_PATTERNS["ct_status"]):
                result["ct_status"].append(col)
        
        return result
    
    def _check_chiller_pump_mutex(
        self, df: pl.DataFrame, chiller_cols: List[str], pump_cols: List[str]
    ) -> Tuple[pl.DataFrame, Optional[Dict]]:
        """
        檢查主機開啟時水泵不可全關
        
        違規條件: (任一主機開啟) AND (所有水泵關閉)
        """
        if not chiller_cols or not pump_cols:
            return df, None
        
        # 建立觸發條件（任一主機開啟）
        trigger_condition = pl.col(chiller_cols[0]) == 1
        for col in chiller_cols[1:]:
            trigger_condition = trigger_condition | (pl.col(col) == 1)
        
        # 建立需求條件（至少一台水泵運轉）
        requirement_condition = pl.col(pump_cols[0]) == 1
        for col in pump_cols[1:]:
            requirement_condition = requirement_condition | (pl.col(col) == 1)
        
        # 違規條件
        violation_condition = trigger_condition & ~requirement_condition
        
        # 計算違規數
        violation_count = df.filter(violation_condition).height
        
        if violation_count > 0:
            # 標記 Quality Flag
            df = df.with_columns(
                pl.when(violation_condition)
                .then(
                    pl.col("quality_flags").list.concat(pl.lit(["PHYSICAL_IMPOSSIBLE"]))
                )
                .otherwise(pl.col("quality_flags"))
                .alias("quality_flags")
            )
            
            violation = {
                "constraint_id": "chiller_pump_mutex",
                "description": "主機開啟時必須有至少一台水泵運轉",
                "count": violation_count,
                "severity": "critical",
                "trigger_columns": chiller_cols,
                "required_columns": pump_cols,
                "timestamp": self.pipeline_origin_timestamp.isoformat()
            }
            return df, violation
        
        return df, None
    
    def _check_pump_redundancy(
        self, df: pl.DataFrame, chiller_cols: List[str],
        chw_pump_cols: List[str], cw_pump_cols: List[str]
    ) -> Tuple[pl.DataFrame, Optional[Dict]]:
        """
        檢查冗餘要求: 主機運轉時必須有冷凍水泵和冷卻水泵運轉
        """
        if not chiller_cols:
            return df, None
        
        # 建立觸發條件
        trigger_condition = pl.col(chiller_cols[0]) == 1
        for col in chiller_cols[1:]:
            trigger_condition = trigger_condition | (pl.col(col) == 1)
        
        violations = []
        
        # 檢查冷凍水泵
        if chw_pump_cols:
            chw_condition = pl.col(chw_pump_cols[0]) == 1
            for col in chw_pump_cols[1:]:
                chw_condition = chw_condition | (pl.col(col) == 1)
            
            chw_violation = trigger_condition & ~chw_condition
            chw_count = df.filter(chw_violation).height
            
            if chw_count > 0:
                df = df.with_columns(
                    pl.when(chw_violation)
                    .then(
                        pl.col("quality_flags").list.concat(pl.lit(["EQUIPMENT_VIOLATION"]))
                    )
                    .otherwise(pl.col("quality_flags"))
                    .alias("quality_flags")
                )
                violations.append(f"chilled_water_pump_missing:{chw_count}")
        
        # 檢查冷卻水泵
        if cw_pump_cols:
            cw_condition = pl.col(cw_pump_cols[0]) == 1
            for col in cw_pump_cols[1:]:
                cw_condition = cw_condition | (pl.col(col) == 1)
            
            cw_violation = trigger_condition & ~cw_condition
            cw_count = df.filter(cw_violation).height
            
            if cw_count > 0:
                df = df.with_columns(
                    pl.when(cw_violation)
                    .then(
                        pl.col("quality_flags").list.concat(pl.lit(["EQUIPMENT_VIOLATION"]))
                    )
                    .otherwise(pl.col("quality_flags"))
                    .alias("quality_flags")
                )
                violations.append(f"cooling_water_pump_missing:{cw_count}")
        
        total_count = sum(
            int(v.split(":")[1]) for v in violations
        ) if violations else 0
        
        if violations:
            violation = {
                "constraint_id": "pump_redundancy",
                "description": "主機運轉時必須有冷凍水泵和冷卻水泵運轉",
                "count": total_count,
                "severity": "critical",
                "details": violations,
                "timestamp": self.pipeline_origin_timestamp.isoformat()
            }
            return df, violation
        
        return df, None
    
    # =========================================================================
    # 重採樣與缺漏處理
    # =========================================================================
    
    def _resample_and_fill(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        重採樣與缺漏處理
        
        策略:
        - 累計值 (KWH): last()
        - 狀態值 (Status): max()
        - 瞬時值 (KW, Temp): mean()
        """
        if "timestamp" not in df.columns:
            return df
        
        # 移除空時間戳
        original_len = len(df)
        df = df.filter(pl.col("timestamp").is_not_null())
        if len(df) < original_len:
            logger.warning(f"移除 {original_len - len(df)} 行空時間戳")
        
        if len(df) == 0:
            return df
        
        # 排序
        df = df.sort("timestamp")
        
        # 建立聚合表達式
        agg_exprs = []
        
        for col in df.columns:
            if col == "timestamp":
                continue
            
            col_upper = col.upper()
            
            # 累計值 (KWH)
            if col_upper.endswith("KWH") or col_upper.endswith("_KWH"):
                agg_exprs.append(pl.col(col).last().alias(col))
            
            # 狀態值
            elif (col_upper.endswith("_STATUS") or 
                  col_upper.endswith(".S") or 
                  "STATUS" in col_upper):
                agg_exprs.append(pl.col(col).max().alias(col))
            
            # quality_flags 需要特殊處理（合併並去重）
            elif col == "quality_flags":
                # 合併該時間窗內的所有 flags 並去重
                # explode() 攤平列表 → unique() 去重 → implode() 重新打包成列表
                agg_exprs.append(
                    pl.col(col).explode().unique().implode().alias(col)
                )
            
            # 瞬時值
            else:
                agg_exprs.append(pl.col(col).mean().alias(col))
        
        # 執行重採樣
        df_resampled = df.group_by_dynamic(
            "timestamp",
            every=self.config.resample_interval
        ).agg(agg_exprs)
        
        logger.info(f"重採樣: {original_len} -> {len(df_resampled)} 行")
        return df_resampled
    
    # =========================================================================
    # Metadata 建構
    # =========================================================================
    
    def _build_column_metadata(self, df: pl.DataFrame) -> Dict[str, Dict[str, Any]]:
        """
        建構欄位 Metadata（白名單過濾）
        
        Returns:
            欄位名稱 -> Metadata 字典（僅含 ALLOWED_METADATA_KEYS）
        """
        metadata: Dict[str, Dict[str, Any]] = {}
        
        for col in df.columns:
            if col == "timestamp":
                continue
            
            # 取得原始 metadata
            raw_meta = self._extract_raw_metadata(col)
            
            # 白名單過濾
            sanitized = {
                k: v for k, v in raw_meta.items()
                if k in ALLOWED_METADATA_KEYS
            }
            
            metadata[col] = sanitized
        
        return metadata
    
    def _extract_raw_metadata(self, column_name: str) -> Dict[str, Any]:
        """從 Annotation 提取原始 Metadata（含 v1.4 拓樸欄位）"""
        if not self.annotation:
            return {"column_name": column_name}
        
        anno = self.annotation.get_column_annotation(column_name)
        if not anno:
            return {"column_name": column_name}
        
        # 🆕 v1.4: 擴充提取 GNN 拓樸欄位
        return {
            "column_name": column_name,
            "physical_type": anno.physical_type.value if anno.physical_type else None,
            "unit": anno.unit,
            "description": anno.description,
            # 🆕 GNN 拓樸欄位
            "topology_node_id": getattr(anno, 'topology_node_id', None),
            "control_semantic": getattr(anno, 'control_semantic', None),
            "decay_factor": getattr(anno, 'decay_factor', None),
        }
    
    # =========================================================================
    # 工具方法
    # =========================================================================
    
    def _enforce_schema_sanitization(self, df: pl.DataFrame) -> pl.DataFrame:
        """強制移除禁止欄位"""
        cols_to_drop = [col for col in FORBIDDEN_COLS if col in df.columns]
        if cols_to_drop:
            logger.warning(f"E500: 自動移除禁止欄位: {cols_to_drop}")
            df = df.drop(*cols_to_drop)
        return df
    
    def _is_snake_case(self, s: str) -> bool:
        """
        檢查字串是否符合 snake_case 規範
        
        支援 ASCII 和中文前綴（如 col_1號冰水主機）
        """
        # 支援 ASCII 小寫開頭，或 col_ 前綴後接中文
        return bool(re.match(r'^[a-z][a-z0-9_]*$', s)) or \
               bool(re.match(r'^col_[\w\u4e00-\u9fff][\w\u4e00-\u9fff0-9_]*$', s))
    
    def _get_device_role(self, column_name: str) -> str:
        """取得欄位的 device_role（預設 primary）"""
        if not self.annotation:
            return "primary"
        
        role = self.annotation.get_device_role(column_name)
        return role or "primary"
    
    def _get_columns_by_physical_type(self, physical_type: str) -> List[str]:
        """依 physical_type 取得欄位列表"""
        if not self.annotation:
            return []
        
        # 從所有標註中篩選
        result = []
        for col_name in self.annotation.get_all_columns():
            anno = self.annotation.get_column_annotation(col_name)
            if anno and anno.physical_type and anno.physical_type.value == physical_type:
                result.append(col_name)
        
        return result
    
    # =========================================================================
    # 向下相容性
    # =========================================================================
    
    def clean_data(self, df: pl.DataFrame, **kwargs) -> pl.DataFrame:
        """
        舊版 clean_data 介面（向下相容）
        
        注意: 不支援新功能（設備邏輯預檢、Metadata 輸出）
        """
        logger.warning(
            "clean_data() 已棄用，請改用 clean()。"
            "新功能（設備邏輯預檢、稽核軌跡）需要 clean() 介面。"
        )
        df_clean, _, _ = self.clean(df)
        return df_clean


# =============================================================================
# 簡易工廠函數
# =============================================================================

def create_cleaner(
    site_id: str,
    pipeline_context: PipelineContext,
    enforce_equipment_validation: bool = True
) -> DataCleaner:
    """
    建立標準 DataCleaner 實例
    
    Args:
        site_id: 案場 ID
        pipeline_context: PipelineContext 實例
        enforce_equipment_validation: 是否啟用設備邏輯預檢
        
    Returns:
        配置完成的 DataCleaner 實例
    """
    from src.features.annotation_manager import FeatureAnnotationManager
    
    config = CleanerConfig(
        enforce_equipment_validation_sync=enforce_equipment_validation
    )
    
    annotation_manager = FeatureAnnotationManager(
        site_id=site_id,
        temporal_context=pipeline_context
    )
    
    return DataCleaner(
        config=config,
        annotation_manager=annotation_manager,
        pipeline_context=pipeline_context,
        site_id=site_id
    )


# =============================================================================
# 測試入口
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # 簡易測試
    print("DataCleaner v2.2 - 簡易測試")
    print("=" * 50)
    
    # 建立測試資料
    test_df = pl.DataFrame({
        "timestamp": pl.datetime_range(
            start=datetime.now(timezone.utc) - timedelta(hours=1),
            end=datetime.now(timezone.utc),
            interval="5m",
            time_zone="UTC"
        ),
        "chiller_1_kw": [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0],
        "chiller_1_status": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
        "pump_1_status": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    })
    
    print(f"測試資料: {test_df.shape[0]} 行 x {test_df.shape[1]} 列")
    print(test_df.head())
    
    # 初始化 Context
    context = PipelineContext()
    try:
        context.initialize()
    except RuntimeError:
        pass  # 已初始化
    
    # 建立 Cleaner（無 Annotation）
    config = CleanerConfig(enforce_equipment_validation_sync=True)
    cleaner = DataCleaner(config=config, pipeline_context=context)
    
    try:
        df_clean, metadata, audit = cleaner.clean(test_df)
        print("\n清洗成功!")
        print(f"輸出: {df_clean.shape[0]} 行 x {df_clean.shape[1]} 列")
        print(f"稽核軌跡: {audit}")
    except Exception as e:
        print(f"\n錯誤: {e}")
