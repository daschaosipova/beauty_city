import datetime
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from bot_manager.models import Appointment, Client, Master, PromoCode, Salon, Service, TimeSlot


class Command(BaseCommand):
    help = "Заполняет базу тестовыми данными для всех сценариев бота"

    def handle(self, *args, **options):
        self.stdout.write("Начало заполнения базы данных...")

        salons_data = [
            {"name": "Ольга Beauty — Сити", "address": "г. Москва, Пресненская наб., д. 12, Башня 'Федерация'", "phone": "+7 (495) 111-22-33"},
            {"name": "Ольга Beauty — Патриаршие", "address": "г. Москва, Малый Козихинский пер., д. 8/18", "phone": "+7 (495) 222-33-44"},
            {"name": "Ольга Beauty — Таганка", "address": "г. Москва, ул. Земляной Вал, д. 52/16, стр. 1", "phone": "+7 (495) 333-44-55"},
        ]

        salons = []
        for data in salons_data:
            salon, _ = Salon.objects.get_or_create(name=data["name"], defaults=data)
            salons.append(salon)
        salon_city, salon_patriarchy, salon_taganka = salons

        services_data = [
            {"name": "Женская стрижка + укладка", "price": Decimal("3500.00"), "duration_minutes": 60},
            {"name": "Сложное окрашивание волос", "price": Decimal("12000.00"), "duration_minutes": 240},
            {"name": "Мужская стрижка + борода", "price": Decimal("2500.00"), "duration_minutes": 45},
            {"name": "Маникюр с покрытием гель-лак", "price": Decimal("2800.00"), "duration_minutes": 90},
            {"name": "Архитектура и окрашивание бровей", "price": Decimal("1800.00"), "duration_minutes": 45},
        ]

        services = {}
        for data in services_data:
            service, _ = Service.objects.get_or_create(name=data["name"], defaults=data)
            services[data["name"]] = service

        masters_data = [
            {
                "full_name": "Александрова Елена Игоревна",
                "salons": [salon_city, salon_patriarchy],
                "services": [services["Женская стрижка + укладка"], services["Сложное окрашивание волос"]]
            },
            {
                "full_name": "Ахмедов Тимур Русланович",
                "salons": [salon_city, salon_taganka],
                "services": [services["Мужская стрижка + борода"]]
            },
            {
                "full_name": "Кривошеева Ольга Сергеевна",
                "salons": [salon_patriarchy, salon_taganka],
                "services": [services["Маникюр с покрытием гель-лак"], services["Архитектура и окрашивание бровей"]]
            }
        ]

        for data in masters_data:
            master, _ = Master.objects.get_or_create(full_name=data["full_name"], defaults={"is_active": True})
            master.salons.set(data["salons"])
            master.services.set(data["services"])

        # Извлекаем мастеров из базы для генерации расписания
        master_elena = Master.objects.get(full_name="Александрова Елена Игоревна")
        master_timur = Master.objects.get(full_name="Ахмедов Тимур Русланович")
        master_olga = Master.objects.get(full_name="Кривошеева Ольга Сергеевна")

        # Один старый клиент (для теста сценария 100 дней) и один новый
        client_old, _ = Client.objects.get_or_create(
            telegram_id=111111111,
            defaults={
                "username": "old_customer",
                "phone": "+7 (999) 777-77-77",
                "is_terms_accepted": True,
                "terms_accepted_at": timezone.now() - datetime.timedelta(days=101)
            }
        )

        client_new, _ = Client.objects.get_or_create(
            telegram_id=222222222,
            defaults={
                "username": "new_guest",
                "phone": "+7 (999) 888-88-88",
                "is_terms_accepted": True,
                "terms_accepted_at": timezone.now()
            }
        )

        today = datetime.date.today()
        days_ahead = 4
        dates = [today + datetime.timedelta(days=i) for i in range(days_ahead + 1)]

        schedule = [
            {
                "master": master_elena,
                "salons": [salon_city, salon_patriarchy],
                "times": [
                    datetime.time(10, 0),
                    datetime.time(12, 0),
                    datetime.time(15, 0),
                ],
            },
            {
                "master": master_timur,
                "salons": [salon_city, salon_taganka],
                "times": [
                    datetime.time(11, 0),
                    datetime.time(12, 0),
                    datetime.time(14, 0),
                    datetime.time(16, 0),
                ],
            },
            {
                "master": master_olga,
                "salons": [salon_patriarchy, salon_taganka],
                "times": [
                    datetime.time(10, 0),
                    datetime.time(12, 0),
                    datetime.time(14, 0),
                    datetime.time(16, 0),
                ],
            },
        ]

        created_slots = []
        for day in dates:
            for sched in schedule:
                salon = sched["salons"][day.weekday() % 2]
                for tm in sched["times"]:
                    slot, _ = TimeSlot.objects.get_or_create(
                        master=sched["master"],
                        date=day,
                        time=tm,
                        defaults={"salon": salon, "is_booked": False},
                    )
                    created_slots.append(slot)

        # Бронируем первый слот под активную запись (Елена сегодня в 10:00)
        created_slots[0].is_booked = True
        created_slots[0].save(update_fields=["is_booked"])

        PromoCode.objects.get_or_create(
            code="SALON10",
            defaults={
                "discount_percent": 10,
                "is_active": True,
                "valid_until": today + datetime.timedelta(days=30),
            },
        )
        PromoCode.objects.get_or_create(
            code="WELCOME500",
            defaults={
                "discount_percent": 15,
                "is_active": True,
                "valid_until": today + datetime.timedelta(days=60),
            },
        )

        # Завершённый визит 100 дней назад — для теста сценария повторного приёма
        past_date = today - datetime.timedelta(days=100)
        past_slot, _ = TimeSlot.objects.get_or_create(
            master=master_elena,
            salon=salon_city,
            date=past_date,
            time=datetime.time(10, 0),
            defaults={"is_booked": True}
        )

        past_appointment, created = Appointment.objects.get_or_create(
            slot=past_slot,
            defaults={
                "client": client_old,
                "service": services["Женская стрижка + укладка"],
                "status": "completed",
                "tips_amount": Decimal("500.00")
            }
        )
        if created:
            # Искусственно сдвигаем дату создания записи назад для реалистичности логов
            past_appointment.created_at = timezone.now() - datetime.timedelta(days=100)
            past_appointment.save()

        # Активная запись на сегодня — первый слот Елены, забронированный выше
        Appointment.objects.get_or_create(
            slot=created_slots[0],
            defaults={
                "client": client_new,
                "service": services["Женская стрижка + укладка"],
                "status": "paid",
                "tips_amount": Decimal("0.00")
            }
        )

        self.stdout.write(self.style.SUCCESS("База данных успешно заполнена тестовыми данными для всех сценариев Ольги!"))