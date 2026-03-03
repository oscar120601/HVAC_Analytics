"""
特徵工程模組 (Feature Engineer) v1.4 - 拓樸感知與控制語意

此模組負責：
1. 從 Manifest 讀取 BatchProcessor 輸出
2. 生成 L0/L1/L2/L3 分層特徵
3. 支援拓樸聚合特徵 (上游設備特徵聚合)
4. 支援控制偏差特徵 (Sensor-Setpoint 偏差)
5. 輸出 GNN Ready 的設備連接矩陣

錯誤代碼:
- E301-E306: 輸入契約錯誤
- E400: Annotation 版本不符
- E413: Topology 版本不符
- E420: Control Semantics 版本不符
- E500: device_role 洩漏
- E601: feature_order_manifest 未記錄
- E602: scaler_params 遺失
"""

from typing import Dict, List, Optional, Union, Final, Tuple, Any
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
import math

import polars as pl
import polars.selectors as cs
import numpy as np
from pydantic import BaseModel

# SSOT 嚴格引用
from src.etl.config_models import (
    VALID_QUALITY_FLAGS,
    TIMESTAMP_CONFIG,
    FeatureEngineeringConfig,
    TopologyAggregationConfig,
    ControlDeviationConfig,
    FEATURE_ANNOTATION_CONSTANTS,
    ERROR_CODES
)
from src.etl.manifest import Manifest
from src.features.annotation_manager import FeatureAnnotationManager, ColumnAnnotation
from src.features.topology_manager import TopologyManager
from src.features.control_semantics_manager import ControlSemanticsManager
from src.utils.logger import get_logger


class ContractViolationError(Exception):
    """契約違反錯誤"""
    pass


class ConfigurationError(Exception):
    """配置錯誤"""
    pass


class DataLeakageRiskError(Exception):
    """Data Leakage 風險錯誤"""
    pass


@dataclass
class FeatureMetadata:
    """特徵元資料"""
    name: str
    physical_type: str
    unit: Optional[str]
    layer: str  # L0/L1/L2/L3
    source_columns: List[str]
    generation_params: Dict[str, Any] = field(default_factory=dict)


# 🆕 Group Policy Rule 類別（PRD v1.4 Group Policy 解耦）
@dataclass
class TopologyAggregationRule:
    """拓樸聚合規則"""
    source_equipment: str  # 設備 ID
    physical_type: str  # 物理量類型
    upstream_equipment: List[str]  # 上游設備列表
    aggregation: List[str]  # 聚合函數列表 ["mean", "max", "min", "std"]


@dataclass
class ControlDeviationRule:
    """控制偏差規則"""
    sensor_column: str
    setpoint_column: str
    deviation_types: List[str]  # ["basic", "absolute", "sign", "rate", "integral", "decay_smoothed"]


class FeatureEngineer:
    """
    Feature Engineer v1.4 - 拓樸感知與控制語意整合
    
    核心職責：
    1. 從 Manifest 讀取物理屬性 (physical_type, unit)
    2. 直接查詢 Annotation SSOT 取得 device_role 與 ignore_warnings
    3. 透過 TopologyManager 取得設備連接關係，生成拓樸聚合特徵
    4. 透過 ControlSemanticsManager 取得控制對，生成控制偏差特徵
    5. 應用語意感知的 Group Policy
    6. 輸出 GNN Ready 的設備連接矩陣
    7. 確保不產生 Data Leakage
    """
    
    def __init__(
        self, 
        config: FeatureEngineeringConfig,
        site_id: str,
        yaml_base_dir: str = "config/features/sites",
        is_training: bool = False
    ):
        """
        初始化 Feature Engineer
        
        Args:
            config: 特徵工程配置
            site_id: 案場 ID
            yaml_base_dir: YAML 配置基礎目錄
            is_training: 是否為訓練模式
        """
        self.config = config
        self.site_id = site_id
        self.is_training = is_training
        self.logger = get_logger("FeatureEngineer")
        
        # 初始化 AnnotationManager
        self.annotation_manager = FeatureAnnotationManager(
            site_id=site_id,
            config_root=Path(yaml_base_dir).parent if yaml_base_dir else None
        )
        
        # 初始化 TopologyManager
        self.topology_manager = TopologyManager(self.annotation_manager)
        
        # 初始化 ControlSemanticsManager
        self.control_semantics_manager = ControlSemanticsManager(self.annotation_manager)
        
        # 驗證拓樸圖完整性
        self._validate_topology_graph()
        
        # 儲存生成的特徵資訊
        self.topology_features: List[Dict] = []
        self.control_deviation_features: List[Dict] = []
        self.scaler_params: Dict[str, Any] = {}
        self.model_artifact: Optional[Dict] = None
        
        # resolved_policies 用於 Group Policy 解耦
        self.resolved_policies: Dict[str, Any] = {}
        
        self.logger.info(
            f"初始化 FeatureEngineer v1.4 "
            f"(Annotation: {self.annotation_manager.get_schema_version()}, "
            f"拓樸節點: {self.topology_manager.get_node_count()}, "
            f"控制對: {self.control_semantics_manager.get_pair_count()}, "
            f"訓練模式: {is_training})"
        )
    
    def _validate_topology_graph(self):
        """
        驗證拓樸圖完整性 (E411)
        """
        if self.topology_manager.has_cycle():
            cycles = self.topology_manager.detect_cycles()
            raise ConfigurationError(
                f"E411: 拓樸圖存在循環: {cycles}. "
                f"請檢查 Feature Annotation 中的 upstream_equipment_id 設定。"
            )
    
    def load_from_batch_processor(
        self, 
        manifest_path: Union[str, Path]
    ) -> Tuple[pl.DataFrame, Dict, Dict]:
        """
        從 BatchProcessor 輸出載入資料
        
        Args:
            manifest_path: Manifest 檔案路徑
            
        Returns:
            (df, feature_metadata, annotation_audit_trail)
            
        Raises:
            ContractViolationError: E301, E302, E303
            ConfigurationError: E400, E413, E420
        """
        manifest_path = Path(manifest_path)
        
        if not manifest_path.exists():
            raise ContractViolationError(f"E301: Manifest 檔案不存在: {manifest_path}")
        
        # 1. 解析 Manifest
        try:
            manifest = Manifest.parse_file(manifest_path)
        except Exception as e:
            raise ContractViolationError(f"E301: Manifest 解析失敗: {e}")
        
        # 2. 驗證 Manifest 完整性
        if hasattr(manifest, 'validate_checksum') and not manifest.validate_checksum():
            raise ContractViolationError("E301: Manifest checksum 驗證失敗")
        
        # 3. 驗證 Annotation 稽核軌跡
        audit = manifest.annotation_audit_trail if hasattr(manifest, 'annotation_audit_trail') else {}
        self.validate_annotation_compatibility(audit)
        
        # 4. 讀取 Parquet 檔案
        if not manifest.output_files:
            raise ContractViolationError("E301: Manifest 無 output_files")
        
        files = [manifest_path.parent / f for f in manifest.output_files]
        df = pl.read_parquet(files)
        
        # 5. 驗證 Schema (E302)
        self._validate_schema(df)
        
        # 6. 驗證 quality_flags (E303)
        if 'quality_flags' in df.columns:
            self._validate_quality_flags(df)
        
        # 7. 檢查 device_role 洩漏 (E500)
        if 'device_role' in df.columns:
            raise ContractViolationError("E500: DataFrame 包含 device_role，違反契約")
        
        # 8. 記憶體優化
        if self.config.memory_optimization:
            df = self._optimize_memory_dtype(df)
        
        # 9. 取得 feature_metadata
        feature_metadata = manifest.feature_metadata if hasattr(manifest, 'feature_metadata') else {}
        
        self.logger.info(
            f"載入資料完成: {len(df)} 行 x {len(df.columns)} 列, "
            f"時間範圍 {df['timestamp'].min()} ~ {df['timestamp'].max()}"
        )
        
        return df, feature_metadata, audit
    
    def validate_annotation_compatibility(self, audit_trail):
        """
        驗證 Annotation 版本相容性 (E400, E413, E420)
        
        audit_trail 可能是 AnnotationAuditTrail Pydantic 物件或舊式 dict。
        """
        if not audit_trail:
            self.logger.warning("Manifest 缺少 annotation_audit_trail")
            return
        
        # 相容 Pydantic 模型與 dict 兩種格式
        def _get(obj, key, default=None):
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)
        
        # 驗證基礎 Schema 版本
        schema_ver = _get(audit_trail, 'schema_version')
        expected = FEATURE_ANNOTATION_CONSTANTS.get('expected_schema_version', '1.4')
        
        if schema_ver and schema_ver != 'unknown' and schema_ver != expected:
            raise ConfigurationError(
                f"E400: Annotation Schema 版本不符。期望: {expected}, 實際: {schema_ver}"
            )
        
        # 驗證拓樸版本
        topo_ver = _get(audit_trail, 'topology_version')
        if topo_ver and topo_ver != "1.0":
            raise ConfigurationError(
                f"E413: Topology 版本不符。期望: 1.0, 實際: {topo_ver}"
            )
        
        # 驗證控制語意版本
        ctrl_ver = _get(audit_trail, 'control_semantics_version')
        if ctrl_ver and ctrl_ver != "1.0":
            raise ConfigurationError(
                f"E420: Control Semantics 版本不符。期望: 1.0, 實際: {ctrl_ver}"
            )
    
    def _validate_schema(self, df: pl.DataFrame):
        """
        驗證 DataFrame Schema (E302)
        """
        # 檢查必要欄位
        if 'timestamp' not in df.columns:
            raise ContractViolationError("E302: 缺少必要欄位 'timestamp'")
        
        # 檢查 timestamp 類型
        timestamp_dtype = df['timestamp'].dtype
        if not str(timestamp_dtype).startswith('Datetime'):
            raise ContractViolationError(f"E302: timestamp 類型錯誤: {timestamp_dtype}")
        
        # 檢查時區
        # Note: Polars Datetime 類型的時區檢查較為複雜，這裡簡化處理
        
    def _validate_quality_flags(self, df: pl.DataFrame):
        """
        驗證 quality_flags (E303)
        """
        # 收集所有唯一的 flags
        all_flags = set()
        for flags in df['quality_flags'].drop_nulls():
            if isinstance(flags, list):
                all_flags.update(flags)
            elif isinstance(flags, str):
                all_flags.add(flags)
        
        # 檢查未知 flags
        unknown = all_flags - set(VALID_QUALITY_FLAGS)
        if unknown:
            self.logger.warning(f"E303: 未知的 quality_flags: {unknown}")
    
    def _optimize_memory_dtype(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        記憶體優化：僅針對 Float 類型進行降級（PRD v1.4 修正）
        
        🆕 修正：使用 cs.float() 取代 cs.numeric()，避免整數型別被強制轉型
        原因：cs.numeric() 包含 Int64, Int32 等離散數值，轉為 Float32 會造成精度流失
        
        Args:
            df: 原始 DataFrame
            
        Returns:
            記憶體優化後的 DataFrame
        """
        # 🆕 修正：只選取 Float 類型（排除整數、布林等離散數值）
        float_cols = df.select(cs.float()).columns
        exclude_cols = ['timestamp', 'quality_flags']
        cols_to_optimize = [c for c in float_cols if c not in exclude_cols]
        
        if not cols_to_optimize:
            return df
        
        cast_exprs = [pl.col(c).cast(pl.Float32) for c in cols_to_optimize]
        df_optimized = df.with_columns(cast_exprs)
        
        original_size = df.estimated_size()
        optimized_size = df_optimized.estimated_size()
        saved_mb = (original_size - optimized_size) / (1024 * 1024)
        
        if saved_mb > 10:
            self.logger.info(
                f"記憶體優化: Float 欄位轉型為 Float32，"
                f"預估節省 {saved_mb:.1f} MB"
            )
        
        return df_optimized

    # ==========================================================================
    # L1 特徵生成: Lag, Rolling, Diff
    # ==========================================================================
    
    def generate_lag_features(
        self, 
        df: pl.DataFrame,
        target_columns: Optional[List[str]] = None
    ) -> Tuple[pl.DataFrame, List[str]]:
        """
        生成 Lag 特徵
        
        Args:
            df: 輸入 DataFrame
            target_columns: 目標欄位列表（None=所有數值欄位）
            
        Returns:
            (df_with_lags, generated_feature_names)
        """
        if not self.config.lag_enabled:
            return df, []
        
        if target_columns is None:
            # 自動選擇數值欄位（排除 timestamp, quality_flags）
            numeric_cols = df.select(cs.numeric()).columns
            target_columns = [c for c in numeric_cols if c not in ['timestamp', 'quality_flags']]
        
        expressions = []
        generated_features = []
        
        for col in target_columns:
            if col not in df.columns:
                continue
                
            # 檢查是否為目標變數（不可生成 Lag）
            anno = self.annotation_manager.get_column_annotation(col)
            if anno and getattr(anno, 'is_target', False):
                continue
            
            # 取得 lag 間隔（從 annotation 或配置）
            lag_intervals = self.config.lag_intervals
            if anno and getattr(anno, 'lag_intervals', None):
                lag_intervals = anno.lag_intervals
            
            for lag in lag_intervals:
                feature_name = f"{col}_lag_{lag}"
                expr = pl.col(col).shift(lag).alias(feature_name)
                expressions.append(expr)
                generated_features.append(feature_name)
        
        if expressions:
            df = df.with_columns(expressions)
            # 前向填充 Null（避免初始 Null 影響 Rolling）
            df = df.with_columns(
                cs.starts_with("_lag_").fill_null(strategy="forward")
            )
            self.logger.info(f"生成 {len(generated_features)} 個 Lag 特徵")
        
        return df, generated_features
    
    def generate_rolling_features(
        self,
        df: pl.DataFrame,
        target_columns: Optional[List[str]] = None
    ) -> Tuple[pl.DataFrame, List[str]]:
        """
        生成 Rolling 特徵
        
        Args:
            df: 輸入 DataFrame
            target_columns: 目標欄位列表
            
        Returns:
            (df_with_rolling, generated_feature_names)
        """
        if not self.config.rolling_enabled:
            return df, []
        
        if target_columns is None:
            numeric_cols = df.select(cs.numeric()).columns
            target_columns = [c for c in numeric_cols if c not in ['timestamp', 'quality_flags']]
        
        expressions = []
        generated_features = []
        
        for col in target_columns:
            if col not in df.columns:
                continue
            
            for window in self.config.rolling_windows:
                for func in self.config.rolling_functions:
                    feature_name = f"{col}_rolling_{func}_{window}"
                    
                    if func == "mean":
                        expr = pl.col(col).rolling_mean(window_size=window, min_periods=1).alias(feature_name)
                    elif func == "std":
                        expr = pl.col(col).rolling_std(window_size=window, min_periods=1).alias(feature_name)
                    elif func == "min":
                        expr = pl.col(col).rolling_min(window_size=window, min_periods=1).alias(feature_name)
                    elif func == "max":
                        expr = pl.col(col).rolling_max(window_size=window, min_periods=1).alias(feature_name)
                    elif func == "sum":
                        expr = pl.col(col).rolling_sum(window_size=window, min_periods=1).alias(feature_name)
                    else:
                        continue
                    
                    expressions.append(expr)
                    generated_features.append(feature_name)
        
        if expressions:
            df = df.with_columns(expressions)
            self.logger.info(f"生成 {len(generated_features)} 個 Rolling 特徵")
        
        return df, generated_features
    
    def generate_diff_features(
        self,
        df: pl.DataFrame,
        target_columns: Optional[List[str]] = None
    ) -> Tuple[pl.DataFrame, List[str]]:
        """
        生成差分特徵
        
        Args:
            df: 輸入 DataFrame
            target_columns: 目標欄位列表
            
        Returns:
            (df_with_diff, generated_feature_names)
        """
        if not self.config.diff_enabled:
            return df, []
        
        if target_columns is None:
            numeric_cols = df.select(cs.numeric()).columns
            target_columns = [c for c in numeric_cols if c not in ['timestamp', 'quality_flags']]
        
        expressions = []
        generated_features = []
        
        for col in target_columns:
            if col not in df.columns:
                continue
            
            for order in self.config.diff_orders:
                feature_name = f"{col}_diff_{order}"
                expr = pl.col(col).diff(n=order).alias(feature_name)
                expressions.append(expr)
                generated_features.append(feature_name)
        
        if expressions:
            df = df.with_columns(expressions)
            # 差分特徵的 Null 填充為 0
            df = df.with_columns(cs.starts_with("_diff_").fill_null(0.0))
            self.logger.info(f"生成 {len(generated_features)} 個 Diff 特徵")
        
        return df, generated_features
    
    def generate_temporal_features(self, df: pl.DataFrame) -> Tuple[pl.DataFrame, List[str]]:
        """
        生成時間特徵
        
        Args:
            df: 輸入 DataFrame
            
        Returns:
            (df_with_temporal, generated_feature_names)
        """
        if 'timestamp' not in df.columns:
            return df, []
        
        expressions = [
            pl.col('timestamp').dt.hour().alias('hour_of_day'),
            pl.col('timestamp').dt.weekday().alias('day_of_week'),
            pl.col('timestamp').dt.month().alias('month'),
            pl.col('timestamp').dt.ordinal_day().alias('day_of_year'),
        ]
        
        # 週期性編碼
        expressions.extend([
            (pl.col('timestamp').dt.hour() * 2 * 3.14159 / 24).sin().alias('hour_sin'),
            (pl.col('timestamp').dt.hour() * 2 * 3.14159 / 24).cos().alias('hour_cos'),
            (pl.col('timestamp').dt.weekday() * 2 * 3.14159 / 7).sin().alias('dow_sin'),
            (pl.col('timestamp').dt.weekday() * 2 * 3.14159 / 7).cos().alias('dow_cos'),
        ])
        
        df = df.with_columns(expressions)
        generated_features = ['hour_of_day', 'day_of_week', 'month', 'day_of_year',
                             'hour_sin', 'hour_cos', 'dow_sin', 'dow_cos']
        
        self.logger.info(f"生成 {len(generated_features)} 個時間特徵")
        return df, generated_features

    # ==========================================================================
    # L2 特徵生成: 拓樸聚合
    # ==========================================================================
    
    def generate_topology_aggregation_features(
        self,
        df: pl.DataFrame
    ) -> Tuple[pl.DataFrame, List[Dict]]:
        """
        生成拓樸聚合特徵 (L2 Features)
        
        對每個設備，找出其上游設備，聚合上游設備的特徵。
        
        🆕 修正：支援 Group Policy 解耦，優先使用 resolved_policies（PRD v1.4）
        
        Args:
            df: 輸入 DataFrame
            
        Returns:
            (df_with_topology_features, feature_metadata_list)
        """
        config = self.config.topology_aggregation
        if not config or not config.enabled:
            return df, []
        
        # 🆕 優先使用已解析的 Group Policies（PRD v1.4 Group Policy 解耦）
        if hasattr(self, 'resolved_policies') and self.resolved_policies:
            return self._generate_topology_from_resolved_policies(df, config)
        
        expressions = []
        generated_features = []
        
        # 取得所有設備
        all_equipment = self.topology_manager.get_all_equipment()
        
        for equipment_id in all_equipment:
            # 取得該設備的上游設備
            upstream_equipment = self.topology_manager.get_upstream_equipment(equipment_id)
            
            if not upstream_equipment:
                continue
            
            # 對每個 physical_type 進行聚合
            for physical_type in config.target_physical_types:
                # 取得上游設備的該類型欄位
                upstream_columns = []
                for up_eq in upstream_equipment:
                    cols = self.annotation_manager.get_columns_by_equipment_id(up_eq)
                    for col in cols:
                        anno = self.annotation_manager.get_column_annotation(col)
                        if anno and anno.physical_type == physical_type:
                            if col in df.columns:
                                upstream_columns.append(col)
                
                if not upstream_columns:
                    continue
                
                # 檢查最小有效來源數
                if len(upstream_columns) < config.min_valid_sources:
                    continue
                
                # 生成聚合特徵
                eq_id_normalized = equipment_id.lower().replace('-', '_')
                
                for agg_func in config.aggregation_functions:
                    feature_name = f"{eq_id_normalized}_upstream_{physical_type}_{agg_func}"
                    
                    if agg_func == "mean":
                        expr = pl.mean_horizontal(upstream_columns).alias(feature_name)
                    elif agg_func == "max":
                        expr = pl.max_horizontal(upstream_columns).alias(feature_name)
                    elif agg_func == "min":
                        expr = pl.min_horizontal(upstream_columns).alias(feature_name)
                    elif agg_func == "std":
                        expr = (
                            pl.concat_list(upstream_columns)
                            .list.eval(pl.element().std(ddof=0))
                            .list.get(0)
                            .alias(feature_name)
                        )
                    else:
                        continue
                    
                    expressions.append(expr)
                    generated_features.append({
                        "name": feature_name,
                        "type": "topology_aggregation",
                        "source_equipment": equipment_id,
                        "upstream_equipment": upstream_equipment,
                        "physical_type": physical_type,
                        "aggregation": agg_func,
                        "source_columns": upstream_columns
                    })
        
        if expressions:
            df = df.with_columns(expressions)
            self.topology_features = generated_features
            
            # 拓樸特徵時間序列連續性填充
            df = df.with_columns(
                cs.starts_with("_upstream_")
                .fill_null(strategy="forward")
                .fill_null(0.0)
            )
            
            self.logger.info(f"生成 {len(generated_features)} 個拓樸聚合特徵")
        
        return df, generated_features
    
    def _generate_topology_from_resolved_policies(
        self,
        df: pl.DataFrame,
        config: TopologyAggregationConfig
    ) -> Tuple[pl.DataFrame, List[Dict]]:
        """
        🆕 從已解析的 Group Policies 生成拓樸聚合特徵（PRD v1.4 Group Policy 解耦）
        
        實現 Group Policy 與手動生成的解耦，統一使用 resolved_policies 的輸出。
        參考 PRD v1.4 第 733-836 節。
        
        Args:
            df: 輸入 DataFrame
            config: 拓樸聚合配置
            
        Returns:
            (df_with_topology_features, feature_metadata_list)
        """
        expressions = []
        generated_features = []
        
        # 取得最小有效來源數量配置
        min_valid_sources = getattr(config, 'min_valid_sources', 1)
        
        # 從 resolved_policies 中篩選拓樸聚合規則
        for rule_id, rule in self.resolved_policies.items():
            if not isinstance(rule, TopologyAggregationRule):
                continue
            
            # 提取規則參數（設備級，非感測器級）
            source_equipment = rule.source_equipment
            physical_type = rule.physical_type
            upstream_equipment = rule.upstream_equipment
            agg_funcs = rule.aggregation
            
            # 收集上游設備的欄位（嚴格匹配物理量類型）
            upstream_columns = []
            for up_eq in upstream_equipment:
                cols = self.annotation_manager.get_columns_by_equipment_id(up_eq)
                for col in cols:
                    anno = self.annotation_manager.get_column_annotation(col)
                    # 嚴格匹配 physical_type
                    if anno and anno.physical_type == physical_type:
                        if col in df.columns:
                            upstream_columns.append(col)
            
            # 最小有效來源數量檢查
            if len(upstream_columns) < min_valid_sources:
                self.logger.warning(
                    f"規則 {rule_id}: 上游可用欄位數量 ({len(upstream_columns)}) "
                    f"低於最小有效來源數量 ({min_valid_sources})，跳過聚合"
                )
                continue
            
            # 迭代聚合函數清單
            for agg_func in agg_funcs:
                # GNN 對齊的命名格式: {eq_id}_upstream_{phys_type}_{agg}
                feature_name = f"{source_equipment.lower().replace('-', '_')}_upstream_{physical_type}_{agg_func}"
                
                # 根據聚合函數生成表達式
                if agg_func == "mean":
                    expr = pl.mean_horizontal(upstream_columns).alias(feature_name)
                elif agg_func == "max":
                    expr = pl.max_horizontal(upstream_columns).alias(feature_name)
                elif agg_func == "min":
                    expr = pl.min_horizontal(upstream_columns).alias(feature_name)
                elif agg_func == "std":
                    expr = (
                        pl.concat_list(upstream_columns)
                        .list.eval(pl.element().std(ddof=0))
                        .list.get(0)
                        .alias(feature_name)
                    )
                else:
                    continue
                
                expressions.append(expr)
                generated_features.append({
                    "name": feature_name,
                    "type": "topology_aggregation",
                    "source_equipment": source_equipment,
                    "physical_type": physical_type,
                    "upstream_equipment": upstream_equipment,
                    "aggregation": agg_func,
                    "source_columns": upstream_columns
                })
        
        if expressions:
            df = df.with_columns(expressions)
            self.topology_features = generated_features
            self.logger.info(f"從 resolved_policies 生成 {len(generated_features)} 個拓樸特徵")
            
            # 拓樸特徵時間序列連續性填充
            # 注意：forward fill 對拓樸聚合特徵無 Look-ahead Bias 疑慮
            # 因為這是利用「過去已存在的觀測值」填補「當下缺漏」，不涉及未來資料
            df = df.with_columns(
                cs.starts_with("_upstream_")
                .fill_null(strategy="forward")
                .fill_null(0.0)
            )
        
        return df, generated_features
    
    # ==========================================================================
    # L3 特徵生成: 控制偏差
    # ==========================================================================
    
    def generate_control_deviation_features(
        self,
        df: pl.DataFrame
    ) -> Tuple[pl.DataFrame, List[Dict]]:
        """
        生成控制偏差特徵 (L3 Features)
        
        計算 Sensor-Setpoint 之間的偏差。
        
        Args:
            df: 輸入 DataFrame
            
        Returns:
            (df_with_deviation_features, feature_metadata_list)
        """
        config = self.config.control_deviation
        if not config or not config.enabled:
            return df, []
        
        expressions = []
        generated_features = []
        
        # 取得所有控制對
        control_pairs = self.control_semantics_manager.get_all_pairs()
        
        for pair in control_pairs:
            sensor_col = pair.sensor_column
            setpoint_col = pair.setpoint_column
            
            # 檢查欄位存在
            if sensor_col not in df.columns or setpoint_col not in df.columns:
                continue
            
            prefix = f"delta_{sensor_col}"
            
            for dev_type in config.deviation_types:
                if dev_type == "basic":
                    feature_name = prefix
                    expr = (pl.col(sensor_col) - pl.col(setpoint_col)).alias(feature_name)
                    expressions.append(expr)
                    generated_features.append({
                        "name": feature_name, "type": "control_deviation", "subtype": "basic",
                        "sensor": sensor_col, "setpoint": setpoint_col
                    })
                
                elif dev_type == "absolute":
                    feature_name = f"{prefix}_abs"
                    expr = (pl.col(sensor_col) - pl.col(setpoint_col)).abs().alias(feature_name)
                    expressions.append(expr)
                    generated_features.append({
                        "name": feature_name, "type": "control_deviation", "subtype": "absolute"
                    })
                
                elif dev_type == "sign":
                    feature_name = f"{prefix}_sign"
                    expr = (pl.col(sensor_col) - pl.col(setpoint_col)).sign().alias(feature_name)
                    expressions.append(expr)
                    generated_features.append({
                        "name": feature_name, "type": "control_deviation", "subtype": "sign"
                    })
                
                elif dev_type == "rate" and "timestamp" in df.columns:
                    feature_name = f"{prefix}_rate"
                    expr = (pl.col(sensor_col) - pl.col(setpoint_col)).diff().alias(feature_name)
                    expressions.append(expr)
                    generated_features.append({
                        "name": feature_name, "type": "control_deviation", "subtype": "rate"
                    })
                
                elif dev_type == "integral":
                    feature_name = f"{prefix}_integral"
                    integral_window = config.integral_window
                    expr = (
                        (pl.col(sensor_col) - pl.col(setpoint_col))
                        .fill_null(0.0)
                        .rolling_sum(window_size=integral_window, min_periods=1)
                        .alias(feature_name)
                    )
                    expressions.append(expr)
                    generated_features.append({
                        "name": feature_name, "type": "control_deviation", 
                        "subtype": "integral", "window": integral_window
                    })
                
                elif dev_type == "decay_smoothed":
                    feature_name = f"{prefix}_decay"
                    decay_alpha = config.decay_alpha
                    expr = (
                        (pl.col(sensor_col) - pl.col(setpoint_col))
                        .ewm_mean(alpha=decay_alpha, min_periods=1)
                        .alias(feature_name)
                    )
                    expressions.append(expr)
                    generated_features.append({
                        "name": feature_name, "type": "control_deviation",
                        "subtype": "decay_smoothed", "alpha": decay_alpha
                    })
        
        if expressions:
            df = df.with_columns(expressions)
            self.control_deviation_features = generated_features
            
            # 控制偏差特徵的 Null 填充
            df = df.with_columns(
                cs.starts_with("delta_")
                .fill_null(strategy="forward")
                .fill_null(0.0)
            )
            
            self.logger.info(f"生成 {len(generated_features)} 個控制偏差特徵")
        
        return df, generated_features

    # ==========================================================================
    # 特徵縮放
    # ==========================================================================
    
    def fit_scaler(self, df: pl.DataFrame, feature_columns: List[str]) -> Dict[str, Any]:
        """
        擬合特徵縮放參數
        
        Args:
            df: 訓練資料 DataFrame
            feature_columns: 要縮放的特徵欄位
            
        Returns:
            縮放參數字典
        """
        if not self.config.scaling_enabled:
            return {}
        
        scaler_params = {
            "method": self.config.scaling_method,
            "features": {}
        }
        
        for col in feature_columns:
            if col not in df.columns:
                continue
            
            series = df[col]
            
            if self.config.scaling_method == "standard":
                mean_val = series.mean()
                std_val = series.std()
                if std_val is None or std_val == 0:
                    std_val = 1.0
                scaler_params["features"][col] = {
                    "mean": float(mean_val) if mean_val is not None else 0.0,
                    "std": float(std_val),
                    "method": "standard"
                }
            
            elif self.config.scaling_method == "minmax":
                min_val = series.min()
                max_val = series.max()
                if min_val is None:
                    min_val = 0.0
                if max_val is None or max_val == min_val:
                    max_val = min_val + 1.0
                scaler_params["features"][col] = {
                    "min": float(min_val),
                    "max": float(max_val),
                    "method": "minmax"
                }
            
            elif self.config.scaling_method == "robust":
                median_val = series.median()
                q25 = series.quantile(0.25)
                q75 = series.quantile(0.75)
                iqr = q75 - q25 if q75 and q25 else 1.0
                if iqr == 0:
                    iqr = 1.0
                scaler_params["features"][col] = {
                    "median": float(median_val) if median_val is not None else 0.0,
                    "iqr": float(iqr),
                    "method": "robust"
                }
        
        self.scaler_params = scaler_params
        self.logger.info(f"擬合 {len(scaler_params['features'])} 個特徵的縮放參數")
        return scaler_params
    
    def transform_scaler(self, df: pl.DataFrame, scaler_params: Dict[str, Any]) -> pl.DataFrame:
        """
        應用特徵縮放
        
        Args:
            df: 輸入 DataFrame
            scaler_params: 縮放參數
            
        Returns:
            縮放後的 DataFrame
        """
        if not scaler_params or not scaler_params.get("features"):
            return df
        
        expressions = []
        
        for col, params in scaler_params["features"].items():
            if col not in df.columns:
                continue
            
            method = params.get("method", "standard")
            
            if method == "standard":
                mean_val = params["mean"]
                std_val = params["std"]
                expr = ((pl.col(col) - mean_val) / std_val).alias(f"{col}_scaled")
            
            elif method == "minmax":
                min_val = params["min"]
                max_val = params["max"]
                range_val = max_val - min_val
                if range_val == 0:
                    range_val = 1.0
                expr = ((pl.col(col) - min_val) / range_val).alias(f"{col}_scaled")
            
            elif method == "robust":
                median_val = params["median"]
                iqr = params["iqr"]
                expr = ((pl.col(col) - median_val) / iqr).alias(f"{col}_scaled")
            
            else:
                continue
            
            expressions.append(expr)
        
        if expressions:
            df = df.with_columns(expressions)
            self.logger.info(f"縮放 {len(expressions)} 個特徵")
        
        return df
    
    # ==========================================================================
    # GNN 資料匯出
    # ==========================================================================
    
    def export_gnn_data(
        self,
        df: pl.DataFrame,
        output_format: str = "both"
    ) -> Dict[str, Any]:
        """
        匯出 GNN 訓練資料
        
        Args:
            df: 特徵工程後的 DataFrame
            output_format: 輸出格式 (static/timeline/both)
            
        Returns:
            GNN 資料字典
        """
        if not self.config.gnn_enabled:
            return {}
        
        # 取得拓樸資訊
        adjacency_matrix = self.topology_manager.get_adjacency_matrix()
        edge_index = self.topology_manager.get_edge_index()
        equipment_to_idx = self.topology_manager.get_equipment_to_idx()
        idx_to_equipment = self.topology_manager.get_idx_to_equipment()
        node_types = self.topology_manager.get_node_type_list()
        
        gnn_data = {
            "num_nodes": len(equipment_to_idx),
            "num_edges": len(edge_index[0]) if len(edge_index.shape) > 1 else 0,
            "adjacency_matrix": adjacency_matrix,
            "edge_index": edge_index,
            "equipment_to_idx": equipment_to_idx,
            "idx_to_equipment": idx_to_equipment,
            "node_types": node_types,
        }
        
        # 收集每個設備的特徵
        equipment_features = self._collect_equipment_features(df, equipment_to_idx)
        gnn_data["equipment_features"] = equipment_features
        
        # 生成 3D Tensor (timeline format)
        # 🆕 修正：回傳 Tuple[np.ndarray, List[str]]，需解包
        if output_format in ["timeline", "both"]:
            tensor_3d, node_types_3d = self._generate_3d_tensor(
                df, equipment_to_idx, equipment_features, 
                stride=self.config.gnn_stride if hasattr(self.config, 'gnn_stride') else 1
            )
            gnn_data["tensor_3d"] = tensor_3d
            # 確保 node_types 一致性
            if node_types_3d:
                gnn_data["node_types"] = node_types_3d
        
        self.logger.info(
            f"GNN 資料匯出: 節點={gnn_data['num_nodes']}, "
            f"邊={gnn_data['num_edges']}, 格式={output_format}"
        )
        
        return gnn_data
    
    def _collect_equipment_features(
        self,
        df: pl.DataFrame,
        equipment_to_idx: Dict[str, int]
    ) -> np.ndarray:
        """
        收集每個設備的特徵 - 批次處理優化版
        
        🆕 修正：使用批次 select 取代逐欄位計算，啟動 Polars Rust 級平行運算
        參考 PRD v1.4 第 1481-1578 節 _generate_static_feature_matrix
        
        Returns:
            設備特徵矩陣 (n_nodes, n_features_per_node)
        """
        n_nodes = len(equipment_to_idx)
        sorted_equipment = sorted(equipment_to_idx.keys())
        
        # 步驟 1：為每個設備收集所屬欄位
        equipment_columns = {eq_id: [] for eq_id in sorted_equipment}
        
        for col in df.columns:
            if col in ['timestamp', 'quality_flags']:
                continue
            
            anno = self.annotation_manager.get_column_annotation(col)
            if not anno:
                continue
            
            eq_id = getattr(anno, 'equipment_id', None)
            if not eq_id or eq_id not in equipment_columns:
                continue
            
            equipment_columns[eq_id].append(col)
        
        # 步驟 2：批次計算每個設備的統計值
        equipment_feature_dict = {eq_id: [] for eq_id in sorted_equipment}
        
        for eq_id, cols in equipment_columns.items():
            if not cols:
                continue
            
            # 🆕 批次計算：單一 select 啟動 Rust 級平行運算
            # 而非逐欄位呼叫 .mean(), .std()（會各自觸發獨立計算）
            stats_exprs = []
            for c in cols:
                stats_exprs.extend([
                    pl.col(c).mean().alias(f"{c}_mean"),
                    pl.col(c).std().alias(f"{c}_std"),
                    pl.col(c).min().alias(f"{c}_min"),
                    pl.col(c).max().alias(f"{c}_max"),
                ])
            
            # 一次性計算所有統計值
            stats_df = df.select(stats_exprs)
            
            # 提取統計值並處理 NaN/None
            for c in cols:
                col_stats = [
                    stats_df[f"{c}_mean"][0],
                    stats_df[f"{c}_std"][0],
                    stats_df[f"{c}_min"][0],
                    stats_df[f"{c}_max"][0],
                ]
                
                # 安全處理 None 與 NaN 值
                col_stats = [
                    0.0 if s is None or (isinstance(s, float) and math.isnan(s)) else float(s)
                    for s in col_stats
                ]
                equipment_feature_dict[eq_id].extend(col_stats)
        
        # 步驟 3：統一 Padding 並組成矩陣
        feature_counts = [len(feats) for feats in equipment_feature_dict.values()]
        max_features = max(feature_counts) if feature_counts else 0
        
        feature_matrix = np.zeros((n_nodes, max_features), dtype=np.float32)
        
        for eq_id in sorted_equipment:
            idx = equipment_to_idx[eq_id]
            feats = equipment_feature_dict.get(eq_id, [])
            # 填充不足的部分為 0
            if feats:
                feature_matrix[idx, :len(feats)] = feats
        
        return feature_matrix
    
    def _generate_3d_tensor(
        self,
        df: pl.DataFrame,
        equipment_to_idx: Dict[str, int],
        equipment_features: np.ndarray,
        stride: int = 1,
        dtype: np.dtype = np.float32
    ) -> Tuple[np.ndarray, List[str]]:
        """
        生成 3D Tensor (T, N, F) 供 ST-GNN 使用 - 向量化重構版
        
        🆕 修正：採用向量化 NumPy 操作取代 Python 迴圈，效能提升 1000x+
        參考 PRD v1.4 第 1618-1744 節 _generate_temporal_feature_tensor
        
        Args:
            df: DataFrame
            equipment_to_idx: 設備到索引映射
            equipment_features: 設備靜態特徵矩陣 (N, F_static)
            stride: 時間步進（降採樣）
            dtype: 數值精度（預設 float32 節省記憶體）
            
        Returns:
            Tuple[3D Tensor (T, N, F), node_types List[str]]
        """
        # 🆕 套用 stride 降採樣
        if stride > 1:
            df = df[::stride]
        
        n_timesteps = len(df)
        n_nodes = len(equipment_to_idx)
        
        # 收集每個設備的特徵欄位（依設備順序）
        sorted_equipment = sorted(equipment_to_idx.keys())
        equipment_feature_cols = {eq_id: [] for eq_id in sorted_equipment}
        
        for col in df.columns:
            if col in ['timestamp', 'quality_flags']:
                continue
            
            anno = self.annotation_manager.get_column_annotation(col)
            if not anno:
                continue
            
            eq_id = getattr(anno, 'equipment_id', None)
            if not eq_id or eq_id not in equipment_feature_cols:
                continue
            
            equipment_feature_cols[eq_id].append(col)
        
        # 收集所有特徵欄位（依設備順序展平）
        all_feature_cols_ordered = []
        equipment_feature_counts = []
        
        for eq_id in sorted_equipment:
            cols = equipment_feature_cols[eq_id]
            all_feature_cols_ordered.extend(cols)
            equipment_feature_counts.append(len(cols))
        
        max_features = max(equipment_feature_counts) if equipment_feature_counts else 0
        
        # 🆕 記憶體預檢查
        element_size = np.dtype(dtype).itemsize
        estimated_memory_gb = (n_timesteps * n_nodes * (max_features + 1) * element_size) / (1024**3)
        
        if estimated_memory_gb > 4.0:
            import warnings
            warnings.warn(
                f"3D Tensor 預估記憶體占用: {estimated_memory_gb:.2f} GB "
                f"({n_timesteps} steps × {n_nodes} nodes × {max_features} features). "
                f"建議：1) 使用 stride > 1 降低時間解析度；2) 確認 dtype=np.float32；"
                f"3) 考慮分批處理（chunking）",
                ResourceWarning
            )
        
        # 🆕 向量化轉換：一次性轉為 NumPy (T, F_total)
        # 注意：使用 to_numpy() 而非逐行 .row()，效能差 1000 倍
        if all_feature_cols_ordered:
            data_matrix = df[all_feature_cols_ordered].to_numpy().astype(dtype)
        else:
            data_matrix = np.zeros((n_timesteps, 0), dtype=dtype)
        
        # 初始化 3D Tensor: (T, N, F_max + 1 for mask)
        tensor_dim = max(max_features + 1, equipment_features.shape[1] + 1)
        tensor = np.zeros((n_timesteps, n_nodes, tensor_dim), dtype=dtype)
        
        # 填充靜態設備特徵（所有時間步相同）
        for i in range(n_nodes):
            static_dim = min(equipment_features.shape[1], tensor_dim - 1)
            tensor[:, i, :static_dim] = equipment_features[i, :static_dim]
        
        # 🆕 向量化填充時間序列特徵
        feature_idx = 0
        for i, eq_id in enumerate(sorted_equipment):
            n_eq_features = equipment_feature_counts[i]
            
            if n_eq_features > 0 and feature_idx + n_eq_features <= data_matrix.shape[1]:
                # 提取該設備的所有特徵 (T, F_eq)
                eq_data = data_matrix[:, feature_idx:feature_idx + n_eq_features]
                
                # 🆕 使用 L0 原始特徵判斷設備斷線（避免 L1 Rolling 初始 NaN 過度遮蔽）
                # 檢查是否為實質缺失（全 NaN）
                nan_mask = np.isnan(eq_data).all(axis=1) if eq_data.shape[1] > 0 else np.zeros(n_timesteps, dtype=bool)
                
                # NaN → 0.0 安全轉換
                eq_data_safe = np.nan_to_num(eq_data, nan=0.0)
                
                # 填入 Tensor
                tensor[:, i, :n_eq_features] = eq_data_safe
                
                # 🆕 動態更新 Mask（該時間點斷線則 Mask=1）
                tensor[nan_mask, i, -1] = 1.0
                
                feature_idx += n_eq_features
            else:
                # 無特徵設備：全時間 Mask = 1
                tensor[:, i, -1] = 1.0
        
        # 🆕 生成 node_types（供異質 GNN 使用）
        node_types = []
        for eq_id in sorted_equipment:
            device_role = self.annotation_manager.get_device_role(eq_id)
            node_types.append(device_role if device_role else "unknown")
        
        return tensor, node_types

    # ==========================================================================
    # 主要處理流程
    # ==========================================================================
    
    def process(
        self,
        df: pl.DataFrame,
        fit_scaler: bool = True
    ) -> Dict[str, Any]:
        """
        執行完整的特徵工程流程
        
        Args:
            df: 輸入 DataFrame（來自 BatchProcessor）
            fit_scaler: 是否擬合縮放參數
            
        Returns:
            特徵工程結果字典
        """
        self.logger.info("開始特徵工程處理...")
        
        original_columns = set(df.columns)
        all_generated_features = []
        feature_hierarchy = {}
        
        # L0: 原始特徵
        for col in df.columns:
            if col not in ['timestamp', 'quality_flags']:
                feature_hierarchy[col] = "L0"
        
        # L1: 時間特徵
        df, temporal_features = self.generate_temporal_features(df)
        all_generated_features.extend(temporal_features)
        for f in temporal_features:
            feature_hierarchy[f] = "L1"
        
        # L1: Lag 特徵
        df, lag_features = self.generate_lag_features(df)
        all_generated_features.extend(lag_features)
        for f in lag_features:
            feature_hierarchy[f] = "L1"
        
        # L1: Rolling 特徵
        df, rolling_features = self.generate_rolling_features(df)
        all_generated_features.extend(rolling_features)
        for f in rolling_features:
            feature_hierarchy[f] = "L1"
        
        # L1: Diff 特徵
        df, diff_features = self.generate_diff_features(df)
        all_generated_features.extend(diff_features)
        for f in diff_features:
            feature_hierarchy[f] = "L1"
        
        # L2: 拓樸聚合特徵
        df, topology_features = self.generate_topology_aggregation_features(df)
        all_generated_features.extend([f["name"] for f in topology_features])
        for f in topology_features:
            feature_hierarchy[f["name"]] = "L2"
        
        # L3: 控制偏差特徵
        df, deviation_features = self.generate_control_deviation_features(df)
        all_generated_features.extend([f["name"] for f in deviation_features])
        for f in deviation_features:
            feature_hierarchy[f["name"]] = "L3"
        
        # 特徵縮放
        if fit_scaler:
            # 選擇要縮放的特徵（排除 L0 原始特徵和時間特徵）
            features_to_scale = [
                c for c in df.columns 
                if c not in original_columns and c not in ['timestamp', 'quality_flags']
            ]
            self.fit_scaler(df, features_to_scale)
        
        # GNN 資料匯出
        gnn_data = {}
        if self.config.gnn_enabled:
            gnn_data = self.export_gnn_data(df, self.config.gnn_output_format)
        
        # 準備輸出
        result = {
            "feature_matrix": df,
            "feature_order": df.columns,
            "original_columns": list(original_columns),
            "generated_features": all_generated_features,
            "feature_hierarchy": feature_hierarchy,
            "scaler_params": self.scaler_params,
            "topology_context": {
                "num_nodes": self.topology_manager.get_node_count(),
                "num_edges": len(self.topology_manager._edges),
                "adjacency_matrix": self.topology_manager.get_adjacency_matrix().tolist() if self.topology_manager.get_node_count() > 0 else [],
                "node_types": self.topology_manager.get_node_type_list(),
                "equipment_list": self.topology_manager.get_all_equipment()
            },
            "control_semantics_context": self.control_semantics_manager.get_control_semantics_info(),
            "gnn_data": gnn_data,
            "config": {
                "version": self.config.version,
                "lag_enabled": self.config.lag_enabled,
                "rolling_enabled": self.config.rolling_enabled,
                "topology_enabled": self.config.topology_aggregation.enabled,
                "control_deviation_enabled": self.config.control_deviation.enabled,
                "scaling_enabled": self.config.scaling_enabled
            }
        }
        
        self.logger.info(
            f"特徵工程完成: {len(df)} 行 x {len(df.columns)} 列, "
            f"生成 {len(all_generated_features)} 個新特徵"
        )
        
        return result
    
    def save_feature_manifest(
        self,
        result: Dict[str, Any],
        output_path: Union[str, Path]
    ):
        """
        儲存 Feature Manifest (E601 合規)
        
        Args:
            result: process() 的輸出結果
            output_path: 輸出路徑
        """
        output_path = Path(output_path)
        
        # 準備可序列化的內容
        manifest = {
            "version": "2.1",
            "feature_engineer_version": "1.4",
            "timestamp": datetime.now().isoformat(),
            "feature_order": list(result["feature_order"]),
            "feature_hierarchy": result["feature_hierarchy"],
            "original_columns": result["original_columns"],
            "generated_features": result["generated_features"],
            "scaler_params": result["scaler_params"],
            "topology_context": result["topology_context"],
            "control_semantics": result["control_semantics_context"],
            "config": result["config"]
        }
        
        # 儲存為 JSON
        import json
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Feature Manifest 已儲存: {output_path}")
    
    def save_feature_matrix(
        self,
        df: pl.DataFrame,
        output_path: Union[str, Path]
    ):
        """
        儲存特徵矩陣為 Parquet
        
        Args:
            df: 特徵矩陣 DataFrame
            output_path: 輸出路徑
        """
        output_path = Path(output_path)
        
        # 確保輸出目錄存在
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 儲存為 Parquet
        df.write_parquet(output_path)
        
        self.logger.info(f"特徵矩陣已儲存: {output_path}")
    
    # ==========================================================================
    # 輔助方法
    # ==========================================================================
    
    def set_model_artifact(self, model_artifact: Dict[str, Any]):
        """
        設定 Model Artifact（供 Data Leakage 防護使用）
        
        Args:
            model_artifact: 模型工件字典
        """
        self.model_artifact = model_artifact
    
    def _get_historical_global_mean(
        self, 
        physical_type: str,
        strict_mode: bool = True
    ) -> float:
        """
        取得歷史全域平均值（嚴格防 Data Leakage）
        
        資料來源優先順序：
        1. Model Artifact 中的 Scaling 統計屬性
        2. Fallback 預設值（訓練模式下）
        
        Args:
            physical_type: 物理類型
            strict_mode: 嚴格模式
            
        Returns:
            歷史全域平均值
        """
        # 策略1：從 Model Artifact 載入
        if self.model_artifact:
            scaling_stats = self.model_artifact.get('scaling_stats', {})
            if physical_type in scaling_stats:
                return scaling_stats[physical_type]['mean']
        
        # 嚴格模式檢查
        if strict_mode and not self.is_training:
            raise DataLeakageRiskError(
                f"E306: 嚴格模式下禁止動態計算 {physical_type} 的全域平均值。"
            )
        
        # 訓練模式警告
        if self.is_training and strict_mode:
            self.logger.warning(f"訓練模式：使用 fallback 值作為 {physical_type} 的備援")
        
        # Fallback 值
        fallback_values = {
            'temperature': 25.0,
            'pressure': 101.3,
            'flow_rate': 100.0,
            'power': 500.0,
            'frequency': 50.0,
            'voltage': 220.0,
        }
        
        return fallback_values.get(physical_type, 0.0)


# =============================================================================
# 便捷函數
# =============================================================================

def run_feature_engineering(
    manifest_path: Union[str, Path],
    site_id: str,
    output_dir: Union[str, Path],
    config: Optional[FeatureEngineeringConfig] = None,
    is_training: bool = True
) -> Dict[str, Any]:
    """
    執行完整特徵工程流程（便捷函數）
    
    Args:
        manifest_path: BatchProcessor 輸出的 Manifest 路徑
        site_id: 案場 ID
        output_dir: 輸出目錄
        config: 特徵工程配置（None=使用預設）
        is_training: 是否為訓練模式
        
    Returns:
        特徵工程結果
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 使用預設配置
    if config is None:
        config = FeatureEngineeringConfig(site_id=site_id)
    
    # 初始化 Feature Engineer
    fe = FeatureEngineer(
        config=config,
        site_id=site_id,
        is_training=is_training
    )
    
    # 載入資料
    df, feature_metadata, audit = fe.load_from_batch_processor(manifest_path)
    
    # 執行特徵工程
    result = fe.process(df, fit_scaler=is_training)
    
    # 儲存結果
    fe.save_feature_matrix(result["feature_matrix"], output_dir / "feature_matrix.parquet")
    fe.save_feature_manifest(result, output_dir / "feature_manifest.json")
    
    # 儲存 GNN 資料
    if result.get("gnn_data"):
        import json
        import numpy as np
        
        gnn_data = result["gnn_data"]
        
        # 儲存鄰接矩陣
        if "adjacency_matrix" in gnn_data:
            np.save(output_dir / "gnn_adjacency_matrix.npy", gnn_data["adjacency_matrix"])
        
        # 儲存設備特徵
        if "equipment_features" in gnn_data:
            np.save(output_dir / "gnn_equipment_features.npy", gnn_data["equipment_features"])
        
        # 儲存 3D Tensor
        if "tensor_3d" in gnn_data:
            np.save(output_dir / "gnn_tensor_3d.npy", gnn_data["tensor_3d"])
        
        # 儲存拓樸資訊
        topology_info = {
            "equipment_to_idx": gnn_data.get("equipment_to_idx", {}),
            "node_types": gnn_data.get("node_types", []),
            "num_nodes": gnn_data.get("num_nodes", 0),
            "num_edges": gnn_data.get("num_edges", 0)
        }
        with open(output_dir / "gnn_topology.json", 'w') as f:
            json.dump(topology_info, f, indent=2)
    
    return result
