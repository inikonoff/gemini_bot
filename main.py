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

from config import TELEGRAM_TOKEN, LOG_FILE, LOG_LEVEL, ADMIN_IDS, validate_config, GEMINI_API_KEY, DEFAULT_MODEL
# Импортируем сессии из нового менеджера
from utils.session_manager import user_sessions

# --- НАСТРОЙКА ЛОГГИРОВАНИЯ ---
def setup_logging():
    if not os.path.exists('logs'):
        os.makedirs('logs')

    logging.basicConfig(
        level=LOG_LEVEL,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logging.getLogger('aiogram').setLevel(logging.WARNING)
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    
setup_logging()
logger = logging.getLogger(__name__)

# --- ИНИЦИАЛИЗАЦИЯ GEMINI ---
try:
    genai.configure(api_key=GEMINI_API_KEY)
    logger.info("✅ Gemini API сконфигурирован")
except Exception as e:
    logger.error(f"❌ Ошибка инициализации Gemini: {e}")
    sys.exit(1)

# --- ИНИЦИАЛИЗАЦИЯ БОТА ---
try:
    validate_config()
except ValueError as e:
    logger.error(f"❌ Ошибка конфигурации: {e}")
    sys.exit(1)

bot = Bot(token=TELEGRAM_TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher()

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER ---
async def health_check(request: web.Request):
    return web.json_response({
        "status": "ok",
        "users": len(user_sessions),
        "timestamp": datetime.now().isoformat()
    })

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    return runner

# --- ОЧИСТКА СЕССИЙ ---
async def cleanup_old_sessions():
    while True:
        await asyncio.sleep(3600)
        now = datetime.now()
        for user_id, session in list(user_sessions.items()):
            if (now - session.last_activity).total_seconds() > 86400:
                del user_sessions[user_id]

# --- СОБЫТИЯ ЖИЗНЕННОГО ЦИКЛА ---
async def on_startup(bot: Bot):
    # Импорт хендлеров внутри функции для предотвращения Circular Import
    from handlers.gemini_handlers import register_gemini_handlers
    register_gemini_handlers(dp)
    
    logger.info("✅ Бот запущен и хендлеры зарегистрированы")

@contextlib.asynccontextmanager
async def lifespan(bot: Bot):
    web_runner = await start_web_server()
    cleanup_task = asyncio.create_task(cleanup_old_sessions())
    try:
        yield
    finally:
        cleanup_task.cancel()
        await web_runner.cleanup()

async def main():
    async with lifespan(bot):
        dp.startup.register(on_startup)
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
