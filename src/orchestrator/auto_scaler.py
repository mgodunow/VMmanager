from typing import Dict, List, Optional
import sys
sys.path.append('../..')

from src.shared.logger import setup_logger
from src.infrastructure.database.connection import DatabaseManager
from src.infrastructure.database.repositories import VMRepository
from src.infrastructure.database.models import VMStatus
from src.infrastructure.proxmox.client import ProxmoxClient
from src.infrastructure.monitoring.metrics_storage import MetricsStorage

logger = setup_logger(__name__)

class AutoScaler:
    """Автоматическое масштабирование ресурсов ВМ"""
    
    def __init__(
        self,
        db_manager: DatabaseManager,
        proxmox_client: ProxmoxClient,
        metrics_storage: MetricsStorage,
        cpu_threshold: float = 85.0,
        memory_threshold: float = 85.0,
        check_period_minutes: int = 10,
        max_cpu_cores: int = 8,
        max_memory_gb: int = 16,
        dry_run: bool = False
    ):
        """
        Args:
            db_manager: Менеджер базы данных
            proxmox_client: Клиент Proxmox
            metrics_storage: Хранилище метрик
            cpu_threshold: Порог CPU для масштабирования (%)
            memory_threshold: Порог памяти для масштабирования (%)
            check_period_minutes: Период проверки метрик
            max_cpu_cores: Максимум ядер CPU
            max_memory_gb: Максимум памяти в GB
            dry_run: Режим тестирования
        """
        self.db_manager = db_manager
        self.proxmox = proxmox_client
        self.metrics_storage = metrics_storage
        self.cpu_threshold = cpu_threshold
        self.memory_threshold = memory_threshold
        self.check_period = check_period_minutes
        self.max_cpu = max_cpu_cores
        self.max_memory_mb = max_memory_gb * 1024
        self.dry_run = dry_run
        self.logger = logger
    
    def check_and_scale_vms(self) -> Dict[str, List]:
        """
        Проверить и масштабировать ВМ при необходимости
        
        Returns:
            Словарь с результатами
        """
        result = {
            'checked': [],
            'scaled_cpu': [],
            'scaled_memory': [],
            'failed': [],
            'at_limit': []
        }
        
        self.logger.info("Starting auto-scaling check")
        
        try:
            with self.db_manager.get_session() as session:
                vm_repo = VMRepository(session)
                all_vms = vm_repo.get_all()
                running_vms = [vm for vm in all_vms if vm.status == VMStatus.RUNNING]
                
                self.logger.info(f"Checking {len(running_vms)} running VMs for scaling")
                
                for vm in running_vms:
                    result['checked'].append(vm.vmid)
                    
                    # Получаем средние метрики
                    avg_metrics = self.metrics_storage.calculate_average_metrics(
                        vm.vmid,
                        minutes=self.check_period
                    )
                    
                    if not avg_metrics:
                        continue
                    
                    # Проверяем CPU
                    if avg_metrics['avg_cpu'] > self.cpu_threshold:
                        if self._scale_cpu(vm, avg_metrics):
                            result['scaled_cpu'].append(vm.vmid)
                    
                    # Проверяем память
                    if avg_metrics['avg_memory'] > self.memory_threshold:
                        if self._scale_memory(vm, avg_metrics):
                            result['scaled_memory'].append(vm.vmid)
                
                self.logger.info(
                    f"Auto-scaling completed: "
                    f"CPU scaled={len(result['scaled_cpu'])}, "
                    f"Memory scaled={len(result['scaled_memory'])}"
                )
                
        except Exception as e:
            self.logger.error(f"Error during auto-scaling: {e}", exc_info=True)
        
        return result
    
    def _scale_cpu(self, vm, metrics: dict) -> bool:
        """
        Увеличить CPU для ВМ
        
        Args:
            vm: Объект VirtualMachine
            metrics: Метрики ВМ
            
        Returns:
            True если успешно
        """
        try:
            current_cores = vm.cpu_cores
            
            # Проверяем лимит
            if current_cores >= self.max_cpu:
                self.logger.info(f"VM {vm.vmid} already at max CPU cores ({self.max_cpu})")
                return False
            
            # Увеличиваем на 1 ядро (или можно на 25%)
            new_cores = min(current_cores + 1, self.max_cpu)
            
            self.logger.info(
                f"Scaling CPU for VM {vm.vmid} ({vm.name}): "
                f"{current_cores} -> {new_cores} cores "
                f"(avg CPU: {metrics['avg_cpu']:.1f}%)"
            )
            
            if self.dry_run:
                self.logger.info(f"[DRY RUN] Would scale CPU for VM {vm.vmid}")
                return True
            
            # Обновляем конфигурацию
            self.proxmox.proxmox.nodes(vm.node).qemu(vm.vmid).config.put(
                cores=new_cores
            )
            
            # Обновляем БД
            with self.db_manager.get_session() as session:
                vm_repo = VMRepository(session)
                vm_obj = vm_repo.get_by_id(vm.id)
                vm_obj.ram_mb = new_memory_mb
                session.commit()
            
            self.logger.info(f"Successfully scaled memory for VM {vm.vmid}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error scaling memory for VM {vm.vmid}: {e}")
            return False