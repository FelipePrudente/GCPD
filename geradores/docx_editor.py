# -*- coding: utf-8 -*-
"""Converte documentos Word gerados pelo sistema em conteúdo seguro para o editor."""
import base64
import re
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree
from zipfile import ZipFile

import mammoth

TAGS_PERMITIDAS = {
    "a", "blockquote", "br", "caption", "div", "em", "h1", "h2", "h3",
    "h4", "h5", "h6", "hr", "img", "li", "ol", "p", "s", "strong",
    "sub", "sup", "table", "tbody", "td", "tfoot", "th", "thead", "tr",
    "u", "ul",
}
TAGS_VAZIAS = {"br", "hr", "img"}
TAGS_BLOQUEADAS = {"iframe", "object", "script", "style", "svg"}
MIMES_IMAGEM = {"image/bmp", "image/gif", "image/jpeg", "image/png", "image/webp"}
NAMESPACE_WORD = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class _SanitizadorHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.partes = []
        self.abertas = []
        self.bloqueadas = []

    def handle_starttag(self, tag, attrs):
        if self.bloqueadas:
            if tag in TAGS_BLOQUEADAS:
                self.bloqueadas.append(tag)
            return
        if tag in TAGS_BLOQUEADAS:
            self.bloqueadas.append(tag)
            return
        if tag not in TAGS_PERMITIDAS:
            return

        atributos = dict(attrs)
        seguros = {}
        if tag == "a":
            href = atributos.get("href", "")
            esquema = urlparse(href).scheme.lower()
            if esquema in {"http", "https", "mailto"}:
                seguros["href"] = href
        elif tag == "img":
            origem = atributos.get("src", "")
            if re.fullmatch(r"data:image/(?:bmp|gif|jpeg|png|webp);base64,[A-Za-z0-9+/=]+", origem):
                seguros["src"] = origem
            else:
                return
            if atributos.get("alt"):
                seguros["alt"] = atributos["alt"]
        elif tag in {"td", "th"}:
            for chave in ("colspan", "rowspan"):
                valor = atributos.get(chave, "")
                if valor.isdigit() and 1 <= int(valor) <= 100:
                    seguros[chave] = valor
        elif tag in {"h1", "h2", "h3", "h4", "h5", "h6", "li", "p"}:
            alinhamento = atributos.get("align", "").lower()
            if alinhamento in {"center", "left", "right", "justify"}:
                seguros["align"] = alinhamento
            # Classes do editor SEI (ex.: Texto_Justificado) precisam ser preservadas
            classe = (atributos.get("class") or "").strip()
            if classe:
                classes_ok = [
                    parte
                    for parte in re.split(r"\s+", classe)
                    if re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,40}", parte or "")
                ]
                if classes_ok:
                    seguros["class"] = " ".join(classes_ok[:6])

        texto_atributos = "".join(
            f' {chave}="{escape(valor, quote=True)}"'
            for chave, valor in seguros.items()
        )
        self.partes.append(f"<{tag}{texto_atributos}>")
        if tag not in TAGS_VAZIAS:
            self.abertas.append(tag)

    def handle_endtag(self, tag):
        if self.bloqueadas:
            if tag == self.bloqueadas[-1]:
                self.bloqueadas.pop()
            return
        if tag not in self.abertas:
            return
        while self.abertas:
            atual = self.abertas.pop()
            self.partes.append(f"</{atual}>")
            if atual == tag:
                break

    def handle_data(self, data):
        if not self.bloqueadas:
            self.partes.append(escape(data))

    def resultado(self):
        while self.abertas:
            self.partes.append(f"</{self.abertas.pop()}>")
        return "".join(self.partes)


def sanitizar_html(html):
    sanitizador = _SanitizadorHTML()
    sanitizador.feed(str(html or ""))
    sanitizador.close()
    return sanitizador.resultado()


class _AplicadorAlinhamento(HTMLParser):
    def __init__(self, alinhamentos):
        super().__init__(convert_charrefs=False)
        self.alinhamentos = iter(alinhamentos)
        self.partes = []

    def handle_starttag(self, tag, attrs):
        marca = self.get_starttag_text()
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6", "li", "p"}:
            alinhamento = next(self.alinhamentos, None)
            if alinhamento and "align=" not in marca:
                marca = marca[:-1] + f' align="{alinhamento}">'
        self.partes.append(marca)

    def handle_startendtag(self, tag, attrs):
        self.partes.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        self.partes.append(f"</{tag}>")

    def handle_data(self, data):
        self.partes.append(data)

    def handle_entityref(self, name):
        self.partes.append(f"&{name};")

    def handle_charref(self, name):
        self.partes.append(f"&#{name};")

    def resultado(self):
        return "".join(self.partes)


def _alinhamentos_docx(caminho):
    with ZipFile(caminho) as arquivo:
        raiz = ElementTree.fromstring(arquivo.read("word/document.xml"))
    alinhamentos = []
    mapa = {
        "both": "justify",
        "center": "center",
        "end": "right",
        "justify": "justify",
        "left": "left",
        "right": "right",
        "start": "left",
    }
    for paragrafo in raiz.iter(f"{NAMESPACE_WORD}p"):
        propriedades = paragrafo.find(f"{NAMESPACE_WORD}pPr")
        alinhamento = propriedades.find(f"{NAMESPACE_WORD}jc") if propriedades is not None else None
        valor = alinhamento.get(f"{NAMESPACE_WORD}val") if alinhamento is not None else None
        alinhamentos.append(mapa.get(valor))
    return alinhamentos


def converter_docx_para_html(caminho):
    caminho = Path(caminho)

    def imagem_em_data_url(imagem):
        if imagem.content_type not in MIMES_IMAGEM:
            return {}
        with imagem.open() as arquivo_imagem:
            conteudo = arquivo_imagem.read()
        codificado = base64.b64encode(conteudo).decode("ascii")
        return {"src": f"data:{imagem.content_type};base64,{codificado}"}

    with caminho.open("rb") as arquivo:
        resultado = mammoth.convert_to_html(
            arquivo,
            convert_image=mammoth.images.img_element(imagem_em_data_url),
        )
    aplicador = _AplicadorAlinhamento(_alinhamentos_docx(caminho))
    aplicador.feed(resultado.value)
    aplicador.close()
    return {
        "html": sanitizar_html(aplicador.resultado()),
        "avisos": [aviso.message for aviso in resultado.messages],
    }
