# config.py

from selenium.webdriver.common.by import By
import os

# --- Selenium/Web 設定 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAPTCHA_DATASET_DIR = os.path.join(BASE_DIR, "captchaAI", "dataset")
CAPTCHA_MODEL_DIR = os.path.join(BASE_DIR, "captchaAI", "model")
MODEL_FILENAME = "crnn_ctc_model.h5"
MODEL_PATH = os.path.join(CAPTCHA_MODEL_DIR, MODEL_FILENAME)
TIXCRAFT_URL = "https://tixcraft.com/"
CHROME_DRIVER_PATH = r"D:\codehere\python\chromedriver-win64\chromedriver.exe"
WAIT_TIMEOUT = 15 # WebDriverWait 等待秒數

# --- 客製化搶票選擇 ---
WANTED_TICKET_COUNT = "2"
WANTED_AREA_KEYWORD = "VIP"
# 開賣時間 (HH:MM:SS)
TARGET_TIME = "17:22:00"

# 監控目標網址 (通常是活動的"場次列表頁"或"立即購票頁")
# 請換成您要搶的那個活動網址，例如:
TIME_WATCH_URL = "https://tixcraft.com/activity/game/25_whyte"

# --- 網頁元素選擇器 (Selector) ---
class Selector:
    # 點擊 Cookie
    COOKIE_ACCEPT_BTN = (By.ID, "onetrust-accept-btn-handler")
    # 立即購票 (進入購票頁面)
    BUY_TICKET_BTN_SELECTOR = (By.CSS_SELECTOR, 'a[target="_new"]') # CSS Selector
    BUY_TICKET_BTN_TEXT = "立即購票"

    # 立即訂購 (購票頁面上的按鈕)
    ORDER_BTN = (By.CSS_SELECTOR, 'button.btn.btn-primary.text-bold.m-0')

    # 區域/價位選擇
    TICKET_PRICE_SELECT = (By.ID, "TicketForm_ticketPrice_01")
    TICKET_AREA_A = (By.CLASS_NAME, "select_form_a") 
    TICKET_AREA_B = (By.CLASS_NAME, "select_form_b") 

    # 選擇張數
    QUANTITY_DROPDOWN = (By.CSS_SELECTOR, '.mobile-select')

    # 同意打勾
    AGREEMENT_CHECKBOX = (By.CLASS_NAME, "form-check-input")

    # 確認張數並前往下一步
    CONFIRM_NEXT_BTN = (By.XPATH, '//*[@id="form-ticket-ticket"]/div[4]/button[2]')
    
    # 驗證碼相關
    CAPTCHA_IMAGE = (By.ID, "TicketForm_verifyCode-image")# 驗證碼圖片
    CAPTCHA_INPUT = (By.ID, "TicketForm_verifyCode")# 驗證碼輸入框
    CONFIRM_PURCHASE = (By.CSS_SELECTOR, 'button[type="submit"]')# 提交訂單按鈕


