# -*- coding: utf-8 -*-
"""Configuração editável do Relatório de Justificativa (tags + texto)."""
from __future__ import annotations

import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO = RAIZ / "modelos" / "config_rj.json"

TIPOS_CAMPO = {"texto_curto", "texto", "numero", "ia_web", "tabela"}
LARGURAS_CAMPO = {1, 2, 3, 4}


def _tag(
    id_,
    rotulo,
    grupo,
    calculado=False,
    tipo="texto_curto",
    largura=2,
    consulta_ia="",
    colunas=None,
    agrupar_por="",
    somar="",
    reuso_em=None,
):
    tag = {
        "id": id_,
        "rotulo": rotulo,
        "grupo": grupo,
        "reuso_em": list(reuso_em or []),
        "calculado": calculado,
        "tipo": tipo,
        "largura": largura,
        "consulta_ia": consulta_ia,
        "colunas": list(colunas or []),
        "agrupar_por": agrupar_por or "",
        "somar": somar or "",
    }
    return tag


TAGS_PADRAO = [
    _tag("mes_ano", "Mês e ano", "Identificação", tipo="texto_curto", largura=2),
    _tag("prazo_meses", "Prazo em meses", "Identificação", tipo="numero", largura=1),
    _tag("codigo_relatorio", "Código do relatório", "Identificação", tipo="texto_curto", largura=2),
    _tag("versao_relatorio", "Versão do relatório", "Identificação", tipo="texto_curto", largura=1),
    _tag("assunto", "Assunto", "Identificação", tipo="texto", largura=4),
    _tag("tecnologia", "Tecnologia", "Objeto", tipo="texto_curto", largura=4),
    _tag("catalogo", "Catálogo (grupos e serviços)", "Objeto", tipo="texto", largura=4),
    _tag("fatos", "Fatos", "Objeto", tipo="texto", largura=4),
    _tag("cliente", "Cliente", "Clientes e projetos", tipo="texto_curto", largura=2),
    _tag("projeto", "Projeto / sistema", "Clientes e projetos", tipo="texto_curto", largura=2),
    _tag("item", "Item / lote", "Perfis", tipo="texto_curto", largura=2),
    _tag("perfil", "Perfil técnico", "Perfis", tipo="texto_curto", largura=2),
    _tag("experiencia", "Experiência (anos)", "Perfis", tipo="numero", largura=1),
    _tag("horas", "Horas", "Perfis", tipo="numero", largura=1),
    _tag("proporcao", "Proporção valor-hora", "Perfis", tipo="texto_curto", largura=1),
    _tag("total_horas", "Total de horas", "Calculado", calculado=True, tipo="numero", largura=2),
    _tag("total_por_extenso", "Total por extenso", "Calculado", calculado=True, tipo="texto_curto", largura=2),
    _tag("perfil_referencia", "Perfil de referência", "Medição", tipo="texto_curto", largura=4),
    _tag("horas_por_pf", "Horas por ponto de função", "Medição", tipo="numero", largura=1),
    _tag("regra_vma", "Regra do VMA", "Medição", tipo="texto", largura=4),
    _tag("parceria", "Parceria com o fabricante", "Habilitação", tipo="texto", largura=4),
    _tag("estudo_mercado", "Estudo de mercado", "Habilitação", tipo="texto", largura=4),
    _tag("atestados", "Atestados específicos", "Habilitação", tipo="texto", largura=4),
    _tag("horas_professional", "Horas professional services", "Habilitação", tipo="numero", largura=2),
    _tag("regime_certificacao", "Regime da certificação", "Habilitação", tipo="texto_curto", largura=2),
    _tag("certificacoes", "Certificações", "Habilitação", tipo="texto", largura=4),
    _tag("area_elaboracao", "Quem elabora o relatório", "Elaboração", tipo="texto", largura=4),
    _tag("local_data", "Local e data", "Aprovação", tipo="texto_curto", largura=4),
    _tag("nome", "Nome do aprovador", "Aprovação", tipo="texto_curto", largura=2),
    _tag("matricula", "Matrícula", "Aprovação", tipo="texto_curto", largura=1),
    _tag("cargo", "Cargo", "Aprovação", tipo="texto_curto", largura=2),
]

DOCUMENTO_PADRAO = """
<article class="folha-rj">
  <h2>1. OBJETIVO</h2>
  <p>Justificar a necessidade de abertura de Processo Licitatório para contratação de Serviços de Apoio Técnico Especializado contemplando design, desenvolvimento, configuração, implantação, manutenção e suporte de sistemas de informação e plataformas tecnológicas da PRODESP utilizando {{tecnologia}}.</p>

  <h2>2. CONSIDERAÇÕES</h2>
  <h3>2.1 Definições</h3>
  <h4>2.1.1 {{tecnologia}}</h4>
  <p>{{tecnologia}} é a plataforma objeto desta contratação, utilizada pela PRODESP para desenvolvimento, implantação, manutenção e suporte de sistemas de informação.</p>
  <p>O escopo informado no cadastro contempla os seguintes grupos: {{catalogo}}.</p>

  <h3>2.2 Unidades de Medidas para Desenvolvimento dos Serviços</h3>
  <p class="fixo">[bloco fixo: APF, HST, local, teletrabalho e critério de medição]</p>

  <h3>2.3 Situação Atual</h3>
  <p>{{fatos}}</p>
  <p class="fixo">Esses serviços complementam a capacidade interna da PRODESP e apoiam a transferência de conhecimento…</p>

  <h2>3. PROCEDIMENTOS ADOTADOS</h2>
  <h3>3.1 Justificativa Para a Licitação</h3>
  <p>A PRODESP necessita contratar serviços de Apoio Técnico Especializado em {{tecnologia}}…</p>
  <p>{{fatos}}</p>
  <p>As demandas informadas no cadastro incluem: {{projeto}} ({{cliente}}).</p>

  <h3>3.1.2 Demanda Atual de Serviços</h3>
  <p class="fixo">[introdução fixa sobre consulta às gerências]</p>
  <table>
    <thead><tr><th>Cliente</th><th>Projeto / Sistema</th></tr></thead>
    <tbody><tr><td>{{cliente}}</td><td>{{projeto}}</td></tr></tbody>
  </table>
  <p class="fixo">[fecho fixo sobre Ordem de Serviço]</p>

  <h3>3.2 Demanda</h3>
  <p class="fixo">A demanda apresentada foi apurada… conforme o quadro a seguir.</p>
  <table>
    <thead><tr><th>Item</th><th>Perfil</th><th>Experiência</th><th>Horas</th></tr></thead>
    <tbody>
      <tr>
        <td>{{item}}</td>
        <td>{{perfil}}</td>
        <td>{{experiencia}}</td>
        <td>{{horas}}</td>
      </tr>
    </tbody>
  </table>

  <h3>3.3 Da Licitação</h3>
  <p>Para a realização dos serviços… foi estimado um total de {{total_horas}} ({{total_por_extenso}}) horas.</p>
  <table>
    <thead><tr><th>Item</th><th>Perfil</th><th>Horas</th><th>Proporção</th></tr></thead>
    <tbody>
      <tr>
        <td>{{item}}</td>
        <td>{{perfil}}</td>
        <td>{{horas}}</td>
        <td>{{proporcao}}</td>
      </tr>
    </tbody>
  </table>

  <h3>3.4 Critérios para Contratação</h3>
  <p>…Termo de Referência em {{tecnologia}}…</p>
  <p>…maior desconto ofertado sobre o item de referência “{{perfil_referencia}}”.</p>

  <h3>3.5 Contratação de Projetos em Pontos de Função</h3>
  <p class="fixo">[fórmula fixa VPF = VMA * PROD]</p>
  <p>VMA = {{regra_vma}}.</p>
  <p>A PRODESP adota… o fator de {{horas_por_pf}} horas por ponto de função.</p>

  <h3>3.6 Proposta Comercial</h3>
  <p>…item de referência “{{perfil_referencia}}”…</p>

  <h3>3.7 Perfis Técnicos</h3>
  <p>…qualificações descritas no Termo de Referência de {{tecnologia}}…</p>
  <p class="fixo">[bloco fixo de perfis técnicos]</p>

  <h3>3.8 Comprovação Técnica</h3>
  <p class="fixo">[declarações gerais fixas]</p>
  <p>{{parceria}}</p>
  <p>{{estudo_mercado}}</p>
  <p>Certificações profissionais exigidas: {{certificacoes}}.</p>
  <p>Regime da exigência: {{regime_certificacao}}.</p>
  <p>Atestados específicos: {{atestados}}</p>
  <p>…equivalência {{horas_por_pf}} horas por ponto de função…</p>
  <p>…volume mínimo de {{horas_professional}} horas de professional services.</p>

  <h3>3.9 Qualificação Econômico-Financeira</h3>
  <p class="fixo">[bloco fixo]</p>

  <h3>3.10 Planilha de Composição de Custos e Preços</h3>
  <p class="fixo">[bloco fixo]</p>

  <h3>3.11 Assinatura do contrato</h3>
  <p class="fixo">[representante técnico — bloco fixo]</p>
  <h4>3.11.2 Parceiro, estudo de mercado e certificações</h4>
  <p>{{parceria}}</p>
  <p>{{estudo_mercado}}</p>
  <p>{{certificacoes}}</p>
  <p class="fixo">[CMMI / MPS.BR / ISO — bloco fixo]</p>

  <h2>4. OBRIGAÇÕES</h2>
  <p class="fixo">[bloco fixo]</p>

  <h2>5. MODELOS DE FORMULÁRIOS</h2>
  <p class="fixo">[anexos 01 a 08 — modelos padrão]</p>

  <h2>6. RECURSOS FINANCEIROS</h2>
  <p class="fixo">[bloco fixo]</p>

  <h2>7. GESTOR E FISCAL DO CONTRATO</h2>
  <p class="fixo">[bloco fixo]</p>

  <h2>8. CONCLUSÃO</h2>
  <p>…contratação de {{total_horas}} ({{total_por_extenso}}) horas de serviços de Apoio Técnico Especializado em {{tecnologia}}… período de {{prazo_meses}} meses…</p>

  <h2>9. ELABORAÇÃO</h2>
  <p>{{area_elaboracao}}</p>

  <h2>10. APROVAÇÃO</h2>
  <p>{{local_data}}</p>
  <p>{{nome}}</p>
  <p>Matrícula: {{matricula}}</p>
  <p>{{cargo}}</p>
</article>
""".strip()


def _padrao():
    return {"tags": [dict(tag) for tag in TAGS_PADRAO], "documento": DOCUMENTO_PADRAO}


def _normalizar_id(valor):
    texto = str(valor or "").strip().lower()
    texto = re.sub(r"[^a-z0-9_]+", "_", texto)
    texto = re.sub(r"_+", "_", texto).strip("_")
    if not texto:
        raise ValueError("Informe um identificador para a tag.")
    if not re.fullmatch(r"[a-z][a-z0-9_]*", texto):
        raise ValueError("O identificador da tag deve começar com letra e usar só letras, números e _.")
    return texto


def _normalizar_tipo(valor):
    tipo = str(valor or "texto_curto").strip().lower()
    aliases = {
        "string": "texto_curto",
        "text": "texto",
        "textarea": "texto",
        "number": "numero",
        "ia": "ia_web",
        "internet": "ia_web",
        "table": "tabela",
        "quadro": "tabela",
    }
    tipo = aliases.get(tipo, tipo)
    if tipo not in TIPOS_CAMPO:
        raise ValueError("Tipo de campo inválido. Use texto_curto, texto, numero, ia_web ou tabela.")
    return tipo


def _normalizar_largura(valor):
    try:
        largura = int(valor)
    except (TypeError, ValueError):
        largura = 2
    if largura not in LARGURAS_CAMPO:
        raise ValueError("Largura inválida. Use 1, 2, 3 ou 4 quartos de linha.")
    return largura


def _normalizar_coluna(bruto, usados):
    if not isinstance(bruto, dict):
        raise ValueError("Coluna de tabela inválida.")
    col_id = _normalizar_id(bruto.get("id") or bruto.get("rotulo"))
    if col_id in usados:
        raise ValueError(f"Coluna duplicada na tabela: {col_id}")
    usados.add(col_id)
    tipo = str(bruto.get("tipo") or "texto").strip().lower()
    if tipo not in {"texto", "numero"}:
        tipo = "texto"
    return {
        "id": col_id,
        "rotulo": str(bruto.get("rotulo") or "").strip() or col_id,
        "tipo": tipo,
    }


def _normalizar_colunas_tabela(bruto):
    lista = bruto if isinstance(bruto, list) else []
    usados = set()
    colunas = [_normalizar_coluna(item, usados) for item in lista]
    if not colunas:
        raise ValueError("Tabela precisa de ao menos uma coluna.")
    return colunas


def _normalizar_tag(bruto):
    if not isinstance(bruto, dict):
        raise ValueError("Tag inválida.")
    calculado = bool(bruto.get("calculado"))
    tipo = _normalizar_tipo(bruto.get("tipo") or ("texto_curto" if not calculado else "texto_curto"))
    if tipo == "tabela":
        calculado = False
    largura_padrao = 4 if tipo in {"texto", "ia_web", "tabela"} else 2
    largura = _normalizar_largura(
        bruto.get("largura") if bruto.get("largura") is not None else largura_padrao
    )
    if tipo == "tabela":
        largura = 4
    consulta = str(bruto.get("consulta_ia") or "").strip()
    if tipo != "ia_web":
        consulta = ""
    colunas = []
    agrupar_por = ""
    somar = ""
    if tipo == "tabela":
        colunas = _normalizar_colunas_tabela(bruto.get("colunas"))
        ids = {c["id"] for c in colunas}
        agrupar_por = str(bruto.get("agrupar_por") or "").strip().lower()
        somar = str(bruto.get("somar") or "").strip().lower()
        if agrupar_por and agrupar_por not in ids:
            raise ValueError("A coluna de agrupamento deve existir na tabela.")
        if somar and somar not in ids:
            raise ValueError("A coluna de soma deve existir na tabela.")
        if somar == agrupar_por and somar:
            raise ValueError("A coluna de soma não pode ser a mesma do agrupamento.")
    grupo = str(bruto.get("grupo") or "Geral").strip() or "Geral"
    reuso_em = []
    bruto_reuso = bruto.get("reuso_em")
    if isinstance(bruto_reuso, list):
        for item in bruto_reuso:
            nome = str(item or "").strip()
            if not nome or nome == grupo or nome in reuso_em:
                continue
            reuso_em.append(nome[:80])
    tag = {
        "id": _normalizar_id(bruto.get("id")),
        "rotulo": str(bruto.get("rotulo") or "").strip() or _normalizar_id(bruto.get("id")),
        "grupo": grupo,
        "reuso_em": reuso_em,
        "calculado": calculado,
        "tipo": tipo,
        "largura": largura,
        "consulta_ia": consulta,
        "colunas": colunas,
        "agrupar_por": agrupar_por,
        "somar": somar,
    }
    return tag


def _normalizar_config(bruto):
    if not isinstance(bruto, dict):
        raise ValueError("Configuração inválida.")
    tags_brutas = bruto.get("tags")
    if not isinstance(tags_brutas, list) or not tags_brutas:
        raise ValueError("Informe ao menos uma tag.")
    tags = []
    vistos = set()
    for item in tags_brutas:
        tag = _normalizar_tag(item)
        if tag["id"] in vistos:
            raise ValueError(f"Tag duplicada: {tag['id']}")
        vistos.add(tag["id"])
        tags.append(tag)
    documento = str(bruto.get("documento") or "").strip()
    if not documento:
        raise ValueError("O texto do documento não pode ficar vazio.")
    return {"tags": tags, "documento": documento}


def carregar_config_rj():
    from geradores.config_catalogo import carregar_config_rj as _carregar

    return _carregar()


def salvar_config_rj(bruto):
    from geradores.config_catalogo import salvar_config_rj as _salvar

    return _salvar(bruto)
