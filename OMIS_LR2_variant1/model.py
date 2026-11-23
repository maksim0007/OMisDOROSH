"""Объектная модель из ЛР1: классы данных не содержат бизнес-логики."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Client:
    id: int
    name: str
    email: str


@dataclass
class Product:
    id: int
    title: str
    category: str


@dataclass
class Rating:
    value: int
    date: str


@dataclass
class Status:
    name: str


@dataclass
class Feedback:
    id: int
    text: str
    created_at: str
    sentiment: str
    client: Client
    product: Product
    rating: Rating
    status: Status
    manager_comment: str = ""
    assigned_at: Optional[str] = None
