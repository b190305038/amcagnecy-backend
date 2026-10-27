"""
core_salesman (the `Salesman` model) is a legacy, standalone field-sales
roster — id/name/area/territory/target/achieved/commission — that predates
the Employee/HR directory and was never linked to a login account. It still
feeds the Reports page's "Target vs Achievement" and "Margin Report".

core_salesorder (the `SalesOrder` model) is the real invoice table. Every
order carries a free-text `sr` field (who sold it) that was typed by hand
before that field was locked to picking a real Employee — so a name can show
up on invoices/reports with no Employee login behind it at all.

Both are matched to the Employee directory BY NAME everywhere the app does
hierarchy/visibility/"who sold this" resolution (core/visibility.py,
sales_report.py's ASE Name, the Dashboard/Reports/Targets/Visits/Attendance
pickers) — so a name with no matching Employee just doesn't show up anywhere
an Employee is expected, even though real sales exist under it.

This command creates a real Employee login for every such orphaned name —
every Salesman row, and every free-text SalesOrder.sr that matches neither
an Employee nor a Salesman. It does NOT delete or modify Salesman rows (their
target/achieved/commission figures are still read by Reports) and does NOT
touch SalesOrder rows — once a matching Employee exists, every name-based
lookup elsewhere in the app picks it up on its own; nothing else needs
rewriting.

    python manage.py merge_salesmen_into_employees --dry-run
    python manage.py merge_salesmen_into_employees
    python manage.py merge_salesmen_into_employees --designation ASE

Idempotent: names that already have a matching Employee are skipped, so
re-running after onboarding someone properly via HR is harmless.
"""
import secrets
from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from core.models import Employee, SalesOrder, Salesman
from core.specs import next_employee_id


class Command(BaseCommand):
    help = "Create a real Employee login for every Salesman / SalesOrder.sr name with no matching Employee yet."

    def add_arguments(self, parser):
        parser.add_argument(
            "--designation",
            default="ASE",
            help="Designation to give each newly-created Employee (default: ASE).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List what WOULD be created, without writing anything.",
        )

    def handle(self, *args, **options):
        designation = options["designation"]
        dry_run = options["dry_run"]

        existing_names = {e.name.strip().lower() for e in Employee.objects.all()}

        salesmen = list(Salesman.objects.all())
        salesman_names = {s.name.strip().lower() for s in salesmen}
        order_names = set(SalesOrder.objects.exclude(sr="").values_list("sr", flat=True))
        extra_names = {n for n in order_names if n.strip() and n.strip().lower() not in existing_names | salesman_names}

        to_create: list[tuple[str | None, str]] = []
        for s in salesmen:
            if s.name.strip().lower() in existing_names:
                continue
            to_create.append((s.id, s.name.strip()))
        for n in sorted(extra_names):
            to_create.append((None, n.strip()))

        if not to_create:
            self.stdout.write(self.style.SUCCESS(
                "Every Salesman and SalesOrder.sr name already has a matching Employee. Nothing to do."
            ))
            return

        self.stdout.write(f"{len(to_create)} name(s) need a new Employee login:\n")
        for salesman_id, name in to_create:
            tag = f"Salesman id {salesman_id}" if salesman_id else "from SalesOrder.sr only, no Salesman row"
            self.stdout.write(f"  {name}  ({tag})")

        if dry_run:
            self.stdout.write(self.style.WARNING(
                "\nDry run — nothing created. Re-run without --dry-run to actually create these logins."
            ))
            return

        used_emails = {e.email.lower() for e in Employee.objects.all()}
        created_rows = []
        with transaction.atomic():
            for salesman_id, name in to_create:
                if salesman_id and not Employee.objects.filter(id_no=salesman_id).exists():
                    id_no = salesman_id
                else:
                    id_no = next_employee_id()

                base_slug = slugify(name).replace("-", ".") or "employee"
                email = f"{base_slug}@amcagency.local"
                n = 2
                while email.lower() in used_emails:
                    email = f"{base_slug}{n}@amcagency.local"
                    n += 1
                used_emails.add(email.lower())

                # Earliest recorded sale under this name, if any — a far
                # better guess at joining_date than "today" for someone who
                # has been selling for years under the legacy system.
                earliest = (
                    SalesOrder.objects.filter(sr__iexact=name).order_by("date").values_list("date", flat=True).first()
                )
                try:
                    joining = date.fromisoformat(earliest) if earliest else date.today()
                except ValueError:
                    joining = date.today()

                password = secrets.token_urlsafe(9)
                employee = Employee(
                    id_no=id_no, name=name, email=email, designation=designation,
                    status="Active", joining_date=joining,
                )
                employee.set_password(password)
                employee.save()
                created_rows.append((id_no, name, email, password))
                self.stdout.write(f"Created {id_no} — {name} <{email}>")

        self.stdout.write(self.style.SUCCESS(f"\nCreated {len(created_rows)} employee login(s)."))
        self.stdout.write(
            "Placeholder emails (@amcagency.local) and random passwords were generated — "
            "edit each one's real email from the HR page and reset their password before they "
            "actually need to log in. Starting now they'll correctly show up everywhere a real "
            "employee is expected (Dashboard, Reports, Targets, Visits, Attendance, the ASE/Sale-by "
            "name on past invoices and the MTD/YTD report)."
        )
        for id_no, name, email, password in created_rows:
            self.stdout.write(f"  {id_no}\t{name}\t{email}\tpassword={password}")
