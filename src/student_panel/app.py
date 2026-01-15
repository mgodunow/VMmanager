from flask import Flask, render_template
import os
import sys
sys.path.append('..')

from student_panel.config import get_config
from student_panel.routes.auth import auth_bp
from student_panel.routes.vm_control import vm_control_bp
from src.shared.logger import setup_logger
from src.infrastructure.database.connection import DatabaseManager
from src.infrastructure.proxmox.client import ProxmoxClient

def create_app(config_name=None):
    """
    Фабрика приложения Flask
    
    Args:
        config_name: Имя конфигурации (development/production)
        
    Returns:
        Настроенное Flask приложение
    """
    app = Flask(__name__)
    
    # Загружаем конфигурацию
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')
    
    config_class = get_config()
    app.config.from_object(config_class)
    
    # Настраиваем логирование
    logger = setup_logger(
        'student_panel',
        log_file=str(app.config['LOG_FILE']),
        level='DEBUG' if app.config['DEBUG'] else 'INFO'
    )
    
    logger.info("Starting Student Panel application")
    
    # Инициализируем подключение к БД
    db_manager = DatabaseManager(app.config['DATABASE_URL'])
    app.config['DB_MANAGER'] = db_manager
    
    # Инициализируем Proxmox клиент
    proxmox_client = ProxmoxClient(
        host=app.config['PROXMOX_HOST'],
        user=app.config['PROXMOX_USER'],
        password=app.config['PROXMOX_PASSWORD'],
        verify_ssl=app.config['PROXMOX_VERIFY_SSL']
    )
    app.config['PROXMOX_CLIENT'] = proxmox_client
    
    # Регистрируем blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(vm_control_bp)
    
    # Главная страница - редирект на логин или dashboard
    @app.route('/')
    def index():
        from flask import session, redirect, url_for
        if 'user_id' in session:
            return redirect(url_for('vm_control.dashboard'))
        return redirect(url_for('auth.login'))
    
    # Обработка ошибок
    @app.errorhandler(404)
    def not_found(error):
        return "404 Not Found", 404
    
    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal server error: {error}", exc_info=True)
        return "500 Internal Server Error", 500
    
    logger.info("Student Panel application initialized successfully")
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=app.config['DEBUG']
    )