import logging
from pathlib import Path
from datetime import datetime


class Logger:
    """File-based logger for debugging agent interactions"""

    def __init__(self, name: str = "Agent", log_level=logging.DEBUG, is_active: bool = True):
        self.is_active = is_active
        self.name = name
        self._log_level = log_level
        self._current_session_id = None
        self._log_dir = Path(__file__).parent / "logs"
        self._logger = None

        if self.is_active:
            self._log_dir.mkdir(exist_ok=True)
            self._logger = self._setup_logging(log_level)

    def _setup_logging(self, log_level):
        """Setup file-based logging for debugging agent interactions"""
        log_dir = self._log_dir
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"{self.name.lower()}_debug_{timestamp}.txt"

        logger = logging.getLogger(f"{self.name}_{timestamp}")
        logger.setLevel(log_level)

        file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
        file_handler.setLevel(log_level)
        file_handler.setFormatter(logging.Formatter(
            '[%(asctime)s] [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        logger.addHandler(file_handler)

        logger.info("=" * 80)
        logger.info(f"{self.name} Debug Session Started")
        logger.info(f"Log file: {log_file}")
        logger.info("=" * 80)

        return logger

    def start_session(self, session_id: str):
        """Switch logging to a session-specific file. Creates if new, appends if existing."""
        if not self.is_active or session_id == self._current_session_id:
            return
        self._current_session_id = session_id
        log_file = self._log_dir / f"{self.name.lower()}_debug_{session_id}.txt"

        logger = logging.getLogger(f"{self.name}_{session_id}")
        logger.setLevel(self._log_level)
        logger.handlers.clear()

        fh = logging.FileHandler(log_file, mode='a', encoding='utf-8')
        fh.setLevel(self._log_level)
        fh.setFormatter(logging.Formatter(
            '[%(asctime)s] [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        logger.addHandler(fh)
        self._logger = logger
    
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