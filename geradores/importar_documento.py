# -*- coding: utf-8 -*-
"""Converte Word (.docx) e PDF em HTML editável para o catálogo de documentos."""
from __future__ import annotations

import html
import io
import re
from pathlib import Path

# Aceita {{tag}}, {{ tag }} e variações com espaço interno.
TAG_RE = re.compile(r"\{\{\s*([A-Za-z][A-Za-z0-9_]*)\s*\}\}")


def _esc(texto):
    return html.escape(str(texto or ""), quote=False)


def normalizar_placeholders(html_doc: str) -> str:
    """Padroniza placeholders para {{id}} em minúsculas."""

    def troca(match):
        return "{{" + match.group(1).lower() + "}}"

    return TAG_RE.sub(troca, str(html_doc or ""))


def extrair_ids_tags(html_doc: str) -> list[str]:
    """Retorna ids de tags na ordem da primeira aparição."""
    vistos = []
    for match in TAG_RE.finditer(str(html_doc or "")):
        tid = match.group(1).lower()
        if tid not in vistos:
            vistos.append(tid)
    return vistos


def _rotulo_de_id(tag_id: str) -> str:
    partes = [p for p in str(tag_id or "").split("_") if p]
    if not partes:
        return tag_id
    return " ".join(p.capitalize() for p in partes)


def tags_a_partir_de_ids(ids, grupo="Documento"):
    """Cria tags básicas (tipo texto) a partir dos ids encontrados no Word."""
    from geradores.config_documento import _normalizar_tag

    tags = []
    vistos = set()
    grupo_nome = str(grupo or "Documento").strip() or "Documento"
    for bruto in ids or []:
        tid = str(bruto or "").strip().lower()
        if not tid or tid in vistos:
            continue
        try:
            tag = _normalizar_tag({
                "id": tid,
                "rotulo": _rotulo_de_id(tid),
                "grupo": grupo_nome,
                "tipo": "texto",
                "largura": 4,
                "calculado": False,
            })
        except ValueError:
            continue
        vistos.add(tag["id"])
        tags.append(tag)
    return tags


def _paragrafo_html(texto, estilo=""):
    texto = (texto or "").strip()
    if not texto:
        return ""
    nome = (estilo or "").lower()
    if "heading 1" in nome or nome == "title":
        return f"<h2>{_esc(texto)}</h2>"
    if "heading 2" in nome:
        return f"<h3>{_esc(texto)}</h3>"
    if "heading 3" in nome or "heading 4" in nome:
        return f"<h4>{_esc(texto)}</h4>"
    return f"<p>{_esc(texto)}</p>"


def docx_para_html(dados: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(dados))
    partes = ['<article class="folha-doc">']

    # Percorre o corpo na ordem: parágrafos e tabelas.
    body = doc.element.body
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    for filho in body.iterchildren():
        if filho.tag == qn("w:p"):
            paragrafo = Paragraph(filho, doc)
            bloco = _paragrafo_html(paragrafo.text, paragrafo.style.name if paragrafo.style else "")
            if bloco:
                partes.append(bloco)
        elif filho.tag == qn("w:tbl"):
            tabela = Table(filho, doc)
            partes.append("<table><tbody>")
            for linha in tabela.rows:
                partes.append("<tr>")
                for celula in linha.cells:
                    texto = " ".join(p.text.strip() for p in celula.paragraphs if p.text.strip())
                    partes.append(f"<td>{_esc(texto)}</td>")
                partes.append("</tr>")
            partes.append("</tbody></table>")

    if len(partes) == 1:
        for paragrafo in doc.paragraphs:
            bloco = _paragrafo_html(paragrafo.text, paragrafo.style.name if paragrafo.style else "")
            if bloco:
                partes.append(bloco)

    partes.append("</article>")
    html_doc = "\n".join(partes)
    if not re.search(r"<p>|<h\d|<table", html_doc, re.I):
        raise ValueError("Não foi possível extrair texto do Word enviado.")
    return html_doc


def pdf_para_html(dados: bytes) -> str:
    import fitz  # pymupdf

    documento = fitz.open(stream=dados, filetype="pdf")
    partes = ['<article class="folha-doc">']
    vistos = set()
    for pagina in documento:
        blocos = pagina.get_text("blocks")
        # blocks: (x0, y0, x1, y1, text, block_no, block_type)
        for bloco in sorted(blocos, key=lambda b: (round(b[1], 1), round(b[0], 1))):
            if len(bloco) < 5:
                continue
            texto = str(bloco[4] or "").strip()
            if not texto:
                continue
            chave = re.sub(r"\s+", " ", texto).lower()
            if chave in vistos:
                continue
            vistos.add(chave)
            for trecho in re.split(r"\n{2,}", texto):
                linha = re.sub(r"[ \t]+\n", "\n", trecho).strip()
                if not linha:
                    continue
                # Títulos curtos em caixa alta viram heading.
                compacto = re.sub(r"\s+", " ", linha)
                if len(compacto) <= 80 and compacto == compacto.upper() and any(c.isalpha() for c in compacto):
                    partes.append(f"<h3>{_esc(compacto.title() if compacto.isupper() else compacto)}</h3>")
                else:
                    partes.append(f"<p>{_esc(linha.replace(chr(10), ' '))}</p>")
    documento.close()
    partes.append("</article>")
    html_doc = "\n".join(partes)
    if not re.search(r"<p>|<h\d", html_doc, re.I):
        raise ValueError("Não foi possível extrair texto do PDF enviado.")
    return html_doc


def arquivo_para_html(nome_arquivo: str, dados: bytes) -> str:
    nome = (nome_arquivo or "").lower().strip()
    if nome.endswith(".docx"):
        return docx_para_html(dados)
    if nome.endswith(".pdf"):
        return pdf_para_html(dados)
    if nome.endswith(".doc"):
        raise ValueError("Envie o arquivo em .docx (Word atual) ou PDF.")
    raise ValueError("Formato não suportado. Use .docx ou .pdf.")


def nome_sugerido(nome_arquivo: str) -> str:
    base = Path(nome_arquivo or "Novo documento").stem
    base = re.sub(r"\s+", " ", base).strip() or "Novo documento"
    return base[:120]
