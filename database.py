from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import aiosqlite
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    phone_number = Column(String(20), nullable=False)
    birth_date = Column(String(10), nullable=False)  # DD.MM.YYYY
    bonuses = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.now)
    last_order_at = Column(DateTime, nullable=True)
    
    orders = relationship("Order", back_populates="user")

class Admin(Base):
    __tablename__ = 'admins'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    is_on_duty = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    
    orders = relationship("Order", back_populates="admin")

class Order(Base):
    __tablename__ = 'orders'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    admin_id = Column(Integer, ForeignKey('admins.id'), nullable=True)
    
    # Информация о заказе
    coffee_id = Column(String(50), nullable=False)
    coffee_name = Column(String(100), nullable=False)
    size = Column(String(20), nullable=False)
    milk = Column(String(20), nullable=False)
    syrup = Column(String(20), nullable=False)
    
    # Цены
    base_price = Column(Float, nullable=False)
    milk_price = Column(Float, default=0.0)
    syrup_price = Column(Float, default=0.0)
    total_price = Column(Float, nullable=False)
    bonuses_used = Column(Float, default=0.0)
    bonuses_earned = Column(Float, default=0.0)
    
    # Статус заказа
    status = Column(String(20), default='pending')  # pending, accepted, preparing, ready, completed, cancelled
    preparation_time = Column(Integer, nullable=True)  # в минутах
    
    # Временные метки
    created_at = Column(DateTime, default=datetime.now)
    accepted_at = Column(DateTime, nullable=True)
    preparing_at = Column(DateTime, nullable=True)
    ready_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="orders")
    admin = relationship("Admin", back_populates="orders")

class Broadcast(Base):
    __tablename__ = 'broadcasts'
    
    id = Column(Integer, primary_key=True)
    admin_id = Column(Integer, ForeignKey('admins.id'), nullable=False)
    message = Column(Text, nullable=True)
    image_path = Column(String(255), nullable=True)
    sent_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)

# Асинхронный движок
engine = create_async_engine('sqlite+aiosqlite:///coffee_bot.db', echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    """Инициализация базы данных"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Добавляем администраторов если их нет
    async with async_session() as session:
        from config import ADMINS
        
        for admin_id, admin_name in ADMINS.items():
            result = await session.execute(
                select(Admin).where(Admin.telegram_id == admin_id)
            )
            existing_admin = result.scalar_one_or_none()
            
            if not existing_admin:
                admin = Admin(
                    telegram_id=admin_id,
                    name=admin_name,
                    is_on_duty=False
                )
                session.add(admin)
        
        await session.commit()

async def get_or_create_user(telegram_id: int, full_name: str, phone_number: str, birth_date: str):
    """Получить или создать пользователя"""
    from config import WELCOME_BONUS
    
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            user = User(
                telegram_id=telegram_id,
                full_name=full_name,
                phone_number=phone_number,
                birth_date=birth_date,
                bonuses=WELCOME_BONUS
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user, True  # Новый пользователь
        
        return user, False  # Существующий пользователь

async def get_user_by_telegram_id(telegram_id: int):
    """Получить пользователя по telegram_id"""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

async def get_all_users():
    """Получить всех пользователей"""
    async with async_session() as session:
        result = await session.execute(select(User))
        return result.scalars().all()

async def get_on_duty_admin():
    """Получить администратора на смене"""
    async with async_session() as session:
        result = await session.execute(
            select(Admin).where(Admin.is_on_duty == True)
        )
        return result.scalar_one_or_none()

async def set_admin_on_duty(admin_id: int, on_duty: bool):
    """Установить статус администратора"""
    async with async_session() as session:
        # Сначала снимаем всех со смены
        if on_duty:
            await session.execute(
                update(Admin).values(is_on_duty=False)
            )
        
        # Устанавливаем статус конкретному админу
        result = await session.execute(
            select(Admin).where(Admin.telegram_id == admin_id)
        )
        admin = result.scalar_one_or_none()
        
        if admin:
            admin.is_on_duty = on_duty
            await session.commit()
            return admin
        return None

async def create_order(user_id: int, coffee_data: dict):
    """Создать заказ"""
    async with async_session() as session:
        order = Order(
            user_id=user_id,
            **coffee_data
        )
        session.add(order)
        await session.commit()
        await session.refresh(order)
        return order

async def get_order(order_id: int):
    """Получить заказ по ID"""
    async with async_session() as session:
        result = await session.execute(
            select(Order).where(Order.id == order_id)
        )
        return result.scalar_one_or_none()

async def update_order_status(order_id: int, status: str, admin_id: int = None, preparation_time: int = None):
    """Обновить статус заказа"""
    async with async_session() as session:
        result = await session.execute(
            select(Order).where(Order.id == order_id)
        )
        order = result.scalar_one_or_none()
        
        if order:
            order.status = status
            
            if admin_id:
                order.admin_id = admin_id
            
            if preparation_time:
                order.preparation_time = preparation_time
            
            # Обновляем временные метки
            now = datetime.now()
            if status == 'accepted':
                order.accepted_at = now
            elif status == 'preparing':
                order.preparing_at = now
            elif status == 'ready':
                order.ready_at = now
            elif status == 'completed':
                order.completed_at = now
            
            await session.commit()
            return order
        return None

async def add_bonuses_to_user(user_id: int, amount: float):
    """Добавить бонусы пользователю"""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            user.bonuses += amount
            await session.commit()
            return user
        return None

async def use_bonuses(user_id: int, amount: float):
    """Списать бонусы у пользователя"""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if user and user.bonuses >= amount:
            user.bonuses -= amount
            await session.commit()
            return user
        return None

async def get_pending_orders():
    """Получить ожидающие заказы"""
    async with async_session() as session:
        result = await session.execute(
            select(Order).where(Order.status.in_(['pending', 'accepted', 'preparing']))
            .order_by(Order.created_at.desc())
        )
        return result.scalars().all()

async def get_user_orders(user_id: int, limit: int = 10):
    """Получить заказы пользователя"""
    async with async_session() as session:
        result = await session.execute(
            select(Order).where(Order.user_id == user_id)
            .order_by(Order.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

# Импортируем select и update
from sqlalchemy import select, update
