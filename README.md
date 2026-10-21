# Hospital Management System (Django)

College project: roles (Admin, Receptionist, Doctor, Patient), patient portal,
appointments, consultations and prescriptions, billing with printable bills.

## Run it (Windows PowerShell)

```powershell
cd hospital_project
py -m pip install -r requirements.txt
# one-time: create the database (see "PostgreSQL setup" below), then:
py manage.py makemigrations hms
py manage.py migrate   # run both again after updating, existing data is kept
py manage.py setup_demo
py manage.py runserver
```

Open http://127.0.0.1:8000/

## Demo logins (created by `setup_demo`; change or delete before any real use)

| Role         | Username   | Password       |
|--------------|------------|----------------|
| Admin        | admin      | admin123       |
| Receptionist | reception  | reception123   |
| Doctor       | drsmith    | doctor123      |
| Patient      | patient1   | patient123     |

New patients can also sign up at `/register/`.

## Website vs dashboard

- Visitors and **patients** see a public red-themed hospital website with separate pages: Home, About Us, Departments, Our Doctors, Contact. A logged-in patient gets a "My Account" menu (appointments, records, bills, profile)
  and a welcome panel with their next appointments.
- **Admin, receptionist and doctors** are sent to the dashboard after login.
- Change the hospital name, phone, address, hours and tagline in `config/settings.py` (`HOSPITAL = {...}`).
- Everything on the website is managed by the admin (no code changes): departments, doctors, home page hero banners and patient testimonials.
- Doctors without an uploaded photo show a default picture: the woman picture for female doctors and the man picture for male doctors (set **Gender** on the doctor). The default disappears as soon as a photo is uploaded, by the admin (Website Manager > Doctors) or by the doctor after login (**My profile & photo**). Uploaded files are stored in `media/`. The default pictures are `hms/static/hms/img/doctor-male.jpg` and `doctor-female.jpg`.
- Hero banners, department banners and the About page picture use built-in illustrations in `hms/static/hms/img/` until you upload your own (hero banner and department images in Website Manager; for the About page replace `about-hospital.svg`).
- The About and Contact pages use `established`, `beds` and `map_query` from `HOSPITAL` in `config/settings.py`. Edit them to your real details.
- Messages sent from the Contact page form are saved and appear in Website Manager > Messages.

## Fees collection (admin and doctor)

- A separate **Fees collection** page in the sidebar. **Admin** sees every doctor with total patients, today's earning and total earning, plus recent paid fees. A **doctor** sees only their own patients and earnings (taken from the login, not the URL).
- Earnings are the consultation fee on bills marked **Paid**; "today" is the day the bill was marked paid (`Bill.paid_at`).

## Room booking (reception only)

Room booking is a **reception** tool and does not appear on the admin side. It works like a hotel: a room is booked **for dates**, so it is unavailable only for those dates and free again from the check-out date. The reception sidebar has separate pages:

- **Available rooms**: pick check-in and check-out dates (and optionally a room type) to see which rooms are free, which are booked and when they free up, plus a 14 day availability chart. One click on *Book this room* opens the booking form with the room and dates filled in.
- **Book a room**: patient, dates, room, doctor and reason. A live panel shows free beds per room for the chosen dates and the cost estimate; tick *Check the patient in now* for a patient arriving today.
- **Check-in**: patients arriving today (Check in / Cancel) and upcoming arrivals. Check-in opens on the arrival date and is blocked while the previous guest is still in the room.
- **Check-out**: patients currently in a room with days and charge so far. *Check out* frees the room and opens a printable stay receipt.
- **Add room**: add or edit rooms (number, type, floor, beds, charge per day, open/closed). *Beds* = how many patients can stay at the same time (1 for a private room, more for a ward).
- **Room overview** (live bed board) and **All bookings** (search, history, receipts).

All of these pages refresh themselves every 5 seconds, so a booking, check-in or check-out made by a colleague appears without reloading. The server re-checks availability when saving, so a room can never be double booked for the same dates. A patient cannot hold two rooms for the same dates. The estimated charge is days x the room's daily charge. `setup_demo` adds a few sample rooms.

Run `py manage.py makemigrations hms` and `py manage.py migrate` after updating.

- Doctor photos are cropped to 4:3 when uploaded (a crop window opens after choosing a file); default pictures are shown whole.

## Chat assistant

A chat button ("Ask us") appears on every public page. It answers from the database: departments, doctors (days, timings, fees), who is available today or tomorrow, hospital contact details and how to book. Logged-in patients can also ask for *my appointments*, *my bills* and *my records*. It is rule based, so it needs no API key or internet service.

## Who can do what

- **Admin** (superuser): everything, plus the Website Manager (`/panel/`) to add doctors, departments, receptionists and manage website content.
- **Receptionist**: register/edit patients, book/cancel appointments, create bills, mark paid.
- **Doctor**: see own appointments, write consultation and prescription (marks appointment completed), view patient history.
- **Patient**: book/cancel own appointments, see own records and bills, edit own contact details.

## Managing the website (admin)

Log in as `admin` and open **Website Manager** (dashboard button or `/panel/`). It is a separate admin area in the same red design as the site, not the Django admin page.

- **Departments**: name, icon (leave blank and it is chosen automatically from the name, e.g. Dental gets a tooth; you can still type your own emoji), description, services (one per line), banner image upload, display order, active on/off. Each department gets its own public page.
- **Doctors**: one form creates the doctor's login and profile together: name, username, password, department, qualification, experience, **photo upload with preview**, bio, days, timings, fee. *Featured* puts the doctor first on the home page (every active doctor is shown there); unticking *Active* hides the doctor from the website and from booking. Editing lets you set a new password.
- **Hero banners**: title, subtitle, background image upload and up to two buttons for the home page slider.
- **Testimonials**: patient reviews for the home page.
- **Receptionists**: create and manage front-desk logins.
- **Messages**: messages sent from the Contact page (open, reply by email, mark read, delete).

Everything you save is live on the public website straight away. Deleting a department that has doctors, or a doctor who has appointments, is blocked; hide it with *Active* instead.
Doctors can also upload their own photo after login from **My profile & photo**.
`/admin/` now redirects to the Website Manager. Django's built-in admin is kept only as a hidden backup at `/django-admin/`.

Receptionists are added in Website Manager > Receptionists.

## Project layout

- `config/` project settings and root URLs
- `hms/models.py` Department, Doctor, HeroSlide, Testimonial, Patient, Appointment, Consultation, Bill
- `hms/views.py` all pages, `hms/roles.py` + `hms/decorators.py` role checks
- `hms/templates/` HTML pages

## PostgreSQL setup

The project uses PostgreSQL (driver: `psycopg` 3). One-time setup:

1. Install PostgreSQL and remember the password you set for the `postgres` user.
2. Create the database, using `psql` or pgAdmin:
   ```sql
   CREATE DATABASE hospital_db;
   ```
3. Tell Django how to connect. In PowerShell, before running `manage.py`:
   ```powershell
   $env:DB_PASSWORD = "your-postgres-password"
   ```
   Optional overrides, with defaults: `DB_NAME=hospital_db`, `DB_USER=postgres`,
   `DB_HOST=localhost`, `DB_PORT=5432`.
4. Run `py manage.py makemigrations hms`, `py manage.py migrate` and `py manage.py setup_demo`.

## Before deploying anywhere real

Set `DJANGO_SECRET_KEY`, set `DJANGO_DEBUG=0`, use HTTPS, use a strong database password (not the default), and remove the demo accounts. Real patient data is sensitive; check
the privacy rules that apply to you.
