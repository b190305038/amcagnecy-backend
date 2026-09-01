"""
Seed the HR module with demo employees (all 13 fields), a few Promotion
History / Reward / Punishment records, and matching login accounts so the
Employees Directory isn't empty and the designation-based role system can be
tried out end to end.

    python manage.py seed_employees          # insert/update demo employees
    python manage.py seed_employees --flush   # delete the demo employees first, then re-insert

Idempotent: safe to run more than once — employees are matched by id_no, and
existing rows are updated in place rather than duplicated. Every seeded
employee's login password is "demo123".
"""
from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import User
from core.models import Employee, EmployeePunishment, EmployeeReward, PromotionHistory

DEMO_PASSWORD = "demo123"

# id_no, name, email, father, mother, designation, dob, joining_date, salary,
# home_district, permanent_address
EMPLOYEES = [
    (
        "EMP-001", "Ahsan Habib", "ahsan.habib@amc.com",
        "Mokbul Habib", "Rahima Habib", "Manager",
        date(1985, 3, 12), date(2018, 1, 10), 120000,
        "Dhaka", "House 14, Road 7, Banani, Dhaka",
    ),
    (
        "EMP-002", "Nazmul Karim", "nazmul.karim@amc.com",
        "Aminul Karim", "Sultana Karim", "DSM",
        date(1988, 7, 22), date(2019, 4, 1), 85000,
        "Chattogram", "House 22, Agrabad, Chattogram",
    ),
    (
        "EMP-003", "Rashed Khan", "rashed.khan@amc.com",
        "Habibur Khan", "Nasrin Khan", "ASM",
        date(1990, 11, 5), date(2020, 6, 15), 65000,
        "Dhaka", "House 9, Uttara Sector 4, Dhaka",
    ),
    (
        "EMP-004", "Shahid Alam", "shahid.alam@amc.com",
        "Zakir Alam", "Ferdousi Alam", "ASE",
        date(1992, 2, 18), date(2021, 3, 1), 45000,
        "Sylhet", "House 5, Zindabazar, Sylhet",
    ),
    (
        "EMP-005", "Imran Hossain", "imran.hossain@amc.com",
        "Delwar Hossain", "Shirin Hossain", "SE",
        date(1995, 9, 9), date(2022, 8, 20), 32000,
        "Dhaka", "House 31, Mirpur 10, Dhaka",
    ),
    (
        "EMP-006", "Sabbir Ahmed", "sabbir.ahmed@amc.com",
        "Nurul Ahmed", "Kohinoor Ahmed", "SE",
        date(1996, 12, 30), date(2023, 1, 5), 30000,
        "Rajshahi", "House 18, Shaheb Bazar, Rajshahi",
    ),
    (
        "EMP-007", "Yusuf Ali", "yusuf.ali@amc.com",
        "Idris Ali", "Momtaz Begum", "Support Staff",
        date(1993, 5, 14), date(2021, 11, 1), 25000,
        "Dhaka", "House 3, Tejgaon Industrial Area, Dhaka",
    ),
    (
        "EMP-008", "Mahbub Hasan", "mahbub.hasan@amc.com",
        "Aziz Hasan", "Rokeya Hasan", "Administrative",
        date(1991, 4, 27), date(2020, 9, 12), 40000,
        "Khulna", "House 12, Khulna Sadar, Khulna",
    ),
]

# id, employee id_no, date, type, from_designation, to_designation, from_area,
# to_area, from_salary, to_salary, reason, approved_by, approved_date
PROMOTIONS = [
    (
        "PROMO-001", "EMP-003", date(2023, 1, 1), "Promotion",
        "ASE", "ASM", "Dhaka North", "Dhaka North",
        50000, 65000, "Strong regional sales performance",
        "Ahsan Habib", date(2022, 12, 20),
    ),
    (
        "PROMO-002", "EMP-004", date(2022, 6, 1), "Promotion",
        "SE", "ASE", "Sylhet", "Sylhet",
        35000, 45000, "Consistently exceeded quarterly targets",
        "Nazmul Karim", date(2022, 5, 18),
    ),
]

# id, employee id_no, date, type, description, amount, issued_by
REWARDS = [
    (
        "REWARD-001", "EMP-005", date(2024, 3, 15), "Performance Bonus",
        "Top sales officer for Q1 2024 — exceeded target by 32%.",
        15000, "Rashed Khan",
    ),
    (
        "REWARD-002", "EMP-003", date(2024, 7, 1), "Excellence Award",
        "Recognized for outstanding leadership during the monsoon supply disruption.",
        10000, "Ahsan Habib",
    ),
]

# id, employee id_no, date, severity, offense, description, action_taken,
# duration_days, fine_amount, issued_by
PUNISHMENTS = [
    (
        "PUNISH-001", "EMP-006", date(2024, 5, 10), "Warning",
        "Late attendance", "Reported late for 5 consecutive working days without notice.",
        "Verbal warning issued; attendance monitored for one month.",
        0, 0, "Nazmul Karim",
    ),
]


class Command(BaseCommand):
    help = "Seed demo Employees (HR module) with matching login accounts, plus sample promotion/reward/punishment records."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete the demo employees (and their linked logins) before re-inserting.",
        )

    def handle(self, *args, **options):
        with transaction.atomic():
            if options["flush"]:
                ids = [row[0] for row in EMPLOYEES]
                emails = [row[2] for row in EMPLOYEES]
                deleted, _ = Employee.objects.filter(id_no__in=ids).delete()
                User.objects.filter(email__in=emails).delete()
                self.stdout.write(self.style.WARNING(f"Flushed {deleted} existing demo HR row(s)."))

            employees_by_id = {}
            for (
                id_no, name, email, father, mother, designation, dob,
                joining_date, salary, home_district, permanent_address,
            ) in EMPLOYEES:
                employee, created = Employee.objects.update_or_create(
                    id_no=id_no,
                    defaults=dict(
                        name=name,
                        email=email,
                        fathers_name=father,
                        mothers_name=mother,
                        designation=designation,
                        date_of_birth=dob,
                        joining_date=joining_date,
                        salary=salary,
                        home_district=home_district,
                        permanent_address=permanent_address,
                    ),
                )
                employees_by_id[id_no] = employee

                user, user_created = User.objects.get_or_create(
                    email=email,
                    defaults=dict(name=name, role=designation, branch=home_district),
                )
                if user_created:
                    user.set_password(DEMO_PASSWORD)
                    user.save()
                else:
                    # Keep an existing login's role/name in sync with the employee record.
                    user.name = name
                    user.role = designation
                    user.save(update_fields=["name", "role"])

                verb = "Created" if created else "Updated"
                self.stdout.write(f"{verb} employee {id_no} — {name} ({designation})")

            for (
                promo_id, emp_id, promo_date, promo_type, from_desig, to_desig,
                from_area, to_area, from_salary, to_salary, reason, approved_by, approved_date,
            ) in PROMOTIONS:
                employee = employees_by_id.get(emp_id) or Employee.objects.filter(id_no=emp_id).first()
                if not employee:
                    continue
                PromotionHistory.objects.update_or_create(
                    id=promo_id,
                    defaults=dict(
                        employee=employee,
                        promotion_date=promo_date,
                        promotion_type=promo_type,
                        from_designation=from_desig,
                        to_designation=to_desig,
                        from_area=from_area,
                        to_area=to_area,
                        from_salary=from_salary,
                        to_salary=to_salary,
                        reason=reason,
                        approved_by=approved_by,
                        approved_date=approved_date,
                    ),
                )

            for reward_id, emp_id, reward_date, reward_type, description, amount, issued_by in REWARDS:
                employee = employees_by_id.get(emp_id) or Employee.objects.filter(id_no=emp_id).first()
                if not employee:
                    continue
                EmployeeReward.objects.update_or_create(
                    id=reward_id,
                    defaults=dict(
                        employee=employee,
                        date=reward_date,
                        reward_type=reward_type,
                        description=description,
                        amount=amount,
                        issued_by=issued_by,
                    ),
                )

            for (
                punish_id, emp_id, punish_date, severity, offense, description,
                action_taken, duration_days, fine_amount, issued_by,
            ) in PUNISHMENTS:
                employee = employees_by_id.get(emp_id) or Employee.objects.filter(id_no=emp_id).first()
                if not employee:
                    continue
                EmployeePunishment.objects.update_or_create(
                    id=punish_id,
                    defaults=dict(
                        employee=employee,
                        date=punish_date,
                        severity=severity,
                        offense=offense,
                        description=description,
                        action_taken=action_taken,
                        duration_days=duration_days,
                        fine_amount=fine_amount,
                        issued_by=issued_by,
                    ),
                )

        self.stdout.write(self.style.SUCCESS(
            f"\nSeeded {len(EMPLOYEES)} employees, {len(PROMOTIONS)} promotion(s), "
            f"{len(REWARDS)} reward(s), {len(PUNISHMENTS)} punishment(s)."
        ))
        self.stdout.write(f"Every seeded employee can log in with password: {DEMO_PASSWORD}")
