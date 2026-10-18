# Wdrożenie demo DoubleShine

Konfiguracja przygotowana do hostingu kontenerów z trwałą bazą PostgreSQL. Hosting i baza nie zostały jeszcze utworzone. Nie korzystaj z SQLite na ulotnym dysku hostingu.

## Ustawienia w panelu hostingu

- Buduj z Dockerfile w głównym katalogu repozytorium.
- DJANGO_DEBUG=false
- DJANGO_SECRET_KEY: nowy losowy sekret, zapisany wyłącznie w panelu hostingu.
- DATABASE_URL: prywatny adres bazy PostgreSQL; zasady TLS dobierz do dostawcy.
- DJANGO_ALLOWED_HOSTS: dokładna domena demo, bez protokołu.
- DJANGO_CSRF_TRUSTED_ORIGINS i DJANGO_SITE_URL: https:// oraz domena demo.
- DJANGO_DEMO_MODE=true i DJANGO_INDEXING_ENABLED=false.
- DJANGO_TRUST_PROXY=true wyłącznie gdy hosting zapewnia zaufany nagłówek X-Forwarded-Proto.

## Kolejność uruchomienia

1. Utwórz osobną bazę demo. Nie importuj prawdziwych klientów ani rezerwacji.
2. Ustaw zmienne i zbuduj aplikację.
3. Przed dopuszczeniem ruchu uruchom w środowisku hostingu `python manage.py migrate` oraz `python manage.py check --deploy`.
4. Utwórz administratora przez `python manage.py createsuperuser`. Nie zapisuj jego hasła w kodzie i nie udostępniaj konta publicznie.
5. Dodaj przykładowe przyszłe terminy w panelu administratora. Dane klientów mają być fikcyjne.
6. Przed publikacją sprawdź HTTPS, statyczne pliki, rezerwację i anulowanie oraz izolację kont. Konfiguracja nie została jeszcze uruchomiona ani przetestowana na hostingu.

## Pozostałe prace przed publicznym demo

Widoczny komunikat demo nie blokuje wpisywania prawdziwych danych. Przed otwartym udostępnieniem trzeba ustalić usuwanie danych testowych, ograniczyć próby logowania/rejestracji i nadużycia rezerwacji oraz przygotować właściwą informację o prywatności. Sprawdź treści kontaktowe i prawa do zdjęć. Nie publikuj obietnicy rzeczywistych wizyt.

Migracji nie wykonujemy przy starcie każdego workera. Uruchamiaj je jako osobny krok wdrożenia, raz na wersję. Zasady kopii bazy i jej retencji ustal u dostawcy.
