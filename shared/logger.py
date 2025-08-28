import logging
import os
import sys
from enum import Enum
from logging.handlers import RotatingFileHandler


class LogLevel(Enum):
    """日誌等級枚舉"""

    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


class ProductionLogFilter(logging.Filter):
    """生產環境日誌過濾器 - 過濾除錯訊息"""

    def filter(self, record):
        # 生產環境下過濾 DEBUG 等級的日誌
        if os.getenv("NODE_ENV") == "production" or os.getenv("ENVIRONMENT") == "production":
            return record.levelno >= logging.INFO
        return True


class LogManager:
    """日誌管理器"""

    def __init__(self):
        self._loggers = {}
        self._initialized = False

    def get_logger(self, name: str = "potato") -> logging.Logger:
        """獲取或創建日誌記錄器"""
        if name not in self._loggers:
            self._loggers[name] = self._create_logger(name)
        return self._loggers[name]

    def _create_logger(self, name: str) -> logging.Logger:
        """創建日誌記錄器"""
        logger = logging.getLogger(name)

        # 避免重複設置
        if logger.handlers:
            return logger

        # 設置日誌等級
        log_level = self._get_log_level()
        logger.setLevel(log_level)

        # 創建格式器
        formatter = self._create_formatter()

        # 添加控制台處理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(log_level)
        console_handler.addFilter(ProductionLogFilter())
        logger.addHandler(console_handler)

        # 添加文件處理器
        try:
            file_handler = RotatingFileHandler(
                "bot.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"  # 10MB
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(log_level)
            file_handler.addFilter(ProductionLogFilter())
            logger.addHandler(file_handler)
        except Exception as e:
            print(f"⚠️ 無法創建日誌文件：{e}")

        # 防止傳播到root logger
        logger.propagate = False

        return logger

    def _get_log_level(self) -> int:
        """獲取日誌等級"""
        level_str = os.getenv("LOG_LEVEL", "INFO").upper()
        debug_mode = os.getenv("DEBUG", "false").lower() == "true"
        is_testing = os.getenv("TESTING", "false").lower() == "true"

        if is_testing:
            return logging.DEBUG
        elif debug_mode:
            return logging.DEBUG

        level_mapping = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }

        return level_mapping.get(level_str, logging.INFO)

    def _create_formatter(self) -> logging.Formatter:
        """創建日誌格式器"""
        is_production = (
            os.getenv("NODE_ENV") == "production" or os.getenv("ENVIRONMENT") == "production"
        )

        if is_production:
            # 生產環境使用結構化格式
            return logging.Formatter(
                fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
            )
        else:
            # 開發環境使用詳細格式
            return logging.Formatter(
                fmt="%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )

    def set_level(self, level: LogLevel, logger_name: str = "potato"):
        """設置日誌等級"""
        logger = self.get_logger(logger_name)
        logger.setLevel(level.value)

        # 更新所有處理器的等級
        for handler in logger.handlers:
            handler.setLevel(level.value)


# 全域日誌管理器
_log_manager = LogManager()

# 獲取預設日誌記錄器
logger = _log_manager.get_logger()


# 向後兼容的設置函數
def setup_logging(debug=False):
    """設置日誌系統（向後兼容）"""
    if debug:
        _log_manager.set_level(LogLevel.DEBUG)
    return logger


def get_logger(name: str = "potato") -> logging.Logger:
    """獲取日誌記錄器"""
    return _log_manager.get_logger(name)


# 生產環境下的日誌清理裝飾器
def production_log_filter(func):
    """生產環境日誌過濾裝飾器"""

    def wrapper(*args, **kwargs):
        # 在生產環境下，將 debug 調用轉為 info
        is_production = os.getenv("NODE_ENV") == "production"
        if is_production and hasattr(args[0], "debug"):
            # 如果是 logger.debug 調用，在生產環境下忽略
            return
        return func(*args, **kwargs)

    return wrapper
