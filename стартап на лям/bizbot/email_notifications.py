"""
Email Notifications — отправка email уведомлений
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from datetime import datetime

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "your_email@gmail.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "your_password")
FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@bizbot.ru")


class EmailNotifier:
    def __init__(self):
        self.smtp_host = SMTP_HOST
        self.smtp_port = SMTP_PORT
        self.smtp_user = SMTP_USER
        self.smtp_password = SMTP_PASSWORD
        self.from_email = FROM_EMAIL
    
    def _send_email(self, to_email: str, subject: str, html_content: str):
        """Отправляет email"""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.from_email
            msg['To'] = to_email
            msg['Subject'] = subject
            
            msg.attach(MIMEText(html_content, 'html'))
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            return True
        except Exception as e:
            print(f"Email error: {e}")
            return False
    
    async def send_welcome_email(self, business_name: str, business_email: str, widget_code: str = None):
        """Приветственное письмо новому бизнесу"""
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ padding: 30px; background: #f9f9f9; }}
                .code {{ background: #2d3748; color: #00ff00; padding: 15px; border-radius: 8px; font-family: monospace; overflow-x: auto; }}
                .button {{ display: inline-block; padding: 12px 24px; background: #667eea; color: white; text-decoration: none; border-radius: 6px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Добро пожаловать в BizBot! 🎉</h1>
                </div>
                <div class="content">
                    <h2>Здравствуйте, {business_name}!</h2>
                    <p>Ваш аккаунт успешно создан. У вас активен <strong>14-дневный бесплатный период</strong>.</p>
                    
                    <h3>📋 Что дальше?</h3>
                    <ol>
                        <li><strong>Настройте бота</strong> — добавьте услуги и рабочее время</li>
                        <li><strong>Подключите каналы</strong> — Telegram, WhatsApp, виджет на сайт</li>
                        <li><strong>Начните общаться</strong> — бот готов отвечать клиентам 24/7</li>
                    </ol>
                    
                    <h3>🔧 Код для вставки на сайт</h3>
                    <p>Скопируйте этот код и вставьте на ваш сайт перед закрывающим тегом &lt;/body&gt;:</p>
                    
                    <div class="code">
                        {widget_code if widget_code else "<!-- Вставьте код виджета из админ-панели -->"}
                    </div>
                    
                    <br>
                    <a href="https://bizbot.ru/dashboard" class="button">Перейти в дашборд</a>
                    
                    <hr style="margin: 30px 0;">
                    <p style="color: #666; font-size: 12px;">Если у вас есть вопросы, ответим на письмо или напишите в Telegram: @bizbot_support</p>
                </div>
            </div>
        </body>
        </html>
        """
        return self._send_email(business_email, "Добро пожаловать в BizBot!", html)
    
    async def send_subscription_expiring(self, business_name: str, business_email: str, days_left: int):
        """Уведомление о скором окончании подписки"""
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <div style="max-width: 600px; margin: 0 auto;">
                <div style="background: #f39c12; color: white; padding: 20px; text-align: center;">
                    <h1>⏰ Подписка заканчивается</h1>
                </div>
                <div style="padding: 20px;">
                    <h2>{business_name}</h2>
                    <p>Ваша подписка закончится через <strong>{days_left} дней</strong>.</p>
                    <p>Чтобы не потерять доступ к боту, продлите подписку:</p>
                    
                    <a href="https://bizbot.ru/billing" style="display: inline-block; padding: 12px 24px; background: #f39c12; color: white; text-decoration: none; border-radius: 6px;">Продлить подписку</a>
                </div>
            </div>
        </body>
        </html>
        """
        return self._send_email(business_email, f"Подписка BizBot истекает через {days_left} дней", html)
    
    async def send_payment_confirmation(self, business_name: str, business_email: str, plan: str, amount: str):
        """Подтверждение оплаты"""
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <div style="max-width: 600px; margin: 0 auto;">
                <div style="background: #27ae60; color: white; padding: 20px; text-align: center;">
                    <h1>✅ Оплата получена</h1>
                </div>
                <div style="padding: 20px;">
                    <h2>{business_name}</h2>
                    <p>Спасибо за оплату!</p>
                    <p><strong>План:</strong> {plan}</p>
                    <p><strong>Сумма:</strong> {amount}</p>
                    <p>Подписка активна на 30 дней.</p>
                    
                    <a href="https://bizbot.ru/dashboard" style="display: inline-block; padding: 12px 24px; background: #27ae60; color: white; text-decoration: none; border-radius: 6px;">Перейти в дашборд</a>
                </div>
            </div>
        </body>
        </html>
        """
        return self._send_email(business_email, "Подтверждение оплаты BizBot", html)