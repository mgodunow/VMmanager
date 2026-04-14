
import time
import signal
import sys
from pathlib import Path
from datetime import datetime
sys.path.append('..')

from shared.logger import setup_logger
from infrastructure.database.connection import DatabaseManager
from infrastructure.database.repositories import VMRepository
from infrastructure.proxmox.client import ProxmoxClient
from infrastructure.monitoring.metrics_collector import MetricsCollector
from infrastructure.monitoring.metrics_storage import MetricsStorage
from src.orchestrator.inactivity_monitor import InactivityMonitor
from src.orchestrator.auto_scaler import AutoScaler
import os
from dotenv import load_dotenv
import yaml

load_dotenv()
logger = setup_logger(__name__)

class Orchestrator:
    """Главный оркестратор системы"""
    
    def __init__(self, config_path: str = "configs/orchestrator.yaml"):
        """
        Args:
            config_path: Путь к конфигурационному файлу
        """
        self.logger = logger
        self.running = True
        
        # Загружаем конфигурацию
        self.config = self._load_config(config_path)
        
        # Инициализируем компоненты
        self._init_components()
        
        # Обработчик сигналов для graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _load_config(self, config_path: str) -> dict:
        """Загрузить конфигурацию"""
        default_config = {
            'monitoring': {
                'collection_interval_seconds': 300,  # 5 минут
                'metrics_retention_days': 7
            },
            'inactivity_monitor': {
                'check_interval_seconds': 600,  # 10 минут
                'inactivity_threshold_minutes': 60,  # 1 час
                'enabled': True
            },
            'auto_scaler': {
                'check_interval_seconds': 600,  # 10 минут
                'cpu_threshold': 85.0,
                'memory_threshold': 85.0,
                'max_cpu_cores': 8,
                'max_memory_gb': 16,
                'enabled': True
            },
            'dry_run': False  # Режим тестирования
        }
        
        config_file = Path(config_path)
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    user_config = yaml.safe_load(f)
                    default_config.update(user_config)
                    self.logger.info(f"Loaded config from {config_path}")
            except Exception as e:
                self.logger.warning(f"Could not load config file: {e}, using defaults")
        else:
            self.logger.info("No config file found, using default configuration")
        
        return default_config
    
    def _init_components(self):
        """Инициализировать все компоненты"""
        self.logger.info("Initializing orchestrator components...")
        
        # Database
        db_url = os.getenv('DATABASE_URL')
        self.db_manager = DatabaseManager(db_url)
        
        # Proxmox client
        self.proxmox = ProxmoxClient(
            host=os.getenv('PROXMOX_HOST'),
            user=os.getenv('PROXMOX_USER'),
            password=os.getenv('PROXMOX_PASSWORD'),
            verify_ssl=os.getenv('PROXMOX_VERIFY_SSL', 'false').lower() == 'true'
        )
        
        # Monitoring
        self.metrics_collector = MetricsCollector(self.proxmox)
        self.metrics_storage = MetricsStorage(
            db_path="data/metrics.db",
            history_size=100
        )
        
        # Services
        dry_run = self.config.get('dry_run', False)
        
        self.inactivity_monitor = InactivityMonitor(
            db_manager=self.db_manager,
            proxmox_client=self.proxmox,
            metrics_storage=self.metrics_storage,
            inactivity_threshold_minutes=self.config['inactivity_monitor']['inactivity_threshold_minutes'],
            dry_run=dry_run
        )
        
        self.auto_scaler = AutoScaler(
            db_manager=self.db_manager,
            proxmox_client=self.proxmox,
            metrics_storage=self.metrics_storage,
            cpu_threshold=self.config['auto_scaler']['cpu_threshold'],
            memory_threshold=self.config['auto_scaler']['memory_threshold'],
            max_cpu_cores=self.config['auto_scaler']['max_cpu_cores'],
            max_memory_gb=self.config['auto_scaler']['max_memory_gb'],
            dry_run=dry_run
        )
        
        # Таймеры
        self.last_metrics_collection = 0
        self.last_inactivity_check = 0
        self.last_scaling_check = 0
        self.last_cleanup = 0
        
        self.logger.info("✓ All components initialized successfully")
    
    def _signal_handler(self, signum, frame):
        """Обработчик сигналов для graceful shutdown"""
        self.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.running = False
    
    def _collect_metrics(self):
        """Собрать метрики со всех ВМ"""
        try:
            # Получаем список всех ВМ из БД
            with self.db_manager.get_session() as session:
                vm_repo = VMRepository(session)
                all_vms = vm_repo.get_all()
                
                # Формируем список (node, vmid)
                vm_list = [(vm.node, vm.vmid) for vm in all_vms]
            
            # Собираем метрики
            metrics_dict = self.metrics_collector.collect_all_vms_metrics(vm_list)
            
            # Сохраняем метрики
            for vmid, metrics in metrics_dict.items():
                self.metrics_storage.store_metrics(metrics)
            
            self.logger.info(f"✓ Collected and stored metrics for {len(metrics_dict)} VMs")
            
        except Exception as e:
            self.logger.error(f"Error collecting metrics: {e}", exc_info=True)
    
    def _run_inactivity_check(self):
        """Запустить проверку неактивных ВМ"""
        if not self.config['inactivity_monitor']['enabled']:
            return
        
        try:
            result = self.inactivity_monitor.check_and_shutdown_inactive_vms()
            
            if result['shutdown']:
                self.logger.info(
                    f"✓ Shut down {len(result['shutdown'])} inactive VMs: "
                    f"{result['shutdown']}"
                )
            
        except Exception as e:
            self.logger.error(f"Error during inactivity check: {e}", exc_info=True)
    
    def _run_auto_scaling(self):
        """Запустить автомасштабирование"""
        if not self.config['auto_scaler']['enabled']:
            return
        
        try:
            result = self.auto_scaler.check_and_scale_vms()
            
            if result['scaled_cpu'] or result['scaled_memory']:
                self.logger.info(
                    f"✓ Auto-scaling completed: "
                    f"CPU={result['scaled_cpu']}, "
                    f"Memory={result['scaled_memory']}"
                )
            
        except Exception as e:
            self.logger.error(f"Error during auto-scaling: {e}", exc_info=True)
    
    def _cleanup_old_data(self):
        """Очистить старые данные"""
        try:
            retention_days = self.config['monitoring']['metrics_retention_days']
            self.metrics_storage.cleanup_old_metrics(days=retention_days)
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}", exc_info=True)
    
    def run(self):
        """Главный цикл оркестратора"""
        self.logger.info("="*60)
        self.logger.info("VM Management Orchestrator Started")
        self.logger.info("="*60)
        self.logger.info(f"Dry run mode: {self.config.get('dry_run', False)}")
        self.logger.info(f"Inactivity monitor: {self.config['inactivity_monitor']['enabled']}")
        self.logger.info(f"Auto-scaler: {self.config['auto_scaler']['enabled']}")
        self.logger.info("="*60)
        
        while self.running:
            try:
                current_time = time.time()
                
                # Сбор метрик
                collection_interval = self.config['monitoring']['collection_interval_seconds']
                if current_time - self.last_metrics_collection >= collection_interval:
                    self.logger.info("→ Collecting metrics...")
                    self._collect_metrics()
                    self.last_metrics_collection = current_time
                
                # Проверка неактивных ВМ
                inactivity_interval = self.config['inactivity_monitor']['check_interval_seconds']
                if current_time - self.last_inactivity_check >= inactivity_interval:
                    self.logger.info("→ Checking for inactive VMs...")
                    self._run_inactivity_check()
                    self.last_inactivity_check = current_time
                
                # Автомасштабирование
                scaling_interval = self.config['auto_scaler']['check_interval_seconds']
                if current_time - self.last_scaling_check >= scaling_interval:
                    self.logger.info("→ Running auto-scaling...")
                    self._run_auto_scaling()
                    self.last_scaling_check = current_time
                
                # Очистка старых данных (раз в день)
                if current_time - self.last_cleanup >= 86400:  # 24 часа
                    self.logger.info("→ Cleaning up old data...")
                    self._cleanup_old_data()
                    self.last_cleanup = current_time
                
                # Спим 10 секунд перед следующей проверкой
                time.sleep(10)
                
            except KeyboardInterrupt:
                self.logger.info("Keyboard interrupt received")
                break
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}", exc_info=True)
                time.sleep(30)  # Ждем дольше при ошибке
        
        self.logger.info("Orchestrator stopped gracefully")


def main():
    """Точка входа"""
    print("="*60)
    print("VM Management System - Orchestrator")
    print("="*60)
    
    # Создаем директорию для данных
    Path("data").mkdir(exist_ok=True)
    
    # Запускаем оркестратор
    orchestrator = Orchestrator()
    orchestrator.run()


if __name__ == '__main__':
    main()

