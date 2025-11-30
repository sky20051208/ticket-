# bot.py (正式版 V14.0 - 世紀大發現版)
# 特性：CDP 全域監聽 + 自動刷新機制 + 會員預購支援 + 多策略選位

import asyncio
import nodriver as uc
import random
import time
import os
from datetime import datetime
from config import WANTED_TICKET_COUNT, WANTED_AREA_KEYWORD, Selector, TARGET_TIME, TIME_WATCH_URL, AREA_AUTO_SELECT_MODE, ENABLE_TIME_WATCHER, EXCLUDE_AREA_KEYWORD, PRE_ORDER_CODE
from timeWatcher import TimeWatcher
from captchaAI.predict import solve_captcha_nodriver

PAUSE_FILE = "pause.lock"

# ----------------------------------------------------
# 輔助函式
# ----------------------------------------------------

async def check_pause():
    if os.path.exists(PAUSE_FILE):
        print("\n⏸️ 程式已暫停...", end='\r')
        while os.path.exists(PAUSE_FILE):
            await asyncio.sleep(1)
        print("\n▶️ 程式繼續執行！        ")

async def random_sleep(min_s=0.3, max_s=0.8):
    await asyncio.sleep(random.uniform(min_s, max_s))

async def pre_fill_form(tab):
    """預填表單 (mobile-select)"""
    num = WANTED_TICKET_COUNT
    js = f"""
    (function() {{
        let count = 0;
        let selects = document.querySelectorAll('.mobile-select');
        selects.forEach(s => {{
            if (s) {{
                s.value = '{num}';
                s.dispatchEvent(new Event('change', {{ bubbles: true }}));
                count++;
            }}
        }});
        var agree = document.getElementById('TicketForm_agree');
        if (agree && !agree.checked) {{ agree.click(); }}
        return count;
    }})()
    """
    try: await tab.evaluate(js)
    except: pass

async def submit_order_nodriver(tab, captcha_code: str):
    """
    提交訂單 (極簡化)
    只負責點擊，彈窗攔截交給全域監聽器
    """
    if not captcha_code: return False
    try:
        fill_js = f"""
        (function() {{
            var input = document.getElementById('{Selector.CAPTCHA_INPUT[1]}');
            if (input) {{
                input.value = '{captcha_code}';
                input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                
                var btn = document.querySelector('button[type="submit"]');
                if (btn) {{
                    // 使用 setTimeout 非同步點擊，確保 Python 不會被卡住
                    setTimeout(() => btn.click(), 0);
                    return true; 
                }}
            }}
            return false;
        }})()
        """
        await tab.evaluate(fill_js)
        return True
    except Exception as e:
        print(f"❌ 提交異常: {e}")
        return False

async def refresh_captcha_nodriver(tab):
    """手動刷新驗證碼"""
    try:
        await tab.evaluate(f"document.getElementById('{Selector.CAPTCHA_IMAGE[1]}').click();")
        await asyncio.sleep(0.3)
        return True
    except: pass
    return False

# ----------------------------------------------------
# 頁面處理器 (Handlers)
# ----------------------------------------------------

# [保留] 預購碼驗證頁處理
# bot.py (handle_verify_page 純點擊版)

async def handle_verify_page(tab):
    await check_pause()
    
    print(f"🔐 [驗證頁] 準備輸入預購碼: {PRE_ORDER_CODE}...")
    
    if not PRE_ORDER_CODE:
        print("⚠️ 警告：未設定預購碼！請在 GUI 設定。")
        await asyncio.sleep(1)
        return

    # [純淨版] 針對您提供的 Selector 進行精準打擊
    # 輸入框: #form-ticket-verify ... input
    # 按鈕: #form-ticket-verify ... button
    verify_js = f"""
    (function() {{
        // 1. 定位輸入框 (鎖定在 form-ticket-verify 內)
        var input = document.querySelector("#form-ticket-verify input[name='checkCode']");
        
        // 備用: 如果結構稍微變動，嘗試找 ID 或 Class
        if (!input) input = document.querySelector("#checkCode");
        if (!input) input = document.querySelector("input.greyInput[name='checkCode']");
        
        if (input) {{
            // 2. 輸入會員碼 (觸發事件確保網頁吃到值)
            input.focus();
            input.value = '{PRE_ORDER_CODE}';
            input.dispatchEvent(new Event('input', {{ bubbles: true }}));
            input.dispatchEvent(new Event('change', {{ bubbles: true }}));
            input.blur();
            
            // 3. 定位送出按鈕 (鎖定在 form-ticket-verify 內)
            var btn = document.querySelector("#form-ticket-verify button[type='submit']");
            
            // 備用: 找 ID 或 Class
            if (!btn) btn = document.getElementById('submitButton');
            if (!btn) btn = document.querySelector("button.btn-primary");
            
            if (btn) {{
                console.log("[Bot] 點擊送出");
                setTimeout(() => btn.click(), 0);
                return true;
            }}
        }}
        return false;
    }})()
    """
    
    is_submitted = await tab.evaluate(verify_js)
    
    if is_submitted:
        print("🚀 預購碼已送出，等待跳轉...")
        # 送出後稍微等待，讓主迴圈去判斷網址是否變更 (進入選區)
        await asyncio.sleep(0.5)
    else:
        print("❌ 找不到輸入框或按鈕 (Selector不匹配)，刷新重試...")
        await tab.reload()
        await asyncio.sleep(1)

async def handle_game_page(tab):
    await check_pause()
    current_url = await tab.evaluate("window.location.href")
    
    if "activity/detail" in current_url and "activity/game" in TIME_WATCH_URL:
        print(f"🚀 [場次頁] 直連跳轉 -> {TIME_WATCH_URL}")
        await tab.get(TIME_WATCH_URL)
        return

    scan_js = """
    (function() {
        const tags = ["button", "div", "a"];
        for (let tag of tags) {
            let elements = document.querySelectorAll(tag);
            for (let el of elements) {
                let text = el.innerText.replace(/\\s/g, '');
                if (el.classList.contains('disabled') || text.includes("售完") || text.includes("尚未開賣")) continue;

                if (text.includes("立即訂購")) {
                    setTimeout(() => el.click(), 0); 
                    return true; 
                }
            }
        }
        return false;
    })();
    """
    # 3次微重試
    for _ in range(3):
        if await tab.evaluate(scan_js):
            print("🔥 [場次頁] 點擊成功！")
            await asyncio.sleep(0.5)
            return
        await asyncio.sleep(0.1)

    await tab.reload()
    await tab.wait_for("body")

async def handle_area_page(tab):
    await check_pause()
    strategy = AREA_AUTO_SELECT_MODE
    print(f"🎯 [選區頁] 策略: {strategy}...")
    try: await tab.wait_for(".select_form_a, .select_form_b, .zone", timeout=1)
    except: return

    mode_map = { "關鍵字優先": "KEYWORD", "由上而下": "TOP_DOWN", "由下而上": "BOTTOM_UP", "隨機": "RANDOM" }
    mode_js_var = mode_map.get(strategy, "KEYWORD")

    # 排除關鍵字邏輯
    js_script = f"""
    (function() {{
        const mode = '{mode_js_var}';
        const keyword = '{WANTED_AREA_KEYWORD}';
        const excludes = '{EXCLUDE_AREA_KEYWORD}'.split(';');
        
        document.querySelectorAll("footer, img, header").forEach(e => e.remove());
        let links = Array.from(document.querySelectorAll('.select_form_a a, .select_form_b a, .zone a'));
        let validLinks = links.filter(link => {{
            let text = link.innerText.replace(/\\s/g, '');
            if (link.classList.contains('disabled')) return false;
            if (text.includes('售完') || text.includes('Soldout')) return false;
            if (text.includes('剩餘0')) return false;
            
            for (let ex of excludes) {{
                if (ex && ex.trim() !== "" && text.includes(ex.trim())) {{ return false; }}
            }}
            return true;
        }});
        
        if (validLinks.length === 0) return false; 

        let targetLink = null;
        if (mode === 'KEYWORD') {{
            targetLink = validLinks.find(link => link.innerText.replace(/\\s/g, '').includes(keyword));
        }} 
        else if (mode === 'TOP_DOWN') {{ targetLink = validLinks[0]; }} 
        else if (mode === 'BOTTOM_UP') {{ targetLink = validLinks[validLinks.length - 1]; }} 
        else if (mode === 'RANDOM') {{ targetLink = validLinks[Math.floor(Math.random() * validLinks.length)]; }}

        if (targetLink) {{
            setTimeout(() => targetLink.click(), 0);
            return true;
        }}
        return false;
    }})()
    """
    if await tab.evaluate(js_script):
        print("🔥 [選區頁] 點擊成功！")
        await asyncio.sleep(0.2) 
    else:
        print(f"⚠️ [選區頁] 無票，冷卻 7 秒...")
        await tab.reload()
        await asyncio.sleep(7)

async def handle_ticket_page(tab):
    await check_pause()
    print("📝 [填單頁] 處理中...")
    
    # 第一次進來不刷圖 (保留第一張)
    
    await pre_fill_form(tab)
    captcha_code = await solve_captcha_nodriver(tab)
    
    await check_pause()

    if captcha_code and len(captcha_code) == 4:
        print(f"🚀 送出: {captcha_code}")
        
        # 點擊送出 -> 觸發頁面 Reload -> 觸發 Alert -> 監聽器秒殺 -> 頁面完成 Reload (圖片換新)
        await submit_order_nodriver(tab, captcha_code)
        
        # 等待 0.5 秒 (給予監聽器反應時間)
        await asyncio.sleep(0.5)
        
        try:
            current_url = await tab.evaluate("window.location.href")
            if "/ticket/ticket" in current_url:
                # 如果還在原頁面，代表驗證碼錯了 (Alert 已被監聽器按掉，網頁已刷新)
                # 我們直接 return，讓主迴圈重新進來辨識新圖
                print("⚠️ 驗證碼錯誤 (Alert已攔截)，原地重試...")
                return 
        except: pass
    else:
        print(f"⚠️ 辨識失敗，手動刷新...")
        await refresh_captcha_nodriver(tab)
        await asyncio.sleep(0.2)

# ----------------------------------------------------
# 啟動流程 (CDP 監聽器搭載)
# ----------------------------------------------------

async def run_initial_setup():
    print("🚀 啟動 nodriver (V14.0 世紀大發現版)...")
    
    import os
    user_data_dir = os.path.abspath("./chrome_profile")
    
    browser = await uc.start(
        headless=False,
        user_data_dir=user_data_dir,
        browser_args=["--start-maximized", "--disable-notifications"]
    )
    tab = await browser.get("https://tixcraft.com/")
    
    # ==================================================
    # [核心] CDP 事件監聽器 (Alert Killer)
    # ==================================================
    async def alert_handler(event: uc.cdp.page.JavascriptDialogOpening):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"⚡ [{timestamp}] 偵測到 Alert: {event.message} -> 秒殺！")
        try:
            # [修正] 使用您測試成功的 API 方法
            await tab.send(uc.cdp.page.handle_java_script_dialog(accept=True))
        except:
            pass

    # 1. 啟用 Page 域
    await tab.send(uc.cdp.page.enable())
    # 2. 綁定事件
    tab.add_handler(uc.cdp.page.JavascriptDialogOpening, alert_handler)
    # ==================================================

    try:
        await tab.send(uc.cdp.network.enable())
    except: pass
    
    try: await tab.evaluate("if(document.getElementById('onetrust-accept-btn-handler')){document.getElementById('onetrust-accept-btn-handler').click();}")
    except: pass

    if ENABLE_TIME_WATCHER:
        print("\n🛑 [待命模式] 等待倒數...")
        watcher = TimeWatcher(TARGET_TIME, TIME_WATCH_URL)
        await watcher.wait_for_open_async()
        print(f"⚡ 時間到！直連前往...")
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
                    print(f"⚡ 偵測到目標詳情頁！直連跳轉 -> {TIME_WATCH_URL}")
                    await tab.get(TIME_WATCH_URL)
                    break
                if f"/activity/game/{target_id}" in current_url:
                    print("✅ 已在場次頁，開始接管！")
                    break
            except: pass
            await asyncio.sleep(0.5)

    try: await tab.wait_for("body") 
    except: pass
    return browser, tab