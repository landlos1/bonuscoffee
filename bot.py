import logging
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.error import TelegramError
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from config import BOT_TOKEN, COFFEE_SHOP_NAME, COFFEE_MENU, SIZE_OPTIONS, MILK_OPTIONS, SYRUP_OPTIONS, PREPARATION_TIMES, CASHBACK_PERCENT, BIRTHDAY_BONUS, ADMINS
from database import (
    init_db, get_or_create_user, get_user_by_telegram_id, get_on_duty_admin,
    set_admin_on_duty, create_order, get_order, update_order_status,
    add_bonuses_to_user, use_bonuses, get_non_completed_orders, get_all_users,
    get_user_orders, get_orders_statistics, update_order_comment,
    get_all_non_completed_orders
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
(
    REG_FULL_NAME, REG_PHONE, REG_BIRTH_DATE,
    ORDER_SIZE, ORDER_MILK, ORDER_SYRUP, ORDER_COMMENT, ORDER_BONUSES, ORDER_CONFIRM,
    BROADCAST_MESSAGE, BROADCAST_IMAGE
) = range(11)

# Временное хранилище данных заказа
user_orders = {}

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def is_admin(telegram_id: int) -> bool:
    """Проверить, является ли пользователь администратором"""
    return telegram_id in ADMINS

def format_price(price: float) -> str:
    """Форматировать цену"""
    return f"{int(price)} ₽"

def format_bonuses(bonuses: float) -> str:
    """Форматировать бонусы"""
    return f"{int(bonuses)} бонусов"

def get_coffee_by_id(coffee_id: str) -> dict:
    """Получить кофе по ID"""
    for coffee in COFFEE_MENU:
        if coffee['id'] == coffee_id:
            return coffee
    return None

def calculate_price(coffee_id: str, size: str, milk: str, syrup: str) -> dict:
    """Рассчитать цену заказа"""
    coffee = get_coffee_by_id(coffee_id)
    if not coffee:
        return None
    base_price = coffee['price'] * SIZE_OPTIONS[size]['multiplier']
    milk_price = MILK_OPTIONS[milk]['price']
    syrup_price = SYRUP_OPTIONS[syrup]['price']
    total = base_price + milk_price + syrup_price
    return {
        'base_price': base_price,
        'milk_price': milk_price,
        'syrup_price': syrup_price,
        'total': total
    }

def check_birthday(birth_date: str) -> bool:
    """Проверить, сегодня ли день рождения"""
    try:
        today = datetime.now()
        birth = datetime.strptime(birth_date, "%d.%m.%Y")
        return today.day == birth.day and today.month == birth.month
    except:
        return False

def get_main_keyboard(is_admin_user: bool = False) -> ReplyKeyboardMarkup:
    """Получить главную клавиатуру"""
    keyboard = [
        [KeyboardButton("☕ Меню"), KeyboardButton("🛒 Мой заказ")],
        [KeyboardButton("💰 Бонусы"), KeyboardButton("📋 История заказов")],
    ]
    if is_admin_user:
        keyboard.append([KeyboardButton("👨💼 Панель администратора")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_admin_keyboard() -> ReplyKeyboardMarkup:
    """Получить клавиатуру администратора"""
    keyboard = [
        [KeyboardButton("✅ На смене"), KeyboardButton("❌ Сойти со смены")],
        [KeyboardButton("📦 Активные заказы"), KeyboardButton("📊 Статистика")],
        [KeyboardButton("📢 Массовая рассылка")],
        [KeyboardButton("🔙 В главное меню")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_back_button() -> list:
    """Кнопка назад"""
    return [InlineKeyboardButton("🔙 Назад", callback_data="back_menu")]

# ==================== ОБРАБОТЧИКИ КОМАНД ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    telegram_id = update.effective_user.id
    # Проверяем, зарегистрирован ли пользователь
    user = await get_user_by_telegram_id(telegram_id)
    if user:
        # Проверяем день рождения
        if check_birthday(user.birth_date):
             # Начисляем бонусы на ДР если еще не начисляли сегодня
            await add_bonuses_to_user(user.id, BIRTHDAY_BONUS)
            await update.message.reply_text(
                f"🎉 С Днём Рождения, {user.full_name}!\n\n"
                f"Вам начислено {BIRTHDAY_BONUS} бонусов в честь праздника!\n\n"
                f"Приятного кофепития! ☕",
                reply_markup=get_main_keyboard(is_admin(telegram_id))
            )
        else:
            await update.message.reply_text(
                f"👋 С возвращением, {user.full_name}!\n\n"
                f"💰 Ваши бонусы: {format_bonuses(user.bonuses)}\n\n"
                f"Что будем заказывать? ☕",
                reply_markup=get_main_keyboard(is_admin(telegram_id))
            )
    else:
        # Начинаем регистрацию
        await update.message.reply_text(
            f"👋 Добро пожаловать в {COFFEE_SHOP_NAME}!\n\n"
            f"Для оформления заказа необходимо зарегистрироваться.\n\n"
            f"Пожалуйста, введите ваше ФИО:"
        )
        return REG_FULL_NAME

async def reg_full_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ввода ФИО"""
    context.user_data['full_name'] = update.message.text
    await update.message.reply_text(
        "📱 Теперь введите ваш номер телефона:\n"
        "(например: +7 999 123 45 67)"
    )
    return REG_PHONE

async def reg_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ввода телефона"""
    context.user_data['phone_number'] = update.message.text
    await update.message.reply_text(
        "🎂 Введите вашу дату рождения:\n"
        "(в формате ДД.ММ.ГГГГ, например: 15.03.1990)"
    )
    return REG_BIRTH_DATE

async def reg_birth_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ввода даты рождения и завершение регистрации"""
    birth_date = update.message.text
    # Проверяем формат даты
    try:
        datetime.strptime(birth_date, "%d.%m.%Y")
    except ValueError:
        await update.message.reply_text(
             "❌ Неверный формат даты. Пожалуйста, введите в формате ДД.ММ.ГГГГ:\n"
             "(например: 15.03.1990)"
        )
        return REG_BIRTH_DATE
        
    telegram_id = update.effective_user.id
    full_name = context.user_data['full_name']
    phone_number = context.user_data['phone_number']

    # Создаем пользователя
    user, is_new = await get_or_create_user(telegram_id, full_name, phone_number, birth_date)

    welcome_text = (
        f"✅ Регистрация завершена!\n\n"
        f"👤 ФИО: {full_name}\n"
        f"📱 Телефон: {phone_number}\n"
        f"🎂 Дата рождения: {birth_date}\n\n"
        f"{'🎁 Вам начислено 100 бонусов за регистрацию!' if is_new else ''}\n\n"
        f"Теперь вы можете делать заказы! ☕"
    )
    await update.message.reply_text(
        welcome_text,
        reply_markup=get_main_keyboard(is_admin(telegram_id))
    )
    return ConversationHandler.END

# ==================== МЕНЮ И ЗАКАЗ ====================

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать меню кофе"""
    keyboard = []
    for coffee in COFFEE_MENU:
        keyboard.append([InlineKeyboardButton(
            f"{coffee['name']} - {format_price(coffee['price'])}",
            callback_data=f"coffee_{coffee['id']}"
        )])
    keyboard.append(get_back_button())
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"☕ Меню {COFFEE_SHOP_NAME}:\n\n"
        f"Выберите кофе:",
        reply_markup=reply_markup
    )

async def coffee_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора кофе"""
    query = update.callback_query
    await query.answer()
    coffee_id = query.data.replace("coffee_", "")
    coffee = get_coffee_by_id(coffee_id)
    if not coffee:
        await query.edit_message_text("❌ Кофе не найдено")
        return
    # Сохраняем выбор
    user_id = update.effective_user.id
    user_orders[user_id] = {
        'coffee_id': coffee_id,
        'coffee_name': coffee['name'],
        'base_price': coffee['price']
    }
    # Показываем выбор размера
    keyboard = []
    for size_key, size_data in SIZE_OPTIONS.items():
        price = coffee['price'] * size_data['multiplier']
        keyboard.append([InlineKeyboardButton(
            f"{size_data['name']} - {format_price(price)}",
            callback_data=f"size_{size_key}"
        )])
    keyboard.append(get_back_button())
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        f"☕ Вы выбрали: {coffee['name']}\n"
        f"📝 {coffee['description']}\n\n"
        f"Выберите размер:",
        reply_markup=reply_markup
    )
    return ORDER_SIZE

async def size_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора размера"""
    query = update.callback_query
    await query.answer()
    size = query.data.replace("size_", "")
    user_id = update.effective_user.id
    user_orders[user_id]['size'] = size
    user_orders[user_id]['size_name'] = SIZE_OPTIONS[size]['name']

    # Показываем выбор молока
    keyboard = []
    for milk_key, milk_data in MILK_OPTIONS.items():
        price_text = f"+{format_price(milk_data['price'])}" if milk_data['price'] > 0 else "Бесплатно"
        keyboard.append([InlineKeyboardButton(
            f"{milk_data['name']} - {price_text}",
            callback_data=f"milk_{milk_key}"
        )])
    keyboard.append([InlineKeyboardButton("🔙 Назад к размерам", callback_data="back_size")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        f"☕ {user_orders[user_id]['coffee_name']}\n"
        f"📏 Размер: {user_orders[user_id]['size_name']}\n\n"
        f"🥛 Выберите тип молока:",
        reply_markup=reply_markup
    )
    return ORDER_MILK

async def milk_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора молока"""
    query = update.callback_query
    await query.answer()
    milk = query.data.replace("milk_", "")
    user_id = update.effective_user.id
    user_orders[user_id]['milk'] = milk
    user_orders[user_id]['milk_name'] = MILK_OPTIONS[milk]['name']

    # Показываем выбор сиропа
    keyboard = []
    for syrup_key, syrup_data in SYRUP_OPTIONS.items():
        price_text = f"+{format_price(syrup_data['price'])}" if syrup_data['price'] > 0 else "Бесплатно"
        keyboard.append([InlineKeyboardButton(
            f"{syrup_data['name']} - {price_text}",
            callback_data=f"syrup_{syrup_key}"
        )])
    keyboard.append([InlineKeyboardButton("🔙 Назад к молоку", callback_data="back_milk")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        f"☕ {user_orders[user_id]['coffee_name']}\n"
        f"📏 Размер: {user_orders[user_id]['size_name']}\n"
        f"🥛 Молоко: {user_orders[user_id]['milk_name']}\n\n"
        f"🍯 Выберите сироп:",
        reply_markup=reply_markup
    )
    return ORDER_SYRUP

async def syrup_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора сиропа"""
    query = update.callback_query
    await query.answer()
    syrup = query.data.replace("syrup_", "")
    user_id = update.effective_user.id
    user_orders[user_id]['syrup'] = syrup
    user_orders[user_id]['syrup_name'] = SYRUP_OPTIONS[syrup]['name']

    # Показываем запрос комментария
    keyboard = [
        [InlineKeyboardButton("📝 Добавить комментарий", callback_data="add_comment")],
        [InlineKeyboardButton("⏭️ Пропустить", callback_data="skip_comment")],
        [InlineKeyboardButton("🔙 Назад к сиропу", callback_data="back_syrup")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        f"☕ {user_orders[user_id]['coffee_name']}\n"
        f"📏 Размер: {user_orders[user_id]['size_name']}\n"
        f"🥛 Молоко: {user_orders[user_id]['milk_name']}\n"
        f"🍯 Сироп: {user_orders[user_id]['syrup_name']}\n\n"
        f"Хотите добавить комментарий к заказу?",
        reply_markup=reply_markup
    )
    return ORDER_COMMENT

async def comment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик комментария"""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    
    if query.data == "add_comment":
        await query.edit_message_text(
            "📝 Введите ваш комментарий к заказу:\n"
            "(например: 'не слишком горячий', 'без сахара' и т.д.)"
        )
        return ORDER_COMMENT
    elif query.data == "skip_comment":
        user_orders[user_id]['comment'] = None
        return await show_bonus_selection(update, context)

async def comment_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ввода комментария"""
    user_id = update.effective_user.id
    user_orders[user_id]['comment'] = update.message.text
    await update.message.reply_text(f"✅ Комментарий сохранен: {update.message.text}")
    return await show_bonus_selection_message(update, context)

async def show_bonus_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать выбор бонусов (из callback)"""
    query = update.callback_query
    user_id = update.effective_user.id

    # Рассчитываем цену
    prices = calculate_price(
        user_orders[user_id]['coffee_id'],
        user_orders[user_id]['size'],
        user_orders[user_id]['milk'],
        user_orders[user_id]['syrup']
    )
    user_orders[user_id]['prices'] = prices

    # Получаем информацию о пользователе
    user = await get_user_by_telegram_id(user_id)

    keyboard = [
        [InlineKeyboardButton("❌ Не использовать бонусы", callback_data="bonus_0")],
    ]
    # Предлагаем использовать бонусы
    if user and user.bonuses > 0:
        max_bonus = min(user.bonuses, prices['total'])
        keyboard.insert(0, [InlineKeyboardButton(
            f"Использовать {int(max_bonus)} бонусов",
            callback_data=f"bonus_{int(max_bonus)}"
        )])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_comment")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    comment_text = f"\n📝 Комментарий: {user_orders[user_id].get('comment', 'нет')}" if user_orders[user_id].get('comment') else " "
    order_summary = (
        f"📋 Ваш заказ:\n\n"
        f"☕ {user_orders[user_id]['coffee_name']}\n"
        f"📏 Размер: {user_orders[user_id]['size_name']}\n"
        f"🥛 Молоко: {user_orders[user_id]['milk_name']}\n"
        f"🍯 Сироп: {user_orders[user_id]['syrup_name']}{comment_text}\n\n"
        f"💰 Итого: {format_price(prices['total'])}\n"
        f"💎 Доступно бонусов: {int(user.bonuses) if user else 0}\n\n"
        f"Хотите использовать бонусы?"
    )
    await query.edit_message_text(order_summary, reply_markup=reply_markup)
    return ORDER_BONUSES

async def show_bonus_selection_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать выбор бонусов (из message)"""
    user_id = update.effective_user.id

    # Рассчитываем цену
    prices = calculate_price(
        user_orders[user_id]['coffee_id'],
        user_orders[user_id]['size'],
        user_orders[user_id]['milk'],
        user_orders[user_id]['syrup']
    )
    user_orders[user_id]['prices'] = prices

    # Получаем информацию о пользователе
    user = await get_user_by_telegram_id(user_id)

    keyboard = [
        [InlineKeyboardButton("❌ Не использовать бонусы", callback_data="bonus_0")],
    ]
    # Предлагаем использовать бонусы
    if user and user.bonuses > 0:
        max_bonus = min(user.bonuses, prices['total'])
        keyboard.insert(0, [InlineKeyboardButton(
            f"Использовать {int(max_bonus)} бонусов",
            callback_data=f"bonus_{int(max_bonus)}"
        )])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_comment")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    comment_text = f"\n📝 Комментарий: {user_orders[user_id].get('comment', 'нет')}" if user_orders[user_id].get('comment') else " "
    order_summary = (
        f"📋 Ваш заказ:\n\n"
        f"☕ {user_orders[user_id]['coffee_name']}\n"
        f"📏 Размер: {user_orders[user_id]['size_name']}\n"
        f"🥛 Молоко: {user_orders[user_id]['milk_name']}\n"
        f"🍯 Сироп: {user_orders[user_id]['syrup_name']}{comment_text}\n\n"
        f"💰 Итого: {format_price(prices['total'])}\n"
        f"💎 Доступно бонусов: {int(user.bonuses) if user else 0}\n\n"
        f"Хотите использовать бонусы?"
    )
    await update.message.reply_text(order_summary, reply_markup=reply_markup)
    return ORDER_BONUSES

async def bonus_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора бонусов"""
    query = update.callback_query
    await query.answer()
    bonus = int(query.data.replace("bonus_", ""))
    user_id = update.effective_user.id
    user_orders[user_id]['bonuses_used'] = bonus
    prices = user_orders[user_id]['prices']
    final_price = prices['total'] - bonus
    # Рассчитываем кэшбэк
    cashback = final_price * CASHBACK_PERCENT / 100
    user_orders[user_id]['cashback'] = cashback

    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить заказ", callback_data="confirm_order")],
        [InlineKeyboardButton("❌ Отменить", callback_data="cancel_order")],
        [InlineKeyboardButton("🔙 Назад к бонусам", callback_data="back_bonus")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    comment_text = f"\n📝 Комментарий: {user_orders[user_id].get('comment', 'нет')}" if user_orders[user_id].get('comment') else " "
    order_summary = (
        f"📋 Подтверждение заказа:\n\n"
        f"☕ {user_orders[user_id]['coffee_name']}\n"
        f"📏 Размер: {user_orders[user_id]['size_name']}\n"
        f"🥛 Молоко: {user_orders[user_id]['milk_name']}\n"
        f"🍯 Сироп: {user_orders[user_id]['syrup_name']}{comment_text}\n\n"
        f"💰 Сумма: {format_price(prices['total'])}\n"
    )
    if bonus > 0:
        order_summary += f"💎 Бонусы: -{format_price(bonus)}\n"
    order_summary += (
        f"💵 К оплате: {format_price(final_price)}\n"
        f"🎁 Кэшбэк: {format_price(cashback)}\n\n"
        f"Подтвердить заказ?"
    )
    await query.edit_message_text(order_summary, reply_markup=reply_markup)
    return ORDER_CONFIRM

async def confirm_order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик подтверждения заказа"""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    user = await get_user_by_telegram_id(user_id)
    if not user:
        await query.edit_message_text("❌ Ошибка: пользователь не найден")
        return ConversationHandler.END
    order_data = user_orders.get(user_id, {})
    prices = order_data.get('prices', {})
    bonuses_used = order_data.get('bonuses_used', 0)

    # Проверяем, есть ли админ на смене
    on_duty_admin = await get_on_duty_admin()

    # Создаем заказ в базе
    coffee_data = {
        'coffee_id': order_data['coffee_id'],
        'coffee_name': order_data['coffee_name'],
        'size': order_data['size'],
        'milk': order_data['milk'],
        'syrup': order_data['syrup'],
        'base_price': prices['base_price'],
        'milk_price': prices['milk_price'],
        'syrup_price': prices['syrup_price'],
        'total_price': prices['total'] - bonuses_used,
        'bonuses_used': bonuses_used,
        'bonuses_earned': order_data.get('cashback', 0),
        'comment': order_data.get('comment'),
    }
    order = await create_order(user.id, coffee_data)
    # Сохраняем ID заказа для возможного обновления комментария
    user_orders[user_id]['order_id'] = order.id

    # Списываем бонусы
    if bonuses_used > 0:
        await use_bonuses(user.id, bonuses_used)

    comment_text = f"\n📝 Комментарий: {order_data.get('comment')}" if order_data.get('comment') else " "
    # Отправляем уведомление клиенту
    await query.edit_message_text(
        f"✅ Заказ #{order.id} создан!\n\n"
        f"☕ {order_data['coffee_name']}{comment_text}\n"
        f"💵 К оплате: {format_price(prices['total'] - bonuses_used)}\n\n"
        f"{'👨💼 Ваш заказ готовит: ' + on_duty_admin.name if on_duty_admin else '⏳ Ожидаем принятия заказа...'}\n\n"
        f"Мы уведомим вас о статусе заказа! 📱"
    )

    # Отправляем уведомление администратору
    if on_duty_admin:
        admin_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Принять заказ", callback_data=f"admin_accept_{order.id}")],
            [InlineKeyboardButton("❌ Отменить заказ", callback_data=f"admin_cancel_{order.id}")],
        ])
        comment_text_admin = f"\n📝 Комментарий: {order_data.get('comment')}" if order_data.get('comment') else " "
        try:
            await context.bot.send_message(
                chat_id=on_duty_admin.telegram_id,
                text=(
                    f"🆕 Новый заказ #{order.id}!\n\n"
                    f"👤 Клиент: {user.full_name}\n"
                    f"📱 Телефон: {user.phone_number}\n"
                    f"🎂 Дата рождения: {user.birth_date}\n\n"
                    f"☕ {order_data['coffee_name']}\n"
                    f"📏 Размер: {order_data['size_name']}\n"
                    f"🥛 Молоко: {order_data['milk_name']}\n"
                    f"🍯 Сироп: {order_data['syrup_name']}{comment_text_admin}\n\n"
                    f"💰 Сумма: {format_price(prices['total'])}\n"
                    f"💎 Бонусы: -{format_price(bonuses_used)}\n"
                    f"💵 К оплате: {format_price(prices['total'] - bonuses_used)}"
                ),
                reply_markup=admin_keyboard
            )
        except TelegramError as e:
            logger.error(f"Ошибка отправки уведомления админу (ID: {on_duty_admin.telegram_id}): {e}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка при отправке уведомления админу: {e}")

    # Очищаем данные заказа
    if user_id in user_orders:
        del user_orders[user_id]
    return ConversationHandler.END

async def cancel_order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик отмены заказа"""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if user_id in user_orders:
        del user_orders[user_id]
    await query.edit_message_text("❌ Заказ отменен")
    return ConversationHandler.END# ==================== НАВИГАЦИЯ НАЗАД ====================

async def back_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки назад"""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = query.data

    if data == "back_menu":
        # Возврат в главное меню
        await query.edit_message_text("Используйте кнопки меню для навигации")
        return ConversationHandler.END
    elif data == "back_size":
        # Возврат к выбору кофе
        coffee = get_coffee_by_id(user_orders[user_id]['coffee_id'])
        keyboard = []
        for size_key, size_data in SIZE_OPTIONS.items():
            price = coffee['price'] * size_data['multiplier']
            keyboard.append([InlineKeyboardButton(
                f"{size_data['name']} - {format_price(price)}",
                callback_data=f"size_{size_key}"
            )])
        keyboard.append(get_back_button())
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"☕ Вы выбрали: {coffee['name']}\n"
            f"📝 {coffee['description']}\n\n"
            f"Выберите размер:",
            reply_markup=reply_markup
        )
        return ORDER_SIZE
    elif data == "back_milk":
        # Возврат к выбору молока
        keyboard = []
        for milk_key, milk_data in MILK_OPTIONS.items():
            price_text = f"+{format_price(milk_data['price'])}" if milk_data['price'] > 0 else "Бесплатно"
            keyboard.append([InlineKeyboardButton(
                f"{milk_data['name']} - {price_text}",
                callback_data=f"milk_{milk_key}"
            )])
        keyboard.append([InlineKeyboardButton("🔙 Назад к размерам", callback_data="back_size")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"☕ {user_orders[user_id]['coffee_name']}\n"
            f"📏 Размер: {user_orders[user_id]['size_name']}\n\n"
            f"🥛 Выберите тип молока:",
            reply_markup=reply_markup
        )
        return ORDER_MILK
    elif data == "back_syrup":
        # Возврат к выбору сиропа
        keyboard = []
        for syrup_key, syrup_data in SYRUP_OPTIONS.items():
            price_text = f"+{format_price(syrup_data['price'])}" if syrup_data['price'] > 0 else "Бесплатно"
            keyboard.append([InlineKeyboardButton(
                f"{syrup_data['name']} - {price_text}",
                callback_data=f"syrup_{syrup_key}"
            )])
        keyboard.append([InlineKeyboardButton("🔙 Назад к молоку", callback_data="back_milk")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"☕ {user_orders[user_id]['coffee_name']}\n"
            f"📏 Размер: {user_orders[user_id]['size_name']}\n"
            f"🥛 Молоко: {user_orders[user_id]['milk_name']}\n\n"
            f"🍯 Выберите сироп:",
            reply_markup=reply_markup
        )
        return ORDER_SYRUP
    elif data == "back_comment":
        # Возврат к комментарию
        return await show_bonus_selection(update, context)
    elif data == "back_bonus":
        # Возврат к выбору бонусов
        return await show_bonus_selection(update, context)

# ==================== АДМИНИСТРАТИВНЫЕ ФУНКЦИИ ====================

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Панель администратора"""
    telegram_id = update.effective_user.id
    logger.info(f"Попытка входа в админ-панель. User ID: {telegram_id}, ADMINS: {ADMINS}")
    if not is_admin(telegram_id):
        await update.message.reply_text(
            f"❌ У вас нет доступа к панели администратора.\n\n"
            f"Ваш ID: {telegram_id}\n"
            f"Добавьте этот ID в файл .env в переменную ADMIN_IDS"
        )
        return
    admin = await get_on_duty_admin()
    status = "✅ На смене" if admin and admin.telegram_id == telegram_id else "❌ Не на смене"
    await update.message.reply_text(
        f"👨💼 Панель администратора\n\n"
        f"Статус: {status}\n\n"
        f"Выберите действие:",
        reply_markup=get_admin_keyboard()
    )

async def admin_on_duty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Админ выходит на смену"""
    telegram_id = update.effective_user.id
    if not is_admin(telegram_id):
        return
    admin = await set_admin_on_duty(telegram_id, True)
    if admin:
        await update.message.reply_text(
            f"✅ {admin.name}, вы вышли на смену!\n\n"
            f"Теперь заказы будут приходить вам.",
            reply_markup=get_admin_keyboard()
        )
    else:
        await update.message.reply_text("❌ Ошибка при выходе на смену")

async def admin_off_duty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Админ сходит со смены"""
    telegram_id = update.effective_user.id
    if not is_admin(telegram_id):
        return
    admin = await set_admin_on_duty(telegram_id, False)
    if admin:
        await update.message.reply_text(
            f"❌ {admin.name}, вы сошли со смены.",
            reply_markup=get_admin_keyboard()
        )
    else:
        await update.message.reply_text("❌ Ошибка при сходе со смены")

async def admin_accept_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Админ принимает заказ"""
    query = update.callback_query
    await query.answer()
    telegram_id = update.effective_user.id
    if not is_admin(telegram_id):
        await query.edit_message_text("❌ У вас нет доступа")
        return
    order_id = int(query.data.replace("admin_accept_", ""))
    order = await get_order(order_id)
    if not order:
        await query.edit_message_text("❌ Заказ не найден")
        return
    # Обновляем статус заказа
    await update_order_status(order_id, 'accepted', telegram_id)
    # Показываем кнопки управления заказом
    keyboard = []
    for time in PREPARATION_TIMES:
        keyboard.append([InlineKeyboardButton(
            f"⏱️ {time} минут",
            callback_data=f"admin_prep_{order_id}_{time}"
        )])
    keyboard.append([InlineKeyboardButton("❌ Отменить заказ", callback_data=f"admin_cancel_{order_id}")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    comment_text = f"\n📝 Комментарий: {order.comment}" if order.comment else " "
    await query.edit_message_text(
        f"✅ Заказ #{order_id} принят!{comment_text}\n\n"
        f"Выберите время приготовления:",
        reply_markup=reply_markup
    )
    # Уведомляем клиента
    try:
        await context.bot.send_message(
            chat_id=order.user.telegram_id,
            text=f"✅ Ваш заказ #{order_id} принят!\n\n"
                 f"👨💼 Ваш заказ готовит: {ADMINS.get(telegram_id, 'Бариста')}"
        )
    except TelegramError as e:
        logger.error(f"Ошибка уведомления клиента (ID: {order.user.telegram_id}): {e}")
    except Exception as e:
        logger.error(f"Неожиданная ошибка при уведомлении клиента (ID: {order.user.telegram_id}): {e}")

async def admin_preparing_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Админ начинает готовить заказ"""
    query = update.callback_query
    await query.answer()
    telegram_id = update.effective_user.id
    if not is_admin(telegram_id):
        await query.edit_message_text("❌ У вас нет доступа")
        return
    data = query.data.replace("admin_prep_", "").split("_")
    order_id = int(data[0])
    prep_time = int(data[1])
    order = await get_order(order_id)
    if not order:
        await query.edit_message_text("❌ Заказ не найден")
        return
    # Обновляем статус
    await update_order_status(order_id, 'preparing', preparation_time=prep_time)
    # Рассчитываем время готовности
    ready_time = datetime.now() + timedelta(minutes=prep_time)
    ready_time_str = ready_time.strftime("%H:%M")
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Заказ готов", callback_data=f"admin_ready_{order_id}")],
    ])
    await query.edit_message_text(
        f"⏱️ Заказ #{order_id} готовится!\n\n"
        f"Время приготовления: {prep_time} минут\n"
        f"🕐 Будет готов к: {ready_time_str}\n\n"
        f"Нажмите 'Заказ готов' когда заказ будет готов.",
        reply_markup=keyboard
    )
    # Уведомляем клиента с указанием времени готовности
    try:
        await context.bot.send_message(
            chat_id=order.user.telegram_id,
            text=f"⏱️ Ваш заказ #{order_id} готовится!\n\n"
                 f"🕐 Заказ будет готов примерно к: {ready_time_str}"
        )
    except TelegramError as e:
        logger.error(f"Ошибка уведомления клиента (ID: {order.user.telegram_id}): {e}")
    except Exception as e:
        logger.error(f"Неожиданная ошибка при уведомлении клиента (ID: {order.user.telegram_id}): {e}")

async def admin_ready_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Админ отмечает заказ готовым"""
    query = update.callback_query
    await query.answer()
    telegram_id = update.effective_user.id
    if not is_admin(telegram_id):
        await query.edit_message_text("❌ У вас нет доступа")
        return
    order_id = int(query.data.replace("admin_ready_", ""))
    order = await get_order(order_id)
    if not order:
        await query.edit_message_text("❌ Заказ не найден")
        return
    # Обновляем статус и начисляем бонусы
    await update_order_status(order_id, 'completed')
    await add_bonuses_to_user(order.user_id, order.bonuses_earned)
    await query.edit_message_text(
        f"✅ Заказ #{order_id} готов!\n\n"
        f"Клиент уведомлен.\n"
        f"Начислено {format_bonuses(order.bonuses_earned)} клиенту."
    )
    # Уведомляем клиента
    try:
        await context.bot.send_message(
            chat_id=order.user.telegram_id,
            text=(
                f"✅ Ваш заказ #{order_id} готов!\n\n"
                f"🎉 Можете забирать!\n\n"
                f"🎁 Вам начислено {format_bonuses(order.bonuses_earned)}\n"
                f"💰 Текущий баланс: {format_bonuses(order.user.bonuses + order.bonuses_earned)}\n\n"
                f"Приятного кофепития! ☕"
            )
        )
    except TelegramError as e:
        logger.error(f"Ошибка уведомления клиента (ID: {order.user.telegram_id}): {e}")
    except Exception as e:
        logger.error(f"Неожиданная ошибка при уведомлении клиента (ID: {order.user.telegram_id}): {e}")

async def admin_cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Админ отменяет заказ"""
    query = update.callback_query
    await query.answer()
    telegram_id = update.effective_user.id
    if not is_admin(telegram_id):
        await query.edit_message_text("❌ У вас нет доступа")
        return
    order_id = int(query.data.replace("admin_cancel_", ""))
    order = await get_order(order_id)
    if not order:
        await query.edit_message_text("❌ Заказ не найден")
        return
    # Возвращаем бонусы
    if order.bonuses_used > 0:
        await add_bonuses_to_user(order.user_id, order.bonuses_used)
    await update_order_status(order_id, 'cancelled')
    await query.edit_message_text(f"❌ Заказ #{order_id} отменен")
    # Уведомляем клиента
    try:
        await context.bot.send_message(
            chat_id=order.user.telegram_id,
            text=f"❌ К сожалению, ваш заказ #{order_id} был отменен.\n\n"
                 f"Если вы использовали бонусы, они вернулись на ваш счет."
        )
    except TelegramError as e:
        logger.error(f"Ошибка уведомления клиента (ID: {order.user.telegram_id}): {e}")
    except Exception as e:
        logger.error(f"Неожиданная ошибка при уведомлении клиента (ID: {order.user.telegram_id}): {e}")

async def admin_active_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать активные заказы"""
    telegram_id = update.effective_user.id
    if not is_admin(telegram_id):
        return
    orders = await get_all_non_completed_orders()
    if not orders:
        await update.message.reply_text(
             "📦 Нет активных заказов",
            reply_markup=get_admin_keyboard()
        )
        return
    # Отправляем каждый заказ отдельным сообщением с кнопками
    for order in orders:
        status_emoji = {
            'pending' : '⏳',
            'accepted': '✅',
            'preparing': '⏱️',
            'completed': '✓',
            'cancelled': '❌'
        }.get(order.status, '❓')
        status_text = {
            'pending': 'Ожидает',
            'accepted': 'Принят',
             'preparing': 'Готовится',
             'completed': 'Выполнен',
             'cancelled': 'Отменен'
        }.get(order.status, 'Неизвестно')
        # Рассчитываем оставшееся время
        remaining_time_text = " "
        if order.status == 'preparing' and order.preparation_time and order.preparing_at:
            elapsed = (datetime.now() - order.preparing_at).total_seconds() / 60
            remaining = order.preparation_time - int(elapsed)
            if remaining > 0:
                remaining_time_text = f"\n⏱️ Осталось: ~{remaining} мин"
            else:
                remaining_time_text = f"\n⚠️ Просрочен на: {abs(remaining)} мин"
        comment_text = f"\n📝 Комментарий: {order.comment}" if order.comment else " "
        text = (
            f"{status_emoji} Заказ #{order.id} - {status_text}\n\n"
            f"☕ {order.coffee_name}\n"
            f"👤 Клиент: {order.user.full_name}\n"
            f"📱 Телефон: {order.user.phone_number}\n"
            f"💰 Сумма: {format_price(order.total_price)}{comment_text}{remaining_time_text}"
        )
        # Добавляем кнопки действий в зависимости от статуса
        keyboard = []
        if order.status == 'pending':
            keyboard = [
                [InlineKeyboardButton("✅ Принять", callback_data=f"admin_accept_{order.id}")],
                [InlineKeyboardButton("❌ Отменить", callback_data=f"admin_cancel_{order.id}")],
            ]
        elif order.status == 'accepted':
            for time in PREPARATION_TIMES:
                keyboard.append([InlineKeyboardButton(
                    f"⏱️ {time} мин",
                    callback_data=f"admin_prep_{order.id}_{time}"
                )])
            keyboard.append([InlineKeyboardButton("❌ Отменить", callback_data=f"admin_cancel_{order.id}")])
        elif order.status == 'preparing':
            keyboard = [
                [InlineKeyboardButton("✅ Заказ готов", callback_data=f"admin_ready_{order.id}")],
                [InlineKeyboardButton("❌ Отменить", callback_data=f"admin_cancel_{order.id}")],
            ]
        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
        await update.message.reply_text(text, reply_markup=reply_markup)
    # Отправляем итоговое сообщение с клавиатурой админа
    await update.message.reply_text(
        f"📊 Всего активных заказов: {len(orders)}",
        reply_markup=get_admin_keyboard()
    )

async def admin_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику"""
    telegram_id = update.effective_user.id
    if not is_admin(telegram_id):
        return
    stats = await get_orders_statistics()
    text = (
        f"📊 Статистика {COFFEE_SHOP_NAME}\n\n"
        f"📦 Заказы:\n"
        f"  • Всего: {stats['total_orders']}\n"
        f"  • Сегодня: {stats['today_orders']}\n"
        f"  • Ожидают: {stats['status_counts'].get('pending', 0)}\n"
        f"  • Приняты: {stats['status_counts'].get('accepted', 0)}\n"
        f"  • Готовятся: {stats['status_counts'].get('preparing', 0)}\n"
        f"  • Готовы: {stats['status_counts'].get('ready', 0)}\n"
        f"  • Выполнены: {stats['status_counts'].get('completed', 0)}\n"
        f"  • Отменены: {stats['status_counts'].get('cancelled', 0)}\n\n"
        f"💰 Выручка:\n"
        f"  • Всего: {format_price(stats['total_revenue'])}\n"
        f"  • Сегодня: {format_price(stats['today_revenue'])}\n\n"
        f"👥 Пользователей: {stats['total_users']}"
    )
    await update.message.reply_text(text, reply_markup=get_admin_keyboard())# ==================== МАССОВАЯ РАССЫЛКА ====================

async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать массовую рассылку"""
    telegram_id = update.effective_user.id
    if not is_admin(telegram_id):
        return
    await update.message.reply_text(
        "📢 Массовая рассылка\n\n"
        "Введите текст сообщения:\n"
        "(или отправьте /cancel для отмены)"
    )
    return BROADCAST_MESSAGE

async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить текст рассылки"""
    context.user_data['broadcast_message'] = update.message.text
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Пропустить", callback_data="broadcast_no_image")],
    ])
    await update.message.reply_text(
        "📸 Теперь отправьте изображение (опционально):\n"
        "Или нажмите 'Пропустить'",
        reply_markup=keyboard
    )
    return BROADCAST_IMAGE

async def broadcast_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить изображение для рассылки"""
    telegram_id = update.effective_user.id
    # Получаем фото (берем самое большое)
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    # Сохраняем путь к файлу
    image_path = f"broadcast_{telegram_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    await file.download_to_drive(image_path)
    context.user_data['broadcast_image'] = image_path
    # Начинаем рассылку
    await send_broadcast(update, context)
    return ConversationHandler.END

async def broadcast_no_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Рассылка без изображения"""
    query = update.callback_query
    await query.answer()
    context.user_data['broadcast_image'] = None
    await send_broadcast(update, context, from_query=True)
    return ConversationHandler.END

async def send_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE, from_query: bool = False):
    """Отправить рассылку всем пользователям"""
    message = context.user_data.get('broadcast_message', '')
    image_path = context.user_data.get('broadcast_image')
    users = await get_all_users()
    sent_count = 0
    failed_count = 0
    for user in users:
        try:
            if image_path:
                with open(image_path, 'rb') as photo:
                    await context.bot.send_photo(
                        chat_id=user.telegram_id,
                        photo=photo,
                        caption=message
                    )
            else:
                await context.bot.send_message(
                    chat_id=user.telegram_id,
                    text=message
                )
            sent_count += 1
        except TelegramError as e:
            logger.error(f"Ошибка отправки пользователю {user.telegram_id}: {e}")
            failed_count += 1
        except Exception as e:
            logger.error(f"Неожиданная ошибка отправки пользователю {user.telegram_id}: {e}")
            failed_count += 1
    result_text = f"📢 Рассылка завершена!\n\n✅ Отправлено: {sent_count}\n❌ Ошибок: {failed_count}"
    if from_query:
        await context.bot.send_message(
            chat_id=update.effective_user.id,
            text=result_text
        )
    else:
        await update.message.reply_text(result_text)

async def cancel_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменить рассылку"""
    await update.message.reply_text("❌ Рассылка отменена")
    return ConversationHandler.END

async def my_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать ID пользователя"""
    telegram_id = update.effective_user.id
    username = update.effective_user.username or "нет"
    await update.message.reply_text(
        f"👤 Информация о вас:\n\n"
        f"🆔 Ваш ID: <code>{telegram_id}</code>\n"
        f"👤 Username: @{username}\n\n"
        f"Добавьте этот ID в файл .env:\n"
        f"ADMIN_IDS={telegram_id}",
        parse_mode='HTML'
    )

async def check_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверить статус администратора"""
    telegram_id = update.effective_user.id
    is_admin_user = is_admin(telegram_id)
    admin_list = "\n".join([f"• {name} (ID: {admin_id})" for admin_id, name in ADMINS.items()]) if ADMINS else "Список пуст"
    await update.message.reply_text(
        f"👨💼 Проверка администратора:\n\n"
        f"Ваш ID: {telegram_id}\n"
        f"Статус: {'✅ Администратор' if is_admin_user else '❌ Не администратор'}\n\n"
        f"📋 Список администраторов:\n{admin_list}\n\n"
        f"Если ваш ID не в списке, добавьте его в .env файл"
    )

# ==================== ОСТАЛЬНЫЕ ФУНКЦИИ ====================

async def show_bonuses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать бонусы пользователя"""
    user = await get_user_by_telegram_id(update.effective_user.id)
    if not user:
        await update.message.reply_text("❌ Сначала необходимо зарегистрироваться. Нажмите /start")
        return
    await update.message.reply_text(
        f"💰 Ваши бонусы\n\n"
        f"Текущий баланс: {format_bonuses(user.bonuses)}\n\n"
        f"💡 1 бонус = 1 рубль\n"
        f"🎁 Кэшбэк с каждого заказа: {CASHBACK_PERCENT}%\n\n"
        f"Используйте бонусы при оформлении заказа!"
    )

async def show_order_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать историю заказов"""
    user = await get_user_by_telegram_id(update.effective_user.id)
    if not user:
        await update.message.reply_text("❌ Сначала необходимо зарегистрироваться. Нажмите /start")
        return
    orders = await get_user_orders(user.id)
    if not orders:
        await update.message.reply_text("📋 У вас пока нет заказов")
        return
    text = "📋 История заказов:\n\n"
    for order in orders:
        status_text = {
            'pending': '⏳ Ожидает',
            'accepted': '✅ Принят',
            'preparing': '⏱️ Готовится',
            'ready': '✨ Готов',
            'completed': '✓ Выполнен',
            'cancelled': '❌ Отменен'
        }.get(order.status, '❓')
        text += f"#{order.id} - {order.coffee_name} - {format_price(order.total_price)} - {status_text}\n"
    await update.message.reply_text(text)

async def show_current_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать текущий заказ"""
    user = await get_user_by_telegram_id(update.effective_user.id)
    if not user:
        await update.message.reply_text("❌ Сначала необходимо зарегистрироваться. Нажмите /start")
        return
    # Получаем *все* заказы пользователя
    orders = await get_user_orders(user.id)
    # Фильтруем только активные заказы
    active_orders = [o for o in orders if o.status in ['pending', 'accepted', 'preparing']]
    if not active_orders:
        await update.message.reply_text("🛒 У вас нет активных заказов. Сделайте заказ через меню!")
        return
    # Показываем все активные заказы
    for order in active_orders:
        status_text = {
            'pending': '⏳ Ожидает принятия',
            'accepted': '✅ Принят',
            'preparing': '⏱️ Готовится'
        }.get(order.status, '❓')
        admin_name = order.admin.name if order.admin else 'Не назначен'
        remaining_time_text = " "
        if order.status == 'preparing' and order.preparation_time and order.preparing_at:
            elapsed = (datetime.now() - order.preparing_at).total_seconds() / 60
            remaining = order.preparation_time - int(elapsed)
            if remaining > 0:
                remaining_time_text = f"\n⏱️ Осталось: ~{remaining} мин"
            else:
                remaining_time_text = f"\n⚠️ Заказ должен быть готов!"
        elif order.status == 'accepted' and order.preparation_time:
             remaining_time_text = f"\n🕐 Время приготовления: ~{order.preparation_time} мин (ожидайте)"
        comment_text = f"\n📝 Комментарий: {order.comment}" if order.comment else " "
        await update.message.reply_text(
            f"🛒 Заказ #{order.id}:\n\n"
            f"☕ {order.coffee_name}\n"
            f"💰 Сумма: {format_price(order.total_price)}\n"
            f"📊 Статус: {status_text}\n"
            f"👨💼 Готовит: {admin_name}{comment_text}{remaining_time_text}"
        )

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вернуться в главное меню"""
    telegram_id = update.effective_user.id
    is_admin_user = is_admin(telegram_id)
    await update.message.reply_text(
        "Главное меню",
        reply_markup=get_main_keyboard(is_admin_user)
    )
    logger.info(f"Возврат в главное меню. User ID: {telegram_id}, is_admin: {is_admin_user}")

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /admin для быстрого доступа к админ-панели"""
    await admin_panel(update, context)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    text = update.message.text
    telegram_id = update.effective_user.id

    if text == "☕ Меню":
        await show_menu(update, context)
    elif text == "💰 Бонусы":
        await show_bonuses(update, context)
    elif text == "📋 История заказов":
        await show_order_history(update, context)
    elif text == "🛒 Мой заказ":
        await show_current_order(update, context)
    elif text == "👨💼 Панель администратора":
        await admin_panel(update, context)
    elif text == "✅ На смене":
        await admin_on_duty(update, context)
    elif text == "❌ Сойти со смены":
        await admin_off_duty(update, context)
    elif text == "📦 Активные заказы":
        await admin_active_orders(update, context)
    elif text == "📢 Массовая рассылка":
        await broadcast_start(update, context)
    elif text == "🔙 В главное меню":
        await back_to_main(update, context)
    elif text == "📊 Статистика":
        await admin_statistics(update, context)
    else:
        # Проверяем, зарегистрирован ли пользователь
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
             await update.message.reply_text(
                 "Добро пожаловать! Для начала работы нажмите /start"
            )
        else:
            await update.message.reply_text(
                 "Используйте кнопки меню для навигации",
                reply_markup=get_main_keyboard(is_admin(telegram_id))
            )

# ==================== ГЛАВНАЯ ФУНКЦИЯ ====================

async def post_init(application: Application):
    """Инициализация после запуска бота"""
    await init_db()
    logger.info("База данных инициализирована")

def main():
    """Запуск бота"""
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # ConversationHandler для регистрации
    reg_conv = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            REG_FULL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_full_name)],
            REG_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_phone)],
            REG_BIRTH_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_birth_date)],
        },
        fallbacks=[CommandHandler('cancel', lambda u, c: u.message.reply_text('Отменено'))],
    )

    # ConversationHandler для заказа
    order_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(coffee_callback, pattern=r'^coffee_')],
        states={
            ORDER_SIZE: [
                CallbackQueryHandler(size_callback, pattern=r'^size_'),
                CallbackQueryHandler(back_handler, pattern=r'^back_'),
            ],
            ORDER_MILK: [
                CallbackQueryHandler(milk_callback, pattern=r'^milk_'),
                CallbackQueryHandler(back_handler, pattern=r'^back_'),
            ],
            ORDER_SYRUP: [
                CallbackQueryHandler(syrup_callback, pattern=r'^syrup_'),
                CallbackQueryHandler(back_handler, pattern=r'^back_'),
            ],
            ORDER_COMMENT: [
                CallbackQueryHandler(comment_callback, pattern=r'^(add_comment|skip_comment)$'),
                CallbackQueryHandler(back_handler, pattern=r'^back_'),
                MessageHandler(filters.TEXT & ~filters.COMMAND, comment_input),
            ],
            ORDER_BONUSES: [
                CallbackQueryHandler(bonus_callback, pattern=r'^bonus_'),
                CallbackQueryHandler(back_handler, pattern=r'^back_'),
            ],
            ORDER_CONFIRM: [
                CallbackQueryHandler(confirm_order_callback, pattern=r'^confirm_order$'),
                CallbackQueryHandler(cancel_order_callback, pattern=r'^cancel_order$'),
                CallbackQueryHandler(back_handler, pattern=r'^back_'),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_order_callback, pattern=r'^cancel_order$'),
            CallbackQueryHandler(back_handler, pattern=r'^back_'),
        ],
    )

    # ConversationHandler для рассылки
    broadcast_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^📢 Массовая рассылка$'), broadcast_start)],
        states={
            BROADCAST_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_message)],
            BROADCAST_IMAGE: [
                MessageHandler(filters.PHOTO, broadcast_image),
                CallbackQueryHandler(broadcast_no_image, pattern=r'^broadcast_no_image$'),
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel_broadcast)],
    )

    # Добавляем обработчики
    application.add_handler(reg_conv)
    application.add_handler(order_conv)
    application.add_handler(broadcast_conv)

    # Обработчики для администраторов
    application.add_handler(CallbackQueryHandler(admin_accept_order, pattern=r'^admin_accept_'))
    application.add_handler(CallbackQueryHandler(admin_preparing_order, pattern=r'^admin_prep_'))
    application.add_handler(CallbackQueryHandler(admin_ready_order, pattern=r'^admin_ready_'))
    application.add_handler(CallbackQueryHandler(admin_cancel_order, pattern=r'^admin_cancel_'))

    # Команды для отладки и администрирования
    application.add_handler(CommandHandler('myid', my_id))
    application.add_handler(CommandHandler('checkadmin', check_admin))
    application.add_handler(CommandHandler('admin', admin_command))

    # Обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Запускаем бота
    logger.info("Запуск бота...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
