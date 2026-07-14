"""
配置文件
"""

# 数据库配置
DB_CONFIG = {
    'host': '192.168.10.21',
    'port': 5432,
    'database': 'new-api',
    'user': 'root',
    'password': '123456'
}

# 汇率配置：1元 = 68493.15 Token
EXCHANGE_RATE = 68493.15

# 分页默认配置
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# 应用配置
APP_HOST = '0.0.0.0'
APP_PORT = 5000
DEBUG = False