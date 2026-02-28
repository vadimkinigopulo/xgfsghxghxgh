import vk_api

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
