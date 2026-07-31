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
    payment_status  = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Статус платежа")
    tips_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Чаевые мастера (руб.)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания записи")

    # Блок отзывов
    feedback = models.TextField(blank=True, null=True, verbose_name="Текст отзыва")
    feedback_asked = models.BooleanField(default=False, verbose_name="Уже спрашивали отзыв?")

    # Блок промокодов
    promo_code_used = models.CharField(max_length=50, blank=True, null=True, verbose_name="Примененный промокод")
    discount_applied = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Скидка (руб.)")

    def __str__(self):
        return f"Запись {self.id}: {self.client} к {self.slot.master} на {self.slot.date}"

    class Meta:
        verbose_name = "Запись на процедуру"
        verbose_name_plural = "Записи на процедуры"



# 7. ТАБЛИЦА ПРОМОКОДОВ
class PromoCode(models.Model):
    DISCOUNT_TYPE_CHOICES = [
        ('percent', 'Процентная скидка'),
        ('fixed', 'Фиксированная скидка (руб.)'),
    ]

    code = models.CharField(max_length=50, unique=True, verbose_name="Код промокода")
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES, default='percent',
                                     verbose_name="Тип скидки")
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Значение скидки")
    description = models.CharField(max_length=255, blank=True, null=True, verbose_name="Описание")
    valid_from = models.DateTimeField(verbose_name="Действует с")
    valid_to = models.DateTimeField(verbose_name="Действует до")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    usage_limit = models.IntegerField(default=0, verbose_name="Лимит использований (0 - безлимит)")
    used_count = models.IntegerField(default=0, verbose_name="Сколько раз использован")

    # Привязка к конкретным услугам (опционально)
    services = models.ManyToManyField('Service', blank=True,
                                      verbose_name="Применяется к услугам (если пусто - ко всем)")

    def __str__(self):
        return f"{self.code} ({self.discount_value}{'%' if self.discount_type == 'percent' else ' руб.'})"

    def is_valid(self):
        from django.utils import timezone
        now = timezone.now()
        if not self.is_active:
            return False
        if self.valid_from and self.valid_from > now:
            return False
        if self.valid_to and self.valid_to < now:
            return False
        if self.usage_limit > 0 and self.used_count >= self.usage_limit:
            return False
        return True

    # Применяет скидку к цене
    def apply_discount(self, price):
        if self.discount_type == 'percent':
            # Преобразуем Decimal в float для вычислений
            discount_value = float(self.discount_value)
            discount_amount = price * (discount_value / 100)
            return price - discount_amount
        else:  # fixed
            # Преобразуем Decimal в float
            discount_value = float(self.discount_value)
            return max(0, price - discount_value)
