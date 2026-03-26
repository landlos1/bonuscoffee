import os
from dotenv import load_dotenv

load_dotenv()

# Токен бота
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
if not BOT_TOKEN:
    print("⚠️ ВНИМАНИЕ: BOT_TOKEN не задан в .env файле!")

# ID администраторов
admin_ids_str = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = []
if admin_ids_str:
    try:
        ADMIN_IDS = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip()]
    except ValueError as e:
        print(f"⚠️ Ошибка в ADMIN_IDS: {e}")
        ADMIN_IDS = []

ADMIN_NAMES = [x.strip() for x in os.getenv("ADMIN_NAMES", "").split(",") if x.strip()]

# Словарь администраторов
ADMINS = dict(zip(ADMIN_IDS, ADMIN_NAMES))

# Проверка конфигурации
if not ADMINS:
    print("⚠️ ВНИМАНИЕ: Список администраторов пуст! Добавьте ADMIN_IDS и ADMIN_NAMES в .env")
else:
    print(f"✅ Администраторы загружены: {ADMINS}")

# Название кофейни
COFFEE_SHOP_NAME = os.getenv("COFFEE_SHOP_NAME", "Кофейня")

# Бонусы
WELCOME_BONUS = int(os.getenv("WELCOME_BONUS", "100"))
BIRTHDAY_BONUS = int(os.getenv("BIRTHDAY_BONUS", "500"))
CASHBACK_PERCENT = int(os.getenv("CASHBACK_PERCENT", "5"))

# Меню кофе (можно редактировать)
COFFEE_MENU = [
    {
        "id": "espresso",
        "name": "Эспрессо",
        "price": 80,
        "description": "Классический эспрессо 30мл",
    },
    {
        "id": "doppio",
        "name": "Доппио",
        "price": 120,
        "description": "Двойной эспрессо 60мл",
    },
    {
        "id": "americano",
        "name": "Американо",
        "price": 100,
        "description": "Эспрессо с горячей водой 200мл",
    },
    {
        "id": "cappuccino",
        "name": "Капучино",
        "price": 150,
        "description": "Эспрессо со вспененным молоком 200мл",
    },
    {
        "id": "latte",
        "name": "Латте",
        "price": 160,
        "description": "Эспрессо с молоком и молочной пенкой 250мл",
    },
    {
        "id": "flat_white",
        "name": "Флэт Уайт",
        "price": 170,
        "description": "Двойной эспрессо с молоком 180мл",
    },
    {
        "id": "raf",
        "name": "Раф",
        "price": 180,
        "description": "Кофе со сливками и ванильным сахаром 250мл",
    },
    {
        "id": "mocha",
        "name": "Мокка",
        "price": 170,
        "description": "Эспрессо с шоколадом и молоком 250мл",
    },
]

# Варианты размера
SIZE_OPTIONS = {
    "small": {"name": "Маленький", "multiplier": 1.0},
    "medium": {"name": "Средний", "multiplier": 1.2},
    "large": {"name": "Большой", "multiplier": 1.4},
}

# Варианты молока
MILK_OPTIONS = {
    "regular": {"name": "Обычное", "price": 0},
    "oat": {"name": "Овсяное", "price": 40},
    "almond": {"name": "Миндальное", "price": 50},
    "coconut": {"name": "Кокосовое", "price": 45},
    "soy": {"name": "Соевое", "price": 35},
}

# Варианты сиропа
SYRUP_OPTIONS = {
    "none": {"name": "Без сиропа", "price": 0},
    "vanilla": {"name": "Ваниль", "price": 30},
    "caramel": {"name": "Карамель", "price": 30},
    "hazelnut": {"name": "Лесной орех", "price": 30},
    "chocolate": {"name": "Шоколад", "price": 30},
    "coconut": {"name": "Кокос", "price": 30},
}

# Время приготовления (в минутах)
PREPARATION_TIMES = [5, 10, 15, 20, 25, 30]
