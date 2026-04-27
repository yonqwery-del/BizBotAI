"""
Billing — подписки и платежи
Планы: Basic (990₽), Pro (2990₽), Enterprise (9990₽)
"""
from datetime import datetime, timedelta
import aiosqlite
import asyncio
import json

SUBSCRIPTION_PLANS = {
    "trial": {
        "name": "Пробный период",
        "price": 0,
        "price_rub": "0 ₽",
        "days": 14,
        "limits": {
            "messages_per_month": 500,
            "conversations_per_month": 100,
            "telegram": True,
            "whatsapp": False,
            "website_widget": True,
            "analytics": False,
            "custom_bot_name": False,
            "priority_support": False,
            "api_access": False
        },
        "features": ["Telegram бот", "Виджет на сайт", "500 сообщений/мес"]
    },
    "basic": {
        "name": "Базовый",
        "price": 990,
        "price_rub": "990 ₽/мес",
        "days": 30,
        "limits": {
            "messages_per_month": 2000,
            "conversations_per_month": 500,
            "telegram": True,
            "whatsapp": False,
            "website_widget": True,
            "analytics": True,
            "custom_bot_name": False,
            "priority_support": False,
            "api_access": False
        },
        "features": ["Telegram бот", "Виджет на сайт", "Аналитика", "2000 сообщений/мес"]
    },
    "pro": {
        "name": "Профессиональный",
        "price": 2990,
        "price_rub": "2 990 ₽/мес",
        "days": 30,
        "limits": {
            "messages_per_month": 10000,
            "conversations_per_month": 2000,
            "telegram": True,
            "whatsapp": True,
            "website_widget": True,
            "analytics": True,
            "custom_bot_name": True,
            "priority_support": False,
            "api_access": False
        },
        "features": ["Все каналы", "Свой бренд", "Расширенная аналитика", "10000 сообщений/мес"]
    },
    "enterprise": {
        "name": "Предприятие",
        "price": 9990,
        "price_rub": "9 990 ₽/мес",
        "days": 30,
        "limits": {
            "messages_per_month": 100000,
            "conversations_per_month": "unlimited",
            "telegram": True,
            "whatsapp": True,
            "website_widget": True,
            "analytics": True,
            "custom_bot_name": True,
            "priority_support": True,
            "api_access": True
        },
        "features": ["Безлимит сообщений", "Приоритетная поддержка", "API доступ", "Интеграция с CRM"]
    }
}


class Billing:
    def __init__(self, db):
        self.db_path = db.db_path if hasattr(db, 'db_path') else "bizbot.db"
    
    async def check_subscription(self, business_id: str) -> dict:
        """Проверяет статус подписки бизнеса"""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT subscription_plan, subscription_status, subscription_expires_at FROM businesses WHERE id=?",
                (business_id,)
            )
            row = await cursor.fetchone()
            
            if not row:
                return {"active": False, "error": "Business not found"}
            
            expires_at = datetime.fromisoformat(row["subscription_expires_at"])
            now = datetime.now()
            is_active = row["subscription_status"] == "active" and expires_at > now
            
            return {
                "active": is_active,
                "plan": row["subscription_plan"],
                "plan_details": SUBSCRIPTION_PLANS.get(row["subscription_plan"], {}),
                "expires_at": row["subscription_expires_at"],
                "days_left": max(0, (expires_at - now).days),
                "status": row["subscription_status"]
            }
    
    async def check_limits(self, business_id: str) -> tuple:
        """Проверяет, не превышен ли лимит"""
        sub = await self.check_subscription(business_id)
        if not sub["active"]:
            return False, "Подписка неактивна", 0, 0
        
        plan_limits = SUBSCRIPTION_PLANS[sub["plan"]]["limits"]
        
        async with aiosqlite.connect(self.db_path) as conn:
            month = datetime.now().strftime("%Y-%m")
            cursor = await conn.execute("""
                SELECT COUNT(*) FROM messages m
                JOIN conversations c ON m.conversation_id = c.id
                WHERE c.client_id LIKE ? AND strftime('%Y-%m', m.created_at) = ?
            """, (f"{business_id}_%", month))
            messages_used = (await cursor.fetchone())[0]
            
            limit = plan_limits["messages_per_month"]
            if limit != "unlimited" and messages_used >= limit:
                return False, f"Превышен лимит сообщений ({limit}/мес)", messages_used, limit
        
        return True, "OK", messages_used, plan_limits.get("messages_per_month", 0)
    
    async def upgrade_plan(self, business_id: str, new_plan: str) -> dict:
        """Обновляет тарифный план"""
        if new_plan not in SUBSCRIPTION_PLANS:
            return {"error": "Invalid plan", "success": False}
        
        if new_plan == "trial":
            return {"error": "Cannot downgrade to trial", "success": False}
        
        async with aiosqlite.connect(self.db_path) as conn:
            # Получаем текущий план
            cursor = await conn.execute("SELECT subscription_plan FROM businesses WHERE id=?", (business_id,))
            row = await cursor.fetchone()
            old_plan = row[0] if row else None
            
            now = datetime.now()
            expires_at = now + timedelta(days=30)
            
            await conn.execute("""
                UPDATE businesses 
                SET subscription_plan=?, subscription_status='active', 
                    subscription_expires_at=?, updated_at=?
                WHERE id=?
            """, (new_plan, expires_at.isoformat(), now.isoformat(), business_id))
            await conn.commit()
        
        return {
            "success": True,
            "old_plan": old_plan,
            "new_plan": new_plan,
            "expires_at": expires_at.isoformat(),
            "price": SUBSCRIPTION_PLANS[new_plan]["price_rub"]
        }
    
    async def create_invoice(self, business_id: str, plan: str) -> dict:
        """Создаёт счёт на оплату"""
        plan_data = SUBSCRIPTION_PLANS.get(plan)
        if not plan_data:
            return {"error": "Invalid plan"}
        
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("SELECT name, email FROM businesses WHERE id=?", (business_id,))
            business = await cursor.fetchone()
        
        return {
            "invoice_id": str(uuid.uuid4())[:8],
            "business_id": business_id,
            "business_name": business["name"],
            "email": business["email"],
            "plan": plan,
            "plan_name": plan_data["name"],
            "amount": plan_data["price"],
            "amount_rub": plan_data["price_rub"],
            "period_days": plan_data["days"],
            "created_at": datetime.now().isoformat()
        }
    
    async def get_available_plans(self, current_plan: str = None) -> list:
        """Список доступных планов для апгрейда"""
        plans = []
        for key, plan in SUBSCRIPTION_PLANS.items():
            if key == "trial":
                continue
            plans.append({
                "id": key,
                "name": plan["name"],
                "price": plan["price"],
                "price_rub": plan["price_rub"],
                "features": plan["features"],
                "is_current": key == current_plan,
                "is_upgrade": current_plan < key if current_plan else False
            })
        return plans
    
    async def get_invoice_history(self, business_id: str, limit: int = 20) -> list:
        """История счетов бизнеса"""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("""
                SELECT * FROM invoices 
                WHERE business_id=? 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (business_id, limit))
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
    
    async def auto_check_expired(self):
        """Фоновая задача: проверяет и отключает просроченные подписки"""
        while True:
            try:
                async with aiosqlite.connect(self.db_path) as conn:
                    now = datetime.now().isoformat()
                    
                    # Находим истекшие подписки
                    cursor = await conn.execute("""
                        SELECT id, name, email FROM businesses 
                        WHERE subscription_expires_at < ? AND subscription_status='active'
                    """, (now,))
                    expired = await cursor.fetchall()
                    
                    for biz in expired:
                        # Обновляем статус
                        await conn.execute("""
                            UPDATE businesses 
                            SET subscription_status='expired', is_active=0, updated_at=?
                            WHERE id=?
                        """, (now, biz[0]))
                        
                        # Логируем
                        await conn.execute("""
                            INSERT INTO business_logs (business_id, action, details, created_at)
                            VALUES (?, ?, ?, ?)
                        """, (biz[0], "subscription_expired", f"Plan expired for {biz[1]}", now))
                    
                    await conn.commit()
                    
                    if expired:
                        print(f"⚠️ Deactivated {len(expired)} expired subscriptions")
                
            except Exception as e:
                print(f"Auto-check error: {e}")
            
            await asyncio.sleep(86400)  # Раз в день


import uuid