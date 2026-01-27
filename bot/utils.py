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

def _get_container_name() -> Optional[str]:
    """Получить имя контейнера Amnezia."""
    try:
        result = subprocess.run(
            ['docker', 'ps', '--filter', 'name=amnezia-awg', '--format', '{{.Names}}'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            container_name = result.stdout.strip().split('\n')[0]
            logger.info(f"Найден контейнер: {container_name}")
            return container_name
    except Exception as e:
        logger.warning(f"Не удалось найти контейнер: {e}")
    return None

def _run_wg_in_container(cmd: list, container_name: Optional[str] = None) -> subprocess.CompletedProcess:
    """Выполнить команду wg внутри Docker контейнера."""
    if container_name is None:
        container_name = _get_container_name()
    
    if container_name:
        # Выполняем команду через docker exec
        docker_cmd = ['docker', 'exec', container_name] + cmd
        return subprocess.run(
            docker_cmd,
            capture_output=True,
            text=True,
            timeout=10
        )
    else:
        # Если контейнер не найден, выполняем на хосте
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10
        )

def reload_wg_config(vpn_config_dir: str) -> Tuple[bool, str]:
    """Применить конфигурацию WireGuard без перезапуска (добавление только последнего нового пира через wg set)."""
    try:
        config_path = os.path.join(vpn_config_dir, "wg0.conf")
        if not os.path.exists(config_path):
            return False, "Конфиг не найден"
        
        container_name = _get_container_name()
        
        # Получаем список текущих пиров из интерфейса
        existing_peers = set()
        try:
            result = _run_wg_in_container(['wg', 'show', WG_INTERFACE], container_name)
            if result.returncode == 0 and result.stdout.strip():
                # Парсим публичные ключи пиров из вывода wg show
                # Формат: peer: <публичный_ключ>
                peer_keys = re.findall(r'peer:\s*([A-Za-z0-9+/=]{44})', result.stdout)
                existing_peers = set(peer_keys)
                logger.info(f"Найдено существующих пиров: {len(existing_peers)}")
        except Exception as e:
            logger.warning(f"Не удалось получить список текущих пиров: {e}")
            existing_peers = set()
        
        # Читаем конфиг и находим последний пир (самый новый, добавленный в конец)
        with open(config_path, 'r') as f:
            config_content = f.read()
        
        # Находим все секции [Peer] и берем последнюю
        peer_sections = re.findall(
            r'\[Peer\]\s*\n(.*?)(?=\n\[Peer\]|\n\[Interface\]|\Z)',
            config_content,
            re.DOTALL
        )
        
        if not peer_sections:
            return True, "✅ Конфигурация актуальна (пиров нет в конфиге)"
        
        # Берем последний пир (самый новый)
        last_peer_section = peer_sections[-1]
        
        # Извлекаем публичный ключ
        public_key_match = re.search(r'PublicKey\s*=\s*([A-Za-z0-9+/=]{44})', last_peer_section)
        if not public_key_match:
            return False, "Не удалось найти публичный ключ последнего пира"
        
        public_key = public_key_match.group(1).strip()
        
        # Проверяем, есть ли уже такой пир
        if public_key in existing_peers:
            logger.info(f"Пир {public_key[:8]}... уже существует в интерфейсе")
            return True, "✅ Конфигурация актуальна (пир уже применен)"
        
        logger.info(f"Добавляем новый пир: {public_key[:8]}...")
        
        # Формируем команду wg set для добавления пира
        # Используем bash -c для правильной передачи ключей через echo
        psk_match = re.search(r'PresharedKey\s*=\s*([A-Za-z0-9+/=]{44})', last_peer_section)
        allowed_ips_match = re.search(r'AllowedIPs\s*=\s*([^\s]+)', last_peer_section)
        
        if not allowed_ips_match:
            return False, "Не найден AllowedIPs для последнего пира"
        
        allowed_ips = allowed_ips_match.group(1)
        
        # Формируем команду через bash для правильной передачи ключей
        if psk_match:
            psk = psk_match.group(1)
            # Используем echo для передачи ключей через pipe
            wg_cmd = f"echo '{psk}' | wg set {WG_INTERFACE} peer {public_key} preshared-key - allowed-ips {allowed_ips}"
        else:
            wg_cmd = f"wg set {WG_INTERFACE} peer {public_key} allowed-ips {allowed_ips}"
        
        logger.info(f"Выполняем команду wg set для пира {public_key[:8]}...")
        
        if container_name:
            # Выполняем через docker exec с bash
            cmd = ['docker', 'exec', container_name, 'bash', '-c', wg_cmd]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
        else:
            # Выполняем на хосте
            result = subprocess.run(
                ['bash', '-c', wg_cmd],
                capture_output=True,
                text=True,
                timeout=10
            )
        
        if result.returncode == 0:
            logger.info(f"✅ Добавлен пир {public_key[:8]}...")
            return True, f"✅ Конфигурация применена (добавлен пир {public_key[:8]}...)"
        else:
            error_msg = result.stderr if result.stderr else result.stdout
            # Если пир уже существует, это не критичная ошибка
            if "already exists" in error_msg.lower() or "file exists" in error_msg.lower():
                logger.info(f"Пир {public_key[:8]}... уже существует")
                return True, "✅ Конфигурация актуальна (пир уже существует)"
            else:
                logger.warning(f"Ошибка добавления пира: {error_msg}")
                return False, f"Ошибка добавления пира: {error_msg}"
            
    except FileNotFoundError:
        logger.error("Команда wg не найдена")
        return False, "wg команда недоступна"
    except Exception as e:
        logger.error(f"Ошибка применения конфигурации: {e}")
        return False, f"Ошибка: {e}"

def restart_vpn(docker_compose_dir: str, vpn_config_dir: str = None) -> Tuple[bool, str]:
    """Применить изменения конфигурации VPN через wg syncconf (без перезапуска)."""
    if vpn_config_dir is None:
        vpn_config_dir = VPN_CONFIG_DIR
    
    return reload_wg_config(vpn_config_dir)
