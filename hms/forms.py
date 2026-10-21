from django import forms
from django.contrib.auth.models import Group, User
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone

from .models import (
    Appointment,
    Bill,
    ContactMessage,
    Consultation,
    Department,
    Doctor,
    HeroSlide,
    Patient,
    Room,
    RoomBooking,
    Testimonial,
)


class DateInput(forms.DateInput):
    input_type = "date"

    def __init__(self, **kwargs):
        kwargs.setdefault("format", "%Y-%m-%d")
        super().__init__(**kwargs)


class TimeInput(forms.TimeInput):
    input_type = "time"

    def __init__(self, **kwargs):
        kwargs.setdefault("format", "%H:%M")
        super().__init__(**kwargs)


class PatientForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = ["name", "date_of_birth", "gender", "phone", "address", "blood_group", "allergies"]
        widgets = {
            "date_of_birth": DateInput(),
            "address": forms.Textarea(attrs={"rows": 2}),
            "allergies": forms.Textarea(attrs={"rows": 2}),
        }

    def clean_date_of_birth(self):
        dob = self.cleaned_data["date_of_birth"]
        if dob > timezone.localdate():
            raise forms.ValidationError("Date of birth cannot be in the future.")
        return dob


class PatientProfileForm(forms.ModelForm):
    """Fields a patient may edit about themselves."""

    class Meta:
        model = Patient
        fields = ["phone", "address", "blood_group", "allergies"]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 2}),
            "allergies": forms.Textarea(attrs={"rows": 2}),
        }


class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ["patient", "doctor", "date", "time", "reason"]
        widgets = {"date": DateInput(), "time": TimeInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["doctor"].queryset = Doctor.objects.filter(is_active=True).select_related("user", "department")
        self.fields["doctor"].label_from_instance = lambda d: f"{d} - {d.department}"

    def clean_date(self):
        d = self.cleaned_data["date"]
        if d < timezone.localdate():
            raise forms.ValidationError("Appointment date cannot be in the past.")
        return d


class PortalAppointmentForm(AppointmentForm):
    """Used by patients: the patient is taken from the logged-in user."""

    class Meta(AppointmentForm.Meta):
        fields = ["doctor", "date", "time", "reason"]


class ConsultationForm(forms.ModelForm):
    class Meta:
        model = Consultation
        fields = ["symptoms", "diagnosis", "prescription", "notes"]
        widgets = {f: forms.Textarea(attrs={"rows": 3}) for f in fields}


class BillForm(forms.ModelForm):
    class Meta:
        model = Bill
        fields = ["consultation_fee", "other_charges", "description", "payment_status"]


class RegisterForm(forms.Form):
    username = forms.CharField(max_length=150)
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput)
    name = forms.CharField(label="Full name", max_length=150)
    date_of_birth = forms.DateField(widget=DateInput())
    gender = forms.ChoiceField(choices=Patient.GENDER_CHOICES)
    phone = forms.CharField(max_length=20)

    def clean_username(self):
        username = self.cleaned_data["username"]
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def clean_date_of_birth(self):
        dob = self.cleaned_data["date_of_birth"]
        if dob > timezone.localdate():
            raise forms.ValidationError("Date of birth cannot be in the future.")
        return dob

    def clean(self):
        data = super().clean()
        p1, p2 = data.get("password1"), data.get("password2")
        if p1 and p2:
            if p1 != p2:
                self.add_error("password2", "Passwords do not match.")
            else:
                try:
                    validate_password(p1)
                except forms.ValidationError as e:
                    self.add_error("password1", e)
        return data


class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ["name", "email", "phone", "subject", "message"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Your name"}),
            "email": forms.EmailInput(attrs={"placeholder": "you@example.com"}),
            "phone": forms.TextInput(attrs={"placeholder": "Phone (optional)"}),
            "subject": forms.TextInput(attrs={"placeholder": "How can we help?"}),
            "message": forms.Textarea(attrs={"rows": 5, "placeholder": "Write your message"}),
        }


class DoctorProfileForm(forms.ModelForm):
    """Fields a doctor may edit about themselves (including their website photo)."""

    class Meta:
        model = Doctor
        fields = ["photo", "gender", "qualification", "experience_years", "bio", "available_days", "timings", "phone"]
        widgets = {"bio": forms.Textarea(attrs={"rows": 4})}


# ------------------------------------------------ website manager (admin)

IMG = {"accept": "image/*"}


class DepartmentForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.initial["icon"] = ""  # blank: the icon is chosen automatically from the name

    class Meta:
        model = Department
        fields = ["name", "icon", "description", "services", "image", "display_order", "is_active"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "services": forms.Textarea(attrs={"rows": 6, "placeholder": "One service per line"}),
            "image": forms.FileInput(attrs=IMG),
        }


class HeroSlideForm(forms.ModelForm):
    class Meta:
        model = HeroSlide
        fields = ["badge", "title", "subtitle", "image", "button_text", "button_link",
                  "second_button_text", "second_button_link", "display_order", "is_active"]
        widgets = {"image": forms.FileInput(attrs=IMG), "subtitle": forms.Textarea(attrs={"rows": 2})}


class TestimonialForm(forms.ModelForm):
    rating = forms.TypedChoiceField(choices=[(i, f"{i} star{'s' if i > 1 else ''}") for i in range(5, 0, -1)], coerce=int)

    class Meta:
        model = Testimonial
        fields = ["name", "designation", "rating", "message", "is_active"]
        widgets = {"message": forms.Textarea(attrs={"rows": 4})}


class DoctorManageForm(forms.ModelForm):
    """Add or edit a doctor in one form. A new doctor's login account is created together with the profile."""

    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150, required=False)
    username = forms.CharField(max_length=150, help_text="The doctor logs in with this username")
    password = forms.CharField(widget=forms.PasswordInput(render_value=False), help_text="At least 8 characters")

    field_order = ["first_name", "last_name", "username", "password", "gender", "department", "specialization",
                   "qualification", "experience_years", "photo", "bio", "available_days", "timings",
                   "consultation_fee", "phone", "is_featured", "is_active"]

    class Meta:
        model = Doctor
        exclude = ("user",)
        widgets = {"photo": forms.FileInput(attrs=IMG), "bio": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["department"].queryset = Department.objects.all()
        if self.instance.pk:
            del self.fields["username"]
            self.fields["password"].required = False
            self.fields["password"].label = "New password"
            self.fields["password"].help_text = "Leave blank to keep the current password"
            self.fields["first_name"].initial = self.instance.user.first_name
            self.fields["last_name"].initial = self.instance.user.last_name

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def clean_password(self):
        pw = self.cleaned_data.get("password")
        if pw:
            validate_password(pw)
        return pw

    def save(self, commit=True):
        d = self.cleaned_data
        doctor = super().save(commit=False)
        if doctor.pk:
            user = doctor.user
            user.first_name, user.last_name = d["first_name"], d.get("last_name", "")
            if d.get("password"):
                user.set_password(d["password"])
            user.save()
        else:
            doctor.user = User.objects.create_user(
                username=d["username"], password=d["password"],
                first_name=d["first_name"], last_name=d.get("last_name", ""),
            )
        doctor.save()
        return doctor


class ReceptionistForm(forms.ModelForm):
    """Add or edit a receptionist login."""

    password = forms.CharField(
        widget=forms.PasswordInput(render_value=False), required=False,
        help_text="At least 8 characters",
    )

    field_order = ["first_name", "last_name", "username", "password", "is_active"]

    class Meta:
        model = User
        fields = ["first_name", "last_name", "username", "is_active"]
        labels = {"is_active": "Active (can log in)"}
        help_texts = {"username": "Used to log in", "is_active": "Untick to block this person from logging in"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        if self.instance.pk:
            self.fields["password"].label = "New password"
            self.fields["password"].help_text = "Leave blank to keep the current password"
        else:
            self.fields["password"].required = True

    def clean_password(self):
        pw = self.cleaned_data.get("password")
        if pw:
            validate_password(pw)
        return pw

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data.get("password"):
            user.set_password(self.cleaned_data["password"])
        user.save()
        user.groups.add(Group.objects.get_or_create(name="Receptionist")[0])
        return user


# ------------------------------------------------------------------ rooms

class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ["number", "room_type", "floor", "beds", "daily_charge", "is_active"]


class RoomBookingForm(forms.ModelForm):
    check_in_now = forms.BooleanField(required=False, label="Check the patient in now (arriving today)")

    class Meta:
        model = RoomBooking
        fields = ["patient", "room", "doctor", "check_in", "check_out", "reason"]
        widgets = {"check_in": DateInput(), "check_out": DateInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["patient"].queryset = Patient.objects.order_by("name")
        self.fields["room"].queryset = Room.objects.filter(is_active=True)
        self.fields["room"].label_from_instance = lambda r: f"{r} - {r.beds} bed{'s' if r.beds != 1 else ''}, \u20b9{r.daily_charge:.0f}/day"
        self.fields["doctor"].queryset = Doctor.objects.filter(is_active=True).select_related("user", "department")
        self.fields["doctor"].label_from_instance = lambda d: f"{d} - {d.department}"
        self.fields["doctor"].required = False

    def clean_check_in(self):
        d = self.cleaned_data["check_in"]
        if d < timezone.localdate():
            raise forms.ValidationError("Admission date cannot be in the past.")
        return d

    def clean(self):
        data = super().clean()
        start, end, room, patient = data.get("check_in"), data.get("check_out"), data.get("room"), data.get("patient")
        if not (start and end):
            return data
        if end <= start:
            self.add_error("check_out", "Discharge date must be after the admission date.")
            return data
        if room and room.free_beds(start, end) < 1:
            raise forms.ValidationError(f"{room} has no free bed between {start:%d %b} and {end:%d %b}. Choose another room or other dates.")
        if patient and RoomBooking.objects.filter(
            patient=patient, status__in=RoomBooking.ACTIVE, check_in__lt=end, check_out__gt=start
        ).exists():
            raise forms.ValidationError(f"{patient.name} already has a room booked for these dates.")
        return data
