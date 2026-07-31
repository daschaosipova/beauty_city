from django.contrib import admin
from .models import Salon, Service, Master, Client, TimeSlot, Appointment, PromoCode

# Регистрируем каждую таблицу, чтобы она появилась в админке
admin.site.register(Salon)
admin.site.register(Service)
admin.site.register(Master)
admin.site.register(Client)
admin.site.register(TimeSlot)
admin.site.register(Appointment)


# Регистрируем промокоды с расширенными настройками
@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_type', 'discount_value', 'is_active', 'valid_from', 'valid_to', 'used_count')
    list_filter = ('is_active', 'discount_type', 'valid_from', 'valid_to')
    search_fields = ('code', 'description')
    filter_horizontal = ('services',)

    fieldsets = (
        ('Основная информация', {
            'fields': ('code', 'description', 'discount_type', 'discount_value')
        }),
        ('Период действия', {
            'fields': ('valid_from', 'valid_to', 'is_active')
        }),
        ('Ограничения', {
            'fields': ('usage_limit', 'used_count', 'services')
        }),
    )
