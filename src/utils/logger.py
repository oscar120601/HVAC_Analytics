import logging
import sys
from pathlib import Path

def setup_logger(name: str = "hvac_analytics", log_file: str = None, level: int = logging.INFO) -> logging.Logger:
    """
    Setup a standardized logger.
    
    Args:
        name: Logger name (usually __name__)
        log_file: Path to log file. If None, logs only to console.
        level: Logging level
        
    Returns:
        Configured logger
    """
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Check if logger already has handlers to prevent duplicate logs
    if logger.handlers:
        return logger
        
    # Create formatters
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File Handler (if requested)
    if log_file:
        # Ensure log directory exists
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
    return logger

def get_logger(name: str) -> logging.Logger:
    """
    Get an existing logger or create one with default settings
    wrapper around logging.getLogger but ensures we can standardize later if needed.
    """
    return logging.getLogger(name)
