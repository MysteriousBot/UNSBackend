# Generated by Django 5.0.6 on 2025-02-07 00:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0004_alter_job_budget_alter_job_uuid'),
    ]

    operations = [
        migrations.CreateModel(
            name='Timesheet',
            fields=[
                ('uuid', models.UUIDField(editable=False, primary_key=True, serialize=False)),
                ('job_id', models.CharField(blank=True, max_length=50, null=True)),
                ('job_name', models.CharField(blank=True, max_length=255, null=True)),
                ('task_uuid', models.UUIDField(blank=True, null=True)),
                ('task_name', models.CharField(blank=True, max_length=255, null=True)),
                ('staff_uuid', models.UUIDField(blank=True, null=True)),
                ('staff_name', models.CharField(blank=True, max_length=255, null=True)),
                ('entry_date', models.DateTimeField(blank=True, null=True)),
                ('minutes', models.IntegerField(blank=True, null=True)),
                ('note', models.TextField(blank=True, null=True)),
                ('billable', models.BooleanField(default=False)),
                ('invoice_task_uuid', models.UUIDField(blank=True, null=True)),
            ],
        ),
    ]
