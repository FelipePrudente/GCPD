# -*- coding: utf-8 -*-
"""Sugere certificações a partir da tecnologia e dos perfis cadastrados.

1. Consulta a internet (DuckDuckGo HTML) com tecnologia + perfil.
2. Extrai nomes que parecem certificações oficiais.
3. Complementa com acervo local de fabricantes conhecidos.

O usuário revisa as sugestões na tela antes de gravar no formulário.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from html import unescape

AGENTE = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

PADROES = [
    re.compile(r"\bAWS Certified [A-Za-z0-9 /+\-]{3,80}", re.I),
    re.compile(r"\bMicrosoft Certified[:]?[^\.|<\n]{3,90}", re.I),
    re.compile(
        r"\bAzure [A-Za-z0-9 \-]{0,40}"
        r"(?:Administrator|Developer|Architect|Engineer|Security|Fundamentals)"
        r"[^\.|<\n]{0,40}",
        re.I,
    ),
    re.compile(r"\b(?:AZ|DP|AI|PL|MB|SC|MS)-\d{3,4}[^\.|<\n]{0,60}", re.I),
    re.compile(r"\bGoogle Cloud (?:Professional |Associate )?[A-Za-z0-9 \-]{3,60}", re.I),
    re.compile(r"\b(?:CKA|CKAD|CKS|KCNA)\b", re.I),
    re.compile(r"\bCertified Kubernetes [A-Za-z ]{3,40}", re.I),
    re.compile(r"\bCompTIA [A-Za-z+ ]{2,40}", re.I),
    re.compile(r"\bCISSP\b|\bCISM\b|\bCISA\b|\bCCSP\b", re.I),
    re.compile(r"\bPMP\b|\bPMI-ACP\b|\bCAPM\b", re.I),
    re.compile(r"\b(?:ITIL|TOGAF|COBIT)[^\.|<\n]{0,40}", re.I),
    re.compile(r"\bOracle Certified [A-Za-z0-9 \-]{3,60}", re.I),
    re.compile(r"\bSalesforce Certified [A-Za-z0-9 \-]{3,60}", re.I),
    re.compile(r"\bHashiCorp Certified[^\.|<\n]{0,50}", re.I),
    re.compile(r"\bRed Hat Certified [A-Za-z0-9 \-]{3,50}", re.I),
    re.compile(
        r"\bCertified [A-Za-z0-9 \-/+]{6,70}"
        r"(?:Professional|Associate|Expert|Specialist|Engineer|Architect)\b",
        re.I,
    ),
]

ACERVO = {
    "aws": [
        ("AWS Certified Solutions Architect – Associate", "Arquiteto / Cloud"),
        ("AWS Certified Solutions Architect – Professional", "Arquiteto Sênior"),
        ("AWS Certified Developer – Associate", "Desenvolvedor Cloud"),
        ("AWS Certified DevOps Engineer – Professional", "DevOps"),
        ("AWS Certified SysOps Administrator – Associate", "Operações / SysOps"),
        ("AWS Certified Security – Specialty", "Segurança Cloud"),
        ("AWS Certified Data Engineer – Associate", "Engenharia de Dados"),
    ],
    "microsoft": [
        ("Microsoft Certified: Azure Administrator Associate (AZ-104)", "Administração Azure"),
        ("Microsoft Certified: Azure Developer Associate (AZ-204)", "Desenvolvimento Azure"),
        ("Microsoft Certified: Azure Solutions Architect Expert (AZ-305)", "Arquitetura Azure"),
        ("Microsoft Certified: Power Platform Developer Associate (PL-400)", "Power Platform"),
        ("Microsoft Certified: Dynamics 365 Developer Associate", "Dynamics 365"),
        ("Microsoft Certified: Dynamics 365 Fundamentals (MB-910 / MB-920)", "Dynamics fundamentos"),
        ("Microsoft Certified: Azure AI Engineer Associate (AI-102)", "IA / ML"),
    ],
    "azure": [
        ("Microsoft Certified: Azure Administrator Associate (AZ-104)", "Administração Azure"),
        ("Microsoft Certified: Azure Developer Associate (AZ-204)", "Desenvolvimento Azure"),
        ("Microsoft Certified: Azure Solutions Architect Expert (AZ-305)", "Arquitetura Azure"),
        ("Microsoft Certified: Azure Security Engineer Associate (AZ-500)", "Segurança Azure"),
    ],
    "dynamics": [
        ("Microsoft Certified: Dynamics 365 Developer Associate", "Dynamics 365"),
        ("Microsoft Certified: Power Platform Developer Associate (PL-400)", "Power Apps / Power Platform"),
        ("Microsoft Certified: Dynamics 365 Fundamentals (MB-910 / MB-920)", "Dynamics fundamentos"),
        ("Microsoft Certified: Power Platform Functional Consultant Associate (PL-200)", "Consultoria funcional"),
    ],
    "google": [
        ("Google Cloud Associate Cloud Engineer", "Engenharia Cloud"),
        ("Google Cloud Professional Cloud Architect", "Arquitetura Cloud"),
        ("Google Cloud Professional Data Engineer", "Engenharia de Dados"),
        ("Google Cloud Professional DevOps Engineer", "DevOps"),
    ],
    "kubernetes": [
        ("Certified Kubernetes Administrator (CKA)", "Administração Kubernetes"),
        ("Certified Kubernetes Application Developer (CKAD)", "Desenvolvimento Kubernetes"),
        ("Certified Kubernetes Security Specialist (CKS)", "Segurança Kubernetes"),
    ],
    "nuvem": [
        ("AWS Certified Solutions Architect – Associate", "Arquitetura Cloud"),
        ("Microsoft Certified: Azure Administrator Associate (AZ-104)", "Administração Cloud"),
        ("Google Cloud Associate Cloud Engineer", "Engenharia Cloud"),
        ("CompTIA Cloud+", "Fundamentos de nuvem"),
    ],
    "dados": [
        ("AWS Certified Data Engineer – Associate", "Engenharia de Dados"),
        ("Google Cloud Professional Data Engineer", "Engenharia de Dados"),
        ("Microsoft Certified: Azure Data Engineer Associate (DP-203)", "Engenharia de Dados Azure"),
    ],
    "seguranca": [
        ("CISSP", "Segurança da informação"),
        ("CompTIA Security+", "Fundamentos de segurança"),
        ("AWS Certified Security – Specialty", "Segurança Cloud"),
        ("Microsoft Certified: Azure Security Engineer Associate (AZ-500)", "Segurança Azure"),
    ],
}


def _texto(valor):
    return str(valor or "").strip()


def _normalizar_nome(nome):
    texto = re.sub(r"\s+", " ", _texto(nome))
    texto = texto.strip(" -:;,.")
    if len(texto) < 3 or len(texto) > 120:
        return ""
    return texto


def _chave_acervo(tecnologia):
    texto = _texto(tecnologia).lower()
    mapa = [
        ("aws", "aws"),
        ("amazon", "aws"),
        ("dynamics", "dynamics"),
        ("power apps", "dynamics"),
        ("power platform", "dynamics"),
        ("microsoft", "microsoft"),
        ("azure", "azure"),
        ("google", "google"),
        ("gcp", "google"),
        ("kubernetes", "kubernetes"),
        ("k8s", "kubernetes"),
        ("armazen", "dados"),
        ("dados", "dados"),
        ("data", "dados"),
        ("nuvem", "nuvem"),
        ("cloud", "nuvem"),
        ("segura", "seguranca"),
        ("security", "seguranca"),
    ]
    for termo, chave in mapa:
        if termo in texto:
            return chave
    return ""


def _baixar(url):
    pedido = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    with urllib.request.urlopen(pedido, timeout=18) as resposta:
        return resposta.read().decode("utf-8", errors="ignore")


def _buscar_web(consulta):
    url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": consulta})
    try:
        html = _baixar(url)
    except Exception:
        return []
    blocos = []
    for titulo, trecho in re.findall(
        r'class="result__a"[^>]*>(.*?)</a>.*?class="result__snippet"[^>]*>(.*?)</(?:a|td)',
        html,
        flags=re.I | re.S,
    ):
        limpo = unescape(re.sub(r"<[^>]+>", " ", f"{titulo} {trecho}"))
        limpo = re.sub(r"\s+", " ", limpo).strip()
        if limpo:
            blocos.append(limpo)
    if not blocos:
        texto = unescape(re.sub(r"<[^>]+>", " ", html))
        texto = re.sub(r"\s+", " ", texto)
        blocos.append(texto[:4000])
    return blocos


def _extrair_certificacoes(textos):
    achados = []
    vistos = set()
    for texto in textos:
        for padrao in PADROES:
            for match in padrao.findall(texto):
                nome = _normalizar_nome(match)
                chave = nome.lower()
                if not nome or chave in vistos:
                    continue
                vistos.add(chave)
                achados.append(nome)
    return achados


def _do_acervo(tecnologia, perfis):
    chave = _chave_acervo(tecnologia)
    if not chave:
        return []
    itens = []
    perfil_txt = " ".join(perfis).lower()
    for nome, contexto in ACERVO.get(chave, []):
        peso = 1
        for palavra in re.findall(r"[a-zà-ú]{4,}", contexto.lower()):
            if palavra in perfil_txt:
                peso += 1
        itens.append((peso, nome, f"Acervo local ({contexto})"))
    itens.sort(key=lambda item: (-item[0], item[1].lower()))
    return [{"nome": nome, "fonte": fonte, "origem": "acervo"} for _, nome, fonte in itens]


def sugerir_certificacoes(tecnologia, perfis):
    tecnologia = _texto(tecnologia)
    if not tecnologia:
        raise ValueError("Informe a tecnologia antes de buscar certificações.")
    nomes_perfil = []
    for item in perfis or []:
        if isinstance(item, dict):
            nome = _texto(item.get("perfil"))
        else:
            nome = _texto(item)
        if nome and nome not in nomes_perfil:
            nomes_perfil.append(nome)
    if not nomes_perfil:
        raise ValueError("Informe ao menos um perfil no cadastro para orientar a busca.")

    sugestoes = []
    vistos = set()
    avisos = []

    for nome, fonte, origem in [
        (item["nome"], item["fonte"], item["origem"]) for item in _do_acervo(tecnologia, nomes_perfil)
    ]:
        chave = nome.lower()
        if chave in vistos:
            continue
        vistos.add(chave)
        sugestoes.append({
            "nome": nome,
            "fonte": fonte,
            "origem": origem,
            "perfis": nomes_perfil[:4],
        })

    consultas = [
        f"certificações profissionais {tecnologia} {' '.join(nomes_perfil[:3])}",
        f"{tecnologia} required certifications {nomes_perfil[0]}",
    ]
    textos_web = []
    for consulta in consultas:
        textos_web.extend(_buscar_web(consulta))
    if not textos_web:
        avisos.append("A consulta à internet não retornou trechos úteis; use o acervo local e revise manualmente.")
    else:
        for nome in _extrair_certificacoes(textos_web):
            chave = nome.lower()
            if chave in vistos:
                continue
            vistos.add(chave)
            sugestoes.append({
                "nome": nome,
                "fonte": "Busca na internet (DuckDuckGo)",
                "origem": "web",
                "perfis": nomes_perfil[:4],
            })

    if not sugestoes:
        raise ValueError(
            "Não foi possível sugerir certificações para esta tecnologia/perfis. "
            "Tente ajustar os nomes ou incluir certificações manualmente."
        )

    return {
        "tecnologia": tecnologia,
        "perfis": nomes_perfil,
        "certificacoes": sugestoes[:18],
        "avisos": avisos,
    }


_STOPWORDS_BUSCA = {
    "a", "o", "os", "as", "um", "uma", "uns", "umas", "de", "da", "do", "das", "dos",
    "e", "ou", "em", "no", "na", "nos", "nas", "por", "para", "com", "sem", "que",
    "qual", "quais", "como", "sobre", "pelo", "pela", "pelos", "pelas", "ao", "à",
    "the", "and", "or", "of", "in", "on", "to", "for", "with", "from", "is", "are",
    "was", "were", "be", "this", "that", "an", "as", "at", "by", "it",
}


def _tokens_busca(texto):
    return {
        token
        for token in re.findall(r"[a-zà-ú0-9]{3,}", str(texto or "").lower())
        if token not in _STOPWORDS_BUSCA
    }


def _relevancia_busca(trecho, consulta):
    tokens_consulta = _tokens_busca(consulta)
    tokens_trecho = _tokens_busca(trecho)
    if not tokens_consulta:
        return 0.0
    inter = len(tokens_consulta & tokens_trecho)
    return inter / len(tokens_consulta)


def _trecho_inutil(texto):
    baixo = str(texto or "").lower()
    bloqueios = (
        "unfortunately, bots use duckduckgo",
        "complete the following challenge",
        "please enable cookies",
        "captcha",
        "verify you are a human",
    )
    return any(item in baixo for item in bloqueios)


def _buscar_ddg_api(consulta):
    url = "https://api.duckduckgo.com/?" + urllib.parse.urlencode({
        "q": consulta,
        "format": "json",
        "no_html": "1",
        "skip_disambig": "1",
    })
    try:
        bruto = json.loads(_baixar(url))
    except Exception:
        return []
    textos = []
    abstract = _texto(bruto.get("AbstractText"))
    abstract_fonte = _texto(bruto.get("AbstractSource"))
    if abstract:
        if abstract_fonte:
            textos.append(f"{abstract} (Fonte: {abstract_fonte})")
        else:
            textos.append(abstract)
    resposta = _texto(bruto.get("Answer"))
    if resposta:
        textos.append(resposta)
    definicao = _texto(bruto.get("Definition"))
    if definicao:
        textos.append(definicao)
    for item in bruto.get("RelatedTopics") or []:
        if isinstance(item, dict) and item.get("Text"):
            textos.append(_texto(item.get("Text")))
        elif isinstance(item, dict):
            for sub in item.get("Topics") or []:
                if isinstance(sub, dict) and sub.get("Text"):
                    textos.append(_texto(sub.get("Text")))
    return [t for t in textos if t and not _trecho_inutil(t)]


def _buscar_wikipedia(consulta):
    try:
        url_busca = "https://pt.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
            "action": "opensearch",
            "search": consulta,
            "limit": 5,
            "namespace": 0,
            "format": "json",
        })
        dados = json.loads(_baixar(url_busca))
        titulos = dados[1] if isinstance(dados, list) and len(dados) > 1 else []
        descricoes = dados[2] if isinstance(dados, list) and len(dados) > 2 else []
    except Exception:
        return []
    textos = []
    for indice, titulo in enumerate(titulos[:5]):
        desc = descricoes[indice] if indice < len(descricoes) else ""
        if desc:
            textos.append(f"{titulo}: {desc}")
        try:
            url_resumo = "https://pt.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(titulo)
            resumo = json.loads(_baixar(url_resumo))
            extract = _texto(resumo.get("extract"))
            if extract:
                textos.append(extract)
        except Exception:
            continue
    return [t for t in textos if t and not _trecho_inutil(t)]


def sugerir_texto_campo(consulta, tecnologia="", rotulo="", usar_tecnologia=False):
    """Busca trechos na internet com base no prompt do usuário.

    Por padrão NÃO mistura a tecnologia do formulário na consulta, para evitar
    respostas fora de contexto (ex.: pergunta de ágil + tecnologia AWS).
    """
    consulta = _texto(consulta) or _texto(rotulo)
    if not consulta:
        raise ValueError("Escreva o que você quer buscar neste campo.")
    tecnologia = _texto(tecnologia)
    consultas = [consulta]
    if usar_tecnologia and tecnologia:
        consultas.append(f"{consulta} {tecnologia}")

    textos = []
    fontes = []
    for termo in consultas:
        api = _buscar_ddg_api(termo)
        if api:
            textos.extend(api)
            fontes.append("DuckDuckGo API")
        wiki = _buscar_wikipedia(termo)
        if wiki:
            textos.extend(wiki)
            fontes.append("Wikipedia")
        html = [t for t in _buscar_web(termo) if not _trecho_inutil(t)]
        if html:
            textos.extend(html)
            fontes.append("DuckDuckGo HTML")

    if not textos:
        raise ValueError("A busca na internet não retornou trechos úteis para este campo.")

    ranqueados = []
    vistos = set()
    for item in textos:
        chave = item.lower()
        if chave in vistos or len(item) < 24 or _trecho_inutil(item):
            continue
        vistos.add(chave)
        score = _relevancia_busca(item, consulta)
        ranqueados.append((score, item))
    ranqueados.sort(key=lambda par: (-par[0], -len(par[1])))

    filtrados = [item for score, item in ranqueados if score >= 0.12]
    if not filtrados:
        filtrados = [item for score, item in ranqueados if score > 0][:6]
    if not filtrados:
        filtrados = [item for _, item in ranqueados[:4]]

    itens = [{"id": indice + 1, "texto": texto} for indice, texto in enumerate(filtrados[:8])]
    if not itens:
        raise ValueError("A busca na internet não retornou trechos úteis para este campo.")
    fonte = " + ".join(dict.fromkeys(fontes)) if fontes else "Busca na internet"
    return {
        "consulta": consulta if not (usar_tecnologia and tecnologia) else f"{consulta} | tecnologia: {tecnologia}",
        "itens": itens,
        "sugestao": "\n\n".join(item["texto"] for item in itens),
        "fonte": fonte,
    }
