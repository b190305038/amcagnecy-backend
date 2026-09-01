import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Area',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120, unique=True)),
                ('active', models.BooleanField(default=True)),
                ('zone', models.CharField(blank=True, default='', max_length=120)),
            ],
            options={
                'ordering': ['name'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Brand',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120, unique=True)),
                ('active', models.BooleanField(default=True)),
            ],
            options={
                'ordering': ['name'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='CompanySettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(default='A.M.C. Agency', max_length=200)),
                ('tagline', models.CharField(blank=True, default='', max_length=200)),
                ('logo', models.TextField(blank=True, default='')),
                ('address', models.CharField(blank=True, default='', max_length=400)),
                ('phone', models.CharField(blank=True, default='', max_length=60)),
                ('email', models.EmailField(blank=True, default='', max_length=254)),
                ('website', models.CharField(blank=True, default='', max_length=200)),
                ('currency', models.CharField(default='৳', max_length=8)),
                ('vatBin', models.CharField(blank=True, default='', max_length=60)),
                ('invoiceFooter', models.CharField(blank=True, default='', max_length=400)),
            ],
            options={
                'verbose_name_plural': 'company settings',
            },
        ),
        migrations.CreateModel(
            name='ProductCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120, unique=True)),
                ('active', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name_plural': 'product categories',
                'ordering': ['name'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ShopCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120, unique=True)),
                ('active', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name_plural': 'shop categories',
                'ordering': ['name'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Unit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('active', models.BooleanField(default=True)),
                ('name', models.CharField(max_length=40, unique=True)),
            ],
            options={
                'ordering': ['name'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Territory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120)),
                ('active', models.BooleanField(default=True)),
                ('area', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='territories', to='core.area')),
            ],
            options={
                'ordering': ['area__name', 'name'],
                'constraints': [models.UniqueConstraint(fields=('name', 'area'), name='unique_territory_per_area')],
            },
        ),
    ]
