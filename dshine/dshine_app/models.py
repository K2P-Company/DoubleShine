from django.db import models, transaction
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone


class AppointmentSlot(models.Model):
    start = models.DateTimeField('Początek')
    end = models.DateTimeField('Koniec')
    available = models.BooleanField('Udostępniony klientom', default=True)

    class Meta:
        ordering = ['start']
        verbose_name = 'termin'
        verbose_name_plural = 'terminy'
        constraints = [models.CheckConstraint(condition=models.Q(end__gt=models.F('start')), name='slot_end_after_start')]

    def clean(self):
        if self.start and self.end:
            if self.end <= self.start:
                raise ValidationError('Koniec musi być późniejszy niż początek.')
            if AppointmentSlot.objects.exclude(pk=self.pk).filter(start__lt=self.end, end__gt=self.start).exists():
                raise ValidationError('Termin nakłada się na inny termin. W tej wersji obsługujemy jedno auto jednocześnie.')
            if self.pk and Booking.objects.filter(slot=self, status='confirmed').exists():
                old = AppointmentSlot.objects.get(pk=self.pk)
                if old.start != self.start or old.end != self.end:
                    raise ValidationError('Nie zmieniaj godzin zarezerwowanego terminu. Najpierw anuluj rezerwację i uzgodnij zmianę z klientem.')

    def __str__(self):
        return timezone.localtime(self.start).strftime('%d.%m.%Y %H:%M')


class Booking(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = 'confirmed', 'Potwierdzona'
        CANCELLED = 'cancelled', 'Anulowana'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name='Klient')
    slot = models.ForeignKey(AppointmentSlot, on_delete=models.PROTECT, verbose_name='Termin')
    service = models.CharField('Usługa', max_length=32, choices=[('exterior', 'Pielęgnacja nadwozia'), ('interior', 'Pielęgnacja wnętrza'), ('individual', 'Indywidualny zakres')])
    name = models.CharField('Imię i nazwisko', max_length=120)
    phone = models.CharField('Telefon', max_length=24)
    car = models.CharField('Marka i model auta', max_length=120)
    notes = models.TextField('Uwagi', max_length=1000, blank=True)
    status = models.CharField('Status', max_length=16, choices=Status.choices, default=Status.CONFIRMED)
    created = models.DateTimeField('Utworzono', auto_now_add=True)

    class Meta:
        ordering = ['slot__start']
        verbose_name = 'rezerwacja'
        verbose_name_plural = 'rezerwacje'
        constraints = [models.UniqueConstraint(fields=['slot'], condition=models.Q(status='confirmed'), name='one_confirmed_booking_per_slot')]

    def __str__(self):
        return f'{self.name} — {self.slot}'

    def clean(self):
        if self.slot_id and self.status == self.Status.CONFIRMED:
            if not self.slot.available or self.slot.start <= timezone.now():
                raise ValidationError('Nie można rezerwować wyłączonego lub przeszłego terminu.')
            if Booking.objects.filter(slot_id=self.slot_id, status='confirmed').exclude(pk=self.pk).exists():
                raise ValidationError('Ten termin ma już potwierdzoną rezerwację.')


    def save(self, *args, **kwargs):
        if self.pk and self.status == self.Status.CANCELLED:
            # Ten sam skutek w panelu Django i na stronie klienta.
            with transaction.atomic():
                AppointmentSlot.objects.select_for_update().get(pk=self.slot_id)
                previous = type(self).objects.filter(pk=self.pk).values_list('status', flat=True).first()
                result = super().save(*args, **kwargs)
                if previous == self.Status.CONFIRMED and not type(self).objects.filter(slot_id=self.slot_id, status=self.Status.CONFIRMED).exists():
                    AppointmentSlot.objects.filter(pk=self.slot_id).update(available=False)
                return result
        return super().save(*args, **kwargs)
