"""
Adds, in one step:

  * CompanySettings.shiftStart / shiftEnd — the attendance window (10:05 / 19:00)
  * Attendance.lateMinutes / earlyMinutes — how late in, how early out
  * SalesOrder.publicToken — capability token behind the invoice QR code

…and backfills tokens plus late/early figures for rows that already exist, so
old invoices get a working QR and past attendance is classified consistently
with new records rather than showing blank.
"""
from django.db import migrations, models


def backfill(apps, schema_editor):
    SalesOrder = apps.get_model("core", "SalesOrder")
    Attendance = apps.get_model("core", "Attendance")
    CompanySettings = apps.get_model("core", "CompanySettings")

    # Import the helpers directly — historical models have no custom methods.
    from core.attendance_rules import evaluate, to_minutes
    from core.models import new_public_token

    # Every existing invoice needs a token or its QR link 404s.
    for order in SalesOrder.objects.filter(publicToken="").only("pk"):
        SalesOrder.objects.filter(pk=order.pk).update(publicToken=new_public_token())

    company = CompanySettings.objects.first()
    start = getattr(company, "shiftStart", "") or "10:05"
    end = getattr(company, "shiftEnd", "") or "19:00"

    class Window:
        shiftStart = start
        shiftEnd = end

    for row in Attendance.objects.all().only("pk", "check_in", "check_out", "status"):
        status, late, early = evaluate(
            row.check_in, row.check_out, company=Window, current_status=row.status
        )
        Attendance.objects.filter(pk=row.pk).update(
            status=status, lateMinutes=late, earlyMinutes=early
        )

    # The old "Late" value is now spelled "Late Present"; evaluate() rewrites
    # rows that have a check-in time, this catches any that don't.
    Attendance.objects.filter(status="Late").update(status="Late Present")


def noop(apps, schema_editor):
    """Reversing only drops the columns; nothing to undo in data."""


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0014_add_offeraccrual_payout_last_date"),
    ]

    operations = [
        migrations.AddField(
            model_name="companysettings",
            name="shiftStart",
            field=models.CharField(default="10:05", max_length=5),
        ),
        migrations.AddField(
            model_name="companysettings",
            name="shiftEnd",
            field=models.CharField(default="19:00", max_length=5),
        ),
        migrations.AddField(
            model_name="attendance",
            name="lateMinutes",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="attendance",
            name="earlyMinutes",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="salesorder",
            name="publicToken",
            field=models.CharField(blank=True, db_index=True, default="", max_length=64),
        ),
        migrations.RunPython(backfill, noop),
    ]
