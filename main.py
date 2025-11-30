# main.py (正式版 V13.0 - 配合 Selenium 寄生版)

import sys
import os
import asyncio
import nodriver as uc

# 路徑設定
if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
    sys.path.append(application_path)
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    sys.path.append(application_path)

# [修改] 只需要導入核心流程函式，不需要 send_os_enter
from bot import run_initial_setup, handle_game_page, handle_area_page, handle_ticket_page, check_pause

async def main():
    print("--- Tixcraft 搶票輔助機器人 V13.0 (Selenium 寄生版) ---")
    
    try:
        # run_initial_setup 內部已經會啟動 Selenium 執行緒了
        browser, tab = await run_initial_setup()
    except Exception as e:
        print(f"❌ 啟動失敗: {e}")
        input("按 Enter 鍵退出...") 
        return
    
    if not tab: return

    print("\n🤖 機器人已接管... (關閉視窗可結束)")
    print("🛡️ Selenium 守護神已在背景執行，自動防禦彈窗。")
    
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
            
            # === 狀態機判斷 ===
            
            # 1. 搶票成功
            if "/ticket/checkout" in current_url:
                print(f"\n🎉🎉🎉 搶票成功！網址: {current_url}")
                print("⏳ 程式保持開啟 1 小時，請盡快付款...")
                await asyncio.sleep(3600)
                break 

            # 2. 轉圈圈 (訂單處理中)
            elif "/ticket/order" in current_url:
                # 這裡不需要做任何事，Selenium 執行緒會在背景監控彈窗
                # 如果跳出「沒票」彈窗，Selenium 會按掉 -> 網址變回 area -> 下一圈迴圈會自動接手重選
                print("⏳ [轉圈圈] 訂單處理中...", end='\r')
                await asyncio.sleep(0.5)
                continue

            # 3. 填單頁
            elif "/ticket/ticket" in current_url:
                await handle_ticket_page(tab)
            
            # 4. 選區頁
            elif "/ticket/area" in current_url:
                await handle_area_page(tab)
            
            # 5. 場次/詳情頁
            elif "/activity/game" in current_url or "/activity/detail" in current_url:
                await handle_game_page(tab)
            
            # 6. 其他
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