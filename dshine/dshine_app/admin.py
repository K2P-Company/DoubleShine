from django.contrib import admin
from .models import AppointmentSlot, Booking


@admin.register(AppointmentSlot)
class SlotAdmin(admin.ModelAdmin):
    list_display = ['start', 'end', 'available']
    list_filter = ['available', 'start']
    date_hierarchy = 'start'


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['name', 'slot', 'service', 'phone', 'car', 'status']
    list_filter = ['status', 'service', 'slot__start']
    search_fields = ['name', 'phone', 'car', 'user__username']
    readonly_fields = ['created']

    def get_readonly_fields(self, request, obj=None):
        return ['created', 'user', 'slot'] if obj else ['created']

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'slot':
            from django.utils import timezone
            kwargs['queryset'] = AppointmentSlot.objects.filter(available=True, start__gt=timezone.now()).exclude(booking__status='confirmed')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def has_delete_permission(self, request, obj=None):
        return False
