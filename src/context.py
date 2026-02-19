"""
PipelineContext - 全域時間基準與 Pipeline 狀態管理

此模組實作 PipelineContext 單例模式，作為 HVAC-1 系統的核心時間基準傳遞機制。
所有 ETL 模組必須透過此上下文取得時間基準，禁止直接使用 datetime.now()。

設計原則:
- Thread-safe Singleton: 確保全域唯一時間基準
- 不可變時間基準: 一旦設定不可更改
- E000 強制檢查: 未初始化時拋出 E000 錯誤
- 時間漂移檢測: 自動監控長時間執行流程

錯誤代碼:
- E000: 時間基準遺失
- E000-W: 時間漂移警告
"""

from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import threading
import logging

from src.etl.config_models import (
    E000_TEMPORAL_BASELINE_MISSING,
    E000W_TEMPORAL_DRIFT_WARNING,
    ErrorSeverity,
)

logger = logging.getLogger(__name__)


class PipelineContext:
    """
    Pipeline 全域上下文管理器 (Thread-safe Singleton)
    
    負責管理:
    1. 時間基準 (pipeline_origin_timestamp)
    2. Pipeline 執行狀態
    3. 跨模組共享的唯讀配置
    
    Usage:
        >>> context = PipelineContext()
        >>> context.initialize()  # 必須先初始化
        >>> baseline = context.get_baseline()
        >>> if context.is_future(some_timestamp):
        ...     raise ValueError("未來資料")
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
                    cls._instance._origin_timestamp = None
                    cls._instance._site_id = None
                    cls._instance._pipeline_id = None
                    cls._instance._version = "1.2.0"
                    cls._instance._drift_warning_threshold_minutes = 60
        return cls._instance
    
    def initialize(
        self,
        timestamp: Optional[datetime] = None,
        site_id: Optional[str] = None,
        pipeline_id: Optional[str] = None
    ) -> None:
        """
        初始化 PipelineContext（僅可執行一次）
        
        Args:
            timestamp: 時間基準，預設為當前 UTC 時間
            site_id: 案場 ID
            pipeline_id: Pipeline 執行 ID
            
        Raises:
            RuntimeError: 若已初始化過
        """
        if self._initialized:
            raise RuntimeError(
                "PipelineContext 已初始化，不可重複設定。"
                "如需新的時間基準，請建立新的 Pipeline 實例。"
            )
        
        with self._lock:
            self._origin_timestamp = timestamp or datetime.now(timezone.utc)
            self._site_id = site_id
            self._pipeline_id = pipeline_id
            self._initialized = True
            
            logger.info(
                f"PipelineContext 已初始化 | "
                f"timestamp={self._origin_timestamp.isoformat()}, "
                f"site_id={site_id}, pipeline_id={pipeline_id}"
            )
    
    def get_baseline(self) -> datetime:
        """
        取得 Pipeline 啟動時間戳（時間基準）
        
        Returns:
            datetime: UTC 時間戳
            
        Raises:
            RuntimeError: E000 時間基準遺失
        """
        if not self._initialized or self._origin_timestamp is None:
            raise RuntimeError(
                f"[{E000_TEMPORAL_BASELINE_MISSING.code}] "
                f"{E000_TEMPORAL_BASELINE_MISSING.user_message_template}"
            )
        return self._origin_timestamp
    
    def is_initialized(self) -> bool:
        """檢查是否已初始化"""
        return self._initialized
    
    def is_future(
        self,
        timestamp: datetime,
        tolerance_minutes: int = 5
    ) -> bool:
        """
        判斷時間戳是否為「未來資料」
        
        標準：timestamp > origin_timestamp + tolerance_minutes
        
        Args:
            timestamp: 待檢查的時間戳
            tolerance_minutes: 容忍時間（分鐘），預設 5 分鐘
            
        Returns:
            bool: True 若為未來資料
            
        Raises:
            RuntimeError: 若 PipelineContext 未初始化
        """
        baseline = self.get_baseline()
        threshold = baseline + timedelta(minutes=tolerance_minutes)
        return timestamp > threshold
    
    def get_elapsed_seconds(self) -> float:
        """
        取得 Pipeline 已執行時間（秒）
        
        Returns:
            float: 已執行秒數
        """
        baseline = self.get_baseline()
        return (datetime.now(timezone.utc) - baseline).total_seconds()
    
    def get_elapsed_minutes(self) -> float:
        """
        取得 Pipeline 已執行時間（分鐘）
        
        Returns:
            float: 已執行分鐘數
        """
        return self.get_elapsed_seconds() / 60
    
    def check_drift_warning(self) -> Optional[Dict[str, Any]]:
        """
        檢查是否需要發出時間漂移警告
        
        Returns:
            Optional[Dict]: 警告資訊，若無警告則返回 None
        """
        elapsed_minutes = self.get_elapsed_minutes()
        
        if elapsed_minutes > self._drift_warning_threshold_minutes:
            warning = {
                "code": E000W_TEMPORAL_DRIFT_WARNING.code,
                "message": E000W_TEMPORAL_DRIFT_WARNING.user_message_template,
                "severity": E000W_TEMPORAL_DRIFT_WARNING.severity.value,
                "elapsed_minutes": elapsed_minutes,
                "threshold_minutes": self._drift_warning_threshold_minutes,
            }
            logger.warning(f"時間漂移警告: {warning}")
            return warning
        return None
    
    def get_site_id(self) -> Optional[str]:
        """取得案場 ID"""
        return self._site_id
    
    def get_pipeline_id(self) -> Optional[str]:
        """取得 Pipeline 執行 ID"""
        return self._pipeline_id
    
    def to_dict(self) -> Dict[str, Any]:
        """
        轉換為字典格式（用於傳遞至下游模組）
        
        Returns:
            Dict 包含:
                - pipeline_origin_timestamp: ISO 格式時間戳
                - timezone: 時區資訊
                - site_id: 案場 ID
                - pipeline_id: Pipeline ID
                - version: PipelineContext 版本
        """
        return {
            "pipeline_origin_timestamp": (
                self._origin_timestamp.isoformat() 
                if self._origin_timestamp else None
            ),
            "timezone": "UTC",
            "site_id": self._site_id,
            "pipeline_id": self._pipeline_id,
            "version": self._version,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PipelineContext":
        """
        從字典恢復 PipelineContext（僅供測試使用）
        
        Args:
            data: 包含 pipeline_origin_timestamp 等欄位的字典
            
        Returns:
            PipelineContext 實例
        """
        instance = cls()
        if not instance._initialized:
            ts_str = data.get("pipeline_origin_timestamp")
            if ts_str:
                timestamp = datetime.fromisoformat(ts_str)
                instance.initialize(
                    timestamp=timestamp,
                    site_id=data.get("site_id"),
                    pipeline_id=data.get("pipeline_id")
                )
        return instance
    
    @classmethod
    def reset_for_testing(cls) -> None:
        """
        重置單例（僅供測試使用）
        
        ⚠️ 警告: 此方法僅應在單元測試中使用，生產環境禁止呼叫
        """
        with cls._lock:
            cls._instance = None
        logger.debug("PipelineContext 已重置（測試模式）")


class TemporalContextInjector:
    """
    時間基準注入器
    
    用於將 PipelineContext 的時間基準注入至 ETL 模組的輸入參數。
    確保所有模組都能正確接收並使用時間基準。
    
    Usage:
        >>> injector = TemporalContextInjector()
        >>> result = injector.inject_to_dict({"data": "value"})
        >>> print(result["temporal_context"]["pipeline_origin_timestamp"])
    """
    
    def __init__(self, context: Optional[PipelineContext] = None):
        self.context = context or PipelineContext()
    
    def inject_to_dict(self, input_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        將時間基準注入字典
        
        Args:
            input_dict: 原始輸入字典
            
        Returns:
            包含 temporal_context 的字典
        """
        result = input_dict.copy()
        result["temporal_context"] = self.context.to_dict()
        return result
    
    def validate_received(
        self,
        received_context: Optional[Dict[str, Any]]
    ) -> datetime:
        """
        驗證接收到的時間基準
        
        Args:
            received_context: 接收到的 temporal_context 字典
            
        Returns:
            datetime: 驗證後的時間基準
            
        Raises:
            RuntimeError: E000 若時間基準遺失
        """
        if not received_context:
            raise RuntimeError(
                f"[{E000_TEMPORAL_BASELINE_MISSING.code}] "
                f"{E000_TEMPORAL_BASELINE_MISSING.user_message_template}"
            )
        
        ts_str = received_context.get("pipeline_origin_timestamp")
        if not ts_str:
            raise RuntimeError(
                f"[{E000_TEMPORAL_BASELINE_MISSING.code}] "
                f"{E000_TEMPORAL_BASELINE_MISSING.user_message_template}"
            )
        
        return datetime.fromisoformat(ts_str)


def require_temporal_context(func):
    """
    裝飾器: 確保函數呼叫時 PipelineContext 已初始化
    
    Usage:
        >>> @require_temporal_context
        ... def process_data(data):
        ...     context = PipelineContext()
        ...     # 確保這裡 context 已初始化
        ...     pass
    """
    def wrapper(*args, **kwargs):
        context = PipelineContext()
        if not context.is_initialized():
            raise RuntimeError(
                f"[{E000_TEMPORAL_BASELINE_MISSING.code}] "
                f"函數 {func.__name__} 需要已初始化的 PipelineContext"
            )
        return func(*args, **kwargs)
    return wrapper


__all__ = [
    "PipelineContext",
    "TemporalContextInjector",
    "require_temporal_context",
]
