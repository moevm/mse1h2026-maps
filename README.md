# mse-template

## Требования
### Для запуска через Docker
- **Docker** 28 или выше
- **Git** 

## Установка и запуск
### Запуск через Docker

1. **Клонируйте репозиторий**
    ```bash
    git clone https://github.com/moevm/mse1h2026-maps.git
    cd mse1h2026-maps
    
2. **Настройте переменные окружения**

Скопируйте **.env.example** в **.env** и при необходимости отредактируйте.

3. **Соберите и запустите контейнеры**
    ```bash
    docker-compose up --build

4. **Приложение станет доступно по адресу http://localhost:8000**

