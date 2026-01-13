import asyncio
import os
import logging
import sys
import contextlib
from datetime import datetime
import aiohttp
from aiohttp import web

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, BotCommandScopeDefault
from aiogram.client.default import DefaultBotProperties

from config import TELEGRAM_TOKEN, LOG_FILE, LOG_LEVEL, ADMIN_IDS, validate_config
from handlers.gemini_handlers import register_gemini_handlers

# --- НАСТРОЙКА ЛОГГИРОВАНИЯ ---
def setup_logging():
    """Настройка логирования в файл и консоль"""
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
    # Уменьшаем логи внешних библиотек
    logging.getLogger('aiogram').setLevel(logging.WARNING)
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    
setup_logging()
logger = logging.getLogger(__name__)

# --- ИНИЦИАЛИЗАЦИЯ ---
try:
    validate_config()
except ValueError as e:
    logger.error(f"❌ Критическая ошибка конфигурации: {e}", exc_info=True)
    sys.exit(1)

# Создаем бота и диспетчер
bot = Bot(token=TELEGRAM_TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher()

# --- ХРАНЕНИЕ СЕССИЙ В ПАМЯТИ ---
class UserSession:
    """Класс для хранения сессии пользователя в памяти"""
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.history = []
        self.current_model = 'gemini-1.5-flash'
        self.created_at = datetime.now()
        self.message_count = 0
        self.last_activity = datetime.now()

# Словарь для хранения сессий
user_sessions = {}

# --- 🌐 ВЕБ-СЕРВЕР ДЛЯ RENDER.COM И UPTIME ROBOT ---
async def health_check(request: web.Request):
    """Эндпоинт для проверки работоспособности бота"""
    return web.json_response({
        "status": "ok",
        "service": "gemini-telegram-bot",
        "timestamp": datetime.now().isoformat(),
        "users_count": len(user_sessions),
        "uptime": "running"
    })

async def start_web_server():
    """Запуск веб-сервера для Render.com"""
    try:
        app = web.Application()
        
        # Регистрируем эндпоинты
        app.router.add_get('/', health_check)
        app.router.add_get('/health', health_check)
        app.router.add_get('/ping', health_check)  # для UptimeRobot
        app.router.add_get('/status', health_check)
        
        runner = web.AppRunner(app)
        await runner.setup()
        
        # Render.com предоставляет порт через переменную окружения PORT
        port = int(os.environ.get("PORT", 8080))
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        
        logger.info(f"✅ Веб-сервер запущен на порту {port}")
        logger.info(f"🌐 Health check доступен по: http://0.0.0.0:{port}/health")
        
        # Если есть внешний URL, логируем его
        render_url = os.environ.get('RENDER_EXTERNAL_URL')
        if render_url:
            logger.info(f"🌐 Внешний URL: {render_url}")
        
        return runner
    except Exception as e:
        logger.error(f"❌ Ошибка запуска веб-сервера: {e}", exc_info=True)
        raise

# --- САМОПИНГ ДЛЯ БЕСПЛАТНОГО РЕЖИМА RENDER ---
async def self_ping_periodically():
    """
    Периодически пингуем себя, чтобы бот не засыпал
    на бесплатном тарифе Render.com
    """
    while True:
        try:
            # Ждем 60 секунд после старта
            await asyncio.sleep(60)
            
            # Получаем URL нашего сервиса
            render_url = os.environ.get('RENDER_EXTERNAL_URL')
            if render_url:
                async with aiohttp.ClientSession() as session:
                    try:
                        async with session.get(f"{render_url}/ping", timeout=10) as resp:
                            if resp.status == 200:
                                logger.info(f"🔄 Self-ping успешен: {resp.status}")
                            else:
                                logger.warning(f"⚠️ Self-ping статус: {resp.status}")
                    except asyncio.TimeoutError:
                        logger.warning("⚠️ Self-ping timeout")
                    except Exception as e:
                        logger.error(f"❌ Self-ping ошибка: {e}")
            else:
                logger.debug("Self-ping пропущен (нет внешнего URL)")
                
            # Пингуем каждые 5 минут (бесплатный Render засыпает после 15 минут неактивности)
            await asyncio.sleep(300)
            
        except asyncio.CancelledError:
            logger.info("Self-ping задача остановлена")
            break
        except Exception as e:
            logger.error(f"Ошибка в self-ping: {e}")
            await asyncio.sleep(300)

# --- ОЧИСТКА СТАРЫХ СЕССИЙ ---
async def cleanup_old_sessions():
    """Очищаем сессии пользователей, которые неактивны более 24 часов"""
    while True:
        try:
            await asyncio.sleep(3600)  # Проверяем каждый час
            
            now = datetime.now()
            expired_count = 0
            
            for user_id, session in list(user_sessions.items()):
                # Удаляем сессии старше 24 часов
                time_diff = (now - session.last_activity).total_seconds()
                if time_diff > 86400:  # 24 часа в секундах
                    del user_sessions[user_id]
                    expired_count += 1
            
            if expired_count > 0:
                logger.info(f"🗑 Очищено {expired_count} неактивных сессий")
                
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"❌ Ошибка очистки сессий: {e}")
            await asyncio.sleep(3600)

# --- НАСТРОЙКА КОМАНД БОТА ---
async def setup_bot_commands(bot: Bot):
    """Настройка меню команд бота"""
    try:
        # Команды для русского языка
        ru_commands = [
            BotCommand(command="start", description="🔄 Главное меню"),
            BotCommand(command="models", description="🤖 Выбор модели"),
            BotCommand(command="clear", description="🧹 Очистить историю"),
            BotCommand(command="help", description="❓ Помощь"),
            BotCommand(command="stats", description="📊 Статистика"),
        ]
        await bot.set_my_commands(ru_commands, scope=BotCommandScopeDefault(), language_code="ru")

        # Команды по умолчанию (английский)
        en_commands = [
            BotCommand(command="start", description="🔄 Main Menu"),
            BotCommand(command="models", description="🤖 Select Model"),
            BotCommand(command="clear", description="🧹 Clear History"),
            BotCommand(command="help", description="❓ Help"),
            BotCommand(command="stats", description="📊 Statistics"),
        ]
        await bot.set_my_commands(en_commands, scope=BotCommandScopeDefault())
        
        logger.info("✅ Команды бота настроены (RU + EN)")
        
    except Exception as e:
        logger.error(f"❌ Ошибка настройки команд: {e}")

# --- СОБЫТИЯ ЖИЗНЕННОГО ЦИКЛА ---
async def on_startup(dispatcher: Dispatcher, bot: Bot):
    """Действия при запуске бота"""
    logger.info("⚙️ Запуск инициализации...")
    
    # Регистрируем обработчики
    register_gemini_handlers(dp)
    
    # Настраиваем команды бота
    await setup_bot_commands(bot)
    
    # Уведомляем администраторов
    for admin_id in ADMIN_IDS:
        try:
            if admin_id:
                await bot.send_message(
                    admin_id,
                    f"✅ Gemini Bot запущен!\n"
                    f"👥 Пользователей в памяти: {len(user_sessions)}\n"
                    f"🕐 Время запуска: {datetime.now().strftime('%H:%M %d.%m.%Y')}\n"
                    f"⚙️ Версия: 1.0.0"
                )
                logger.info(f"📨 Уведомление отправлено админу {admin_id}")
        except Exception as e:
            logger.warning(f"Не удалось отправить уведомление админу {admin_id}: {e}")
    
    logger.info("✅ Бот инициализирован и готов к работе!")

async def on_shutdown(dispatcher: Dispatcher, bot: Bot):
    """Действия при остановке бота"""
    logger.info("🛑 Начало остановки бота...")
    
    # Очищаем сессии
    user_sessions.clear()
    logger.info("🗑 Все сессии пользователей очищены")
    
    # Закрываем сессию бота
    await bot.session.close()
    logger.info("👋 Сессия бота закрыта")

@contextlib.asynccontextmanager
async def lifespan():
    """
    Контекстный менеджер для управления жизненным циклом приложения
    """
    logger.info("🔗 Инициализация ресурсов...")
    
    # Запускаем веб-сервер
    web_runner = await start_web_server()
    
    # Запускаем фоновые задачи
    cleanup_task = asyncio.create_task(cleanup_old_sessions())
    ping_task = asyncio.create_task(self_ping_periodically())
    
    logger.info("✅ Фоновые задачи запущены")
    
    try:
        yield
    finally:
        logger.info("🧹 Очистка ресурсов...")
        
        # Останавливаем фоновые задачи
        cleanup_task.cancel()
        ping_task.cancel()
        
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
            
        try:
            await ping_task
        except asyncio.CancelledError:
            pass
        
        # Останавливаем веб-сервер
        await web_runner.cleanup()
        logger.info("✅ Веб-сервер остановлен")
        
        logger.info("✅ Все ресурсы освобождены")

# --- ГЛАВНАЯ ФУНКЦИЯ ---
async def main():
    """Основная функция запуска приложения"""
    logger.info("🚀 Запуск Gemini Telegram Bot...")
    logger.info(f"📊 Уровень логирования: {LOG_LEVEL}")
    logger.info(f"👑 Администраторы: {ADMIN_IDS}")
    
    async with lifespan():
        # Регистрируем обработчики событий жизненного цикла
        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)
        
        # Удаляем вебхук (используем polling)
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            logger.info("✅ Webhook сброшен, используется polling")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка сброса webhook: {e}")
        
        # Запускаем polling
        logger.info("⏳ Запуск polling...")
        try:
            await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        except Exception as e:
            logger.critical(f"💀 Критическая ошибка polling: {e}", exc_info=True)
            raise

if __name__ == "__main__":
    try:
        # Запускаем бота
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем (Ctrl+C)")
    except Exception as e:
        logger.critical(f"💀 Критическая ошибка при запуске: {e}", exc_info=True)
        sys.exit(1)