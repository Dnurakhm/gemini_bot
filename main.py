import os
import google.generativeai as genai
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# Получаем ключи из переменных окружения
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

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
