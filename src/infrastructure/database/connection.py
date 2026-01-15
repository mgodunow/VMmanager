from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from contextlib import contextmanager
from typing import Generator

class DatabaseManager:
    """Менеджер подключений к БД"""
    
    def __init__(self, connection_string: str):
        """
        Args:
            connection_string: Строка подключения PostgreSQL
                Пример: postgresql://user:password@localhost:5432/vm_management
        """
        self.engine = create_engine(
            connection_string,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            echo=False
        )
        
        self.session_factory = sessionmaker(bind=self.engine)
        self.Session = scoped_session(self.session_factory)
    
    @contextmanager
    def get_session(self) -> Generator:
        """
        Контекстный менеджер для работы с сессией
        
        Yields:
            Сессия SQLAlchemy
        """
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def create_tables(self):
        """Создает все таблицы в БД"""
        from .models import Base
        Base.metadata.create_all(self.engine)
    
    def drop_tables(self):
        """Удаляет все таблицы из БД"""
        from .models import Base
        Base.metadata.drop_all(self.engine)