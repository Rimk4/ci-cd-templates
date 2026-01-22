"""
Конфигурация Docker Manager с Buildx
Все параметры можно переопределить переменными окружения с префиксом DOCKER_
"""

# Имя Dockerfile (по умолчанию: Dockerfile)
DOCKERFILE = 'Dockerfile'

# Имя образа (по умолчанию: myapp)
IMAGE_NAME = 'myapp'

# URL Docker реестра (например: registry.gitlab.com/username/project)
REGISTRY_URL = None

# Тег по умолчанию (по умолчанию: latest)
LATEST_TAG = 'latest'

# Имя пользователя для авторизации в реестре
USERNAME = None

# Пароль или токен для авторизации в реестре
PASSWORD = None

# Платформа для сборки (можно указать несколько через запятую)
# Примеры: linux/amd64, linux/amd64,linux/arm64, linux/arm/v7
PLATFORM = 'linux/amd64'

# Имя builder'а для Buildx
BUILDER = 'default'

# Кэширование сборки (опционально)
# Примеры: type=registry,ref=registry.example.com/cache
CACHE_TO = None
CACHE_FROM = None
