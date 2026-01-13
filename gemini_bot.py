import os
import logging
from typing import Optional, Dict, List
from dataclasses import dataclass
from io import BytesIO

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from telegram.constants import ParseMode
import google.generativeai as genai
from PIL import Image
import requests
from dotenv import load_dotenv
# ... (ваши импорты)
from config import MAX_HISTORY_MESSAGES, GEMINI_TIMEOUT
# ИСПРАВЛЕННЫЙ ИМПОРТ:
from utils.session_manager import user_sessions, UserSession 

router = Router()
# ... (далее ваш код без изменений)

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация Gemini
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

# Доступные модели Gemini
@dataclass
class GeminiModel:
    name: str
    model_id: str
    description: str
    supports_vision: bool
    supports_image_gen: bool = False

# Список доступных моделей
AVAILABLE_MODELS = {
    'gemini-1.5-flash': GeminiModel(
        name='Gemini 1.5 Flash',
        model_id='gemini-1.5-flash',
        description='Быстрая модель для чата и анализа изображений',
        supports_vision=True
    ),
    'gemini-1.5-pro': GeminiModel(
        name='Gemini 1.5 Pro',
        model_id='gemini-1.5-pro',
        description='Продвинутая модель для сложных задач',
        supports_vision=True
    ),
    'gemini-1.5-flash-8b': GeminiModel(
        name='Gemini 1.5 Flash 8B',
        model_id='gemini-1.5-flash-8b',
        description='Компактная модель для быстрых ответов',
        supports_vision=True
    ),
    'imagen-3': GeminiModel(
        name='Imagen 3 (Генерация)',
        model_id='imagen-3',
        description='Генерация изображений по описанию',
        supports_vision=False,
        supports_image_gen=True
    )
}

# Класс для управления историей диалога
class ChatSession:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.history: List[Dict] = []
        self.current_model: str = 'gemini-1.5-flash'
        self.image_generation_model = genai.GenerativeModel('imagen-3')
        
    def add_message(self, role: str, content: str, image_parts: Optional[List] = None):
        message = {"role": role, "parts": [content]}
        if image_parts:
            message["parts"].extend(image_parts)
        self.history.append(message)
        
        # Ограничиваем историю последними 20 сообщениями
        if len(self.history) > 20:
            self.history = self.history[-20:]
    
    def clear_history(self):
        self.history = []
    
    def get_gemini_model(self):
        model_config = AVAILABLE_MODELS[self.current_model]
        return genai.GenerativeModel(model_config.model_id)

# Хранилище сессий пользователей
user_sessions: Dict[int, ChatSession] = {}

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Создаем или получаем сессию пользователя
    if user_id not in user_sessions:
        user_sessions[user_id] = ChatSession(user_id)
    
    welcome_text = (
        "🤖 *Добро пожаловать в Gemini Bot!*\n\n"
        "Я поддерживаю:\n"
        "💬 Обычный чат\n"
        "💻 Генерацию и анализ кода\n"
        "🖼️ Анализ загруженных изображений\n"
        "🎨 Генерацию изображений по описанию\n\n"
        "*Доступные команды:*\n"
        "/start - Начать диалог\n"
        "/models - Выбрать модель Gemini\n"
        "/clear - Очистить историю диалога\n"
        "/help - Справка по использованию\n\n"
        "Просто отправьте текст или изображение!"
    )
    
    await update.message.reply_text(
        welcome_text,
        parse_mode=ParseMode.MARKDOWN
    )

# Команда /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 *Как использовать бота:*\n\n"
        "1. *Чат*: Просто отправьте текстовое сообщение\n"
        "2. *Анализ изображений*: Отправьте фото с подписью или без\n"
        "3. *Генерация кода*: Попросите написать код на любом языке\n"
        "4. *Генерация изображений*: Используйте Imagen 3 модель\n\n"
        "*Примеры запросов:*\n"
        "• \"Напиши код на Python для парсинга сайта\"\n"
        "• \"Что на этом изображении?\" (с фото)\n"
        "• \"Создай изображение космического корабля\"\n\n"
        "Используйте /models для выбора модели"
    )
    
    await update.message.reply_text(
        help_text,
        parse_mode=ParseMode.MARKDOWN
    )

# Команда /models - выбор модели
async def show_models(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = user_sessions.get(user_id, ChatSession(user_id))
    
    keyboard = []
    
    for model_id, model in AVAILABLE_MODELS.items():
        is_current = "✅ " if model_id == session.current_model else ""
        button_text = f"{is_current}{model.name}"
        
        keyboard.append([
            InlineKeyboardButton(
                button_text,
                callback_data=f"model_{model_id}"
            )
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🤖 *Выберите модель Gemini:*\n\n"
        "• *Gemini Flash* - Быстрая, для повседневных задач\n"
        "• *Gemini Pro* - Продвинутая, для сложных запросов\n"
        "• *Imagen 3* - Только для генерации изображений",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

# Обработчик выбора модели
async def model_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    model_id = query.data.replace("model_", "")
    
    if user_id not in user_sessions:
        user_sessions[user_id] = ChatSession(user_id)
    
    session = user_sessions[user_id]
    session.current_model = model_id
    
    model = AVAILABLE_MODELS[model_id]
    
    await query.edit_message_text(
        f"✅ Модель изменена на: *{model.name}*\n\n"
        f"*Описание:* {model.description}",
        parse_mode=ParseMode.MARKDOWN
    )

# Команда /clear - очистка истории
async def clear_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id in user_sessions:
        user_sessions[user_id].clear_history()
    
    await update.message.reply_text(
        "🧹 История диалога очищена!",
        parse_mode=ParseMode.MARKDOWN
    )

# Обработка текстовых сообщений
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Получаем или создаем сессию
    if user_id not in user_sessions:
        user_sessions[user_id] = ChatSession(user_id)
    
    session = user_sessions[user_id]
    user_message = update.message.text
    
    # Проверяем, не является ли это запросом на генерацию изображения
    if session.current_model == 'imagen-3':
        await generate_image(update, context, user_message)
        return
    
    # Показываем статус "печатает"
    await update.message.chat.send_action(action="typing")
    
    try:
        # Добавляем сообщение пользователя в историю
        session.add_message("user", user_message)
        
        # Получаем модель
        model = session.get_gemini_model()
        
        # Генерируем контент на основе истории
        chat = model.start_chat(history=session.history[:-1])
        response = chat.send_message(user_message)
        
        # Добавляем ответ в историю
        session.add_message("model", response.text)
        
        # Отправляем ответ
        await update.message.reply_text(
            response.text,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Ошибка при обработке текста: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при обработке запроса. Попробуйте еще раз."
        )

# Обработка изображений
async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in user_sessions:
        user_sessions[user_id] = ChatSession(user_id)
    
    session = user_sessions[user_id]
    
    # Получаем изображение
    photo_file = await update.message.photo[-1].get_file()
    photo_bytes = await photo_file.download_as_bytearray()
    
    # Показываем статус
    await update.message.chat.send_action(action="upload_photo")
    
    try:
        # Создаем объект изображения для Gemini
        image = Image.open(BytesIO(photo_bytes))
        
        # Подготавливаем промпт
        prompt = update.message.caption or "Опиши это изображение"
        
        # Получаем модель
        model = session.get_gemini_model()
        
        # Генерируем ответ
        response = model.generate_content([prompt, image])
        
        # Отправляем ответ
        await update.message.reply_text(
            response.text,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Ошибка при обработке изображения: {e}")
        await update.message.reply_text(
            "❌ Не удалось обработать изображение. Проверьте, что вы используете модель с поддержкой Vision."
        )

# Генерация изображений через Imagen 3
async def generate_image(update: Update, context: ContextTypes.DEFAULT_TYPE, prompt: str = None):
    if not prompt:
        prompt = update.message.text
    
    # Показываем статус
    await update.message.chat.send_action(action="upload_photo")
    
    try:
        # Генерируем изображение
        response = user_sessions[update.effective_user.id].image_generation_model.generate_images(
            prompt=prompt,
            number_of_images=1,
            language="ru"
        )
        
        # Получаем URL изображения
        image_url = response.images[0]._image_url
        
        # Загружаем изображение
        img_response = requests.get(image_url)
        img_data = BytesIO(img_response.content)
        
        # Отправляем изображение
        await update.message.reply_photo(
            photo=img_data,
            caption=f"🖼️ Сгенерировано по запросу: *{prompt}*",
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Ошибка при генерации изображения: {e}")
        await update.message.reply_text(
            "❌ Не удалось сгенерировать изображение. Возможно, промпт содержит ограниченный контент."
        )

# Основная функция
def main():
    # Создаем Application
    application = Application.builder().token(os.getenv('TELEGRAM_TOKEN')).build()
    
    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("models", show_models))
    application.add_handler(CommandHandler("clear", clear_history))
    
    # Регистрируем обработчик выбора модели
    application.add_handler(CallbackQueryHandler(model_callback, pattern="^model_"))
    
    # Регистрируем обработчики сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.PHOTO, handle_image))
    
    # Запускаем бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
