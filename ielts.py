import logging
import gspread
from datetime import datetime, time, timedelta
from telegram import ReplyKeyboardMarkup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters, JobQueue
)
from collections import defaultdict

# --- ЛОГИРОВАНИЕ ---
logging.basicConfig(level=logging.INFO)

# --- GOOGLE SHEETS ---
gc = gspread.service_account(filename='C:\\Users\\Админ\\Downloads\\bot-467620-5b226ea58465.json')
sh = gc.open("IELTS Tracker")
worksheet = sh.sheet1

# --- ГЛАВНОЕ МЕНЮ ---
def main_menu():
    keyboard = [
        [InlineKeyboardButton("Mark🏆", callback_data='mark')],
        [InlineKeyboardButton("Table📊", callback_data='table')],
        [InlineKeyboardButton("Progress💪", callback_data='progress')],
        [InlineKeyboardButton("Top🥇", callback_data='top')]
    ]
    return InlineKeyboardMarkup(keyboard)

menu_keyboard = ReplyKeyboardMarkup([['/menu']], resize_keyboard=True)

# --- ВЫБОР РАЗДЕЛА ---
def section_menu():
    keyboard = [
        [InlineKeyboardButton("📚 Listening", callback_data='listening')],
        [InlineKeyboardButton("📗 Reading", callback_data='reading')],
        [InlineKeyboardButton("📕 Writing", callback_data='writing')],
        [InlineKeyboardButton("📙 Speaking", callback_data='speaking')],
        [InlineKeyboardButton("🔙 Басты бетке оралу", callback_data='menu')]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- /START ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    username = user.username or "NoUsername"

    await update.message.reply_text(
        f"Сәлеметсіз бе, @{username}! Қош келдіңіз! 👋\n\nТөмендегі мәзірден таңдаңыз:",
        InlineKeyboardButton("🔙 Басты бетке оралу", callback_data='menu')
    )

# --- /MENU ---
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Мәзірден таңдаңыз:", reply_markup=main_menu())

# --- ОБРАБОТКА КНОПОК ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    if data == "mark":
        await query.message.reply_text("Қай бөлім бойынша белгі салғыңыз келеді?", reply_markup=section_menu())

    elif data in ['listening', 'reading', 'writing', 'speaking']:
        context.user_data['current_section'] = data
        await query.message.reply_text(f"{data.capitalize()} бойынша не істегеніңізді жазыңыз:")

    elif data == "table":
        await query.message.reply_text("📊 Google Sheets-ті тексеріңіз: [IELTS Tracker](https://docs.google.com/spreadsheets/d/174A32kv9iWEYRpcmqab1KorLqsqimgAVGUbLb_zjnCI)", parse_mode='Markdown', reply_markup=menu_keyboard)

    elif data == "progress":
        user = query.from_user
        username = user.username or "NoUsername"
        records = worksheet.get_all_records()

        activity = defaultdict(lambda: "❌")
        for row in records:
            if row['username'] == username:
                date = row['date']
                activity[date] = "✅"

        user_dates = [datetime.strptime(row['date'], "%Y-%m-%d").date() for row in records if row['username'] == username]
        if user_dates:
            start_date = min(user_dates)
            end_date = max(datetime.today().date(), start_date + timedelta(days=29))
        else:
            start_date = datetime.today().date() - timedelta(days=29)
            end_date = datetime.today().date()

        calendar = "📅 *30 күндік прогресс:*\n\n"
        for i in range((end_date - start_date).days + 1):
            day = start_date + timedelta(days=i)
            mark = activity[day.strftime('%Y-%m-%d')]
            calendar += f"{day.strftime('%d.%m')} - {mark}\n"

        await query.message.reply_text(calendar, parse_mode="Markdown", reply_markup=menu_keyboard)


    elif data == "top":
        records = worksheet.get_all_records()
        count = defaultdict(int)

        for row in records:
            username = row["username"]
            for part in ['listening', 'reading', 'writing', 'speaking']:
                if row.get(part):
                    count[username] += 1

        top = sorted(count.items(), key=lambda x: x[1], reverse=True)[:10]
        leaderboard = "🥇 *ТОП 10 қолданушы:*\n\n"
        for i, (user, score) in enumerate(top, 1):
            leaderboard += f"{i}. @{user} — {score} entries\n"

        await query.message.reply_text(leaderboard, parse_mode="Markdown", reply_markup=menu_keyboard)


    elif data == "menu":
        await query.message.reply_text("Басты мәзір:", reply_markup=main_menu())

# --- ОБРАБОТКА ТЕКСТА ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = update.message.text
    section = context.user_data.get('current_section')

    if not section:
        await update.message.reply_text("Алдымен бөлімді таңдаңыз: /menu")
        return

    username = user.username or "NoUsername"
    user_id = str(user.id)
    today = str(datetime.now().date())

    part_columns = {'listening': 'D', 'reading': 'E', 'writing': 'F', 'speaking': 'G'}
    col_letter = part_columns[section]

    records = worksheet.get_all_records()
    row_index = None
    for idx, row in enumerate(records, start=2):
        if str(row['id']) == user_id and str(row['date']) == today:
            row_index = idx
            break

    if row_index:
        cell = worksheet.acell(f"{col_letter}{row_index}").value
        updated_text = (cell + "\n+ " + msg) if cell else msg
        worksheet.update_acell(f"{col_letter}{row_index}", updated_text)
    else:
        data = {'listening': '', 'reading': '', 'writing': '', 'speaking': ''}
        data[section] = msg
        worksheet.append_row([
            user_id, username, today,
            data['listening'], data['reading'], data['writing'], data['speaking'],
            today, '🟢'
        ])

    await update.message.reply_text("✅ Тамаша! Белгіленді. Солай жалғастырыңыз! 💪", reply_markup=main_menu())
    context.user_data['current_section'] = None

# --- НАПОМИНАНИЕ В 18:00 ---
async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_ids = [123456789, 987654321]
    for chat_id in chat_ids:
        try:
            await context.bot.send_message(chat_id=chat_id, text="📖 Әлі де практистарыңызды белгілемедіңіз бе? Күннің аяқталуына дейін үлгеріңіз!⏳")
        except Exception as e:
            logging.warning(f"Ошибка при отправке напоминания в {chat_id}: {e}")

# --- ЗАПУСК БОТА ---
app = ApplicationBuilder().token("8417568456:AAFukr8t3VNOzda-38GXE6FHIKhD4tsF4DY").build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("menu", menu))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

job_queue: JobQueue = app.job_queue
job_queue.run_daily(send_reminder, time(hour=18, minute=0))

app.run_polling()
