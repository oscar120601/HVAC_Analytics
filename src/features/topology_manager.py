"""
拓樸管理器 (Topology Manager) v1.4

負責管理設備之間的連接關係圖，支援：
- 設備上下游關係查詢
- 鄰接矩陣生成（供 GNN 使用）
- Hop-N 傳播計算
- 循環偵測

錯誤代碼:
- E410: 拓樸循環偵測 (保留給 Feature Annotation)
- E411: 拓樸圖無效
- E413: 拓樸版本不符
"""

from typing import Dict, List, Optional, Set, Tuple, Any
from collections import defaultdict, deque
import numpy as np
from pathlib import Path

from src.utils.logger import get_logger


class TopologyManager:
    """
    拓樸管理器 v1.4
    
    從 FeatureAnnotationManager 讀取設備連接關係，
    提供設備圖查詢與 GNN 所需的鄰接矩陣。
    """
    
    def __init__(self, annotation_manager):
        """
        初始化拓樸管理器
        
        Args:
            annotation_manager: FeatureAnnotationManager 實例
        """
        self.annotation_manager = annotation_manager
        self.logger = get_logger("TopologyManager")
        
        # 設備連接圖 (有向圖: 上游 -> 下游)
        self._graph: Dict[str, List[str]] = defaultdict(list)
        self._reverse_graph: Dict[str, List[str]] = defaultdict(list)
        self._equipment_to_idx: Dict[str, int] = {}
        self._idx_to_equipment: Dict[int, str] = {}
        self._node_types: Dict[str, str] = {}
        self._edges: List[Tuple[str, str]] = []
        
        # 建立拓樸圖
        self._build_topology_graph()
        
        self.logger.info(
            f"TopologyManager 初始化完成: "
            f"節點數={len(self._equipment_to_idx)}, "
            f"邊數={len(self._edges)}"
        )
    
    def _build_topology_graph(self):
        """
        從 AnnotationManager 建立設備連接圖
        
        讀取每個欄位的 equipment_id 和 topology_node_id，
        建立設備之間的上下游關係。
        """
        try:
            # 取得所有欄位標註
            all_columns = self.annotation_manager.get_all_columns()
            
            equipment_nodes = set()
            equipment_topology = {}  # equipment_id -> topology_node_id
            
            # 收集設備資訊
            for col_name in all_columns:
                anno = self.annotation_manager.get_column_annotation(col_name)
                if not anno:
                    continue
                
                eq_id = getattr(anno, 'equipment_id', None)
                topo_node = getattr(anno, 'topology_node_id', None)
                
                if eq_id:
                    equipment_nodes.add(eq_id)
                    if topo_node:
                        equipment_topology[eq_id] = topo_node
            
            # 建立設備到索引的映射
            for idx, eq_id in enumerate(sorted(equipment_nodes)):
                self._equipment_to_idx[eq_id] = idx
                self._idx_to_equipment[idx] = eq_id
                
                # 推斷節點類型
                self._node_types[eq_id] = self._infer_node_type(eq_id)
            
            # 從 annotation_manager 讀取拓樸連接 (如果存在)
            self._load_topology_connections()
            
            # 如果沒有明確連接，嘗試從設備命名推斷
            if not self._edges:
                self._infer_topology_from_naming(equipment_nodes)
            
        except Exception as e:
            self.logger.warning(f"建立拓樸圖時發生錯誤: {e}")
    
    def _infer_node_type(self, equipment_id: str) -> str:
        """
        根據設備 ID 推斷節點類型
        
        Args:
            equipment_id: 設備 ID (如 "CH-01", "CT-02")
            
        Returns:
            節點類型字串
        """
        eq_upper = equipment_id.upper()
        
        if eq_upper.startswith('CH') and 'WP' not in eq_upper:
            return "chiller"
        elif eq_upper.startswith('CT'):
            return "cooling_tower"
        elif 'WP' in eq_upper or 'PUMP' in eq_upper:
            return "pump"
        elif eq_upper.startswith('AHU'):
            return "ahu"
        elif eq_upper.startswith('FCU'):
            return "fcu"
        elif eq_upper.startswith('TOWER'):
            return "cooling_tower"
        else:
            return "sensor"
    
    def _load_topology_connections(self):
        """
        從 AnnotationManager 讀取明確的拓樸連接
        """
        try:
            # 嘗試取得 topology 配置
            config = self.annotation_manager.site_config
            if hasattr(config, 'topology') and config.topology:
                topology = config.topology
                
                # 讀取 edges
                if 'edges' in topology:
                    for edge in topology['edges']:
                        from_node = edge.get('from')
                        to_node = edge.get('to')
                        if from_node and to_node:
                            self._graph[from_node].append(to_node)
                            self._reverse_graph[to_node].append(from_node)
                            self._edges.append((from_node, to_node))
                
                # 讀取 nodes 類型
                if 'nodes' in topology:
                    for node_id, node_info in topology['nodes'].items():
                        if isinstance(node_info, dict) and 'type' in node_info:
                            self._node_types[node_id] = node_info['type']
                            
        except Exception as e:
            self.logger.debug(f"讀取拓樸連接時發生錯誤: {e}")
    
    def _infer_topology_from_naming(self, equipment_nodes: Set[str]):
        """
        從設備命名慣例推斷拓樸連接
        
        HVAC 典型連接:
        - 冷卻塔 (CT) -> 冰水主機 (CH) 的冷卻水側
        - 冰水主機 (CH) -> 冰水泵 (CHWP) -> 空調箱 (AHU)
        """
        # 按類型分組
        chillers = [eq for eq in equipment_nodes if self._node_types.get(eq) == "chiller"]
        towers = [eq for eq in equipment_nodes if self._node_types.get(eq) == "cooling_tower"]
        pumps = [eq for eq in equipment_nodes if self._node_types.get(eq) == "pump"]
        ahus = [eq for eq in equipment_nodes if self._node_types.get(eq) == "ahu"]
        
        # 簡化規則：冷卻塔供應冰水主機
        for chiller in chillers:
            # 找最近的冷卻塔
            for tower in towers:
                self._graph[tower].append(chiller)
                self._reverse_graph[chiller].append(tower)
                self._edges.append((tower, chiller))
        
        # 簡化規則：冰水主機供應冰水泵
        for chiller in chillers:
            for pump in pumps:
                self._graph[chiller].append(pump)
                self._reverse_graph[pump].append(chiller)
                self._edges.append((chiller, pump))
        
        # 簡化規則：冰水泵供應 AHU
        for pump in pumps:
            for ahu in ahus:
                self._graph[pump].append(ahu)
                self._reverse_graph[ahu].append(pump)
                self._edges.append((pump, ahu))
        
        if self._edges:
            self.logger.info(f"從命名慣例推斷 {len(self._edges)} 條連接")
    
    def get_node_count(self) -> int:
        """取得節點數量"""
        return len(self._equipment_to_idx)
    
    def get_all_equipment(self) -> List[str]:
        """取得所有設備 ID 列表"""
        return list(self._equipment_to_idx.keys())
    
    def get_upstream_equipment(
        self, 
        equipment_id: str, 
        recursive: bool = False,
        max_hops: int = 2
    ) -> List[str]:
        """
        取得指定設備的上游設備
        
        Args:
            equipment_id: 設備 ID
            recursive: 是否遞迴取得所有上游
            max_hops: 最大跳數
            
        Returns:
            上游設備 ID 列表
        """
        if equipment_id not in self._reverse_graph:
            return []
        
        if not recursive:
            return list(self._reverse_graph[equipment_id])
        
        # BFS 取得多跳上游
        upstream = set()
        visited = {equipment_id}
        queue = deque([(eq, 1) for eq in self._reverse_graph[equipment_id]])
        
        while queue:
            current_eq, hop = queue.popleft()
            
            if current_eq in visited or hop > max_hops:
                continue
            
            visited.add(current_eq)
            upstream.add(current_eq)
            
            for next_eq in self._reverse_graph.get(current_eq, []):
                if next_eq not in visited:
                    queue.append((next_eq, hop + 1))
        
        return list(upstream)
    
    def get_downstream_equipment(
        self, 
        equipment_id: str,
        recursive: bool = False,
        max_hops: int = 2
    ) -> List[str]:
        """
        取得指定設備的下游設備
        
        Args:
            equipment_id: 設備 ID
            recursive: 是否遞迴取得所有下游
            max_hops: 最大跳數
            
        Returns:
            下游設備 ID 列表
        """
        if equipment_id not in self._graph:
            return []
        
        if not recursive:
            return list(self._graph[equipment_id])
        
        # BFS 取得多跳下游
        downstream = set()
        visited = {equipment_id}
        queue = deque([(eq, 1) for eq in self._graph[equipment_id]])
        
        while queue:
            current_eq, hop = queue.popleft()
            
            if current_eq in visited or hop > max_hops:
                continue
            
            visited.add(current_eq)
            downstream.add(current_eq)
            
            for next_eq in self._graph.get(current_eq, []):
                if next_eq not in visited:
                    queue.append((next_eq, hop + 1))
        
        return list(downstream)
    
    def get_adjacency_matrix(self) -> np.ndarray:
        """
        生成鄰接矩陣（供 GNN 使用）
        
        Returns:
            NxN 鄰接矩陣，N 為設備數
        """
        n = len(self._equipment_to_idx)
        if n == 0:
            return np.array([[]])
        
        adj_matrix = np.zeros((n, n), dtype=np.int32)
        
        for from_eq, to_eq in self._edges:
            if from_eq in self._equipment_to_idx and to_eq in self._equipment_to_idx:
                from_idx = self._equipment_to_idx[from_eq]
                to_idx = self._equipment_to_idx[to_eq]
                adj_matrix[from_idx, to_idx] = 1
        
        return adj_matrix
    
    def get_edge_index(self) -> np.ndarray:
        """
        生成邊索引（COO 格式，供 PyG 使用）
        
        Returns:
            2xE 矩陣，E 為邊數
        """
        if not self._edges:
            return np.array([[], []], dtype=np.int64)
        
        edge_list = []
        for from_eq, to_eq in self._edges:
            if from_eq in self._equipment_to_idx and to_eq in self._equipment_to_idx:
                from_idx = self._equipment_to_idx[from_eq]
                to_idx = self._equipment_to_idx[to_eq]
                edge_list.append([from_idx, to_idx])
        
        if not edge_list:
            return np.array([[], []], dtype=np.int64)
        
        return np.array(edge_list, dtype=np.int64).T
    
    def get_equipment_to_idx(self) -> Dict[str, int]:
        """取得設備到索引的映射"""
        return self._equipment_to_idx.copy()
    
    def get_idx_to_equipment(self) -> Dict[int, str]:
        """取得索引到設備的映射"""
        return self._idx_to_equipment.copy()
    
    def get_node_types(self) -> Dict[str, str]:
        """取得設備節點類型"""
        return self._node_types.copy()
    
    def get_node_type_list(self) -> List[str]:
        """
        取得按索引排序的節點類型列表
        
        Returns:
            節點類型列表，與 adjacency_matrix 順序一致
        """
        return [
            self._node_types.get(self._idx_to_equipment[i], "unknown")
            for i in range(len(self._idx_to_equipment))
        ]
    
    def has_cycle(self) -> bool:
        """檢查拓樸圖是否有循環"""
        visited = set()
        rec_stack = set()
        
        def dfs(node):
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in self._graph.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            
            rec_stack.remove(node)
            return False
        
        for node in self._equipment_to_idx.keys():
            if node not in visited:
                if dfs(node):
                    return True
        
        return False
    
    def detect_cycles(self) -> List[List[str]]:
        """
        偵測所有循環
        
        Returns:
            循環列表，每個循環是設備 ID 列表
        """
        cycles = []
        visited = set()
        
        def dfs(node, path):
            if node in path:
                cycle_start = path.index(node)
                cycles.append(path[cycle_start:] + [node])
                return
            
            if node in visited:
                return
            
            visited.add(node)
            path.append(node)
            
            for neighbor in self._graph.get(node, []):
                dfs(neighbor, path)
            
            path.pop()
        
        for node in self._equipment_to_idx.keys():
            dfs(node, [])
        
        return cycles
    
    def get_topology_info(self) -> Dict[str, Any]:
        """
        取得完整的拓樸資訊
        
        Returns:
            包含 nodes, edges, adjacency_matrix 等資訊的字典
        """
        return {
            "nodes": list(self._equipment_to_idx.keys()),
            "node_types": self.get_node_type_list(),
            "edges": self._edges,
            "adjacency_matrix": self.get_adjacency_matrix().tolist(),
            "equipment_to_idx": self._equipment_to_idx,
            "has_cycle": self.has_cycle()
        }
