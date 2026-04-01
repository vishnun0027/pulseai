"""
storage/logging_config.py
Centralized logging configuration with file rotation.
"""

import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logger(name: str, log_file: str, level=logging.INFO):
    """
    Configure a logger with both console and file output.
    
    Args:
        name: Logger name (typically __name__)
        log_file: Path to log file (e.g., 'logs/ai_consumer.log')
        level: Logging level (default INFO)
    
    Returns:
        Configured logger instance
    """
    # Ensure logs directory exists
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Prevent duplicate handlers
    if logger.handlers:
        return logger
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s"
    )
    console_handler.setFormatter(console_formatter)
    
    # File handler with rotation (10 MB per file, keep 5 backups)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5
    )
    file_handler.setLevel(level)
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    file_handler.setFormatter(file_formatter)
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger
