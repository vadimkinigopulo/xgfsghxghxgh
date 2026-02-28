import os
import json
import time
from dotenv import load_dotenv
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.utils import get_random_id


load_dotenv()

TOKEN = os.getenv("VK_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))

vk_session = vk_api.VkApi(token=TOKEN)
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, GROUP_ID)

DATA_FILE = "admins.json"


def load_admins():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}


def save_admins(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


admins = load_admins()


def get_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("Login", VkKeyboardColor.POSITIVE)
    keyboard.add_button("Logout", VkKeyboardColor.NEGATIVE)
    keyboard.add_line()
    keyboard.add_button("Admins online", VkKeyboardColor.PRIMARY)
    return keyboard.get_keyboard()


def send_message(peer_id, text):
    vk.messages.send(
        peer_id=peer_id,
        message=text,
        random_id=get_random_id(),
        keyboard=get_keyboard()
    )


def get_user_name(user_id):
    user = vk.users.get(user_ids=user_id)[0]
    return user["first_name"], user["last_name"]


def format_time(seconds):
    minutes = int(seconds // 60)
    hours = minutes // 60
    minutes = minutes % 60

    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def handle_login(peer_id, user_id):
    user_id = str(user_id)

    if user_id in admins:
        send_message(peer_id, "You are already logged in.")
        return

    first_name, last_name = get_user_name(user_id)

    admins[user_id] = {
        "first_name": first_name,
        "last_name": last_name,
        "start_time": time.time()
    }

    save_admins(admins)

    send_message(
        peer_id,
        f"Administrator {first_name} {last_name} logged in.\n"
        f"Admins online: {len(admins)}"
    )


def handle_logout(peer_id, user_id):
    user_id = str(user_id)

    if user_id not in admins:
        send_message(peer_id, "You are not logged in.")
        return

    first_name = admins[user_id]["first_name"]
    last_name = admins[user_id]["last_name"]

    del admins[user_id]
    save_admins(admins)

    send_message(
        peer_id,
        f"Administrator {first_name} {last_name} logged out.\n"
        f"Admins online: {len(admins)}"
    )


def show_online_admins(peer_id):
    if not admins:
        send_message(peer_id, "No admins online.")
        return

    text = "Admins online:\n\n"
    now = time.time()

    for i, (uid, data) in enumerate(admins.items(), start=1):
        online_seconds = now - data["start_time"]
        online_time = format_time(online_seconds)

        text += f"{i}. {data['first_name']} {data['last_name']} - {online_time}\n"

    send_message(peer_id, text)


print("Bot started")

for event in longpoll.listen():
    if event.type == VkBotEventType.MESSAGE_NEW:
        message = event.message["text"]
        peer_id = event.message["peer_id"]
        user_id = event.message["from_id"]

        if message == "Login":
            handle_login(peer_id, user_id)

        elif message == "Logout":
            handle_logout(peer_id, user_id)

        elif message == "Admins online":
            show_online_admins(peer_id)

        else:
            send_message(peer_id, "Use menu buttons.")
