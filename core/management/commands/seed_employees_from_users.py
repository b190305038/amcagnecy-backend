"""
Backfill Employee Directory records from your EXISTING login accounts
(accounts.User) — the same people who show up under the old "Users & Roles"
list. Employee CRUD now owns login/role management (see EmployeeViewSet),
but any account that predates that change has a login with no matching
Employee row, so it never appears in HR > Employees.

    python manage.py seed_employees_from_users

Several people have two accounts (e.g. admin@amc.com and ahsan@amc.com are
both "Ahsan Habib" / Manager) — those are collapsed to ONE employee, keeping
the account whose email looks like a real personal/work address over a
generic one (admin@, manager@, area@, sr@, warehouse@, accounts@ are skipped
in favor of the named alternative when both exist for the same person).

IMPORTANT — unlike `seed_employees` (fully fictional demo people), this
command is backfilling records for accounts that may belong to real people.
It intentionally does NOT invent father's/mother's name, home district, or
permanent address — those are left blank for you to fill in with real
information via the Employee edit form. Only what the User model already
held (name, email, role/designation, join date) is carried over. Salary is
not tracked on User either; a placeholder by designation tier is used and
should be corrected per employee.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import User
from core.models import Employee
from core.specs import next_employee_id

# Login accounts to skip in favor of a same-person duplicate with a more
# personal-looking email. Add pairs here if your roster has other doubles.
PREFERRED_OVER = {
    "admin@amc.com": "ahsan@amc.com",
    "manager@amc.com": "nazmul@amc.com",
    "area@amc.com": "rashed@amc.com",
    "sr@amc.com": "imran@amc.com",
    "warehouse@amc.com": "yusuf@amc.com",
    "accounts@amc.com": "mahbub@amc.com",
}

# Placeholder salary by designation — there's no salary field on User, so
# this is only a starting point. Edit each employee with the real figure.
SALARY_BY_DESIGNATION = {
    "Manager": 120000,
    "DSM": 85000,
    "ASM": 65000,
    "ASE": 45000,
    "SE": 32000,
    "Support Staff": 25000,
    "Administrative": 40000,
}


class Command(BaseCommand):
    help = "Create Employee records from existing login accounts (accounts.User) that don't have one yet."

    def handle(self, *args, **options):
        skip_emails = set(PREFERRED_OVER.keys())
        existing_employee_emails = set(Employee.objects.values_list("email", flat=True))

        created = 0
        skipped_duplicate = 0
        skipped_existing = 0

        with transaction.atomic():
            for user in User.objects.exclude(email__in=skip_emails).order_by("date_joined"):
                if user.email in existing_employee_emails:
                    skipped_existing += 1
                    continue

                Employee.objects.create(
                    id_no=next_employee_id(),
                    name=user.name,
                    email=user.email,
                    designation=user.role,
                    joining_date=user.date_joined.date(),
                    salary=SALARY_BY_DESIGNATION.get(user.role, 0),
                )
                existing_employee_emails.add(user.email)
                created += 1
                self.stdout.write(f"Created employee for {user.name} <{user.email}> ({user.role})")

            skipped_duplicate = User.objects.filter(email__in=skip_emails).count()

        self.stdout.write(self.style.SUCCESS(
            f"\nCreated {created} employee(s) from existing login accounts. "
            f"Skipped {skipped_duplicate} duplicate account(s) and {skipped_existing} "
            f"account(s) that already had an employee record."
        ))
        self.stdout.write(self.style.WARNING(
            "Father's/mother's name, home district and permanent address were left "
            "blank — fill those in per employee via the Employee edit form. Salary "
            "was set to a placeholder by designation and should be corrected."
        ))
