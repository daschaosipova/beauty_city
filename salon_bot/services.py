from datetime import date as date_cls

import re

from asgiref.sync import sync_to_async
from django.db import transaction
from django.utils import timezone

from bot_manager.models import Appointment, Client, Master, Salon, Service, TimeSlot


class SlotAlreadyBookedError(Exception):
    pass


async def get_salons():
    return await sync_to_async(lambda: list(Salon.objects.order_by("name")))()


async def get_salon(pk):
    return await sync_to_async(Salon.objects.get)(pk=pk)


async def get_services():
    return await sync_to_async(lambda: list(Service.objects.order_by("name")))()


async def get_service(pk):
    return await sync_to_async(Service.objects.get)(pk=pk)


async def get_active_masters():
    return await sync_to_async(
        lambda: list(Master.objects.filter(is_active=True).order_by("full_name"))
    )()


async def get_master_services(master_id):
    def _impl():
        return list(Master.objects.get(pk=master_id).services.order_by("name"))

    return await sync_to_async(_impl)()


async def get_master_salons(master_id):
    def _impl():
        return list(Master.objects.get(pk=master_id).salons.order_by("name"))

    return await sync_to_async(_impl)()


async def get_fm_dates(master_id, salon_id):
    def _impl():
        return list(
            TimeSlot.objects.filter(
                is_booked=False,
                master_id=master_id,
                salon_id=salon_id,
                date__gte=date_cls.today(),
            )
            .order_by("date")
            .values_list("date", flat=True)
            .distinct()
        )

    return await sync_to_async(_impl)()


async def get_fm_slots(master_id, salon_id, slot_date):
    def _impl():
        return list(
            TimeSlot.objects.filter(
                is_booked=False,
                master_id=master_id,
                salon_id=salon_id,
                date=slot_date,
            )
            .select_related("master", "salon")
            .order_by("time")
        )

    return await sync_to_async(_impl)()


def _proc_slots(service_id):
    return TimeSlot.objects.filter(
        is_booked=False,
        date__gte=date_cls.today(),
        master__is_active=True,
        master__services__id=service_id,
    )


async def get_procedure_dates(service_id):
    def _impl():
        return list(
            _proc_slots(service_id)
            .order_by("date")
            .values_list("date", flat=True)
            .distinct()
        )

    return await sync_to_async(_impl)()


async def get_procedure_times(service_id, slot_date):
    def _impl():
        return list(
            _proc_slots(service_id)
            .filter(date=slot_date)
            .order_by("time")
            .values_list("time", flat=True)
            .distinct()
        )

    return await sync_to_async(_impl)()


async def get_time_masters(service_id, slot_date, slot_time):
    def _impl():
        master_ids = (
            _proc_slots(service_id)
            .filter(date=slot_date, time=slot_time)
            .values_list("master_id", flat=True)
            .distinct()
        )
        return list(Master.objects.filter(pk__in=master_ids).order_by("full_name"))

    return await sync_to_async(_impl)()


async def get_procedure_salons(service_id, master_id, slot_date, slot_time):
    def _impl():
        salon_ids = (
            _proc_slots(service_id)
            .filter(master_id=master_id, date=slot_date, time=slot_time)
            .values_list("salon_id", flat=True)
            .distinct()
        )
        return list(Salon.objects.filter(pk__in=salon_ids).order_by("name"))

    return await sync_to_async(_impl)()


async def resolve_slot(service_id, master_id, salon_id, slot_date, slot_time):
    def _impl():
        return (
            _proc_slots(service_id)
            .filter(
                master_id=master_id,
                salon_id=salon_id,
                date=slot_date,
                time=slot_time,
            )
            .select_related("master", "salon")
            .first()
        )

    return await sync_to_async(_impl)()


async def get_masters(salon_id, service_id):
    def _impl():
        return list(
            Master.objects.filter(
                is_active=True,
                salons__id=salon_id,
                services__id=service_id,
            )
            .distinct()
            .order_by("full_name")
        )

    return await sync_to_async(_impl)()


async def get_available_dates(master_id, salon_id, service_id):
    def _impl():
        qs = TimeSlot.objects.filter(
            is_booked=False,
            salon_id=salon_id,
            date__gte=date_cls.today(),
        )
        if master_id:
            qs = qs.filter(master_id=master_id)
        else:
            qs = qs.filter(master__is_active=True, master__services__id=service_id)
        return list(qs.order_by("date").values_list("date", flat=True).distinct())

    return await sync_to_async(_impl)()


async def get_free_slots(master_id, salon_id, service_id, slot_date):
    def _impl():
        qs = TimeSlot.objects.filter(
            is_booked=False,
            salon_id=salon_id,
            date=slot_date,
        )
        if master_id:
            qs = qs.filter(master_id=master_id)
        else:
            qs = qs.filter(master__is_active=True, master__services__id=service_id)
        return list(qs.select_related("master", "salon").order_by("time"))

    return await sync_to_async(_impl)()


async def get_slot(pk):
    return await sync_to_async(
        lambda: TimeSlot.objects.select_related("master", "salon").get(pk=pk)
    )()


async def has_terms_consent(telegram_id):
    def _impl():
        return Client.objects.filter(
            telegram_id=telegram_id, is_terms_accepted=True
        ).exists()

    return await sync_to_async(_impl)()


async def save_client(telegram_id, username, phone):
    def _impl():
        client, _ = Client.objects.get_or_create(
            telegram_id=telegram_id,
            defaults={"username": username, "phone": phone},
        )
        client.phone = phone
        if username is not None:
            client.username = username
        client.is_terms_accepted = True
        client.terms_accepted_at = timezone.now()
        client.save(
            update_fields=["phone", "username", "is_terms_accepted", "terms_accepted_at"]
        )
        return client

    return await sync_to_async(_impl)()


async def create_appointment(client_id, slot_id, service_id):
    @sync_to_async
    def _impl():
        with transaction.atomic():
            slot = TimeSlot.objects.select_for_update().get(pk=slot_id)
            if slot.is_booked:
                raise SlotAlreadyBookedError()
            slot.is_booked = True
            slot.save(update_fields=["is_booked"])
            return Appointment.objects.create(
                client_id=client_id,
                slot=slot,
                service_id=service_id,
            )

    return await _impl()


def _normalize_phone(phone):
    return re.sub(r"\D", "", phone)


def _phone_telegram_id(phone):
    return -int(_normalize_phone(phone))


async def get_or_create_client_by_phone(phone):
    """Находит или создаёт клиента по номеру телефона (запись по звонку)."""

    def _impl():
        telegram_id = _phone_telegram_id(phone)
        client, _ = Client.objects.get_or_create(
            telegram_id=telegram_id,
            defaults={"phone": phone},
        )
        client.phone = phone
        client.save(update_fields=["phone"])
        return client

    return await sync_to_async(_impl)()
