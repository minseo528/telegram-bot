import os
import threading
import requests
from flask import Flask
from bs4 import BeautifulSoup
from time import sleep
from dotenv import load_dotenv

# ✅ .env 로드
load_dotenv()
LOGIN_ID = os.getenv("MUSINSA_ID")
LOGIN_PW = os.getenv("MUSINSA_PW")
TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
URL = f"https://api.telegram.org/bot{TOKEN}"

# ✅ Flask 앱
app = Flask(__name__)

@app.route('/')
def index():
    return "Telegram bot is running!"

# ✅ Musinsa 로그인 및 세션 생성
def get_login_session():
    session = requests.Session()
    headers = {"User-Agent": "Mozilla/5.0"}

    # 1단계: 로그인 페이지 접속 → CSRF 토큰 추출
    login_page = session.get("https://www.musinsa.com/member/login", headers=headers)
    soup = BeautifulSoup(login_page.text, 'html.parser')
    csrf_token = soup.find("input", {"name": "csrf_token"})
    token_value = csrf_token['value'] if csrf_token else None

    # 2단계: 로그인 요청
    data = {
        "id": LOGIN_ID,
        "pw": LOGIN_PW,
        "referer": "https://www.musinsa.com/",
        "isSave": "true",
        "csrf_token": token_value
    }

    res = session.post("https://www.musinsa.com/member/login_check", data=data, headers=headers)
    if "logout" in res.text.lower():  # 간단한 로그인 성공 체크
        return session
    else:
        return None

# ✅ 상품 정보 추출
def extract_product_info(url):
    session = get_login_session()
    if not session:
        return "상품명 없음", "정가 없음", "할인가 없음", "실구매가 없음"

    headers = {"User-Agent": "Mozilla/5.0"}
    res = session.get(url, headers=headers)
    soup = BeautifulSoup(res.text, 'html.parser')

    try:
        name = soup.select_one("span.product_title").get_text(strip=True)
    except:
        name = "상품명 없음"

    try:
        origin_price = soup.select_one("span.product_article_price .price").get_text(strip=True)
    except:
        origin_price = "정가 없음"

    try:
        discount_price = soup.select_one("span.product_article_price .discounted_price").get_text(strip=True)
    except:
        discount_price = "할인가 없음"

    try:
        real_price = soup.select_one("span.final_price").get_text(strip=True)
    except:
        real_price = "실구매가 없음"

    return name, origin_price, discount_price, real_price

# ✅ 텔레그램 응답 함수
def send_message(chat_id, text):
    requests.post(f"{URL}/sendMessage", data={"chat_id": chat_id, "text": text})

# ✅ 텔레그램 봇 실행
def run_bot():
    last_update_id = None
    print("텔레그램 봇 가동 중...")

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
                    name, origin, discount, real = extract_product_info(url)
                    msg = f"📦 상품 정보\n상품명: {name}\n정가: {origin}\n할인가: {discount}\n실구매가: {real}"
                    send_message(chat_id, msg)

        except Exception as e:
            print("오류 발생:", e)
            sleep(2)

# ✅ Flask + 텔레그램 봇 병렬 실행
if __name__ == "__main__":
    t1 = threading.Thread(target=run_bot)
    t1.start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
