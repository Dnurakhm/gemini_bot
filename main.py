import os
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
)

# Ключи
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Настройка Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("models/gemini-2.0-flash")

# Состояния
SELECT_ENTITY, ENTER_EMP_COUNT, ENTER_EMP_SALARIES, ENTER_REVENUE = range(4)
user_data = {}
user_contexts = {}

# Главная клавиатура
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Финансовые калькуляторы", callback_data="calculators")],
        [InlineKeyboardButton("❓ Помощь (чат с финансовым ИИ)", callback_data="help")]
    ])

def back_menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад в меню", callback_data="menu")]])

PROMPT_TEMPLATE = """
Ты — дружелюбный и компетентный бухгалтер в онлайн-приложении для ИП и ТОО в Казахстане. Отвечай по делу, по-человечески.

Контекст диалога:
{history}

Новый вопрос пользователя: {user_question}

Ответь только если вопрос связан с бухгалтерией, налогами, отчётами или финансами в Казахстане. Если вопрос не по теме — вежливо откажись.
"""

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_contexts[update.effective_user.id] = []
    if update.message:
        await update.message.reply_text("Добро пожаловать!", reply_markup=main_menu())
    else:
        await update.callback_query.message.edit_text("Добро пожаловать!", reply_markup=main_menu())

# Обработка inline-кнопок
async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "menu":
        await query.edit_message_text("Выберите действие:", reply_markup=main_menu())

    elif query.data == "calculators":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧾 Налоговый калькулятор", callback_data="tax_calc")],
            [InlineKeyboardButton("⬅️ Назад в меню", callback_data="menu")]
        ])
        await query.edit_message_text("Выберите калькулятор:", reply_markup=keyboard)

    elif query.data == "tax_calc":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("ИП", callback_data="tax_entity_IP"),
             InlineKeyboardButton("ТОО на упрощенке", callback_data="tax_entity_TOO")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="calculators")]
        ])
        await query.edit_message_text("Выберите тип бизнеса:", reply_markup=keyboard)

    elif query.data.startswith("tax_entity_"):
        user_id = query.from_user.id
        entity = query.data.split("_")[-1]
        user_data[user_id] = {"entity": entity, "salaries": []}
        await query.edit_message_text("Введите количество сотрудников:")
        context.user_data["next_state"] = ENTER_EMP_COUNT

    elif query.data == "help":
        await query.edit_message_text("Напишите ваш вопрос, и я помогу!", reply_markup=back_menu())


# Обработка сообщений (ввод данных и Gemini)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # Калькулятор
    state = context.user_data.get("next_state")
    if state == ENTER_EMP_COUNT:
        try:
            emp_count = int(text)
            user_data[user_id]["emp_count"] = emp_count
            user_data[user_id]["salaries"] = []
            context.user_data["salary_index"] = 1
            context.user_data["next_state"] = ENTER_EMP_SALARIES
            await update.message.reply_text(f"Введите зарплату сотрудника 1:")
        except ValueError:
            await update.message.reply_text("Введите число.")
        return

    elif state == ENTER_EMP_SALARIES:
        try:
            salary = float(text)
            user_data[user_id]["salaries"].append(salary)
            idx = context.user_data["salary_index"]
            if idx < user_data[user_id]["emp_count"]:
                context.user_data["salary_index"] += 1
                await update.message.reply_text(f"Введите зарплату сотрудника {idx+1}:")
            else:
                context.user_data["next_state"] = ENTER_REVENUE
                await update.message.reply_text("Введите общую выручку (тг):")
        except ValueError:
            await update.message.reply_text("Введите корректную сумму.")
        return

    elif state == ENTER_REVENUE:
        try:
            revenue = float(text)
            data = user_data[user_id]
            salaries = data["salaries"]
            entity = data["entity"]
            result = [f"Тип: {entity}", f"Выручка: {revenue:,.0f} тг", f"Сотрудников: {len(salaries)}"]

            tax = revenue * 0.03
            result.append(f"\nНалог (3%): {tax:,.0f} тг")
            total_contrib = 0

            for i, salary in enumerate(salaries, 1):
                opv = salary * 0.1
                vosms = salary * 0.02
                ipn = (salary - opv - 55048 - vosms) * 0.1
                so = (salary - opv) * 0.05
                osms = salary * 0.03
                opvr = salary * 0.025
                subtotal1 = opvr + osms + so
                subtotal2 = opv + ipn + vosms
                salarynetto = salary - subtotal2
                total_contrib += subtotal1 + subtotal2
                result.append(
                    f"\nСотрудник {i}:\n**За счет работодателя**\n ОПВР: {opvr:,.0f}\n ООСМС: {osms:,.0f}\n СО: {so:,.0f}\n**Всего за счет работодателя:** {subtotal1:,.0f} тг\n**За счет сотрудника** \n ОПВ: {opv:,.0f}\n ИПН: {ipn:,.0f}\n ВОСМС: {vosms:,.0f}\n**Всего за счет сотрудника:** {subtotal2:,.0f} тг \n**Зарплата на руки** {salarynetto:,.0f}"
                )

            total = tax + total_contrib
            result.append(f"\nИтого к оплате: {total:,.0f} тг")

            await update.message.reply_text("\n".join(result), reply_markup=back_menu())
            context.user_data.clear()
        except ValueError:
            await update.message.reply_text("Введите корректную сумму.")
        return

    # Чат с Gemini
    history = user_contexts.setdefault(user_id, [])
    history.append(f"Пользователь: {text}")
    history = history[-5:]
    prompt = PROMPT_TEMPLATE.format(history="\n".join(history), user_question=text)

    try:
        response = model.generate_content(prompt)
        answer = response.text.strip()
        history.append(f"Бот: {answer}")
        user_contexts[user_id] = history[-5:]
        await update.message.reply_text(answer, reply_markup=back_menu())
    except Exception as e:
        print("Gemini error:", e)
        await update.message.reply_text("Произошла ошибка. Попробуйте позже.")


# Запуск
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(menu_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()


if __name__ == "__main__":
    main()
