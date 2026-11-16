from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_split_full_name'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='full_name',
        ),
    ]
