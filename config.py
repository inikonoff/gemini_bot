import os
import logging
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# === ТОКЕНЫ И КЛЮЧИ ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN не найден в .env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("❌ GEMINI_API_KEY не найден в .env")

# === АДМИНИСТРАТОРЫ ===
ADMIN_IDS_STR = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = []
if ADMIN_IDS_STR:
    try:
        ADMIN_IDS = [int(id.strip()) for id in ADMIN_IDS_STR.split(",") if id.strip()]
    except ValueError:
        print("⚠️ ADMIN_IDS должен содержать числа через запятую")

# === НАСТРОЙКИ ЛОГГИРОВАНИЯ ===
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
VALID_LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
if LOG_LEVEL not in VALID_LOG_LEVELS:
    LOG_LEVEL = "INFO"

LOG_FILE = os.getenv("LOG_FILE", "logs/bot.log")

# === НАСТРОЙКИ БОТА ===
MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", "30"))
GEMINI_TIMEOUT = int(os.getenv("GEMINI_TIMEOUT", "60"))
SESSION_LIFETIME_HOURS = int(os.getenv("SESSION_LIFETIME_HOURS", "24"))

# Модель по умолчанию
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gemini-1.5-flash")

def validate_config():
    """Проверка конфигурации"""
    errors = []
    
    if not TELEGRAM_TOKEN:
        errors.append("TELEGRAM_TOKEN не установлен")
    
    if not GEMINI_API_KEY:
        errors.append("GEMINI_API_KEY не установлен")
    
    if errors:
        error_msg = "\n".join([f"  • {error}" for error in errors])
        raise ValueError(f"Ошибки конфигурации:\n{error_msg}")
    
    print("✅ Конфигурация успешно проверена")
    print(f"   🤖 Режим: {'Production' if LOG_LEVEL != 'DEBUG' else 'Debug'}")
    print(f"   📊 Логирование: {LOG_LEVEL} -> {LOG_FILE}")
    print(f"   👑 Администраторов: {len(ADMIN_IDS)}")
    print(f"   🧠 Модель по умолчанию: {DEFAULT_MODEL}")

# Автопроверка
if __name__ != "__main__":
    try:
        validate_config()
    except ValueError as e:
        print(f"❌ Ошибка конфигурации: {e}")
        raise