# time_watcher.py (低頻監控 + 衝刺校正版)

import requests
import time
import sys
import asyncio
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

class TimeWatcher:
    def __init__(self, target_time_str, target_url):
        self.target_url = target_url
        self.target_time = self._parse_target_time(target_time_str)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://tixcraft.com/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        }
        # 初始化時間誤差
        self.time_offset = timedelta(seconds=0)

    def _parse_target_time(self, time_str):
        now = datetime.now()
        try:
            t = datetime.strptime(time_str, "%H:%M:%S")
            target = now.replace(hour=t.hour, minute=t.minute, second=t.second, microsecond=0)
            if target < now:
                target += timedelta(days=1)
            return target
        except ValueError:
            print("❌ 時間格式錯誤！請使用 HH:MM:SS")
            sys.exit(1)

    def sync_time(self):
        """同步伺服器時間"""
        try:
            # print("🔄 對時中...", end="\r") # 減少干擾顯示
            start_req = time.time()
            # 使用 HEAD 請求，極速且低調
            resp = requests.head(self.target_url, headers=self.headers, timeout=5)
            end_req = time.time()
            rtt = end_req - start_req
            
            if "Date" in resp.headers:
                server_time_gmt = parsedate_to_datetime(resp.headers["Date"])
                tw_timezone = timezone(timedelta(hours=8))
                server_time_tw = server_time_gmt.astimezone(tw_timezone).replace(tzinfo=None)
                
                # 校正：Server時間 + RTT/2
                corrected_server_time = server_time_tw + timedelta(seconds=rtt/2)
                
                local_now = datetime.fromtimestamp(end_req)
                self.time_offset = corrected_server_time - local_now
                return True
        except Exception as e:
            # print(f"對時失敗: {e}")
            pass
        return False

    async def wait_for_open_async(self):
        print(f"🎯 目標時間: {self.target_time}")
        print("⏳ 進入【後端低頻監控模式】... (平時每5分對時)")
        
        # 1. 初始對時
        self.sync_time()
        last_sync_time = time.time()
        print(f"✅ 初始對時完成 (誤差: {self.time_offset.total_seconds():.3f}s)")

        while True:
            now = time.time()
            # 計算當下精準時間
            current_server_time = datetime.fromtimestamp(now) + self.time_offset
            remaining = (self.target_time - current_server_time).total_seconds()
            
            # 時間到：提早 0.05 秒回傳，讓 bot.py 有時間反應
            if remaining <= 1:
                print("\n⚡⚡⚡ 時間到！啟動瀏覽器搶票！ ⚡⚡⚡")
                return True
            
            # --- 對時邏輯 ---
            time_since_sync = now - last_sync_time
            
            if remaining <= 10:
                # [最後 10 秒] 每 3 秒對時一次
                # 為了安全，剩餘時間小於 1.5 秒時就不再發送請求，避免網路卡住
                if time_since_sync >= 3 and remaining > 1.5:
                    print(f"\n🔄 [衝刺階段] 精準校時中... (剩 {remaining:.1f} 秒)")
                    self.sync_time()
                    last_sync_time = time.time()
            else:
                # [平時] 每 5 分鐘 (300秒) 對時一次
                if time_since_sync >= 300:
                    print(f"\n🔄 [例行檢查] 伺服器對時中... (剩 {remaining/60:.1f} 分)")
                    self.sync_time()
                    last_sync_time = time.time()

            # --- 顯示倒數 ---
            sys.stdout.write(f"\r⏳ 倒數: {remaining:.1f} 秒   ")
            sys.stdout.flush()
            
            # --- 迴圈休眠 ---
            if remaining > 60:
                await asyncio.sleep(1)
            elif remaining > 10:
                await asyncio.sleep(0.5)
            else:
                await asyncio.sleep(0.05) # 最後衝刺期提高檢查頻率