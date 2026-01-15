import os
from pathlib import Path

class Config:
    """Базовая конфигурация"""
    
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = False
    TESTING = False
    
    # Database
    DATABASE_URL = os.getenv(
        'DATABASE_URL',
        'postgresql://vm_admin:vm_password@localhost:5432/vm_management'
    )
    
    # Proxmox
    PROXMOX_HOST = os.getenv('PROXMOX_HOST', 'proxmox.local')
    PROXMOX_USER = os.getenv('PROXMOX_USER', 'root@pam')
    PROXMOX_PASSWORD = os.getenv('PROXMOX_PASSWORD', 'password')
    PROXMOX_VERIFY_SSL = os.getenv('PROXMOX_VERIFY_SSL', 'false').lower() == 'true'
    
    # Session
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 86400  # 24 часа
    
    # Logging
    LOG_DIR = Path('logs')
    LOG_FILE = LOG_DIR / 'student_panel.log'

class DevelopmentConfig(Config):
    """Конфигурация для разработки"""
    DEBUG = True
    SESSION_COOKIE_SECURE = False

class ProductionConfig(Config):
    """Конфигурация для продакшена"""
    DEBUG = False

# Выбор конфигурации по переменной окружения
config_dict = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

def get_config():
    """Получить конфигурацию по переменной окружения"""
    env = os.getenv('FLASK_ENV', 'default')
    return config_dict.get(env, DevelopmentConfig)