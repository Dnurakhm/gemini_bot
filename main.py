import os
import google.generativeai as genai
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, ConversationHandler

# Переменные окружения
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Настройка Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("models/gemini-2.0-flash")

# МЗП и константы для калькуляторов
MZP = 85000  # Минимальная заработная плата

# Состояния для калькуляторов
SELECT_ENTITY, SELECT_EMPLOYEES, ENTER_REVENUE = range(3)
ESP_LOCATION = range(1)
SALARY_ENTER = range(2)

# Хранение данных о пользователях
user_data = {}

# Функция расчета налогов и взносов
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

# Функция расчета ЕСП
def calc_esp(is_city: bool) -> str:
    """
    ЕСП: в городе — 1 МЗП (85000), в селе — 0.5 МЗП
    Делится:
    - 10% — ОПВ
    - 30% — ОСМС
    - 10% — ИПН
    - 50% — Социальные отчисления
    """
    base = MZP if is_city else MZP / 2
    opv = base * 0.1
    osms = base * 0.3
    ipn = base * 0.1
    so = base * 0.5

    total = opv + osms + ipn + so
    return (
        f"Расчёт ЕСП ({'город' if is_city else 'село'}):\n"
        f"ОПВ (10%): {opv:,.0f} тг\n"
        f"ОСМС (30%): {osms:,.0f} тг\n"
        f"ИПН (10%): {ipn:,.0f} тг\n"
        f"Социальные отчисления (50%): {so:,.0f} тг\n"
        f"Итого к оплате: {total:,.0f} тг"
    )

# Функция расчета зарплаты сотрудника
def calc_salary(base_salary: float, is_city: bool) -> str:
    """
    Расчет зарплаты сотрудника с учетом всех налогов и отчислений
    - ИПН (10%)
    - ОПВ (10%)
    - СО (3.5% от МЗП)
    - СОПР (5% от МЗП)
    - ОСМС (2% от МЗП)
    """
    ipn = base_salary * 0.1
    opv = base_salary * 0.1
    so = MZP * 0.035
    sopr = MZP * 0.05
    osms = MZP * 0.02

    deductions = ipn + opv + so + sopr + osms

    net_salary = base_salary - deductions

    return (
        f"Зарплата сотрудника с учетом всех отчислений:\n"
        f"Брутто зарплата: {base_salary:,.0f} тг\n"
        f"ИПН (10%): {ipn:,.0f} тг\n"
        f"ОПВ (10%): {opv:,.0f} тг\n"
        f"СО (3.5% от МЗП): {so:,.0f} тг\n"
        f"СОПР (5% от МЗП): {sopr:,.0f} тг\n"
        f"ОСМС (2% от МЗП): {osms:,.0f} тг\n"
        f"Итого отчислений: {deductions:,.0f} тг\n"
        f"Чистая зарплата: {net_salary:,.0f} тг"
    )

# Функция начала взаимодействия
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["Финансовые калькуляторы"]]
    await update.message.reply_text(
        "Привет! Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )

# Функция калькуляторов
async def calculators(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["Налоговый калькулятор", "ЕСП калькулятор", "Зарплатный калькулятор"], ["Назад"]]
    await update.message.reply_text(
        "Выберите калькулятор:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )

# Налоговый калькулятор
async def start_tax_calc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["ИП", "ТОО"]]
    await update.message.reply_text(
        "Выберите тип бизнеса:", reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return SELECT_ENTITY

async def choose_entity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    entity = update.message.text
    user_data[update.effective_user.id] = {"entity": entity}
    keyboard = [["Да", "Нет"]]
    await update.message.reply_text(
        "Есть ли у вас сотрудники?", reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
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

# ЕСП калькулятор
async def start_esp_calc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["Город", "Село"]]
    await update.message.reply_text(
        "Выберите местоположение (город или село):", reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return ESP_LOCATION

async def choose_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_city = update.message.text == "Город"
    result = calc_esp(is_city)
    await update.message.reply_text(result)
    return ConversationHandler.END

# Зарплатный калькулятор
async def start_salary_calc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Введите брутто зарплату сотрудника в тг (например: 120000):", reply_markup=ReplyKeyboardRemove()
    )
    return SALARY_ENTER

async def enter_salary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        base_salary = float(update.message.text)
        data = user_data.get(update.effective_user.id, {})
        is_city = data.get("location", "Город") == "Город"  # Если место не указано, предположим "Город"
        result = calc_salary(base_salary, is_city)
        await update.message.reply_text(result)
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите корректное число.")
        return SALARY_ENTER

    return ConversationHandler.END

# Обработка команды отмены
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Расчёт отменён.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# Обработка сообщений для Gemini
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_question = update.message.text.strip()
    user_id = update.message.from_user.id

    if user_id not in user_data:
        user_data[user_id] = []

    # Формируем контекст для Gemini
    full_prompt = f"Контекст: {user_data[user_id]}\nВопрос: {user_question}"

    try:
        response = model.generate_content(full_prompt)
        answer = response.text.strip()
        await update.message.reply_text(answer)
    except Exception as e:
        await update.message.reply_text("Произошла ошибка. Попробуйте позже.")

# Основная функция для запуска бота
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Настройка ConversationHandler для налогового и ЕСП калькуляторов
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Налоговый калькулятор$"), start_tax_calc),
                      MessageHandler(filters.Regex("^ЕСП калькулятор$"), start_esp_calc),
                      MessageHandler(filters.Regex("^Зарплатный калькулятор$"), start_salary_calc)],
        states={
            SELECT_ENTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_entity)],
            SELECT_EMPLOYEES: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_employees)],
            ENTER_REVENUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_revenue)],
            ESP_LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_location)],
            SALARY_ENTER: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_salary)],
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
