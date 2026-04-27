import requests
import json

# Бот должен быть запущен (python main.py)

# 1. Тест здоровья
print("1. Проверка здоровья:")
r = requests.get("http://localhost:8000/api/health")
print(r.json())

# 2. Создаем диалог через отправку сообщения (вручную через запрос)
print("\n2. Тест создания диалога:")
# Обратите внимание: бот ожидает webhook, но для теста сделаем GET
r = requests.get("http://localhost:8000/api/conversations")
print(f"Диалоги: {r.json()}")

# 3. Статистика
print("\n3. Статистика:")
r = requests.get("http://localhost:8000/api/stats")
print(r.json())