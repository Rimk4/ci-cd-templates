"""
Универсальный скрипт для работы с Docker Buildx.
Позволяет собирать образы, отправлять их в реестр и скачивать обратно.
"""

import argparse
import subprocess
import os
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict, List


class DockerManager:
    """Менеджер для работы с Docker Buildx операциями"""
    
    def __init__(self, verbose: bool = True):
        """
        Инициализация менеджера Docker
        
        Args:
            verbose (bool): Включить подробный вывод
        """
        self.verbose = verbose
        self.config = self._load_config()
        self._check_buildx_installed()
        
    def _load_config(self) -> Dict:
        """Загрузка конфигурации из файла или переменных окружения"""
        # Базовые настройки по умолчанию
        config = {
            'dockerfile': 'Dockerfile',
            'image_name': 'myapp',
            'registry_url': None,
            'latest_tag': 'latest',
            'username': None,
            'password': None,
            'platform': 'linux/amd64',  # Платформа по умолчанию
            'builder': 'default',       # Имя builder'а
            'cache_to': None,           # Кэширование сборки
            'cache_from': None,         # Использование кэша
        }
        
        # Загрузка из файла конфигурации, если он существует
        config_file = Path('docker-config.py')
        if config_file.exists():
            try:
                # Динамический импорт конфигурации
                import importlib.util
                spec = importlib.util.spec_from_file_location("docker_config", config_file)
                docker_config = importlib.util.module_from_spec(spec)
                
                # Устанавливаем значения по умолчанию
                for key in config.keys():
                    if not hasattr(docker_config, key.upper()):
                        setattr(docker_config, key.upper(), config[key])
                
                spec.loader.exec_module(docker_config)
                
                # Читаем значения из модуля
                for key in config.keys():
                    if hasattr(docker_config, key.upper()):
                        config[key] = getattr(docker_config, key.upper())
            except Exception as e:
                self.log(f"Warning: Config file exists but couldn't be imported: {str(e)}", "WARNING")
        
        # Переопределение переменными окружения
        for key in config.keys():
            env_key = f'DOCKER_{key.upper()}'
            if env_key in os.environ:
                config[key] = os.environ[env_key]
                
        return config
    
    def _check_buildx_installed(self) -> bool:
        """Проверка установки Docker Buildx"""
        try:
            result = subprocess.run(
                ['docker', 'buildx', 'version'],
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode != 0:
                self.log("Docker Buildx не установлен или не настроен", "WARNING")
                self.log("Установите Buildx: https://docs.docker.com/go/buildx/", "INFO")
                return False
            return True
        except Exception:
            return False
    
    def log(self, message: str, level: str = "INFO") -> None:
        """Логирование сообщений"""
        if self.verbose:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] [{level}] {message}")
    
    def run_command(self, cmd: str, capture_output: bool = False) -> Tuple[bool, Optional[str]]:
        """
        Выполнение shell команды
        
        Args:
            cmd (str): Команда для выполнения
            capture_output (bool): Захватить вывод команды
            
        Returns:
            tuple: (success, output) или (success, None)
        """
        self.log(f"Выполнение команды: {cmd}")
        
        try:
            if capture_output:
                result = subprocess.run(
                    cmd, 
                    shell=True, 
                    check=True, 
                    capture_output=True, 
                    text=True,
                    env={**os.environ, 'DOCKER_BUILDKIT': '1'}  # Всегда включаем BuildKit
                )
                output = result.stdout
                self.log(f"Успешно выполнено")
                return True, output
            else:
                subprocess.run(
                    cmd, 
                    shell=True, 
                    check=True,
                    env={**os.environ, 'DOCKER_BUILDKIT': '1'}
                )
                self.log(f"Успешно выполнено")
                return True, None
        except subprocess.CalledProcessError as e:
            self.log(f"Ошибка выполнения команды: {e}", "ERROR")
            if capture_output:
                self.log(f"Вывод ошибки: {e.stderr}", "ERROR")
            return False, e.stderr if capture_output else None
    
    def check_dockerfile_exists(self, dockerfile_path: str) -> bool:
        """Проверка существования Dockerfile"""
        dockerfile = Path(dockerfile_path)
        if not dockerfile.exists():
            self.log(f"❌ Dockerfile не найден: {dockerfile_path}", "ERROR")
            self.log(f"📁 Текущая директория: {os.getcwd()}", "INFO")
            
            # Показать доступные Dockerfile
            try:
                result = subprocess.run(
                    ["find", ".", "-name", "Dockerfile*", "-type", "f"],
                    capture_output=True,
                    text=True
                )
                if result.stdout.strip():
                    self.log("📋 Найдены следующие Dockerfile:", "INFO")
                    for line in result.stdout.strip().split('\n'):
                        self.log(f"   - {line}", "INFO")
                else:
                    self.log("📋 Dockerfile не найдены в проекте", "INFO")
            except:
                pass
            
            self.log("\n💡 Создайте Dockerfile или укажите существующий:", "INFO")
            self.log("   python3 docker-manager.py build --dockerfile path/to/Dockerfile", "INFO")
            self.log("   или используйте один из шаблонов в README.md", "INFO")
            return False
        return True
    
    def setup_buildx_builder(self, builder_name: str = "multiarch") -> bool:
        """
        Настройка Buildx builder'а для мультиархитектурной сборки
        
        Args:
            builder_name (str): Имя builder'а
            
        Returns:
            bool: Успешность настройки
        """
        self.log(f"Настройка Buildx builder'а: {builder_name}")
        
        # Проверяем существующий builder
        cmd = f"docker buildx ls"
        success, output = self.run_command(cmd, capture_output=True)
        
        if success and output:
            if builder_name in output:
                self.log(f"Builder '{builder_name}' уже существует, используем его")
                # Используем существующий builder
                cmd = f"docker buildx use {builder_name}"
                return self.run_command(cmd)[0]
        
        # Создаем новый builder
        self.log(f"Создание нового builder'а: {builder_name}")
        cmd = f"docker buildx create --name {builder_name} --use --bootstrap"
        return self.run_command(cmd)[0]
    
    def build(self, 
              tag: Optional[str] = None, 
              dockerfile: Optional[str] = None, 
              context: str = ".", 
              no_cache: bool = False, 
              pull: bool = False,
              platform: Optional[str] = None,
              push: bool = False,
              load: bool = False,
              builder: Optional[str] = None,
              cache_to: Optional[str] = None,
              cache_from: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Сборка Docker образа с помощью Buildx
        
        Args:
            tag (str): Тег образа
            dockerfile (str): Путь к Dockerfile
            context (str): Контекст сборки
            no_cache (bool): Не использовать кэш
            pull (bool): Всегда скачивать базовые образы
            platform (str): Платформа для сборки (например: linux/amd64,linux/arm64)
            push (bool): Отправлять образ в реестр после сборки
            load (bool): Загружать образ в локальный Docker
            builder (str): Имя builder'а
            cache_to (str): Сохранять кэш сборки
            cache_from (str): Использовать кэш из указанного источника
            
        Returns:
            tuple: (success, output)
        """
        if tag is None:
            tag = self.config['latest_tag']
        
        if dockerfile is None:
            dockerfile = self.config['dockerfile']
        
        if platform is None:
            platform = self.config['platform']
        
        if builder is None:
            builder = self.config['builder']
        
        if cache_to is None:
            cache_to = self.config['cache_to']
        
        if cache_from is None:
            cache_from = self.config['cache_from']
        
        # Проверяем существование Dockerfile
        if not self.check_dockerfile_exists(dockerfile):
            return False, None
        
        # Настраиваем builder
        if not self.setup_buildx_builder(builder):
            self.log("Используем builder по умолчанию", "WARNING")
        
        image_name = self.config['image_name']
        full_image_name = f"{image_name}:{tag}"
        
        # Добавляем реестр к имени образа если нужно
        if push and self.config['registry_url']:
            full_image_name = f"{self.config['registry_url']}/{full_image_name}"
        
        # Формирование команды сборки
        cmd_parts = ["docker buildx build"]
        
        # Добавляем тег
        cmd_parts.append(f"-t {full_image_name}")
        
        # Добавляем Dockerfile
        if dockerfile:
            cmd_parts.append(f"-f {dockerfile}")
        
        # Платформы
        if platform:
            cmd_parts.append(f"--platform {platform}")
        
        # Кэширование
        if cache_to:
            cmd_parts.append(f"--cache-to {cache_to}")
        
        if cache_from:
            cmd_parts.append(f"--cache-from {cache_from}")
        
        if no_cache:
            cmd_parts.append("--no-cache")
        
        if pull:
            cmd_parts.append("--pull")
        
        # Действия после сборки
        if push:
            cmd_parts.append("--push")
        elif load:
            cmd_parts.append("--load")
        else:
            cmd_parts.append("--load")  # По умолчанию загружаем в локальный Docker
        
        # Прогресс
        cmd_parts.append("--progress=plain")
        
        # Контекст
        cmd_parts.append(context)
        
        cmd = " ".join(cmd_parts)
        
        self.log(f"🚀 Сборка образа с Buildx")
        self.log(f"   Образ: {full_image_name}")
        self.log(f"   Dockerfile: {dockerfile}")
        self.log(f"   Платформа: {platform}")
        self.log(f"   Контекст: {context}")
        if push:
            self.log(f"   Действие: отправка в реестр")
        else:
            self.log(f"   Действие: загрузка в локальный Docker")
        
        return self.run_command(cmd)
    
    def push(self, tag: Optional[str] = None, registry_url: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Отправка Docker образа в реестр
        
        Args:
            tag (str): Тег образа
            registry_url (str): URL реестра
            
        Returns:
            tuple: (success, output)
        """
        if tag is None:
            tag = self.config['latest_tag']
        
        if registry_url is None:
            registry_url = self.config['registry_url']
            
        if not registry_url:
            self.log("URL реестра не указан", "ERROR")
            self.log("Укажите в конфигурации или через --registry", "INFO")
            return False, None
        
        image_name = self.config['image_name']
        source_image = f"{image_name}:{tag}"
        target_image = f"{registry_url}/{source_image}"
        
        # Тегируем образ
        cmd_tag = f"docker tag {source_image} {target_image}"
        success, _ = self.run_command(cmd_tag)
        if not success:
            return False, None
        
        # Отправляем в реестр
        cmd_push = f"docker push {target_image}"
        
        self.log(f"📤 Отправка образа: {target_image}")
        
        return self.run_command(cmd_push)
    
    def pull(self, tag: Optional[str] = None, registry_url: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Скачивание Docker образа из реестра
        
        Args:
            tag (str): Тег образа
            registry_url (str): URL реестра
            
        Returns:
            tuple: (success, output)
        """
        if tag is None:
            tag = self.config['latest_tag']
        
        if registry_url is None:
            registry_url = self.config['registry_url']
            
        if not registry_url:
            self.log("URL реестра не указан", "ERROR")
            return False, None
        
        image_name = self.config['image_name']
        full_image_name = f"{registry_url}/{image_name}:{tag}"
        
        cmd = f"docker pull {full_image_name}"
        
        self.log(f"📥 Скачивание образа: {full_image_name}")
        
        return self.run_command(cmd)
    
    def login(self, 
              registry_url: Optional[str] = None, 
              username: Optional[str] = None, 
              password: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Авторизация в Docker реестре
        
        Args:
            registry_url (str): URL реестра
            username (str): Имя пользователя
            password (str): Пароль или токен
            
        Returns:
            tuple: (success, output)
        """
        if registry_url is None:
            registry_url = self.config['registry_url']
            
        if username is None:
            username = self.config['username']
            
        if password is None:
            password = self.config['password']
            
        if not all([registry_url, username, password]):
            self.log("Не хватает данных для авторизации", "ERROR")
            return False, None
        
        # Используем stdin для передачи пароля
        cmd = f"echo '{password}' | docker login {registry_url} -u {username} --password-stdin"
        
        self.log(f"🔑 Авторизация в реестре: {registry_url}")
        
        return self.run_command(cmd)
    
    def list_images(self) -> Tuple[bool, Optional[str]]:
        """Список локальных Docker образов"""
        cmd = "docker images --format 'table {{.Repository}}\\t{{.Tag}}\\t{{.Size}}\\t{{.CreatedAt}}'"
        self.log("📋 Получение списка локальных образов")
        return self.run_command(cmd, capture_output=True)
    
    def list_builders(self) -> Tuple[bool, Optional[str]]:
        """Список доступных Buildx builders"""
        cmd = "docker buildx ls"
        self.log("🔧 Получение списка Buildx builders")
        return self.run_command(cmd, capture_output=True)
    
    def inspect_image(self, tag: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Информация о Docker образе
        
        Args:
            tag (str): Тег образа
            
        Returns:
            tuple: (success, output)
        """
        if tag is None:
            tag = self.config['latest_tag']
        
        image_name = self.config['image_name']
        full_image_name = f"{image_name}:{tag}"
        
        cmd = f"docker image inspect {full_image_name} --format '{{{{json .}}}}'"
        
        self.log(f"🔍 Инспекция образа: {full_image_name}")
        
        success, output = self.run_command(cmd, capture_output=True)
        
        if success and output:
            try:
                image_info = json.loads(output)
                formatted_output = json.dumps(image_info, indent=2, ensure_ascii=False)
                return True, formatted_output
            except json.JSONDecodeError:
                return True, output
        
        return success, output
    
    def run_container(self, 
                      image_tag: str, 
                      ports: Optional[Dict] = None, 
                      volumes: Optional[Dict] = None, 
                      env: Optional[Dict] = None, 
                      detach: bool = False, 
                      name: Optional[str] = None,
                      rm: bool = True) -> Tuple[bool, Optional[str]]:
        """
        Запуск Docker контейнера
        
        Args:
            image_tag (str): Тег образа
            ports (dict): Маппинг портов {host_port: container_port}
            volumes (dict): Маппинг томов {host_path: container_path}
            env (dict): Переменные окружения
            detach (bool): Запуск в фоновом режиме
            name (str): Имя контейнера
            rm (bool): Удалять контейнер после остановки
            
        Returns:
            tuple: (success, output)
        """
        image_name = self.config['image_name']
        full_image_name = f"{image_name}:{image_tag}"
        
        cmd_parts = ["docker run"]
        
        if detach:
            cmd_parts.append("-d")
        
        if rm:
            cmd_parts.append("--rm")
        
        if name:
            cmd_parts.append(f"--name {name}")
        
        if ports:
            for host_port, container_port in ports.items():
                cmd_parts.append(f"-p {host_port}:{container_port}")
        
        if volumes:
            for host_path, container_path in volumes.items():
                cmd_parts.append(f"-v {host_path}:{container_path}")
        
        if env:
            for key, value in env.items():
                cmd_parts.append(f"-e {key}='{value}'")
        
        cmd_parts.append(full_image_name)
        cmd = " ".join(cmd_parts)
        
        self.log(f"▶️  Запуск контейнера: {full_image_name}")
        
        return self.run_command(cmd)
    
    def clean(self, 
              remove_containers: bool = False, 
              remove_images: bool = False, 
              remove_volumes: bool = False,
              remove_build_cache: bool = False) -> Tuple[bool, Optional[str]]:
        """
        Очистка Docker ресурсов
        
        Args:
            remove_containers (bool): Удалить остановленные контейнеры
            remove_images (bool): Удалить неиспользуемые образы
            remove_volumes (bool): Удалить неиспользуемые тома
            remove_build_cache (bool): Очистить кэш сборки Buildx
            
        Returns:
            tuple: (success, output)
        """
        commands = []
        
        if remove_containers:
            commands.append("docker container prune -f")
        
        if remove_images:
            commands.append("docker image prune -af")
        
        if remove_volumes:
            commands.append("docker volume prune -f")
        
        if remove_build_cache:
            commands.append("docker builder prune -af")
        
        if not commands:
            self.log("Не указано что очищать", "WARNING")
            return True, None
        
        all_success = True
        for cmd in commands:
            self.log(f"🧹 Очистка: {cmd}")
            success, _ = self.run_command(cmd)
            if not success:
                all_success = False
        
        return all_success, None
    
    def scan_image(self, tag: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Сканирование Docker образа на уязвимости
        
        Args:
            tag (str): Тег образа
            
        Returns:
            tuple: (success, output)
        """
        if tag is None:
            tag = self.config['latest_tag']
        
        image_name = self.config['image_name']
        full_image_name = f"{image_name}:{tag}"
        
        cmd = f"docker scan {full_image_name}"
        
        self.log(f"🔒 Сканирование образа на уязвимости: {full_image_name}")
        
        return self.run_command(cmd, capture_output=True)


def create_config_template():
    """Создание шаблона файла конфигурации"""
    config_template = '''"""
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
'''
    
    with open('docker-config.py', 'w') as f:
        f.write(config_template)
    
    print("✅ Создан файл конфигурации: docker-config.py")
    print("📝 Отредактируйте его под ваши нужды.")


def main():
    """Основная функция для CLI"""
    parser = argparse.ArgumentParser(
        description='🚀 Универсальный скрипт для работы с Docker Buildx',
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
Примеры использования:
  python3 docker-manager.py build --tag v1.0
  python3 docker-manager.py build --platform linux/amd64,linux/arm64 --push
  python3 docker-manager.py build --dockerfile Dockerfile.python --tag backend
  python3 docker-manager.py push --tag v1.0 --registry registry.example.com
  python3 docker-manager.py run --tag latest -p 8080:80 -d
  python3 docker-manager.py clean --all
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Доступные команды')
    
    # Build command
    build_parser = subparsers.add_parser('build', help='Сборка Docker образа с Buildx')
    build_parser.add_argument('--tag', '-t', default='latest', help='Тег образа')
    build_parser.add_argument('--dockerfile', '-f', help='Путь к Dockerfile')
    build_parser.add_argument('--context', '-c', default='.', help='Контекст сборки')
    build_parser.add_argument('--no-cache', action='store_true', help='Не использовать кэш')
    build_parser.add_argument('--pull', action='store_true', help='Всегда скачивать базовые образы')
    build_parser.add_argument('--platform', help='Платформа для сборки (например: linux/amd64,linux/arm64)')
    build_parser.add_argument('--push', action='store_true', help='Отправлять в реестр после сборки')
    build_parser.add_argument('--load', action='store_true', help='Загрузить в локальный Docker (по умолчанию)')
    build_parser.add_argument('--builder', help='Имя builder\'а Buildx')
    build_parser.add_argument('--cache-to', help='Сохранять кэш сборки')
    build_parser.add_argument('--cache-from', help='Использовать кэш из указанного источника')
    
    # Push command
    push_parser = subparsers.add_parser('push', help='Отправка образа в реестр')
    push_parser.add_argument('--tag', '-t', default='latest', help='Тег образа')
    push_parser.add_argument('--registry', '-r', help='URL реестра')
    
    # Pull command
    pull_parser = subparsers.add_parser('pull', help='Скачивание образа из реестра')
    pull_parser.add_argument('--tag', '-t', default='latest', help='Тег образа')
    pull_parser.add_argument('--registry', '-r', help='URL реестра')
    
    # Login command
    login_parser = subparsers.add_parser('login', help='Авторизация в реестре')
    login_parser.add_argument('--registry', '-r', help='URL реестра')
    login_parser.add_argument('--username', '-u', help='Имя пользователя')
    login_parser.add_argument('--password', '-p', help='Пароль')
    
    # List command
    list_parser = subparsers.add_parser('list', help='Список локальных образов')
    
    # Builders command
    builders_parser = subparsers.add_parser('builders', help='Список Buildx builders')
    
    # Run command
    run_parser = subparsers.add_parser('run', help='Запуск контейнера')
    run_parser.add_argument('--tag', '-t', default='latest', help='Тег образа')
    run_parser.add_argument('--port', '-p', action='append', help='Порты (формат: хост:контейнер)')
    run_parser.add_argument('--volume', '-v', action='append', help='Тома (формат: хост:контейнер)')
    run_parser.add_argument('--env', '-e', action='append', help='Переменные окружения (формат: КЛЮЧ=значение)')
    run_parser.add_argument('--detach', '-d', action='store_true', help='Запуск в фоне')
    run_parser.add_argument('--name', '-n', help='Имя контейнера')
    run_parser.add_argument('--rm', action='store_true', default=True, help='Удалять контейнер после остановки (по умолчанию)')
    run_parser.add_argument('--no-rm', action='store_false', dest='rm', help='Не удалять контейнер после остановки')
    
    # Clean command
    clean_parser = subparsers.add_parser('clean', help='Очистка Docker ресурсов')
    clean_parser.add_argument('--containers', action='store_true', help='Удалить остановленные контейнеры')
    clean_parser.add_argument('--images', action='store_true', help='Удалить неиспользуемые образы')
    clean_parser.add_argument('--volumes', action='store_true', help='Удалить неиспользуемые тома')
    clean_parser.add_argument('--build-cache', action='store_true', help='Очистить кэш сборки Buildx')
    clean_parser.add_argument('--all', action='store_true', help='Удалить всё')
    
    # Inspect command
    inspect_parser = subparsers.add_parser('inspect', help='Информация об образе')
    inspect_parser.add_argument('--tag', '-t', default='latest', help='Тег образа')
    
    # Scan command
    scan_parser = subparsers.add_parser('scan', help='Сканирование образа на уязвимости')
    scan_parser.add_argument('--tag', '-t', default='latest', help='Тег образа')
    
    # Init command
    init_parser = subparsers.add_parser('init', help='Создание шаблона конфигурации')
    
    # Общие аргументы
    parser.add_argument('--quiet', '-q', action='store_true', help='Тихий режим')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Создание менеджера
    manager = DockerManager(verbose=not args.quiet)
    
    # Обработка команд
    success = True
    output = None
    
    try:
        if args.command == 'build':
            success, output = manager.build(
                tag=args.tag,
                dockerfile=args.dockerfile,
                context=args.context,
                no_cache=args.no_cache,
                pull=args.pull,
                platform=args.platform,
                push=args.push,
                load=args.load,
                builder=args.builder,
                cache_to=args.cache_to,
                cache_from=args.cache_from
            )
            
        elif args.command == 'push':
            success, output = manager.push(tag=args.tag, registry_url=args.registry)
            
        elif args.command == 'pull':
            success, output = manager.pull(tag=args.tag, registry_url=args.registry)
            
        elif args.command == 'login':
            success, output = manager.login(
                registry_url=args.registry,
                username=args.username,
                password=args.password
            )
            
        elif args.command == 'list':
            success, output = manager.list_images()
            
        elif args.command == 'builders':
            success, output = manager.list_builders()
            
        elif args.command == 'run':
            ports_dict = {}
            volumes_dict = {}
            env_dict = {}
            
            # Преобразование аргументов в словари
            if hasattr(args, 'port') and args.port:
                for port in args.port:
                    if ':' in port:
                        host_port, container_port = port.split(':', 1)
                        ports_dict[host_port] = container_port
            
            if hasattr(args, 'volume') and args.volume:
                for volume in args.volume:
                    if ':' in volume:
                        host_path, container_path = volume.split(':', 1)
                        volumes_dict[host_path] = container_path
            
            if hasattr(args, 'env') and args.env:
                for env in args.env:
                    if '=' in env:
                        key, value = env.split('=', 1)
                        env_dict[key] = value
            
            success, output = manager.run_container(
                image_tag=args.tag,
                ports=ports_dict if ports_dict else None,
                volumes=volumes_dict if volumes_dict else None,
                env=env_dict if env_dict else None,
                detach=args.detach,
                name=args.name,
                rm=args.rm
            )
            
        elif args.command == 'clean':
            if hasattr(args, 'all') and args.all:
                remove_containers = remove_images = remove_volumes = remove_build_cache = True
            else:
                remove_containers = args.containers if hasattr(args, 'containers') else False
                remove_images = args.images if hasattr(args, 'images') else False
                remove_volumes = args.volumes if hasattr(args, 'volumes') else False
                remove_build_cache = args.build_cache if hasattr(args, 'build_cache') else False
                
            success, output = manager.clean(
                remove_containers=remove_containers,
                remove_images=remove_images,
                remove_volumes=remove_volumes,
                remove_build_cache=remove_build_cache
            )
            
        elif args.command == 'inspect':
            success, output = manager.inspect_image(tag=args.tag)
            
        elif args.command == 'scan':
            success, output = manager.scan_image(tag=args.tag)
            
        elif args.command == 'init':
            create_config_template()
            success = True
            
        else:
            print(f"Неизвестная команда: {args.command}")
            success = False
            
    except KeyboardInterrupt:
        print("\n⏹️  Операция прервана пользователем")
        sys.exit(130)
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        success = False
    
    # Вывод результата если есть
    if output:
        print(output)
    
    # Завершение работы
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
