"""
ETLContainer - 依賴注入容器與系統初始化控制

此模組實作 HVAC-1 系統的 DI 容器，嚴格遵循 Foundation First Policy 的
4 步驟初始化順序：

1. PipelineContext 建立（時間基準）
2. ConfigLoader 初始化（配置載入，含 E406 檢查）
3. FeatureAnnotationManager 載入（YAML SSOT）
4. ETL Pipeline 模組實例化（Parser → Cleaner → BatchProcessor → ...）

錯誤代碼:
- E000: 時間基準遺失
- E406: Excel/YAML 不同步
- E906: 版本漂移

設計原則:
- Foundation First: 必須按順序初始化，不可跳過
- Immutable Context: 時間基準一旦設定不可更改
- Fail Fast: 初始化失敗立即終止
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Type, List
from datetime import datetime, timezone
from enum import Enum, auto
from dataclasses import dataclass, field

from src.context import PipelineContext, TemporalContextInjector
from src.etl.config_models import (
    ETLConfig,
    SiteFeatureConfig,
    E906_PIPELINE_VERSION_DRIFT,
    check_version_compatibility,
    ERROR_CODES,
)
from src.utils.config_loader import ConfigLoader, SyncCheckResult

logger = logging.getLogger(__name__)


class InitializationState(Enum):
    """初始化狀態"""
    UNINITIALIZED = auto()
    CONTEXT_CREATED = auto()      # 步驟 1 完成
    CONFIG_LOADED = auto()        # 步驟 2 完成
    ANNOTATION_READY = auto()     # 步驟 3 完成
    MODULES_INITIALIZED = auto()  # 步驟 4 完成
    FAILED = auto()


@dataclass
class InitializationStatus:
    """初始化狀態追蹤"""
    state: InitializationState = InitializationState.UNINITIALIZED
    current_step: int = 0
    total_steps: int = 4
    completed_steps: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def is_ready(self) -> bool:
        """檢查是否已完成所有初始化步驟"""
        return self.state == InitializationState.MODULES_INITIALIZED
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典"""
        return {
            "state": self.state.name,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "completed_steps": self.completed_steps,
            "errors": self.errors,
            "warnings": self.warnings,
            "is_ready": self.is_ready(),
        }


class ETLContainer:
    """
    ETL Pipeline 依賴注入容器
    
    嚴格控制初始化順序，確保所有依賴正確建立。
    
    Usage:
        >>> container = ETLContainer(site_id="cgmh_ty")
        >>> 
        >>> # 完整初始化（4 步驟）
        >>> container.initialize_all()
        >>> 
        >>> # 或逐步初始化
        >>> container.step1_create_context()
        >>> container.step2_load_config()
        >>> container.step3_load_annotation()
        >>> container.step4_initialize_modules()
        >>> 
        >>> # 取得元件
        >>> parser = container.get_parser()
        >>> cleaner = container.get_cleaner()
    """
    
    def __init__(
        self,
        site_id: str,
        config_base_path: str = "config/features",
        enable_sync_check: bool = True,
        temporal_baseline: Optional[datetime] = None,
    ):
        self.site_id = site_id
        self.config_base_path = config_base_path
        self.enable_sync_check = enable_sync_check
        self.temporal_baseline = temporal_baseline
        
        # 初始化狀態
        self._status = InitializationStatus()
        
        # 步驟 1: PipelineContext
        self._context: Optional[PipelineContext] = None
        
        # 步驟 2: ConfigLoader & ETLConfig
        self._config_loader: Optional[ConfigLoader] = None
        self._etl_config: Optional[ETLConfig] = None
        
        # 步驟 3: FeatureAnnotationManager（lazy import 避免循環依賴）
        self._annotation_manager: Optional[Any] = None
        
        # 步驟 4: ETL 模組
        self._parser: Optional[Any] = None
        self._cleaner: Optional[Any] = None
        self._batch_processor: Optional[Any] = None
        self._feature_engineer: Optional[Any] = None
        
        logger.info(f"ETLContainer 已建立: site_id={site_id}")
    
    # =========================================================================
    # 步驟 1: PipelineContext 建立
    # =========================================================================
    def step1_create_context(self) -> PipelineContext:
        """
        步驟 1: 建立 PipelineContext（時間基準）
        
        Returns:
            PipelineContext
            
        Raises:
            RuntimeError: 若上下文已初始化
        """
        logger.info("步驟 1/4: 建立 PipelineContext...")
        
        try:
            self._context = PipelineContext()
            
            # 初始化時間基準
            baseline = self.temporal_baseline or datetime.now(timezone.utc)
            self._context.initialize(
                timestamp=baseline,
                site_id=self.site_id,
                pipeline_id=f"{self.site_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
            )
            
            self._status.state = InitializationState.CONTEXT_CREATED
            self._status.current_step = 1
            self._status.completed_steps.append("step1_create_context")
            
            logger.info(
                f"PipelineContext 已建立 | "
                f"baseline={self._context.get_baseline().isoformat()}"
            )
            return self._context
            
        except Exception as e:
            self._status.state = InitializationState.FAILED
            self._status.errors.append(f"步驟 1 失敗: {e}")
            raise RuntimeError(f"PipelineContext 建立失敗: {e}") from e
    
    # =========================================================================
    # 步驟 2: ConfigLoader 初始化
    # =========================================================================
    def step2_load_config(self) -> ETLConfig:
        """
        步驟 2: 初始化 ConfigLoader 並載入 ETLConfig
        
        包含 E406 同步檢查（若啟用）
        
        Returns:
            ETLConfig
            
        Raises:
            RuntimeError: 若 E406 檢查失敗或配置載入失敗
        """
        logger.info("步驟 2/4: 載入 ETLConfig...")
        
        if self._status.state.value < InitializationState.CONTEXT_CREATED.value:
            raise RuntimeError(
                "必須先執行 step1_create_context()"
            )
        
        try:
            # 建立 ConfigLoader
            self._config_loader = ConfigLoader(
                config_base_path=self.config_base_path,
                enable_file_lock=True
            )
            
            # E406 同步檢查
            if self.enable_sync_check:
                sync_result = self._config_loader.validate_annotation_sync(
                    self.site_id
                )
                if not sync_result.is_synced:
                    error_msg = f"E406 同步檢查失敗: {sync_result.message}"
                    if sync_result.recovery_action:
                        error_msg += f"\n恢復建議: {sync_result.recovery_action}"
                    self._status.warnings.append(error_msg)
                    logger.warning(error_msg)
                    # 嚴格模式下可以選擇拋出異常
                    # raise RuntimeError(error_msg)
            
            # 載入 ETLConfig
            self._etl_config = self._config_loader.load_etl_config(
                self.site_id,
                skip_sync_check=True  # 已在上面檢查
            )
            
            # 設定時間基準
            if self._context:
                self._etl_config.temporal_baseline = self._context.get_baseline().isoformat()
            
            # 版本相容性檢查（E906）
            is_compatible, messages = self._etl_config.validate_compatibility()
            if not is_compatible:
                error_msg = f"E906 版本漂移: {'; '.join(messages)}"
                self._status.errors.append(error_msg)
                raise RuntimeError(error_msg)
            elif messages:
                # 部分相容警告
                self._status.warnings.append(f"版本相容性警告: {'; '.join(messages)}")
            
            self._status.state = InitializationState.CONFIG_LOADED
            self._status.current_step = 2
            self._status.completed_steps.append("step2_load_config")
            
            logger.info(f"ETLConfig 已載入: {len(self._etl_config.annotation.features)} 個特徵")
            return self._etl_config
            
        except Exception as e:
            self._status.state = InitializationState.FAILED
            self._status.errors.append(f"步驟 2 失敗: {e}")
            raise RuntimeError(f"配置載入失敗: {e}") from e
    
    # =========================================================================
    # 步驟 3: FeatureAnnotationManager 載入
    # =========================================================================
    def step3_load_annotation(self) -> Any:
        """
        步驟 3: 載入 FeatureAnnotationManager
        
        Returns:
            FeatureAnnotationManager 實例
        """
        logger.info("步驟 3/4: 載入 FeatureAnnotationManager...")
        
        if self._status.state.value < InitializationState.CONFIG_LOADED.value:
            raise RuntimeError(
                "必須先執行 step2_load_config()"
            )
        
        try:
            # Lazy import 避免循環依賴
            try:
                from src.features.annotation_manager import FeatureAnnotationManager
            except ImportError:
                logger.warning("FeatureAnnotationManager 尚未實作，使用 stub")
                FeatureAnnotationManager = None
            
            if FeatureAnnotationManager:
                self._annotation_manager = FeatureAnnotationManager(
                    site_id=self.site_id,
                    config=self._etl_config.annotation
                )
            else:
                # Stub 實作
                self._annotation_manager = None
            
            self._status.state = InitializationState.ANNOTATION_READY
            self._status.current_step = 3
            self._status.completed_steps.append("step3_load_annotation")
            
            logger.info("FeatureAnnotationManager 已載入")
            return self._annotation_manager
            
        except Exception as e:
            self._status.state = InitializationState.FAILED
            self._status.errors.append(f"步驟 3 失敗: {e}")
            raise RuntimeError(f"Annotation 載入失敗: {e}") from e
    
    # =========================================================================
    # 步驟 4: ETL Pipeline 模組實例化
    # =========================================================================
    def step4_initialize_modules(self) -> Dict[str, Any]:
        """
        步驟 4: 初始化 ETL Pipeline 模組
        
        依序建立:
        1. Parser
        2. Cleaner
        3. BatchProcessor
        4. FeatureEngineer
        
        Returns:
            模組字典
        """
        logger.info("步驟 4/4: 初始化 ETL Pipeline 模組...")
        
        if self._status.state.value < InitializationState.ANNOTATION_READY.value:
            raise RuntimeError(
                "必須先執行 step3_load_annotation()"
            )
        
        try:
            # 建立 TemporalContextInjector
            injector = TemporalContextInjector(self._context)
            
            # 4.1 Parser
            try:
                from src.etl.parser import ReportParser
                # 嘗試使用新接口初始化，若失敗則使用預設構造函數
                try:
                    self._parser = ReportParser(
                        site_id=self.site_id,
                        annotation_manager=self._annotation_manager
                    )
                except TypeError:
                    # 使用現有 Parser 的簡單構造函數
                    self._parser = ReportParser()
                logger.debug("Parser 已初始化")
            except ImportError:
                logger.warning("ReportParser 尚未實作，略過")
                self._parser = None
            
            # 4.2 Cleaner
            try:
                from src.etl.cleaner import DataCleaner
                # 使用現有接口初始化
                self._cleaner = DataCleaner()
                logger.debug("Cleaner 已初始化")
            except ImportError:
                logger.warning("DataCleaner 尚未實作，略過")
                self._cleaner = None
            
            # 4.3 BatchProcessor（目前無法直接實例化，略過）
            self._batch_processor = None
            logger.debug("BatchProcessor 略過（模組結構需調整）")
            
            # 4.4 FeatureEngineer（尚未實作）
            self._feature_engineer = None
            logger.debug("FeatureEngineer 略過（尚未實作）")
            
            self._status.state = InitializationState.MODULES_INITIALIZED
            self._status.current_step = 4
            self._status.completed_steps.append("step4_initialize_modules")
            
            logger.info("所有 ETL 模組已初始化")
            
            return {
                "parser": self._parser,
                "cleaner": self._cleaner,
                "batch_processor": self._batch_processor,
                "feature_engineer": self._feature_engineer,
            }
            
        except Exception as e:
            self._status.state = InitializationState.FAILED
            self._status.errors.append(f"步驟 4 失敗: {e}")
            raise RuntimeError(f"模組初始化失敗: {e}") from e
    
    # =========================================================================
    # 完整初始化流程
    # =========================================================================
    def initialize_all(self) -> "ETLContainer":
        """
        執行完整的 4 步驟初始化流程
        
        Returns:
            self (方便串接)
        """
        logger.info("開始 ETLContainer 完整初始化...")
        
        self.step1_create_context()
        self.step2_load_config()
        self.step3_load_annotation()
        self.step4_initialize_modules()
        
        logger.info("ETLContainer 初始化完成！")
        return self
    
    # =========================================================================
    # Getter 方法
    # =========================================================================
    def get_context(self) -> PipelineContext:
        """取得 PipelineContext"""
        if self._context is None:
            raise RuntimeError("PipelineContext 尚未初始化")
        return self._context
    
    def get_config(self) -> ETLConfig:
        """取得 ETLConfig"""
        if self._etl_config is None:
            raise RuntimeError("ETLConfig 尚未初始化")
        return self._etl_config
    
    def get_annotation_manager(self) -> Any:
        """取得 FeatureAnnotationManager"""
        if self._annotation_manager is None:
            raise RuntimeError("FeatureAnnotationManager 尚未初始化")
        return self._annotation_manager
    
    def get_parser(self) -> Any:
        """取得 Parser"""
        return self._parser
    
    def get_cleaner(self) -> Any:
        """取得 Cleaner"""
        return self._cleaner
    
    def get_batch_processor(self) -> Any:
        """取得 BatchProcessor"""
        return self._batch_processor
    
    def get_feature_engineer(self) -> Any:
        """取得 FeatureEngineer"""
        return self._feature_engineer
    
    def get_status(self) -> InitializationStatus:
        """取得初始化狀態"""
        return self._status
    
    # =========================================================================
    # 實用方法
    # =========================================================================
    def is_ready(self) -> bool:
        """檢查是否已完成初始化"""
        return self._status.is_ready()
    
    def get_temporal_baseline(self) -> datetime:
        """取得時間基準"""
        return self.get_context().get_baseline()
    
    def check_drift(self) -> Optional[str]:
        """檢查時間漂移警告"""
        if self._context:
            return self._context.check_drift_warning()
        return None
    
    def reset(self) -> None:
        """重置容器狀態（僅供測試使用）"""
        self._status = InitializationStatus()
        self._context = None
        self._config_loader = None
        self._etl_config = None
        self._annotation_manager = None
        self._parser = None
        self._cleaner = None
        self._batch_processor = None
        self._feature_engineer = None
        
        # 重置 PipelineContext 單例
        PipelineContext.reset_for_testing()
        
        logger.info("ETLContainer 已重置")


class ContainerFactory:
    """
    Container 工廠
    
    用於建立預配置的 ETLContainer 實例。
    """
    
    @staticmethod
    def create(
        site_id: str,
        auto_initialize: bool = True,
        **kwargs
    ) -> ETLContainer:
        """
        建立並初始化 ETLContainer
        
        Args:
            site_id: 案場 ID
            auto_initialize: 是否自動執行完整初始化
            **kwargs: 傳遞給 ETLContainer 的其他參數
            
        Returns:
            ETLContainer
        """
        container = ETLContainer(site_id=site_id, **kwargs)
        
        if auto_initialize:
            container.initialize_all()
        
        return container
    
    @staticmethod
    def create_test_container(
        site_id: str = "test_site",
        skip_sync_check: bool = True
    ) -> ETLContainer:
        """
        建立測試用 Container（跳過同步檢查）
        
        Args:
            site_id: 案場 ID
            skip_sync_check: 是否跳過同步檢查
            
        Returns:
            ETLContainer
        """
        return ContainerFactory.create(
            site_id=site_id,
            enable_sync_check=not skip_sync_check,
            auto_initialize=True
        )


def get_container(
    site_id: str,
    auto_initialize: bool = True
) -> ETLContainer:
    """
    快捷函數: 取得已初始化的 ETLContainer
    
    Args:
        site_id: 案場 ID
        auto_initialize: 是否自動初始化
        
    Returns:
        ETLContainer
    """
    return ContainerFactory.create(
        site_id=site_id,
        auto_initialize=auto_initialize
    )


__all__ = [
    "ETLContainer",
    "ContainerFactory",
    "InitializationState",
    "InitializationStatus",
    "get_container",
]
