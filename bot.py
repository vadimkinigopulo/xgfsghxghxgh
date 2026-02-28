# -*- coding: utf-8 -*-

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
LEADERS = os.getenv("LEADERS", "")

if not TOKEN or not GROUP_ID:
    logger.error("❌ Не указан VK_TOKEN или GROUP_ID")
    exit(1)

GROUP_ID = int(GROUP_ID)
LEADERS = [x.strip() for x in LEADERS.split(",") if x.strip()]

vk_session = vk_api.VkApi(token=TOKEN)
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, GROUP_ID)

DATA_FILE = "admins.json"

# ================= ФАЙЛ =================
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
    keyboard.add_button("✅ Войти", VkKeyboardColor.POSITIVE)
    keyboard.add_button("❌ Выйти", VkKeyboardColor.NEGATIVE)
    keyboard.add_line()
    keyboard.add_button("📋 Онлайн", VkKeyboardColor.PRIMARY)
    keyboard.add_button("👑 Руководство", VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("👤 Ст. админы", VkKeyboardColor.SECONDARY)
    keyboard.add_button("👥 Мл. админы", VkKeyboardColor.SECONDARY)
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
logger.info("✅ Бот запущен")

for event in longpoll.listen():
    if event.type != VkBotEventType.MESSAGE_NEW:
        continue

    msg = event.message
    peer_id = msg["peer_id"]
    user_id = str(msg["from_id"])
    text = msg.get("text", "").lower()

    now = time.time()

    # ===== ВХОД =====
    if text in ["войти", "✅ войти"]:
        if user_id in admins:
            send_message(peer_id, "⚠️ Вы уже в системе.")
            continue

        first_name, last_name = get_user_info(user_id)

        role = "Мл. Администратор"
        if user_id in LEADERS:
            role = "Руководство"

        admins[user_id] = {
            "first_name": first_name,
            "last_name": last_name,
            "role": role,
            "start_time": now
        }
        save_admins(admins)

        send_message(peer_id, f"✅ {role} [id{user_id}|{first_name} {last_name}] вошел в систему.\n👥 Онлайн: {len(admins)}")

    # ===== ВЫХОД =====
    elif text in ["выйти", "❌ выйти"]:
        if user_id not in admins:
            send_message(peer_id, "⚠️ Вы не в системе.")
            continue

        data = admins[user_id]
        del admins[user_id]
        save_admins(admins)

        send_message(peer_id, f"❌ {data['role']} [id{user_id}|{data['first_name']} {data['last_name']}] вышел.\n👥 Онлайн: {len(admins)}")

    # ===== СПИСОК ОБЩИЙ =====
    elif text in ["онлайн", "📋 онлайн"]:
        if not admins:
            send_message(peer_id, "👥 Никто не в сети.")
            continue

        msg_lines = ["📋 **Общий список онлайн:**\n"]
        for uid, data in admins.items():
            msg_lines.append(
                f"• {data['role']} [id{uid}|{data['first_name']} {data['last_name']}] — ⏱ {format_time(now - data['start_time'])}"
            )
        send_message(peer_id, "\n".join(msg_lines))

    # ===== СПИСОК РОЛЕЙ =====
    elif text in ["руководство", "👑 руководство"]:
        leaders_list = [f"• [id{uid}|{data['first_name']} {data['last_name']}] — ⏱ {format_time(now - data['start_time'])}" 
                        for uid, data in admins.items() if data["role"] == "Руководство"]
        send_message(peer_id, "👑 **Руководство в сети:**\n" + ("\n".join(leaders_list) if leaders_list else "Сейчас никто не онлайн."))

    elif text in ["ст. админы", "👤 ст. админы"]:
        senior_list = [f"• [id{uid}|{data['first_name']} {data['last_name']}] — ⏱ {format_time(now - data['start_time'])}" 
                        for uid, data in admins.items() if data["role"] == "Ст. Администратор"]
        send_message(peer_id, "👤 **Старшие администраторы:**\n" + ("\n".join(senior_list) if senior_list else "Сейчас никто не онлайн."))

    elif text in ["мл. админы", "👥 мл. админы"]:
        junior_list = [f"• [id{uid}|{data['first_name']} {data['last_name']}] — ⏱ {format_time(now - data['start_time'])}" 
                        for uid, data in admins.items() if data["role"] == "Мл. Администратор"]
        send_message(peer_id, "👥 **Младшие администраторы:**\n" + ("\n".join(junior_list) if junior_list else "Сейчас никто не онлайн."))

    # ===== ИЗМЕНЕНИЕ РОЛЕЙ (ТОЛЬКО РУКОВОДСТВО) =====
    elif text.startswith("/role"):
        if user_id not in admins or admins[user_id]["role"] != "Руководство":
            send_message(peer_id, "⛔ Только руководство может менять роли.")
            continue

        parts = text.split()
        if len(parts) != 3:
            send_message(peer_id, "Пример: /role 123456789 ст")
            continue

        target_id = parts[1]
        new_role_key = parts[2]

        if target_id not in admins:
            send_message(peer_id, "⚠️ Пользователь не в сети.")
            continue

        if new_role_key == "ст":
            admins[target_id]["role"] = "Ст. Администратор"
        elif new_role_key == "мл":
            admins[target_id]["role"] = "Мл. Администратор"
        else:
            send_message(peer_id, "Доступные роли: ст / мл")
            continue

        save_admins(admins)
        send_message(peer_id, f"✅ Роль пользователя [id{target_id}|{admins[target_id]['first_name']} {admins[target_id]['last_name']}] изменена на {admins[target_id]['role']}")
