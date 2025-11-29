# main.py (正式版 V9.6 - 物理 Enter 轉圈圈轟炸)

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

# [修改] 移除 handle_order_page，加入 send_os_enter
from bot import run_initial_setup, handle_game_page, handle_area_page, handle_ticket_page, check_pause, send_os_enter

async def main():
    print("--- Tixcraft 搶票輔助機器人 V9.6 (物理 Enter 版) ---")
    
    try:
        browser, tab = await run_initial_setup()
    except Exception as e:
        print(f"❌ 啟動失敗: {e}")
        input("按 Enter 鍵退出...") 
        return
    
    if not tab: return

    print("\n🤖 機器人已接管... (關閉視窗可結束)")
    
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
            
            if "/ticket/checkout" in current_url:
                print(f"\n🎉🎉🎉 搶票成功！網址: {current_url}")
                print("⏳ 程式保持開啟 1 小時，請盡快付款...")
                await asyncio.sleep(3600)
                break 

            elif "/ticket/order" in current_url:
                # [核心修改] 轉圈圈時，持續按 Enter (防禦沒票彈窗)
                print("⏳ [轉圈圈] 持續 Enter 轟炸中...", end='\r')
                send_os_enter()
                await asyncio.sleep(0.2) # 頻率不用太高，0.2秒一次即可
                continue

            elif "/ticket/ticket" in current_url:
                await handle_ticket_page(tab)
            
            elif "/ticket/area" in current_url:
                await handle_area_page(tab)
            
            elif "/activity/game" in current_url or "/activity/detail" in current_url:
                await handle_game_page(tab)
            
            else:
                await asyncio.sleep(1)

        except Exception as e:
            err_msg = str(e).lower()
            if "connection" in err_msg or "closed" in err_msg:
                fail_count += 1
                if fail_count >= MAX_FAIL_COUNT:
                    print("\n🛑 視窗已關閉。")
                    break
            await asyncio.sleep(0.5)

    print("\n程式結束。")

if __name__ == "__main__":
    uc.loop().run_until_complete(main())