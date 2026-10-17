from django.core.exceptions import ValidationError
from django.contrib import messages
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import redirect, render
from .services import SERVICES
import calendar as month_calendar
from datetime import date, datetime, time, timedelta
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, OperationalError, transaction
from django.db.models import Exists, OuterRef, Q, Prefetch
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST
from .forms import BookingForm, StaffBookingForm, SlotForm, DirectBookingForm
from .models import AppointmentSlot, Booking
from django.utils.http import url_has_allowed_host_and_scheme
from urllib.parse import urlencode


def calendar(request):
    today = timezone.localdate()
    try:
        month = date.fromisoformat(request.GET.get('month', today.replace(day=1).isoformat())).replace(day=1)
        if not 2000 <= month.year <= 2100:
            raise ValueError
    except ValueError:
        month = today.replace(day=1)
    previous = date(month.year - 1, 12, 1) if month.month == 1 else date(month.year, month.month - 1, 1)
    following = date(month.year + 1, 1, 1) if month.month == 12 else date(month.year, month.month + 1, 1)
    active = Booking.objects.filter(slot=OuterRef('pk'), status=Booking.Status.CONFIRMED)
    first = timezone.make_aware(datetime.combine(month, time.min))
    last = timezone.make_aware(datetime.combine(following, time.min))
    query = AppointmentSlot.objects.filter(start__lt=last, end__gt=first).annotate(taken=Exists(active)).filter(Q(taken=True) | Q(available=True, start__gte=max(first, timezone.now())))
    staff = request.user.is_staff and request.user.has_perm('dshine_app.view_booking')
    if staff:
        query = query.prefetch_related(Prefetch('booking_set', queryset=Booking.objects.filter(status='confirmed'), to_attr='calendar_bookings'))
    slots = list(query)
    by_day = {}
    for slot in slots:
        local_start, local_end = timezone.localtime(slot.start), timezone.localtime(slot.end)
        if not slot.taken:
            by_day.setdefault(local_start.date(), []).append({'slot': slot})
            continue
        day = max(local_start.date(), month)
        while day < following:
            day_start = timezone.make_aware(datetime.combine(day, time.min))
            next_day = day + timedelta(days=1)
            day_end = timezone.make_aware(datetime.combine(next_day, time.min))
            if day_start >= slot.end:
                break
            segment_start, segment_end = max(local_start, day_start), min(local_end, day_end)
            end_label = '24:00' if segment_end == day_end else segment_end.strftime('%H:%M')
            label = f'{segment_start:%H:%M} – {end_label}'
            by_day.setdefault(day, []).append({'slot': slot, 'time_label': label, 'description': 'Zarezerwowany · cały dzień' if segment_start == day_start and segment_end == day_end else 'Zarezerwowany'})
            day = next_day
    weeks = []
    for week in month_calendar.Calendar(firstweekday=0).monthdatescalendar(month.year, month.month):
        weeks.append([{'date': day, 'in_month': day.month == month.month, 'slots': by_day.get(day, []) if day.month == month.month else [], 'has_bookings': any(entry['slot'].taken for entry in by_day.get(day, []))} for day in week])
    return render(request, 'dshine/calendar.html', {'weeks': weeks, 'month': month, 'previous': previous, 'following': following, 'has_slots': any(not slot.taken for slot in slots), 'calendar_staff': staff})


@login_required
def book(request, slot_id):
    slot = get_object_or_404(AppointmentSlot, pk=slot_id)
    staff_booking = request.user.is_staff and request.user.has_perm('dshine_app.add_booking')
    form_class = StaffBookingForm if staff_booking else BookingForm
    form = form_class(request.POST if request.method == 'POST' else None, initial={'name': '' if staff_booking else request.user.get_full_name()})
    unavailable = not slot.available or slot.start <= timezone.now() or Booking.objects.filter(slot=slot, status='confirmed').exists()
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                locked = AppointmentSlot.objects.select_for_update().get(pk=slot.pk)
                if not locked.available or locked.start <= timezone.now() or Booking.objects.filter(slot=locked, status='confirmed').exists():
                    raise IntegrityError('Termin jest już niedostępny.')
                booking = form.save(commit=False)
                booking.user = (form.cleaned_data.get('user') or request.user) if staff_booking else request.user
                booking.slot = locked
                booking.save()
            messages.success(request, 'Wizyta została zarezerwowana. Szczegóły znajdziesz poniżej.')
            return redirect('staff_bookings' if staff_booking else 'bookings')
        except IntegrityError:
            unavailable = True
            form.add_error(None, 'Ten termin jest już niedostępny. Wybierz inny w kalendarzu.')
        except OperationalError as error:
            if 'locked' not in str(error).lower():
                raise
            form.add_error(None, 'Ktoś właśnie rezerwuje termin. Spróbuj ponownie za chwilę.')
    return render(request, 'dshine/book.html', {'slot': slot, 'form': form, 'unavailable': unavailable})


@login_required
def bookings(request):
    return render(request, 'dshine/bookings.html', {'bookings': Booking.objects.filter(user=request.user).select_related('slot'), 'now': timezone.now()})


@login_required
@require_POST
def cancel_booking(request, booking_id):
    staff = request.user.is_staff and request.user.has_perm('dshine_app.change_booking')
    query = Booking.objects.all() if staff else Booking.objects.filter(user=request.user)
    booking = get_object_or_404(query, pk=booking_id)
    if booking.slot.start > timezone.now():
        Booking.objects.filter(pk=booking.pk, status='confirmed').update(status='cancelled')
        messages.success(request, 'Rezerwacja została anulowana.')
    else:
        messages.error(request, 'Termin już się rozpoczął. W sprawie zmian skontaktuj się z nami telefonicznie.')
    return redirect('staff_bookings' if staff else 'bookings')


@login_required
def staff_bookings(request):
    from django.core.exceptions import PermissionDenied
    if not request.user.is_staff or not request.user.has_perm('dshine_app.view_booking'):
        raise PermissionDenied
    direct = request.method == 'POST' and request.POST.get('action') == 'reserve'
    form = SlotForm(request.POST if request.method == 'POST' and not direct else None)
    booking_form = DirectBookingForm(request.POST if direct else None)
    if request.method == 'POST':
        if not request.user.has_perm('dshine_app.add_appointmentslot') or (direct and not request.user.has_perm('dshine_app.add_booking')):
            raise PermissionDenied
        if direct and booking_form.is_valid():
            try:
                with transaction.atomic():
                    start, end = booking_form.cleaned_data['start'], booking_form.cleaned_data['end']
                    slot = AppointmentSlot.objects.select_for_update().filter(start=start, end=end).first()
                    if slot is None:
                        slot = AppointmentSlot(start=start, end=end)
                        slot.full_clean()
                        slot.save()
                    if not slot.available or Booking.objects.filter(slot=slot, status='confirmed').exists():
                        raise IntegrityError('Termin zajęty.')
                    booking = booking_form.save(commit=False)
                    booking.user = booking_form.cleaned_data.get('user') or request.user
                    booking.slot = slot
                    booking.full_clean()
                    booking.save()
                messages.success(request, 'Rezerwacja klienta została dodana.')
                return redirect('staff_bookings')
            except (IntegrityError, OperationalError):
                booking_form.add_error(None, 'Termin został zajęty lub trwa inny zapis. Spróbuj ponownie.')
            except ValidationError as error:
                booking_form.add_error(None, error)
        elif not direct and form.is_valid():
            form.save()
            messages.success(request, 'Termin został dodany do kalendarza.')
            return redirect('staff_bookings')
    return render(request, 'dshine/staff_bookings.html', {'form': form, 'booking_form': booking_form, 'bookings': Booking.objects.select_related('user', 'slot').order_by('-slot__start'), 'now': timezone.now()})


def home(request):
    return render(request, 'dshine/home.html', {'services': SERVICES})


def rejestracja(request):
    if request.user.is_authenticated:
        return redirect('home')
    form = UserCreationForm(request.POST or None)
    next_url = request.POST.get('next', request.GET.get('next', ''))
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        next_url = ''
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Konto zostało utworzone. Możesz się zalogować.')
        if next_url:
            from django.urls import reverse
            return redirect(reverse('login') + '?' + urlencode({'next': next_url}))
        return redirect('login')
    return render(request, 'registration/register.html', {'form': form, 'next': next_url})
