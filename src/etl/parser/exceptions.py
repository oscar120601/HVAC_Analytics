"""Parser v2.2 specific exceptions."""

from src.exceptions import ContractViolationError


class PointMappingError(ContractViolationError):
    """E106: failed to parse or apply point mapping."""


class MetadataIncompleteError(ContractViolationError):
    """E107: parser metadata missing required fields."""

