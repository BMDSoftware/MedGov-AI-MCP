import logging
from pathlib import Path
from datetime import datetime


class Logger:
    """File-based logger for debugging agent interactions"""
    
    def __init__(self, name: str = "Agent", log_level=logging.DEBUG, is_active: bool = True):
        self.is_active = is_active
        self.name = name
        self._logger = None
        
        if self.is_active:
            self._logger = self._setup_logging(log_level)
    
    def _setup_logging(self, log_level):
        """Setup file-based logging for debugging agent interactions"""
        # Create logs directory if it doesn't exist
        log_dir = Path(__file__).parent / "logs"
        log_dir.mkdir(exist_ok=True)
        
        # Create timestamped log file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"{self.name.lower()}_debug_{timestamp}.txt"
        
        # Create logger
        logger = logging.getLogger(f"{self.name}_{timestamp}")
        logger.setLevel(log_level)
        
        # Create file handler
        file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
        file_handler.setLevel(log_level)
        
        # Create formatter
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        
        # Add handler to logger
        logger.addHandler(file_handler)
        
        logger.info("=" * 80)
        logger.info(f"{self.name} Debug Session Started")
        logger.info(f"Log file: {log_file}")
        logger.info("=" * 80)
        
        return logger
    
    def log(self, message):
        """Log a message at INFO level (for backward compatibility)"""
        self.info(message)
    
    def debug(self, message):
        """Log a debug message"""
        if self.is_active and self._logger:
            self._logger.debug(message)
    
    def info(self, message):
        """Log an info message"""
        if self.is_active and self._logger:
            self._logger.info(message)
    
    def warning(self, message):
        """Log a warning message"""
        if self.is_active and self._logger:
            self._logger.warning(message)
    
    def error(self, message):
        """Log an error message"""
        if self.is_active and self._logger:
            self._logger.error(message)
    
    def critical(self, message):
        """Log a critical message"""
        if self.is_active and self._logger:
            self._logger.critical(message)