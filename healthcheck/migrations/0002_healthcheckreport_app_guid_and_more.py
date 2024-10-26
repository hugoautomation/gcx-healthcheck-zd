# Generated by Django 5.1.2 on 2024-10-26 06:13

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("healthcheck", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="healthcheckreport",
            name="app_guid",
            field=models.CharField(default="0", max_length=320),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="healthcheckreport",
            name="instance_guid",
            field=models.CharField(db_index=True, max_length=320),
        ),
        migrations.AlterField(
            model_name="healthcheckreport",
            name="plan",
            field=models.CharField(blank=True, max_length=320, null=True),
        ),
        migrations.AlterField(
            model_name="healthcheckreport",
            name="stripe_subscription_id",
            field=models.CharField(blank=True, max_length=320, null=True),
        ),
    ]
