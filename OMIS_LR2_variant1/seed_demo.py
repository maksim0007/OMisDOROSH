"""Необязательное заполнение учебной БД примерами для показа на защите."""
from main import AppInjector
from pathlib import Path
import threading

injector = AppInjector(str(Path(__file__).resolve().parent / "feedback.db"))
repo = injector.repo
if repo.FindAll():
    print("В базе уже есть отзывы. Данные не изменены.")
else:
    client = injector.auth.Login("client", "demo123")
    examples = [
        ("Доставка опоздала, плохой сервис и проблема с заказом", 1, 2),
        ("Отличные наушники, хорошее качество, спасибо", 5, 1),
        ("Понравилась быстрая поддержка, все отлично", 5, 3),
        ("Качество нормальное, но доставка долгая", 3, 2),
        ("Ужас: сломалась колонка, не работает", 1, 4),
        ("Хорошая колонка и удобный интерфейс", 4, 4),
    ]
    for text, rating, product_id in examples:
        injector.feedback_controller.SaveFeedback({
            "user": client, "text": text, "rating": rating, "product_id": product_id,
        })
    for thread in threading.enumerate():
        if thread.name.startswith("FeedbackAnalysis-"):
            thread.join(timeout=2)
    repo.ChangeStatus(2, "В работе", "Связались с клиентом")
    repo.ChangeStatus(2, "Решен", "Проблема решена")
    repo.ChangeStatus(3, "В работе", "Рассматриваем обращение")
    print("Добавлены 6 тестовых отзывов для демонстрации.")
