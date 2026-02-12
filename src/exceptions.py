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
