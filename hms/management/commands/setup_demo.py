from datetime import time, timedelta

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from django.utils import timezone

from hms.models import Appointment, Department, Doctor, HeroSlide, Patient, Room, Testimonial


FEMALE = {"drpriya", "drmeena", "drkavya", "drsana", "drlata", "drfarah"}  # demo doctors shown with the woman picture


class Command(BaseCommand):
    help = "Create roles and demo data (DEMO ONLY - passwords are weak on purpose)."

    def handle(self, *args, **options):
        for name in ("Receptionist", "Doctor", "Patient"):
            Group.objects.get_or_create(name=name)

        def make_user(username, password, first, last="", superuser=False):
            user, created = User.objects.get_or_create(
                username=username, defaults={"first_name": first, "last_name": last}
            )
            if created:
                user.set_password(password)
                if superuser:
                    user.is_staff = user.is_superuser = True
                user.save()
            return user

        make_user("admin", "admin123", "Admin", superuser=True)

        rec = make_user("reception", "reception123", "Reema", "Front Desk")
        rec.groups.add(Group.objects.get(name="Receptionist"))

        # name, icon, description, services (one per line)
        dept_data = [
            ("General Medicine", "\U0001FA7A", "Primary care for adults: fever, infections, diabetes, blood pressure and general health check-ups.",
             "Routine check-ups\nDiabetes care\nHypertension management\nFever and infections\nHealth screening packages"),
            ("Cardiology", "\u2764\ufe0f", "Heart care from prevention to treatment, with ECG, echo and stress testing.",
             "ECG and Echo\nTreadmill stress test\nHeart failure care\nBlood pressure clinic\nPreventive cardiology"),
            ("Pediatrics", "\U0001F476", "Gentle, complete care for babies, children and teenagers.",
             "Newborn care\nChild vaccination\nGrowth and development\nChildhood infections\nNutrition advice"),
            ("Orthopedics", "\U0001F9B4", "Treatment for bones, joints, sports injuries and fractures.",
             "Fracture care\nJoint replacement\nSports injuries\nArthritis treatment\nPhysiotherapy referral"),
            ("Neurology", "\U0001F9E0", "Diagnosis and treatment of brain, nerve and spine conditions.",
             "Headache and migraine\nEpilepsy care\nStroke rehabilitation\nNerve conduction tests\nMemory clinic"),
            ("Gynecology & Obstetrics", "\U0001F931", "Women's health, pregnancy care and safe delivery.",
             "Antenatal care\nNormal and C-section delivery\nFertility counselling\nPCOS treatment\nFamily planning"),
            ("Dermatology", "\u2728", "Skin, hair and nail care for all ages.",
             "Acne and pigmentation\nHair fall treatment\nAllergy and eczema\nSkin infections\nCosmetic dermatology"),
            ("ENT", "\U0001F442", "Ear, nose and throat care, including hearing tests.",
             "Hearing assessment\nSinus treatment\nTonsil and throat care\nVertigo clinic\nEndoscopy"),
            ("Ophthalmology", "\U0001F441\ufe0f", "Complete eye care and vision correction.",
             "Eye check-up\nCataract surgery\nGlaucoma screening\nSpectacle prescription\nRetina care"),
            ("Dental Care", "\U0001F9B7", "Preventive, restorative and cosmetic dentistry.",
             "Scaling and polishing\nRoot canal treatment\nBraces and aligners\nDental implants\nPediatric dentistry"),
            ("Gastroenterology", "\U0001F33F", "Digestive, liver and stomach disorders.",
             "Endoscopy\nLiver clinic\nAcidity and ulcers\nIBS treatment\nColonoscopy"),
            ("Emergency & Trauma", "\U0001F691", "24/7 emergency response with trained trauma and critical-care staff.",
             "24/7 casualty\nAmbulance support\nTrauma care\nCritical care unit\nPoison management"),
        ]
        depts = {}
        for order, (name, icon, desc, services) in enumerate(dept_data, start=1):
            d, created = Department.objects.get_or_create(
                name=name, defaults={"icon": icon, "description": desc, "services": services, "display_order": order}
            )
            if not created:  # fill only what is still empty so admin edits are never overwritten
                changed = False
                for field, value in (("description", desc), ("services", services)):
                    if not getattr(d, field):
                        setattr(d, field, value)
                        changed = True
                if d.icon in ("", "\u271A"):
                    d.icon, changed = icon, True
                if changed:
                    d.save()
            depts[name] = d

        # username, first, last, department, specialization, qualification, years, days, timings, fee, featured, bio
        doctor_data = [
            ("drsmith", "John", "Smith", "General Medicine", "Physician", "MBBS, MD", 14, "Mon - Sat", "9:00 AM - 1:00 PM", 300, True,
             "Dr. Smith provides comprehensive primary care and manages long-term conditions such as diabetes and hypertension."),
            ("drpriya", "Priya", "Nair", "Cardiology", "Cardiologist", "MBBS, MD, DM (Cardiology)", 18, "Mon, Wed, Fri", "10:00 AM - 3:00 PM", 600, True,
             "Dr. Priya focuses on preventive cardiology and heart failure management."),
            ("drarun", "Arun", "Kumar", "Pediatrics", "Pediatrician", "MBBS, DCH", 10, "Mon - Sat", "10:00 AM - 4:00 PM", 400, True,
             "Dr. Arun cares for newborns, children and teenagers with a gentle, family-first approach."),
            ("drmeena", "Meena", "Iyer", "Gynecology & Obstetrics", "Gynecologist", "MBBS, MS (OBG)", 16, "Mon - Fri", "11:00 AM - 5:00 PM", 500, True,
             "Dr. Meena supports women through pregnancy, delivery and every stage of women's health."),
            ("drrahul", "Rahul", "Menon", "Orthopedics", "Orthopedic Surgeon", "MBBS, MS (Ortho)", 12, "Tue, Thu, Sat", "9:00 AM - 2:00 PM", 550, True,
             "Dr. Rahul specialises in joint replacement and sports injuries."),
            ("drkavya", "Kavya", "Reddy", "Neurology", "Neurologist", "MBBS, MD, DM (Neurology)", 11, "Mon, Wed, Fri", "2:00 PM - 6:00 PM", 700, True,
             "Dr. Kavya treats epilepsy, migraine, stroke and movement disorders."),
            ("drsana", "Sana", "Khan", "Dermatology", "Dermatologist", "MBBS, MD (Dermatology)", 8, "Mon - Sat", "10:00 AM - 5:00 PM", 450, True,
             "Dr. Sana treats skin, hair and nail conditions for all ages."),
            ("drvikram", "Vikram", "Das", "ENT", "ENT Specialist", "MBBS, MS (ENT)", 13, "Mon - Sat", "10:00 AM - 2:00 PM", 400, False,
             "Dr. Vikram treats ear, nose and throat problems and hearing loss."),
            ("drlata", "Lata", "Pillai", "Ophthalmology", "Eye Surgeon", "MBBS, MS (Ophthalmology)", 15, "Mon - Fri", "9:00 AM - 1:00 PM", 450, False,
             "Dr. Lata is an experienced cataract and glaucoma surgeon."),
            ("drnaveen", "Naveen", "Joshi", "Dental Care", "Dentist", "BDS, MDS", 9, "Mon - Sat", "10:00 AM - 7:00 PM", 350, False,
             "Dr. Naveen offers preventive, restorative and cosmetic dental care."),
            ("drfarah", "Farah", "Sheikh", "Gastroenterology", "Gastroenterologist", "MBBS, MD, DM (Gastro)", 12, "Tue, Thu", "11:00 AM - 4:00 PM", 650, False,
             "Dr. Farah treats digestive and liver disorders."),
            ("dranil", "Anil", "Varma", "Emergency & Trauma", "Emergency Physician", "MBBS, MD (Emergency Medicine)", 10, "24 x 7", "Round the clock", 500, False,
             "Dr. Anil leads our emergency and trauma team."),
        ]
        doctors = []
        for username, first, last, dept, spec, qual, years, days, timings, fee, featured, bio in doctor_data:
            user = make_user(username, "doctor123", first, last)
            doc, created = Doctor.objects.get_or_create(
                user=user,
                defaults={"department": depts[dept], "specialization": spec, "qualification": qual,
                          "experience_years": years, "gender": "F" if username in FEMALE else "M", "available_days": days, "timings": timings, "bio": bio,
                          "phone": "9000000000", "consultation_fee": fee, "is_featured": featured},
            )
            if not created and username in FEMALE and doc.gender != "F":
                doc.gender = "F"
                doc.save(update_fields=["gender"])
            doctors.append(doc)

        if not HeroSlide.objects.exists():
            HeroSlide.objects.create(
                badge="Trusted healthcare, close to home", title="Your health, in caring hands.",
                subtitle="Book appointments online, meet experienced specialists and keep your medical records in one safe place.",
                button_text="Book an Appointment", button_link="/register/",
                second_button_text="Meet our Doctors", second_button_link="/doctors/", display_order=1)
            HeroSlide.objects.create(
                badge="12 departments, one roof", title="Expert specialists for every need.",
                subtitle="From cardiology to pediatrics, find the right doctor and the right treatment.",
                button_text="Explore Departments", button_link="/departments/",
                second_button_text="Find a Doctor", second_button_link="/doctors/", display_order=2)
            HeroSlide.objects.create(
                badge="Open 24 x 7", title="Emergency care, any time of day.",
                subtitle="Our trauma and critical-care team is always ready. Call 108 in an emergency.",
                button_text="Contact Us", button_link="/contact/", display_order=3)

        if not Testimonial.objects.exists():
            for name, desig, msg, rating in [
                ("Anita R.", "Patient, General Medicine", "Booking online was simple and the doctor explained everything clearly. I got my prescription in my account the same day.", 5),
                ("Ravi K.", "Patient, Cardiology", "Caring staff and very little waiting time. I felt safe and well looked after throughout my treatment.", 5),
                ("Suma P.", "Parent, Pediatrics", "The pediatric team was so gentle with my son. Clean, friendly and professional.", 4),
            ]:
                Testimonial.objects.create(name=name, designation=desig, message=msg, rating=rating)

        pu = make_user("patient1", "patient123", "Anita Raj")
        patient, _ = Patient.objects.get_or_create(
            user=pu,
            defaults={"name": "Anita Raj", "date_of_birth": "1998-05-14", "gender": "F", "phone": "9876543210",
                      "blood_group": "B+"},
        )
        walkin, _ = Patient.objects.get_or_create(
            name="Ravi Kumar",
            defaults={"date_of_birth": "1985-11-02", "gender": "M", "phone": "9123456780", "allergies": "Penicillin"},
        )

        today = timezone.localdate()
        Appointment.objects.get_or_create(
            patient=patient, doctor=doctors[0], date=today, time=time(10, 0), defaults={"reason": "Fever and cold"}
        )
        Appointment.objects.get_or_create(
            patient=walkin, doctor=doctors[1], date=today + timedelta(days=1), time=time(11, 30),
            defaults={"reason": "Chest discomfort"},
        )

        for number, rtype, floor, beds, charge in [
            ("101", "GENERAL", "Ground floor", 6, 800), ("102", "GENERAL", "Ground floor", 6, 800),
            ("201", "SEMI", "1st floor", 2, 1500), ("202", "SEMI", "1st floor", 2, 1500),
            ("301", "PRIVATE", "2nd floor", 1, 2500), ("302", "PRIVATE", "2nd floor", 1, 2500),
            ("401", "DELUXE", "3rd floor", 1, 4500), ("ICU-1", "ICU", "Ground floor", 4, 6000),
        ]:
            Room.objects.get_or_create(number=number, defaults={"room_type": rtype, "floor": floor, "beds": beds, "daily_charge": charge})

        self.stdout.write(self.style.SUCCESS("Demo data ready."))
        self.stdout.write("Logins:  admin/admin123  reception/reception123  drsmith/doctor123  patient1/patient123")
