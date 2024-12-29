import logging
import logging.handlers
import os

# Redis 配置
CELERY_BROKER_URL = 'redis://:88188818@192.168.6.235:6379/0'
CELERY_RESULT_BACKEND = 'redis://:88188818@192.168.6.235:6379/0'

# MySQL 配置
db_config = {
    'host': '192.168.6.235',
    'database': 'QPM',
    'user': 'qiuhu',
    'password': '88188818'
}

# 此函数用于配置日志
def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)  # 设置日志器的级别

    # 配置日志输出到文件
    log_file_path = os.path.join(os.getcwd(), 'image_processing.log')
    file_handler = logging.handlers.RotatingFileHandler(
        log_file_path,  # 日志文件名
        maxBytes=1024*1024*10,  # 文件大小限制为10MB
        backupCount=5  # 备份份数
    )
    file_handler.setLevel(logging.INFO)  # 设置日志级别为INFO
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)

    # 配置日志输出到标准输出（控制台）
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)  # 设置日志级别为INFO
    console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)

    # 将两个处理器添加到日志器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

# 默认情况下不配置日志，只在被显式调用时配置
# 这样在执行模块级别的代码时不会自动配置日志
log_configured = False

def configure_logging():
    global log_configured
    if not log_configured:
        setup_logging()
        log_configured = True
