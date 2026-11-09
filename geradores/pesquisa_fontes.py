# -*- coding: utf-8 -*-
"""Consulta o guia salarial Robert Half (Brasil) e devolve faixa CLT mensal.

A média do documento é (percentil 25 + percentil 75) / 2. A mediana publicada
não entra no cálculo. Cargo sem faixa publicada fica sem valor.
"""
import re
import unicodedata
import urllib.request

from geradores.comum import cargo_base, senioridade

SITEMAP = (
    "https://www.roberthalf.com/content/"
    "roberthalf.sitemap.br-pt-external-role-details-sitemap.xml"
)
AGENTE = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

_SLUGS = None

# prefixo do slug nacional, título publicado, aderência inicial
FAMILIAS = {
    "desenvolvedor": [
        ("desenvolvedora-back-end", "Desenvolvedor(a) Back-End", "media"),
        ("desenvolvedora-full-stack", "Desenvolvedor(a) Full-Stack", "media"),
    ],
    "front": [("desenvolvedora-front-end", "Desenvolvedor(a) Front-End", "alta")],
    "mobile": [("desenvolvedora-mobile", "Desenvolvedor(a) Mobile", "alta")],
    "rpa": [("desenvolvedora-rpa", "Desenvolvedor(a) RPA", "alta")],
    "arquiteto": [("arquiteto-de-software", "Arquiteto de Software", "alta")],
    "scrum": [("scrum-master", "Scrum Master", "alta")],
    "cientista": [
        ("especialistacientista-de-dados", "Especialista/Cientista de Dados", "media")
    ],
    "dados": [
        ("engenheiro-de-dados", "Engenheiro de Dados", "alta"),
        ("gerente-de-dados", "Gerente de Dados", "media"),
    ],
    "bi": [("gerente-de-bi", "Gerente de BI", "media")],
    "devops": [
        ("engenheiro-devops", "Engenheiro DevOps", "alta"),
        ("devops", "DevOps", "alta"),
    ],
    "seguranca": [
        ("gerente-de-seguranca-da-informacao", "Gerente de Segurança da Informação", "media")
    ],
    "infra": [("gerente-de-infraestrutura", "Gerente de Infraestrutura", "media")],
    "gerente": [
        ("gerente-de-desenvolvimento", "Gerente de Desenvolvimento", "media"),
        ("gerente-de-projetos", "Gerente de Projetos", "alta"),
    ],
    "ux": [
        ("ux-designer", "UX Designer", "alta"),
        ("designer-de-ux", "Designer de UX", "alta"),
    ],
    "teste": [
        ("analista-de-testes", "Analista de Testes", "alta"),
        ("analista-de-qualidade", "Analista de Qualidade", "media"),
    ],
    "suporte": [("analista-de-suporte", "Analista de Suporte", "alta")],
    "negocio": [
        ("analista-de-negocios", "Analista de Negócios", "alta"),
        ("analista-de-requisitos", "Analista de Requisitos", "media"),
    ],
    "sistemas": [("analista-de-sistemas", "Analista de Sistemas", "alta")],
    "bi_analista": [("analista-de-bi", "Analista de BI", "alta")],
}

GENERICOS = {
    "analista",
    "desenvolvedor",
    "desenvolvedora",
    "tecnico",
    "tecnica",
    "especialista",
    "engenheiro",
    "engenheira",
    "gerente",
    "de",
    "da",
    "do",
    "das",
    "dos",
    "em",
    "e",
    "para",
    "pleno",
    "senior",
    "junior",
}


def _baixar(url, timeout=45):
    pedido = urllib.request.Request(
        url,
        headers={"User-Agent": AGENTE, "Accept-Language": "pt-BR,pt;q=0.9"},
    )
    with urllib.request.urlopen(pedido, timeout=timeout) as resposta:
        return resposta.read()


def _sem_acento(texto):
    texto = unicodedata.normalize("NFD", texto or "")
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", texto.lower()).strip()


def reais(valor):
    return "R$ " + f"{int(round(valor)):,}".replace(",", ".")


def carregar_slugs():
    global _SLUGS
    if _SLUGS is not None:
        return _SLUGS
    xml = _baixar(SITEMAP).decode("utf-8", "replace")
    nacionais = {}
    for loc in re.findall(r"<loc>([^<]+)</loc>", xml):
        if "/vagas-detalhes/" not in loc:
            continue
        resto = loc.split("/vagas-detalhes/", 1)[1].strip("/")
        if "/" in resto:
            continue
        nacionais[resto] = loc.rstrip("/")
    _SLUGS = nacionais
    return nacionais


def _nivel_slug(nivel):
    return {
        "pleno": "pleno",
        "sênior": "senior",
        "senior": "senior",
        "júnior": "junior",
        "junior": "junior",
    }.get(_sem_acento(nivel), "")


def _familia(cargo_n):
    if "scrum" in cargo_n:
        return "scrum"
    if "rpa" in cargo_n:
        return "rpa"
    if "front" in cargo_n:
        return "front"
    if "mobile" in cargo_n:
        return "mobile"
    if "arquiteto" in cargo_n:
        return "arquiteto"
    if "cientista" in cargo_n:
        return "cientista"
    if "devops" in cargo_n:
        return "devops"
    if "seguranca" in cargo_n or "ciber" in cargo_n:
        return "seguranca"
    if "infraestrutura" in cargo_n:
        return "infra"
    if "ux" in cargo_n or "designer" in cargo_n:
        return "ux"
    if "teste" in cargo_n or "qualidade" in cargo_n or "qa" in cargo_n.split():
        return "teste"
    if "suporte" in cargo_n or "service desk" in cargo_n:
        return "suporte"
    if "negocio" in cargo_n or "requisito" in cargo_n:
        return "negocio"
    if "sistemas" in cargo_n and "desenvolvedor" not in cargo_n:
        return "sistemas"
    if ("business intelligence" in cargo_n or cargo_n.endswith(" bi") or " bi " in f" {cargo_n} ") and "gerente" not in cargo_n:
        return "bi_analista"
    if "business intelligence" in cargo_n or cargo_n.endswith(" bi") or " bi " in f" {cargo_n} ":
        return "bi"
    if "dados" in cargo_n and "gerente" in cargo_n:
        return "dados"
    if "dados" in cargo_n:
        return "dados"
    if "gerente" in cargo_n:
        return "gerente"
    if "desenvolvedor" in cargo_n:
        return "desenvolvedor"
    return ""


def _slug_existente(prefixo, nivel, slugs):
    if nivel:
        exato = f"{prefixo}-{nivel}"
        if exato in slugs:
            return exato
        for slug in slugs:
            if slug.startswith(prefixo) and slug.endswith("-" + nivel):
                return slug
        return ""
    if prefixo in slugs:
        return prefixo
    return ""


def escolher(nome, slugs):
    cargo = cargo_base(nome) or nome
    nivel = senioridade(nome)
    nivel_slug = _nivel_slug(nivel)
    familia = _familia(_sem_acento(cargo))
    if not familia or not nivel_slug and familia not in ("scrum", "arquiteto", "cientista"):
        if not familia:
            return None
    for prefixo, titulo, aderencia in FAMILIAS.get(familia, []):
        slug = _slug_existente(prefixo, nivel_slug, slugs)
        if slug:
            return {
                "slug": slug,
                "url": slugs[slug],
                "titulo": titulo,
                "aderencia": aderencia,
                "nivel": nivel,
                "cargo": cargo,
            }
        if not nivel_slug and prefixo in slugs:
            return {
                "slug": prefixo,
                "url": slugs[prefixo],
                "titulo": titulo,
                "aderencia": aderencia,
                "nivel": nivel,
                "cargo": cargo,
            }
    return None


def ler_faixa(url_base):
    url_sp = url_base.rstrip("/") + "/sao-paulo"
    html = ""
    regiao = "São Paulo"
    url_usada = url_sp
    try:
        html = _baixar(url_sp).decode("utf-8", "replace")
    except Exception:
        html = ""
    if "percentile25" not in html:
        html = _baixar(url_base).decode("utf-8", "replace")
        regiao = "DADO NACIONAL - SEM RECORTE REGIONAL."
        url_usada = url_base
    encontrado = re.search(
        r'"percentile25":"(\d+)","median":"(\d+)","percentile75":"(\d+)"',
        html,
    )
    if not encontrado:
        return None
    titulo = ""
    cabecalho = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
    if cabecalho:
        titulo = re.sub(r"<[^>]+>", "", cabecalho.group(1))
        titulo = re.sub(r"\s+", " ", titulo).strip()
    return {
        "minimo": int(encontrado.group(1)),
        "maximo": int(encontrado.group(3)),
        "regiao": regiao,
        "url": url_usada,
        "ano": "2026" if "2026" in html else "",
        "titulo_pagina": titulo,
    }


def _aderencia_e_justificativa(nome, cargo, escolha, faixa):
    cargo_n = _sem_acento(cargo)
    slug_n = escolha["slug"].replace("-", " ")
    distintivos = [
        token
        for token in cargo_n.split()
        if token not in GENERICOS and len(token) > 3
    ]
    faltam = [token for token in distintivos if token not in slug_n]
    publicado = faixa.get("titulo_pagina") or escolha["titulo"]
    if not faltam and escolha["aderencia"] == "alta":
        return "Alta", "", publicado
    motivo = ", ".join(faltam) if faltam else "o recorte do cargo solicitado"
    texto = (
        f"O guia Robert Half não publica o cargo {nome}. "
        f"Foi utilizada a faixa publicada de {publicado}, da mesma família profissional "
        f"e da mesma senioridade, no recorte disponível. "
        f"Aderência média, porque o guia não traz linha específica para {motivo}."
    )
    return "Média", texto, publicado


def pesquisar_perfil(perfil, slugs):
    nome = (perfil.get("perfil") or "").strip()
    cargo = cargo_base(nome) or nome
    nivel = senioridade(nome)
    vazio = {
        "nome": nome,
        "cargo": cargo,
        "senioridade": nivel,
        "encontrado": False,
    }
    escolha = escolher(nome, slugs)
    if not escolha:
        return vazio
    try:
        faixa = ler_faixa(escolha["url"])
    except Exception:
        return vazio
    if not faixa or faixa["minimo"] <= 0 or faixa["maximo"] < faixa["minimo"]:
        return vazio
    aderencia, justificativa, publicado = _aderencia_e_justificativa(nome, cargo, escolha, faixa)
    if aderencia not in ("Alta", "Média"):
        return vazio
    media = int(round((faixa["minimo"] + faixa["maximo"]) / 2))
    return {
        "nome": nome,
        "cargo": cargo,
        "senioridade": nivel,
        "encontrado": True,
        "minimo": faixa["minimo"],
        "maximo": faixa["maximo"],
        "media": media,
        "fonte": "Robert Half",
        "referencia": faixa["regiao"],
        "ano": faixa["ano"] or "2026",
        "url": faixa["url"],
        "proxy": publicado if justificativa else "",
        "aderencia": aderencia,
        "justificativa": justificativa,
        "titulo_publicado": publicado,
    }


def pesquisar(dados):
    slugs = carregar_slugs()
    return [
        pesquisar_perfil(perfil, slugs)
        for perfil in dados.get("perfis") or []
        if (perfil.get("perfil") or "").strip()
    ]
