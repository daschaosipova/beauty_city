from django.contrib import admin

from .models import Appointment, Client, Master, PromoCode, Review, Salon, Service, TimeSlot


@admin.register(Salon)
class SalonAdmin(admin.ModelAdmin):
    list_display = ("name", "address", "phone")
    search_fields = ("name", "address", "phone")


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "duration_minutes")
    search_fields = ("name",)


class TimeSlotInline(admin.TabularInline):
    model = TimeSlot
    extra = 1


@admin.register(Master)
class MasterAdmin(admin.ModelAdmin):
    list_display = ("full_name", "is_active", "display_salons")
    filter_horizontal = ("salons", "services")
    list_filter = ("is_active", "salons")
    search_fields = ("full_name",)
    inlines = (TimeSlotInline,)

    @admin.display(description="Салоны")
    def display_salons(self, obj):
        return ", ".join(s.name for s in obj.salons.all()[:5])


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("telegram_id", "username", "phone", "is_terms_accepted", "terms_accepted_at")
    list_filter = ("is_terms_accepted",)
    search_fields = ("telegram_id", "username", "phone")


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ("date", "time", "master", "salon", "is_booked")
    list_filter = ("is_booked", "salon", "date")
    search_fields = ("master__full_name",)
    date_hierarchy = "date"


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "discount_percent", "is_active", "valid_until", "created_at")
    list_filter = ("is_active", "valid_until")
    search_fields = ("code",)


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "client",
        "slot",
        "service",
        "status",
        "payment_method",
        "payment_id",
        "promo_code",
        "discount_amount",
        "final_price",
        "tips_amount",
        "tips_paid_at",
        "tips_payment_method",
        "tips_payment_id",
        "created_at",
    )
    list_filter = ("status", "payment_method", "created_at")
    search_fields = ("client__phone", "client__username", "slot__master__full_name", "promo_code__code")
    date_hierarchy = "created_at"


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "master", "rating", "appointment", "created_at")
    list_filter = ("rating", "created_at")
    search_fields = ("client__phone", "client__username", "master__full_name", "text")
    date_hierarchy = "created_at"
