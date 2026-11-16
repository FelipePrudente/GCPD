# -*- coding: utf-8 -*-
"""Gera Word a partir de documentos do catálogo (seções/cards + tags)."""
from __future__ import annotations

import html as html_lib
import re
from html.parser import HTMLParser
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

from geradores.comum import aplicar_arial, novo_documento, quadro_generico, subtitulo

_TAG_RE = re.compile(r"\{\{\s*([a-zA-Z][a-zA-Z0-9_]*)\s*\}\}")


def _tags_por_id(doc_config):
    return {
        str(tag.get("id")): tag
        for tag in ((doc_config or {}).get("tags") or [])
        if isinstance(tag, dict) and tag.get("id")
    }


def _eh_valor_tabela(valor):
    return isinstance(valor, dict) and "linhas" in valor


def _linhas_tabela(valor):
    if isinstance(valor, dict):
        bruto = valor.get("linhas")
        return bruto if isinstance(bruto, list) else []
    if isinstance(valor, list):
        return valor
    return []


def _valor_texto_html(valor):
    """Escapa texto e preserva quebras de linha da IA no HTML do documento."""
    texto = str(valor or "").replace("\r\n", "\n").replace("\r", "\n")
    if not texto.strip():
        return ""
    partes = [html_lib.escape(p.strip()) for p in texto.split("\n") if p.strip()]
    if not partes:
        return ""
    if len(partes) == 1:
        return partes[0]
    return "".join(f"<p>{p}</p>" for p in partes)


def _mapa_valores(dados, tags_tabela=None):
    tags_tabela = set(tags_tabela or [])
    mapa = {}
    for chave, valor in (dados or {}).items():
        if chave == "extras":
            continue
        if isinstance(valor, (str, int, float)):
            mapa[chave] = _valor_texto_html(valor)
    extras = dados.get("extras") if isinstance(dados.get("extras"), dict) else {}
    for chave, valor in extras.items():
        if chave in tags_tabela or _eh_valor_tabela(valor):
            # Tabelas ficam como {{tag}} para inserção estruturada no Word.
            continue
        if isinstance(valor, (list, dict)):
            mapa[chave] = html_lib.escape(str(valor))
        else:
            mapa[chave] = _valor_texto_html(valor)
    return mapa


def _substituir_tags(texto, mapa):
    def troca(match):
        chave = match.group(1)
        if chave in mapa:
            return mapa[chave]
        return match.group(0)

    return _TAG_RE.sub(troca, str(texto or ""))


def _inserir_tabela_tag(doc, tag, valor_extra):
    tag = tag or {}
    colunas = list(tag.get("colunas") or [])
    linhas = _linhas_tabela(valor_extra)
    if not colunas:
        ids = []
        for linha in linhas:
            if not isinstance(linha, dict):
                continue
            for chave in linha:
                if chave not in ids:
                    ids.append(chave)
        colunas = [
            {"id": chave, "rotulo": str(chave).replace("_", " ").upper()}
            for chave in ids
        ]
    if not colunas:
        return
    colunas = [
        {
            **coluna,
            "rotulo": str(coluna.get("rotulo") or coluna.get("id") or "").upper(),
        }
        for coluna in colunas
        if isinstance(coluna, dict)
    ]
    tem_dado = any(
        isinstance(r, dict) and any(str(v or "").strip() for v in r.values())
        for r in linhas
    )
    if not tem_dado:
        linhas = []
    quadro_generico(
        doc,
        colunas,
        linhas,
        agrupar_por=tag.get("agrupar_por") or "",
        somar=tag.get("somar") or "",
    )


def _escrever_html_com_tabelas(doc, html_bruto, dados, tags_mapa):
    extras = dados.get("extras") if isinstance(dados.get("extras"), dict) else {}
    html = str(html_bruto or "")
    pos = 0
    houve_conteudo = False
    for match in _TAG_RE.finditer(html):
        chave = match.group(1)
        tag = tags_mapa.get(chave)
        valor = extras.get(chave)
        eh_tabela = (tag and tag.get("tipo") == "tabela") or _eh_valor_tabela(valor)
        if not eh_tabela:
            continue
        before = html[pos:match.start()]
        if before.strip():
            _escrever_paragrafos_formatados(doc, before)
            houve_conteudo = True
        _inserir_tabela_tag(doc, tag or {"id": chave}, valor)
        houve_conteudo = True
        pos = match.end()
    resto = html[pos:]
    if resto.strip():
        _escrever_paragrafos_formatados(doc, resto)
        houve_conteudo = True
    elif not houve_conteudo and html.strip():
        _escrever_paragrafos_formatados(doc, html)


def _alinhamento_de_attrs(attrs):
    mapa = {str(k).lower(): str(v or "") for k, v in (attrs or [])}
    align = (mapa.get("align") or "").strip().lower()
    estilo = (mapa.get("style") or "").lower()
    if "text-align" in estilo:
        m = re.search(r"text-align\s*:\s*(left|right|center|justify)", estilo)
        if m:
            align = m.group(1)
    if align in {"left", "right", "center", "justify"}:
        return align
    return "left"


class _HtmlFormatParser(HTMLParser):
    """Converte HTML do editor em parágrafos com runs (negrito/itálico/sublinhado/alinhamento)."""

    BLOCO = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr"}
    IGNORAR = {"script", "style", "head", "meta", "link"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.paragrafos = []
        self._runs = []
        self._texto = []
        self._bold = 0
        self._italic = 0
        self._underline = 0
        self._align_stack = ["left"]
        self._span_stack = []  # deltas de formatação por <span>
        self._ignorar = 0

    def _flush_run(self):
        texto = "".join(self._texto)
        self._texto = []
        if not texto:
            return
        self._runs.append({
            "texto": texto,
            "bold": self._bold > 0,
            "italic": self._italic > 0,
            "underline": self._underline > 0,
        })

    def _flush_paragrafo(self, forcar=False):
        self._flush_run()
        if not self._runs and not forcar:
            return
        texto_junto = "".join(r["texto"] for r in self._runs)
        if not texto_junto.strip() and not forcar:
            self._runs = []
            return
        # Compacta espaços internos mantendo quebras intencionais já convertidas.
        runs = []
        for run in self._runs:
            limpo = re.sub(r"[ \t\r\f\v]+", " ", run["texto"])
            if not limpo:
                continue
            runs.append({**run, "texto": limpo})
        if runs:
            # Trim só nas pontas do parágrafo.
            runs[0]["texto"] = runs[0]["texto"].lstrip()
            runs[-1]["texto"] = runs[-1]["texto"].rstrip()
            runs = [r for r in runs if r["texto"]]
        if runs or forcar:
            self.paragrafos.append({
                "align": self._align_stack[-1] if self._align_stack else "left",
                "runs": runs or [{"texto": "", "bold": False, "italic": False, "underline": False}],
            })
        self._runs = []

    def handle_starttag(self, tag, attrs):
        nome = (tag or "").lower()
        if nome in self.IGNORAR:
            self._ignorar += 1
            return
        if self._ignorar:
            return
        if nome in self.BLOCO:
            self._flush_paragrafo()
            self._align_stack.append(_alinhamento_de_attrs(attrs))
            return
        if nome == "br":
            self._texto.append("\n")
            self._flush_run()
            self._flush_paragrafo(forcar=True)
            return
        self._flush_run()
        if nome in {"b", "strong"}:
            self._bold += 1
        elif nome in {"i", "em"}:
            self._italic += 1
        elif nome == "u":
            self._underline += 1
        elif nome == "span":
            estilo = ""
            for k, v in attrs or []:
                if str(k).lower() == "style":
                    estilo = str(v or "").lower()
            delta = {"bold": 0, "italic": 0, "underline": 0}
            if "font-weight" in estilo and ("bold" in estilo or re.search(r"font-weight\s*:\s*[6-9]00", estilo)):
                delta["bold"] = 1
                self._bold += 1
            if "font-style" in estilo and "italic" in estilo:
                delta["italic"] = 1
                self._italic += 1
            if "underline" in estilo:
                delta["underline"] = 1
                self._underline += 1
            self._span_stack.append(delta)

    def handle_endtag(self, tag):
        nome = (tag or "").lower()
        if nome in self.IGNORAR:
            if self._ignorar:
                self._ignorar -= 1
            return
        if self._ignorar:
            return
        if nome in self.BLOCO:
            self._flush_paragrafo()
            if len(self._align_stack) > 1:
                self._align_stack.pop()
            return
        self._flush_run()
        if nome in {"b", "strong"} and self._bold:
            self._bold -= 1
        elif nome in {"i", "em"} and self._italic:
            self._italic -= 1
        elif nome == "u" and self._underline:
            self._underline -= 1
        elif nome == "span" and self._span_stack:
            delta = self._span_stack.pop()
            self._bold = max(0, self._bold - delta["bold"])
            self._italic = max(0, self._italic - delta["italic"])
            self._underline = max(0, self._underline - delta["underline"])

    def handle_data(self, data):
        if self._ignorar or not data:
            return
        self._texto.append(data)

    def close(self):
        self._flush_paragrafo()
        super().close()


def _html_para_paragrafos(html_bruto):
    bruto = str(html_bruto or "").strip()
    if not bruto:
        return [{"align": "left", "runs": [{"texto": "", "bold": False, "italic": False, "underline": False}]}]
    parser = _HtmlFormatParser()
    try:
        parser.feed(bruto)
        parser.close()
    except Exception:
        texto = html_lib.unescape(re.sub(r"<[^>]+>", " ", bruto))
        texto = re.sub(r"\s+", " ", texto).strip()
        return [{"align": "left", "runs": [{"texto": texto, "bold": False, "italic": False, "underline": False}]}]
    return parser.paragrafos or [{"align": "left", "runs": [{"texto": "", "bold": False, "italic": False, "underline": False}]}]


_ALINHAMENTOS = {
    "left": WD_ALIGN_PARAGRAPH.LEFT,
    "right": WD_ALIGN_PARAGRAPH.RIGHT,
    "center": WD_ALIGN_PARAGRAPH.CENTER,
    "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
}


def _escrever_paragrafos_formatados(doc, html_bruto):
    for item in _html_para_paragrafos(html_bruto):
        bloco = doc.add_paragraph()
        bloco.alignment = _ALINHAMENTOS.get(item.get("align") or "left", WD_ALIGN_PARAGRAPH.LEFT)
        bloco.paragraph_format.space_before = Pt(2)
        bloco.paragraph_format.space_after = Pt(6)
        bloco.paragraph_format.line_spacing = 1.08
        runs = item.get("runs") or []
        if not runs:
            run = bloco.add_run("")
            aplicar_arial(run, 10, False)
            continue
        for trecho in runs:
            texto = str(trecho.get("texto") or "")
            # Quebras internas viram runs separados com break.
            partes = texto.split("\n")
            for idx, parte in enumerate(partes):
                if idx:
                    bloco.add_run().add_break()
                if not parte and idx < len(partes) - 1:
                    continue
                run = bloco.add_run(parte)
                aplicar_arial(run, 10, bool(trecho.get("bold")))
                run.italic = bool(trecho.get("italic"))
                run.underline = bool(trecho.get("underline"))


def _html_tabela_catalogo(tag, valor):
    """Tabela no formato simples aceito pelo editor de seções do SEI."""
    colunas = [
        coluna for coluna in (tag or {}).get("colunas") or []
        if isinstance(coluna, dict) and coluna.get("id")
    ]
    if not colunas:
        return ""
    linhas = _linhas_tabela(valor)
    cabecalho = "".join(
        '<td style="background-color:#d6e3bc; border:1px solid #000000; '
        'text-align:center; font-weight:bold;"><strong>'
        f"{html_lib.escape(str(coluna.get('rotulo') or coluna['id']))}</strong></td>"
        for coluna in colunas
    )
    corpo = []
    for linha in linhas:
        if not isinstance(linha, dict):
            continue
        celulas = "".join(
            '<td style="border:1px solid #000000; vertical-align:top;">'
            f"{html_lib.escape(str(linha.get(coluna['id']) or ''))}</td>"
            for coluna in colunas
        )
        if any(str(linha.get(coluna["id"]) or "").strip() for coluna in colunas):
            corpo.append(f"<tr>{celulas}</tr>")
    return (
        '<table border="1" cellpadding="4" cellspacing="0" '
        'style="border-collapse:collapse; width:100%; border:1px solid #000000;">'
        f"<tbody><tr>{cabecalho}</tr>{''.join(corpo)}</tbody>"
        "</table>"
    )


def gerar_documento_catalogo_html(dados, doc_config):
    """Renderiza o documento do catálogo como HTML para prévia e inclusão no SEI."""
    doc_config = doc_config or {}
    tags_mapa = _tags_por_id(doc_config)
    extras = dados.get("extras") if isinstance(dados.get("extras"), dict) else {}
    html_documento = str(doc_config.get("documento") or "")
    for tag_id, tag in tags_mapa.items():
        if tag.get("tipo") != "tabela":
            continue
        valor = extras.get(tag_id)
        tabela_html = _html_tabela_catalogo(tag, valor)
        html_documento = re.sub(
            rf"\{{\{{\s*{re.escape(tag_id)}\s*\}}\}}",
            lambda _: tabela_html,
            html_documento,
        )
    mapa = _mapa_valores(dados, {
        tag_id for tag_id, tag in tags_mapa.items() if tag.get("tipo") == "tabela"
    })
    html_documento = _substituir_tags(html_documento, mapa)
    for tag_id, tag in tags_mapa.items():
        if tag.get("calculado"):
            html_documento = re.sub(
                rf"\{{\{{\s*{re.escape(tag_id)}\s*\}}\}}",
                "",
                html_documento,
            )
    # Para a prévia na UI ainda mostra o título; o envio ao SEI normaliza via
    # html_para_secao_sei (sem <h1>, com classes do editor SEI).
    titulo = html_lib.escape(str(doc_config.get("nome") or "Documento"))
    return f"<h1>{titulo}</h1>{html_documento}"


def normalizar_caracteres_para_sei(texto):
    """
    Troca caracteres tipográficos (Word/IA/navegador) por equivalentes ASCII/Latin-1
    seguros para a API do SEI.

    O SEI de homologação já rejeitou hífens Unicode (en dash U+2013 etc.) no payload;
    por isso todas as variantes de traço viram hífen ASCII U+002D.
    Também remove controles e caracteres fora de Latin-1 que costumam corromper a seção.

    Ex.: "SCL – Superintendência" → "SCL - Superintendência"
    """
    if not texto:
        return ""
    # Entidades tipográficas que às vezes chegam literais no HTML do catálogo.
    bruto = str(texto)
    entidades = (
        ("&ndash;", "-"),
        ("&mdash;", "-"),
        ("&minus;", "-"),
        ("&#8211;", "-"),
        ("&#x2013;", "-"),
        ("&#X2013;", "-"),
        ("&#8212;", "-"),
        ("&#x2014;", "-"),
        ("&#X2014;", "-"),
        ("&nbsp;", " "),
        ("&hellip;", "..."),
        ("&lsquo;", "'"),
        ("&rsquo;", "'"),
        ("&ldquo;", '"'),
        ("&rdquo;", '"'),
    )
    for origem, destino in entidades:
        bruto = bruto.replace(origem, destino)

    mapa = {
        # Hífens / traços (todas → ASCII '-')
        "\u2010": "-",   # ‐ hyphen
        "\u2011": "-",   # ‑ non-breaking hyphen
        "\u2012": "-",   # ‒ figure dash
        "\u2013": "-",   # – en dash
        "\u2014": "-",   # — em dash
        "\u2015": "-",   # ― horizontal bar
        "\u2212": "-",   # − minus sign
        "\uFE58": "-",   # ﹘ small em dash
        "\uFE63": "-",   # ﹣ small hyphen-minus
        "\uFF0D": "-",   # － fullwidth hyphen-minus
        "\u2E3A": "-",   # ⸺ two-em dash
        "\u2E3B": "-",   # ⸻ three-em dash
        # Aspas
        "\u2018": "'",   # ‘
        "\u2019": "'",   # ’
        "\u201a": "'",   # ‚
        "\u201b": "'",   # ‛
        "\u2032": "'",   # ′
        "\u201c": '"',   # “
        "\u201d": '"',   # ”
        "\u201e": '"',   # „
        "\u201f": '"',   # ‟
        "\u2033": '"',   # ″
        # Espaços / invisíveis
        "\u00a0": " ",   # non-breaking space
        "\u202f": " ",   # narrow no-break space
        "\u2007": " ",   # figure space
        "\u2008": " ",   # punctuation space
        "\u2009": " ",   # thin space
        "\u200a": " ",   # hair space
        "\u200b": "",    # zero-width space
        "\u200c": "",    # ZWNJ
        "\u200d": "",    # ZWJ
        "\u2060": "",    # word joiner
        "\ufeff": "",    # BOM
        "\u00ad": "",    # soft hyphen
        # Outros tipográficos comuns
        "\u2026": "...", # …
        "\u2022": "-",   # • bullet
        "\u00b7": "-",   # · middle dot
        "\u2192": "->",  # →
        "\u2190": "<-",  # ←
        "\u00d7": "x",   # ×
    }
    saida = []
    for ch in bruto:
        if ch in mapa:
            saida.append(mapa[ch])
            continue
        codigo = ord(ch)
        # Controles (exceto \n \r \t)
        if codigo < 32 and ch not in "\n\r\t":
            continue
        # Latin-1 (ISO-8859-1) cobre PT-BR; fora disso o SEI costuma falhar/corromper.
        if codigo > 255:
            continue
        saida.append(ch)
    return "".join(saida)


def _texto_entidades_sei(texto):
    """
    Codifica texto no estilo do editor SEI: entidades nomeadas para acentos
    (&oacute;, &ccedil;, &nbsp;…) e escape de & < >.
    """
    mapa = html_lib.entities.codepoint2name
    partes = []
    for ch in str(texto or ""):
        codigo = ord(ch)
        if ch == "&":
            partes.append("&amp;")
        elif ch == "<":
            partes.append("&lt;")
        elif ch == ">":
            partes.append("&gt;")
        elif ch == '"':
            partes.append("&quot;")
        elif ch == "\xa0":
            partes.append("&nbsp;")
        elif codigo > 127:
            nome = mapa.get(codigo)
            if nome:
                partes.append(f"&{nome};")
            else:
                partes.append(f"&#{codigo};")
        else:
            partes.append(ch)
    return "".join(partes)


def _alinhamento_de_string_attrs(attrs_html):
    """Extrai alinhamento de uma string de atributos HTML bruta."""
    attrs = []
    for nome, valor in re.findall(
        r'([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*"([^"]*)"', attrs_html or ""
    ):
        attrs.append((nome, valor))
    for nome, valor in re.findall(
        r"([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*'([^']*)'", attrs_html or ""
    ):
        attrs.append((nome, valor))
    return _alinhamento_de_attrs(attrs)


def _tag_abertura_paragrafo_sei(alinhamento="left", negrito=False):
    """Abre <p> no estilo do editor SEI, preservando centro/direita quando houver."""
    alinhamento = (alinhamento or "left").lower()
    if alinhamento == "center":
        abertura = '<p class="Texto_Centralizado" align="center" style="text-align:center;">'
    elif alinhamento == "right":
        abertura = (
            '<p class="Texto_Alinhado_Direita" align="right" '
            'style="text-align:right;">'
        )
    else:
        abertura = '<p class="Texto_Justificado">'
    if negrito:
        abertura += "<strong>"
    return abertura


def _preparar_html_catalogo_para_sei(html):
    """
    Normaliza o HTML do editor de Configurações antes do parser SEI.

    O contenteditable grava cada linha como <div> (muitas vezes com
    text-align:center). Remover o <div> sem virar <p> cola as linhas
    (ex.: PauloCompanhia). Aqui div → p preservando o alinhamento.
    """
    html = str(html or "")

    def _abrir_como_p(match):
        return _tag_abertura_paragrafo_sei(_alinhamento_de_string_attrs(match.group(1) or ""))

    # Divs do editor → parágrafos (preserva centro/direita).
    html = re.sub(r"(?is)<div\b([^>]*)>", _abrir_como_p, html)
    html = re.sub(r"(?is)</div>", "</p>", html)

    # Wrappers sem valor tipográfico: só remove a tag, mantém o miolo.
    html = re.sub(
        r"(?is)</?(html|body|article|section|header|footer|main)\b[^>]*>",
        "",
        html,
    )
    return html


def html_para_secao_sei(html_bruto):
    """
    Converte HTML do catálogo/Word para o subset que o SEI grava de fato.

    Formato aceito pelo editor de seções (homologação PRODESP):
    - <p class="Texto_Justificado|Texto_Centralizado">…</p> separados por \\r\\n\\r\\n
    - acentos como entidades (&oacute;, &ccedil;…)
    - <strong>, <em>, <u>, <br />
    - <ul>/<ol>/<li> e tabelas border=1 cellpadding=1 cellspacing=1
    - sem DOCTYPE / html / head / body / h1 de capa
    - preserva alinhamento (centro/direita) vindo do editor de Configurações
    """
    html = str(html_bruto or "").strip()
    if not html:
        return ""

    # 1) Limpa documento completo / metadados
    html = re.sub(r"(?is)<!DOCTYPE[^>]*>", "", html)
    html = re.sub(r"(?is)<head\b[^>]*>.*?</head>", "", html)
    html = re.sub(r"(?is)<script\b[^>]*>.*?</script>", "", html)
    html = re.sub(r"(?is)<style\b[^>]*>.*?</style>", "", html)
    # Divs do contenteditable → <p> (não apagar: cola linhas)
    html = _preparar_html_catalogo_para_sei(html)
    # Título do formulário — no SEI já existe seção só-leitura com o título
    html = re.sub(r"(?is)<h1\b[^>]*>.*?</h1>", "", html, count=1)
    # <hr> não existe no subset do SEI
    html = re.sub(r"(?is)<hr\b[^>]*/?>", "", html)

    class _ConversorSEI(HTMLParser):
        PERMITIDAS = {
            "p", "strong", "em", "b", "i", "u", "br", "span",
            "ul", "ol", "li",
            "table", "thead", "tbody", "tfoot", "tr", "th", "td",
            "h2", "h3", "h4", "h5", "h6",
        }

        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.partes = []
            self.abertas = []
            self.bloqueadas = []
            self._em_celula = False
            self._em_bloco = False
            self._texto_solto = []

        def _flush_texto_solto(self):
            if self._em_bloco or self._em_celula:
                return
            bruto = "".join(self._texto_solto)
            self._texto_solto = []
            # Cada linha solta vira um parágrafo (não colar tudo numa linha).
            for linha in re.split(r"[\r\n]+", bruto):
                limpo = " ".join(linha.split()).strip()
                if limpo:
                    self.partes.append(
                        f'{_tag_abertura_paragrafo_sei("left")}'
                        f"{_texto_entidades_sei(limpo)}</p>"
                    )

        def handle_starttag(self, tag, attrs):
            tag = tag.lower()
            if self.bloqueadas:
                if tag in {"script", "style"}:
                    self.bloqueadas.append(tag)
                return
            if tag in {"script", "style"}:
                self.bloqueadas.append(tag)
                return
            if tag not in self.PERMITIDAS:
                return

            self._flush_texto_solto()
            attrs_map = {str(k).lower(): str(v or "") for k, v in (attrs or [])}
            alinhamento = _alinhamento_de_attrs(attrs)

            if tag in {"h2", "h3", "h4", "h5", "h6"}:
                # Títulos centralizados no modelo viram parágrafo centralizado.
                self.partes.append(
                    _tag_abertura_paragrafo_sei(alinhamento, negrito=True)
                )
                self.abertas.append(("h", tag))
                self._em_bloco = True
                return

            if tag == "p":
                self.partes.append(_tag_abertura_paragrafo_sei(alinhamento))
                self.abertas.append(("p", tag))
                self._em_bloco = True
                return

            if tag == "span":
                estilo = attrs_map.get("style", "").strip()
                classe = attrs_map.get("class", "").strip().lower()
                # Tags do editor ({{campo}}) — só o texto, sem o span.
                if "tag" in classe.split():
                    self.abertas.append(("span_skip", tag))
                    return
                # Só preserva estilos simples usados no template SEI (cor).
                if estilo and re.fullmatch(
                    r"(?i)\s*color\s*:\s*#[0-9a-f]{3,8}\s*;?\s*", estilo
                ):
                    cor = re.search(r"(?i)#[0-9a-f]{3,8}", estilo)
                    if cor:
                        self.partes.append(
                            f'<span style="color:{cor.group(0).lower()};">'
                        )
                        self.abertas.append(("span", tag))
                        return
                self.abertas.append(("span_skip", tag))
                return

            if tag == "table":
                self.partes.append(
                    '<table border="1" cellpadding="1" cellspacing="1" '
                    'style="width: 810px;">'
                )
                self.abertas.append(("table", tag))
                self._em_bloco = True
                return

            if tag == "th":
                self.partes.append(
                    '<td style="background-color:#d6e3bc; text-align:center;">'
                    "<strong>"
                )
                self.abertas.append(("th", tag))
                self._em_celula = True
                return

            if tag == "td":
                self.partes.append("<td>")
                self.abertas.append(("td", tag))
                self._em_celula = True
                return

            if tag == "br":
                self.partes.append("<br />")
                return

            if tag in {"b"}:
                self.partes.append("<strong>")
                self.abertas.append(("strong", tag))
                return
            if tag in {"i"}:
                self.partes.append("<em>")
                self.abertas.append(("em", tag))
                return

            self.partes.append(f"<{tag}>")
            self.abertas.append((tag, tag))
            if tag in {"ul", "ol", "li", "tr", "thead", "tbody", "tfoot"}:
                self._em_bloco = True

        def handle_endtag(self, tag):
            tag = tag.lower()
            if self.bloqueadas:
                if self.bloqueadas[-1] == tag:
                    self.bloqueadas.pop()
                return
            if tag not in self.PERMITIDAS:
                return
            if tag == "br":
                return
            if not self.abertas:
                return

            while self.abertas:
                tipo, origem = self.abertas.pop()
                if tipo == "h":
                    self.partes.append("</strong></p>")
                    self._em_bloco = False
                elif tipo == "th":
                    self.partes.append("</strong></td>")
                    self._em_celula = False
                elif tipo == "p":
                    self.partes.append("</p>")
                    self._em_bloco = False
                elif tipo == "span_skip":
                    pass
                elif tipo == "span":
                    self.partes.append("</span>")
                elif tipo in {"strong", "em"} and origem in {"b", "i", tag}:
                    self.partes.append(f"</{tipo}>")
                else:
                    self.partes.append(f"</{tipo}>")
                    if tipo in {"table", "ul", "ol"}:
                        self._em_bloco = False
                    if tipo in {"th", "td"}:
                        self._em_celula = False
                if (
                    tipo == tag
                    or (tipo == "h" and tag.startswith("h"))
                    or (tipo == "strong" and tag == "b")
                    or (tipo == "em" and tag == "i")
                    or (tipo == "span_skip" and tag == "span")
                ):
                    break

        def handle_data(self, data):
            if self.bloqueadas:
                return
            texto = normalizar_caracteres_para_sei(data)
            if not texto:
                return
            # Preserva quebras de linha; só colapsa espaços horizontais.
            texto = re.sub(r"[ \t]+", " ", texto)
            if not self._em_bloco and not self._em_celula and not self.abertas:
                self._texto_solto.append(texto)
                return
            # Dentro de parágrafo: newline do editor → <br />
            if "\n" in texto and self._em_bloco:
                pedacos = re.split(r"\r?\n", texto)
                for i, pedaco in enumerate(pedacos):
                    if i:
                        self.partes.append("<br />")
                    pedaco = pedaco.strip() if i not in (0, len(pedacos) - 1) else pedaco
                    if pedaco:
                        self.partes.append(_texto_entidades_sei(pedaco))
                return
            self.partes.append(_texto_entidades_sei(texto))

        def resultado(self):
            self._flush_texto_solto()
            while self.abertas:
                tipo, _ = self.abertas.pop()
                if tipo == "h":
                    self.partes.append("</strong></p>")
                elif tipo == "th":
                    self.partes.append("</strong></td>")
                elif tipo == "p":
                    self.partes.append("</p>")
                elif tipo == "span":
                    self.partes.append("</span>")
                elif tipo == "span_skip":
                    pass
                else:
                    self.partes.append(f"</{tipo}>")
            bruto = "".join(self.partes)
            # Linhas em branco do editor (div/p vazios ou só <br>) → &nbsp;
            # para o SEI manter o espaçamento vertical do modelo.
            def _paragrafo_espaco(match):
                abertura = match.group(1)
                # Cada <br> extra no mesmo bloco vira um parágrafo em branco a mais.
                qtd_br = len(re.findall(r"(?i)<br\s*/?>", match.group(0)))
                qtd = max(1, qtd_br)
                return "".join(f"{abertura}&nbsp;</p>" for _ in range(qtd))

            bruto = re.sub(
                r'(?is)(<p class="Texto_(?:Justificado|Centralizado|Alinhado_Direita)"[^>]*>)'
                r"(?:\s|&nbsp;|<br\s*/?>)*"
                r"</p>",
                _paragrafo_espaco,
                bruto,
            )
            # Blocos separados como no conteúdo nativo do SEI
            bruto = re.sub(r"</p>\s*<p ", "</p>\r\n\r\n<p ", bruto)
            bruto = re.sub(r"</p>\s*<table", "</p>\r\n\r\n<table", bruto)
            bruto = re.sub(r"</table>\s*<p ", "</table>\r\n\r\n<p ", bruto)
            bruto = re.sub(r"</ul>\s*<p ", "</ul>\r\n\r\n<p ", bruto)
            bruto = re.sub(r"</ol>\s*<p ", "</ol>\r\n\r\n<p ", bruto)
            return bruto.strip()

    # Pré-normaliza tipografia Word no HTML bruto (hífens/aspas), sem
    # tocar em tags ASCII.
    html = normalizar_caracteres_para_sei(html)

    parser = _ConversorSEI()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        return _fallback_paragrafos(html)
    saida = parser.resultado()
    if not saida:
        return _fallback_paragrafos(html)
    return saida


def _fallback_paragrafos(html_bruto):
    """Fallback quando o parser falha: só texto normalizado em parágrafos."""
    texto = re.sub(r"(?is)<[^>]+>", "\n", str(html_bruto or ""))
    texto = html_lib.unescape(texto)
    texto = normalizar_caracteres_para_sei(texto)
    paragrafos = []
    for linha in texto.split("\n"):
        limpa = " ".join(linha.split()).strip()
        if limpa:
            paragrafos.append(
                f'{_tag_abertura_paragrafo_sei("left")}'
                f"{_texto_entidades_sei(limpa)}</p>"
            )
    return "\r\n\r\n".join(paragrafos)


def gerar_documento_catalogo(dados, doc_config, caminho):
    """Monta um .docx a partir das seções do documento do catálogo."""
    tags_mapa = _tags_por_id(doc_config)
    tags_tabela = {
        tid for tid, tag in tags_mapa.items() if tag.get("tipo") == "tabela"
    }
    mapa = _mapa_valores(dados, tags_tabela)
    nome = str((doc_config or {}).get("nome") or "Documento")
    # Reusa margens/estilo base do pacote quando possível.
    try:
        doc = novo_documento(dados, "catalogo")
    except Exception:
        doc = Document()
        for secao in doc.sections:
            secao.top_margin = Pt(72)
            secao.bottom_margin = Pt(72)

    titulo = doc.add_paragraph()
    titulo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = titulo.add_run(nome.upper())
    aplicar_arial(run, 14, negrito=True)

    secoes = (doc_config or {}).get("secoes") or []
    if not secoes:
        html_doc = _substituir_tags((doc_config or {}).get("documento") or "", mapa)
        _escrever_html_com_tabelas(doc, html_doc, dados, tags_mapa)
    else:
        for secao in secoes:
            grupo = str(secao.get("grupo") or "").strip() or "Seção"
            subtitulo(doc, grupo)
            html_sec = _substituir_tags(secao.get("html") or "", mapa)
            _escrever_html_com_tabelas(doc, html_sec, dados, tags_mapa)

    Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(caminho))
    return caminho
