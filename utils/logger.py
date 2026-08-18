"""
日志模块 - 每次启动生成独立日志文件
"""
import os
import logging
import datetime
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')

_global_debug = False
_current_log_file = None


def print_banner():
    """输出 ASCII art banner"""
    W = 50  # 总宽度
    def cw(s):
        """计算字符串显示宽度（中文占2）"""
        w = 0
        for ch in s:
            w += 2 if ord(ch) > 127 else 1
        return w

    def pad(s):
        """居中填充到 W-2 宽度"""
        inner = W - 2
        pw = inner - cw(s)
        left = pw // 2
        return ' ' * left + s + ' ' * (pw - left)

    lines = [
        '知识点管理系统  v1.0',
        'Knowledge Base Management System',
    ]
    print('╔' + '═' * (W - 2) + '╗')
    for line in lines:
        print('║' + pad(line) + '║')
    print('╚' + '═' * (W - 2) + '╝')
    print()


class ColoredFormatter(logging.Formatter):
    COLORS = {
        'ERROR': '\033[91m',
        'WARNING': '\033[93m',
        'INFO': '\033[97m',
        'DEBUG': '\033[90m',
    }
    RESET = '\033[0m'

    def format(self, record):
        color = self.COLORS.get(record.levelname, '')
        record.msg = f"{color}{record.msg}{self.RESET}"
        return super().format(record)


def print_step(status, message):
    """根据 status 输出带颜色的步骤前缀"""
    symbols = {
        'ok': '\033[92m✓\033[0m',
        'fail': '\033[91m✗\033[0m',
        'warn': '\033[93m⚠\033[0m',
        'info': '\033[94mℹ\033[0m',
    }
    symbol = symbols.get(status, '')
    print(f"{symbol} {message}")


def get_logger(name=None, debug=False):
    """获取日志实例，每次启动生成带时间戳的日志文件"""
    global _current_log_file
    os.makedirs(LOG_DIR, exist_ok=True)

    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(LOG_DIR, f'startup_{timestamp}.log')
    _current_log_file = log_file

    logger = logging.getLogger(name or 'knowledge_base')
    logger.setLevel(logging.DEBUG)

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    # 文件 handler
    fh = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=10, encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    logger.addHandler(fh)

    # 控制台 handler
    effective_debug = debug or _global_debug
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG if effective_debug else logging.INFO)
    ch.setFormatter(ColoredFormatter('[%(levelname)s] %(message)s'))
    logger.addHandler(ch)

    return logger


def setup_global_debug(debug):
    """设置全局 debug 标志，供所有模块获取"""
    global _global_debug
    _global_debug = debug
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)


def get_current_log_file():
    """获取当前启动的日志文件路径"""
    return _current_log_file