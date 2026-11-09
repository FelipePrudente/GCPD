# -*- coding: utf-8 -*-
from geradores.comum import cabecalho_institucional, novo_documento, paragrafo, subtitulo, tabela, titulo
from geradores.pesquisa_fontes import pesquisar, reais


def _faixa(item):
    if not item["encontrado"]:
        return "Dado não localizado em fontes primárias."
    return f"{reais(item['minimo'])} a {reais(item['maximo'])}"


def gerar_pesquisa(dados, caminho):
    resultados = pesquisar(dados)
    com_faixa = [item for item in resultados if item["encontrado"]]
    sem_faixa = [item for item in resultados if not item["encontrado"]]
    proxies = [item for item in com_faixa if item.get("justificativa")]

    doc = novo_documento(dados, "pesquisa")
    cabecalho_institucional(doc, dados)
    titulo(doc, "Pesquisa Salarial de Mercado - Subsídio para TR e ETP")

    subtitulo(doc, "Premissas")
    assunto = (dados.get("assunto") or "").strip() or (
        f"CONTRATAÇÃO DE SERVIÇOS DE APOIO TÉCNICO ESPECIALIZADO EM "
        f"{(dados.get('tecnologia') or '').upper()}"
    )
    paragrafo(doc, f"Assunto: {assunto}")
    paragrafo(doc, f"Objeto: apoio técnico especializado em {dados['tecnologia']}.")
    paragrafo(
        doc,
        "Região, em ordem de prioridade: São Paulo Capital, Grande São Paulo, Estado de São Paulo e Brasil. "
        "A consulta usou o recorte São Paulo do guia. Quando a página regional não publica a faixa, o registro indica DADO NACIONAL - SEM RECORTE REGIONAL.",
    )
    paragrafo(
        doc,
        "Regime: CLT, salário-base mensal bruto, em reais. Ficam fora PJ, valor-hora, hora técnica, benefícios, bônus, PLR, encargos e remuneração anual.",
    )
    paragrafo(
        doc,
        "Fontes autorizadas, nesta ordem: Robert Half, Michael Page, SINDPD-SP, LinkedIn e Glassdoor. "
        "A faixa desta geração saiu do guia salarial Robert Half, primeira fonte da ordem, com página consultada na internet.",
    )
    paragrafo(doc, "Critério da média, quando houver faixa publicada: (mínimo + máximo) ÷ 2.")
    paragrafo(
        doc,
        "No guia Robert Half, o mínimo é o percentil 25 e o máximo é o percentil 75 da faixa publicada. A mediana publicada não substitui a média.",
    )
    paragrafo(
        doc,
        "O SINDPD-SP permanece piso normativo e não foi usado como referência principal de mercado para perfil especializado ou sênior.",
    )

    subtitulo(doc, "Tabela Salarial")
    linhas = []
    for item in resultados:
        linhas.append([
            item["cargo"] or item["nome"],
            item["senioridade"],
            _faixa(item),
            reais(item["media"]) if item["encontrado"] else "—",
            item["fonte"] if item["encontrado"] else "—",
            item["referencia"] if item["encontrado"] else "—",
            item["ano"] if item["encontrado"] else "—",
        ])
    tabela(
        doc,
        ["Cargo pesquisado", "Senioridade", "Faixa salarial CLT", "Média", "Fonte", "Referência", "Ano"],
        linhas,
    )

    soma_min = sum(item["minimo"] for item in com_faixa)
    soma_max = sum(item["maximo"] for item in com_faixa)
    soma_med = sum(item["media"] for item in com_faixa)

    subtitulo(doc, "Totalização")
    if com_faixa:
        paragrafo(
            doc,
            "A soma considera somente os cargos com faixa localizada. Cargo sem valor definido não entra na totalização.",
        )
        tabela(
            doc,
            ["Indicador", "Valor"],
            [
                ["Soma dos mínimos", reais(soma_min)],
                ["Soma dos máximos", reais(soma_max)],
                ["Soma das médias", reais(soma_med)],
            ],
        )
    else:
        paragrafo(doc, "Nenhum cargo teve faixa salarial localizada. A soma não foi calculada.")
        tabela(
            doc,
            ["Indicador", "Valor"],
            [
                ["Soma dos mínimos", "Não aplicável"],
                ["Soma dos máximos", "Não aplicável"],
                ["Soma das médias", "Não aplicável"],
            ],
        )

    subtitulo(doc, "Cargos sem Dados")
    if sem_faixa:
        for item in sem_faixa:
            paragrafo(doc, f"{item['nome']}: Dado não localizado em fontes primárias.")
    else:
        paragrafo(doc, "Todos os cargos pesquisados tiveram faixa publicada em fonte autorizada.")

    subtitulo(doc, "Proxies Utilizados")
    if proxies:
        tabela(
            doc,
            ["Cargo solicitado", "Proxy utilizado", "Fonte", "Aderência", "Justificativa"],
            [
                [
                    item["nome"],
                    item["proxy"],
                    item["fonte"],
                    item["aderencia"],
                    item["justificativa"],
                ]
                for item in proxies
            ],
        )
    else:
        paragrafo(doc, "Nenhum proxy foi utilizado.")
        tabela(
            doc,
            ["Cargo solicitado", "Proxy utilizado", "Fonte", "Aderência", "Justificativa"],
            [["—", "—", "—", "—", "Nenhum proxy utilizado."]],
        )

    subtitulo(doc, "Observações Metodológicas")
    paragrafo(doc, "A média é (mínimo + máximo) ÷ 2. A mediana do guia não foi usada como média.")
    paragrafo(
        doc,
        "A consulta foi feita na internet, no mapa de cargos do guia Robert Half Brasil e na página de São Paulo de cada cargo escolhido.",
    )
    paragrafo(
        doc,
        "Nenhum salário foi estimado, completado por conhecimento próprio ou copiado de anúncio, blog ou fonte fora da lista autorizada.",
    )
    paragrafo(
        doc,
        "Os salários-base representam apenas parte da composição de custos. A formação de preços deve considerar encargos trabalhistas, tributos, custos administrativos, ferramentas, treinamento, reserva técnica e lucro.",
    )

    subtitulo(doc, "Faixas de Referência")
    if com_faixa:
        tabela(
            doc,
            ["Referência", "Critério", "Valor"],
            [
                ["Faixa conservadora", "Soma dos mínimos", reais(soma_min)],
                ["Faixa de mercado", "Soma das médias", reais(soma_med)],
                ["Faixa premium", "Soma dos máximos", reais(soma_max)],
            ],
        )
    else:
        tabela(
            doc,
            ["Referência", "Critério", "Valor"],
            [
                ["Faixa conservadora", "Soma dos mínimos", "Não aplicável"],
                ["Faixa de mercado", "Soma das médias", "Não aplicável"],
                ["Faixa premium", "Soma dos máximos", "Não aplicável"],
            ],
        )

    subtitulo(doc, "Recomendação")
    if com_faixa:
        paragrafo(
            doc,
            "Para contratações públicas de serviços especializados de TI, a referência preferencial é a Faixa de Mercado, soma das médias. "
            f"Nesta pesquisa, a Faixa de Mercado dos cargos com dado localizado é {reais(soma_med)}.",
        )
        if sem_faixa:
            nomes = ", ".join(item["nome"] for item in sem_faixa)
            paragrafo(
                doc,
                f"A recomendação não cobre {nomes}, porque esses cargos ficaram sem faixa em fonte autorizada.",
            )
    else:
        paragrafo(
            doc,
            "Para contratações públicas de serviços especializados de TI, a referência preferencial é a Faixa de Mercado, soma das médias, quando as faixas estiverem publicadas em fonte autorizada.",
        )
        paragrafo(doc, "Como nenhuma faixa foi localizada, a recomendação de valor ainda não pode ser fechada.")
    paragrafo(
        doc,
        "Os salários-base representam apenas parte da composição de custos. A formação de preços deve considerar encargos trabalhistas, tributos, custos administrativos, ferramentas, treinamento, reserva técnica e lucro.",
    )
    if com_faixa:
        paragrafo(
            doc,
            "Valor abaixo do mínimo identificado nesta pesquisa deve ser tratado como risco de inexequibilidade.",
        )

    subtitulo(doc, "Links Consultados")
    links = []
    vistos = set()
    for item in com_faixa:
        if item["url"] in vistos:
            continue
        vistos.add(item["url"])
        links.append([
            "Robert Half",
            item["url"],
            f"Faixa CLT de {item['titulo_publicado']}",
        ])
        if len(links) == 10:
            break
    if links:
        tabela(doc, ["Fonte", "Referência consultada", "Uso"], links)
    else:
        paragrafo(doc, "Nenhum link de faixa publicada foi utilizado nesta geração.")
        tabela(
            doc,
            ["Fonte", "Referência consultada", "Uso"],
            [["—", "Nenhuma faixa publicada foi localizada.", "—"]],
        )

    doc.save(caminho)
