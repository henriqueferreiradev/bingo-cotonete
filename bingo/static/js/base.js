const checkboxes = document.querySelectorAll('.card-item-checkbox');
const count = document.getElementById('count');
const btn = document.getElementById('btn-confirmar');
const btnApurar = document.getElementById('btn-apurar')
const MAX = 15;
function atualizarBotoes() {
    const total = document.querySelectorAll('.card-item-checkbox:checked').length;

    if (count) count.textContent = total;
    if (btn) btn.disabled = total !== MAX;
    if (btnApurar) btnApurar.disabled = total !== MAX;
}
checkboxes.forEach(cb => {
    cb.addEventListener('change', () => {
        const marcados = document.querySelectorAll('.card-item-checkbox:checked').length;

        if (cb.checked && marcados > MAX) {
            cb.checked = false;
        }

        atualizarBotoes();
    });
});

atualizarBotoes();

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
if (btn) {
btn.addEventListener('click', async function () {
    console.log('Confirmar button clicked');
    const selectedItems = [...document.querySelectorAll('.card-item-checkbox:checked')].map(checkbox => parseInt(checkbox.value));

    console.log('Selected items:', selectedItems);

    try {
        const response = await fetch('/cartela/salvar/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({ items: selectedItems })
        })
        if (!response.ok) {
            throw new Error('Error saving cartela');
        }
    } catch (error) {
        console.error('Error saving cartela:', error);
    }
})
}

if (btnApurar) {
    btnApurar.addEventListener('click', async function () {
        const selectedItems = [...document.querySelectorAll('.card-item-checkbox:checked')]
            .map(checkbox => parseInt(checkbox.value));

        try {
            const response = await fetch('/cartela/conferir/', {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify({ items: selectedItems })
            });

            // se foi redirecionado para o login, navega o browser
            if (response.redirected) {
                window.location.href = response.url;
                return;
            }
            if (!response.ok) {
                console.error('Erro ao conferir:', response.status);
                return;
            }
            const data = await response.json();
            if (data.redirect) window.location.href = data.redirect;
        } catch (error) {
            console.error('Erro:', error);
        }
    });
}