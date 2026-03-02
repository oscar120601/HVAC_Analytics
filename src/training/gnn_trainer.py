"""
多任務圖神經網路訓練器 (Multi-Task GNN Trainer)

實作:
- Multi-Task GNN 架構（同時預測 System + Components）
- 支援 GCN/GAT/GraphSAGE
- 整合物理守恆損失
- Captum 特徵重要性
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import numpy as np

try:
    from torch_geometric.nn import GCNConv, GATConv, SAGEConv, global_mean_pool
    from torch_geometric.data import Data, DataLoader
    TORCH_GEOMETRIC_AVAILABLE = True
except ImportError:
    TORCH_GEOMETRIC_AVAILABLE = False

from .base_trainer import BaseModelTrainer
from .physics_loss import PhysicsInformedHybridLoss


class MultiTaskGraphNeuralNetwork(nn.Module):
    """
    多任務圖神經網路
    
    核心設計：
    - 共享 GNN 卷積層提取全域特徵
    - 多輸出頭同時預測 System + Components
    """
    
    def __init__(
        self,
        input_dim: int,
        hidden_dim: int = 64,
        num_outputs: int = 1,
        output_names: Optional[List[str]] = None,
        num_layers: int = 3,
        model_type: str = "GCN",
        dropout: float = 0.2,
        use_edge_attr: bool = False
    ):
        super().__init__()
        
        if not TORCH_GEOMETRIC_AVAILABLE:
            raise ImportError("torch_geometric is required for GNN models")
        
        self.model_type = model_type
        self.num_layers = num_layers
        self.dropout = dropout
        self.use_edge_attr = use_edge_attr
        self.num_outputs = num_outputs
        self.output_names = output_names or [f"output_{i}" for i in range(num_outputs)]
        
        # 選擇卷積層類型
        conv_class = {"GCN": GCNConv, "GAT": GATConv, "GraphSAGE": SAGEConv}.get(model_type, GCNConv)
        
        # 共享 GNN 卷積層
        self.convs = nn.ModuleList()
        self.batch_norms = nn.ModuleList()
        
        self.convs.append(conv_class(input_dim, hidden_dim))
        self.batch_norms.append(nn.BatchNorm1d(hidden_dim))
        
        for _ in range(num_layers - 2):
            self.convs.append(conv_class(hidden_dim, hidden_dim))
            self.batch_norms.append(nn.BatchNorm1d(hidden_dim))
        
        self.convs.append(conv_class(hidden_dim, hidden_dim))
        
        # 多輸出頭
        self.output_heads = nn.ModuleList([
            nn.Sequential(
                nn.Linear(hidden_dim, hidden_dim // 2),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(hidden_dim // 2, 1)
            )
            for _ in range(num_outputs)
        ])
    
    def forward(self, data) -> torch.Tensor:
        """
        前向傳播
        
        Args:
            data: PyG Data 物件
            
        Returns:
            預測輸出 (batch_size, num_outputs)
        """
        x, edge_index = data.x, data.edge_index
        edge_attr = data.edge_attr if self.use_edge_attr and hasattr(data, 'edge_attr') else None
        
        # 共享 GNN 層
        for i, (conv, bn) in enumerate(zip(self.convs[:-1], self.batch_norms)):
            if self.model_type == "GAT":
                x = conv(x, edge_index)
            else:
                x = conv(x, edge_index, edge_weight=edge_attr)
            
            x = bn(x)
            x = F.relu(x)
            x = F.dropout(x, p=self.dropout, training=self.training)
        
        # 最後一層
        if self.model_type == "GAT":
            x = self.convs[-1](x, edge_index)
        else:
            x = self.convs[-1](x, edge_index, edge_weight=edge_attr)
        
        # 全域池化
        if hasattr(data, 'batch') and data.batch is not None:
            x = global_mean_pool(x, data.batch)
        else:
            x = x.mean(dim=0, keepdim=True)
        
        # 多輸出頭預測
        outputs = [head(x) for head in self.output_heads]
        predictions = torch.cat(outputs, dim=1)
        
        return predictions
    
    def get_system_prediction(self, predictions: torch.Tensor) -> torch.Tensor:
        """取得 System-Level 預測"""
        return predictions[:, 0]
    
    def get_component_predictions(self, predictions: torch.Tensor) -> torch.Tensor:
        """取得 Component-Level 預測"""
        return predictions[:, 1:]


class MultiTaskGNNTrainer(BaseModelTrainer):
    """
    多任務 GNN 訓練器
    
    支援物理損失聯合訓練
    """
    
    def __init__(
        self,
        config: Any,
        random_state: int = 42,
        target_id: str = "multitask_gnn",
        device: str = "auto",
        output_names: Optional[List[str]] = None
    ):
        super().__init__(config, random_state, target_id)
        
        if not TORCH_GEOMETRIC_AVAILABLE:
            raise ImportError("torch_geometric is required for GNN training")
        
        self.output_names = output_names or ["system_total_kw"]
        self.num_outputs = len(self.output_names)
        
        self.model_metadata.update({
            'trainer_version': '1.4.2',
            'supports_incremental': False,
            'supports_explainability': True,
            'model_family': 'gnn_multitask',
            'gnn_type': config.model_type if hasattr(config, 'model_type') else 'GCN',
            'num_outputs': self.num_outputs
        })
        
        # 自動選擇設備
        if device == "auto":
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self.device = torch.device(device)
        
        self.train_mean_tensor = None
        
        self.logger.info(
            f"MultiTaskGNN Trainer 初始化: "
            f"model_type={config.model_type if hasattr(config, 'model_type') else 'GCN'}, "
            f"num_outputs={self.num_outputs}, "
            f"device={self.device}"
        )
    
    def prepare_graph_data(
        self,
        X: np.ndarray,
        y: np.ndarray,
        adjacency_matrix: np.ndarray,
        equipment_features: Optional[np.ndarray] = None,
        batch_size: int = 32
    ) -> 'DataLoader':
        """
        準備圖資料
        
        Args:
            X: 特徵矩陣
            y: 目標變數
            adjacency_matrix: 鄰接矩陣
            equipment_features: 設備節點特徵
            batch_size: 批次大小
            
        Returns:
            PyG DataLoader
        """
        n_samples = len(X)
        n_nodes = adjacency_matrix.shape[0]
        
        self.adjacency_matrix = adjacency_matrix
        
        # 轉換鄰接矩陣為 edge_index
        edge_index = torch.from_numpy(np.array(np.where(adjacency_matrix == 1))).long()
        
        # 建立節點特徵
        if X.ndim == 2:
            node_features = X[:, np.newaxis, :].repeat(n_nodes, axis=1)
        else:
            node_features = X
        
        # 拼接設備特徵
        if equipment_features is not None:
            eq_features_expanded = np.expand_dims(equipment_features, axis=0).repeat(n_samples, axis=0)
            node_features = np.concatenate([node_features, eq_features_expanded], axis=-1)
        
        x = torch.from_numpy(node_features).float()
        
        # 確保 y 是二維
        if y.ndim == 1:
            y = y.reshape(-1, 1)
        y_tensor = torch.from_numpy(y).float()
        
        # 建立 Data 列表
        data_list = []
        for i in range(n_samples):
            data = Data(
                x=x[i],
                edge_index=edge_index,
                y=y_tensor[i]
            )
            data_list.append(data)
        
        loader = DataLoader(
            data_list,
            batch_size=batch_size,
            shuffle=True,
            num_workers=0,
            pin_memory=True if self.device.type == 'cuda' else False
        )
        
        return loader
    
    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        adjacency_matrix: np.ndarray,
        equipment_features: Optional[np.ndarray] = None,
        sample_weights: Optional[np.ndarray] = None,
        feature_names: Optional[List[str]] = None,
        physics_loss_fn: Optional[PhysicsInformedHybridLoss] = None
    ) -> Dict[str, Any]:
        """
        執行多任務 GNN 訓練
        
        Args:
            physics_loss_fn: 物理損失函數（可選）
            
        Returns:
            訓練結果
        """
        # 儲存設備特徵
        if equipment_features is not None:
            self.equipment_features = equipment_features
        
        # 準備資料
        train_loader = self.prepare_graph_data(
            X_train, y_train, adjacency_matrix, equipment_features,
            batch_size=getattr(self.config, 'batch_size', 32)
        )
        
        # 從 batch 計算均值
        sample_batch = next(iter(train_loader))
        self.train_mean_tensor = sample_batch.x.mean(dim=0).to(self.device)
        
        val_loader = self.prepare_graph_data(
            X_val, y_val, adjacency_matrix, equipment_features,
            batch_size=getattr(self.config, 'batch_size', 32)
        )
        
        # 推斷輸入維度
        input_dim = sample_batch.x.shape[1]
        
        # 初始化模型
        self.model = MultiTaskGraphNeuralNetwork(
            input_dim=input_dim,
            hidden_dim=getattr(self.config, 'hidden_dim', 64),
            num_outputs=self.num_outputs,
            output_names=self.output_names,
            num_layers=getattr(self.config, 'num_layers', 3),
            model_type=getattr(self.config, 'model_type', 'GCN'),
            dropout=getattr(self.config, 'dropout', 0.2)
        ).to(self.device)
        
        # 優化器
        optimizer = torch.optim.Adam(
            self.model.parameters(),
            lr=getattr(self.config, 'learning_rate', 0.001),
            weight_decay=1e-5
        )
        
        prediction_criterion = nn.MSELoss()
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode='min', factor=0.5, patience=10
        )
        
        # 訓練迴圈
        best_val_loss = float('inf')
        patience_counter = 0
        patience = getattr(self.config, 'early_stopping_patience', 20)
        
        train_losses = []
        val_losses = []
        physics_loss_history = []
        
        num_epochs = getattr(self.config, 'num_epochs', 100)
        
        for epoch in range(num_epochs):
            if physics_loss_fn is not None:
                physics_loss_fn.set_epoch(epoch)
            
            # 訓練模式
            self.model.train()
            epoch_loss = 0
            epoch_physics_loss = 0
            
            for batch in train_loader:
                batch = batch.to(self.device)
                optimizer.zero_grad()
                
                predictions = self.model(batch)
                pred_loss = prediction_criterion(predictions, batch.y)
                
                # 物理損失
                if physics_loss_fn is not None:
                    pred_dict = {name: predictions[:, i] for i, name in enumerate(self.output_names)}
                    target_dict = {name: batch.y[:, i] for i, name in enumerate(self.output_names)}
                    total_loss, loss_metrics = physics_loss_fn(pred_dict, target_dict)
                else:
                    total_loss = pred_loss
                    loss_metrics = {'physics_loss': 0.0}
                
                total_loss.backward()
                optimizer.step()
                
                epoch_loss += total_loss.item()
                epoch_physics_loss += loss_metrics.get('physics_loss', 0.0)
            
            avg_train_loss = epoch_loss / len(train_loader)
            train_losses.append(avg_train_loss)
            if physics_loss_fn:
                physics_loss_history.append(epoch_physics_loss / len(train_loader))
            
            # 驗證
            self.model.eval()
            val_loss = 0
            stationary_val_loss = 0
            
            with torch.no_grad():
                for batch in val_loader:
                    batch = batch.to(self.device)
                    predictions = self.model(batch)
                    
                    if physics_loss_fn is not None:
                        pred_dict = {name: predictions[:, i] for i, name in enumerate(self.output_names)}
                        target_dict = {name: batch.y[:, i] for i, name in enumerate(self.output_names)}
                        loss, loss_metrics = physics_loss_fn(pred_dict, target_dict)
                        
                        stationary_pred_loss = loss_metrics.get('prediction_loss', 0.0)
                        stationary_physics_loss = loss_metrics.get('physics_loss', 0.0)
                        fixed_physics_weight = physics_loss_fn.physics_weight
                        stationary_loss = stationary_pred_loss + fixed_physics_weight * stationary_physics_loss
                    else:
                        loss = prediction_criterion(predictions, batch.y)
                        stationary_loss = loss.item()
                    
                    val_loss += loss.item()
                    stationary_val_loss += stationary_loss
            
            avg_val_loss = val_loss / len(val_loader)
            avg_stationary_val_loss = stationary_val_loss / len(val_loader)
            val_losses.append(avg_val_loss)
            
            scheduler.step(avg_stationary_val_loss)
            
            # Early Stopping
            if avg_stationary_val_loss < best_val_loss:
                best_val_loss = avg_stationary_val_loss
                patience_counter = 0
                self.best_model_state = self.model.state_dict().copy()
            else:
                patience_counter += 1
            
            if patience_counter >= patience:
                self.logger.info(f"Early stopping at epoch {epoch}")
                break
            
            if epoch % 10 == 0:
                log_msg = f"Epoch {epoch}: train_loss={avg_train_loss:.4f}, val_loss={avg_val_loss:.4f}"
                if physics_loss_fn:
                    log_msg += f", physics_loss={physics_loss_history[-1]:.4f}"
                self.logger.info(log_msg)
        
        # 載入最佳模型
        self.model.load_state_dict(self.best_model_state)
        self.is_fitted = True
        
        self.training_history = {
            'train_losses': train_losses,
            'val_losses': val_losses,
            'best_epoch': len(train_losses) - patience_counter - 1,
            'best_val_loss': best_val_loss,
            'num_epochs': len(train_losses),
            'physics_loss_history': physics_loss_history if physics_loss_fn else None
        }
        
        return {
            'model': self.model,
            'best_iteration': self.training_history['best_epoch'],
            'training_history': self.training_history,
            'best_val_loss': best_val_loss,
            'num_outputs': self.num_outputs,
            'output_names': self.output_names
        }
    
    def predict(
        self,
        X: np.ndarray,
        adjacency_matrix: Optional[np.ndarray] = None,
        equipment_features: Optional[np.ndarray] = None,
        batch_size: int = 32
    ) -> Dict[str, np.ndarray]:
        """
        執行預測
        
        Returns:
            Dict[str, np.ndarray]: {output_name: predictions}
        """
        if not self.is_fitted:
            raise RuntimeError("E702: 模型尚未訓練")
        
        self.model.eval()
        
        if adjacency_matrix is None:
            if hasattr(self, 'adjacency_matrix') and self.adjacency_matrix is not None:
                adjacency_matrix = self.adjacency_matrix
            else:
                raise ValueError("E759: GNN 預測必須提供 adjacency_matrix")
        
        if equipment_features is None:
            equipment_features = getattr(self, 'equipment_features', None)
        
        y_dummy = np.zeros((len(X), self.num_outputs))
        
        predict_loader = self.prepare_graph_data(
            X, y_dummy, adjacency_matrix,
            equipment_features=equipment_features,
            batch_size=batch_size
        )
        
        predictions_dict = {name: [] for name in self.output_names}
        
        with torch.no_grad():
            for batch in predict_loader:
                batch = batch.to(self.device)
                output = self.model(batch)
                
                for idx, name in enumerate(self.output_names):
                    predictions_dict[name].extend(output[:, idx].cpu().numpy())
        
        return {name: np.array(preds) for name, preds in predictions_dict.items()}
    
    def save_model(self, path: Path):
        """儲存模型"""
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'config': self.config.__dict__ if hasattr(self.config, '__dict__') else {},
            'training_history': self.training_history,
            'adjacency_matrix': getattr(self, 'adjacency_matrix', None),
            'train_mean_tensor': getattr(self, 'train_mean_tensor', None),
            'equipment_features': getattr(self, 'equipment_features', None),
            'num_outputs': self.num_outputs,
            'output_names': self.output_names
        }, path)
    
    def load_model(self, path: Path):
        """載入模型"""
        checkpoint = torch.load(path, map_location=self.device)
        
        # 重建模型（需要知道輸入維度）
        self.num_outputs = checkpoint.get('num_outputs', 1)
        self.output_names = checkpoint.get('output_names', ["output_0"])
        
        if self.model is None:
            raise RuntimeError("模型尚未初始化，請先呼叫 prepare_graph_data 建立模型")
        
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.training_history = checkpoint['training_history']
        self.adjacency_matrix = checkpoint.get('adjacency_matrix', None)
        self.train_mean_tensor = checkpoint.get('train_mean_tensor', None)
        self.equipment_features = checkpoint.get('equipment_features', None)
        self.is_fitted = True
