# D:\Work\EkoServer\Eko-production\reset_database.py
import os
from app import app, db

def reset_database():
    # Удаляем старую базу данных
    if os.path.exists('eko_production.db'):
        os.remove('eko_production.db')
        print("Старая база данных удалена")
    
    # Удаляем загруженные файлы
    import shutil
    if os.path.exists('static/uploads'):
        shutil.rmtree('static/uploads')
        print("Загруженные файлы удалены")
    
    # Создаем новую базу данных
    with app.app_context():
        db.create_all()
        print("Новая база данных создана")
    
    # Создаем папку для загрузок
    os.makedirs('static/uploads', exist_ok=True)
    print("Папка для загрузок создана")
    
    print("База данных успешно сброшена!")

if __name__ == '__main__':
    reset_database()