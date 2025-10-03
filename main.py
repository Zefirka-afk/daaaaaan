import os
import sqlite3
import threading
from flask import Flask, request, render_template, jsonify
# Импортируем SocketIO
from flask_socketio import SocketIO, join_room
import telebot
# Импортируем eventlet для правильной работы WebSocket
import eventlet

# Необходимо для асинхронной работы WebSocket
eventlet.monkey_patch()

# ===================================================================
# ========= КОНФИГУРАЦИЯ =
# ===================================================================
TOKEN = "8441945670:AAFTTAym0douRv4mUnFfDlu3k1eNsBATPu8"
WEB_APP_URL = "https://daaaaaan.onrender.com"  # Убедись, что этот URL правильный

# Добавь сюда свой Telegram ID
ADMIN_IDS = [6453186214]  # <-- ЗАМЕНИ НА СВОЙ ID. Можно добавить несколько через запятую.

# ===================================================================
# ========= ПЕРЕВОДЫ (TEXTS) =========
# ===================================================================
TEXTS = {
    'ru': {
        'welcome': "Привет 👋 Я бот для трейдинга!\n\nНажми на кнопку <b>Меню</b> слева внизу, чтобы открыть свой личный кабинет.",
        'my_id': "Твой Telegram ID: <b>{id}</b>",
        'reg_success': "✅ <b>Регистрация подтверждена!</b>\nВаш личный кабинет в приложении обновлен.",
        'ftd_success': "💰 <b>Первый депозит!</b>\nВы внесли <b>${sum}</b>. Данные в кабинете обновлены.",
        'dep_success': "➕ <b>Пополнение</b>\nВы пополнили счет на <b>${sum}</b>. Данные в кабинете обновлены.",
        'wdr_request': "💵 <b>Запрос на вывод</b>\nСумма: <b>{sum}</b>. Статус: {status}",
        'new_event': "🔔 <b>Новое событие:</b> {event}"
    },
    'en': {
        'welcome': "Hello 👋 I'm a trading bot!\n\nPress the <b>Menu</b> button in the bottom left to open your personal cabinet.",
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
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
app = Flask(__name__)
# Инициализируем SocketIO
socketio = SocketIO(app, async_mode='eventlet')

# ===================================================================
# ========= ЛОГИКА РАБОТЫ С БАЗОЙ ДАННЫХ =========
# ===================================================================
DB_NAME = "data.db"

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

@bot.message_handler(commands=['state'])
def show_stats(message):
    if message.from_user.id not in ADMIN_IDS: return
    try:
        conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        c = conn.cursor()
        c.execute("SELECT COUNT(chat_id) FROM users"); total_users = c.fetchone()[0]
        c.execute("SELECT COUNT(chat_id) FROM users WHERE last_seen >= datetime('now', '-1 hour')"); hourly_users = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM postbacks WHERE event = 'reg'"); total_regs = c.fetchone()[0]
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

# ===================================================================
# ========= ЛОГИКА ВЕБ-СЕРВЕРА (FLASK) =========
# ===================================================================
@app.route("/")
def index(): return "Web server for Telegram Mini App is running."

@app.route("/app")
def app_page(): return render_template("app.html")

@app.route("/user/<int:chat_id>/data")
def user_data_api(chat_id):
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("INSERT INTO users (chat_id, last_seen) VALUES (?, CURRENT_TIMESTAMP) ON CONFLICT(chat_id) DO UPDATE SET last_seen=CURRENT_TIMESTAMP", (chat_id,)); conn.commit()
    c.execute("SELECT 1 FROM postbacks WHERE subid = ? AND event = 'reg' LIMIT 1", (str(chat_id),)); is_registered = c.fetchone() is not None
    c.execute("SELECT event, sumdep, wdr_sum, status, created_at FROM postbacks WHERE subid = ? ORDER BY created_at DESC", (str(chat_id),)); rows = c.fetchall()
    events = []
    for row in rows:
        event_list = list(row)
        if event_list[0] in ['FTD', 'dep'] and event_list[1] is not None:
            try:
                event_list[1] = f"{(float(event_list[1]) / 94 * 100):.2f}"
            except (ValueError, TypeError): pass
        events.append(event_list)
    conn.close()
    return jsonify({"is_registered": is_registered, "events": events})

@app.route("/postback", methods=["GET", "POST"])
def partner_postback():
    data = request.args
    event = data.get("event")
    subid = data.get("subid")
    sumdep_raw = data.get("sumdep")
    if not subid: return "No subid provided", 400
    try: chat_id = int(subid)
    except (ValueError, TypeError): return "Invalid subid", 400

    save_postback(event, subid, data.get("trader_id"), sumdep_raw, data.get("wdr_sum"), data.get("status"))
    
    socketio.emit('update_data', {'message': 'Your data has been updated!'}, room=str(chat_id))

    conn = sqlite3.connect(DB_NAME, check_same_thread=False); c = conn.cursor()
    c.execute("SELECT lang FROM users WHERE chat_id = ?", (chat_id,)); result = c.fetchone(); conn.close()
    lang = result[0] if result else 'en'
    message_text = ""
    if event in ["FTD", "dep"]:
        try: display_sum = f"{(float(sumdep_raw) / 94 * 100):.2f}"
        except (ValueError, TypeError, ZeroDivisionError): display_sum = sumdep_raw
        message_key = 'ftd_success' if event == 'FTD' else 'dep_success'
        message_text = TEXTS[lang][message_key].format(sum=display_sum)
    elif event == "reg": message_text = TEXTS[lang]['reg_success']
    if message_text:
        try: bot.send_message(chat_id, message_text)
        except Exception as e: print(f"Failed to send message to {chat_id}: {e}")
    return "OK", 200

# ===================================================================
# ========= ЛОГИКА WEBSOCKET =========
# ===================================================================
@socketio.on('connect')
def handle_connect():
    print('Client connected to WebSocket')

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
    if not chat_id_str: return "Ошибка: Пожалуйста, укажите 'chat_id' в параметрах URL.", 400
    try: chat_id = int(chat_id_str)
    except ValueError: return "Ошибка: 'chat_id' должен быть числом.", 400
    import requests
    try:
        requests.get(f"{request.url_root}postback", params={'event': 'reg', 'subid': chat_id}, timeout=3)
    except requests.exceptions.RequestException as e:
        print(f"Test registration request failed: {e}")
    return f"Тестовая регистрация для ID {chat_id} инициирована.", 200

@app.route("/test_deposit")
def add_test_deposit():
    chat_id_str = request.args.get("chat_id")
    sum_str = request.args.get("sum", "94")
    if not chat_id_str: return "Ошибка: Пожалуйста, укажите 'chat_id' в параметрах URL.", 400
    try:
        chat_id = int(chat_id_str)
        raw_deposit_sum = float(sum_str)
    except ValueError: return "Ошибка: 'chat_id' и 'sum' должны быть числами.", 400
    import requests
    try:
        requests.get(f"{request.url_root}postback", params={'event': 'FTD', 'subid': chat_id, 'sumdep': raw_deposit_sum}, timeout=3)
    except requests.exceptions.RequestException as e:
        print(f"Test deposit request failed: {e}")
    return f"Тестовый депозит для ID {chat_id} инициирован.", 200

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
    # Запускаем приложение через socketio.run
    socketio.run(app, host="0.0.0.0", port=port)

