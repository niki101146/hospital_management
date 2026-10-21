from django import forms
from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.utils.html import format_html

from .models import (
    Appointment,
    Bill,
    ContactMessage,
    Consultation,
    Department,
    Doctor,
    HeroSlide,
    Patient,
    Testimonial,
)

admin.site.site_header = "Hospital Admin"
admin.site.site_title = "Hospital Admin"
admin.site.index_title = "Manage hospital and website"


def thumb(image, size=44, radius="8px"):
    if not image:
        return "-"
    return format_html(
        '<img src="{}" style="width:{}px;height:{}px;object-fit:cover;border-radius:{}">', image.url, size, size, radius
    )


# ------------------------------------------------------------ departments

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("icon", "name", "doctor_count", "display_order", "is_active")
    list_display_links = ("name",)
    list_editable = ("display_order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)
    fieldsets = (
        (None, {"fields": ("name", "icon", "description", "is_active", "display_order")}),
        ("Department page", {"fields": ("services", "image")}),
    )

    @admin.display(description="Doctors")
    def doctor_count(self, obj):
        return obj.doctors.count()


# --------------------------------------------------------------- doctors

class DoctorAdminForm(forms.ModelForm):
    """Add a doctor in one step: the login account is created together with the profile."""

    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150, required=False)
    username = forms.CharField(max_length=150, help_text="The doctor logs in with this name")
    password = forms.CharField(widget=forms.PasswordInput(render_value=False), help_text="At least 8 characters")

    class Meta:
        model = Doctor
        exclude = ("user",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:  # editing: names come from the linked user, no new account fields
            del self.fields["username"]
            del self.fields["password"]
            self.fields["first_name"].initial = self.instance.user.first_name
            self.fields["last_name"].initial = self.instance.user.last_name

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def clean(self):
        data = super().clean()
        if not self.instance.pk and data.get("password"):
            try:
                validate_password(data["password"])
            except forms.ValidationError as e:
                self.add_error("password", e)
        return data


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    form = DoctorAdminForm
    list_display = ("photo_thumb", "__str__", "department", "specialization", "experience_years",
                    "consultation_fee", "is_featured", "is_active")
    list_display_links = ("photo_thumb", "__str__")
    list_editable = ("is_featured", "is_active")
    list_filter = ("department", "is_active", "is_featured")
    search_fields = ("user__username", "user__first_name", "user__last_name", "specialization")
    list_select_related = ("user", "department")

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            account = ("Login account", {"fields": ("first_name", "last_name", "username", "password")})
        else:
            account = ("Name", {"fields": ("first_name", "last_name", "login_username")})
        return (
            account,
            ("Professional details", {"fields": ("department", "gender", "specialization", "qualification",
                                                  "experience_years", "bio", "photo")}),
            ("Availability and fee", {"fields": ("available_days", "timings", "consultation_fee", "phone")}),
            ("Website", {"fields": ("is_featured", "is_active")}),
        )

    def get_readonly_fields(self, request, obj=None):
        return ("login_username",) if obj else ()

    @admin.display(description="Login username")
    def login_username(self, obj):
        return obj.user.username if obj else "-"

    @admin.display(description="Photo")
    def photo_thumb(self, obj):
        return thumb(obj.photo, radius="50%")

    def save_model(self, request, obj, form, change):
        d = form.cleaned_data
        if change:
            user = obj.user
            user.first_name, user.last_name = d["first_name"], d.get("last_name", "")
            user.save(update_fields=["first_name", "last_name"])
        else:
            obj.user = User.objects.create_user(
                username=d["username"], password=d["password"],
                first_name=d["first_name"], last_name=d.get("last_name", ""),
            )
        super().save_model(request, obj, form, change)


# ------------------------------------------------------------ website

@admin.register(HeroSlide)
class HeroSlideAdmin(admin.ModelAdmin):
    list_display = ("title", "badge", "image_thumb", "display_order", "is_active")
    list_editable = ("display_order", "is_active")
    fieldsets = (
        (None, {"fields": ("badge", "title", "subtitle", "image", "display_order", "is_active")}),
        ("Buttons", {"fields": ("button_text", "button_link", "second_button_text", "second_button_link")}),
    )

    @admin.display(description="Image")
    def image_thumb(self, obj):
        return thumb(obj.image, size=60)


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ("name", "designation", "rating", "is_active", "created_at")
    list_editable = ("is_active",)


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "subject", "email", "phone", "created_at", "is_read")
    list_editable = ("is_read",)
    list_filter = ("is_read",)
    search_fields = ("name", "email", "subject", "message")
    readonly_fields = ("name", "email", "phone", "subject", "message", "created_at")

    def has_add_permission(self, request):
        return False


# ----------------------------------------------------------- hospital data

@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ("patient_id", "name", "gender", "phone", "registered_on")
    search_fields = ("patient_id", "name", "phone")
    list_filter = ("gender",)


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("patient", "doctor", "date", "time", "status")
    list_filter = ("status", "date", "doctor")
    search_fields = ("patient__name", "patient__patient_id")


@admin.register(Consultation)
class ConsultationAdmin(admin.ModelAdmin):
    list_display = ("appointment", "created_at")


@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = ("id", "appointment", "total", "payment_status", "created_at")
    list_filter = ("payment_status",)

