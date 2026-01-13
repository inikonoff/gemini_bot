FROM python:3.11-slim

# Установка рабочей директории
WORKDIR /app

# Установка системных зависимостей (нужны для некоторых Python-библиотек)
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Обновляем pip для корректной установки новых версий библиотек
RUN pip install --upgrade pip

# Копируем и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код проекта
COPY . .

# --- КРИТИЧЕСКИ ВАЖНЫЙ ШАГ ---
# Создаем необходимые папки и файлы инициализации пакетов, 
# чтобы избежать ошибок импорта (Circular Import / ModuleNotFoundError)
RUN mkdir -p logs handlers utils && \
    touch handlers/__init__.py && \
    touch utils/__init__.py

# Указываем порт для веб-сервера (Render использует 8080 по умолчанию)
EXPOSE 8080

# Запуск бота через основной файл
CMD ["python", "main.py"]