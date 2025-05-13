import os
import google.generativeai as genai
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

# Получаем ключи из переменных окружения
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Проверка ключей
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN не задан. Проверь переменные окружения Railway.")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY не задан. Проверь переменные окружения Railway.")

# Настройка Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-pro-latest")

# Шаблон запроса
PROMPT_TEMPLATE = """
Ты — дружелюбный и компетентный бухгалтер в онлайн-приложении для ИП и ТОО в Казахстане. Отвечай по делу, по-человечески.

Вопрос пользователя: {user_question}
"""

# Меню кнопок
menu_keyboard = [["Популярные вопросы"], ["Помощь"]]
reply_markup = ReplyKeyboardMarkup(menu_keyboard, resize_keyboard=True)

# Обработка команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я ваш онлайн-бухгалтер. Выберите действие или напишите вопрос:",
        reply_markup=reply_markup
    )

# Обработка текстовых сообщений и кнопок
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_question = update.message.text

    if user_question == "Помощь":
        await update.message.reply_text("Я могу помочь вам с вопросами по налогам, ИП, ТОО и бухгалтерии в Казахстане.")
        return
    elif user_question == "Популярные вопросы":
        await update.message.reply_text(
            "Вот примеры:\n"
            "- Как открыть ИП?\n"
            "- Какие налоги платит ТОО?\n"
            "- Что такое ОПВ и ОСМС?"
        )
        return

    # Основной запрос к Gemini
    prompt = PROMPT_TEMPLATE.format(user_question=user_question)

    try:
        response = model.generate_content(prompt)
        await update.message.reply_text(response.text)
    except Exception as e:
        await update.message.reply_text("Произошла ошибка. Попробуйте позже.")
        print("Ошибка:", e)

# Запуск приложения
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.run_polling()
