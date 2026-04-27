"""
BizBot Backend — полная коммерческая версия (ИСПРАВЛЕННАЯ)
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from contextlib import asynccontextmanager
import asyncio
import json
import os
import re
import uuid
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

import aiosqlite
import httpx

from bot_brain import BotBrain
from database import Database
from scheduler import Scheduler
from manager_hub import ManagerHub

# ==================== ИНИЦИАЛИЗАЦИЯ ====================

db = Database()
brain = BotBrain()
scheduler = Scheduler(db)
manager_hub = ManagerHub(db)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Запуск при старте"""
    await db.init()
    asyncio.create_task(scheduler.start())
    print("=" * 50)
    print("[INFO] BizBot FULL готов к работе!")
    print("=" * 50)
    print("[INFO] API: http://localhost:8000")
    print("[INFO] Документация: http://localhost:8000/docs")
    print("=" * 50)
    yield
    scheduler.running = False
    print("[INFO] BizBot остановлен")


app = FastAPI(title="BizBot API", version="2.0.0", lifespan=lifespan)
BASE_DIR = Path(__file__).resolve().parent.parent
LANDING_FILE = BASE_DIR / "templates" / "landing.html"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

async def process_message(channel: str, client_id: str, text: str, user_name: str, raw: dict = None, business_id: str = None):
    """Обработка сообщения"""
    try:
        # Получаем контекст бизнеса
        business_context = None
        if business_id:
            business_context = await db.get_business(business_id)
            if not business_context:
                print(f"Business {business_id} not found")
        
        # Создаём диалог
        conversation = await db.get_or_create_conversation(client_id, channel, user_name, business_id)
        
        # Если передан менеджеру
        if conversation.get("transferred_to_manager"):
            await manager_hub.forward_to_manager(conversation["id"], text, user_name, channel)
            return {"text": ""}
        
        # Сохраняем сообщение
        await db.save_message(conversation["id"], "client", text)
        
        # Генерируем ответ
        history = await db.get_conversation_history(conversation["id"])
        result = await brain.respond(text, history, client_id, conversation["id"], business_context)
        
        # Обрабатываем действия
        if result.get("action") == "book_appointment":
            booking_data = result.get("booking_data", {})
            await db.create_booking(
                client_id=client_id,
                client_name=user_name,
                service=booking_data.get("service", "Консультация"),
                datetime_str=booking_data.get("datetime"),
                channel=channel,
                conversation_id=conversation["id"]
            )
        elif result.get("action") == "transfer_to_manager":
            await db.transfer_to_manager(conversation["id"])
            await manager_hub.notify_manager(conversation, text)
            result["text"] = "Соединяю вас с менеджером... 👤"
        
        # Сохраняем ответ
        await db.save_message(conversation["id"], "bot", result.get("text", ""))
        
        return result
    except Exception as e:
        print(f"Process message error: {e}")
        return {"text": "Извините, произошла ошибка. Попробуйте позже.", "action": "none"}


async def send_telegram(chat_id: str, text: str):
    """Отправка в Telegram"""
    import httpx
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        return
    async with httpx.AsyncClient() as client:
        await client.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": text})


# ==================== WEBHOOKS ====================

@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    data = await request.json()
    if "message" not in data:
        return {"ok": True}
    
    msg = data["message"]
    chat_id = str(msg["chat"]["id"])
    text = msg.get("text", "")
    user_name = msg.get("from", {}).get("first_name", "Клиент")
    
    response = await process_message("telegram", f"tg_{chat_id}", text, user_name)
    
    if response.get("text"):
        await send_telegram(chat_id, response["text"])
    return {"ok": True}


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    data = await request.json()
    phone = data.get("from", "").replace("@c.us", "")
    text = data.get("body", "")
    user_name = data.get("pushname", "Клиент")
    
    response = await process_message("whatsapp", f"wa_{phone}", text, user_name)
    return {"reply": response.get("text", "")}


# ==================== WEBSOCKET ====================

@app.websocket("/ws/chat/{session_id}")
async def website_chat(websocket: WebSocket, session_id: str):
    await websocket.accept()
    client_id = f"web_{session_id}"
    
    # Получаем business_id из query параметра
    business_id = websocket.query_params.get("business_id", None)
    print(f"[WS] connected: session={session_id}, business={business_id}")
    
    # Приветственное сообщение
    welcome_msg = "Здравствуйте! Чем могу помочь? 😊"
    
    await websocket.send_json({
        "type": "bot", 
        "text": welcome_msg, 
        "time": datetime.now().strftime("%H:%M")
    })
    
    try:
        while True:
            data = await websocket.receive_json()
            text = data.get("text", "")
            user_name = data.get("name", "Гость")
            
            print(f"[WS] message from {client_id}: {text}")
            
            # Отправляем индикатор печатания
            await websocket.send_json({"type": "typing"})
            
            # Обрабатываем сообщение
            response = await process_message("website", client_id, text, user_name, None, business_id)
            
            # Отправляем ответ
            await websocket.send_json({
                "type": "bot",
                "text": response.get("text", "Извините, я вас не понял. Повторите пожалуйста."),
                "buttons": response.get("buttons", []),
                "time": datetime.now().strftime("%H:%M")
            })
            
    except WebSocketDisconnect:
        print(f"[WS] disconnected: {client_id}")
        await db.mark_session_closed(client_id)
    except Exception as e:
        print(f"WebSocket error: {e}")
        try:
            await websocket.send_json({"type": "bot", "text": "Извините, произошла ошибка. Попробуйте позже."})
        except:
            pass


# ==================== ОСНОВНЫЕ API ====================

@app.get("/")
async def root():
    if LANDING_FILE.exists():
        return FileResponse(LANDING_FILE)
    return HTMLResponse("<h1>BizBot API</h1><p>Landing file not found.</p>")


@app.get("/landing")
async def landing_page():
    if not LANDING_FILE.exists():
        raise HTTPException(404, "Landing template not found")
    return FileResponse(LANDING_FILE)


@app.get("/api/health")
async def health():
    return {"status": "ok", "time": datetime.now().isoformat()}


@app.post("/api/demo/gigachat")
async def demo_gigachat(request: Request):
    """Демо-эндпоинт для лендинга: ответ через текущий BotBrain (GigaChat)."""
    data = await request.json()
    message = str(data.get("message", "")).strip()
    if not message:
        raise HTTPException(400, "Message is required")

    result = await brain.respond(
        message=message,
        history=[],
        client_id=f"landing_{uuid.uuid4().hex[:8]}",
        conversation_id=f"landing_{uuid.uuid4().hex[:10]}",
        business_context=None
    )
    return {
        "text": result.get("text", "Извините, не удалось получить ответ."),
        "action": result.get("action", "none")
    }


@app.get("/api/conversations")
async def get_conversations(status: Optional[str] = None, limit: int = 50, business_id: str = None):
    return await db.get_conversations(business_id, status, limit)


@app.get("/api/conversations/{conv_id}/messages")
async def get_messages(conv_id: str):
    return await db.get_messages(conv_id)


@app.post("/api/conversations/{conv_id}/reply")
async def manager_reply(conv_id: str, request: Request):
    data = await request.json()
    text = data.get("text", "")
    conv = await db.get_conversation(conv_id)
    
    await db.save_message(conv_id, "manager", text)
    
    if conv.get("channel") == "telegram":
        chat_id = conv["client_id"].replace("tg_", "")
        await send_telegram(chat_id, f"👤 Менеджер: {text}")
    
    return {"ok": True}


@app.post("/api/conversations/{conv_id}/close")
async def close_conversation(conv_id: str):
    await db.close_conversation(conv_id)
    return {"ok": True}


@app.get("/api/bookings")
async def get_bookings(date: Optional[str] = None, business_id: str = None):
    return await db.get_bookings(business_id, date)


@app.get("/api/stats")
async def get_stats(business_id: str = None):
    return await db.get_stats(business_id)


# ==================== BUSINESS API ====================

@app.post("/api/business/register")
async def register_business(email: str, name: str, owner_name: str, phone: str = None):
    """Регистрация нового бизнеса"""
    business_id = str(uuid.uuid4())[:8]
    widget_id = str(uuid.uuid4())[:16]
    now = datetime.now().isoformat()
    expires_at = (datetime.now() + timedelta(days=14)).isoformat()
    
    async with aiosqlite.connect(db.db_path) as conn:
        try:
            await conn.execute("""
                INSERT INTO businesses 
                (id, name, owner_name, email, phone, website_widget_id, 
                 subscription_status, subscription_expires_at, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (business_id, name, owner_name, email, phone, widget_id, 'trial', expires_at, now, now))
            await conn.commit()
            
            return {
                "success": True,
                "business_id": business_id,
                "widget_id": widget_id,
                "trial_days_left": 14,
                "message": f"Бизнес {name} зарегистрирован!"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


@app.get("/api/business/{business_id}")
async def get_business(business_id: str):
    business = await db.get_business(business_id)
    if not business:
        raise HTTPException(404, "Business not found")
    return business


@app.put("/api/business/{business_id}")
async def update_business(business_id: str, request: Request):
    updates = await request.json()
    async with aiosqlite.connect(db.db_path) as conn:
        for key, value in updates.items():
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            await conn.execute(
                f"UPDATE businesses SET {key}=?, updated_at=? WHERE id=?",
                (value, datetime.now().isoformat(), business_id)
            )
        await conn.commit()
    return {"success": True, "updated_fields": list(updates.keys())}


@app.get("/api/business/{business_id}/widget")
async def get_widget_code(business_id: str):
    """Возвращает код виджета для вставки на сайт"""
    business = await db.get_business(business_id)
    if not business:
        raise HTTPException(404, "Business not found")
    
    return {
        "widget_code": f"""
<!-- BizBot Widget -->
<div id="bizbot-chat"></div>
<script>
(function() {{
    const businessId = "{business_id}";
    const apiUrl = "http://localhost:8000";
    let sessionId = localStorage.getItem('bizbot_session') || 's_' + Math.random().toString(36).substr(2, 9);
    localStorage.setItem('bizbot_session', sessionId);
    let ws = null;
    
    // Стили
    const style = document.createElement('style');
    style.textContent = `
        .bizbot-btn {{ position: fixed; bottom: 20px; right: 20px; width: 55px; height: 55px; background: #667eea; border-radius: 50%; cursor: pointer; display: flex; align-items: center; justify-content: center; z-index: 99999; box-shadow: 0 2px 10px rgba(0,0,0,0.2); }}
        .bizbot-container {{ position: fixed; bottom: 85px; right: 20px; width: 350px; height: 450px; background: white; border-radius: 12px; display: none; flex-direction: column; z-index: 99999; box-shadow: 0 5px 20px rgba(0,0,0,0.2); font-family: sans-serif; }}
        .bizbot-header {{ background: #667eea; color: white; padding: 12px; display: flex; justify-content: space-between; }}
        .bizbot-close {{ background: none; border: none; color: white; font-size: 20px; cursor: pointer; }}
        .bizbot-messages {{ flex: 1; overflow-y: auto; padding: 12px; background: #f5f5f5; }}
        .bizbot-message {{ margin-bottom: 10px; display: flex; }}
        .bizbot-message.user {{ justify-content: flex-end; }}
        .bizbot-message.bot {{ justify-content: flex-start; }}
        .bizbot-bubble {{ max-width: 70%; padding: 8px 12px; border-radius: 15px; font-size: 14px; }}
        .user .bizbot-bubble {{ background: #667eea; color: white; }}
        .bot .bizbot-bubble {{ background: white; color: #333; }}
        .bizbot-input-area {{ display: flex; padding: 10px; border-top: 1px solid #eee; gap: 8px; }}
        .bizbot-input {{ flex: 1; padding: 8px; border: 1px solid #ddd; border-radius: 20px; }}
        .bizbot-send {{ padding: 8px 16px; background: #667eea; color: white; border: none; border-radius: 20px; cursor: pointer; }}
    `;
    document.head.appendChild(style);
    
    document.body.insertAdjacentHTML('beforeend', `
        <div class="bizbot-btn"><svg width="24" height="24" viewBox="0 0 24 24" fill="white"><path d="M20 2H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h4l4 4 4-4h4c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/></svg></div>
        <div class="bizbot-container"><div class="bizbot-header"><span>💬 Помощник</span><button class="bizbot-close">×</button></div>
        <div class="bizbot-messages"><div class="bizbot-message bot"><div class="bizbot-bubble">Здравствуйте! Чем могу помочь?</div></div></div>
        <div class="bizbot-input-area"><input class="bizbot-input" placeholder="Сообщение..."><button class="bizbot-send">→</button></div></div>
    `);
    
    function addMessage(role, text) {{
        const div = document.createElement('div');
        div.className = 'bizbot-message ' + role;
        div.innerHTML = '<div class="bizbot-bubble">' + text + '</div>';
        document.querySelector('.bizbot-messages').appendChild(div);
    }}
    
    function connect() {{
        ws = new WebSocket(`${{apiUrl.replace('http', 'ws')}}/ws/chat/${{sessionId}}?business_id=${{businessId}}`);
        ws.onmessage = (e) => {{
            const data = JSON.parse(e.data);
            if (data.type === 'bot') addMessage('bot', data.text);
        }};
    }}
    
    document.querySelector('.bizbot-btn').onclick = () => {{
        const c = document.querySelector('.bizbot-container');
        if (c.style.display === 'flex') c.style.display = 'none';
        else {{ c.style.display = 'flex'; if (!ws) connect(); }}
    }};
    document.querySelector('.bizbot-close').onclick = () => document.querySelector('.bizbot-container').style.display = 'none';
    document.querySelector('.bizbot-send').onclick = () => {{
        const input = document.querySelector('.bizbot-input');
        const text = input.value.trim();
        if (!text) return;
        addMessage('user', text);
        input.value = '';
        if (!ws) connect();
        setTimeout(() => ws.send(JSON.stringify({{text, name: "Клиент"}})), 100);
    }};
    document.querySelector('.bizbot-input').onkeypress = (e) => {{ if (e.key === 'Enter') document.querySelector('.bizbot-send').click(); }};
}})();
</script>
"""
    }


@app.post("/api/auth/ucaller/start")
async def ucaller_start(request: Request):
    data = await request.json()
    phone = re.sub(r"\D+", "", str(data.get("phone", "")))
    if not phone:
        raise HTTPException(400, "Phone is required")

    service_id = os.getenv("UCALLER_SERVICE_ID", "").strip()
    api_key = os.getenv("UCALLER_API_KEY", "").strip()
    if not service_id or not api_key:
        raise HTTPException(503, "uCaller is not configured on server")

    init_url = os.getenv("UCALLER_INIT_URL", "https://api.ucaller.ru/v1.0/initCall")
    callback_url = os.getenv("UCALLER_CALLBACK_URL", "").strip()
    payload = {"service_id": service_id, "key": api_key, "phone": phone}
    if callback_url:
        payload["callback_url"] = callback_url

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(init_url, json=payload)
        response_data = resp.json() if resp.content else {}
    except Exception as e:
        raise HTTPException(502, f"uCaller request failed: {str(e)}")

    if resp.status_code >= 400:
        raise HTTPException(resp.status_code, response_data.get("error") or response_data.get("message") or "uCaller init failed")

    return {"ok": True, "phone": phone, "provider": response_data}


@app.post("/api/auth/ucaller/verify")
async def ucaller_verify(request: Request):
    data = await request.json()
    phone = re.sub(r"\D+", "", str(data.get("phone", "")))
    code = str(data.get("code", "")).strip()
    if not phone or not code:
        raise HTTPException(400, "Phone and code are required")

    service_id = os.getenv("UCALLER_SERVICE_ID", "").strip()
    api_key = os.getenv("UCALLER_API_KEY", "").strip()
    if not service_id or not api_key:
        raise HTTPException(503, "uCaller is not configured on server")

    verify_url = os.getenv("UCALLER_VERIFY_URL", "https://api.ucaller.ru/v1.0/checkCode")
    payload = {"service_id": service_id, "key": api_key, "phone": phone, "code": code}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(verify_url, json=payload)
        verify_data = resp.json() if resp.content else {}
    except Exception as e:
        raise HTTPException(502, f"uCaller verify failed: {str(e)}")

    if resp.status_code >= 400:
        raise HTTPException(resp.status_code, verify_data.get("error") or verify_data.get("message") or "uCaller verify failed")

    verified = bool(
        verify_data.get("verified")
        or verify_data.get("success")
        or str(verify_data.get("status", "")).lower() in {"ok", "success", "verified"}
    )
    if not verified:
        raise HTTPException(400, verify_data.get("message") or "Phone code verification failed")

    return {"ok": True, "phone": phone, "provider": verify_data}


# ==================== BILLING API ====================

@app.get("/api/billing/{business_id}/subscription")
async def check_subscription(business_id: str):
    business = await db.get_business(business_id)
    if not business:
        raise HTTPException(404, "Business not found")
    
    expires_at = datetime.fromisoformat(business["subscription_expires_at"])
    now = datetime.now()
    is_active = business["subscription_status"] == "active" and expires_at > now
    
    return {
        "active": is_active,
        "plan": business["subscription_plan"],
        "expires_at": business["subscription_expires_at"],
        "days_left": max(0, (expires_at - now).days),
        "status": business["subscription_status"]
    }


@app.post("/api/billing/{business_id}/upgrade")
async def upgrade_plan(business_id: str, plan: str):
    if plan not in ["basic", "pro", "enterprise"]:
        raise HTTPException(400, "Invalid plan")
    
    expires_at = (datetime.now() + timedelta(days=30)).isoformat()
    
    async with aiosqlite.connect(db.db_path) as conn:
        await conn.execute("""
            UPDATE businesses 
            SET subscription_plan=?, subscription_status='active', subscription_expires_at=?, updated_at=?
            WHERE id=?
        """, (plan, expires_at, datetime.now().isoformat(), business_id))
        await conn.commit()
    
    return {"success": True, "new_plan": plan, "expires_at": expires_at}


# ==================== ЗАПУСК ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)