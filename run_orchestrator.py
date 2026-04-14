
import sys
from pathlib import Path
from dotenv import load_dotenv
import argparse

# Загружаем переменные окружения
load_dotenv()

# Добавляем путь к src
sys.path.append(str(Path(__file__).parent / 'src'))

from orchestrator.main import Orchestrator

def main():
    parser = argparse.ArgumentParser(description='VM Management Orchestrator')
    parser.add_argument(
        '--config',
        default='configs/orchestrator.yaml',
        help='Path to configuration file'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run in dry-run mode (no actual changes)'
    )
    
    args = parser.parse_args()
    
    print("="*60)
    print("VM Management System - Orchestrator")
    print("="*60)
    
    if args.dry_run:
        print("⚠️  DRY RUN MODE - No actual changes will be made")
        print("="*60)
    
    # Создаем необходимые директории
    Path('data').mkdir(exist_ok=True)
    Path('logs').mkdir(exist_ok=True)
    
    # Запускаем оркестратор
    try:
        orchestrator = Orchestrator(config_path=args.config)
        
        # Если указан dry-run, переопределяем конфиг
        if args.dry_run:
            orchestrator.config['dry_run'] = True
            orchestrator.inactivity_monitor.dry_run = True
            orchestrator.auto_scaler.dry_run = True
        
        orchestrator.run()
    except KeyboardInterrupt:
        print("\n\nShutting down gracefully...")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()