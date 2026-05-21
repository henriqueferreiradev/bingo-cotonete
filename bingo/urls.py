from .views import *


from django.urls import path

urlpatterns = [
    path('', identificacao, name='identificacao'),
    path('cartela/', cartela, name='cartela'),
    path('confirmacao/', confirmacao, name='confirmarcao'),
    path('resultado/', resultado, name='resultado'),
    path('apuracao/', apuracao, name='apuracao'),
    
    path('cartela/salvar/', salvar_cartela, name='salvar_cartela'),
    path('cartela/conferir/', conferir_cartela, name='conferir_cartela'),
    path('resultado/salvar-vencedor/', salvar_vencedor, name='salvar_vencedor'),
    ]