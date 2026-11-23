"""Пять UI-классов базовой диаграммы и композиционный корневой App."""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from services import STATUSES, ROLES

BG = "#f4f7fb"
DARK = "#1b2a45"
BLUE = "#2563eb"
BORDER = "#dae2ed"


def heading(parent: tk.Widget, title: str, subtitle: str = "") -> None:
    tk.Label(parent, text=title, font=("Arial", 23, "bold"), fg=DARK, bg=BG,
             anchor="w").pack(fill="x", pady=(0, 4))
    if subtitle:
        tk.Label(parent, text=subtitle, font=("Arial", 10), fg="#687993", bg=BG,
                 anchor="w").pack(fill="x", pady=(0, 17))


def field(parent: tk.Widget, name: str, *, width: int = 38, password: bool = False):
    ttk.Label(parent, text=name).pack(anchor="w", pady=(12, 4))
    entry = ttk.Entry(parent, width=width, show="*" if password else "")
    entry.pack(anchor="w", fill="x")
    return entry


class BaseWindow(ttk.Frame):
    def __init__(self, app: "App", user: dict | None = None) -> None:
        super().__init__(app, padding=24)
        self.app, self.user = app, user
        self.pack(fill="both", expand=True)

    def nav(self) -> None:
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 22))
        ttk.Label(bar, text="OMIS / CLIENT EXPERIENCE", style="Brand.TLabel").pack(side="left")
        ttk.Button(bar, text="Выйти из аккаунта", command=self.app.Logout).pack(side="right")
        if self.user:
            ttk.Label(bar, text=f'{self.user["name"]}  ·  {self.user["role"]}',
                      style="Muted.TLabel").pack(side="right", padx=16)


class LoginWindow(BaseWindow):
    def __init__(self, app: "App", auth_service) -> None:
        super().__init__(app)
        self.auth_service = auth_service
        wrap = ttk.Frame(self, padding=35, style="Card.TFrame")
        wrap.pack(expand=True, ipadx=30, ipady=15)
        ttk.Label(wrap, text="АВТОМАТИЗИРОВАННАЯ СИСТЕМА", style="Muted.TLabel").pack(anchor="w")
        ttk.Label(wrap, text="Вход в систему", style="Large.TLabel").pack(anchor="w", pady=(12, 8))
        ttk.Label(wrap, text="Учёт и анализ клиентских отзывов", style="Muted.TLabel").pack(anchor="w")
        self.login = field(wrap, "Логин")
        self.login.insert(0, "client")
        self.password = field(wrap, "Пароль", password=True)
        self.password.insert(0, "demo123")
        ttk.Button(wrap, text="Войти", style="Primary.TButton", command=self.OnSubmit).pack(fill="x", pady=(22, 12))
        ttk.Label(wrap, text="Демо: client / manager / analyst / admin", style="Muted.TLabel").pack(anchor="w")
        ttk.Label(wrap, text="Пароль для всех: demo123", style="Muted.TLabel").pack(anchor="w", pady=(3, 0))
        self.password.bind("<Return>", lambda _event: self.OnSubmit())
        self.login.focus_set()

    def OnSubmit(self) -> None:
        try:
            user = self.auth_service.Login(self.login.get(), self.password.get())
            self.app.ShowRoleWindow(user)
        except ValueError as exc:
            self.ShowError(str(exc))

    def ShowError(self, text: str = "Ошибка авторизации") -> None:
        messagebox.showerror("Не удалось войти", text, parent=self)


class FeedbackFormWindow(BaseWindow):
    def __init__(self, app: "App", user: dict, controller, repo) -> None:
        super().__init__(app, user)
        self.controller, self.repo = controller, repo
        self.nav()
        heading(self, "Оставить отзыв", "Расскажите, что понравилось или что нужно улучшить")
        card = ttk.Frame(self, padding=22, style="Card.TFrame")
        card.pack(fill="x")
        ttk.Label(card, text="Продукт или услуга").pack(anchor="w")
        self.products = repo.FindProducts()
        self.product_labels = {f"{p.title} · {p.category}": p.id for p in self.products}
        self.product = ttk.Combobox(card, state="readonly", values=list(self.product_labels), width=55)
        self.product.pack(anchor="w", pady=(6, 14))
        if self.products:
            self.product.current(0)
        ttk.Label(card, text="Ваша оценка").pack(anchor="w")
        self.rating_var = tk.IntVar(value=5)
        scorebar = ttk.Frame(card)
        scorebar.pack(anchor="w", pady=(7, 12))
        for i in range(1, 6):
            ttk.Radiobutton(scorebar, text=f"★ {i}", value=i, variable=self.rating_var).pack(side="left", padx=(0, 13))
        ttk.Label(card, text="Текст отзыва").pack(anchor="w", pady=(3, 6))
        self.text = tk.Text(card, height=6, width=72, wrap="word", relief="solid", bd=1,
                            font=("Arial", 11), padx=10, pady=10)
        self.text.pack(fill="x")
        self.text.insert("1.0", "")
        buttons = ttk.Frame(card)
        buttons.pack(fill="x", pady=(16, 2))
        ttk.Button(buttons, text="Отправить отзыв", style="Primary.TButton",
                   command=lambda: self.OnSubmit(self.user, self._dto())).pack(side="right")
        ttk.Button(buttons, text="Очистить", command=lambda: self.text.delete("1.0", "end")).pack(side="right", padx=8)
        ttk.Separator(self).pack(fill="x", pady=20)
        ttk.Label(self, text="Мои последние отзывы", style="Section.TLabel").pack(anchor="w", pady=(0, 8))
        self.history = ttk.Treeview(self, columns=("product", "rating", "sentiment", "status"),
                                    show="headings", height=5)
        for col, title, width in [
            ("product", "Продукт", 310), ("rating", "Оценка", 80),
            ("sentiment", "Тональность", 170), ("status", "Статус", 130)
        ]:
            self.history.heading(col, text=title)
            self.history.column(col, width=width)
        self.history.pack(fill="both", expand=True)
        self.ShowHistory()

    def _dto(self) -> dict:
        return {"product_id": self.product_labels.get(self.product.get()),
                "rating": self.rating_var.get(), "text": self.text.get("1.0", "end").strip()}

    def OnSubmit(self, user: dict, dto: dict) -> None:
        dto["user"] = user
        try:
            feedback_id = self.controller.SaveFeedback(dto)
            self.text.delete("1.0", "end")
            self.ShowThanks(feedback_id)
            self.ShowHistory()
        except (ValueError, PermissionError, TypeError) as exc:
            messagebox.showerror("Ошибка данных", str(exc), parent=self)

    def ShowThanks(self, feedback_id: int) -> None:
        messagebox.showinfo("Спасибо", f"Отзыв № {feedback_id} сохранён. Спасибо за обратную связь!",
                            parent=self)

    def ShowHistory(self) -> None:
        self.history.delete(*self.history.get_children())
        for f in self.repo.FindAll(client_id=self.user["id"]):
            self.history.insert("", "end", values=(f.product.title, f.rating.value,
                                                   f.sentiment, f.status.name))


class SupportWindow(BaseWindow):
    def __init__(self, app: "App", user: dict, repo, controller) -> None:
        super().__init__(app, user)
        self.repo, self.controller = repo, controller
        self.nav()
        heading(self, "Обработка отзывов", "Фильтрация, просмотр и изменение состояния обращения")
        filterbar = ttk.Frame(self)
        filterbar.pack(fill="x", pady=(0, 10))
        ttk.Label(filterbar, text="Статус").pack(side="left", padx=(0, 8))
        self.status_filter = ttk.Combobox(filterbar, state="readonly", values=("Все", *STATUSES), width=16)
        self.status_filter.current(0)
        self.status_filter.pack(side="left", padx=(0, 20))
        self.search = ttk.Entry(filterbar, width=34)
        self.search.pack(side="left", padx=(0, 10))
        ttk.Button(filterbar, text="Поиск / обновить", command=self.ShowList).pack(side="left")
        self.status_filter.bind("<<ComboboxSelected>>", lambda _event: self.ShowList())
        columns = ("id", "client", "product", "rating", "sentiment", "status", "date")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=9)
        for col, label, width in [
            ("id", "ID", 55), ("client", "Клиент", 155), ("product", "Продукт", 190),
            ("rating", "Оценка", 72), ("sentiment", "Тональность", 135),
            ("status", "Статус", 110), ("date", "Дата", 145),
        ]:
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width, minwidth=50)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", lambda _event: self.ShowDetails())
        ttk.Label(self, text="Содержание и внутренний комментарий", style="Section.TLabel").pack(anchor="w", pady=(15, 6))
        self.detail = tk.Text(self, height=4, wrap="word", font=("Arial", 10), padx=8, pady=8)
        self.detail.pack(fill="x")
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(12, 0))
        for label, status in [("Взять в работу", "В работе"), ("Решен", "Решен"),
                              ("Отклонить", "Отклонен")]:
            ttk.Button(toolbar, text=label, command=lambda s=status: self.OnSubmitStatus(s)).pack(side="left", padx=(0, 10))
        self.ShowList()

    def ShowList(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for f in self.repo.FindAll(status=self.status_filter.get(), query=self.search.get()):
            self.tree.insert("", "end", iid=str(f.id), values=(
                f.id, f.client.name, f.product.title, f.rating.value, f.sentiment,
                f.status.name, f.created_at[:16].replace("T", " "),
            ))

    def _selected_id(self) -> int | None:
        items = self.tree.selection()
        return int(items[0]) if items else None

    def ShowDetails(self, feedback_id: int | None = None) -> None:
        feedback_id = feedback_id or self._selected_id()
        self.detail.delete("1.0", "end")
        if feedback_id is None:
            return
        f = self.repo.FindById(feedback_id)
        if f:
            self.detail.insert("1.0", f"Отзыв № {f.id}: {f.text}\n\nКомментарий менеджера: {f.manager_comment or '(нет)'}")

    def OnSubmitStatus(self, status: str) -> None:
        feedback_id = self._selected_id()
        if feedback_id is None:
            messagebox.showwarning("Выберите отзыв", "Выберите строку в таблице", parent=self)
            return
        comment = self.detail.get("1.0", "end").strip()
        # Внутренний комментарий вводится после метки 'Комментарий менеджера:'.
        marker = "Комментарий менеджера:"
        comment = comment.split(marker, 1)[1].strip() if marker in comment else ""
        if comment == "(нет)":
            comment = ""
        try:
            self.controller.ChangeStatus(feedback_id, status, comment)
            self.ShowList()
            if self.tree.exists(str(feedback_id)):
                self.tree.selection_set(str(feedback_id))
                self.ShowDetails(feedback_id)
        except ValueError as exc:
            messagebox.showerror("Переход невозможен", str(exc), parent=self)


class DashboardWindow(BaseWindow):
    def __init__(self, app: "App", user: dict, analytics) -> None:
        super().__init__(app, user)
        self.analytics = analytics
        self.nav()
        heading(self, "Аналитика клиентского опыта", "Показатели удовлетворённости и тональность отзывов")
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 18))
        ttk.Label(bar, text="Период").pack(side="left", padx=(0, 10))
        self.period = ttk.Combobox(bar, state="readonly", values=("7 дней", "30 дней", "90 дней", "365 дней"), width=14)
        self.period.set("30 дней")
        self.period.pack(side="left")
        ttk.Button(bar, text="Построить отчёт", command=self.ShowCharts).pack(side="left", padx=12)
        ttk.Button(bar, text="Экспорт CSV", command=self.ExportReport).pack(side="right")
        kpis = ttk.Frame(self)
        kpis.pack(fill="x")
        self.cards = []
        for _ in range(4):
            f = ttk.Frame(kpis, padding=18, style="Card.TFrame")
            f.pack(side="left", fill="x", expand=True, padx=(0, 10))
            title = ttk.Label(f, text="", style="Muted.TLabel")
            title.pack(anchor="w")
            value = ttk.Label(f, text="", style="Kpi.TLabel")
            value.pack(anchor="w", pady=7)
            self.cards.append((title, value))
        ttk.Label(self, text="Распределение оценок по пятибалльной шкале", style="Section.TLabel").pack(
            anchor="w", pady=(25, 10))
        self.canvas = tk.Canvas(self, height=270, bg="white", highlightthickness=1,
                                highlightbackground=BORDER)
        self.canvas.pack(fill="both", expand=True)
        self.summary = ttk.Label(self, text="", style="Muted.TLabel")
        self.summary.pack(anchor="w", pady=12)
        self.ShowCharts()

    def _days(self) -> int:
        return int(self.period.get().split()[0])

    def ShowCharts(self, period: int | None = None) -> None:
        data = self.analytics.BuildDashboard(period or self._days())
        for (title, value), label, number in zip(self.cards,
                ("СРЕДНЯЯ ОЦЕНКА", "ВСЕГО ОТЗЫВОВ", "ДОЛЯ НЕГАТИВА", "РЕШЕНО"),
                (f'{data["average"]:.2f} / 5', str(data["total"]),
                 f'{data["negative_percent"]}%', str(data["resolved"]))):
            title.config(text=label)
            value.config(text=number)
        self.canvas.delete("all")
        width = 800
        height = 220
        ratings = data["ratings"]
        largest = max([1, *ratings.values()])
        for i in range(1, 6):
            x = 65 + (i - 1) * 145
            h = ratings.get(i, 0) / largest * 165
            self.canvas.create_rectangle(x, height-h, x+85, height, fill="#4b8af6", outline="")
            self.canvas.create_text(x+42, height-h-13, text=str(ratings.get(i, 0)), fill=DARK, font=("Arial", 11, "bold"))
            self.canvas.create_text(x+42, height+22, text=f"★ {i}", fill=DARK, font=("Arial", 11))
        sentiments = data["sentiments"]
        self.summary.config(text=(
            f'Тональность: положительная — {sentiments["положительный"]}; '
            f'нейтральная — {sentiments["нейтральный"]}; '
            f'негативная — {sentiments["негативный"]}; '
            f'ожидает анализа — {sentiments["ожидает анализа"]}.'
        ))

    def ExportReport(self, fmt: str = "csv") -> None:
        path = filedialog.asksaveasfilename(title="Экспорт отчёта", defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")], parent=self)
        if path:
            self.analytics.ExportReport(path, self._days())
            messagebox.showinfo("Экспорт завершён", f"Сохранено: {path}", parent=self)


class AdminWindow(BaseWindow):
    def __init__(self, app: "App", user: dict, admin, repo) -> None:
        super().__init__(app, user)
        self.admin, self.repo = admin, repo
        self.nav()
        heading(self, "Администрирование", "Управление пользователями и настройками")
        columns = ("id", "login", "name", "role", "email")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=9)
        for col, label, width in [
            ("id", "ID", 65), ("login", "Логин", 165), ("name", "Имя", 230),
            ("role", "Роль", 170), ("email", "Email", 260),
        ]:
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width)
        self.tree.pack(fill="x")
        ttk.Label(self, text="Добавить пользователя", style="Section.TLabel").pack(anchor="w", pady=(20, 10))
        form = ttk.Frame(self)
        form.pack(fill="x")
        self.entries = {}
        for label, key in [("Логин", "login"), ("Имя", "name"), ("Email", "email"), ("Пароль", "password")]:
            f = ttk.Frame(form)
            f.pack(side="left", padx=(0, 12))
            ttk.Label(f, text=label).pack(anchor="w", pady=(0, 5))
            self.entries[key] = ttk.Entry(f, width=22, show="*" if key == "password" else "")
            self.entries[key].pack()
        f = ttk.Frame(form)
        f.pack(side="left")
        ttk.Label(f, text="Роль").pack(anchor="w", pady=(0, 5))
        self.role = ttk.Combobox(f, state="readonly", width=17, values=ROLES)
        self.role.set("Клиент")
        self.role.pack()
        ttk.Button(self, text="Создать пользователя", style="Primary.TButton",
                   command=self.OnSubmitUser).pack(anchor="w", pady=(12, 22))
        ttk.Separator(self).pack(fill="x", pady=(2, 18))
        ttk.Label(self, text="Настройки приложения", style="Section.TLabel").pack(anchor="w")
        settings = ttk.Frame(self)
        settings.pack(anchor="w", pady=10)
        ttk.Label(settings, text="SLA, часов:").pack(side="left", padx=(0, 9))
        self.sla = ttk.Entry(settings, width=7)
        self.sla.insert(0, repo.GetSetting("sla_hours", "24"))
        self.sla.pack(side="left")
        ttk.Button(settings, text="Сохранить", command=self.OnSubmitSettings).pack(side="left", padx=12)
        self.ShowUsers()

    def ShowUsers(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for user in self.repo.FindUsers():
            self.tree.insert("", "end", values=(user["id"], user["login"], user["name"],
                                                       user["role"], user["email"]))

    def OnSubmitUser(self) -> None:
        vals = {name: entry.get() for name, entry in self.entries.items()}
        try:
            self.admin.CreateUser(vals["login"], vals["name"], vals["email"],
                                  self.role.get(), vals["password"])
            self.ShowUsers()
            for e in self.entries.values():
                e.delete(0, "end")
            messagebox.showinfo("Пользователь создан", "Учётная запись добавлена", parent=self)
        except ValueError as exc:
            messagebox.showerror("Ошибка", str(exc), parent=self)

    def OnSubmitSettings(self) -> None:
        try:
            v = int(self.sla.get())
            if not 1 <= v <= 720:
                raise ValueError
            self.admin.UpdateSettings("sla_hours", str(v))
            messagebox.showinfo("Сохранено", "Настройки обновлены", parent=self)
        except ValueError:
            messagebox.showerror("Ошибка", "SLA должен быть целым числом от 1 до 720", parent=self)
