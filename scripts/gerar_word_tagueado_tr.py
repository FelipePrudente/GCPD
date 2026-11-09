# -*- coding: utf-8 -*-
"""Gera Word tagueado do Termo de Referência a partir da comparação AWS x Dynamics."""
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt, RGBColor

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "modelos" / "Termo_de_Referencia_TAGUEADO.docx"

TAGS = [
    ("unidade_cabecalho", "Unidade no cabeçalho da capa"),
    ("n_processo_sei", "Número do processo SEI"),
    ("interessado", "Interessado na capa"),
    ("tecnologia", "Nome da tecnologia"),
    ("sigla_relatorio", "Código do termo (ex.: REL.GEN.055.2026)"),
    ("versao", "Versão (ex.: V1.0)"),
    ("mes_ano", "Mês e ano (ex.: Março/2026)"),
    ("prazo_meses", "Prazo de vigência em meses"),
    ("catalogo_tecnologia", "Catálogo da tecnologia por grupo/serviços"),
    ("regra_vma", "Regra do valor médio da hora (VMA)"),
    ("horas_por_pf", "Horas por ponto de função"),
    ("incluir_snap", "Incluir método SNAP (sim/não ou texto)"),
    ("versao_sisp", "Versão do roteiro SISP"),
    ("quadro_lotes", "Tabela de itens/perfis/horas/proporção"),
    ("perfil_referencia", "Perfil de referência do desconto"),
    ("dominio_plataforma", "Domínio mínimo da plataforma (item 3.1.8)"),
    ("descricao_perfis", "Texto IA — atuação e domínio de cada perfil"),
    ("regime_certificacao", "Regime da exigência de certificações"),
    ("certificacoes", "Lista de certificações profissionais"),
    ("descricao_itens", "Texto IA — descrição dos serviços por item (se houver)"),
    ("texto_elaboracao", "Texto da elaboração"),
    ("local_data", "Local e data da assinatura"),
    ("lista_aprovadores", "Aprovadores (nome, matrícula, cargo)"),
]


def _run(para, texto, *, bold=False, size=11, tag=False):
    run = para.add_run(texto)
    run.bold = bold
    run.font.name = "Arial"
    run.font.size = Pt(size)
    if tag or "{{" in texto:
        run.font.color.rgb = RGBColor(0x1D, 0x4E, 0x89)
    return run


def p(doc, texto, *, bold=False, center=False, size=11, space_after=6):
    para = doc.add_paragraph()
    if center:
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    para.paragraph_format.space_after = Pt(space_after)
    para.paragraph_format.space_before = Pt(0)
    _run(para, texto, bold=bold, size=size)
    return para


def mixed(doc, partes, *, center=False, size=11, space_after=6):
    para = doc.add_paragraph()
    if center:
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    para.paragraph_format.space_after = Pt(space_after)
    for texto, bold in partes:
        _run(para, texto, bold=bold, size=size)
    return para


def gerar():
    doc = Document()
    for secao in doc.sections:
        secao.top_margin = Cm(2)
        secao.bottom_margin = Cm(2)
        secao.left_margin = Cm(2.5)
        secao.right_margin = Cm(2.5)

    # CAPA
    p(doc, "Governo do Estado de São Paulo", bold=True, center=True, size=12, space_after=2)
    p(
        doc,
        "Companhia de Processamento de Dados do Estado de São Paulo",
        bold=True,
        center=True,
        size=12,
        space_after=2,
    )
    mixed(doc, [("{{unidade_cabecalho}}", False)], center=True, size=11, space_after=12)

    p(doc, "TERMO DE REFERÊNCIA", bold=True, center=True, size=14, space_after=10)
    mixed(doc, [("Nº do Processo: ", False), ("{{n_processo_sei}}", False)])
    mixed(doc, [("Interessado: ", False), ("{{interessado}}", False)])
    mixed(
        doc,
        [
            ("Assunto: CONTRATAÇÃO DE SERVIÇOS DE APOIO TÉCNICO ESPECIALIZADO EM ", False),
            ("{{tecnologia}}", False),
        ],
        space_after=10,
    )

    p(doc, "TERMO DE REFERÊNCIA", bold=True, center=True, size=12, space_after=2)
    mixed(
        doc,
        [("{{sigla_relatorio}} ", False), ("{{versao}}", False)],
        center=True,
        space_after=8,
    )
    p(doc, "CONTRATAÇÃO DE SERVIÇOS DE APOIO TÉCNICO ESPECIALIZADO", bold=True, center=True, size=11, space_after=2)
    mixed(doc, [("EM ", True), ("{{tecnologia}}", True)], center=True, space_after=12)

    p(doc, "DDS - Diretoria de Desenvolvimento de Sistemas", center=True, space_after=2)
    p(doc, "SCL – Superintendência de Sistemas Estruturantes", center=True, space_after=2)
    p(doc, "GEN - Gerência de Engenharia de Software e Serviços", center=True, space_after=2)
    mixed(doc, [("{{mes_ano}}", False)], center=True, space_after=16)

    # 1 INTRODUÇÃO
    p(doc, "1. INTRODUÇÃO", bold=True, size=12, space_after=8)
    p(
        doc,
        "Este Termo de Referência fornece as especificações técnicas mínimas que a proponente "
        "deverá atender para a prestação dos serviços de Apoio Técnico Especializado. "
        "(Texto padrão fixo.)",
        space_after=12,
    )

    # 2 ESCOPO
    p(doc, "2. ESCOPO E ESTRATÉGIA DE CONTRATAÇÃO DOS SERVIÇOS", bold=True, size=12, space_after=8)
    p(doc, "2.1 Do Objeto", bold=True, size=11, space_after=6)
    mixed(
        doc,
        [
            (
                "Contratação de Serviços de Apoio Técnico Especializado em ",
                False,
            ),
            ("{{tecnologia}}", False),
            (
                ", contemplando design, desenvolvimento, configuração, implantação, manutenção "
                "e suporte de sistemas de informação e plataformas tecnológicas, pelo período de ",
                False,
            ),
            ("{{prazo_meses}}", False),
            (" meses.", False),
        ],
        space_after=6,
    )
    p(doc, "Catálogo da tecnologia (por grupo de serviços):", bold=True, space_after=4)
    mixed(doc, [("{{catalogo_tecnologia}}", False)], space_after=4)
    p(
        doc,
        "(Lista cadastrada por grupo — ex.: Computação | EC2, Lambda… — sem inventar serviço novo.)",
        size=9,
        space_after=10,
    )

    p(doc, "2.2 Ambiente Tecnológico da Prodesp", bold=True, size=11, space_after=6)
    p(
        doc,
        "Catálogo padrão da PRODESP: sistemas operacionais, bancos de dados, linguagens, "
        "servidores, portais, nuvem (AWS, Azure, Google Cloud, Huawei, Prodesp VCloud), "
        "observabilidade e a nota de que poderão ser pedidas versões superiores. "
        "(Texto/tabela padrão fixo.)",
        space_after=10,
    )

    p(doc, "2.3 Metodologia, Disciplinas e Artefatos", bold=True, size=11, space_after=6)
    p(
        doc,
        "Metodologia, artefatos, Scrum, BPM e plano de projeto. Percentuais de esforço: "
        "requisitos 25%, design 10%, implementação 40%, testes 15%, homologação 5% e "
        "implantação 5%. (Texto padrão fixo.)",
        space_after=10,
    )

    p(doc, "2.4 Planejamento de Projetos", bold=True, size=11, space_after=6)
    p(doc, "(Texto padrão fixo.)", space_after=10)

    p(doc, "2.5 Modalidades de Remuneração", bold=True, size=11, space_after=6)
    p(
        doc,
        "Modalidades: Análise de Pontos de Função (APF), Horas de Serviço Técnico (HST) e "
        "sprint ou release. (Texto padrão fixo.)",
        space_after=10,
    )

    p(doc, "2.6 Remuneração por Análise de Pontos de Função", bold=True, size=11, space_after=6)
    p(
        doc,
        "Quando o dimensionamento for em Pontos de Função, o valor será calculado pela fórmula:",
    )
    p(doc, "VPF = VMA * PROD", bold=True, center=True)
    mixed(doc, [("VMA = ", False), ("{{regra_vma}}", False)])
    mixed(
        doc,
        [
            (
                "A PRODESP adota como taxa de entrega ou produtividade mínima o fator de ",
                False,
            ),
            ("{{horas_por_pf}}", False),
            (" Horas por Ponto de Função.", False),
        ],
    )
    mixed(
        doc,
        [
            ("Métodos admitidos: IFPUG, SFP, NESMA, COSMIC", False),
            ("{{incluir_snap}}", False),
            (".", False),
        ],
    )
    mixed(doc, [("Roteiro SISP versão ", False), ("{{versao_sisp}}", False), (".", False)], space_after=10)

    p(doc, "2.7 Remuneração por Horas de Serviço Técnico", bold=True, size=11, space_after=6)
    p(doc, "(Texto padrão fixo.)", space_after=10)

    p(doc, "2.8 Remuneração por Sprints", bold=True, size=11, space_after=6)
    p(doc, "(Texto padrão fixo.)", space_after=10)

    p(doc, "2.9 Tecnologias e Forma de Medição", bold=True, size=11, space_after=6)
    p(doc, "(Texto padrão fixo sobre quando usar PF ou HST.)", space_after=10)

    p(doc, "2.10 Proposta Comercial", bold=True, size=11, space_after=6)
    p(doc, "(Texto padrão fixo.)", space_after=10)

    p(doc, "2.11 Formação de Lotes", bold=True, size=11, space_after=6)
    mixed(
        doc,
        [
            (
                "A contratação será definida em lote único para tecnologias ",
                False,
            ),
            ("{{tecnologia}}", False),
            (", conforme o quadro a seguir (mesmo quadro do Relatório de Justificativa):", False),
        ],
        space_after=6,
    )
    mixed(doc, [("{{quadro_lotes}}", False)], space_after=4)
    p(
        doc,
        "(Tabela: ITEM | PERFIL | EXPERIÊNCIA MÍNIMA (ANOS) | HORAS | PROPORÇÃO DO VALOR-HORA.)",
        size=9,
        space_after=4,
    )
    mixed(
        doc,
        [
            ('Item de referência do desconto: "', False),
            ("{{perfil_referencia}}", False),
            ('".', False),
        ],
        space_after=12,
    )

    # 3 QUALIFICAÇÕES
    p(doc, "3. QUALIFICAÇÕES E COMPETÊNCIAS", bold=True, size=12, space_after=8)
    p(doc, "3.1 Qualificações", bold=True, size=11, space_after=6)
    p(
        doc,
        "3.1.1 a 3.1.4, 3.1.6 e 3.1.7 — comprovação de experiência, formação superior e "
        "substituição em até 5 (cinco) dias úteis. (Texto padrão fixo.)",
    )
    p(
        doc,
        "3.1.5 Quadro de experiência mínima — reaproveita os perfis do item 2.11.",
        space_after=6,
    )
    p(doc, "3.1.8 Domínio mínimo da plataforma:", bold=True, space_after=4)
    mixed(doc, [("{{dominio_plataforma}}", False)], space_after=4)
    p(
        doc,
        "(Lista de serviços/módulos da tecnologia, a partir do catálogo do objeto.)",
        size=9,
        space_after=10,
    )

    p(doc, "3.2 Perfis Técnicos", bold=True, size=11, space_after=6)
    p(
        doc,
        "Para execução dos serviços serão requeridos os Perfis Técnicos relacionados no "
        "quadro do subitem 2.11, com as qualificações e competências descritas a seguir.",
        space_after=6,
    )
    mixed(doc, [("{{descricao_perfis}}", False)], space_after=4)
    p(
        doc,
        "(Texto da IA por perfil: atuação + experiência e domínio — limitado aos perfis e "
        "à tecnologia cadastrados.)",
        size=9,
        space_after=10,
    )

    p(doc, "3.3 Certificações", bold=True, size=11, space_after=6)
    mixed(doc, [("Regime da exigência: ", False), ("{{regime_certificacao}}", False)])
    mixed(doc, [("Certificações: ", False), ("{{certificacoes}}", False)], space_after=4)
    p(
        doc,
        "(Ex.: obrigatória no ato da contratação, ou exemplificativa na ordem de serviço.)",
        size=9,
        space_after=10,
    )

    p(doc, "3.4 Métodos ágeis", bold=True, size=11, space_after=6)
    p(
        doc,
        "Declaração de capacidade em Scrum, XP, FDD ou ASD. (Texto padrão fixo.)",
        space_after=12,
    )

    # 4 EXECUÇÃO
    p(doc, "4. EXECUÇÃO E ENTREGA DOS SERVIÇOS", bold=True, size=12, space_after=8)
    p(doc, "4.1 a 4.5 Ordem de serviço, local, horário, teletrabalho e representantes", bold=True, size=11, space_after=6)
    p(
        doc,
        "Ordem de serviço (assinatura em até 2 dias úteis), local de execução, horário, "
        "teletrabalho e representantes técnicos. (Texto padrão fixo.)",
        space_after=10,
    )

    p(doc, "4.6 Descrição dos serviços por item (quando aplicável)", bold=True, size=11, space_after=6)
    mixed(doc, [("{{descricao_itens}}", False)], space_after=4)
    p(
        doc,
        "(Texto da IA por item do lote, a partir do catálogo e dos perfis, sem criar serviço novo. "
        "Pode ficar vazio se o escopo já estiver concentrado no item 2.1.)",
        size=9,
        space_after=10,
    )

    p(doc, "4.7 a 4.9 Entrega, recebimento, SLA, ICE e aceite", bold=True, size=11, space_after=6)
    p(
        doc,
        "Entrega, recebimento, qualidade, ICE de 90% e aceite final. (Texto padrão fixo, "
        "com numeração única.)",
        space_after=12,
    )

    # 5 GOVERNANÇA
    p(doc, "5. PROTEÇÃO E GOVERNANÇA", bold=True, size=12, space_after=8)
    p(doc, "5.1 a 5.5 Subcontratação, garantia, conhecimento, propriedade e dados", bold=True, size=11, space_after=6)
    p(
        doc,
        "Subcontratação até 30%, garantia de 90 dias, transferência de conhecimento, "
        "propriedade intelectual e proteção de dados (comunicação de incidente em até "
        "24 horas). (Texto padrão fixo.)",
        space_after=10,
    )
    p(doc, "5.6 Vedação a consórcio", bold=True, size=11, space_after=6)
    p(
        doc,
        "Vedação a consórcio, com fundamento em execução integrada, habitualidade, "
        "subordinação e mercado apto a atender sozinho. (Texto padrão fixo.)",
        space_after=12,
    )

    # 6 e 7
    p(doc, "6. ELABORAÇÃO", bold=True, size=12, space_after=8)
    mixed(doc, [("{{texto_elaboracao}}", False)], space_after=12)

    p(doc, "7. APROVAÇÃO", bold=True, size=12, space_after=8)
    mixed(doc, [("{{local_data}}", False)], space_after=6)
    mixed(doc, [("{{lista_aprovadores}}", False)], space_after=4)
    p(doc, "(Lista repetível: NOME | MATRÍCULA | CARGO.)", size=9, space_after=16)

    p(
        doc,
        "— LEGENDA DAS TAGS (campos que diferem entre REL.GEN.055 AWS e REL.GEN.099 Dynamics) —",
        bold=True,
        size=10,
        space_after=8,
    )
    for tag, desc in TAGS:
        mixed(doc, [("{{" + tag + "}}", True), (" — " + desc, False)], size=9, space_after=2)

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(SAIDA))
    return SAIDA


if __name__ == "__main__":
    caminho = gerar()
    print(f"salvo {caminho}")
    print(f"tags {len(TAGS)}")
