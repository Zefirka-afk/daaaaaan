import os
import sqlite3
import threading
from flask import Flask, request, render_template, jsonify
import telebot
import random
import time

# =====================================================================
# ========= КОНФИГУРАЦИЯ =
# ===================================================================
TOKEN = "8441945670:AAFTTAym0douRv4mUnFfDlu3k1eNsBATPu8"
WEB_APP_URL = "https://daaaaaan.onrender.com"

# ===================================================================
# ========= ПЕРЕВОДЫ (TEXTS) =========
# ===================================================================
TEXTS = {
    'ru': {
        'welcome': "Привет 👋 Я бот для трейдинга!\n\nНажми на кнопку <b>Меню</b> слева внизу, чтобы открыть свой личный кабинет.",
        'my_id': "Твой Telegram ID: <b>{id}</b>",
        'reg_success': "✅ <b>Регистрация подтверждена!</b>\nВаш личный кабинет в приложении обновлен.",
        'ftd_success': "💰 <b>Первый депозит!</b>\nВы внесли <b>{sum}</b>. Данные в кабинете обновлены.",
        'dep_success': "➕ <b>Пополнение</b>\nВы пополнили счет на <b>{sum}</b>. Данные в кабинете обновлены.",
        'wdr_request': "💵 <b>Запрос на вывод</b>\nСумма: <b>{sum}</b>. Статус: {status}",
        'new_event': "🔔 <b>Новое событие:</b> {event}"
    },
    'en': {
        'welcome': "Hello 👋 I'm a trading bot!\n\nPress the <b>Menu</b> button in the bottom left to open your personal cabinet.",
        'my_id': "Your Telegram ID: <b>{id}</b>",
        'reg_success': "✅ <b>Registration confirmed!</b>\nYour personal cabinet has been updated.",
        'ftd_success': "💰 <b>First deposit!</b>\nYou've deposited <b>{sum}</b>. Your cabinet is updated.",
        'dep_success': "➕ <b>Deposit</b>\nYou have topped up your account with <b>{sum}</b>.",
        'wdr_request': "💵 <b>Withdrawal request</b>\nAmount: <b>{sum}</b>. Status: {status}",
        'new_event': "🔔 <b>New event:</b> {event}"
    }
}

# ===================================================================
# ========= ИНИЦИАЛИЗАЦИЯ БОТА И ВЕБ-СЕРВЕРА =========
# ===================================================================
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
app = Flask(__name__)

# ===================================================================
# ========= ЛОГИКА РАБОТЫ С БАЗОЙ ДАННЫХ =========
# ===================================================================
DB_NAME = "data.db"

def init_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS postbacks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event TEXT, subid TEXT, trader_id TEXT,
        sumdep REAL, wdr_sum REAL, status TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        chat_id INTEGER PRIMARY KEY,
        lang TEXT
    )""")
    conn.commit()
    conn.close()

def save_postback(event, subid, trader_id, sumdep=None, wdr_sum=None, status=None):
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    c = conn.cursor()
    c.execute("""INSERT INTO postbacks (event, subid, trader_id, sumdep, wdr_sum, status)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (event, subid, trader_id, sumdep, wdr_sum, status))
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
    c.execute("""
        INSERT INTO users (chat_id, lang) VALUES (?, ?)
        ON CONFLICT(chat_id) DO UPDATE SET lang=excluded.lang
    """, (message.chat.id, lang))
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

# ===================================================================
# ========= ЛОГИКА ВЕБ-СЕРВЕРА (FLASK) =========
# ===================================================================
@app.route("/")
def index():
    return "Web server for Telegram Mini App is running."

@app.route("/app")
def app_page():
    return render_template("app.html")

@app.route("/user/<int:chat_id>/data")
def user_data_api(chat_id):
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute("SELECT 1 FROM postbacks WHERE subid = ? AND event = 'reg' LIMIT 1", (str(chat_id),))
    is_registered = c.fetchone() is not None
    
    c.execute("SELECT event, sumdep, wdr_sum, status, created_at FROM postbacks WHERE subid = ? ORDER BY created_at DESC", (str(chat_id),))
    events = [list(row) for row in c.fetchall()]
        
    conn.close()
    return jsonify({"is_registered": is_registered, "events": events})

@app.route("/postback", methods=["GET", "POST"])
def partner_postback():
    data = request.args
    event = data.get("event")
    subid = data.get("subid")
    trader_id = data.get("trader_id")
    sumdep = data.get("sumdep")
    wdr_sum = data.get("wdr_sum")
    status = data.get("status")

    if not subid:
        return "No subid provided", 400
    try:
        chat_id = int(subid)
    except (ValueError, TypeError):
        return "Invalid subid", 400

    save_postback(event, subid, trader_id, sumdep, wdr_sum, status)

    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT lang FROM users WHERE chat_id = ?", (chat_id,))
    result = c.fetchone()
    conn.close()
    
    lang = result[0] if result else 'en'
    
    message_text = ""
    
    if event == "reg": message_text = TEXTS[lang]['reg_success']
    elif event == "FTD": message_text = TEXTS[lang]['ftd_success'].format(sum=sumdep)
    elif event == "dep": message_text = TEXTS[lang]['dep_success'].format(sum=sumdep)
    elif event == "wdr": message_text = TEXTS[lang]['wdr_request'].format(sum=wdr_sum, status=status)
    else: message_text = TEXTS[lang]['new_event'].format(event=event)

    if message_text:
        try:
            bot.send_message(chat_id, message_text)
        except Exception as e:
            print(f"Failed to send message to {chat_id}: {e}")

    return "OK", 200

# ===================================================================
# ========= ТЕСТОВЫЕ МАРШРУТЫ =========
# ===================================================================

# НОВЫЙ МАРШРУТ ДЛЯ ТЕСТА РЕГИСТРАЦИИ
@app.route("/test_registration")
def add_test_registration():
    # Пример использования: /test_registration?chat_id=1234567
    chat_id_str = request.args.get("chat_id")

    if not chat_id_str:
        return "Ошибка: Пожалуйста, укажите 'chat_id' в параметрах URL.", 400

    try:
        chat_id = int(chat_id_str)
    except ValueError:
        return "Ошибка: 'chat_id' должен быть числом.", 400

    # Имитируем событие 'reg'
    save_postback(
        event="reg",
        subid=str(chat_id),
        trader_id=f"test_trader_{chat_id}", # Генерируем уникальный тестовый ID трейдера
        sumdep=None,
        wdr_sum=None,
        status=None
    )

    # Оповещаем пользователя в боте
    try:
        conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        c = conn.cursor()
        c.execute("SELECT lang FROM users WHERE chat_id = ?", (chat_id,))
        result = c.fetchone()
        conn.close()
        lang = result[0] if result else 'en'
        
        message_text = TEXTS[lang]['reg_success']
        bot.send_message(chat_id, message_text)
    except Exception as e:
        print(f"Не удалось отправить тестовое сообщение о регистрации {chat_id}: {e}")

    return f"Успешно создана тестовая регистрация для пользователя с ID {chat_id}.<br>Закройте и снова откройте Mini App, чтобы увидеть изменения.", 200


@app.route("/test_deposit")
def add_test_deposit():
    # Пример: /test_deposit?chat_id=1234567&sum=50
    chat_id_str = request.args.get("chat_id")
    sum_str = request.args.get("sum", "50")

    if not chat_id_str:
        return "Ошибка: Пожалуйста, укажите 'chat_id' в параметрах URL.", 400

    try:
        chat_id = int(chat_id_str)
        deposit_sum = float(sum_str)
    except ValueError:
        return "Ошибка: 'chat_id' и 'sum' должны быть числами.", 400

    # Имитируем событие 'FTD'
    save_postback(
        event="FTD",
        subid=str(chat_id),
        trader_id=f"test_trader_{chat_id}",
        sumdep=deposit_sum,
        wdr_sum=None,
        status="approved"
    )

    try:
        conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        c = conn.cursor()
        c.execute("SELECT lang FROM users WHERE chat_id = ?", (chat_id,))
        result = c.fetchone()
        conn.close()
        lang = result[0] if result else 'en'
        
        message_text = TEXTS[lang]['ftd_success'].format(sum=deposit_sum)
        bot.send_message(chat_id, message_text)
    except Exception as e:
        print(f"Не удалось отправить тестовое сообщение о депозите {chat_id}: {e}")

    return f"Успешно создан тестовый депозит в размере ${deposit_sum} для пользователя с ID {chat_id}.<br>Закройте и снова откройте Mini App, чтобы увидеть изменения.", 200


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
    app.run(host="0.0.0.0", port=port)






