"""
Scheduler — напоминания клиентам
"""
import asyncio
import os
import httpx
from datetime import datetime


class Scheduler:
    def __init__(self, db):
        self.db = db
        self.running = False
    
    async def start(self):
        self.running = True
        asyncio.create_task(self._check_loop())
        print("[OK] Scheduler started")
    
    async def _check_loop(self):
        while self.running:
            await self._send_reminders()
            await asyncio.sleep(300)
    
    async def _send_reminders(self):
        bookings = await self.db.get_pending_reminders()
        for booking in bookings:
            try:
                await self._send_reminder(booking)
                await self.db.mark_reminder_sent(booking["id"])
            except Exception as e:
                print(f"Reminder error: {e}")
    
    async def _send_reminder(self, booking: dict):
        channel = booking.get("channel", "telegram")
        client_id = booking.get("client_id", "")
        name = booking.get("client_name", "Клиент")
        service = booking.get("service", "услугу")
        dt = booking.get("booking_datetime", "")
        
        text = f"⏰ Напоминаем! Через час у вас {service} в {dt}. Ждём вас!"
        
        if channel == "telegram" and client_id.startswith("tg_"):
            chat_id = client_id[3:]
            await self._send_telegram(chat_id, text)
    
    async def _send_telegram(self, chat_id: str, text: str):
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            return
        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text},
                timeout=10
            )
    
    async def schedule_reminder(self, booking_id: str, datetime_str: str):
        print(f"[SCHEDULER] Напоминание для {booking_id} на {datetime_str} запланировано")