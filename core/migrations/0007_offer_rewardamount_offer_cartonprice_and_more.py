# Offer: reward in taka (rewardAmount), auto carton price, Cartons default.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_remove_product_reorder'),
    ]

    operations = [
        migrations.AddField(
            model_name='offer',
            name='rewardAmount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=16),
        ),
        migrations.AddField(
            model_name='offer',
            name='cartonPrice',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=16),
        ),
        migrations.AlterField(
            model_name='offer',
            name='qtyUnit',
            field=models.CharField(blank=True, default='Cartons', max_length=20),
        ),
        migrations.AlterField(
            model_name='offer',
            name='reward',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
    ]
