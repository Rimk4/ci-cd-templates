# Используем официальный базовый образ
FROM alpine:3.18

# Устанавливаем рабочую директорию
WORKDIR /app

# Установка зависимостей (пример для Alpine)
RUN apk add --no-cache \
    bash \
    curl \
    git \
    && rm -rf /var/cache/apk/*

# Копируем файлы приложения
COPY . .

# Указываем команду по умолчанию
CMD ["/bin/bash"]
