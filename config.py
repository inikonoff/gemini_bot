import os
import logging
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# === НАСТРОЙКИ БОТА ===

# Токен Telegram бота (получить у @BotFather)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TELEGRAM_TOKEN:
    raise ValueError("""
❌ КРИТИЧЕСКАЯ ОШИБКА: TELEGRAM_TOKEN не найден!
Добавьте в .env файл или переменные окружения:
TELEGRAM_TOKEN=ваш_токен_бота
""")

# API ключ для Google Gemini (получить на https://makersuite.google.com/app/apikey)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("""
❌ КРИТИЧЕСКАЯ ОШИБКА: GEMINI_API_KEY не найден!
Добавьте в .env файл или переменные окружения:
GEMINI_API_KEY=ваш_gemini_api_ключ
""")

# === АДМИНИСТРАТОРЫ ===
# ID администраторов через запятую (можно узнать через @userinfobot)
ADMIN_IDS_STR = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = []

if ADMIN_IDS_STR:
    try:
        # Преобразуем строку "123,456,789" в список [123, 456, 789]
        ADMIN_IDS = [int(id_str.strip()) for id_str in ADMIN_IDS_STR.split(",") if id_str.strip()]
        logging.info(f"👑 Загружено ID администраторов: {ADMIN_IDS}")
    except ValueError as e:
        print(f"⚠️ Внимание: ADMIN_IDS должен содержать числа через запятую. Ошибка: {e}")
        ADMIN_IDS = []
else:
    print("ℹ️ ADMIN_IDS не указан. Уведомления администраторам отправляться не будут.")

# === НАСТРОЙКИ ЛОГГИРОВАНИЯ ===
# Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Проверяем корректность уровня логирования
VALID_LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
if LOG_LEVEL not in VALID_LOG_LEVELS:
    print(f"⚠️ Неверный LOG_LEVEL '{LOG_LEVEL}'. Используется 'INFO' по умолчанию.")
    LOG_LEVEL = "INFO"

# Файл для логов
LOG_FILE = os.getenv("LOG_FILE", "logs/bot.log")

# === ДОПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ ===
# Максимальное количество сообщений в истории (чтобы не переполнять память)
MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", "50"))

# Таймаут для запросов к Gemini (в секундах)
GEMINI_TIMEOUT = int(os.getenv("GEMINI_TIMEOUT", "30"))

# Время жизни сессии пользователя в памяти (в часах)
SESSION_LIFETIME_HOURS = int(os.getenv("SESSION_LIFETIME_HOURS", "24"))

def validate_config():
    """
    Проверяет корректность конфигурации.
    Вызывает исключение если обнаружены критические ошибки.
    """
    errors = []
    
    # Проверка обязательных переменных
    if not TELEGRAM_TOKEN:
        errors.append("TELEGRAM_TOKEN не установлен")
    
    if not GEMINI_API_KEY:
        errors.append("GEMINI_API_KEY не установлен")
    
    # Проверка формата ADMIN_IDS
    if ADMIN_IDS_STR and not ADMIN_IDS:
        errors.append(f"ADMIN_IDS содержит некорректные значения: '{ADMIN_IDS_STR}'")
    
    # Проверка числовых значений
    if MAX_HISTORY_MESSAGES <= 0:
        errors.append(f"MAX_HISTORY_MESSAGES должен быть > 0, получено: {MAX_HISTORY_MESSAGES}")
    
    if GEMINI_TIMEOUT <= 0:
        errors.append(f"GEMINI_TIMEOUT должен быть > 0, получено: {GEMINI_TIMEOUT}")
    
    if SESSION_LIFETIME_HOURS <= 0:
        errors.append(f"SESSION_LIFETIME_HOURS должен быть > 0, получено: {SESSION_LIFETIME_HOURS}")
    
    # Если есть ошибки - выбрасываем исключение
    if errors:
        error_msg = "\n".join([f"  • {error}" for error in errors])
        raise ValueError(f"Ошибки конфигурации:\n{error_msg}")
    
    # Логируем успешную проверку
    print("✅ Конфигурация успешно проверена")
    print(f"   🤖 Режим: {'Production' if LOG_LEVEL != 'DEBUG' else 'Debug'}")
    print(f"   📊 Логирование: {LOG_LEVEL} -> {LOG_FILE}")
    print(f"   👑 Администраторов: {len(ADMIN_IDS)}")
    print(f"   💾 Макс. история: {MAX_HISTORY_MESSAGES} сообщений")
    print(f"   ⏱️ Таймаут Gemini: {GEMINI_TIMEOUT} сек")
    print(f"   🕐 Время жизни сессии: {SESSION_LIFETIME_HOURS} ч")

# Автоматическая проверка при импорте
if __name__ != "__main__":
    try:
        validate_config()
    except ValueError as e:
        print(f"❌ Ошибка при загрузке конфигурации: {e}")
        raise