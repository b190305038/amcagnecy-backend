"""
Find (and optionally clear) a free-text name that shows up as a "Sale by" /
assigned-officer value somewhere, but doesn't belong to any real Employee —
e.g. a name typed into Shop.srName or SalesOrder.sr by hand before those
fields were backed by the Employee directory, which then lingers on reports
and invoices even though no such login exists.

Dry run (lists every match, changes nothing):

    python manage.py find_orphan_name "Md. Sharif"

Actually clear the matches (blanks srName/srEmail on Shop rows; leaves
SalesOrder.sr/srEmail alone since those are historical invoices — real past
sales that happened under that name, not safe to silently rewrite):

    python manage.py find_orphan_name "Md. Sharif" --clear-shops
"""
from django.core.management.base import BaseCommand, CommandError

from core.models import Dealer, Employee, SalesOrder, Salesman, Shop, Visit


class Command(BaseCommand):
    help = "Find (and optionally clear) a free-text name with no matching Employee."

    def add_arguments(self, parser):
        parser.add_argument("name", help="The name to search for (case-insensitive, exact match).")
        parser.add_argument(
            "--clear-shops",
            action="store_true",
            help="Blank Shop.srName/srEmail on every matching outlet (irreversible).",
        )

    def handle(self, *args, **options):
        name = options["name"].strip()
        if not name:
            raise CommandError("Give a name to search for.")

        is_real_employee = Employee.objects.filter(name__iexact=name).exists()
        self.stdout.write(
            self.style.WARNING(f"'{name}' IS a real Employee login.")
            if is_real_employee
            else self.style.SUCCESS(f"'{name}' is NOT a real Employee login — any match below is orphaned data.")
        )
        self.stdout.write("")

        shops = list(Shop.objects.filter(srName__iexact=name))
        self.stdout.write(f"Shops with srName = '{name}': {len(shops)}")
        for s in shops:
            self.stdout.write(f"  {s.code} — {s.name} (srEmail={s.srEmail!r})")

        orders = list(SalesOrder.objects.filter(sr__iexact=name))
        self.stdout.write(f"\nSalesOrder (invoices) with sr = '{name}': {len(orders)}")
        for o in orders[:20]:
            self.stdout.write(f"  {o.id} — {o.date} — {o.shop} — ৳{o.amount}")
        if len(orders) > 20:
            self.stdout.write(f"  ... and {len(orders) - 20} more")

        salesmen = list(Salesman.objects.filter(name__iexact=name))
        self.stdout.write(f"\nSalesman records named '{name}': {len(salesmen)}")
        for s in salesmen:
            self.stdout.write(f"  {s.id} — {s.name}")

        dealers = list(Dealer.objects.filter(ase__name__iexact=name))
        self.stdout.write(f"\nDealers with ASE = '{name}': {len(dealers)}")
        for d in dealers:
            self.stdout.write(f"  {d.code} — {d.name} (ase_id={d.ase_id})")

        visits = Visit.objects.filter(sr__iexact=name).count()
        self.stdout.write(f"\nVisit records logged under '{name}': {visits}")

        if options["clear_shops"]:
            if not shops:
                self.stdout.write(self.style.SUCCESS("\nNo Shop rows to clear."))
                return
            for s in shops:
                s.srName = ""
                s.srEmail = ""
            Shop.objects.bulk_update(shops, ["srName", "srEmail"])
            self.stdout.write(self.style.SUCCESS(f"\nCleared srName/srEmail on {len(shops)} shop(s)."))
        else:
            self.stdout.write(
                self.style.WARNING(
                    "\nDry run only — nothing changed. Re-run with --clear-shops to blank the "
                    "Shop.srName/srEmail matches above (re-assign each outlet to a real employee "
                    "afterward). SalesOrder/Visit rows are left alone on purpose — those are real "
                    "historical records, not safe to rewrite automatically."
                )
            )
