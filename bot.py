import os
import json
import time
from dotenv import load_dotenv
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.utils import get_random_id

# Загружаем токен
load_dotenv()
TOKEN = os.getenv("VK_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")

if not TOKEN:
    print("❌ Ошибка: Нет токена в .env файле")
    exit(1)

try:
    GROUP_ID = int(GROUP_ID)
except:
    print("❌ Ошибка: GROUP_ID должен быть числом")
    exit(1)

print(f"✅ Токен загружен")
print(f"✅ ID группы: {GROUP_ID}")

# Подключаемся к VK
try:
    vk_session = vk_api.VkApi(token=TOKEN)
    vk = vk_session.get_api()
    longpoll = VkBotLongPoll(vk_session, GROUP_ID)
    print("✅ Подключение к VK API успешно")
except Exception as e:
    print(f"❌ Ошибка подключения: {e}")
    exit(1)

# Простая функция отправки сообщений
def send_message(peer_id, text):
    try:
        vk.messages.send(
            peer_id=peer_id,
            message=text,
            random_id=get_random_id()
        )
        print(f"✅ Отправлено сообщение: {text[:50]}...")
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")

print("🤖 Бот запущен и слушает сообщения...")
print("📝 Напишите что-нибудь боту в ЛС или беседу")

# Главный цикл
for event in longpoll.listen():
    try:
        if event.type == VkBotEventType.MESSAGE_NEW:
            msg = event.object.message
            peer_id = msg['peer_id']
            user_id = msg['from_id']
            text = msg['text']
            
            print(f"📨 Сообщение от {user_id}: {text}")
            
            # Отвечаем на любое сообщение
            send_message(peer_id, f"Привет! Я работаю! Твой ID: {user_id}")
            
    except Exception as e:
        print(f"❌ Ошибка в цикле: {e}")
