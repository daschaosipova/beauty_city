from django.db import models


# 1. ТАБЛИЦА САЛОНОВ
# Отвечает за сценарий: "Предложили выбрать ближайший салон"
class Salon(models.Model):
    name = models.CharField(max_length=100, verbose_name="Название салона")
    address = models.CharField(max_length=255, verbose_name="Адрес")
    phone = models.CharField(max_length=20, verbose_name="Телефон филиала")

    def __str__(self):
        return f"{self.name} ({self.address})"

    class Meta:
        verbose_name = "Салон"
        verbose_name_plural = "Салоны"


# 2. ТАБЛИЦА УСЛУГ
# Отвечает за сценарии: "Выбрать процедуру" и "Интересно узнать цены"
class Service(models.Model):
    name = models.CharField(max_length=150, verbose_name="Название процедуры")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена (руб.)")
    duration_minutes = models.IntegerField(default=60, verbose_name="Длительность (в минутах)")

    def __str__(self):
        return f"{self.name} — {self.price} руб."

    class Meta:
        verbose_name = "Услуга"
        verbose_name_plural = "Услуги"


# 3. ТАБЛИЦА МАСТЕРОВ (СПЕЦИАЛИСТОВ)
# Отвечает за сценарии: "Попасть к любимому специалисту" и "Выбрать сразу мастера"
class Master(models.Model):
    full_name = models.CharField(max_length=150, verbose_name="ФИО Мастера")
    salons = models.ManyToManyField(Salon, verbose_name="В каких салонах работает")
    services = models.ManyToManyField(Service, verbose_name="Какие процедуры делает")
    is_active = models.BooleanField(default=True, verbose_name="Работает сейчас в сети?")

    def __str__(self):
        return self.full_name

    class Meta:
        verbose_name = "Мастер"
        verbose_name_plural = "Мастера"


# 4. ТАБЛИЦА КЛИЕНТОВ И СОГЛАСИЯ НА ПД
# Отвечает за сценарии: "Избежать штрафа за ПД", "Спросили номер телефона" и "100 дней после визита"
class Client(models.Model):
    telegram_id = models.BigIntegerField(unique=True, verbose_name="ID пользователя в Telegram")
    username = models.CharField(max_length=100, blank=True, null=True, verbose_name="Никнейм (@username)")
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Номер телефона")
    
    # Юридический блок безопасности
    is_terms_accepted = models.BooleanField(default=False, verbose_name="Согласен с обработкой ПД?")
    terms_accepted_at = models.DateTimeField(blank=True, null=True, verbose_name="Дата и время принятия согласия")

    def __str__(self):
        return f"{self.phone or 'Новый клиент'} (@{self.username or 'нет'})"

    class Meta:
        verbose_name = "Клиент"
        verbose_name_plural = "Клиенты"


# 5. ТАБЛИЦА РАСПИСАНИЯ (СВОБОДНЫЕ ОКНА)
# Отвечает за сценарии: "Доступные даты записи", "Свободные окна + адреса"
class TimeSlot(models.Model):
    master = models.ForeignKey(Master, on_delete=models.CASCADE, verbose_name="Мастер")
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, verbose_name="Салон, где принимает мастер в этот день")
    date = models.DateField(verbose_name="Дата")
    time = models.TimeField(verbose_name="Время начала приема")
    is_booked = models.BooleanField(default=False, verbose_name="Слот уже забронирован?")

    def __str__(self):
        return f"{self.date} в {self.time} — {self.master.full_name} ({self.salon.name})"

    class Meta:
        verbose_name = "Свободное окно (Слот)"
        verbose_name_plural = "Расписание (Слоты)"


# 6. ТАБЛИЦА ЗАПИСЕЙ НА ПРОЦЕДУРЫ
# Отвечает за сценарии: "Получил подтверждение", "Принять оплату и чаевые", "Запись по телефону через админку"
class Appointment(models.Model):
    # Статусы оплаты
    STATUS_CHOICES = [
        ('pending', 'Ожидает оплаты'),
        ('paid', 'Оплачено'),
        ('completed', 'Визит завершен'),
        ('cancelled', 'Отменено'),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, verbose_name="Клиент")
    slot = models.OneToOneField(TimeSlot, on_delete=models.PROTECT, verbose_name="Выбранное время и мастер")
    service = models.ForeignKey(Service, on_delete=models.PROTECT, verbose_name="Услуга")
    
    # Блок оплаты и чаевых
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Статус записи")
    tips_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Чаевые мастера (руб.)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания записи")

    feedback = models.TextField(blank=True, null=True, verbose_name="Текст отзыва")
    feedback_asked = models.BooleanField(default=False, verbose_name="Уже спрашивали отзыв?")

    def __str__(self):
        return f"Запись {self.id}: {self.client} к {self.slot.master} на {self.slot.date}"

    class Meta:
        verbose_name = "Запись на процедуру"
        verbose_name_plural = "Записи на процедуры"
