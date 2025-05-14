import os
import requests
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters
import google.generativeai as genai

# Переменные окружения
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
HF_API_TOKEN = os.getenv("HF_API_TOKEN")  # Hugging Face token

# Настройка Gemini
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel("gemini-2.0-flash")

# Шаблон для Gemini
PROMPT_TEMPLATE = """
Ты — дружелюбный и компетентный бухгалтер в онлайн-приложении для ИП и ТОО в Казахстане. Отвечай по делу, по-человечески.

Вопрос пользователя: {user_question}
"""

# Состояние пользователя
user_modes = {}  # user_id: "gemini" или "fingpt"

# Клавиатура
keyboard = [["Финансовый консультант"], ["Обычный вопрос"]]
reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

# Обработка /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Выберите режим общения:", reply_markup=reply_markup)

# Обработка выбора режима
async def mode_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    if text == "Финансовый консультант":
        user_modes[user_id] = "fingpt"
        await update.message.reply_text("Режим: Финансовый консультант.\nВведите ваш вопрос:")
    elif text == "Обычный вопрос":
        user_modes[user_id] = "gemini"
        await update.message.reply_text("Режим: Бухгалтер Gemini.\nВведите ваш вопрос:")

# Запрос к FinGPT
def query_fingpt(prompt: str) -> str:
    api_url = "https://api-inference.huggingface.co/models/AI4Finance/FinGPT"
    headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}
    response = requests.post(api_url, headers=headers, json={"inputs": prompt})
    result = response.json()
    try:
        return result[0]["generated_text"]
    except Exception:
        return "Произошла ошибка при получении ответа от FinGPT."

# Обработка сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_question = update.message.text
    mode = user_modes.get(user_id, "gemini")

    try:
        if mode == "fingpt":
            answer = query_fingpt(user_question)
        else:
            prompt = PROMPT_TEMPLATE.format(user_question=user_question)
            response = gemini_model.generate_content(prompt)
            answer = response.text

        # Разделение длинных сообщений
        for i in range(0, len(answer), 4000):
            await update.message.reply_text(answer[i:i+4000])

    except Exception as e:
        await update.message.reply_text("Произошла ошибка. Попробуйте позже.")
        print("Ошибка:", e)

# Запуск бота
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mode_handler))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.run_polling()
