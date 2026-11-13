# -*- coding: utf-8 -*-
import io
import ipaddress
import os
import re
import secrets
import shutil
import sqlite3
import threading
import time
import uuid
import zipfile
from html import escape, unescape
from html.parser import HTMLParser
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, send_file, send_from_directory, session
from flask.sessions import SecureCookieSessionInterface

import banco
import integracao_sei
from geradores.abertura_ia import gerar_html_secao, montar_abertura, sugerir_preenchimento_formulario
from geradores.assistente_abertura import conversar as conversar_abertura
from geradores.campo_ia import responder_campo_ia
from geradores.ia_config import payload_ia_config, salvar_ia_config
from geradores.certificacoes_sugestao import sugerir_certificacoes
from geradores.config_catalogo import (
    ID_RJ,
    carregar_catalogo,
    criar_documento_em_branco,
    definir_ativo,
    documento_por_id,
    excluir_documento,
    importar_arquivo,
    payload_catalogo,
    salvar_catalogo,
)
from geradores.config_documento import carregar_config_rj, salvar_config_rj
from geradores.documento_catalogo import (
    gerar_documento_catalogo,
    gerar_documento_catalogo_html,
    html_para_secao_sei,
    normalizar_caracteres_para_sei,
)
from geradores.docx_editor import converter_docx_para_html, sanitizar_html
from geradores.pesquisa import gerar_pesquisa
from geradores.relatorio import gerar_relatorio
from geradores.termo import gerar_termo

RAIZ = Path(__file__).resolve().parent
SAIDA = RAIZ / "saida"
SAIDA.mkdir(exist_ok=True)


def _config_cookie_sessao_seguro():
    valor = os.environ.get("GCPD_SESSION_COOKIE_SECURE")
    if valor is None:
        return None
    valor = valor.strip().lower()
    if valor in {"1", "true", "yes", "on"}:
        return True
    if valor in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError("GCPD_SESSION_COOKIE_SECURE deve ser true ou false.")


class _InterfaceSessaoCookieLocal(SecureCookieSessionInterface):
    def get_cookie_secure(self, app):
        configurado = app.config["SESSION_COOKIE_SECURE"]
        if configurado is not None:
            return configurado
        try:
            loopback = ipaddress.ip_address(request.remote_addr or "").is_loopback
        except ValueError:
            loopback = False
        return request.is_secure or not loopback


app = Flask(__name__)
app.secret_key = secrets.token_bytes(32)
app.config["MAX_CONTENT_LENGTH"] = 30 * 1024 * 1024
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SECURE"] = _config_cookie_sessao_seguro()
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.session_interface = _InterfaceSessaoCookieLocal()
banco.iniciar()

_SESSOES_SEI = {}
_LOCK_SESSOES_SEI = threading.Lock()
_DURACAO_SESSAO_SEI = 8 * 60 * 60
TIPO_PROCESSO_CONTRATACAO = (
    "Processo de Contratação de Serviço Técnico Profissional Especializado"
)

NOMES = {
    "relatorio": "Relatorio_de_Justificativa.docx",
    "termo": "Termo_de_Referencia.docx",
    "pesquisa": "Pesquisa_Salarial.docx",
}

# Documentos clássicos embutidos (Termo/Pesquisa) — vazios: o usuário recria pelo catálogo.
DOCS_SISTEMA = []


def _limpar_sessoes_sei():
    agora = time.monotonic()
    expiradas = [
        identificador
        for identificador, dados in _SESSOES_SEI.items()
        if dados["expira_em"] <= agora
    ]
    for identificador in expiradas:
        _SESSOES_SEI.pop(identificador, None)


def _sessao_sei_atual():
    identificador = session.get("sei_session_id")
    if not identificador:
        return None
    with _LOCK_SESSOES_SEI:
        _limpar_sessoes_sei()
        dados = _SESSOES_SEI.get(identificador)
    if dados is None:
        session.pop("sei_session_id", None)
    return dados


def _csrf_sei_valido():
    token = session.get("csrf_sei")
    recebido = request.headers.get("X-CSRF-Token", "")
    return bool(token and recebido and secrets.compare_digest(token, recebido))


def _conexao_sei_segura():
    if request.is_secure:
        return True
    try:
        return ipaddress.ip_address(request.remote_addr or "").is_loopback
    except ValueError:
        return False


def _encerrar_sessao_sei():
    identificador = session.pop("sei_session_id", None)
    if identificador:
        with _LOCK_SESSOES_SEI:
            _SESSOES_SEI.pop(identificador, None)


@app.before_request
def exigir_autenticacao_sei():
    permitidos = {"static", "inicio", "estado_sessao_sei", "login_sei", "logout_sei"}
    if request.endpoint in permitidos or _sessao_sei_atual():
        return None
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "mensagem": "Conecte-se ao SEI para acessar o GCPD."}), 401
    return redirect("/")


@app.after_request
def nao_armazenar_respostas_dinamicas(resposta):
    if request.endpoint != "static":
        resposta.headers["Cache-Control"] = "no-store"
    return resposta


def _slug_arquivo(texto):
    limpo = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(texto or "documento").strip())
    return (limpo.strip("_") or "documento")[:80]


def _ids_geracao(bruto):
    bruto_ids = bruto.get("documentos_ids") or bruto.get("documentos") or []
    if not isinstance(bruto_ids, list):
        return []
    saida = []
    vistos = set()
    for item in bruto_ids:
        doc_id = str(item or "").strip()
        if not doc_id or doc_id in vistos:
            continue
        vistos.add(doc_id)
        saida.append(doc_id)
    return saida


def _precisa_pacote_completo(ids):
    especiais = {ID_RJ, "termo_de_referencia", "pesquisa_salarial"}
    return any(doc_id in especiais for doc_id in ids)


def _texto(dados, chave):
    return str(dados.get(chave) or "").strip()


def _linhas(dados, chave, campos):
    itens = []
    for item in dados.get(chave) or []:
        if not isinstance(item, dict):
            continue
        limpo = {campo: str(item.get(campo) or "").strip() for campo in campos}
        if any(limpo.values()):
            itens.append(limpo)
    return itens


def normalizar(bruto, exigir_pacote_completo=True):
    if not isinstance(bruto, dict):
        raise ValueError("O cadastro chegou vazio.")
    processo_sei_bruto = bruto.get("processo_sei")
    if not isinstance(processo_sei_bruto, dict):
        processo_sei_bruto = {}
    processo_contratacao_bruto = bruto.get("processo_contratacao")
    if not isinstance(processo_contratacao_bruto, dict):
        processo_contratacao_bruto = {}

    def lista_textos_processo_sei(chave):
        valores = processo_sei_bruto.get(chave)
        if not isinstance(valores, list):
            return []
        return [str(valor).strip() for valor in valores if str(valor or "").strip()]

    def lista_textos_contratacao(chave):
        valores = processo_contratacao_bruto.get(chave)
        if not isinstance(valores, list):
            return []
        return [str(valor).strip() for valor in valores if str(valor or "").strip()]

    protocolo = _texto(processo_sei_bruto, "protocolo")
    nivel_acesso = _texto(processo_sei_bruto, "nivel_acesso")
    nivel_acesso_contratacao = _texto(processo_contratacao_bruto, "nivel_acesso")
    texto_inicial_contratacao = _texto(processo_contratacao_bruto, "texto_inicial")
    certificacoes = []
    for item in bruto.get("certificacoes") or []:
        if isinstance(item, str) and item.strip():
            certificacoes.append(item.strip())
    dados = {
        "mes_ano": _texto(bruto, "mes_ano"),
        "codigo_relatorio": _texto(bruto, "codigo_relatorio"),
        "versao_relatorio": _texto(bruto, "versao_relatorio") or "V1.0",
        "codigo_termo": _texto(bruto, "codigo_termo"),
        "versao_termo": _texto(bruto, "versao_termo") or "V1.0",
        "assunto": _texto(bruto, "assunto"),
        "tipo_processo_sei": _texto(bruto, "tipo_processo_sei"),
        "tipo_processo_sei_id": _texto(bruto, "tipo_processo_sei_id"),
        "processo_sei": {
            "protocolo": protocolo if protocolo in {"automatico", "informado"} else "automatico",
            "numero_protocolo": _texto(processo_sei_bruto, "numero_protocolo"),
            "especificacao": _texto(processo_sei_bruto, "especificacao"),
            "prioridade": _texto(processo_sei_bruto, "prioridade"),
            "assuntos": lista_textos_processo_sei("assuntos"),
            "interessados": lista_textos_processo_sei("interessados"),
            "observacoes": _texto(processo_sei_bruto, "observacoes"),
            "nivel_acesso": nivel_acesso if nivel_acesso in {"sigiloso", "restrito", "publico"} else "publico",
        },
        "processo_contratacao": {
            "especificacao": (
                _texto(processo_contratacao_bruto, "especificacao")
                or _texto(processo_contratacao_bruto, "descricao")
            ),
            "descricao": (
                _texto(processo_contratacao_bruto, "descricao")
                or _texto(processo_contratacao_bruto, "especificacao")
            ),
            "prioridade": _texto(processo_contratacao_bruto, "prioridade"),
            "interessados": lista_textos_contratacao("interessados"),
            "assuntos": lista_textos_contratacao("assuntos"),
            "observacoes": _texto(processo_contratacao_bruto, "observacoes"),
            "nivel_acesso": (
                nivel_acesso_contratacao
                if nivel_acesso_contratacao in {"sigiloso", "restrito", "publico"}
                else "publico"
            ),
        },
        "tecnologia": _texto(bruto, "tecnologia"),
        "prazo_meses": _texto(bruto, "prazo_meses") or "12",
        "fatos": _texto(bruto, "fatos"),
        "catalogo": _linhas(bruto, "catalogo", ["grupo", "servicos"]),
        "clientes": _linhas(bruto, "clientes", ["cliente", "projeto"]),
        "perfis": _linhas(bruto, "perfis", ["item", "perfil", "experiencia", "horas", "proporcao"]),
        "perfil_referencia": _texto(bruto, "perfil_referencia"),
        "horas_por_pf": _texto(bruto, "horas_por_pf"),
        "regra_vma": _texto(bruto, "regra_vma"),
        "versao_sisp": _texto(bruto, "versao_sisp") or "3.0",
        "incluir_snap": bool(bruto.get("incluir_snap")),
        "parceria": _texto(bruto, "parceria"),
        "estudo_mercado": _texto(bruto, "estudo_mercado"),
        "atestados": _texto(bruto, "atestados"),
        "regime_certificacao": _texto(bruto, "regime_certificacao") or "Obrigatória no ato da contratação",
        "certificacoes": certificacoes,
        "horas_professional": _texto(bruto, "horas_professional"),
        "area_elaboracao": _texto(bruto, "area_elaboracao"),
        "texto_elaboracao": _texto(bruto, "texto_elaboracao"),
        "local_data": _texto(bruto, "local_data"),
        "aprovadores": _linhas(bruto, "aprovadores", ["nome", "matricula", "cargo"]),
        "extras": {},
    }
    extras = bruto.get("extras") if isinstance(bruto.get("extras"), dict) else {}
    for chave, valor in extras.items():
        nome = str(chave or "").strip()
        if not nome:
            continue
        if isinstance(valor, dict):
            # Tabelas e estruturas: preserva linhas/colunas.
            dados["extras"][nome] = valor
        elif isinstance(valor, list):
            dados["extras"][nome] = valor
        else:
            dados["extras"][nome] = str(valor or "").strip()
    if not exigir_pacote_completo:
        if not dados["assunto"] and dados["tecnologia"]:
            dados["assunto"] = (
                "CONTRATAÇÃO DE SERVIÇOS DE APOIO TÉCNICO ESPECIALIZADO EM "
                f"{dados['tecnologia'].upper()}"
            )
        if not dados["assunto"]:
            dados["assunto"] = "Documento gerado pelo GCPD"
        return dados
    faltas = []
    obrigatorios = [
        ("mes_ano", "mês e ano"),
        ("codigo_relatorio", "código do relatório"),
        ("codigo_termo", "código do termo"),
        ("assunto", "assunto"),
        ("tecnologia", "tecnologia"),
        ("perfil_referencia", "perfil de referência"),
        ("horas_por_pf", "horas por ponto de função"),
        ("regra_vma", "regra do valor médio da hora"),
        ("area_elaboracao", "área que elabora o relatório"),
        ("texto_elaboracao", "texto de elaboração do termo"),
    ]
    for chave, nome in obrigatorios:
        if not dados[chave]:
            faltas.append(nome)
    if not any(p.get("perfil") and p.get("horas") for p in dados["perfis"]):
        faltas.append("ao menos um perfil com nome e horas")
    if not dados["aprovadores"]:
        faltas.append("ao menos um aprovador")
    if faltas:
        raise ValueError("Faltam: " + ", ".join(faltas) + ".")
    return dados


def _pasta(identificador):
    if not identificador or not all(c in "0123456789abcdef" for c in identificador):
        raise ValueError("Identificador inválido.")
    pasta = (SAIDA / identificador).resolve()
    if SAIDA.resolve() not in pasta.parents:
        raise ValueError("Identificador inválido.")
    return pasta


def _corpo_json():
    bruto = request.get_json(force=True, silent=True) or {}
    if not isinstance(bruto, dict):
        raise ValueError("Os dados da lista chegaram vazios.")
    return bruto


@app.get("/")
def inicio():
    if not _sessao_sei_atual():
        return render_template("login.html")
    return render_template("index.html")


@app.get("/cadastro")
def cadastro_page():
    if not _sessao_sei_atual():
        return redirect("/")
    return render_template("index.html")


@app.get("/fluxo-criar")
def fluxo_criar_processo():
    if not _sessao_sei_atual():
        return redirect("/")
    return render_template("fluxo_criar_processo.html")


@app.get("/processo-sei-ia")
def processo_sei_ia():
    if not _sessao_sei_atual():
        return redirect("/")
    return render_template("processo_sei_ia.html")


@app.get("/api/catalogo")
def catalogo():
    return jsonify({"tecnologias": banco.listar()})


@app.get("/api/tipos-processo-sei")
def tipos_processo_sei():
    return jsonify({"tipos": banco.listar_tipos_processo_sei()})


@app.get("/api/assuntos-sei")
def assuntos_sei():
    return jsonify({"assuntos": banco.listar_assuntos_sei()})


@app.get("/api/tipos-documento-sei")
def tipos_documento_sei():
    return jsonify({"tipos": banco.listar_tipos_documento_sei()})


@app.post("/api/tipos-processo-sei")
def novo_tipo_processo_sei():
    try:
        identificador = banco.criar_tipo_processo_sei(_corpo_json().get("nome"))
    except (ValueError, TypeError) as erro:
        return jsonify({"ok": False, "mensagem": str(erro)}), 400
    return jsonify({
        "ok": True,
        "id": identificador,
        "tipos": banco.listar_tipos_processo_sei(),
    })


@app.post("/api/tecnologias")
def nova_tecnologia():
    try:
        identificador = banco.criar_tecnologia(_corpo_json().get("nome"))
    except ValueError as erro:
        return jsonify({"ok": False, "mensagem": str(erro)}), 400
    return jsonify({"ok": True, "id": identificador, "tecnologias": banco.listar()})


@app.post("/api/grupos")
def novo_grupo():
    try:
        corpo = _corpo_json()
        identificador = banco.criar_grupo(corpo.get("tecnologia_id"), corpo.get("nome"))
    except (ValueError, TypeError) as erro:
        return jsonify({"ok": False, "mensagem": str(erro)}), 400
    return jsonify({"ok": True, "id": identificador, "tecnologias": banco.listar()})


@app.post("/api/servicos")
def novo_servico():
    try:
        corpo = _corpo_json()
        identificador = banco.criar_servico(corpo.get("grupo_id"), corpo.get("nome"))
    except (ValueError, TypeError) as erro:
        return jsonify({"ok": False, "mensagem": str(erro)}), 400
    return jsonify({"ok": True, "id": identificador, "tecnologias": banco.listar()})


@app.post("/api/perfis")
def novo_perfil():
    try:
        corpo = _corpo_json()
        identificador = banco.criar_perfil(corpo.get("tecnologia_id"), corpo.get("nome"))
    except (ValueError, TypeError) as erro:
        return jsonify({"ok": False, "mensagem": str(erro)}), 400
    return jsonify({"ok": True, "id": identificador, "tecnologias": banco.listar()})


@app.post("/api/certificacoes/sugerir")
def certificacoes_sugerir():
    bruto = request.get_json(force=True, silent=False) or {}
    try:
        resultado = sugerir_certificacoes(bruto.get("tecnologia"), bruto.get("perfis") or [])
    except ValueError as erro:
        return jsonify({"ok": False, "mensagem": str(erro)}), 400
    except Exception as erro:
        return jsonify({"ok": False, "mensagem": f"Falha na busca de certificações: {erro}"}), 502
    return jsonify({"ok": True, **resultado})


@app.get("/api/config/relatorio-justificativa")
def config_rj_obter():
    return jsonify({"ok": True, **carregar_config_rj()})


@app.put("/api/config/relatorio-justificativa")
def config_rj_salvar():
    bruto = request.get_json(force=True, silent=False) or {}
    try:
        dados = salvar_config_rj(bruto)
    except ValueError as erro:
        return jsonify({"ok": False, "mensagem": str(erro)}), 400
    return jsonify({"ok": True, **dados})


@app.get("/api/config/catalogo")
def config_catalogo_obter():
    corpo = payload_catalogo(carregar_catalogo())
    docs = list(corpo.get("documentos") or [])
    corpo["documentos"] = docs
    corpo["documentos_geracao"] = docs
    return jsonify(corpo)


@app.get("/api/formularios-sei")
def formularios_sei():
    catalogo = carregar_catalogo()
    return jsonify({
        "formularios": [
            {
                "id": documento["id"],
                "nome": documento["nome"],
                "tags": documento.get("tags") or [],
                "documento": documento.get("documento") or "",
                "secoes": documento.get("secoes") or [],
            }
            for documento in catalogo["documentos"]
        ],
    })


@app.put("/api/config/catalogo")
def config_catalogo_salvar():
    bruto = request.get_json(force=True, silent=False) or {}
    try:
        cat = carregar_catalogo()
        doc_id = str(bruto.get("ativo") or cat["ativo"]).strip()
        alvo = documento_por_id(cat, doc_id)
        if not alvo:
            raise ValueError("Documento não encontrado.")
        if bruto.get("nome") is not None:
            nome = str(bruto.get("nome") or "").strip()
            if not nome:
                raise ValueError("Informe o nome do documento.")
            alvo["nome"] = nome[:160]
        if bruto.get("documento") is not None:
            texto = str(bruto.get("documento") or "").strip()
            if not texto:
                raise ValueError("O texto do documento não pode ficar vazio.")
            alvo["documento"] = texto
        if "tags" in bruto:
            from geradores.config_catalogo import _normalizar_tags_lista
            alvo["tags"] = _normalizar_tags_lista(bruto.get("tags") or [], permitir_vazio=True)
        if "grupos" in bruto:
            from geradores.config_catalogo import _normalizar_grupos, _sincronizar_secoes, _montar_documento_de_secoes
            alvo["grupos"] = _normalizar_grupos(bruto.get("grupos") or [], alvo.get("tags") or [])
            secoes_in = bruto.get("secoes") if "secoes" in bruto else alvo.get("secoes")
            alvo["secoes"] = _sincronizar_secoes(alvo["grupos"], secoes_in, alvo.get("documento") or "")
            if alvo["secoes"]:
                alvo["documento"] = _montar_documento_de_secoes(alvo["secoes"])
        elif "secoes" in bruto:
            from geradores.config_catalogo import _sincronizar_secoes, _montar_documento_de_secoes
            alvo["secoes"] = _sincronizar_secoes(alvo.get("grupos") or [], bruto.get("secoes") or [], "")
            if alvo["secoes"]:
                alvo["documento"] = _montar_documento_de_secoes(alvo["secoes"])
        cat["ativo"] = doc_id
        cat = salvar_catalogo(cat)
        return jsonify(payload_catalogo(cat))
    except ValueError as erro:
        return jsonify({"ok": False, "mensagem": str(erro)}), 400


@app.post("/api/config/catalogo/documento")
def config_catalogo_criar():
    bruto = request.get_json(force=True, silent=False) or {}
    try:
        cat, _novo = criar_documento_em_branco(bruto.get("nome"))
        return jsonify(payload_catalogo(cat))
    except ValueError as erro:
        return jsonify({"ok": False, "mensagem": str(erro)}), 400


@app.post("/api/config/catalogo/upload")
def config_catalogo_upload():
    arquivo = request.files.get("arquivo")
    if not arquivo or not arquivo.filename:
        return jsonify({"ok": False, "mensagem": "Selecione um arquivo Word (.docx) ou PDF."}), 400
    try:
        dados = arquivo.read()
        if not dados:
            raise ValueError("Arquivo vazio.")
        cat, novo, meta = importar_arquivo(arquivo.filename, dados, request.form.get("nome") or "")
        corpo = payload_catalogo(cat)
        qtd = int((meta or {}).get("qtd_tags") or 0)
        if qtd:
            corpo["mensagem"] = (
                f"Documento “{novo['nome']}” importado com {qtd} tag(s). "
                "O formulário já está pronto; ajuste o tipo de cada tag se quiser."
            )
        else:
            corpo["mensagem"] = (
                f"Documento “{novo['nome']}” importado sem tags {{campo}}. "
                "Crie os grupos e as tags manualmente, ou envie um Word já tagueado."
            )
        corpo["qtd_tags"] = qtd
        return jsonify(corpo)
    except ValueError as erro:
        return jsonify({"ok": False, "mensagem": str(erro)}), 400
    except Exception as erro:
        return jsonify({"ok": False, "mensagem": f"Falha ao importar: {erro}"}), 502


@app.post("/api/config/catalogo/ativo")
def config_catalogo_ativo():
    bruto = request.get_json(force=True, silent=False) or {}
    try:
        cat = definir_ativo(bruto.get("id"))
        return jsonify(payload_catalogo(cat))
    except ValueError as erro:
        return jsonify({"ok": False, "mensagem": str(erro)}), 400


@app.delete("/api/config/catalogo/documento/<doc_id>")
def config_catalogo_excluir(doc_id):
    try:
        from geradores.config_catalogo import excluir_documentos
        cat, removidos = excluir_documentos([doc_id])
        corpo = payload_catalogo(cat)
        nome = (removidos[0].get("nome") if removidos else doc_id) or doc_id
        corpo["mensagem"] = f"Documento “{nome}” excluído."
        corpo["excluidos"] = len(removidos)
        return jsonify(corpo)
    except ValueError as erro:
        return jsonify({"ok": False, "mensagem": str(erro)}), 400
    except Exception as erro:
        return jsonify({"ok": False, "mensagem": f"Falha ao excluir: {erro}"}), 502


@app.delete("/api/config/catalogo/documentos")
def config_catalogo_excluir_varios():
    bruto = request.get_json(force=True, silent=True) or {}
    ids = bruto.get("ids") if isinstance(bruto, dict) else None
    try:
        from geradores.config_catalogo import excluir_documentos
        cat, removidos = excluir_documentos(ids or [])
        corpo = payload_catalogo(cat)
        qtd = len(removidos)
        corpo["excluidos"] = qtd
        if qtd == 1:
            corpo["mensagem"] = f"Documento “{removidos[0].get('nome') or removidos[0].get('id')}” excluído."
        else:
            corpo["mensagem"] = f"{qtd} documentos excluídos."
        return jsonify(corpo)
    except ValueError as erro:
        return jsonify({"ok": False, "mensagem": str(erro)}), 400
    except Exception as erro:
        return jsonify({"ok": False, "mensagem": f"Falha ao excluir: {erro}"}), 502


@app.get("/api/config/ia")
def config_ia_obter():
    return jsonify(payload_ia_config())


@app.put("/api/config/ia")
def config_ia_salvar():
    bruto = request.get_json(force=True, silent=False) or {}
    try:
        salvar_ia_config(bruto)
    except ValueError as erro:
        return jsonify({"ok": False, "mensagem": str(erro)}), 400
    except Exception as erro:
        return jsonify({"ok": False, "mensagem": f"Falha ao salvar IA: {erro}"}), 500
    return jsonify(payload_ia_config())


@app.get("/api/config/processo-assunto")
def config_processo_assunto_listar():
    return jsonify({
        "ok": True,
        "relacoes": banco.listar_relacoes_processo_assunto(),
        "assuntos": banco.listar_assuntos_sei(),
        "tipos_processo": banco.listar_tipos_processo_sei(),
    })


@app.put("/api/config/processo-assunto")
def config_processo_assunto_salvar():
    bruto = request.get_json(silent=True)
    if not isinstance(bruto, dict):
        return jsonify({"ok": False, "mensagem": "Informe a relação processo/assunto."}), 400
    try:
        banco.salvar_relacao_processo_assunto(
            bruto.get("tipo_processo_id_sei") or bruto.get("id_sei") or "",
            bruto.get("assunto_id_sei") or "",
        )
        banco.persistir_relacoes_processo_assunto_arquivo()
    except ValueError as erro:
        return jsonify({"ok": False, "mensagem": str(erro)}), 400
    except Exception as erro:
        app.logger.exception("Falha ao salvar relação processo/assunto")
        return jsonify({"ok": False, "mensagem": f"Falha ao salvar: {erro}"}), 500
    return jsonify({
        "ok": True,
        "relacoes": banco.listar_relacoes_processo_assunto(),
    })


@app.get("/api/processo-assunto")
def processo_assunto_obter():
    """Retorna o assunto vinculado a um tipo de processo (por id_sei ou nome)."""
    id_sei = (request.args.get("tipo_processo_id_sei") or "").strip()
    nome = (request.args.get("tipo_processo") or request.args.get("nome") or "").strip()
    assunto = banco.obter_assunto_do_tipo_processo(tipo_processo_id_sei=id_sei, tipo_processo_nome=nome)
    return jsonify({"ok": True, "assunto": assunto})


@app.post("/api/ia/montar-abertura")
def ia_montar_abertura():
    """Usa a IA cadastrada para montar processo + documento a partir de um texto livre."""
    bruto = request.get_json(silent=True)
    if not isinstance(bruto, dict):
        return jsonify({"ok": False, "mensagem": "Informe a descrição do processo."}), 400
    try:
        resultado = montar_abertura(
            bruto.get("descricao") or bruto.get("pedido") or bruto.get("texto"),
            bruto.get("tipo_processo") or bruto.get("tipo_processo_sei") or "",
        )
    except ValueError as erro:
        return jsonify({"ok": False, "mensagem": str(erro)}), 400
    except Exception as erro:
        app.logger.exception("Falha em /api/ia/montar-abertura")
        return jsonify({"ok": False, "mensagem": f"Falha ao montar abertura com IA: {erro}"}), 502
    return jsonify(resultado)


@app.post("/api/ia/assistente-abertura")
def ia_assistente_abertura():
    """Bate-papo para achar tipo de processo e documento nas listas internas."""
    bruto = request.get_json(silent=True)
    if not isinstance(bruto, dict):
        bruto = {}
    try:
        resultado = conversar_abertura(
            bruto.get("mensagem") or bruto.get("texto") or "",
            bruto.get("estado"),
            bruto.get("escolha"),
        )
    except ValueError as erro:
        return jsonify({"ok": False, "mensagem": str(erro)}), 400
    except Exception as erro:
        app.logger.exception("Falha em /api/ia/assistente-abertura")
        return jsonify({"ok": False, "mensagem": f"Falha no assistente: {erro}"}), 502
    return jsonify(resultado)


@app.post("/api/ia/gerar-secao")
def ia_gerar_secao():
    """Gera HTML de seção editável com a IA configurada (Gemini/OpenAI)."""
    if not _csrf_sei_valido():
        return jsonify({"ok": False, "mensagem": "Sessão expirada. Atualize a página e tente novamente."}), 403
    bruto = request.get_json(silent=True)
    if not isinstance(bruto, dict):
        return jsonify({"ok": False, "mensagem": "Informe o prompt da seção."}), 400
    try:
        resultado = gerar_html_secao(
            bruto.get("prompt") or bruto.get("consulta") or "",
            bruto.get("contexto") or "",
            bruto.get("tipo_documento") or "",
        )
    except ValueError as erro:
        return jsonify({"ok": False, "mensagem": str(erro)}), 400
    except Exception as erro:
        app.logger.exception("Falha em /api/ia/gerar-secao")
        return jsonify({"ok": False, "mensagem": f"Falha ao gerar seção com IA: {erro}"}), 502
    return jsonify(resultado)


@app.post("/api/ia/preencher-formulario")
def ia_preencher_formulario():
    """Sugere valores para as tags do formulário escolhido (genérico para qualquer formulário)."""
    if not _csrf_sei_valido():
        return jsonify({"ok": False, "mensagem": "Sessão expirada. Atualize a página e tente novamente."}), 403
    bruto = request.get_json(silent=True)
    if not isinstance(bruto, dict):
        return jsonify({"ok": False, "mensagem": "Informe o formulário e o contexto."}), 400
    formulario = bruto.get("formulario")
    if not isinstance(formulario, dict):
        return jsonify({"ok": False, "mensagem": "Selecione um formulário válido."}), 400
    contexto = bruto.get("contexto") if isinstance(bruto.get("contexto"), dict) else {}
    sessao = _sessao_sei_atual() or {}
    if not contexto.get("interessado") and sessao.get("usuario"):
        contexto = {**contexto, "interessado": sessao.get("usuario")}
    try:
        resultado = sugerir_preenchimento_formulario(formulario, contexto)
    except ValueError as erro:
        return jsonify({"ok": False, "mensagem": str(erro)}), 400
    except Exception as erro:
        app.logger.exception("Falha em /api/ia/preencher-formulario")
        return jsonify({"ok": False, "mensagem": f"Falha ao sugerir preenchimento: {erro}"}), 502
    return jsonify(resultado)


@app.post("/api/campos/sugerir")
def campos_sugerir():
    bruto = request.get_json(force=True, silent=False) or {}
    try:
        resultado = responder_campo_ia(
            bruto.get("consulta") or bruto.get("consulta_ia"),
            bruto.get("tecnologia"),
            bruto.get("rotulo"),
            bool(bruto.get("usar_tecnologia")),
            bruto.get("historico") or [],
        )
    except ValueError as erro:
        return jsonify({"ok": False, "mensagem": str(erro)}), 400
    except Exception as erro:
        return jsonify({"ok": False, "mensagem": f"Falha na busca do campo: {erro}"}), 502
    return jsonify({"ok": True, **resultado})


@app.get("/api/processos")
def processos():
    return jsonify({"processos": banco.listar_processos()})


@app.get("/api/processos/por-sei")
def processo_por_sei():
    try:
        processos = banco.buscar_por_sei(request.args.get("numero"))
    except ValueError as erro:
        return jsonify({"ok": False, "mensagem": str(erro)}), 404
    return jsonify({"ok": True, "processos": processos, "processo": processos[0]})


@app.get("/api/processos/<int:processo_id>")
def processo(processo_id):
    try:
        return jsonify({"ok": True, "processo": banco.obter_processo(processo_id)})
    except ValueError as erro:
        return jsonify({"ok": False, "mensagem": str(erro)}), 404


@app.get("/api/processos/<int:processo_id>/documentos")
def documentos_processo(processo_id):
    try:
        processo = banco.obter_processo(processo_id)
        disponiveis = []
        if processo.get("pasta_id"):
            pasta = _pasta(processo["pasta_id"])
            if pasta.is_dir():
                for arquivo in sorted(pasta.glob("*.docx")):
                    disponiveis.append({
                        "arquivo": arquivo.name,
                        "slug": arquivo.stem,
                        "nome": arquivo.stem.replace("_", " "),
                    })
        return jsonify({
            "disponiveis": disponiveis,
            "anexados": banco.listar_documentos_processo(processo_id),
        })
    except ValueError as erro:
        return jsonify({"ok": False, "mensagem": str(erro)}), 404


@app.post("/api/processos/<int:processo_id>/documentos/converter")
def converter_documento_processo(processo_id):
    bruto = _corpo_json()
    nome_arquivo = _texto(bruto, "arquivo")
    if not nome_arquivo.lower().endswith(".docx") or Path(nome_arquivo).name != nome_arquivo:
        return jsonify({"ok": False, "mensagem": "Selecione um Word gerado por este processo."}), 400
    try:
        processo = banco.obter_processo(processo_id)
        if not processo.get("pasta_id"):
            raise ValueError("Gere ao menos um documento Word para este processo antes de incluí-lo.")
        pasta = _pasta(processo["pasta_id"])
        arquivo = pasta / nome_arquivo
        if arquivo.parent.resolve() != pasta.resolve() or not arquivo.is_file():
            raise ValueError("O Word selecionado não pertence à geração atual deste processo.")
        convertido = converter_docx_para_html(arquivo)
    except ValueError as erro:
        return jsonify({"ok": False, "mensagem": str(erro)}), 400
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as erro:
        app.logger.exception("Falha ao converter Word do processo %s", processo_id)
        return jsonify({
            "ok": False,
            "mensagem": f"Não foi possível converter o Word para o editor: {erro}",
        }), 500
    return jsonify({"ok": True, **convertido})


@app.post("/api/processos/<int:processo_id>/documentos")
def anexar_documento_processo(processo_id):
    try:
        bruto = _corpo_json()
        metadados = bruto.get("metadados")
        if not isinstance(metadados, dict):
            raise ValueError("Informe os dados do documento.")
        conteudo_html = sanitizar_html(bruto.get("conteudo_html"))
        if not conteudo_html.strip():
            raise ValueError("O conteúdo do documento está vazio.")
        documento = banco.adicionar_documento_processo(
            processo_id=processo_id,
            nome=_texto(bruto, "nome"),
            tipo_documento=_texto(bruto, "tipo_documento"),
            arquivo_origem=_texto(bruto, "arquivo_origem"),
            metadados=metadados,
            conteudo_html=conteudo_html,
        )
    except ValueError as erro:
        return jsonify({"ok": False, "mensagem": str(erro)}), 400
    return jsonify({"ok": True, "documento": documento}), 201


@app.get("/api/processos/<int:processo_id>/documentos/<int:documento_id>")
def baixar_documento_processo(processo_id, documento_id):
    try:
        documento = banco.obter_documento_processo(documento_id)
        if documento["processo_id"] != processo_id:
            raise ValueError("Documento não encontrado neste processo.")
        conteudo = documento["conteudo_html"]
    except ValueError as erro:
        return jsonify({"ok": False, "mensagem": str(erro)}), 404
    html_documento = f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(documento['nome'])}</title>
  <style>
    body {{ max-width: 900px; margin: 32px auto; padding: 0 24px; color: #111; font: 12pt/1.4 "Times New Roman", serif; }}
    table {{ width: 100%; margin: 12px 0; border-collapse: collapse; }}
    th, td {{ padding: 5px 7px; border: 1px solid #666; vertical-align: top; }}
    img {{ max-width: 100%; height: auto; }}
  </style>
</head>
<body>{conteudo}</body>
</html>"""
    return send_file(
        io.BytesIO(html_documento.encode("utf-8")),
        mimetype="text/html",
        as_attachment=True,
        download_name=f"{_slug_arquivo(documento['nome'])}.html",
    )


@app.post("/api/processos/rascunho")
def salvar_rascunho_processo():
    bruto = _corpo_json()
    try:
        dados = normalizar(bruto, exigir_pacote_completo=False)
        assunto = (
            _texto(bruto, "assunto")
            or dados["processo_sei"]["especificacao"]
            or dados["processo_contratacao"]["descricao"]
            or f"Processo SEI - {dados['tipo_processo_sei'] or 'Abertura'}"
        )
        processo_id = bruto.get("processo_id")
        if processo_id:
            processo = banco.atualizar_processo(
                int(processo_id),
                cadastro=dados,
                assunto=assunto,
            )
        else:
            processo = banco.criar_processo(
                tipo="Abertura",
                assunto=assunto,
                cadastro=dados,
            )
    except (ValueError, TypeError) as erro:
        return jsonify({"ok": False, "mensagem": str(erro)}), 400
    return jsonify({"ok": True, "processo": processo})


@app.get("/api/sei/sessao")
def estado_sessao_sei():
    csrf_token = session.get("csrf_sei")
    if not csrf_token:
        csrf_token = secrets.token_urlsafe(32)
        session["csrf_sei"] = csrf_token
    dados = _sessao_sei_atual()
    return jsonify({
        "autenticado": bool(dados),
        "usuario": dados["usuario"] if dados else "",
        "csrf_token": csrf_token,
    })


@app.post("/api/sei/login")
def login_sei():
    if not _conexao_sei_segura():
        return jsonify({
            "ok": False,
            "mensagem": "Acesse o GCPD por HTTPS para enviar suas credenciais do SEI.",
        }), 400
    bruto = request.get_json(silent=True)
    if not isinstance(bruto, dict):
        return jsonify({"ok": False, "mensagem": "Informe usuário e senha."}), 400
    if not _csrf_sei_valido():
        return jsonify({"ok": False, "mensagem": "Sessão expirada. Atualize a página e tente novamente."}), 403
    usuario = str(bruto.get("usuario") or "").strip()
    senha = bruto.get("senha")
    if not usuario or not isinstance(senha, str) or not senha:
        return jsonify({"ok": False, "mensagem": "Informe usuário e senha do SEI."}), 400
    try:
        token = integracao_sei.autenticar(usuario, senha)
    except integracao_sei.ErroIntegracaoSEI as erro:
        return jsonify({"ok": False, "mensagem": str(erro)}), erro.status_http

    _encerrar_sessao_sei()
    session.clear()
    identificador = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    with _LOCK_SESSOES_SEI:
        _limpar_sessoes_sei()
        _SESSOES_SEI[identificador] = {
            "token": token,
            "usuario": usuario,
            "expira_em": time.monotonic() + _DURACAO_SESSAO_SEI,
        }
    session["sei_session_id"] = identificador
    session["csrf_sei"] = csrf_token
    return jsonify({"ok": True, "usuario": usuario, "csrf_token": csrf_token})


@app.post("/api/sei/logout")
def logout_sei():
    if not _csrf_sei_valido():
        return jsonify({"ok": False, "mensagem": "Sessão expirada. Atualize a página e tente novamente."}), 403
    _encerrar_sessao_sei()
    session.clear()
    return jsonify({"ok": True})


def _dados_criacao_processo_sei(cadastro):
    tipo_processo = str(cadastro.get("tipo_processo_sei") or "").strip()
    tipo_id = banco.obter_id_sei_tipo_processo(tipo_processo)
    if not tipo_id:
        raise ValueError("O tipo de processo ainda não tem ID SEI configurado.")

    processo_contratacao = cadastro.get("processo_contratacao")
    if not isinstance(processo_contratacao, dict):
        processo_contratacao = {}
    processo_sei = cadastro.get("processo_sei")
    if not isinstance(processo_sei, dict):
        processo_sei = {}
    # Qualquer tipo (exceto Decreto) usa o formulário Iniciar Processo.
    if tipo_processo.casefold() == "decreto":
        dados_tipo = processo_sei
    else:
        dados_tipo = processo_contratacao
    assunto = (
        str(cadastro.get("assunto") or "").strip()
        or str(dados_tipo.get("especificacao") or dados_tipo.get("descricao") or "").strip()
        or f"Processo SEI - {tipo_processo}"
    )
    assuntos = _resolver_assuntos_sei(dados_tipo.get("assuntos") or [])
    if not assuntos:
        relacionado = banco.obter_assunto_do_tipo_processo(
            tipo_processo_id_sei=tipo_id,
            tipo_processo_nome=tipo_processo,
        )
        if relacionado and relacionado.get("id_sei"):
            assuntos = [{"id": relacionado["id_sei"]}]
    if not assuntos:
        raise ValueError(
            "Selecione ao menos um assunto na Classificação por Assuntos. "
            "É obrigatório para criar o processo no SEI."
        )
    return {
        "tipo_processo": tipo_processo,
        "tipo_id": tipo_id,
        "assunto": assunto,
        "especificacao": dados_tipo.get("especificacao") or dados_tipo.get("descricao") or "",
        "observacoes": dados_tipo.get("observacoes") or "",
        "nivel_acesso": dados_tipo.get("nivel_acesso") or "publico",
        "assuntos": assuntos,
    }


def _resolver_assuntos_sei(assuntos):
    """Converte nomes (ou objetos) de assunto para {id: id_sei} aceito pela API."""
    resolvidos = []
    for item in assuntos or []:
        if isinstance(item, dict) and item.get("id") is not None:
            resolvidos.append({"id": item["id"]})
            continue
        texto = str(item or "").strip()
        if not texto:
            continue
        if texto.isdigit():
            resolvidos.append({"id": texto})
            continue
        id_sei = banco.obter_id_sei_assunto(texto)
        if id_sei:
            resolvidos.append({"id": id_sei})
    return resolvidos


def _executar_criacao_processo_sei(processo_id, cadastro, dados_tipo, sessao_sei):
    try:
        retorno = integracao_sei.criar_processo(
            tipo_processo=dados_tipo["tipo_id"],
            especificacao=dados_tipo["especificacao"],
            observacoes=dados_tipo["observacoes"],
            nivel_acesso=dados_tipo["nivel_acesso"],
            assuntos=dados_tipo["assuntos"],
            token=sessao_sei["token"],
        )
    except integracao_sei.ErroIntegracaoSEI as erro:
        banco.falhar_criacao_sei(processo_id, erro.resultado_incerto)
        if erro.status_http == 401:
            _encerrar_sessao_sei()
        mensagem = str(erro)
        if erro.resultado_incerto:
            mensagem = (
                f"{mensagem} O resultado está indeterminado; consulte o SEI antes de qualquer nova tentativa."
            )
        return jsonify({
            "ok": False,
            "mensagem": mensagem,
            "resultado_incerto": erro.resultado_incerto,
            "processo": banco.obter_processo(processo_id),
        }), erro.status_http

    extras = cadastro.get("extras")
    if not isinstance(extras, dict):
        extras = {}
    cadastro["extras"] = extras
    extras["n_processo_sei"] = retorno["protocolo"]
    try:
        processo = banco.concluir_criacao_sei(
            processo_id,
            retorno["id_procedimento"],
            retorno["protocolo"],
            cadastro=cadastro,
        )
    except (ValueError, sqlite3.Error) as erro:
        try:
            banco.falhar_criacao_sei(processo_id, resultado_incerto=True)
        except sqlite3.Error:
            app.logger.exception(
                "Não foi possível marcar como indeterminada a criação SEI do processo %s.",
                processo_id,
            )
        return jsonify({
            "ok": False,
            "mensagem": (
                f"O SEI criou o processo {retorno['protocolo']}, mas o GCPD não conseguiu "
                f"salvar o retorno localmente: {erro}"
            ),
            "processo_criado": True,
            "resultado_incerto": True,
            "protocolo": retorno["protocolo"],
            "processo": banco.obter_processo(processo_id),
        }), 500
    return jsonify({"ok": True, "processo": processo})


@app.post("/api/processos/criar-no-sei")
def criar_novo_processo_no_sei():
    if not _csrf_sei_valido():
        return jsonify({"ok": False, "mensagem": "Sessão expirada. Atualize a página e tente novamente."}), 403
    sessao_sei = _sessao_sei_atual()
    if not sessao_sei:
        return jsonify({"ok": False, "mensagem": "Entre no SEI antes de criar o processo."}), 401
    bruto = request.get_json(silent=True)
    if not isinstance(bruto, dict):
        return jsonify({"ok": False, "mensagem": "Informe os dados do processo."}), 400
    try:
        cadastro = normalizar(bruto, exigir_pacote_completo=False)
        dados_tipo = _dados_criacao_processo_sei(cadastro)
        processo = banco.reservar_novo_processo_sei(
            tipo=str(bruto.get("tipo_processo") or "Abertura").strip(),
            assunto=dados_tipo["assunto"],
            cadastro=cadastro,
        )
    except (ValueError, TypeError) as erro:
        return jsonify({"ok": False, "mensagem": str(erro)}), 400
    return _executar_criacao_processo_sei(
        processo["id"],
        cadastro,
        dados_tipo,
        sessao_sei,
    )


@app.post("/api/processos/<int:processo_id>/criar-no-sei")
def criar_processo_no_sei(processo_id):
    if not _csrf_sei_valido():
        return jsonify({"ok": False, "mensagem": "Sessão expirada. Atualize a página e tente novamente."}), 403
    sessao_sei = _sessao_sei_atual()
    if not sessao_sei:
        return jsonify({"ok": False, "mensagem": "Entre no SEI antes de criar o processo."}), 401
    try:
        processo = banco.obter_processo(processo_id)
        bruto = request.get_json(silent=True)
        if isinstance(bruto, dict):
            cadastro = normalizar(bruto, exigir_pacote_completo=False)
        else:
            cadastro = processo.get("cadastro")
        if not isinstance(cadastro, dict):
            raise ValueError("Preencha os dados do processo antes de criar no SEI.")
        dados_tipo = _dados_criacao_processo_sei(cadastro)
        if isinstance(bruto, dict):
            processo = banco.atualizar_processo(
                processo_id,
                cadastro=cadastro,
                assunto=dados_tipo["assunto"],
            )
        banco.reservar_criacao_sei(processo_id)
    except ValueError as erro:
        return jsonify({"ok": False, "mensagem": str(erro)}), 400
    return _executar_criacao_processo_sei(
        processo_id,
        cadastro,
        dados_tipo,
        sessao_sei,
    )


@app.post("/api/processos/<int:processo_id>/documentos/criar-no-sei")
def criar_documento_interno_no_sei(processo_id):
    if not _csrf_sei_valido():
        return jsonify({"ok": False, "mensagem": "Sessão expirada. Atualize a página e tente novamente."}), 403
    sessao_sei = _sessao_sei_atual()
    if not sessao_sei:
        return jsonify({"ok": False, "mensagem": "Entre no SEI antes de anexar o documento."}), 401
    try:
        processo = banco.obter_processo(processo_id)
    except ValueError as erro:
        return jsonify({"ok": False, "mensagem": str(erro)}), 404
    try:
        procedimento_id = processo.get("id_procedimento_sei")
        if not procedimento_id:
            raise ValueError("Crie o processo no SEI antes de anexar um documento.")
        bruto = _corpo_json()
        bruto, tipo_documento = banco.aplicar_regras_documento_sei(bruto)
        documento = integracao_sei.cadastrar_documento_interno(
            procedimento=procedimento_id,
            campos=bruto,
            token=sessao_sei["token"],
        )
    except integracao_sei.ErroIntegracaoSEI as erro:
        if erro.status_http == 401:
            _encerrar_sessao_sei()
        return jsonify({
            "ok": False,
            "mensagem": str(erro),
            "resultado_incerto": erro.resultado_incerto,
            "campo_faltante": erro.campo_faltante,
        }), erro.status_http
    except ValueError as erro:
        return jsonify({
            "ok": False,
            "mensagem": str(erro),
            "campo_faltante": integracao_sei.extrair_campo_faltante_documento(str(erro)),
        }), 400
    if documento.get("id_documento"):
        try:
            descricao_local = (
                str(bruto.get("descricao") or "").strip()
                or str(bruto.get("nomeArvore") or "").strip()
                or tipo_documento["nome"]
            )
            banco.registrar_documento_sei(
                processo_id=processo_id,
                id_documento=documento["id_documento"],
                protocolo=documento.get("protocolo"),
                descricao=descricao_local,
                id_serie=tipo_documento["id"],
                tipo_documento=tipo_documento["nome"],
            )
        except (ValueError, sqlite3.Error):
            app.logger.exception(
                "O SEI confirmou o documento %s, mas o GCPD não conseguiu associá-lo ao processo %s.",
                documento["id_documento"],
                processo_id,
            )
            return jsonify({
                "ok": False,
                "mensagem": (
                    f"O SEI confirmou o cadastro do documento {documento['id_documento']}, "
                    "mas o GCPD não conseguiu registrá-lo localmente. Não repita o cadastro; "
                    "consulte o administrador do sistema."
                ),
                "documento": documento,
                "cadastro_confirmado": True,
                "resultado_incerto": True,
            }), 500
    return jsonify({"ok": True, "documento": documento}), 201


@app.get("/api/processos/<int:processo_id>/documentos-sei")
def listar_documentos_internos_sei(processo_id):
    try:
        processo = banco.obter_processo(processo_id)
        if not processo.get("id_procedimento_sei"):
            raise ValueError("Crie o processo no SEI antes de consultar os documentos.")
        documentos = banco.listar_documentos_sei(processo_id)
    except ValueError as erro:
        status = 404 if "não encontrado" in str(erro) else 400
        return jsonify({"ok": False, "mensagem": str(erro)}), status
    return jsonify({"ok": True, "documentos": documentos})


def _secao_sei_somente_leitura(valor):
    if isinstance(valor, bool):
        return valor
    texto = str(valor or "").strip().upper()
    if texto in {"N", "NAO", "NÃO", "0", "FALSE"}:
        return False
    if texto in {"S", "SIM", "1", "TRUE"}:
        return True
    return True


class _TextoHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.partes = []
        self.imagens = 0

    def handle_data(self, data):
        self.partes.append(data)

    def handle_starttag(self, tag, attrs):
        if tag == "img":
            self.imagens += 1


def _conteudo_html_preservado(esperado, recebido):
    parsers = []
    for conteudo in (esperado, recebido):
        parser = _TextoHTMLParser()
        parser.feed(unescape(str(conteudo or "")))
        parser.close()
        parsers.append(parser)
    texto_esperado = " ".join(" ".join(parsers[0].partes).split())
    texto_recebido = " ".join(" ".join(parsers[1].partes).split())
    if texto_esperado:
        return texto_esperado in texto_recebido
    return parsers[0].imagens > 0 and parsers[0].imagens == parsers[1].imagens


def _texto_util_html(html_bruto):
    """Extrai texto legível do HTML (sem tags) para validar se há conteúdo real."""
    parser = _TextoHTMLParser()
    parser.feed(unescape(str(html_bruto or "")))
    parser.close()
    return " ".join(" ".join(parser.partes).split())


def _exigir_html_substancial(conteudo_html, contexto="formulário", minimo=1):
    """Impede envio ao SEI de HTML sem texto útil (que apagaria a seção)."""
    texto = _texto_util_html(conteudo_html)
    if len(texto) < int(minimo):
        raise ValueError(
            f"O {contexto} gerou pouco ou nenhum texto útil ({len(texto)} caracteres). "
            "Informe um texto antes de enviar à seção do SEI."
        )
    return texto


def _resumo_secao_sei(indice, secao):
    # id da seção no documento (obrigatório no POST alterar) ≠ id do modelo
    id_secao_doc = str(
        secao.get("id")
        or secao.get("idSecaoDocumento")
        or secao.get("idSecao")
        or ""
    )
    id_modelo = str(
        secao.get("idSecaoModelo")
        or secao.get("idSecaoModeloSecaoDocumento")
        or ""
    )
    nome = next(
        (
            str(secao.get(chave)).strip()
            for chave in ("nomeSecao", "nomeSecaoModelo", "descricao", "nome", "titulo")
            if secao.get(chave)
        ),
        f"Seção {id_modelo or id_secao_doc or indice + 1}",
    )
    conteudo = unescape(str(secao.get("conteudo") or ""))
    return {
        "indice": indice,
        "id_secao_documento": id_secao_doc,
        "id_secao_modelo": id_modelo,
        "nome": nome,
        "somente_leitura": _secao_sei_somente_leitura(
            secao.get("somenteLeitura")
            if "somenteLeitura" in secao
            else secao.get("sinSomenteLeitura")
        ),
        "conteudo_html": sanitizar_html(conteudo),
    }


@app.post("/api/processos/<int:processo_id>/formularios/visualizar")
def visualizar_formulario_sei(processo_id):
    if not _csrf_sei_valido():
        return jsonify({"ok": False, "mensagem": "Sessão expirada. Atualize a página e tente novamente."}), 403
    try:
        processo = banco.obter_processo(processo_id)
        if not processo.get("id_procedimento_sei"):
            raise ValueError("Crie o processo no SEI antes de preparar o conteúdo.")
        bruto = _corpo_json()
        formulario_id = _texto(bruto, "formulario_id")
        catalogo = carregar_catalogo()
        formulario = documento_por_id(catalogo, formulario_id)
        if not formulario:
            raise ValueError("Selecione um formulário cadastrado válido.")
        valores = bruto.get("valores")
        if not isinstance(valores, dict):
            raise ValueError("Os dados preenchidos no formulário são inválidos.")
        ids_tags = {
            str(tag.get("id"))
            for tag in formulario.get("tags") or []
            if isinstance(tag, dict) and tag.get("id") and not tag.get("calculado")
        }
        dados_formulario = {
            "extras": {
                chave: valor
                for chave, valor in valores.items()
                if chave in ids_tags
            }
        }
        corpo_formulario = str(formulario.get("documento") or "").strip()
        if len(corpo_formulario) < 40:
            raise ValueError(
                f"O formulário “{formulario.get('nome') or formulario_id}” está sem o corpo do documento no catálogo. "
                "Abra Configurações, edite esse formulário e cole/importe o HTML completo antes de usá-lo no SEI."
            )
        # HTML do catálogo normalizado para o editor de seções do SEI
        # (classes Texto_Justificado, sem <h1>/wrappers que quebram o mod-wssei).
        # Formato Postman/SEI: só <p class="Texto_Justificado"> (sem sanitizar genérico).
        conteudo_html = html_para_secao_sei(
            gerar_documento_catalogo_html(dados_formulario, formulario)
        )
        if not conteudo_html.strip():
            raise ValueError("O formulário não gerou conteúdo HTML para visualizar.")
        _exigir_html_substancial(conteudo_html, contexto="formulário")
    except ValueError as erro:
        status = 404 if "Processo não encontrado" in str(erro) else 400
        return jsonify({"ok": False, "mensagem": str(erro)}), status
    return jsonify({
        "ok": True,
        "formulario": {"id": formulario["id"], "nome": formulario["nome"]},
        "conteudo_html": conteudo_html,
    })


@app.get("/api/processos/<int:processo_id>/documentos/<int:documento_id>/secoes")
def listar_secoes_documento_sei(processo_id, documento_id):
    sessao_sei = _sessao_sei_atual()
    if not sessao_sei:
        return jsonify({"ok": False, "mensagem": "Entre no SEI antes de consultar as seções."}), 401
    try:
        processo = banco.obter_processo(processo_id)
        if not processo.get("id_procedimento_sei"):
            raise ValueError("Crie o processo no SEI antes de consultar as seções.")
    except ValueError as erro:
        return jsonify({"ok": False, "mensagem": str(erro)}), 404
    try:
        banco.validar_documento_sei(processo_id, documento_id)
        resultado = integracao_sei.listar_secoes_documento(
            documento=str(documento_id),
            token=sessao_sei["token"],
        )
    except integracao_sei.ErroIntegracaoSEI as erro:
        if erro.status_http == 401:
            _encerrar_sessao_sei()
        return jsonify({"ok": False, "mensagem": str(erro)}), erro.status_http
    except ValueError as erro:
        codigo = 404 if "associado a este processo" in str(erro) else 400
        return jsonify({"ok": False, "mensagem": str(erro)}), codigo
    return jsonify({
        "ok": True,
        "secoes": [
            _resumo_secao_sei(indice, secao)
            for indice, secao in enumerate(resultado["secoes"])
        ],
    })


@app.post("/api/processos/<int:processo_id>/documentos/<int:documento_id>/secoes/alterar")
def alterar_secao_documento_sei(processo_id, documento_id):
    if not _csrf_sei_valido():
        return jsonify({"ok": False, "mensagem": "Sessão expirada. Atualize a página e tente novamente."}), 403
    sessao_sei = _sessao_sei_atual()
    if not sessao_sei:
        return jsonify({"ok": False, "mensagem": "Entre no SEI antes de alterar o documento."}), 401
    try:
        processo = banco.obter_processo(processo_id)
    except ValueError as erro:
        return jsonify({"ok": False, "mensagem": str(erro)}), 404
    try:
        if not processo.get("id_procedimento_sei"):
            raise ValueError("Crie o processo no SEI antes de alterar o documento.")
        bruto = _corpo_json()
        conteudo_bruto = bruto.get("conteudo_html")
        if not isinstance(conteudo_bruto, str) or not conteudo_bruto.strip():
            raise ValueError("Gere e revise a pré-visualização HTML antes de incluir o conteúdo.")
        # Sempre passa pelo pipeline SEI-safe:
        # tipografia Word (en dash, aspas curvas…) → ASCII; só <p>…</p>.
        conteudo_html = html_para_secao_sei(normalizar_caracteres_para_sei(conteudo_bruto))
        if not conteudo_html.strip():
            raise ValueError("O conteúdo HTML está vazio após a normalização para o SEI.")
        _exigir_html_substancial(conteudo_html, contexto="conteúdo a incluir no SEI", minimo=1)
        try:
            indice_secao = int(bruto.get("indice_secao"))
        except (TypeError, ValueError) as erro:
            raise ValueError("Selecione uma seção válida do documento SEI.") from erro
        if indice_secao < 0:
            raise ValueError("Selecione uma seção válida do documento SEI.")
        banco.validar_documento_sei(processo_id, documento_id)

        listagem = integracao_sei.listar_secoes_documento(
            documento=str(documento_id),
            token=sessao_sei["token"],
        )
        secoes = listagem["secoes"]
        if indice_secao >= len(secoes):
            raise ValueError("A lista de seções mudou. Atualize-a antes de alterar o documento.")
        secao_alvo = secoes[indice_secao]
        id_esperado = str(bruto.get("id_secao_modelo") or "")
        id_atual = str(
            secao_alvo.get("idSecaoModelo")
            or secao_alvo.get("idSecaoModeloSecaoDocumento")
            or ""
        )
        if id_esperado and id_atual and id_esperado != id_atual:
            raise ValueError("A seção selecionada mudou. Atualize a lista antes de continuar.")
        if _secao_sei_somente_leitura(
            secao_alvo.get("somenteLeitura")
            if "somenteLeitura" in secao_alvo
            else secao_alvo.get("sinSomenteLeitura")
        ):
            raise ValueError("A seção selecionada é somente leitura no SEI.")

        # Igual à collection Postman:
        # 1) pega a lista completa do GET listar
        # 2) troca só o conteudo da seção alvo
        # 3) preparar_secao faz unescape + remove somenteLeitura/Assinatura/...
        # 4) POST multipart com documento + secoes (JSON) + versao
        secoes_envio = []
        for indice, secao in enumerate(secoes):
            copia = dict(secao)
            if indice == indice_secao:
                copia["conteudo"] = conteudo_html
            secoes_envio.append(copia)
        integracao_sei.alterar_secoes_documento(
            documento=str(documento_id),
            secoes=secoes_envio,
            versao=listagem["versao"],
            token=sessao_sei["token"],
        )
        try:
            confirmacao = integracao_sei.listar_secoes_documento(
                documento=str(documento_id),
                token=sessao_sei["token"],
            )
        except integracao_sei.ErroIntegracaoSEI as erro:
            raise integracao_sei.ErroIntegracaoSEI(
                "O SEI recebeu a alteração, mas não foi possível confirmar o conteúdo. "
                "Consulte o documento no SEI antes de tentar novamente.",
                status_http=502,
                resultado_incerto=True,
            ) from erro
        secoes_confirmadas = confirmacao["secoes"]
        conteudo_confirmado = ""
        if indice_secao < len(secoes_confirmadas):
            conteudo_confirmado = str(
                secoes_confirmadas[indice_secao].get("conteudo") or ""
            )
        texto_confirmado = _texto_util_html(conteudo_confirmado)
        if (
            indice_secao >= len(secoes_confirmadas)
            or str(
                secoes_confirmadas[indice_secao].get("idSecaoModelo")
                or secoes_confirmadas[indice_secao].get("idSecao")
                or ""
            ) != id_atual
            or not _conteudo_html_preservado(
                conteudo_html,
                conteudo_confirmado,
            )
        ):
            detalhe_confirmacao = (
                f" Após a gravação, a seção no SEI ficou com {len(texto_confirmado)} caracteres de texto."
                if texto_confirmado
                else " Após a gravação, a seção no SEI voltou vazia (0 caracteres de texto)."
            )
            raise integracao_sei.ErroIntegracaoSEI(
                "O SEI recebeu a alteração, mas não confirmou o conteúdo HTML na seção selecionada."
                + detalhe_confirmacao
                + " Consulte o documento no SEI antes de tentar novamente. "
                "Dica: use um formulário do catálogo compatível com o tipo documental "
                "(ex.: Relatório de Justificativa para série de Relatório) e confira se a prévia "
                "mostra o texto completo.",
                status_http=502,
                resultado_incerto=True,
            )
    except integracao_sei.ErroIntegracaoSEI as erro:
        if erro.status_http == 401:
            _encerrar_sessao_sei()
        return jsonify({
            "ok": False,
            "mensagem": str(erro),
            "resultado_incerto": erro.resultado_incerto,
        }), erro.status_http
    except ValueError as erro:
        codigo = 404 if "associado a este processo" in str(erro) else 400
        return jsonify({"ok": False, "mensagem": str(erro)}), codigo
    except (KeyError, TypeError) as erro:
        app.logger.exception(
            "Falha ao alterar a seção do documento %s no processo %s.",
            documento_id,
            processo_id,
        )
        return jsonify({
            "ok": False,
            "mensagem": f"Não foi possível preparar ou alterar o conteúdo HTML: {erro}",
        }), 500
    return jsonify({"ok": True, "mensagem": "Conteúdo enviado à seção selecionada no SEI."})


@app.put("/api/processos/<int:processo_id>")
def salvar_processo(processo_id):
    bruto = request.get_json(force=True, silent=False) or {}
    try:
        dados = normalizar(bruto)
        processo = banco.atualizar_processo(
            processo_id,
            cadastro=dados,
            assunto=dados["assunto"],
        )
    except ValueError as erro:
        return jsonify({"ok": False, "mensagem": str(erro)}), 400
    return jsonify({"ok": True, "processo": processo})


@app.post("/api/processos/<int:processo_id>/sei")
def enviar_processo_sei(processo_id):
    bruto = request.get_json(force=True, silent=False) or {}
    try:
        processo = banco.enviar_sei(processo_id, bruto.get("numero_sei"))
    except ValueError as erro:
        return jsonify({"ok": False, "mensagem": str(erro)}), 400
    return jsonify({"ok": True, "processo": processo})


def _apagar_pasta_saida(pasta_id):
    identificador = str(pasta_id or "").strip()
    if not identificador or "/" in identificador or "\\" in identificador or ".." in identificador:
        return
    pasta = (SAIDA / identificador).resolve()
    try:
        if SAIDA.resolve() not in pasta.parents:
            return
    except OSError:
        return
    if pasta.is_dir():
        shutil.rmtree(pasta, ignore_errors=True)


@app.delete("/api/processos/<int:processo_id>")
def excluir_processo(processo_id):
    try:
        removidos = banco.excluir_processos([processo_id])
    except ValueError as erro:
        return jsonify({"ok": False, "mensagem": str(erro)}), 400
    for item in removidos:
        _apagar_pasta_saida(item.get("pasta_id"))
    return jsonify({
        "ok": True,
        "excluidos": len(removidos),
        "processos": removidos,
        "mensagem": (
            f"Processo {removidos[0]['codigo'] or removidos[0]['numero_sei'] or removidos[0]['id']} excluído."
        ),
    })


@app.delete("/api/processos")
def excluir_processos():
    bruto = request.get_json(force=True, silent=True) or {}
    ids = bruto.get("ids") if isinstance(bruto, dict) else None
    if ids is None and request.args.get("ids"):
        ids = request.args.get("ids").split(",")
    try:
        removidos = banco.excluir_processos(ids or [])
    except ValueError as erro:
        return jsonify({"ok": False, "mensagem": str(erro)}), 400
    for item in removidos:
        _apagar_pasta_saida(item.get("pasta_id"))
    qtd = len(removidos)
    if qtd == 1:
        identificador = (
            removidos[0]["codigo"]
            or removidos[0]["numero_sei"]
            or removidos[0]["id"]
        )
        mensagem = f"Processo {identificador} excluído."
    else:
        mensagem = f"{qtd} processos excluídos."
    return jsonify({
        "ok": True,
        "excluidos": qtd,
        "processos": removidos,
        "mensagem": mensagem,
    })


@app.post("/api/gerar")
def gerar():
    bruto = request.get_json(force=True, silent=False) or {}
    processo_id = bruto.pop("processo_id", None)
    tipo_processo = str(bruto.pop("tipo_processo", "") or "").strip() or "Abertura"
    docs_ids = _ids_geracao(bruto)
    bruto.pop("documentos_ids", None)
    bruto.pop("documentos", None)
    if tipo_processo not in {"Abertura", "Aditamento", "Prorrogação"}:
        tipo_processo = "Abertura"
    if not docs_ids:
        return jsonify({"ok": False, "mensagem": "Selecione ao menos um documento para gerar."}), 400
    try:
        dados = normalizar(bruto, exigir_pacote_completo=_precisa_pacote_completo(docs_ids))
    except ValueError as erro:
        return jsonify({"ok": False, "mensagem": str(erro)}), 400

    cat = carregar_catalogo()
    mapa_catalogo = {d["id"]: d for d in cat["documentos"]}
    mapa_sistema = {d["id"]: d for d in DOCS_SISTEMA}

    identificador = uuid.uuid4().hex
    pasta = SAIDA / identificador
    pasta.mkdir(parents=True)
    gerados = []

    for doc_id in docs_ids:
        if doc_id == ID_RJ or (doc_id in mapa_catalogo and mapa_catalogo[doc_id].get("id") == ID_RJ):
            arquivo = NOMES["relatorio"]
            gerar_relatorio(dados, pasta / arquivo)
            gerados.append({"slug": "relatorio", "nome": "Relatório de Justificativa", "arquivo": arquivo})
            continue
        if doc_id == "termo_de_referencia" or mapa_sistema.get(doc_id, {}).get("gerador") == "termo":
            arquivo = NOMES["termo"]
            gerar_termo(dados, pasta / arquivo)
            gerados.append({"slug": "termo", "nome": "Termo de Referência", "arquivo": arquivo})
            continue
        if doc_id == "pesquisa_salarial" or mapa_sistema.get(doc_id, {}).get("gerador") == "pesquisa":
            arquivo = NOMES["pesquisa"]
            gerar_pesquisa(dados, pasta / arquivo)
            gerados.append({"slug": "pesquisa", "nome": "Pesquisa Salarial", "arquivo": arquivo})
            continue
        cfg = mapa_catalogo.get(doc_id)
        if not cfg:
            return jsonify({"ok": False, "mensagem": f"Documento não encontrado: {doc_id}"}), 400
        slug = _slug_arquivo(cfg["id"])
        arquivo = f"{slug}.docx"
        gerar_documento_catalogo(dados, cfg, pasta / arquivo)
        gerados.append({"slug": slug, "nome": cfg.get("nome") or cfg["id"], "arquivo": arquivo})

    if not gerados:
        return jsonify({"ok": False, "mensagem": "Nenhum documento foi gerado."}), 400

    try:
        if processo_id:
            processo = banco.atualizar_processo(
                int(processo_id),
                cadastro={**dados, "documentos_ids": docs_ids},
                assunto=dados["assunto"],
                pasta_id=identificador,
            )
        else:
            processo = banco.criar_processo(
                tipo=tipo_processo,
                assunto=dados["assunto"],
                pasta_id=identificador,
                numero_sei="",
                cadastro={**dados, "documentos_ids": docs_ids},
            )
    except ValueError as erro:
        return jsonify({"ok": False, "mensagem": str(erro)}), 400
    return jsonify({
        "ok": True,
        "id": identificador,
        "processo": processo,
        "documentos": gerados,
    })


@app.get("/arquivo/<identificador>/<nome>")
def baixar(identificador, nome):
    try:
        pasta = _pasta(identificador)
    except ValueError:
        return "Arquivo não encontrado.", 404
    # Impede path traversal; aceita qualquer arquivo gerado na pasta.
    if "/" in nome or "\\" in nome or nome.startswith("."):
        return "Arquivo não encontrado.", 404
    alvo = pasta / nome
    if not alvo.is_file() or alvo.parent.resolve() != pasta.resolve():
        return "Arquivo não encontrado.", 404
    return send_from_directory(pasta, nome, as_attachment=True)


@app.post("/api/pdf/<identificador>/<slug>")
def pdf_gerado(identificador, slug):
    try:
        pasta = _pasta(identificador)
    except ValueError:
        return jsonify({"ok": False, "mensagem": "Geração não encontrada."}), 404
    if slug in NOMES:
        origem = pasta / NOMES[slug]
    else:
        candidato = pasta / f"{slug}.docx"
        origem = candidato if candidato.is_file() else None
        if origem is None:
            # tenta casar pelo stem
            for arq in pasta.glob("*.docx"):
                if arq.stem == slug:
                    origem = arq
                    break
    if not origem or not origem.is_file():
        return jsonify({"ok": False, "mensagem": "O Word desta geração não está mais na pasta."}), 404
    destino = origem.with_suffix(".pdf")
    try:
        convert = __import__("docx2pdf", fromlist=["convert"]).convert
    except Exception:
        return jsonify({
            "ok": False,
            "mensagem": "A biblioteca de conversão do Word não está instalada.",
        }), 500
    try:
        convert(str(origem), str(destino))
    except Exception as erro:
        return jsonify({
            "ok": False,
            "mensagem": "O Word está instalado, mas a conversão não concluiu. Feche o Word se ele estiver aberto e tente de novo. Detalhe: " + str(erro),
        }), 500
    return jsonify({"ok": True, "arquivo": destino.name})


@app.post("/api/pdf-upload")
def pdf_upload():
    arquivo = request.files.get("arquivo")
    if not arquivo or not arquivo.filename.lower().endswith(".docx"):
        return jsonify({"ok": False, "mensagem": "Envie um arquivo .docx."}), 400
    identificador = uuid.uuid4().hex
    pasta = SAIDA / identificador
    pasta.mkdir(parents=True)
    origem = pasta / "documento_corrigido.docx"
    arquivo.save(origem)
    destino = pasta / "documento_corrigido.pdf"
    try:
        convert = __import__("docx2pdf", fromlist=["convert"]).convert
    except Exception:
        return jsonify({
            "ok": False,
            "mensagem": "A biblioteca de conversão do Word não está instalada.",
        }), 500
    try:
        convert(str(origem), str(destino))
    except Exception as erro:
        return jsonify({
            "ok": False,
            "mensagem": "Não foi possível converter o Word corrigido. Feche o Word se ele estiver aberto e tente de novo. Detalhe: " + str(erro),
        }), 500
    return jsonify({"ok": True, "id": identificador, "arquivo": destino.name})


@app.post("/api/processos/criar-com-documento")
def criar_processo_com_documento():
    """Cria processo no SEI e cadastra documento interno em uma única operação.
    Retorna status parcial em caso de falha no documento (processo já criado).
    """
    if not _csrf_sei_valido():
        return jsonify({"ok": False, "mensagem": "Sessão expirada. Atualize a página e tente novamente."}), 403
    sessao_sei = _sessao_sei_atual()
    if not sessao_sei:
        return jsonify({"ok": False, "mensagem": "Entre no SEI antes de criar o processo."}), 401

    bruto = request.get_json(silent=True)
    if not isinstance(bruto, dict):
        return jsonify({"ok": False, "mensagem": "Informe os dados do processo e do documento."}), 400

    dados_processo = bruto.get("processo") or bruto
    dados_documento = bruto.get("documento") or {}

    if not isinstance(dados_processo, dict) or not isinstance(dados_documento, dict):
        return jsonify({
            "ok": False,
            "mensagem": "Estrutura inválida. Use {processo: {...}, documento: {...}}.",
        }), 400

    try:
        cadastro = normalizar(dados_processo, exigir_pacote_completo=False)
        dados_tipo = _dados_criacao_processo_sei(cadastro)
        processo = banco.reservar_novo_processo_sei(
            tipo=str(dados_processo.get("tipo_processo") or "Abertura").strip(),
            assunto=dados_tipo["assunto"],
            cadastro=cadastro,
        )
    except (ValueError, TypeError) as erro:
        return jsonify({"ok": False, "mensagem": str(erro), "etapa": "validacao"}), 400

    try:
        retorno_processo = integracao_sei.criar_processo(
            tipo_processo=dados_tipo["tipo_id"],
            especificacao=dados_tipo["especificacao"],
            observacoes=dados_tipo["observacoes"],
            nivel_acesso=dados_tipo["nivel_acesso"],
            assuntos=dados_tipo["assuntos"],
            token=sessao_sei["token"],
        )
    except integracao_sei.ErroIntegracaoSEI as erro:
        banco.falhar_criacao_sei(processo["id"], erro.resultado_incerto)
        if erro.status_http == 401:
            _encerrar_sessao_sei()
        return jsonify({
            "ok": False,
            "mensagem": str(erro),
            "etapa": "criar_processo",
            "resultado_incerto": erro.resultado_incerto,
            "processo_id": processo["id"],
        }), erro.status_http or 500

    try:
        extras = cadastro.get("extras") or {}
        extras["n_processo_sei"] = retorno_processo["protocolo"]
        cadastro["extras"] = extras
        processo = banco.concluir_criacao_sei(
            processo["id"],
            retorno_processo["id_procedimento"],
            retorno_processo["protocolo"],
            cadastro=cadastro,
        )
    except (ValueError, sqlite3.Error):
        banco.falhar_criacao_sei(processo["id"], resultado_incerto=True)
        return jsonify({
            "ok": False,
            "mensagem": (
                "Processo criado no SEI, mas falhou ao registrar localmente. "
                "Não tente criar novamente."
            ),
            "etapa": "registrar_processo",
            "resultado_incerto": True,
            "protocolo": retorno_processo.get("protocolo"),
            "id_procedimento": retorno_processo.get("id_procedimento"),
        }), 500

    documento_resultado = None
    if dados_documento and dados_documento.get("idSerie"):
        try:
            dados_documento, tipo_documento = banco.aplicar_regras_documento_sei(dados_documento)
        except ValueError as erro:
            return jsonify({
                "ok": False,
                "mensagem": (
                    f"Processo criado com sucesso ({retorno_processo.get('protocolo')}), "
                    f"mas o documento não foi enviado: {erro}"
                ),
                "etapa": "validar_documento",
                "campo_faltante": integracao_sei.extrair_campo_faltante_documento(str(erro)),
                "processo": processo,
                "protocolo": retorno_processo.get("protocolo"),
                "id_procedimento": retorno_processo.get("id_procedimento"),
            }), 400
        try:
            documento_resultado = integracao_sei.cadastrar_documento_interno(
                procedimento=retorno_processo["id_procedimento"],
                campos=dados_documento,
                token=sessao_sei["token"],
            )
            if documento_resultado.get("id_documento"):
                descricao_local = (
                    str(dados_documento.get("descricao") or "").strip()
                    or str(dados_documento.get("nomeArvore") or "").strip()
                    or tipo_documento["nome"]
                )
                banco.registrar_documento_sei(
                    processo_id=processo["id"],
                    id_documento=documento_resultado["id_documento"],
                    protocolo=documento_resultado.get("protocolo"),
                    descricao=descricao_local,
                    id_serie=tipo_documento["id"],
                    tipo_documento=tipo_documento["nome"],
                )
        except integracao_sei.ErroIntegracaoSEI as erro:
            if erro.status_http == 401:
                _encerrar_sessao_sei()
            return jsonify({
                "ok": False,
                "mensagem": (
                    f"Processo criado com sucesso ({retorno_processo.get('protocolo')}), "
                    f"mas falhou ao cadastrar o documento: {erro}"
                ),
                "etapa": "cadastrar_documento",
                "resultado_incerto": erro.resultado_incerto,
                "campo_faltante": erro.campo_faltante,
                "processo": processo,
                "protocolo": retorno_processo.get("protocolo"),
                "id_procedimento": retorno_processo.get("id_procedimento"),
            }), erro.status_http or 500
        except (ValueError, sqlite3.Error) as erro:
            return jsonify({
                "ok": False,
                "mensagem": (
                    "Processo criado e documento confirmado no SEI, "
                    f"mas falhou ao registrar localmente: {erro}"
                ),
                "etapa": "registrar_documento",
                "campo_faltante": integracao_sei.extrair_campo_faltante_documento(str(erro)),
                "processo": processo,
                "documento": documento_resultado,
                "protocolo": retorno_processo.get("protocolo"),
                "id_procedimento": retorno_processo.get("id_procedimento"),
            }), 500

    return jsonify({
        "ok": True,
        "mensagem": (
            "Processo e documento criados com sucesso."
            if documento_resultado
            else "Processo criado com sucesso."
        ),
        "processo": processo,
        "documento": documento_resultado,
        "protocolo": retorno_processo.get("protocolo"),
        "id_procedimento": retorno_processo.get("id_procedimento"),
    }), 201


if __name__ == "__main__":
    if not os.environ.get("SEI_HOMOLOGACAO_BASE_URL", "").strip():
        while True:
            try:
                base_url = input("Informe a URL base da API do SEI homologação: ")
            except EOFError as erro:
                raise RuntimeError(
                    "SEI_HOMOLOGACAO_BASE_URL não foi definida e não há terminal "
                    "disponível para informá-la."
                ) from erro
            try:
                os.environ["SEI_HOMOLOGACAO_BASE_URL"] = integracao_sei.validar_base_url(
                    base_url
                )
            except integracao_sei.ErroIntegracaoSEI as erro:
                print(str(erro))
                continue
            break
    app.run(host="127.0.0.1", port=5050, debug=False, use_reloader=False)
