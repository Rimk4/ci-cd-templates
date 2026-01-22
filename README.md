# Docker Manager - Быстрый старт

## 📦 Установка и настройка

### Требования
- **Docker Engine 20.10+**
- **Python 3.8+**
- Пользователь в группе docker

```bash
# Добавить пользователя в группу docker
sudo usermod -aG docker ${USER}
newgrp docker

# Проверить установку
docker --version
python3 --version
```

### Быстрая установка
```bash
# Скачать скрипт
wget https://your-repository/docker-manager.py

# Сделать исполняемым
chmod +x docker-manager.py

# Инициализировать конфигурацию
python3 docker-manager.py init

# Настроить файл конфигурации
nano docker-config.py
```

## ⚙️ Конфигурация

### Основные настройки (docker-config.py)
```python
DOCKERFILE = 'Dockerfile'                  # Имя Dockerfile
IMAGE_NAME = 'myapp'                       # Имя образа
REGISTRY_URL = 'registry.example.com/proj' # URL реестра
LATEST_TAG = 'latest'                      # Тег по умолчанию
USERNAME = 'your-username'                 # Логин для реестра
PASSWORD = 'your-token'                    # Пароль/токен
```

### Переменные окружения
```bash
export DOCKER_IMAGE_NAME="my-service"
export DOCKER_REGISTRY_URL="registry.gitlab.com/myproject"
export DOCKER_USERNAME="$CI_REGISTRY_USER"
export DOCKER_PASSWORD="$CI_REGISTRY_PASSWORD"
```

## 🚀 Основные команды

### 🔨 Сборка образа
```bash
python3 docker-manager.py build --tag v1.0
```

**Опции:**
- `--tag, -t` - тег образа (default: latest)
- `--dockerfile, -f` - путь к Dockerfile
- `--context, -c` - контекст сборки
- `--no-cache` - отключить кэш
- `--pull` - скачать базовый образ

### ▶️ Запуск контейнера
```bash
python3 docker-manager.py run --tag v1.0 -p 8080:80
```

**Опции:**
- `--port, -p` - маппинг портов (хост:контейнер)
- `--volume, -v` - маппинг томов (хост:контейнер)
- `--env, -e` - переменные окружения (КЛЮЧ=значение)
- `--detach, -d` - запуск в фоне
- `--name, -n` - имя контейнера

### 📤📥 Работа с реестром
```bash
# Авторизация
python3 docker-manager.py login --registry registry.example.com

# Отправка образа
python3 docker-manager.py push --tag v1.0

# Скачивание образа
python3 docker-manager.py pull --tag v1.0
```

### 🛠 Утилиты
```bash
# Список локальных образов
python3 docker-manager.py list

# Очистка Docker
python3 docker-manager.py clean --all

# Справка
python3 docker-manager.py --help
```

## 💡 Примеры использования

### Пример 1: Разработка с hot-reload
```bash
# Собрать dev образ
python3 docker-manager.py build --tag dev --dockerfile Dockerfile.dev

# Запустить с hot-reload
python3 docker-manager.py run --tag dev \
  -p 3000:3000 \
  -v ./src:/app/src \
  -v ./public:/app/public \
  -e NODE_ENV=development
```

### Пример 2: Продакшен сборка
```bash
# Сборка без кэша
python3 docker-manager.py build --tag prod-v1.2.3 --no-cache

# Публикация в реестр
python3 docker-manager.py push --tag prod-v1.2.3
python3 docker-manager.py push --tag latest
```

### Пример 3: База данных + приложение
```bash
# Запуск PostgreSQL
python3 docker-manager.py run \
  --tag postgres:15 \
  --name database \
  -p 5432:5432 \
  -e POSTGRES_PASSWORD=secret \
  --detach

# Запуск приложения
python3 docker-manager.py run \
  --tag myapp:latest \
  --name app \
  -p 8080:80 \
  -e DB_HOST=database \
  --detach
```

## 🔄 Интеграция с CI/CD

### GitLab CI
```yaml
build:
  script:
    - python3 docker-manager.py build --tag "$CI_COMMIT_SHORT_SHA"
    - python3 docker-manager.py push --tag "$CI_COMMIT_SHORT_SHA"
```

### GitHub Actions
```yaml
- name: Build and push
  env:
    DOCKER_REGISTRY_URL: ghcr.io
  run: |
    python3 docker-manager.py build --tag "${{ github.sha }}"
    python3 docker-manager.py push --tag "${{ github.sha }}"
```

## 🎯 Быстрые команды

```bash
# Полный цикл: сборка → публикация
python3 docker-manager.py build --tag v1.0 && \
python3 docker-manager.py push --tag v1.0

# Запуск с портами и томами
python3 docker-manager.py run --tag latest \
  -p 80:80 \
  -v ./config:/config \
  -v ./data:/data \
  --detach

# Полная очистка системы
python3 docker-manager.py clean --all
```

## 🚨 Решение проблем

### 1. Ошибка прав доступа
```bash
# Добавить в группу docker
sudo usermod -aG docker $USER
newgrp docker

# Проверить
docker ps
```

### 2. Очистка диска
```bash
# Полная очистка
python3 docker-manager.py clean --all

# Или вручную
docker system prune -af
```

### 3. Проверка состояния
```bash
docker ps          # Активные контейнеры
docker ps -a       # Все контейнеры
docker images      # Локальные образы
docker info        # Информация о системе
```

### 4. Ошибка авторизации
```bash
# Проверить логин/пароль
python3 docker-manager.py login \
  --registry your.registry.com \
  --username your-user \
  --password your-token
```

## 📝 Важные заметки

- ✅ Все команды работают без `sudo` после добавления в группу docker
- ✅ Пароли хранятся только в переменных окружения или секретах CI/CD
- ✅ Используйте `.dockerignore` для исключения ненужных файлов
- ✅ Для продакшена используйте multi-stage сборки
- ✅ Логирование отключается флагом `--quiet`

## 🎪 Шпаргалка

```bash
# Инициализация
python3 docker-manager.py init

# Сборка
python3 docker-manager.py build -t mytag -f Dockerfile.prod

# Запуск
python3 docker-manager.py run -t mytag -p 80:80 -d

# Публикация
python3 docker-manager.py push -t mytag

# Очистка
python3 docker-manager.py clean --images --volumes
```

---

**Техподдержка:** devops@company.com  
**Документация:** docs.company.com/docker  
**Версия:** 1.0.0
