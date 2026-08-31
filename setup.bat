@echo off
REM E:\Work\EkoServer\Eko-production\setup.bat
echo Установка Eko-production...

REM Создание виртуального окружения
echo Создание виртуального окружения...
python -m venv venv

REM Активация виртуального окружения
echo Активация виртуального окружения...
call venv\Scripts\activate

REM Установка зависимостей
echo Установка зависимостей...
pip install -r requirements.txt

REM Создание базы данных и запуск приложения
echo Создание базы данных...
python -c "from app import app, db; app.app_context().push(); db.create_all()"

echo.
echo ========================================
echo Установка завершена!
echo.
echo Для запуска приложения выполните:
echo 1. cd E:\Work\EkoServer\Eko-production
echo 2. venv\Scripts\activate
echo 3. python app.py
echo.
echo Или запустите файл start.bat
echo ========================================
pause