"""Utility functions for VPN bot."""
import os
import re
import subprocess
import qrcode
import io
import logging
from typing import Optional, Tuple, Dict
from config.settings import VPN_BASE_IP, VPN_CLIENT_START_IP, VPN_CONFIG_DIR, WG_INTERFACE, WG_RELOAD_METHOD, DOCKER_COMPOSE_DIR

logger = logging.getLogger(__name__)

def get_external_ip() -> str:
    """Получить внешний IP сервера."""
    try:
        result = subprocess.run(
            ['curl', '-s', 'ifconfig.me'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception as e:
        logger.error(f"Ошибка получения внешнего IP: {e}")
    return "UNKNOWN_IP"

def get_amnezia_params(vpn_config_dir: str) -> Optional[Dict[str, int]]:
    """Получить параметры AmneziaVPN из серверного конфига."""
    try:
        config_path = os.path.join(vpn_config_dir, "wg0.conf")
        if not os.path.exists(config_path):
            logger.warning(f"Конфиг не найден: {config_path}")
            return None
        
        with open(config_path, 'r') as f:
            content = f.read()
        
        # Ищем секцию [Interface] и извлекаем параметры
        params = {}
        param_names = ['Jc', 'Jmin', 'Jmax', 'S1', 'S2', 'H1', 'H2', 'H3', 'H4']
        
        for param_name in param_names:
            # Ищем параметр в секции [Interface]
            pattern = rf'\[Interface\].*?{param_name}\s*=\s*(\d+)'
            match = re.search(pattern, content, re.DOTALL)
            if match:
                try:
                    params[param_name] = int(match.group(1))
                except ValueError:
                    logger.warning(f"Не удалось преобразовать {param_name} в число")
        
        # Проверяем, что все параметры найдены
        if len(params) == len(param_names):
            logger.info(f"Параметры AmneziaVPN загружены из конфига: {params}")
            return params
        else:
            missing = set(param_names) - set(params.keys())
            logger.warning(f"Не найдены параметры AmneziaVPN: {missing}")
            return None
            
    except Exception as e:
        logger.error(f"Ошибка чтения параметров AmneziaVPN: {e}")
        return None

def get_server_public_key(vpn_config_dir: str) -> Optional[str]:
    """Получить публичный ключ сервера из конфига."""
    try:
        config_path = os.path.join(vpn_config_dir, "wg0.conf")
        if not os.path.exists(config_path):
            logger.error(f"Файл конфигурации не найден: {config_path}")
            return None
        
        with open(config_path, 'r') as f:
            content = f.read()
        
        # Ищем секцию [Interface] и извлекаем PrivateKey
        interface_match = re.search(
            r'\[Interface\].*?PrivateKey\s*=\s*([^\s]+)',
            content,
            re.DOTALL
        )
        
        if not interface_match:
            logger.error("Не найден PrivateKey сервера в конфиге")
            return None
        
        private_key = interface_match.group(1).strip()
        
        # Генерируем публичный ключ из приватного
        result = subprocess.run(
            ['wg', 'pubkey'],
            input=private_key,
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            logger.error(f"Ошибка генерации публичного ключа: {result.stderr}")
            return None
            
    except Exception as e:
        logger.error(f"Ошибка получения публичного ключа сервера: {e}")
        return None

def get_next_client_ip(vpn_config_dir: str) -> int:
    """Найти следующий доступный IP для клиента."""
    try:
        config_path = os.path.join(vpn_config_dir, "wg0.conf")
        if not os.path.exists(config_path):
            # Если конфига нет, начинаем с начального IP
            return VPN_CLIENT_START_IP
        
        with open(config_path, 'r') as f:
            content = f.read()
        
        # Находим все использованные IP адреса клиентов
        # Экранируем точку в базовом IP для regex
        base_ip_escaped = VPN_BASE_IP.replace('.', r'\.')
        ips = re.findall(rf'AllowedIPs\s*=\s*{base_ip_escaped}\.(\d+)/32', content)
        
        if ips:
            max_ip = max([int(ip) for ip in ips])
            return max_ip + 1
        else:
            # Начинаем с начального IP
            return VPN_CLIENT_START_IP
            
    except Exception as e:
        logger.error(f"Ошибка определения следующего IP: {e}")
        return VPN_CLIENT_START_IP

def generate_keys() -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Генерация ключей WireGuard."""
    try:
        # Private key
        result = subprocess.run(
            ['wg', 'genkey'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            logger.error(f"Ошибка генерации приватного ключа: {result.stderr}")
            return None, None, None
        
        private_key = result.stdout.strip()
        
        # Public key
        result = subprocess.run(
            ['wg', 'pubkey'],
            input=private_key,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            logger.error(f"Ошибка генерации публичного ключа: {result.stderr}")
            return None, None, None
        
        public_key = result.stdout.strip()
        
        # PSK
        result = subprocess.run(
            ['wg', 'genpsk'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            logger.error(f"Ошибка генерации PSK: {result.stderr}")
            return None, None, None
        
        psk = result.stdout.strip()
        
        return private_key, public_key, psk
        
    except Exception as e:
        logger.error(f"Ошибка генерации ключей: {e}")
        return None, None, None

def generate_qr_code(config_text: str) -> Optional[io.BytesIO]:
    """Генерация QR-кода для конфига."""
    try:
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(config_text)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Сохранить в BytesIO
        bio = io.BytesIO()
        img.save(bio, 'PNG')
        bio.seek(0)
        return bio
    except Exception as e:
        logger.error(f"Ошибка генерации QR-кода: {e}")
        return None

def get_server_status(docker_compose_dir: str, vpn_config_dir: str) -> str:
    """Получить статус сервера."""
    try:
        # Статус контейнера
        docker_status = "Контейнер не найден"
        try:
            result = subprocess.run(
                ['docker', 'ps', '--filter', 'name=amnezia-awg', '--format', 'table {{.Names}}\t{{.Status}}'],
                capture_output=True,
                text=True,
                cwd=docker_compose_dir,
                timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                docker_status = result.stdout.strip()
        except Exception as e:
            logger.error(f"Ошибка проверки статуса Docker: {e}")
        
        # WireGuard статус
        wg_info = "WireGuard интерфейс не активен"
        try:
            result = subprocess.run(
                ['wg', 'show'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                wg_output = result.stdout.strip()
                # Подсчет активных соединений
                active_connections = len(re.findall(r'latest handshake:', wg_output))
                wg_info = f"Активных подключений: {active_connections}"
        except Exception as e:
            logger.error(f"Ошибка проверки статуса WireGuard: {e}")
        
        external_ip = get_external_ip()
        
        # Используем code блок для Docker статуса, чтобы избежать проблем с экранированием
        status = f"""🖥 **Статус сервера:**

📦 **Docker:**
```
{docker_status}
```

🔐 **WireGuard:**
{wg_info}

🌐 **Внешний IP:** `{external_ip}`
"""
        return status
        
    except Exception as e:
        logger.error(f"Ошибка при получении статуса: {e}")
        return f"❌ Ошибка при получении статуса: {e}"

def reload_wg_config(vpn_config_dir: str) -> Tuple[bool, str]:
    """Применить конфигурацию WireGuard без перезапуска (wg syncconf)."""
    try:
        config_path = os.path.join(vpn_config_dir, "wg0.conf")
        if not os.path.exists(config_path):
            return False, "Конфиг не найден"
        
        # Используем wg syncconf для применения изменений без перезапуска
        result = subprocess.run(
            ['wg', 'syncconf', WG_INTERFACE, config_path],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            logger.info(f"Конфигурация WireGuard применена через syncconf")
            return True, "✅ Конфигурация применена"
        else:
            error_msg = result.stderr if result.stderr else result.stdout
            logger.warning(f"Ошибка syncconf: {error_msg}")
            return False, f"Ошибка syncconf: {error_msg}"
            
    except FileNotFoundError:
        logger.warning("Команда wg не найдена, используем docker restart")
        return False, "wg команда недоступна"
    except Exception as e:
        logger.error(f"Ошибка применения конфигурации: {e}")
        return False, f"Ошибка: {e}"

def restart_vpn_docker(docker_compose_dir: str) -> Tuple[bool, str]:
    """Полный перезапуск VPN через Docker."""
    try:
        result = subprocess.run(
            ['docker', 'compose', 'restart'],
            capture_output=True,
            text=True,
            cwd=docker_compose_dir,
            timeout=60
        )
        if result.returncode == 0:
            return True, "✅ VPN сервер перезапущен"
        else:
            error_msg = result.stderr if result.stderr else result.stdout
            return False, f"❌ Ошибка перезапуска: {error_msg}"
    except Exception as e:
        logger.error(f"Ошибка перезапуска VPN: {e}")
        return False, f"❌ Ошибка: {e}"

def restart_vpn(docker_compose_dir: str, vpn_config_dir: str = None) -> Tuple[bool, str]:
    """Применить изменения конфигурации VPN.
    
    Пытается использовать wg syncconf (быстро, без разрыва соединений),
    если не получается - делает docker restart.
    """
    if vpn_config_dir is None:
        vpn_config_dir = VPN_CONFIG_DIR
    
    # Если метод syncconf, пробуем его сначала
    if WG_RELOAD_METHOD == "syncconf" or WG_RELOAD_METHOD == "auto":
        success, message = reload_wg_config(vpn_config_dir)
        if success:
            return True, "✅ Конфигурация применена (без перезапуска)"
        
        # Если syncconf не сработал и метод auto, пробуем docker restart
        if WG_RELOAD_METHOD == "auto":
            logger.info("syncconf не сработал, используем docker restart")
            return restart_vpn_docker(docker_compose_dir)
        else:
            # Если метод строго syncconf и не сработал, возвращаем ошибку
            return False, message
    
    # Если метод restart, сразу делаем docker restart
    return restart_vpn_docker(docker_compose_dir)
