def get_role(user):
    """Return 'admin', 'receptionist', 'doctor', 'patient' or None."""
    if not user.is_authenticated:
        return None
    if user.is_superuser:
        return "admin"
    if user.groups.filter(name="Receptionist").exists():
        return "receptionist"
    if hasattr(user, "doctor"):
        return "doctor"
    if hasattr(user, "patient_profile"):
        return "patient"
    return None
