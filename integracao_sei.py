# -*- coding: utf-8 -*-
"""Cliente da API REST do SEI (homologação PRODESP / mod-wssei)."""
from __future__ import annotations

import json
import os
import re
import secrets
from html import unescape as html_unescape
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

TAMANHO_MAXIMO_RESPOSTA = 2 * 1024 * 1024
TAMANHO_MAXIMO_RESPOSTA_SECOES = 8 * 1024 * 1024
BASE_URL_PADRAO = "https://homologacao.sei.sp.gov.br/sei/modulos/mod-wssei/controlador_ws.php/api/v1"


class ErroIntegracaoSEI(Exception):
    def __init__(self, mensagem, status_http=502, resultado_incerto=False):
        super().__init__(mensagem)
        self.status_http = int(status_http or 502)
        self.resultado_incerto = bool(resultado_incerto)


def validar_base_url(valor):
    bruto = str(valor or "").strip().rstrip("/")
    if not bruto:
        raise ErroIntegracaoSEI("Informe a URL base da API do SEI.", status_http=400)
    partes = urlparse(bruto)
    if partes.scheme not in {"http", "https"} or not partes.netloc:
        raise ErroIntegracaoSEI(
            "A URL base do SEI é inválida. Use o endereço completo da API (https://...).",
            status_http=400,
        )
    return bruto


def _base_url():
    configurada = os.environ.get("SEI_HOMOLOGACAO_BASE_URL", "").strip()
    if configurada:
        return validar_base_url(configurada)
    return BASE_URL_PADRAO


def _mensagem_api(payload):
    if not isinstance(payload, dict):
        return ""
    for chave in ("mensagem", "message", "erro", "error", "detail"):
        valor = payload.get(chave)
        if isinstance(valor, str) and valor.strip():
            return valor.strip()
    data = payload.get("data")
    if isinstance(data, dict):
        for chave in ("mensagem", "message", "erro", "error"):
            valor = data.get(chave)
            if isinstance(valor, str) and valor.strip():
                return valor.strip()
    return ""


def _post_form(base_url, caminho, campos, token=None, resultado_incerto=False, timeout=30):
    cabecalhos = {"Content-Type": "application/x-www-form-urlencoded"}
    if token:
        cabecalhos["token"] = token
    pedido = Request(
        f"{base_url}/{caminho.lstrip('/')}",
        data=urlencode(campos).encode("utf-8"),
        headers=cabecalhos,
        method="POST",
    )
    try:
        with urlopen(pedido, timeout=timeout) as resposta:
            bruto = resposta.read(TAMANHO_MAXIMO_RESPOSTA_SECOES + 1)
    except HTTPError as erro:
        incerto = resultado_incerto and erro.code >= 500
        detalhe = ""
        try:
            payload = json.loads(erro.read(TAMANHO_MAXIMO_RESPOSTA).decode("utf-8"))
            detalhe = _mensagem_api(payload)
        except (UnicodeDecodeError, json.JSONDecodeError, Exception):
            pass
        mensagem = f"SEI respondeu com HTTP {erro.code}."
        if detalhe:
            mensagem = f"{mensagem} {detalhe}"
        raise ErroIntegracaoSEI(
            mensagem,
            status_http=erro.code if 400 <= erro.code < 500 else 502,
            resultado_incerto=incerto,
        ) from erro
    except (TimeoutError, URLError) as erro:
        raise ErroIntegracaoSEI(
            "Não foi possível confirmar a resposta do SEI. "
            "Verifique se o serviço de homologação está no ar antes de tentar novamente.",
            resultado_incerto=resultado_incerto,
        ) from erro

    if len(bruto) > TAMANHO_MAXIMO_RESPOSTA_SECOES:
        raise ErroIntegracaoSEI(
            "A resposta do SEI excede o tamanho esperado.",
            resultado_incerto=resultado_incerto,
        )
    try:
        dados = json.loads(bruto.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as erro:
        raise ErroIntegracaoSEI(
            "O SEI retornou uma resposta inválida.",
            resultado_incerto=resultado_incerto,
        ) from erro
    if not isinstance(dados, dict):
        raise ErroIntegracaoSEI(
            "O SEI retornou uma resposta inesperada.",
            resultado_incerto=resultado_incerto,
        )
    if dados.get("sucesso") is not True:
        raise ErroIntegracaoSEI(
            _mensagem_api(dados) or "O SEI recusou a operação.",
            status_http=502,
            resultado_incerto=resultado_incerto,
        )
    return dados


def autenticar(usuario, senha):
    base_url = _base_url()
    usuario = str(usuario or "").strip()
    if not usuario or not isinstance(senha, str) or not senha:
        raise ErroIntegracaoSEI("Informe usuário e senha do SEI.", status_http=400)
    try:
        dados = _post_form(
            base_url,
            "autenticar",
            {"usuario": usuario, "senha": senha},
            resultado_incerto=False,
            timeout=20,
        )
    except ErroIntegracaoSEI as erro:
        # Propaga 401/403/5xx com mensagem clara na tela de login.
        if erro.status_http >= 500:
            raise ErroIntegracaoSEI(
                str(erro) if str(erro) else "SEI respondeu com erro de servidor.",
                status_http=503 if "503" in str(erro) else 502,
            ) from erro
        raise

    data = dados.get("data") if isinstance(dados.get("data"), dict) else {}
    token = data.get("token") or dados.get("token")
    if not isinstance(token, str) or not token.strip():
        raise ErroIntegracaoSEI("O SEI não retornou o token de autenticação.")
    return token.strip()


def _nivel_acesso_codigo(valor):
    mapa = {
        "sigiloso": "2",
        "restrito": "1",
        "publico": "0",
        "público": "0",
        "0": "0",
        "1": "1",
        "2": "2",
    }
    chave = str(valor or "publico").strip().lower()
    return mapa.get(chave, "0")


def criar_processo(tipo_processo, especificacao, observacoes, nivel_acesso, assuntos, token):
    base_url = _base_url()
    if not isinstance(token, str) or not token:
        raise ErroIntegracaoSEI("Entre no SEI antes de criar o processo.", status_http=401)

    tipo = str(tipo_processo or "").strip()
    if not tipo:
        raise ErroIntegracaoSEI("Informe o tipo de processo SEI.", status_http=400)

    lista_assuntos = []
    if isinstance(assuntos, list):
        for item in assuntos:
            if isinstance(item, dict) and item.get("id") is not None:
                lista_assuntos.append({"id": int(item["id"]) if str(item["id"]).isdigit() else item["id"]})
            elif str(item or "").strip().isdigit():
                lista_assuntos.append({"id": int(str(item).strip())})

    campos = {
        "tipoProcesso": tipo,
        "especificacao": str(especificacao or "").strip(),
        "observacoes": str(observacoes or "").strip(),
        "nivelAcesso": _nivel_acesso_codigo(nivel_acesso),
        "hipoteseLegal": "",
        "grauSigilo": "",
        "assuntos": json.dumps(lista_assuntos, ensure_ascii=False) if lista_assuntos else "",
    }
    # assuntos no Postman às vezes vai como JSON; se vazio, omite estrutura inválida
    if not lista_assuntos:
        campos["assuntos"] = "[]"

    dados = _post_form(
        base_url,
        "processo/criar",
        campos,
        token=token,
        resultado_incerto=True,
        timeout=30,
    )
    data = dados.get("data") if isinstance(dados.get("data"), dict) else {}
    id_procedimento = (
        data.get("IdProcedimento")
        or data.get("idProcedimento")
        or data.get("id_procedimento")
    )
    protocolo = (
        data.get("ProtocoloFormatado")
        or data.get("protocoloFormatado")
        or data.get("protocolo")
    )
    if not id_procedimento:
        raise ErroIntegracaoSEI(
            "O SEI não retornou o ID do procedimento criado.",
            resultado_incerto=True,
        )
    return {
        "id_procedimento": str(id_procedimento),
        "protocolo": str(protocolo or ""),
        "bruto": data,
    }


def cadastrar_documento_interno(procedimento, campos, token):
    base_url = _base_url()
    procedimento = str(procedimento or "").strip()
    if not procedimento.isdigit():
        raise ErroIntegracaoSEI("O ID do procedimento SEI é inválido.", status_http=400)
    if not isinstance(token, str) or not token:
        raise ErroIntegracaoSEI("Entre no SEI antes de cadastrar o documento.", status_http=401)
    if not isinstance(campos, dict):
        raise ErroIntegracaoSEI("Os dados do documento são inválidos.", status_http=400)

    nomes_campos = (
        "idSerie",
        "flagProtocolo",
        "unidadesReabertura",
        "nivelAcesso",
        "idHipoteseLegal",
        "grauSigilo",
        "descricao",
        "assuntos",
        "interessados",
        "destinatarios",
        "observacao",
        "idUnidadeGeradoraProtocolo",
        "idTextoPadraoInterno",
    )
    valores = {
        nome: str(campos.get(nome) or "").strip()
        for nome in nomes_campos
    }
    if not re.fullmatch(r"-?\d+", valores["idSerie"]):
        raise ErroIntegracaoSEI(
            "Informe o ID numérico da série/tipo documental do SEI.",
            status_http=400,
        )
    if not valores["descricao"]:
        raise ErroIntegracaoSEI("Informe a descrição do documento.", status_http=400)
    if valores["nivelAcesso"] not in {"0", "1", "2"}:
        # aceita nomes e normaliza
        valores["nivelAcesso"] = _nivel_acesso_codigo(valores["nivelAcesso"] or campos.get("nivelAcesso") or "0")
        if valores["nivelAcesso"] not in {"0", "1", "2"}:
            raise ErroIntegracaoSEI("Selecione um nível de acesso válido.", status_http=400)

    boundary = f"----GCPD{secrets.token_hex(16)}"
    partes = []
    for nome, valor in valores.items():
        partes.extend((
            f"--{boundary}\r\n".encode("ascii"),
            f'Content-Disposition: form-data; name="{nome}"\r\n\r\n'.encode("ascii"),
            valor.encode("utf-8"),
            b"\r\n",
        ))
    partes.append(f"--{boundary}--\r\n".encode("ascii"))
    pedido = Request(
        f"{base_url}/documento/{procedimento}/interno/criar",
        data=b"".join(partes),
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "token": token,
        },
        method="POST",
    )
    try:
        with urlopen(pedido, timeout=30) as resposta:
            bruto = resposta.read(TAMANHO_MAXIMO_RESPOSTA + 1)
    except HTTPError as erro:
        incerto = erro.code >= 500
        detalhe = ""
        try:
            payload = json.loads(erro.read(TAMANHO_MAXIMO_RESPOSTA).decode("utf-8"))
            detalhe = _mensagem_api(payload)
        except (UnicodeDecodeError, json.JSONDecodeError, Exception):
            pass
        mensagem = f"SEI respondeu com HTTP {erro.code} ao cadastrar o documento."
        if detalhe:
            mensagem = f"{mensagem} {detalhe}"
        raise ErroIntegracaoSEI(
            mensagem,
            status_http=erro.code if 400 <= erro.code < 500 else 502,
            resultado_incerto=incerto,
        ) from erro
    except (TimeoutError, URLError) as erro:
        raise ErroIntegracaoSEI(
            "Não foi possível confirmar se o documento foi cadastrado. "
            "Verifique o processo no SEI antes de tentar novamente.",
            resultado_incerto=True,
        ) from erro

    if len(bruto) > TAMANHO_MAXIMO_RESPOSTA:
        raise ErroIntegracaoSEI(
            "A resposta do SEI excede o tamanho esperado; verifique o processo antes de tentar novamente.",
            resultado_incerto=True,
        )
    try:
        resposta = json.loads(bruto.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as erro:
        raise ErroIntegracaoSEI(
            "O SEI retornou uma resposta inválida. Verifique o processo antes de tentar novamente.",
            resultado_incerto=True,
        ) from erro
    if not isinstance(resposta, dict):
        raise ErroIntegracaoSEI(
            "O SEI retornou uma resposta inesperada. Verifique o processo antes de tentar novamente.",
            resultado_incerto=True,
        )
    if resposta.get("sucesso") is not True:
        raise ErroIntegracaoSEI(
            _mensagem_api(resposta) or "O SEI recusou o cadastro do documento.",
            status_http=502,
        )
    data = resposta.get("data") if isinstance(resposta.get("data"), dict) else {}
    id_documento = (
        data.get("idDocumento")
        or data.get("IdDocumento")
        or data.get("id_documento")
    )
    protocolo = (
        data.get("protocoloDocumentoFormatado")
        or data.get("ProtocoloDocumentoFormatado")
        or data.get("protocolo")
    )
    if not id_documento:
        raise ErroIntegracaoSEI(
            "O SEI não retornou o ID do documento criado.",
            resultado_incerto=True,
        )
    return {
        "id_documento": str(id_documento),
        "protocolo": str(protocolo or ""),
        "bruto": data,
    }


def listar_secoes_documento(documento, token):
    base_url = _base_url()
    documento = str(documento or "").strip()
    if not documento.isdigit():
        raise ErroIntegracaoSEI("O ID do documento SEI é inválido.", status_http=400)
    if not isinstance(token, str) or not token:
        raise ErroIntegracaoSEI("Entre no SEI antes de consultar as seções.", status_http=401)

    pedido = Request(
        f"{base_url}/documento/secao/listar?{urlencode({'id': documento})}",
        headers={"token": token},
        method="GET",
    )
    try:
        with urlopen(pedido, timeout=30) as resposta:
            bruto = resposta.read(TAMANHO_MAXIMO_RESPOSTA_SECOES + 1)
    except HTTPError as erro:
        detalhe = ""
        try:
            payload = json.loads(erro.read(TAMANHO_MAXIMO_RESPOSTA).decode("utf-8"))
            detalhe = _mensagem_api(payload)
        except (UnicodeDecodeError, json.JSONDecodeError, Exception):
            pass
        mensagem = f"SEI respondeu com HTTP {erro.code} ao listar as seções."
        if detalhe:
            mensagem = f"{mensagem} {detalhe}"
        raise ErroIntegracaoSEI(
            mensagem,
            status_http=erro.code if 400 <= erro.code < 500 else 502,
        ) from erro
    except (TimeoutError, URLError) as erro:
        raise ErroIntegracaoSEI(
            "Não foi possível consultar as seções do documento no SEI."
        ) from erro

    if len(bruto) > TAMANHO_MAXIMO_RESPOSTA_SECOES:
        raise ErroIntegracaoSEI("A resposta do SEI excede o tamanho esperado.")
    try:
        resposta = json.loads(bruto.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as erro:
        raise ErroIntegracaoSEI(
            "O SEI retornou uma resposta inválida ao listar as seções."
        ) from erro
    data = resposta.get("data") if isinstance(resposta, dict) else None
    secoes = data.get("secoes") if isinstance(data, dict) else None
    if (
        not isinstance(resposta, dict)
        or resposta.get("sucesso") is not True
        or not isinstance(data, dict)
        or not isinstance(secoes, list)
        or not all(isinstance(secao, dict) for secao in secoes)
    ):
        detalhe = _mensagem_api(resposta) if isinstance(resposta, dict) else ""
        raise ErroIntegracaoSEI(
            detalhe or "O SEI não retornou uma lista válida de seções."
        )
    versao = (
        data.get("ultimaVersaoDocumento")
        or data.get("versao")
        or data.get("versaoDocumento")
        or 1
    )
    return {"secoes": secoes, "versao": str(versao)}


def _desescapar_conteudo_sei(conteudo):
    """
    O GET /documento/secao/listar devolve HTML escapado (ex.: &lt;p&gt; e
    Relat&amp;oacute;rio). O Postman usa _.unescape; em conteúdo duplamente
    codificado aplicamos até 2 passes.
    """
    texto = str(conteudo or "")
    for _ in range(2):
        novo = html_unescape(texto)
        if novo == texto:
            break
        texto = novo
    return texto


def _preparar_secao_para_envio(secao):
    """
    Replica o script da collection Postman "Documento - Listar Seções" → "Alterar Seção":

      el.conteudo = _.unescape(el.conteudo);
      delete el.somenteLeitura;
      delete el.AssinaturaSecaoDocumento;
      delete el.PrincipalSecaoDocumento;
      delete el.DinamicaSecaoDocumento;
    """
    if not isinstance(secao, dict):
        return {}

    enviado = dict(secao)
    conteudo = enviado.get("conteudo")
    if conteudo is None:
        conteudo = enviado.get("Conteudo") or ""
    enviado["conteudo"] = _desescapar_conteudo_sei(conteudo)

    for chave in (
        "somenteLeitura",
        "AssinaturaSecaoDocumento",
        "PrincipalSecaoDocumento",
        "DinamicaSecaoDocumento",
        "sinSomenteLeitura",
        "sinAssinatura",
    ):
        enviado.pop(chave, None)

    if not enviado.get("id"):
        id_doc = (
            enviado.get("idSecaoDocumento")
            or enviado.get("idSecao")
            or enviado.get("IdSecaoDocumento")
            or ""
        )
        if id_doc:
            enviado["id"] = str(id_doc).strip()

    if not enviado.get("idSecaoModelo"):
        id_modelo = (
            enviado.get("IdSecaoModelo")
            or enviado.get("idSecaoModeloSecaoDocumento")
            or ""
        )
        if id_modelo:
            enviado["idSecaoModelo"] = str(id_modelo).strip()

    return enviado


def alterar_secoes_documento(documento, secoes, versao, token):
    base_url = _base_url()
    documento = str(documento or "").strip()
    if not documento.isdigit():
        raise ErroIntegracaoSEI("O ID do documento SEI é inválido.", status_http=400)
    if not isinstance(token, str) or not token:
        raise ErroIntegracaoSEI("Entre no SEI antes de alterar o documento.", status_http=401)
    if not isinstance(secoes, list) or not secoes or not all(isinstance(secao, dict) for secao in secoes):
        raise ErroIntegracaoSEI("A lista de seções do documento é inválida.", status_http=400)

    secoes_envio = [_preparar_secao_para_envio(secao) for secao in secoes]
    campos = {
        "documento": documento,
        "secoes": json.dumps(secoes_envio, ensure_ascii=False),
        "versao": str(versao or "1"),
    }

    # Collection Postman usa multipart/form-data; mantém urlencoded como fallback.
    erros = []
    for modo in ("multipart", "urlencoded"):
        try:
            if modo == "urlencoded":
                pedido = Request(
                    f"{base_url}/documento/secao/alterar",
                    data=urlencode(campos).encode("utf-8"),
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "token": token,
                    },
                    method="POST",
                )
            else:
                boundary = f"----GCPD{secrets.token_hex(16)}"
                partes = []
                for nome, valor in campos.items():
                    partes.extend((
                        f"--{boundary}\r\n".encode("ascii"),
                        f'Content-Disposition: form-data; name="{nome}"\r\n\r\n'.encode("ascii"),
                        valor.encode("utf-8"),
                        b"\r\n",
                    ))
                partes.append(f"--{boundary}--\r\n".encode("ascii"))
                pedido = Request(
                    f"{base_url}/documento/secao/alterar",
                    data=b"".join(partes),
                    headers={
                        "Content-Type": f"multipart/form-data; boundary={boundary}",
                        "token": token,
                    },
                    method="POST",
                )
            with urlopen(pedido, timeout=60) as resposta:
                bruto = resposta.read(TAMANHO_MAXIMO_RESPOSTA + 1)
        except HTTPError as erro:
            detalhe = ""
            try:
                payload = json.loads(erro.read(TAMANHO_MAXIMO_RESPOSTA).decode("utf-8"))
                detalhe = _mensagem_api(payload)
            except (UnicodeDecodeError, json.JSONDecodeError, Exception):
                pass
            mensagem = f"SEI respondeu com HTTP {erro.code} ao alterar a seção ({modo})."
            if detalhe:
                mensagem = f"{mensagem} {detalhe}"
            if erro.code >= 500:
                raise ErroIntegracaoSEI(
                    mensagem,
                    status_http=502,
                    resultado_incerto=True,
                ) from erro
            erros.append(mensagem)
            continue
        except (TimeoutError, URLError) as erro:
            erros.append(f"Falha de rede ao alterar a seção ({modo}).")
            if modo == "multipart":
                continue
            raise ErroIntegracaoSEI(
                "Não foi possível confirmar a alteração da seção. "
                "Consulte o documento no SEI antes de tentar novamente.",
                resultado_incerto=True,
            ) from erro

        if len(bruto) > TAMANHO_MAXIMO_RESPOSTA:
            raise ErroIntegracaoSEI(
                "A resposta do SEI excede o tamanho esperado. Consulte o documento antes de tentar novamente.",
                resultado_incerto=True,
            )
        try:
            resposta = json.loads(bruto.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            erros.append(f"Resposta inválida do SEI ({modo}).")
            continue
        if not isinstance(resposta, dict):
            erros.append(f"Resposta inesperada do SEI ({modo}).")
            continue
        if resposta.get("sucesso") is not True:
            detalhe = _mensagem_api(resposta)
            erros.append(detalhe or f"O SEI recusou a alteração da seção ({modo}).")
            continue
        return resposta

    raise ErroIntegracaoSEI(
        " ".join(erros) if erros else "O SEI recusou a alteração da seção.",
        status_http=502,
    )
