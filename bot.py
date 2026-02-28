import os
import json
import time
import logging
from dotenv import load_dotenv
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.utils import get_random_id

# ================= НАСТРОЙКА =================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vk-admin-bot")

load_dotenv()

TOKEN = os.getenv("VK_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")

if not TOKEN or not GROUP_ID:
    logger.error("❌ Не указан VK_TOKEN или GROUP_ID в .env")
    exit(1)

GROUP_ID = int(GROUP_ID)

vk_session = vk_api.VkApi(token=TOKEN)
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, GROUP_ID)

DATA_FILE = "admins.json"

# ================= РАБОТА С ФАЙЛОМ =================

def load_admins():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_admins(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

admins = load_admins()

# ================= КЛАВИАТУРА =================

def get_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("✅ Вошел", VkKeyboardColor.POSITIVE)
    keyboard.add_button("❌ Вышел", VkKeyboardColor.NEGATIVE)
    keyboard.add_line()
    keyboard.add_button("👥 Администрация в сети", VkKeyboardColor.PRIMARY)
    return keyboard.get_keyboard()

def send_message(peer_id, text):
    vk.messages.send(
        peer_id=peer_id,
        message=text,
        random_id=get_random_id(),
        keyboard=get_keyboard()
    )

# ================= УТИЛИТЫ =================

def format_time(seconds):
    minutes = int(seconds // 60)
    hours = minutes // 60
    minutes = minutes % 60
    if hours > 0:
        return f"{hours}ч {minutes}м"
    return f"{minutes}м"

def get_user_info(user_id):
    user = vk.users.get(user_ids=user_id)[0]
    return user["first_name"], user["last_name"]

# ================= ЛОГИКА =================

logger.info("✅ Бот запущен и работает")

for event in longpoll.listen():
    if event.type != VkBotEventType.MESSAGE_NEW:
        continue

    msg = event.message
    peer_id = msg["peer_id"]
    user_id = str(msg["from_id"])
    text = msg.get("text", "").lower()

    # ===== ВХОД =====
    if text in ["вошел", "✅ вошел"]:

        if user_id in admins:
            send_message(peer_id, "⚠️ Вы уже авторизованы.")
            continue

        first_name, last_name = get_user_info(user_id)

        admins[user_id] = {
            "first_name": first_name,
            "last_name": last_name,
            "start_time": time.time()
        }

        save_admins(admins)

        send_message(
            peer_id,
            f"✅ Администратор [id{user_id}|{first_name} {last_name}] успешно авторизовался.\n"
            f"👥 Администраторов онлайн: {len(admins)}"
        )

    # ===== ВЫХОД =====
    elif text in ["вышел", "❌ вышел"]:

        if user_id not in admins:
            send_message(peer_id, "⚠️ Вы не авторизованы.")
            continue

        first_name = admins[user_id]["first_name"]
        last_name = admins[user_id]["last_name"]

        del admins[user_id]
        save_admins(admins)

        send_message(
            peer_id,
            f"❌ Администратор [id{user_id}|{first_name} {last_name}] вышел.\n"
            f"👥 Администраторов онлайн: {len(admins)}"
        )

    # ===== СПИСОК =====
    elif text in ["администрация в сети", "👥 администрация в сети"]:

        if not admins:
            send_message(peer_id, "👥 Сейчас никто из администрации не в сети.")
            continue

        now = time.time()
        response = "👥 Администрация в сети:\n\n"

        for uid, data in admins.items():
            online_time = now - data["start_time"]
            response += (
                f"• [id{uid}|{data['first_name']} {data['last_name']}] — "
                f"{format_time(online_time)}\n"
            )

        send_message(peer_id, response)
