"""
Database — полная версия для любого бизнеса
"""
import aiosqlite
import os
import json
import uuid
from datetime import datetime, timedelta
from typing import Optional

DATABASE_URL = os.getenv("DATABASE_URL", "bizbot.db")


class Database:
    def __init__(self):
        self.db_path = DATABASE_URL
    
    async def init(self):
        """Создаём ВСЕ таблицы"""
        async with aiosqlite.connect(self.db_path) as db:
            # Таблица бизнесов
            await db.execute("""
                CREATE TABLE IF NOT EXISTS businesses (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    owner_name TEXT,
                    email TEXT UNIQUE,
                    phone TEXT,
                    business_type TEXT DEFAULT 'service',
                    address TEXT,
                    working_hours TEXT,
                    timezone TEXT DEFAULT 'Europe/Moscow',
                    language TEXT DEFAULT 'ru',
                    services TEXT,
                    menu TEXT,
                    catalog TEXT,
                    prices TEXT,
                    delivery_zones TEXT,
                    delivery_price INTEGER DEFAULT 0,
                    delivery_free_from INTEGER DEFAULT 0,
                    delivery_time_min INTEGER DEFAULT 30,
                    delivery_time_max INTEGER DEFAULT 90,
                    min_order_amount INTEGER DEFAULT 0,
                    rooms TEXT,
                    doctors TEXT,
                    specialists TEXT,
                    telegram_bot_token TEXT,
                    telegram_chat_id TEXT,
                    whatsapp_phone TEXT,
                    viber_token TEXT,
                    website_widget_id TEXT,
                    custom_bot_name TEXT DEFAULT 'BizBot',
                    bot_avatar_url TEXT,
                    welcome_message TEXT DEFAULT 'Здравствуйте! Чем могу помочь? 😊',
                    bot_theme TEXT DEFAULT 'purple',
                    subscription_plan TEXT DEFAULT 'trial',
                    subscription_status TEXT DEFAULT 'trial',
                    subscription_expires_at TEXT,
                    messages_used_this_month INTEGER DEFAULT 0,
                    messages_limit INTEGER DEFAULT 500,
                    conversations_this_month INTEGER DEFAULT 0,
                    created_at TEXT,
                    updated_at TEXT,
                    is_active INTEGER DEFAULT 1
                )
            """)
            
            # Таблица диалогов (исправлена - есть все колонки)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    client_name TEXT,
                    client_phone TEXT,
                    client_email TEXT,
                    channel TEXT NOT NULL,
                    business_id TEXT,
                    status TEXT DEFAULT 'active',
                    transferred_to_manager INTEGER DEFAULT 0,
                    assigned_manager TEXT,
                    rating INTEGER,
                    feedback TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    closed_at TEXT
                )
            """)
            
            # Таблица сообщений
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    text TEXT NOT NULL,
                    attachments TEXT,
                    created_at TEXT
                )
            """)
            
            # Таблица бронирований
            await db.execute("""
                CREATE TABLE IF NOT EXISTS bookings (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT,
                    business_id TEXT,
                    client_id TEXT NOT NULL,
                    client_name TEXT,
                    client_phone TEXT,
                    service TEXT,
                    specialist TEXT,
                    duration INTEGER,
                    booking_datetime TEXT,
                    channel TEXT,
                    status TEXT DEFAULT 'confirmed',
                    reminder_sent INTEGER DEFAULT 0,
                    created_at TEXT
                )
            """)
            
            # Таблица заказов
            await db.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id TEXT PRIMARY KEY,
                    business_id TEXT NOT NULL,
                    conversation_id TEXT,
                    client_id TEXT NOT NULL,
                    client_name TEXT,
                    client_phone TEXT,
                    client_address TEXT,
                    items TEXT,
                    subtotal INTEGER,
                    delivery_price INTEGER,
                    total_price INTEGER,
                    payment_method TEXT,
                    payment_status TEXT DEFAULT 'pending',
                    delivery_time TEXT,
                    status TEXT DEFAULT 'new',
                    created_at TEXT,
                    updated_at TEXT,
                    delivered_at TEXT
                )
            """)
            
            # Таблица заявок
            await db.execute("""
                CREATE TABLE IF NOT EXISTS leads (
                    id TEXT PRIMARY KEY,
                    business_id TEXT NOT NULL,
                    conversation_id TEXT,
                    client_id TEXT NOT NULL,
                    client_name TEXT,
                    client_phone TEXT,
                    client_email TEXT,
                    request_type TEXT,
                    request_text TEXT,
                    status TEXT DEFAULT 'new',
                    assigned_manager TEXT,
                    created_at TEXT,
                    processed_at TEXT
                )
            """)
            
            # Таблица сотрудников
            await db.execute("""
                CREATE TABLE IF NOT EXISTS employees (
                    id TEXT PRIMARY KEY,
                    business_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    role TEXT,
                    phone TEXT,
                    telegram_id TEXT,
                    work_hours TEXT,
                    specialties TEXT,
                    is_active INTEGER DEFAULT 1
                )
            """)
            
            # Таблица платежей
            await db.execute("""
                CREATE TABLE IF NOT EXISTS payments (
                    id TEXT PRIMARY KEY,
                    business_id TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    currency TEXT DEFAULT 'RUB',
                    plan TEXT,
                    status TEXT DEFAULT 'pending',
                    yookassa_id TEXT,
                    created_at TEXT,
                    paid_at TEXT
                )
            """)
            
            # Таблица логов
            await db.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    business_id TEXT,
                    level TEXT,
                    action TEXT,
                    details TEXT,
                    ip TEXT,
                    created_at TEXT
                )
            """)
            
            await db.commit()
            print("[OK] База данных инициализирована")
    
    # ==================== BUSINESS METHODS ====================
    
    async def create_business(self, email: str, name: str, owner_name: str, phone: str = None, business_type: str = "service") -> dict:
        business_id = str(uuid.uuid4())[:8]
        widget_id = str(uuid.uuid4())[:16]
        now = datetime.now().isoformat()
        expires_at = (datetime.now() + timedelta(days=14)).isoformat()
        
        async with aiosqlite.connect(self.db_path) as conn:
            try:
                await conn.execute("""
                    INSERT INTO businesses 
                    (id, name, owner_name, email, phone, website_widget_id, business_type,
                     subscription_status, subscription_expires_at, created_at, updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """, (business_id, name, owner_name, email, phone, widget_id, business_type,
                      'trial', expires_at, now, now))
                await conn.commit()
                return {
                    "success": True,
                    "business_id": business_id,
                    "widget_id": widget_id,
                    "trial_days_left": 14
                }
            except Exception as e:
                return {"success": False, "error": str(e)}
    
    async def get_business(self, business_id: str):
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("SELECT * FROM businesses WHERE id=?", (business_id,))
            row = await cursor.fetchone()
            if row:
                data = dict(row)
                for field in ['services', 'menu', 'catalog', 'prices', 'working_hours']:
                    if data.get(field) and isinstance(data[field], str):
                        try:
                            data[field] = json.loads(data[field])
                        except:
                            pass
                return data
            return None
    
    async def update_business(self, business_id: str, updates: dict) -> dict:
        async with aiosqlite.connect(self.db_path) as conn:
            for key, value in updates.items():
                if value is None:
                    continue
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False)
                await conn.execute(
                    f"UPDATE businesses SET {key}=?, updated_at=? WHERE id=?",
                    (value, datetime.now().isoformat(), business_id)
                )
            await conn.commit()
        return {"success": True}
    
    async def get_all_businesses(self, limit: int = 100, offset: int = 0) -> list:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("""
                SELECT id, name, email, business_type, subscription_plan, subscription_status, 
                       subscription_expires_at, created_at, is_active
                FROM businesses 
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
    
    # ==================== CONVERSATION METHODS ====================
    
    async def get_or_create_conversation(self, client_id: str, channel: str, client_name: str = None, 
                                          business_id: str = None, client_phone: str = None, 
                                          client_email: str = None) -> dict:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            
            if business_id:
                cursor = await conn.execute(
                    "SELECT * FROM conversations WHERE client_id = ? AND business_id = ? AND status = 'active' ORDER BY created_at DESC LIMIT 1",
                    (client_id, business_id)
                )
            else:
                cursor = await conn.execute(
                    "SELECT * FROM conversations WHERE client_id = ? AND status = 'active' ORDER BY created_at DESC LIMIT 1",
                    (client_id,)
                )
            row = await cursor.fetchone()
            
            if row:
                return dict(row)
            
            conv_id = str(uuid.uuid4())[:8]
            now = datetime.now().isoformat()
            
            await conn.execute("""
                INSERT INTO conversations 
                (id, client_id, client_name, client_phone, client_email, channel, business_id, status, transferred_to_manager, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (conv_id, client_id, client_name, client_phone, client_email, channel, business_id, "active", 0, now, now))
            await conn.commit()
            
            return {
                "id": conv_id, "client_id": client_id, "client_name": client_name,
                "client_phone": client_phone, "client_email": client_email,
                "channel": channel, "business_id": business_id, "status": "active",
                "transferred_to_manager": 0, "created_at": now, "updated_at": now
            }
    
    async def get_conversations(self, business_id: str = None, status: str = None, limit: int = 50) -> list:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            query = """
                SELECT c.*, 
                       (SELECT text FROM messages WHERE conversation_id=c.id ORDER BY created_at DESC LIMIT 1) as last_message
                FROM conversations c
                WHERE 1=1
            """
            params = []
            
            if business_id:
                query += " AND c.business_id = ?"
                params.append(business_id)
            if status:
                query += " AND c.status = ?"
                params.append(status)
            
            query += " ORDER BY c.updated_at DESC LIMIT ?"
            params.append(limit)
            
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
    
    async def get_conversation(self, conv_id: str) -> dict:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("SELECT * FROM conversations WHERE id=?", (conv_id,))
            row = await cursor.fetchone()
            return dict(row) if row else {}
    
    async def transfer_to_manager(self, conv_id: str, manager_id: str = None):
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
                UPDATE conversations 
                SET transferred_to_manager=1, assigned_manager=?, updated_at=? 
                WHERE id=?
            """, (manager_id, datetime.now().isoformat(), conv_id))
            await conn.commit()
    
    async def close_conversation(self, conv_id: str):
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
                UPDATE conversations 
                SET status='closed', closed_at=?, updated_at=? 
                WHERE id=?
            """, (datetime.now().isoformat(), datetime.now().isoformat(), conv_id))
            await conn.commit()
    
    async def mark_session_closed(self, client_id: str):
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                "UPDATE conversations SET status='closed' WHERE client_id=? AND channel='website'",
                (client_id,)
            )
            await conn.commit()
    
    # ==================== MESSAGE METHODS ====================
    
    async def save_message(self, conv_id: str, role: str, text: str, attachments: list = None):
        if not text:
            return
        async with aiosqlite.connect(self.db_path) as conn:
            attachments_json = json.dumps(attachments, ensure_ascii=False) if attachments else None
            await conn.execute("""
                INSERT INTO messages (conversation_id, role, text, attachments, created_at) 
                VALUES (?,?,?,?,?)
            """, (conv_id, role, text, attachments_json, datetime.now().isoformat()))
            await conn.execute("""
                UPDATE conversations SET updated_at=? WHERE id=?
            """, (datetime.now().isoformat(), conv_id))
            await conn.commit()
    
    async def get_messages(self, conv_id: str) -> list:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at ASC",
                (conv_id,)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
    
    async def get_conversation_history(self, conv_id: str, limit: int = 10) -> list:
        messages = await self.get_messages(conv_id)
        return messages[-limit:] if len(messages) > limit else messages
    
    # ==================== BOOKING METHODS ====================
    
    async def create_booking(self, business_id: str = None, client_id: str = None, client_name: str = None,
                              service: str = None, datetime_str: str = None, channel: str = None, 
                              conversation_id: str = None, specialist: str = None, 
                              duration: int = 60, client_phone: str = None) -> str:
        booking_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()
        
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
                INSERT INTO bookings 
                (id, conversation_id, business_id, client_id, client_name, client_phone, service, specialist, duration, booking_datetime, channel, status, created_at) 
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (booking_id, conversation_id, business_id, client_id, client_name, client_phone,
                  service, specialist, duration, datetime_str, channel, "confirmed", now))
            await conn.commit()
        return booking_id
    
    async def get_bookings(self, business_id: str = None, date: str = None) -> list:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            if business_id and date:
                cursor = await conn.execute("""
                    SELECT * FROM bookings 
                    WHERE business_id=? AND booking_datetime LIKE ? 
                    ORDER BY booking_datetime ASC
                """, (business_id, f"{date}%"))
            elif business_id:
                cursor = await conn.execute("""
                    SELECT * FROM bookings 
                    WHERE business_id=? AND status='confirmed' 
                    ORDER BY booking_datetime ASC LIMIT 100
                """, (business_id,))
            else:
                cursor = await conn.execute("""
                    SELECT * FROM bookings 
                    WHERE status='confirmed' 
                    ORDER BY booking_datetime ASC LIMIT 100
                """)
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
    
    async def get_pending_reminders(self) -> list:
        now = datetime.now()
        in_one_hour = (now + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
        now_str = now.strftime("%Y-%m-%d %H:%M")
        
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("""
                SELECT b.*, c.channel, c.client_id 
                FROM bookings b
                LEFT JOIN conversations c ON b.conversation_id = c.id
                WHERE b.booking_datetime BETWEEN ? AND ?
                AND b.reminder_sent=0 AND b.status='confirmed'
            """, (now_str, in_one_hour))
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
    
    async def mark_reminder_sent(self, booking_id: str):
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("UPDATE bookings SET reminder_sent=1 WHERE id=?", (booking_id,))
            await conn.commit()
    
    # ==================== ORDER METHODS ====================
    
    async def create_order(self, business_id: str = None, client_id: str = None, client_name: str = None,
                            client_phone: str = None, client_address: str = None, items: list = None,
                            subtotal: int = 0, delivery_price: int = 0, total_price: int = 0,
                            conversation_id: str = None, payment_method: str = None) -> str:
        order_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()
        
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
                INSERT INTO orders 
                (id, business_id, conversation_id, client_id, client_name, client_phone, client_address,
                 items, subtotal, delivery_price, total_price, payment_method, status, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (order_id, business_id, conversation_id, client_id, client_name, client_phone, client_address,
                  json.dumps(items, ensure_ascii=False) if items else None, 
                  subtotal, delivery_price, total_price or subtotal + delivery_price, 
                  payment_method, "new", now, now))
            await conn.commit()
        return order_id
    
    async def get_orders(self, business_id: str = None, status: str = None) -> list:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            if business_id and status:
                cursor = await conn.execute("""
                    SELECT * FROM orders 
                    WHERE business_id=? AND status=? 
                    ORDER BY created_at DESC
                """, (business_id, status))
            elif business_id:
                cursor = await conn.execute("""
                    SELECT * FROM orders 
                    WHERE business_id=? 
                    ORDER BY created_at DESC LIMIT 100
                """, (business_id,))
            else:
                cursor = await conn.execute("""
                    SELECT * FROM orders 
                    ORDER BY created_at DESC LIMIT 100
                """)
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
    
    async def update_order_status(self, order_id: str, status: str):
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
                UPDATE orders 
                SET status=?, updated_at=?, delivered_at=CASE WHEN ?='delivered' THEN ? ELSE delivered_at END
                WHERE id=?
            """, (status, datetime.now().isoformat(), status, datetime.now().isoformat(), order_id))
            await conn.commit()
    
    # ==================== LEAD METHODS ====================
    
    async def create_lead(self, business_id: str = None, client_id: str = None, client_name: str = None,
                          request_type: str = "consultation", request_text: str = None, 
                          client_phone: str = None, client_email: str = None,
                          conversation_id: str = None) -> str:
        lead_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()
        
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
                INSERT INTO leads 
                (id, business_id, conversation_id, client_id, client_name, client_phone, client_email,
                 request_type, request_text, status, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (lead_id, business_id, conversation_id, client_id, client_name, client_phone, client_email,
                  request_type, request_text, "new", now))
            await conn.commit()
        return lead_id
    
    async def get_leads(self, business_id: str = None, status: str = None) -> list:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            if business_id and status:
                cursor = await conn.execute("""
                    SELECT * FROM leads 
                    WHERE business_id=? AND status=? 
                    ORDER BY created_at DESC
                """, (business_id, status))
            elif business_id:
                cursor = await conn.execute("""
                    SELECT * FROM leads 
                    WHERE business_id=? 
                    ORDER BY created_at DESC LIMIT 100
                """, (business_id,))
            else:
                cursor = await conn.execute("""
                    SELECT * FROM leads 
                    ORDER BY created_at DESC LIMIT 100
                """)
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
    
    # ==================== STATS METHODS ====================
    
    async def get_stats(self, business_id: str = None) -> dict:
        async with aiosqlite.connect(self.db_path) as conn:
            today = datetime.now().strftime("%Y-%m-%d")
            stats = {}
            
            if business_id:
                cursor = await conn.execute("SELECT COUNT(*) FROM conversations WHERE business_id=?", (business_id,))
                stats["total_conversations"] = (await cursor.fetchone())[0] or 0
                
                cursor = await conn.execute("SELECT COUNT(*) FROM conversations WHERE business_id=? AND created_at LIKE ?", (business_id, f"{today}%"))
                stats["today_conversations"] = (await cursor.fetchone())[0] or 0
                
                cursor = await conn.execute("SELECT COUNT(*) FROM bookings WHERE business_id=?", (business_id,))
                stats["total_bookings"] = (await cursor.fetchone())[0] or 0
                
                cursor = await conn.execute("SELECT COUNT(*) FROM orders WHERE business_id=?", (business_id,))
                stats["total_orders"] = (await cursor.fetchone())[0] or 0
                
                cursor = await conn.execute("SELECT COUNT(*) FROM leads WHERE business_id=?", (business_id,))
                stats["total_leads"] = (await cursor.fetchone())[0] or 0
            else:
                cursor = await conn.execute("SELECT COUNT(*) FROM conversations")
                stats["total_conversations"] = (await cursor.fetchone())[0] or 0
                
                cursor = await conn.execute("SELECT COUNT(*) FROM conversations WHERE created_at LIKE ?", (f"{today}%",))
                stats["today_conversations"] = (await cursor.fetchone())[0] or 0
                
                cursor = await conn.execute("SELECT COUNT(*) FROM bookings")
                stats["total_bookings"] = (await cursor.fetchone())[0] or 0
                
                cursor = await conn.execute("SELECT COUNT(*) FROM orders")
                stats["total_orders"] = (await cursor.fetchone())[0] or 0
                
                cursor = await conn.execute("SELECT COUNT(*) FROM businesses")
                stats["total_businesses"] = (await cursor.fetchone())[0] or 0
            
            cursor = await conn.execute("SELECT COUNT(*) FROM conversations WHERE transferred_to_manager=1")
            stats["transferred"] = (await cursor.fetchone())[0] or 0
            
            cursor = await conn.execute("SELECT channel, COUNT(*) FROM conversations GROUP BY channel")
            rows = await cursor.fetchall()
            stats["by_channel"] = {row[0]: row[1] for row in rows} if rows else {}
            
            return stats