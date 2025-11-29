# config.py

from selenium.webdriver.common.by import By
import os

# --- Selenium/Web 設定 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAPTCHA_DATASET_DIR = os.path.join(BASE_DIR, "captchaAI", "dataset")
CAPTCHA_MODEL_DIR = os.path.join(BASE_DIR, "captchaAI", "model")
MODEL_FILENAME = "crnn_ctc_model.h5"
MODEL_PATH = os.path.join(CAPTCHA_MODEL_DIR, MODEL_FILENAME)

# --- 搶票參數 ---
TIXCRAFT_URL = "https://tixcraft.com/"
WANTED_TICKET_COUNT = "2"

# 選位策略: "關鍵字優先", "由上而下", "由下而上", "隨機"
AREA_AUTO_SELECT_MODE = "由上而下"
WANTED_AREA_KEYWORD = ""

# [新增] 排除關鍵字 (以分號 ; 分隔)
# 凡是區域名稱包含這些字詞的，機器人一律跳過
EXCLUDE_AREA_KEYWORD = "輪椅;身障;身心;障礙;Restricted View;燈柱遮蔽;視線不完整"

# --- 時間與監控 ---
ENABLE_TIME_WATCHER = False
TARGET_TIME = "13:00:00"
TIME_WATCH_URL = "https://tixcraft.com/activity/game/25_whyte"

# --- 網頁元素選擇器 ---
class Selector:
    COOKIE_ACCEPT_BTN = (By.ID, "onetrust-accept-btn-handler")
    BUY_TICKET_BTN_SELECTOR = (By.CSS_SELECTOR, 'a[target="_new"]') 
    BUY_TICKET_BTN_TEXT = "立即購票"
    ORDER_BTN = (By.CSS_SELECTOR, 'button.btn.btn-primary.text-bold.m-0')
    TICKET_PRICE_SELECT = (By.ID, "TicketForm_ticketPrice_01")
    TICKET_AREA_A = (By.CLASS_NAME, "select_form_a") 
    TICKET_AREA_B = (By.CLASS_NAME, "select_form_b") 
    QUANTITY_DROPDOWN = (By.CSS_SELECTOR, '.mobile-select') 
    AGREEMENT_CHECKBOX = (By.CLASS_NAME, "form-check-input")
    CONFIRM_NEXT_BTN = (By.XPATH, '//*[@id="form-ticket-ticket"]/div[4]/button[2]')
    CAPTCHA_IMAGE = (By.ID, "TicketForm_verifyCode-image")
    CAPTCHA_INPUT = (By.ID, "TicketForm_verifyCode")
    CONFIRM_PURCHASE = (By.CSS_SELECTOR, 'button[type="submit"]')