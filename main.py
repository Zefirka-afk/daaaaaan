import os
import sqlite3
import threading
from flask import Flask, request, render_template, jsonify
import telebot

# ===================================================================
# =========                   КОНФИГУРАЦИЯ                    =========
# ===================================================================
# !!! ВАЖНО: Вставьте сюда свой токен, полученный от @BotFather
TOKEN = "8369181511:AAFVk4TtFaoqx9-K1CUkf901P5xGAMcmMDA" 

# !!! ВАЖНО: Вставьте сюда основной URL вашего приложения с Render
# Пример: "https://your-app-name.onrender.com"
WEB_APP_URL = "https://daaaaaan.onrender.com"

# ===================================================================
# =========                   ПЕРЕВОДЫ (TEXTS)                =========
# ===================================================================
TEXTS = {
    'ru': {
        'welcome': "Привет 👋 Я бот для трейдинга!\n\nНажми на кнопку <b>Меню</b> слева внизу, чтобы открыть свой личный кабинет.",
        'my_id': "Твой Telegram ID: <b>{id}</b>",
        'reg_success': "✅ <b>Регистрация подтверждена!</b>\nВаш личный кабинет в приложении обновлен.",
        'ftd_success': "💰 <b>Первый депозит!</b>\nВы внесли <b>${sum}</b>. Данные в кабинете обновлены.",
        'dep_success': "➕ <b>Пополнение</b>\nВы пополнили счет на <b>${sum}</b>.",
        'wdr_request': "💵 <b>Запрос на вывод</b>\nСумма: <b>${sum}</b>. Статус: {status}",
        'new_event': "🔔 <b>Новое событие:</b> {event}"
    },
    'en': {
        'welcome': "Hello 👋 I'm a trading bot!\n\nPress the <b>Menu</b> button in the bottom left to open your personal cabinet.",
        'my_id': "Your Telegram ID: <b>{id}</b>",
        'reg_success': "✅ <b>Registration confirmed!</b>\nYour personal cabinet has been updated.",
        'ftd_success': "💰 <b>First deposit!</b>\nYou've deposited <b>${sum}</b>. Your cabinet is updated.",
        'dep_success': "➕ <b>Deposit</b>\nYou have topped up your account with <b>${sum}</b>.",
        'wdr_request': "💵 <b>Withdrawal request</b>\nAmount: <b>${sum}</b>. Status: {status}",
        'new_event': "🔔 <b>New event:</b> {event}"
    }
}
# Временное хранилище для языка пользователя.
user_langs = {}

# ===================================================================
# =========      ИНИЦИАЛИЗАЦИЯ БОТА И ВЕБ-СЕРВЕРА           =========
# ===================================================================
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
app = Flask(__name__)

# ===================================================================
# =========            ЛОГИКА РАБОТЫ С БАЗОЙ ДАННЫХ           =========
# ===================================================================
def init_db():
    conn = sqlite3.connect("postbacks.db", check_same_thread=False)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS postbacks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event TEXT, subid TEXT, trader_id TEXT,
                    sumdep REAL, wdr_sum REAL, status TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )""")
    conn.commit()
    conn.close()

def save_postback(event, subid, trader_id, sumdep=None, wdr_sum=None, status=None):
    conn = sqlite3.connect("postbacks.db", check_same_thread=False)
    c = conn.cursor()
    c.execute("""INSERT INTO postbacks (event, subid, trader_id, sumdep, wdr_sum, status)
                 VALUES (?, ?, ?, ?, ?, ?)""",
              (event, subid, trader_id, sumdep, wdr_sum, status))
    conn.commit()
    conn.close()

# ===================================================================
# =========                  ЛОГИКА ТЕЛЕГРАМ-БОТА             =========
# ===================================================================
@bot.message_handler(commands=['start'])
def start_message(message):
    lang_code = message.from_user.language_code
    lang = 'ru' if lang_code and lang_code.startswith('ru') else 'en'
    user_langs[message.chat.id] = lang

    # УБИРАЕМ большую кнопку ReplyKeyboardMarkup. 
    # Теперь пользователь будет использовать кнопку "Меню", настроенную в @BotFather.
    bot.send_message(message.chat.id, TEXTS[lang]['welcome'])

@bot.message_handler(commands=['myid'])
def my_id(message):
    lang = user_langs.get(message.chat.id, 'en')
    bot.send_message(message.chat.id, TEXTS[lang]['my_id'].format(id=message.chat.id))

# ===================================================================
# =========            ЛОГИКА ВЕБ-СЕРВЕРА (FLASK)             =========
# ===================================================================
@app.route("/")
def index():
    return "Web server for Telegram Mini App is running."

# Упрощенный маршрут. Язык теперь определяется на стороне фронтенда (в app.html).
@app.route("/app")
def app_page():
    return render_template("app.html")

@app.route("/user/<int:chat_id>/data")
def user_data_api(chat_id):
    conn = sqlite3.connect("postbacks.db", check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT 1 FROM postbacks WHERE subid = ? AND event = 'reg' LIMIT 1", (str(chat_id),))
    is_registered = c.fetchone() is not None
    events = []
    if is_registered:
        c.execute("SELECT event, sumdep, wdr_sum, status, created_at FROM postbacks WHERE subid = ? ORDER BY created_at DESC", (str(chat_id),))
        events = c.fetchall()
    conn.close()
    return jsonify({"is_registered": is_registered, "events": events})

@app.route("/postback", methods=["GET", "POST"])
def partner_postback():
    data = request.args
    event, subid = data.get("event"), data.get("subid")
    trader_id, sumdep = data.get("trader_id"), data.get("sumdep")
    wdr_sum, status = data.get("wdr_sum"), data.get("status")

    if not subid: return "No subid provided", 400
    try: chat_id = int(subid)
    except (ValueError, TypeError): return "Invalid subid", 400
    
    save_postback(event, subid, trader_id, sumdep, wdr_sum, status)

    lang = user_langs.get(chat_id, 'en')
    message_text = ""
    if event == "reg": message_text = TEXTS[lang]['reg_success']
    elif event == "FTD": message_text = TEXTS[lang]['ftd_success'].format(sum=sumdep)
    elif event == "dep": message_text = TEXTS[lang]['dep_success'].format(sum=sumdep)
    elif event == "wdr": message_text = TEXTS[lang]['wdr_request'].format(sum=wdr_sum, status=status)
    else: message_text = TEXTS[lang]['new_event'].format(event=event)

    if message_text:
        try: bot.send_message(chat_id, message_text)
        except Exception as e: print(f"Failed to send message to {chat_id}: {e}")

    return "OK", 200

# ===================================================================
# =========                   ЗАПУСК ПРИЛОЖЕНИЯ               =========
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


