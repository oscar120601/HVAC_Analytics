"""
ConfigLoader - 統一配置載入與管理

此模組提供強化的配置載入功能，包含：
1. E406 Excel/YAML 同步檢查
2. 檔案鎖機制（防止並發修改）
3. Checksum 驗證
4. 自動備份與恢復

錯誤代碼:
- E007: 設定檔損毀
- E406: Excel/YAML 不同步
- E408: SSOT 品質標記不匹配

設計原則:
- Thread-safe: 使用檔案鎖防止並發存取
- Atomic: 寫入操作先寫入暫存檔，再原子移動
- Validated: 載入時自動驗證 Schema
"""

import os
import json
import yaml
import hashlib
import fcntl
import logging
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, timezone
from contextlib import contextmanager
from dataclasses import dataclass

from src.etl.config_models import (
    E007_CONFIG_FILE_CORRUPTED,
    E406_EXCEL_YAML_OUT_OF_SYNC,
    E408_SSOT_QUALITY_FLAGS_MISMATCH,
    VALID_QUALITY_FLAGS,
    SiteFeatureConfig,
    ETLConfig,
)

logger = logging.getLogger(__name__)


@dataclass
class SyncCheckResult:
    """同步檢查結果"""
    is_synced: bool
    excel_mtime: Optional[float]
    yaml_mtime: Optional[float]
    checksum_match: bool
    message: str
    recovery_action: Optional[str] = None


class FileLock:
    """
    跨平台檔案鎖
    
    Usage:
        with FileLock("/path/to/file.lock"):
            # 臨界區
            pass
    """
    
    def __init__(self, lock_path: str, timeout: float = 30.0):
        self.lock_path = lock_path
        self.timeout = timeout
        self.lock_file = None
    
    def __enter__(self):
        self.lock_file = open(self.lock_path, 'w')
        try:
            # 嘗試取得獨佔鎖
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            logger.debug(f"取得檔案鎖: {self.lock_path}")
        except (IOError, OSError) as e:
            # 鎖已被其他程序持有
            self.lock_file.close()
            raise RuntimeError(
                f"無法取得檔案鎖（可能另一個程序正在修改配置）: {self.lock_path}"
            ) from e
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.lock_file:
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
            self.lock_file.close()
            logger.debug(f"釋放檔案鎖: {self.lock_path}")


class ConfigLoader:
    """
    配置載入器
    
    負責：
    1. YAML/JSON 設定檔載入
    2. E406 同步檢查
    3. Checksum 驗證
    4. 檔案鎖管理
    
    Usage:
        >>> loader = ConfigLoader()
        >>> config = loader.load_site_config("cgmh_ty")
        >>> 
        >>> # 驗證同步狀態
        >>> result = loader.validate_annotation_sync("cgmh_ty")
        >>> if not result.is_synced:
        ...     print(result.message)
    """
    
    def __init__(self, 
                 config_base_path: str = "config/features",
                 enable_file_lock: bool = True):
        self.config_base_path = Path(config_base_path)
        self.enable_file_lock = enable_file_lock
        self._lock_dir = Path(".locks")
        self._lock_dir.mkdir(exist_ok=True)
    
    def _get_lock_path(self, identifier: str) -> str:
        """取得鎖檔案路徑"""
        return str(self._lock_dir / f"{identifier}.lock")
    
    @contextmanager
    def _acquire_lock(self, identifier: str):
        """取得檔案鎖的上下文管理器"""
        if not self.enable_file_lock:
            yield
            return
        
        lock_path = self._get_lock_path(identifier)
        with FileLock(lock_path):
            yield
    
    def _compute_checksum(self, filepath: str) -> str:
        """計算檔案 SHA256 Checksum"""
        sha256 = hashlib.sha256()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def load_yaml(self, filepath: str, validate_schema: bool = True) -> Dict[str, Any]:
        """
        載入 YAML 檔案
        
        Args:
            filepath: YAML 檔案路徑
            validate_schema: 是否驗證 Schema
            
        Returns:
            解析後的字典
            
        Raises:
            RuntimeError: E007 若檔案損毀
        """
        path = Path(filepath)
        
        with self._acquire_lock(path.stem):
            if not path.exists():
                raise FileNotFoundError(f"設定檔不存在: {filepath}")
            
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                
                if data is None:
                    data = {}
                
                # 驗證 quality_flags_reference 一致性（E408）
                if validate_schema and 'quality_flags_reference' in data:
                    self._validate_quality_flags_reference(data['quality_flags_reference'])
                
                logger.debug(f"已載入 YAML: {filepath}")
                return data
                
            except yaml.YAMLError as e:
                raise RuntimeError(
                    f"[{E007_CONFIG_FILE_CORRUPTED.code}] "
                    f"{E007_CONFIG_FILE_CORRUPTED.user_message_template.format(filepath=filepath)}: {e}"
                ) from e
    
    def load_json(self, filepath: str) -> Dict[str, Any]:
        """
        載入 JSON 檔案
        
        Args:
            filepath: JSON 檔案路徑
            
        Returns:
            解析後的字典
            
        Raises:
            RuntimeError: E007 若檔案損毀
        """
        path = Path(filepath)
        
        with self._acquire_lock(path.stem):
            if not path.exists():
                raise FileNotFoundError(f"設定檔不存在: {filepath}")
            
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                logger.debug(f"已載入 JSON: {filepath}")
                return data
                
            except json.JSONDecodeError as e:
                raise RuntimeError(
                    f"[{E007_CONFIG_FILE_CORRUPTED.code}] "
                    f"{E007_CONFIG_FILE_CORRUPTED.user_message_template.format(filepath=filepath)}: {e}"
                ) from e
    
    def save_yaml(self, 
                  data: Dict[str, Any], 
                  filepath: str,
                  atomic: bool = True) -> None:
        """
        儲存 YAML 檔案（支援原子寫入）
        
        Args:
            data: 要儲存的資料
            filepath: 目標檔案路徑
            atomic: 是否使用原子寫入
        """
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with self._acquire_lock(path.stem):
            if atomic:
                # 寫入暫存檔，然後原子移動
                temp_path = path.with_suffix('.tmp')
                with open(temp_path, 'w', encoding='utf-8') as f:
                    yaml.dump(data, f, allow_unicode=True, sort_keys=False)
                shutil.move(str(temp_path), str(path))
            else:
                with open(path, 'w', encoding='utf-8') as f:
                    yaml.dump(data, f, allow_unicode=True, sort_keys=False)
        
        logger.debug(f"已儲存 YAML: {filepath}")
    
    def _validate_quality_flags_reference(self, reference_flags: List[str]):
        """
        驗證 quality_flags_reference 與 SSOT 一致（E408）
        
        Raises:
            RuntimeError: E408 若不一致
        """
        current_flags = set(VALID_QUALITY_FLAGS)
        reference_set = set(reference_flags)
        
        if current_flags != reference_set:
            missing = current_flags - reference_set
            extra = reference_set - current_flags
            
            error_msg = f"[{E408_SSOT_QUALITY_FLAGS_MISMATCH.code}] "
            error_msg += E408_SSOT_QUALITY_FLAGS_MISMATCH.user_message_template
            
            if missing:
                error_msg += f"\n缺少的 flags: {missing}"
            if extra:
                error_msg += f"\n多餘的 flags: {extra}"
            
            raise RuntimeError(error_msg)
    
    def validate_annotation_sync(self, 
                                  site_id: str,
                                  excel_path: Optional[str] = None,
                                  yaml_path: Optional[str] = None) -> SyncCheckResult:
        """
        E406 同步檢查: 驗證 Excel 與 YAML 是否同步
        
        檢查項目:
        1. 檔案存在性
        2. 時間戳: mtime(excel) ≤ mtime(yaml)
        3. Checksum 一致性
        
        Args:
            site_id: 案場 ID
            excel_path: Excel 檔案路徑（預設: tools/features/templates/{site_id}.xlsx）
            yaml_path: YAML 檔案路徑（預設: config/features/sites/{site_id}.yaml）
            
        Returns:
            SyncCheckResult
        """
        if excel_path is None:
            excel_path = f"tools/features/templates/{site_id}.xlsx"
        if yaml_path is None:
            yaml_path = f"config/features/sites/{site_id}.yaml"
        
        excel_file = Path(excel_path)
        yaml_file = Path(yaml_path)
        
        excel_mtime = None
        yaml_mtime = None
        checksum_match = False
        
        # 檢查檔案存在性
        if not excel_file.exists():
            return SyncCheckResult(
                is_synced=False,
                excel_mtime=None,
                yaml_mtime=None,
                checksum_match=False,
                message=f"[{E406_EXCEL_YAML_OUT_OF_SYNC.code}] Excel 檔案不存在: {excel_path}",
                recovery_action="執行: python -m tools.features.wizard --create-excel"
            )
        
        if not yaml_file.exists():
            return SyncCheckResult(
                is_synced=False,
                excel_mtime=None,
                yaml_mtime=None,
                checksum_match=False,
                message=f"[{E406_EXCEL_YAML_OUT_OF_SYNC.code}] YAML 檔案不存在: {yaml_path}",
                recovery_action="執行: python -m tools.features.excel_to_yaml --site " + site_id
            )
        
        excel_mtime = excel_file.stat().st_mtime
        yaml_mtime = yaml_file.stat().st_mtime
        
        # 檢查時間戳
        if excel_mtime > yaml_mtime:
            return SyncCheckResult(
                is_synced=False,
                excel_mtime=excel_mtime,
                yaml_mtime=yaml_mtime,
                checksum_match=False,
                message=(
                    f"[{E406_EXCEL_YAML_OUT_OF_SYNC.code}] "
                    f"Excel 檔案 ({datetime.fromtimestamp(excel_mtime)}) "
                    f"比 YAML 檔案 ({datetime.fromtimestamp(yaml_mtime)}) 新，"
                    f"表示 Excel 已修改但未重新轉換"
                ),
                recovery_action=f"執行: python -m tools.features.excel_to_yaml --site {site_id}"
            )
        
        # 檢查 Checksum
        try:
            yaml_data = self.load_yaml(str(yaml_file), validate_schema=False)
            stored_checksum = yaml_data.get('excel_checksum')
            
            if stored_checksum:
                actual_checksum = self._compute_checksum(str(excel_file))
                checksum_match = (stored_checksum == actual_checksum)
                
                if not checksum_match:
                    return SyncCheckResult(
                        is_synced=False,
                        excel_mtime=excel_mtime,
                        yaml_mtime=yaml_mtime,
                        checksum_match=False,
                        message=(
                            f"[{E406_EXCEL_YAML_OUT_OF_SYNC.code}] "
                            f"Checksum 不匹配: 儲存的 {stored_checksum[:16]}... "
                            f"vs 實際的 {actual_checksum[:16]}..."
                        ),
                        recovery_action=f"執行: python -m tools.features.excel_to_yaml --site {site_id} --force"
                    )
            else:
                # 沒有儲存 checksum，視為不同步
                return SyncCheckResult(
                    is_synced=False,
                    excel_mtime=excel_mtime,
                    yaml_mtime=yaml_mtime,
                    checksum_match=False,
                    message=f"[{E406_EXCEL_YAML_OUT_OF_SYNC.code}] YAML 缺少 excel_checksum 欄位",
                    recovery_action=f"執行: python -m tools.features.excel_to_yaml --site {site_id} --force"
                )
        
        except Exception as e:
            return SyncCheckResult(
                is_synced=False,
                excel_mtime=excel_mtime,
                yaml_mtime=yaml_mtime,
                checksum_match=False,
                message=f"[{E406_EXCEL_YAML_OUT_OF_SYNC.code}] 檢查過程發生錯誤: {e}",
                recovery_action="檢查檔案權限與內容完整性"
            )
        
        # 全部通過
        return SyncCheckResult(
            is_synced=True,
            excel_mtime=excel_mtime,
            yaml_mtime=yaml_mtime,
            checksum_match=True,
            message="Excel 與 YAML 已同步"
        )
    
    def load_site_config(self, 
                         site_id: str,
                         skip_sync_check: bool = False) -> SiteFeatureConfig:
        """
        載入案場特徵配置
        
        Args:
            site_id: 案場 ID
            skip_sync_check: 是否跳過 E406 同步檢查
            
        Returns:
            SiteFeatureConfig
            
        Raises:
            RuntimeError: E406 若不同步且未跳過檢查
        """
        yaml_path = self.config_base_path / "sites" / f"{site_id}.yaml"
        
        # E406 同步檢查
        if not skip_sync_check:
            sync_result = self.validate_annotation_sync(site_id, yaml_path=str(yaml_path))
            if not sync_result.is_synced:
                logger.error(sync_result.message)
                if sync_result.recovery_action:
                    logger.info(f"恢復建議: {sync_result.recovery_action}")
                raise RuntimeError(sync_result.message)
        
        # 載入 YAML
        data = self.load_yaml(str(yaml_path))
        
        # 解析為 Pydantic 模型
        config = SiteFeatureConfig(**data)
        logger.info(f"已載入案場配置: {site_id}")
        
        return config
    
    def load_etl_config(self, 
                        site_id: str,
                        config_path: Optional[str] = None,
                        skip_sync_check: bool = False) -> ETLConfig:
        """
        載入 ETL 全域配置
        
        Args:
            site_id: 案場 ID
            config_path: 設定檔路徑（預設: config/settings.yaml）
            skip_sync_check: 是否跳過 E406 同步檢查
            
        Returns:
            ETLConfig
        """
        if config_path is None:
            config_path = "config/settings.yaml"
        
        config_file = Path(config_path)
        
        if config_file.exists():
            data = self.load_yaml(str(config_file))
        else:
            data = {}
        
        # 確保 site_id 設定
        data['site_id'] = site_id
        
        # 載入並合併 annotation 配置
        try:
            annotation_config = self.load_site_config(site_id, skip_sync_check=skip_sync_check)
            data['annotation'] = annotation_config
        except FileNotFoundError:
            logger.warning(f"案場 {site_id} 的特徵配置不存在，使用預設值")
            data['annotation'] = SiteFeatureConfig(site_id=site_id)
        
        return ETLConfig(**data)
    
    def create_backup(self, filepath: str, backup_dir: str = ".backups") -> str:
        """
        建立檔案備份
        
        Args:
            filepath: 原始檔案路徑
            backup_dir: 備份目錄
            
        Returns:
            備份檔案路徑
        """
        path = Path(filepath)
        backup_path = Path(backup_dir)
        backup_path.mkdir(exist_ok=True)
        
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_file = backup_path / f"{path.stem}_{timestamp}{path.suffix}"
        
        shutil.copy2(filepath, backup_file)
        logger.info(f"已建立備份: {backup_file}")
        
        return str(backup_file)
    
    def list_backups(self, 
                     filename: str,
                     backup_dir: str = ".backups") -> List[str]:
        """
        列出檔案的備份列表
        
        Args:
            filename: 原始檔案名稱（不含路徑）
            backup_dir: 備份目錄
            
        Returns:
            備份檔案路徑列表（按時間排序，最新的在最後）
        """
        backup_path = Path(backup_dir)
        if not backup_path.exists():
            return []
        
        stem = Path(filename).stem
        backups = sorted(backup_path.glob(f"{stem}_*"))
        return [str(b) for b in backups]
    
    def restore_backup(self,
                       filename: str,
                       target_path: str,
                       backup_index: int = -1,
                       backup_dir: str = ".backups") -> str:
        """
        從備份恢復檔案
        
        Args:
            filename: 原始檔案名稱
            target_path: 恢復目標路徑
            backup_index: 備份索引（-1 表示最新的）
            backup_dir: 備份目錄
            
        Returns:
            恢復的備份檔案路徑
        """
        backups = self.list_backups(filename, backup_dir)
        
        if not backups:
            raise FileNotFoundError(f"沒有找到 {filename} 的備份")
        
        if backup_index < 0:
            backup_index = len(backups) + backup_index
        
        if backup_index < 0 or backup_index >= len(backups):
            raise IndexError(f"備份索引 {backup_index} 超出範圍")
        
        backup_file = backups[backup_index]
        shutil.copy2(backup_file, target_path)
        logger.info(f"已從 {backup_file} 恢復到 {target_path}")
        
        return backup_file


def load_config(site_id: str, 
                config_base_path: str = "config/features") -> ETLConfig:
    """
    快捷函數: 載入完整 ETL 配置
    
    Args:
        site_id: 案場 ID
        config_base_path: 配置基礎路徑
        
    Returns:
        ETLConfig
    """
    loader = ConfigLoader(config_base_path)
    return loader.load_etl_config(site_id)


__all__ = [
    "ConfigLoader",
    "SyncCheckResult",
    "FileLock",
    "load_config",
]
