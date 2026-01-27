"""Telegram bot command handlers."""
import os
import re
import io
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from config.settings import (
    is_admin,
    VPN_CONFIG_DIR,
    DOCKER_COMPOSE_DIR,
    WG_PORT,
    WG_INTERFACE,
    AMNEZIA_JC,
    AMNEZIA_JMIN,
    AMNEZIA_JMAX,
    AMNEZIA_S1,
    AMNEZIA_S2,
    AMNEZIA_H1,
    AMNEZIA_H2,
    AMNEZIA_H3,
    AMNEZIA_H4
)
from bot.vpn_manager import (
    create_client,
    delete_client,
    list_clients,
    get_client_config
)
from bot.utils import (
    generate_qr_code,
    get_server_status,
    restart_vpn
)

logger = logging.getLogger(__name__)

def generate_keenetic_command() -> str:
    """Генерация команды для роутеров Keenetic."""
    return f"interface <INTERFACE> wireguard asc {AMNEZIA_JC} {AMNEZIA_JMIN} {AMNEZIA_JMAX} {AMNEZIA_S1} {AMNEZIA_S2} {AMNEZIA_H1} {AMNEZIA_H2} {AMNEZIA_H3} {AMNEZIA_H4}"

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /start."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав доступа к этому боту.")
        return
    
    welcome_text = """🎛 **VPN Manager Bot**

Доступные команды:
/add\\_client `<имя>` - Создать клиента
/list\\_clients - Список клиентов  
/get\\_config `<имя>` - Получить конфиг
/delete\\_client `<имя>` - Удалить клиента
/status - Статус сервера
/restart - Перезапуск VPN
/help - Эта справка"""
    
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN_V2)

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /help."""
    await start_handler(update, context)

async def add_client_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Добавление клиента."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Недостаточно прав")
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ Укажите имя клиента: `/add_client имя`",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return
    
    client_name = context.args[0]
    
    # Проверка на недопустимые символы
    if not re.match(r'^[a-zA-Z0-9_-]+$', client_name):
        await update.message.reply_text(
            "❌ Имя может содержать только буквы, цифры, _ и -"
        )
        return
    
    await update.message.reply_text(
        f"🔄 Создаю клиента `{client_name}`\\.\\.\\.",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    
    success, config_or_error = create_client(
        client_name,
        VPN_CONFIG_DIR,
        DOCKER_COMPOSE_DIR,
        WG_PORT
    )
    
    if success:
        # Применение изменений конфигурации VPN
        restart_success, restart_msg = restart_vpn(DOCKER_COMPOSE_DIR, VPN_CONFIG_DIR)
        
        status_msg = "✅ Клиент создан успешно\\!\n"
        if restart_success:
            status_msg += f"🔄 {restart_msg}\n\n"
        else:
            status_msg += f"⚠️ {restart_msg}\n\n"
        
        status_msg += f"📋 Используйте `/get_config {client_name}` для получения конфига"
        
        await update.message.reply_text(
            status_msg,
            parse_mode=ParseMode.MARKDOWN_V2
        )
    else:
        await update.message.reply_text(
            f"❌ Ошибка создания клиента: {config_or_error}"
        )

async def get_config_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Получение конфига клиента."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Недостаточно прав")
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ Укажите имя клиента: `/get_config имя`",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return
    
    client_name = context.args[0]
    config_content = get_client_config(client_name, DOCKER_COMPOSE_DIR)
    
    if not config_content:
        await update.message.reply_text(
            f"❌ Клиент `{client_name}` не найден",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return
    
    try:
        # Отправка конфига файлом
        config_file = io.BytesIO(config_content.encode('utf-8'))
        config_file.name = f"{client_name}.conf"
        
        # Генерация QR-кода
        qr_image = generate_qr_code(config_content)
        
        # Генерация команды для Keenetic
        keenetic_cmd = generate_keenetic_command()
        
        # Отправляем QR-код
        if qr_image:
            await update.message.reply_photo(
                photo=qr_image,
                caption=f"📱 QR\\-код для `{client_name}`",
                parse_mode=ParseMode.MARKDOWN_V2
            )
        
        # Отправляем файл конфига
        await update.message.reply_document(
            document=config_file,
            caption=f"📋 Конфиг для `{client_name}`",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        
        # Отправляем команду для Keenetic
        keenetic_info = f"""🔧 **Команда для роутера Keenetic:**

```
{keenetic_cmd}
```

ℹ️ **Информация:**
• Для начала необходимо создать новое подключение с помощью приложенного конфиг-файла
• После этого необходимо узнать имя нового интерфейса: `show interface`
• Чтобы сохранить параметры необходимо выполнить команду: `system configuration save`
"""
        await update.message.reply_text(keenetic_info, parse_mode=ParseMode.MARKDOWN_V2)
        
    except Exception as e:
        logger.error(f"Ошибка отправки конфига: {e}")
        await update.message.reply_text(f"❌ Ошибка отправки конфига: {e}")

async def list_clients_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Список клиентов."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Недостаточно прав")
        return
    
    clients_list = list_clients(VPN_CONFIG_DIR, DOCKER_COMPOSE_DIR)
    await update.message.reply_text(clients_list, parse_mode=ParseMode.MARKDOWN_V2)

async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Статус сервера."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Недостаточно прав")
        return
    
    status = get_server_status(DOCKER_COMPOSE_DIR, VPN_CONFIG_DIR)
    await update.message.reply_text(status, parse_mode=ParseMode.MARKDOWN_V2)

async def restart_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Перезапуск VPN."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Недостаточно прав")
        return
    
    await update.message.reply_text("🔄 Применяю изменения конфигурации VPN\\.\\.\\.",
                                    parse_mode=ParseMode.MARKDOWN_V2)
    
    success, message = restart_vpn(DOCKER_COMPOSE_DIR, VPN_CONFIG_DIR)
    await update.message.reply_text(message)

async def delete_client_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Удаление клиента."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Недостаточно прав")
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ Укажите имя клиента: `/delete_client имя`",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return
    
    client_name = context.args[0]
    config_path = os.path.join(DOCKER_COMPOSE_DIR, f"{client_name}.conf")
    
    if not os.path.exists(config_path):
        await update.message.reply_text(
            f"❌ Клиент `{client_name}` не найден",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return
    
    # Кнопки подтверждения
    keyboard = [
        [InlineKeyboardButton("✅ Да, удалить", callback_data=f"delete_yes_{client_name}")],
        [InlineKeyboardButton("❌ Отмена", callback_data="delete_no")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"⚠️ Вы уверены, что хотите удалить клиента `{client_name}`\\?\nЭто действие необратимо\\!",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN_V2
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик нажатий кнопок."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not is_admin(user_id):
        await query.edit_message_text("❌ Недостаточно прав")
        return
    
    if query.data.startswith("delete_yes_"):
        client_name = query.data.replace("delete_yes_", "")
        
        success, message = delete_client(client_name, VPN_CONFIG_DIR, DOCKER_COMPOSE_DIR)
        
        if success:
            # Применение изменений конфигурации VPN
            restart_success, restart_msg = restart_vpn(DOCKER_COMPOSE_DIR, VPN_CONFIG_DIR)
            
            status_msg = f"✅ Клиент `{client_name}` удален\n"
            if restart_success:
                status_msg += f"🔄 {restart_msg}"
            else:
                status_msg += f"⚠️ {restart_msg}"
            
            await query.edit_message_text(status_msg, parse_mode=ParseMode.MARKDOWN_V2)
        else:
            await query.edit_message_text(f"❌ Ошибка удаления: {message}")
    
    elif query.data == "delete_no":
        await query.edit_message_text("❌ Удаление отменено")
