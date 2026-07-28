from django.contrib import admin
from .models import Salon, Service, Master, Client, TimeSlot, Appointment

# Регистрируем каждую таблицу, чтобы она появилась в админке
admin.site.register(Salon)
admin.site.register(Service)
admin.site.register(Master)
admin.site.register(Client)
admin.site.register(TimeSlot)
admin.site.register(Appointment)
