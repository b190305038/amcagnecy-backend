# Payout: reimbursements paid to shops against accrued offer/cashback liability.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0008_seed_brands_units"),
    ]

    operations = [
        migrations.CreateModel(
            name="Payout",
            fields=[
                ("id", models.CharField(max_length=40, primary_key=True, serialize=False)),
                ("shop", models.CharField(max_length=200)),
                ("date", models.CharField(max_length=20)),
                ("amount", models.DecimalField(decimal_places=2, default=0, max_digits=16)),
                ("method", models.CharField(default="Cash", max_length=40)),
                ("offer", models.CharField(blank=True, default="", max_length=200)),
                ("note", models.CharField(blank=True, default="", max_length=400)),
            ],
            options={
                "ordering": ["-date", "-id"],
            },
        ),
    ]
