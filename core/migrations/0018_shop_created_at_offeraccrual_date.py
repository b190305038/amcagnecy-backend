from django.db import migrations, models
from django.utils import timezone


def backfill_shop_created_at(apps, schema_editor):
    """Existing outlets predate this field — stamp them with 'now' (in code
    order, a few seconds apart) so they sort in a stable order below anything
    created after this migration runs, mirroring Product's createdAt backfill."""
    Shop = apps.get_model("core", "Shop")
    base = timezone.now()
    total = Shop.objects.count()
    for i, s in enumerate(Shop.objects.order_by("code")):
        s.createdAt = base - timezone.timedelta(seconds=(total - i))
        s.save(update_fields=["createdAt"])


def backfill_accrual_date(apps, schema_editor):
    """Existing accruals have no dated event of their own — use the last
    payout date when one exists (that IS a real date this record relates
    to); rows with neither are left blank and simply won't match a date
    filter until they're next edited."""
    OfferAccrual = apps.get_model("core", "OfferAccrual")
    for a in OfferAccrual.objects.all():
        if a.payout_last_date:
            a.date = a.payout_last_date
            a.save(update_fields=["date"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0017_salesman_area_territory_optional"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="shop",
            options={"ordering": ["-createdAt", "code"]},
        ),
        migrations.AddField(
            model_name="shop",
            name="createdAt",
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AddField(
            model_name="offeraccrual",
            name="date",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
        migrations.RunPython(backfill_shop_created_at, noop),
        migrations.RunPython(backfill_accrual_date, noop),
    ]
