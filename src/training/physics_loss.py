"""
物理守恆損失函數

實作 HVAC 系統的物理守恆約束：
System-Level 預測 ≈ Σ(Component-Level 預測)
"""

import torch
import torch.nn as nn
from typing import Dict, Tuple


class PhysicsInformedHybridLoss(nn.Module):
    """
    物理資訊混合損失
    
    結合預測損失與物理守恆損失:
    total_loss = pred_loss + physics_weight * physics_loss
    
    其中 physics_loss 確保:
    system_prediction ≈ sum(component_predictions)
    """
    
    def __init__(
        self,
        physics_weight: float = 0.1,
        loss_type: str = "mse",
        warmup_epochs: int = 10,
        use_physics_scaling: bool = True,
        system_scale: float = 1000.0
    ):
        """
        初始化
        
        Args:
            physics_weight: 物理損失權重
            loss_type: 損失類型 (mse/mae/huber)
            warmup_epochs: 物理損失暖身期（線性遞增）
            use_physics_scaling: 是否使用物理量級縮放
            system_scale: 系統量級縮放因子
        """
        super().__init__()
        self.physics_weight = physics_weight
        self.target_physics_weight = physics_weight
        self.loss_type = loss_type
        self.warmup_epochs = warmup_epochs
        self.current_epoch = 0
        self.use_physics_scaling = use_physics_scaling
        self.system_scale = system_scale
        self.eps = 1e-8
        
        # 預測損失函數
        if loss_type == "mse":
            self.pred_criterion = nn.MSELoss()
        elif loss_type == "mae":
            self.pred_criterion = nn.L1Loss()
        elif loss_type == "huber":
            self.pred_criterion = nn.SmoothL1Loss()
        else:
            self.pred_criterion = nn.MSELoss()
        
        # 物理損失函數
        self.physics_criterion = nn.MSELoss()
    
    def set_epoch(self, epoch: int):
        """
        設定當前 epoch（用於暖身機制）
        
        Args:
            epoch: 當前 epoch
        """
        self.current_epoch = epoch
    
    def get_effective_physics_weight(self) -> float:
        """
        取得有效的物理損失權重（考慮暖身期）
        
        Returns:
            有效權重
        """
        if self.current_epoch < self.warmup_epochs:
            # 線性遞增
            return self.target_physics_weight * (self.current_epoch / self.warmup_epochs)
        return self.target_physics_weight
    
    def forward(
        self,
        predictions: Dict[str, torch.Tensor],
        targets: Dict[str, torch.Tensor]
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        計算混合損失
        
        Args:
            predictions: 預測值字典，格式: {"system": ..., "component_1": ..., ...}
            targets: 目標值字典，格式同上
            
        Returns:
            (total_loss, loss_metrics)
        """
        # 計算預測損失（所有輸出）
        pred_loss = 0.0
        for key in predictions.keys():
            if key in targets:
                pred_loss += self.pred_criterion(predictions[key], targets[key])
        
        # 計算物理守恆損失
        physics_loss = self._compute_physics_loss(predictions, targets)
        
        # 應用暖身權重
        effective_weight = self.get_effective_physics_weight()
        
        # 總損失
        total_loss = pred_loss + effective_weight * physics_loss
        
        # 損失分解（用於記錄）
        loss_metrics = {
            'prediction_loss': pred_loss.item() if isinstance(pred_loss, torch.Tensor) else pred_loss,
            'physics_loss': physics_loss.item() if isinstance(physics_loss, torch.Tensor) else physics_loss,
            'physics_weight': effective_weight,
            'total_loss': total_loss.item() if isinstance(total_loss, torch.Tensor) else total_loss
        }
        
        return total_loss, loss_metrics
    
    def _compute_physics_loss(
        self,
        predictions: Dict[str, torch.Tensor],
        targets: Dict[str, torch.Tensor]
    ) -> torch.Tensor:
        """
        計算物理守恆損失
        
        檢查: system ≈ sum(components)
        
        Args:
            predictions: 預測值字典
            targets: 目標值字典
            
        Returns:
            物理損失
        """
        # 找到 system 預測
        system_key = None
        component_keys = []
        
        for key in predictions.keys():
            if 'system' in key.lower() or key == 'total':
                system_key = key
            else:
                component_keys.append(key)
        
        if system_key is None or len(component_keys) == 0:
            # 無法計算物理損失
            return torch.tensor(0.0, device=next(iter(predictions.values())).device)
        
        # 計算組件總和
        component_sum = sum(predictions[k] for k in component_keys)
        
        # 物理損失: system 應該約等於 component_sum
        physics_loss = self.physics_criterion(predictions[system_key], component_sum)
        
        # 量級縮放
        if self.use_physics_scaling:
            scale = max(self.system_scale, self.eps)
            physics_loss = physics_loss / scale
        
        return physics_loss
