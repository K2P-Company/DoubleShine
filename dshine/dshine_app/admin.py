from django.contrib import admin
from .models import AppointmentSlot, Booking

admin.site.site_header = 'Double Shine — zarządzanie'
admin.site.site_title = 'Panel Double Shine'
admin.site.index_title = 'Terminy, rezerwacje i konta'


@admin.register(AppointmentSlot)
class SlotAdmin(admin.ModelAdmin):
    list_display = ['start', 'end', 'available']
    list_filter = ['available', 'start']
    date_hierarchy = 'start'
    list_per_page = 25
    list_editable = ['available']


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['name', 'slot', 'service', 'phone', 'car', 'status']
    list_filter = ['status', 'service', 'slot__start']
    search_fields = ['name', 'phone', 'car', 'user__username']
    readonly_fields = ['created']
    list_per_page = 25
    date_hierarchy = 'slot__start'

    def get_readonly_fields(self, request, obj=None):
        return ['created', 'user', 'slot'] if obj else ['created']

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'slot':
            from django.utils import timezone
            kwargs['queryset'] = AppointmentSlot.objects.filter(available=True, start__gt=timezone.now()).exclude(booking__status='confirmed')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def has_delete_permission(self, request, obj=None):
        return False
