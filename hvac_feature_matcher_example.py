"""
HVAC 特徵分類架構使用範例
展示如何載入 JSON 並進行特徵匹配
"""

import sys
import io
# 設置 stdout 為 UTF-8 編碼
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json
import fnmatch
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class FeatureInfo:
    """特徵資訊資料類別"""
    feature_id: str
    name_zh: str
    name_en: str
    unit: str
    category_id: str
    category_name_zh: str
    category_name_en: str
    emoji: str
    is_target: bool
    wildcard_patterns: List[str]


class HVACFeatureMatcher:
    """HVAC 特徵匹配器"""
    
    def __init__(self, json_path: str = "hvac_feature_classification.json"):
        """初始化並載入分類架構"""
        with open(json_path, 'r', encoding='utf-8') as f:
            self.schema = json.load(f)
        
        # 建立特徵查找表
        self._build_feature_index()
    
    def _build_feature_index(self):
        """建立特徵索引，方便快速查找"""
        self.feature_list: List[FeatureInfo] = []
        self.feature_by_id: Dict[str, FeatureInfo] = {}
        
        for category in self.schema['categories']:
            for feat in category['features']:
                info = FeatureInfo(
                    feature_id=feat['feature_id'],
                    name_zh=feat['name_zh'],
                    name_en=feat['name_en'],
                    unit=feat['unit'],
                    category_id=category['category_id'],
                    category_name_zh=category['name_zh'],
                    category_name_en=category['name_en'],
                    emoji=category['emoji'],
                    is_target=feat.get('is_target', False),
                    wildcard_patterns=feat.get('wildcard_patterns', [])
                )
                self.feature_list.append(info)
                self.feature_by_id[feat['feature_id']] = info
    
    def match_column(self, column_name: str) -> Optional[FeatureInfo]:
        """
        根據欄位名稱匹配特徵
        
        Args:
            column_name: 資料集中的欄位名稱
            
        Returns:
            匹配到的特徵資訊，若無匹配則回傳 None
        """
        column_lower = column_name.lower().strip()
        
        # 優先順序：精確匹配 > 萬用字元匹配
        
        # 1. 精確 ID 匹配
        if column_lower in self.feature_by_id:
            return self.feature_by_id[column_lower]
        
        # 2. 萬用字元匹配
        for feature in self.feature_list:
            for pattern in feature.wildcard_patterns:
                if fnmatch.fnmatch(column_lower, pattern.lower()):
                    return feature
        
        return None
    
    def match_all_columns(self, columns: List[str]) -> Dict[str, Optional[FeatureInfo]]:
        """
        批量匹配多個欄位
        
        Args:
            columns: 欄位名稱列表
            
        Returns:
            欄位名稱到特徵資訊的對照字典
        """
        return {col: self.match_column(col) for col in columns}
    
    def get_target_features(self) -> List[FeatureInfo]:
        """取得所有 Target 特徵（模型預測目標）"""
        return [f for f in self.feature_list if f.is_target]
    
    def get_features_by_category(self, category_id: str) -> List[FeatureInfo]:
        """根據類別 ID 取得該類別的所有特徵"""
        return [f for f in self.feature_list if f.category_id == category_id]
    
    def get_features_by_system(self, system_id: str) -> List[FeatureInfo]:
        """根據父系統 ID 取得該系統的所有特徵"""
        # 取得該系統下的所有類別
        category_ids = [
            cat['category_id'] 
            for cat in self.schema['categories']
            if cat['parent_system'] == system_id
        ]
        return [f for f in self.feature_list if f.category_id in category_ids]
    
    def get_category_summary(self) -> List[Dict]:
        """取得類別摘要資訊"""
        summary = []
        for category in self.schema['categories']:
            feature_count = len(category['features'])
            target_count = sum(1 for f in category['features'] if f.get('is_target'))
            summary.append({
                'category_id': category['category_id'],
                'name_zh': category['name_zh'],
                'name_en': category['name_en'],
                'emoji': category['emoji'],
                'feature_count': feature_count,
                'target_count': target_count,
                'parent_system': category['parent_system']
            })
        return summary
    
    def print_match_results(self, columns: List[str]):
        """印出欄位匹配結果報告"""
        print("=" * 80)
        print("HVAC 特徵匹配報告")
        print("=" * 80)
        
        matched = []
        unmatched = []
        
        for col in columns:
            feature = self.match_column(col)
            if feature:
                matched.append((col, feature))
            else:
                unmatched.append(col)
        
        # 印出匹配結果
        print(f"\n✅ 已匹配 ({len(matched)}/{len(columns)}):")
        print("-" * 80)
        for col, feat in matched:
            target_mark = " 🎯" if feat.is_target else ""
            print(f"  {feat.emoji} {col:<30} → {feat.category_name_zh} / {feat.name_zh} [{feat.unit}]{target_mark}")
        
        # 印出未匹配欄位
        if unmatched:
            print(f"\n⚠️  未匹配 ({len(unmatched)}):")
            print("-" * 80)
            for col in unmatched:
                print(f"     {col}")
        
        print("\n" + "=" * 80)


def demo():
    """展示如何使用 HVACFeatureMatcher"""
    
    # 建立匹配器
    matcher = HVACFeatureMatcher("hvac_feature_classification.json")
    
    # 模擬資料集中的欄位名稱
    sample_columns = [
        # 匹配成功的欄位
        "CHP_Frequency",
        "chp_power",
        "chilled_water_supply_temp",
        "CHW_Return_Temp",
        "scp_frequency",
        "cooling_load_kW",
        "ct_freq",
        "cwp_power",
        "OAT",
        "wet_bulb_temp",
        "total_power",
        "kw_per_rt",
        
        # 可能未匹配的欄位
        "unknown_column_1",
        "some_random_data",
        "timestamp",
        "building_id"
    ]
    
    # 執行匹配並印出報告
    matcher.print_match_results(sample_columns)
    
    # 取得所有 Target 特徵
    print("\n🎯 Target 特徵（模型預測目標）:")
    print("-" * 80)
    for feat in matcher.get_target_features():
        print(f"  • {feat.feature_id}: {feat.name_zh} ({feat.name_en}) [{feat.unit}]")
    
    # 取得系統摘要
    print("\n\n📊 類別摘要:")
    print("-" * 80)
    for cat in matcher.get_category_summary():
        target_info = f", Targets: {cat['target_count']}" if cat['target_count'] > 0 else ""
        print(f"  {cat['emoji']} {cat['name_zh']:<12} ({cat['category_id']:<25}): "
              f"{cat['feature_count']:>2} features{target_info}")


if __name__ == "__main__":
    demo()
