from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('terminy/', views.calendar, name='calendar'),
    path('terminy/<int:slot_id>/rezerwuj/', views.book, name='book'),
    path('moje-rezerwacje/', views.bookings, name='bookings'),
    path('zarzadzanie/', views.staff_bookings, name='staff_bookings'),
    path('moje-rezerwacje/<int:booking_id>/anuluj/', views.cancel_booking, name='cancel_booking'),
]
