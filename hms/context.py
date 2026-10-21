from django.conf import settings
from django.urls import reverse

from .roles import get_role

# Patients and visitors see the public website layout; staff and doctors see the dashboard layout.
SITE_ROLES = (None, "patient")


def role(request):
    r = get_role(request.user)
    if r == "patient":
        book_url = reverse("portal_book")
    elif not request.user.is_authenticated:
        book_url = reverse("register")
    elif r in ("admin", "receptionist"):
        book_url = reverse("appointment_create")
    elif r == "doctor":
        book_url = reverse("doctor_appointments")
    else:
        book_url = reverse("home")
    return {
        "role": r,
        "base_template": "site/base.html" if r in SITE_ROLES else "hms/base.html",
        "hospital": getattr(settings, "HOSPITAL", {}),
        "book_url": book_url,
    }
