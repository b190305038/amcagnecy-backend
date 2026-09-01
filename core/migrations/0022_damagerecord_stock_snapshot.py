# Snapshot fields that make a damage write-off reversible: the exact number of
# pieces it removed from good stock, and the carton size in force at the time.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0021_target_employee"),
    ]

    operations = [
        migrations.AddField(
            model_name="damagerecord",
            name="damaged_pcs",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="damagerecord",
            name="pcs_per_carton",
            field=models.IntegerField(default=1),
        ),
    ]
