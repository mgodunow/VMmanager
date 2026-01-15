from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Session
from .models import User, VirtualMachine, VMTemplate, UserRole, VMStatus

class UserRepository:
    """Репозиторий для работы с пользователями"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_by_id(self, user_id: int) -> Optional[User]:
        """Получить пользователя по ID"""
        return self.session.query(User).filter(User.id == user_id).first()
    
    def get_by_username(self, username: str) -> Optional[User]:
        """Получить пользователя по имени"""
        return self.session.query(User).filter(User.username == username).first()
    
    def create(self, username: str, email: str, password_hash: str, 
               password_salt: str, role: UserRole = UserRole.STUDENT,
               full_name: Optional[str] = None) -> User:
        """Создать нового пользователя"""
        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            password_salt=password_salt,
            role=role,
            full_name=full_name
        )
        self.session.add(user)
        self.session.flush()
        return user
    
    def get_all_students(self) -> List[User]:
        """Получить всех студентов"""
        return self.session.query(User).filter(User.role == UserRole.STUDENT).all()

class VMRepository:
    """Репозиторий для работы с ВМ"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_by_id(self, vm_id: int) -> Optional[VirtualMachine]:
        """Получить ВМ по ID"""
        return self.session.query(VirtualMachine).filter(VirtualMachine.id == vm_id).first()
    
    def get_by_user_id(self, user_id: int) -> Optional[VirtualMachine]:
        """Получить ВМ пользователя"""
        return self.session.query(VirtualMachine).filter(VirtualMachine.user_id == user_id).first()
    
    def get_by_vmid(self, vmid: int) -> Optional[VirtualMachine]:
        """Получить ВМ по Proxmox VMID"""
        return self.session.query(VirtualMachine).filter(VirtualMachine.vmid == vmid).first()
    
    def create(self, name: str, vmid: int, user_id: int, node: str,
               cpu_cores: int = 2, ram_mb: int = 2048, disk_gb: int = 20,
               template_id: Optional[int] = None) -> VirtualMachine:
        """Создать новую ВМ"""
        vm = VirtualMachine(
            name=name,
            vmid=vmid,
            user_id=user_id,
            node=node,
            cpu_cores=cpu_cores,
            ram_mb=ram_mb,
            disk_gb=disk_gb,
            template_id=template_id,
            status=VMStatus.STOPPED
        )
        self.session.add(vm)
        self.session.flush()
        return vm
    
    def update_status(self, vm_id: int, status: VMStatus):
        """Обновить статус ВМ"""
        vm = self.get_by_id(vm_id)
        if vm:
            vm.status = status
            vm.updated_at = datetime.utcnow()
            self.session.flush()
    
    def update_last_activity(self, vm_id: int):
        """Обновить время последней активности"""
        vm = self.get_by_id(vm_id)
        if vm:
            vm.last_activity = datetime.utcnow()
            self.session.flush()
    
    def get_all(self) -> List[VirtualMachine]:
        """Получить все ВМ"""
        return self.session.query(VirtualMachine).all()