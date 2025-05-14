import os
import google.generativeai as genai
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
)

# Ключи
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Настройка Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("models/gemini-gemini-2.0-flash")

# Состояния для ConversationHandler
SELECT_ENTITY, SELECT_EMPLOYEES, ENTER_REVENUE = range(3)
MZP = 85000  # Минимальная заработная плата на 2025

# Контекст пользователя
user_contexts = {}
user_data = {}

# Шаблон
PROMPT_TEMPLATE = """
Ты — дружелюбный и компетентный бухгалтер в онлайн-приложении для ИП и ТОО в Казахстане. Отвечай по делу, по-человечески.

Контекст диалога:
{history}

Новый вопрос пользователя: {user_question}

Ответь только если вопрос связан с бухгалтерией, налогами, отчётами или финансами в Казахстане. Если вопрос не по теме — вежливо откажись.
"""

# Главное меню
main_menu_keyboard = [
    ["Инструкция по 910", "Как платить налоги"],
    ["Помощь", "Связаться с бухгалтером"],
    ["Финансовые калькуляторы"]
]
reply_markup = ReplyKeyboardMarkup(main_menu_keyboard, resize_keyboard=True)

# Кнопка калькулятора
async def calculators(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["Налоговый калькулятор"], ["Назад в меню"]]
    await update.message.reply_text(
        "Выберите калькулятор:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# Кнопка /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_contexts[user_id] = []
    await update.message.reply_text(
        "Привет! Готов помочь с бухгалтерией твоего ИП или ТОО в Казахстане. Выбери действие:",
        reply_markup=reply_markup
    )

# Обработка вопросов пользователю → Gemini
MAX_HISTORY = 5
MAX_MESSAGE_LENGTH = 4096

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "Назад в меню":
        await update.message.reply_text("Вы вернулись в главное меню.", reply_markup=reply_markup)
        return
    elif text in ["Налоговый калькулятор"]:
        return await start_tax_calc(update, context)

    user_id = update.message.from_user.id
    user_question = update.message.text.strip()

    if user_id not in user_contexts:
        user_contexts[user_id] = []

    # История
    history = user_contexts[user_id]
    history.append(f"Пользователь: {user_question}")
    history = history[-MAX_HISTORY:]

    prompt = PROMPT_TEMPLATE.format(
        history="\n".join(history),
        user_question=user_question
    )

    try:
        response = model.generate_content(prompt)
        answer = response.text.strip()

        history.append(f"Бот: {answer}")
        user_contexts[user_id] = history[-MAX_HISTORY:]

        for i in range(0, len(answer), MAX_MESSAGE_LENGTH):
            chunk = answer[i:i + MAX_MESSAGE_LENGTH]
            await update.message.reply_text(chunk)

    except Exception as e:
        print("Ошибка:", e)
        await update.message.reply_text("Произошла ошибка. Попробуйте позже.")


# === Логика налогового калькулятора ===
def calc_tax_kz(entity_type: str, revenue: float, with_employees: bool) -> str:
    result = []

    tax = revenue * 0.03
    result.append(f"Налог (3% от выручки): {tax:,.0f} тг")

    if with_employees or entity_type == "ИП":
        opv_base = MZP * 14
        opv = opv_base * 0.1
        osms = opv_base * 0.02
        so = MZP * 0.035
        sopr = MZP * 0.05

        result.append(f"ОПВ (10% от 14 МЗП): {opv:,.0f} тг")
        result.append(f"ОСМС (2% от 14 МЗП): {osms:,.0f} тг")
        result.append(f"СО (3.5% от 1 МЗП): {so:,.0f} тг")
        result.append(f"СОПР (5% от 1 МЗП): {sopr:,.0f} тг")

        total = tax + opv + osms + so + sopr
    else:
        total = tax

    result.append(f"\nИтого к оплате: {total:,.0f} тг")
    return "\n".join(result)


async def start_tax_calc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["ИП", "ТОО"]]
    await update.message.reply_text(
        "Выберите тип бизнеса:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return SELECT_ENTITY


async def choose_entity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    entity = update.message.text
    user_data[update.effective_user.id] = {"entity": entity}
    keyboard = [["Да", "Нет"]]
    await update.message.reply_text(
        "Есть ли у вас сотрудники?",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return SELECT_EMPLOYEES


async def choose_employees(update: Update, context: ContextTypes.DEFAULT_TYPE):
    has_employees = update.message.text == "Да"
    user_data[update.effective_user.id]["with_employees"] = has_employees
    await update.message.reply_text(
        "Введите вашу выручку в тг (например: 1200000):", reply_markup=ReplyKeyboardRemove()
    )
    return ENTER_REVENUE


async def enter_revenue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        revenue = float(update.message.text)
        data = user_data[update.effective_user.id]
        result = calc_tax_kz(
            entity_type=data["entity"], revenue=revenue, with_employees=data["with_employees"]
        )
        await update.message.reply_text(result)
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите корректное число.")
        return ENTER_REVENUE

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Расчёт отменён.", reply_markup=reply_markup)
    return ConversationHandler.END


# Запуск
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Conversation handler для налогового калькулятора
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Налоговый калькулятор$"), start_tax_calc)],
        states={
            SELECT_ENTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_entity)],
            SELECT_EMPLOYEES: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_employees)],
            ENTER_REVENUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_revenue)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^Финансовые калькуляторы$"), calculators))
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()


if __name__ == "__main__":
    main()
