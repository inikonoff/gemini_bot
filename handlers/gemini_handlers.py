import os
import logging
from typing import Optional
from io import BytesIO

from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.enums import ParseMode
import google.generativeai as genai
from PIL import Image
import requests

from config import GEMINI_API_KEY, MAX_HISTORY_MESSAGES
from main import user_sessions, UserSession

# Настройка Gemini API
genai.configure(api_key=GEMINI_API_KEY)

# Доступные модели Gemini
GEMINI_MODELS = {
    'gemini-1.5-flash': {
        'name': 'Gemini 1.5 Flash',
        'model_id': 'gemini-1.5-flash',
        'description': '⚡ Быстрая модель для чата и анализа изображений',
        'supports_vision': True,
        'max_tokens': 8192
    },
    'gemini-1.5-pro': {
        'name': 'Gemini 1.5 Pro',
        'model_id': 'gemini-1.5-pro',
        'description': '🎯 Продвинутая модель для сложных задач',
        'supports_vision': True,
        'max_tokens': 8192
    },
    'imagen-3': {
        'name': 'Imagen 3',
        'model_id': 'imagen-3',
        'description': '🎨 Генерация изображений по описанию',
        'supports_vision': False,
        'supports_image_gen': True,
        'max_tokens': 2048
    }
}

# Создаем роутер
router = Router()
logger = logging.getLogger(__name__)

# ========== КОМАНДЫ БОТА ==========

@router.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    
    # Создаем новую сессию если ее нет
    if user_id not in user_sessions:
        user_sessions[user_id] = UserSession(user_id)
    
    session = user_sessions[user_id]
    
    welcome_text = (
        "🤖 *Добро пожаловать в Gemini Bot!*\n\n"
        "✨ *Что я умею:*\n"
        "• 💬 Умный чат с поддержкой контекста\n"
        "• 💻 Генерация и анализ кода\n"
        "• 🖼️ Анализ загруженных изображений\n"
        "• 🎨 Создание картинок по описанию\n\n"
        "📋 *Доступные команды:*\n"
        "/start - Главное меню\n"
        "/models - Выбрать модель AI\n"
        "/clear - Очистить историю\n"
        "/help - Справка\n"
        "/stats - Ваша статистика\n\n"
        "🚀 *Просто отправьте мне текст или фото!*\n"
        f"⚙️ Текущая модель: *{GEMINI_MODELS[session.current_model]['name']}*"
    )
    
    await message.answer(welcome_text, parse_mode=ParseMode.MARKDOWN)

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    help_text = (
        "📖 *Руководство по использованию*\n\n"
        "🔹 *Основные возможности:*\n"
        "1. *Текстовый чат* - просто напишите мне\n"
        "2. *Анализ изображений* - отправьте фото\n"
        "3. *Генерация кода* - попросите написать программу\n"
        "4. *Создание изображений* - выберите Imagen 3\n\n"
        
        "🔹 *Примеры запросов:*\n"
        "• `Напиши код калькулятора на Python`\n"
        "• `Объясни квантовую физику простыми словами`\n"
        "• `Что на этом изображении?` (отправь фото)\n"
        "• `Создай изображение космического корабля`\n\n"
        
        "🔹 *Советы:*\n"
        "• Используйте /models для смены модели\n"
        "• /clear - если ответы стали некорректными\n"
        "• Изображения лучше анализирует Gemini Pro\n"
        "• Для генерации картинок нужна Imagen 3\n\n"
        
        "🆘 *Проблемы?*\n"
        "Если бот не отвечает:\n"
        "1. Проверьте выбранную модель (/models)\n"
        "2. Очистите историю (/clear)\n"
        "3. Переформулируйте запрос"
    )
    
    await message.answer(help_text, parse_mode=ParseMode.MARKDOWN)

@router.message(Command("models"))
async def cmd_models(message: Message):
    """Обработчик команды /models - выбор модели"""
    user_id = message.from_user.id
    
    # Получаем или создаем сессию
    if user_id not in user_sessions:
        user_sessions[user_id] = UserSession(user_id)
    
    session = user_sessions[user_id]
    
    # Создаем клавиатуру с моделями
    keyboard = []
    
    for model_id, model in GEMINI_MODELS.items():
        # Помечаем текущую модель галочкой
        is_current = "✅ " if model_id == session.current_model else ""
        button_text = f"{is_current}{model['name']}"
        
        keyboard.append([
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"model_{model_id}"
            )
        ])
    
    # Кнопка для возврата
    keyboard.append([
        InlineKeyboardButton(
            text="🔙 Назад",
            callback_data="model_back"
        )
    ])
    
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    model_info = (
        "🤖 *Выберите модель AI:*\n\n"
        "• *Gemini 1.5 Flash* - ⚡ Быстрая, для повседневных задач\n"
        "• *Gemini 1.5 Pro* - 🎯 Для сложных запросов и анализа\n"
        "• *Imagen 3* - 🎨 Только генерация изображений\n\n"
        f"📊 Текущая: *{GEMINI_MODELS[session.current_model]['name']}*"
    )
    
    await message.answer(
        model_info,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

@router.callback_query(F.data.startswith("model_"))
async def model_callback(callback: CallbackQuery):
    """Обработчик выбора модели"""
    model_id = callback.data.replace("model_", "")
    user_id = callback.from_user.id
    
    if model_id == "back":
        # Возвращаемся в главное меню
        await callback.message.delete()
        await cmd_start(callback.message)
        await callback.answer()
        return
    
    # Проверяем существование модели
    if model_id not in GEMINI_MODELS:
        await callback.answer("❌ Неизвестная модель", show_alert=True)
        return
    
    # Обновляем сессию
    if user_id not in user_sessions:
        user_sessions[user_id] = UserSession(user_id)
    
    session = user_sessions[user_id]
    session.current_model = model_id
    
    model = GEMINI_MODELS[model_id]
    
    # Редактируем сообщение
    await callback.message.edit_text(
        f"✅ *Модель изменена!*\n\n"
        f"🤖 *{model['name']}*\n"
        f"📝 {model['description']}\n\n"
        f"⚙️ Макс. токенов: {model['max_tokens']}\n"
        f"👁️ Анализ изображений: {'✅' if model['supports_vision'] else '❌'}\n"
        f"🎨 Генерация изображений: {'✅' if model.get('supports_image_gen', False) else '❌'}",
        parse_mode=ParseMode.MARKDOWN
    )
    
    await callback.answer(f"Установлена модель: {model['name']}")

@router.message(Command("clear"))
async def cmd_clear(message: Message):
    """Обработчик команды /clear - очистка истории"""
    user_id = message.from_user.id
    
    if user_id in user_sessions:
        old_count = len(user_sessions[user_id].history)
        user_sessions[user_id].history = []
        
        if old_count > 0:
            await message.answer(
                f"🧹 *История очищена!*\n\n"
                f"Удалено *{old_count}* сообщений из памяти.",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await message.answer(
                "ℹ️ *История уже пуста*\n\n"
                "Нет сообщений для очистки.",
                parse_mode=ParseMode.MARKDOWN
            )
    else:
        await message.answer(
            "ℹ️ *История отсутствует*\n\n"
            "Вы еще не начинали диалог.",
            parse_mode=ParseMode.MARKDOWN
        )

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Обработчик команды /stats - статистика"""
    user_id = message.from_user.id
    session = user_sessions.get(user_id)
    
    if not session:
        stats_text = (
            "📊 *Статистика*\n\n"
            "Вы еще не начали диалог.\n"
            "Отправьте любое сообщение чтобы создать сессию!"
        )
    else:
        model_name = GEMINI_MODELS[session.current_model]['name']
        
        stats_text = (
            f"📊 *Ваша статистика*\n\n"
            f"• 🤖 Текущая модель: *{model_name}*\n"
            f"• 💬 Сообщений в истории: *{len(session.history)}/{MAX_HISTORY_MESSAGES}*\n"
            f"• 📈 Всего сообщений: *{session.message_count}*\n"
            f"• 🕐 Сессия создана: *{session.created_at.strftime('%d.%m.%Y %H:%M')}*\n"
            f"• ⏰ Последняя активность: *{session.last_activity.strftime('%d.%m.%Y %H:%M')}*"
        )
    
    await message.answer(stats_text, parse_mode=ParseMode.MARKDOWN)

# ========== ОБРАБОТКА ТЕКСТОВЫХ СООБЩЕНИЙ ==========

@router.message(F.text & ~F.command)
async def handle_text(message: Message):
    """Обработка обычных текстовых сообщений"""
    user_id = message.from_user.id
    user_message = message.text
    
    # Создаем или обновляем сессию
    if user_id not in user_sessions:
        user_sessions[user_id] = UserSession(user_id)
    
    session = user_sessions[user_id]
    session.message_count += 1
    session.last_activity = datetime.now()
    
    # Проверяем длину истории и обрезаем если нужно
    if len(session.history) > MAX_HISTORY_MESSAGES:
        # Оставляем последние N сообщений
        keep_messages = MAX_HISTORY_MESSAGES // 2
        session.history = session.history[-keep_messages:]
        logger.info(f"История пользователя {user_id} обрезана до {keep_messages} сообщений")
    
    # Показываем статус "печатает"
    await message.chat.do("typing")
    
    try:
        # Если выбрана Imagen 3 - генерируем изображение
        if session.current_model == 'imagen-3':
            await generate_image(message, user_message)
            return
        
        # Добавляем сообщение пользователя в историю
        session.history.append({"role": "user", "parts": [user_message]})
        
        # Получаем выбранную модель
        model_config = GEMINI_MODELS[session.current_model]
        model = genai.GenerativeModel(model_config['model_id'])
        
        # Генерируем ответ с учетом истории
        if len(session.history) > 1:
            # Используем историю диалога
            chat = model.start_chat(history=session.history[:-1])
            response = await asyncio.to_thread(
                chat.send_message,
                user_message
            )
        else:
            # Первое сообщение в диалоге
            response = await asyncio.to_thread(
                model.generate_content,
                user_message
            )
        
        # Извлекаем текст ответа
        response_text = response.text
        
        # Добавляем ответ в историю
        session.history.append({"role": "model", "parts": [response_text]})
        
        # Отправляем ответ пользователю
        await message.answer(response_text, parse_mode=ParseMode.MARKDOWN)
        
    except Exception as e:
        logger.error(f"Ошибка при обработке текста от пользователя {user_id}: {e}", exc_info=True)
        
        # Удаляем последнее сообщение из истории (оно не удалось)
        if session.history and session.history[-1]["role"] == "user":
            session.history.pop()
        
        error_message = (
            "❌ *Произошла ошибка*\n\n"
            "Не удалось обработать ваш запрос.\n\n"
            "Возможные причины:\n"
            "• 🔄 Проблемы с API Google Gemini\n"
            "• ⏱️ Превышен таймаут запроса\n"
            "• 🚫 Запрос содержит ограниченный контент\n\n"
            "Попробуйте:\n"
            "1. Переформулировать запрос\n"
            "2. Использовать /clear\n"
            "3. Сменить модель через /models"
        )
        
        await message.answer(error_message, parse_mode=ParseMode.MARKDOWN)

# ========== ОБРАБОТКА ИЗОБРАЖЕНИЙ ==========

@router.message(F.photo)
async def handle_image(message: Message):
    """Обработка загруженных изображений"""
    user_id = message.from_user.id
    
    # Создаем или обновляем сессию
    if user_id not in user_sessions:
        user_sessions[user_id] = UserSession(user_id)
    
    session = user_sessions[user_id]
    session.message_count += 1
    session.last_activity = datetime.now()
    
    # Проверяем поддержку анализа изображений
    model_config = GEMINI_MODELS[session.current_model]
    if not model_config['supports_vision']:
        await message.answer(
            "❌ *Эта модель не поддерживает анализ изображений*\n\n"
            f"Текущая модель: *{model_config['name']}*\n\n"
            "Используйте /models чтобы переключиться на:\n"
            "• Gemini 1.5 Flash\n"
            "• Gemini 1.5 Pro",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Показываем статус загрузки
    await message.chat.do("upload_photo")
    
    try:
        # Скачиваем изображение
        photo = await message.photo[-1].get_file()
        img_bytes = await photo.download_as_bytearray()
        
        # Открываем изображение
        image = Image.open(BytesIO(img_bytes))
        
        # Получаем подпись или используем стандартный промпт
        prompt = message.caption or "Опиши это изображение подробно. Что на нем изображено?"
        
        # Добавляем в историю
        session.history.append({"role": "user", "parts": [f"[Изображение] {prompt}"]})
        
        # Создаем модель и генерируем ответ
        model = genai.GenerativeModel(model_config['model_id'])
        response = await asyncio.to_thread(
            model.generate_content,
            [prompt, image]
        )
        
        response_text = response.text
        
        # Добавляем ответ в историю
        session.history.append({"role": "model", "parts": [response_text]})
        
        # Отправляем ответ
        await message.answer(response_text, parse_mode=ParseMode.MARKDOWN)
        
    except Exception as e:
        logger.error(f"Ошибка при обработке изображения от пользователя {user_id}: {e}", exc_info=True)
        
        # Удаляем сообщение из истории
        if session.history and session.history[-1]["role"] == "user":
            session.history.pop()
        
        await message.answer(
            "❌ *Не удалось проанализировать изображение*\n\n"
            "Попробуйте:\n"
            "• Отправить изображение меньшего размера\n"
            "• Добавить более четкое описание\n"
            "• Проверить подключение к интернету",
            parse_mode=ParseMode.MARKDOWN
        )

# ========== ГЕНЕРАЦИЯ ИЗОБРАЖЕНИЙ ==========

async def generate_image(message: Message, prompt: str):
    """Генерация изображения через Imagen 3"""
    user_id = message.from_user.id
    session = user_sessions.get(user_id)
    
    if not session:
        session = UserSession(user_id)
        user_sessions[user_id] = session
    
    session.message_count += 1
    session.last_activity = datetime.now()
    
    # Показываем статус
    await message.chat.do("upload_photo")
    
    try:
        # Проверяем длину промпта
        if len(prompt) > 500:
            await message.answer(
                "⚠️ *Слишком длинный запрос*\n\n"
                "Пожалуйста, сократите описание до 500 символов.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Добавляем запрос в историю
        session.history.append({"role": "user", "parts": [f"[Генерация изображения] {prompt}"]})
        
        # Создаем модель Imagen 3
        imagen_model = genai.GenerativeModel('imagen-3')
        
        # Генерируем изображение
        response = await asyncio.to_thread(
            imagen_model.generate_images,
            prompt=prompt,
            number_of_images=1,
            language="ru"
        )
        
        # Проверяем наличие изображений
        if not response.images:
            raise ValueError("API не вернул изображение")
        
        # Получаем URL изображения
        image_url = response.images[0]._image_url
        
        # Скачиваем изображение
        img_response = requests.get(image_url, timeout=30)
        img_response.raise_for_status()
        
        img_data = BytesIO(img_response.content)
        
        # Добавляем информацию в историю
        session.history.append({"role": "model", "parts": ["[Изображение сгенерировано]"]})
        
        # Отправляем изображение пользователю
        await message.answer_photo(
            photo=img_data,
            caption=f"🎨 *Сгенерировано по запросу:*\n{prompt}",
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Ошибка генерации изображения для пользователя {user_id}: {e}", exc_info=True)
        
        # Удаляем запрос из истории
        if session.history and session.history[-1]["role"] == "user":
            session.history.pop()
        
        error_msg = (
            "❌ *Не удалось сгенерировать изображение*\n\n"
            "Возможные причины:\n"
            "• 🚫 Запрос содержит ограниченный контент\n"
            "• ⏱️ Превышено время ожидания\n"
            "• 🔧 Временные проблемы с API Google\n\n"
            "Попробуйте:\n"
            "• Изменить описание\n"
            "• Сделать запрос более конкретным\n"
            "• Попробовать позже"
        )
        
        await message.answer(error_msg, parse_mode=ParseMode.MARKDOWN)

# ========== РЕГИСТРАЦИЯ ХЭНДЛЕРОВ ==========

def register_gemini_handlers(dp: Dispatcher):
    """Функция для регистрации всех хэндлеров Gemini"""
    dp.include_router(router)
    logger.info("✅ Хэндлеры Gemini зарегистрированы")
