# main.py (轉圈圈等待 + 成功掛機版)

import sys
import os

# 強制將「執行檔所在的目錄」加入模組搜尋路徑
if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
    sys.path.append(application_path)
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    sys.path.append(application_path)

import asyncio
import nodriver as uc
# 確保 bot.py 裡有 check_pause
from bot import run_initial_setup, handle_game_page, handle_area_page, handle_ticket_page, check_pause

async def main():
    print("--- Tixcraft 搶票輔助機器人 V5.4 (轉圈圈守護版) ---")
    
    # 1. 啟動
    try:
        browser, tab = await run_initial_setup()
    except Exception as e:
        print(f"❌ 啟動失敗: {e}")
        input("按 Enter 鍵退出...") 
        return
    
    if not tab:
        return

    print("\n🤖 機器人已接管，進入自動搶票狀態機...")
    print("💡 若要結束程式，請直接關閉 Chrome 視窗即可。\n")

    # 斷線容錯計數器 (關鍵：防止轉圈圈時誤判退出)
    fail_count = 0
    MAX_FAIL_COUNT = 20 # 容許連續失敗 20 次 (約 10 秒)，轉圈圈夠用了

    while True:
        try:
            await check_pause()

            if not browser or not tab: 
                print("🛑 瀏覽器物件遺失。")
                break
            
            # 嘗試獲取網址
            current_url = await tab.evaluate("window.location.href")
            
            # 若成功獲取網址，重置錯誤計數
            fail_count = 0
            
            # === 狀態判斷 ===
            
            # 1. 搶票成功 (結帳頁)
            if "/ticket/checkout" in current_url:
                print(f"\n🎉🎉🎉 搶票成功！已抵達結帳頁面！ 🎉🎉🎉")
                print(f"網址: {current_url}")
                print("⏳ 程式將保持開啟 1 小時，請盡快完成付款...")
                
                # [需求] 成功後掛機 3600 秒，不關閉瀏覽器
                await asyncio.sleep(3600)
                break 

            # 2. 轉圈圈中 (處理頁)
            elif "/ticket/order" in current_url:
                # [需求] 就在這裡死等，什麼都不做，直到網址改變
                print("⏳ [轉圈圈] 訂單處理中... (請勿關閉)", end='\r')
                await asyncio.sleep(0.5)
                continue

            # 3. 填單頁
            elif "/ticket/ticket" in current_url:
                await handle_ticket_page(tab)
            
            # 4. 選區頁 (被踢回來)
            elif "/ticket/area" in current_url:
                await handle_area_page(tab)
            
            # 5. 場次頁 (起點)
            elif "/activity/game" in current_url or "/activity/detail" in current_url:
                await handle_game_page(tab)
                
            # 6. 其他頁面
            else:
                await asyncio.sleep(1)

        except Exception as e:
            err_msg = str(e).lower()
            
            # 偵測是否為斷線錯誤
            if "connection" in err_msg or "closed" in err_msg or "refused" in err_msg or "reset" in err_msg:
                fail_count += 1
                # 在轉圈圈時，斷線是正常的 (因為頁面正在跳轉)，所以給予寬容度
                print(f"⚠️ 連線不穩/轉圈跳轉中 ({fail_count}/{MAX_FAIL_COUNT})...", end='\r')
                
                if fail_count >= MAX_FAIL_COUNT:
                    print("\n🛑 偵測到視窗已長時間關閉 (或嚴重斷線)，程式結束。")
                    break
            else:
                # 其他錯誤 (如 DOM 變動) 忽略
                pass
                
            await asyncio.sleep(0.5)

    print("\n程式結束。")

if __name__ == "__main__":
    uc.loop().run_until_complete(main())