from dotenv import load_dotenv
import os
import requests
from time import sleep
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from flask import Flask
import threading

# ✅ .env 환경변수 로드
load_dotenv()
LOGIN_ID = os.getenv("MUSINSA_ID")
LOGIN_PW = os.getenv("MUSINSA_PW")
TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
CHROME_DRIVER_PATH = os.getenv("CHROME_DRIVER_PATH")
URL = f"https://api.telegram.org/bot{TOKEN}"

# 🔁 앱 링크 → 웹 링크 리디렉션 처리
def resolve_redirected_url(short_url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(short_url, headers=headers, allow_redirects=True, timeout=5)
        if "www.musinsa.com/products/" in res.url:
            return res.url
        return None
    except:
        return None

# 🔐 로그인 및 WebDriver 객체 반환
def login_and_get_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    service = Service(CHROME_DRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)

    driver.get("https://www.musinsa.com/auth/login?referer=https%3A%2F%2Fwww.musinsa.com%2Fmypage")

    try:
        id_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='아이디']"))
        )
        id_input.send_keys(LOGIN_ID)
        pw_input = driver.find_element(By.CSS_SELECTOR, "input[placeholder='비밀번호']")
        pw_input.send_keys(LOGIN_PW)
        login_btn = driver.find_element(By.CLASS_NAME, "login-v2-button--highlight")
        login_btn.click()
        sleep(2)
    except Exception as e:
        print("회원 로그인 실패:", e)
        driver.save_screenshot("login_fail.png")
        driver.quit()
        return None

    return driver

# 플래시 상품 정보 추출
def extract_product_info(url):
    driver = login_and_get_driver()
    if not driver:
        return "상품명 없음", "정가 없음", "할인가 없음", "실구매가 없음"

    driver.get(url)
    sleep(2)

    try:
        name = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "span.text-title_18px_med.exqQRL"))
        ).text.strip()
    except:
        name = "상품명 없음"

    try:
        origin_price = driver.find_element(By.CSS_SELECTOR, "span.text-body_13px_med.line-through").text.strip()
    except:
        origin_price = "정가 없음"

    try:
        discount_price = driver.find_element(By.CSS_SELECTOR, "span.text-title_18px_semi.text-black").text.strip()
    except:
        discount_price = "할인가 없음"

    try:
        real_price = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, '//span[text()="최대혜택가"]/preceding::span[1]'))
        ).text.strip()
    except:
        real_price = "실구매가 없음"

    driver.quit()
    return name, origin_price, discount_price, real_price

# 텔레그램 메시지 전송
def send_message(chat_id, text):
    requests.post(f"{URL}/sendMessage", data={"chat_id": chat_id, "text": text})

# 번역 버스 반응 룸
def run_bot():
    print("번역 복사 발번 중...")
    last_update_id = None

    while True:
        try:
            params = {"timeout": 5}
            if last_update_id:
                params["offset"] = last_update_id + 1

            res = requests.get(f"{URL}/getUpdates", params=params, timeout=10)
            updates = res.json().get("result", [])

            if not updates:
                sleep(2)
                continue

            for update in updates:
                update_id = update["update_id"]
                last_update_id = update_id

                message = update.get("message", {})
                text = message.get("text", "").strip()
                chat_id = message.get("chat", {}).get("id")

                if "musinsa" in text:
                    url = text
                    if "musinsaapp.page.link" in url:
                        redirected = resolve_redirected_url(url)
                        if not redirected:
                            send_message(chat_id, "링크를 웹 주소로 변환하지 못했어요. \n웹 링크를 직접 보내주세요.")
                            continue
                        url = redirected

                    name, origin, discount, real = extract_product_info(url)

                    msg = f"상품 정보\n상품명: {name}\n정가: {origin}\n할인가: {discount}\n실구매가: {real}"
                    send_message(chat_id, msg)

        except Exception as e:
            print("오류 발생:", e)
            sleep(2)

# 🌐 Flask server for Render app detection
app = Flask(__name__)

@app.route('/')
def index():
    return "Telegram bot is running!"

def start_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# ✅ Flask + 봇 병렬 실행
if __name__ == "__main__":
    t1 = threading.Thread(target=run_bot)
    t1.start()
    start_flask()
