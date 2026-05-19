import json

from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from allauth.socialaccount.models import SocialAccount
from .models import Cartela, Apuracao

ITENS = [
{'id': 1,  'num': '01', 'nome': 'GTA VI gameplay'},
{'id': 2,  'num': '02', 'nome': 'Novo Resident Evil'},
{'id': 3,  'num': '03', 'nome': 'Novo jogo da FromSoftware'},
{'id': 4,  'num': '04', 'nome': 'Remake de clássico (Silent Hill / Metal Gear)'},
{'id': 5,  'num': '05', 'nome': 'Novo God of War'},
{'id': 6,  'num': '06', 'nome': 'Novo jogo da Naughty Dog'},
{'id': 7,  'num': '07', 'nome': 'Novo jogo da Xbox Game Studios'},
{'id': 8,  'num': '08', 'nome': 'Novo jogo da PlayStation Studios'},
{'id': 9,  'num': '09', 'nome': "Novo Assassin's Creed"},
{'id': 10, 'num': '10', 'nome': 'Novo RPG gigante estilo Skyrim'},
{'id': 11, 'num': '11', 'nome': 'The Witcher 4 novidades'},
{'id': 12, 'num': '12', 'nome': 'Novo Cyberpunk (expansão ou sequência)'},
{'id': 13, 'num': '13', 'nome': 'Novo Call of Duty'},
{'id': 14, 'num': '14', 'nome': 'Novo Battlefield'},
{'id': 15, 'num': '15', 'nome': 'Novo Monster Hunter'},
{'id': 16, 'num': '16', 'nome': 'Novo jogo da franquia Final Fantasy'},
{'id': 17, 'num': '17', 'nome': 'Continuação de jogo indie famoso'},
{'id': 18, 'num': '18', 'nome': 'Novo jogo de super-herói (Marvel/DC)'},
{'id': 19, 'num': '19', 'nome': 'Bloodborne remaster/remake'},
{'id': 20, 'num': '20', 'nome': 'Hollow Knight: Silksong aparece'},
{'id': 21, 'num': '21', 'nome': 'Half-Life 3 (clássico impossível)'},
{'id': 22, 'num': '22', 'nome': 'Novo jogo do Hideo Kojima'},
{'id': 23, 'num': '23', 'nome': 'Novo BioShock'},
{'id': 24, 'num': '24', 'nome': 'Novo Tomb Raider'},
{'id': 25, 'num': '25', 'nome': 'Novo Prince of Persia'},
{'id': 26, 'num': '26', 'nome': 'Novo Splinter Cell'},
{'id': 27, 'num': '27', 'nome': 'Nova IP AAA (jogo totalmente novo)'},
{'id': 28, 'num': '28', 'nome': 'Jogo exclusivo anunciado (PlayStation ou Xbox)'},
{'id': 29, 'num': '29', 'nome': 'Jogo multiplayer live service'},
{'id': 30, 'num': '30', 'nome': 'Indie com potencial de viralizar'},
]

ITEM_IDS_VALIDOS = {item['id'] for item in ITENS}


def pegar_imagem_perfil(user):
    try:
        social = SocialAccount.objects.get(user=user, provider='discord')
        discord_id = social.extra_data['id']
        avatar_hash = social.extra_data.get('avatar')
        if not avatar_hash:
            return None
        return f"https://cdn.discordapp.com/avatars/{discord_id}/{avatar_hash}.png"
    except SocialAccount.DoesNotExist:
        return None


def identificacao(request):
    return render(request, 'bingo/identificacao.html')


@login_required(login_url='/')
def cartela(request):
    if request.user.is_staff:
        if Apuracao.get():
            return redirect('/resultado/')
        return redirect('/apuracao/')
    if hasattr(request.user, 'cartela'):
        return redirect('/confirmacao/')
    return render(request, 'bingo/cartela.html', {'itens': ITENS})


@login_required(login_url='/')
def confirmacao(request):
    if not hasattr(request.user, 'cartela'):
        return redirect('/cartela/')

    cartela = request.user.cartela
    itens_selecionados = [item for item in ITENS if item['id'] in cartela.items]
    avatar_url = pegar_imagem_perfil(request.user)
    apuracao_realizada = Apuracao.objects.exists()
    return render(request, 'bingo/confirmacao.html', {
        'itens': itens_selecionados,
        'avatar_url': avatar_url,
        'apuracao_realizada': apuracao_realizada,
    })


@login_required(login_url='/')
@require_POST
def salvar_cartela(request):
    if request.user.is_staff:
        return HttpResponseBadRequest('Staff não pode salvar cartela.')

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest('JSON inválido.')

    itens_selecionados = data.get('items', [])
    if not isinstance(itens_selecionados, list):
        return HttpResponseBadRequest('items deve ser uma lista.')
    itens_selecionados = [i for i in itens_selecionados if i in ITEM_IDS_VALIDOS]
    if len(itens_selecionados) != 15:
        return HttpResponseBadRequest('Selecione exatamente 15 itens válidos.')

    cartela, _ = Cartela.objects.get_or_create(user=request.user)
    cartela.items = itens_selecionados
    cartela.save()
    return redirect('confirmarcao')


@login_required(login_url='/')
@require_POST
def conferir_cartela(request):
    if not request.user.is_staff:
        return JsonResponse({'erro': 'Acesso negado.'}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest('JSON inválido.')

    numeros_vencedores = data.get('items', [])
    if not isinstance(numeros_vencedores, list):
        return HttpResponseBadRequest('items deve ser uma lista.')
    numeros_vencedores = [i for i in numeros_vencedores if i in ITEM_IDS_VALIDOS]
    if len(numeros_vencedores) != 15:
        return HttpResponseBadRequest('Selecione exatamente 15 itens válidos.')

    Apuracao.salvar(numeros_vencedores)

    return JsonResponse({'redirect': '/resultado/'})


def resultado(request):
    apuracao = Apuracao.get()
    if not apuracao:
        return render(request, 'bingo/resultado.html', {
            'resultados_json': json.dumps([]),
            'escolhas_json': json.dumps([]),
        })

    numeros_vencedores = apuracao.escolhas
    resultado = []
    for cartela in Cartela.objects.select_related('user').all():
        iguais = set(numeros_vencedores) & set(cartela.items)
        resultado.append({
            "jogador": cartela.user.username,
            "total_iguais": len(iguais),
            "avatar_url": pegar_imagem_perfil(cartela.user),
        })

    resultado.sort(key=lambda x: x['total_iguais'], reverse=True)

    return render(request, 'bingo/resultado.html', {
        'resultados_json': json.dumps(resultado),
        'escolhas_json': json.dumps(numeros_vencedores),
    })


@login_required(login_url='/')
def apuracao(request):
    if not request.user.is_staff:
        return redirect('/')
    return render(request, 'bingo/apuracao.html', {'itens': ITENS})
