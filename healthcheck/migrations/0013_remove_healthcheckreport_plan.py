# Generated by Django 5.1.2 on 2024-12-21 23:19

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("healthcheck", "0012_healthcheckreport_healthcheck_subdoma_f62e37_idx"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="healthcheckreport",
            name="plan",
        ),
    ]