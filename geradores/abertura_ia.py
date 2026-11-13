# -*- coding: utf-8 -*-
"""Montagem assistida por IA do pacote processo + documento para abertura no SEI."""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request

import banco
from geradores.ia_config import carregar_ia_config

TIPO_CONTRATACAO = (
    "Processo de Contratação de Serviço Técnico Profissional Especializado"
)
INTERESSADO_PADRAO = "GESP - TUPP"
UNIDADE_GERADORA_PADRAO = "110000001"


def _texto(valor):
    return str(valor or "").strip()


def _normalizar(texto):
    bruto = _texto(texto).casefold()
    bruto = (
        bruto.replace("á", "a")
        .replace("à", "a")
        .replace("â", "a")
        .replace("ã", "a")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ô", "o")
        .replace("õ", "o")
        .replace("ú", "u")
        .replace("ç", "c")
    )
    return re.sub(r"[^a-z0-9]+", " ", bruto).strip()


def _post_gemini(chave, modelo, prompt, max_tokens, thinking=True, timeout=45):
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{urllib.parse.quote(modelo)}:generateContent?key={urllib.parse.quote(chave)}"
    )
    config = {"temperature": 0.1, "maxOutputTokens": max_tokens}
    if thinking:
        config["thinkingConfig"] = {"thinkingBudget": 0}
    corpo = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": config,
    }
    pedido = urllib.request.Request(
        url,
        data=json.dumps(corpo).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(pedido, timeout=timeout) as resp:
        dados = json.loads(resp.read().decode("utf-8"))
    partes = (
        dados.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [])
    )
    return "\n".join(_texto(p.get("text")) for p in partes).strip()


def _eh_timeout(erro):
    texto = str(erro or "").lower()
    return "timed out" in texto or "timeout" in texto or "time out" in texto


def _gemini_texto(prompt, max_tokens=2048, timeout=45, preferir_rapido=False):
    cfg = carregar_ia_config()
    chave = _texto(cfg.get("google_api_key"))
    if not chave:
        openai = _texto(cfg.get("openai_api_key"))
        if not openai:
            raise ValueError(
                "Chave de IA não configurada. Em Configurações → IA / API, informe a chave do Gemini."
            )
        return _openai_texto(prompt, openai, cfg.get("modelo_openai") or "gpt-4o-mini", max_tokens)

    modelo = _texto(cfg.get("modelo_google")) or "gemini-3.5-flash"
    lite = "gemini-3.5-flash-lite"
    if preferir_rapido:
        fila = [lite] if modelo == lite else [lite, modelo]
    else:
        fila = [modelo]
        if modelo != lite:
            fila.append(lite)
    ultimo = ""
    for indice, nome in enumerate(fila):
        try:
            try:
                texto = _post_gemini(
                    chave, nome, prompt, max_tokens, thinking=True, timeout=timeout
                )
            except Exception as erro:
                detalhe = str(erro).lower()
                if "thinking" in detalhe or "400" in str(erro):
                    texto = _post_gemini(
                        chave, nome, prompt, max_tokens, thinking=False, timeout=timeout
                    )
                else:
                    raise
            if texto:
                return texto, f"Google Gemini ({nome})"
            ultimo = f"Modelo {nome} retornou vazio."
        except Exception as erro:
            ultimo = str(erro)
            baixo = ultimo.lower()
            modelo_indisponivel = "404" in ultimo or "not_found" in baixo or "no longer available" in baixo
            if (modelo_indisponivel or _eh_timeout(erro)) and indice < len(fila) - 1:
                continue
            break
    raise RuntimeError(ultimo or "A IA não retornou conteúdo.")


def _openai_texto(prompt, chave, modelo, max_tokens):
    corpo = {
        "model": modelo,
        "temperature": 0.2,
        "max_tokens": max_tokens,
        "messages": [
            {
                "role": "system",
                "content": "Você auxilia abertura de processos administrativos no SEI. Responda só o pedido.",
            },
            {"role": "user", "content": prompt},
        ],
    }
    pedido = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(corpo).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {chave}",
        },
        method="POST",
    )
    with urllib.request.urlopen(pedido, timeout=25) as resp:
        dados = json.loads(resp.read().decode("utf-8"))
    texto = _texto(((dados.get("choices") or [{}])[0].get("message") or {}).get("content"))
    if not texto:
        raise RuntimeError("OpenAI retornou vazio.")
    return texto, f"OpenAI ({modelo})"


def _extrair_json(texto):
    bruto = _texto(texto)
    if not bruto:
        return {}
    if bruto.startswith("```"):
        bruto = re.sub(r"^```(?:json)?\s*", "", bruto, flags=re.IGNORECASE)
        bruto = re.sub(r"\s*```$", "", bruto)
    try:
        dados = json.loads(bruto)
        return dados if isinstance(dados, dict) else {}
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", bruto)
        if not match:
            return {}
        try:
            dados = json.loads(match.group(0))
            return dados if isinstance(dados, dict) else {}
        except json.JSONDecodeError:
            return {}


_PALAVRAS_GENERICAS = {
    "de", "da", "do", "das", "dos", "e", "ou", "a", "o", "as", "os",
    "um", "uma", "uns", "para", "por", "com", "sem", "em", "no", "na",
    "nos", "nas", "que", "se", "ao", "aos", "como", "sobre", "preciso",
    "precisa", "quero", "criar", "abrir", "elaborar", "processo",
    "documento", "sei", "tipo", "novo", "cadastro", "gerar", "favor",
    "gostaria", "necessito", "solicito", "informar", "informacao",
}


def _tokens_pedido(pedido):
    return [
        token
        for token in _normalizar(pedido).split()
        if len(token) > 2 and not token.isdigit() and token not in _PALAVRAS_GENERICAS
    ]


def _pontuar_catalogo(pedido, nome):
    """Quanto o nome da tabela aparece nas palavras do usuário."""
    alvo = _normalizar(pedido)
    norm = _normalizar(nome)
    if not alvo or not norm:
        return 0
    if norm == alvo or f" {norm} " in f" {alvo} ":
        return 1000
    tokens = _tokens_pedido(pedido)
    palavras = [p for p in norm.split() if p not in _PALAVRAS_GENERICAS and len(p) > 2]
    if not palavras:
        palavras = norm.split()
    hits = [token for token in tokens if token in palavras]
    if not hits:
        return 0
    cobertura = len(hits) / len(palavras)
    # Pedido curto: "Decreto" casa com "DOE: Decreto Numerado".
    # Pedido longo: uma palavra solta não puxa um tipo comprido.
    if len(tokens) <= 2 and cobertura >= 0.3:
        return 220 + int(cobertura * 200)
    if cobertura >= 0.5:
        return 300 + int(cobertura * 200)
    return 0


def _escolher_por_pedido(pedido, opcoes, chave="nome", minimo=200):
    alvo = _normalizar(pedido)
    palavras_alvo = set(alvo.split())
    ranked = []
    for item in opcoes or []:
        nome = _texto(item.get(chave) if isinstance(item, dict) else item)
        score = _pontuar_catalogo(pedido, nome)
        if score < minimo:
            continue
        norm_partes = _normalizar(nome).split()
        posicoes = [alvo.find(parte) for parte in norm_partes if parte in palavras_alvo and alvo.find(parte) >= 0]
        posicao = min(posicoes) if posicoes else 9999
        ranked.append((-score, posicao, len(norm_partes), item))
    if not ranked:
        return None, 0
    ranked.sort(key=lambda linha: (linha[0], linha[1], linha[2]))
    return ranked[0][3], -ranked[0][0]


def _melhor_match(consulta, opcoes, chave="nome"):
    alvo = _normalizar(consulta)
    if not alvo or not opcoes:
        return None
    melhor = None
    melhor_score = 0
    for item in opcoes:
        nome = _texto(item.get(chave) if isinstance(item, dict) else item)
        norm = _normalizar(nome)
        if not norm:
            continue
        if norm == alvo:
            return item if isinstance(item, dict) else {"nome": item}
        score = 0
        if alvo in norm or norm in alvo:
            score = min(len(alvo), len(norm))
        else:
            tokens = [t for t in alvo.split() if len(t) > 2]
            if tokens:
                hits = sum(1 for t in tokens if t in norm)
                score = hits * 10
        if score > melhor_score:
            melhor_score = score
            melhor = item if isinstance(item, dict) else {"nome": item}
    return melhor


def _recortar_lista(pedido, itens, extras=(), limite=6, chave="nome"):
    """Manda só os itens mais parecidos com o pedido, para a IA responder mais rápido."""
    tokens = [t for t in _normalizar(pedido).split() if len(t) > 3]
    pontuados = []
    for item in itens or []:
        nome = _normalizar(item.get(chave) if isinstance(item, dict) else item)
        score = sum(1 for token in tokens if token in nome)
        pontuados.append((score, item))
    pontuados.sort(key=lambda par: par[0], reverse=True)
    escolhidos = []
    vistos = set()

    def incluir(item):
        if not isinstance(item, dict):
            return
        marca = str(item.get("id") or item.get(chave) or "")
        if not marca or marca in vistos:
            return
        vistos.add(marca)
        escolhidos.append(item)

    for extra in extras:
        alvo = _normalizar(extra)
        if not alvo:
            continue
        for item in itens or []:
            nome = _normalizar(item.get(chave) if isinstance(item, dict) else "")
            if alvo == nome or alvo in nome or nome in alvo:
                incluir(item)
                break
    for score, item in pontuados:
        if len(escolhidos) >= limite:
            break
        if score <= 0 and len(escolhidos) >= 3:
            continue
        incluir(item)
    if len(escolhidos) < 3:
        for item in itens or []:
            if len(escolhidos) >= limite:
                break
            incluir(item)
    return escolhidos


def _escolher_tipo_processo(preferido, tipos):
    if preferido:
        achado = next(
            (t for t in tipos if _normalizar(t.get("nome")) == _normalizar(preferido)),
            None,
        )
        if achado:
            return achado
        prox = _melhor_match(preferido, tipos)
        if prox:
            return prox
    padrao = next((t for t in tipos if t.get("nome") == TIPO_CONTRATACAO), None)
    return padrao or (tipos[0] if tipos else None)


def _escolher_assunto(pedido, tipo_nome, assuntos, sugerido_ia=""):
    if sugerido_ia:
        direto = next(
            (a for a in assuntos if _normalizar(a.get("nome")) == _normalizar(sugerido_ia)),
            None,
        )
        if direto:
            return direto
        prox = _melhor_match(sugerido_ia, assuntos)
        if prox:
            return prox
    por_tipo = _melhor_match(tipo_nome, assuntos)
    if por_tipo:
        return por_tipo
    por_pedido = _melhor_match(pedido, assuntos)
    if por_pedido:
        return por_pedido
    # Preferência comum de contratação de serviço técnico.
    for trecho in (
        "contratação de serviço técnico profissional especializado",
        "contratação de serviço técnico",
        "expediente de atendimento",
    ):
        achado = _melhor_match(trecho, assuntos)
        if achado:
            return achado
    return assuntos[0] if assuntos else None


def _escolher_documento(sugerido_id, sugerido_nome, tipos_doc, pedido=""):
    if pedido:
        por_texto, _score = _escolher_por_pedido(pedido, tipos_doc)
        if por_texto:
            return por_texto
    if sugerido_id:
        achado = next((t for t in tipos_doc if str(t.get("id")) == str(sugerido_id)), None)
        if achado:
            return achado
    if sugerido_nome:
        prox = _melhor_match(sugerido_nome, tipos_doc)
        if prox:
            return prox
    for trecho in (
        "Relatório de Justificativa - OS",
        "Termo",
        "Despacho",
    ):
        achado = next((t for t in tipos_doc if t.get("nome") == trecho), None)
        if achado:
            return achado
        prox = _melhor_match(trecho, tipos_doc)
        if prox:
            return prox
    return tipos_doc[0] if tipos_doc else None


def _especificacao_curta(pedido, ia_valor=""):
    texto = _texto(ia_valor) or _texto(pedido)
    texto = re.sub(r"\s+", " ", texto).strip()
    if len(texto) > 220:
        texto = texto[:217].rstrip() + "..."
    return texto or "Abertura de processo assistida por IA"


def montar_pacote_confirmado(pedido, tipo, tipo_doc, assunto=None, fonte="Assistente IA"):
    """Monta o payload final depois que o usuário confirmou processo e documento."""
    pedido = _texto(pedido)
    if not tipo:
        raise ValueError("Selecione um tipo de processo.")
    if not tipo_doc:
        raise ValueError("Selecione um tipo de documento.")
    assuntos = banco.listar_assuntos_sei()
    if not assunto:
        assunto = banco.obter_assunto_do_tipo_processo(
            tipo_processo_id_sei=tipo.get("id_sei") or "",
            tipo_processo_nome=tipo.get("nome") or "",
        )
    if not assunto:
        assunto = _escolher_assunto(pedido, tipo.get("nome"), assuntos)
    if not assunto:
        raise ValueError("Não foi possível escolher um assunto SEI.")
    observacoes = f"Abertura assistida por IA. Pedido: {pedido[:300]}"
    processo = {
        "tipo_processo_sei": tipo.get("nome"),
        "assunto": tipo.get("nome") or "",
        "processo_contratacao": {
            "especificacao": "",
            "descricao": "",
            "prioridade": "",
            "interessados": [INTERESSADO_PADRAO],
            "assuntos": [assunto.get("nome")],
            "observacoes": observacoes,
            "nivel_acesso": "publico",
        },
        "processo_sei": {
            "protocolo": "automatico",
            "especificacao": "",
            "prioridade": "",
            "interessados": [INTERESSADO_PADRAO],
            "assuntos": [assunto.get("nome")],
            "observacoes": observacoes,
            "nivel_acesso": "publico",
        },
    }
    documento = {
        "idSerie": str(tipo_doc.get("id")),
        "descricao": "",
        "nomeArvore": "",
        "nivelAcesso": "0",
        "assuntos": str(assunto.get("id_sei") or "") if tipo_doc.get("precisa_assunto") else "",
        "observacao": "",
        "idUnidadeGeradoraProtocolo": UNIDADE_GERADORA_PADRAO,
    }
    if tipo_doc.get("precisa_numero"):
        documento["numero"] = "DDS001"
    nome_doc = tipo_doc.get("nome") or "Documento"
    return {
        "ok": True,
        "fonte": fonte,
        "resumo": f"Processo “{tipo.get('nome')}” + documento “{nome_doc}”",
        "pedido": pedido,
        "processo": processo,
        "documento": documento,
        "preview": {
            "tipo_processo": tipo.get("nome"),
            "especificacao": "",
            "assunto": assunto.get("nome"),
            "nivel_acesso": "publico",
            "interessado": INTERESSADO_PADRAO,
            "tipo_documento": f"{tipo_doc.get('id')} — {nome_doc}",
            "descricao_documento": nome_doc,
            "nome_arvore": nome_doc[:80],
        },
    }


def montar_abertura(descricao, tipo_processo_preferido=""):
    pedido = _texto(descricao)
    if len(pedido) < 3:
        raise ValueError("Informe ao menos uma palavra, como Decreto, Ofício ou Contrato.")

    tipos = banco.listar_tipos_processo_sei()
    assuntos = banco.listar_assuntos_sei()
    tipos_doc = banco.listar_tipos_documento_sei()
    if not tipos:
        raise ValueError("Nenhum tipo de processo SEI cadastrado.")
    if not assuntos:
        raise ValueError("Nenhum assunto SEI cadastrado.")
    if not tipos_doc:
        raise ValueError("Nenhum tipo documental SEI cadastrado.")

    tipo_local, score_tipo = _escolher_por_pedido(pedido, tipos)
    doc_local, score_doc = _escolher_por_pedido(pedido, tipos_doc)
    assunto_local, _score_assunto = _escolher_por_pedido(pedido, assuntos, minimo=400)
    preferido = _texto(tipo_processo_preferido)
    if preferido == TIPO_CONTRATACAO and score_tipo >= 200:
        preferido = ""
    extra_tipo = (tipo_local or {}).get("nome") or preferido or TIPO_CONTRATACAO
    extra_doc = (doc_local or {}).get("nome") or "Relatório de Justificativa - OS"
    tipos_curtos = _recortar_lista(pedido, tipos, extras=[extra_tipo], limite=6)
    assuntos_curtos = _recortar_lista(pedido, assuntos, extras=[extra_tipo, (assunto_local or {}).get("nome", "")], limite=6)
    docs_curtos = _recortar_lista(pedido, tipos_doc, extras=[extra_doc], limite=6)
    lista_tipos = "\n".join(f"- {t.get('nome')}" for t in tipos_curtos)
    lista_assuntos = "\n".join(f"- {a.get('nome')}" for a in assuntos_curtos)
    lista_docs = "\n".join(f"- id={t.get('id')} | {t.get('nome')}" for t in docs_curtos)

    prompt = (
        "Você monta a abertura de um processo no SEI (homologação PRODESP).\n"
        "Responda APENAS um JSON válido, sem markdown, com este formato:\n"
        "{\n"
        '  "tipo_processo_sei": "nome EXATO da lista",\n'
        '  "especificacao": "texto curto do objeto",\n'
        '  "observacoes": "opcional",\n'
        '  "nivel_acesso": "publico|restrito|sigiloso",\n'
        '  "prioridade": "",\n'
        '  "assunto_nome": "nome EXATO da lista de assuntos",\n'
        '  "documento": {\n'
        '    "idSerie": "id numérico da lista",\n'
        '    "nome_tipo": "nome do tipo documental",\n'
        '    "descricao": "descrição do documento",\n'
        '    "nomeArvore": "nome curto na árvore",\n'
        '    "observacao": "",\n'
        '    "nivelAcesso": "0"\n'
        "  },\n"
        '  "resumo": "frase curta do que será criado"\n'
        "}\n\n"
        f"Pedido do usuário:\n{pedido}\n\n"
        f"Tipo preferido (se houver): {preferido or '(nenhum — use a palavra do pedido)'}\n\n"
        f"Tipos de processo disponíveis:\n{lista_tipos}\n\n"
        f"Assuntos disponíveis:\n{lista_assuntos}\n\n"
        f"Tipos de documento disponíveis:\n{lista_docs}\n\n"
        "Regras: escolha apenas itens das listas. Se uma palavra do pedido for o nome "
        "de um tipo de processo ou de documento, use esse item. Não troque por outro tipo. "
        "nivel_acesso padrão publico; nivelAcesso do documento padrão 0."
    )

    fonte = "Catálogo interno"
    bruto = {}
    pedido_curto = len(_tokens_pedido(pedido)) <= 2
    catalogo_fechado = score_tipo >= 200 and score_doc >= 200
    # Palavra já achada na tabela, ou frase curta com um tipo claro: não espera a IA.
    if not catalogo_fechado and not (pedido_curto and (score_tipo >= 200 or score_doc >= 200)):
        try:
            texto_ia, fonte = _gemini_texto(prompt, max_tokens=500)
            bruto = _extrair_json(texto_ia)
        except ValueError:
            raise
        except Exception:
            bruto = {}

    if score_tipo >= 200:
        tipo = tipo_local
    else:
        tipo = _escolher_tipo_processo(
            _texto(bruto.get("tipo_processo_sei")) or preferido or TIPO_CONTRATACAO,
            tipos,
        )
    if not tipo:
        raise ValueError("Não foi possível escolher um tipo de processo.")

    assunto = assunto_local or _escolher_assunto(
        pedido,
        tipo.get("nome"),
        assuntos,
        _texto(bruto.get("assunto_nome")),
    )
    if not assunto:
        raise ValueError("Não foi possível escolher um assunto SEI.")

    doc_bruto = bruto.get("documento") if isinstance(bruto.get("documento"), dict) else {}
    if score_doc >= 200:
        tipo_doc = doc_local
    else:
        tipo_doc = _escolher_documento(
            _texto(doc_bruto.get("idSerie")),
            _texto(doc_bruto.get("nome_tipo")) or _texto(doc_bruto.get("descricao")),
            tipos_doc,
            pedido,
        )
    if not tipo_doc:
        raise ValueError("Não foi possível escolher um tipo documental.")

    especificacao = _especificacao_curta(pedido, bruto.get("especificacao"))
    nivel = _texto(bruto.get("nivel_acesso")).casefold()
    if nivel not in {"publico", "restrito", "sigiloso"}:
        nivel = "publico"
    observacoes = _texto(bruto.get("observacoes")) or f"Abertura assistida por IA. Pedido: {pedido[:300]}"
    prioridade = _texto(bruto.get("prioridade"))

    descricao_doc = _texto(doc_bruto.get("descricao")) or tipo_doc.get("nome") or "Documento interno"
    nome_arvore = _texto(doc_bruto.get("nomeArvore")) or descricao_doc[:80]
    obs_doc = _texto(doc_bruto.get("observacao"))
    nivel_doc = _texto(doc_bruto.get("nivelAcesso")) or "0"
    if nivel_doc not in {"0", "1", "2"}:
        nivel_doc = "0"

    processo = {
        "tipo_processo_sei": tipo.get("nome"),
        "assunto": especificacao,
        "processo_contratacao": {
            "especificacao": especificacao,
            "descricao": especificacao,
            "prioridade": prioridade,
            "interessados": [INTERESSADO_PADRAO],
            "assuntos": [assunto.get("nome")],
            "observacoes": observacoes,
            "nivel_acesso": nivel,
        },
        "processo_sei": {
            "protocolo": "automatico",
            "especificacao": especificacao,
            "prioridade": prioridade,
            "interessados": [INTERESSADO_PADRAO],
            "assuntos": [assunto.get("nome")],
            "observacoes": observacoes,
            "nivel_acesso": nivel,
        },
    }

    documento = {
        "idSerie": str(tipo_doc.get("id")),
        "descricao": "",
        "nomeArvore": "",
        "nivelAcesso": nivel_doc,
        "assuntos": str(assunto.get("id_sei") or "") if tipo_doc.get("precisa_assunto") else "",
        "observacao": "",
        "idUnidadeGeradoraProtocolo": UNIDADE_GERADORA_PADRAO,
    }
    if tipo_doc.get("precisa_numero"):
        documento["numero"] = "DDS001"

    resumo = _texto(bruto.get("resumo")) or (
        f"Processo “{tipo.get('nome')}” + documento “{tipo_doc.get('nome')}” "
        f"sobre: {especificacao}"
    )

    return {
        "ok": True,
        "fonte": fonte,
        "resumo": resumo,
        "pedido": pedido,
        "processo": processo,
        "documento": documento,
        "preview": {
            "tipo_processo": tipo.get("nome"),
            "especificacao": especificacao,
            "assunto": assunto.get("nome"),
            "nivel_acesso": nivel,
            "interessado": INTERESSADO_PADRAO,
            "tipo_documento": f"{tipo_doc.get('id')} — {tipo_doc.get('nome')}",
            "descricao_documento": descricao_doc,
            "nome_arvore": nome_arvore,
        },
    }


def gerar_html_secao(prompt, contexto="", tipo_documento=""):
    pedido = _texto(prompt)
    if not pedido:
        raise ValueError("Descreva o que a IA deve preencher na seção.")
    instrucao = (
        "Gere o conteúdo de uma seção de documento administrativo do SEI/PRODESP.\n"
        "Responda SOMENTE HTML simples com tags <p>, <strong>, <em>, <ul>, <ol>, <li>, <table>, <tr>, <th>, <td>.\n"
        "Sem markdown, sem ``` e sem explicações fora do HTML.\n"
        "Texto formal em português do Brasil.\n\n"
        f"Tipo do documento: {_texto(tipo_documento) or '(não informado)'}\n"
        f"Contexto atual da seção (pode estar vazio):\n{_texto(contexto)[:2000]}\n\n"
        f"Pedido:\n{pedido}"
    )
    texto, fonte = _gemini_texto(instrucao, max_tokens=1200)
    html = _texto(texto)
    if html.startswith("```"):
        html = re.sub(r"^```(?:html)?\s*", "", html, flags=re.IGNORECASE)
        html = re.sub(r"\s*```$", "", html)
    if "<" not in html:
        paragrafos = [f"<p>{escape_basico(p)}</p>" for p in re.split(r"\n\s*\n", html) if p.strip()]
        html = "".join(paragrafos) or f"<p>{escape_basico(html)}</p>"
    return {"ok": True, "html": html, "fonte": fonte}


_MESES_PT = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)


def _mes_ano_atual():
    from datetime import datetime

    agora = datetime.now()
    return f"{_MESES_PT[agora.month - 1]}/{agora.year}"


def _ids_campo_conhecidos(tag):
    """Normaliza id + rótulo para casar campos equivalentes entre formulários."""
    partes = [_normalizar(tag.get("id")), _normalizar(tag.get("rotulo"))]
    return " ".join(p for p in partes if p)


def _valor_sistema_para_tag(tag, contexto):
    """Preenche campos objetivos a partir do processo/sessão, sem chamar a IA."""
    chave = _ids_campo_conhecidos(tag)
    if not chave:
        return None
    numero = _texto(contexto.get("numero_sei"))
    interessado = _texto(contexto.get("interessado")) or INTERESSADO_PADRAO
    assunto = _texto(contexto.get("assunto"))
    data = _texto(contexto.get("data")) or _mes_ano_atual()

    if any(x in chave for x in ("numero sei", "n processo sei", "n proc sei", "processo sei", "numero_sei", "n_processo")):
        return numero or None
    if "interessado" in chave:
        return interessado
    if chave in {"data", "mes ano", "mes_ano"} or "mes e ano" in chave or chave.endswith(" mes ano"):
        return data
    if chave in {"assunto", "assunto processo", "assunto_processo"} or (
        "assunto" in chave and "documento" not in chave
    ):
        return assunto or None
    return None


def sugerir_preenchimento_formulario(formulario, contexto=None):
    """
    Analisa as tags do formulário escolhido e sugere valores.
    Campos de sistema (SEI, interessado, data…) vêm do contexto;
    demais campos de texto/número vêm da IA a partir do pedido do usuário.
    Tabelas ficam de fora nesta etapa.
    """
    contexto = contexto if isinstance(contexto, dict) else {}
    form = formulario if isinstance(formulario, dict) else {}
    tags = [
        tag for tag in (form.get("tags") or [])
        if isinstance(tag, dict) and _texto(tag.get("id")) and not tag.get("calculado")
    ]
    if not tags:
        raise ValueError("O formulário selecionado não possui campos para preencher.")

    valores = {}
    pendentes = []
    for tag in tags:
        tipo = _texto(tag.get("tipo")) or "texto"
        if tipo == "tabela":
            continue
        sistema = _valor_sistema_para_tag(tag, contexto)
        if sistema:
            valores[tag["id"]] = sistema
        else:
            pendentes.append({
                "id": tag["id"],
                "rotulo": _texto(tag.get("rotulo")) or tag["id"],
                "tipo": tipo,
                "grupo": _texto(tag.get("grupo")) or "Geral",
            })

    fonte_partes = ["sistema"]
    aviso_ia = ""
    if pendentes:
        pedido = _texto(contexto.get("pedido") or contexto.get("descricao") or contexto.get("texto"))
        # Lista enxuta: só id + rótulo (menos tokens → resposta mais rápida).
        campos_json = json.dumps(
            [{"id": item["id"], "rotulo": item["rotulo"]} for item in pendentes],
            ensure_ascii=False,
        )
        instrucao = (
            "Preencha formulário PRODESP/SEI. Responda SÓ JSON: "
            "{\"valores\":{\"id\":\"texto\"}}.\n"
            "PT-BR formal. Não invente horas/PF/UE/prazos/valores se não estiverem no pedido. "
            "Pode inferir tecnologia, projeto e objetivo do pedido. Sem tabelas. Sem texto fora do JSON.\n"
            f"Formulário: {_texto(form.get('nome')) or _texto(form.get('id')) or '(sem nome)'}\n"
            f"SEI: {_texto(contexto.get('numero_sei')) or '-'}\n"
            f"Interessado: {_texto(contexto.get('interessado')) or INTERESSADO_PADRAO}\n"
            f"Assunto: {_texto(contexto.get('assunto')) or '-'}\n"
            f"Tipo processo: {_texto(contexto.get('tipo_processo')) or '-'}\n"
            f"Mês/ano: {_texto(contexto.get('data')) or _mes_ano_atual()}\n"
            f"Pedido:\n{(pedido or '-')[:2500]}\n"
            f"Campos:\n{campos_json}"
        )
        try:
            texto, fonte_ia = _gemini_texto(
                instrucao,
                max_tokens=900,
                timeout=55,
                preferir_rapido=True,
            )
            dados = _extrair_json(texto)
            sugeridos = dados.get("valores") if isinstance(dados.get("valores"), dict) else {}
            ids_ok = {item["id"] for item in pendentes}
            for chave, valor in sugeridos.items():
                if chave in ids_ok and _texto(valor):
                    valores[chave] = _texto(valor)
            fonte_partes.append(fonte_ia)
        except Exception as erro:
            # Mantém o que o sistema já preencheu; o usuário completa o restante.
            aviso_ia = (
                "A IA demorou demais para sugerir os demais campos. "
                "Os campos objetivos já foram preenchidos; complete o restante manualmente."
                if _eh_timeout(erro)
                else f"A IA não conseguiu sugerir os demais campos ({erro})."
            )

    return {
        "ok": True,
        "valores": valores,
        "fonte": " + ".join(fonte_partes),
        "aviso": aviso_ia,
        "campos_sugeridos": len(valores),
        "campos_ignorados_tabela": sum(
            1 for tag in tags if (_texto(tag.get("tipo")) or "texto") == "tabela"
        ),
    }


def escape_basico(texto):
    return (
        _texto(texto)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
