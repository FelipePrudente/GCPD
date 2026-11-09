# -*- coding: utf-8 -*-
from geradores.comum import (
    TRECHOS,
    agrupar_perfis,
    abrir_corpo,
    capa,
    escrever_blocos,
    extenso,
    formato_inteiro,
    novo_documento,
    paragrafo,
    quadro_perfis,
    inserir_tabelas_extras,
    subtitulo,
    titulo,
    total_horas,
)


def _narrativa_definicao(dados):
    textos = [
        f"{dados['tecnologia']} é a plataforma objeto desta contratação, utilizada pela PRODESP "
        "para desenvolvimento, implantação, manutenção e suporte de sistemas de informação."
    ]
    if dados["catalogo"]:
        textos.append("O escopo informado no cadastro contempla os seguintes grupos, sem inclusão de serviço que não tenha sido registrado:")
        for grupo in dados["catalogo"]:
            textos.append(f"{grupo['grupo']}: {grupo['servicos']}.")
    else:
        textos.append("O catálogo de serviços da plataforma não foi informado no cadastro e deve ser completado na revisão deste relatório.")
    return textos


def _narrativa_situacao(dados):
    textos = []
    if dados.get("fatos"):
        textos.append(dados["fatos"].strip())
    textos.append(
        "Esses serviços complementam a capacidade interna da PRODESP e apoiam a transferência "
        "de conhecimento para o corpo técnico, mediante demandas formalizadas por Ordem de Serviço."
    )
    return textos


def _narrativa_justificativa(dados):
    textos = [
        f"A PRODESP necessita contratar serviços de Apoio Técnico Especializado em {dados['tecnologia']} "
        "para assegurar design, desenvolvimento, configuração, implantação, manutenção e suporte "
        "de sistemas de informação e plataformas tecnológicas."
    ]
    if dados.get("fatos"):
        textos.append(dados["fatos"].strip())
    if dados["clientes"]:
        nomes = ", ".join(
            f"{c['projeto']} ({c['cliente']})" if c.get("cliente") else c["projeto"]
            for c in dados["clientes"]
        )
        textos.append(f"As demandas informadas no cadastro incluem: {nomes}.")
    textos.append(
        "Nenhum indicador quantitativo além dos fatos e das horas cadastradas foi acrescentado a este texto."
    )
    return textos


def gerar_relatorio(dados, caminho):
    doc = novo_documento(dados, "relatorio")
    capa(doc, "RELATÓRIO DE JUSTIFICATIVA", dados, dados["codigo_relatorio"], dados["versao_relatorio"])
    abrir_corpo(doc, dados)

    titulo(doc, "1. OBJETIVO")
    paragrafo(
        doc,
        "Justificar a necessidade de abertura de Processo Licitatório para contratação de Serviços de "
        "Apoio Técnico Especializado contemplando design, desenvolvimento, configuração, implantação, "
        f"manutenção e suporte de sistemas de informação e plataformas tecnológicas da PRODESP utilizando {dados['tecnologia']}.",
    )

    titulo(doc, "2. CONSIDERAÇÕES")
    subtitulo(doc, "2.1 Definições")
    subtitulo(doc, f"2.1.1 {dados['tecnologia']}")
    for texto in _narrativa_definicao(dados):
        paragrafo(doc, texto)

    escrever_blocos(doc, TRECHOS["rj"]["unidades_medida"])

    subtitulo(doc, "2.3 Situação Atual")
    for texto in _narrativa_situacao(dados):
        paragrafo(doc, texto)

    titulo(doc, "3. PROCEDIMENTOS ADOTADOS")
    subtitulo(doc, "3.1 Justificativa Para a Licitação")
    for texto in _narrativa_justificativa(dados):
        paragrafo(doc, texto)

    subtitulo(doc, "3.1.2 Demanda Atual de Serviços")
    paragrafo(
        doc,
        "Para confirmar a necessidade de nova contratação foi efetuada consulta às gerências das áreas de "
        "desenvolvimento e de operações para manifestarem-se sobre a existência de demandas, projetos e "
        "sistemas que utilizarão as referidas tecnologias.",
    )
    paragrafo(
        doc,
        "Constatou-se que existem projetos em fase de estudo que poderão utilizar os serviços que serão "
        "contratados, assim como sistemas que requerem Apoio Técnico Especializado nestas tecnologias "
        "para sua manutenção evolutiva, dos quais se destacam os seguintes:",
    )
    if dados["clientes"]:
        from geradores.comum import tabela
        tabela(
            doc,
            ["Cliente", "Projeto/Sistema"],
            [[c.get("cliente", ""), c.get("projeto", "")] for c in dados["clientes"]],
        )
    else:
        paragrafo(doc, "Nenhum cliente ou projeto foi informado no cadastro.")
    paragrafo(
        doc,
        "Como a utilização do Apoio Técnico Especializado se dará por intermédio de demandas, que serão "
        "apresentadas pelas gerências de Desenvolvimento de Sistemas e de Operações, no decorrer da vigência "
        "dos contratos, na fase atual não é possível fechar o cronograma de execução dos projetos, o que será "
        "feito por ocasião da apresentação do relatório que justificará a emissão da Ordem de Serviço, que "
        "contemplará o dimensionamento dos entregáveis, perfis técnicos, respectivos níveis e prazo de execução.",
    )

    subtitulo(doc, "3.2 Demanda")
    paragrafo(
        doc,
        "A demanda apresentada foi apurada frente ao volume de serviços, sistemas e plataformas demandados "
        "pela PRODESP, além das novas demandas informadas no cadastro, conforme o quadro a seguir.",
    )
    quadro_perfis(doc, dados["perfis"], com_proporcao=False)

    horas = total_horas(dados["perfis"])
    subtitulo(doc, "3.3 Da Licitação")
    paragrafo(
        doc,
        f"Para a realização dos serviços de Apoio Técnico Especializado previstos, foi estimado um total de "
        f"{formato_inteiro(horas)} ({extenso(horas)}) horas, apresentados no quadro abaixo.",
    )
    quadro_perfis(doc, dados["perfis"], com_proporcao=True)
    inserir_tabelas_extras(doc, dados)

    subtitulo(doc, "3.4 Critérios para Contratação")
    paragrafo(
        doc,
        "3.4.1 A elaboração do edital de licitação e do contrato de prestação de serviços deverá ser baseada "
        f"neste relatório e no TERMO DE REFERÊNCIA - Contratação de Serviços de Apoio Técnico Especializado em "
        f"{dados['tecnologia']}, juntado ao processo.",
    )
    paragrafo(
        doc,
        "3.4.2 O critério de julgamento será o de menor valor total do lote, obtido mediante aplicação da relação "
        f"de proporcionalidade do maior desconto ofertado sobre o item de referência \"{dados['perfil_referencia']}\".",
    )
    paragrafo(
        doc,
        "O critério de julgamento será o menor valor total do lote, apurado a partir do maior desconto percentual "
        f"ofertado sobre o valor base do item de referência (\"{dados['perfil_referencia']}\"). Os preços dos demais "
        "itens serão calculados automaticamente, mediante a aplicação da tabela de proporcionalidade de valor-hora "
        "vinculada ao item principal, conforme detalhado no item 2.11 do Termo de Referência.",
    )

    subtitulo(doc, "3.5 Contratação de Projetos em Pontos de Função")
    paragrafo(
        doc,
        "3.5.1 A critério da PRODESP poderá ser solicitado o desenvolvimento de projetos dimensionados em Pontos de "
        "Função, que deverão contemplar somente as tecnologias passíveis de medição nesta sistemática, conforme "
        "previsto no item 2.2 deste relatório.",
    )
    paragrafo(doc, "3.5.2 Quando o dimensionamento de projetos for realizado em Pontos de Função, o valor do Ponto de Função será calculado de acordo com a seguinte fórmula: VPF = VMA * PROD.")
    paragrafo(doc, "VPF = Valor do Ponto de Função.")
    paragrafo(doc, f"VMA = {dados['regra_vma']}.")
    paragrafo(doc, "PROD = Produtividade mínima estabelecida.")
    paragrafo(
        doc,
        f"A PRODESP adota como taxa de entrega ou de produtividade mínima, nas tecnologias previstas neste "
        f"documento, o fator de {dados['horas_por_pf']} horas por ponto de função.",
    )
    paragrafo(doc, "3.5.3 A medição dos serviços para execução em Pontos de Função será feita de acordo com a técnica de Análise de Pontos de Função (APF), conforme previsto no Termo de Referência.")
    paragrafo(doc, "3.5.4 Para execução dos projetos contratados em Pontos de Função, a PRODESP solicitará à CONTRATADA a elaboração de um Plano de Projeto (SoW - Statement of Work). A PRODESP se reserva o direito de dispensar a elaboração do SoW, avaliando caso a caso.")
    paragrafo(doc, "3.5.5 A Ordem de Serviço para projetos dimensionados em Pontos de Função terá como anexo a Planilha de Memória de Cálculo de Pontos de Função, e o pagamento se dará de acordo com os entregáveis acordados.")

    subtitulo(doc, "3.6 Proposta Comercial")
    paragrafo(
        doc,
        f"3.6.1 A Proposta Comercial com o percentual de desconto proposto no item de referência "
        f"\"{dados['perfil_referencia']}\" deverá ser apresentada juntamente com a planilha dos preços ofertados, "
        "nos termos do Edital, ambas em formulários eletrônicos, devidamente assinados.",
    )
    paragrafo(doc, "3.6.2 Os preços resultantes do cálculo linear do desconto final negociado devem ser apresentados para a Hora de Serviço Técnico (HST) de cada Perfil Técnico, juntamente com o valor total calculado com base nos quantitativos previstos para o lote em disputa, conforme a Planilha Orçamentária, Anexo II-B do Edital.")
    paragrafo(doc, "3.6.3 O preço deverá ser expresso em moeda corrente nacional, com aproximação de duas casas decimais, devendo incluir os impostos, taxas, salários, encargos sociais e trabalhistas, contribuições previdenciárias e todas as demais obrigações e despesas necessárias à execução dos serviços.")
    paragrafo(
        doc,
        f"3.6.4 A licitante vencedora será definida pela apresentação do menor valor total do lote, apurado a partir "
        f"do maior desconto percentual ofertado sobre o valor base do item de referência (\"{dados['perfil_referencia']}\").",
    )
    paragrafo(doc, "3.6.5 As informações deverão ser apresentadas conforme o modelo da Proposta Comercial.")

    subtitulo(doc, "3.7 Perfis Técnicos")
    paragrafo(
        doc,
        "3.7.1 Para execução dos serviços contratados serão requeridos os Perfis Técnicos relacionados no quadro "
        f"do subitem 3.3, com as qualificações e competências descritas no Termo de Referência de {dados['tecnologia']}, "
        "juntado ao processo.",
    )
    escrever_blocos(doc, TRECHOS["rj"]["perfis_tecnicos_fixos"])

    subtitulo(doc, "3.8 Comprovação Técnica")
    paragrafo(doc, "Para garantir que os serviços que serão prestados estarão aderentes aos processos de desenvolvimento de software, voltados à qualidade e alinhados com as melhores práticas do mercado, a LICITANTE que sagrar-se vencedora deverá atender às seguintes exigências.")
    subtitulo(doc, "3.8.1 Na Habilitação")
    subtitulo(doc, "3.8.1.1 Declarações")
    paragrafo(doc, "a) Declaração de Capacidade Técnica Própria subscrita por representante legal da licitante, declarando que possui pessoal técnico essencial e capacitado para a execução dos serviços descritos no Termo de Referência.")
    paragrafo(doc, "b) Declaração de que já desenvolveu projetos usando métodos ágeis, tais como Scrum, XP, FDD, ASD ou assemelhados, identificando as principais características da metodologia empregada.")
    paragrafo(doc, "c) Declaração de ciência quanto aos requisitos de assinatura do contrato, nos termos informados no cadastro:")
    if dados.get("parceria"):
        paragrafo(doc, dados["parceria"].strip())
    if dados.get("estudo_mercado"):
        paragrafo(doc, dados["estudo_mercado"].strip())
    if dados.get("certificacoes"):
        paragrafo(doc, "Certificações profissionais exigidas: " + "; ".join(dados["certificacoes"]) + ".")
        paragrafo(doc, f"Regime da exigência: {dados['regime_certificacao']}.")
    subtitulo(doc, "3.8.1.2 Qualificação Técnica Operacional")
    paragrafo(doc, "Atestados específicos informados no cadastro:")
    paragrafo(doc, dados.get("atestados") or "Nenhum atestado específico foi informado no cadastro. Completar na revisão.")
    regras = []
    for bloco in TRECHOS["rj"]["atestados_regras"]:
        regras.append(bloco.replace("12 Horas", f"{dados['horas_por_pf']} Horas").replace("12 horas", f"{dados['horas_por_pf']} horas"))
    escrever_blocos(doc, regras)
    if dados.get("horas_professional"):
        paragrafo(
            doc,
            f"A empresa deverá comprovar a contratação de serviços profissionais do fabricante nos últimos 12 meses, "
            f"com volume mínimo de {dados['horas_professional']} horas.",
        )

    escrever_blocos(doc, TRECHOS["rj"]["economico"])
    escrever_blocos(doc, TRECHOS["rj"]["planilha"])
    subtitulo(doc, "3.11 Assinatura do contrato")
    paragrafo(doc, "Por ocasião da celebração do contrato, a LICITANTE que sagrar-se vencedora deverá atender as condições dispostas nos subitens a seguir.")
    escrever_blocos(doc, TRECHOS["rj"]["representante"])
    subtitulo(doc, "3.11.2 Parceiro, estudo de mercado e certificações")
    paragrafo(doc, dados.get("parceria") or "A comprovação de parceiro do fabricante deve ser completada na revisão.")
    paragrafo(doc, dados.get("estudo_mercado") or "O estudo de mercado exigido deve ser completado na revisão.")
    if dados.get("certificacoes"):
        for certificacao in dados["certificacoes"]:
            paragrafo(doc, certificacao)
    escrever_blocos(doc, TRECHOS["rj"]["cmmi"])
    escrever_blocos(doc, TRECHOS["rj"]["iso"])

    escrever_blocos(doc, TRECHOS["rj"]["obrigacoes"])
    escrever_blocos(doc, TRECHOS["rj"]["modelos"])
    escrever_blocos(doc, TRECHOS["rj"]["recursos"])
    escrever_blocos(doc, TRECHOS["rj"]["gestor"])

    subtitulo(doc, "8. CONCLUSÃO")
    paragrafo(
        doc,
        "Considerando a necessidade de garantir a continuidade dos serviços prestados aos clientes e de atender "
        f"a novas demandas de projetos, solicita-se autorização para a abertura de processo licitatório visando à "
        f"contratação de {formato_inteiro(horas)} ({extenso(horas)}) horas de serviços de Apoio Técnico Especializado "
        f"em {dados['tecnologia']}, para atividades de design, desenvolvimento, configuração, implantação, manutenção "
        f"e suporte de sistemas de informação e plataformas tecnológicas, a serem utilizadas em um período de "
        f"{dados['prazo_meses']} ({_prazo(dados['prazo_meses'])}) meses a partir da data de assinatura do contrato, "
        "definido em lote único, com valor total a ser estimado na pesquisa de preços.",
    )

    subtitulo(doc, "9. ELABORAÇÃO")
    paragrafo(doc, dados["area_elaboracao"])
    subtitulo(doc, "10. APROVAÇÃO")
    if dados.get("local_data"):
        paragrafo(doc, dados["local_data"])
    for pessoa in dados["aprovadores"]:
        paragrafo(doc, pessoa["nome"])
        if pessoa.get("matricula"):
            paragrafo(doc, f"Matrícula: {pessoa['matricula']}")
        paragrafo(doc, pessoa.get("cargo") or "")

    doc.save(caminho)


def _prazo(meses):
    try:
        numero = int(meses)
    except (TypeError, ValueError):
        return str(meses)
    nomes = {12: "doze", 24: "vinte e quatro", 36: "trinta e seis", 6: "seis", 18: "dezoito"}
    return nomes.get(numero, extenso(numero, feminino=False))
