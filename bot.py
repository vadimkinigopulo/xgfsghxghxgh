import os
import json
import time
import logging
from flask import Flask, request
import vk_api
from vk_api.utils import get_random_id
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ==== Конфигурация VK ====
VK_TOKEN = os.getenv("VK_TOKEN")
CONFIRMATION_TOKEN = os.getenv("CONFIRMATION_TOKEN")
SECRET_KEY = os.getenv("SECRET_KEY")

if not VK_TOKEN or not CONFIRMATION_TOKEN:
    logger.error("VK_TOKEN или CONFIRMATION_TOKEN не найдены в .env")
    exit(1)

# ==== Инициализация VK ====
vk_session = vk_api.VkApi(token=VK_TOKEN)
vk = vk_session.get_api()

# ==== Файлы для хранения данных ====
admins_file = "admins.json"
senior_admins_file = "senior_admins.json"
management_file = "management.json"

# ==== Загрузка данных из JSON ====
def load_json(file_path, default):
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

admins = load_json(admins_file, {})
senior_admins = load_json(senior_admins_file, [])
management = load_json(management_file, [])

logger.info(f"Загружено: {len(admins)} мл.админов, {len(senior_admins)} ст.админов, {len(management)} руководства")

# ==== Функции сохранения ====
def save_admins():
    with open(admins_file, "w", encoding="utf-8") as f:
        json.dump(admins, f, ensure_ascii=False, indent=2)

def save_senior_admins():
    with open(senior_admins_file, "w", encoding="utf-8") as f:
        json.dump(senior_admins, f, ensure_ascii=False, indent=2)

def save_management():
    with open(management_file, "w", encoding="utf-8") as f:
        json.dump(management, f, ensure_ascii=False, indent=2)

# ==== Вспомогательные функции ====
def is_management(user_id):
    return str(user_id) in [str(m) for m in management]

def is_senior_admin(user_id):
    return str(user_id) in [str(sa) for sa in senior_admins]

def is_junior_admin(user_id):
    return str(user_id) in admins

def get_user_role(user_id):
    if is_management(user_id):
        return "management"
    elif is_senior_admin(user_id):
        return "senior"
    elif is_junior_admin(user_id):
        return "junior"
    return "none"

def format_time(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    if hours and minutes:
        return f"{hours}ч {minutes}м"
    elif hours:
        return f"{hours}ч"
    elif minutes:
        return f"{minutes}м"
    return "меньше минуты"

def get_user_info(user_id):
    try:
        user = vk.users.get(user_ids=user_id)[0]
        return user["first_name"], user["last_name"]
    except:
        return "Неизвестно", "Неизвестно"

def parse_user_input(input_text):
    input_text = input_text.strip()
    if input_text.startswith('@'):
        input_text = input_text[1:]
    if input_text.startswith('[id') and '|' in input_text:
        try:
            return input_text.split('[id')[1].split('|')[0]
        except:
            pass
    if 'vk.com/' in input_text:
        try:
            parts = input_text.split('vk.com/')[1].split('/')[0]
            if parts.startswith('id'):
                return parts[2:]
            users = vk.users.get(user_ids=parts)
            if users:
                return str(users[0]['id'])
        except:
            pass
    if input_text.isdigit():
        return input_text
    return None

def send_message(peer_id, message):
    try:
        vk.messages.send(
            peer_id=peer_id,
            message=message,
            random_id=get_random_id()
        )
    except Exception as e:
        logger.error(f"Ошибка отправки: {e}")

# ==== Обработчики ====
def handle_message_new(peer_id, user_id, text):
    """Основная логика обработки сообщений"""
    
    # Текстовые команды
    if text.startswith('/'):
        args = text.split()
        command = args[0].lower()
        
        if command == '/start':
            send_message(peer_id, "👋 Добро пожаловать! Я бот для учета времени администраторов.")
            return
        
        if command == '/help':
            help_text = (
                "📋 **Доступные команды:**\n\n"
                "/start - приветствие\n"
                "/help - это меню\n"
                "вошел - отметить вход\n"
                "вышел - отметить выход\n"
                "список - показать онлайн\n\n"
                "**Для руководства:**\n"
                "/addgroup [группа] [пользователь] - добавить в группу\n"
                "/removegroup [группа] [пользователь] - удалить из группы\n"
                "Группы: junior, senior, management"
            )
            send_message(peer_id, help_text)
            return
        
        # Команды для руководства
        if is_management(user_id):
            if command == '/addgroup' and len(args) >= 3:
                group = args[1].lower()
                target_id = parse_user_input(' '.join(args[2:]))
                if not target_id:
                    send_message(peer_id, "❌ Не удалось распознать пользователя")
                    return
                
                first_name, last_name = get_user_info(target_id)
                target_name = f"{first_name} {last_name}"
                
                if group == 'junior':
                    if target_id in admins:
                        send_message(peer_id, f"⚠️ [id{target_id}|{target_name}] уже является младшим администратором")
                    else:
                        admins[target_id] = {
                            "start_time": time.time(),
                            "first_name": first_name,
                            "last_name": last_name
                        }
                        save_admins()
                        send_message(peer_id, f"✅ [id{target_id}|{target_name}] назначен младшим администратором!")
                
                elif group == 'senior':
                    if int(target_id) in senior_admins:
                        send_message(peer_id, f"⚠️ [id{target_id}|{target_name}] уже является старшим администратором")
                    else:
                        senior_admins.append(int(target_id))
                        save_senior_admins()
                        send_message(peer_id, f"✅ [id{target_id}|{target_name}] назначен старшим администратором!")
                
                elif group == 'management':
                    if int(target_id) in management:
                        send_message(peer_id, f"⚠️ [id{target_id}|{target_name}] уже является руководством")
                    else:
                        management.append(int(target_id))
                        save_management()
                        send_message(peer_id, f"✅ [id{target_id}|{target_name}] назначен руководством!")
                
                else:
                    send_message(peer_id, "❌ Неизвестная группа. Доступно: junior, senior, management")
            
            elif command == '/removegroup' and len(args) >= 3:
                group = args[1].lower()
                target_id = parse_user_input(' '.join(args[2:]))
                if not target_id:
                    send_message(peer_id, "❌ Не удалось распознать пользователя")
                    return
                
                first_name, last_name = get_user_info(target_id)
                target_name = f"{first_name} {last_name}"
                
                if group == 'junior':
                    if target_id not in admins:
                        send_message(peer_id, f"⚠️ [id{target_id}|{target_name}] не является младшим администратором")
                    else:
                        del admins[target_id]
                        save_admins()
                        send_message(peer_id, f"✅ [id{target_id}|{target_name}] удален из младших администраторов")
                
                elif group == 'senior':
                    if int(target_id) not in senior_admins:
                        send_message(peer_id, f"⚠️ [id{target_id}|{target_name}] не является старшим администратором")
                    else:
                        senior_admins.remove(int(target_id))
                        save_senior_admins()
                        send_message(peer_id, f"✅ [id{target_id}|{target_name}] удален из старших администраторов")
                
                elif group == 'management':
                    if int(target_id) not in management:
                        send_message(peer_id, f"⚠️ [id{target_id}|{target_name}] не является руководством")
                    else:
                        management.remove(int(target_id))
                        save_management()
                        send_message(peer_id, f"✅ [id{target_id}|{target_name}] удален из руководства")
                
                else:
                    send_message(peer_id, "❌ Неизвестная группа. Доступно: junior, senior, management")
        
        return
    
    # Простые команды по тексту
    text_lower = text.lower()
    
    if text_lower == "вошел":
        if user_id in admins:
            send_message(peer_id, "⚠️ Вы уже авторизованы")
        else:
            first_name, last_name = get_user_info(user_id)
            admins[user_id] = {
                "start_time": time.time(),
                "first_name": first_name,
                "last_name": last_name
            }
            save_admins()
            
            role_text = "Младший администратор"
            if is_senior_admin(user_id):
                role_text = "Старший администратор"
            if is_management(user_id):
                role_text = "Руководство"
            
            send_message(peer_id, f"✅ {role_text} [id{user_id}|{first_name} {last_name}] успешно авторизовался!\n👥 Онлайн: {len(admins)}")
    
    elif text_lower == "вышел":
        if user_id not in admins:
            send_message(peer_id, "⚠️ Вы не авторизованы")
        else:
            first_name = admins[user_id].get("first_name", "Неизвестно")
            last_name = admins[user_id].get("last_name", "Неизвестно")
            del admins[user_id]
            save_admins()
            send_message(peer_id, f"❌ Администратор [id{user_id}|{first_name} {last_name}] вышел из системы\n👥 Онлайн: {len(admins)}")
    
    elif text_lower == "список":
        if not admins:
            send_message(peer_id, "👥 Нет администраторов онлайн")
        else:
            now = time.time()
            lines = []
            for uid, info in admins.items():
                online_time = now - info.get("start_time", now)
                lines.append(f"👤 [id{uid}|{info['first_name']} {info['last_name']}] — ⏱ {format_time(online_time)}")
            send_message(peer_id, "👥 Администраторы онлайн:\n\n" + "\n".join(lines))
    
    elif text_lower == "руководство" or text_lower == "админы":
        # Показываем списки
        result = []
        
        if management:
            result.append("👑 **Руководство:**")
            for i, m_id in enumerate(management, 1):
                first_name, last_name = get_user_info(m_id)
                status = "✅" if str(m_id) in admins else "❌"
                result.append(f"{i}. [id{m_id}|{first_name} {last_name}] {status}")
        
        if senior_admins:
            result.append("\n👤 **Старшие администраторы:**")
            for i, sa_id in enumerate(senior_admins, 1):
                first_name, last_name = get_user_info(sa_id)
                status = "✅" if str(sa_id) in admins else "❌"
                result.append(f"{i}. [id{sa_id}|{first_name} {last_name}] {status}")
        
        if result:
            send_message(peer_id, "\n".join(result))
        else:
            send_message(peer_id, "📋 Списки пусты")


@app.route('/', methods=['POST'])
def webhook():
    """Главный обработчик вебхуков"""
    try:
        data = request.get_json()
        logger.info(f"Получен вебхук: {data.get('type')}")
        
        # Проверка секретного ключа
        if SECRET_KEY and data.get('secret') != SECRET_KEY:
            logger.warning("Неверный секретный ключ")
            return 'Forbidden', 403
        
        event_type = data.get('type')
        
        # Подтверждение сервера
        if event_type == 'confirmation':
            logger.info("Подтверждение сервера")
            return CONFIRMATION_TOKEN, 200
        
        # Новое сообщение
        if event_type == 'message_new':
            msg = data['object']['message']
            peer_id = msg['peer_id']
            user_id = str(msg['from_id'])
            text = msg.get('text', '')
            
            logger.info(f"Сообщение от {user_id}: {text}")
            handle_message_new(peer_id, user_id, text)
        
        # Всегда возвращаем 'ok' для VK
        return 'ok', 200
    
    except Exception as e:
        logger.error(f"Ошибка обработки вебхука: {e}", exc_info=True)
        return 'Internal Server Error', 500


@app.route('/', methods=['GET'])
def health():
    """Проверка работоспособности"""
    return 'Bot is running', 200


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)import os
import json
import time
import logging
from flask import Flask, request
import vk_api
from vk_api.utils import get_random_id
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ==== Конфигурация VK ====
VK_TOKEN = os.getenv("VK_TOKEN")
CONFIRMATION_TOKEN = os.getenv("CONFIRMATION_TOKEN")
SECRET_KEY = os.getenv("SECRET_KEY")

if not VK_TOKEN or not CONFIRMATION_TOKEN:
    logger.error("VK_TOKEN или CONFIRMATION_TOKEN не найдены в .env")
    exit(1)

# ==== Инициализация VK ====
vk_session = vk_api.VkApi(token=VK_TOKEN)
vk = vk_session.get_api()

# ==== Файлы для хранения данных ====
admins_file = "admins.json"
senior_admins_file = "senior_admins.json"
management_file = "management.json"

# ==== Загрузка данных из JSON ====
def load_json(file_path, default):
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

admins = load_json(admins_file, {})
senior_admins = load_json(senior_admins_file, [])
management = load_json(management_file, [])

logger.info(f"Загружено: {len(admins)} мл.админов, {len(senior_admins)} ст.админов, {len(management)} руководства")

# ==== Функции сохранения ====
def save_admins():
    with open(admins_file, "w", encoding="utf-8") as f:
        json.dump(admins, f, ensure_ascii=False, indent=2)

def save_senior_admins():
    with open(senior_admins_file, "w", encoding="utf-8") as f:
        json.dump(senior_admins, f, ensure_ascii=False, indent=2)

def save_management():
    with open(management_file, "w", encoding="utf-8") as f:
        json.dump(management, f, ensure_ascii=False, indent=2)

# ==== Вспомогательные функции (без изменений) ====
def is_management(user_id):
    return str(user_id) in [str(m) for m in management]

def is_senior_admin(user_id):
    return str(user_id) in [str(sa) for sa in senior_admins]

def is_junior_admin(user_id):
    return str(user_id) in admins

def get_user_role(user_id):
    if is_management(user_id):
        return "management"
    elif is_senior_admin(user_id):
        return "senior"
    elif is_junior_admin(user_id):
        return "junior"
    return "none"

def format_time(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    if hours and minutes:
        return f"{hours}ч {minutes}м"
    elif hours:
        return f"{hours}ч"
    elif minutes:
        return f"{minutes}м"
    return "меньше минуты"

def get_user_info(user_id):
    try:
        user = vk.users.get(user_ids=user_id)[0]
        return user["first_name"], user["last_name"]
    except:
        return "Неизвестно", "Неизвестно"

def parse_user_input(input_text):
    input_text = input_text.strip()
    if input_text.startswith('@'):
        input_text = input_text[1:]
    if input_text.startswith('[id') and '|' in input_text:
        try:
            return input_text.split('[id')[1].split('|')[0]
        except:
            pass
    if 'vk.com/' in input_text:
        try:
            parts = input_text.split('vk.com/')[1].split('/')[0]
            if parts.startswith('id'):
                return parts[2:]
            users = vk.users.get(user_ids=parts)
            if users:
                return str(users[0]['id'])
        except:
            pass
    if input_text.isdigit():
        return input_text
    return None

def send_message(peer_id, message):
    try:
        vk.messages.send(
            peer_id=peer_id,
            message=message,
            random_id=get_random_id()
        )
    except Exception as e:
        logger.error(f"Ошибка отправки: {e}")

# ==== Обработчики ====
def handle_message_new(peer_id, user_id, text):
    """Основная логика обработки сообщений"""
    
    # Текстовые команды
    if text.startswith('/'):
        args = text.split()
        command = args[0].lower()
        
        if command == '/start':
            send_message(peer_id, "👋 Добро пожаловать!")
            return
        
        if command == '/help':
            help_text = "📋 Команды: /start, /help"
            send_message(peer_id, help_text)
            return
        
        # Команды для руководства
        if is_management(user_id):
            if command == '/addgroup' and len(args) >= 3:
                group = args[1].lower()
                target_id = parse_user_input(' '.join(args[2:]))
                if not target_id:
                    send_message(peer_id, "❌ Не удалось распознать пользователя")
                    return
                
                first_name, last_name = get_user_info(target_id)
                
                if group == 'junior':
                    if target_id in admins:
                        send_message(peer_id, f"⚠️ Уже мл.админ")
                    else:
                        admins[target_id] = {
                            "start_time": time.time(),
                            "first_name": first_name,
                            "last_name": last_name
                        }
                        save_admins()
                        send_message(peer_id, f"✅ Назначен мл.админом")
                
                elif group == 'senior':
                    if int(target_id) in senior_admins:
                        send_message(peer_id, f"⚠️ Уже ст.админ")
                    else:
                        senior_admins.append(int(target_id))
                        save_senior_admins()
                        send_message(peer_id, f"✅ Назначен ст.админом")
                
                elif group == 'management':
                    if int(target_id) in management:
                        send_message(peer_id, f"⚠️ Уже руководство")
                    else:
                        management.append(int(target_id))
                        save_management()
                        send_message(peer_id, f"✅ Назначен руководством")
        
        return
    
    # Простые команды по тексту (можно добавить кнопки потом)
    if text.lower() == "вошел":
        if user_id in admins:
            send_message(peer_id, "⚠️ Вы уже авторизованы")
        else:
            first_name, last_name = get_user_info(user_id)
            admins[user_id] = {
                "start_time": time.time(),
                "first_name": first_name,
                "last_name": last_name
            }
            save_admins()
            send_message(peer_id, f"✅ {first_name} авторизовался")
    
    elif text.lower() == "вышел":
        if user_id not in admins:
            send_message(peer_id, "⚠️ Вы не авторизованы")
        else:
            del admins[user_id]
            save_admins()
            send_message(peer_id, f"✅ Вы вышли")
    
    elif text.lower() == "список":
        if not admins:
            send_message(peer_id, "👥 Нет админов онлайн")
        else:
            now = time.time()
            lines = []
            for uid, info in admins.items():
                online_time = now - info.get("start_time", now)
                lines.append(f"[id{uid}|{info['first_name']}] — ⏱ {format_time(online_time)}")
            send_message(peer_id, "👥 Онлайн:\n" + "\n".join(lines))


@app.route('/', methods=['POST'])
def webhook():
    """Главный обработчик вебхуков"""
    try:
        data = request.get_json()
        
        # Проверка секретного ключа
        if SECRET_KEY and data.get('secret') != SECRET_KEY:
            return 'Forbidden', 403
        
        event_type = data.get('type')
        
        # Подтверждение сервера
        if event_type == 'confirmation':
            return CONFIRMATION_TOKEN, 200
        
        # Новое сообщение
        if event_type == 'message_new':
            msg = data['object']['message']
            peer_id = msg['peer_id']
            user_id = str(msg['from_id'])
            text = msg.get('text', '')
            
            handle_message_new(peer_id, user_id, text)
        
        return 'ok', 200
    
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)
        return 'Internal Server Error', 500


@app.route('/', methods=['GET'])
def health():
    return 'Bot is running', 200


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)import os
import json
import time
import logging
import ast
from dotenv import load_dotenv
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.utils import get_random_id

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Создаем папку для логов
os.makedirs("logs", exist_ok=True)

# ==== Загрузка токена и GROUP_ID ====
load_dotenv()
TOKEN = os.getenv("VK_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")

if not TOKEN:
    logger.error("Не указан VK_TOKEN в файле .env")
    exit(1)

try:
    GROUP_ID = int(GROUP_ID) if GROUP_ID else 0
except ValueError:
    logger.error("GROUP_ID должен быть числом")
    exit(1)

if GROUP_ID == 0:
    logger.error("Не указан GROUP_ID в файле .env")
    exit(1)

# Инициализация VK сессии
vk_session = vk_api.VkApi(token=TOKEN)
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, GROUP_ID)

# Файлы для хранения данных
admins_file = "admins.json"
senior_admins_file = "senior_admins.json"
management_file = "management.json"

# Загружаем младших администраторов
if os.path.exists(admins_file):
    with open(admins_file, "r", encoding="utf-8") as f:
        admins = json.load(f)
    logger.info(f"Загружено {len(admins)} младших администраторов")
else:
    admins = {}
    logger.info("Файл admins.json не найден, создан пустой словарь")

# Загружаем старших администраторов
if os.path.exists(senior_admins_file):
    with open(senior_admins_file, "r", encoding="utf-8") as f:
        senior_admins = json.load(f)
    logger.info(f"Загружено {len(senior_admins)} старших администраторов")
else:
    senior_admins = []
    logger.info("Файл senior_admins.json не найден, создан пустой список")

# Загружаем руководство
if os.path.exists(management_file):
    with open(management_file, "r", encoding="utf-8") as f:
        management = json.load(f)
    logger.info(f"Загружено {len(management)} руководства")
else:
    management = []
    logger.info("Файл management.json не найден, создан пустой список")

def save_admins():
    """Сохранение младших администраторов"""
    with open(admins_file, "w", encoding="utf-8") as f:
        json.dump(admins, f, ensure_ascii=False, indent=2)
    logger.debug("Файл admins.json сохранен")

def save_senior_admins():
    """Сохранение старших администраторов"""
    with open(senior_admins_file, "w", encoding="utf-8") as f:
        json.dump(senior_admins, f, ensure_ascii=False, indent=2)
    logger.debug("Файл senior_admins.json сохранен")

def save_management():
    """Сохранение руководства"""
    with open(management_file, "w", encoding="utf-8") as f:
        json.dump(management, f, ensure_ascii=False, indent=2)
    logger.debug("Файл management.json сохранен")

# ==== Проверка прав пользователя ====
def is_management(user_id):
    """Проверка, является ли пользователь руководством"""
    return str(user_id) in [str(m) for m in management]

def is_senior_admin(user_id):
    """Проверка, является ли пользователь старшим администратором"""
    return str(user_id) in [str(sa) for sa in senior_admins]

def is_junior_admin(user_id):
    """Проверка, является ли пользователь младшим администратором"""
    return str(user_id) in admins

def get_user_role(user_id):
    """Получение роли пользователя"""
    if is_management(user_id):
        return "management"
    elif is_senior_admin(user_id):
        return "senior"
    elif is_junior_admin(user_id):
        return "junior"
    return "none"

# ==== Клавиатура ====
def get_keyboard(user_id=None):
    """Создание клавиатуры в зависимости от роли"""
    keyboard = VkKeyboard(one_time=False)
    role = get_user_role(user_id) if user_id else "none"
    
    # Основные кнопки для всех с payload
    keyboard.add_button("✅ Вошел", VkKeyboardColor.POSITIVE, 
                       payload=json.dumps({"command": "entered"}))
    keyboard.add_button("❌ Вышел", VkKeyboardColor.NEGATIVE, 
                       payload=json.dumps({"command": "exited"}))
    keyboard.add_line()
    
    # Кнопки для просмотра списков
    keyboard.add_button("👥 Мл. админы", VkKeyboardColor.SECONDARY, 
                       payload=json.dumps({"command": "junior_admins"}))
    keyboard.add_button("👤 Ст. админы", VkKeyboardColor.PRIMARY, 
                       payload=json.dumps({"command": "senior_admins"}))
    keyboard.add_line()
    keyboard.add_button("👑 Руководство", VkKeyboardColor.PRIMARY, 
                       payload=json.dumps({"command": "management"}))
    
    # Дополнительные кнопки для руководства
    if role == "management":
        keyboard.add_line()
        keyboard.add_button("➕ Дать мл.админа", VkKeyboardColor.POSITIVE, 
                          payload=json.dumps({"command": "add_junior"}))
        keyboard.add_button("➖ Убрать мл.админа", VkKeyboardColor.NEGATIVE, 
                          payload=json.dumps({"command": "remove_junior"}))
        keyboard.add_line()
        keyboard.add_button("➕ Дать ст.админа", VkKeyboardColor.POSITIVE, 
                          payload=json.dumps({"command": "add_senior"}))
        keyboard.add_button("➖ Убрать ст.админа", VkKeyboardColor.NEGATIVE, 
                          payload=json.dumps({"command": "remove_senior"}))
        keyboard.add_line()
        keyboard.add_button("➕ Дать руководство", VkKeyboardColor.POSITIVE, 
                          payload=json.dumps({"command": "add_management"}))
        keyboard.add_button("➖ Убрать руководство", VkKeyboardColor.NEGATIVE, 
                          payload=json.dumps({"command": "remove_management"}))
    
    return keyboard.get_keyboard()

# ==== Отправка сообщений ====
def send_message(peer_id, message, user_id=None):
    """Отправка сообщения с клавиатурой"""
    try:
        vk.messages.send(
            peer_id=peer_id,
            message=message,
            random_id=get_random_id(),
            keyboard=get_keyboard(user_id)
        )
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения: {e}")

# ==== Красивое время онлайн ====
def format_time(seconds):
    """Форматирование времени"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    if hours and minutes:
        return f"{hours}ч {minutes}м"
    elif hours:
        return f"{hours}ч"
    elif minutes:
        return f"{minutes}м"
    else:
        return "меньше минуты"

# ==== Получение имени пользователя ====
def get_user_info(user_id):
    """Получение имени и фамилии пользователя"""
    try:
        user = vk.users.get(user_ids=user_id)[0]
        return user["first_name"], user["last_name"]
    except Exception as e:
        logger.error(f"Ошибка получения информации о пользователе {user_id}: {e}")
        return "Неизвестно", "Неизвестно"

# ==== Парсинг пользователя из текста ====
def parse_user_input(input_text):
    """Парсит ввод пользователя (ссылку или ID) и возвращает user_id"""
    input_text = input_text.strip()
    
    # Убираем @ если есть
    if input_text.startswith('@'):
        input_text = input_text[1:]
    
    # Проверяем формат [id123|Name]
    if input_text.startswith('[id') and '|' in input_text:
        try:
            user_id = input_text.split('[id')[1].split('|')[0]
            return user_id
        except:
            pass
    
    # Проверяем ссылку vk.com/id123
    if 'vk.com/' in input_text:
        try:
            parts = input_text.split('vk.com/')[1].split('/')[0]
            if parts.startswith('id'):
                return parts[2:]
            else:
                users = vk.users.get(user_ids=parts)
                if users:
                    return str(users[0]['id'])
        except:
            pass
    
    # Проверяем просто число
    if input_text.isdigit():
        return input_text
    
    return None

# ==== Список младших админов онлайн ====
def get_junior_admins_list():
    """Получение списка младших администраторов онлайн"""
    if not admins:
        return "👥 Младшие администраторы в сети:\n\nСейчас никто не авторизован."

    now = time.time()
    result = []
    for i, (uid, info) in enumerate(admins.items(), start=1):
        first_name = info.get("first_name", "Неизвестно")
        last_name = info.get("last_name", "Неизвестно")
        online_time = now - info.get("start_time", now)
        result.append(f"{i}. [id{uid}|{first_name} {last_name}] — ⏱ {format_time(online_time)}")
    
    return "👥 Младшие администраторы в сети:\n\n" + "\n".join(result)

# ==== Список старших админов ====
def get_senior_admins_list():
    """Получение списка старших администраторов"""
    if not senior_admins:
        return "👤 Старшие администраторы:\n\nСписок пуст."

    result = []
    for i, sa_id in enumerate(senior_admins, start=1):
        first_name, last_name = get_user_info(sa_id)
        status = "✅ В сети" if str(sa_id) in admins else "❌ Не в сети"
        result.append(f"{i}. [id{sa_id}|{first_name} {last_name}] — {status}")
    
    return "👤 Старшие администраторы:\n\n" + "\n".join(result)

# ==== Список руководства ====
def get_management_list():
    """Получение списка руководства"""
    if not management:
        return "👑 Руководство:\n\nСписок пуст."

    result = []
    for i, m_id in enumerate(management, start=1):
        first_name, last_name = get_user_info(m_id)
        status = "✅ В сети" if str(m_id) in admins else "❌ Не в сети"
        result.append(f"{i}. [id{m_id}|{first_name} {last_name}] — {status}")
    
    return "👑 Руководство:\n\n" + "\n".join(result)

# ==== Проверка устаревших сессий ====
def check_expired_sessions():
    """Проверка и удаление сессий старше 24 часов"""
    now = time.time()
    expired = []
    for uid, info in admins.items():
        if now - info.get("start_time", 0) > 24 * 3600:
            expired.append(uid)
    
    for uid in expired:
        del admins[uid]
    
    if expired:
        save_admins()
        logger.info(f"Удалено {len(expired)} устаревших сессий")

# Стартовая информация
logger.info("🤖 Бот запущен")
logger.info(f"👑 Руководство: {len(management)} человек")
logger.info(f"👤 Старшие администраторы: {len(senior_admins)} человек")
check_expired_sessions()

# Хранение состояния ожидания ввода
waiting_for_input = {}
message_counter = 0

# ================= ГЛАВНЫЙ ЦИКЛ =================
for event in longpoll.listen():
    try:
        if event.type == VkBotEventType.MESSAGE_NEW:
            msg = event.message
            peer_id = msg["peer_id"]
            user_id = str(msg["from_id"])
            message_text = msg.get("text", "")

            # Периодическая проверка устаревших сессий
            message_counter += 1
            if message_counter % 100 == 0:
                check_expired_sessions()

            # Обработка текстовых команд
            if message_text.startswith('/'):
                args = message_text.split()
                command = args[0].lower()
                
                # Команда /addgroup
                if command == '/addgroup' and is_management(user_id):
                    if len(args) < 3:
                        send_message(peer_id, 
                            "❌ Использование: /addgroup [группа] [пользователь]\n"
                            "Группы: junior, senior, management\n"
                            "Пример: /addgroup junior @durov", user_id)
                    else:
                        group = args[1].lower()
                        target_input = ' '.join(args[2:])
                        target_id = parse_user_input(target_input)
                        
                        if not target_id:
                            send_message(peer_id, "❌ Не удалось распознать пользователя", user_id)
                            continue
                        
                        first_name, last_name = get_user_info(target_id)
                        target_name = f"{first_name} {last_name}"
                        
                        if group == 'junior':
                            if target_id in admins:
                                send_message(peer_id, f"⚠️ [id{target_id}|{target_name}] уже является младшим администратором", user_id)
                            else:
                                admins[target_id] = {
                                    "start_time": time.time(),
                                    "first_name": first_name,
                                    "last_name": last_name
                                }
                                save_admins()
                                send_message(peer_id, f"✅ [id{target_id}|{target_name}] назначен младшим администратором!", user_id)
                        
                        elif group == 'senior':
                            if int(target_id) in senior_admins:
                                send_message(peer_id, f"⚠️ [id{target_id}|{target_name}] уже является старшим администратором", user_id)
                            else:
                                senior_admins.append(int(target_id))
                                save_senior_admins()
                                send_message(peer_id, f"✅ [id{target_id}|{target_name}] назначен старшим администратором!", user_id)
                        
                        elif group == 'management':
                            if int(target_id) in management:
                                send_message(peer_id, f"⚠️ [id{target_id}|{target_name}] уже является руководством", user_id)
                            else:
                                management.append(int(target_id))
                                save_management()
                                send_message(peer_id, f"✅ [id{target_id}|{target_name}] назначен руководством!", user_id)
                        
                        else:
                            send_message(peer_id, "❌ Неизвестная группа. Доступно: junior, senior, management", user_id)
                
                # Команда /removegroup
                elif command == '/removegroup' and is_management(user_id):
                    if len(args) < 3:
                        send_message(peer_id, 
                            "❌ Использование: /removegroup [группа] [пользователь]\n"
                            "Группы: junior, senior, management\n"
                            "Пример: /removegroup junior @durov", user_id)
                    else:
                        group = args[1].lower()
                        target_input = ' '.join(args[2:])
                        target_id = parse_user_input(target_input)
                        
                        if not target_id:
                            send_message(peer_id, "❌ Не удалось распознать пользователя", user_id)
                            continue
                        
                        first_name, last_name = get_user_info(target_id)
                        target_name = f"{first_name} {last_name}"
                        
                        if group == 'junior':
                            if target_id not in admins:
                                send_message(peer_id, f"⚠️ [id{target_id}|{target_name}] не является младшим администратором", user_id)
                            else:
                                del admins[target_id]
                                save_admins()
                                send_message(peer_id, f"✅ [id{target_id}|{target_name}] удален из младших администраторов", user_id)
                        
                        elif group == 'senior':
                            if int(target_id) not in senior_admins:
                                send_message(peer_id, f"⚠️ [id{target_id}|{target_name}] не является старшим администратором", user_id)
                            else:
                                senior_admins.remove(int(target_id))
                                save_senior_admins()
                                send_message(peer_id, f"✅ [id{target_id}|{target_name}] удален из старших администраторов", user_id)
                        
                        elif group == 'management':
                            if int(target_id) not in management:
                                send_message(peer_id, f"⚠️ [id{target_id}|{target_name}] не является руководством", user_id)
                            else:
                                management.remove(int(target_id))
                                save_management()
                                send_message(peer_id, f"✅ [id{target_id}|{target_name}] удален из руководства", user_id)
                        
                        else:
                            send_message(peer_id, "❌ Неизвестная группа. Доступно: junior, senior, management", user_id)
                
                # Команда /help
                elif command == '/help':
                    help_text = (
                        "📋 **Доступные команды:**\n\n"
                        "**Для руководства:**\n"
                        "/addgroup [группа] [пользователь] - добавить в группу\n"
                        "/removegroup [группа] [пользователь] - удалить из группы\n"
                        "Группы: junior, senior, management\n\n"
                        "**Для всех:**\n"
                        "Кнопки в меню для входа/выхода и просмотра списков"
                    )
                    send_message(peer_id, help_text, user_id)
                
                # Команда /start
                elif command == '/start':
                    send_message(peer_id, "👋 Добро пожаловать! Используйте кнопки ниже для навигации.", user_id)
                
                continue

            # Парсинг payload из сообщения
            payload = None
            if msg.get("payload"):
                try:
                    if isinstance(msg["payload"], str):
                        payload = json.loads(msg["payload"])
                    elif isinstance(msg["payload"], dict):
                        payload = msg["payload"]
                    else:
                        payload = ast.literal_eval(msg["payload"])
                except Exception as e:
                    logger.error(f"Ошибка парсинга payload: {e}")

            action = payload.get("command") if payload else None

            # Проверяем, ожидаем ли мы ввод
            if user_id in waiting_for_input:
                action_input = waiting_for_input[user_id]
                
                if action_input in ["add_junior", "remove_junior", "add_senior", "remove_senior", "add_management", "remove_management"]:
                    target_id = parse_user_input(message_text)
                    
                    if not target_id:
                        send_message(peer_id, "❌ Не удалось распознать пользователя. Отправьте ID или ссылку.", user_id)
                        del waiting_for_input[user_id]
                        continue
                    
                    first_name, last_name = get_user_info(target_id)
                    target_name = f"{first_name} {last_name}"
                    
                    if action_input == "add_junior":
                        if target_id in admins:
                            send_message(peer_id, f"⚠️ [id{target_id}|{target_name}] уже является младшим администратором.", user_id)
                        else:
                            admins[target_id] = {
                                "start_time": time.time(),
                                "first_name": first_name,
                                "last_name": last_name
                            }
                            save_admins()
                            send_message(peer_id, f"✅ [id{target_id}|{target_name}] назначен младшим администратором!", user_id)
                    
                    elif action_input == "remove_junior":
                        if target_id not in admins:
                            send_message(peer_id, f"⚠️ [id{target_id}|{target_name}] не является младшим администратором.", user_id)
                        else:
                            del admins[target_id]
                            save_admins()
                            send_message(peer_id, f"✅ [id{target_id}|{target_name}] удален из младших администраторов.", user_id)
                    
                    elif action_input == "add_senior":
                        if int(target_id) in senior_admins:
                            send_message(peer_id, f"⚠️ [id{target_id}|{target_name}] уже является старшим администратором.", user_id)
                        else:
                            senior_admins.append(int(target_id))
                            save_senior_admins()
                            send_message(peer_id, f"✅ [id{target_id}|{target_name}] назначен старшим администратором!", user_id)
                    
                    elif action_input == "remove_senior":
                        if int(target_id) not in senior_admins:
                            send_message(peer_id, f"⚠️ [id{target_id}|{target_name}] не является старшим администратором.", user_id)
                        else:
                            senior_admins.remove(int(target_id))
                            save_senior_admins()
                            send_message(peer_id, f"✅ [id{target_id}|{target_name}] удален из старших администраторов.", user_id)
                    
                    elif action_input == "add_management":
                        if int(target_id) in management:
                            send_message(peer_id, f"⚠️ [id{target_id}|{target_name}] уже является руководством.", user_id)
                        else:
                            management.append(int(target_id))
                            save_management()
                            send_message(peer_id, f"✅ [id{target_id}|{target_name}] назначен руководством!", user_id)
                    
                    elif action_input == "remove_management":
                        if int(target_id) not in management:
                            send_message(peer_id, f"⚠️ [id{target_id}|{target_name}] не является руководством.", user_id)
                        else:
                            management.remove(int(target_id))
                            save_management()
                            send_message(peer_id, f"✅ [id{target_id}|{target_name}] удален из руководства.", user_id)
                    
                    del waiting_for_input[user_id]
                    continue

            # Обработка действий
            if action == "entered":
                if user_id in admins:
                    send_message(peer_id, "⚠️ Вы уже авторизованы.", user_id)
                else:
                    first_name, last_name = get_user_info(user_id)
                    admins[user_id] = {
                        "start_time": time.time(),
                        "first_name": first_name,
                        "last_name": last_name
                    }
                    save_admins()
                    
                    role_text = "Младший администратор"
                    if is_senior_admin(user_id):
                        role_text = "Старший администратор"
                    if is_management(user_id):
                        role_text = "Руководство"
                    
                    send_message(peer_id,
                        f"✅ {role_text} [id{user_id}|{first_name} {last_name}] успешно авторизовался.\n"
                        f"👥 Мл.админов онлайн: {len(admins)}", user_id
                    )
                    logger.info(f"Пользователь {user_id} ({first_name} {last_name}) авторизовался")

            elif action == "exited":
                if user_id not in admins:
                    send_message(peer_id, "⚠️ Вы не авторизованы.", user_id)
                else:
                    first_name = admins[user_id].get("first_name", "Неизвестно")
                    last_name = admins[user_id].get("last_name", "Неизвестно")
                    del admins[user_id]
                    save_admins()
                    
                    send_message(peer_id,
                        f"❌ Администратор [id{user_id}|{first_name} {last_name}] вышел из системы.\n"
                        f"👥 Мл.админов онлайн: {len(admins)}", user_id
                    )
                    logger.info(f"Пользователь {user_id} ({first_name} {last_name}) вышел")

            elif action == "junior_admins":
                send_message(peer_id, get_junior_admins_list(), user_id)

            elif action == "senior_admins":
                send_message(peer_id, get_senior_admins_list(), user_id)

            elif action == "management":
                send_message(peer_id, get_management_list(), user_id)

            # Действия только для руководства
            elif action in ["add_junior", "remove_junior", "add_senior", "remove_senior", "add_management", "remove_management"]:
                if not is_management(user_id):
                    send_message(peer_id, "⛔ Эта команда доступна только руководству.", user_id)
                    continue

                action_messages = {
                    "add_junior": "👥 Отправьте ID или ссылку на пользователя, которого хотите назначить младшим администратором:",
                    "remove_junior": "👥 Отправьте ID или ссылку на пользователя, которого хотите удалить из младших администраторов:",
                    "add_senior": "👤 Отправьте ID или ссылку на пользователя, которого хотите назначить старшим администратором:",
                    "remove_senior": "👤 Отправьте ID или ссылку на пользователя, которого хотите удалить из старших администраторов:",
                    "add_management": "👑 Отправьте ID или ссылку на пользователя, которого хотите назначить руководством:",
                    "remove_management": "👑 Отправьте ID или ссылку на пользователя, которого хотите удалить из руководства:"
                }
                
                send_message(peer_id, action_messages[action], user_id)
                waiting_for_input[user_id] = action

    except Exception as e:
        logger.error(f"Ошибка в обработке события: {e}", exc_info=True)
        try:
            if 'peer_id' in locals():
                send_message(peer_id, "❌ Произошла внутренняя ошибка. Попробуйте позже.", 
                           user_id if 'user_id' in locals() else None)
        except:
            passimport vk_api

TOKEN = "ВАШ_ТОКЕН"
GROUP_ID = 123456789  # ваш ID

try:
    vk_session = vk_api.VkApi(token=TOKEN)
    vk = vk_session.get_api()
    
    # Проверяем, что токен работает
    group = vk.groups.getById(group_id=GROUP_ID)
    print(f"✅ Токен работает! Группа: {group[0]['name']}")
    
    # Проверяем права на сообщения
    settings = vk.groups.getLongPollServer(group_id=GROUP_ID)
    print(f"✅ LongPoll сервер: {settings}")
    
except Exception as e:
    print(f"❌ Ошибка: {e}")



