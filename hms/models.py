from django.conf import settings
from datetime import timedelta

from django.db import models
from django.db.models import Q
from django.utils import timezone


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    icon = models.CharField(
        max_length=8, blank=True, default="\u271A",
        help_text="Leave blank to choose one automatically from the department name (e.g. Dental gets a tooth)",
    )
    description = models.TextField(blank=True, help_text="Short text shown on department cards")
    services = models.TextField(blank=True, help_text="Treatments / services offered, one per line (shown on the department page)")
    image = models.ImageField(upload_to="departments/", blank=True, help_text="Optional banner photo for the department page")
    is_active = models.BooleanField(default=True, help_text="Untick to hide from the website")
    display_order = models.PositiveIntegerField(default=0, help_text="Lower numbers are shown first")

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name

    ICON_RULES = [
        (("dental", "dentist", "teeth", "tooth", "orthodon"), "\U0001F9B7"),
        (("cardio", "heart"), "\u2764\ufe0f"),
        (("neuro", "brain"), "\U0001F9E0"),
        (("ortho", "bone", "joint", "spine"), "\U0001F9B4"),
        (("pediatric", "paediatric", "child", "neonat"), "\U0001F476"),
        (("gyn", "obstet", "matern", "women"), "\U0001F931"),
        (("ophthal", "eye"), "\U0001F441\ufe0f"),
        (("otolaryn", "ear,", "ear nose", "ear and"), "\U0001F442"),
        (("derma", "skin", "cosmet"), "\u2728"),
        (("gastro", "liver", "digest", "hepat"), "\U0001F33F"),
        (("emergency", "trauma", "casualty", "critical", "icu"), "\U0001F691"),
        (("uro", "nephro", "kidney"), "\U0001F4A7"),
        (("psych", "mental", "counsel"), "\U0001F9D8"),
        (("onco", "cancer"), "\U0001F397\ufe0f"),
        (("pulmo", "lung", "respir", "chest"), "\U0001F32C\ufe0f"),
        (("endocrin", "diabet", "thyroid"), "\U0001FA78"),
        (("radio", "imaging", "x-ray", "scan"), "\U0001F52C"),
        (("patholog", "lab"), "\U0001F9EA"),
        (("physio", "rehab"), "\U0001F4AA"),
        (("pharm",), "\U0001F48A"),
        (("general", "physician", "medicine", "family"), "\U0001FA7A"),
    ]

    @classmethod
    def icon_for(cls, name):
        n = (name or "").lower()
        if n.strip() in ("ent", "e.n.t", "e.n.t."):
            return "\U0001F442"
        for words, icon in cls.ICON_RULES:
            if any(w in n for w in words):
                return icon
        return "\U0001F3E5"

    @property
    def symbol(self):
        """The icon to show: the one the admin typed, or one chosen automatically from the department name."""
        return self.icon if self.icon and self.icon != "\u271A" else self.icon_for(self.name)

    def save(self, *args, **kwargs):
        if not self.icon or self.icon == "\u271A":
            self.icon = self.icon_for(self.name)
        super().save(*args, **kwargs)

    @property
    def service_list(self):
        return [line.strip() for line in self.services.splitlines() if line.strip()]


class Doctor(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="doctors")
    GENDER_CHOICES = [("M", "Male"), ("F", "Female")]

    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, default="M", help_text="Chooses the default picture shown until a photo is uploaded")
    specialization = models.CharField(max_length=100, blank=True)
    qualification = models.CharField(max_length=150, blank=True, help_text="e.g. MBBS, MD (Cardiology)")
    experience_years = models.PositiveIntegerField(default=0, help_text="Years of experience")
    bio = models.TextField(blank=True, help_text="Short profile shown on the doctor's page")
    photo = models.ImageField(upload_to="doctors/", blank=True, help_text="Doctor photo. After choosing a file you can crop it to fit the cards (4:3)")
    phone = models.CharField(max_length=20, blank=True)
    consultation_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    available_days = models.CharField(max_length=100, blank=True, help_text="e.g. Mon - Sat")
    timings = models.CharField(max_length=100, blank=True, help_text="e.g. 10:00 AM - 2:00 PM")
    is_featured = models.BooleanField(default=False, help_text="Show on the home page")
    is_active = models.BooleanField(default=True, help_text="Untick to hide from the website and from booking")

    class Meta:
        ordering = ["user__first_name", "user__last_name"]

    def __str__(self):
        return f"Dr. {self.user.get_full_name() or self.user.username}"

    @property
    def placeholder(self):
        """Default picture (static path) shown while the doctor has not uploaded a photo."""
        return "hms/img/doctor-female.jpg" if self.gender == "F" else "hms/img/doctor-male.jpg"

    @property
    def initials(self):
        u = self.user
        letters = (u.first_name[:1] + u.last_name[:1]) or u.username[:2]
        return letters.upper()


class HeroSlide(models.Model):
    """A banner in the home page slider. Managed from the admin site."""

    badge = models.CharField(max_length=60, blank=True, help_text="Small label above the title")
    title = models.CharField(max_length=120)
    subtitle = models.CharField(max_length=255, blank=True)
    image = models.ImageField(upload_to="hero/", blank=True, help_text="Background photo (wide, about 1600x700). Leave empty for a plain colour banner")
    button_text = models.CharField(max_length=40, blank=True, default="Book an Appointment")
    button_link = models.CharField(max_length=200, blank=True, help_text="Page or address, e.g. /portal/book/ or /departments/")
    second_button_text = models.CharField(max_length=40, blank=True)
    second_button_link = models.CharField(max_length=200, blank=True)
    display_order = models.PositiveIntegerField(default=0, help_text="Lower numbers are shown first")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "id"]

    def __str__(self):
        return self.title


class Testimonial(models.Model):
    name = models.CharField(max_length=100)
    designation = models.CharField(max_length=100, blank=True, help_text="e.g. Patient, Cardiology")
    message = models.TextField()
    rating = models.PositiveSmallIntegerField(default=5, help_text="1 to 5 stars")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.rating}/5)"


class ContactMessage(models.Model):
    """A message sent from the website contact form; read it in the admin site."""

    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    subject = models.CharField(max_length=150)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name}: {self.subject}"


class Patient(models.Model):
    GENDER_CHOICES = [("M", "Male"), ("F", "Female"), ("O", "Other")]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="patient_profile",
        help_text="Set this if the patient has a login for the patient portal",
    )
    patient_id = models.CharField(max_length=20, unique=True, editable=False, blank=True)
    name = models.CharField(max_length=150)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    phone = models.CharField(max_length=20)
    address = models.TextField(blank=True)
    blood_group = models.CharField(max_length=5, blank=True)
    allergies = models.TextField(blank=True)
    registered_on = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.patient_id:
            self.patient_id = f"PID{self.pk:05d}"
            super().save(update_fields=["patient_id"])

    def __str__(self):
        return f"{self.patient_id} - {self.name}"


class Appointment(models.Model):
    STATUS_CHOICES = [
        ("BOOKED", "Booked"),
        ("COMPLETED", "Completed"),
        ("CANCELLED", "Cancelled"),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="appointments")
    doctor = models.ForeignKey(Doctor, on_delete=models.PROTECT, related_name="appointments")
    date = models.DateField()
    time = models.TimeField()
    reason = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="BOOKED")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date", "time"]
        constraints = [
            models.UniqueConstraint(
                fields=["doctor", "date", "time"],
                condition=~models.Q(status="CANCELLED"),
                name="unique_active_doctor_slot",
                violation_error_message="This doctor already has an appointment at that date and time.",
            )
        ]

    def __str__(self):
        return f"{self.patient.name} with {self.doctor} on {self.date} {self.time}"


class Consultation(models.Model):
    appointment = models.OneToOneField(Appointment, on_delete=models.CASCADE, related_name="consultation")
    symptoms = models.TextField(blank=True)
    diagnosis = models.TextField(blank=True)
    prescription = models.TextField(blank=True, help_text="Medicines, dosage, duration")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Consultation #{self.pk} - {self.appointment.patient.name}"


class Bill(models.Model):
    PAYMENT_CHOICES = [("PENDING", "Pending"), ("PAID", "Paid")]

    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, related_name="bills")
    consultation_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    other_charges = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    description = models.CharField(max_length=255, blank=True)
    payment_status = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default="PENDING")
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True, editable=False, help_text="When the bill was paid (used for fee collection reports)")

    def save(self, *args, **kwargs):
        if self.payment_status == "PAID" and not self.paid_at:
            self.paid_at = timezone.now()
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = list(kwargs["update_fields"]) + ["paid_at"]
        super().save(*args, **kwargs)

    @property
    def paid_when(self):
        """Date the money was collected. Older paid bills without paid_at fall back to the creation time."""
        return self.paid_at or self.created_at

    @property
    def total(self):
        return self.consultation_fee + self.other_charges

    def __str__(self):
        return f"Bill #{self.pk} - {self.appointment.patient.name} - {self.total}"


class Room(models.Model):
    """A ward or room with one or more beds that the front desk can book for patients."""

    TYPE_CHOICES = [
        ("GENERAL", "General ward"),
        ("SEMI", "Semi-private"),
        ("PRIVATE", "Private room"),
        ("DELUXE", "Deluxe room"),
        ("ICU", "ICU"),
    ]

    number = models.CharField(max_length=20, unique=True, help_text="e.g. 101 or ICU-2")
    room_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default="GENERAL")
    floor = models.CharField(max_length=30, blank=True, help_text="e.g. Ground floor, 2nd floor")
    beds = models.PositiveIntegerField(default=1, help_text="Number of beds in this room")
    daily_charge = models.DecimalField(max_digits=8, decimal_places=2, default=0, help_text="Charge per bed per day")
    is_active = models.BooleanField(default=True, help_text="Untick to stop new bookings (e.g. under maintenance)")

    class Meta:
        ordering = ["number"]

    def __str__(self):
        return f"Room {self.number} ({self.get_room_type_display()})"

    def blockers(self, start, end):
        """Active bookings that hold a bed of this room at some point between start (included) and end (excluded).
        Like a hotel, a booking only blocks its own dates; the room is free again from the check-out date."""
        today = timezone.localdate()
        qs = self.bookings.filter(status__in=RoomBooking.ACTIVE, check_in__lt=end).select_related("patient")
        return [b for b in qs if b.effective_end(today) > start]

    def booked_beds(self, start, end):
        return len(self.blockers(start, end))

    def free_beds(self, start, end):
        return max(self.beds - self.booked_beds(start, end), 0)


class RoomBooking(models.Model):
    STATUS_CHOICES = [
        ("BOOKED", "Booked"),
        ("ADMITTED", "Checked in"),
        ("DISCHARGED", "Discharged"),
        ("CANCELLED", "Cancelled"),
    ]
    ACTIVE = ("BOOKED", "ADMITTED")

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="room_bookings")
    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name="bookings")
    doctor = models.ForeignKey(Doctor, on_delete=models.SET_NULL, null=True, blank=True, related_name="room_bookings",
                               help_text="Doctor in charge (optional)")
    check_in = models.DateField(help_text="Admission date")
    check_out = models.DateField(help_text="Expected discharge date")
    reason = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="BOOKED")
    discharged_on = models.DateField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-check_in", "-id"]

    def __str__(self):
        return f"{self.patient.name} - {self.room} ({self.check_in} to {self.check_out})"

    def effective_end(self, today=None):
        """Date the bed is free again. A patient who is still checked in after the expected date keeps the bed today."""
        today = today or timezone.localdate()
        if self.status == "ADMITTED" and self.check_out <= today:
            return today + timedelta(days=1)
        return self.check_out

    @property
    def nights(self):
        end = self.discharged_on or self.check_out
        return max((end - self.check_in).days, 1)

    @property
    def estimated_charge(self):
        return self.nights * self.room.daily_charge
