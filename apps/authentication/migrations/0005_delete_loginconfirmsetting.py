# Generated by Django 3.1.12 on 2021-09-26 11:13

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0004_ssotoken'),
    ]

    operations = [
        migrations.DeleteModel(
            name='LoginConfirmSetting',
        ),
    ]