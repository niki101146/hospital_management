"""Website manager: the admin's own pages for departments, doctors, hero banners, testimonials and messages."""
from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.db.models.deletion import ProtectedError
from django.http import Http404
from django.templatetags.static import static
from django.shortcuts import get_object_or_404, redirect, render

from .decorators import role_required
from .forms import DepartmentForm, DoctorManageForm, HeroSlideForm, ReceptionistForm, TestimonialForm
from .models import ContactMessage, Department, Doctor, HeroSlide, Testimonial


def text(v):
    return {"t": "text", "v": v if v not in (None, "") else "-"}


def pill(on, yes="Active", no="Hidden"):
    return {"t": "pill", "on": on, "v": yes if on else no}


def image(obj_image, initials="", wide=False):
    return {"t": "img", "url": obj_image.url if obj_image else "", "init": initials, "wide": wide}


def stars(n):
    return text("\u2605" * n + "\u2606" * (5 - n))


PANELS = {
    "departments": {
        "model": Department, "form": DepartmentForm, "singular": "Department", "plural": "Departments",
        "hint": "Specialities shown on the Departments page and home page.",
        "columns": ["Image", "Name", "Doctors", "Order", "Status"],
        "qs": lambda: Department.objects.annotate(n=Count("doctors")),
        "cells": lambda o: [image(o.image, o.symbol, True), text(o.name), text(o.n), text(o.display_order), pill(o.is_active)],
        "search": ["name"],
    },
    "doctors": {
        "model": Doctor, "form": DoctorManageForm, "singular": "Doctor", "plural": "Doctors",
        "hint": "Doctors shown on the Our Doctors page. Each doctor also gets a login account.",
        "columns": ["Photo", "Name", "Department", "Experience", "Fee", "Featured", "Status"],
        "qs": lambda: Doctor.objects.select_related("user", "department"),
        "cells": lambda o: [{"t": "img", "url": o.photo.url if o.photo else static(o.placeholder), "init": o.initials, "wide": False}, text(str(o)), text(o.department.name),
                            text(f"{o.experience_years} yrs" if o.experience_years else "-"),
                            text(f"\u20b9{o.consultation_fee:.0f}"), pill(o.is_featured, "Yes", "No"), pill(o.is_active)],
        "search": ["user__first_name", "user__last_name", "specialization", "department__name"],
    },
    "slides": {
        "model": HeroSlide, "form": HeroSlideForm, "singular": "Hero banner", "plural": "Hero banners",
        "hint": "Banners at the top of the home page. With two or more active banners they change automatically every 5 seconds.",
        "columns": ["Image", "Title", "Order", "Status"],
        "qs": lambda: HeroSlide.objects.all(),
        "cells": lambda o: [image(o.image, "", True), text(o.title), text(o.display_order), pill(o.is_active)],
        "search": ["title"],
    },
    "testimonials": {
        "model": Testimonial, "form": TestimonialForm, "singular": "Testimonial", "plural": "Testimonials",
        "hint": "Patient reviews shown on the home page.",
        "columns": ["Name", "Rating", "Message", "Status"],
        "qs": lambda: Testimonial.objects.all(),
        "cells": lambda o: [text(o.name), stars(o.rating), text(o.message[:70] + ("..." if len(o.message) > 70 else "")), pill(o.is_active)],
        "search": ["name", "message"],
    },
    "receptionists": {
        "model": User, "form": ReceptionistForm, "singular": "Receptionist", "plural": "Receptionists",
        "hint": "Front-desk staff who register patients, book appointments and create bills.",
        "columns": ["Name", "Username", "Status"],
        "qs": lambda: User.objects.filter(groups__name="Receptionist").order_by("first_name"),
        "count": lambda: User.objects.filter(groups__name="Receptionist").count(),
        "cells": lambda o: [text(o.get_full_name() or o.username), text(o.username), pill(o.is_active)],
        "search": ["first_name", "last_name", "username"],
    },
    "messages": {
        "model": ContactMessage, "form": None, "singular": "Message", "plural": "Messages",
        "hint": "Messages sent from the website Contact page.",
        "columns": ["From", "Subject", "Received", "Status"],
        "qs": lambda: ContactMessage.objects.all(),
        "cells": lambda o: [text(o.name), text(o.subject), text(o.created_at.strftime("%d %b %Y, %I:%M %p")),
                            pill(not o.is_read, "New", "Read")],
        "search": ["name", "email", "subject", "message"],
    },
}


def get_panel(kind):
    conf = PANELS.get(kind)
    if not conf:
        raise Http404
    return conf


def conf_count(conf):
    return conf["count"]() if "count" in conf else conf["model"].objects.count()


def nav(active):
    items = []
    for key, conf in PANELS.items():
        count = conf_count(conf)
        if key == "messages":
            count = ContactMessage.objects.filter(is_read=False).count()
        items.append({"key": key, "label": conf["plural"], "count": count, "on": key == active})
    return items


def render_panel(request, template, active, **ctx):
    ctx.update({"nav": nav(active), "active": active})
    return render(request, template, ctx)


@role_required("admin")
def panel_home(request):
    stats = [{"label": c["plural"], "count": conf_count(c), "key": k} for k, c in PANELS.items() if k != "messages"]
    return render_panel(
        request, "panel/home.html", "home",
        stats=stats,
        unread=ContactMessage.objects.filter(is_read=False).count(),
        recent=ContactMessage.objects.all()[:5],
    )


@role_required("admin")
def panel_list(request, kind):
    conf = get_panel(kind)
    q = request.GET.get("q", "").strip()
    qs = conf["qs"]()
    if q:
        cond = Q()
        for f in conf["search"]:
            cond |= Q(**{f + "__icontains": q})
        qs = qs.filter(cond)
    rows = [{"obj": o, "cells": conf["cells"](o)} for o in qs]
    return render_panel(request, "panel/list.html", kind, conf=conf, kind=kind, rows=rows, q=q)


@role_required("admin")
def panel_edit(request, kind, pk=None):
    conf = get_panel(kind)
    if not conf["form"]:
        raise Http404
    obj = get_object_or_404(conf["qs"](), pk=pk) if pk else None
    form = conf["form"](request.POST or None, request.FILES or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        messages.success(request, f"{conf['singular']} \"{saved}\" saved. It is now live on the website.")
        return redirect("panel_list", kind=kind)
    return render_panel(request, "panel/form.html", kind, conf=conf, kind=kind, form=form, obj=obj)


@role_required("admin")
def panel_delete(request, kind, pk):
    conf = get_panel(kind)
    obj = get_object_or_404(conf["qs"](), pk=pk)
    if request.method == "POST":
        try:
            if kind == "doctors":
                obj.user.delete()  # removes the doctor profile and the login together
            else:
                obj.delete()
            messages.success(request, f"{conf['singular']} deleted.")
        except ProtectedError:
            messages.error(
                request,
                "This cannot be deleted because it is still in use (a department with doctors, or a doctor with "
                "appointments). Hide it instead by unticking Active.",
            )
        return redirect("panel_list", kind=kind)
    return render_panel(request, "panel/confirm_delete.html", kind, conf=conf, kind=kind, obj=obj)


@role_required("admin")
def panel_message(request, pk):
    msg = get_object_or_404(ContactMessage, pk=pk)
    if request.method == "POST":
        msg.is_read = not msg.is_read
        msg.save(update_fields=["is_read"])
        return redirect("panel_message", pk=pk)
    if not msg.is_read:
        msg.is_read = True
        msg.save(update_fields=["is_read"])
    return render_panel(request, "panel/message.html", "messages", conf=PANELS["messages"], kind="messages", obj=msg)
