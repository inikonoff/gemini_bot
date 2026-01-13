import asyncio
import os
import logging
import sys
import contextlib
from datetime import datetime
import aiohttp
from aiohttp import web
import google.generativeai as genai

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, BotCommandScopeDefault
from aiogram.client.default import DefaultBotProperties

from config import TELEGRAM_TOKEN, LOG_FILE, LOG_LEVEL, ADMIN_IDS, validate_config, GEMINI_API_KEY
from utils.session_manager import user_sessions # Импорт из нового файла

# --- НАСТРОЙКА ЛОГГИРОВАНИЯ ---
def setup_logging():
    if not os.path.exists('logs'): os.makedirs('logs')
    logging.basicConfig(
        level=LOG_LEVEL,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )

setup_logging()
logger = logging.getLogger(__name__)

# --- ИНИЦИАЛИЗАЦИЯ ---
genai.configure(api_key=GEMINI_API_KEY)
bot = Bot(token=TELEGRAM_TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher()

# --- ВЕБ-СЕРВЕР (Для Render) ---
async def health_check(request):
    return web.Response(text="OK")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 8080)))
    await site.start()
    return runner

# --- ЗАПУСК ---
async def on_startup(bot: Bot):
    # Важно: импорт хендлеров только здесь!
    from handlers.gemini_handlers import register_gemini_handlers
    register_gemini_handlers(dp)
    logger.info("✅ Бот готов к работе")

async def main():
    web_runner = await start_web_server()
    dp.startup.register(on_startup)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await web_runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())