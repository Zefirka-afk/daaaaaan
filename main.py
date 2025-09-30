import os
import threading
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, render_template, jsonify
import telebot

# ========= Конфиги из переменных окружения =========
TOKEN = os.environ.get("TELEGRAM_TOKEN")
# URL будет предоставлен Render'ом после первого развертывания
WEB_APP_URL = os.environ.get("WEB_APP_URL") 
# Render предоставляет DATABASE_URL автоматически при подключении БД
DATABASE_URL = os.environ.get("DATABASE_URL")
REGISTER_LINK = "https://u3.shortink.io/register?utm_campaign=825192&utm_source=affiliate&utm_medium=sr&a=PDSrNY9vG5LpeF&ac=1d&code=50START"

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
app = Flask(__name__)

# ========= Временные данные =========
user_data = {}

# ========= База данных PostgreSQL =========
def get_db_connection():
    """Устанавливает соединение с базой данных PostgreSQL."""
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def init_db():
    """Создает таблицу, если она не существует."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS postbacks (
            id SERIAL PRIMARY KEY,
            event TEXT,
            subid TEXT,
            trader_id TEXT,
            sumdep REAL,
            wdr_sum REAL,
            status TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    c.close()
    conn.close()

def save_postback(event, subid, trader_id, sumdep=None, wdr_sum=None, status=None):
    """Сохраняет постбэк в PostgreSQL."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO postbacks (event, subid, trader_id, sumdep, wdr_sum, status)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (event, subid, trader_id, sumdep, wdr_sum, status)
    )
    conn.commit()
    c.close()
    conn.close()

# ========= Логика бота =========
@bot.message_handler(commands=['start'])
def start_message(message):
    lang = "ru" if (message.from_user.language_code or "").startswith("ru") else "en"
    user_data[message.chat.id] = {"lang": lang}

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
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/get_user_status/<int:chat_id>")
def get_user_status(chat_id):
    conn = get_db_connection()
    c = conn.cursor()

    c.execute("SELECT sumdep FROM postbacks WHERE subid = %s AND event IN ('FTD', 'dep') ORDER BY created_at ASC LIMIT 1", (str(chat_id),))
    deposit_row = c.fetchone()
    
    c.execute("SELECT 1 FROM postbacks WHERE subid = %s AND event = 'reg' LIMIT 1", (str(chat_id),))
    reg_row = c.fetchone()
    
    c.close()
    conn.close()

    status = "unregistered"
    deposit_amount = 0

    if deposit_row:
        status = "deposited"
        deposit_amount = deposit_row[0]
    elif reg_row:
        status = "registered"
    
    lang = user_data.get(chat_id, {}).get("lang", "en")
    referral_link = f"{REGISTER_LINK}&sub_id1={chat_id}"

    return jsonify({
        "status": status,
        "deposit_amount": deposit_amount,
        "lang": lang,
        "referral_link": referral_link
    })

# ========= Flask: обработка постбеков =========
@app.route("/postback", methods=["GET", "POST"])
def partner_postback():
    event = request.args.get("event")
    subid = request.args.get("subid")
    trader_id = request.args.get("trader_id")
    sumdep = request.args.get("sumdep")
    
    if not subid: return "No subid"
    try: chat_id = int(subid)
    except: return "Invalid subid"

    save_postback(event, subid, trader_id, sumdep)

    lang = user_data.get(chat_id, {}).get("lang", "en")

    if event == "reg":
        msg = f"✅ Регистрация подтверждена! Trader ID: {trader_id}\n\nТеперь вернитесь в приложение, чтобы продолжить." if lang == "ru" else f"✅ Registration confirmed! Trader ID: {trader_id}\n\nPlease return to the app to continue."
        bot.send_message(chat_id, msg)
    
    elif event == "FTD":
        msg = f"💰 Ваш первый депозит на ${sumdep} зачислен! Trader ID: {trader_id}\n\nОтлично, теперь можно начинать!" if lang == "ru" else f"💰 Your first deposit of ${sumdep} is confirmed! Trader ID: {trader_id}\n\nGreat, now you can start!"
        bot.send_message(chat_id, msg)

    return "OK"

# ========= Запуск =========
# Инициализируем БД при старте приложения
with app.app_context():
    init_db()

# Запускаем бота в отдельном потоке
threading.Thread(target=bot.infinity_polling, daemon=True).start()

# Gunicorn будет запускать 'app', поэтому этот блок не выполнится на Render
# Он остается для локального тестирования
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)







