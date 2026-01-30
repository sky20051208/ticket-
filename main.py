# main.py (正式版 V16.0 - 拓元/KKTIX 雙模組整合版)

import sys
import os
import asyncio
import nodriver as uc

# 路徑設定 (保持不變)
if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
    sys.path.append(application_path)
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    sys.path.append(application_path)

# 匯入設定檔與拓元模組
from config import PLATFORM, TIME_WATCH_URL
from bot import run_initial_setup, handle_game_page, handle_area_page, handle_ticket_page, handle_verify_page, check_pause

# [新增] 匯入 KKTIX 模組
try:
    from kktix import kkbot as kktix_bot
except ImportError:
    kktix_bot = None

async def main():
    print(f"--- 搶票輔助機器人 V16.0 (目前平台: {PLATFORM}) ---")
    
    # === 根據平台選擇進入點 ===
    if PLATFORM == "KKTIX":
        if kktix_bot:
            # 直接執行 kkbot.py 裡面的主邏輯
            await kktix_bot.main()
        else:
            print("❌ 找不到 kktix/kkbot.py 檔案，請檢查路徑。")
        return

    # === 原本的拓元 (Tixcraft) 邏輯 ===
    try:
        # run_initial_setup 內部已經啟動了 CDP 監聽器
        browser, tab = await run_initial_setup()
    except Exception as e:
        print(f"❌ 啟動失敗: {e}")
        input("按 Enter 鍵退出...") 
        return
    
    if not tab: return

    print("\n🤖 拓元模式已接管... (關閉視窗可結束)")
    print("🛡️ CDP 全域監聽器運作中，自動防禦彈窗。")
    
    fail_count = 0
    MAX_FAIL_COUNT = 20

    while True:
        try:
            await check_pause()

            if not browser or not tab: 
                print("🛑 瀏覽器物件遺失。")
                break
            
            current_url = await tab.evaluate("window.location.href")
            fail_count = 0 
            
            # === 拓元狀態機判斷 ===
            
            # 1. 搶票成功
            if "/ticket/checkout" in current_url:
                print(f"\n🎉🎉🎉 搶票成功！網址: {current_url}")
                print("⏳ 程式保持開啟 1 小時，請盡快付款...")
                await asyncio.sleep(3600)
                break 

            # 2. 轉圈圈 (訂單處理中)
            elif "/ticket/order" in current_url:
                print("⏳ [轉圈圈] 訂單處理中... (監聽器待命中)", end='\r')
                await asyncio.sleep(0.5)
                continue

            # 3. 預購驗證頁
            elif "/ticket/verify" in current_url:
                await handle_verify_page(tab)

            # 4. 填單頁
            elif "/ticket/ticket" in current_url:
                await handle_ticket_page(tab)
            
            # 5. 選區頁
            elif "/ticket/area" in current_url:
                await handle_area_page(tab)
            
            # 6. 場次/詳情頁
            elif "/activity/game" in current_url or "/activity/detail" in current_url:
                await handle_game_page(tab)
            
            # 7. 其他
            else:
                await asyncio.sleep(1)

        except Exception as e:
            err_msg = str(e).lower()
            if "connection" in err_msg or "closed" in err_msg:
                fail_count += 1
                if fail_count >= MAX_FAIL_COUNT:
                    print("\n🛑 視窗已關閉，程式結束。")
                    break
            await asyncio.sleep(0.5)

    print("\n程式結束。")

if __name__ == "__main__":
    uc.loop().run_until_complete(main())