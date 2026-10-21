from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Count, F, Q, Sum
import json
from collections import defaultdict
from datetime import date as date_cls, timedelta

from django.http import HttpResponseNotAllowed, JsonResponse
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .chatbot import answer
from .decorators import role_required
from .forms import (
    AppointmentForm,
    BillForm,
    ContactForm,
    DoctorProfileForm,
    ConsultationForm,
    PatientForm,
    PatientProfileForm,
    PortalAppointmentForm,
    RegisterForm,
    RoomBookingForm,
    RoomForm,
)
from .models import Appointment, Bill, Consultation, Department, Doctor, HeroSlide, Patient, Room, RoomBooking, Testimonial
from .roles import get_role

STAFF = ("admin", "receptionist")


def form_page(request, form, title, back="dashboard", submit="Save"):
    return render(request, "hms/form.html", {"form": form, "title": title, "back": back, "submit": submit})


# ---------------------------------------------------------------- auth

def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        user = User.objects.create_user(username=d["username"], password=d["password1"], first_name=d["name"])
        Patient.objects.create(
            user=user, name=d["name"], date_of_birth=d["date_of_birth"], gender=d["gender"], phone=d["phone"]
        )
        login(request, user)
        messages.success(request, "Registration successful. Welcome!")
        return redirect("dashboard")
    return render(request, "registration/register.html", {"form": form})


# ------------------------------------------------------- fee collection

def fee_summary(doctor=None):
    """Per-doctor patient count and fees collected.

    Earnings = consultation fee on PAID bills (other charges such as lab/medicine are not the doctor's fee).
    "Today" uses the date the bill was marked paid. Pass a Doctor to get only that doctor's row.
    """
    start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    paid_today = (
        Q(paid_at__gte=start, paid_at__lt=end)
        | Q(paid_at__isnull=True, created_at__gte=start, created_at__lt=end)  # older bills saved before paid_at existed
    )
    bills = Bill.objects.filter(payment_status="PAID")
    appts = Appointment.objects.exclude(status="CANCELLED")
    docs = Doctor.objects.select_related("user", "department").order_by("user__first_name", "user__last_name")
    if doctor is not None:
        bills, appts, docs = bills.filter(appointment__doctor=doctor), appts.filter(doctor=doctor), docs.filter(pk=doctor.pk)

    earned = {
        r["appointment__doctor"]: r
        for r in bills.values("appointment__doctor").annotate(
            total=Sum("consultation_fee"), today=Sum("consultation_fee", filter=paid_today)
        )
    }
    patients = {r["doctor"]: r["n"] for r in appts.values("doctor").annotate(n=Count("patient", distinct=True))}
    rows = []
    for d in docs:
        e = earned.get(d.pk, {})
        rows.append({
            "doctor": d,
            "patients": patients.get(d.pk, 0),
            "today": e.get("today") or 0,
            "total": e.get("total") or 0,
        })
    totals = {
        "patients": appts.values("patient").distinct().count(),
        "today": sum(r["today"] for r in rows),
        "total": sum(r["total"] for r in rows),
    }
    return rows, totals


# ----------------------------------------------------------- dashboard

def home(request):
    """Public website. Everyone can view it; staff and doctors have a Dashboard button in the header."""
    role = get_role(request.user)
    active_docs = Doctor.objects.filter(is_active=True).select_related("user", "department")
    everyone = list(active_docs.order_by("-is_featured", "user__first_name", "user__last_name"))  # all active doctors, featured first
    ctx = {
        "slides": HeroSlide.objects.filter(is_active=True),
        "departments": active_departments()[:8],
        "finder_departments": Department.objects.filter(is_active=True),
        "department_total": Department.objects.filter(is_active=True).count(),
        "doctors": everyone,
        "doctor_total": active_docs.count(),
        "patient_total": Patient.objects.count(),
        "testimonials": Testimonial.objects.filter(is_active=True)[:6],
        "upcoming": [],
    }
    if role == "patient":
        ctx["upcoming"] = (
            request.user.patient_profile.appointments.filter(status="BOOKED", date__gte=timezone.localdate())
            .select_related("doctor__user")
            .order_by("date", "time")[:3]
        )
    return render(request, "site/home.html", ctx)


def chatbot(request):
    """Answers website visitors' questions from database records. Personal answers are for logged-in patients only."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    try:
        message = str(json.loads(request.body or "{}").get("message", ""))
    except (ValueError, AttributeError):
        message = ""
    return JsonResponse(answer(request.user, get_role(request.user), message))


def doctors_public(request):
    dept = request.GET.get("dept", "")
    q = request.GET.get("q", "").strip()
    doctors = Doctor.objects.filter(is_active=True).select_related("user", "department").order_by(
        "department__display_order", "department__name", "user__first_name"
    )
    if dept.isdigit():
        doctors = doctors.filter(department_id=int(dept))
    if q:
        doctors = doctors.filter(
            Q(user__first_name__icontains=q) | Q(user__last_name__icontains=q)
            | Q(specialization__icontains=q) | Q(department__name__icontains=q)
        )
    ctx = {"doctors": doctors, "departments": Department.objects.filter(is_active=True), "dept": dept, "q": q}
    return render(request, "site/doctors.html", ctx)


def doctor_detail(request, pk):
    doctor = get_object_or_404(Doctor.objects.select_related("user", "department"), pk=pk, is_active=True)
    colleagues = (
        Doctor.objects.filter(is_active=True, department=doctor.department)
        .exclude(pk=doctor.pk).select_related("user", "department")[:3]
    )
    return render(request, "site/doctor_detail.html", {"doctor": doctor, "colleagues": colleagues})


def about(request):
    active_docs = Doctor.objects.filter(is_active=True).select_related("user", "department")
    ctx = {
        "team": list(active_docs.filter(is_featured=True)[:4]) or list(active_docs[:4]),
        "doctor_total": active_docs.count(),
        "department_total": Department.objects.filter(is_active=True).count(),
        "patient_total": Patient.objects.count(),
    }
    return render(request, "site/about.html", ctx)


def active_departments():
    return Department.objects.filter(is_active=True).annotate(
        doctor_count=Count("doctors", filter=Q(doctors__is_active=True))
    )


def departments(request):
    return render(request, "site/departments.html", {"departments": active_departments()})


def department_detail(request, pk):
    dept = get_object_or_404(active_departments(), pk=pk)
    doctors = dept.doctors.filter(is_active=True).select_related("user", "department")
    others = active_departments().exclude(pk=pk)[:6]
    return render(request, "site/department_detail.html", {"dept": dept, "doctors": doctors, "others": others})


def contact(request):
    form = ContactForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Thank you. Your message has been sent and our team will get back to you soon.")
        return redirect("contact")
    return render(request, "site/contact.html", {"form": form})


@login_required
def dashboard(request):
    role = get_role(request.user)
    if role == "patient":
        return redirect("home")
    today = timezone.localdate()
    active = Appointment.objects.exclude(status="CANCELLED")
    ctx = {}

    if role in STAFF:
        paid = Bill.objects.filter(payment_status="PAID").aggregate(t=Sum(F("consultation_fee") + F("other_charges")))
        ctx = {
            "patients": Patient.objects.count(),
            "doctors": Doctor.objects.count(),
            "today_count": active.filter(date=today).count(),
            "pending_bills": Bill.objects.filter(payment_status="PENDING").count(),
            "revenue": paid["t"] or 0,
            "appointments": active.filter(date__gte=today, status="BOOKED").select_related("patient", "doctor__user")[:8],
        }
        if role == "receptionist":
            ctx["admitted"] = RoomBooking.objects.filter(status="ADMITTED").count()
    elif role == "doctor":
        me = request.user.doctor  # always the logged-in doctor, never taken from the URL
        mine = active.filter(doctor=me).select_related("patient")
        ctx = {
            "today_count": mine.filter(date=today).count(),
            "appointments": mine.filter(date__gte=today, status="BOOKED")[:10],
        }
    elif role == "patient":
        mine = request.user.patient_profile.appointments.exclude(status="CANCELLED").select_related("doctor__user")
        ctx = {"appointments": mine.filter(date__gte=today, status="BOOKED")[:5]}
    return render(request, "hms/dashboard.html", ctx)


# ----------------------------------------------------- patients (staff)

@role_required(*STAFF)
def patient_list(request):
    q = request.GET.get("q", "").strip()
    patients = Patient.objects.all().order_by("-id")
    if q:
        patients = patients.filter(Q(name__icontains=q) | Q(patient_id__icontains=q) | Q(phone__icontains=q))
    return render(request, "hms/patient_list.html", {"patients": patients, "q": q})


@role_required(*STAFF)
def patient_edit(request, pk=None):
    patient = get_object_or_404(Patient, pk=pk) if pk else None
    form = PatientForm(request.POST or None, instance=patient)
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        messages.success(request, f"Patient {saved.patient_id} saved.")
        return redirect("patient_detail", pk=saved.pk)
    return form_page(request, form, "Edit patient" if patient else "Register new patient", back="patient_list")


@role_required(*STAFF, "doctor")
def patient_detail(request, pk):
    patient = get_object_or_404(Patient, pk=pk)
    appointments = patient.appointments.select_related("doctor__user", "doctor__department").order_by("-date", "-time")
    room_bookings = patient.room_bookings.select_related("room") if get_role(request.user) == "receptionist" else []
    return render(request, "hms/patient_detail.html", {"patient": patient, "appointments": appointments, "room_bookings": room_bookings})


# ------------------------------------------------ appointments (staff)

@role_required(*STAFF)
def appointment_list(request):
    today = timezone.localdate()
    show = request.GET.get("show", "upcoming")
    qs = Appointment.objects.select_related("patient", "doctor__user", "doctor__department")
    if show == "all":
        qs = qs.order_by("-date", "-time")
    elif show == "today":
        qs = qs.filter(date=today)
    else:
        qs = qs.filter(date__gte=today)
    return render(request, "hms/appointment_list.html", {"appointments": qs, "show": show, "title": "Appointments"})


@role_required(*STAFF)
def appointment_create(request):
    initial = {}
    if request.GET.get("patient"):
        initial["patient"] = request.GET["patient"]
    form = AppointmentForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Appointment booked.")
        return redirect("appointment_list")
    return form_page(request, form, "Book appointment", back="appointment_list", submit="Book")


@login_required
def appointment_cancel(request, pk):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    appt = get_object_or_404(Appointment, pk=pk)
    role = get_role(request.user)
    allowed = role in STAFF or (role == "patient" and appt.patient.user_id == request.user.id)
    if not allowed:
        raise PermissionDenied
    if appt.status == "BOOKED":
        appt.status = "CANCELLED"
        appt.save(update_fields=["status"])
        messages.success(request, "Appointment cancelled.")
    else:
        messages.error(request, "Only booked appointments can be cancelled.")
    return redirect("portal_appointments" if role == "patient" else "appointment_list")


# --------------------------------------------------------------- doctor

@role_required("doctor")
def doctor_appointments(request):
    today = timezone.localdate()
    show = request.GET.get("show", "upcoming")
    qs = request.user.doctor.appointments.select_related("patient", "doctor__user")
    if show == "all":
        qs = qs.order_by("-date", "-time")
    elif show == "today":
        qs = qs.filter(date=today)
    else:
        qs = qs.filter(date__gte=today)
    return render(request, "hms/appointment_list.html", {"appointments": qs, "show": show, "title": "My appointments"})


@role_required("doctor")
def doctor_profile(request):
    form = DoctorProfileForm(request.POST or None, request.FILES or None, instance=request.user.doctor)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Your profile and photo were updated on the website.")
        return redirect("doctor_profile")
    return form_page(request, form, "My profile and photo", back="dashboard")


@role_required("doctor")
def consultation_edit(request, appointment_id):
    appt = get_object_or_404(Appointment, pk=appointment_id, doctor=request.user.doctor)
    if appt.status == "CANCELLED":
        messages.error(request, "This appointment was cancelled.")
        return redirect("doctor_appointments")
    consultation = Consultation.objects.filter(appointment=appt).first()
    form = ConsultationForm(request.POST or None, instance=consultation)
    if request.method == "POST" and form.is_valid():
        c = form.save(commit=False)
        c.appointment = appt
        c.save()
        appt.status = "COMPLETED"
        appt.save(update_fields=["status"])
        messages.success(request, "Consultation saved and appointment marked completed.")
        return redirect("doctor_appointments")
    title = f"Consultation - {appt.patient.name} ({appt.patient.patient_id})"
    return form_page(request, form, title, back="doctor_appointments")


# -------------------------------------------------------------- billing

@role_required(*STAFF)
def bill_list(request):
    from django.db.models import DecimalField, ExpressionWrapper
    base = Bill.objects.select_related("appointment__patient", "appointment__doctor__user").order_by("-id")
    amount = ExpressionWrapper(F("consultation_fee") + F("other_charges"), output_field=DecimalField(max_digits=12, decimal_places=2))

    def money(qs):
        return qs.aggregate(t=Sum(amount))["t"] or 0

    show = request.GET.get("show", "all")
    q = request.GET.get("q", "").strip()
    bills = base
    if show == "paid":
        bills = bills.filter(payment_status="PAID")
    elif show == "pending":
        bills = bills.filter(payment_status="PENDING")
    else:
        show = "all"
    if q:
        match = (Q(appointment__patient__name__icontains=q) | Q(appointment__doctor__user__first_name__icontains=q)
                 | Q(appointment__doctor__user__last_name__icontains=q))
        if q.lstrip("#").isdigit():
            match |= Q(pk=int(q.lstrip("#")))
        bills = bills.filter(match)
    paid_qs, pending_qs = base.filter(payment_status="PAID"), base.filter(payment_status="PENDING")
    stats = {
        "count": base.count(), "paid_count": paid_qs.count(), "pending_count": pending_qs.count(),
        "paid_amount": money(paid_qs), "pending_amount": money(pending_qs),
    }
    stats["billed"] = stats["paid_amount"] + stats["pending_amount"]
    stats["rate"] = round(100 * stats["paid_amount"] / stats["billed"]) if stats["billed"] else 0
    return render(request, "hms/bill_list.html", {"bills": bills, "title": "Bills", "stats": stats, "show": show, "q": q})


@role_required(*STAFF)
def bill_create(request, appointment_id):
    appt = get_object_or_404(Appointment, pk=appointment_id)
    form = BillForm(request.POST or None, initial={"consultation_fee": appt.doctor.consultation_fee})
    if request.method == "POST" and form.is_valid():
        bill = form.save(commit=False)
        bill.appointment = appt
        bill.save()
        messages.success(request, f"Bill #{bill.pk} created.")
        return redirect("bill_detail", pk=bill.pk)
    return form_page(request, form, f"New bill - {appt.patient.name}", back="appointment_list", submit="Create bill")


@login_required
def bill_detail(request, pk):
    bill = get_object_or_404(Bill.objects.select_related("appointment__patient", "appointment__doctor__user"), pk=pk)
    role = get_role(request.user)
    owns = role == "patient" and bill.appointment.patient.user_id == request.user.id
    if role not in STAFF and not owns:
        raise PermissionDenied
    return render(request, "hms/bill_detail.html", {"bill": bill})


@role_required(*STAFF)
def bill_mark_paid(request, pk):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    bill = get_object_or_404(Bill, pk=pk)
    bill.payment_status = "PAID"
    bill.save(update_fields=["payment_status"])  # Bill.save() also stamps paid_at
    messages.success(request, f"Bill #{bill.pk} marked as paid.")
    return redirect("bill_detail", pk=bill.pk)


# --------------------------------------------------------- patient portal

@role_required("patient")
def portal_appointments(request):
    qs = request.user.patient_profile.appointments.select_related("doctor__user", "doctor__department").order_by("-date", "-time")
    return render(request, "hms/appointment_list.html", {"appointments": qs, "title": "My appointments"})


@role_required("patient")
def portal_book(request):
    patient = request.user.patient_profile
    form = PortalAppointmentForm(request.POST or None)
    if request.method == "POST":
        form.instance.patient = patient
        if form.is_valid():
            form.save()
            messages.success(request, "Appointment booked.")
            return redirect("portal_appointments")
    return form_page(request, form, "Book an appointment", back="portal_appointments", submit="Book")


@role_required("patient")
def portal_records(request):
    consultations = (
        Consultation.objects.filter(appointment__patient=request.user.patient_profile)
        .select_related("appointment__doctor__user")
        .order_by("-created_at")
    )
    return render(request, "hms/records.html", {"consultations": consultations})


@role_required("patient")
def portal_bills(request):
    bills = (
        Bill.objects.filter(appointment__patient=request.user.patient_profile)
        .select_related("appointment__patient", "appointment__doctor__user")
        .order_by("-id")
    )
    return render(request, "hms/bill_list.html", {"bills": bills, "title": "My bills"})


@role_required("patient")
def portal_profile(request):
    patient = request.user.patient_profile
    form = PatientProfileForm(request.POST or None, instance=patient)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile updated.")
        return redirect("home")
    return form_page(request, form, f"My profile - {patient.patient_id}", back="home")


# ------------------------------------------------------ fees collection

@role_required("admin", "doctor")
def fees_collection(request):
    """Admin sees every doctor; a doctor sees only their own patients and earnings (taken from the login)."""
    bills = Bill.objects.filter(payment_status="PAID").select_related("appointment__patient", "appointment__doctor__user")
    if get_role(request.user) == "doctor":
        me = request.user.doctor
        rows, totals = fee_summary(me)
        bills = bills.filter(appointment__doctor=me)
    else:
        rows, totals = fee_summary()
    recent = bills.order_by("-paid_at", "-created_at")[:30]
    return render(request, "hms/fees.html", {"rows": rows, "totals": totals, "recent": recent})


# ------------------------------------------------ rooms (reception only)

FRONT_DESK = ("receptionist",)  # room booking is a reception tool; it is not shown on the admin side


def room_board():
    """Live bed picture for every room: who is in, who arrives today, what is coming up."""
    today = timezone.localdate()
    by_room = defaultdict(list)
    active = RoomBooking.objects.filter(status__in=RoomBooking.ACTIVE).select_related("patient").order_by("check_in")
    for b in active:
        by_room[b.room_id].append(b)
    rooms = list(Room.objects.all())
    for r in rooms:
        bs = by_room[r.id]
        r.admitted = [b for b in bs if b.status == "ADMITTED"]
        r.due = [b for b in bs if b.status == "BOOKED" and b.check_in <= today < b.check_out]
        r.upcoming = [b for b in bs if b.status == "BOOKED" and b.check_in > today]
        occ = min(len(r.admitted), r.beds)
        res = min(len(r.due), r.beds - occ)
        r.free = r.beds - occ - res
        r.bed_states = ["occ"] * occ + ["res"] * res + ["free"] * r.free
    live = [r for r in rooms if r.is_active]
    beds = sum(r.beds for r in live)
    occupied = sum(r.bed_states.count("occ") for r in live)
    reserved = sum(r.bed_states.count("res") for r in live)
    free = sum(r.free for r in live)
    stats = {
        "rooms": len(live), "beds": beds, "occupied": occupied, "reserved": reserved, "free": free,
        "pct": round((occupied + reserved) * 100 / beds) if beds else 0,
    }
    return rooms, stats


@role_required(*FRONT_DESK)
def room_list(request):
    rooms, stats = room_board()
    ctx = {"rooms": rooms, "stats": stats, "room_types": Room.TYPE_CHOICES}
    # ?partial=1 is what the page polls every few seconds to stay live
    return render(request, "hms/_room_board.html" if request.GET.get("partial") else "hms/room_list.html", ctx)


def parse_date(value, default):
    try:
        return date_cls.fromisoformat(value)
    except (TypeError, ValueError):
        return default


NEXT_PAGES = ("room_checkin", "room_checkout", "room_booking_list", "room_available")


@role_required(*FRONT_DESK)
def room_edit(request, pk=None):
    room = get_object_or_404(Room, pk=pk) if pk else None
    form = RoomForm(request.POST or None, instance=room)
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        messages.success(request, f"Room {saved.number} saved.")
        return redirect("room_list")
    return render(request, "hms/room_edit.html", {"form": form, "room": room, "rooms": Room.objects.all()})


# ---- available rooms (hotel style: pick dates, see what is free)

@role_required(*FRONT_DESK)
def room_available(request):
    today = timezone.localdate()
    one_day = timedelta(days=1)
    start = max(parse_date(request.GET.get("check_in"), today), today)
    end = parse_date(request.GET.get("check_out"), start + one_day)
    if end <= start:
        end = start + one_day
    rtype = request.GET.get("type", "")
    if rtype not in dict(Room.TYPE_CHOICES):
        rtype = ""
    nights = (end - start).days

    rooms = list(Room.objects.filter(is_active=True, **({"room_type": rtype} if rtype else {})))
    free, busy = [], []
    for r in rooms:
        blockers = r.blockers(start, end)
        r.free = max(r.beds - len(blockers), 0)
        r.bed_states = ["free"] * r.free + ["occ"] * (r.beds - r.free)
        r.total = nights * r.daily_charge
        if r.free:
            free.append(r)
        else:
            r.free_from = min(b.effective_end(today) for b in blockers)
            busy.append(r)

    # 14 day availability chart (like a hotel's tape chart)
    by_room = defaultdict(list)
    for b in RoomBooking.objects.filter(status__in=RoomBooking.ACTIVE).select_related("patient"):
        by_room[b.room_id].append(b)
    days = [{"date": today + timedelta(days=n), "sel": start <= today + timedelta(days=n) < end, "today": n == 0} for n in range(14)]
    chart = []
    for r in rooms:
        cells = []
        for d in days:
            taken = [b for b in by_room[r.id] if b.check_in <= d["date"] < b.effective_end(today)]
            state = "full" if len(taken) >= r.beds else ("part" if taken else "free")
            cells.append({"state": state, "sel": d["sel"], "names": ", ".join(b.patient.name for b in taken)})
        chart.append({"room": r, "cells": cells})

    ctx = {
        "free": free, "busy": busy, "chart": chart, "days": days, "start": start, "end": end, "nights": nights,
        "rtype": rtype, "room_types": Room.TYPE_CHOICES, "today": today,
    }
    return render(request, "hms/_room_available.html" if request.GET.get("partial") else "hms/room_available.html", ctx)


# ---- bookings list, new booking, availability json

@role_required(*FRONT_DESK)
def room_booking_list(request):
    today = timezone.localdate()
    show = request.GET.get("show", "active")
    qs = RoomBooking.objects.select_related("patient", "room", "doctor__user")
    if show == "history":
        qs = qs.filter(status__in=("DISCHARGED", "CANCELLED"))
    elif show == "all":
        pass
    else:
        show = "active"
        qs = qs.filter(status__in=RoomBooking.ACTIVE).order_by("status", "check_in")  # checked-in first
    bookings = list(qs)
    for b in bookings:
        b.due = b.status == "BOOKED" and b.check_in <= today
        b.overdue = b.status == "ADMITTED" and b.check_out < today
    open_ = RoomBooking.objects.filter(status__in=RoomBooking.ACTIVE)
    counts = {
        "admitted": open_.filter(status="ADMITTED").count(),
        "due": open_.filter(status="BOOKED", check_in__lte=today).count(),
        "upcoming": open_.filter(status="BOOKED", check_in__gt=today).count(),
    }
    ctx = {"bookings": bookings, "show": show, "counts": counts}
    return render(request, "hms/_room_booking_table.html" if request.GET.get("partial") else "hms/room_booking_list.html", ctx)


@role_required(*FRONT_DESK)
def room_booking_create(request):
    today = timezone.localdate()
    start = max(parse_date(request.GET.get("check_in"), today), today)
    end = parse_date(request.GET.get("check_out"), start + timedelta(days=1))
    initial = {"check_in": start, "check_out": end if end > start else start + timedelta(days=1)}
    for key in ("patient", "room"):
        if request.GET.get(key, "").isdigit():
            initial[key] = request.GET[key]
    form = RoomBookingForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        with transaction.atomic():
            # re-check inside a transaction: another receptionist may have just taken the room
            room = Room.objects.select_for_update().get(pk=d["room"].pk)
            if room.free_beds(d["check_in"], d["check_out"]) < 1:
                form.add_error(None, f"{room} was just booked by someone else. Pick another room or other dates.")
            else:
                b = form.save()
                if d.get("check_in_now") and b.check_in == today:
                    b.status = "ADMITTED"
                    b.save(update_fields=["status"])
                    messages.success(request, f"{b.patient.name} checked in to room {b.room.number}.")
                    return redirect("room_checkout")
                messages.success(request, f"Room {b.room.number} booked for {b.patient.name} ({b.check_in:%d %b} to {b.check_out:%d %b}).")
                return redirect("room_checkin")
    return render(request, "hms/room_booking_form.html", {"form": form, "today": today})


@role_required(*FRONT_DESK)
def room_availability(request):
    """JSON used by the booking form: free beds per room for the chosen dates (refreshed live)."""
    today = timezone.localdate()
    start = parse_date(request.GET.get("check_in"), today)
    end = parse_date(request.GET.get("check_out"), start + timedelta(days=1))
    valid = end > start and start >= today
    if end <= start:
        end = start + timedelta(days=1)
    rooms = [
        {"id": r.pk, "number": r.number, "type": r.get_room_type_display(), "floor": r.floor, "beds": r.beds,
         "free": r.free_beds(start, end), "charge": float(r.daily_charge)}
        for r in Room.objects.filter(is_active=True)
    ]
    return JsonResponse({"valid": valid, "nights": (end - start).days, "rooms": rooms})


# ---- check-in and check-out pages

@role_required(*FRONT_DESK)
def room_checkin(request):
    today = timezone.localdate()
    booked = list(RoomBooking.objects.filter(status="BOOKED").select_related("patient", "room", "doctor__user").order_by("check_in"))
    due = [b for b in booked if b.check_in <= today]
    upcoming = [b for b in booked if b.check_in > today]
    counts = {"due": len(due), "upcoming": len(upcoming), "inhouse": RoomBooking.objects.filter(status="ADMITTED").count()}
    ctx = {"due": due, "upcoming": upcoming, "counts": counts, "today": today}
    return render(request, "hms/_room_checkin.html" if request.GET.get("partial") else "hms/room_checkin.html", ctx)


@role_required(*FRONT_DESK)
def room_checkout(request):
    today = timezone.localdate()
    inhouse = list(RoomBooking.objects.filter(status="ADMITTED").select_related("patient", "room", "doctor__user").order_by("check_out"))
    for b in inhouse:
        b.days_in = max((today - b.check_in).days, 1)
        b.charge_so_far = b.days_in * b.room.daily_charge
        b.due_today = b.check_out == today
        b.overdue = b.check_out < today
    counts = {
        "inhouse": len(inhouse),
        "due_today": len([b for b in inhouse if b.due_today]),
        "overdue": len([b for b in inhouse if b.overdue]),
        "checked_out": RoomBooking.objects.filter(status="DISCHARGED").count(),
        "checked_out_today": RoomBooking.objects.filter(status="DISCHARGED", discharged_on=today).count(),
    }
    ctx = {"bookings": inhouse, "counts": counts}
    return render(request, "hms/_room_checkout.html" if request.GET.get("partial") else "hms/room_checkout.html", ctx)


@role_required(*FRONT_DESK)
def room_receipt(request, pk):
    b = get_object_or_404(RoomBooking.objects.select_related("patient", "room", "doctor__user"), pk=pk)
    return render(request, "hms/room_receipt.html", {"b": b})


@role_required(*FRONT_DESK)
def room_booking_action(request, pk, action):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    today = timezone.localdate()
    nxt = request.POST.get("next")
    target = nxt if nxt in NEXT_PAGES else "room_booking_list"
    b = get_object_or_404(RoomBooking.objects.select_related("patient", "room"), pk=pk)

    if action == "checkin" and b.status == "BOOKED":
        if b.check_in > today:
            messages.error(request, f"{b.patient.name} arrives on {b.check_in:%d %b %Y}. Check-in opens on that day.")
        elif b.room.bookings.filter(status="ADMITTED").exclude(pk=b.pk).count() >= b.room.beds:
            who = ", ".join(x.patient.name for x in b.room.bookings.filter(status="ADMITTED").exclude(pk=b.pk).select_related("patient"))
            messages.error(request, f"Room {b.room.number} is still occupied by {who}. Check them out first.")
        else:
            b.status = "ADMITTED"
            b.save(update_fields=["status"])
            messages.success(request, f"{b.patient.name} checked in to room {b.room.number}.")
    elif action == "discharge" and b.status == "ADMITTED":
        b.status, b.discharged_on = "DISCHARGED", today
        b.save(update_fields=["status", "discharged_on"])
        messages.success(request, f"{b.patient.name} checked out of room {b.room.number}. Room is available again.")
        return redirect("room_receipt", pk=b.pk)
    elif action == "cancel" and b.status == "BOOKED":
        b.status = "CANCELLED"
        b.save(update_fields=["status"])
        messages.success(request, "Room booking cancelled. The room is available again for those dates.")
    else:
        messages.error(request, "That action is not possible for this booking.")
    return redirect(target)
