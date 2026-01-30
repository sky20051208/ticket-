# kktix/kkbot.py

import asyncio
import nodriver as uc
import os
import sys
import random

# --- 確保能抓到根目錄的 config ---
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from timeWatcher import TimeWatcher
from config import WANTED_TICKET_COUNT, WANTED_AREA_KEYWORD, WANTED_DATE_KEYWORD, TARGET_TIME, TIME_WATCH_URL, ENABLE_TIME_WATCHER

PAUSE_FILE = "pause.lock"

# ----------------------------------------------------
# 輔助函式
# ----------------------------------------------------

async def check_pause():
    if os.path.exists(PAUSE_FILE):
        print("\n⏸️ [KKTIX] 程式已暫停 (等待 GUI 恢復)...", end='\r')
        while os.path.exists(PAUSE_FILE):
            await asyncio.sleep(1)
        print("\n▶️ [KKTIX] 繼續執行！               ")

# ----------------------------------------------------
# 核心處理器
# ----------------------------------------------------

async def handle_kktix_event_page(tab):
    """
    [活動頁] 根據 日期關鍵字 點擊對應的下一步
    """
    await check_pause()
    
    # [修正] 將日期關鍵字傳入 JS，在點擊按鈕前先確認該列是否有該日期
    js = f"""
    (function() {{
        let dateKeyword = '{WANTED_DATE_KEYWORD}'; 
        // 抓取所有可能的按鈕
        let btns = document.querySelectorAll('a.btn-point, button.btn-primary');
        
        for (let btn of btns) {{
            // 1. 檢查按鈕狀態
            if (btn.classList.contains('disabled')) {{ continue; }}
            
            // 2. 檢查按鈕文字 (必須是下一步相關)
            let text = btn.innerText.trim();
            if (!text.includes('下一步') && !text.includes('Next') && !text.includes('立即')) {{
                continue;
            }}

            // 3. [核心] 日期關鍵字篩選
            // 如果有設定日期，就往上找父元素(tr 或 div)，看文字有沒有包含日期
            if (dateKeyword) {{
                // 嘗試找最近的行容器 (Table Row 或 Ticket Unit)
                let container = btn.closest('tr') || btn.closest('.ticket-unit') || btn.closest('div.description') || btn.closest('li');
                
                // 如果找不到容器，或容器文字不包含日期關鍵字，就跳過這顆按鈕
                if (container && !container.innerText.includes(dateKeyword)) {{
                    continue; 
                }}
            }}

            // 通過所有檢查，點擊！
            btn.click();
            return true;
        }}
        return false;
    }})()
    """
    
    if await tab.evaluate(js):
        print(f"\n🔥🔥🔥 [活動頁] 鎖定日期 '{WANTED_DATE_KEYWORD}'，已點擊下一步！")
        return True
    return False

async def handle_kktix_register_page(tab):
    """[填單頁] 鎖定價格列、填入張數、勾選、送出"""
    await check_pause()
    
    # 這裡不需要再檢查日期了，因為上一步已經選對場次進來了
    js = f"""
    (function() {{
        let targetPrice = '{WANTED_AREA_KEYWORD}';
        let count = '{WANTED_TICKET_COUNT}';
        let ticketFound = false;

        let checkbox = document.querySelector('input[type="checkbox"]');
        if (checkbox && !checkbox.checked) {{ checkbox.click(); }}

        let rows = document.querySelectorAll('.ticket-unit, tr[id^="ticket_"]');
        for (let row of rows) {{
            let priceEl = row.querySelector('.ticket-price');
            if (!priceEl) continue;

            let priceText = priceEl.innerText.replace(/[^0-9]/g, '');
            
            if (priceText === targetPrice) {{
                let qtyInput = row.querySelector('input[type="text"], input[type="number"], .ticket-quantity input');
                if (qtyInput) {{
                    qtyInput.focus();
                    qtyInput.value = count;
                    qtyInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    qtyInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    ticketFound = true;
                    break;
                }}
            }}
        }}

        if (ticketFound) {{
            let nextBtn = document.querySelector('.btn.btn-primary.btn-lg.ng-scope');
            if (nextBtn) {{
                nextBtn.click();
                return "SUCCESS";
            }}
        }}
        return ticketFound ? "FILLED" : "NOT_FOUND";
    }})()
    """
    result = await tab.evaluate(js)
    if result == "SUCCESS":
        print("\n🚀 [填單完成] 成功送出！")
        return True
    return False

# ----------------------------------------------------
# 啟動邏輯
# ----------------------------------------------------

async def run_kktix_setup():
    print("🚀 KKTIX 模式啟動。")
    print("💡 請先完成登入，隨後進入活動頁等待倒數。")
    
    browser = await uc.start(
        headless=False,
        browser_args=["--start-maximized", "--disable-notifications"]
    )
    tab = await browser.get("https://kktix.com/users/sign_in")

    async def handle_dialog(event: uc.cdp.page.JavascriptDialogOpening):
        await tab.send(uc.cdp.page.handle_java_script_dialog(accept=True))

    await tab.send(uc.cdp.page.enable())
    tab.add_handler(uc.cdp.page.JavascriptDialogOpening, handle_dialog)

    return browser, tab

async def main():
    browser, tab = await run_kktix_setup()
    
    watcher = TimeWatcher(TARGET_TIME, TIME_WATCH_URL)
    has_waited = not ENABLE_TIME_WATCHER

    print(f"\n⏳ 監控啟動！目標時間: {TARGET_TIME}")
    if WANTED_DATE_KEYWORD:
        print(f"📅 目標日期: {WANTED_DATE_KEYWORD}")

    print("👉 策略：可手動待在 /events/ 或是嘗試進入 /registrations/new (偷跑)")

    while True:
        try:
            await check_pause()
            if not browser or not tab: break

            current_url = await tab.evaluate("window.location.href")
            
            # === [時間鎖] ===
            if not has_waited:
                if "/events/" in current_url or "/registrations/" in current_url:
                    await watcher.wait_for_open_async()
                    has_waited = True
                    print("\n⚡ 時間到！執行戰術動作！")
                    
                    if "/registrations/" in current_url:
                        print("🔄 [偷跑模式] 時間到，立即刷新頁面！")
                        await tab.reload()
                        await asyncio.sleep(0.5)
                else:
                    await asyncio.sleep(1)
                    continue

            # === [狀態機] ===

            # 1. 填單頁
            if "/registrations/new" in current_url:
                if await handle_kktix_register_page(tab):
                    await asyncio.sleep(2) 

            # 2. 訂單確認頁
            elif "/registrations/" in current_url and "/new" not in current_url:
                print(f"\n🎉🎉🎉 [恭喜] 搶票成功！進入訂單確認頁面！")
                print("🛑 機器人已停止操作，請盡快完成後續付款流程。")
                while True:
                    await asyncio.sleep(10)
            
            # 3. 活動頁
            elif "/events/" in current_url:
                clicked = await handle_kktix_event_page(tab)
                if clicked:
                    # 點擊成功後等待跳轉
                    await asyncio.sleep(0.1)
                else:
                    # 沒點到按鈕 (可能未開賣或日期不對)
                    print(f"🔄 [清票/等待] 刷新重試...", end='\r')
                    await tab.reload()
                    delay = random.uniform(0.8, 1.5)
                    await asyncio.sleep(delay)
                
            else:
                await asyncio.sleep(0.5)

        except Exception:
            await asyncio.sleep(0.1)

if __name__ == "__main__":
    uc.loop().run_until_complete(main())