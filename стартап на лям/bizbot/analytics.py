"""
Analytics — аналитический модуль для бизнесов
"""
import aiosqlite
from datetime import datetime, timedelta
import json


class Analytics:
    def __init__(self, db):
        self.db = db
    
    async def get_dashboard_data(self, business_id: str) -> dict:
        """Данные для дашборда бизнеса"""
        
        async with aiosqlite.connect(self.db.db_path) as conn:
            # За последние 7 дней
            seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            
            # Диалоги по дням
            cursor = await conn.execute("""
                SELECT DATE(created_at) as date, COUNT(*) as count
                FROM conversations
                WHERE client_id LIKE ? AND DATE(created_at) >= ?
                GROUP BY DATE(created_at)
                ORDER BY date
            """, (f"{business_id}_%", seven_days_ago))
            conv_chart = [{"date": row[0], "conversations": row[1]} for row in await cursor.fetchall()]
            
            # Часы пик активности
            cursor = await conn.execute("""
                SELECT strftime('%H', created_at) as hour, COUNT(*) as count
                FROM messages m
                JOIN conversations c ON m.conversation_id = c.id
                WHERE c.client_id LIKE ? AND m.role='client'
                GROUP BY hour
                ORDER BY hour
            """, (f"{business_id}_%",))
            hourly_stats = [{"hour": int(row[0]), "messages": row[1]} for row in await cursor.fetchall()]
            
            # Популярные услуги (из записей)
            cursor = await conn.execute("""
                SELECT service, COUNT(*) as count
                FROM bookings
                WHERE client_id LIKE ?
                GROUP BY service
                ORDER BY count DESC
                LIMIT 5
            """, (f"{business_id}_%",))
            popular_services = [{"service": row[0], "bookings": row[1]} for row in await cursor.fetchall()]
            
            # Среднее время ответа
            cursor = await conn.execute("""
                SELECT 
                    m1.created_at as client_msg,
                    MIN(m2.created_at) as bot_msg
                FROM messages m1
                JOIN messages m2 ON m1.conversation_id = m2.conversation_id
                WHERE m1.role='client' AND m2.role='bot' 
                AND m1.created_at < m2.created_at
                AND m1.conversation_id IN (SELECT id FROM conversations WHERE client_id LIKE ?)
                GROUP BY m1.id
            """, (f"{business_id}_%",))
            
            response_times = []
            for row in await cursor.fetchall():
                if row[0] and row[1]:
                    t1 = datetime.fromisoformat(row[0])
                    t2 = datetime.fromisoformat(row[1])
                    response_times.append((t2 - t1).total_seconds())
            
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0
            
            # Процент потерянных диалогов (без записи)
            cursor = await conn.execute("""
                SELECT 
                    COUNT(DISTINCT c.id) as total_conv,
                    COUNT(DISTINCT b.conversation_id) as conv_with_booking
                FROM conversations c
                LEFT JOIN bookings b ON c.id = b.conversation_id
                WHERE c.client_id LIKE ?
            """, (f"{business_id}_%",))
            row = await cursor.fetchone()
            total_conv = row[0] or 0
            conv_with_booking = row[1] or 0
            lost_percentage = round((1 - conv_with_booking / max(total_conv, 1)) * 100, 2)
            
            return {
                "business_id": business_id,
                "period": "last_7_days",
                "conversations_chart": conv_chart,
                "hourly_activity": hourly_stats,
                "popular_services": popular_services,
                "avg_response_time_seconds": round(avg_response_time, 2),
                "avg_response_time_formatted": f"{int(avg_response_time // 60)} мин {int(avg_response_time % 60)} сек" if avg_response_time else "Нет данных",
                "lost_conversations_percentage": lost_percentage,
                "conversion_rate": round(conv_with_booking / max(total_conv, 1) * 100, 2)
            }
    
    async def get_export_data(self, business_id: str, start_date: str, end_date: str) -> dict:
        """Экспорт данных для бизнеса (CSV/Excel)"""
        
        async with aiosqlite.connect(self.db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            
            # Диалоги
            cursor = await conn.execute("""
                SELECT id, client_name, channel, status, created_at, updated_at
                FROM conversations
                WHERE client_id LIKE ? AND DATE(created_at) BETWEEN ? AND ?
                ORDER BY created_at DESC
            """, (f"{business_id}_%", start_date, end_date))
            conversations = [dict(r) for r in await cursor.fetchall()]
            
            # Записи
            cursor = await conn.execute("""
                SELECT id, client_name, service, booking_datetime, status, created_at
                FROM bookings
                WHERE client_id LIKE ? AND DATE(created_at) BETWEEN ? AND ?
                ORDER BY booking_datetime DESC
            """, (f"{business_id}_%", start_date, end_date))
            bookings = [dict(r) for r in await cursor.fetchall()]
            
            return {
                "conversations": conversations,
                "bookings": bookings,
                "start_date": start_date,
                "end_date": end_date,
                "exported_at": datetime.now().isoformat()
            }