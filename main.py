import os
import sqlite3
import threading
from flask import Flask, request, render_template, jsonify
import telebot

# ========= Конфиги =========
# ВАЖНО: В реальном проекте храните токен в переменных окружения!
TOKEN = "8183205134:AAEJ95MtbBfYQXOej4ZBxb3GRyS1oz56qlY"
REGISTER_LINK = "https://u3.shortink.io/register?utm_campaign=825192&utm_source=affiliate&utm_medium=sr&a=PDSrNY9vG5LpeF&ac=1d&code=50START"
# URL вашего веб-приложения. Для локального теста используйте ngrok, для прода - Render/Heroku/etc.
WEB_APP_URL = "https://your-domain.onrender.com" # ЗАМЕНИТЕ НА СВОЙ АДРЕС

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
app = Flask(__name__)

# ========= Временные данные =========
# Храним язык пользователя. В проде лучше использовать базу данных типа Redis.
user_data = {}

# ========= База данных (без изменений) =========
def init_db():
    conn = sqlite3.connect("postbacks.db", check_same_thread=False)
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
    conn = sqlite3.connect("postbacks.db", check_same_thread=False)
    c = conn.cursor()
    c.execute("""INSERT INTO postbacks (event, subid, trader_id, sumdep, wdr_sum, status)
                 VALUES (?, ?, ?, ?, ?, ?)""",
              (event, subid, trader_id, sumdep, wdr_sum, status))
    conn.commit()
    conn.close()

# ========= Логика бота =========
@bot.message_handler(commands=['start'])
def start_message(message):
    # Запоминаем язык пользователя
    lang = "ru" if (message.from_user.language_code or "").startswith("ru") else "en"
    user_data[message.chat.id] = {"lang": lang}

    # Создаем кнопку для запуска Mini App
    markup = telebot.types.InlineKeyboardMarkup()
    web_app_info = telebot.types.WebAppInfo(WEB_APP_URL)
    app_button = telebot.types.InlineKeyboardButton(
        text="🚀 Открыть кабинет" if lang == "ru" else "🚀 Open App",
        web_app=web_app_info
    )
    markup.add(app_button)
    
    bot.send_message(
        message.chat.id,
        "👋 Привет! Нажми кнопку ниже, чтобы начать." if lang == "ru" else "👋 Hello! Press the button below to start.",
        reply_markup=markup
    )

# ========= Flask: эндпоинты для Mini App =========

# 1. Отдает главную HTML страницу
@app.route("/")
def index():
    return render_template("index.html")

# 2. API: Mini App будет запрашивать этот эндпоинт, чтобы понять, что показывать пользователю
@app.route("/get_user_status/<int:chat_id>")
def get_user_status(chat_id):
    conn = sqlite3.connect("postbacks.db", check_same_thread=False)
    c = conn.cursor()

    # Проверяем наличие депозита
    c.execute("SELECT sumdep FROM postbacks WHERE subid = ? AND event IN ('FTD', 'dep') ORDER BY created_at ASC LIMIT 1", (str(chat_id),))
    deposit_row = c.fetchone()

    # Проверяем наличие регистрации
    c.execute("SELECT 1 FROM postbacks WHERE subid = ? AND event = 'reg' LIMIT 1", (str(chat_id),))
    reg_row = c.fetchone()
    
    conn.close()

    status = "unregistered"
    deposit_amount = 0

    if deposit_row:
        status = "deposited"
        deposit_amount = deposit_row[0]
    elif reg_row:
        status = "registered"
    
    # Получаем язык пользователя
    lang = user_data.get(chat_id, {}).get("lang", "en")
    
    # Формируем персональную ссылку для регистрации
    referral_link = f"{REGISTER_LINK}&sub_id1={chat_id}"

    return jsonify({
        "status": status,
        "deposit_amount": deposit_amount,
        "lang": lang,
        "referral_link": referral_link
    })


# ========= Flask: обработка постбеков (без изменений) =========
@app.route("/postback", methods=["GET", "POST"])
def partner_postback():
    event = request.args.get("event")
    subid = request.args.get("subid")
    trader_id = request.args.get("trader_id")
    sumdep = request.args.get("sumdep")
    
    if not subid: return "No subid"
    try: chat_id = int(subid)
    except: return "Invalid subid"

    # Сохраняем событие в БД
    save_postback(event, subid, trader_id, sumdep)

    # Отправляем уведомление пользователю
    lang = user_data.get(chat_id, {}).get("lang", "en")

    if event == "reg":
        if lang == "ru":
            bot.send_message(chat_id, f"✅ Регистрация подтверждена! Trader ID: {trader_id}\n\nТеперь вернитесь в приложение, чтобы продолжить.")
        else:
            bot.send_message(chat_id, f"✅ Registration confirmed! Trader ID: {trader_id}\n\nPlease return to the app to continue.")
    
    elif event == "FTD":
        if lang == "ru":
            bot.send_message(chat_id, f"💰 Ваш первый депозит на ${sumdep} зачислен! Trader ID: {trader_id}\n\nОтлично, теперь можно начинать!")
        else:
            bot.send_message(chat_id, f"💰 Your first deposit of ${sumdep} is confirmed! Trader ID: {trader_id}\n\nGreat, now you can start!")

    return "OK"

# ========= Запуск =========
if __name__ == "__main__":
    init_db()

    # Запускаем бота в отдельном потоке
    threading.Thread(target=bot.infinity_polling, daemon=True).start()

    # Запускаем Flask-сервер
    # Для продакшена используйте Gunicorn или другой WSGI-сервер
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True) # debug=True для разработки









