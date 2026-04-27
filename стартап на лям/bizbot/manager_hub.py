"""
Manager Hub — уведомления менеджеров
"""
import os
import httpx
from datetime import datetime

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
MANAGER_CHAT_ID = os.getenv("MANAGER_TELEGRAM_ID")


class ManagerHub:
    def __init__(self, db):
        self.db = db
    
    async def notify_manager(self, conversation: dict, text: str):
        """Уведомление менеджера о новом диалоге"""
        print(f"[MANAGER] Уведомление: диалог {conversation.get('id')}, сообщение: {text[:100]}")
        # Здесь можно добавить реальную отправку в Telegram
    
    async def forward_to_manager(self, conv_id: str, text: str, user_name: str, channel: str):
        """Пересылка сообщения менеджеру"""
        print(f"[MANAGER] Пересылка: {user_name} ({channel}): {text[:100]}")
    
    async def notify_new_conversation(self, conversation: dict, text: str):
        """Уведомление о новом разговоре"""
        print(f"[MANAGER] Новый диалог: {conversation.get('client_name')} - {text[:100]}")
    
    async def notify_new_order(self, business_id: str, order_id: str, order_data: dict, client_name: str):
        """Уведомление о новом заказе"""
        print(f"[MANAGER] Новый заказ {order_id} от {client_name}")
    
    async def notify_new_lead(self, business_id: str, lead_id: str, lead_data: dict, client_name: str, message: str):
        """Уведомление о новой заявке"""
        print(f"[MANAGER] Новая заявка {lead_id} от {client_name}")