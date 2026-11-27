# -*- coding: utf-8 -*-
"""Cliente Direct Line para agente do Microsoft Copilot Studio."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
import uuid

from geradores.ia_config import carregar_ia_config

DIRECT_LINE = "https://directline.botframework.com/v3/directline"


def _texto(valor):
    return str(valor or "").strip()


def _json_request(metodo, url, token=None, corpo=None, timeout=30):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None if corpo is None else json.dumps(corpo).encode("utf-8")
    pedido = urllib.request.Request(url, data=data, headers=headers, method=metodo)
    try:
        with urllib.request.urlopen(pedido, timeout=timeout) as resp:
            bruto = resp.read().decode("utf-8")
            return json.loads(bruto) if bruto else {}
    except urllib.error.HTTPError as erro:
        detalhe = ""
        try:
            detalhe = erro.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            detalhe = str(erro)
        raise RuntimeError(f"Direct Line HTTP {erro.code}: {detalhe or erro}") from erro


def _iniciar_conversa(secret, usuario_id, timeout=25):
    dados = _json_request(
        "POST",
        f"{DIRECT_LINE}/conversations",
        token=secret,
        corpo={"user": {"id": usuario_id, "name": "GCPD"}},
        timeout=timeout,
    )
    conversa = _texto(dados.get("conversationId"))
    token = _texto(dados.get("token")) or secret
    if not conversa:
        raise RuntimeError("Não foi possível iniciar a conversa no Copilot Studio.")
    return token, conversa


def _url_atividades(conversa_id, watermark=None):
    url = f"{DIRECT_LINE}/conversations/{conversa_id}/activities"
    if watermark is not None and str(watermark) != "":
        url = f"{url}?watermark={watermark}"
    return url


def _enviar_mensagem(token, conversa_id, texto, usuario_id, timeout=30):
    return _json_request(
        "POST",
        _url_atividades(conversa_id),
        token=token,
        corpo={
            "type": "message",
            "from": {"id": usuario_id, "name": "GCPD"},
            "text": texto,
            "locale": "pt-BR",
        },
        timeout=timeout,
    )


def _ler_atividades(token, conversa_id, watermark=None, timeout=20):
    dados = _json_request(
        "GET",
        _url_atividades(conversa_id, watermark),
        token=token,
        timeout=timeout,
    )
    return dados.get("activities") or [], dados.get("watermark", watermark)


def _eh_resposta_bot(atividade, usuario_id):
    if str(atividade.get("type") or "") not in {"message", "messageUpdate"}:
        return False
    origem = atividade.get("from") or {}
    if _texto(origem.get("id")) == usuario_id:
        return False
    return bool(_texto(atividade.get("text")) or _texto(atividade.get("speak")))


def _texto_atividade(atividade):
    return _texto(atividade.get("text")) or _texto(atividade.get("speak"))


def _coletar_resposta(token, conversa_id, usuario_id, watermark_inicial=None, timeout=45, intervalo=1.0):
    """Lê só atividades novas depois do watermark_inicial (após o nosso post)."""
    watermark = watermark_inicial
    limite = time.time() + max(12, int(timeout))
    partes = []
    vistos = set()
    while time.time() < limite:
        atividades, watermark = _ler_atividades(token, conversa_id, watermark, timeout=20)
        for atividade in atividades:
            if not _eh_resposta_bot(atividade, usuario_id):
                continue
            aid = _texto(atividade.get("id")) or _texto_atividade(atividade)
            if aid in vistos:
                continue
            vistos.add(aid)
            texto = _texto_atividade(atividade)
            if texto:
                partes.append(texto)
        if partes:
            # Pequena espera por continuação da mesma resposta.
            time.sleep(0.9)
            atividades2, watermark = _ler_atividades(token, conversa_id, watermark, timeout=15)
            for atividade in atividades2:
                if not _eh_resposta_bot(atividade, usuario_id):
                    continue
                aid = _texto(atividade.get("id")) or _texto_atividade(atividade)
                if aid in vistos:
                    continue
                vistos.add(aid)
                texto = _texto_atividade(atividade)
                if texto:
                    partes.append(texto)
            return "\n\n".join(partes).strip()
        time.sleep(intervalo)
    raise RuntimeError("O agente do Copilot Studio não respondeu a tempo.")


def responder_copilot(prompt, timeout=45):
    """Envia o prompt ao agente publicado e devolve (texto, fonte)."""
    cfg = carregar_ia_config()
    secret = _texto(cfg.get("copilot_directline_secret"))
    if not secret:
        raise ValueError(
            "Segredo Direct Line do Copilot não configurado. "
            "Em Configurações → IA / API, cole o Segredo 1 do canal Web."
        )
    prompt = _texto(prompt)
    if not prompt:
        raise ValueError("Informe o texto para o agente do Copilot Studio.")

    usuario_id = f"gcpd-{uuid.uuid4().hex[:10]}"
    token, conversa = _iniciar_conversa(secret, usuario_id, timeout=min(25, timeout))
    # Marca o ponto atual antes do envio para não misturar atividades velhas.
    _, watermark = _ler_atividades(token, conversa, None, timeout=15)
    _enviar_mensagem(token, conversa, prompt, usuario_id, timeout=min(30, timeout))
    time.sleep(0.5)
    texto = _coletar_resposta(
        token,
        conversa,
        usuario_id,
        watermark_inicial=watermark,
        timeout=timeout,
    )
    if not texto:
        raise RuntimeError("Copilot Studio retornou vazio.")
    nome = _texto(cfg.get("copilot_agent_name")) or "GCPD Assistente SEI"
    return texto, f"Copilot Studio ({nome})"
