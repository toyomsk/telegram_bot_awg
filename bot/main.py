#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Main entry point for the VPN Telegram bot."""
import logging
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

from config.settings import BOT_TOKEN
from bot.handlers import (
    start_handler,
    help_handler,
    add_client_handler,
    get_config_handler,
    list_clients_handler,
    status_handler,
    restart_handler,
    delete_client_handler,
    button_handler
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main() -> None:
    """Запуск бота."""
    # Создание приложения
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрация обработчиков команд
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("help", help_handler))
    application.add_handler(CommandHandler("add_client", add_client_handler))
    application.add_handler(CommandHandler("get_config", get_config_handler))
    application.add_handler(CommandHandler("list_clients", list_clients_handler))
    application.add_handler(CommandHandler("status", status_handler))
    application.add_handler(CommandHandler("restart", restart_handler))
    application.add_handler(CommandHandler("delete_client", delete_client_handler))
    
    # Обработчик inline кнопок
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Запуск бота
    logger.info("🤖 Бот запущен!")
    application.run_polling()

if __name__ == '__main__':
    main()
