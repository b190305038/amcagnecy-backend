"""
Remove one specific test invoice and everything that hangs off it — found
during a full database audit: Shop "SH-5001 / Test" (literally named
"Test"), SalesOrder "INV-24001" against it (implausible per-unit prices —
Tk 200,000 for a single "Golden Smile"), its Payment, its 4 LedgerEntry rows,
and Target "AAA" (a placeholder name, Tk 500,000, unrelated line items).

Dry run (lists what would be deleted, changes nothing):

    python manage.py clear_test_invoice

Actually delete it:

    python manage.py clear_test_invoice --confirm
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import LedgerEntry, Payment, SalesOrder, Shop, Target

ORDER_ID = "INV-24001"
SHOP_CODE = "SH-5001"
TARGET_ID = 2
TARGET_NAME = "AAA"


class Command(BaseCommand):
    help = "Remove the test invoice INV-24001, its Shop/Payment/Ledger rows, and Target 'AAA'."

    def add_arguments(self, parser):
        parser.add_argument("--confirm", action="store_true", help="Actually delete (default is dry run).")

    def handle(self, *args, **options):
        order = SalesOrder.objects.filter(id=ORDER_ID).first()
        shop = Shop.objects.filter(code=SHOP_CODE).first()
        payments = list(Payment.objects.filter(invoiceId=ORDER_ID))
        ledger = list(LedgerEntry.objects.filter(ref=ORDER_ID))
        target = Target.objects.filter(id=TARGET_ID, name=TARGET_NAME).first()

        self.stdout.write(f"SalesOrder {ORDER_ID}: {'found — Tk ' + str(order.amount) if order else 'not found'}")
        if order:
            for l in order.lines.all():
                self.stdout.write(f"    line: {l.sku} {l.name} x{l.qty} @ Tk {l.price}")
        self.stdout.write(f"Shop {SHOP_CODE}: {'found — ' + shop.name if shop else 'not found'}")
        self.stdout.write(f"Payment rows against {ORDER_ID}: {len(payments)}")
        self.stdout.write(f"LedgerEntry rows ref={ORDER_ID}: {len(ledger)}")
        self.stdout.write(f"Target #{TARGET_ID} '{TARGET_NAME}': {'found — Tk ' + str(target.target_value) if target else 'not found'}")

        if not options["confirm"]:
            self.stdout.write(self.style.WARNING("\nDry run only — nothing deleted. Re-run with --confirm to delete."))
            return

        with transaction.atomic():
            n, _ = Payment.objects.filter(invoiceId=ORDER_ID).delete()
            self.stdout.write(f"Deleted {n} Payment row(s)")
            n, _ = LedgerEntry.objects.filter(ref=ORDER_ID).delete()
            self.stdout.write(f"Deleted {n} LedgerEntry row(s)")
            n, _ = SalesOrder.objects.filter(id=ORDER_ID).delete()  # cascades InvoiceLine
            self.stdout.write(f"Deleted {n} SalesOrder (+ its lines)")
            n, _ = Shop.objects.filter(code=SHOP_CODE).delete()
            self.stdout.write(f"Deleted {n} Shop row(s)")
            n, _ = Target.objects.filter(id=TARGET_ID, name=TARGET_NAME).delete()
            self.stdout.write(f"Deleted {n} Target row(s)")

        self.stdout.write(self.style.SUCCESS("\nDone."))
