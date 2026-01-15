from proxmoxer import ProxmoxAPI
from typing import Optional, Dict, Any
import time

class ProxmoxClient:
    """Клиент для взаимодействия с Proxmox"""
    
    def __init__(self, host: str, user: str, password: str, verify_ssl: bool = False):
        """
        Args:
            host: Адрес Proxmox сервера
            user: Пользователь (например, root@pam)
            password: Пароль
            verify_ssl: Проверять SSL сертификат
        """
        self.proxmox = ProxmoxAPI(
            host,
            user=user,
            password=password,
            verify_ssl=verify_ssl
        )
    
    def get_vm_status(self, node: str, vmid: int) -> Dict[str, Any]:
        """
        Получить статус ВМ
        
        Args:
            node: Имя ноды
            vmid: ID виртуальной машины
            
        Returns:
            Информация о статусе ВМ
        """
        return self.proxmox.nodes(node).qemu(vmid).status.current.get()
    
    def start_vm(self, node: str, vmid: int) -> bool:
        """
        Запустить ВМ
        
        Args:
            node: Имя ноды
            vmid: ID виртуальной машины
            
        Returns:
            True если успешно
        """
        try:
            self.proxmox.nodes(node).qemu(vmid).status.start.post()
            return True
        except Exception as e:
            print(f"Error starting VM {vmid}: {e}")
            return False
    
    def stop_vm(self, node: str, vmid: int) -> bool:
        """
        Остановить ВМ
        
        Args:
            node: Имя ноды
            vmid: ID виртуальной машины
            
        Returns:
            True если успешно
        """
        try:
            self.proxmox.nodes(node).qemu(vmid).status.stop.post()
            return True
        except Exception as e:
            print(f"Error stopping VM {vmid}: {e}")
            return False
    
    def shutdown_vm(self, node: str, vmid: int) -> bool:
        """
        Корректно выключить ВМ (через гостевую ОС)
        
        Args:
            node: Имя ноды
            vmid: ID виртуальной машины
            
        Returns:
            True если успешно
        """
        try:
            self.proxmox.nodes(node).qemu(vmid).status.shutdown.post()
            return True
        except Exception as e:
            print(f"Error shutting down VM {vmid}: {e}")
            return False
    
    def get_vm_config(self, node: str, vmid: int) -> Dict[str, Any]:
        """Получить конфигурацию ВМ"""
        return self.proxmox.nodes(node).qemu(vmid).config.get()
    
    def wait_for_status(self, node: str, vmid: int, target_status: str, 
                       timeout: int = 60) -> bool:
        """
        Ожидать определенного статуса ВМ
        
        Args:
            node: Имя ноды
            vmid: ID виртуальной машины
            target_status: Ожидаемый статус ('running' или 'stopped')
            timeout: Таймаут в секундах
            
        Returns:
            True если статус достигнут
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            status = self.get_vm_status(node, vmid)
            if status.get('status') == target_status:
                return True
            time.sleep(2)
        return False