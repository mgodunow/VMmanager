import sqlite3
from pathlib import Path
from typing import List, Optional, Dict
from collections import deque
import json
from datetime import datetime, timedelta
from .metrics_collector import VMMetrics
from src.shared.logger import setup_logger

class MetricsStorage:
    """Хранилище метрик с историей"""
    
    def __init__(self, db_path: str = "metrics.db", history_size: int = 100):
        """
        Args:
            db_path: Путь к SQLite базе данных
            history_size: Количество точек истории в памяти для каждой ВМ
        """
        self.db_path = Path(db_path)
        self.history_size = history_size
        
        # История в памяти: {vmid: deque([metrics, ...])}
        self.memory_history: Dict[int, deque] = {}
        
        # Инициализация БД
        self._init_database()
        
        self.logger = setup_logger(__name__)
    
    def _init_database(self):
        """Создать таблицу для хранения метрик"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Создаем таблицу
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vm_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vmid INTEGER NOT NULL,
                node TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                metrics_json TEXT NOT NULL
            )
        """)
        
        # Создаем индекс отдельной командой
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_vmid_timestamp 
            ON vm_metrics(vmid, timestamp)
        """)
        
        conn.commit()
        conn.close()
    
    def store_metrics(self, metrics: VMMetrics):
        """
        Сохранить метрики
        
        Args:
            metrics: Метрики ВМ
        """
        # Сохраняем в память
        if metrics.vmid not in self.memory_history:
            self.memory_history[metrics.vmid] = deque(maxlen=self.history_size)
        
        self.memory_history[metrics.vmid].append(metrics)
        
        # Сохраняем в БД
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO vm_metrics (vmid, node, timestamp, metrics_json)
                VALUES (?, ?, ?, ?)
            """, (
                metrics.vmid,
                metrics.node,
                metrics.timestamp.isoformat(),
                json.dumps(metrics.to_dict())
            ))
            
            conn.commit()
            conn.close()
        except Exception as e:
            self.logger.error(f"Error storing metrics to database: {e}")
    
    def get_recent_metrics(self, vmid: int, count: int = 10) -> List[VMMetrics]:
        """
        Получить последние N метрик для ВМ
        
        Args:
            vmid: ID виртуальной машины
            count: Количество последних записей
            
        Returns:
            Список метрик (от старых к новым)
        """
        if vmid not in self.memory_history:
            return []
        
        history = list(self.memory_history[vmid])
        return history[-count:] if len(history) > count else history
    
    def calculate_average_metrics(self, vmid: int, minutes: int = 60) -> Optional[dict]:
        """
        Вычислить средние метрики за последние N минут
        
        Args:
            vmid: ID виртуальной машины
            minutes: Количество минут для усреднения
            
        Returns:
            Словарь со средними значениями или None
        """
        metrics_list = self.get_recent_metrics(vmid, count=minutes)
        
        if not metrics_list:
            return None
        
        # Фильтруем метрики за нужный период
        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)
        recent_metrics = [m for m in metrics_list if m.timestamp >= cutoff_time]
        
        if not recent_metrics:
            return None
        
        # Вычисляем средние
        count = len(recent_metrics)
        return {
            'vmid': vmid,
            'period_minutes': minutes,
            'samples_count': count,
            'avg_cpu': sum(m.cpu_usage for m in recent_metrics) / count,
            'avg_memory': sum(m.memory_usage for m in recent_metrics) / count,
            'avg_network_in': sum(m.network_in_mb for m in recent_metrics) / count,
            'avg_network_out': sum(m.network_out_mb for m in recent_metrics) / count,
            'max_cpu': max(m.cpu_usage for m in recent_metrics),
            'max_memory': max(m.memory_usage for m in recent_metrics)
        }
    
    def cleanup_old_metrics(self, days: int = 7):
        """
        Удалить старые метрики из БД
        
        Args:
            days: Удалить метрики старше N дней
        """
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                DELETE FROM vm_metrics
                WHERE timestamp < ?
            """, (cutoff.isoformat(),))
            
            deleted = cursor.rowcount
            conn.commit()
            conn.close()
            
            self.logger.info(f"Cleaned up {deleted} old metrics records")
        except Exception as e:
            self.logger.error(f"Error cleaning up old metrics: {e}")
