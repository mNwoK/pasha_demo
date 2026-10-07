"""Pydantic-схемы: валидация входных данных и формирование ответов API.

Схемы с суффиксом *Create — что клиент присылает в теле запроса.
Схемы с суффиксом *Read — что API возвращает в ответе.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field


# --- Пользователи ---


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=100, examples=["ivan"])
    email: EmailStr = Field(examples=["ivan@example.com"])


class UserRead(BaseModel):
    id: int
    username: str
    email: str
    created_at: datetime


# --- Товары ---


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200, examples=["Беспроводная мышь"])
    description: str | None = Field(default=None, examples=["Компактная мышь"])
    price: Decimal = Field(gt=0, examples=["1499.99"])
    stock: int = Field(ge=0, default=0, examples=[10])


class ProductRead(BaseModel):
    id: int
    name: str
    description: str | None
    price: Decimal
    stock: int


# --- Корзина ---


class CartItemAdd(BaseModel):
    product_id: int = Field(gt=0, examples=[1])
    quantity: int = Field(gt=0, le=1000, default=1, examples=[2])


class CartItemUpdate(BaseModel):
    quantity: int = Field(ge=1, le=1000, examples=[5])


class CartItemRead(BaseModel):
    product_id: int
    name: str
    price: Decimal
    quantity: int
    total: Decimal


class CartRead(BaseModel):
    user_id: int
    items: list[CartItemRead]
    total: Decimal
