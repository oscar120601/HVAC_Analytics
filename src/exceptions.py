class HVACError(Exception):
    """Base exception for HVAC Analytics project."""
    pass


class DataValidationError(HVACError):
    """Raised when input data fails validation schema."""
    pass


class ConfigurationError(HVACError):
    """Raised when configuration is invalid or missing."""
    pass


class ModelNotTrainedError(HVACError):
    """Raised when attempting to use a model that hasn't been trained."""
    pass


class OptimizationFailedError(HVACError):
    """Raised when the optimization process fails to converge or find a solution."""
    pass


class FeatureExtractionError(HVACError):
    """Raised when feature extraction fails (e.g., missing columns)."""
    pass


# =============================================================================
# Parser v2.1 新增例外類別 (Interface Contract 相關)
# =============================================================================

class ContractViolationError(HVACError):
    """
    違反模組間介面契約 (Interface Contract)。
    
    用於 Parser、Cleaner、BatchProcessor 之間的契約驗證失敗時拋出。
    對應錯誤代碼: E101-E105
    """
    pass


class EncodingError(ContractViolationError):
    """
    編碼相關錯誤。
    
    - 無法偵測檔案編碼
    - UTF-8 BOM 殘留
    - 非 UTF-8 輸出
    
    對應錯誤代碼: E101_ENCODING_MISMATCH
    """
    pass


class TimezoneError(ContractViolationError):
    """
    時區轉換錯誤或非預期時區。
    
    對應錯誤代碼: E102_TIMEZONE_VIOLATION, E111_TIMEZONE_WARNING
    """
    pass


class HeaderValidationError(ContractViolationError):
    """
    標頭驗證錯誤。
    
    - 無法定位標頭行 (E104)
    - 標頭正規化失敗 (E105)
    - 標頭與 Annotation 不匹配 (E409)
    """
    pass
