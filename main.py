from telegram import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Update,
)
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters,
)
import os
import google.generativeai as genai

# Ключи
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Настройка Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("models/gemini-2.0-flash")

# Состояния
SELECT_ENTITY, ENTER_EMP_COUNT, ENTER_EMP_SALARIES, ENTER_REVENUE = range(4)

MZP = 85000
user_data = {}
user_contexts = {}

PROMPT_TEMPLATE = """
Ты — дружелюбный и компетентный бухгалтер в онлайн-приложении для ИП и ТОО в Казахстане. Отвечай по делу, по-человечески.

Контекст диалога:
{history}

Новый вопрос пользователя: {user_question}

Ответь только если вопрос связан с бухгалтерией, налогами, отчётами или финансами в Казахстане. Если вопрос не по теме — вежливо откажись.
"""

def main_menu():
    keyboard = [
        [InlineKeyboardButton("Финансовые калькуляторы", callback_data="calculators")],
        [InlineKeyboardButton("Помощь", callback_data="help")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_contexts[update.effective_user.id] = []
    await update.message.reply_text(
        "Привет! Готов помочь с бухгалтерией твоего ИП или ТОО в Казахстане. Выбирай из меню:",
        reply_markup=main_menu()
    )

async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "calculators":
        keyboard = [
            [InlineKeyboardButton("Налоговый калькулятор", callback_data="tax_calc")],
            [InlineKeyboardButton("Назад", callback_data="back_to_main")]
        ]
        await query.edit_message_text("Выберите калькулятор:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "help":
        await query.edit_message_text("Напиши свой вопрос, и я постараюсь помочь. Это чат с Gemini.")

    elif data == "back_to_main":
        await query.edit_message_text("Главное меню:", reply_markup=main_menu())

    elif data == "tax_calc":
        keyboard = [
            [InlineKeyboardButton("ИП", callback_data="tax_calc_ip"),
             InlineKeyboardButton("ТОО", callback_data="tax_calc_too")],
            [InlineKeyboardButton("Назад", callback_data="calculators")]
        ]
        await query.edit_message_text("Выберите тип бизнеса:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data in ["tax_calc_ip", "tax_calc_too"]:
        entity = "ИП" if data.endswith("ip") else "ТОО"
        user_data[query.from_user.id] = {
            "entity": entity,
            "salaries": []
        }
        await query.edit_message_text(f"Вы выбрали: {entity}. Введите количество сотрудников:")
        return SELECT_ENTITY

async def choose_entity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        emp_count = int(update.message.text)
        user_id = update.message.from_user.id
        user_data[user_id]["emp_count"] = emp_count
        await update.message.reply_text("Введите зарплату сотрудника 1:")
        return ENTER_EMP_SALARIES
    except ValueError:
        await update.message.reply_text("Введите число.")
        return SELECT_ENTITY

async def enter_employee_salaries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    data = user_data[user_id]
    try:
        salary = float(update.message.text)
        data["salaries"].append(salary)
        if len(data["salaries"]) < data["emp_count"]:
            await update.message.reply_text(f"Введите зарплату сотрудника {len(data['salaries']) + 1}:")
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
        user_id = update.message.from_user.id
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
                f"\nСотрудник {i}:\n"
                f"**За счет работодателя**\n ОПВР: {opvr:,.0f}\n ООСМС: {osms:,.0f}\n СО: {so:,.0f}\n"
                f"**Всего за счет работодателя:** {subtotal1:,.0f} тг\n"
                f"**За счет сотрудника**\n ОПВ: {opv:,.0f}\n ИПН: {ipn:,.0f}\n ВОСМС: {vosms:,.0f}\n"
                f"**Всего за счет сотрудника:** {subtotal2:,.0f} тг\n"
                f"**Зарплата на руки:** {salarynetto:,.0f}"
            )

        total = tax + total_contrib
        result.append(f"\nИтого к оплате: {total:,.0f} тг")

        await update.message.reply_text("\n".join(result), parse_mode='Markdown')
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("Введите корректную сумму.")
        return ENTER_REVENUE

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Расчёт отменён.")
    return ConversationHandler.END

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

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_menu_callback, pattern="^tax_calc")],
        states={
            SELECT_ENTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_entity)],
            ENTER_EMP_SALARIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_employee_salaries)],
            ENTER_REVENUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_revenue)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_menu_callback))
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()

if __name__ == "__main__":
    main()
