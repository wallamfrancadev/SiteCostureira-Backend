from __future__ import annotations

import hashlib
import logging
from decimal import Decimal
from typing import TypedDict

import requests as http
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

_ME_BASE = (
    'https://sandbox.melhorenvio.com.br'
    if getattr(settings, 'MELHOR_ENVIO_SANDBOX', True)
    else 'https://www.melhorenvio.com.br'
)
_CACHE_TTL = 86_400  # 24 horas


class OpcaoFrete(TypedDict):
    id: int
    transportadora: str
    servico: str
    preco: Decimal
    prazo_dias: int
    prazo_com_producao: int


def _consolidar_pacote(product_quantities: list[tuple]) -> dict:
    total_weight = sum(float(p.peso) * q for p, q in product_quantities)
    total_volume = sum(float(p.comprimento) * float(p.largura) * float(p.altura) * q for p, q in product_quantities)

    max_comprimento = max(float(p.comprimento) for p, _ in product_quantities)
    max_largura = max(float(p.largura) for p, _ in product_quantities)
    base_area = max_comprimento * max_largura
    altura_consolidada = total_volume / base_area if base_area > 0 else 10.0

    return {
        'weight': max(round(total_weight, 2), 0.1),
        'length': max(round(max_comprimento), 16),
        'width': max(round(max_largura), 11),
        'height': max(round(altura_consolidada), 2),
    }


def _cache_key(cep: str, pacote: dict) -> str:
    pacote_str = f"{pacote['weight']}{pacote['length']}{pacote['width']}{pacote['height']}"
    digest = hashlib.md5(pacote_str.encode()).hexdigest()[:12]
    return f'frete_{cep}_{digest}'


def _dev_opcoes(dias_adicionais: int) -> list[OpcaoFrete]:
    return [
        OpcaoFrete(id=1, transportadora='Correios', servico='PAC',
                   preco=Decimal('15.90'), prazo_dias=8,
                   prazo_com_producao=8 + dias_adicionais),
        OpcaoFrete(id=2, transportadora='Correios', servico='SEDEX',
                   preco=Decimal('35.50'), prazo_dias=3,
                   prazo_com_producao=3 + dias_adicionais),
        OpcaoFrete(id=7, transportadora='Jadlog', servico='.Package',
                   preco=Decimal('22.00'), prazo_dias=5,
                   prazo_com_producao=5 + dias_adicionais),
    ]


def _chamar_melhor_envio(cep_destino: str, pacote: dict, valor_seguro: Decimal) -> list[dict]:
    token = settings.MELHOR_ENVIO_TOKEN
    origin = settings.ORIGIN_POSTAL_CODE
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'User-Agent': 'App DetyCosureira contato@dety.com.br',
    }
    body = {
        'from': {'postal_code': origin, 'number': getattr(settings, 'ORIGIN_NUMBER', '')},
        'to': {'postal_code': cep_destino},
        'package': pacote,
        'options': {
            'insurance_value': float(valor_seguro),
            'receipt': False,
            'own_hand': False,
        },
    }
    resp = http.post(f'{_ME_BASE}/api/v2/me/shipment/calculate', json=body, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json()


def calcular_frete(cep_destino: str, product_quantities: list[tuple], valor_total: Decimal) -> list[OpcaoFrete]:
    dias_adicionais: int = getattr(settings, 'DIAS_ADICIONAIS_PRODUCAO', 2)

    if getattr(settings, 'ME_DEV_MODE', False) or not getattr(settings, 'MELHOR_ENVIO_TOKEN', ''):
        logger.info('Frete em modo dev — retornando opções simuladas.')
        return _dev_opcoes(dias_adicionais)

    pacote = _consolidar_pacote(product_quantities)
    key = _cache_key(cep_destino, pacote)
    cached = cache.get(key)
    if cached is not None:
        logger.debug('Cache hit frete key=%s', key)
        return cached

    try:
        raw = _chamar_melhor_envio(cep_destino, pacote, valor_total)
    except Exception as exc:
        logger.error('Melhor Envio falhou: %s', exc)
        raise

    opcoes: list[OpcaoFrete] = []
    for item in raw:
        if item.get('error'):
            continue
        preco_raw = item.get('price') or item.get('custom_price')
        if not preco_raw:
            continue
        prazo = int(item.get('custom_delivery_time') or item.get('delivery_time', 0))
        opcoes.append(OpcaoFrete(
            id=item['id'],
            transportadora=item.get('company', {}).get('name', ''),
            servico=item.get('name', ''),
            preco=Decimal(str(preco_raw)),
            prazo_dias=prazo,
            prazo_com_producao=prazo + dias_adicionais,
        ))

    cache.set(key, opcoes, _CACHE_TTL)
    return opcoes
