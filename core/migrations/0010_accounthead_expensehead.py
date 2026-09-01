# Accounting master data: Account Heads + Expense Heads (created and seeded).

from django.db import migrations, models


ACCOUNT_HEADS = ["Income", "Expense", "Asset", "Liability", "Equity"]

EXPENSE_HEADS = [
    "Raw Material Import Cost",
    "Custom Duty & VAT",
    "Freight & Forwarding",
    "Packing Cost",
    "Salaries & Wages",
    "Festival Bonus",
    "Sales Incentive & Commission",
    "Recruitment Expenses",
    "Wholesaler & Retailer Incentive",
    "Utility Bill",
    "Telephone & Internet",
    "Mobile Allowance",
    "Office Stationery",
    "Cleaning & Housekeeping",
    "LC Charges",
    "Bank & Loan Interest",
    "Travel & Conveyance",
    "Fixed Asset Purchase & Maintenance",
    "Computer & IT Expenses",
    "Miscellaneous Expenses",
]


def seed(apps, schema_editor):
    AccountHead = apps.get_model("core", "AccountHead")
    ExpenseHead = apps.get_model("core", "ExpenseHead")
    for name in ACCOUNT_HEADS:
        AccountHead.objects.get_or_create(name=name, defaults={"active": True})
    for name in EXPENSE_HEADS:
        ExpenseHead.objects.get_or_create(name=name, defaults={"active": True})


def unseed(apps, schema_editor):
    AccountHead = apps.get_model("core", "AccountHead")
    ExpenseHead = apps.get_model("core", "ExpenseHead")
    AccountHead.objects.filter(name__in=ACCOUNT_HEADS).delete()
    ExpenseHead.objects.filter(name__in=EXPENSE_HEADS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0009_payout"),
    ]

    operations = [
        migrations.CreateModel(
            name="AccountHead",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True)),
                ("active", models.BooleanField(default=True)),
            ],
            options={
                "verbose_name_plural": "account heads",
                "ordering": ["name"],
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="ExpenseHead",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True)),
                ("active", models.BooleanField(default=True)),
            ],
            options={
                "verbose_name_plural": "expense heads",
                "ordering": ["name"],
                "abstract": False,
            },
        ),
        migrations.RunPython(seed, unseed),
    ]
