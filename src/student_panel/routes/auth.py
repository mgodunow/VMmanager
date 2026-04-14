from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from functools import wraps
import sys
sys.path.append('../..')

from src.shared.security import SecurityUtils
from src.shared.exceptions import AuthenticationException
from src.shared.logger import setup_logger
from src.infrastructure.database.connection import DatabaseManager
from src.infrastructure.database.repositories import UserRepository

auth_bp = Blueprint('auth', __name__)
logger = setup_logger(__name__)

def login_required(f):
    """Декоратор для проверки авторизации"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Пожалуйста, войдите в систему', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/test')
def test():
    return "Auth Blueprint is working!"

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Страница входа"""
    if 'user_id' in session:
        return redirect(url_for('vm_control.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            flash('Введите логин и пароль', 'error')
            return render_template('login.html')
        
        try:
            # Получаем DB manager из конфигурации приложения через current_app
            db_manager = current_app.config['DB_MANAGER']
            
            with db_manager.get_session() as db_session:
                user_repo = UserRepository(db_session)
                user = user_repo.get_by_username(username)
                
                if not user:
                    logger.warning(f"Login attempt for non-existent user: {username}")
                    flash('Неверный логин или пароль', 'error')
                    return render_template('login.html')
                
                if not user.is_active:
                    logger.warning(f"Login attempt for inactive user: {username}")
                    flash('Аккаунт деактивирован. Обратитесь к администратору', 'error')
                    return render_template('login.html')
                
                # Проверяем пароль
                if not SecurityUtils.verify_password(password, user.password_hash, user.password_salt):
                    logger.warning(f"Failed login attempt for user: {username}")
                    flash('Неверный логин или пароль', 'error')
                    return render_template('login.html')
                
                # Успешный вход
                session['user_id'] = user.id
                session['username'] = user.username
                session['role'] = user.role.value
                session.permanent = True
                
                logger.info(f"User logged in successfully: {username}")
                flash(f'Добро пожаловать, {user.full_name or user.username}!', 'success')
                return redirect(url_for('vm_control.dashboard'))
                
        except Exception as e:
            logger.error(f"Login error: {e}", exc_info=True)
            flash('Ошибка при входе. Попробуйте позже', 'error')
            return render_template('login.html')
    
    return render_template('088')

@auth_bp.route('/logout')
def logout():
    """Выход из системы"""
    username = session.get('username', 'Unknown')
    session.clear()
    logger.info(f"User logged out: {username}")
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('auth.login'))