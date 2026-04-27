"""
Business Manager — управление мультитенантностью
Каждый бизнес получает свой ID, свои настройки, свою БД
"""
import uuid
import json
from datetime import datetime
from typing import Optional
import aiosqlite

class BusinessManager:
    def __init__(self, db_path="bizbot.db"):
        self.db_path = db_path
    
    async def init(self):
        """Создаём таблицу бизнесов"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS businesses (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    owner_name TEXT,
                    email TEXT UNIQUE,
                    phone TEXT,
                    services TEXT,  -- JSON: ["услуга1", "услуга2"]
                    prices TEXT,    -- JSON: {"услуга1": 1000}
                    working_hours TEXT,  -- JSON: {"mon-fri": "9-18"}
                    address TEXT,
                    telegram_bot_token TEXT,
                    whatsapp_phone TEXT,
                    website_widget_id TEXT,
                    subscription_plan TEXT DEFAULT 'basic',  -- basic, pro, enterprise
                    subscription_status TEXT DEFAULT 'trial',  -- trial, active, expired
                    subscription_expires_at TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
            await db.commit()
    
    async def create_business(self, email: str, name: str, owner_name: str) -> dict:
        """Создаёт нового клиента-бизнес"""
        business_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO businesses 
                (id, name, owner_name, email, subscription_status, subscription_expires_at, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?)
            """, (business_id, name, owner_name, email, 'trial', 
                  (datetime.now().replace(day=datetime.now().day+14)).isoformat(), now, now))
            await db.commit()
            
            return {
                "id": business_id,
                "name": name,
                "email": email,
                "subscription_status": "trial",
                "trial_days_left": 14
            }
    
    async def get_business(self, business_id: str) -> dict:
        """Получает данные бизнеса"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM businesses WHERE id=?", (business_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def update_settings(self, business_id: str, settings: dict):
        """Обновляет настройки бизнеса"""
        async with aiosqlite.connect(self.db_path) as db:
            for key, value in settings.items():
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False)
                await db.execute(
                    f"UPDATE businesses SET {key}=?, updated_at=? WHERE id=?",
                    (value, datetime.now().isoformat(), business_id)
                )
            await db.commit()
    
    async def get_business_statistics(self, business_id: str) -> dict:
        """Статистика для конкретного бизнеса"""
        async with aiosqlite.connect(self.db_path) as db:
            # Получаем все диалоги этого бизнеса
            cursor = await db.execute(
                "SELECT COUNT(*) FROM conversations WHERE client_id LIKE ?",
                (f"{business_id}_%",)
            )
            total_conv = (await cursor.fetchone())[0]
            
            cursor = await db.execute(
                "SELECT COUNT(*) FROM bookings WHERE client_id LIKE ?",
                (f"{business_id}_%",)
            )
            total_bookings = (await cursor.fetchone())[0]
            
            return {
                "business_id": business_id,
                "total_conversations": total_conv,
                "total_bookings": total_bookings,
                "conversion_rate": round(total_bookings / max(total_conv, 1) * 100, 2)
            }