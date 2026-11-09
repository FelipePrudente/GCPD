# -*- coding: utf-8 -*-
"""Extrai trechos fixos dos PDFs de referência para os geradores."""
import json
import re
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "modelos"
OUT.mkdir(exist_ok=True)


def pages_text(pdf_name, footer_prefix):
    doc = fitz.open(ROOT / pdf_name)
    chunks = []
    for page in doc:
        raw = page.get_text("text")
        lines = []
        for ln in raw.splitlines():
            s = ln.strip()
            if not s:
                lines.append("")
                continue
            if s.startswith(footer_prefix):
                continue
            if re.match(r"^(Governo do Estado de São Paulo|Companhia de Processamento de Dados do Estado de São Paulo)$", s):
                continue
            lines.append(s)
        chunks.append("\n".join(lines))
    return "\n\n".join(chunks)


def juntar_linhas(texto):
    linhas = texto.splitlines()
    blocos = []
    atual = []
    for ln in linhas:
        if not ln.strip():
            if atual:
                blocos.append(" ".join(atual))
                atual = []
            continue
        atual.append(ln.strip())
    if atual:
        blocos.append(" ".join(atual))
    limpos = []
    for b in blocos:
        b = re.sub(r"\s+", " ", b).strip()
        b = b.replace(" ,", ",").replace(" .", ".")
        if len(b) < 2:
            continue
        limpos.append(b)
    return limpos


def recortar(blocos, inicio, fim):
    ini = None
    for i, b in enumerate(blocos):
        if b.startswith(inicio):
            ini = i
            break
    if ini is None:
        raise SystemExit(f"inicio nao encontrado: {inicio}")
    fin = len(blocos)
    if fim:
        for i in range(ini + 1, len(blocos)):
            if blocos[i].startswith(fim):
                fin = i
                break
    return blocos[ini:fin]


def main():
    rj = juntar_linhas(pages_text(
        "SEI_0102585311_Relatorio_de_justificativa 6.pdf",
        "Relatório de justificativa REL.GEN",
    ))
    tr = juntar_linhas(pages_text(
        "SEI_0102588543_Termo_de_Referencia 2.pdf",
        "Termo de Referência REL.GEN",
    ))
    dados = {
        "rj": {
            "unidades_medida": recortar(rj, "2.2 Unidades de Medidas", "2.3 Situação Atual"),
            "perfis_tecnicos_fixos": recortar(rj, "3.7.2 A avaliação", "3.8 Comprovação"),
            "economico": recortar(rj, "3.9 Qualificação Econômico-Financeira", "3.10 Planilha"),
            "planilha": recortar(rj, "3.10 Planilha de Composição", "3.11 Assinatura"),
            "representante": recortar(rj, "3.11.1 Representante Técnico", "3.11.2 Comprovação"),
            "cmmi": recortar(rj, "3.11.4 Comprovação de Certificação CMMI", "3.11.5 Comprovação de ISO"),
            "iso": recortar(rj, "3.11.5 Comprovação de ISO", "4. DAS OBRIGAÇÕES"),
            "obrigacoes": recortar(rj, "4. DAS OBRIGAÇÕES", "5. MODELOS DE FORMULÁRIOS"),
            "modelos": recortar(rj, "5. MODELOS DE FORMULÁRIOS", "6. RECURSOS FINANCEIROS"),
            "recursos": recortar(rj, "6. RECURSOS FINANCEIROS", "7. GESTOR"),
            "gestor": recortar(rj, "7. GESTOR E FISCAL", "8. CONCLUSÃO"),
            "atestados_regras": recortar(rj, "e) A proponente deverá apresentar", "3.8.1.2.1 Comprovação de contratação"),
        },
        "tr": {
            "introducao": recortar(tr, "1. INTRODUÇÃO", "2. ESCOPO"),
            "ambiente": recortar(tr, "2.2 Ambiente Tecnológico", "2.3 Metodologia"),
            "metodologia": recortar(tr, "2.3 Metodologia, Disciplinas", "2.4 Planejamento"),
            "planejamento": recortar(tr, "2.4 Planejamento de Projetos", "2.5 Modalidades"),
            "modalidades": recortar(tr, "2.5 Modalidades de Remuneração", "2.6 Remuneração por Análise"),
            "apf_depois": recortar(tr, "2.6.1.3 A medição dos serviços", "2.6.3 Roteiro"),
            "hst": recortar(tr, "2.7 Remuneração por Horas", "2.8 Remuneração por Sprints"),
            "sprints": recortar(tr, "2.8 Remuneração por Sprints", "2.9 Tecnologias"),
            "medicao": recortar(tr, "2.9 Tecnologias e Forma de Medição", "2.10 Proposta"),
            "proposta": recortar(tr, "2.10 Proposta Comercial", "2.11 Formação"),
            "qualificacao_fixa": recortar(tr, "3.1.1 Para execução dos serviços", "3.1.5 O tempo"),
            "formacao": recortar(tr, "3.1.6 Todos os profissionais", "3.1.8 Os profissionais"),
            "perfis_intro": recortar(tr, "3.2 Perfis Técnicos", "3.2.1 "),
            "ageis": recortar(tr, "3.4 Exigência de Declaração", "4. EXECUÇÃO"),
            "execucao": recortar(tr, "4.1 Ordem de Serviço", "4.6"),
            "entrega_sla": recortar(tr, "4.7 Entrega dos Produtos", "5. PRÁTICAS"),
            "governanca": recortar(tr, "5. PRÁTICAS DE PROTEÇÃO", "6. ELABORAÇÃO"),
        },
    }
    path = OUT / "trechos_fixos.json"
    path.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    for doc, secoes in dados.items():
        print("==", doc)
        for nome, blocos in secoes.items():
            print(f"  {nome}: {len(blocos)} blocos, {sum(len(b) for b in blocos)} chars")


if __name__ == "__main__":
    main()
