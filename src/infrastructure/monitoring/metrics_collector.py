import sys
sys.path.append('../..')

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import time
from src.shared.logger import setup_logger
from src.infrastructure.proxmox.client import ProxmoxClient

logger = setup_logger(__name__)

@dataclass
class VMMetrics:
    """Метрики виртуальной машины"""
    vmid: int
    node: str
    timestamp: datetime
    
    # Основные метрики
    cpu_usage: float  # Процент использования CPU (0-100)
    memory_usage: float  # Процент использования RAM (0-100)
    memory_used_mb: int  # Использовано RAM в MB
    memory_total_mb: int  # Всего RAM в MB
    disk_read_mb: float  # Чтение диска MB/s
    disk_write_mb: float  # Запись диска MB/s
    network_in_mb: float  # Входящий трафик MB/s
    network_out_mb: float  # Исходящий трафик MB/s
    
    # Дополнительные метрики
    uptime_seconds: int  # Время работы в секундах
    status: str  # running, stopped, paused
    
    def is_idle(self, threshold_minutes: int = 60) -> bool:
        """
        Проверяет, является ли ВМ неактивной
        
        Критерии неактивности:
        - CPU < 5%
        - Сетевой трафик < 0.01 MB/s (10 KB/s)
        - Время проверки > threshold_minutes
        """
        return (
            self.cpu_usage < 5.0 and
            self.network_in_mb < 0.01 and
            self.network_out_mb < 0.01
        )
    
    def needs_more_resources(self) -> bool:
        """
        Проверяет, нужны ли ВМ больше ресурсов
        
        Критерии:
        - CPU > 90%
        - RAM > 90%
        """
        return self.cpu_usage > 90.0 or self.memory_usage > 90.0
    
    def to_dict(self) -> dict:
        """Преобразовать в словарь для сохранения"""
        return {
            'vmid': self.vmid,
            'node': self.node,
            'timestamp': self.timestamp.isoformat(),
            'cpu_usage': self.cpu_usage,
            'memory_usage': self.memory_usage,
            'memory_used_mb': self.memory_used_mb,
            'memory_total_mb': self.memory_total_mb,
            'disk_read_mb': self.disk_read_mb,
            'disk_write_mb': self.disk_write_mb,
            'network_in_mb': self.network_in_mb,
            'network_out_mb': self.network_out_mb,
            'uptime_seconds': self.uptime_seconds,
            'status': self.status
        }


class MetricsCollector:
    """Класс для сбора метрик с виртуальных машин"""
    
    def __init__(self, proxmox_client: ProxmoxClient):
        self.proxmox = proxmox_client
        self.logger = logger
        
    def collect_vm_metrics(self, node: str, vmid: int) -> Optional[VMMetrics]:
        """
        Собрать метрики для конкретной ВМ
        
        Args:
            node: Имя ноды Proxmox
            vmid: ID виртуальной машины
            
        Returns:
            VMMetrics или None если ВМ недоступна
        """
        try:
            # Получаем текущий статус
            status_data = self.proxmox.get_vm_status(node, vmid)
            
            if status_data.get('status') != 'running':
                # ВМ не запущена - возвращаем базовые метрики
                return VMMetrics(
                    vmid=vmid,
                    node=node,
                    timestamp=datetime.utcnow(),
                    cpu_usage=0.0,
                    memory_usage=0.0,
                    memory_used_mb=0,
                    memory_total_mb=status_data.get('maxmem', 0) // (1024*1024),
                    disk_read_mb=0.0,
                    disk_write_mb=0.0,
                    network_in_mb=0.0,
                    network_out_mb=0.0,
                    uptime_seconds=0,
                    status=status_data.get('status', 'stopped')
                )
            
            # Вычисляем метрики
            cpu_usage = status_data.get('cpu', 0) * 100  # Proxmox возвращает 0-1
            
            mem_used = status_data.get('mem', 0)
            mem_max = status_data.get('maxmem', 1)
            memory_usage = (mem_used / mem_max * 100) if mem_max > 0 else 0
            
            # Получаем метрики диска и сети (из RRD данных за последнюю минуту)
            try:
                rrd_data = self.proxmox.proxmox.nodes(node).qemu(vmid).rrddata.get(
                    timeframe='minute'
                )
                
                # Берем последнюю точку данных
                if rrd_data and len(rrd_data) > 0:
                    last_point = rrd_data[-1]
                    
                    # Диск (байты/сек -> МБ/сек)
                    disk_read = last_point.get('diskread', 0) / (1024*1024)
                    disk_write = last_point.get('diskwrite', 0) / (1024*1024)
                    
                    # Сеть (байты/сек -> МБ/сек)
                    net_in = last_point.get('netin', 0) / (1024*1024)
                    net_out = last_point.get('netout', 0) / (1024*1024)
                else:
                    disk_read = disk_write = net_in = net_out = 0.0
            except Exception as e:
                self.logger.debug(f"Could not get RRD data for VM {vmid}: {e}")
                disk_read = disk_write = net_in = net_out = 0.0
            
            metrics = VMMetrics(
                vmid=vmid,
                node=node,
                timestamp=datetime.utcnow(),
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                memory_used_mb=mem_used // (1024*1024),
                memory_total_mb=mem_max // (1024*1024),
                disk_read_mb=disk_read,
                disk_write_mb=disk_write,
                network_in_mb=net_in,
                network_out_mb=net_out,
                uptime_seconds=status_data.get('uptime', 0),
                status=status_data.get('status', 'unknown')
            )
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error collecting metrics for VM {vmid} on node {node}: {e}")
            return None
    
    def collect_all_vms_metrics(self, vms: List[tuple]) -> Dict[int, VMMetrics]:
        """
        Собрать метрики для всех ВМ
        
        Args:
            vms: Список кортежей (node, vmid)
            
        Returns:
            Словарь {vmid: VMMetrics}
        """
        metrics_dict = {}
        
        for node, vmid in vms:
            metrics = self.collect_vm_metrics(node, vmid)
            if metrics:
                metrics_dict[vmid] = metrics
        
        self.logger.info(f"Collected metrics for {len(metrics_dict)} VMs")
        return metrics_dict
