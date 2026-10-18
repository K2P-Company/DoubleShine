# Double Shine

Responsywna strona Django: oferta, galeria, kontakt i wspólne szablony konta. Oferta jest w `dshine/dshine_app/services.py`. Opisy są propozycją do potwierdzenia przez właścicieli; nie zawierają cen ani obietnic konkretnych zabiegów.

## Uruchomienie lokalne (PowerShell, Python 3.12+)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:DJANGO_DEBUG='true'
cd dshine
python manage.py migrate
python manage.py runserver
```

Zmienne ustawiaj w środowisku procesu. `.env.example` jest przykładem; aplikacja nie wczytuje automatycznie plików `.env`.

## Kontrola i wdrożenie

Uruchom `python manage.py check` oraz `python manage.py test`.

Produkcja wymaga `DJANGO_DEBUG=false`, silnego i unikalnego `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS` i `DJANGO_CSRF_TRUSTED_ORIGINS` z domeną HTTPS. Bez klucza aplikacja odmawia startu produkcyjnego. Nie używaj starego klucza z archiwum.

Wykonaj migracje, `collectstatic` i `check --deploy`; skonfiguruj serwer WSGI/ASGI, statyczne pliki, HTTPS, kopie zapasowe oraz logowanie błędów. Przy proxy dostosuj rozpoznawanie HTTPS do zaufanej infrastruktury. Nie używaj `runserver` do produkcji.

Przed publikacją potwierdź ofertę, kontakt, godziny pracy i prawa do zdjęć. Przed udostępnieniem kont klientom dopracuj informację o przetwarzaniu danych, odzyskiwanie hasła i ograniczanie prób logowania. Konta są dostępne z nawigacji i służą do zarządzania rezerwacjami. Oryginalna baza nie jest częścią paczki; uruchom migracje, aby utworzyć nową.

## Kalendarz i konta

- `/terminy/`: publiczny kalendarz wolnych terminów.
- `/register/` i `/login/`: rejestracja i logowanie klienta.
- `/moje-rezerwacje/`: własne wizyty i anulowanie przyszłych rezerwacji.
- `/admin/`: panel właściciela. Dodawaj terminy w sekcji „Terminy”, a zapisy obsługuj w „Rezerwacje”.

Po aktualizacji wykonaj `python manage.py migrate`. Utwórz administratora poleceniem `python manage.py createsuperuser`. Uruchom serwer ponownie.

Właściciel podaje początek i koniec każdego terminu. Kalendarz nie generuje fikcyjnej dostępności. Terminy nie mogą się nakładać: wersja obsługuje jedno auto jednocześnie. Wszystkie trzy rodzaje usług mogą być wybierane w każdym udostępnionym terminie; właściciel powinien udostępniać odpowiednio długie przedziały i potwierdzić zakres z klientem. Cena nie jest wyliczana automatycznie. Brak płatności i automatycznych powiadomień e-mail/SMS.

Rezerwacja zajmuje cały termin i od razu ma status „Potwierdzona”. Aktywny zapis jest unikalny w bazie. Anulowanie zachowuje historię i zwalnia termin. Klient nie może przeglądać ani anulować cudzych rezerwacji. Administrator może zmienić status rezerwacji; godzin zajętego terminu nie można edytować bez uprzedniego anulowania.

Przed publicznym wdrożeniem uzupełnij właściwą informację o przetwarzaniu danych i zasady rezerwacji, skonfiguruj odzyskiwanie dostępu oraz ograniczanie prób logowania. Dla większego ruchu zalecana jest baza PostgreSQL i testy współbieżności na docelowej infrastrukturze. SQLite to wersja startowa do lokalnego uruchomienia i małej skali.

## Rezerwacje administratora

Administrator po zalogowaniu na stronie ma pozycję „Zarządzanie” (`/zarzadzanie/`). Może dodawać wolne terminy, widzieć wszystkie wizyty i anulować przyszłe zapisy. Przycisk „Zarezerwuj dla klienta” prowadzi do kalendarza. Formularz rezerwacji pozwala wybrać konto klienta lub pozostawić je puste — wtedy zapis należy do administratora, z podanym imieniem i telefonem klienta.

W panelu `/admin/` w sekcji „Rezerwacje” działa „Dodaj rezerwację”. Należy wybrać konto, wolny termin i wypełnić dane klienta. Nie można zajmować terminu potwierdzonego dla innej osoby. Zarządzanie wymaga konta personelu z odpowiednimi uprawnieniami; zwykły klient nie ma dostępu. Konto superadministratora ma wszystkie wymagane uprawnienia.

Konto utworzone w lokalnej bazie nie jest częścią paczki ZIP. Przy uruchamianiu projektu na innym komputerze utwórz własnego administratora przez `python manage.py createsuperuser`.

Na stronie zarządzania formularz „Dodaj rezerwację klienta” tworzy przedział i rezerwację w jednym kroku. Dokładnie taki sam wolny przedział jest używany ponownie; częściowo nakładający się przedział jest odrzucany. Pasek pod menu pokazuje nazwę zalogowanego konta i jego rolę.

Kalendarz pokazuje również potwierdzone rezerwacje jako zajęte. Publicznie widoczne są wyłącznie godziny i status. Personel z uprawnieniem podglądu rezerwacji widzi klienta, auto i usługę. Anulowane rezerwacje zwalniają termin.

## Indeksowanie w wyszukiwarkach

Strona główna jest stroną przeznaczoną do wyników wyszukiwania. Logowanie, rejestracja, kalendarz, rezerwacje i zarządzanie mają `noindex` w nagłówku HTTP. Strony kont nadal wymagają uprawnień; noindex nie zastępuje zabezpieczeń.

Dla publicznej domeny ustaw:

```powershell
$env:DJANGO_DEBUG='false'
$env:DJANGO_SITE_URL='https://twoja-domena.pl'
$env:DJANGO_INDEXING_ENABLED='true'
```

Zastąp przykład rzeczywistą domeną. Ustaw też klucz, ALLOWED_HOSTS, zaufane adresy CSRF i obsługę HTTPS zgodnie z instrukcją wdrożenia. Po zmianie konfiguracji uruchom proces aplikacji ponownie.

`/robots.txt` wtedy pozwala na odczyt, a `/sitemap.xml` zawiera wyłącznie kanoniczny adres strony głównej. Fragmenty `#oferta`, `#kontakt` itd. są sekcjami tej samej strony, więc nie są osobnymi wpisami w mapie. Canonical wskazuje stałą domenę, pomija parametry śledzące i nie jest wyprowadzany z nagłówka Host.

Przy DEBUG=true, braku domeny lub INDEXING_ENABLED=false wersja pozostaje zablokowana. Staging powinien mieć INDEXING_ENABLED=false i dodatkowe ograniczenie dostępu, gdy zawiera prywatne dane. Robots i noindex są instrukcjami dla wyszukiwarek, nie kontrolą dostępu.

Po publikacji sprawdź publiczną stronę narzędziem kontroli adresu URL w Google Search Console i zgłoś mapę witryny. Zweryfikuj także przekierowania HTTP→HTTPS, www→wybrana domena oraz czy hosting/CDN nie dodaje własnego noindex ani blokad Googlebota. Indeksowanie nie gwarantuje pozycji w wynikach ani samego przyjęcia strony do indeksu.

## Demo na hostingu

Przygotowanie kontenera, bazy i zmiennych opisuje [WDROZENIE_DEMO.md](WDROZENIE_DEMO.md). Tryb `DJANGO_DEMO_MODE=true` wyświetla komunikat o testowych rezerwacjach i wyłącza indeksowanie. Nie zastępuje ochrony przed nadużyciami ani zasad przetwarzania danych.

## Aktualne zasady rezerwacji

Publiczny kalendarz służy wyłącznie do podglądu. Tworzenie rezerwacji wymaga konta personelu z uprawnieniem add_booking, także przy bezpośrednim wejściu na adres formularza lub wysłaniu POST. Publiczna rejestracja jest wyłączona (GET i POST zwracają 403). Wcześniejsze opisy samodzielnych zapisów klientów powyżej są nieaktualne. Klient kontaktuje się ze studiem, a administrator wprowadza wizytę. Istniejące konta zachowują podgląd i anulowanie własnych wizyt.

## Wyświetlanie godzin dostępności

Wielodniowe wolne przedziały w kalendarzu są przycinane do grafiku: pon.–pt. 10:00–18:00, sobota 10:00–14:00; niedziele pomijane. Jednodniowy termin ustawiony przez administratora jest wyjątkiem i zachowuje dokładne godziny. Zajęte rezerwacje zawsze pokazują rzeczywisty zapisany zakres. To sposób prezentacji dostępności, a nie podział przedziału na niezależne terminy: rezerwacja nadal zajmuje cały rekord terminu.
