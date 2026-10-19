import re
from django import forms
from .models import Booking
from .models import AppointmentSlot
from django.contrib.auth import get_user_model


class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['service', 'name', 'phone', 'car', 'notes']
        widgets = {'notes': forms.Textarea(attrs={'rows': 3}), 'phone': forms.TextInput(attrs={'type': 'tel', 'autocomplete': 'tel'}), 'name': forms.TextInput(attrs={'autocomplete': 'name'})}

    def clean_phone(self):
        phone = self.cleaned_data['phone'].strip()
        if not re.fullmatch(r'\+?[\d\s()-]+', phone) or not 9 <= len(re.sub(r'\D', '', phone)) <= 15:
            raise forms.ValidationError('Podaj poprawny numer telefonu (9–15 cyfr).')
        return phone


class StaffBookingForm(BookingForm):
    user = forms.ModelChoiceField(queryset=get_user_model().objects.filter(is_active=True), required=False, label='Konto klienta (opcjonalnie)', help_text='Bez konta klienta rezerwacja zostanie przypisana do Twojego konta administratora.')

    class Meta(BookingForm.Meta):
        fields = ['user', 'service', 'name', 'phone', 'car', 'notes']


class SlotForm(forms.ModelForm):
    start = forms.DateField(label='Od dnia', widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))
    end = forms.DateField(label='Do dnia (włącznie)', widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}), help_text='Dla jednego dnia wybierz tę samą datę w obu polach.')

    class Meta:
        model = AppointmentSlot
        fields = ['start', 'end', 'available']

    def __init__(self, *args, **kwargs):
        from datetime import timedelta
        from django.utils import timezone
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.initial['start'] = timezone.localtime(self.instance.start).date()
            self.initial['end'] = timezone.localtime(self.instance.end - timedelta(microseconds=1)).date()

    def clean_start(self):
        from datetime import datetime, time
        from django.utils import timezone
        day = self.cleaned_data['start']
        if not self.instance.pk and day < timezone.localdate():
            raise forms.ValidationError('Wybierz dzisiejszą lub przyszłą datę.')
        return timezone.make_aware(datetime.combine(day, time.min))

    def clean_end(self):
        from datetime import datetime, time, timedelta
        from django.utils import timezone
        try:
            day_after = self.cleaned_data['end'] + timedelta(days=1)
        except OverflowError:
            raise forms.ValidationError('Wybierz wcześniejszą datę.')
        return timezone.make_aware(datetime.combine(day_after, time.min))

    def save(self, commit=True):
        slot = super().save(commit=False)
        slot.is_day_off = True
        if commit:
            slot.save()
        return slot


class DirectBookingForm(StaffBookingForm):
    start = forms.DateTimeField(label='Początek wizyty', widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}))
    end = forms.DateTimeField(label='Koniec wizyty', widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}))

    def clean(self):
        from django.utils import timezone
        from django.core.exceptions import ValidationError
        data = super().clean()
        start, end = data.get('start'), data.get('end')
        if start and end:
            if start <= timezone.now():
                self.add_error('start', 'Wybierz datę w przyszłości.')
            if end <= start:
                self.add_error('end', 'Koniec musi być późniejszy niż początek.')
            else:
                slot = AppointmentSlot.objects.filter(start=start, end=end).first()
                if slot:
                    if slot.is_day_off or not slot.available or Booking.objects.filter(slot=slot, status='confirmed').exists():
                        raise forms.ValidationError('Ten termin jest niedostępny lub już zarezerwowany.')
                else:
                    try:
                        AppointmentSlot(start=start, end=end).full_clean()
                    except ValidationError as error:
                        raise forms.ValidationError(error.messages)
        return data
