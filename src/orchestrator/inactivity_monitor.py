from datetime import datetime, timedelta
from typing import List, Dict
import sys
sys.path.append('../..')

from src.shared.logger import setup_logger
from src.infrastructure.database.connection import DatabaseManager
from src.infrastructure.database.repositories import VMRepository
from src.infrastructure.database.models import VMStatus
from src.infrastructure.proxmox.client import ProxmoxClient
from src.infrastructure.monitoring.metrics_storage import MetricsStorage

logger = setup_logger(__name__)

class InactivityMonitor:
    """Мониторинг неактивных ВМ и их автоматическое отключение"""
    
    def __init__(
        self,
        db_manager: DatabaseManager,
        proxmox_client: ProxmoxClient,
        metrics_storage: MetricsStorage,
        inactivity_threshold_minutes: int = 60,
        dry_run: bool = False
    ):
        """
        Args:
            db_manager: Менеджер базы данных
            proxmox_client: Клиент Proxmox
            metrics_storage: Хранилище метрик
            inactivity_threshold_minutes: Порог неактивности в минутах
            dry_run: Режим тестирования (не выключать ВМ реально)
        """
        self.db_manager = db_manager
        self.proxmox = proxmox_client
        self.metrics_storage = metrics_storage
        self.inactivity_threshold = inactivity_threshold_minutes
        self.dry_run = dry_run
        self.logger = logger
    
    def check_and_shutdown_inactive_vms(self) -> Dict[str, List[int]]:
        """
        Проверить и выключить неактивные ВМ
        
        Returns:
            Словарь с результатами: {
                'checked': [vmid, ...],
                'shutdown': [vmid, ...],
                'failed': [vmid, ...]
            }
        """
        result = {
            'checked': [],
            'shutdown': [],
            'failed': []
        }
        
        self.logger.info(f"Starting inactivity check (threshold: {self.inactivity_threshold} min)")
        
        try:
            with self.db_manager.get_session() as session:
                vm_repo = VMRepository(session)
                
                # Получаем все работающие ВМ
                all_vms = vm_repo.get_all()
                running_vms = [vm for vm in all_vms if vm.status == VMStatus.RUNNING]
                
                self.logger.info(f"Found {len(running_vms)} running VMs to check")
                
                for vm in running_vms:
                    result['checked'].append(vm.vmid)
                    
                    # Проверяем активность
                    if self._is_vm_inactive(vm.vmid):
                        self.logger.info(
                            f"VM {vm.vmid} ({vm.name}) is inactive for "
                            f"{self.inactivity_threshold} minutes"
                        )
                        
                        if self.dry_run:
                            self.logger.info(f"[DRY RUN] Would shutdown VM {vm.vmid}")
                            result['shutdown'].append(vm.vmid)
                        else:
                            # Выключаем ВМ
                            if self._shutdown_vm(vm):
                                result['shutdown'].append(vm.vmid)
                            else:
                                result['failed'].append(vm.vmid)
                
                self.logger.info(
                    f"Inactivity check completed: "
                    f"checked={len(result['checked'])}, "
                    f"shutdown={len(result['shutdown'])}, "
                    f"failed={len(result['failed'])}"
                )
                
        except Exception as e:
            self.logger.error(f"Error during inactivity check: {e}", exc_info=True)
        
        return result
    
    def _is_vm_inactive(self, vmid: int) -> bool:
        """
        Проверить, является ли ВМ неактивной
        
        Args:
            vmid: ID виртуальной машины
            
        Returns:
            True если неактивна
        """
        # Получаем средние метрики за период
        avg_metrics = self.metrics_storage.calculate_average_metrics(
            vmid,
            minutes=self.inactivity_threshold
        )
        
        if not avg_metrics:
            self.logger.debug(f"No metrics available for VM {vmid}")
            return False
        
        # Проверяем, достаточно ли у нас данных
        if avg_metrics['samples_count'] < self.inactivity_threshold * 0.7:
            self.logger.debug(
                f"Not enough samples for VM {vmid}: "
                f"{avg_metrics['samples_count']}/{self.inactivity_threshold}"
            )
            return False
        
        # Критерии неактивности:
        # - CPU < 5%
        # - Сетевой трафик < 0.01 MB/s (10 KB/s)
        is_inactive = (
            avg_metrics['avg_cpu'] < 5.0 and
            avg_metrics['avg_network_in'] < 0.01 and
            avg_metrics['avg_network_out'] < 0.01
        )
        
        if is_inactive:
            self.logger.debug(
                f"VM {vmid} inactive: "
                f"CPU={avg_metrics['avg_cpu']:.2f}%, "
                f"NET_IN={avg_metrics['avg_network_in']:.4f} MB/s, "
                f"NET_OUT={avg_metrics['avg_network_out']:.4f} MB/s"
            )
        
        return is_inactive
    
    def _shutdown_vm(self, vm) -> bool:
        """
        Выключить ВМ
        
        Args:
            vm: Объект VirtualMachine из БД
            
        Returns:
            True если успешно
        """
        try:
            self.logger.info(f"Shutting down inactive VM {vm.vmid} ({vm.name})")
            
            # Пытаемся корректно выключить
            success = self.proxmox.shutdown_vm(vm.node, vm.vmid)
            
            if success:
                # Ждем выключения
                if self.proxmox.wait_for_status(vm.node, vm.vmid, 'stopped', timeout=60):
                    # Обновляем статус в БД
                    with self.db_manager.get_session() as session:
                        vm_repo = VMRepository(session)
                        vm_repo.update_status(vm.id, VMStatus.STOPPED)
                    
                    self.logger.info(f"Successfully shut down VM {vm.vmid}")
                    return True
                else:
                    # Принудительно выключаем
                    self.logger.warning(f"Graceful shutdown timeout for VM {vm.vmid}, forcing stop")
                    self.proxmox.stop_vm(vm.node, vm.vmid)
                    self.proxmox.wait_for_status(vm.node, vm.vmid, 'stopped', timeout=30)
                    
                    with self.db_manager.get_session() as session:
                        vm_repo = VMRepository(session)
                        vm_repo.update_status(vm.id, VMStatus.STOPPED)
                    
                    return True
            else:
                self.logger.error(f"Failed to shutdown VM {vm.vmid}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error shutting down VM {vm.vmid}: {e}", exc_info=True)
            return False