from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

Base = declarative_base()

class UserRole(enum.Enum):
    """Роли пользователей"""
    STUDENT = "student"
    ADMIN = "admin"
    TEACHER = "teacher"

class VMStatus(enum.Enum):
    """Статусы ВМ"""
    RUNNING = "running"
    STOPPED = "stopped"
    PAUSED = "paused"
    ERROR = "error"

class User(Base):
    """Модель пользователя"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(64), nullable=False)
    password_salt = Column(String(64), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.STUDENT)
    full_name = Column(String(100))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связь с ВМ
    vm = relationship("VirtualMachine", back_populates="user", uselist=False)

class VirtualMachine(Base):
    """Модель виртуальной машины"""
    __tablename__ = 'virtual_machines'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    vmid = Column(Integer, unique=True, nullable=False, index=True)  # ID в Proxmox
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    node = Column(String(50), nullable=False)  # Нода Proxmox
    status = Column(Enum(VMStatus), default=VMStatus.STOPPED)
    cpu_cores = Column(Integer, default=2)
    ram_mb = Column(Integer, default=2048)
    disk_gb = Column(Integer, default=20)
    ip_address = Column(String(15))
    template_id = Column(Integer, ForeignKey('vm_templates.id'))
    last_activity = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связи
    user = relationship("User", back_populates="vm")
    template = relationship("VMTemplate")

class VMTemplate(Base):
    """Модель шаблона ВМ"""
    __tablename__ = 'vm_templates'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    vmid = Column(Integer, nullable=False)  # ID шаблона в Proxmox
    os_type = Column(String(50))
    default_cpu = Column(Integer, default=2)
    default_ram = Column(Integer, default=2048)
    default_disk = Column(Integer, default=20)
    created_at = Column(DateTime, default=datetime.utcnow)