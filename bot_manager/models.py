from django.db import models


class Salon(models.Model):
    name = models.CharField(max_length=100, verbose_name="Название салона")
    address = models.CharField(max_length=255, verbose_name="Адрес")
    phone = models.CharField(max_length=20, verbose_name="Телефон филиала")

    def __str__(self):
        return f"{self.name} ({self.address})"

    class Meta:
        verbose_name = "Салон"
        verbose_name_plural = "Салоны"


class Service(models.Model):
    name = models.CharField(max_length=150, verbose_name="Название процедуры")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена (руб.)")
    duration_minutes = models.IntegerField(default=60, verbose_name="Длительность (в минутах)")

    def __str__(self):
        return f"{self.name} — {self.price} руб."

    class Meta:
        verbose_name = "Услуга"
        verbose_name_plural = "Услуги"


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


class Client(models.Model):
    telegram_id = models.BigIntegerField(unique=True, verbose_name="ID пользователя в Telegram")
    username = models.CharField(max_length=100, blank=True, null=True, verbose_name="Никнейм (@username)")
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Номер телефона")
    is_terms_accepted = models.BooleanField(default=False, verbose_name="Согласен с обработкой ПД?")
    terms_accepted_at = models.DateTimeField(blank=True, null=True, verbose_name="Дата и время принятия согласия")

    def __str__(self):
        return f"{self.phone or 'Новый клиент'} (@{self.username or 'нет'})"

    class Meta:
        verbose_name = "Клиент"
        verbose_name_plural = "Клиенты"


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


class PromoCode(models.Model):
    code = models.CharField(max_length=50, unique=True, verbose_name="Промокод")
    discount_percent = models.PositiveIntegerField(default=10, verbose_name="Скидка (%)")
    is_active = models.BooleanField(default=True, verbose_name="Активен?")
    valid_until = models.DateField(null=True, blank=True, verbose_name="Действует до (включительно)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    def __str__(self):
        return self.code

    class Meta:
        verbose_name = "Промокод"
        verbose_name_plural = "Промокоды"


class Appointment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Ожидает оплаты'),
        ('paid', 'Оплачено'),
        ('completed', 'Визит завершен'),
        ('cancelled', 'Отменено'),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('card', 'Банковская карта'),
        ('sbp', 'СБП'),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, verbose_name="Клиент")
    slot = models.OneToOneField(TimeSlot, on_delete=models.PROTECT, verbose_name="Выбранное время и мастер")
    service = models.ForeignKey(Service, on_delete=models.PROTECT, verbose_name="Услуга")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Статус записи")
    tips_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Чаевые мастера (руб.)")
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата и время онлайн-оплаты")
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, blank=True, null=True, verbose_name="Способ оплаты")
    payment_id = models.CharField(max_length=40, blank=True, null=True, verbose_name="Номер транзакции (имитация)")
    tips_token = models.CharField(max_length=40, blank=True, null=True, unique=True, verbose_name="Токен ссылки на чаевые")
    tips_paid_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата и время оплаты чаевых")
    tips_payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, blank=True, null=True, verbose_name="Способ оплаты чаевых")
    tips_payment_id = models.CharField(max_length=40, blank=True, null=True, verbose_name="Номер транзакции чаевых (имитация)")
    promo_code = models.ForeignKey(PromoCode, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Промокод")
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Скидка по промокоду (руб.)")
    final_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Итоговая цена (руб.)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания записи")

    def __str__(self):
        return f"Запись {self.id}: {self.client} к {self.slot.master} на {self.slot.date}"

    class Meta:
        verbose_name = "Запись на процедуру"
        verbose_name_plural = "Записи на процедуры"


class Review(models.Model):
    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, verbose_name="Клиент")
    master = models.ForeignKey(Master, on_delete=models.CASCADE, verbose_name="Мастер")
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, verbose_name="Запись")
    rating = models.PositiveIntegerField(choices=RATING_CHOICES, verbose_name="Оценка (1–5)")
    text = models.TextField(verbose_name="Текст отзыва")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата отзыва")

    def __str__(self):
        return f"Отзыв #{self.appointment_id} на {self.master_id}: {self.rating}/5"

    class Meta:
        verbose_name = "Отзыв"
        verbose_name_plural = "Отзывы"
        constraints = [
            models.UniqueConstraint(
                fields=["appointment"],
                name="unique_review_per_appointment",
            )
        ]