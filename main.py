import os
import google.generativeai as genai
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters

# Ключи
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Настройка Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("models/gemini-2.0-flash")

# Контекст пользователя
user_contexts = {}

# Шаблон
PROMPT_TEMPLATE = """
Ты — дружелюбный и компетентный бухгалтер в онлайн-приложении для ИП и ТОО в Казахстане. Отвечай по делу, по-человечески.

Контекст диалога:
{history}

Новый вопрос пользователя: {user_question}

Ответь только если вопрос связан с бухгалтерией, налогами, отчётами или финансами в Казахстане. Если вопрос не по теме — вежливо откажись.
"""

# Меню
menu_keyboard = [
    ["Инструкция по 910", "Как платить налоги"],
    ["Помощь", "Связаться с бухгалтером"]
]
reply_markup = ReplyKeyboardMarkup(menu_keyboard, resize_keyboard=True)

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_contexts[user_id] = []
    await update.message.reply_text(
        "Привет! Готов помочь с бухгалтерией твоего ИП или ТОО в Казахстане. Спрашивай!",
        reply_markup=reply_markup
    )

# Обработка сообщений
MAX_HISTORY = 5
MAX_MESSAGE_LENGTH = 4096

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_question = update.message.text.strip()

    if user_id not in user_contexts:
        user_contexts[user_id] = []

    # Обновляем историю
    history = user_contexts[user_id]
    history.append(f"Пользователь: {user_question}")
    history = history[-MAX_HISTORY:]

    # Формируем промпт
    full_prompt = PROMPT_TEMPLATE.format(
        history="\n".join(history),
        user_question=user_question
    )

    try:
        response = model.generate_content(full_prompt)
        answer = response.text.strip()

        # Сохраняем ответ в историю
        history.append(f"Бот: {answer}")
        user_contexts[user_id] = history[-MAX_HISTORY:]

        # Делим длинный ответ
        for i in range(0, len(answer), MAX_MESSAGE_LENGTH):
            chunk = answer[i:i + MAX_MESSAGE_LENGTH]
            await update.message.reply_text(chunk)

    except Exception as e:
        print("Ошибка:", e)
        await update.message.reply_text("Произошла ошибка. Попробуйте позже.")

# Запуск
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.run_polling()
