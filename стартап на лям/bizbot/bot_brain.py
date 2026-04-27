"""
BotBrain — мозг бота на GigaChat от Сбера (РАБОЧАЯ ВЕРСИЯ)
"""
import json
import re
import asyncio
import aiohttp
import ssl
from datetime import datetime

# GigaChat настройки
CLIENT_ID = "019dc59f-ce68-7a8e-a873-7ceac3acbd0f"
CLIENT_SECRET = "17711145-dfaa-4a4e-8143-08c61f18f2f4"
AUTH_KEY = "MDE5ZGM1OWYtY2U2OC03YThlLWE4NzMtN2NlYWMzYWNiZDBmOjE3NzExMTQ1LWRmYWEtNGE0ZS04MTQzLTA4YzYxZjE4ZjJmNA=="

SYSTEM_PROMPT = """Ты — умный ассистент BizBot для малого бизнеса. 
Твоя задача: вежливо отвечать клиентам, записывать их на услуги и помогать с вопросами.

ВАЖНЫЕ ПРАВИЛА:
1. Отвечай кратко и дружелюбно (2-4 предложения максимум)
2. Если клиент хочет записаться — уточни: услугу, имя, удобное время
3. Если клиент злой, расстроен или требует живого человека — передай менеджеру
4. Если вопрос слишком сложный или ты не знаешь ответ — передай менеджеру

ФОРМАТ ОТВЕТА — всегда возвращай JSON:
{
  "text": "текст ответа клиенту",
  "action": "none",
  "booking_data": {}
}

action может быть: "none", "book_appointment", "transfer_to_manager"
"""


class BotBrain:
    def __init__(self):
        self.client_id = CLIENT_ID
        self.client_secret = CLIENT_SECRET
        self.auth_key = AUTH_KEY
        self.access_token = None
        self.token_expires_at = 0
        
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
    
    async def _get_access_token(self):
        if self.access_token and datetime.now().timestamp() < self.token_expires_at - 300:
            return self.access_token
        
        url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        
        headers = {
            "Authorization": f"Bearer {self.auth_key}",
            "RqUID": self.client_id,
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        data = {"scope": "GIGACHAT_API_PERS"}
        connector = aiohttp.TCPConnector(ssl=self.ssl_context)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            try:
                async with session.post(url, headers=headers, data=data, timeout=30) as response:
                    if response.status == 200:
                        result = await response.json()
                        self.access_token = result.get("access_token")
                        self.token_expires_at = datetime.now().timestamp() + 1500
                        print("✅ GigaChat авторизован")
                        return self.access_token
                    else:
                        error_text = await response.text()
                        print(f"Auth error: {response.status} - {error_text}")
                        return None
            except Exception as e:
                print(f"Auth exception: {e}")
                return None
    
    async def respond(self, message: str, history: list, client_id: str, conversation_id: str, business_context: dict = None) -> dict:
        token = await self._get_access_token()
        if not token:
            return {"text": "Извините, ошибка. Соединяю с менеджером.", "action": "transfer_to_manager", "action_data": {}}
        
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        # Добавляем историю
        for msg in history[-10:]:
            role = "user" if msg["role"] == "client" else "assistant"
            messages.append({"role": role, "content": msg["text"]})
        
        messages.append({"role": "user", "content": message})
        
        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {"model": "GigaChat", "messages": messages, "temperature": 0.7, "max_tokens": 500}
        
        connector = aiohttp.TCPConnector(ssl=self.ssl_context)
        
        try:
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(url, headers=headers, json=payload, timeout=60) as response:
                    if response.status == 200:
                        data = await response.json()
                        result_text = data["choices"][0]["message"]["content"]
                        
                        print(f"GigaChat ответ: {result_text[:200]}")
                        
                        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
                        if json_match:
                            result = json.loads(json_match.group())
                        else:
                            result = {"text": result_text[:500], "action": "none", "action_data": {}}
                        
                        if "text" not in result:
                            result["text"] = "Пожалуйста, уточните ваш вопрос."
                        if "action" not in result:
                            result["action"] = "none"
                        if "action_data" not in result:
                            result["action_data"] = {}
                        
                        return result
                    else:
                        error_text = await response.text()
                        print(f"GigaChat ошибка {response.status}: {error_text}")
                        return {"text": "Извините, ошибка. Соединяю с менеджером.", "action": "transfer_to_manager", "action_data": {}}
        except Exception as e:
            print(f"GigaChat ошибка: {e}")
            return {"text": "Извините, ошибка. Соединяю с менеджером.", "action": "transfer_to_manager", "action_data": {}}