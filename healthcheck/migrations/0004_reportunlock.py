# Generated by Django 5.1.2 on 2024-10-28 19:46

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("healthcheck", "0003_healthcheckreport_updated_at"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReportUnlock",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("stripe_payment_id", models.CharField(max_length=320)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "report",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="healthcheck.healthcheckreport",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]