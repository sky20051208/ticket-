# bot.py (正式版 V9.7 - 零延遲極速版)

import asyncio
import nodriver as uc
import random
import time
import os
import ctypes
from config import WANTED_TICKET_COUNT, WANTED_AREA_KEYWORD, Selector, TARGET_TIME, TIME_WATCH_URL, AREA_AUTO_SELECT_MODE, ENABLE_TIME_WATCHER
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

def send_os_enter():
    """OS 物理按鍵 (Enter)"""
    try:
        ctypes.windll.user32.keybd_event(0x0D, 0, 0, 0)      # 按下
        time.sleep(0.03) # [優化] 按壓時間縮短，提升頻率
        ctypes.windll.user32.keybd_event(0x0D, 0, 0x0002, 0) # 放開
    except: pass

async def pre_fill_form(tab):
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
    提交訂單 + 1秒轟炸 (完全依照您的指示)
    """
    if not captcha_code: return False
    
    try:
        # 1. 填寫
        fill_js = f"""
        (function() {{
            var input = document.getElementById('{Selector.CAPTCHA_INPUT[1]}');
            if (input) {{
                input.value = '{captcha_code}';
                input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                
                var btn = document.querySelector('button[type="submit"]');
                if (btn) {{
                    setTimeout(() => btn.click(), 0);
                    return true; 
                }}
            }}
            return false;
        }})()
        """
        await tab.evaluate(fill_js)
        
        # 2. [階段一] 狂按 Enter 1 秒 (處理驗證碼錯誤彈窗)
        # 這段時間是必要的，因為如果真的有彈窗，必須要在這裡解決
        start_time = time.time()
        while time.time() - start_time < 1.0:
            send_os_enter()
            await asyncio.sleep(0.1) # 保持高頻轟炸
            
        return True
    except Exception as e:
        print(f"❌ 提交異常: {e}")
        return False

async def refresh_captcha_nodriver(tab):
    try:
        send_os_enter() # 清場
        await tab.evaluate(f"document.getElementById('{Selector.CAPTCHA_IMAGE[1]}').click();")
        # [優化] 縮短等待，假設網路夠快
        await asyncio.sleep(0.1)
        return True
    except: pass
    return False

# ----------------------------------------------------
# 頁面處理器 (移除所有不必要的 sleep)
# ----------------------------------------------------

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
    is_clicked = await tab.evaluate(scan_js)
    
    if is_clicked:
        print("🔥 [場次頁] 點擊成功！")
        await asyncio.sleep(0.2)
        # [核心修正] 移除 await asyncio.sleep(0.5)
        # 點了就跑，讓主迴圈去偵測跳轉
    else:
        await tab.reload()
        # await tab.wait_for("body") # reload 自帶等待，這裡可以拿掉

async def handle_area_page(tab):
    await check_pause()
    strategy = AREA_AUTO_SELECT_MODE
    print(f"🎯 [選區頁] 策略: {strategy}...")
    
    try: await tab.wait_for(".select_form_a, .select_form_b, .zone", timeout=1)
    except: return

    mode_map = { "關鍵字優先": "KEYWORD", "由上而下": "TOP_DOWN", "由下而上": "BOTTOM_UP", "隨機": "RANDOM" }
    mode_js_var = mode_map.get(strategy, "KEYWORD")

    js_script = f"""
    (function() {{
        const mode = '{mode_js_var}';
        const keyword = '{WANTED_AREA_KEYWORD}';
        document.querySelectorAll("footer, img, header").forEach(e => e.remove());
        let links = Array.from(document.querySelectorAll('.select_form_a a, .select_form_b a, .zone a'));
        let validLinks = links.filter(link => {{
            let text = link.innerText.replace(/\\s/g, '');
            if (link.classList.contains('disabled')) return false;
            if (text.includes('售完') || text.includes('Soldout')) return false;
            if (text.includes('剩餘0')) return false;
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
    is_clicked = await tab.evaluate(js_script)
    
    if is_clicked:
        print("🔥 [選區頁] 點擊成功！")
        await asyncio.sleep(0.1)
        # [核心修正] 移除 await asyncio.sleep(0.2)
        # 點擊後立刻回傳，讓主迴圈去抓下一頁
    else:
        print(f"⚠️ [選區頁] 無票，冷卻 7 秒...")
        await tab.reload()
        await asyncio.sleep(7)

async def handle_ticket_page(tab):
    await check_pause()
    print("📝 [填單頁] 處理中...")
    
    # [維持] 進場不刷新圖片
    
    await pre_fill_form(tab)
    captcha_code = await solve_captcha_nodriver(tab)
    
    await check_pause()

    if captcha_code and len(captcha_code) == 4:
        print(f"🚀 送出: {captcha_code}")
        
        # 執行送出 + 1秒轟炸
        await submit_order_nodriver(tab, captcha_code)
        
        # 轟炸完立刻檢查
        try:
            current_url = await tab.evaluate("window.location.href")
            
            # 情況 A: 進入轉圈圈 (/ticket/order)
            # -> 結束此函式，交給 main.py 的轉圈圈邏輯 (無限 Enter)
            if "/ticket/order" in current_url:
                return

            # 情況 B: 還在原頁面 (/ticket/ticket)
            # -> 代表驗證碼錯了，且彈窗已被 1 秒轟炸按掉
            # -> 圖片已自動換新，直接 return，讓主迴圈重新進來填寫
            if "/ticket/ticket" in current_url:
                print("⚠️ 驗證碼錯誤 (已按 Enter)，原地重試...")
                return 

        except:
            pass
            
    else:
        print(f"⚠️ 辨識失敗，刷新...")
        await refresh_captcha_nodriver(tab)
        await asyncio.sleep(0.1)

# ----------------------------------------------------
# 啟動流程
# ----------------------------------------------------

async def run_initial_setup():
    print("🚀 啟動 nodriver (V9.7 零延遲極速版)...")
    
    import os
    user_data_dir = os.path.abspath("./chrome_profile")
    browser = await uc.start(
        headless=False,
        user_data_dir=user_data_dir,
        browser_args=["--start-maximized", "--disable-notifications"]
    )
    tab = await browser.get("https://tixcraft.com/")
    
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