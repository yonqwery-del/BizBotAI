"""
Admin Panel — управление бизнесами и просмотр статистики
Доступно только супер-админу системы
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from datetime import datetime, timedelta

router = APIRouter(prefix="/admin", tags=["Admin Panel"])

# В реальном проекте добавьте JWT авторизацию
ADMIN_SECRET = os.getenv("ADMIN_SECRET", "super_secret_key_123")


async def verify_admin(api_key: str):
    """Проверка прав администратора"""
    if api_key != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid admin key")
    return True


@router.get("/businesses")
async def list_businesses(admin_key: str, limit: int = 100):
    """Список всех бизнесов"""
    await verify_admin(admin_key)
    
    async with aiosqlite.connect("bizbot.db") as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, name, email, subscription_plan, subscription_status, subscription_expires_at, created_at FROM businesses LIMIT ?",
            (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


@router.get("/businesses/{business_id}/stats")
async def get_business_stats(business_id: str, admin_key: str):
    """Детальная статистика бизнеса"""
    await verify_admin(admin_key)
    
    async with aiosqlite.connect("bizbot.db") as db:
        # Общая статистика
        cursor = await db.execute(
            "SELECT COUNT(*) FROM conversations WHERE client_id LIKE ?",
            (f"{business_id}_%",)
        )
        total_conv = (await cursor.fetchone())[0]
        
        cursor = await db.execute(
            "SELECT COUNT(*) FROM bookings WHERE client_id LIKE ?",
            (f"{business_id}_%",)
        )
        total_bookings = (await cursor.fetchone())[0]
        
        # Статистика по дням за последнюю неделю
        daily_stats = []
        for i in range(7):
            day = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            cursor = await db.execute(
                "SELECT COUNT(*) FROM conversations WHERE client_id LIKE ? AND created_at LIKE ?",
                (f"{business_id}_%", f"{day}%")
            )
            conv_day = (await cursor.fetchone())[0]
            daily_stats.append({"date": day, "conversations": conv_day})
        
        return {
            "business_id": business_id,
            "total_conversations": total_conv,
            "total_bookings": total_bookings,
            "daily_stats": daily_stats
        }


@router.post("/businesses/{business_id}/subscription")
async def update_subscription(business_id: str, plan: str, admin_key: str):
    """Обновляет подписку бизнеса"""
    await verify_admin(admin_key)
    
    from billing import Billing
    billing = Billing(db)  # db нужно передать
    
    result = await billing.upgrade_plan(business_id, plan)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.get("/stats")
async def platform_stats(admin_key: str):
    """Общая статистика платформы"""
    await verify_admin(admin_key)
    
    async with aiosqlite.connect("bizbot.db") as db:
        cursor = await db.execute("SELECT COUNT(*) FROM businesses")
        total_businesses = (await cursor.fetchone())[0]
        
        cursor = await db.execute("SELECT COUNT(*) FROM businesses WHERE subscription_status='active'")
        active_businesses = (await cursor.fetchone())[0]
        
        cursor = await db.execute("SELECT subscription_plan, COUNT(*) FROM businesses GROUP BY subscription_plan")
        plans = {row[0]: row[1] for row in await cursor.fetchall()}
        
        # Предполагаемый MRR
        mrr = (plans.get("basic", 0) * 990 + 
               plans.get("pro", 0) * 2990 + 
               plans.get("enterprise", 0) * 9990)
        
        return {
            "total_businesses": total_businesses,
            "active_businesses": active_businesses,
            "plans_distribution": plans,
            "estimated_mrr": mrr,
            "estimated_mrr_rub": f"{mrr:,} ₽".replace(",", " ")
        }