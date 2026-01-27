"""Configuration settings loaded from environment variables."""
import os
from typing import List
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Токен бота (обязательный)
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не установлен в переменных окружения или .env файле")

# ID администраторов (обязательный)
ADMIN_IDS_STR = os.getenv("ADMIN_IDS", "")
if not ADMIN_IDS_STR:
    raise ValueError("ADMIN_IDS не установлен в переменных окружения или .env файле")

try:
    ADMIN_IDS = [int(admin_id.strip()) for admin_id in ADMIN_IDS_STR.split(",")]
except ValueError:
    raise ValueError("ADMIN_IDS должен содержать числовые ID, разделенные запятыми")

# Пути к конфигурации VPN
VPN_CONFIG_DIR = os.getenv("VPN_CONFIG_DIR", "/opt/docker/amnezia/awg-config")
DOCKER_COMPOSE_DIR = os.getenv("DOCKER_COMPOSE_DIR", "/opt/docker/amnezia")

# Порт WireGuard
WG_PORT = int(os.getenv("WG_PORT", "51820"))

# Подсеть VPN
VPN_SUBNET = os.getenv("VPN_SUBNET", "10.10.1.0/24")

# Базовый IP адрес для клиентов (первые 3 октета, например "10.10.1")
VPN_BASE_IP = os.getenv("VPN_BASE_IP", "10.10.1")

# Начальный IP адрес для клиентов (последний октет, обычно 2, так как 1 занят сервером)
VPN_CLIENT_START_IP = int(os.getenv("VPN_CLIENT_START_IP", "2"))

# DNS серверы для клиентов (через запятую, например "1.1.1.1,8.8.8.8")
DNS_SERVERS_STR = os.getenv("DNS_SERVERS", "1.1.1.1,8.8.8.8")
DNS_SERVERS = [dns.strip() for dns in DNS_SERVERS_STR.split(",") if dns.strip()]
# Форматируем для использования в конфиге (через запятую)
DNS_SERVERS_FORMATTED = ", ".join(DNS_SERVERS)

# Параметры AmneziaVPN (obfuscation)
AMNEZIA_JC = int(os.getenv("AMNEZIA_JC", "2"))
AMNEZIA_JMIN = int(os.getenv("AMNEZIA_JMIN", "10"))
AMNEZIA_JMAX = int(os.getenv("AMNEZIA_JMAX", "50"))
AMNEZIA_S1 = int(os.getenv("AMNEZIA_S1", "42"))
AMNEZIA_S2 = int(os.getenv("AMNEZIA_S2", "94"))
AMNEZIA_H1 = int(os.getenv("AMNEZIA_H1", "2128364304"))
AMNEZIA_H2 = int(os.getenv("AMNEZIA_H2", "1938340076"))
AMNEZIA_H3 = int(os.getenv("AMNEZIA_H3", "1419736917"))
AMNEZIA_H4 = int(os.getenv("AMNEZIA_H4", "478726153"))

# Имя интерфейса WireGuard (обычно wg0)
WG_INTERFACE = os.getenv("WG_INTERFACE", "wg0")

# Метод применения изменений: "syncconf" (рекомендуется) или "restart" (docker restart)
# syncconf применяет изменения без перезапуска, не прерывая соединения
WG_RELOAD_METHOD = os.getenv("WG_RELOAD_METHOD", "syncconf")

def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором."""
    return user_id in ADMIN_IDS
