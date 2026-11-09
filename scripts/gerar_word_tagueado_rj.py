# -*- coding: utf-8 -*-
"""Gera Word tagueado a partir da comparação AWS x Dynamics."""
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt, RGBColor

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "modelos" / "Relatorio_Justificativa_TAGUEADO.docx"

TAGS = [
    ("unidade_cabecalho", "Unidade no cabeçalho da capa"),
    ("n_processo_sei", "Número do processo SEI"),
    ("tecnologia", "Nome da tecnologia"),
    ("sigla_relatorio", "Código do relatório (ex.: REL.GEN.054.2026)"),
    ("versao", "Versão (ex.: V1.0)"),
    ("mes_ano", "Mês e ano (ex.: Março/2026)"),
    ("definicao_da_plataforma", "Texto IA — item 2.1.1"),
    ("situacao_atual", "Texto IA — item 2.3"),
    ("existe_contrato_vigente", "Fato cadastral para a IA (contrato vigente?)"),
    ("justificativa", "Texto IA — item 3.1"),
    ("fatos_que_nao_podem_ser_inventados", "Fatos cadastrais para a IA na justificativa"),
    ("lista_cliente_projeto", "Tabela CLIENTE | PROJETO/SISTEMA"),
    ("quadro_demanda", "Tabela de perfis/horas do item 3.2"),
    ("quadro_licitacao", "Tabela do item 3.3 com proporção"),
    ("total_horas", "Total de horas (calculado)"),
    ("total_por_extenso", "Total de horas por extenso (calculado)"),
    ("perfil_referencia", "Perfil de referência do desconto"),
    ("regra_vma", "Regra do valor médio da hora (VMA)"),
    ("horas_por_pf", "Horas por ponto de função"),
    ("parceria_fabricante", "Exigência de parceria com o fabricante"),
    ("estudo_de_mercado", "Estudo de mercado exigido"),
    ("atestados_especificos", "Atestados específicos e horas mínimas"),
    ("certificacoes", "Certificações profissionais exigidas"),
    ("prazo_meses", "Prazo de vigência em meses"),
    ("area_elaboradora", "Área que elabora o relatório"),
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

    p(doc, "RELATÓRIO DE JUSTIFICATIVA", bold=True, center=True, size=14, space_after=10)
    mixed(doc, [("Nº do Processo: ", False), ("{{n_processo_sei}}", False)])
    p(doc, "Interessado: CIA DE PROCESSAMENTO DE DADOS DO ESTADO DE SAO PAULO - PRODESP")
    mixed(
        doc,
        [
            ("Assunto: CONTRATAÇÃO DE SERVIÇOS DE APOIO TÉCNICO ESPECIALIZADO EM ", False),
            ("{{tecnologia}}", False),
        ],
        space_after=10,
    )

    p(doc, "RELATÓRIO DE JUSTIFICATIVA", bold=True, center=True, size=12, space_after=2)
    mixed(doc, [("{{sigla_relatorio}} ", False), ("{{versao}}", False)], center=True, space_after=8)
    p(
        doc,
        "LICITAÇÃO PARA CONTRATAÇÃO DE SERVIÇOS DE APOIO TÉCNICO",
        bold=True,
        center=True,
        size=11,
        space_after=2,
    )
    mixed(doc, [("ESPECIALIZADO EM ", True), ("{{tecnologia}}", True)], center=True, space_after=12)

    p(doc, "DDS - Diretoria de Desenvolvimento de Sistemas", center=True, space_after=2)
    p(doc, "SCL – Superintendência de Sistemas Estruturantes", center=True, space_after=2)
    p(doc, "GEN - Gerência de Engenharia de Software e Serviços", center=True, space_after=2)
    mixed(doc, [("{{mes_ano}}", False)], center=True, space_after=16)

    p(doc, "1. OBJETIVO", bold=True, size=12, space_after=8)
    mixed(
        doc,
        [
            (
                "Justificar a necessidade de abertura de Processo Licitatório para contratação de "
                "Serviços de Apoio Técnico Especializado contemplando design, desenvolvimento, "
                "configuração, implantação, manutenção e suporte de sistemas de informação e "
                "plataformas tecnológicas da PRODESP utilizando ",
                False,
            ),
            ("{{tecnologia}}", False),
            (".", False),
        ],
        space_after=12,
    )

    p(doc, "2. CONSIDERAÇÕES", bold=True, size=12, space_after=8)
    p(doc, "2.1 Definições", bold=True, size=11, space_after=6)
    mixed(doc, [("2.1.1 ", False), ("{{definicao_da_plataforma}}", False)], space_after=4)
    p(doc, "(Texto integral redigido pela IA a partir da tecnologia informada.)", size=9, space_after=10)

    p(doc, "2.2 Unidades de Medidas para Desenvolvimento dos Serviços", bold=True, size=11, space_after=6)
    p(
        doc,
        "2.2.1 A medição dos serviços poderá ser baseada em Análise de Pontos de Função (APF) "
        "ou em Horas de Serviço Técnico (HST).",
    )
    p(
        doc,
        "2.2.2 A escolha da forma de medição se dará de acordo com as características de cada "
        "projeto, considerando-se os requisitos da tecnologia que será utilizada, conforme "
        "detalhado no subitem “2.2.5 Tecnologias e Forma de Medição”.",
    )
    p(
        doc,
        "a) Serviços que podem ser desenvolvidos com medição em Pontos de Função, a critério da "
        "PRODESP também poderão ser contratados em Horas de Serviço Técnico (HST), mediante "
        "solicitação por intermédio de Ordem de Serviço.",
    )
    p(
        doc,
        "b) A medição em Horas de Serviço Técnico (HST) atenderá preferencialmente serviços de "
        "manutenção de Sistemas e Aplicativos, devido à impossibilidade de produção dos "
        "artefatos necessários para realização das manutenções em Pontos de Função, dentro dos "
        "prazos de urgência requeridos.",
    )
    p(
        doc,
        "2.2.3 O valor unitário do Ponto de Função será calculado conforme fórmula apresentada "
        "no subitem “3.5 Contratação de Projetos em Pontos de Função”.",
    )
    p(
        doc,
        "2.2.4 A execução de serviços contratados em Horas de Serviço Técnico (HST) ocorrerá "
        "somente nas dependências da PRODESP, de seus Clientes ou em regime de Teletrabalho "
        "(Home Office) quando requerido pela PRODESP, e a CONTRATADA deverá apresentar um "
        "Relatório de Serviço Técnico (RST), mensal, por ocasião do faturamento dos serviços.",
    )
    p(
        doc,
        "2.2.4.1 Independentemente do local de trabalho a CONTRATADA deverá fornecer às suas "
        "expensas todos os recursos necessários para a execução dos serviços, dentre os quais "
        "destacam-se: hardware, software, meios de comunicação etc.",
    )
    p(doc, "2.2.5 Tecnologias e Forma de Medição:", bold=True, space_after=4)
    p(
        doc,
        "Será passível de medição em PF quando envolver linguagens de programação que utilizem "
        "requisitos funcionais definidos e mensuráveis em Pontos de Função. Para recursos "
        "tecnológicos que envolva apenas recursos de configuração e parametrização deve-se "
        "adotar HST, sempre que possível.",
        space_after=10,
    )

    p(doc, "2.3 Situação Atual", bold=True, size=11, space_after=6)
    mixed(doc, [("{{situacao_atual}}", False)], space_after=4)
    p(doc, "(Texto integral redigido pela IA. Fato cadastral que não pode ser inventado:)", size=9, space_after=2)
    mixed(doc, [("{{existe_contrato_vigente}}", False)], space_after=12)

    p(doc, "3. PROCEDIMENTOS ADOTADOS", bold=True, size=12, space_after=8)
    p(doc, "3.1 Justificativa Para a Licitação", bold=True, size=11, space_after=6)
    mixed(doc, [("{{justificativa}}", False)], space_after=4)
    p(
        doc,
        "(Texto integral redigido pela IA. Fatos cadastrais que não podem ser inventados:)",
        size=9,
        space_after=2,
    )
    mixed(doc, [("{{fatos_que_nao_podem_ser_inventados}}", False)], space_after=10)

    p(doc, "3.1.2 Demanda Atual de Serviços", bold=True, size=11, space_after=6)
    p(
        doc,
        "Para confirmar a necessidade de nova contratação foi efetuada consulta às gerências "
        "das áreas de desenvolvimento e de operações para manifestarem-se sobre a existência "
        "de demandas/projetos/sistemas que utilizarão as referidas tecnologias.",
    )
    p(
        doc,
        "Constatou-se que existem projetos em fase de estudo que poderão utilizar os serviços "
        "que serão contratados, assim como diversos sistemas que requerem a utilização de "
        "serviços de Apoio Técnico Especializado nestas Tecnologias para sua manutenção "
        "evolutiva, dos quais destacamos os seguintes:",
    )
    mixed(doc, [("{{lista_cliente_projeto}}", False)], space_after=4)
    p(doc, "(Tabela: colunas CLIENTE | PROJETO/SISTEMA — uma linha por demanda.)", size=9, space_after=6)
    p(
        doc,
        "Como a utilização do Apoio Técnico Especializado se dará por intermédio de demandas, "
        "que serão apresentadas pelas gerências de Desenvolvimento de Sistemas e de Operações, "
        "no decorrer da vigência dos contratos, na fase atual não é possível fechar o "
        "cronograma de execução dos projetos, o que será feito por ocasião da apresentação do "
        "relatório que justificará a emissão da Ordem de Serviço.",
        space_after=10,
    )

    p(doc, "3.2 Demanda", bold=True, size=11, space_after=6)
    p(
        doc,
        "A demanda apresentada foi apurada frente ao volume de serviços, sistemas e plataformas "
        "demandados pela Prodesp nos últimos 12 meses, além de novas demandas em estágio de "
        "prospecção e negociação comercial pela Prodesp, conforme demonstrado no quadro a seguir:",
    )
    mixed(doc, [("{{quadro_demanda}}", False)], space_after=4)
    p(
        doc,
        "(Tabela repetível por item/lote: ITEM | PERFIL | EXPERIÊNCIA MÍNIMA (ANOS) | TOTAL DE HORAS.)",
        size=9,
        space_after=10,
    )

    p(doc, "3.3 Da Licitação", bold=True, size=11, space_after=6)
    mixed(
        doc,
        [
            (
                "Para a realização dos serviços de Apoio Técnico Especializado previstos, "
                "foi estimado um total de ",
                False,
            ),
            ("{{total_horas}}", False),
            (" (", False),
            ("{{total_por_extenso}}", False),
            (") horas, apresentados no quadro abaixo.", False),
        ],
        space_after=6,
    )
    mixed(doc, [("{{quadro_licitacao}}", False)], space_after=4)
    p(doc, "(Mesmo quadro do 3.2, acrescido da coluna PROPORÇÃO DO VALOR-HORA.)", size=9, space_after=10)

    p(doc, "3.4 Critérios para Contratação", bold=True, size=11, space_after=6)
    mixed(
        doc,
        [
            (
                "3.4.1 A elaboração do edital de licitação e do contrato de prestação de serviços "
                "deverá ser baseada neste relatório e no TERMO DE REFERÊNCIA - Contratação de "
                "Serviços de Apoio Técnico Especializado em ",
                False,
            ),
            ("{{tecnologia}}", False),
            (", juntado ao processo.", False),
        ],
    )
    mixed(
        doc,
        [
            (
                "3.4.2 O critério de julgamento será o de menor valor total do lote, obtido "
                "mediante aplicação da relação de proporcionalidade do maior desconto ofertado "
                'sobre o item de referência "',
                False,
            ),
            ("{{perfil_referencia}}", False),
            ('".', False),
        ],
        space_after=10,
    )

    p(doc, "3.5 Contratação de Projetos em Pontos de Função", bold=True, size=11, space_after=6)
    p(
        doc,
        "3.5.2 Quando o dimensionamento de projetos for realizado em Pontos de Função, o valor "
        "do Ponto de Função será calculado de acordo com a seguinte fórmula:",
    )
    p(doc, "VPF = VMA * PROD", bold=True, center=True)
    mixed(doc, [("VMA = ", False), ("{{regra_vma}}", False)])
    mixed(
        doc,
        [
            (
                "A PRODESP adota como taxa de entrega ou de produtividade mínima, nas tecnologias "
                "previstas neste documento, o fator de ",
                False,
            ),
            ("{{horas_por_pf}}", False),
            (" Horas por Ponto de Função.", False),
        ],
        space_after=6,
    )
    p(doc, "(Os itens 3.5.1, 3.5.3, 3.5.4 e 3.5.5 permanecem no texto padrão fixo.)", size=9, space_after=10)

    p(doc, "3.6 Proposta Comercial", bold=True, size=11, space_after=6)
    mixed(
        doc,
        [
            ('A proposta comercial observará o item de referência "', False),
            ("{{perfil_referencia}}", False),
            ('", conforme critérios do edital.', False),
        ],
        space_after=10,
    )

    p(doc, "3.7 Perfis Técnicos", bold=True, size=11, space_after=6)
    mixed(
        doc,
        [
            (
                "3.7.1 Para execução dos serviços contratados serão requeridos os Perfis Técnicos "
                "relacionados no quadro apresentados no subitem 3.3., acima, com as Qualificações "
                "e Competências descritas no TERMO DE REFERÊNCIA – Contratação de Serviços de "
                "Apoio Técnico Especializado em ",
                False,
            ),
            ("{{tecnologia}}", False),
            (", juntado ao processo.", False),
        ],
    )
    p(doc, "3.7.4 Qualquer profissional alocado deverá ser substituído em até 5 (cinco) dias úteis.")
    p(
        doc,
        "3.7.5 Todos os profissionais deverão possuir graduação Superior em pelo menos um dos "
        "cursos previstos no texto padrão.",
        space_after=10,
    )

    p(doc, "3.8 Comprovação Técnica", bold=True, size=11, space_after=6)
    p(
        doc,
        "Para garantir que os serviços que serão prestados estarão aderentes aos processos de "
        "desenvolvimento de software, voltados à qualidade e alinhados com as melhores práticas "
        "do mercado, a LICITANTE que sagrar-se vencedora deverá atender às seguintes exigências.",
    )
    p(
        doc,
        "(Declarações gerais de capacidade própria, métodos ágeis, regras de atestados a 50% do "
        "volume, sigilo, diligência, tradução e grupo empresarial: texto padrão fixo.)",
        size=9,
        space_after=6,
    )
    p(doc, "Bloco variável por tecnologia:", bold=True, space_after=4)
    mixed(doc, [("Parceria com o fabricante: ", False), ("{{parceria_fabricante}}", False)])
    mixed(doc, [("Estudo de mercado: ", False), ("{{estudo_de_mercado}}", False)])
    mixed(doc, [("Atestados específicos e horas mínimas: ", False), ("{{atestados_especificos}}", False)])
    mixed(
        doc,
        [
            ("Equivalência dos atestados em Pontos de Função: ", False),
            ("{{horas_por_pf}}", False),
            (" horas por ponto de função.", False),
        ],
        space_after=10,
    )

    p(doc, "3.9 Qualificação Econômico-Financeira", bold=True, size=11, space_after=6)
    p(
        doc,
        "Certidão negativa de falência, balanço patrimonial e patrimônio líquido mínimo de "
        "10% (dez por cento) do valor estimado da contratação. (Texto padrão fixo.)",
        space_after=10,
    )

    p(doc, "3.10 Planilha de Composição de Custos e Preços", bold=True, size=11, space_after=6)
    p(
        doc,
        "Critérios da letra a à letra k, inclusive salário por perfil, regime tributário, "
        "encargos, benefícios da CCT, lucro e taxa de administração. (Texto padrão fixo.)",
        space_after=10,
    )

    p(doc, "3.11 Assinatura do contrato", bold=True, size=11, space_after=6)
    p(
        doc,
        "3.11.1 Representante Técnico — a LICITANTE deverá designar um Representante Técnico "
        "que atuará como o preposto. (Texto padrão fixo.)",
    )
    mixed(doc, [("3.11.2 Comprovação de Parceiro Certificado: ", False), ("{{parceria_fabricante}}", False)])
    mixed(doc, [("3.11.3 Reconhecimento em Estudo de Mercado: ", False), ("{{estudo_de_mercado}}", False)])
    mixed(doc, [("Comprovação de profissional certificado: ", False), ("{{certificacoes}}", False)])
    p(
        doc,
        "3.11.4 CMMI nível 3 ou MPS.BR nível C, e 3.11.5 ISO 9001 e ISO/IEC 27001. "
        "(Texto padrão fixo, se confirmado que o nível exigido não muda.)",
        space_after=10,
    )

    p(doc, "4. OBRIGAÇÕES", bold=True, size=12, space_after=8)
    p(
        doc,
        "4.1.1 Garantia Contratual — A contratada deverá apresentar garantia de 5% do valor do "
        "contrato, em até 15 dias após a assinatura.",
    )
    p(
        doc,
        "4.1.2 Substituição de profissional em até 5 (cinco) dias úteis, entre as demais "
        "obrigações da contratada e da PRODESP. (Texto padrão fixo.)",
        space_after=10,
    )

    p(doc, "5. MODELOS DE FORMULÁRIOS", bold=True, size=12, space_after=8)
    for item in [
        "5.1 Modelo da Ordem de Serviço de Apoio Técnico Especializado - ATE",
        "5.2 Modelo do Plano do Projeto – SoW (Statement Of Work)",
        "5.3 Modelo de Termo de Recebimento de Serviços",
        "5.4 Modelo do Termo de Aceite de Serviços",
        "5.5 Modelo da Planilha de Composição de Custos e Preços",
        "5.6 Modelo da Planilha de Apuração de Qualificação Técnica Operacional",
        "5.7 Modelo da Proposta Comercial",
        "5.8 Termo de Confidencialidade Sigilo e Uso",
    ]:
        p(doc, item, space_after=2)
    p(doc, "(Anexos 01 a 08: modelos padrão em branco.)", size=9, space_after=10)

    p(doc, "6. RECURSOS FINANCEIROS", bold=True, size=12, space_after=8)
    p(
        doc,
        "Serão utilizados recursos financeiros de origem corporativa para a emissão do DCO "
        "(Documento de Comprovação Orçamentária) destinado a esta contratação, porém a execução "
        "dos serviços se dará mediante a emissão de Ordens de Serviços que serão vinculadas ao "
        "referido DCO, podendo as despesas serem cobertas por ESP, Recurso Corporativo, "
        "Investimento, Condomínio etc.",
        space_after=10,
    )

    p(doc, "7. GESTOR E FISCAL DO CONTRATO", bold=True, size=12, space_after=8)
    p(
        doc,
        "Os funcionários que atuarão como Gestor e Fiscal dos contratos serão indicados pela "
        "área demandante no decorrer do processo.",
        space_after=10,
    )

    p(doc, "8. CONCLUSÃO", bold=True, size=12, space_after=8)
    mixed(
        doc,
        [
            (
                "Considerando a necessidade de garantir a continuidade dos serviços prestados "
                "aos nossos clientes e de atender a novas demandas de projetos, solicitamos a "
                "autorização para a abertura de processo licitatório visando à contratação de ",
                False,
            ),
            ("{{total_horas}}", False),
            (" (", False),
            ("{{total_por_extenso}}", False),
            (") horas de serviços de Apoio Técnico Especializado em ", False),
            ("{{tecnologia}}", False),
            (
                ", para atividades de design, desenvolvimento, configuração, implantação, "
                "manutenção e suporte de sistemas de informação e plataformas tecnológicas, "
                "a serem utilizadas em um período de ",
                False,
            ),
            ("{{prazo_meses}}", False),
            (
                " meses a partir da data de assinatura do contrato, definido em lote único, "
                "com valor total a ser estimado na pesquisa de preços.",
                False,
            ),
        ],
        space_after=12,
    )

    p(doc, "9. ELABORAÇÃO", bold=True, size=12, space_after=8)
    mixed(
        doc,
        [
            ("Este relatório foi elaborado pela ", False),
            ("{{area_elaboradora}}", False),
            (
                ", da Superintendência de Sistemas Estruturantes vinculada à Diretoria de "
                "Desenvolvimento de Sistemas.",
                False,
            ),
        ],
        space_after=10,
    )

    p(doc, "10. APROVAÇÃO", bold=True, size=12, space_after=8)
    mixed(doc, [("{{lista_aprovadores}}", False)], space_after=4)
    p(doc, "(Lista repetível: NOME | MATRÍCULA | CARGO.)", size=9, space_after=12)

    p(doc, "ANEXOS 01 A 08", bold=True, size=12, space_after=6)
    p(
        doc,
        "Modelos padrão em branco (ordem de serviço, SoW, recebimento, aceite, planilhas, "
        "proposta e termo de sigilo). Não fazem parte do preenchimento deste cadastro.",
        space_after=16,
    )

    p(
        doc,
        "— LEGENDA DAS TAGS (campos que diferem entre REL.GEN.054 AWS e REL.GEN.105 Dynamics) —",
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
