import os
import google.generativeai as genai
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# Получаем ключи из переменных окружения
GEMINI_API_KEY = os.getenv("AIzaSyD5j9b3IFKxJ6YdzyGVBS7i3nSoSyc5xMU")
TELEGRAM_TOKEN = os.getenv("7532015526:AAH6onVHZ7cBL6r13cyA95W0hgY1R4oECrI")

# Настройка Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-pro")

PROMPT_TEMPLATE = """
Ты — дружелюбный и компетентный бухгалтер в онлайн-приложении для ИП и ТОО в Казахстане. Отвечай по делу, по-человечески.

Вопрос пользователя: {user_question}
"""

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_question = update.message.text
    prompt = PROMPT_TEMPLATE.format(user_question=user_question)

    try:
        response = model.generate_content(prompt)
        await update.message.reply_text(response.text)
    except Exception as e:
        await update.message.reply_text("Произошла ошибка. Попробуйте позже.")
        print("Ошибка:", e)

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.run_polling()
