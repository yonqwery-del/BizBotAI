"""
Payment — интеграция с ЮKassa (бывшая Яндекс.Касса)
Для приёма платежей от бизнесов
"""
import uuid
import json
import aiohttp
import hashlib
import hmac
import os
import aiosqlite
from datetime import datetime
from typing import Optional

# Настройки ЮKassa (получить в dashboard.yookassa.ru)
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID", "ваш_shop_id")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY", "ваш_secret_key")
YOOKASSA_URL = "https://api.yookassa.ru/v3/payments"


class PaymentProcessor:
    def __init__(self, db):
        self.db = db
        self.shop_id = YOOKASSA_SHOP_ID
        self.secret_key = YOOKASSA_SECRET_KEY
    
    async def create_payment(self, business_id: str, plan: str, return_url: str) -> dict:
        """Создаёт платёж для подписки"""
        from billing import SUBSCRIPTION_PLANS
        
        plan_data = SUBSCRIPTION_PLANS.get(plan)
        if not plan_data:
            return {"error": "Invalid plan", "success": False}
        
        # Получаем данные бизнеса
        business = await self.db.get_business(business_id)
        if not business:
            return {"error": "Business not found", "success": False}
        
        payment_id = str(uuid.uuid4())
        
        # Данные для платежа
        payment_data = {
            "amount": {
                "value": str(plan_data["price"]),
                "currency": "RUB"
            },
            "payment_method_data": {
                "type": "bank_card"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": return_url
            },
            "description": f"Подписка BizBot - {plan_data['name']} для {business['name']}",
            "metadata": {
                "business_id": business_id,
                "plan": plan,
                "payment_id": payment_id
            },
            "capture": True
        }
        
        # Авторизация в ЮKassa
        auth = aiohttp.BasicAuth(self.shop_id, self.secret_key)
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    YOOKASSA_URL,
                    json=payment_data,
                    auth=auth,
                    headers={"Idempotence-Key": payment_id}
                ) as resp:
                    result = await resp.json()
                    
                    if resp.status == 200:
                        # Сохраняем информацию о платеже
                        await self._save_payment({
                            "payment_id": payment_id,
                            "business_id": business_id,
                            "plan": plan,
                            "amount": plan_data["price"],
                            "status": "pending",
                            "yookassa_id": result["id"],
                            "confirmation_url": result["confirmation"]["confirmation_url"],
                            "created_at": datetime.now().isoformat()
                        })
                        
                        return {
                            "success": True,
                            "payment_id": payment_id,
                            "confirmation_url": result["confirmation"]["confirmation_url"],
                            "amount": plan_data["price_rub"]
                        }
                    else:
                        return {"success": False, "error": result.get("description", "Payment error")}
                        
            except Exception as e:
                return {"success": False, "error": str(e)}
    
    async def handle_webhook(self, payload: dict) -> dict:
        """Обрабатывает webhook от ЮKassa"""
        event = payload.get("event")
        payment_object = payload.get("object", {})
        
        if event == "payment.succeeded":
            # Платёж успешен
            metadata = payment_object.get("metadata", {})
            business_id = metadata.get("business_id")
            plan = metadata.get("plan")
            yookassa_id = payment_object.get("id")
            
            # Обновляем статус платежа
            await self._update_payment_status(yookassa_id, "succeeded")
            
            # Активируем подписку
            from billing import Billing
            billing = Billing(self.db)
            result = await billing.upgrade_plan(business_id, plan)
            
            return {"success": True, "message": "Subscription activated"}
        
        elif event == "payment.canceled":
            # Платёж отменён
            metadata = payment_object.get("metadata", {})
            yookassa_id = payment_object.get("id")
            await self._update_payment_status(yookassa_id, "canceled")
            
            return {"success": True, "message": "Payment canceled"}
        
        return {"success": True}
    
    async def _save_payment(self, payment_data: dict):
        """Сохраняет информацию о платеже"""
        async with aiosqlite.connect(self.db.db_path) as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS payments (
                    payment_id TEXT PRIMARY KEY,
                    business_id TEXT,
                    plan TEXT,
                    amount INTEGER,
                    status TEXT,
                    yookassa_id TEXT,
                    confirmation_url TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
            
            await conn.execute("""
                INSERT INTO payments 
                (payment_id, business_id, plan, amount, status, yookassa_id, confirmation_url, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (
                payment_data["payment_id"],
                payment_data["business_id"],
                payment_data["plan"],
                payment_data["amount"],
                payment_data["status"],
                payment_data["yookassa_id"],
                payment_data["confirmation_url"],
                payment_data["created_at"],
                payment_data["created_at"]
            ))
            await conn.commit()
    
    async def _update_payment_status(self, yookassa_id: str, status: str):
        """Обновляет статус платежа"""
        async with aiosqlite.connect(self.db.db_path) as conn:
            await conn.execute("""
                UPDATE payments 
                SET status=?, updated_at=?
                WHERE yookassa_id=?
            """, (status, datetime.now().isoformat(), yookassa_id))
            await conn.commit()