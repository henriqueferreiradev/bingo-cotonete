from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bingo', '0002_apuracao'),
    ]

    operations = [
        migrations.AddField(
            model_name='apuracao',
            name='vencedor_desempate',
            field=models.CharField(blank=True, max_length=150, null=True),
        ),
    ]
