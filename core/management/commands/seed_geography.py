"""
One-time load of the real Region / Area / Territory master data supplied by
the client. Idempotent (get_or_create / update_or_create), so re-running it
after adding more rows to the lists below is safe.

    python manage.py seed_geography
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Area, Region, Territory

REGIONS = ["Central-1", "Central-2", "Central-3", "West-1", "West-2", "East-1", "East-2"]

# name, code, region
AREAS = [
    ("Dhaka North", "CEN-1-DN-001", "Central-1"),
    ("Dhaka South", "CEN-2-DS-001", "Central-2"),
    ("Tangail", "CEN-3-TNL-001", "Central-3"),
]

# name, code, area
TERRITORIES = [
    ("Chawkbazar", "CN1-DN-CB00001", "Dhaka North"),
    ("Kaptan Bazar", "CN1-DN-KPB00001", "Dhaka North"),
    ("Mirpur-Mohammadpur", "CN1-DN-MP00001", "Dhaka North"),
    ("Savar", "CN1-DN-SV00001", "Dhaka North"),
    ("Hemayetpur", "CN1-DN-HMP00001", "Dhaka North"),
    ("Gulistan", "CN1-DN-GTN00001", "Dhaka North"),
    ("Manikganj", "CN1-DN-MJ00001", "Dhaka North"),
    ("Kawran Bazar", "CN1-DN-KB00001", "Dhaka North"),
    ("Narayanganj", "CN2-DS-NG00001", "Dhaka South"),
    ("Jatrabari", "CN2-DS-JTB00001", "Dhaka South"),
    ("Rampura-Malibagh", "CN2-DS-RMP00001", "Dhaka South"),
    ("Gulshan-Banani", "CN2-DS-GB00001", "Dhaka South"),
    ("Uttara", "CN2-DS-UTR00001", "Dhaka South"),
    ("Tongi-Gazipur", "CN2-DS-TG00001", "Dhaka South"),
]


class Command(BaseCommand):
    help = "Load the real Region/Area/Territory master data."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("Replacing existing geography (Region/Area/Territory) with the real data...")
        Territory.objects.all().delete()
        Area.objects.all().delete()
        Region.objects.all().delete()

        for name in REGIONS:
            Region.objects.get_or_create(name=name)
        self.stdout.write(f"Regions: {Region.objects.count()}")

        for name, code, region_name in AREAS:
            region = Region.objects.get(name=region_name)
            Area.objects.update_or_create(name=name, defaults={"code": code, "region": region})
        self.stdout.write(f"Areas: {Area.objects.count()}")

        for name, code, area_name in TERRITORIES:
            area = Area.objects.get(name=area_name)
            Territory.objects.update_or_create(name=name, area=area, defaults={"code": code})
        self.stdout.write(f"Territories: {Territory.objects.count()}")

        self.stdout.write(self.style.SUCCESS("Geography loaded."))
