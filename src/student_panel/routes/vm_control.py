from flask import Blueprint, render_template, request, jsonify, session, flash, redirect, url_for, current_app
import sys
sys.path.append('../..')

from src.shared.logger import setup_logger
from src.shared.exceptions import VMNotFoundException, VMOperationException
from src.infrastructure.database.connection import DatabaseManager
from src.infrastructure.database.repositories import VMRepository
from src.infrastructure.database.models import VMStatus
from src.infrastructure.proxmox.client import ProxmoxClient
from .auth import login_required

vm_control_bp = Blueprint('vm_control', __name__)
logger = setup_logger(__name__)

@vm_control_bp.route('/dashboard')
@login_required
def dashboard():
    """Главная страница студента"""
    user_id = session.get('user_id')
    
    try:
        db_manager = current_app.config['DB_MANAGER']
        proxmox = current_app.config['PROXMOX_CLIENT']
        
        with db_manager.get_session() as db_session:
            vm_repo = VMRepository(db_session)
            vm = vm_repo.get_by_user_id(user_id)
            
            if not vm:
                flash('У вас еще нет виртуальной машины. Обратитесь к администратору', 'warning')
                return render_template('dashboard.html', vm=None)
            
            # Получаем актуальный статус из Proxmox
            try:
                proxmox_status = proxmox.get_vm_status(vm.node, vm.vmid)
                actual_status = proxmox_status.get('status', 'unknown')
                
                # Обновляем статус в БД если он изменился
                if actual_status == 'running' and vm.status != VMStatus.RUNNING:
                    vm_repo.update_status(vm.id, VMStatus.RUNNING)
                elif actual_status == 'stopped' and vm.status != VMStatus.STOPPED:
                    vm_repo.update_status(vm.id, VMStatus.STOPPED)
                
                vm_info = {
                    'id': vm.id,
                    'name': vm.name,
                    'vmid': vm.vmid,
                    'status': actual_status,
                    'cpu_cores': vm.cpu_cores,
                    'ram_mb': vm.ram_mb,
                    'disk_gb': vm.disk_gb,
                    'ip_address': vm.ip_address,
                    'node': vm.node
                }
            except Exception as e:
                logger.error(f"Error getting VM status from Proxmox: {e}")
                vm_info = {
                    'id': vm.id,
                    'name': vm.name,
                    'vmid': vm.vmid,
                    'status': vm.status.value,
                    'cpu_cores': vm.cpu_cores,
                    'ram_mb': vm.ram_mb,
                    'disk_gb': vm.disk_gb,
                    'ip_address': vm.ip_address,
                    'node': vm.node
                }
            
            return render_template('dashboard.html', vm=vm_info)
            
    except Exception as e:
        logger.error(f"Dashboard error: {e}", exc_info=True)
        flash('Ошибка загрузки данных', 'error')
        return render_template('dashboard.html', vm=None)

@vm_control_bp.route('/api/vm/start', methods=['POST'])
@login_required
def start_vm():
    """API: Запустить ВМ"""
    user_id = session.get('user_id')
    
    try:
        db_manager = current_app.config['DB_MANAGER']
        proxmox = current_app.config['PROXMOX_CLIENT']
        
        with db_manager.get_session() as db_session:
            vm_repo = VMRepository(db_session)
            vm = vm_repo.get_by_user_id(user_id)
            
            if not vm:
                return jsonify({
                    'success': False,
                    'message': 'Виртуальная машина не найдена'
                }), 404
            
            # Проверяем текущий статус
            current_status = proxmox.get_vm_status(vm.node, vm.vmid)
            if current_status.get('status') == 'running':
                return jsonify({
                    'success': True,
                    'message': 'Виртуальная машина уже запущена',
                    'status': 'running'
                })
            
            # Запускаем ВМ
            success = proxmox.start_vm(vm.node, vm.vmid)
            
            if success:
                # Ждем запуска
                if proxmox.wait_for_status(vm.node, vm.vmid, 'running', timeout=30):
                    vm_repo.update_status(vm.id, VMStatus.RUNNING)
                    vm_repo.update_last_activity(vm.id)
                    
                    logger.info(f"VM {vm.vmid} started by user {user_id}")
                    return jsonify({
                        'success': True,
                        'message': 'Виртуальная машина успешно запущена',
                        'status': 'running'
                    })
                else:
                    return jsonify({
                        'success': False,
                        'message': 'Превышено время ожидания запуска'
                    }), 500
            else:
                return jsonify({
                    'success': False,
                    'message': 'Ошибка при запуске виртуальной машины'
                }), 500
                
    except Exception as e:
        logger.error(f"Error starting VM: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': 'Ошибка при запуске виртуальной машины'
        }), 500

@vm_control_bp.route('/api/vm/stop', methods=['POST'])
@login_required
def stop_vm():
    """API: Остановить ВМ"""
    user_id = session.get('user_id')
    
    try:
        db_manager = current_app.config['DB_MANAGER']
        proxmox = current_app.config['PROXMOX_CLIENT']
        
        with db_manager.get_session() as db_session:
            vm_repo = VMRepository(db_session)
            vm = vm_repo.get_by_user_id(user_id)
            
            if not vm:
                return jsonify({
                    'success': False,
                    'message': 'Виртуальная машина не найдена'
                }), 404
            
            # Проверяем текущий статус
            current_status = proxmox.get_vm_status(vm.node, vm.vmid)
            if current_status.get('status') == 'stopped':
                return jsonify({
                    'success': True,
                    'message': 'Виртуальная машина уже остановлена',
                    'status': 'stopped'
                })
            
            # Пробуем корректное выключение
            success = proxmox.shutdown_vm(vm.node, vm.vmid)
            
            if success:
                # Ждем остановки
                if proxmox.wait_for_status(vm.node, vm.vmid, 'stopped', timeout=60):
                    vm_repo.update_status(vm.id, VMStatus.STOPPED)
                    
                    logger.info(f"VM {vm.vmid} stopped by user {user_id}")
                    return jsonify({
                        'success': True,
                        'message': 'Виртуальная машина успешно остановлена',
                        'status': 'stopped'
                    })
                else:
                    # Если не остановилась корректно, принудительно останавливаем
                    proxmox.stop_vm(vm.node, vm.vmid)
                    proxmox.wait_for_status(vm.node, vm.vmid, 'stopped', timeout=30)
                    vm_repo.update_status(vm.id, VMStatus.STOPPED)
                    
                    logger.warning(f"VM {vm.vmid} force stopped by user {user_id}")
                    return jsonify({
                        'success': True,
                        'message': 'Виртуальная машина принудительно остановлена',
                        'status': 'stopped'
                    })
            else:
                return jsonify({
                    'success': False,
                    'message': 'Ошибка при остановке виртуальной машины'
                }), 500
                
    except Exception as e:
        logger.error(f"Error stopping VM: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': 'Ошибка при остановке виртуальной машины'
        }), 500

@vm_control_bp.route('/api/vm/status', methods=['GET'])
@login_required
def get_vm_status():
    """API: Получить статус ВМ"""
    user_id = session.get('user_id')
    
    try:
        db_manager = current_app.config['DB_MANAGER']
        proxmox = current_app.config['PROXMOX_CLIENT']
        
        with db_manager.get_session() as db_session:
            vm_repo = VMRepository(db_session)
            vm = vm_repo.get_by_user_id(user_id)
            
            if not vm:
                return jsonify({
                    'success': False,
                    'message': 'Виртуальная машина не найдена'
                }), 404
            
            # Получаем актуальный статус
            proxmox_status = proxmox.get_vm_status(vm.node, vm.vmid)
            
            return jsonify({
                'success': True,
                'status': proxmox_status.get('status', 'unknown'),
                'cpu': proxmox_status.get('cpu', 0),
                'mem': proxmox_status.get('mem', 0),
                'maxmem': proxmox_status.get('maxmem', 0),
                'uptime': proxmox_status.get('uptime', 0)
            })
            
    except Exception as e:
        logger.error(f"Error getting VM status: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': 'Ошибка получения статуса'
        }), 500