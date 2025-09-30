# parser.py
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

def fetch_high_payout_pairs():
    """
    Запускает Selenium, логинится на Pocket Option и парсит валютные пары с выплатой 92%.
    """
    # --- ВАШИ УЧЕТНЫЕ ДАННЫЕ ---
    # !!! ВАЖНО: Замените значения ниже на ваши реальные логин и пароль
    login_email = "revakina1955@gmail.com"
    login_password = "sos112233"

    if login_email == "ВАШ_ЛОГИН@EMAIL.COM" or login_password == "ВАШ_СУПЕР_СЕКРЕТНЫЙ_ПАРОЛЬ":
        print("Ошибка: Пожалуйста, укажите ваши реальные логин и пароль в файле parser.py")
        return []

    # --- Настройка опций для запуска Chrome в headless-режиме на сервере ---
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")

    # --- Инициализация драйвера ---
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        print("Драйвер Chrome успешно запущен.")
    except Exception as e:
        print(f"Ошибка при инициализации драйвера Selenium: {e}")
        return []
        
    found_pairs = []
    
    try:
        # 1. Открываем страницу входа
        driver.get("https://pocketoption.com/ru/login/")
        print("Страница входа открыта.")

        # 2. Ждем загрузки формы, вводим данные и логинимся
        wait = WebDriverWait(driver, 20)
        
        email_input = wait.until(EC.presence_of_element_located((By.NAME, "email")))
        email_input.send_keys(login_email)
        print("Email введен.")
        
        password_input = driver.find_element(By.NAME, "password")
        password_input.send_keys(login_password)
        print("Пароль введен.")

        login_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Войти')]")
        login_button.click()
        print("Кнопка 'Войти' нажата.")

        # 3. Ждем успешной загрузки кабинета
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a.btn.deposit-btn")))
        print("Успешный вход в кабинет.")
        
        time.sleep(5) 

        # 4. Парсим данные
        asset_elements = driver.find_elements(By.CSS_SELECTOR, "li.menu-item")
        print(f"Найдено {len(asset_elements)} элементов активов.")

        for asset in asset_elements:
            try:
                pair_name_element = asset.find_element(By.CSS_SELECTOR, "span.asset-name")
                pair_name = pair_name_element.text.strip()

                payout_element = asset.find_element(By.CSS_SELECTOR, "span.asset-val")
                payout_text = payout_element.text.strip()
                
                if '%' in payout_text:
                    payout_value = int(payout_text.replace('%', ''))
                    if payout_value == 92:
                        print(f"Найдена подходящая пара: {pair_name} с выплатой {payout_value}%")
                        found_pairs.append(pair_name)
            except Exception:
                continue
                
    except Exception as e:
        print(f"Произошла ошибка во время парсинга: {e}")
        driver.save_screenshot("error_screenshot.png")
    
    finally:
        driver.quit()
        print("Драйвер закрыт.")

    return found_pairs
