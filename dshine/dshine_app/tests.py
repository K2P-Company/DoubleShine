from django.test import Client, TestCase, override_settings

from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from datetime import timedelta
from .models import AppointmentSlot, Booking
from datetime import datetime
import xml.etree.ElementTree as ET


class IndexingTests(TestCase):
    @override_settings(SITE_URL='https://example.com', SITE_INDEXING_ENABLED=True)
    def test_public_home_is_indexable_and_canonical_has_no_query(self):
        response = self.client.get('/', {'utm_source': 'test'})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('X-Robots-Tag', response)
        self.assertContains(response, '<meta name="robots" content="index, follow">', html=True)
        self.assertContains(response, '<link rel="canonical" href="https://example.com/">', html=True)

    @override_settings(SITE_URL='https://example.com', SITE_INDEXING_ENABLED=True)
    def test_sitemap_only_contains_public_canonical(self):
        response = self.client.get('/sitemap.xml')
        root = ET.fromstring(response.content)
        urls = [loc.text for loc in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]
        self.assertEqual(urls, ['https://example.com/'])
        robots = self.client.get('/robots.txt')
        self.assertContains(robots, 'Sitemap: https://example.com/sitemap.xml')
        self.assertNotContains(robots, 'Disallow: /')

    @override_settings(SITE_URL='https://example.com', SITE_INDEXING_ENABLED=True)
    def test_account_calendar_and_admin_not_indexed(self):
        for path in ['/login/', '/register/', '/terminy/', '/moje-rezerwacje/', '/zarzadzanie/', '/admin/', '/missing-page/']:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path)['X-Robots-Tag'], 'noindex, follow')

    @override_settings(SITE_URL='', SITE_INDEXING_ENABLED=False)
    def test_local_preview_not_indexed_and_no_fake_domain(self):
        response = self.client.get('/')
        self.assertEqual(response['X-Robots-Tag'], 'noindex, follow')
        self.assertNotContains(response, 'rel="canonical"')
        self.assertContains(self.client.get('/robots.txt'), 'Disallow: /')
        root = ET.fromstring(self.client.get('/sitemap.xml').content)
        self.assertEqual(len(root), 0)


class CalendarPeriodTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('period-client')

    def create_booking(self, start, end):
        slot = AppointmentSlot.objects.create(start=timezone.make_aware(datetime.fromisoformat(start)), end=timezone.make_aware(datetime.fromisoformat(end)))
        return Booking.objects.create(user=self.user, slot=slot, service='individual', name='Klient', phone='501987654', car='Auto')

    def days(self, month):
        response = self.client.get(reverse('calendar'), {'month': month})
        self.assertEqual(response.status_code, 200)
        return {day['date'].isoformat(): day for week in response.context['weeks'] for day in week if day['in_month']}

    def test_all_days_and_partial_start_end(self):
        self.create_booking('2027-01-15T10:00', '2027-01-18T10:00')
        days = self.days('2027-01-01')
        self.assertEqual([day for day, data in days.items() if data['has_bookings']], ['2027-01-15', '2027-01-16', '2027-01-17', '2027-01-18'])
        self.assertEqual(days['2027-01-15']['slots'][0]['time_label'], '10:00 – 24:00')
        self.assertEqual(days['2027-01-16']['slots'][0]['time_label'], '00:00 – 24:00')
        self.assertEqual(days['2027-01-18']['slots'][0]['time_label'], '00:00 – 10:00')

    def test_period_crossing_month(self):
        self.create_booking('2027-01-30T10:00', '2027-02-02T14:00')
        days = self.days('2027-02-01')
        self.assertTrue(days['2027-02-01']['has_bookings'])
        self.assertTrue(days['2027-02-02']['has_bookings'])
        self.assertFalse(days['2027-02-03']['has_bookings'])

    def test_midnight_end_does_not_block_next_day(self):
        self.create_booking('2027-01-15T10:00', '2027-01-17T00:00')
        days = self.days('2027-01-01')
        self.assertTrue(days['2027-01-16']['has_bookings'])
        self.assertFalse(days['2027-01-17']['has_bookings'])

    def test_cancelled_period_disappears(self):
        booking = self.create_booking('2027-01-30T10:00', '2027-02-02T14:00')
        booking.status = 'cancelled'
        booking.save()
        self.assertFalse(any(day['has_bookings'] for day in self.days('2027-02-01').values()))


class WebsiteTests(TestCase):
    def test_registration_preserves_only_safe_next(self):
        response = self.client.get(reverse('register'), {'next': '/terminy/1/rezerwuj/'})
        self.assertEqual(response.context['next'], '/terminy/1/rezerwuj/')
        response = self.client.get(reverse('register'), {'next': 'https://example.com/'})
        self.assertEqual(response.context['next'], '')

    def test_home(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'lang="pl"')
        self.assertContains(response, 'id="terminarz"')
        self.assertContains(response, 'tel:+48576562394')

    def test_invalid_registration(self):
        response = self.client.post(reverse('register'), {'username': 'visitor', 'password1': 'a', 'password2': 'b'})
        self.assertTrue(response.context['form'].errors)

    def test_register_login_logout_and_safe_redirect(self):
        data = {'username': 'visitor', 'password1': 'Detailing-example-482!', 'password2': 'Detailing-example-482!'}
        self.assertRedirects(self.client.post(reverse('register'), data), reverse('login'))
        response = self.client.post(reverse('login'), {'username': data['username'], 'password': data['password1'], 'next': 'https://example.com/'})
        self.assertRedirects(response, reverse('home'))
        self.assertRedirects(self.client.post(reverse('logout')), reverse('home'))


class BookingTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('client', password='Booking-password-482!')
        self.other = get_user_model().objects.create_user('other', password='Booking-password-482!')
        start = timezone.now() + timedelta(days=2)
        self.slot = AppointmentSlot.objects.create(start=start, end=start + timedelta(hours=3))
        self.data = {'service': 'exterior', 'name': 'Jan Testowy', 'phone': '576 562 394', 'car': 'Peugeot 207', 'notes': 'Test'}

    def reserve(self):
        self.client.force_login(self.user)
        return self.client.post(reverse('book', args=[self.slot.pk]), self.data)

    def test_login_required_and_calendar_public(self):
        self.assertEqual(self.client.get(reverse('calendar')).status_code, 200)
        self.assertRedirects(self.client.get(reverse('book', args=[self.slot.pk])), f"/login/?next=/terminy/{self.slot.pk}/rezerwuj/")
        self.assertEqual(self.client.post(reverse('book', args=[self.slot.pk]), self.data).status_code, 302)
        self.assertFalse(Booking.objects.exists())

    def test_booking_and_calendar_hides_occupied_slot(self):
        self.assertRedirects(self.reserve(), reverse('bookings'))
        booking = Booking.objects.get()
        self.assertEqual(booking.user, self.user)
        month = timezone.localtime(self.slot.start).date().replace(day=1).isoformat()
        response = self.client.get(reverse('calendar'), {'month': month})
        self.assertNotContains(response, reverse('book', args=[self.slot.pk]))
        self.assertContains(response, 'Zarezerwowany')
        self.assertNotContains(response, 'Jan Testowy')
        self.assertContains(self.client.get(reverse('bookings')), 'Peugeot 207')

    def test_occupied_calendar_details_only_for_administrator(self):
        self.data['phone'] = '501 987 654'
        self.reserve()
        month = timezone.localtime(self.slot.start).date().replace(day=1).isoformat()
        self.client.logout()
        public = self.client.get(reverse('calendar'), {'month': month})
        self.assertContains(public, 'slot-booked')
        self.assertNotContains(public, 'Jan Testowy')
        self.assertNotContains(public, 'Peugeot 207')
        self.assertNotContains(public, '501 987 654')
        admin = get_user_model().objects.create_superuser('calendar-owner', password='Owner-test-482!')
        self.client.force_login(admin)
        private = self.client.get(reverse('calendar'), {'month': month})
        self.assertContains(private, 'Jan Testowy')
        self.assertContains(private, 'Peugeot 207')
        self.assertContains(private, reverse('admin:dshine_app_booking_change', args=[Booking.objects.get().pk]))

    def test_cancelled_booking_is_free_again_in_calendar(self):
        self.reserve()
        Booking.objects.update(status='cancelled')
        month = timezone.localtime(self.slot.start).date().replace(day=1).isoformat()
        response = self.client.get(reverse('calendar'), {'month': month})
        self.assertContains(response, reverse('book', args=[self.slot.pk]))
        self.assertNotContains(response, '<div class="slot-booked">', html=False)

    def test_duplicate_reservation_rejected_by_view_and_database(self):
        self.reserve()
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse('book', args=[self.slot.pk]), self.data).status_code, 200)
        self.assertEqual(Booking.objects.count(), 1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Booking.objects.create(user=self.other, slot=self.slot, **self.data)

    def test_cancel_is_private_post_only_and_releases_slot(self):
        self.reserve()
        booking = Booking.objects.get()
        url = reverse('cancel_booking', args=[booking.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.assertNotContains(self.client.get(reverse('bookings')), 'Peugeot 207')
        self.client.force_login(self.user)
        self.assertRedirects(self.client.post(url), reverse('bookings'))
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'cancelled')
        self.client.force_login(self.other)
        self.assertRedirects(self.client.post(reverse('book', args=[self.slot.pk]), self.data), reverse('bookings'))
        self.assertEqual(Booking.objects.filter(status='confirmed').count(), 1)

    def test_past_and_blocked_slots_cannot_be_booked(self):
        self.slot.available = False
        self.slot.save()
        self.reserve()
        self.assertFalse(Booking.objects.exists())
        self.slot.available = True
        self.slot.start = timezone.now() - timedelta(hours=2)
        self.slot.end = timezone.now() - timedelta(hours=1)
        self.slot.save()
        self.reserve()
        self.assertFalse(Booking.objects.exists())

    def test_phone_validation_and_invalid_month(self):
        self.data['phone'] = '123'
        self.reserve()
        self.assertFalse(Booking.objects.exists())
        self.assertEqual(self.client.get(reverse('calendar'), {'month': 'invalid'}).status_code, 200)

    def test_slot_overlap_and_booked_time_edit_rejected(self):
        duplicate = AppointmentSlot(start=self.slot.start, end=self.slot.end)
        with self.assertRaises(ValidationError):
            duplicate.full_clean()
        self.reserve()
        self.slot.start += timedelta(minutes=30)
        with self.assertRaises(ValidationError):
            self.slot.full_clean()

    def test_csrf_protects_booking_and_cancellation(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(reverse('book', args=[self.slot.pk]), self.data).status_code, 403)
        self.reserve()
        self.assertEqual(client.post(reverse('cancel_booking', args=[Booking.objects.get().pk])).status_code, 403)


class AdminBookingTests(BookingTests):
    def test_direct_reservation_creates_slot_and_booking(self):
        self.client.force_login(self.admin)
        start = timezone.localtime(self.slot.end + timedelta(days=1))
        data = {**self.data, 'action': 'reserve', 'start': start.strftime('%Y-%m-%dT%H:%M'), 'end': (start + timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M')}
        self.assertRedirects(self.client.post(reverse('staff_bookings'), data), reverse('staff_bookings'))
        self.assertEqual(AppointmentSlot.objects.count(), 2)
        self.assertEqual(Booking.objects.get().user, self.admin)
        self.assertEqual(self.client.post(reverse('staff_bookings'), data).status_code, 200)
        self.assertEqual(Booking.objects.count(), 1)

    def test_direct_reservation_reuses_exact_slot(self):
        self.client.force_login(self.admin)
        start = timezone.localtime(self.slot.start).replace(second=0, microsecond=0)
        end = start + timedelta(hours=3)
        self.slot.start, self.slot.end = start, end
        self.slot.save()
        data = {**self.data, 'action': 'reserve', 'start': start.strftime('%Y-%m-%dT%H:%M'), 'end': end.strftime('%Y-%m-%dT%H:%M'), 'user': self.user.pk}
        self.assertRedirects(self.client.post(reverse('staff_bookings'), data), reverse('staff_bookings'))
        self.assertEqual(AppointmentSlot.objects.count(), 1)
        self.assertEqual(Booking.objects.get().user, self.user)

    def test_direct_overlap_rejected_and_bad_data_leaves_no_slot(self):
        self.client.force_login(self.admin)
        start = timezone.localtime(self.slot.start)
        data = {**self.data, 'action': 'reserve', 'start': start.strftime('%Y-%m-%dT%H:%M'), 'end': (start + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M')}
        response = self.client.post(reverse('staff_bookings'), data)
        self.assertTrue(response.context['booking_form'].errors)
        self.assertFalse(Booking.objects.exists())
        self.assertEqual(AppointmentSlot.objects.count(), 1)

    def test_admin_account_label(self):
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse('home')), 'Konto administratora')

    def setUp(self):
        super().setUp()
        self.admin = get_user_model().objects.create_superuser('admin', password='Admin-test-482!')

    def test_admin_reserves_for_client_on_website(self):
        self.client.force_login(self.admin)
        data = {**self.data, 'user': self.user.pk}
        self.assertRedirects(self.client.post(reverse('book', args=[self.slot.pk]), data), reverse('staff_bookings'))
        self.assertEqual(Booking.objects.get().user, self.user)
        self.assertContains(self.client.get(reverse('staff_bookings')), 'Jan Testowy')

    def test_admin_can_reserve_without_client_account(self):
        self.client.force_login(self.admin)
        self.assertRedirects(self.client.post(reverse('book', args=[self.slot.pk]), self.data), reverse('staff_bookings'))
        self.assertEqual(Booking.objects.get().user, self.admin)

    def test_client_cannot_access_management_or_assign_owner(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('staff_bookings')).status_code, 403)
        self.client.post(reverse('book', args=[self.slot.pk]), {**self.data, 'user': self.other.pk})
        self.assertEqual(Booking.objects.get().user, self.user)

    def test_admin_adds_slot_on_website(self):
        self.client.force_login(self.admin)
        start = timezone.localtime(self.slot.end + timedelta(days=1))
        data = {'start': start.strftime('%Y-%m-%dT%H:%M'), 'end': (start + timedelta(hours=3)).strftime('%Y-%m-%dT%H:%M'), 'available': 'on'}
        self.assertRedirects(self.client.post(reverse('staff_bookings'), data), reverse('staff_bookings'))
        self.assertEqual(AppointmentSlot.objects.count(), 2)

    def test_admin_adds_booking_in_admin_and_duplicate_is_rejected(self):
        self.client.force_login(self.admin)
        url = reverse('admin:dshine_app_booking_add')
        self.assertContains(self.client.get(url), 'name="slot"')
        data = {**self.data, 'slot': self.slot.pk, 'user': self.user.pk, 'status': 'confirmed', '_save': 'Zapisz'}
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.assertEqual(Booking.objects.get().user, self.user)
        self.assertEqual(self.client.post(url, data).status_code, 200)
        self.assertEqual(Booking.objects.count(), 1)

    def test_admin_can_cancel_client_booking(self):
        self.reserve()
        self.client.force_login(self.admin)
        self.assertRedirects(self.client.post(reverse('cancel_booking', args=[Booking.objects.get().pk])), reverse('staff_bookings'))
        self.assertEqual(Booking.objects.get().status, 'cancelled')
