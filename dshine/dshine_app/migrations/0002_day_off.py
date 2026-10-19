from django.db import migrations, models

def classify_existing(apps, schema_editor):
    Slot = apps.get_model('dshine_app', 'AppointmentSlot')
    Booking = apps.get_model('dshine_app', 'Booking')
    booked_ids = Booking.objects.filter(status='confirmed').values_list('slot_id', flat=True)
    Slot.objects.filter(available=True).exclude(pk__in=booked_ids).update(is_day_off=True)

class Migration(migrations.Migration):
    dependencies = [('dshine_app', '0001_initial')]
    operations = [
        migrations.AddField(model_name='appointmentslot', name='is_day_off', field=models.BooleanField(default=False, verbose_name='Dzień wolny od pracy')),
        migrations.AlterField(model_name='appointmentslot', name='available', field=models.BooleanField(default=True, verbose_name='Aktywny wpis w kalendarzu')),
        migrations.RunPython(classify_existing, migrations.RunPython.noop),
    ]
