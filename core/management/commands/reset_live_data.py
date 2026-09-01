"""
One-time reset: wipe every business record (products, users, sales, shops,
payments, visits, attendance, ledger, offers, HR...) and replace the product
catalogue and login accounts with the real, production data the client
supplied. Master option-lists (Brand/Unit/Category/Segment/Area/... and
Company settings) are left alone except for get_or_create-ing the few entries
the new products need.

    python manage.py reset_live_data

This is destructive and irreversible — it is meant to be run exactly once
against the live database to move it from demo/seed data to real data.
"""
from django.contrib.auth import get_user_model
from django.db import transaction

from django.core.management.base import BaseCommand

from core.models import (
    Attendance,
    Brand,
    CashbackTxn,
    DamageRecord,
    Employee,
    LedgerEntry,
    Offer,
    OfferAccrual,
    Payment,
    Payout,
    Product,
    ProductCategory,
    ProductSegment,
    SalesOrder,
    Salesman,
    Shop,
    ShopReview,
    Target,
    Visit,
)

User = get_user_model()

# sku, name, segment, category, brand
PRODUCTS = [
    ("KM-2001", "Mark 2", "Personal Hygiene", "Economic", "KITE"),
    ("ORL-GS-001", "Golden Smile", "Personal Hygiene", "Premium", "Oralite"),
    ("ORL-SN-001", "Sensitive", "Personal Hygiene", "Economic", "Oralite"),
]

# email, name, id_number, role, password, is_admin
USERS = [
    ("sharafiorbittech@gmail.com", "Developer", "", "Manager", "Goo123!@#", True),
    ("amcagency.info@gmail.com", "Admin", "AMC-001", "Manager", "Admin@123", True),
    ("showkathasib.amc@gmail.com", "MD Showkat Osman Hasib", "AMC-002", "DSM", "Hasib@123", False),
    ("sayhanulislam.amc@gmail.com", "Rayhanul Islam", "AMC-003", "ASM", "Rayhanul@123", False),
    ("amcagency.hr@gmail.com", "MUSLEH UDDIN", "AMC-005", "Administrative", "Musleh@123", False),
]


class Command(BaseCommand):
    help = "Wipe demo/business data and load the real product catalogue + login accounts."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("Wiping existing business data...")
        # Children before parents where there's no cascading FK.
        for model in (
            Payment,
            CashbackTxn,
            OfferAccrual,
            Offer,
            Payout,
            ShopReview,
            LedgerEntry,
            Visit,
            Attendance,
            DamageRecord,
            Target,
            SalesOrder,   # cascades InvoiceLine
            Salesman,
            Shop,
            Employee,     # cascades PromotionHistory / EmployeeReward / EmployeePunishment
            Product,
        ):
            count, _ = model.objects.all().delete()
            self.stdout.write(f"  {model.__name__}: removed {count}")

        removed_users, _ = User.objects.all().delete()
        self.stdout.write(f"  {User.__name__}: removed {removed_users}")

        # Master entries the new products reference.
        for name in ["Personal Hygiene"]:
            ProductSegment.objects.get_or_create(name=name)
        for name in ["Economic", "Premium"]:
            ProductCategory.objects.get_or_create(name=name)
        for name in ["KITE", "Oralite"]:
            Brand.objects.get_or_create(name=name)

        for sku, name, segment, category, brand in PRODUCTS:
            Product.objects.update_or_create(sku=sku, defaults=dict(
                name=name, segment=segment, category=category, brand=brand,
                price=0, stock=0,
            ))

        for email, name, id_number, role, password, is_admin in USERS:
            user = User(
                email=email, name=name, id_number=id_number, role=role,
                branch="HQ", status="Active", is_staff=is_admin, is_superuser=is_admin,
            )
            user.set_password(password)
            user.save()

        self.stdout.write(self.style.SUCCESS(
            f"Done. {Product.objects.count()} products, {User.objects.count()} users."
        ))
