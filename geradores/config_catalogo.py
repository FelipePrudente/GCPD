# -*- coding: utf-8 -*-
"""Catálogo de documentos editáveis (tags vinculadas a cada documento)."""
from __future__ import annotations

import html
import json
import re
import time
from pathlib import Path

from geradores.config_documento import (
    ARQUIVO as ARQUIVO_RJ,
    DOCUMENTO_PADRAO,
    TAGS_PADRAO,
    _normalizar_config,
    _normalizar_id,
    _normalizar_tag,
)
from geradores.importar_documento import (
    arquivo_para_html,
    extrair_ids_tags,
    nome_sugerido,
    normalizar_placeholders,
    tags_a_partir_de_ids,
)

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO = RAIZ / "modelos" / "config_catalogo.json"
PASTA_ORIGENS = RAIZ / "modelos" / "documentos_origem"

ID_RJ = "relatorio_justificativa"


def _slug_documento(valor, usados=None):
    usados = usados or set()
    base = _normalizar_id(valor)
    candidato = base
    n = 2
    while candidato in usados:
        candidato = f"{base}_{n}"
        n += 1
    usados.add(candidato)
    return candidato


def _normalizar_tags_lista(bruto, permitir_vazio=True):
    if bruto is None:
        return []
    if not isinstance(bruto, list):
        raise ValueError("Lista de tags inválida.")
    if not bruto:
        if permitir_vazio:
            return []
        raise ValueError("Informe ao menos uma tag.")
    tags = []
    vistos = set()
    for item in bruto:
        tag = _normalizar_tag(item)
        if tag["id"] in vistos:
            raise ValueError(f"Tag duplicada: {tag['id']}")
        vistos.add(tag["id"])
        tags.append(tag)
    return tags


def _grupos_de_tags(tags):
    ordem = []
    for tag in tags or []:
        grupo = str((tag or {}).get("grupo") or "").strip()
        if grupo and grupo not in ordem:
            ordem.append(grupo)
    return ordem


def _normalizar_grupos(bruto, tags=None):
    grupos = []
    if isinstance(bruto, list):
        for item in bruto:
            nome = str(item or "").strip()
            if nome and nome not in grupos:
                grupos.append(nome[:80])
    # Garante que grupos usados pelas tags existam na lista.
    for grupo in _grupos_de_tags(tags):
        if grupo not in grupos:
            grupos.append(grupo)
    return grupos


def _corpo_html_legado(documento):
    texto = str(documento or "").strip()
    if not texto:
        return "<p></p>"
    # Se já for article, usa o miolo; senão mantém o HTML.
    m = re.search(r"<article[^>]*>([\s\S]*)</article>", texto, re.I)
    if m:
        miolo = m.group(1).strip()
        return miolo or "<p></p>"
    return texto


def _montar_documento_de_secoes(secoes):
    partes = ['<article class="folha-doc">']
    for secao in secoes or []:
        grupo = str(secao.get("grupo") or "").strip()
        if not grupo:
            continue
        corpo = str(secao.get("html") or "").strip() or "<p></p>"
        partes.append(
            f'<section class="card-bloco" data-grupo="{html.escape(grupo, quote=True)}">'
            f'<header class="card-bloco-cabecalho"><h3>{html.escape(grupo)}</h3></header>'
            f'<div class="card-bloco-corpo">{corpo}</div>'
            f"</section>"
        )
    partes.append("</article>")
    return "\n".join(partes)


def _sincronizar_secoes(grupos, secoes_brutas=None, documento_legado=""):
    mapa = {}
    if isinstance(secoes_brutas, list):
        for item in secoes_brutas:
            if not isinstance(item, dict):
                continue
            nome = str(item.get("grupo") or "").strip()
            if not nome or nome in mapa:
                continue
            mapa[nome] = str(item.get("html") or "").strip() or "<p></p>"
    secoes = []
    legado_usado = False
    for indice, grupo in enumerate(grupos or []):
        if grupo in mapa:
            html_sec = mapa[grupo]
        elif not mapa and not legado_usado and documento_legado.strip():
            html_sec = _corpo_html_legado(documento_legado)
            legado_usado = True
        else:
            html_sec = "<p></p>"
        secoes.append({"grupo": grupo, "html": html_sec})
    return secoes


def _doc_padrao_rj(documento=None, tags=None):
    lista_tags = list(tags if tags is not None else [dict(t) for t in TAGS_PADRAO])
    grupos = _grupos_de_tags(lista_tags)
    doc_html = str(documento or DOCUMENTO_PADRAO).strip() or DOCUMENTO_PADRAO
    secoes = _sincronizar_secoes(grupos, None, doc_html)
    return {
        "id": ID_RJ,
        "nome": "Relatório de Justificativa",
        "documento": _montar_documento_de_secoes(secoes) if secoes else doc_html,
        "tags": lista_tags,
        "grupos": grupos,
        "secoes": secoes,
        "origem": "nativo",
        "arquivo_origem": "",
        "atualizado_em": int(time.time()),
    }


def _padrao():
    return {
        "documentos": [_doc_padrao_rj()],
        "ativo": ID_RJ,
    }


def _normalizar_documento(bruto, usados, tags_legado=None):
    if not isinstance(bruto, dict):
        raise ValueError("Documento inválido.")
    nome = str(bruto.get("nome") or "").strip() or "Documento"
    doc_id = str(bruto.get("id") or "").strip().lower()
    if doc_id:
        try:
            doc_id = _normalizar_id(doc_id)
        except ValueError:
            doc_id = _slug_documento(nome, usados)
        if doc_id in usados:
            doc_id = _slug_documento(doc_id, usados)
        else:
            usados.add(doc_id)
    else:
        doc_id = _slug_documento(nome, usados)
    documento = str(bruto.get("documento") or "").strip()
    if not documento:
        raise ValueError(f"O documento “{nome}” está vazio.")

    if "tags" in bruto:
        tags = _normalizar_tags_lista(bruto.get("tags"), permitir_vazio=True)
    elif tags_legado is not None and doc_id == ID_RJ:
        tags = _normalizar_tags_lista(tags_legado, permitir_vazio=True)
    else:
        # Documento novo / sem tags próprias.
        tags = []

    if "grupos" in bruto:
        grupos = _normalizar_grupos(bruto.get("grupos"), tags)
    else:
        # Migração: deriva dos grupos já usados nas tags (RJ); docs novos ficam vazios.
        grupos = _grupos_de_tags(tags)

    if "secoes" in bruto and isinstance(bruto.get("secoes"), list):
        secoes = _sincronizar_secoes(grupos, bruto.get("secoes"), "")
    else:
        secoes = _sincronizar_secoes(grupos, None, documento)

    if secoes:
        documento = _montar_documento_de_secoes(secoes)

    return {
        "id": doc_id,
        "nome": nome[:160],
        "documento": documento,
        "tags": tags,
        "grupos": grupos,
        "secoes": secoes,
        "origem": str(bruto.get("origem") or "manual").strip() or "manual",
        "arquivo_origem": str(bruto.get("arquivo_origem") or "").strip(),
        "atualizado_em": int(bruto.get("atualizado_em") or time.time()),
    }


def _normalizar_catalogo(bruto):
    if not isinstance(bruto, dict):
        raise ValueError("Catálogo inválido.")

    # Migração: tags na raiz → ficam no RJ; demais docs começam vazios se não tiverem tags.
    tags_raiz = None
    if "tags" in bruto and isinstance(bruto.get("tags"), list):
        tags_raiz = bruto.get("tags")

    docs_brutos = bruto.get("documentos")
    if not isinstance(docs_brutos, list) or not docs_brutos:
        raise ValueError("Informe ao menos um documento.")
    usados = set()
    documentos = [
        _normalizar_documento(item, usados, tags_legado=tags_raiz)
        for item in docs_brutos
    ]
    ativo = str(bruto.get("ativo") or "").strip().lower()
    ids = {d["id"] for d in documentos}
    if ativo not in ids:
        ativo = documentos[0]["id"]
    return {"documentos": documentos, "ativo": ativo}


def _migrar_do_rj():
    if not ARQUIVO_RJ.exists():
        return _padrao()
    try:
        bruto = json.loads(ARQUIVO_RJ.read_text(encoding="utf-8"))
        antigo = _normalizar_config(bruto)
        return {
            "documentos": [_doc_padrao_rj(antigo["documento"], antigo["tags"])],
            "ativo": ID_RJ,
        }
    except Exception:
        return _padrao()


def carregar_catalogo():
    if ARQUIVO.exists():
        try:
            bruto = json.loads(ARQUIVO.read_text(encoding="utf-8"))
            dados = _normalizar_catalogo(bruto)
            # Regrava se ainda estava no formato antigo.
            docs_brutos = bruto.get("documentos") if isinstance(bruto.get("documentos"), list) else []
            precisa_migrar = "tags" in bruto or any(
                not isinstance(doc, dict) or "grupos" not in doc or "secoes" not in doc
                for doc in docs_brutos
            )
            if precisa_migrar:
                salvar_catalogo(dados)
            return dados
        except Exception:
            pass
    dados = _migrar_do_rj()
    salvar_catalogo(dados)
    return dados


def _gravar_json(caminho, dados):
    """Grava JSON de forma atômica (evita arquivo pela metade no OneDrive)."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(caminho.suffix + ".tmp")
    texto = json.dumps(dados, ensure_ascii=False, indent=2) + "\n"
    temporario.write_text(texto, encoding="utf-8")
    temporario.replace(caminho)


def salvar_catalogo(bruto):
    dados = _normalizar_catalogo(bruto)
    _gravar_json(ARQUIVO, dados)
    # Mantém o RJ legado sincronizado para geradores/APIs antigas.
    rj = next((d for d in dados["documentos"] if d["id"] == ID_RJ), dados["documentos"][0])
    legado = {"tags": rj.get("tags") or [], "documento": rj["documento"]}
    _gravar_json(ARQUIVO_RJ, legado)
    return dados


def documento_por_id(catalogo, doc_id):
    return next((d for d in catalogo["documentos"] if d["id"] == doc_id), None)


def tags_do_ativo(catalogo):
    ativo = documento_por_id(catalogo, catalogo.get("ativo")) or catalogo["documentos"][0]
    return list(ativo.get("tags") or [])


def tags_formulario(catalogo):
    """Une tags de todos os documentos (sem duplicar id) para montar o formulário."""
    unidos = []
    vistos = set()
    for doc in catalogo.get("documentos") or []:
        for tag in doc.get("tags") or []:
            tid = tag.get("id")
            if not tid or tid in vistos:
                continue
            vistos.add(tid)
            unidos.append(tag)
    return unidos


def payload_catalogo(catalogo):
    ativo = documento_por_id(catalogo, catalogo.get("ativo")) or catalogo["documentos"][0]
    return {
        "ok": True,
        "tags": list(ativo.get("tags") or []),
        "grupos": list(ativo.get("grupos") or []),
        "tags_formulario": tags_formulario(catalogo),
        "ativo": catalogo["ativo"],
        "documentos": resumo_documentos(catalogo),
        "documento": {
            "id": ativo["id"],
            "nome": ativo["nome"],
            "documento": ativo["documento"],
            "origem": ativo.get("origem") or "",
            "arquivo_origem": ativo.get("arquivo_origem") or "",
            "tags": list(ativo.get("tags") or []),
            "grupos": list(ativo.get("grupos") or []),
            "secoes": list(ativo.get("secoes") or []),
        },
        "secoes": list(ativo.get("secoes") or []),
    }


def resumo_documentos(catalogo):
    return [
        {
            "id": d["id"],
            "nome": d["nome"],
            "origem": d["origem"],
            "arquivo_origem": d.get("arquivo_origem") or "",
            "atualizado_em": d.get("atualizado_em") or 0,
            "ativo": d["id"] == catalogo.get("ativo"),
            "qtd_tags": len(d.get("tags") or []),
            "qtd_grupos": len(d.get("grupos") or []),
            "tags": list(d.get("tags") or []),
            "grupos": list(d.get("grupos") or []),
            "gerador": (
                "relatorio" if d["id"] == ID_RJ
                else "catalogo"
            ),
        }
        for d in catalogo["documentos"]
    ]


def definir_ativo(doc_id):
    cat = carregar_catalogo()
    if not documento_por_id(cat, doc_id):
        raise ValueError("Documento não encontrado.")
    cat["ativo"] = doc_id
    return salvar_catalogo(cat)


def _documento_em_branco(nome, usados=None):
    usados = usados if usados is not None else set()
    nome_limpo = str(nome or "").strip() or "Novo documento"
    doc_id = _slug_documento(nome_limpo, usados)
    titulo = html.escape(nome_limpo[:160])
    return {
        "id": doc_id,
        "nome": nome_limpo[:160],
        "documento": (
            f'<article class="folha-doc">\n'
            f"  <h2>{titulo}</h2>\n"
            f"  <p>Envie um Word tagueado ou defina os grupos/blocos e as tags.</p>\n"
            f"</article>"
        ),
        "tags": [],
        "grupos": [],
        "secoes": [],
        "origem": "manual",
        "arquivo_origem": "",
        "atualizado_em": int(time.time()),
    }


def criar_documento_em_branco(nome):
    cat = carregar_catalogo()
    usados = {d["id"] for d in cat["documentos"]}
    novo = _documento_em_branco(nome, usados)
    cat["documentos"].append(novo)
    cat["ativo"] = novo["id"]
    return salvar_catalogo(cat), novo


def importar_arquivo(nome_arquivo, dados_binarios, nome_documento=""):
    html_doc = normalizar_placeholders(arquivo_para_html(nome_arquivo, dados_binarios))
    ids_tags = extrair_ids_tags(html_doc)
    cat = carregar_catalogo()
    usados = {d["id"] for d in cat["documentos"]}
    nome = str(nome_documento or "").strip() or nome_sugerido(nome_arquivo)
    doc_id = _slug_documento(nome, usados)

    PASTA_ORIGENS.mkdir(parents=True, exist_ok=True)
    extensao = Path(nome_arquivo).suffix.lower() or ".bin"
    destino = PASTA_ORIGENS / f"{doc_id}{extensao}"
    destino.write_bytes(dados_binarios)

    grupo_padrao = "Documento"
    tags = tags_a_partir_de_ids(ids_tags, grupo=grupo_padrao)
    if tags:
        # Word já tagueado: cria grupo + seção com o HTML e as tags do formulário.
        corpo = _corpo_html_legado(html_doc)
        grupos = [grupo_padrao]
        secoes = [{"grupo": grupo_padrao, "html": corpo}]
        documento = _montar_documento_de_secoes(secoes)
    else:
        # Sem placeholders: mantém o HTML bruto até o usuário criar grupos/tags.
        tags = []
        grupos = []
        secoes = []
        documento = html_doc

    novo = {
        "id": doc_id,
        "nome": nome[:160],
        "documento": documento,
        "tags": tags,
        "grupos": grupos,
        "secoes": secoes,
        "origem": "upload",
        "arquivo_origem": destino.name,
        "atualizado_em": int(time.time()),
    }
    cat["documentos"].append(novo)
    cat["ativo"] = doc_id
    return salvar_catalogo(cat), novo, {"qtd_tags": len(tags), "ids_tags": [t["id"] for t in tags]}


def atualizar_documento(doc_id, nome=None, documento=None, tags=None):
    cat = carregar_catalogo()
    alvo = documento_por_id(cat, doc_id)
    if not alvo:
        raise ValueError("Documento não encontrado.")
    if nome is not None:
        nome_limpo = str(nome).strip()
        if not nome_limpo:
            raise ValueError("Informe o nome do documento.")
        alvo["nome"] = nome_limpo[:160]
    if documento is not None:
        texto = str(documento).strip()
        if not texto:
            raise ValueError("O texto do documento não pode ficar vazio.")
        alvo["documento"] = texto
    if tags is not None:
        alvo["tags"] = _normalizar_tags_lista(tags, permitir_vazio=True)
    alvo["atualizado_em"] = int(time.time())
    cat["ativo"] = doc_id
    return salvar_catalogo(cat)


def excluir_documento(doc_id):
    cat, _removidos = excluir_documentos([doc_id])
    return cat


def excluir_documentos(ids):
    """Remove um ou mais documentos do catálogo. Sempre mantém ao menos um (em branco se preciso)."""
    cat = carregar_catalogo()
    brutos = ids if isinstance(ids, (list, tuple, set)) else [ids]
    pedidos = []
    vistos = set()
    for bruto in brutos:
        doc_id = str(bruto or "").strip().lower()
        if not doc_id or doc_id in vistos:
            continue
        vistos.add(doc_id)
        pedidos.append(doc_id)
    if not pedidos:
        raise ValueError("Selecione ao menos um documento para excluir.")

    removidos = []
    restantes = []
    for doc in cat["documentos"]:
        if doc["id"] in vistos:
            removidos.append(doc)
        else:
            restantes.append(doc)
    if not removidos:
        raise ValueError("Nenhum dos documentos selecionados foi encontrado.")

    cat["documentos"] = restantes
    if not cat["documentos"]:
        novo = _documento_em_branco("Novo documento", set())
        cat["documentos"] = [novo]
        cat["ativo"] = novo["id"]
    elif cat.get("ativo") not in {d["id"] for d in cat["documentos"]}:
        cat["ativo"] = cat["documentos"][0]["id"]

    for removido in removidos:
        if removido.get("arquivo_origem"):
            caminho = PASTA_ORIGENS / removido["arquivo_origem"]
            if caminho.is_file():
                try:
                    caminho.unlink()
                except OSError:
                    pass
    return salvar_catalogo(cat), removidos


# --- Compatibilidade com API antiga do RJ ---

def carregar_config_rj():
    cat = carregar_catalogo()
    rj = documento_por_id(cat, ID_RJ) or cat["documentos"][0]
    return {"tags": list(rj.get("tags") or []), "documento": rj["documento"]}


def salvar_config_rj(bruto):
    """Salva tags + texto no documento Relatório de Justificativa."""
    dados = _normalizar_config(bruto)
    cat = carregar_catalogo()
    rj = documento_por_id(cat, ID_RJ)
    if rj:
        rj["documento"] = dados["documento"]
        rj["tags"] = dados["tags"]
        rj["atualizado_em"] = int(time.time())
    else:
        cat["documentos"].insert(0, _doc_padrao_rj(dados["documento"], dados["tags"]))
    cat["ativo"] = ID_RJ
    return salvar_catalogo(cat)
