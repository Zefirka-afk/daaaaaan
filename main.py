import os
import sqlite3
import threading
from flask import Flask, request, render_template, jsonify # Добавили jsonify
import telebot

# ========= Конфиги =========
TOKEN = "8369181511:AAEvwUn5gQUAXizdvvUpbP4repqU26iKQd0" # Убедитесь, что используете правильный токен
REGISTER_LINK = "https://u3.shortink.io/register?utm_campaign=825192&utm_source=affiliate&utm_medium=sr&a=PDSrNY9vG5LpeF&ac=1d&code=50START"
# !!! ВАЖНО: URL вашего развернутого приложения
WEB_APP_URL = "https://daaaaaan.onrender.com" 

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
app = Flask(__name__)

# ========= База данных (без изменений) =========
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

# ========= Логика бота (СИЛЬНО УПРОЩЕНА) =========
@bot.message_handler(commands=['start'])
def start_message(message):
    # Теперь бот просто предлагает открыть приложение
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    web_app_info = telebot.types.WebAppInfo(f"{WEB_APP_URL}/app")
    markup.add(telebot.types.KeyboardButton("🚀 Открыть кабинет", web_app=web_app_info))
    
    bot.send_message(
        message.chat.id, 
        "Привет 👋 Я бот для трейдинга!\n\nНажми на кнопку ниже, чтобы войти в свой личный кабинет и начать.", 
        reply_markup=markup
    )

# Команда /myid все еще полезна для отладки
@bot.message_handler(commands=['myid'])
def my_id(message):
    bot.send_message(message.chat.id, f"Твой Telegram ID: <b>{message.chat.id}</b>")


# ========= Flask: страницы и API =========

# Страница-заглушка для корневого URL
@app.route("/")
def index():
    return "Web server for Telegram Mini App is running."

# Страница самого Mini App
@app.route("/app")
def app_page():
    return render_template("app.html")

# API для получения данных пользователя (МОДИФИЦИРОВАНО)
@app.route("/user/<int:chat_id>/data") # Изменили URL для ясности
def user_data_api(chat_id):
    conn = sqlite3.connect("postbacks.db")
    c = conn.cursor()
    # Проверяем, есть ли событие 'reg' для этого пользователя
    c.execute("SELECT 1 FROM postbacks WHERE subid = ? AND event = 'reg' LIMIT 1", (str(chat_id),))
    is_registered = c.fetchone() is not None
    
    events = []
    if is_registered:
        c.execute("SELECT event, sumdep, wdr_sum, status, created_at FROM postbacks WHERE subid = ? ORDER BY created_at DESC", (str(chat_id),))
        events = c.fetchall()
        
    conn.close()
    # Возвращаем и статус регистрации, и события
    return jsonify({"is_registered": is_registered, "events": events})

# ========= Flask: обработка постбеков (почти без изменений) =========
@app.route("/postback", methods=["GET", "POST"])
def partner_postback():
    event = request.args.get("event")
    subid = request.args.get("subid")
    # ... (остальной код обработки постбека остается таким же) ...
    # Просто убедитесь, что бот отправляет уведомления, это полезно
    
    # ... (весь ваш код из этой функции)
    
    if not subid:
        return "No subid", 400
    try:
        chat_id = int(subid)
    except (ValueError, TypeError):
        return "Invalid subid", 400

    save_postback(event, subid, trader_id, sumdep, wdr_sum, status)

    if event == "reg":
        bot.send_message(chat_id, "✅ Регистрация подтверждена! Ваш личный кабинет обновлен.")
    elif event == "FTD":
        bot.send_message(chat_id, f"💰 Вы внесли первый депозит на ${sumdep}! Данные в кабинете обновлены.")
    # ... и так далее для других событий
    
    return "OK"

# ========= Запуск =========
if __name__ == "__main__":
    init_db()

    def run_bot():
        # Добавим очистку ожидающих обновлений, чтобы избежать ошибки 409
        bot.delete_webhook(drop_pending_updates=True) 
        bot.infinity_polling()

    threading.Thread(target=run_bot).start()

    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
