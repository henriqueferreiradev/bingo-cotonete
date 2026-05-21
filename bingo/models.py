from django.db import models
from django.contrib.auth.models import User


class Cartela(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cartela')
    items = models.JSONField(default=list)
    criada_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Cartela de {self.user.username}"


class Apuracao(models.Model):
    """Singleton — só pode existir um registro. Representa o sorteio realizado."""
    escolhas = models.JSONField(default=list)
    realizada_em = models.DateTimeField(auto_now=True)
    vencedor_desempate = models.CharField(max_length=150, null=True, blank=True)

    def __str__(self):
        return f"Apuração em {self.realizada_em:%d/%m/%Y %H:%M}"

    @classmethod
    def get(cls):
        return cls.objects.first()

    @classmethod
    def salvar(cls, escolhas):
        cls.objects.all().delete()
        return cls.objects.create(escolhas=escolhas)