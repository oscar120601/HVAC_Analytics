"""
模型訓練模組

包含:
- BaseModelTrainer: 基礎訓練器介面
- GNNTrainer: 圖神經網路訓練器
- MultiTaskGNNTrainer: 多任務 GNN 訓練器
- PhysicsInformedHybridLoss: 物理守恆損失
- ModelRegistry: 模型註冊表
"""

from .base_trainer import BaseModelTrainer
from .gnn_trainer import MultiTaskGNNTrainer, MultiTaskGraphNeuralNetwork
from .physics_loss import PhysicsInformedHybridLoss

__all__ = [
    'BaseModelTrainer',
    'MultiTaskGNNTrainer',
    'MultiTaskGraphNeuralNetwork',
    'PhysicsInformedHybridLoss',
]
