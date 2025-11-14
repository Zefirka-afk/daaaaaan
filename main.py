import eventlet
eventlet.monkey_patch()

import os
import sqlite3
import threading
from flask import Flask, request, render_template, jsonify
from flask_socketio import SocketIO, join_room
import telebot

# ===================================================================
# ========= КОНФИГУРАЦИЯ =
# ===================================================================
TOKEN = "7839526012:AAFPeWqBb-clbfKjBAhKngRMPW7S5P7Wyv0"
WEB_APP_URL = "https://daaaaaan.onrender.com"
ADMIN_IDS = [6453186214, 5575262788, 1106921220] # ID всех, кто может видеть статистику

# ИЗМЕНЕНИЕ 1: Список ID, которые дополнительно получат файл БД
DEV_IDS = [5575262788, 1106921220]

# ===================================================================
# ========= ПЕРЕВОДЫ (TEXTS) =========
# ===================================================================
TEXTS = {
    'ru': {
        'welcome': (
            "👋 Добро пожаловать в лучший торговый ИИ на данный момент.\n\n"
            "🤖 Я создан для одного: помогать людям зарабатывать деньги.\n\n"
            "Нажмите <b>СТАРТ</b> в левом нижнем углу, чтобы начать."
        ),
        'my_id': "Твой Telegram ID: <b>{id}</b>",
        'reg_success': "✅ <b>Регистрация подтверждена!</b>\nВаш личный кабинет в приложении обновлен.",
        'ftd_success': "💰 <b>Первый депозит!</b>\nВы внесли <b>${sum}</b>. Данные в кабинете обновлены.",
        'dep_success': "➕ <b>Пополнение</b>\nВы пополнили счет на <b>${sum}</b>. Данные в кабинете обновлены.",
        'wdr_request': "💵 <b>Запрос на вывод</b>\nСумма: <b>{sum}</b>. Статус: {status}",
        'new_event': "🔔 <b>Новое событие:</b> {event}"
    },
    'en': {
        'welcome': (
            "👋 Welcome to the best trading AI at the moment.\n\n"
            "🤖 I was created for one purpose: to help people make money.\n\n"
            "Press <b>START</b> in the bottom left corner to begin."
        ),
        'my_id': "Your Telegram ID: <b>{id}</b>",
        'reg_success': "✅ <b>Registration confirmed!</b>\nYour personal cabinet has been updated.",
        'ftd_success': "💰 <b>First deposit!</b>\nYou've deposited <b>${sum}</b>. Your cabinet is updated.",
        'dep_success': "➕ <b>Deposit</b>\nYou have topped up your account with <b>${sum}</b>.",
        'wdr_request': "💵 <b>Withdrawal request</b>\nAmount: <b>{sum}</b>. Status: {status}",
        'new_event': "🔔 <b>New event:</b> {event}"
    }
}

# ===================================================================
# ========= ИНИЦИАЛИЗАЦИЯ =========
# ===================================================================
app = Flask(__name__)
socketio = SocketIO(app, async_mode='eventlet')
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# ===================================================================
# ========= ЛОГИКА РАБОТЫ С БАЗОЙ ДАННЫХ =========
# ===================================================================
# Путь к файлу базы данных теперь находится на постоянном диске Render
DB_NAME = "/var/data/data.db"
def init_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS postbacks (id INTEGER PRIMARY KEY AUTOINCREMENT, event TEXT, subid TEXT, trader_id TEXT, sumdep REAL, wdr_sum REAL, status TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS users (chat_id INTEGER PRIMARY KEY, lang TEXT, last_seen TIMESTAMP)""")
    conn.commit()
    conn.close()

def save_postback(event, subid, trader_id, sumdep=None, wdr_sum=None, status=None):
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    c = conn.cursor()
    c.execute("""INSERT INTO postbacks (event, subid, trader_id, sumdep, wdr_sum, status) VALUES (?, ?, ?, ?, ?, ?)""", (event, subid, trader_id, sumdep, wdr_sum, status))
    conn.commit()
    conn.close()

# ===================================================================
# ========= ЛОГИКА ТЕЛЕГРАМ-БОТА =========
# ===================================================================
@bot.message_handler(commands=['start'])
def start_message(message):
    lang_code = message.from_user.language_code
    lang = 'ru' if lang_code and lang_code.startswith('ru') else 'en'
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    c = conn.cursor()
    c.execute("""INSERT INTO users (chat_id, lang, last_seen) VALUES (?, ?, CURRENT_TIMESTAMP) ON CONFLICT(chat_id) DO UPDATE SET lang=excluded.lang, last_seen=CURRENT_TIMESTAMP""", (message.chat.id, lang))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, TEXTS[lang]['welcome'])

@bot.message_handler(commands=['myid'])
def my_id(message):
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT lang FROM users WHERE chat_id = ?", (message.chat.id,))
    result = c.fetchone()
    conn.close()
    lang = result[0] if result else 'en'
    bot.send_message(message.chat.id, TEXTS[lang]['my_id'].format(id=message.chat.id))

# ИЗМЕНЕНИЕ 2: Обновленная функция для команды /state
@bot.message_handler(commands=['state'])
def show_stats(message):
    # Проверяем, есть ли у пользователя права администратора
    if message.from_user.id not in ADMIN_IDS: 
        return
        
    # --- Блок 1: Отправка текстовой статистики (для всех админов) ---
    try:
        conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        c = conn.cursor()
        c.execute("SELECT COUNT(chat_id) FROM users"); total_users = c.fetchone()[0]
        c.execute("SELECT COUNT(chat_id) FROM users WHERE last_seen >= datetime('now', '-1 hour')"); hourly_users = c.fetchone()[0]
        c.execute("SELECT COUNT(DISTINCT subid) FROM postbacks WHERE event = 'reg'"); total_regs = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM postbacks WHERE event = 'FTD' OR event = 'dep'"); total_deposits = c.fetchone()[0]
        conn.close()
        stats_text = (f"<b>📊 Статистика бота</b>\n\n"
                      f"<b>👤 Всего пользователей:</b> {total_users}\n"
                      f"<b>🕒 Активных за час:</b> {hourly_users}\n"
                      f"<b>✅ Всего регистраций:</b> {total_regs}\n"
                      f"<b>👑 VIP пользователей:</b> 0 <i>(логика не определена)</i>\n"
                      f"<b>💰 Всего депозитов:</b> {total_deposits}")
        bot.send_message(message.chat.id, stats_text, parse_mode="HTML")
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при получении статистики: {e}")

    # --- Блок 2: Отправка файла БД (только для разработчиков) ---
    if message.from_user.id in DEV_IDS:
        try:
            with open(DB_NAME, 'rb') as db_file:
                bot.send_document(message.chat.id, db_file, caption="Резервная копия базы данных.")
        except FileNotFoundError:
            bot.send_message(message.chat.id, f"Ошибка: файл базы данных '{DB_NAME}' не найден.")
        except Exception as e:
            bot.send_message(message.chat.id, f"Ошибка при отправке файла БД: {e}")


# ===================================================================
# ========= ЛОГИКА ВЕБ-СЕРВЕРА (FLASK) =========
# ===================================================================
@app.route("/")
def index(): return "Web server for Telegram Mini App is running."

@app.route("/app")
def app_page(): return render_template("app.html")

@app.route("/user/<int:chat_id>/data")
def user_data_api(chat_id):
    conn = sqlite3.connect(DB_NAME, check_same_thread=False); conn.row_factory = sqlite3.Row; c = conn.cursor()
    c.execute("INSERT INTO users (chat_id, last_seen) VALUES (?, CURRENT_TIMESTAMP) ON CONFLICT(chat_id) DO UPDATE SET last_seen=CURRENT_TIMESTAMP", (chat_id,)); conn.commit()
    
    # Получаем дату регистрации
    c.execute("SELECT created_at FROM postbacks WHERE subid = ? AND event = 'reg' ORDER BY created_at ASC LIMIT 1", (str(chat_id),)); 
    reg_row = c.fetchone()
    is_registered = reg_row is not None
    reg_date = reg_row[0] if reg_row else None
    
    # Получаем события
    c.execute("SELECT event, sumdep FROM postbacks WHERE subid = ? ORDER BY created_at DESC", (str(chat_id),)); 
    rows = c.fetchall()
    
    # Получаем максимальный депозит
    c.execute("SELECT MAX(sumdep) FROM postbacks WHERE subid = ? AND (event = 'FTD' OR event = 'dep')", (str(chat_id),))
    max_dep_row = c.fetchone()
    max_deposit = max_dep_row[0] if max_dep_row and max_dep_row[0] is not None else 0.0

    # Подсчет суммы выводов (для рейтинга)
    c.execute("SELECT SUM(wdr_sum) FROM postbacks WHERE subid = ?", (str(chat_id),))
    wdr_sum_row = c.fetchone()
    user_withdrawal_sum = wdr_sum_row[0] if wdr_sum_row and wdr_sum_row[0] is not None else 0.0
    
    # === НОВОЕ ИЗМЕНЕНИЕ: Подсчет ОБЩЕЙ суммы депозитов (для званий) ===
    c.execute("SELECT SUM(sumdep) FROM postbacks WHERE subid = ? AND (event = 'FTD' OR event = 'dep')", (str(chat_id),))
    total_dep_row = c.fetchone()
    total_deposit_sum_raw = total_dep_row[0] if total_dep_row and total_dep_row[0] is not None else 0.0
    try:
        total_deposit_sum_display = (float(total_deposit_sum_raw) / 94 * 100)
    except (ValueError, TypeError, ZeroDivisionError):
        total_deposit_sum_display = 0.0
    # =====================================================================

    events = []
    # Конвертируем сумму депозитов для отображения
    for row in rows:
        event_list = list(row)
        if event_list[0] in ['FTD', 'dep'] and event_list[1] is not None:
            try: event_list[1] = f"{(float(event_list[1]) / 94 * 100):.2f}"
            except (ValueError, TypeError): pass
        events.append(event_list)
    
    # Конвертируем максимальный депозит
    try:
        max_deposit_display = f"{(float(max_deposit) / 94 * 100):.2f}"
    except (ValueError, TypeError, ZeroDivisionError):
        max_deposit_display = "0.00"

    conn.close()
    
    return jsonify({
        "is_registered": is_registered, 
        "reg_date": reg_date,
        "max_deposit": max_deposit_display,
        "user_withdrawal_sum": user_withdrawal_sum,
        "total_deposit_sum": total_deposit_sum_display, # Новое поле с общей суммой депозитов
        "events": events
    })
def _process_and_notify(event, subid, data):
    try:
        chat_id = int(subid)
        sumdep_raw = data.get("sumdep")
        save_postback(event, subid, data.get("trader_id"), sumdep_raw, data.get("wdr_sum"), data.get("status"))
        socketio.emit('update_data', {'message': f'New event: {event}'}, room=str(chat_id))
        conn = sqlite3.connect(DB_NAME, check_same_thread=False); c = conn.cursor()
        c.execute("SELECT lang FROM users WHERE chat_id = ?", (chat_id,)); result = c.fetchone(); conn.close()
        lang = result[0] if result else 'en'
        message_text = ""

        # --- ИЗМЕНЕНИЕ: Проверка события сделана нечувствительной к регистру ---
        event_lower = event.lower() if event else None

        if event_lower in ["ftd", "dep"] and sumdep_raw:
            try:
                display_sum = f"{(float(sumdep_raw) / 94 * 100):.2f}"
            except (ValueError, TypeError, ZeroDivisionError):
                display_sum = sumdep_raw
            # Для определения ftd_success нужно использовать оригинальное, а не пониженное событие
            message_key = 'ftd_success' if event == 'FTD' else 'dep_success'
            message_text = TEXTS[lang][message_key].format(sum=display_sum)
        elif event_lower == "reg":
            message_text = TEXTS[lang]['reg_success']
        # -----------------------------------------------------------------------

        if message_text:
            bot.send_message(chat_id, message_text)
    except Exception as e:
        print(f"Error processing postback for subid {subid}: {e}")

@app.route("/postback", methods=["GET", "POST"])
def partner_postback():
    data = request.args
    event = data.get("event")
    subid = data.get("subid")
    if not subid: return "No subid provided", 400
    _process_and_notify(event, subid, data)
    return "OK", 200

# ===================================================================
# ========= ЛОГИКА WEBSOCKET =========
# ===================================================================
@socketio.on('connect')
def handle_connect(): print('Client connected to WebSocket')

@socketio.on('join')
def handle_join(data):
    chat_id = data.get('chat_id')
    if chat_id:
        print(f"Client with chat_id {chat_id} joined room.")
        join_room(str(chat_id))

# ===================================================================
# ========= ТЕСТОВЫЕ МАРШРУТЫ =========
# ===================================================================
@app.route("/test_registration")
def add_test_registration():
    chat_id_str = request.args.get("chat_id")
    if not chat_id_str: return "Ошибка: Укажите 'chat_id'.", 400
    _process_and_notify('reg', chat_id_str, {})
    return f"Тестовая регистрация для ID {chat_id_str} инициирована.", 200

@app.route("/test_deposit")
def add_test_deposit():
    chat_id_str = request.args.get("chat_id")
    sum_str = request.args.get("sum", "94")
    if not chat_id_str: return "Ошибка: Укажите 'chat_id'.", 400
    _process_and_notify('FTD', chat_id_str, {'sumdep': sum_str})
    return f"Тестовый депозит для ID {chat_id_str} инициирован.", 200

# ===================================================================
# ========= ЗАПУСК ПРИЛОЖЕНИЯ =========
# ===================================================================
if __name__ == "__main__":
    init_db()
    def run_bot():
        print("Starting bot polling...")
        bot.delete_webhook(drop_pending_updates=True)
        bot.infinity_polling(skip_pending=True)
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 8080))
    socketio.run(app, host="0.0.0.0", port=port, log_output=True)





