# Seed the KITE & Oralite brands and the Carton & Piece stock units so they
# show up as options in the Product / Stock form dropdowns.

from django.db import migrations


BRANDS = ["KITE", "Oralite"]
UNITS = ["Carton", "Piece"]


def seed(apps, schema_editor):
    Brand = apps.get_model("core", "Brand")
    Unit = apps.get_model("core", "Unit")
    for name in BRANDS:
        Brand.objects.get_or_create(name=name, defaults={"active": True})
    for name in UNITS:
        Unit.objects.get_or_create(name=name, defaults={"active": True})


def unseed(apps, schema_editor):
    Brand = apps.get_model("core", "Brand")
    Unit = apps.get_model("core", "Unit")
    Brand.objects.filter(name__in=BRANDS).delete()
    Unit.objects.filter(name__in=UNITS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0007_offer_rewardamount_offer_cartonprice_and_more"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
