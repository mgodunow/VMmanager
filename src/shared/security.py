import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional
import jwt

class SecurityUtils:
    """Утилиты для безопасности"""
    
    @staticmethod
    def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
        """
        Хеширует пароль с использованием SHA-256 и соли
        
        Args:
            password: Пароль для хеширования
            salt: Соль (если None, генерируется новая)
            
        Returns:
            Кортеж (хеш, соль)
        """
        if salt is None:
            salt = secrets.token_hex(32)
        
        password_salt = f"{password}{salt}"
        password_hash = hashlib.sha256(password_salt.encode()).hexdigest()
        
        return password_hash, salt
    
    @staticmethod
    def verify_password(password: str, password_hash: str, salt: str) -> bool:
        """
        Проверяет соответствие пароля хешу
        
        Args:
            password: Введенный пароль
            password_hash: Сохраненный хеш
            salt: Соль
            
        Returns:
            True если пароль верный, иначе False
        """
        computed_hash, _ = SecurityUtils.hash_password(password, salt)
        return computed_hash == password_hash
    
    @staticmethod
    def generate_session_token(user_id: int, secret_key: str, expires_hours: int = 24) -> str:
        """
        Генерирует JWT токен для сессии
        
        Args:
            user_id: ID пользователя
            secret_key: Секретный ключ для подписи
            expires_hours: Время жизни токена в часах
            
        Returns:
            JWT токен
        """
        payload = {
            'user_id': user_id,
            'exp': datetime.utcnow() + timedelta(hours=expires_hours),
            'iat': datetime.utcnow()
        }
        
        return jwt.encode(payload, secret_key, algorithm='HS256')
    
    @staticmethod
    def verify_session_token(token: str, secret_key: str) -> Optional[dict]:
        """
        Проверяет и декодирует JWT токен
        
        Args:
            token: JWT токен
            secret_key: Секретный ключ
            
        Returns:
            Payload токена или None если токен невалидный
        """
        try:
            payload = jwt.decode(token, secret_key, algorithms=['HS256'])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
