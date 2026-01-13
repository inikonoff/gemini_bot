import os
import logging
from datetime import datetime
from io import BytesIO
from typing import Optional

from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.enums import ParseMode
import google.generativeai as genai
from PIL import Image
import requests

from config import MAX_HISTORY_MESSAGES, GEMINI_TIMEOUT
from main import user_sessions, UserSession

router = Router()
logger = logging.getLogger(__name__)

# --- ДОСТУПНЫЕ МОДЕЛИ GEMINI ---
GEMINI_MODELS = {
    'gemini-1.5-flash': {
        'name': 'Gemini 1.5 Flash',
        'model_id': 'gemini-1.5-flash',
        'description': '⚡ Быстрая и умная модель для любых задач',
        'supports_vision': True,
        'supports_image_gen': False,
        'max_tokens': 8192,
        'category': 'text'
    },
    'gemini-1.5-pro': {
        'name': 'Gemini 1.5 Pro',
        'model_id': 'gemini-1.5-pro',
        'description': '🎯 Продвинутая модель для сложных запросов',
        'supports_vision': True,
        'supports_image_gen': False,
        'max_tokens': 8192,
        'category': 'text'
    },
    'gemini-2.0-flash-exp': {
        'name': 'Gemini 2.0 Flash',
        'model_id': 'gemini-2.0-flash-exp',
        'description': '🚀 Экспериментальная модель 2.0',
        'supports_vision': True,
        'supports_image_gen': False,
        'max_tokens': 8192,
        'category': 'text'
    },
    'gemini-3.0-flash': {
        'name': 'Gemini 3.0 Flash',
        'model_id': 'gemini-3.0-flash',
        'description': '🌟 Самая новая и мощная модель',
        'supports_vision': True,
        'supports_image_gen': False,
        'max_tokens': 8192,
        'category': 'text'
    },
    'imagen-3': {
        'name': 'Imagen 3',
        'model_id': 'imagen-3',
        'description': '🎨 Генерация изображений по описанию',
        'supports_vision': False,
        'supports_image_gen': True,
        'max_tokens': 2048,
        'category': 'image'
    }
}

# --- КОМАНДЫ ---
@router.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    
    if user_id not in user_sessions:
        user_sessions[user_id] = UserSession(user_id)
    
    session = user_sessions[user_id]
    model_name = GEMINI_MODELS[session.current_model]['name']
    
    welcome_text = (
        f"🤖 *Gemini Bot v2.0*\n\n"
        f"Текущая модель: *{model_name}*\n\n"
        "✨ *Возможности:*\n"
        "• 💬 Умный чат с контекстом\n"
        "• 🖼️ Анализ изображений\n"
        "• 💻 Генерация кода\n"
        "• 🎨 Создание картинок\n\n"
        "📋 *Команды:*\n"
        "/models - Выбрать модель\n"
        "/clear - Очистить историю\n"
        "/image - Создать картинку\n"
        "/help - Справка\n\n"
        "*Просто отправьте сообщение или фото!*"
    )
    
    await message.answer(welcome_text, parse_mode=ParseMode.MARKDOWN)

@router.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        "📖 *Помощь*\n\n"
        "*Как использовать:*\n"
        "1. Напишите любой вопрос\n"
        "2. Отправьте фото для анализа\n"
        "3. Используйте /image для генерации картинок\n\n"
        "*Советы:*\n"
        "• Используйте /models для смены модели\n"
        "• Gemini 3.0 Flash - самая новая и мощная\n"
        "• Imagen 3 - только для генерации изображений\n"
        "• /clear если ответы стали странными\n\n"
        "*Примеры запросов:*\n"
        "• `Объясни теорию относительности`\n"
        "• `Напиши код сайта на Python`\n"
        "• `Что на этом фото?` (отправьте фото)\n"
        "• `/image космический корабль в туманности`"
    )
    
    await message.answer(help_text, parse_mode=ParseMode.MARKDOWN)

@router.message(Command("models"))
async def cmd_models(message: Message):
    user_id = message.from_user.id
    
    if user_id not in user_sessions:
        user_sessions[user_id] = UserSession(user_id)
    
    session = user_sessions[user_id]
    
    # Создаем клавиатуру с категориями
    keyboard = []
    
    # Текстовые модели
    keyboard.append([InlineKeyboardButton(
        text="💬 Текстовые модели",
        callback_data="category_text"
    )])
    
    # Изображения
    keyboard.append([InlineKeyboardButton(
        text="🎨 Генерация изображений",
        callback_data="category_image"
    )])
    
    # Текущая модель
    current_model = GEMINI_MODELS[session.current_model]
    current_text = f"📊 Текущая: {current_model['name']}"
    
    await message.answer(
        f"🤖 *Выбор модели*\n\n{current_text}\n\nВыберите категорию:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

@router.callback_query(F.data == "category_text")
async def category_text(callback: CallbackQuery):
    """Показать текстовые модели"""
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, UserSession(user_id))
    
    keyboard = []
    
    # Фильтруем текстовые модели
    text_models = {k: v for k, v in GEMINI_MODELS.items() if v['category'] == 'text'}
    
    for model_id, model in text_models.items():
        is_current = "✅ " if model_id == session.current_model else ""
        button_text = f"{is_current}{model['name']}"
        
        keyboard.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"model_{model_id}"
        )])
    
    # Кнопка назад
    keyboard.append([InlineKeyboardButton(
        text="🔙 Назад",
        callback_data="models_back"
    )])
    
    await callback.message.edit_text(
        "💬 *Текстовые модели:*\n\n"
        "• Gemini 1.5 Flash - ⚡ Баланс скорости и качества\n"
        "• Gemini 1.5 Pro - 🎯 Для сложных задач\n"
        "• Gemini 3.0 Flash - 🚀 Самая новая и мощная",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode=ParseMode.MARKDOWN
    )
    await callback.answer()

@router.callback_query(F.data == "category_image")
async def category_image(callback: CallbackQuery):
    """Показать модели для генерации изображений"""
    keyboard = []
    
    # Только Imagen 3
    model = GEMINI_MODELS['imagen-3']
    keyboard.append([InlineKeyboardButton(
        text=f"🎨 {model['name']}",
        callback_data="model_imagen-3"
    )])
    
    # Кнопка назад
    keyboard.append([InlineKeyboardButton(
        text="🔙 Назад",
        callback_data="models_back"
    )])
    
    await callback.message.edit_text(
        "🎨 *Генерация изображений:*\n\n"
        f"*{model['name']}*\n"
        f"{model['description']}\n\n"
        "Для генерации используйте команду /image",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode=ParseMode.MARKDOWN
    )
    await callback.answer()

@router.callback_query(F.data.startswith("model_"))
async def model_selected(callback: CallbackQuery):
    """Обработка выбора модели"""
    model_id = callback.data.replace("model_", "")
    user_id = callback.from_user.id
    
    if model_id not in GEMINI_MODELS:
        await callback.answer("❌ Неизвестная модель")
        return
    
    if user_id not in user_sessions:
        user_sessions[user_id] = UserSession(user_id)
    
    session = user_sessions[user_id]
    session.current_model = model_id
    
    model = GEMINI_MODELS[model_id]
    
    await callback.message.edit_text(
        f"✅ *Модель выбрана!*\n\n"
        f"🤖 *{model['name']}*\n"
        f"📝 {model['description']}\n\n"
        f"Теперь вы можете использовать {'текстовый чат' if model['category'] == 'text' else 'генерацию изображений'}",
        parse_mode=ParseMode.MARKDOWN
    )
    await callback.answer(f"Установлена: {model['name']}")

@router.callback_query(F.data == "models_back")
async def models_back(callback: CallbackQuery):
    """Вернуться к выбору категорий"""
    await cmd_models(callback.message)
    await callback.answer()

@router.message(Command("clear"))
async def cmd_clear(message: Message):
    user_id = message.from_user.id
    
    if user_id in user_sessions:
        old_count = len(user_sessions[user_id].history)
        user_sessions[user_id].history = []
        
        if old_count > 0:
            await message.answer(f"🧹 Очищено {old_count} сообщений")
        else:
            await message.answer("ℹ️ История уже пуста")
    else:
        await message.answer("ℹ️ История отсутствует")

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    user_id = message.from_user.id
    session = user_sessions.get(user_id)
    
    if not session:
        await message.answer("📊 Вы еще не начали диалог")
        return
    
    model = GEMINI_MODELS[session.current_model]
    
    stats_text = (
        f"📊 *Статистика*\n\n"
        f"🤖 Модель: *{model['name']}*\n"
        f"💬 Сообщений: *{len(session.history)}/{MAX_HISTORY_MESSAGES}*\n"
        f"📈 Всего: *{session.message_count}*\n"
        f"🕐 Активность: *{session.last_activity.strftime('%H:%M %d.%m')}*"
    )
    
    await message.answer(stats_text, parse_mode=ParseMode.MARKDOWN)

@router.message(Command("image"))
async def cmd_image(message: Message):
    """Команда для генерации изображений"""
    prompt = message.text.replace("/image", "").strip()
    
    if not prompt:
        await message.answer(
            "🎨 *Генерация изображений*\n\n"
            "Использование: `/image описание`\n\n"
            "*Примеры:*\n"
            "• `/image космический корабль`\n"
            "• `/image кот в костюме супергероя`\n"
            "• `/image закат над горами в стиле аниме`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    await generate_image(message, prompt)

# --- ГЕНЕРАЦИЯ ИЗОБРАЖЕНИЙ ---
async def generate_image(message: Message, prompt: str):
    """Генерация изображения через Imagen 3"""
    user_id = message.from_user.id
    
    if user_id not in user_sessions:
        user_sessions[user_id] = UserSession(user_id)
    
    session = user_sessions[user_id]
    session.message_count += 1
    session.last_activity = datetime.now()
    
    # Проверяем длину промпта
    if len(prompt) > 1000:
        await message.answer("⚠️ Промпт слишком длинный (макс 1000 символов)")
        return
    
    await message.chat.do("upload_photo")
    
    try:
        # Используем Imagen 3
        imagen_model = genai.GenerativeModel('imagen-3')
        
        response = await asyncio.to_thread(
            imagen_model.generate_images,
            prompt=prompt,
            number_of_images=1,
            language="ru"
        )
        
        if not response.images:
            raise ValueError("API не вернул изображение")
        
        image_url = response.images[0]._image_url
        img_response = requests.get(image_url, timeout=GEMINI_TIMEOUT)
        img_response.raise_for_status()
        
        img_data = BytesIO(img_response.content)
        
        await message.answer_photo(
            photo=img_data,
            caption=f"🎨 *Создано по запросу:*\n{prompt}",
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Ошибка генерации изображения: {e}")
        await message.answer(
            "❌ *Не удалось создать изображение*\n\n"
            "Попробуйте:\n"
            "• Изменить описание\n"
            "• Сделать запрос проще\n"
            "• Попробовать позже"
        )

# --- ОБРАБОТКА ТЕКСТА ---
@router.message(F.text & ~F.command)
async def handle_text(message: Message):
    user_id = message.from_user.id
    user_message = message.text
    
    if user_id not in user_sessions:
        user_sessions[user_id] = UserSession(user_id)
    
    session = user_sessions[user_id]
    session.message_count += 1
    session.last_activity = datetime.now()
    
    # Ограничиваем историю
    if len(session.history) > MAX_HISTORY_MESSAGES:
        keep = MAX_HISTORY_MESSAGES // 2
        session.history = session.history[-keep:]
    
    await message.chat.do("typing")
    
    try:
        model_config = GEMINI_MODELS[session.current_model]
        
        # Если выбрана Imagen 3 для текста - предлагаем использовать /image
        if model_config['category'] == 'image':
            await message.answer(
                "🎨 *Эта модель только для генерации изображений*\n\n"
                "Используйте команду `/image описание`\n\n"
                "Или выберите текстовую модель через /models",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Добавляем в историю
        session.history.append({"role": "user", "parts": [user_message]})
        
        # Создаем модель
        model = genai.GenerativeModel(model_config['model_id'])
        
        # Генерируем ответ
        if len(session.history) > 1:
            chat = model.start_chat(history=session.history[:-1])
            response = await asyncio.to_thread(chat.send_message, user_message)
        else:
            response = await asyncio.to_thread(model.generate_content, user_message)
        
        response_text = response.text
        session.history.append({"role": "model", "parts": [response_text]})
        
        await message.answer(response_text, parse_mode=ParseMode.MARKDOWN)
        
    except Exception as e:
        logger.error(f"Ошибка текста: {e}")
        
        if session.history and session.history[-1]["role"] == "user":
            session.history.pop()
        
        await message.answer(
            "❌ *Ошибка обработки*\n\n"
            "Попробуйте:\n"
            "• Переформулировать запрос\n"
            "• Использовать /clear\n"
            "• Сменить модель через /models"
        )

# --- ОБРАБОТКА ИЗОБРАЖЕНИЙ ---
@router.message(F.photo)
async def handle_image(message: Message):
    user_id = message.from_user.id
    
    if user_id not in user_sessions:
        user_sessions[user_id] = UserSession(user_id)
    
    session = user_sessions[user_id]
    session.message_count += 1
    session.last_activity = datetime.now()
    
    # Проверяем поддержку vision
    model_config = GEMINI_MODELS[session.current_model]
    if not model_config['supports_vision']:
        await message.answer(
            "❌ *Модель не поддерживает анализ изображений*\n\n"
            f"Текущая: *{model_config['name']}*\n\n"
            "Используйте /models чтобы выбрать:\n"
            "• Gemini 1.5 Flash/Pro\n"
            "• Gemini 3.0 Flash",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    await message.chat.do("upload_photo")
    
    try:
        photo = await message.photo[-1].get_file()
        img_bytes = await photo.download_as_bytearray()
        image = Image.open(BytesIO(img_bytes))
        
        prompt = message.caption or "Опиши это изображение"
        
        session.history.append({"role": "user", "parts": [f"[Изображение] {prompt}"]})
        
        model = genai.GenerativeModel(model_config['model_id'])
        response = await asyncio.to_thread(
            model.generate_content,
            [prompt, image]
        )
        
        response_text = response.text
        session.history.append({"role": "model", "parts": [response_text]})
        
        await message.answer(response_text, parse_mode=ParseMode.MARKDOWN)
        
    except Exception as e:
        logger.error(f"Ошибка анализа изображения: {e}")
        await message.answer("❌ Не удалось проанализировать изображение")

# --- РЕГИСТРАЦИЯ ---
def register_gemini_handlers(dp):
    dp.include_router(router)
    logger.info("✅ Хэндлеры Gemini зарегистрированы")