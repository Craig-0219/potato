import logging
import sys
from logging.handlers import RotatingFileHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("potato")
# 修復：設置日誌系統
# 確保不會重複設置處理器，避免重複輸出
def setup_logging(debug=False):
    """設置日誌系統（修復版）"""
    
    # 修復：檢查是否已經設置過
    logger = logging.getLogger("potato")
    if logger.handlers:
        return logger
    
    # 設置日誌等級
    level = logging.DEBUG if debug else logging.INFO
    logger.setLevel(level)
    
    # 修復：創建格式器
    formatter = logging.Formatter(
        fmt='%(asctime)s - [%(levelname)s] - %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 修復：控制台處理器（避免重複）
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(level)
        logger.addHandler(console_handler)
    
    # 修復：文件處理器（輪轉日誌）
    if not any(isinstance(h, RotatingFileHandler) for h in logger.handlers):
        try:
            file_handler = RotatingFileHandler(
                'bot.log', 
                maxBytes=10*1024*1024,  # 10MB
                backupCount=5,
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(level)
            logger.addHandler(file_handler)
        except Exception as e:
            print(f"⚠️ 無法創建日誌文件：{e}")
    
    # 修復：防止傳播到root logger
    logger.propagate = False
    
    return logger



