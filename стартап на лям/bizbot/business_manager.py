"""
Business Manager — управление мультитенантностью
Каждый бизнес получает свой ID, свои настройки, свою БД
"""
import uuid
import json
import aiosqlite
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
import hashlib
import secrets


class BusinessManager:
    def __init__(self, db_path="bizbot.db"):
        self.db_path = db_path
    
    async def init(self):
        """Создаём все таблицы для бизнесов"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS businesses (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    owner_name TEXT,
                    email TEXT UNIQUE NOT NULL,
                    phone TEXT,
                    services TEXT,
                    prices TEXT,
                    working_hours TEXT,
                    address TEXT,
                    telegram_bot_token TEXT,
                    telegram_chat_id TEXT,
                    whatsapp_phone TEXT,
                    website_widget_id TEXT,
                    custom_bot_name TEXT DEFAULT 'BizBot',
                    bot_avatar_url TEXT,
                    welcome_message TEXT DEFAULT 'Здравствуйте! Чем могу помочь? 😊',
                    subscription_plan TEXT DEFAULT 'trial',
                    subscription_status TEXT DEFAULT 'trial',
                    subscription_expires_at TEXT,
                    messages_used_this_month INTEGER DEFAULT 0,
                    messages_limit INTEGER DEFAULT 500,
                    created_at TEXT,
                    updated_at TEXT,
                    is_active INTEGER DEFAULT 1
                );
                
                CREATE TABLE IF NOT EXISTS business_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    business_id TEXT NOT NULL,
                    action TEXT,
                    details TEXT,
                    created_at TEXT,
                    FOREIGN KEY (business_id) REFERENCES businesses(id)
                );
                
                CREATE TABLE IF NOT EXISTS business_analytics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    business_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    conversations_count INTEGER DEFAULT 0,
                    bookings_count INTEGER DEFAULT 0,
                    messages_count INTEGER DEFAULT 0,
                    UNIQUE(business_id, date)
                );
            """)
            await db.commit()
    
    async def create_business(self, email: str, name: str, owner_name: str, phone: str = None) -> Dict:
        """Создаёт нового клиента-бизнес"""
        business_id = str(uuid.uuid4())[:8]
        widget_id = secrets.token_hex(16)
        now = datetime.now().isoformat()
        expires_at = (datetime.now().replace(day=datetime.now().day + 14)).isoformat()
        
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("""
                    INSERT INTO businesses 
                    (id, name, owner_name, email, phone, website_widget_id, 
                     subscription_status, subscription_expires_at, created_at, updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                """, (business_id, name, owner_name, email, phone, widget_id,
                      'trial', expires_at, now, now))
                await db.commit()
                
                # Логируем создание
                await self._log_action(business_id, "business_created", f"Created by {email}")
                
                return {
                    "success": True,
                    "business_id": business_id,
                    "name": name,
                    "email": email,
                    "widget_id": widget_id,
                    "subscription_status": "trial",
                    "trial_days_left": 14
                }
            except aiosqlite.IntegrityError:
                return {"success": False, "error": "Business with this email already exists"}
    
    async def get_business(self, business_id: str) -> Optional[Dict]:
        """Получает данные бизнеса"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM businesses WHERE id=?", (business_id,))
            row = await cursor.fetchone()
            if row:
                data = dict(row)
                # Декодируем JSON поля
                for field in ['services', 'prices', 'working_hours']:
                    if data.get(field):
                        try:
                            data[field] = json.loads(data[field])
                        except:
                            data[field] = None
                return data
            return None
    
    async def get_business_by_widget_id(self, widget_id: str) -> Optional[Dict]:
        """Находит бизнес по ID виджета"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM businesses WHERE website_widget_id=?", (widget_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def update_business(self, business_id: str, updates: Dict) -> Dict:
        """Обновляет данные бизнеса"""
        async with aiosqlite.connect(self.db_path) as db:
            for key, value in updates.items():
                if value is None:
                    continue
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False)
                await db.execute(
                    f"UPDATE businesses SET {key}=?, updated_at=? WHERE id=?",
                    (value, datetime.now().isoformat(), business_id)
                )
            await db.commit()
            
            await self._log_action(business_id, "settings_updated", f"Updated fields: {list(updates.keys())}")
        
        return {"success": True, "updated_fields": list(updates.keys())}
    
    async def get_business_statistics(self, business_id: str, period: str = "month") -> Dict:
        """Детальная статистика для бизнеса"""
        async with aiosqlite.connect(self.db_path) as db:
            now = datetime.now()
            
            # Получаем дату начала периода
            if period == "week":
                start_date = (now - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
            elif period == "month":
                start_date = now.replace(day=1).strftime("%Y-%m-%d")
            else:
                start_date = "2000-01-01"
            
            # Общая статистика
            cursor = await db.execute(
                "SELECT COUNT(*) FROM conversations WHERE client_id LIKE ?",
                (f"{business_id}_%",)
            )
            total_conversations = (await cursor.fetchone())[0]
            
            cursor = await db.execute(
                "SELECT COUNT(*) FROM conversations WHERE client_id LIKE ? AND status='active'",
                (f"{business_id}_%",)
            )
            active_conversations = (await cursor.fetchone())[0]
            
            cursor = await db.execute(
                "SELECT COUNT(*) FROM bookings WHERE client_id LIKE ?",
                (f"{business_id}_%",)
            )
            total_bookings = (await cursor.fetchone())[0]
            
            # Статистика по дням за период
            cursor = await db.execute("""
                SELECT DATE(created_at) as date, COUNT(*) as count
                FROM conversations
                WHERE client_id LIKE ? AND DATE(created_at) >= ?
                GROUP BY DATE(created_at)
                ORDER BY date DESC
            """, (f"{business_id}_%", start_date))
            daily_conv = {row[0]: row[1] for row in await cursor.fetchall()}
            
            # Сообщения за период
            cursor = await db.execute("""
                SELECT COUNT(*) FROM messages m
                JOIN conversations c ON m.conversation_id = c.id
                WHERE c.client_id LIKE ? AND DATE(m.created_at) >= ?
            """, (f"{business_id}_%", start_date))
            period_messages = (await cursor.fetchone())[0]
            
            return {
                "business_id": business_id,
                "total_conversations": total_conversations,
                "active_conversations": active_conversations,
                "total_bookings": total_bookings,
                "period_messages": period_messages,
                "period": period,
                "daily_stats": [{"date": k, "count": v} for k, v in daily_conv.items()],
                "conversion_rate": round(total_bookings / max(total_conversations, 1) * 100, 2)
            }
    
    async def get_all_businesses(self, limit: int = 100, offset: int = 0) -> list:
        """Список всех бизнесов для админа"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT id, name, email, subscription_plan, subscription_status, 
                       subscription_expires_at, created_at, is_active
                FROM businesses 
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
    
    async def _log_action(self, business_id: str, action: str, details: str = None):
        """Логирует действие бизнеса"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO business_logs (business_id, action, details, created_at) VALUES (?,?,?,?)",
                (business_id, action, details, datetime.now().isoformat())
            )
            await db.commit()
    
    async def increment_usage(self, business_id: str, field: str):
        """Увеличивает счётчик использования"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                f"UPDATE businesses SET {field} = {field} + 1, updated_at=? WHERE id=?",
                (datetime.now().isoformat(), business_id)
            )
            await db.commit()