"""
基礎模型訓練器

定義所有訓練器的共同介面
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pathlib import Path
import numpy as np

from src.utils.logger import get_logger


class BaseModelTrainer(ABC):
    """
    基礎模型訓練器抽象類別
    
    所有訓練器必須實現以下方法:
    - train(): 訓練模型
    - predict(): 預測
    - save_model(): 儲存模型
    - load_model(): 載入模型
    """
    
    def __init__(self, config: Any, random_state: int = 42, target_id: str = "default"):
        """
        初始化訓練器
        
        Args:
            config: 模型配置
            random_state: 隨機種子
            target_id: 目標變數 ID
        """
        self.config = config
        self.random_state = random_state
        self.target_id = target_id
        self.logger = get_logger(self.__class__.__name__)
        
        self.model = None
        self.is_fitted = False
        self.training_history = {}
        self.feature_importance = {}
        self.best_model_state = None
        
        # 模型元資料
        self.model_metadata = {
            'trainer_version': '1.0.0',
            'supports_incremental': False,
            'supports_explainability': False,
            'model_family': 'base'
        }
    
    @abstractmethod
    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        訓練模型
        
        Args:
            X_train: 訓練特徵
            y_train: 訓練目標
            X_val: 驗證特徵（可選）
            y_val: 驗證目標（可選）
            
        Returns:
            訓練結果字典
        """
        pass
    
    @abstractmethod
    def predict(self, X: np.ndarray, **kwargs) -> np.ndarray:
        """
        預測
        
        Args:
            X: 輸入特徵
            
        Returns:
            預測結果
        """
        pass
    
    @abstractmethod
    def save_model(self, path: Path):
        """
        儲存模型
        
        Args:
            path: 儲存路徑
        """
        pass
    
    @abstractmethod
    def load_model(self, path: Path):
        """
        載入模型
        
        Args:
            path: 模型路徑
        """
        pass
    
    def get_feature_importance(self) -> Dict[str, float]:
        """
        取得特徵重要性
        
        Returns:
            特徵重要性字典
        """
        return self.feature_importance
    
    def get_training_history(self) -> Dict[str, Any]:
        """
        取得訓練歷史
        
        Returns:
            訓練歷史字典
        """
        return self.training_history
    
    def is_trained(self) -> bool:
        """
        檢查模型是否已訓練
        
        Returns:
            是否已訓練
        """
        return self.is_fitted
