import os
import tempfile
import time
import threading
import unittest
from pathlib import Path

from model import Feedback, Client, Product, Rating, Status
from services import (AdminService, AnalyticsService, AuthService, FeedbackRepository,
                      FeedbackService, SentimentAnalyzer, FeedbackController, now_iso)


class DomainTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = FeedbackRepository(str(Path(self.tmp.name) / "test.db"))
        self.auth = AuthService(self.repo)
        self.service = FeedbackService(self.repo, SentimentAnalyzer())
        self.controller = FeedbackController(self.service)
        self.client = self.auth.Login("client", "demo123")

    def tearDown(self):
        for thread in threading.enumerate():
            if thread.name.startswith("FeedbackAnalysis-"):
                thread.join(timeout=3)
        self.tmp.cleanup()

    def create(self, text="Отличный сервис, спасибо", rating=5):
        return self.controller.SaveFeedback({"user": self.client, "product_id": 1,
                                             "text": text, "rating": rating})

    def test_users_login_and_role(self):
        self.assertEqual(self.client["role"], "Клиент")
        with self.assertRaises(ValueError):
            self.auth.Login("client", "wrong")
        self.assertEqual(self.auth.Login("admin", "demo123")["role"], "Администратор")

    def test_feedback_save_and_composition(self):
        fid = self.create()
        feedback = self.repo.FindById(fid)
        self.assertEqual(feedback.rating.value, 5)
        self.assertEqual(feedback.client.name, "Клиент Демо")
        self.assertEqual(feedback.product.title, "Наушники Aurora X")
        self.assertEqual(feedback.status.name, "Новый")

    def test_validation(self):
        for text, rating in [("", 5), ("OK", 0), ("OK", 6)]:
            with self.assertRaises(ValueError):
                self.create(text, rating)

    def test_roles(self):
        user = self.auth.Login("manager", "demo123")
        with self.assertRaises(PermissionError):
            self.controller.SaveFeedback({"user": user, "product_id": 1,
                                          "text": "Текст", "rating": 5})

    def test_status_transitions(self):
        fid = self.create()
        self.controller.ChangeStatus(fid, "В работе", "Связались с клиентом")
        self.controller.ChangeStatus(fid, "Решен", "Проблема устранена")
        self.assertEqual(self.repo.FindById(fid).status.name, "Решен")
        self.controller.ChangeStatus(fid, "В работе", "Клиент не подтвердил")
        with self.assertRaises(ValueError):
            self.controller.ChangeStatus(fid, "Новый")

    def test_sentiment(self):
        analyzer = SentimentAnalyzer()
        self.assertEqual(analyzer.Analyze("Ужасная проблема, плохой сервис"), "негативный")
        self.assertEqual(analyzer.Analyze("Все отлично, спасибо"), "положительный")
        self.assertEqual(analyzer.Analyze("Текст без оценки"), "нейтральный")

    def test_async_sentiment(self):
        fid = self.create("Ужас, плохая доставка", 1)
        for _ in range(100):
            if self.repo.FindById(fid).sentiment != "ожидает анализа":
                break
            time.sleep(0.01)
        self.assertEqual(self.repo.FindById(fid).sentiment, "негативный")

    def test_analytics_and_report(self):
        self.create("Плохая доставка", 1)
        self.create("Отлично, спасибо", 5)
        dashboard = AnalyticsService(self.repo).BuildDashboard(30)
        self.assertEqual(dashboard["total"], 2)
        self.assertEqual(dashboard["average"], 3)
        path = str(Path(self.tmp.name) / "report.csv")
        AnalyticsService(self.repo).ExportReport(path)
        self.assertTrue(Path(path).read_text(encoding="utf-8-sig").startswith("ID;Клиент"))

    def test_administration(self):
        admin = AdminService(self.repo)
        admin.CreateUser("new_user", "Имя", "new@example.com", "Аналитик", "secret123")
        self.assertEqual(self.auth.Login("new_user", "secret123")["role"], "Аналитик")
        with self.assertRaises(ValueError):
            admin.CreateUser("new_user", "Имя", "new2@example.com", "Аналитик", "secret123")
        admin.UpdateSettings("sla_hours", "24")
        self.assertEqual(self.repo.GetSetting("sla_hours"), "24")

    def test_search_filter(self):
        fid = self.create("Отличные наушники", 4)
        self.assertEqual(len(self.repo.FindAll(status="Новый", query="наушники")), 1)
        self.assertEqual(len(self.repo.FindAll(status="Решен")), 0)


if __name__ == "__main__":
    unittest.main()
