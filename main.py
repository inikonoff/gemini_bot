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
from handlers.gemini_handlers import register_gemini_handlers

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

# --- ХРАНЕНИЕ СЕССИЙ ---
class UserSession:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.history = []
        self.current_model = DEFAULT_MODEL
        self.created_at = datetime.now()
        self.message_count = 0
        self.last_activity = datetime.now()

user_sessions = {}

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER ---
async def health_check(request: web.Request):
    return web.json_response({
        "status": "ok",
        "service": "gemini-telegram-bot",
        "timestamp": datetime.now().isoformat(),
        "users": len(user_sessions),
        "model": "Gemini 1.5/3.0 Flash/Pro",
        "version": "2.0.0"
    })

async def start_web_server():
    try:
        app = web.Application()
        app.router.add_get('/', health_check)
        app.router.add_get('/health', health_check)
        app.router.add_get('/ping', health_check)
        
        runner = web.AppRunner(app)
        await runner.setup()
        
        port = int(os.environ.get("PORT", 8080))
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        
        logger.info(f"✅ Веб-сервер запущен на порту {port}")
        return runner
    except Exception as e:
        logger.error(f"❌ Ошибка веб-сервера: {e}")
        raise

# --- САМОПИНГ ДЛЯ RENDER ---
async def self_ping_periodically():
    while True:
        await asyncio.sleep(60)  # Ждем 60 сек после старта
        
        render_url = os.environ.get('RENDER_EXTERNAL_URL')
        if render_url:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{render_url}/ping", timeout=10) as resp:
                        logger.debug(f"🔄 Self-ping: {resp.status}")
            except Exception as e:
                logger.warning(f"⚠️ Self-ping ошибка: {e}")
        
        await asyncio.sleep(300)  # Каждые 5 минут

# --- ОЧИСТКА СЕССИЙ ---
async def cleanup_old_sessions():
    while True:
        try:
            await asyncio.sleep(3600)
            
            now = datetime.now()
            expired = 0
            
            for user_id, session in list(user_sessions.items()):
                if (now - session.last_activity).total_seconds() > 86400:
                    del user_sessions[user_id]
                    expired += 1
            
            if expired > 0:
                logger.info(f"🗑 Очищено {expired} сессий")
                
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"❌ Ошибка очистки: {e}")
            await asyncio.sleep(3600)

# --- КОМАНДЫ БОТА ---
async def setup_bot_commands(bot: Bot):
    try:
        ru_commands = [
            BotCommand(command="start", description="🔄 Главное меню"),
            BotCommand(command="models", description="🤖 Выбор модели Gemini"),
            BotCommand(command="clear", description="🧹 Очистить историю"),
            BotCommand(command="help", description="❓ Помощь"),
            BotCommand(command="stats", description="📊 Статистика"),
            BotCommand(command="image", description="🎨 Создать изображение"),
        ]
        await bot.set_my_commands(ru_commands, scope=BotCommandScopeDefault(), language_code="ru")

        en_commands = [
            BotCommand(command="start", description="🔄 Main Menu"),
            BotCommand(command="models", description="🤖 Select Gemini Model"),
            BotCommand(command="clear", description="🧹 Clear History"),
            BotCommand(command="help", description="❓ Help"),
            BotCommand(command="stats", description="📊 Statistics"),
            BotCommand(command="image", description="🎨 Generate Image"),
        ]
        await bot.set_my_commands(en_commands, scope=BotCommandScopeDefault())
        
        logger.info("✅ Команды настроены")
    except Exception as e:
        logger.error(f"❌ Ошибка команд: {e}")

# --- СОБЫТИЯ ЖИЗНЕННОГО ЦИКЛА ---
async def on_startup(dispatcher: Dispatcher, bot: Bot):
    logger.info("⚙️ Запуск инициализации...")
    
    register_gemini_handlers(dp)
    await setup_bot_commands(bot)
    
    for admin_id in ADMIN_IDS:
        try:
            if admin_id:
                await bot.send_message(
                    admin_id,
                    f"✅ Gemini Bot v2.0 запущен!\n"
                    f"👥 Пользователей: {len(user_sessions)}\n"
                    f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
                )
        except Exception:
            pass
    
    logger.info("✅ Бот готов!")

async def on_shutdown(dispatcher: Dispatcher, bot: Bot):
    logger.info("🛑 Остановка...")
    user_sessions.clear()
    await bot.session.close()
    logger.info("👋 Бот остановлен")

@contextlib.asynccontextmanager
async def lifespan():
    logger.info("🔗 Инициализация ресурсов...")
    
    web_runner = await start_web_server()
    cleanup_task = asyncio.create_task(cleanup_old_sessions())
    ping_task = asyncio.create_task(self_ping_periodically())
    
    logger.info("✅ Фоновые задачи запущены")
    
    try:
        yield
    finally:
        logger.info("🧹 Очистка ресурсов...")
        cleanup_task.cancel()
        ping_task.cancel()
        await web_runner.cleanup()
        logger.info("✅ Ресурсы освобождены")

# --- ГЛАВНАЯ ФУНКЦИЯ ---
async def main():
    logger.info("🚀 Запуск Gemini Telegram Bot v2.0...")
    
    async with lifespan():
        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)
        
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            logger.info("✅ Webhook сброшен")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка webhook: {e}")
        
        logger.info("⏳ Запуск polling...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Остановлено пользователем")
    except Exception as e:
        logger.critical(f"💀 Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)