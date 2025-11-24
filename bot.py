# bot.py (正式版 - 支援暫停/繼續)

import asyncio
import nodriver as uc
import random
import time
import os # 必須匯入 os
from config import WANTED_TICKET_COUNT, WANTED_AREA_KEYWORD, Selector, TARGET_TIME, TIME_WATCH_URL
from timeWatcher import TimeWatcher
from captchaAI.predict import solve_captcha_nodriver

PAUSE_FILE = "pause.lock"

# ----------------------------------------------------
# 輔助函式
# ----------------------------------------------------

async def check_pause():
    """檢查是否有暫停訊號，若有則無限等待"""
    if os.path.exists(PAUSE_FILE):
        print("\n⏸️ 程式已暫停 (等待 GUI 恢復)...", end='\r')
        while os.path.exists(PAUSE_FILE):
            await asyncio.sleep(1)
        print("\n▶️ 程式繼續執行！               ")

async def random_sleep(min_s=0.3, max_s=0.8):
    await asyncio.sleep(random.uniform(min_s, max_s))

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
        document.querySelectorAll('input[type="checkbox"]').forEach(el => {{ if(!el.checked) el.click(); }});
        return count;
    }})()
    """
    try:
        await tab.evaluate(js)
    except:
        pass

async def submit_order_nodriver(tab, captcha_code: str):
    if not captcha_code: return False
    try:
        fill_and_submit_js = f"""
        (function() {{
            var input = document.getElementById('{Selector.CAPTCHA_INPUT[1]}');
            if (input) {{
                input.value = '{captcha_code}';
                input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                var btn = document.querySelector('button[type="submit"]');
                if (btn) {{ btn.click(); return true; }}
            }}
            return false;
        }})()
        """
        result = await tab.evaluate(fill_and_submit_js)
        return result
    except Exception as e:
        print(f"❌ 提交錯誤: {e}")
        return False

async def refresh_captcha_nodriver(tab):
    try:
        await tab.evaluate(f"document.getElementById('{Selector.CAPTCHA_IMAGE[1]}').click();")
        print("🔄 刷新驗證碼")
        await asyncio.sleep(0.5)
        return True
    except:
        pass
    return False

# ----------------------------------------------------
# 頁面處理器 (已加入 check_pause)
# ----------------------------------------------------

async def handle_game_page(tab):
    await check_pause() # 檢查暫停

    current_url = await tab.evaluate("window.location.href")
    if "activity/detail" in current_url and "activity/game" in TIME_WATCH_URL:
        print(f"🚀 [場次頁] 偵測到詳情頁，強制跳轉至: {TIME_WATCH_URL}")
        await tab.get(TIME_WATCH_URL)
        return

    print("👀 [場次頁] 掃描『立即訂購』...")
    scan_js = """
    (function() {
        const tags = ["button", "div", "a"];
        for (let tag of tags) {
            let elements = document.querySelectorAll(tag);
            for (let el of elements) {
                let text = el.innerText.replace(/\\s/g, '');
                if (el.classList.contains('disabled') || text.includes("售完") || text.includes("尚未開賣")) continue;
                if (text.includes("立即訂購")) { el.click(); return true; }
            }
        }
        return false;
    })();
    """
    is_clicked = await tab.evaluate(scan_js)
    if is_clicked:
        print("🔥 [場次頁] 點擊成功！等待跳轉...")
        await asyncio.sleep(0.5)
    else:
        await tab.reload()
        await tab.wait_for("body")

async def handle_area_page(tab):
    await check_pause() # 檢查暫停

    print(f"🎯 [選區頁] 尋找區域: {WANTED_AREA_KEYWORD}...")
    try:
        await tab.wait_for(".select_form_a, .select_form_b, .zone", timeout=1)
    except:
        return

    js_script = f"""
    (function() {{
        const keyword = '{WANTED_AREA_KEYWORD}';
        document.querySelectorAll("footer, img, header").forEach(e => e.remove());
        const links = document.querySelectorAll('.select_form_a a, .select_form_b a, .zone a');
        let clicked = false;
        for (let link of links) {{
            let text = link.innerText.replace(/\\s/g, '');
            if (link.classList.contains('disabled')) continue;
            if (text.includes('售完') || text.includes('Soldout')) continue;
            if (text.includes('剩餘0')) continue; 

            if (text.includes(keyword)) {{ link.click(); clicked = true; break; }}
        }}
        return clicked; 
    }})()
    """
    is_clicked = await tab.evaluate(js_script)
    if is_clicked:
        print("🔥 [選區頁] 點擊區域成功！")
        await asyncio.sleep(0.2) 
    else:
        print(f"⚠️ [選區頁] 找不到可買區域，冷卻刷新 (2秒)...")
        await tab.reload()
        await asyncio.sleep(7)

async def handle_ticket_page(tab):
    await check_pause() # 檢查暫停

    print("📝 [填單頁] 處理中...")
    await pre_fill_form(tab)
    captcha_code = await solve_captcha_nodriver(tab)
    
    # 在送出前再檢查一次暫停 (避免剛好按下暫停卻送出了)
    await check_pause()

    if captcha_code and len(captcha_code) == 4:
        print(f"🚀 [填單頁] 驗證碼 '{captcha_code}'，嘗試送出！")
        await submit_order_nodriver(tab, captcha_code)
        await asyncio.sleep(0.5) 
    else:
        print(f"⚠️ [填單頁] 辨識失敗，刷新驗證碼...")
        await refresh_captcha_nodriver(tab)

# ----------------------------------------------------
# 啟動流程
# ----------------------------------------------------

async def run_initial_setup():
    print("🚀 啟動 nodriver (正式狀態機+暫停功能)...")
    
    import os
    browser = await uc.start(
        headless=False,
        browser_args=["--start-maximized", "--disable-notifications"]
    )
    tab = await browser.get("https://tixcraft.com/")
    
    try:
        await tab.evaluate("if(document.getElementById('onetrust-accept-btn-handler')){document.getElementById('onetrust-accept-btn-handler').click();}")
    except:
        pass

    print("\n🛑 請在倒數結束前登入帳號...")
    watcher = TimeWatcher(TARGET_TIME, TIME_WATCH_URL)
    await watcher.wait_for_open_async()

    print(f"⚡ 時間到！執行直連戰術...")
    current_url = await tab.evaluate("window.location.href")
    if TIME_WATCH_URL not in current_url:
        print(f"🚀 強制直連前往: {TIME_WATCH_URL}")
        await tab.get(TIME_WATCH_URL)
    else:
        print("✅ 已在場次頁，執行刷新...")
        await tab.reload()

    try: await tab.wait_for("body") 
    except: pass
        
    return browser, tab