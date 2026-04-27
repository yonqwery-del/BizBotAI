import asyncio
from bot_brain import BotBrain

async def test():
    print("Запуск теста GigaChat...")
    brain = BotBrain()
    
    # Простое сообщение без истории
    result = await brain.respond(
        message="Привет! Хочу записаться на стрижку",
        history=[],  # пустая история
        client_id="test123",
        conversation_id="conv123"
    )
    
    print("\n📝 Ответ бота:")
    print(f"Текст: {result.get('text')}")
    print(f"Действие: {result.get('action')}")
    if result.get('booking_data'):
        print(f"Данные записи: {result.get('booking_data')}")

if __name__ == "__main__":
    asyncio.run(test())