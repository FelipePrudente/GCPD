# -*- coding: utf-8 -*-
from geradores.comum import (
    TRECHOS,
    agrupar_perfis,
    abrir_corpo,
    capa,
    escrever_blocos,
    novo_documento,
    paragrafo,
    quadro_perfis,
    inserir_tabelas_extras,
    subtitulo,
    titulo,
)


def _catalogo_texto(dados):
    if not dados["catalogo"]:
        return "O catálogo de serviços não foi informado no cadastro."
    return " ".join(f"{g['grupo']}: {g['servicos']}." for g in dados["catalogo"])


def gerar_termo(dados, caminho):
    doc = novo_documento(dados, "termo")
    capa(doc, "TERMO DE REFERÊNCIA", dados, dados["codigo_termo"], dados["versao_termo"])
    abrir_corpo(doc, dados)

    escrever_blocos(doc, TRECHOS["tr"]["introducao"])

    titulo(doc, "2. ESCOPO E ESTRATÉGIA DE CONTRATAÇÃO DOS SERVIÇOS")
    subtitulo(doc, "2.1 Do Objeto")
    paragrafo(
        doc,
        f"Prestação de serviços de apoio técnico especializado em {dados['tecnologia']}, contemplando design, "
        "desenvolvimento, configuração, implantação, manutenção e suporte de sistemas de informação e "
        f"plataformas tecnológicas da PRODESP, pelo período de {dados['prazo_meses']} meses.",
    )
    paragrafo(
        doc,
        f"Deverão ser prestados serviços de Apoio Técnico Especializado em {dados['tecnologia']} à PRODESP, "
        "cobrindo a cadeia de valor informada no cadastro, sem inclusão de serviço que não conste do catálogo abaixo.",
    )
    paragrafo(doc, _catalogo_texto(dados))

    escrever_blocos(doc, TRECHOS["tr"]["ambiente"])
    escrever_blocos(doc, TRECHOS["tr"]["metodologia"])
    escrever_blocos(doc, TRECHOS["tr"]["planejamento"])
    escrever_blocos(doc, TRECHOS["tr"]["modalidades"])

    subtitulo(doc, "2.6 Remuneração por Análise de Pontos de Função (APF)")
    paragrafo(doc, "2.6.1.1 A critério da PRODESP, poderá ser solicitado o desenvolvimento de projetos dimensionados em Pontos de Função, que deverão contemplar somente as tecnologias passíveis de medição nesta sistemática.")
    paragrafo(doc, "2.6.1.2 Quando o dimensionamento de projetos for realizado em Pontos de Função, o valor do Ponto de Função será calculado de acordo com a fórmula VPF = VMA * PROD.")
    paragrafo(doc, "VPF = Valor do Ponto de Função.")
    paragrafo(doc, f"VMA = {dados['regra_vma']}.")
    paragrafo(doc, "PROD = Produtividade mínima estabelecida.")
    paragrafo(
        doc,
        f"A PRODESP adota como taxa de entrega ou de produtividade mínima, nas tecnologias previstas neste "
        f"documento, o fator de {dados['horas_por_pf']} horas por ponto de função.",
    )
    blocos_apf = []
    for bloco in TRECHOS["tr"]["apf_depois"]:
        texto = bloco
        if dados.get("incluir_snap") and "NESMA, COSMIC" in texto and "SNAP" not in texto:
            texto = texto.replace("NESMA, COSMIC", "NESMA, SNAP, COSMIC")
        blocos_apf.append(texto)
    escrever_blocos(doc, blocos_apf)
    paragrafo(
        doc,
        f"2.6.3 Roteiro de Métricas de Software do SISP, versão {dados['versao_sisp']}, ou versões posteriores. "
        "O roteiro é um guia complementar ao CPM (IFPUG).",
    )

    escrever_blocos(doc, TRECHOS["tr"]["hst"])
    escrever_blocos(doc, TRECHOS["tr"]["sprints"])
    escrever_blocos(doc, TRECHOS["tr"]["medicao"])
    escrever_blocos(doc, TRECHOS["tr"]["proposta"])

    subtitulo(doc, "2.11 Formação de Lotes para a Contratação")
    paragrafo(
        doc,
        "A licitação de Apoio Técnico Especializado será efetuada em lote único, contemplando as tecnologias "
        f"elencadas neste documento para {dados['tecnologia']}, de acordo com os perfis técnicos e quantitativos "
        "apresentados no quadro a seguir.",
    )
    quadro_perfis(doc, dados["perfis"], com_proporcao=True)
    inserir_tabelas_extras(doc, dados)
    paragrafo(
        doc,
        "A proposta orçamentária deverá ser apresentada com base no valor ofertado para o nível ou item de "
        f"referência \"{dados['perfil_referencia']}\". Os valores unitários correspondentes aos demais perfis "
        "técnicos deverão ser elaborados a partir do valor do item de referência, mediante a aplicação do fator "
        "de proporcionalidade definido na tabela de perfis.",
    )

    titulo(doc, "3. QUALIFICAÇÕES E COMPETÊNCIAS")
    subtitulo(doc, "3.1 Qualificações")
    escrever_blocos(doc, TRECHOS["tr"]["qualificacao_fixa"])
    subtitulo(doc, "3.1.5 Experiência mínima")
    paragrafo(doc, "O tempo de experiência mínima requerida dos profissionais será de acordo com o quadro abaixo.")
    quadro_perfis(doc, dados["perfis"], com_proporcao=False)
    escrever_blocos(doc, TRECHOS["tr"]["formacao"])
    subtitulo(doc, "3.1.8 Domínio da plataforma")
    paragrafo(
        doc,
        f"Os profissionais disponibilizados pela CONTRATADA deverão possuir domínio nas tecnologias de "
        f"{dados['tecnologia']} informadas no cadastro, não se restringindo somente a estas quando a Ordem de "
        "Serviço exigir competência já prevista no catálogo:",
    )
    paragrafo(doc, _catalogo_texto(dados))

    escrever_blocos(doc, TRECHOS["tr"]["perfis_intro"])
    for item, lista in agrupar_perfis(dados["perfis"]):
        subtitulo(doc, item)
        for perfil in lista:
            subtitulo(doc, perfil.get("perfil") or "Perfil")
            paragrafo(
                doc,
                f"Atua nos serviços de {dados['tecnologia']} vinculados a {item}. "
                "A descrição abaixo usa somente o catálogo e o perfil cadastrados, para revisão no Word.",
            )
            paragrafo(doc, "Experiência e domínio, conforme o catálogo informado:")
            paragrafo(doc, _catalogo_texto(dados))

    subtitulo(doc, "3.3 Certificações")
    paragrafo(doc, dados["regime_certificacao"])
    if dados["certificacoes"]:
        for certificacao in dados["certificacoes"]:
            paragrafo(doc, certificacao)
    else:
        paragrafo(doc, "Nenhuma certificação foi informada no cadastro.")

    escrever_blocos(doc, TRECHOS["tr"]["ageis"])
    titulo(doc, "4. EXECUÇÃO E ENTREGA DOS SERVIÇOS")
    escrever_blocos(doc, TRECHOS["tr"]["execucao"])

    subtitulo(doc, "Descrição dos serviços por item")
    paragrafo(
        doc,
        "A descrição de cada item reproduz o cadastro. Serviço que não esteja no catálogo não foi acrescentado.",
    )
    for item, lista in agrupar_perfis(dados["perfis"]):
        nomes = ", ".join(p.get("perfil") or "" for p in lista)
        subtitulo(doc, item)
        paragrafo(
            doc,
            f"Prestação de apoio técnico especializado em {dados['tecnologia']} para {item}, "
            f"com os perfis {nomes}. O escopo observado é: {_catalogo_texto(dados)}",
        )

    escrever_blocos(doc, TRECHOS["tr"]["entrega_sla"])
    escrever_blocos(doc, TRECHOS["tr"]["governanca"])

    titulo(doc, "6. ELABORAÇÃO")
    paragrafo(doc, dados["texto_elaboracao"])
    titulo(doc, "7. APROVAÇÃO")
    if dados.get("local_data"):
        paragrafo(doc, dados["local_data"])
    for pessoa in dados["aprovadores"]:
        paragrafo(doc, pessoa["nome"])
        if pessoa.get("matricula"):
            paragrafo(doc, f"Matrícula: {pessoa['matricula']}")
        paragrafo(doc, pessoa.get("cargo") or "")

    doc.save(caminho)
