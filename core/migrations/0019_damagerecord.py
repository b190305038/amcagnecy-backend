from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0018_shop_created_at_offeraccrual_date"),
    ]

    operations = [
        migrations.CreateModel(
            name="DamageRecord",
            fields=[
                ("id", models.CharField(max_length=40, primary_key=True, serialize=False)),
                ("date", models.CharField(max_length=20)),
                ("sku", models.CharField(max_length=40)),
                ("productName", models.CharField(blank=True, default="", max_length=200)),
                ("quantity", models.IntegerField(default=0)),
                ("unit_type", models.CharField(default="PCS", max_length=10)),
                (
                    "reason",
                    models.CharField(
                        choices=[
                            ("Damaged", "Damaged"),
                            ("Expired", "Expired"),
                            ("Broken in Transit", "Broken in Transit"),
                            ("Quality Issue", "Quality Issue"),
                            ("Other", "Other"),
                        ],
                        default="Damaged",
                        max_length=30,
                    ),
                ),
                ("loss_value", models.DecimalField(decimal_places=2, default=0, max_digits=16)),
                ("note", models.CharField(blank=True, default="", max_length=400)),
                ("reportedBy", models.CharField(blank=True, default="", max_length=200)),
                ("createdAt", models.DateTimeField(auto_now_add=True, null=True)),
            ],
            options={
                "ordering": ["-date", "-id"],
            },
        ),
    ]
