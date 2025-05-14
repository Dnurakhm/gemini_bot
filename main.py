import os
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ConversationHandler,
)

# Ключи
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Настройка Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("models/gemini-2.0-flash")

# Состояния калькулятора
SELECT_ENTITY, ENTER_EMP_COUNT, ENTER_EMP_SALARIES, ENTER_REVENUE = range(4)

# Минималка
MZP = 85000  # 2025
user_data = {}
user_contexts = {}

PROMPT_TEMPLATE = """
Ты — дружелюбный и компетентный бухгалтер в онлайн-приложении для ИП и ТОО в Казахстане. Отвечай по делу, по-человечески.

Контекст диалога:
{history}

Новый вопрос пользователя: {user_question}

Ответь только если вопрос связан с бухгалтерией, налогами, отчётами или финансами в Казахстане. Если вопрос не по теме — вежливо откажись.
"""

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Финансовые калькуляторы", callback_data="calc")],
        [InlineKeyboardButton("Помощь", callback_data="help")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    user_contexts[update.message.from_user.id] = []
    await update.message.reply_text(
        "Привет! Готов помочь с бухгалтерией твоего ИП или ТОО в Казахстане. Выбери действие:",
        reply_markup=reply_markup,
    )

# Обработка inline-кнопок

async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "calc":
        await calculators(query, context)  # передаём query, не update
    elif query.data == "help":
        await query.edit_message_text("Если нужна помощь, напиши свой вопрос, и я постараюсь ответить.")


# Финансовые калькуляторы → Налоговый

async def calculators(query, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["Налоговый калькулятор"], ["Назад в меню"]]
    await query.message.reply_text(
        "Выберите калькулятор:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )


async def start_tax_calc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["ИП", "ТОО на упрощенке"]]
    await update.message.reply_text(
        "Выберите тип бизнеса:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )
    return SELECT_ENTITY

async def choose_entity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data[user_id] = {"entity": update.message.text}
    await update.message.reply_text("Количество сотрудников?", reply_markup=ReplyKeyboardRemove())
    return ENTER_EMP_COUNT

async def enter_employee_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        emp_count = int(update.message.text)
        user_id = update.effective_user.id
        user_data[user_id]["emp_count"] = emp_count
        user_data[user_id]["salaries"] = []
        await update.message.reply_text(f"Введите зарплату сотрудника 1:")
        return ENTER_EMP_SALARIES
    except ValueError:
        await update.message.reply_text("Введите число сотрудников.")
        return ENTER_EMP_COUNT

async def enter_employee_salaries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    salaries = user_data[user_id]["salaries"]
    try:
        salary = float(update.message.text)
        salaries.append(salary)
        if len(salaries) < user_data[user_id]["emp_count"]:
            await update.message.reply_text(f"Введите зарплату сотрудника {len(salaries)+1}:")
            return ENTER_EMP_SALARIES
        else:
            await update.message.reply_text("Введите общую выручку (тг):")
            return ENTER_REVENUE
    except ValueError:
        await update.message.reply_text("Введите корректную зарплату.")
        return ENTER_EMP_SALARIES

async def enter_revenue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        revenue = float(update.message.text)
        user_id = update.effective_user.id
        data = user_data[user_id]
        entity = data["entity"]
        salaries = data["salaries"]

        result = [f"Тип бизнеса: {entity}", f"Выручка: {revenue:,.0f} тг", f"Сотрудников: {len(salaries)}"]
        
        tax = revenue * 0.03
        result.append(f"\nНалог (3% от выручки): {tax:,.0f} тг")

        total_contrib = 0
        for i, salary in enumerate(salaries, start=1):
            opv = salary * 0.1
            vosms = salary * 0.02
            ipn = (salary - opv - 55048 - vosms) * 0.1
            so = (salary - opv) * 0.05
            osms = salary * 0.03
            opvr = salary * 0.025
            subtotal1 = opvr + osms + so
            subtotal2 = opv + ipn + vosms
            salarynetto = salary - subtotal2
            total_contrib += (subtotal1 + subtotal2)
            result.append(
                f"\nСотрудник {i}:\n**За счет работодателя**\n ОПВР: {opvr:,.0f}\n ООСМС: {osms:,.0f}\n СО: {so:,.0f}\n**Всего за счет работодателя:** {subtotal1:,.0f} тг\n**За счет сотрудника** \n ОПВ: {opv:,.0f}\n ИПН: {ipn:,.0f}\n ВОСМС: {vosms:,.0f}\n**Всего за счет сотрудника:** {subtotal2:,.0f} тг \n**Зарплата на руки** {salarynetto:,.0f}"
            )

        total = tax + total_contrib
        result.append(f"\nИтого к оплате: {total:,.0f} тг")

        await update.message.reply_text("\n".join(result), parse_mode='Markdown')
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("Введите корректную сумму выручки.")
        return ENTER_REVENUE

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Расчёт отменён.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# Обработка свободных вопросов через Gemini
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_question = update.message.text.strip()

    if user_id not in user_contexts:
        user_contexts[user_id] = []

    history = user_contexts[user_id]
    history.append(f"Пользователь: {user_question}")
    history = history[-5:]

    prompt = PROMPT_TEMPLATE.format(history="\n".join(history), user_question=user_question)

    try:
        response = model.generate_content(prompt)
        answer = response.text.strip()
        history.append(f"Бот: {answer}")
        user_contexts[user_id] = history[-5:]

        await update.message.reply_text(answer)
    except Exception as e:
        print("Gemini error:", e)
        await update.message.reply_text("Произошла ошибка. Попробуйте позже.")

# Запуск
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Налоговый калькулятор$"), start_tax_calc)],
        states={
            SELECT_ENTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_entity)],
            ENTER_EMP_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_employee_count)],
            ENTER_EMP_SALARIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_employee_salaries)],
            ENTER_REVENUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_revenue)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_menu_callback))
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()

if __name__ == "__main__":
    main()
