# Generated by Django 5.1.2 on 2024-10-26 06:43

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("healthcheck", "0002_healthcheckreport_app_guid_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="healthcheckreport",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
    ]