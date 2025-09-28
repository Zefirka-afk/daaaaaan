import os
import sqlite3
import threading
from flask import Flask, request, render_template, jsonify
import telebot

# ===================================================================
# =========                   КОНФИГУРАЦИЯ                    =========
# ===================================================================
# !!! ВАЖНО: Вставьте сюда свой токен, полученный от @BotFather
TOKEN = "8369181511:AAEvwUn5gQUAXizdvvUpbP4repqU26iKQd0" 

# !!! ВАЖНО: Вставьте сюда основной URL вашего приложения с Render
# Пример: "https://your-app-name.onrender.com"
WEB_APP_URL = "https://daaaaaan.onrender.com"

# ===================================================================
# =========                   ПЕРЕВОДЫ (TEXTS)                =========
# ===================================================================
TEXTS = {
    'ru': {
        'welcome': "Привет 👋 Я бот для трейдинга!\n\nНажми на кнопку ниже, чтобы войти в свой личный кабинет и начать.",
        'my_id': "Твой Telegram ID: <b>{id}</b>",
        'reg_success': "✅ <b>Регистрация подтверждена!</b>\nВаш личный кабинет в приложении обновлен.",
        'ftd_success': "💰 <b>Первый депозит!</b>\nВы внесли <b>${sum}</b>. Данные в кабинете обновлены.",
        'dep_success': "➕ <b>Пополнение</b>\nВы пополнили счет на <b>${sum}</b>.",
        'wdr_request': "💵 <b>Запрос на вывод</b>\nСумма: <b>${sum}</b>. Статус: {status}",
        'new_event': "🔔 <b>Новое событие:</b> {event}"
    },
    'en': {
        'welcome': "Hello 👋 I'm a trading bot!\n\nPress the button below to enter your personal cabinet and get started.",
        'my_id': "Your Telegram ID: <b>{id}</b>",
        'reg_success': "✅ <b>Registration confirmed!</b>\nYour personal cabinet has been updated.",
        'ftd_success': "💰 <b>First deposit!</b>\nYou've deposited <b>${sum}</b>. Your cabinet is updated.",
        'dep_success': "➕ <b>Deposit</b>\nYou have topped up your account with <b>${sum}</b>.",
        'wdr_request': "💵 <b>Withdrawal request</b>\nAmount: <b>${sum}</b>. Status: {status}",
        'new_event': "🔔 <b>New event:</b> {event}"
    }
}
# Временное хранилище для языка пользователя. 
# Для продакшена лучше хранить язык в базе данных, привязанной к user_id.
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
    """Создает таблицу в базе данных, если она не существует."""
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
    """Сохраняет данные из постбека в базу данных."""
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
    """
    Обрабатывает команду /start, определяет язык пользователя 
    и отправляет кнопку для открытия Mini App.
    """
    lang_code = message.from_user.language_code
    lang = 'ru' if lang_code and lang_code.startswith('ru') else 'en'
    user_langs[message.chat.id] = lang  # Сохраняем язык пользователя

    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    # Передаем язык в URL Mini App
    web_app_info = telebot.types.WebAppInfo(f"{WEB_APP_URL}/app/{lang}") 
    markup.add(telebot.types.KeyboardButton("🚀 Открыть кабинет", web_app=web_app_info))
    
    bot.send_message(message.chat.id, TEXTS[lang]['welcome'], reply_markup=markup)

@bot.message_handler(commands=['myid'])
def my_id(message):
    """Отправляет пользователю его Telegram ID для отладки."""
    lang = user_langs.get(message.chat.id, 'en') # Используем сохраненный язык
    bot.send_message(message.chat.id, TEXTS[lang]['my_id'].format(id=message.chat.id))

# ===================================================================
# =========            ЛОГИКА ВЕБ-СЕРВЕРА (FLASK)             =========
# ===================================================================
@app.route("/")
def index():
    """Страница-заглушка для проверки работы веб-сервера."""
    return "Web server for Telegram Mini App is running."

@app.route("/app/<lang>")
def app_page(lang):
    """Отдает главную страницу Mini App, передавая в шаблон язык."""
    if lang not in ['ru', 'en']:
        lang = 'en'
    return render_template("app.html", lang=lang)

@app.route("/user/<int:chat_id>/data")
def user_data_api(chat_id):
    """API для фронтенда: отдает статус регистрации и историю событий."""
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
    """Принимает постбеки от партнерской сети и уведомляет пользователя на его языке."""
    data = request.args
    event, subid = data.get("event"), data.get("subid")
    trader_id, sumdep = data.get("trader_id"), data.get("sumdep")
    wdr_sum, status = data.get("wdr_sum"), data.get("status")

    if not subid: return "No subid provided", 400
    try: chat_id = int(subid)
    except (ValueError, TypeError): return "Invalid subid", 400
    
    save_postback(event, subid, trader_id, sumdep, wdr_sum, status)

    lang = user_langs.get(chat_id, 'en') # Получаем сохраненный язык пользователя
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
        # Удаляем вебхук и очищаем обновления при старте, чтобы избежать ошибки 409 Conflict
        bot.delete_webhook(drop_pending_updates=True)
        bot.infinity_polling(skip_pending=True)

    # Запускаем бота в отдельном потоке, чтобы он не блокировал веб-сервер
    threading.Thread(target=run_bot, daemon=True).start()
    
    # Запускаем веб-сервер Flask
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

