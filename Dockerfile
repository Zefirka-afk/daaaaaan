# Используем официальный образ Python как основу
FROM python:3.11-slim

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Установка зависимостей для Google Chrome
# Запускаем от имени root, чтобы иметь все права
USER root
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    # Устанавливаем сам Google Chrome
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list' \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    # Очищаем кэш apt, чтобы уменьшить размер образа
    && rm -rf /var/lib/apt/lists/*

# Копируем файл с зависимостями Python
COPY requirements.txt .

# Устанавливаем зависимости Python
RUN pip install --no-cache-dir -r requirements.txt

# Копируем все файлы проекта в рабочую директорию
COPY . .

# Указываем команду, которая будет запускаться при старте контейнера
CMD ["python", "main.py"]