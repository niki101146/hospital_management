from django.contrib.auth import views as auth_views
from django.urls import path

from . import panel, views

urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("chatbot/", views.chatbot, name="chatbot"),
    path("about/", views.about, name="about"),
    path("departments/", views.departments, name="departments"),
    path("departments/<int:pk>/", views.department_detail, name="department_detail"),
    path("doctors/", views.doctors_public, name="doctors_public"),
    path("doctors/<int:pk>/", views.doctor_detail, name="doctor_detail"),
    path("contact/", views.contact, name="contact"),
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("register/", views.register, name="register"),

    # website manager (admin)
    path("panel/", panel.panel_home, name="panel_home"),
    path("panel/messages/<int:pk>/", panel.panel_message, name="panel_message"),
    path("panel/<str:kind>/", panel.panel_list, name="panel_list"),
    path("panel/<str:kind>/add/", panel.panel_edit, name="panel_add"),
    path("panel/<str:kind>/<int:pk>/edit/", panel.panel_edit, name="panel_edit"),
    path("panel/<str:kind>/<int:pk>/delete/", panel.panel_delete, name="panel_delete"),

    # staff
    path("patients/", views.patient_list, name="patient_list"),
    path("patients/new/", views.patient_edit, name="patient_create"),
    path("patients/<int:pk>/", views.patient_detail, name="patient_detail"),
    path("patients/<int:pk>/edit/", views.patient_edit, name="patient_edit"),
    path("appointments/", views.appointment_list, name="appointment_list"),
    path("appointments/new/", views.appointment_create, name="appointment_create"),
    path("appointments/<int:pk>/cancel/", views.appointment_cancel, name="appointment_cancel"),
    path("bills/", views.bill_list, name="bill_list"),
    path("bills/new/<int:appointment_id>/", views.bill_create, name="bill_create"),
    path("bills/<int:pk>/", views.bill_detail, name="bill_detail"),
    path("bills/<int:pk>/paid/", views.bill_mark_paid, name="bill_mark_paid"),

    # rooms (front desk)
    path("rooms/", views.room_list, name="room_list"),
    path("rooms/new/", views.room_edit, name="room_create"),
    path("rooms/<int:pk>/edit/", views.room_edit, name="room_edit"),
    path("room-bookings/", views.room_booking_list, name="room_booking_list"),
    path("room-bookings/new/", views.room_booking_create, name="room_booking_create"),
    path("room-bookings/availability/", views.room_availability, name="room_availability"),
    path("rooms/available/", views.room_available, name="room_available"),
    path("room-bookings/checkin/", views.room_checkin, name="room_checkin"),
    path("room-bookings/checkout/", views.room_checkout, name="room_checkout"),
    path("room-bookings/<int:pk>/receipt/", views.room_receipt, name="room_receipt"),
    path("room-bookings/<int:pk>/<str:action>/", views.room_booking_action, name="room_booking_action"),

    # fees collection (admin and doctor)
    path("fees/", views.fees_collection, name="fees"),

    # doctor
    path("doctor/appointments/", views.doctor_appointments, name="doctor_appointments"),
    path("doctor/profile/", views.doctor_profile, name="doctor_profile"),
    path("doctor/consultation/<int:appointment_id>/", views.consultation_edit, name="consultation_edit"),

    # patient portal
    path("portal/appointments/", views.portal_appointments, name="portal_appointments"),
    path("portal/book/", views.portal_book, name="portal_book"),
    path("portal/records/", views.portal_records, name="portal_records"),
    path("portal/bills/", views.portal_bills, name="portal_bills"),
    path("portal/profile/", views.portal_profile, name="portal_profile"),
]
