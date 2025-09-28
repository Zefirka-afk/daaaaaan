import os
import sqlite3
import threading
from flask import Flask, request, render_template
import telebot

# ========= Конфиги =========
TOKEN = "8369181511:AAHglPmAnHRDqsuTAghaCtIhIQ58iVHukqI"  
REGISTER_LINK = "https://u3.shortink.io/register?utm_campaign=825192&utm_source=affiliate&utm_medium=sr&a=PDSrNY9vG5LpeF&ac=1d&code=50START"

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
app = Flask(__name__)

# ========= Временные данные =========
user_data = {}

# ========= База данных =========
def init_db():
    conn = sqlite3.connect("postbacks.db")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS postbacks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event TEXT,
                    subid TEXT,
                    trader_id TEXT,
                    sumdep REAL,
                    wdr_sum REAL,
                    status TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )""")
    conn.commit()
    conn.close()

def save_postback(event, subid, trader_id, sumdep=None, wdr_sum=None, status=None):
    conn = sqlite3.connect("postbacks.db")
    c = conn.cursor()
    c.execute("""INSERT INTO postbacks (event, subid, trader_id, sumdep, wdr_sum, status)
                 VALUES (?, ?, ?, ?, ?, ?)""",
              (event, subid, trader_id, sumdep, wdr_sum, status))
    conn.commit()
    conn.close()

# ========= Логика бота =========
@bot.message_handler(commands=['start'])
def start_message(message):
    lang = "ru" if (message.from_user.language_code or "").startswith("ru") else "en"
    user_data[message.chat.id] = {"lang": lang, "registered": False}

    if lang == "ru":
        greet = "Привет 👋 Я бот для трейдинга!\nВот твоя персональная ссылка для регистрации:"
        explain = "Перейди по ссылке и зарегистрируйся.\n➡️ После регистрации я пришлю твой ID и депозит!"
    else:
        greet = "Hello 👋 I am a trading bot!\nHere is your personal registration link:"
        explain = "Follow the link to register.\n➡️ After confirmation, I'll send you your ID and deposit!"

    ref_link = f"{REGISTER_LINK}&sub_id1={message.chat.id}"
    bot.send_message(message.chat.id, f"{greet}\n\n<b>{ref_link}</b>\n\n{explain}")

@bot.message_handler(commands=['myid'])
def my_id(message):
    bot.send_message(message.chat.id, f"Твой Telegram ID: <b>{message.chat.id}</b>")

# кнопка открытия mini app
@bot.message_handler(commands=['app'])
def open_app(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    # !!! ВАЖНО: Замените 'https://your-domain.onrender.com' на реальный URL вашего веб-сервера после развертывания
    web_app_info = telebot.types.WebAppInfo("https://your-domain.onrender.com/app")  
    markup.add(telebot.types.KeyboardButton("🚀 Открыть кабинет", web_app=web_app_info))
    bot.send_message(message.chat.id, "Жми ниже, чтобы открыть личный кабинет:", reply_markup=markup)

# ========= Flask: страница мини‑аппа =========
@app.route("/app")
def app_page():
    # Эта функция теперь будет корректно рендерить ваш HTML-файл
    return render_template("app.html")

# для подгрузки событий пользователя в мини‑аппе
@app.route("/user/<int:chat_id>/events")
def user_events(chat_id):
    conn = sqlite3.connect("postbacks.db")
    c = conn.cursor()
    c.execute("SELECT event, sumdep, wdr_sum, status, created_at FROM postbacks WHERE subid = ?", (str(chat_id),))
    rows = c.fetchall()
    conn.close()
    return {"events": rows}

# ========= Flask: обработка постбеков =========
@app.route("/postback", methods=["GET", "POST"])
def partner_postback():
    event = request.args.get("event")
    subid = request.args.get("subid")
    trader_id = request.args.get("trader_id")
    sumdep = request.args.get("sumdep")
    wdr_sum = request.args.get("wdr_sum")
    status = request.args.get("status")

    if not subid:
        return "No subid"
    try:
        chat_id = int(subid)
    except:
        return "Invalid subid"

    save_postback(event, subid, trader_id, sumdep, wdr_sum, status)

    userdata = user_data.get(chat_id, {"lang": "en", "registered": False})
    lang = userdata["lang"]

    if event == "reg":
        userdata["registered"] = True
        bot.send_message(chat_id, "✅ Регистрация подтверждена!\nTrader ID: " + str(trader_id))

    elif event == "FTD":
        userdata["registered"] = True
        bot.send_message(chat_id, f"💰 Первый депозит ${sumdep}! Trader ID: {trader_id}")

    elif event == "dep":
        bot.send_message(chat_id, f"➕ Пополнение депозита на ${sumdep}")

    elif event == "wdr":
        bot.send_message(chat_id, f"💵 Запрос на вывод: ${wdr_sum}")

    else:
        bot.send_message(chat_id, f"📢 Событие: {event}, Trader: {trader_id}, Sum: {sumdep}")

    return "OK"

# ========= Запуск =========
if __name__ == "__main__":
    init_db()

    def run_bot():
        bot.infinity_polling()

    threading.Thread(target=run_bot).start()

    port = int(os.environ.get("PORT", 8080))

    app.run(host="0.0.0.0", port=port)

