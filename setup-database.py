import sys
from pathlib import Path

# Добавляем путь к src
sys.path.append(str(Path(__file__).parent / 'src'))

from infrastructure.database.connection import DatabaseManager
from infrastructure.database.models import Base, User, VirtualMachine, VMTemplate, UserRole, VMStatus
from shared.security import SecurityUtils
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

def create_tables(db_manager: DatabaseManager):
    """Создать все таблицы"""
    print("Creating database tables...")
    db_manager.create_tables()
    print("✓ Tables created successfully")

def create_test_data(db_manager: DatabaseManager):
    """Создать тестовые данные"""
    print("\nCreating test data...")
    
    with db_manager.get_session() as session:
        # Создаем тестовых пользователей
        print("Creating test users...")
        
        # Администратор
        admin_password_hash, admin_salt = SecurityUtils.hash_password("admin123")
        admin = User(
            username="admin",
            email="admin@university.edu",
            password_hash=admin_password_hash,
            password_salt=admin_salt,
            role=UserRole.ADMIN,
            full_name="Администратор системы",
            is_active=True
        )
        session.add(admin)
        
        # Студенты
        students_data = [
            ("student1", "student1@university.edu", "Иванов Иван Иванович"),
            ("student2", "student2@university.edu", "Петров Петр Петрович"),
            ("student3", "student3@university.edu", "Сидорова Анна Сергеевна"),
        ]
        
        for username, email, full_name in students_data:
            password_hash, salt = SecurityUtils.hash_password("student123")
            student = User(
                username=username,
                email=email,
                password_hash=password_hash,
                password_salt=salt,
                role=UserRole.STUDENT,
                full_name=full_name,
                is_active=True
            )
            session.add(student)
        
        session.flush()
        
        print("✓ Test users created")
        print("\nTest credentials:")
        print("  Admin:    username='admin',    password='admin123'")
        print("  Student1: username='student1', password='student123'")
        print("  Student2: username='student2', password='student123'")
        print("  Student3: username='student3', password='student123'")
        
        # Создаем шаблон ВМ
        print("\nCreating VM template...")
        template = VMTemplate(
            name="Ubuntu 22.04 LTS",
            description="Базовый шаблон с Ubuntu 22.04",
            vmid=9000,
            os_type="Linux",
            default_cpu=2,
            default_ram=2048,
            default_disk=20
        )
        session.add(template)
        session.flush()
        print("✓ VM template created")
        
        # Создаем тестовые ВМ для студентов
        print("\nCreating test VMs...")
        
        # Получаем студентов
        students = session.query(User).filter(User.role == UserRole.STUDENT).all()
        
        for idx, student in enumerate(students):
            vm = VirtualMachine(
                name=f"vm-{student.username}",
                vmid=100 + idx,
                user_id=student.id,
                node="pve",  # Измените на имя вашей ноды Proxmox
                cpu_cores=2,
                ram_mb=2048,
                disk_gb=20,
                template_id=template.id,
                status=VMStatus.STOPPED,
                last_activity=datetime.utcnow()
            )
            session.add(vm)
        
        session.flush()
        print("✓ Test VMs created")
        
        print("\n" + "="*60)
        print("Database initialization completed successfully!")
        print("="*60)

def main():
    """Главная функция"""
    print("="*60)
    print("VM Management System - Database Initialization")
    print("="*60)
    
    # Получаем URL базы данных
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        print("\n❌ ERROR: DATABASE_URL not found in environment variables")
        print("Please create .env file with DATABASE_URL")
        return
    
    print(f"\nDatabase URL: {database_url.split('@')[1] if '@' in database_url else database_url}")
    
    # Создаем менеджер БД
    db_manager = DatabaseManager(database_url)
    
    # Спрашиваем подтверждение
    print("\nThis will:")
    print("1. Create all database tables")
    print("2. Create test users and VMs")
    print("\n⚠️  WARNING: This will drop existing tables if they exist!")
    
    confirm = input("\nDo you want to continue? (yes/no): ")
    
    if confirm.lower() != 'yes':
        print("Operation cancelled")
        return
    
    try:
        # Удаляем существующие таблицы
        print("\nDropping existing tables...")
        db_manager.drop_tables()
        print("✓ Existing tables dropped")
        
        # Создаем таблицы
        create_tables(db_manager)
        
        # Создаем тестовые данные
        create_test_data(db_manager)
        
        print("\n✅ All operations completed successfully!")
        print("\nYou can now start the Student Panel:")
        print("  cd src/student_panel")
        print("  python app.py")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
