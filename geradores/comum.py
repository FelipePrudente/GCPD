# -*- coding: utf-8 -*-
import json
import re
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

RAIZ = Path(__file__).resolve().parent.parent
TRECHOS = json.loads((RAIZ / "modelos" / "trechos_fixos.json").read_text(encoding="utf-8"))
LOGO = RAIZ / "modelos" / "logo_capa.png"
VERDE_TABELA = "EAF0DD"


def parse_numero(valor):
    texto = str(valor or "").strip().replace(" ", "")
    if not texto:
        return 0
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        texto = texto.replace(",", ".")
    elif texto.count(".") > 1:
        texto = texto.replace(".", "")
    elif texto.count(".") == 1:
        inteiro, frac = texto.split(".")
        if inteiro.isdigit() and frac.isdigit() and len(frac) == 3:
            texto = inteiro + frac
    return int(round(float(texto)))


def formato_inteiro(numero):
    return f"{int(numero):,}".replace(",", ".")


def _ate_999(numero, feminino):
    unidades = ["", "uma" if feminino else "um", "duas" if feminino else "dois",
                "três", "quatro", "cinco", "seis", "sete", "oito", "nove"]
    dezenas = ["", "dez", "vinte", "trinta", "quarenta", "cinquenta",
               "sessenta", "setenta", "oitenta", "noventa"]
    especiais = {
        10: "dez", 11: "onze", 12: "doze", 13: "treze", 14: "quatorze",
        15: "quinze", 16: "dezesseis", 17: "dezessete", 18: "dezoito", 19: "dezenove",
    }
    centenas = ["", "cento",
                "duzentas" if feminino else "duzentos",
                "trezentas" if feminino else "trezentos",
                "quatrocentas" if feminino else "quatrocentos",
                "quinhentas" if feminino else "quinhentos",
                "seiscentas" if feminino else "seiscentos",
                "setecentas" if feminino else "setecentos",
                "oitocentas" if feminino else "oitocentos",
                "novecentas" if feminino else "novecentos"]
    if numero == 0:
        return ""
    if numero == 100:
        return "cem"
    partes = []
    if numero >= 100:
        partes.append(centenas[numero // 100])
        numero %= 100
    if numero >= 20:
        partes.append(dezenas[numero // 10])
        if numero % 10:
            partes.append(unidades[numero % 10])
    elif numero >= 10:
        partes.append(especiais[numero])
    elif numero:
        partes.append(unidades[numero])
    return " e ".join(partes)


def extenso(numero, feminino=True):
    numero = int(numero)
    if numero == 0:
        return "zero"
    partes = []
    milhoes = numero // 1_000_000
    resto = numero % 1_000_000
    milhares = resto // 1000
    unidades = resto % 1000
    if milhoes == 1:
        partes.append("um milhão")
    elif milhoes:
        partes.append(_ate_999(milhoes, False) + " milhões")
    if milhares == 1:
        partes.append("mil")
    elif milhares:
        partes.append(_ate_999(milhares, feminino) + " mil")
    if unidades:
        partes.append(_ate_999(unidades, feminino))
    return " e ".join(partes)


def agrupar_perfis(perfis):
    ordem = []
    grupos = {}
    for perfil in perfis:
        item = (perfil.get("item") or "Item único").strip() or "Item único"
        if item not in grupos:
            ordem.append(item)
            grupos[item] = []
        grupos[item].append(perfil)
    return [(item, grupos[item]) for item in ordem]


def total_horas(perfis):
    return sum(parse_numero(p.get("horas")) for p in perfis)


def total_item(lista):
    return sum(parse_numero(p.get("horas")) for p in lista)


def senioridade(nome):
    texto = nome or ""
    for nivel in ("Sênior", "Senior", "Pleno", "Júnior", "Junior"):
        if re.search(rf"\b{nivel}\b", texto, re.I):
            mapa = {"senior": "Sênior", "sênior": "Sênior", "pleno": "Pleno", "junior": "Júnior", "júnior": "Júnior"}
            return mapa.get(nivel.lower(), nivel)
    return "Não informada"


def cargo_base(nome):
    texto = re.sub(r"\b(Sênior|Senior|Pleno|Júnior|Junior)\b", "", nome or "", flags=re.I)
    return re.sub(r"\s+", " ", texto).strip(" -")


def aplicar_arial(run, tamanho=11, negrito=False, cor=None):
    run.font.name = "Arial"
    run.bold = negrito
    run.font.size = Pt(tamanho)
    if cor is not None:
        run.font.color.rgb = cor
    propriedades = run._element.get_or_add_rPr()
    fontes = propriedades.find(qn("w:rFonts"))
    if fontes is None:
        fontes = OxmlElement("w:rFonts")
        propriedades.append(fontes)
    for atributo in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        fontes.set(qn(atributo), "Arial")


def _codigo_rodape(codigo, versao):
    codigo = (codigo or "").strip()
    versao = (versao or "").strip()
    if versao and versao.lower() not in codigo.lower():
        return f"{codigo} {versao}".strip()
    return codigo


def novo_documento(dados, especie):
    doc = Document()
    secao = doc.sections[0]
    secao.page_width = Cm(21.0)
    secao.page_height = Cm(29.7)
    secao.left_margin = Cm(1.2)
    secao.right_margin = Cm(1.5)
    secao.top_margin = Cm(1.3)
    secao.bottom_margin = Cm(1.4)
    estilo = doc.styles["Normal"]
    estilo.font.name = "Arial"
    estilo.font.size = Pt(10)
    estilo.paragraph_format.space_after = Pt(0)
    secao.header.is_linked_to_previous = False
    secao.header.paragraphs[0].text = ""
    if especie == "relatorio":
        nome = "Relatório de justificativa"
        codigo = _codigo_rodape(dados.get("codigo_relatorio"), dados.get("versao_relatorio"))
    elif especie == "termo":
        nome = "Termo de Referência"
        codigo = _codigo_rodape(dados.get("codigo_termo"), dados.get("versao_termo"))
    else:
        nome = "Pesquisa Salarial de Mercado"
        codigo = ""
    rodape = secao.footer.paragraphs[0]
    rodape.alignment = WD_ALIGN_PARAGRAPH.LEFT
    texto = f"{nome} {codigo}".strip() + "          SEI  / pg. "
    run = rodape.add_run(texto)
    aplicar_arial(run, 10, cor=RGBColor(120, 120, 120))
    campo = rodape.add_run()
    aplicar_arial(campo, 10, cor=RGBColor(120, 120, 120))
    inicio = OxmlElement("w:fldChar")
    inicio.set(qn("w:fldCharType"), "begin")
    instrucao = OxmlElement("w:instrText")
    instrucao.set(qn("xml:space"), "preserve")
    instrucao.text = " PAGE "
    fim = OxmlElement("w:fldChar")
    fim.set(qn("w:fldCharType"), "end")
    campo._r.append(inicio)
    campo._r.append(instrucao)
    campo._r.append(fim)
    return doc


def _bloco(doc, texto, tamanho=10, negrito=False, alinhamento="justify", espaco_antes=0, espaco_depois=0, recuo_primeira=0):
    bloco = doc.add_paragraph()
    alinhamentos = {
        "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
        "center": WD_ALIGN_PARAGRAPH.CENTER,
        "left": WD_ALIGN_PARAGRAPH.LEFT,
    }
    bloco.alignment = alinhamentos[alinhamento]
    bloco.paragraph_format.space_before = Pt(espaco_antes)
    bloco.paragraph_format.space_after = Pt(espaco_depois)
    bloco.paragraph_format.line_spacing = 1.08
    if recuo_primeira:
        bloco.paragraph_format.first_line_indent = Cm(recuo_primeira)
    run = bloco.add_run(texto)
    aplicar_arial(run, tamanho, negrito)
    return bloco


def titulo(doc, texto):
    return _bloco(doc, texto, tamanho=10, negrito=True, alinhamento="left", espaco_antes=10, espaco_depois=2)


def subtitulo(doc, texto):
    return _bloco(doc, texto, tamanho=10, negrito=True, alinhamento="left", espaco_antes=8, espaco_depois=2)


def paragrafo(doc, texto):
    bloco = _bloco(doc, texto, tamanho=10, negrito=False, alinhamento="justify", espaco_antes=2, espaco_depois=6)
    bloco.paragraph_format.first_line_indent = Cm(0.45)
    return bloco


def _fatiar_clausula(texto):
    partes = re.split(r"(?<=[.!;])\s+(?=\d+\.\d+(?:\.\d+)*\s+)", texto)
    return [parte.strip() for parte in partes if parte.strip()]


def escrever_blocos(doc, blocos):
    for bloco in blocos:
        texto = (bloco or "").strip()
        if not texto:
            continue
        for parte in _fatiar_clausula(texto):
            if re.match(r"^\d+(\.\d+)*\.?\s+\S", parte) and len(parte) < 140:
                subtitulo(doc, parte)
            else:
                paragrafo(doc, parte)


def pintar(celula, cor):
    propriedades = celula._tc.get_or_add_tcPr()
    sombra = OxmlElement("w:shd")
    sombra.set(qn("w:fill"), cor)
    sombra.set(qn("w:val"), "clear")
    propriedades.append(sombra)


def _largura_colunas(grade, cabecalho):
    quantidade = len(cabecalho)
    primeiro = cabecalho[0]
    if primeiro == "Fonte":
        larguras = [3.2, 10.6, 4.4]
    elif primeiro.startswith("Perfil"):
        larguras = [10.2, 4.0, 4.0] if quantidade == 3 else [7.6, 3.6, 3.5, 3.5]
    elif primeiro == "Referência":
        larguras = [5.4, 7.6, 5.2]
    elif primeiro == "Indicador":
        larguras = [10.0, 8.2]
    elif quantidade == 7:
        larguras = [3.2, 2.0, 3.4, 2.2, 2.4, 2.6, 2.4]
    elif quantidade == 5:
        larguras = [3.3, 3.3, 2.2, 1.8, 7.6]
    else:
        larguras = [18.2 / quantidade] * quantidade
    grade.autofit = False
    tbl = grade._tbl
    tbl_pr = tbl.tblPr
    tbl_w = tbl_pr.find(qn("w:tblW"))
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:type"), "dxa")
    tbl_w.set(qn("w:w"), str(int(sum(larguras) * 567)))
    grade_xml = tbl.find(qn("w:tblGrid"))
    if grade_xml is None:
        grade_xml = OxmlElement("w:tblGrid")
        tbl.insert(1, grade_xml)
    for filho in list(grade_xml):
        grade_xml.remove(filho)
    for largura in larguras:
        coluna = OxmlElement("w:gridCol")
        coluna.set(qn("w:w"), str(int(largura * 567)))
        grade_xml.append(coluna)
    for linha in grade.rows:
        for celula, largura in zip(linha.cells, larguras):
            celula.width = Cm(largura)


def tabela(doc, cabecalho, linhas):
    grade = doc.add_table(rows=1, cols=len(cabecalho))
    grade.style = "Table Grid"
    for indice, nome in enumerate(cabecalho):
        celula = grade.rows[0].cells[indice]
        celula.text = nome
        pintar(celula, VERDE_TABELA)
        for p in celula.paragraphs:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in p.runs:
                aplicar_arial(run, 9, negrito=True)
    for linha in linhas:
        celulas = grade.add_row().cells
        faixa = bool(linha) and str(linha[0] or "").upper().startswith("ITEM")
        total = bool(linha) and str(linha[0] or "").startswith("Total")
        for indice, valor in enumerate(linha):
            celulas[indice].text = "" if valor is None else str(valor)
            if faixa or total:
                pintar(celulas[indice], VERDE_TABELA)
            for p in celulas[indice].paragraphs:
                if indice > 0:
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                for run in p.runs:
                    aplicar_arial(run, 9, negrito=faixa or total)
    _largura_colunas(grade, cabecalho)
    doc.add_paragraph()
    return grade


def cabecalho_institucional(doc, dados):
    if LOGO.is_file():
        logo = doc.add_paragraph()
        logo.alignment = WD_ALIGN_PARAGRAPH.CENTER
        logo.paragraph_format.space_before = Pt(0)
        logo.paragraph_format.space_after = Pt(2)
        logo.add_run().add_picture(str(LOGO), width=Cm(4))
    _bloco(doc, "Governo do Estado de São Paulo", tamanho=11, negrito=True, alinhamento="center")
    _bloco(doc, "Companhia de Processamento de Dados do Estado de São Paulo", tamanho=11, negrito=True, alinhamento="center", espaco_depois=8)


def capa(doc, tipo, dados, codigo, versao):
    cabecalho_institucional(doc, dados)
    _bloco(doc, tipo, tamanho=12, negrito=True, alinhamento="center", espaco_antes=10, espaco_depois=10)
    _bloco(
        doc,
        "Nº do Processo:",
        tamanho=11,
        negrito=True,
        alinhamento="left",
        espaco_antes=6,
        recuo_primeira=2.5,
    )
    _bloco(
        doc,
        "Interessado:",
        tamanho=11,
        negrito=True,
        alinhamento="left",
        espaco_antes=6,
        recuo_primeira=2.5,
    )
    assunto = (dados.get("assunto") or "").strip() or (
        f"CONTRATAÇÃO DE SERVIÇOS DE APOIO TÉCNICO ESPECIALIZADO EM "
        f"{(dados.get('tecnologia') or '').upper()}"
    )
    _bloco(
        doc,
        f"Assunto: {assunto}",
        tamanho=11,
        negrito=True,
        alinhamento="left",
        espaco_antes=6,
        espaco_depois=18,
        recuo_primeira=2.5,
    )
    _bloco(
        doc,
        "CIA. DE PROCESSAMENTO DE DADOS DO ESTADO DE SÃO PAULO",
        tamanho=11,
        negrito=True,
        alinhamento="left",
        espaco_antes=16,
        espaco_depois=16,
    )
    _bloco(doc, tipo, tamanho=13, alinhamento="center", espaco_antes=12)
    _bloco(doc, f"{codigo} {versao}".strip(), tamanho=13, alinhamento="center", espaco_depois=16)
    _bloco(
        doc,
        assunto.upper(),
        tamanho=13,
        alinhamento="center",
        espaco_antes=14,
        espaco_depois=22,
    )
    _bloco(doc, "DDS - Diretoria de Desenvolvimento de Sistemas", tamanho=11, alinhamento="left", espaco_antes=16)
    _bloco(doc, "SCL – Superintendência de Sistemas Estruturantes", tamanho=11, alinhamento="left")
    _bloco(doc, "GEN - Gerência de Engenharia de Software e Serviços", tamanho=11, alinhamento="left")
    doc.add_page_break()


def abrir_corpo(doc, dados):
    texto = re.sub(r"\s*/\s*", " / ", (dados.get("mes_ano") or "").strip()).upper()
    if texto:
        _bloco(doc, texto, tamanho=13, alinhamento="center", espaco_depois=14)


def quadro_perfis(doc, perfis, com_proporcao):
    cabecalho = ["Perfil técnico", "Experiência mínima (anos)", "Total de horas"]
    if com_proporcao:
        cabecalho.append("Proporção do valor-hora")
    linhas = []
    for item, lista in agrupar_perfis(perfis):
        nome_item = item if str(item).upper().startswith("ITEM") else f"ITEM: {item}"
        faixa = [nome_item, "", formato_inteiro(total_item(lista))]
        if com_proporcao:
            faixa.append("")
        linhas.append(faixa)
        for perfil in lista:
            linha = [
                perfil.get("perfil", ""),
                perfil.get("experiencia", ""),
                formato_inteiro(parse_numero(perfil.get("horas"))),
                ]
            if com_proporcao:
                linha.append(perfil.get("proporcao", ""))
            linhas.append(linha)
    total = ["Total geral", "", formato_inteiro(total_horas(perfis))]
    if com_proporcao:
        total.append("")
    linhas.append(total)
    tabela(doc, cabecalho, linhas)


def _linhas_extras_tabela(valor):
    if isinstance(valor, dict):
        bruto = valor.get("linhas")
        return bruto if isinstance(bruto, list) else []
    if isinstance(valor, list):
        return valor
    return []


def _montar_linhas_quadro_generico(colunas, linhas, agrupar_por="", somar=""):
    colunas = [c for c in (colunas or []) if isinstance(c, dict) and c.get("id")]
    if not colunas:
        return [], []
    ids_visiveis = [c["id"] for c in colunas if c["id"] != agrupar_por]
    if not ids_visiveis:
        ids_visiveis = [c["id"] for c in colunas]
    cabecalho = []
    for col_id in ids_visiveis:
        meta = next((c for c in colunas if c["id"] == col_id), {"rotulo": col_id})
        cabecalho.append(meta.get("rotulo") or col_id)

    registros = [r for r in linhas if isinstance(r, dict)]
    registros = [
        r for r in registros
        if any(str(r.get(c["id"]) or "").strip() for c in colunas)
    ]
    saida = []

    def celulas_registro(reg):
        valores = []
        for col_id in ids_visiveis:
            bruto = reg.get(col_id, "")
            if somar and col_id == somar:
                valores.append(formato_inteiro(parse_numero(bruto)) if str(bruto).strip() else "")
            else:
                valores.append("" if bruto is None else str(bruto))
        return valores

    if agrupar_por:
        ordem = []
        grupos = {}
        for reg in registros:
            chave = str(reg.get(agrupar_por) or "").strip() or "Item único"
            if chave not in grupos:
                grupos[chave] = []
                ordem.append(chave)
            grupos[chave].append(reg)
        for chave in ordem:
            lista = grupos[chave]
            faixa = [""] * len(ids_visiveis)
            faixa[0] = chave if str(chave).upper().startswith("ITEM") else chave
            if somar and somar in ids_visiveis:
                idx = ids_visiveis.index(somar)
                total_grupo = sum(parse_numero(r.get(somar)) for r in lista)
                faixa[idx] = formato_inteiro(total_grupo)
            saida.append(faixa)
            for reg in lista:
                saida.append(celulas_registro(reg))
    else:
        for reg in registros:
            saida.append(celulas_registro(reg))

    if somar and somar in ids_visiveis and registros:
        total = [""] * len(ids_visiveis)
        total[0] = "Total geral"
        idx = ids_visiveis.index(somar)
        total[idx] = formato_inteiro(sum(parse_numero(r.get(somar)) for r in registros))
        saida.append(total)
    return cabecalho, saida


def quadro_generico(doc, colunas, linhas, agrupar_por="", somar=""):
    cabecalho, grade = _montar_linhas_quadro_generico(colunas, linhas, agrupar_por, somar)
    if not cabecalho:
        return None
    if not grade:
        grade = [[""] * len(cabecalho)]
    return tabela(doc, cabecalho, grade)


def inserir_tabelas_extras(doc, dados):
    """Insere no Word as tags do tipo tabela preenchidas em extras."""
    try:
        from geradores.config_documento import carregar_config_rj
    except Exception:
        return
    extras = dados.get("extras") if isinstance(dados.get("extras"), dict) else {}
    if not extras:
        return
    try:
        config = carregar_config_rj()
    except Exception:
        return
    tags = [
        tag for tag in (config.get("tags") or [])
        if tag.get("tipo") == "tabela" and not tag.get("calculado")
    ]
    for tag in tags:
        linhas = _linhas_extras_tabela(extras.get(tag.get("id")))
        if not any(
            isinstance(r, dict) and any(str(v or "").strip() for v in r.values())
            for r in linhas
        ):
            continue
        subtitulo(doc, tag.get("rotulo") or tag.get("id"))
        quadro_generico(
            doc,
            tag.get("colunas") or [],
            linhas,
            agrupar_por=tag.get("agrupar_por") or "",
            somar=tag.get("somar") or "",
        )
