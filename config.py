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
COFFEE_SHOP_NAME = os.getenv("COFFEE_SHOP_NAME", "Предзаказ Мечты")

# Бонусы
WELCOME_BONUS = int(os.getenv("WELCOME_BONUS", "100"))
BIRTHDAY_BONUS = int(os.getenv("BIRTHDAY_BONUS", "500"))
CASHBACK_PERCENT = int(os.getenv("CASHBACK_PERCENT", "5"))

# ==================== КАТЕГОРИИ МЕНЮ ====================

MENU_CATEGORIES = {
    "coffee": {
        "name": "☕ Кофе",
        "emoji": "☕",
        "items": [
            {
                "id": "latte",
                "name": "Латте",
                "description": "Нежный кофе с молоком",
                "sizes": {"350 мл": 250, "450 мл": 270},
                "has_milk_choice": True,
                "has_syrup_choice": False
            },
            {
                "id": "cappuccino",
                "name": "Капучино",
                "description": "Кофе с плотной молочной пенкой",
                "sizes": {"350 мл": 250, "450 мл": 270},
                "has_milk_choice": True,
                "has_syrup_choice": False
            },
            {
                "id": "americano",
                "name": "Американо",
                "description": "Эспрессо с горячей водой",
                "sizes": {"300 мл": 220},
                "has_milk_choice": False,
                "has_syrup_choice": False
            },
            {
                "id": "espresso",
                "name": "Эспрессо",
                "description": "Классический эспрессо",
                "sizes": {"40 мл": 150},
                "has_milk_choice": False,
                "has_syrup_choice": False
            },
            {
                "id": "moccaccino",
                "name": "Моккачино",
                "description": "Кофе с шоколадом и молоком",
                "sizes": {"350 мл": 260, "450 мл": 280},
                "has_milk_choice": True,
                "has_syrup_choice": False
            },
            {
                "id": "flat_white",
                "name": "Флэт Уайт",
                "description": "Двойной эспрессо с нежным молоком",
                "sizes": {"250 мл": 240},
                "has_milk_choice": True,
                "has_syrup_choice": False
            }
        ]
    },
    "raf_coffee": {
        "name": "🥛 Раф кофе",
        "emoji": "🥛",
        "items": [
            {
                "id": "raf_classic",
                "name": "Раф Классический",
                "description": "Классический раф с ванилью",
                "sizes": {"350 мл": 320, "450 мл": 340},
                "has_milk_choice": True,
                "has_syrup_choice": True
            },
            {
                "id": "raf_salted_caramel",
                "name": "Раф Соленая карамель",
                "description": "Раф с соленой карамелью",
                "sizes": {"350 мл": 280, "450 мл": 300},
                "has_milk_choice": True,
                "has_syrup_choice": False
            },
            {
                "id": "raf_peanut",
                "name": "Раф Арахисовый",
                "description": "Раф с арахисовым вкусом",
                "sizes": {"350 мл": 340, "450 мл": 360},
                "has_milk_choice": True,
                "has_syrup_choice": False
            },
            {
                "id": "raf_cheese",
                "name": "Раф Сырный",
                "description": "Раф с сырным вкусом",
                "sizes": {"350 мл": 320, "450 мл": 350},
                "has_milk_choice": True,
                "has_syrup_choice": False
            },
            {
                "id": "raf_orange",
                "name": "Раф Апельсиновый",
                "description": "Раф с апельсиновым вкусом",
                "sizes": {"350 мл": 320, "450 мл": 340},
                "has_milk_choice": True,
                "has_syrup_choice": False
            }
        ]
    },
    "non_coffee": {
        "name": "🍵 Не кофе",
        "emoji": "🍵",
        "items": [
            {
                "id": "cocoa",
                "name": "Какао",
                "description": "Горячее какао (без сахара, можно добавить в комментарии)",
                "sizes": {"250 мл": 210, "350 мл": 230, "450 мл": 250},
                "has_milk_choice": True,
                "has_syrup_choice": False
            },
            {
                "id": "matcha",
                "name": "Матча",
                "description": "Японский зеленый чай матча",
                "sizes": {"250 мл": 180, "350 мл": 200},
                "has_milk_choice": True,
                "has_syrup_choice": False
            },
            {
                "id": "coffee_gluhwein",
                "name": "Кофейный глинтвейн",
                "description": "Кофе с пряностями и апельсином",
                "sizes": {"450 мл": 300},
                "has_milk_choice": False,
                "has_syrup_choice": False
            },
            {
                "id": "cherry_tea",
                "name": "Вишневый чай",
                "description": "Фруктовый чай с вишней",
                "sizes": {"450 мл": 200},
                "has_milk_choice": False,
                "has_syrup_choice": False
            },
            {
                "id": "tea",
                "name": "Чай",
                "description": "Ройбуш, Пуэр, Ду Хен Пау",
                "sizes": {"450 мл": 150},
                "has_milk_choice": False,
                "has_syrup_choice": False
            }
        ]
    },
    "weight_coffee": {
        "name": "⚖️ Весовой кофе",
        "emoji": "⚖️",
        "items": [
            {
                "id": "brazil_fazenda",
                "name": "Brazil Fazenda (в зернах)",
                "description": "Бразильская арабика",
                "sizes": {"100 г": 238, "250 г": 595, "500 г": 1190},
                "has_milk_choice": False,
                "has_syrup_choice": False,
                "is_weight_coffee": True
            },
            {
                "id": "nicaragua_maragogype",
                "name": "Nicaragua Maragogype (в зернах)",
                "description": "Никарагуанская арабика, крупное зерно",
                "sizes": {"100 г": 350, "250 г": 875, "500 г": 1750},
                "has_milk_choice": False,
                "has_syrup_choice": False,
                "is_weight_coffee": True
            }
        ]
    }
}

# Для обратной совместимости создаем плоский список
COFFEE_MENU = []
for category in MENU_CATEGORIES.values():
    COFFEE_MENU.extend(category["items"])

# ==================== ОПЦИИ ====================

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
    "peanut": {"name": "Арахис", "price": 30},
    "cheese": {"name": "Сырный", "price": 30},
    "orange": {"name": "Апельсин", "price": 30},
}

# Время приготовления (в минутах)
PREPARATION_TIMES = [5, 10, 15, 20, 25, 30]
