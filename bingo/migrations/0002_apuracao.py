from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bingo', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Apuracao',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('escolhas', models.JSONField(default=list)),
                ('realizada_em', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
