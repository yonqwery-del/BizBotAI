"""
Widget Script — генерация JavaScript виджета для вставки на сайт бизнеса
"""
from datetime import datetime
import json


class WidgetGenerator:
    def __init__(self, db):
        self.db = db
    
    def generate_widget_code(self, business_id: str, widget_id: str, business_name: str = None) -> str:
        """Генерирует HTML/JS код для вставки на сайт"""
        
        widget_js = f"""
<script>
(function() {{
    // BizBot Widget v1.0
    const BUSINESS_ID = "{business_id}";
    const WIDGET_ID = "{widget_id}";
    const BOT_NAME = "{business_name or 'BizBot'}";
    const API_URL = "https://api.bizbot.ru"; // Замените на ваш домен
    
    let isOpen = false;
    let ws = null;
    let sessionId = localStorage.getItem('bizbot_session_' + BUSINESS_ID);
    if (!sessionId) {{
        sessionId = 'web_' + Math.random().toString(36).substr(2, 9);
        localStorage.setItem('bizbot_session_' + BUSINESS_ID, sessionId);
    }}
    
    // Создаём HTML виджета
    const widgetHtml = `
        <div id="bizbot-widget" style="position:fixed; bottom:20px; right:20px; z-index:99999; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
            <div id="bizbot-chat-button" style="width:60px; height:60px; background:linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius:50%; cursor:pointer; box-shadow:0 4px 12px rgba(0,0,0,0.15); display:flex; align-items:center; justify-content:center; transition:transform 0.2s;">
                <svg width="30" height="30" viewBox="0 0 24 24" fill="white">
                    <path d="M20 2H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h4l4 4 4-4h4c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/>
                </svg>
            </div>
            <div id="bizbot-chat-container" style="display:none; position:absolute; bottom:80px; right:0; width:380px; height:500px; background:white; border-radius:12px; box-shadow:0 5px 20px rgba(0,0,0,0.2); overflow:hidden; flex-direction:column;">
                <div style="background:linear-gradient(135deg, #667eea 0%, #764ba2 100%); color:white; padding:15px; display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-weight:bold; font-size:16px;">{BOT_NAME}</span>
                    <button id="bizbot-close" style="background:none; border:none; color:white; font-size:20px; cursor:pointer;">&times;</button>
                </div>
                <div id="bizbot-messages" style="flex:1; overflow-y:auto; padding:15px; background:#f9f9f9;"></div>
                <div style="padding:10px; border-top:1px solid #eee; display:flex; gap:10px;">
                    <input type="text" id="bizbot-input" placeholder="Напишите сообщение..." style="flex:1; padding:10px; border:1px solid #ddd; border-radius:20px; outline:none;">
                    <button id="bizbot-send" style="background:#667eea; color:white; border:none; border-radius:20px; padding:10px 20px; cursor:pointer;">Отправить</button>
                </div>
            </div>
        </div>
    `.replace('{BOT_NAME}', BOT_NAME);
    
    document.body.insertAdjacentHTML('beforeend', widgetHtml);
    
    // DOM элементы
    const button = document.getElementById('bizbot-chat-button');
    const container = document.getElementById('bizbot-chat-container');
    const closeBtn = document.getElementById('bizbot-close');
    const messagesDiv = document.getElementById('bizbot-messages');
    const input = document.getElementById('bizbot-input');
    const sendBtn = document.getElementById('bizbot-send');
    
    // Подключение WebSocket
    function connectWebSocket() {{
        ws = new WebSocket(`${{API_URL.replace('http', 'ws')}}/ws/chat/${{sessionId}}?business_id=${{BUSINESS_ID}}`);
        
        ws.onopen = function() {{
            console.log('BizBot: Connected');
        }};
        
        ws.onmessage = function(event) {{
            const data = JSON.parse(event.data);
            if (data.type === 'bot' && data.text) {{
                addMessage('bot', data.text);
            }}
        }};
        
        ws.onerror = function(error) {{
            console.error('BizBot error:', error);
        }};
    }}
    
    function addMessage(role, text) {{
        const msgDiv = document.createElement('div');
        msgDiv.style.marginBottom = '12px';
        msgDiv.style.display = 'flex';
        msgDiv.style.justifyContent = role === 'user' ? 'flex-end' : 'flex-start';
        
        const bubble = document.createElement('div');
        bubble.style.maxWidth = '70%';
        bubble.style.padding = '8px 12px';
        bubble.style.borderRadius = '12px';
        bubble.style.wordWrap = 'break-word';
        
        if (role === 'user') {{
            bubble.style.background = '#667eea';
            bubble.style.color = 'white';
        }} else {{
            bubble.style.background = '#e4e6eb';
            bubble.style.color = '#1c1e21';
        }}
        
        bubble.innerText = text;
        msgDiv.appendChild(bubble);
        messagesDiv.appendChild(msgDiv);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }}
    
    function sendMessage() {{
        const text = input.value.trim();
        if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;
        
        addMessage('user', text);
        ws.send(JSON.stringify({{text: text, name: 'Клиент'}}));
        input.value = '';
    }}
    
    button.onclick = function() {{
        if (!isOpen) {{
            container.style.display = 'flex';
            isOpen = true;
            if (!ws || ws.readyState !== WebSocket.OPEN) {{
                connectWebSocket();
            }}
        }} else {{
            container.style.display = 'none';
            isOpen = false;
        }}
    }};
    
    closeBtn.onclick = function() {{
        container.style.display = 'none';
        isOpen = false;
    }};
    
    sendBtn.onclick = sendMessage;
    input.onkeypress = function(e) {{
        if (e.key === 'Enter') sendMessage();
    }};
    
    // Приветственное сообщение
    setTimeout(() => {{
        addMessage('bot', 'Здравствуйте! 😊 Чем я могу вам помочь?');
    }}, 500);
}})();
</script>
"""
        return widget_js
    
    def generate_embed_code(self, business_id: str) -> str:
        """Генерирует код для вставки на сайт (одна строка)"""
        business = self.db.get_business(business_id)  # Нужно реализовать
        if not business:
            return "<!-- BizBot: Business not found -->"
        
        widget_code = self.generate_widget_code(business_id, business.get("website_widget_id"), business.get("name"))
        
        return f"""
<!-- BizBot Widget -->
{widget_code}
<!-- End BizBot Widget -->
"""