import sys
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Добавляем путь к src
sys.path.append(str(Path(__file__).parent / 'src'))

from student_panel.app import create_app

if __name__ == '__main__':
    print("="*60)
    print("Starting Student Panel Application")
    print("="*60)
    
    app = create_app()
    
    host = '0.0.0.0'
    port = 5000
    
    print(f"\n✓ Application initialized")
    print(f"✓ Running on http://{host}:{port}")
    print(f"✓ Environment: {app.config.get('FLASK_ENV', 'development')}")
    print(f"\nPress Ctrl+C to stop\n")
    
    app.run(
        host=host,
        port=port,
        debug=app.config['DEBUG']
    )