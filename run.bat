@echo off
call venv\Scripts\activate
python src/django/maps/manage.py runserver
pause