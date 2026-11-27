# -*- coding: utf-8 -*-
"""Regras da CDGA só no Relatório de Justificativa - OS da Almaviva.

O termo conta por gerência cadastrada (sigla e descritivo no banco).
A cota é da diretoria DRC. O saldo é local, para teste, até haver consulta ao GIP.
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO = RAIZ / "modelos" / "compliance_almaviva.json"
ID_DOCUMENTO_OS = "relat_rio_de_justificativa_os"

_TECNOLOGIAS_CONHECIDAS = (
    "middleware",
    "java",
    ".net",
    "dotnet",
    "oracle",
    "sap",
    "red hat",
    "redhat",
    "liferay",
    "php",
    "gitlab",
    "python",
    "angular",
    "react",
    "node",
    "nodejs",
    "kubernetes",
    "docker",
)

_PAPEIS = (
    "analista",
    "gerente",
    "arquiteto",
    "desenvolvedor",
    "coordenador",
    "especialista",
    "consultor",
)

_PADRAO = {
    "fornecedor": "Almaviva Solutions S.A.",
    "contrato": "8446",
    "vigencia_inicio": "2025-07-07",
    "vigencia_fim": "2027-07-06",
    "primeiro_contrato_inicio": "2023-07-07",
    "limite_fim_prodesp": "2028-07-07",
    "renovacao_restante_anos": 1,
    "prazo_maximo_os_dias": 90,
    "max_termos_na_vigencia": 8,
    "dias_sobra_vigencia": 10,
    "saldo_cota": 500000.0,
    "diretoria_cota": "DRC",
    "reajuste_maximo_percentual": 15,
    "perfis": ["Gerente de Projetos", "Analista de Requisitos"],
    "termos_por_gerencia": {},
}


def _sem_acento(valor):
    base = unicodedata.normalize("NFD", str(valor or ""))
    return "".join(c for c in base if unicodedata.category(c) != "Mn").lower()


def _chave(valor):
    return re.sub(r"\s+", " ", _sem_acento(valor)).strip()


def _data(valor):
    texto = str(valor or "").strip()
    if not texto:
        return None
    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(texto[:10], formato).date()
        except ValueError:
            continue
    mes_ano = re.fullmatch(r"(\d{1,2})[/-](\d{4})", texto)
    if mes_ano:
        mes = int(mes_ano.group(1))
        ano = int(mes_ano.group(2))
        if 1 <= mes <= 12:
            if mes == 12:
                return date(ano, 12, 31)
            return date(ano, mes + 1, 1) - timedelta(days=1)
    return None


def _numero(valor):
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return float(valor)
    texto = str(valor or "").strip()
    if not texto:
        return None
    texto = texto.replace("R$", "").replace(" ", "")
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        texto = texto.replace(",", ".")
    texto = re.sub(r"[^0-9.\-]", "", texto)
    if not texto or texto in {".", "-", "-."}:
        return None
    try:
        return float(texto)
    except ValueError:
        return None


def _valor_itens(valor):
    bruto = valor.get("linhas") if isinstance(valor, dict) else None
    if not isinstance(bruto, list):
        return None
    total = 0.0
    achou = False
    for linha in bruto:
        if not isinstance(linha, dict):
            continue
        numero = _numero(linha.get("valor_total"))
        if numero is None:
            continue
        total += numero
        achou = True
    return total if achou else None


def _valores_por_item(valor):
    """Lista (índice 1-based, valor_total) de cada linha com valor informado."""
    bruto = valor.get("linhas") if isinstance(valor, dict) else None
    if not isinstance(bruto, list):
        return []
    saida = []
    for indice, linha in enumerate(bruto, start=1):
        if not isinstance(linha, dict):
            continue
        numero = _numero(linha.get("valor_total"))
        if numero is None:
            continue
        saida.append((indice, numero))
    return saida


def _coluna_itens(valor, coluna):
    bruto = valor.get("linhas") if isinstance(valor, dict) else None
    if not isinstance(bruto, list):
        return []
    saida = []
    for linha in bruto:
        if not isinstance(linha, dict):
            continue
        texto = str(linha.get(coluna) or "").strip()
        if texto:
            saida.append(texto)
    return saida


_STOP_TECH = frozenset({
    "de", "da", "do", "dos", "das", "para", "com", "em", "a", "o", "um", "uma",
    "informacao", "comunicacao", "gestao", "dados", "apoio", "servico", "servicos",
    "contratacao", "projeto", "sistema", "tecnologia", "plataforma", "software",
    "ferramenta", "solucao", "tic", "ti", "id", "esfera",
})


def _norm_tech(texto):
    return _chave(texto).replace("red hat", "redhat").replace(".net", "dotnet")


def _tecnologias(texto):
    """Tokens de tecnologia/sistema no texto (lista conhecida + 1 nome após 'tecnologia/sistema')."""
    chave = _norm_tech(texto)
    achadas = set()
    for nome in _TECNOLOGIAS_CONHECIDAS:
        token = nome.replace(".net", "dotnet").replace("red hat", "redhat")
        if token == "node":
            continue
        if token and re.search(rf"\b{re.escape(token)}\b", chave):
            achadas.add("redhat" if token == "redhat" else ("node" if token == "nodejs" else token))
    if re.search(r"\bnode(?:\.?js)?\b", chave):
        achadas.add("node")
    for achado in re.finditer(
        r"\b(?:sistema|tecnologia|plataforma|software|ferramenta|solucao)"
        r"(?:\s+d[aeo]s?)?\s+([a-z0-9][\w.+-]{2,40})",
        chave,
    ):
        nome = achado.group(1).strip()
        if nome and nome not in _STOP_TECH:
            achadas.add(nome)
    return achadas


def _tecnologias_celula(texto):
    """Na coluna Tecnologia, o conteúdo da célula também conta como o nome da tech."""
    achadas = _tecnologias(texto)
    chave = _norm_tech(texto)
    if chave and chave not in _STOP_TECH:
        achadas.add(chave)
    return achadas


def _tech_coberta(token, universo):
    if not token:
        return True
    for outro in universo or set():
        if token == outro or token in outro or outro in token:
            return True
    return False


def _rotulo_tech(token):
    return _ROTULO_TECNOLOGIA.get(token, str(token or "").upper() if token else "")


def _cargos_celula(texto):
    partes = re.split(r"\s*/\s*|\s*,\s*|\s+e\s+", str(texto or "").strip(), flags=re.IGNORECASE)
    return [parte.strip() for parte in partes if parte and parte.strip()]


def _mencoes_perfil(texto):
    """Cada cargo citado em separado (não engole Arquiteto + Analista numa só menção)."""
    chave = _flexao(texto)
    papeis = "|".join(_PAPEIS)
    starts = list(re.finditer(rf"\b(?:{papeis})\b", chave))
    vistos = []
    for indice, achado in enumerate(starts):
        fim = starts[indice + 1].start() if indice + 1 < len(starts) else len(chave)
        trecho = chave[achado.start():fim]
        trecho = re.split(r"\s+e\s+\d|\s*,\s*|\s+para\s+|\s+com\s+|\s+todos\s+", trecho)[0]
        mencao_m = re.match(
            rf"(?:{papeis})(?:(?:\s*/\s*|\s+)(?:de|do|da|dos|das)?\s*[a-z0-9]+){{0,6}}",
            trecho.strip(),
        )
        mencao = re.sub(r"\s+", " ", (mencao_m.group(0) if mencao_m else achado.group(0))).strip(" /")
        if mencao and mencao not in vistos:
            vistos.append(mencao)
    return vistos


def _flexao(texto):
    """Iguala singular e plural: projeto/projetos, requisito/requisitos."""
    palavras = []
    for palavra in _chave(texto).split():
        if len(palavra) > 3 and palavra.endswith("s"):
            palavra = palavra[:-1]
        palavras.append(palavra)
    return " ".join(palavras)


def _perfil_aceito(mencao, permitidos):
    texto = _flexao(mencao)
    if not texto:
        return True
    for perfil in permitidos or []:
        nome = _flexao(perfil)
        if nome and nome in texto:
            return True
    return False


_ROTULO_TECNOLOGIA = {
    "middleware": "MIDDLEWARE",
    "java": "Java",
    "dotnet": ".NET",
    "oracle": "Oracle",
    "sap": "SAP",
    "redhat": "Red Hat",
    "liferay": "Liferay",
    "php": "PHP",
    "gitlab": "GitLab",
    "python": "Python",
    "angular": "Angular",
    "react": "React",
    "node": "Node.js",
    "kubernetes": "Kubernetes",
    "docker": "Docker",
}


def _perfis_citados(texto, perfis):
    chave = _flexao(texto)
    citados = []
    for perfil in perfis or []:
        nome = _flexao(perfil)
        if nome and nome in chave:
            citados.append(str(perfil).strip())
    return citados


def _nivel_junto(texto, perfil):
    chave = _chave(texto)
    nome = _chave(perfil)
    if nome.endswith("s") and len(nome) > 4:
        nome = nome[:-1]
    indice = chave.find(nome) if nome else -1
    if indice < 0:
        return ""
    trecho = chave[indice:indice + len(nome) + 28]
    if "senior" in trecho:
        return "Sênior"
    if "pleno" in trecho:
        return "Pleno"
    if "junior" in trecho or re.search(r"\bjr\b", trecho):
        return "Júnior"
    return ""


def _sugerir_itens(objeto_txt, perfis, faltantes):
    techs = _tecnologias(objeto_txt)
    tecnologia = ""
    if len(techs) == 1:
        token = next(iter(techs))
        tecnologia = _rotulo_tech(token)
    return [
        {
            "cargo": perfil,
            "tecnologia": tecnologia,
            "nivel": _nivel_junto(objeto_txt, perfil),
        }
        for perfil in faltantes
    ]


def _preencher_fim_vigencia(valores, tags, config):
    texto = _fmt_data(_data(config.get("vigencia_fim")))
    if not texto or not isinstance(valores, dict):
        return
    for tag in tags or []:
        if not isinstance(tag, dict):
            continue
        tag_id = str(tag.get("id") or "")
        rotulo = _chave(tag.get("rotulo"))
        if tag_id == "data_fim_vigencia" or "data fim vigencia" in rotulo:
            valores[tag_id] = texto


def _fmt_data(dia):
    return dia.strftime("%d/%m/%Y") if isinstance(dia, date) else ""


def _fmt_moeda(valor):
    texto = f"{valor:,.2f}"
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


def _termos_map(bruto):
    import banco

    origem = bruto if isinstance(bruto, dict) else {}
    base = {}
    for item in banco.listar_gerencias():
        sigla = str(item.get("sigla") or "").strip().upper()
        if not sigla:
            continue
        valor = origem.get(sigla, origem.get(sigla.lower()))
        base[sigla] = max(0, int(_numero(valor) or 0))
    return base


def documento_justificativa_os(formulario_id="", formulario_nome=""):
    ident = str(formulario_id or "").strip().lower()
    if ident == ID_DOCUMENTO_OS:
        return True
    nome = _chave(formulario_nome)
    return "justificativa" in nome and bool(re.search(r"\bos\b", nome))


def _sigla_gerencia(texto):
    import banco

    chave = _chave(texto)
    if not chave:
        return ""
    gerencias = banco.listar_gerencias()
    for item in sorted(gerencias, key=lambda atual: len(_chave(atual.get("descritivo"))), reverse=True):
        descritivo = _chave(item.get("descritivo"))
        if descritivo and descritivo in chave:
            return str(item.get("sigla") or "").strip().upper()
    for item in gerencias:
        sigla = _chave(item.get("sigla"))
        if sigla and re.search(rf"\b{re.escape(sigla)}\b", chave):
            return str(item.get("sigla") or "").strip().upper()
    return ""


def _sigla_diretoria(texto):
    chave = _chave(texto)
    if re.search(r"\bdrc\b", chave):
        return "DRC"
    return ""


def carregar():
    dados = dict(_PADRAO)
    if ARQUIVO.is_file():
        try:
            bruto = json.loads(ARQUIVO.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            bruto = {}
        if isinstance(bruto, dict):
            dados.update({k: v for k, v in bruto.items() if k in _PADRAO or k in dados})
            if isinstance(bruto.get("perfis"), list):
                dados["perfis"] = [str(item).strip() for item in bruto["perfis"] if str(item).strip()]
            if isinstance(bruto.get("termos_por_gerencia"), dict):
                dados["termos_por_gerencia"] = _termos_map(bruto.get("termos_por_gerencia"))
    for chave in ("vigencia_inicio", "vigencia_fim", "primeiro_contrato_inicio", "limite_fim_prodesp"):
        dia = _data(dados.get(chave))
        dados[chave] = dia.isoformat() if dia else _PADRAO[chave]
    dados["prazo_maximo_os_dias"] = int(_numero(dados.get("prazo_maximo_os_dias")) or 90)
    dados["max_termos_na_vigencia"] = int(_numero(dados.get("max_termos_na_vigencia")) or 8)
    dados["dias_sobra_vigencia"] = int(_numero(dados.get("dias_sobra_vigencia")) or 10)
    dados["renovacao_restante_anos"] = int(_numero(dados.get("renovacao_restante_anos")) or 1)
    dados["saldo_cota"] = float(_numero(dados.get("saldo_cota")) or 0)
    dados["reajuste_maximo_percentual"] = float(_numero(dados.get("reajuste_maximo_percentual")) or 15)
    dados["diretoria_cota"] = str(dados.get("diretoria_cota") or "DRC").strip() or "DRC"
    dados["termos_por_gerencia"] = _termos_map(dados.get("termos_por_gerencia"))
    return dados


def salvar(bruto):
    atual = carregar()
    if isinstance(bruto, dict):
        for chave in (
            "saldo_cota",
            "prazo_maximo_os_dias",
            "vigencia_inicio",
            "vigencia_fim",
            "limite_fim_prodesp",
            "reajuste_maximo_percentual",
            "max_termos_na_vigencia",
            "dias_sobra_vigencia",
            "renovacao_restante_anos",
        ):
            if chave in bruto and bruto.get(chave) not in (None, ""):
                atual[chave] = bruto.get(chave)
        if isinstance(bruto.get("perfis"), list):
            atual["perfis"] = [str(item).strip() for item in bruto["perfis"] if str(item).strip()]
        elif isinstance(bruto.get("perfis"), str):
            atual["perfis"] = [p.strip() for p in bruto["perfis"].split(",") if p.strip()]
        mapa = dict(atual.get("termos_por_gerencia") or {})
        if isinstance(bruto.get("termos_por_gerencia"), dict):
            mapa.update(bruto.get("termos_por_gerencia") or {})
        atual["termos_por_gerencia"] = mapa
    atual = _normalizar_gravado(atual)
    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO.write_text(json.dumps(atual, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return carregar()


def _normalizar_gravado(atual):
    dados = dict(_PADRAO)
    dados.update(atual)
    for chave in ("vigencia_inicio", "vigencia_fim", "primeiro_contrato_inicio", "limite_fim_prodesp"):
        dia = _data(dados.get(chave))
        if not dia:
            raise ValueError(f"Data inválida em {chave}.")
        dados[chave] = dia.isoformat()
    dados["prazo_maximo_os_dias"] = int(_numero(dados.get("prazo_maximo_os_dias")) or 0)
    dados["max_termos_na_vigencia"] = int(_numero(dados.get("max_termos_na_vigencia")) or 0)
    dados["dias_sobra_vigencia"] = int(_numero(dados.get("dias_sobra_vigencia")) or 0)
    dados["renovacao_restante_anos"] = int(_numero(dados.get("renovacao_restante_anos")) or 0)
    dados["saldo_cota"] = float(_numero(dados.get("saldo_cota")) or 0)
    dados["reajuste_maximo_percentual"] = float(_numero(dados.get("reajuste_maximo_percentual")) or 0)
    if dados["prazo_maximo_os_dias"] <= 0:
        raise ValueError("O prazo máximo da OS precisa ser maior que zero.")
    if dados["saldo_cota"] < 0:
        raise ValueError("O saldo da cota não pode ser negativo.")
    dados["diretoria_cota"] = str(dados.get("diretoria_cota") or "DRC").strip() or "DRC"
    dados["termos_por_gerencia"] = _termos_map(dados.get("termos_por_gerencia"))
    return dados


def _rotulo_de(tags, tag_id):
    for tag in tags or []:
        if isinstance(tag, dict) and str(tag.get("id") or "") == tag_id:
            return str(tag.get("rotulo") or "")
    return ""


def _escolher(valores, tags, nomes_id, trechos_rotulo):
    """Devolve (id_do_campo, valor) pelo id conhecido ou pelo rótulo."""
    mapa = {}
    for chave, valor in (valores or {}).items():
        mapa[str(chave)] = valor
    for nome in nomes_id:
        if nome in mapa and mapa[nome] not in (None, "", [], {}):
            return nome, mapa[nome]
    for tag in tags or []:
        if not isinstance(tag, dict) or not tag.get("id"):
            continue
        rotulo = _chave(tag.get("rotulo"))
        if any(trecho in rotulo for trecho in trechos_rotulo):
            tag_id = str(tag["id"])
            if tag_id in mapa and mapa[tag_id] not in (None, "", [], {}):
                return tag_id, mapa[tag_id]
    for nome in nomes_id:
        if nome in mapa:
            return nome, mapa[nome]
    return nomes_id[0], None


def _eh_almaviva(fornecedor, contrato):
    if "almaviva" in _chave(fornecedor):
        return True
    digitos = re.sub(r"\D", "", str(contrato or ""))
    return digitos.endswith("8446") and digitos != ""


def avaliar(valores, tags=None, hoje=None, formulario_id="", formulario_nome=""):
    """Devolve bloqueios da CDGA no Relatório de Justificativa - OS da Almaviva."""
    config = carregar()
    tags = tags or []
    if not documento_justificativa_os(formulario_id, formulario_nome):
        return {
            "aplicavel": False,
            "fornecedor": config["fornecedor"],
            "bloqueios": [],
            "config": config,
        }
    id_fornecedor, fornecedor = _escolher(valores, tags, ("fornecedor",), ("fornecedor",))
    id_contrato, contrato = _escolher(
        valores, tags, ("numero_contrato", "n_contrato", "contrato"), ("contrato",)
    )
    if not _eh_almaviva(fornecedor, contrato):
        return {"aplicavel": False, "fornecedor": config["fornecedor"], "bloqueios": [], "config": config}

    hoje = hoje or date.today()
    if "almaviva" in _chave(fornecedor):
        _preencher_fim_vigencia(valores, tags, config)
    vigencia_fim = _data(config["vigencia_fim"])
    limite_prodesp = _data(config["limite_fim_prodesp"])
    bloqueios = []
    sugestoes_itens = []

    def apontar(regra, campo, mensagem):
        bloqueios.append({"regra": regra, "campo": campo, "mensagem": mensagem})

    id_prazo, prazo_bruto = _escolher(
        valores, tags, ("prazo_os", "prazo"), ("prazo",)
    )
    prazo = _numero(prazo_bruto)
    if prazo is not None and prazo > config["prazo_maximo_os_dias"]:
        apontar(
            "prazo_maximo",
            id_prazo,
            (
                f"Para a Almaviva (contrato {config['contrato']}), o prazo máximo da OS é "
                f"{config['prazo_maximo_os_dias']} dias corridos. "
                f"Em cada gerência, na vigência de 2 anos, cabem {config['max_termos_na_vigencia']} termos "
                f"e sobram {config['dias_sobra_vigencia']} dias."
            ),
        )

    fim_os = hoje + timedelta(days=int(prazo)) if prazo is not None and prazo >= 0 else None
    if fim_os and vigencia_fim and fim_os > vigencia_fim:
        apontar(
            "vigencia_os",
            id_prazo,
            (
                f"A OS terminaria em {_fmt_data(fim_os)} e a vigência do contrato "
                f"{config['contrato']} vai até {_fmt_data(vigencia_fim)}. "
                "Nenhuma OS pode ultrapassar a vigência. O término da vigência exige renovação."
            ),
        )

    id_vigencia, vigencia_bruta = _escolher(
        valores, tags, ("data_fim_vigencia",), ("vigencia", "fim vigencia")
    )
    vigencia_informada = _data(vigencia_bruta)
    if vigencia_informada and limite_prodesp and vigencia_informada > limite_prodesp:
        apontar(
            "limite_cinco_anos",
            id_vigencia,
            (
                f"A Almaviva só pode ter 5 anos de contrato com a Prodesp, até {_fmt_data(limite_prodesp)}. "
                f"A data {_fmt_data(vigencia_informada)} passa desse limite."
            ),
        )
    elif vigencia_informada and vigencia_fim and vigencia_informada > vigencia_fim:
        apontar(
            "renovacao",
            id_vigencia,
            (
                f"A vigência informada ({_fmt_data(vigencia_informada)}) passa de {_fmt_data(vigencia_fim)}. "
                f"Isso é renovação, e a Almaviva só pode renovar mais {config['renovacao_restante_anos']} ano, "
                f"até {_fmt_data(limite_prodesp)}."
            ),
        )

    id_objeto, objeto = _escolher(
        valores,
        tags,
        ("objeto_descricao_atividades", "objeto"),
        ("objeto", "descricao dos servicos"),
    )
    objeto_txt = str(objeto or "")
    objeto_chave = _chave(objeto_txt)
    if len(objeto_chave) >= 30 and not re.search(r"id\s*esfera\s*[:\-]?\s*\d+", objeto_chave):
        apontar(
            "id_esfera",
            id_objeto or "objeto_descricao_atividades",
            "Falta o ID ESFERA no final de Objeto e Descrição dos Serviços/Atividades.",
        )
    id_itens, itens = _escolher(valores, tags, ("itens_contrato",), ("itens do contrato", "itens contrato"))
    # Garante o id real da tag mesmo se o valor ainda estiver vazio.
    if tags:
        for tag in tags:
            if isinstance(tag, dict) and str(tag.get("id") or "") == "objeto_descricao_atividades":
                id_objeto = "objeto_descricao_atividades"
            if isinstance(tag, dict) and str(tag.get("id") or "") == "itens_contrato":
                id_itens = "itens_contrato"
    techs_objeto = _tecnologias(objeto_txt)
    techs_tabela = set()
    for texto in _coluna_itens(itens, "tecnologia"):
        techs_tabela |= _tecnologias_celula(texto)
    if len(objeto_chave) >= 30 and not techs_objeto:
        apontar(
            "tecnologia_objeto",
            id_objeto or "objeto_descricao_atividades",
            (
                "Indique a tecnologia ou o sistema em Objeto e Descrição dos Serviços/Atividades. "
                "A CDGA precisa dessa informação para conferir a coluna Tecnologia dos itens."
            ),
        )
    faltam_tech = {token for token in techs_objeto if not _tech_coberta(token, techs_tabela)}
    if techs_objeto and faltam_tech:
        rotulos = ", ".join(_rotulo_tech(token) or token for token in sorted(faltam_tech))
        apontar(
            "tecnologia",
            id_itens or "itens_contrato",
            (
                f"A tecnologia/sistema indicada no Objeto ({rotulos}) não aparece na coluna "
                "Tecnologia de nenhum item da tabela Itens do Contrato. "
                "Pelo menos um item precisa repetir essa tecnologia."
            ),
        )

    perfis = [str(item).strip() for item in (config.get("perfis") or []) if str(item).strip()]
    lista = ", ".join(perfis) or "nenhum perfil cadastrado"
    cargos = []
    for bruto in _coluna_itens(itens, "cargo"):
        cargos.extend(_cargos_celula(bruto) or [bruto])
    cargos_fora = [cargo for cargo in cargos if not _perfil_aceito(cargo, perfis)]
    if cargos_fora:
        apontar(
            "perfil_contrato",
            id_itens,
            (
                f"O cargo {cargos_fora[0]} não existe no contrato {config['contrato']} da Almaviva. "
                f"Os perfis deste contrato são: {lista}."
            ),
        )
    fora_perfil = [
        mencao for mencao in _mencoes_perfil(objeto_txt)
        if not _perfil_aceito(mencao, perfis)
    ]
    if fora_perfil:
        apontar(
            "perfil_objeto",
            id_objeto,
            (
                f"{fora_perfil[0]} não existe no contrato {config['contrato']} da Almaviva. "
                f"Os perfis deste contrato são: {lista}."
            ),
        )
    citados = _perfis_citados(objeto_txt, perfis)
    faltantes = [
        perfil for perfil in citados
        if not any(_perfil_aceito(cargo, [perfil]) for cargo in cargos)
    ]
    sugestoes_itens = _sugerir_itens(objeto_txt, perfis, faltantes)
    if faltantes:
        pedidos = ", ".join(faltantes)
        apontar(
            "itens_objeto",
            id_itens,
            (
                f"O objeto pede a contratação de {pedidos}, mas a tabela Itens do Contrato "
                "não tem esse item. Preencha a tabela com o cargo e os dados do item."
            ),
        )

    id_gerencia, gerencia = _escolher(valores, tags, ("gerencia",), ("gerencia",))
    sigla_gerencia = _sigla_gerencia(gerencia)
    termos_gerencia = config.get("termos_por_gerencia") or {}
    if sigla_gerencia:
        abertos = int(termos_gerencia.get(sigla_gerencia) or 0)
        proximo = abertos + 1
        if proximo > config["max_termos_na_vigencia"]:
            apontar(
                "max_termos",
                id_gerencia,
                (
                    f"A {sigla_gerencia} já abriu {abertos} termos nesta vigência. "
                    f"Esta OS seria o {proximo}º termo dessa gerência, e o máximo é "
                    f"{config['max_termos_na_vigencia']}. Cada gerência conta em separado."
                ),
            )

    id_recurso, recurso = _escolher(
        valores, tags, ("recurso_financeiro", "valor_total"), ("recurso", "valor total")
    )
    valores_itens = _valores_por_item(itens)
    valor = _valor_itens(itens)
    if valor is None:
        valor = _numero(recurso)
    id_diretoria, diretoria = _escolher(valores, tags, ("diretoria",), ("diretoria",))
    sigla_diretoria = _sigla_diretoria(diretoria)
    cota_desta_diretoria = not str(diretoria or "").strip() or sigla_diretoria == str(config.get("diretoria_cota") or "DRC")
    saldo = float(config["saldo_cota"])
    campo_saldo = id_itens if valores_itens else id_recurso
    if cota_desta_diretoria and saldo >= 0:
        item_acima = next((par for par in valores_itens if par[1] > saldo), None)
        if item_acima:
            indice, valor_item = item_acima
            apontar(
                "saldo_item",
                campo_saldo,
                (
                    f"O item {indice} da tabela Itens do Contrato tem valor total {_fmt_moeda(valor_item)}, "
                    f"superior ao saldo disponível da cota da {config.get('diretoria_cota') or 'DRC'} "
                    f"({_fmt_moeda(saldo)})."
                ),
            )
        elif valor is not None and valor > saldo:
            apontar(
                "saldo_cota",
                campo_saldo,
                (
                    f"O somatório dos itens ({_fmt_moeda(valor)}) supera o saldo da cota da "
                    f"{config.get('diretoria_cota') or 'DRC'} ({_fmt_moeda(saldo)}). "
                    "A CAEP e o GIP recusariam a dedução."
                ),
            )
        elif (
            valor is not None
            and saldo > 0
            and abs(valor - saldo) < 0.01
            and fim_os
            and vigencia_fim
            and fim_os < vigencia_fim
        ):
            apontar(
                "aditivo",
                campo_saldo,
                (
                    f"O pedido consome todo o saldo da cota da {config.get('diretoria_cota') or 'DRC'} "
                    f"({_fmt_moeda(saldo)}) antes do fim da vigência "
                    f"({_fmt_data(vigencia_fim)}). É necessário solicitar um aditivo."
                ),
            )

    id_reajuste, reajuste_bruto = _escolher(
        valores,
        tags,
        ("reajuste", "percentual_reajuste", "equilibrio_contratual"),
        ("reajuste", "equilibrio"),
    )
    reajuste = _numero(reajuste_bruto)
    if reajuste is not None and reajuste > config["reajuste_maximo_percentual"]:
        apontar(
            "reajuste",
            id_reajuste,
            (
                "Em aditivo ou renovação, o reajuste de equilíbrio contratual não pode superar "
                f"{config['reajuste_maximo_percentual']:g}%. O valor informado foi {reajuste:g}%."
            ),
        )

    return {
        "aplicavel": True,
        "fornecedor": config["fornecedor"],
        "contrato": config["contrato"],
        "bloqueios": bloqueios,
        "sugestoes_itens": sugestoes_itens,
        "config": config,
    }


def mensagem_bloqueio(resultado):
    itens = (resultado or {}).get("bloqueios") or []
    if not itens:
        return ""
    return " ".join(item.get("mensagem") or "" for item in itens if item.get("mensagem"))
