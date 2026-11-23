"""Лабораторная работа № 2 — вариант № 1, ОМИС.

Запуск: python main.py
Логины: client, manager, analyst, admin; пароль для всех: demo123.
"""
import os
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from services import (AdminService, AnalyticsService, AuthService, FeedbackController,
                      FeedbackRepository, FeedbackService, SentimentAnalyzer)
from ui import (AdminWindow, DashboardWindow, FeedbackFormWindow, LoginWindow, SupportWindow,
                BG, BLUE, DARK)


class AppInjector:
    """«injector»: центральное создание сервисов, хранилища и окон."""
    def __init__(self, db_path: str):
        self.repo = FeedbackRepository(db_path)
        self.auth = AuthService(self.repo)
        self.analyzer = SentimentAnalyzer()
        self.feedback_service = FeedbackService(self.repo, self.analyzer)
        self.feedback_controller = FeedbackController(self.feedback_service)
        self.analytics = AnalyticsService(self.repo)
        self.admin = AdminService(self.repo)

    def Register(self) -> dict:
        return {"repo": self.repo, "auth": self.auth, "controller": self.feedback_controller,
                "feedback_service": self.feedback_service, "analytics": self.analytics,
                "admin": self.admin}

    def CreateWindow(self, app: "App", user: dict | None):
        if user is None:
            return LoginWindow(app, self.auth)
        if user["role"] == "Клиент":
            return FeedbackFormWindow(app, user, self.feedback_controller, self.repo)
        if user["role"] == "Менеджер":
            return SupportWindow(app, user, self.repo, self.feedback_controller)
        if user["role"] == "Аналитик":
            return DashboardWindow(app, user, self.analytics)
        if user["role"] == "Администратор":
            return AdminWindow(app, user, self.admin, self.repo)
        raise ValueError("Неизвестная роль пользователя")


class App(tk.Tk):
    """«main»: запуск, навигация по окнам и завершение приложения."""
    def __init__(self, db_path: str | None = None):
        super().__init__()
        self.title("OMIS — Учёт и анализ клиентских отзывов")
        self.geometry("1140x790")
        self.minsize(940, 640)
        self.configure(background=BG)
        self._configure_styles()
        database = db_path or str(Path(__file__).resolve().parent / "feedback.db")
        self.injector = AppInjector(database)
        self.user = None
        self.current_window = None
        self.ShowWindow(None)
        self.protocol("WM_DELETE_WINDOW", self.Exit)

    def _configure_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=DARK, font=("Arial", 10))
        style.configure("TButton", font=("Arial", 10), padding=(13, 9))
        style.map("TButton", background=[("active", "#dbeafe")])
        style.configure("Card.TFrame", background="white", relief="solid", borderwidth=1)
        style.configure("Brand.TLabel", font=("Arial", 12, "bold"), foreground=BLUE)
        style.configure("Large.TLabel", font=("Arial", 23, "bold"), background="white")
        style.configure("Muted.TLabel", foreground="#687993", font=("Arial", 10))
        style.configure("Section.TLabel", font=("Arial", 12, "bold"))
        style.configure("Kpi.TLabel", font=("Arial", 23, "bold"), background="white")
        style.configure("Primary.TButton", background=BLUE, foreground="white", font=("Arial", 10, "bold"))
        style.map("Primary.TButton", background=[("active", "#1d4ed8")], foreground=[("active", "white")])
        style.configure("Treeview", rowheight=27, font=("Arial", 10))
        style.configure("Treeview.Heading", font=("Arial", 10, "bold"), background="#dfe8f5")

    def ShowWindow(self, user: dict | None):
        if self.current_window:
            self.current_window.destroy()
        self.current_window = self.injector.CreateWindow(self, user)

    def ShowRoleWindow(self, user: dict):
        self.user = user
        self.ShowWindow(user)

    def Logout(self):
        self.injector.auth.Logout()
        self.user = None
        self.ShowWindow(None)

    def Run(self):
        self.mainloop()

    def Exit(self):
        self.destroy()


if __name__ == "__main__":
    App().Run()
