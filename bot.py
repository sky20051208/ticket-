# bot.py (速度優化版 V14.1)
# 優化項目：減少等待時間、並行處理、快取機制、JS執行優化

import asyncio
import nodriver as uc
import random
import time
import os
from datetime import datetime
from config import WANTED_TICKET_COUNT, WANTED_AREA_KEYWORD, WANTED_DATE_KEYWORD,Selector, TARGET_TIME, TIME_WATCH_URL, AREA_AUTO_SELECT_MODE, ENABLE_TIME_WATCHER, EXCLUDE_AREA_KEYWORD, PRE_ORDER_CODE
from timeWatcher import TimeWatcher
from captchaAI.predict import solve_captcha_nodriver

PAUSE_FILE = "pause.lock"
#打包指令1 pyinstaller --onedir --name=TicketBot --exclude-module=config --hidden-import=selenium --hidden-import=selenium.webdriver.common.by --collect-all ddddocr main.py
#打包指令2 pyinstaller --onefile --name=Launcher --exclude-module=config gui.py

# ----------------------------------------------------
# 輔助函式（優化版）
# ----------------------------------------------------

async def check_pause():
    if os.path.exists(PAUSE_FILE):
        print("\n⏸️ 程式已暫停...", end='\r')
        while os.path.exists(PAUSE_FILE):
            await asyncio.sleep(0.5)  # 從 1 秒改為 0.5 秒，更快恢復
        print("\n▶️ 程式繼續執行！        ")

async def random_sleep(min_s=0.2, max_s=0.5):  # 從 0.3-0.8 改為 0.2-0.5
    await asyncio.sleep(random.uniform(min_s, max_s))

async def pre_fill_form(tab):
    """預填表單（優化：移除不必要的操作）"""
    num = WANTED_TICKET_COUNT
    js = f"""
    (function() {{
        let selects = document.querySelectorAll('.mobile-select');
        selects.forEach(s => {{
            s.value = '{num}';
            s.dispatchEvent(new Event('change', {{ bubbles: true }}));
        }});
        var agree = document.getElementById('TicketForm_agree');
        if (agree && !agree.checked) agree.click();
        return selects.length;
    }})()
    """
    try: 
        return await tab.evaluate(js)
    except: 
        return 0

async def submit_order_nodriver(tab, captcha_code: str):
    """提交訂單（優化：簡化流程）"""
    if not captcha_code: return False
    try:
        fill_js = f"""
        (function() {{
            var input = document.getElementById('{Selector.CAPTCHA_INPUT[1]}');
            if (input) {{
                input.value = '{captcha_code}';
                var btn = document.querySelector('button[type="submit"]');
                if (btn) {{
                    setTimeout(() => btn.click(), 0);
                    return true; 
                }}
            }}
            return false;
        }})()
        """
        return await tab.evaluate(fill_js)
    except:
        return False

async def refresh_captcha_nodriver(tab):
    """刷新驗證碼（優化：減少等待）"""
    try:
        await tab.evaluate(f"document.getElementById('{Selector.CAPTCHA_IMAGE[1]}').click();")
        await asyncio.sleep(0.15)  # 從 0.3 改為 0.15
        return True
    except: 
        return False

# ----------------------------------------------------
# 頁面處理器（速度優化版）
# ----------------------------------------------------

async def handle_verify_page(tab):
    await check_pause()
    print(f"🔐 [驗證頁] 準備輸入預購碼: {PRE_ORDER_CODE}...")
    
    if not PRE_ORDER_CODE:
        print("⚠️ 警告：未設定預購碼！")
        await asyncio.sleep(0.5)  # 從 1 秒改為 0.5 秒
        return

    verify_js = f"""
    (function() {{
        var input = document.querySelector("#form-ticket-verify input[name='checkCode']") 
                    || document.querySelector("#checkCode")
                    || document.querySelector("input.greyInput[name='checkCode']");
        
        if (input) {{
            input.value = '{PRE_ORDER_CODE}';
            input.dispatchEvent(new Event('input', {{ bubbles: true }}));
            
            var btn = document.querySelector("#form-ticket-verify button[type='submit']")
                     || document.getElementById('submitButton')
                     || document.querySelector("button.btn-primary");
            
            if (btn) {{
                setTimeout(() => btn.click(), 0);
                return true;
            }}
        }}
        return false;
    }})()
    """
    
    if await tab.evaluate(verify_js):
        print("🚀 預購碼已送出")
        await asyncio.sleep(0.3)  # 從 0.5 改為 0.3
    else:
        print("❌ 找不到輸入框，刷新重試...")
        await tab.reload()
        await tab.wait_for("body") 

async def handle_game_page(tab):
    await check_pause()

    current_url = await tab.evaluate("window.location.href")
    if "activity/detail" in current_url and "activity/game" in TIME_WATCH_URL:
        print(f"🚀 [場次頁] 偵測到詳情頁，強制跳轉至: {TIME_WATCH_URL}")
        await tab.get(TIME_WATCH_URL)
        return

    # 顯示搜尋模式
    search_msg = f"關鍵字 '{WANTED_DATE_KEYWORD}'" if WANTED_DATE_KEYWORD else "任意場次"
    print(f"👀 [場次頁] 搜尋: {search_msg} 立即訂購...")

    # V15.0 核心邏輯：支援關鍵字過濾
    scan_js = f"""
    (function() {{
        const keyword = '{WANTED_DATE_KEYWORD}'; 
        const tags = ["button", "div", "a"];
        
        // 判斷按鈕是否可點 (排除售完、disabled)
        function isValidBtn(el) {{
            let text = el.innerText.replace(/\\s/g, '');
            if (el.classList.contains('disabled')) return false;
            if (text.includes("售完") || text.includes("Soldout") || text.includes("尚未開賣")) return false;
            if (text.includes("立即訂購") || text.includes("Order")) return true;
            return false;
        }}

        // 模式 1: 有關鍵字 -> 針對表格列 (tr) 搜尋
        if (keyword) {{
            let rows = document.querySelectorAll('#gameList tr');
            for (let row of rows) {{
                if (row.innerText.includes(keyword)) {{
                    let elements = row.querySelectorAll('button, a, div');
                    for (let el of elements) {{
                        if (isValidBtn(el)) {{
                            el.click();
                            return true; 
                        }}
                    }}
                }}
            }}
            return false; 
        }}

        // 模式 2: 無關鍵字 -> 掃描全頁面第一個能按的
        for (let tag of tags) {{
            let elements = document.querySelectorAll(tag);
            for (let el of elements) {{
                if (isValidBtn(el)) {{ 
                    el.click(); 
                    return true; 
                }}
            }}
        }}
        return false;
    }})();
    """
    
    is_clicked = await tab.evaluate(scan_js)
    
    if is_clicked:
        print(f"🔥 [場次頁] 鎖定目標，點擊成功！")
        await asyncio.sleep(0.5)
    else:
        if WANTED_DATE_KEYWORD:
             print(f"⚠️ [場次頁] 找不到符合 '{WANTED_DATE_KEYWORD}' 且可購買的場次，刷新...")
        else:
             print("⚠️ [場次頁] 暫無可購買按鈕，刷新...")
        await tab.reload()
        try: await tab.wait_for("body")
        except: pass

async def handle_area_page(tab):
    await check_pause()
    strategy = AREA_AUTO_SELECT_MODE
    # 預設排除關鍵字為空字串，避免錯誤
    exclude_keyword = EXCLUDE_AREA_KEYWORD if 'EXCLUDE_AREA_KEYWORD' in globals() else ""
    
    print(f"🎯 [選區頁] 策略: {strategy} | 關鍵字: {WANTED_AREA_KEYWORD}")
    
    try: 
        await tab.wait_for(".select_form_a, .select_form_b, .zone", timeout=0.3)
    except: 
        return

    mode_map = {
        "關鍵字優先": "KEYWORD", 
        "由上而下": "TOP_DOWN", 
        "由下而上": "BOTTOM_UP", 
        "隨機": "RANDOM"
    }
    mode_js_var = mode_map.get(strategy, "KEYWORD")

    js_script = f"""
    (function() {{
        const mode = '{mode_js_var}';
        const keyword = '{WANTED_AREA_KEYWORD}';
        const excludes = '{exclude_keyword}'.split(';').filter(e => e.trim());
        
        // 1. 取得所有區域按鈕
        let links = Array.from(document.querySelectorAll('.select_form_a a, .select_form_b a, .zone a'));
        
        // 2. 初步過濾 (排除售完、disabled、排除關鍵字)
        let validLinks = links.filter(link => {{
            let text = link.innerText.replace(/\\s/g, '');
            if (link.classList.contains('disabled') || 
                text.includes('售完') || 
                text.includes('Soldout') || 
                text.includes('剩餘0')) return false;
            
            // 檢查排除關鍵字
            return !excludes.some(ex => text.includes(ex));
        }});
        
        if (validLinks.length === 0) return false; 

        let targetLink = null;

        // 3. 根據策略選出目標
        if (mode === 'KEYWORD') {{
            // [V15.1 優化] 關鍵字模式下，如果有「多個」區域符合關鍵字 (例如 5800 有五區)
            // 這裡改成「隨機」挑選其中一個，避免大家都搶第一個 (A區)
            let matches = validLinks.filter(link => link.innerText.replace(/\\s/g, '').includes(keyword));
            
            if (matches.length > 0) {{
                targetLink = matches[Math.floor(Math.random() * matches.length)];
                console.log("關鍵字命中 " + matches.length + " 個，隨機選擇其一");
            }}
        }} 
        else if (mode === 'TOP_DOWN') targetLink = validLinks[0];
        else if (mode === 'BOTTOM_UP') targetLink = validLinks[validLinks.length - 1];
        else if (mode === 'RANDOM') targetLink = validLinks[Math.floor(Math.random() * validLinks.length)];

        // 4. 執行點擊
        if (targetLink) {{
            // 使用 setTimeout 確保非同步觸發，避免卡住 JS
            setTimeout(() => targetLink.click(), 0);
            return true;
        }}
        return false;
    }})()
    """

    # --- 第一次嘗試 ---
    if await tab.evaluate(js_script):
        print("🔥 [選區頁] 點擊成功！")
        await asyncio.sleep(0.15)
        return
    else:
        print("⚠️ [選區頁] 無票或未找到 → 進入『1 秒高速偵測』")

    # --- reload 並開始 1 秒高速偵測 (你的邏輯) ---
    await tab.reload()

    start = time.time()
    # 稍微增加到 2.5 秒比較保險，處理網頁載入延遲
    while time.time() - start < 2.5:   
        await asyncio.sleep(0.05)    # 每 50ms 偵測一次

        try:
            # timeout 設極短，避免卡住
            await tab.wait_for(".select_form_a, .select_form_b, .zone", timeout=0.1)
        except:
            continue

        ok = await tab.evaluate(js_script)
        if ok:
            print("🔥🔥🔥 [選區頁] 高速偵測中 → 抓到票了！")
            await asyncio.sleep(0.1)
            return

    # --- 偵測失敗，進入長冷卻 ---
    print("❌ [選區頁] 偵測超時仍無票 → 冷卻 5 秒")
    await asyncio.sleep(5)


async def handle_ticket_page(tab):
    await check_pause()
    print("📝 [填單頁] 處理中...")
    
    # 優化：並行執行預填表單和驗證碼辨識
    fill_task = asyncio.create_task(pre_fill_form(tab))
    captcha_task = asyncio.create_task(solve_captcha_nodriver(tab))
    
    await fill_task
    captcha_code = await captcha_task
    
    await check_pause()

    if captcha_code and len(captcha_code) == 4:
        print(f"🚀 送出: {captcha_code}")
        await submit_order_nodriver(tab, captcha_code)
        await asyncio.sleep(0.3)  # 從 0.5 改為 0.3
        
        try:
            current_url = await tab.evaluate("window.location.href")
            if "/ticket/ticket" in current_url:
                print("⚠️ 驗證碼錯誤，原地重試...")
                return 
        except: 
            pass
    else:
        print(f"⚠️ 辨識失敗，刷新...")
        await refresh_captcha_nodriver(tab)
        await asyncio.sleep(0.15)  # 從 0.2 改為 0.15

# ----------------------------------------------------
# 啟動流程（優化版）
# ----------------------------------------------------

async def run_initial_setup():
    print("🚀 啟動 nodriver (速度優化版 V14.1)...")
    
    user_data_dir = os.path.abspath("./chrome_profile")
    
    browser = await uc.start(
        headless=False,
        user_data_dir=user_data_dir,
        browser_args=[
            "--start-maximized", 
            "--disable-notifications",
            "--disable-blink-features=AutomationControlled",  # 優化：減少被偵測
            "--disable-dev-shm-usage",  # 優化：減少記憶體使用
        ]
    )
    tab = await browser.get("https://tixcraft.com/")
    
    # CDP 事件監聽器
    async def alert_handler(event: uc.cdp.page.JavascriptDialogOpening):
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]  # 優化：加入毫秒
        print(f"⚡ [{timestamp}] Alert 秒殺: {event.message}")
        try:
            await tab.send(uc.cdp.page.handle_java_script_dialog(accept=True))
        except:
            pass

    await tab.send(uc.cdp.page.enable())
    tab.add_handler(uc.cdp.page.JavascriptDialogOpening, alert_handler)

    try:
        await tab.send(uc.cdp.network.enable())
    except: 
        pass
    
    # 優化：Cookie 同意按鈕
    try: 
        await tab.evaluate("""
            var btn = document.getElementById('onetrust-accept-btn-handler');
            if (btn) btn.click();
        """)
    except: 
        pass

    if ENABLE_TIME_WATCHER:
        print("\n🛑 [待命模式] 等待倒數...")
        watcher = TimeWatcher(TARGET_TIME, TIME_WATCH_URL)
        await watcher.wait_for_open_async()
        print(f"⚡ 時間到！直連...")
        
        current_url = await tab.evaluate("window.location.href")
        if TIME_WATCH_URL not in current_url:
            await tab.get(TIME_WATCH_URL)
        else:
            await tab.reload()
    else:
        print("\n🚀 [即時模式] 請手動進入活動頁...")
        target_id = TIME_WATCH_URL.split("/")[-1]
        print(f"   目標: {target_id}")
        
        while True:
            await check_pause()
            try:
                current_url = await tab.evaluate("window.location.href")
                if f"/activity/detail/{target_id}" in current_url:
                    print(f"⚡ 偵測到目標頁！跳轉...")
                    await tab.get(TIME_WATCH_URL)
                    break
                if f"/activity/game/{target_id}" in current_url:
                    print("✅ 已在場次頁")
                    break
            except: 
                pass
            await asyncio.sleep(0.3)  # 從 0.5 改為 0.3

    try: 
        await tab.wait_for("body", timeout=2)  # 優化：加入 timeout
    except: 
        pass
    
    return browser, tab