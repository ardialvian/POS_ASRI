from .base import BaseConfig

class LinuxConfig(BaseConfig):
    MYSQL_HOST = '127.0.0.1'
    MYSQL_USER = 'root'
    MYSQL_PASSWORD = 'alvienged.'
    MYSQL_DB = 'pos_db'
