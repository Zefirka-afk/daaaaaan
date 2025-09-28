import os
import sqlite3
import threading
from flask import Flask, request, render_template, jsonify
import telebot

# ===================================================================
# =========                   КОНФИГУРАЦИЯ                    =========
# ===================================================================
# !!! ВАЖНО: Вставьте сюда свой токен, полученный от @BotFather
TOKEN = "8183205134:AAEJ95MtbBfYQXOej4ZBxb3GRyS1oz56qlY" 
#REGISTER_LINK = "https://u3.shortink.io/register?utm_campaign=825192&utm_source=affiliate&utm_medium=sr&a=PDSrNY9vG5LpeF&ac=1d&code=50START"
# !!! ВАЖНО: Вставьте сюда основной URL вашего приложения с Render
# Пример: "https://your-app-name.onrender.com"
WEB_APP_URL = "https://daaaaaan.onrender.com"

# ===================================================================
# =========      ИНИЦИАЛИЗАЦИЯ БОТА И ВЕБ-СЕРВЕРА           =========
# ===================================================================
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
app = Flask(__name__)

# ===================================================================
# =========            ЛОГИКА РАБОТЫ С БАЗОЙ ДАННЫХ           =========
# ===================================================================
# Инициализация базы данных SQLite
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

# Сохранение нового события (postback) в базу данных
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
# Обработчик команды /start
@bot.message_handler(commands=['start'])
def start_message(message):
    """Отправляет приветственное сообщение с кнопкой для открытия Mini App."""
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    web_app_info = telebot.types.WebAppInfo(f"{WEB_APP_URL}/app")
    markup.add(telebot.types.KeyboardButton("🚀 Открыть кабинет", web_app=web_app_info))
    
    bot.send_message(
        message.chat.id, 
        "Привет 👋 Я бот для трейдинга!\n\nНажми на кнопку ниже, чтобы войти в свой личный кабинет и начать.", 
        reply_markup=markup
    )

# Обработчик команды /myid для отладки
@bot.message_handler(commands=['myid'])
def my_id(message):
    """Отправляет пользователю его Telegram ID."""
    bot.send_message(message.chat.id, f"Твой Telegram ID: <b>{message.chat.id}</b>")

# ===================================================================
# =========            ЛОГИКА ВЕБ-СЕРВЕРА (FLASK)             =========
# ===================================================================

# 1. Страница-заглушка для проверки работы сервера
@app.route("/")
def index():
    """Просто сообщает, что веб-сервер работает."""
    return "Web server for Telegram Mini App is running."

# 2. Главная страница Mini App
@app.route("/app")
def app_page():
    """Отдает HTML-файл для отображения в Mini App."""
    return render_template("app.html")

# 3. API для получения данных пользователя
@app.route("/user/<int:chat_id>/data")
def user_data_api(chat_id):
    """
    API, которое вызывается из JavaScript в Mini App.
    Проверяет, зарегистрирован ли пользователь, и отдает историю его событий.
    """
    conn = sqlite3.connect("postbacks.db", check_same_thread=False)
    c = conn.cursor()
    
    # Проверяем, есть ли событие 'reg' для этого пользователя
    c.execute("SELECT 1 FROM postbacks WHERE subid = ? AND event = 'reg' LIMIT 1", (str(chat_id),))
    is_registered = c.fetchone() is not None
    
    events = []
    if is_registered:
        # Если пользователь зарегистрирован, получаем все его события, сортируя по дате (новые сверху)
        c.execute("SELECT event, sumdep, wdr_sum, status, created_at FROM postbacks WHERE subid = ? ORDER BY created_at DESC", (str(chat_id),))
        events = c.fetchall()
        
    conn.close()
    
    # Возвращаем данные в формате JSON
    return jsonify({"is_registered": is_registered, "events": events})

# 4. Обработчик Postback'ов от партнерской сети
@app.route("/postback", methods=["GET", "POST"])
def partner_postback():
    """Принимает данные от партнерской сети, сохраняет их и уведомляет пользователя."""
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

    # Сохраняем событие в базу данных
    save_postback(event, subid, trader_id, sumdep, wdr_sum, status)

    # Отправляем уведомление пользователю через бота
    message_text = ""
    if event == "reg":
        message_text = "✅ <b>Регистрация подтверждена!</b>\nВаш личный кабинет в приложении обновлен."
    elif event == "FTD":
        message_text = f"💰 <b>Первый депозит!</b>\nВы внесли <b>${sumdep}</b>. Данные в кабинете обновлены."
    elif event == "dep":
        message_text = f"➕ <b>Пополнение</b>\nВы пополнили счет на <b>${sumdep}</b>."
    elif event == "wdr":
        message_text = f"💵 <b>Запрос на вывод</b>\nСумма: <b>${wdr_sum}</b>. Статус: {status}"
    else:
        # Уведомление о любом другом событии
        message_text = f"🔔 <b>Новое событие:</b> {event}"

    if message_text:
        try:
            bot.send_message(chat_id, message_text)
        except Exception as e:
            print(f"Failed to send message to {chat_id}: {e}")

    return "OK", 200

# ===================================================================
# =========                   ЗАПУСК ПРИЛОЖЕНИЯ               =========
# ===================================================================
if __name__ == "__main__":
    # Создаем файл и таблицу БД, если их нет
    init_db()

    # Запускаем бота в отдельном потоке
    def run_bot():
        print("Starting bot polling...")
        # Удаляем вебхук и очищаем обновления, чтобы избежать ошибки 409 Conflict
        bot.delete_webhook(drop_pending_updates=True)
        bot.infinity_polling(skip_pending=True)

    threading.Thread(target=run_bot).start()
    
    # Запускаем веб-сервер Flask
    # Render.com предоставляет переменную окружения PORT
    port = int(os.environ.get("PORT", 8080))
    # host='0.0.0.0' нужен, чтобы сервер был доступен извне Docker-контейнера на Render
    app.run(host="0.0.0.0", port=port)
