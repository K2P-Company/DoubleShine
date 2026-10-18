"""Sprawdzenie zapisów wyłącznie przez uprawniony personel."""
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from .models import AppointmentSlot, Booking

@override_settings(SECURE_SSL_REDIRECT=False, STORAGES={'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'}, 'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class BookingPolicyTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='policy-client')
        start = timezone.now() + timedelta(days=10)
        self.slot = AppointmentSlot.objects.create(start=start, end=start + timedelta(hours=2))
        self.url = reverse('book', args=[self.slot.pk])
        self.data = {'service': 'exterior', 'name': 'Klient Testowy', 'phone': '000000000', 'car': 'Auto testowe', 'notes': ''}

    def test_anonymous_cannot_create_booking(self):
        self.assertEqual(self.client.post(self.url, self.data).status_code, 302)
        self.assertFalse(Booking.objects.exists())

    def test_client_cannot_get_or_post_even_with_permission(self):
        self.user.user_permissions.add(Permission.objects.get(codename='add_booking'))
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, self.data).status_code, 403)
        self.assertFalse(Booking.objects.exists())

    def test_staff_without_permission_cannot_book(self):
        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(self.url, self.data).status_code, 403)
        self.assertFalse(Booking.objects.exists())

    def test_authorized_staff_can_book(self):
        self.user.is_staff = True
        self.user.save()
        self.user.user_permissions.add(Permission.objects.get(codename='add_booking'))
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(self.client.post(self.url, self.data).status_code, 302)
        self.assertEqual(Booking.objects.get().user, self.user)

    def test_registration_get_and_post_disabled(self):
        count = get_user_model().objects.count()
        self.assertEqual(self.client.get(reverse('register')).status_code, 403)
        self.assertEqual(self.client.post(reverse('register'), {}).status_code, 403)
        self.assertEqual(get_user_model().objects.count(), count)

    def test_public_menu_and_calendar_have_no_signup_or_booking_links(self):
        response = self.client.get(reverse('home'))
        self.assertNotContains(response, 'href="/login/"')
        self.assertNotContains(response, 'href="/register/"')
        self.assertNotContains(response, 'href="/moje-rezerwacje/"')
        response = self.client.get(reverse('calendar'), {'month': self.slot.start.date().replace(day=1).isoformat()})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.url)
