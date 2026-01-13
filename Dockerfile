FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Обновляем pip перед установкой зависимостей
RUN pip install --upgrade pip

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Создаем папку для логов и инициализируем структуру
RUN mkdir -p logs utils handlers

CMD ["python", "main.py"]
