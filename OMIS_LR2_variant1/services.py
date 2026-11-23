"""Сервисы и хранилище: UI -> controller/service -> repository -> SQLite.

SQLite работает локально без установки СУБД: это сознательная адаптация
предложенной в ЛР1 PostgreSQL к демонстрационной учебной реализации.
"""
from __future__ import annotations

import csv
import hashlib
import os
import secrets
import sqlite3
import threading
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

from model import Client, Feedback, Product, Rating, Status

STATUSES = ("Новый", "В работе", "Решен", "Отклонен")
ROLES = ("Клиент", "Менеджер", "Аналитик", "Администратор")


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 120_000).hex()


class FeedbackRepository:
    """Хранилище доменных объектов с навигацией к Feedback (1:0..*)."""

    def __init__(self, path: str = "feedback.db") -> None:
        self.path = str(path)
        self._uri = self.path.startswith("file:")
        self._init_db()

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=10, uri=self._uri)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=10000")
            with connection:
                yield connection
        finally:
            connection.close()

    def _init_db(self) -> None:
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    login TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    role TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    password_hash TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    category TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id INTEGER NOT NULL REFERENCES users(id),
                    product_id INTEGER NOT NULL REFERENCES products(id),
                    text TEXT NOT NULL,
                    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
                    created_at TEXT NOT NULL,
                    sentiment TEXT NOT NULL DEFAULT 'ожидает анализа',
                    status TEXT NOT NULL DEFAULT 'Новый',
                    manager_comment TEXT NOT NULL DEFAULT '',
                    assigned_at TEXT,
                    CHECK (length(trim(text)) > 0)
                );
                CREATE TABLE IF NOT EXISTS settings (
                    name TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
            """)
            if db.execute("SELECT count(*) FROM products").fetchone()[0] == 0:
                db.executemany("INSERT INTO products (title,category) VALUES (?,?)", [
                    ("Наушники Aurora X", "Электроника"),
                    ("Доставка заказа", "Услуги"),
                    ("Техническая поддержка", "Сервис"),
                    ("Умная колонка HomeOne", "Электроника"),
                ])
            for login, name, role in [
                ("client", "Клиент Демо", "Клиент"),
                ("manager", "Менеджер Демо", "Менеджер"),
                ("analyst", "Аналитик Демо", "Аналитик"),
                ("admin", "Администратор Демо", "Администратор"),
            ]:
                if not db.execute("SELECT 1 FROM users WHERE login=?", (login,)).fetchone():
                    salt = secrets.token_hex(16)
                    db.execute(
                        "INSERT INTO users (login,name,email,role,salt,password_hash) VALUES (?,?,?,?,?,?)",
                        (login, name, f"{login}@example.local", role, salt,
                         hash_password("demo123", salt)),
                    )

    def FindProducts(self) -> list[Product]:
        with self._connect() as db:
            return [Product(row["id"], row["title"], row["category"])
                    for row in db.execute("SELECT * FROM products ORDER BY id")]

    def _row_to_feedback(self, r: sqlite3.Row) -> Feedback:
        return Feedback(
            id=r["id"], text=r["text"], created_at=r["created_at"],
            sentiment=r["sentiment"],
            client=Client(r["client_id"], r["client_name"], r["email"]),
            product=Product(r["product_id"], r["title"], r["category"]),
            rating=Rating(r["rating"], r["created_at"]), status=Status(r["status"]),
            manager_comment=r["manager_comment"], assigned_at=r["assigned_at"],
        )

    _BASE_QUERY = """
        SELECT f.*, u.name AS client_name,u.email,p.title,p.category
        FROM feedback f
        JOIN users u ON u.id=f.client_id
        JOIN products p ON p.id=f.product_id
    """

    def Save(self, feedback: Feedback) -> int:
        """Save(feedback): сохраняет отзыв и композиционно принадлежащую оценку."""
        if not feedback.text.strip():
            raise ValueError("Текст отзыва не может быть пустым")
        if not 1 <= feedback.rating.value <= 5:
            raise ValueError("Оценка должна быть от 1 до 5")
        with self._connect() as db:
            cursor = db.execute("""
                INSERT INTO feedback (client_id,product_id,text,rating,created_at,sentiment,status)
                VALUES (?,?,?,?,?,?,?)
            """, (feedback.client.id, feedback.product.id, feedback.text.strip(),
                  feedback.rating.value, feedback.created_at, feedback.sentiment,
                  feedback.status.name))
            return int(cursor.lastrowid)

    def FindById(self, feedback_id: int) -> Optional[Feedback]:
        with self._connect() as db:
            row = db.execute(self._BASE_QUERY + " WHERE f.id=?", (feedback_id,)).fetchone()
        return self._row_to_feedback(row) if row else None

    def FindAll(self, *, client_id: Optional[int] = None,
                status: Optional[str] = None, query: str = "") -> list[Feedback]:
        sql = self._BASE_QUERY + " WHERE 1=1"
        params: list[object] = []
        if client_id is not None:
            sql += " AND f.client_id=?"
            params.append(client_id)
        if status and status != "Все":
            sql += " AND f.status=?"
            params.append(status)
        if query.strip():
            sql += " AND (f.text LIKE ? OR p.title LIKE ? OR u.name LIKE ?)"
            params.extend([f"%{query.strip()}%"] * 3)
        sql += " ORDER BY f.id DESC"
        with self._connect() as db:
            rows = db.execute(sql, params).fetchall()
        return [self._row_to_feedback(row) for row in rows]

    def FindByPeriod(self, days: int = 30) -> list[Feedback]:
        threshold = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
        with self._connect() as db:
            rows = db.execute(
                self._BASE_QUERY + " WHERE f.created_at>=? ORDER BY f.created_at", (threshold,)
            ).fetchall()
        return [self._row_to_feedback(row) for row in rows]

    def ChangeStatus(self, feedback_id: int, status: str, comment: str = "") -> None:
        if status not in STATUSES:
            raise ValueError("Неизвестный статус")
        with self._connect() as db:
            row = db.execute("SELECT status FROM feedback WHERE id=?", (feedback_id,)).fetchone()
            if row is None:
                raise ValueError("Отзыв не найден")
            current = row["status"]
            allowed = {
                "Новый": {"В работе", "Отклонен"},
                "В работе": {"Решен", "Отклонен"},
                "Решен": {"В работе"},
                "Отклонен": set(),
            }
            if status != current and status not in allowed[current]:
                raise ValueError(f"Недопустимый переход: {current} → {status}")
            assigned_at = now_iso() if status == "В работе" and current == "Новый" else None
            db.execute("""
                UPDATE feedback
                SET status=?, manager_comment=?, assigned_at=COALESCE(?,assigned_at)
                WHERE id=?
            """, (status, comment, assigned_at, feedback_id))

    def UpdateSentiment(self, feedback_id: int, sentiment: str) -> None:
        with self._connect() as db:
            db.execute("UPDATE feedback SET sentiment=? WHERE id=?", (sentiment, feedback_id))

    def FindUsers(self) -> list[dict]:
        with self._connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT id,login,name,email,role FROM users ORDER BY id")]

    def GetUser(self, login: str) -> Optional[dict]:
        with self._connect() as db:
            row = db.execute("SELECT * FROM users WHERE login=?", (login,)).fetchone()
        return dict(row) if row else None

    def AddUser(self, login: str, name: str, email: str, role: str, password: str) -> None:
        if role not in ROLES:
            raise ValueError("Неизвестная роль")
        if not login.strip() or not name.strip() or "@" not in email or len(password) < 6:
            raise ValueError("Заполните имя, логин, email и пароль (от 6 символов)")
        salt = secrets.token_hex(16)
        try:
            with self._connect() as db:
                db.execute("""
                    INSERT INTO users(login,name,email,role,salt,password_hash)
                    VALUES (?,?,?,?,?,?)
                """, (login.strip(), name.strip(), email.strip(), role, salt,
                      hash_password(password, salt)))
        except sqlite3.IntegrityError as exc:
            raise ValueError("Логин или email уже существует") from exc

    def UpdateSettings(self, name: str, value: str) -> None:
        with self._connect() as db:
            db.execute("INSERT OR REPLACE INTO settings(name,value) VALUES (?,?)", (name, value))

    def GetSetting(self, name: str, default: str = "") -> str:
        with self._connect() as db:
            r = db.execute("SELECT value FROM settings WHERE name=?", (name,)).fetchone()
            return r[0] if r else default


class AuthService:
    def __init__(self, repo: FeedbackRepository) -> None:
        self.repo = repo

    def Login(self, login: str, password: str) -> dict:
        user = self.repo.GetUser(login.strip())
        if not user or not secrets.compare_digest(
            hash_password(password, user["salt"]), user["password_hash"]
        ):
            raise ValueError("Неверный логин или пароль")
        return {key: user[key] for key in ("id", "name", "login", "role", "email")}

    def Logout(self) -> None:
        pass  # Сеанс хранится только в App, аутентификация не использует cookie.


class SentimentAnalyzer:
    """«external»: демонстрационный детерминированный NLP-анализатор.

    Не является ML-моделью; текст анализируется по небольшому словарю.
    """
    POSITIVE = ("хорош", "отлич", "быстр", "понрав", "прекрас", "спасибо", "качеств", "удоб")
    NEGATIVE = ("плох", "ужас", "брак", "сломан", "не работа", "опозд", "долг", "проблем", "ошиб", "хам")

    def Analyze(self, text: str) -> str:
        lower = text.lower()
        pos = sum(lower.count(word) for word in self.POSITIVE)
        neg = sum(lower.count(word) for word in self.NEGATIVE)
        if pos > neg:
            return "положительный"
        if neg > pos:
            return "негативный"
        return "нейтральный"


class FeedbackService:
    def __init__(self, repo: FeedbackRepository, analyzer: SentimentAnalyzer) -> None:
        self.repo, self.analyzer = repo, analyzer

    def CreateFeedback(self, dto: dict) -> int:
        product = next((p for p in self.repo.FindProducts() if p.id == dto["product_id"]), None)
        if not product:
            raise ValueError("Выберите продукт")
        user = dto["user"]
        if user["role"] != "Клиент":
            raise PermissionError("Только клиент может отправить отзыв")
        feedback = Feedback(
            id=0, text=dto["text"].strip(), created_at=now_iso(), sentiment="ожидает анализа",
            client=Client(user["id"], user["name"], user["email"]), product=product,
            rating=Rating(int(dto["rating"]), now_iso()), status=Status("Новый"),
        )
        fid = self.repo.Save(feedback)
        # Асинхронный анализ не блокирует сообщение благодарности.
        threading.Thread(target=self._analyze_background, args=(fid, feedback.text),
                         name=f"FeedbackAnalysis-{fid}", daemon=True).start()
        return fid

    def _analyze_background(self, feedback_id: int, text: str) -> None:
        try:
            result = self.analyzer.Analyze(text)
            self.repo.UpdateSentiment(feedback_id, result)
        except Exception:
            # Если внешний анализатор недоступен, сохранённый отзыв остаётся с
            # маркером ожидания и может быть обработан повторно.
            pass

    def ChangeStatus(self, feedback_id: int, status: str, comment: str = "") -> None:
        self.repo.ChangeStatus(feedback_id, status, comment)


class FeedbackController:
    def __init__(self, service: FeedbackService) -> None:
        self.service = service

    def SaveFeedback(self, dto: dict) -> int:
        return self.service.CreateFeedback(dto)

    def ChangeStatus(self, feedback_id: int, status: str, comment: str = "") -> None:
        self.service.ChangeStatus(feedback_id, status, comment)


class AnalyticsService:
    def __init__(self, repo: FeedbackRepository) -> None:
        self.repo = repo

    def BuildDashboard(self, days: int = 30) -> dict:
        feedback = self.repo.FindByPeriod(days)
        ratings = [item.rating.value for item in feedback]
        sentiment = Counter(item.sentiment for item in feedback)
        product_counts = Counter(item.product.title for item in feedback)
        return {
            "total": len(feedback),
            "average": round(sum(ratings) / len(ratings), 2) if ratings else 0.0,
            "negative_percent": round(100 * sentiment["негативный"] / len(feedback), 1) if feedback else 0.0,
            "resolved": sum(item.status.name == "Решен" for item in feedback),
            "sentiments": sentiment,
            "ratings": Counter(ratings),
            "products": product_counts,
            "items": feedback,
        }

    def ExportReport(self, path: str, days: int = 30) -> None:
        items = self.repo.FindByPeriod(days)
        with open(path, "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle, delimiter=";")
            writer.writerow(["ID", "Клиент", "Продукт", "Оценка", "Текст", "Тональность", "Статус", "Дата"])
            for f in items:
                writer.writerow([f.id, f.client.name, f.product.title, f.rating.value,
                                 f.text, f.sentiment, f.status.name, f.created_at])


class AdminService:
    def __init__(self, repo: FeedbackRepository) -> None:
        self.repo = repo

    def CreateUser(self, login: str, name: str, email: str, role: str, password: str) -> None:
        self.repo.AddUser(login, name, email, role, password)

    def UpdateSettings(self, name: str, value: str) -> None:
        self.repo.UpdateSettings(name, value)
