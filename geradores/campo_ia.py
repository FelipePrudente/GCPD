# -*- coding: utf-8 -*-
"""Calibragem da busca por IA: respostas objetivas e refinamento de perguntas abertas."""
from __future__ import annotations

import os
import re
import urllib.parse
import urllib.request
import json

from geradores.certificacoes_sugestao import (
    _baixar,
    _buscar_ddg_api,
    _buscar_web,
    _buscar_wikipedia,
    _relevancia_busca,
    _texto,
    _tokens_busca,
    _trecho_inutil,
)

LIXO = (
    "comprar", "compra ", "desconto", "cupom", "matrícul", "matricul",
    "inscri", "curso online", "como obter", "como se tornar", "como tirar", "onde fazer",
    "hotmart", "udemy", "parceiro oficial da", "clique aqui", "saiba mais",
    "carreira e rotina", "como é ser", "vaga aberta",
)

# Só bloqueia conteúdo salarial quando a pergunta NÃO é sobre salário.
LIXO_SALARIO = (
    "quanto paga", "salário", "salario", "faixa salarial", "remuneração média",
    "remuneracao media", "salary",
)

TITULO_INUTIL = (
    "funções e responsabilidades", "o que a função exige", "sobre a função",
    "como é ser", "o que faz e o que não faz", "guia completo",
    "tudo sobre", "confira", "saiba o que",
)

SEMENTES = [
    {
        "quando": ("product owner", "dono do produto", "po "),
        "e": ("certific",),
        "respostas": [
            "CSPO — Certified Scrum Product Owner",
            "PSPO — Professional Scrum Product Owner (Scrum.org)",
        ],
    },
    {
        "quando": ("scrum master",),
        "e": ("certific",),
        "respostas": [
            "CSM — Certified ScrumMaster",
            "PSM — Professional Scrum Master (Scrum.org)",
        ],
    },
    {
        "quando": ("armazen", "storage", "dados em cloud", "cloud storage"),
        "e": ("tecnolog", "cloud", "principais", "quais"),
        "respostas": [
            "AWS (Amazon S3 / EBS / EFS)",
            "Microsoft Azure (Blob Storage / Files / Disks)",
            "Google Cloud (Cloud Storage / Persistent Disk)",
        ],
    },
]

# Funções objetivas por perfil (quando a busca devolve só títulos de artigo).
FUNCOES_PERFIL = [
    {
        "quando": ("analista de dados", "data analyst"),
        "nivel": ("sênior", "senior", "sr"),
        "respostas": [
            "Transformar dados brutos em insights estratégicos para o negócio",
            "Coletar, organizar e interpretar grandes volumes de dados",
            "Identificar padrões e tendências para apoiar decisões",
            "Criar e validar modelos preditivos",
            "Aplicar Machine Learning e Inteligência Artificial quando cabível",
            "Estruturar bancos de dados, dashboards e relatórios claros",
            "Orientar áreas de negócio com análises de alto impacto",
            "Mentorar analistas júnior/pleno e revisar qualidade analítica",
        ],
    },
    {
        "quando": ("analista de dados", "data analyst"),
        "nivel": (),
        "respostas": [
            "Coletar, limpar e organizar dados",
            "Analisar dados para identificar padrões e tendências",
            "Elaborar dashboards e relatórios gerenciais",
            "Apoiar áreas de negócio com insights orientados a dados",
            "Garantir qualidade e consistência das bases utilizadas",
        ],
    },
    {
        "quando": ("product owner", "dono do produto"),
        "nivel": (),
        "respostas": [
            "Definir e priorizar o backlog do produto",
            "Maximizar o valor entregue ao negócio",
            "Traduzir necessidades do negócio em requisitos claros",
            "Validar entregas com stakeholders",
            "Alinhar visão do produto à estratégia organizacional",
        ],
    },
    {
        "quando": ("scrum master",),
        "nivel": (),
        "respostas": [
            "Facilitar eventos Scrum e remover impedimentos",
            "Garantir adesão ao framework ágil",
            "Apoiar o time na melhoria contínua",
            "Proteger o time de interrupções externas",
            "Promover transparência do andamento do trabalho",
        ],
    },
]

VERBOS_FUNCAO = (
    "coletar", "organizar", "interpretar", "analisar", "criar", "desenvolver", "estruturar",
    "orientar", "apoiar", "definir", "priorizar", "validar", "implementar", "monitorar",
    "garantir", "elaborar", "construir", "modelar", "identificar", "transformar", "liderar",
    "revisar", "mentorar", "automatizar", "documentar", "apresentar", "extrair", "tratar",
)

PADROES_CERT = [
    re.compile(r"\bCSPO\b(?:\s*[—\-–:]\s*|\s+)?(?:Certified Scrum Product Owner)?", re.I),
    re.compile(r"\bPSPO\s*[I]{0,3}\b(?:\s*[—\-–:]\s*|\s+)?(?:Professional Scrum Product Owner)?", re.I),
    re.compile(r"\bCSM\b(?:\s*[—\-–:]\s*|\s+)?(?:Certified ScrumMaster|Certified Scrum Master)?", re.I),
    re.compile(r"\bPSM\s*[I]{0,3}\b(?:\s*[—\-–:]\s*|\s+)?(?:Professional Scrum Master)?", re.I),
    re.compile(r"\bPMP\b(?:\s*[—\-–:]\s*|\s+)?(?:Project Management Professional)?", re.I),
    re.compile(r"\bAWS Certified [A-Za-z0-9 /+\-]{3,60}", re.I),
    re.compile(r"\bMicrosoft Certified[^\.|,\n]{0,70}", re.I),
    re.compile(r"\bGoogle Cloud (?:Professional |Associate )?[A-Za-z0-9 \-]{3,50}", re.I),
    re.compile(r"\bCertified [A-Za-z0-9 \-/+]{4,50}(?:Professional|Associate|Owner|Master|Engineer|Architect)\b", re.I),
]

TECH_CLOUD = [
    ("AWS", ("aws", "amazon s3", "amazon web services")),
    ("Azure", ("azure", "microsoft azure")),
    ("GCP", ("gcp", "google cloud", "google cloud platform")),
]


def _parece_pedido_salario(consulta):
    baixo = _texto(consulta).lower()
    return any(p in baixo for p in (
        "salár", "salar", "remuner", "faixa salarial", "média salarial", "media salarial",
        "quanto ganha", "quanto paga", "salary", "linkedin salary", "glassdoor",
        "robert half", "pesquisa salarial", "valor da hora", "valor-hora", "valor hora",
    ))


def _tem_lixo(texto, consulta=""):
    baixo = str(texto or "").lower()
    if any(p in baixo for p in LIXO):
        return True
    if not _parece_pedido_salario(consulta) and any(p in baixo for p in LIXO_SALARIO):
        return True
    return False


def _limpar_objetivo(texto):
    texto = re.sub(r"\s+", " ", _texto(texto)).strip(" -:;,.|")
    texto = re.sub(r"^(o |a |os |as |um |uma )", "", texto, flags=re.I)
    if len(texto) > 140:
        texto = texto[:137].rsplit(" ", 1)[0] + "…"
    return texto


def _eh_pergunta_funcoes(consulta):
    baixo = consulta.lower()
    return any(p in baixo for p in (
        "funç", "funcao", "funções", "funcoes", "responsabilidad", "atribui",
        "atividades de", "o que faz", "quais as fun",
    ))


def _parece_titulo_inutil(texto):
    baixo = str(texto or "").lower().strip()
    if any(p in baixo for p in TITULO_INUTIL):
        return True
    if baixo.endswith("...") or "|" in baixo:
        return True
    if re.match(r"^(funções|funcoes|responsabilidades|como |o que |guia )", baixo):
        return True
    # Título curto demais sem verbo de ação
    if len(baixo) < 45 and not any(v in baixo for v in VERBOS_FUNCAO):
        return True
    return False


def _respostas_semente(consulta):
    baixo = consulta.lower()
    for item in SEMENTES:
        if any(p in baixo for p in item["quando"]) and any(p in baixo for p in item["e"]):
            return list(item["respostas"])
    return []


def _funcoes_perfil(consulta):
    if not _eh_pergunta_funcoes(consulta):
        return []
    baixo = consulta.lower()
    generico = []
    for item in FUNCOES_PERFIL:
        if not any(p in baixo for p in item["quando"]):
            continue
        nivel = item.get("nivel") or ()
        if nivel:
            if any(n in baixo for n in nivel):
                return list(item["respostas"])
            continue
        if not generico:
            generico = list(item["respostas"])
    return generico


def _funcao_valida(texto):
    baixo = str(texto or "").lower().strip()
    if not baixo or _tem_lixo(baixo) or _parece_titulo_inutil(baixo):
        return False
    if baixo.startswith((
        "também", "alem disso", "além disso", "sendo ", "enquanto ", "além ",
        "o analista", "um profissional", "é um profissional", "é comum",
    )):
        return False
    if baixo.count("…") or baixo.endswith((" e", " de", " para", " com")):
        return False
    tem_verbo = any(v in baixo for v in VERBOS_FUNCAO)
    parece_acao = tem_verbo or baixo.startswith((
        "criação", "criacao", "desenvolvimento", "análise", "analise",
        "estruturação", "estruturacao", "modelagem", "gestão", "gestao",
        "aplicação", "aplicacao", "mentoria",
    ))
    return parece_acao and 18 <= len(texto) <= 140


def _extrair_funcoes(texto):
    """Extrai atribuições objetivas de trechos longos/artigos."""
    bruto = str(texto or "")
    bruto = bruto.replace("•", "\n").replace("·", "\n").replace(";", "\n")
    bruto = re.sub(r"\s+", " ", bruto)
    partes = []
    for bloco in re.split(r"[\n•]| (?=\d+[\.\)]\s)|(?<=\.)\s+", bruto):
        partes.append(bloco.strip(" -–—\t"))
    extras = []
    for parte in list(partes):
        if " e " in parte.lower() and len(parte) > 90:
            extras.extend([p.strip() for p in re.split(r",| e ", parte) if p.strip()])
    partes.extend(extras)

    achados = []
    vistos = set()
    for parte in partes:
        limpo = _limpar_objetivo(parte)
        limpo = re.sub(
            r"^(principais responsabilidades|responsabilidades|funções|funcoes)\s*[:\-–]?\s*",
            "",
            limpo,
            flags=re.I,
        )
        if not _funcao_valida(limpo):
            continue
        chave = limpo.lower()
        if chave in vistos:
            continue
        vistos.add(chave)
        achados.append(limpo)
    return achados[:10]


def analisar_refinamento(consulta):
    """Se a pergunta for aberta demais, devolve perguntas objetivas de calibração."""
    baixo = consulta.lower()
    tokens = _tokens_busca(consulta)
    perguntas = []

    cargos = (
        "desenvolvedor", "developer", "analista", "engenheiro", "arquiteto",
        "product owner", "dono do produto", "scrum master", "devops", "cloud",
    )
    niveis = ("júnior", "junior", "pleno", "sênior", "senior", "especialista", "estagiário", "estagiario")
    stacks = ("java", "python", "javascript", "typescript", ".net", "dotnet", "aws", "azure", "gcp", "react", "angular", "node")

    pediu_pessoa = any(p in baixo for p in ("contratar", "quero um", "quero uma", "preciso de um", "preciso de uma", "vaga", "perfil de"))
    citou_cargo = any(p in baixo for p in cargos)
    citou_nivel = any(p in baixo for p in niveis)
    citou_stack = any(p in baixo for p in stacks)

    if (pediu_pessoa or ("desenvolvedor" in baixo and len(tokens) <= 5)) and citou_cargo and not citou_nivel:
        perguntas.append({
            "id": "nivel",
            "pergunta": "Qual o nível do profissional?",
            "opcoes": ["Júnior", "Pleno", "Sênior"],
        })

    if pediu_pessoa and ("desenvolvedor" in baixo or "developer" in baixo) and not citou_stack:
        perguntas.append({
            "id": "stack",
            "pergunta": "Qual a principal tecnologia?",
            "opcoes": ["Java", "Python", ".NET", "AWS/Cloud", "Front-end"],
        })

    if "certific" in baixo and not any(p in baixo for p in ("product owner", "dono do produto", "scrum", "aws", "azure", "pmp", "devops")):
        perguntas.append({
            "id": "area_cert",
            "pergunta": "Certificação de qual área?",
            "opcoes": ["Product Owner / Ágil", "Cloud (AWS/Azure/GCP)", "Gestão de projetos", "Segurança"],
        })

    if len(tokens) <= 2 and not perguntas:
        perguntas.append({
            "id": "formato",
            "pergunta": "Que tipo de resposta objetiva você precisa?",
            "opcoes": ["Nome de certificação", "Lista de tecnologias", "Nome de cargo/perfil", "Requisito de edital"],
        })

    return perguntas[:3]


def _extrair_certificacoes(texto):
    achados = []
    vistos = set()
    for padrao in PADROES_CERT:
        for match in padrao.findall(texto):
            nome = _limpar_objetivo(match)
            chave = nome.lower()
            if len(nome) < 3 or chave in vistos or _tem_lixo(nome):
                continue
            vistos.add(chave)
            achados.append(nome)
    return achados


def _extrair_tecnologias_cloud(texto):
    baixo = texto.lower()
    achados = []
    for nome, pistas in TECH_CLOUD:
        if any(p in baixo for p in pistas):
            achados.append(nome)
    return achados


def _coletar_fontes(consulta, tecnologia="", usar_tecnologia=False):
    consultas = [consulta]
    baixo = consulta.lower()
    # Consulta enxuta para fatos
    if "certific" in baixo:
        consultas.append(consulta + " nome da certificação oficial")
    if _eh_pergunta_funcoes(consulta):
        consultas.append(consulta + " principais responsabilidades lista")
        consultas.append(consulta + " atribuições objetivas")
    if _parece_pedido_salario(consulta):
        cargo = _extrair_cargo_salario(consulta) or "profissional de TI"
        consultas.extend([
            f"{cargo} salário médio Brasil LinkedIn",
            f"{cargo} salary LinkedIn Brazil São Paulo",
            f"{cargo} faixa salarial Robert Half São Paulo",
            f"{cargo} salário CLT Glassdoor Brasil",
        ])
    if usar_tecnologia and tecnologia:
        consultas.append(f"{consulta} {tecnologia}")

    textos = []
    fontes = []
    for termo in consultas:
        for bloco, nome in (
            (_buscar_ddg_api(termo), "DuckDuckGo API"),
            (_buscar_wikipedia(termo), "Wikipedia"),
            ([t for t in _buscar_web(termo) if not _trecho_inutil(t)], "DuckDuckGo HTML"),
        ):
            if bloco:
                textos.extend(bloco)
                fontes.append(nome)
    return textos, fontes


def _destilar(consulta, textos):
    sementes = _respostas_semente(consulta)
    if sementes:
        return sementes

    juntado = "\n".join(textos)
    baixo_q = consulta.lower()

    if "certific" in baixo_q:
        certs = _extrair_certificacoes(juntado)
        if certs:
            return certs[:6]

    if _eh_pergunta_funcoes(consulta):
        perfil = _funcoes_perfil(consulta)
        funcoes = [f for f in _extrair_funcoes(juntado) if _funcao_valida(f)]
        # Perfil conhecido: devolve lista objetiva pronta (o que o usuário espera).
        if perfil:
            return perfil[:8]
        if funcoes:
            return funcoes[:8]

    if any(p in baixo_q for p in ("armazen", "storage", "tecnolog", "cloud")) and not _eh_pergunta_funcoes(consulta):
        techs = _extrair_tecnologias_cloud(juntado)
        if techs:
            if len(techs) >= 2:
                return [", ".join(techs)] + [f"{t}" for t in techs]
            return techs

    # Frases curtas e sem lixo comercial / títulos de matéria
    candidatos = []
    vistos = set()
    for bruto in textos:
        if _trecho_inutil(bruto) or _tem_lixo(bruto, consulta) or _parece_titulo_inutil(bruto):
            trecho = bruto.split(".")[0]
            if _tem_lixo(trecho, consulta) or _parece_titulo_inutil(trecho):
                continue
            bruto = trecho
        score = _relevancia_busca(bruto, consulta)
        if score < 0.08:
            continue
        frase = re.split(r"(?<=[\.\!\?])\s+", bruto)[0].strip()
        if _parece_pedido_salario(consulta):
            frase = re.sub(r"\s+", " ", frase).strip()
        else:
            frase = _limpar_objetivo(frase)
        if len(frase) < 8 or frase.lower() in vistos:
            continue
        if _tem_lixo(frase, consulta) or _parece_titulo_inutil(frase):
            continue
        if len(frase) > 220 and not _parece_pedido_salario(consulta):
            continue
        vistos.add(frase.lower())
        candidatos.append((score, frase))

    candidatos.sort(key=lambda item: (-item[0], len(item[1])))
    return [texto for _, texto in candidatos[:6]]


LIMITE_RESPOSTA_IA = 2500

_PROMPT_SISTEMA = (
    "Você redige respostas para um formulário de contratação pública (PRODESP/SP), "
    "em português do Brasil, tom formal e técnico. "
    "Calibre o tamanho conforme o pedido: "
    "(1) Lista curta — certificações, tecnologias, nomes/siglas: uma por linha, sem prosa. "
    "(2) Funções/atribuições de cargo — uma atribuição por linha, no infinitivo "
    "(ex.: 'Criar modelos preditivos'). "
    "(3) Definição de plataforma, descrição de produtos/serviços, situação atual ou "
    "justificativa — texto corrido completo e formal, com 2 a 5 parágrafos se necessário, "
    "podendo incluir lista após a prosa; use até 2500 caracteres; NÃO resuma em bullets "
    "curtos quando o pedido pedir definição, descrição, produtos, serviços ou justificativa. "
    "(4) Pesquisa salarial / média de remuneração — responda com faixas em R$ (mensal CLT "
    "quando possível), cite a fonte (LinkedIn Salary, Robert Half, Glassdoor etc.), "
    "ano/região se houver nos trechos, e deixe claro o que é estimado. "
    "Se a pergunta pedir LinkedIn e os trechos não trouxerem valor publicado, diga isso "
    "objetivamente e ofereça a melhor faixa disponível em outra fonte pública citada. "
    "Nunca devolva título de artigo de 'como é ser' ou propaganda de curso. "
    "Não explique onde comprar ou como fazer curso. "
    "Se faltar contexto crítico (ex.: cargo sem nome), responda exatamente no formato: "
    "REFINAR|pergunta1|opcaoA;opcaoB|pergunta2|opcaoA;opcaoB."
)


def _parece_pedido_completo(consulta):
    """Pedidos que exigem prosa longa (definição, justificativa, descrição, salário)."""
    if _parece_pedido_salario(consulta):
        return True
    baixo = _texto(consulta).lower()
    chaves = (
        "defin", "descrev", "descri", "justific", "situação atual", "situacao atual",
        "plataforma", "produtos", "serviços", "servicos", "capacidades", "principais",
        "elabore", "redija", "texto completo", "texto formal", "narra", "contexto",
        "o que é", "o que e", "como funciona", "abrang", "escopo",
    )
    return any(c in baixo for c in chaves)


def _extrair_cargo_salario(consulta):
    texto = _texto(consulta)
    baixo = texto.lower()
    conhecidos = (
        ("product owner", "Product Owner"),
        ("dono do produto", "Product Owner"),
        ("scrum master", "Scrum Master"),
        ("analista de dados", "Analista de Dados"),
        ("cientista de dados", "Cientista de Dados"),
        ("engenheiro de dados", "Engenheiro de Dados"),
        ("desenvolvedor", "Desenvolvedor"),
        ("arquiteto", "Arquiteto de Software"),
        ("devops", "DevOps"),
        ("ux designer", "UX Designer"),
        ("analista de negócios", "Analista de Negócios"),
        ("analista de sistemas", "Analista de Sistemas"),
        ("gerente de projetos", "Gerente de Projetos"),
    )
    for chave, rotulo in conhecidos:
        if chave in baixo:
            return rotulo
    m = re.search(
        r"(?:sal[aá]rio|remunera[cç][aã]o|faixa salarial|m[eé]dia salarial)\s+(?:de\s+|do\s+|da\s+|para\s+)?(.+)$",
        texto,
        re.I,
    )
    if m:
        cargo = re.sub(r"\b(no|na|em|pelo|pela|segundo|conforme|linkedin|brasil|são paulo|sao paulo)\b.*$", "", m.group(1), flags=re.I)
        cargo = re.sub(r"\s+", " ", cargo).strip(" .:-")
        if 3 <= len(cargo) <= 80:
            return cargo.title()
    return ""


def _faixa_robert_half(consulta):
    """Tenta faixa CLT no guia Robert Half (fonte pública usada na Pesquisa Salarial)."""
    cargo = _extrair_cargo_salario(consulta)
    if not cargo:
        return None
    try:
        from geradores.pesquisa_fontes import carregar_slugs, pesquisar_perfil, reais
    except Exception:
        return None
    try:
        resultado = pesquisar_perfil({"perfil": cargo}, carregar_slugs())
    except Exception:
        return None
    if not resultado or not resultado.get("encontrado"):
        return None
    minimo = reais(resultado["minimo"])
    maximo = reais(resultado["maximo"])
    media = reais(resultado["media"])
    fonte = resultado.get("titulo_publicado") or resultado.get("cargo") or cargo
    partes = [
        f"Faixa salarial CLT mensal para {resultado.get('nome') or cargo} "
        f"(referência {resultado.get('referencia') or 'São Paulo'}, "
        f"guia Robert Half {resultado.get('ano') or ''}): "
        f"mínimo {minimo}, máximo {maximo}, média {media}."
    ]
    if resultado.get("justificativa"):
        partes.append(resultado["justificativa"])
    else:
        partes.append(f"Fonte pública: Robert Half — {fonte}.")
    if "linkedin" in _texto(consulta).lower():
        partes.append(
            "O LinkedIn Salary Insights costuma exigir login e não publica a faixa "
            "de forma aberta para coleta automática; na ausência de valor LinkedIn "
            "extraído na busca, esta é a referência pública disponível."
        )
    return " ".join(partes).strip()


def _limitar_resposta_ia(texto, limite=LIMITE_RESPOSTA_IA):
    texto = _texto(texto)
    if len(texto) <= limite:
        return texto
    corte = texto[:limite].rsplit(" ", 1)[0].rstrip(" ,;:")
    return (corte or texto[:limite]).rstrip() + "…"


def _limpar_prosa_ia(texto):
    """Limpa prosa da IA preservando parágrafos (até o limite do campo)."""
    texto = _texto(texto).replace("\r\n", "\n").replace("\r", "\n")
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto).strip()
    return _limitar_resposta_ia(texto)


def _parse_resposta_llm(texto, consulta=""):
    texto = (texto or "").strip()
    if not texto:
        return []
    if texto.upper().startswith("REFINAR|"):
        return {"refinar": texto, "fonte": None}

    forcar_prosa = _parece_pedido_completo(consulta)
    linhas_brutas = [l.strip() for l in texto.splitlines() if l.strip()]
    parece_lista = (
        not forcar_prosa
        and len(linhas_brutas) >= 3
        and sum(1 for l in linhas_brutas if re.match(r"^([-•*]|\d+[.)])\s+", l)) >= max(2, len(linhas_brutas) // 2)
        and all(len(l) <= 180 for l in linhas_brutas)
    )
    # Texto corrido / definição / justificativa: bloco inteiro (até 2500 chars).
    if forcar_prosa or (not parece_lista and (len(texto) > 180 or "\n\n" in texto)):
        prosa = _limpar_prosa_ia(texto)
        if prosa and not _tem_lixo(prosa, consulta):
            return [prosa]

    # Listas objetivas (certificações, funções): uma linha por item, com limite curto.
    linhas = [_limpar_objetivo(l.lstrip("-•* ").strip()) for l in texto.splitlines()]
    limpas = [l for l in linhas if l and not _tem_lixo(l, consulta)]
    if not limpas and texto:
        return [_limpar_prosa_ia(texto)][:1]
    return limpas[:8]


def _erro_http_detalhe(erro):
    texto = str(erro)
    leitura = getattr(erro, "read", None)
    if callable(leitura):
        try:
            bruto = leitura().decode("utf-8", "replace")
            dados = json.loads(bruto)
            msg = ((dados.get("error") or {}).get("message") or "").strip()
            if msg:
                return msg
        except Exception:
            pass
    return texto


def _gemini_generate(chave, modelo, prompt, max_tokens=800, thinking=True):
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{urllib.parse.quote(modelo)}:generateContent?key={urllib.parse.quote(chave)}"
    )
    config = {"temperature": 0.2, "maxOutputTokens": max_tokens}
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
    try:
        with urllib.request.urlopen(pedido, timeout=25) as resp:
            dados = json.loads(resp.read().decode("utf-8"))
    except Exception as erro:
        detalhe = _erro_http_detalhe(erro)
        if thinking and ("thinking" in detalhe.lower() or "400" in detalhe):
            return _gemini_generate(chave, modelo, prompt, max_tokens=max_tokens, thinking=False)
        raise RuntimeError(detalhe) from erro
    partes = (
        dados.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [])
    )
    return "\n".join(str(p.get("text") or "") for p in partes).strip()


def _chamar_gemini(consulta, textos, cfg):
    chave = str(cfg.get("google_api_key") or "").strip()
    if not chave:
        return None
    modelo = str(cfg.get("modelo_google") or "gemini-3.5-flash").strip() or "gemini-3.5-flash"
    candidatos = [modelo]
    if modelo != "gemini-3.5-flash-lite":
        candidatos.append("gemini-3.5-flash-lite")
    contexto = "\n".join(f"- {t}" for t in (textos or [])[:4]) or "(sem trechos web)"
    if _parece_pedido_salario(consulta):
        instrucao = (
            "Este pedido é de PESQUISA SALARIAL. Informe faixas em R$ (mensal CLT se possível), "
            "cite a fonte e o recorte (cidade/ano) quando existir nos trechos. "
            "Se a pergunta mencionar LinkedIn e não houver valor LinkedIn nos trechos, declare "
            "isso e use a melhor fonte pública disponível (ex.: Robert Half). "
            "Resposta em 1 ou 2 parágrafos objetivos, até 900 caracteres."
        )
    elif _parece_pedido_completo(consulta):
        instrucao = (
            "Resposta formal e direta para documento público: "
            "1 ou 2 parágrafos, até 900 caracteres."
        )
    else:
        instrucao = (
            "Responda de forma objetiva e curta, até 900 caracteres. "
            "Lista: uma linha por item. Texto: um parágrafo."
        )
    prompt = (
        f"{_PROMPT_SISTEMA}\n\n"
        f"Pergunta: {consulta}\n\n"
        f"Trechos encontrados:\n{contexto}\n\n"
        f"{instrucao}"
    )
    ultimo_erro = ""
    for indice, nome in enumerate(candidatos):
        try:
            texto = _gemini_generate(chave, nome, prompt, max_tokens=800)
            parseado = _parse_resposta_llm(texto, consulta)

            if isinstance(parseado, dict):
                parseado["fonte"] = f"Google Gemini ({nome})"
                return parseado
            if parseado:
                return {"itens": parseado, "fonte": f"Google Gemini ({nome})", "modelo": nome}
            ultimo_erro = f"Modelo {nome} retornou vazio."
        except Exception as erro:
            ultimo_erro = str(erro)
            baixo = ultimo_erro.lower()
            modelo_indisponivel = "404" in ultimo_erro or "no longer available" in baixo or "not_found" in baixo
            if modelo_indisponivel and indice == 0:
                continue
            break
    return {"erro": ultimo_erro or "Gemini não retornou conteúdo.", "fonte": "Google Gemini"}


def _chamar_openai(consulta, textos, cfg):
    chave = str(cfg.get("openai_api_key") or "").strip()
    if not chave:
        return None
    modelo = str(cfg.get("modelo_openai") or "gpt-4o-mini").strip() or "gpt-4o-mini"
    contexto = "\n".join(f"- {t}" for t in (textos or [])[:8]) or "(sem trechos web)"
    if _parece_pedido_salario(consulta):
        extra = (
            " Responda pesquisa salarial com faixas em R$, fonte e recorte. "
            "Se LinkedIn não aparecer nos trechos, declare e use outra fonte pública."
        )
    elif _parece_pedido_completo(consulta):
        extra = (
            " Responda com texto corrido formal completo (2 a 5 parágrafos, até 2500 caracteres). "
            "Não resuma em bullets curtos."
        )
    else:
        extra = " Calibre o tamanho: lista curta se for catálogo; prosa completa se for definição/justificativa."
    corpo = {
        "model": modelo,
        "temperature": 0.3,
        "max_tokens": 800,
        "messages": [
            {"role": "system", "content": _PROMPT_SISTEMA},
            {
                "role": "user",
                "content": f"Pergunta: {consulta}\n\nTrechos encontrados:\n{contexto}\n\n{extra}",
            },
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
    try:
        with urllib.request.urlopen(pedido, timeout=25) as resp:
            dados = json.loads(resp.read().decode("utf-8"))
        texto = dados["choices"][0]["message"]["content"].strip()
    except Exception as erro:
        return {"erro": str(erro), "fonte": "OpenAI"}
    parseado = _parse_resposta_llm(texto, consulta)
    if isinstance(parseado, dict):
        parseado["fonte"] = "OpenAI"
        return parseado
    return {"itens": parseado, "fonte": "OpenAI"}


def _refinar_com_llm(consulta, textos):
    """Usa Google Gemini e/ou OpenAI conforme configuração local/env."""
    from geradores.ia_config import carregar_ia_config

    cfg = carregar_ia_config()
    provedor = str(cfg.get("provedor") or "google").strip().lower()
    ordem = []
    if provedor == "google":
        ordem = ["google", "openai"]
    elif provedor == "openai":
        ordem = ["openai", "google"]
    else:
        ordem = ["google", "openai"]

    ultimo_erro = ""
    for nome in ordem:
        resultado = _chamar_gemini(consulta, textos, cfg) if nome == "google" else _chamar_openai(consulta, textos, cfg)
        if resultado is None:
            continue
        if resultado.get("erro"):
            ultimo_erro = resultado["erro"]
            continue
        if resultado.get("refinar"):
            return resultado
        itens = resultado.get("itens") or []
        if itens:
            return resultado
    if ultimo_erro:
        return {"erro": ultimo_erro}
    return {"itens": [], "fonte": None}


def responder_campo_ia(consulta, tecnologia="", rotulo="", usar_tecnologia=False, historico=None):
    consulta = _texto(consulta) or _texto(rotulo)
    if not consulta:
        raise ValueError("Escreva o que você quer buscar neste campo.")

    historico = historico or []
    if historico:
        extras = "; ".join(_texto(h) for h in historico if _texto(h))
        if extras:
            consulta = f"{consulta}. Detalhes: {extras}"

    # Definição/justificativa/salário não passam pela calibragem curta.
    perguntas = [] if _parece_pedido_completo(consulta) or _parece_pedido_salario(consulta) else analisar_refinamento(consulta)
    if perguntas:
        return {
            "modo": "refinar",
            "consulta": consulta,
            "mensagem": "A pergunta ainda está aberta. Responda para eu trazer uma resposta objetiva.",
            "perguntas": perguntas,
            "itens": [],
            "fonte": "Calibragem local",
        }

    # Para perguntas de funções, prioriza catálogo objetivo se a web costuma falhar.
    funcoes_diretas = [] if _parece_pedido_salario(consulta) else _funcoes_perfil(consulta)
    sementes = [] if _parece_pedido_salario(consulta) else _respostas_semente(consulta)
    faixa_rh = _faixa_robert_half(consulta) if _parece_pedido_salario(consulta) else None

    from geradores.ia_config import carregar_ia_config

    cfg = carregar_ia_config()
    tem_llm = bool(str(cfg.get("google_api_key") or "").strip() or str(cfg.get("openai_api_key") or "").strip())

    # Com LLM: evita busca web genérica, mas pesquisa salarial e “usar tecnologia” precisam da web.
    textos, fontes = ([], [])
    if (not tem_llm) or usar_tecnologia or _parece_pedido_salario(consulta):
        textos, fontes = _coletar_fontes(consulta, tecnologia, usar_tecnologia)
    if faixa_rh:
        textos = [faixa_rh] + list(textos or [])
        fontes = ["Robert Half"] + list(fontes or [])

    if not textos and not sementes and not funcoes_diretas and not faixa_rh and not tem_llm:
        raise ValueError(
            "Não encontrei base suficiente e nenhuma chave de IA está configurada. "
            "Em Configurações, informe a API Key do Google (Gemini) para testar."
        )

    contexto_llm = textos or funcoes_diretas or sementes
    if faixa_rh and faixa_rh not in (contexto_llm or []):
        contexto_llm = [faixa_rh] + list(contexto_llm or [])
    llm = _refinar_com_llm(consulta, contexto_llm)
    if isinstance(llm, dict) and llm.get("refinar"):
        return {
            "modo": "refinar",
            "consulta": consulta,
            "mensagem": "Preciso de mais detalhes para responder de forma objetiva.",
            "perguntas": analisar_refinamento(consulta + " detalhar") or [{
                "id": "detalhe",
                "pergunta": "Qual informação objetiva você precisa?",
                "opcoes": ["Certificação", "Tecnologia", "Cargo/nível", "Requisito"],
            }],
            "itens": [],
            "fonte": llm.get("fonte") or "IA",
        }

    objetivos = []
    fonte_llm = None
    if isinstance(llm, dict):
        objetivos = list(llm.get("itens") or [])
        fonte_llm = llm.get("fonte")
        # Com chave Google/OpenAI configurada, não devolve lixo de busca web no lugar da IA.
        if llm.get("erro") and tem_llm and not objetivos and not faixa_rh:
            raise ValueError(
                f"Falha na IA ({llm.get('fonte') or 'LLM'}): {llm['erro']}. "
                "Verifique a chave e o modelo em Configurações → IA / API."
            )
    elif isinstance(llm, list):
        objetivos = list(llm)

    if not objetivos:
        if faixa_rh:
            objetivos = [faixa_rh]
        elif tem_llm and not _parece_pedido_salario(consulta):
            raise ValueError(
                "A IA não retornou texto útil. Tente um pedido mais direto, "
                "ex.: “Justificativa formal para contratação de serviços em AWS na PRODESP”."
            )
        else:
            objetivos = _destilar(consulta, textos) or sementes or funcoes_diretas
    if not objetivos:
        if _parece_pedido_salario(consulta):
            raise ValueError(
                "Não encontrei faixa salarial pública para este cargo. "
                "Tente informar o cargo completo e a cidade (ex.: Product Owner pleno São Paulo) "
                "ou consulte a Pesquisa Salarial do sistema (guia Robert Half)."
            )
        raise ValueError("Não consegui extrair uma resposta objetiva. Reformule a pergunta com mais precisão.")

    itens = [{"id": i + 1, "texto": texto} for i, texto in enumerate(objetivos)]
    return {
        "modo": "resposta",
        "consulta": consulta,
        "mensagem": (
            "Resposta completa pronta. Revise e insira no campo."
            if _parece_pedido_completo(consulta) or any(len(t) > 220 for t in objetivos)
            else "Respostas objetivas encontradas. Selecione o que deseja inserir no campo."
        ),
        "perguntas": [],
        "itens": itens,
        "sugestao": "\n".join(objetivos),
        "fonte": fonte_llm or (" + ".join(dict.fromkeys(fontes)) or "Busca calibrada"),
        "limite_caracteres": LIMITE_RESPOSTA_IA,
    }
