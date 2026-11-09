# -*- coding: utf-8 -*-
"""Configuração local das chaves de IA (Google Gemini / OpenAI)."""
from __future__ import annotations

import json
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO = RAIZ / "banco" / "config" / "ia.json"

PADRAO = {
    "provedor": "google",
    "google_api_key": "",
    "openai_api_key": "",
    "modelo_google": "gemini-3.5-flash",
    "modelo_openai": "gpt-4o-mini",
}


def _ler_arquivo():
    if not ARQUIVO.exists():
        return dict(PADRAO)
    try:
        bruto = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except Exception:
        return dict(PADRAO)
    if not isinstance(bruto, dict):
        return dict(PADRAO)
    dados = dict(PADRAO)
    dados.update({k: bruto.get(k, dados[k]) for k in PADRAO})
    return dados


def carregar_ia_config():
    dados = _ler_arquivo()
    # Variáveis de ambiente têm prioridade se preenchidas.
    google_env = (
        os.environ.get("GOOGLE_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
        or ""
    ).strip()
    openai_env = os.environ.get("OPENAI_API_KEY", "").strip()
    if google_env:
        dados["google_api_key"] = google_env
    if openai_env:
        dados["openai_api_key"] = openai_env
    modelo_g = os.environ.get("GEMINI_MODEL", "").strip()
    if modelo_g:
        dados["modelo_google"] = modelo_g
    modelo_o = os.environ.get("OPENAI_MODEL", "").strip()
    if modelo_o:
        dados["modelo_openai"] = modelo_o
    return dados


def salvar_ia_config(bruto):
    atual = _ler_arquivo()
    if not isinstance(bruto, dict):
        raise ValueError("Configuração de IA inválida.")
    if "provedor" in bruto:
        provedor = str(bruto.get("provedor") or "google").strip().lower()
        if provedor not in {"google", "openai", "auto"}:
            raise ValueError("Provedor inválido. Use google, openai ou auto.")
        atual["provedor"] = provedor
    if "google_api_key" in bruto:
        atual["google_api_key"] = str(bruto.get("google_api_key") or "").strip()
    if "openai_api_key" in bruto:
        atual["openai_api_key"] = str(bruto.get("openai_api_key") or "").strip()
    if "modelo_google" in bruto:
        atual["modelo_google"] = str(bruto.get("modelo_google") or PADRAO["modelo_google"]).strip() or PADRAO["modelo_google"]
    if "modelo_openai" in bruto:
        atual["modelo_openai"] = str(bruto.get("modelo_openai") or PADRAO["modelo_openai"]).strip() or PADRAO["modelo_openai"]
    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO.write_text(json.dumps(atual, ensure_ascii=False, indent=2), encoding="utf-8")
    return carregar_ia_config()


def _mascarar(chave):
    texto = str(chave or "").strip()
    if not texto:
        return ""
    if len(texto) <= 8:
        return "*" * len(texto)
    return f"{texto[:4]}…{texto[-4:]}"


def payload_ia_config():
    cfg = carregar_ia_config()
    google = bool(str(cfg.get("google_api_key") or "").strip())
    openai = bool(str(cfg.get("openai_api_key") or "").strip())
    return {
        "ok": True,
        "provedor": cfg.get("provedor") or "google",
        "modelo_google": cfg.get("modelo_google") or PADRAO["modelo_google"],
        "modelo_openai": cfg.get("modelo_openai") or PADRAO["modelo_openai"],
        "google_configurado": google,
        "openai_configurado": openai,
        "google_api_key_mascarada": _mascarar(cfg.get("google_api_key")),
        "openai_api_key_mascarada": _mascarar(cfg.get("openai_api_key")),
        "pronto": google or openai,
    }
