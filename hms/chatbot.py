"""Rule-based website assistant. Every answer is built from live database records (no external AI service)."""
import re

from django.conf import settings
from django.db.models import Q, Sum, F
from django.urls import reverse
from django.utils import timezone

from .models import Appointment, Bill, Consultation, Department, Doctor

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
STOP = {"doctor", "doctors", "which", "where", "what", "when", "who", "that", "this", "with", "have", "need", "show",
        "please", "tell", "about", "hospital", "available", "appointment", "book", "fees", "consultation", "timings",
        "department", "departments", "today", "tomorrow", "there", "their", "from", "your", "mine", "list"}

# words a patient might type -> a piece of the department name they mean.
# A trailing * means "starts with"; other entries must match as whole words.
SYNONYMS = {
    ("heart", "cardiac*", "chest pain", "bp", "blood pressure"): "cardio",
    ("teeth", "tooth", "dentist*", "dental", "braces", "cavity"): "dental",
    ("skin", "hair", "acne", "rash", "dermat*"): "dermat",
    ("eye", "eyes", "vision", "cataract*", "ophthal*"): "ophthal",
    ("child", "children", "kid", "kids", "baby", "babies", "newborn", "pediatric*", "paediatric*"): "pediatric",
    ("bone", "bones", "joint", "joints", "fracture*", "knee", "back pain", "ortho*"): "ortho",
    ("brain", "migraine", "headache", "stroke", "epilepsy", "neuro*"): "neuro",
    ("pregnan*", "women", "delivery", "gynec*", "gynaec*", "obstet*"): "gyn",
    ("stomach", "digest*", "liver", "gastro*", "acidity"): "gastro",
    ("ear", "ears", "nose", "throat", "sinus", "ent"): "ent",
    ("emergency", "accident", "trauma", "ambulance"): "emergency",
    ("fever", "cold", "cough", "general", "physician", "checkup", "check-up"): "general",
}


def _word(text, w):
    if w.endswith("*"):
        return re.search(r"\b" + re.escape(w[:-1]), text) is not None
    return re.search(r"\b" + re.escape(w) + r"\b", text) is not None


def _clean(text):
    return re.sub(r"\s+", " ", text.lower()).strip()


def _has(text, *words):
    return any(w in text for w in words)


def _days_of(doctor):
    """Set of weekday keys a doctor is available, parsed from text like 'Mon - Sat' or 'Mon, Wed, Fri'."""
    raw = (doctor.available_days or "").lower()
    if not raw.strip():
        return set(DAYS)  # unknown: treat as available, the card shows 'ask reception'
    if "24" in raw or "daily" in raw or "every" in raw:
        return set(DAYS)
    found = set()
    for part in re.split(r"[,&/]|\band\b", raw):
        part = part.strip()
        m = re.match(r"^(\w{3})\w*\s*(?:-|to)\s*(\w{3})\w*$", part)
        if m and m.group(1) in DAYS and m.group(2) in DAYS:
            a, b = DAYS.index(m.group(1)), DAYS.index(m.group(2))
            found.update(DAYS[a:b + 1] if a <= b else DAYS[a:] + DAYS[:b + 1])
        elif part[:3] in DAYS:
            found.add(part[:3])
    return found or set(DAYS)


def _doc_line(d):
    bits = [str(d), d.department.name]
    if d.specialization:
        bits.append(d.specialization)
    line = " - ".join(bits)
    extra = []
    if d.available_days:
        extra.append(d.available_days)
    if d.timings:
        extra.append(d.timings)
    extra.append(f"fee ₹{d.consultation_fee:.0f}")
    return f"{line} ({', '.join(extra)})"


def _find_department(text):
    depts = list(Department.objects.filter(is_active=True))
    for d in depts:  # exact name or a main word of the name
        n = d.name.lower()
        if _word(text, n):
            return d
    for words, root in SYNONYMS.items():
        if any(_word(text, w) for w in words):
            for d in depts:
                if re.search(r"\b" + root, d.name.lower()):
                    return d
    for d in depts:
        for w in re.findall(r"[a-z]{5,}", d.name.lower()):
            if w not in STOP and _word(text, w):
                return d
    return None


def _find_doctor(text):
    for d in Doctor.objects.filter(is_active=True).select_related("user", "department"):
        names = [d.user.first_name.lower(), d.user.last_name.lower()]
        if any(len(n) >= 4 and n not in STOP and re.search(r"\b" + re.escape(n) + r"\b", text) for n in names):
            return d
    return None


def reply(text, links=None, chips=None):
    return {"reply": text, "links": links or [], "chips": chips or []}


def answer(user, role, message):
    text = _clean(message)[:300]
    hospital = getattr(settings, "HOSPITAL", {})
    base_chips = ["Departments", "Doctors available today", "Book an appointment", "Contact & timings"]
    if role == "patient":
        base_chips += ["My appointments", "My bills"]

    if not text:
        return reply("Please type a question, for example: \"Which doctors are in Cardiology?\"", chips=base_chips)

    # ---- personal data: patients only, always from their own records
    personal = _has(text, "my appointment", "my booking", "my bill", "my payment", "my record", "my prescription",
                    "my report", "next appointment", "upcoming")
    if personal:
        if role != "patient":
            return reply("Please log in to your patient account to see your own appointments, bills and records.",
                         links=[{"label": "Login", "url": reverse("login")}, {"label": "Register", "url": reverse("register")}],
                         chips=base_chips)
        patient = user.patient_profile
        if _has(text, "bill", "payment"):
            bills = Bill.objects.filter(appointment__patient=patient)
            pending = bills.filter(payment_status="PENDING")
            owed = pending.aggregate(t=Sum(F("consultation_fee") + F("other_charges")))["t"] or 0
            if not bills.exists():
                return reply("You have no bills yet.", chips=base_chips)
            return reply(f"You have {bills.count()} bill(s). {pending.count()} pending, total due ₹{owed:.0f}.",
                         links=[{"label": "Open my bills", "url": reverse("portal_bills")}], chips=base_chips)
        if _has(text, "record", "prescription", "report"):
            c = Consultation.objects.filter(appointment__patient=patient).select_related("appointment__doctor__user").order_by("-created_at").first()
            if not c:
                return reply("You have no consultation records yet. They appear after a doctor completes your visit.", chips=base_chips)
            msg = f"Your latest visit was on {c.appointment.date:%d %b %Y} with {c.appointment.doctor}."
            if c.diagnosis:
                msg += f"\nDiagnosis: {c.diagnosis}"
            if c.prescription:
                msg += f"\nPrescription: {c.prescription}"
            return reply(msg, links=[{"label": "All my records", "url": reverse("portal_records")}], chips=base_chips)
        appts = patient.appointments.filter(status="BOOKED", date__gte=timezone.localdate()).select_related("doctor__user", "doctor__department").order_by("date", "time")[:5]
        if not appts:
            return reply("You have no upcoming appointments.", links=[{"label": "Book an appointment", "url": reverse("portal_book")}], chips=base_chips)
        lines = [f"- {a.date:%a, %d %b} at {a.time:%I:%M %p} with {a.doctor} ({a.doctor.department.name})" for a in appts]
        return reply("Your upcoming appointments:\n" + "\n".join(lines),
                     links=[{"label": "My appointments", "url": reverse("portal_appointments")}], chips=base_chips)

    if re.fullmatch(r"(hi|hii|hello|hey|good (morning|afternoon|evening)|namaste)[ !.]*", text):
        return reply(f"Hello! I'm the {hospital.get('name', 'hospital')} assistant. Ask me about departments, doctors, fees, timings or booking.", chips=base_chips)
    if _has(text, "thank"):
        return reply("You're welcome! Anything else I can help with?", chips=base_chips)

    # ---- hospital info
    if _has(text, "emergency", "ambulance", "urgent") and not _find_department(text.replace("emergency", "")):
        return reply(f"For emergencies call {hospital.get('emergency', '108')} immediately, or come straight to our emergency department. It is open 24/7.",
                     chips=base_chips)
    # ---- a specific doctor
    doc = _find_doctor(text)
    if doc:
        msg = f"{doc} - {doc.department.name}"
        if doc.specialization:
            msg += f", {doc.specialization}"
        if doc.qualification:
            msg += f"\nQualification: {doc.qualification}"
        if doc.experience_years:
            msg += f"\nExperience: {doc.experience_years} years"
        msg += f"\nAvailable: {doc.available_days or 'ask reception'}" + (f", {doc.timings}" if doc.timings else "")
        msg += f"\nConsultation fee: ₹{doc.consultation_fee:.0f}"
        return reply(msg, links=[{"label": "View profile", "url": reverse("doctor_detail", args=[doc.pk])},
                                 {"label": "Book an appointment", "url": reverse("portal_book") if role == "patient" else reverse("register")}],
                     chips=base_chips)

    if _has(text, "contact", "phone", "call", "number", "address", "where", "location", "timing", "hours", "open", "email", "visiting"):
        return reply(f"Address: {hospital.get('address', '-')}\nPhone: {hospital.get('phone', '-')}\nEmergency: {hospital.get('emergency', '-')}\nEmail: {hospital.get('email', '-')}\nHours: {hospital.get('hours', '-')}",
                     links=[{"label": "Contact page", "url": reverse("contact")}], chips=base_chips)

    # ---- availability today / tomorrow
    if _has(text, "today", "tomorrow", "available", "availability", "now"):
        offset = 1 if "tomorrow" in text else 0
        day = DAYS[(timezone.localdate().weekday() + offset) % 7]
        dept = _find_department(text)
        qs = Doctor.objects.filter(is_active=True).select_related("user", "department")
        if dept:
            qs = qs.filter(department=dept)
        docs = [d for d in qs if day in _days_of(d)][:8]
        label = "tomorrow" if offset else "today"
        if not docs:
            return reply(f"I could not find doctors available {label}. Please call {hospital.get('phone', 'reception')}.", chips=base_chips)
        return reply(f"Doctors available {label}:\n" + "\n".join("- " + _doc_line(d) for d in docs),
                     links=[{"label": "All doctors", "url": reverse("doctors_public")}], chips=base_chips)

    # ---- a department (and its doctors)
    dept = _find_department(text)
    if dept:
        docs = list(dept.doctors.filter(is_active=True).select_related("user", "department"))
        msg = f"{dept.name}"
        if dept.description:
            msg += f": {dept.description}"
        if docs:
            msg += f"\n\nDoctors ({len(docs)}):\n" + "\n".join("- " + _doc_line(d) for d in docs)
        else:
            msg += "\n\nNo doctors are listed in this department yet."
        return reply(msg, links=[{"label": f"See {dept.name} doctors", "url": reverse("doctors_public") + f"?dept={dept.pk}"},
                                 {"label": "Department page", "url": reverse("department_detail", args=[dept.pk])}],
                     chips=base_chips)

    if _has(text, "department", "speciality", "specialty", "specialities", "services", "treatment"):
        names = list(Department.objects.filter(is_active=True).values_list("name", flat=True))
        return reply("Our departments:\n" + "\n".join("- " + n for n in names) if names else "Departments will be listed soon.",
                     links=[{"label": "View departments", "url": reverse("departments")}], chips=base_chips)

    if _has(text, "fee", "fees", "cost", "price", "charge", "charges"):
        docs = Doctor.objects.filter(is_active=True).select_related("user", "department").order_by("consultation_fee")
        if not docs:
            return reply("Fee details will be listed soon.", chips=base_chips)
        lo, hi = docs.first(), docs.last()
        return reply(f"Consultation fees range from ₹{lo.consultation_fee:.0f} to ₹{hi.consultation_fee:.0f}, depending on the doctor. Ask me about a specific doctor or department for the exact fee.",
                     links=[{"label": "Our doctors", "url": reverse("doctors_public")}], chips=base_chips)

    if _has(text, "book", "appointment", "register", "sign up", "signup", "schedule", "visit"):
        if role == "patient":
            return reply("You can book in under a minute: choose a doctor, date and time.",
                         links=[{"label": "Book an appointment", "url": reverse("portal_book")}], chips=base_chips)
        return reply("Create a free patient account, then choose a doctor, date and time to book online.",
                     links=[{"label": "Register", "url": reverse("register")}, {"label": "Login", "url": reverse("login")}], chips=base_chips)

    if _has(text, "doctor", "specialist", "dr "):
        n = Doctor.objects.filter(is_active=True).count()
        top = Doctor.objects.filter(is_active=True, is_featured=True).select_related("user", "department")[:5]
        msg = f"We have {n} doctors across {Department.objects.filter(is_active=True).count()} departments."
        if top:
            msg += "\n\nFeatured doctors:\n" + "\n".join("- " + _doc_line(d) for d in top)
        return reply(msg, links=[{"label": "All doctors", "url": reverse("doctors_public")}], chips=base_chips)

    return reply("Sorry, I did not understand that. I can help with departments, doctors, fees, availability, booking, contact details" +
                 (" and your own appointments and bills." if role == "patient" else "."), chips=base_chips)
