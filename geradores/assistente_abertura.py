# -*- coding: utf-8 -*-
"""Assistente conversacional para abrir processo + documento no SEI."""
from __future__ import annotations

import re

import banco
from geradores.abertura_ia import (
    TIPO_CONTRATACAO,
    _escolher_assunto,
    _normalizar,
    _pontuar_catalogo,
    _texto,
    _tokens_pedido,
    montar_pacote_confirmado,
)

ETAPA_PROCESSO = "processo"
ETAPA_DOCUMENTO = "documento"
ETAPA_ASSUNTO = "assunto"
ETAPA_PRONTO = "pronto"

DOC_HABITO = {
    TIPO_CONTRATACAO: "334",
    "Decreto": "524",
}

SINONIMOS = {
    "licenca": {"aquisicao", "material", "permanente", "consumo", "software", "contratacao"},
    "licencas": {"aquisicao", "material", "permanente", "consumo", "software", "contratacao"},
    "software": {"aquisicao", "material", "permanente", "contratacao"},
    "gitlab": {"aquisicao", "software", "material", "permanente"},
    "contratacao": {"aquisicao", "servico"},
    "servico": {"contratacao", "especializado"},
    "servicos": {"contratacao", "especializado"},
    "decreto": {"decreto"},
    "oficio": {"oficio"},
    "contrato": {"contrato"},
    "ata": {"ata"},
    "relatorio": {"relatorio", "justificativa"},
    "justificativa": {"relatorio", "justificativa"},
}

AFIRMACOES = {
    "sim", "s", "ss", "isso", "isso mesmo", "pode", "pode ser", "ok", "okay",
    "certo", "correto", "confirmo", "confirma", "yes", "yep", "uhum",
    "exato", "perfeito", "fechado", "vamos", "beleza", "blz", "positivo",
}
NEGACOES = {
    "nao", "não", "n", "no", "nop", "outro", "outra", "outra coisa",
    "quero outro", "quero outra", "lista", "mostrar", "mostrar lista",
}


def _estado_base(estado=None):
    base = {
        "etapa": ETAPA_PROCESSO,
        "pedido": "",
        "tema": "",
        "tipo_processo": None,
        "documento": None,
        "documento_sugerido": None,
        "assunto": None,
        "assunto_sugerido": None,
        "aguardando_confirmacao": "",
    }
    if isinstance(estado, dict):
        base.update({chave: estado.get(chave, valor) for chave, valor in base.items()})
    return base


def _opcao_assunto(item, score=0, exato=False):
    return {
        "tipo": "assunto",
        "id": str(item.get("id_sei") or item.get("id") or ""),
        "valor": str(item.get("id_sei") or item.get("nome") or ""),
        "rotulo": item.get("nome") or item.get("descricao") or item.get("id_sei"),
        "nome": item.get("nome"),
        "score": score,
        "exato": exato,
    }


def _tema_amigavel(pedido):
    texto = _texto(pedido)
    if not texto:
        return "o que você pediu"
    match = re.search(
        r"(?:para|sobre|de)\s+(.+)$",
        texto,
        flags=re.IGNORECASE,
    )
    trecho = match.group(1) if match else texto
    trecho = re.sub(r"\b\d+\b", " ", trecho)
    trecho = re.sub(r"\s+", " ", trecho).strip(" .,;:-")
    if len(trecho) < 3:
        trecho = texto
    if len(trecho) > 72:
        trecho = trecho[:69].rstrip() + "..."
    return trecho[0].upper() + trecho[1:] if trecho else "o que você pediu"


def _expandir_tokens(pedido):
    tokens = _tokens_pedido(pedido)
    expandido = set(tokens)
    for token in tokens:
        expandido |= SINONIMOS.get(token, set())
    return tokens, expandido


def _score_similar(pedido, nome):
    tokens, expandido = _expandir_tokens(pedido)
    if not tokens:
        return 0
    norm = _normalizar(nome)
    palavras = [p for p in norm.split() if len(p) > 2]
    if not palavras:
        return 0
    hits = 0
    tokens_originais = set(tokens)
    for palavra in palavras:
        if palavra in tokens_originais:
            hits += 3
            continue
        if palavra in expandido:
            hits += 1
            continue
        # Só aceita prefixo do token do usuário no nome do catálogo (evita "contra" ⊂ "contratacao").
        if any(len(t) >= 5 and palavra.startswith(t) for t in tokens_originais):
            hits += 2
    if hits < 2:
        return 0
    cobertura = hits / max(len(palavras), 1)
    return hits * 35 + int(cobertura * 80)


def _ranquear(pedido, opcoes, chave="nome", limite=8, minimo_exato=220, minimo_similar=40):
    exatos = []
    similares = []
    for item in opcoes or []:
        nome = _texto(item.get(chave) if isinstance(item, dict) else item)
        score_exato = _pontuar_catalogo(pedido, nome)
        score_sim = _score_similar(pedido, nome)
        if score_exato >= minimo_exato:
            exatos.append((score_exato, item, True))
        elif score_sim >= minimo_similar:
            similares.append((score_sim, item, False))
    exatos.sort(key=lambda par: par[0], reverse=True)
    similares.sort(key=lambda par: par[0], reverse=True)
    escolhidos = []
    vistos = set()
    for score, item, exato in exatos + similares:
        marca = str(item.get("id") or item.get(chave) or "")
        if not marca or marca in vistos:
            continue
        vistos.add(marca)
        escolhidos.append({"item": item, "score": score, "exato": exato})
        if len(escolhidos) >= limite:
            break
    return escolhidos


def _opcao_processo(item, score=0, exato=False):
    return {
        "tipo": "processo",
        "id": str(item.get("id") or item.get("nome")),
        "valor": item.get("nome"),
        "rotulo": item.get("nome"),
        "score": score,
        "exato": exato,
    }


def _guardar_tipo_processo(estado, tipo):
    """Guarda o processo e já traz o assunto vinculado do cadastro Processo/Assunto."""
    if not tipo:
        estado["tipo_processo"] = None
        return estado
    id_sei = _texto(tipo.get("id_sei"))
    assunto_id = _texto(tipo.get("assunto_id_sei"))
    assunto_nome = _texto(tipo.get("assunto_nome"))
    if id_sei and not assunto_id:
        vinculado = banco.obter_assunto_do_tipo_processo(
            tipo_processo_id_sei=id_sei,
            tipo_processo_nome=tipo.get("nome") or "",
        )
        if vinculado:
            assunto_id = _texto(vinculado.get("id_sei"))
            assunto_nome = _texto(vinculado.get("nome"))
    estado["tipo_processo"] = {
        "nome": tipo.get("nome"),
        "id_sei": id_sei,
        "assunto_id_sei": assunto_id,
        "assunto_nome": assunto_nome,
    }
    return estado


def _opcao_documento(item, score=0, exato=False, usos=None):
    rotulo = f"{item.get('id')} — {item.get('nome')}"
    if usos:
        rotulo = f"{rotulo} (usado {usos}x)"
    return {
        "tipo": "documento",
        "id": str(item.get("id")),
        "valor": str(item.get("id")),
        "rotulo": rotulo,
        "nome": item.get("nome"),
        "score": score,
        "exato": exato,
        "usos": usos or 0,
    }


def _eh_afirmacao(texto):
    return _normalizar(texto) in AFIRMACOES


def _eh_negacao(texto):
    bruto = _normalizar(texto)
    return bruto in NEGACOES or bruto.startswith("nao ") or bruto.startswith("quero outro")


def _buscar_tipo(nome, tipos):
    alvo = _normalizar(nome)
    for item in tipos:
        if _normalizar(item.get("nome")) == alvo:
            return item
    return None


def _buscar_doc(identificador, tipos_doc):
    alvo = str(identificador or "").strip()
    for item in tipos_doc:
        if str(item.get("id")) == alvo or _normalizar(item.get("nome")) == _normalizar(alvo):
            return item
    ranked = _ranquear(alvo, tipos_doc, limite=1, minimo_exato=200, minimo_similar=80)
    return ranked[0]["item"] if ranked else None


def _sugerir_documento(tipo_processo, pedido, tipos_doc):
    nome_tipo = _texto((tipo_processo or {}).get("nome"))
    historico = banco.documentos_mais_usados_por_tipo_processo(nome_tipo, limite=5)
    if historico:
        return historico[0], historico, "historico"
    padrao_id = DOC_HABITO.get(nome_tipo)
    if padrao_id:
        achado = next((d for d in tipos_doc if str(d.get("id")) == padrao_id), None)
        if achado:
            return achado, [achado], "habito"
    ranked = _ranquear(pedido, tipos_doc, limite=6, minimo_exato=200, minimo_similar=50)
    if ranked:
        return ranked[0]["item"], [r["item"] for r in ranked], "pedido"
    fallback = next((d for d in tipos_doc if d.get("nome") == "Relatório de Justificativa - OS"), None)
    if fallback:
        return fallback, [fallback], "padrao"
    return (tipos_doc[0] if tipos_doc else None), tipos_doc[:6], "padrao"


def _resposta(mensagem, estado, opcoes=None, pacote=None):
    return {
        "ok": True,
        "mensagem": mensagem,
        "opcoes": opcoes or [],
        "estado": estado,
        "etapa": estado.get("etapa"),
        "pacote": pacote,
    }


def _botao_ver_documentos():
    return {
        "tipo": "acao",
        "id": "ver_documentos",
        "valor": "ver_documentos",
        "rotulo": "Ver todos os tipos de documento",
    }


def _botao_demais_processos():
    return {
        "tipo": "acao",
        "id": "demais_processos",
        "valor": "demais_processos",
        "rotulo": "Demais Processos",
    }


def _listar_todos_processos(estado, tipos, mensagem=""):
    estado["etapa"] = ETAPA_PROCESSO
    estado["aguardando_confirmacao"] = ""
    opcoes = [_opcao_processo(item) for item in (tipos or [])]
    return _resposta(
        mensagem
        or "Aqui está a lista completa de tipos de processo. Escolha o que deseja usar:",
        estado,
        opcoes,
    )


def _com_demais_processos(opcoes):
    lista = list(opcoes or [])
    if not any(
        _texto(o.get("valor")).casefold().replace(" ", "_") == "demais_processos"
        for o in lista
        if isinstance(o, dict)
    ):
        lista.append(_botao_demais_processos())
    return lista


def _listar_todos_documentos(estado, tipos_doc, mensagem=""):
    estado["etapa"] = ETAPA_DOCUMENTO
    estado["aguardando_confirmacao"] = ""
    estado["documento_sugerido"] = None
    opcoes = [_opcao_documento(item) for item in (tipos_doc or [])]
    return _resposta(
        mensagem
        or "Aqui estão todos os tipos de documento. Escolha o que deseja usar:",
        estado,
        opcoes,
    )


def _iniciar_documento(estado, tipos_doc):
    tipo = estado.get("tipo_processo") or {}
    sugerido, lista, origem = _sugerir_documento(tipo, estado.get("pedido") or "", tipos_doc)
    estado["etapa"] = ETAPA_DOCUMENTO
    estado["documento_sugerido"] = {
        "id": str(sugerido.get("id")),
        "nome": sugerido.get("nome"),
    } if sugerido and origem in {"historico", "habito", "pedido"} else None
    estado["aguardando_confirmacao"] = "documento" if estado["documento_sugerido"] else ""
    opcoes = []
    if sugerido and origem in {"historico", "habito"}:
        usos = sugerido.get("usos") if origem == "historico" else None
        if origem == "historico":
            texto = (
                f"Beleza — processo **{tipo.get('nome')}** anotado.\n\n"
                f"Verifiquei aqui e, quando usam esse processo, o documento mais comum é "
                f"**{sugerido.get('nome')}**"
                + (f" ({usos}x)" if usos else "")
                + ". É isso mesmo?"
            )
        else:
            texto = (
                f"Fechado: **{tipo.get('nome')}**.\n\n"
                f"Nesse tipo de processo o documento que costuma acompanhar é "
                f"**{sugerido.get('nome')}**. Posso seguir com ele?"
            )
        opcoes = [
            {"tipo": "acao", "id": "sim", "valor": "sim", "rotulo": "Sim, pode ser"},
            {"tipo": "acao", "id": "nao", "valor": "nao", "rotulo": "Não, quero outro"},
            _botao_ver_documentos(),
        ]
        for item in lista[:5]:
            if str(item.get("id")) == str(sugerido.get("id")):
                continue
            opcoes.append(_opcao_documento(item, usos=item.get("usos")))
        return _resposta(texto, estado, opcoes)

    if sugerido and origem == "pedido":
        texto = (
            f"Processo **{tipo.get('nome')}** escolhido.\n\n"
            f"No seu pedido, o documento que mais combina é **{sugerido.get('nome')}**. "
            "É esse, ou prefere ver a lista completa?"
        )
        opcoes = [
            _opcao_documento(sugerido, exato=True),
            _botao_ver_documentos(),
        ]
        for item in lista[1:6]:
            opcoes.append(_opcao_documento(item))
        return _resposta(texto, estado, opcoes)

    # Sem documento habitual: não força um padrão; oferece ver a lista completa.
    texto = (
        f"Processo **{tipo.get('nome')}** ok.\n\n"
        "Não achei um documento habitual para ele. "
        "Clique em **Ver todos os tipos de documento** para escolher, "
        "ou selecione uma das opções abaixo se aparecer."
    )
    opcoes = [_botao_ver_documentos()]
    for item in (lista or [])[:6]:
        # Evita apresentar o fallback genérico como se fosse habitual.
        if origem == "padrao":
            continue
        opcoes.append(_opcao_documento(item))
    estado["aguardando_confirmacao"] = ""
    return _resposta(texto, estado, opcoes)


def _rotulo_assunto_curto(assunto):
    if not assunto:
        return ""
    descricao = _texto(assunto.get("descricao"))
    if descricao:
        return descricao
    nome = _texto(assunto.get("nome"))
    if " - " in nome:
        return nome.split(" - ", 1)[1].strip() or nome
    return nome


def _assunto_pos_processo(estado):
    """Depois do processo confirmado: documento ou revisão, conforme o que já existe."""
    tipos_doc = banco.listar_tipos_documento_sei()
    if estado.get("documento") and estado["documento"].get("id"):
        return _fechar_pacote(estado)
    return _iniciar_documento(estado, tipos_doc)


def _resolver_assunto_estado(estado, tipos, assuntos):
    if estado.get("assunto") and estado["assunto"].get("id_sei"):
        direto = banco.obter_assunto_por_id_sei(estado["assunto"]["id_sei"])
        if direto:
            return direto, "escolhido"
    tipo_estado = estado.get("tipo_processo") or {}
    # 1) Assunto já veio no próprio tipo (join Processo/Assunto).
    if tipo_estado.get("assunto_id_sei"):
        direto = banco.obter_assunto_por_id_sei(tipo_estado.get("assunto_id_sei"))
        if direto:
            return direto, "vinculo"
    tipo = _buscar_tipo(tipo_estado.get("nome"), tipos) or {}
    if tipo.get("assunto_id_sei"):
        direto = banco.obter_assunto_por_id_sei(tipo.get("assunto_id_sei"))
        if direto:
            return direto, "vinculo"
    # 2) Consulta explícita na tabela de relação.
    vinculado = banco.obter_assunto_do_tipo_processo(
        tipo_processo_id_sei=tipo_estado.get("id_sei") or tipo.get("id_sei") or "",
        tipo_processo_nome=tipo_estado.get("nome") or tipo.get("nome") or "",
    )
    if vinculado:
        return vinculado, "vinculo"
    # 3) Só sugere por texto se NÃO houver vínculo cadastrado.
    sugerido = _escolher_assunto(
        estado.get("pedido") or "",
        tipo.get("nome") or tipo_estado.get("nome") or "",
        assuntos,
    )
    return sugerido, "sugestao"


def _iniciar_assunto(estado):
    tipos = banco.listar_tipos_processo_sei()
    assuntos = banco.listar_assuntos_sei()
    # Refresca o tipo com o vínculo atual do cadastro Processo/Assunto.
    tipo_estado = estado.get("tipo_processo") or {}
    tipo = _buscar_tipo(tipo_estado.get("nome"), tipos)
    if tipo:
        _guardar_tipo_processo(estado, tipo)
    assunto, origem = _resolver_assunto_estado(estado, tipos, assuntos)
    estado["etapa"] = ETAPA_ASSUNTO

    # Com vínculo Processo/Assunto: só confirma, sem lista de sugestões.
    if origem == "vinculo" and assunto:
        estado["assunto_sugerido"] = {
            "id_sei": assunto.get("id_sei"),
            "nome": assunto.get("nome"),
        }
        estado["aguardando_confirmacao"] = "assunto"
        rotulo = _rotulo_assunto_curto(assunto)
        nome_proc = (estado.get("tipo_processo") or {}).get("nome") or "este processo"
        return _resposta(
            f"Olhei no cadastro **Processo/Assunto**.\n\n"
            f"Para **{nome_proc}**, o assunto relacionado é **{rotulo}**. "
            "Seria este mesmo?",
            estado,
            [
                {"tipo": "acao", "id": "sim", "valor": "sim", "rotulo": "Sim"},
                {"tipo": "acao", "id": "nao", "valor": "nao", "rotulo": "Não"},
            ],
        )

    # Sem vínculo: sugere por palavras-chave e deixa escolher.
    if assunto:
        estado["assunto_sugerido"] = {
            "id_sei": assunto.get("id_sei"),
            "nome": assunto.get("nome"),
        }
        estado["aguardando_confirmacao"] = "assunto"
        ranked = _ranquear(estado.get("pedido") or "", assuntos, limite=6, minimo_exato=180, minimo_similar=40)
        opcoes = [
            {"tipo": "acao", "id": "sim", "valor": "sim", "rotulo": "Sim"},
            {"tipo": "acao", "id": "nao", "valor": "nao", "rotulo": "Não"},
        ]
        for item in ranked:
            opcoes.append(_opcao_assunto(item["item"], item["score"], item["exato"]))
        return _resposta(
            "Não encontrei assunto vinculado a esse processo no cadastro Processo/Assunto.\n\n"
            f"Pelo texto, o que mais combina é **{_rotulo_assunto_curto(assunto)}**. "
            "Seria este mesmo? (Assunto é obrigatório.)",
            estado,
            opcoes,
        )

    estado["aguardando_confirmacao"] = ""
    estado["assunto_sugerido"] = None
    return _resposta(
        "Não achei assunto vinculado nem uma sugestão clara. "
        "Escolha um assunto na lista — sem isso não dá para criar o processo:",
        estado,
        [_opcao_assunto(item) for item in assuntos[:12]],
    )


def _tratar_assunto(mensagem, escolha, estado):
    assuntos = banco.listar_assuntos_sei()
    if escolha and escolha.get("tipo") == "assunto" and escolha.get("valor"):
        assunto = banco.obter_assunto_por_id_sei(escolha.get("valor"))
        if not assunto:
            assunto = next(
                (a for a in assuntos if _normalizar(a.get("nome")) == _normalizar(escolha.get("valor"))),
                None,
            )
        if not assunto:
            return _resposta("Não localizei esse assunto. Escolhe um da lista?", estado, [_opcao_assunto(a) for a in assuntos[:12]])
        estado["assunto"] = {"id_sei": assunto.get("id_sei"), "nome": assunto.get("nome")}
        estado["aguardando_confirmacao"] = ""
        return _assunto_pos_processo(estado)

    texto = _texto(mensagem)
    if escolha and escolha.get("tipo") == "acao":
        valor = _normalizar(escolha.get("valor"))
        if valor in AFIRMACOES and estado.get("assunto_sugerido"):
            estado["assunto"] = dict(estado["assunto_sugerido"])
            estado["aguardando_confirmacao"] = ""
            return _assunto_pos_processo(estado)
        if valor in NEGACOES or valor == "nao":
            estado["aguardando_confirmacao"] = ""
            estado["assunto_sugerido"] = None
            opcoes = [_opcao_assunto(a) for a in assuntos]
            return _resposta(
                "Certo. Selecione o assunto na lista:",
                estado,
                opcoes,
            )

    if estado.get("aguardando_confirmacao") == "assunto":
        if _eh_afirmacao(texto) and estado.get("assunto_sugerido"):
            estado["assunto"] = dict(estado["assunto_sugerido"])
            estado["aguardando_confirmacao"] = ""
            return _assunto_pos_processo(estado)
        if _eh_negacao(texto):
            return _tratar_assunto("", {"tipo": "acao", "valor": "nao"}, estado)

    if texto:
        ranked = _ranquear(texto, assuntos, limite=8, minimo_exato=180, minimo_similar=40)
        if len(ranked) == 1 and ranked[0]["exato"]:
            assunto = ranked[0]["item"]
            estado["assunto"] = {"id_sei": assunto.get("id_sei"), "nome": assunto.get("nome")}
            return _assunto_pos_processo(estado)
        if ranked:
            return _resposta(
                "Encontrei estes assuntos. Qual deles usamos?",
                estado,
                [_opcao_assunto(r["item"], r["score"], r["exato"]) for r in ranked],
            )
    return _iniciar_assunto(estado)


def _fechar_pacote(estado):
    tipos = banco.listar_tipos_processo_sei()
    tipos_doc = banco.listar_tipos_documento_sei()
    assuntos = banco.listar_assuntos_sei()
    tipo_estado = estado.get("tipo_processo") or {}
    tipo = _buscar_tipo(tipo_estado.get("nome"), tipos)
    if tipo:
        _guardar_tipo_processo(estado, tipo)
        tipo = estado.get("tipo_processo") or tipo
    doc = _buscar_doc((estado.get("documento") or {}).get("id"), tipos_doc)
    if not doc:
        return _iniciar_documento(estado, tipos_doc)
    # Só fecha o pacote com assunto já confirmado/escolhido pelo usuário.
    if not (estado.get("assunto") and estado["assunto"].get("id_sei")):
        return _iniciar_assunto(estado)
    assunto, _origem = _resolver_assunto_estado(estado, tipos, assuntos)
    if not assunto:
        return _iniciar_assunto(estado)
    tipo_pacote = _buscar_tipo((estado.get("tipo_processo") or {}).get("nome"), tipos) or tipo
    pacote = montar_pacote_confirmado(
        estado.get("pedido") or "",
        tipo_pacote,
        doc,
        assunto=assunto,
        fonte="Assistente conversacional",
    )
    estado["assunto"] = {"id_sei": assunto.get("id_sei"), "nome": assunto.get("nome")}
    estado["etapa"] = ETAPA_PRONTO
    estado["aguardando_confirmacao"] = ""
    return _resposta(
        "Pronto! Montei o resumo com o processo, o documento e o assunto. "
        "Dá uma olhada e, se estiver tudo certo, confirme a criação no SEI.",
        estado,
        pacote=pacote,
    )


def _alternativas_processo(pedido, tipos, excluir_nome=""):
    ranked = _ranquear(pedido, tipos, limite=10)
    opcoes = []
    for item in ranked:
        nome = item["item"].get("nome")
        if excluir_nome and _normalizar(nome) == _normalizar(excluir_nome):
            continue
        opcoes.append(_opcao_processo(item["item"], item["score"], item["exato"]))
    if opcoes:
        return opcoes
    tokens, expandido = _expandir_tokens(pedido)
    fallback = []
    for item in tipos:
        nome = _normalizar(item.get("nome"))
        if any(chave in nome for chave in ("contratacao", "aquisicao", "decreto", "oficio")):
            if expandido & set(nome.split()) or any(t in nome for t in tokens if len(t) > 4):
                fallback.append(item)
    if not fallback:
        fallback = [t for t in tipos if "contratacao" in _normalizar(t.get("nome"))][:6]
        fallback += [t for t in tipos if "aquisicao" in _normalizar(t.get("nome"))][:4]
    vistos = set()
    for item in fallback:
        marca = item.get("nome")
        if not marca or marca in vistos:
            continue
        if excluir_nome and _normalizar(marca) == _normalizar(excluir_nome):
            continue
        vistos.add(marca)
        opcoes.append(_opcao_processo(item))
        if len(opcoes) >= 8:
            break
    return opcoes


def _tratar_processo(mensagem, escolha, estado, forcar_lista=False):
    tipos = banco.listar_tipos_processo_sei()
    tipos_doc = banco.listar_tipos_documento_sei()
    if escolha and escolha.get("tipo") == "processo" and escolha.get("valor"):
        tipo = _buscar_tipo(escolha.get("valor"), tipos)
        if not tipo:
            return _resposta(
                "Não consegui localizar essa opção. Pode clicar em uma da lista ou descrever de outro jeito?",
                estado,
                [_opcao_processo(t) for t in tipos[:8]],
            )
        _guardar_tipo_processo(estado, tipo)
        estado["aguardando_confirmacao"] = ""
        if not estado.get("pedido"):
            estado["pedido"] = tipo.get("nome")
            estado["tema"] = tipo.get("nome")
        return _iniciar_assunto(estado)

    pedido = _texto(mensagem) or _texto(estado.get("pedido"))
    if len(pedido) < 3:
        return _resposta(
            "Me conta em uma frase o que você precisa abrir. Pode ser só uma palavra, "
            "tipo **Decreto**, ou algo como “contratação de licenças do GitLab”.",
            estado,
        )

    estado["pedido"] = pedido
    estado["tema"] = _tema_amigavel(pedido)
    if forcar_lista:
        excluir = _texto((estado.get("tipo_processo") or {}).get("nome"))
        opcoes = _com_demais_processos(_alternativas_processo(pedido, tipos, excluir_nome=excluir))
        return _resposta(
            f"Sem problema. Aqui vão opções próximas de **{estado['tema']}** — "
            "escolhe uma, use **Demais Processos** para ver a lista completa, ou descreva de outro jeito:",
            estado,
            opcoes,
        )

    ranked = _ranquear(pedido, tipos, limite=8)
    exatos = [r for r in ranked if r["exato"]]

    if len(exatos) == 1 and exatos[0]["score"] >= 800:
        tipo = exatos[0]["item"]
        _guardar_tipo_processo(estado, tipo)
        estado["aguardando_confirmacao"] = "processo"
        return _resposta(
            f"Achei na hora: **{tipo.get('nome')}**. É esse o processo?",
            estado,
            [
                {"tipo": "acao", "id": "sim", "valor": "sim", "rotulo": "Sim, esse mesmo"},
                {"tipo": "acao", "id": "nao", "valor": "nao", "rotulo": "Não, mostrar outras opções"},
                _botao_demais_processos(),
                _opcao_processo(tipo, score=exatos[0]["score"], exato=True),
            ],
        )

    if exatos:
        opcoes = _com_demais_processos(
            [_opcao_processo(r["item"], r["score"], True) for r in exatos[:8]]
        )
        return _resposta(
            f"Encontrei estes tipos de processo parecidos com **{estado['tema']}**. "
            "Qual deles combina melhor? Se preferir, abra **Demais Processos**.",
            estado,
            opcoes,
        )

    if ranked:
        opcoes = _com_demais_processos(
            [_opcao_processo(r["item"], r["score"], False) for r in ranked]
        )
        return _resposta(
            f"Não encontrei nada relacionado a **{estado['tema']}**.\n\n"
            "Mas veja as opções que mais se aproximam do que você pediu — "
            "é só clicar numa, usar **Demais Processos** para ver a lista completa, "
            "ou me contar de outro jeito:",
            estado,
            opcoes,
        )

    return _resposta(
        f"Não encontrei nada sobre **{estado['tema']}** nas tabelas internas.\n\n"
        "Separei algumas opções próximas, ou use **Demais Processos** para ver a lista completa:",
        estado,
        _com_demais_processos(_alternativas_processo(pedido, tipos)),
    )


def _tratar_documento(mensagem, escolha, estado):
    tipos = banco.listar_tipos_processo_sei()
    tipos_doc = banco.listar_tipos_documento_sei()

    if escolha and escolha.get("tipo") == "documento" and escolha.get("valor"):
        doc = _buscar_doc(escolha.get("valor"), tipos_doc)
        if not doc:
            return _resposta("Não achei esse documento. Escolhe um da lista?", estado)
        estado["documento"] = {"id": str(doc.get("id")), "nome": doc.get("nome")}
        return _fechar_pacote(estado)

    if escolha and escolha.get("tipo") == "acao":
        valor_bruto = _texto(escolha.get("valor")).casefold()
        valor = _normalizar(escolha.get("valor"))
        if valor in AFIRMACOES and estado.get("documento_sugerido"):
            estado["documento"] = dict(estado["documento_sugerido"])
            return _fechar_pacote(estado)
        if (
            valor in NEGACOES
            or valor == "nao"
            or valor_bruto in {"ver_documentos", "ver documentos"}
            or valor == "ver documentos"
        ):
            return _listar_todos_documentos(
                estado,
                tipos_doc,
                "Sem problema. Aqui estão todos os tipos de documento — escolha um:",
            )

    texto = _texto(mensagem)
    if estado.get("aguardando_confirmacao") == "documento":
        if _eh_afirmacao(texto) and estado.get("documento_sugerido"):
            estado["documento"] = dict(estado["documento_sugerido"])
            return _fechar_pacote(estado)
        if _eh_negacao(texto):
            estado["aguardando_confirmacao"] = ""
            estado["documento_sugerido"] = None
            return _tratar_documento("", {"tipo": "acao", "valor": "nao"}, estado)

    if estado.get("aguardando_confirmacao") == "processo":
        tipo = _buscar_tipo((estado.get("tipo_processo") or {}).get("nome"), tipos)
        if (_eh_afirmacao(texto) or (escolha and _normalizar(escolha.get("valor")) in AFIRMACOES)) and tipo:
            _guardar_tipo_processo(estado, tipo)
            estado["aguardando_confirmacao"] = ""
            return _iniciar_assunto(estado)
        if _eh_negacao(texto) or (escolha and _normalizar(escolha.get("valor")) in NEGACOES):
            estado["aguardando_confirmacao"] = ""
            estado["etapa"] = ETAPA_PROCESSO
            resposta = _tratar_processo(estado.get("pedido") or texto, None, estado, forcar_lista=True)
            estado["tipo_processo"] = None
            return resposta

    if texto:
        ranked = _ranquear(texto, tipos_doc, limite=8, minimo_exato=200, minimo_similar=50)
        if len(ranked) == 1 and ranked[0]["exato"]:
            doc = ranked[0]["item"]
            estado["documento"] = {"id": str(doc.get("id")), "nome": doc.get("nome")}
            return _fechar_pacote(estado)
        if ranked:
            return _resposta(
                "Encontrei estes documentos. Qual deles você quer?",
                estado,
                [_opcao_documento(r["item"], r["score"], r["exato"]) for r in ranked],
            )
        return _resposta(
            f"Não encontrei documento com **{_tema_amigavel(texto)}**. "
            "Tenta outra palavra (Ofício, Contrato, Relatório…) ou escolhe na lista:",
            estado,
            [_opcao_documento(item) for item in tipos_doc[:10]],
        )

    return _iniciar_documento(estado, tipos_doc)


def conversar(mensagem="", estado=None, escolha=None):
    estado = _estado_base(estado)
    mensagem = _texto(mensagem)
    escolha = escolha if isinstance(escolha, dict) else None

    if not estado.get("pedido") and not mensagem and not escolha:
        estado["etapa"] = ETAPA_PROCESSO
        return _resposta(
            "Oi! Sou o assistente de abertura do SEI.\n\n"
            "Me conta o que você precisa — uma palavra ou uma frase. "
            "Ex.: **Decreto**, **Ofício**, ou “contratação de 1000 licenças do GitLab Ultimate”. "
            "Eu procuro nas listas internas e a gente vai afinando juntos.",
            estado,
        )

    if escolha and escolha.get("tipo") == "processo":
        estado["etapa"] = ETAPA_PROCESSO
        return _tratar_processo(mensagem, escolha, estado)
    if escolha and escolha.get("tipo") == "documento":
        estado["etapa"] = ETAPA_DOCUMENTO
        return _tratar_documento(mensagem, escolha, estado)
    if escolha and escolha.get("tipo") == "assunto":
        estado["etapa"] = ETAPA_ASSUNTO
        return _tratar_assunto(mensagem, escolha, estado)
    if escolha and escolha.get("tipo") == "acao":
        valor_bruto = _texto(escolha.get("valor")).casefold().replace(" ", "_")
        if valor_bruto in {"demais_processos", "ver_processos"}:
            return _listar_todos_processos(
                estado,
                banco.listar_tipos_processo_sei(),
                "Aqui está a lista completa de tipos de processo. Escolha o que deseja usar:",
            )

    if estado.get("aguardando_confirmacao") == "processo" and (mensagem or escolha):
        tipos = banco.listar_tipos_processo_sei()
        tipo = _buscar_tipo((estado.get("tipo_processo") or {}).get("nome"), tipos)
        valor = _normalizar((escolha or {}).get("valor") if escolha else mensagem)
        valor_bruto = _texto((escolha or {}).get("valor") if escolha else "").casefold().replace(" ", "_")
        if valor_bruto in {"demais_processos", "ver_processos"}:
            estado["aguardando_confirmacao"] = ""
            estado["tipo_processo"] = None
            return _listar_todos_processos(
                estado,
                tipos,
                "Aqui está a lista completa de tipos de processo. Escolha o que deseja usar:",
            )
        if tipo and (_eh_afirmacao(mensagem) or valor in AFIRMACOES or (escolha and escolha.get("tipo") == "processo")):
            if escolha and escolha.get("tipo") == "processo":
                tipo = _buscar_tipo(escolha.get("valor"), tipos) or tipo
            _guardar_tipo_processo(estado, tipo)
            estado["aguardando_confirmacao"] = ""
            return _iniciar_assunto(estado)
        if _eh_negacao(mensagem) or valor in NEGACOES:
            estado["aguardando_confirmacao"] = ""
            estado["etapa"] = ETAPA_PROCESSO
            resposta = _tratar_processo(estado.get("pedido") or mensagem, None, estado, forcar_lista=True)
            estado["tipo_processo"] = None
            return resposta

    if escolha and escolha.get("tipo") == "acao":
        if estado.get("etapa") == ETAPA_ASSUNTO or estado.get("aguardando_confirmacao") == "assunto":
            return _tratar_assunto(mensagem, escolha, estado)
        if estado.get("etapa") == ETAPA_DOCUMENTO or estado.get("aguardando_confirmacao") == "documento":
            return _tratar_documento(mensagem, escolha, estado)

    if estado.get("etapa") == ETAPA_ASSUNTO:
        return _tratar_assunto(mensagem, escolha, estado)
    if estado.get("etapa") == ETAPA_DOCUMENTO:
        return _tratar_documento(mensagem, escolha, estado)

    return _tratar_processo(mensagem, escolha, estado)
