# -*- coding: utf-8 -*-
"""Listas permanentes do sistema e registros de processos."""
import json
import sqlite3
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
ARQUIVO = RAIZ / "banco" / "gcpd.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS tecnologia (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL COLLATE NOCASE UNIQUE
);
CREATE TABLE IF NOT EXISTS grupo (
    id INTEGER PRIMARY KEY,
    tecnologia_id INTEGER NOT NULL REFERENCES tecnologia(id) ON DELETE CASCADE,
    nome TEXT NOT NULL COLLATE NOCASE,
    UNIQUE (tecnologia_id, nome)
);
CREATE TABLE IF NOT EXISTS servico (
    id INTEGER PRIMARY KEY,
    grupo_id INTEGER NOT NULL REFERENCES grupo(id) ON DELETE CASCADE,
    nome TEXT NOT NULL COLLATE NOCASE,
    UNIQUE (grupo_id, nome)
);
CREATE TABLE IF NOT EXISTS perfil (
    id INTEGER PRIMARY KEY,
    tecnologia_id INTEGER REFERENCES tecnologia(id) ON DELETE CASCADE,
    nome TEXT NOT NULL COLLATE NOCASE,
    UNIQUE (tecnologia_id, nome)
);
CREATE TABLE IF NOT EXISTS tipo_processo_sei (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL COLLATE NOCASE UNIQUE,
    id_sei TEXT
);
CREATE TABLE IF NOT EXISTS assunto_sei (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL COLLATE NOCASE UNIQUE,
    id_sei TEXT,
    codigo TEXT NOT NULL DEFAULT '',
    descricao TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS tipo_processo_assunto (
    tipo_processo_id_sei TEXT NOT NULL PRIMARY KEY,
    assunto_id_sei TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS tipo_documento_sei (
    id TEXT PRIMARY KEY,
    nome TEXT NOT NULL COLLATE NOCASE,
    ordem INTEGER NOT NULL,
    precisa_assunto INTEGER NOT NULL DEFAULT 0,
    precisa_numero INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS processo (
    id INTEGER PRIMARY KEY,
    codigo TEXT UNIQUE,
    tipo TEXT NOT NULL,
    numero_sei TEXT,
    id_procedimento_sei TEXT,
    assunto TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'nao_enviado',
    pasta_id TEXT,
    cadastro TEXT,
    criado_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documento_processo (
    id INTEGER PRIMARY KEY,
    processo_id INTEGER NOT NULL REFERENCES processo(id) ON DELETE CASCADE,
    nome TEXT NOT NULL,
    tipo_documento TEXT NOT NULL,
    arquivo_origem TEXT NOT NULL,
    metadados TEXT NOT NULL,
    conteudo_html TEXT NOT NULL,
    criado_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documento_sei (
    id INTEGER PRIMARY KEY,
    processo_id INTEGER NOT NULL REFERENCES processo(id) ON DELETE CASCADE,
    id_documento_sei TEXT NOT NULL UNIQUE,
    protocolo TEXT NOT NULL DEFAULT '',
    descricao TEXT NOT NULL,
    id_serie TEXT NOT NULL DEFAULT '',
    tipo_documento TEXT NOT NULL DEFAULT '',
    criado_em TEXT NOT NULL
);
"""

# id, nome, precisa_assunto, precisa_numero. Número, quando exigido, vai fixo como DDS001.
NUMERO_DOCUMENTO_FIXO = "DDS001"
TIPOS_DOCUMENTO_SEI = (
    ("423", "Declaração", 0, 0),
    ("67", "Ata", 0, 0),
    ("80", "Carta", 0, 0),
    ("37", "Contrato", 0, 1),
    ("940", "DER: Req. para circulação em trecho com restrição", 0, 0),
    ("935", "DER: Requerimento CADIN Estadual", 0, 0),
    ("933", "DER: Requerimento de desvinculação de multas", 0, 0),
    ("417", "DETRAN - Requerimento Agendamento de Exame Prático", 0, 0),
    ("523", "DOE: Aviso de Licitação", 0, 0),
    ("518", "DOE: Decreto Não Numerado", 0, 0),
    ("524", "DOE: Decreto Numerado", 0, 0),
    ("522", "DOE: Despacho (Executivo I - Normativo)", 0, 0),
    ("517", "DOE: Resolução (Executivo II - Pessoal)", 0, 0),
    ("5", "Despacho", 0, 0),
    ("1146", "IPEM: Requerimento de restituição", 0, 0),
    ("741", "Informações Inciais - Oferta de Precatórios", 0, 0),
    ("11", "Ofício", 0, 1),
    ("996", "PGE Informações iniciais - Certidão positiva", 0, 0),
    ("1029", "PGE: Ajuizamento Prioritário - Pessoa Física", 0, 0),
    ("1053", "PGE: ITBI - Inventário/Arrolamento", 0, 0),
    ("1144", "PGE: Revisão de Multa", 0, 0),
    ("334", "Relatório de Justificativa - OS", 0, 0),
    ("658", "Requerimento Jucesp", 0, 0),
    ("311", "Requerimento SP", 0, 0),
    ("64", "Requerimento", 0, 0),
    ("1034", "SPPREV Requerimento - Entidades de Classe", 0, 0),
    ("90", "Termo", 0, 0),
    ("420", "Z001T Requerimento", 0, 0),
)


def conectar():
    ARQUIVO.parent.mkdir(exist_ok=True)
    conexao = sqlite3.connect(ARQUIVO)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    return conexao


def _nome(valor):
    texto = str(valor or "").strip()
    if not texto:
        raise ValueError("Informe um nome para gravar na lista.")
    return texto


def iniciar():
    # Semeia AWS/Dynamics só na criação; tipos do fluxo ficam sempre disponíveis.
    banco_novo = not ARQUIVO.exists()
    with conectar() as conexao:
        conexao.executescript(SCHEMA)
        colunas_documento_sei = {
            linha["name"]
            for linha in conexao.execute("PRAGMA table_info(documento_sei)").fetchall()
        }
        for coluna in ("id_serie", "tipo_documento"):
            if coluna not in colunas_documento_sei:
                conexao.execute(
                    f"ALTER TABLE documento_sei ADD COLUMN {coluna} TEXT NOT NULL DEFAULT ''"
                )
        colunas_tipo_documento = {
            linha["name"]
            for linha in conexao.execute("PRAGMA table_info(tipo_documento_sei)").fetchall()
        }
        if "precisa_assunto" not in colunas_tipo_documento:
            conexao.execute(
                "ALTER TABLE tipo_documento_sei ADD COLUMN precisa_assunto INTEGER NOT NULL DEFAULT 0"
            )
        if "precisa_numero" not in colunas_tipo_documento:
            conexao.execute(
                "ALTER TABLE tipo_documento_sei ADD COLUMN precisa_numero INTEGER NOT NULL DEFAULT 0"
            )
        conexao.executemany(
            """
            INSERT INTO tipo_documento_sei (id, nome, ordem, precisa_assunto, precisa_numero)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                nome = excluded.nome,
                ordem = excluded.ordem,
                precisa_assunto = excluded.precisa_assunto,
                precisa_numero = excluded.precisa_numero
            """,
            (
                (identificador, nome, ordem, assunto, numero)
                for ordem, (identificador, nome, assunto, numero) in enumerate(TIPOS_DOCUMENTO_SEI)
            ),
        )
        ids_ativos = tuple(item[0] for item in TIPOS_DOCUMENTO_SEI)
        conexao.execute(
            f"DELETE FROM tipo_documento_sei WHERE id NOT IN ({','.join('?' for _ in ids_ativos)})",
            ids_ativos,
        )
        colunas_tipo_processo = {
            linha["name"]
            for linha in conexao.execute("PRAGMA table_info(tipo_processo_sei)").fetchall()
        }
        if "id_sei" not in colunas_tipo_processo:
            conexao.execute("ALTER TABLE tipo_processo_sei ADD COLUMN id_sei TEXT")
        conexao.execute(
            """
            UPDATE tipo_processo_sei
            SET nome = ?
            WHERE nome = ?
              AND NOT EXISTS (
                  SELECT 1 FROM tipo_processo_sei WHERE nome = ?
              )
            """,
            (
                "Processo de Contratação de Serviço Técnico Profissional Especializado",
                "Processo de Contratação de Serviços Técnicos Profissional Especializado",
                "Processo de Contratação de Serviço Técnico Profissional Especializado",
            ),
        )
        conexao.execute(
            """
            INSERT INTO tipo_processo_sei (nome, id_sei)
            VALUES (?, ?)
            ON CONFLICT(nome) DO UPDATE SET id_sei = excluded.id_sei
            """,
            (
                "Processo de Contratação de Serviço Técnico Profissional Especializado",
                "100000692",
            ),
        )
        # Semeia a lista oficial de tipos de processo do SEI (homologação).
        _semear_tipos_processo_sei(conexao)
        colunas_assunto = {
            linha["name"]
            for linha in conexao.execute("PRAGMA table_info(assunto_sei)").fetchall()
        }
        if "codigo" not in colunas_assunto:
            conexao.execute(
                "ALTER TABLE assunto_sei ADD COLUMN codigo TEXT NOT NULL DEFAULT ''"
            )
        if "descricao" not in colunas_assunto:
            conexao.execute(
                "ALTER TABLE assunto_sei ADD COLUMN descricao TEXT NOT NULL DEFAULT ''"
            )
        conexao.execute(
            """
            CREATE TABLE IF NOT EXISTS tipo_processo_assunto (
                tipo_processo_id_sei TEXT NOT NULL PRIMARY KEY,
                assunto_id_sei TEXT NOT NULL DEFAULT ''
            )
            """
        )
        # Semeia a lista oficial de assuntos do SEI.
        _semear_assuntos_sei(conexao)
        _semear_tipo_processo_assunto(conexao)
        colunas = {
            linha["name"]
            for linha in conexao.execute("PRAGMA table_info(processo)").fetchall()
        }
        if colunas and "cadastro" not in colunas:
            conexao.execute("ALTER TABLE processo ADD COLUMN cadastro TEXT")
        if colunas and "id_procedimento_sei" not in colunas:
            conexao.execute("ALTER TABLE processo ADD COLUMN id_procedimento_sei TEXT")
        coluna_codigo = next(
            (linha for linha in conexao.execute("PRAGMA table_info(processo)") if linha["name"] == "codigo"),
            None,
        )
        if coluna_codigo and coluna_codigo["notnull"]:
            conexao.commit()
            conexao.execute("PRAGMA foreign_keys = OFF")
            try:
                conexao.execute("BEGIN IMMEDIATE")
                conexao.execute(
                    """
                    CREATE TABLE processo_novo (
                        id INTEGER PRIMARY KEY,
                        codigo TEXT UNIQUE,
                        tipo TEXT NOT NULL,
                        numero_sei TEXT,
                        id_procedimento_sei TEXT,
                        assunto TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'nao_enviado',
                        pasta_id TEXT,
                        cadastro TEXT,
                        criado_em TEXT NOT NULL
                    )
                    """
                )
                conexao.execute(
                    """
                    INSERT INTO processo_novo
                    (id, codigo, tipo, numero_sei, id_procedimento_sei, assunto, status, pasta_id, cadastro, criado_em)
                    SELECT id, codigo, tipo, numero_sei, id_procedimento_sei, assunto, status, pasta_id, cadastro, criado_em
                    FROM processo
                    """
                )
                conexao.execute("DROP TABLE processo")
                conexao.execute("ALTER TABLE processo_novo RENAME TO processo")
                conexao.commit()
            except Exception:
                conexao.rollback()
                raise
            finally:
                conexao.execute("PRAGMA foreign_keys = ON")
        if banco_novo:
            _semear(conexao)


def _semear_tipos_processo_sei(conexao):
    """Carrega os tipos de processo oficiais do SEI (arquivo JSON) no SQLite."""
    arquivo = Path(__file__).resolve().parent / "banco" / "tipos_processo_sei.json"
    if not arquivo.exists():
        return
    try:
        tipos = json.loads(arquivo.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(tipos, list):
        return
    registros = [
        (str(item.get("nome") or "").strip(), str(item.get("id_sei") or "").strip())
        for item in tipos
        if isinstance(item, dict) and str(item.get("nome") or "").strip() and str(item.get("id_sei") or "").strip()
    ]
    if not registros:
        return
    conexao.executemany(
        """
        INSERT INTO tipo_processo_sei (nome, id_sei)
        VALUES (?, ?)
        ON CONFLICT(nome) DO UPDATE SET id_sei = excluded.id_sei
        """,
        registros,
    )


def _semear_assuntos_sei(conexao):
    """Carrega os assuntos oficiais do SEI (arquivo JSON) no SQLite."""
    arquivo = Path(__file__).resolve().parent / "banco" / "assuntos_sei.json"
    if not arquivo.exists():
        return
    try:
        assuntos = json.loads(arquivo.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(assuntos, list):
        return
    registros = []
    for item in assuntos:
        if not isinstance(item, dict):
            continue
        id_sei = str(item.get("id_sei") or "").strip()
        codigo = str(item.get("codigo") or "").strip()
        descricao = str(item.get("descricao") or "").strip()
        nome = str(item.get("nome") or "").strip()
        if not nome and codigo and descricao:
            nome = f"{codigo} - {descricao}"
        if not nome and descricao:
            nome = descricao
        if not nome or not id_sei:
            continue
        if not descricao and " - " in nome:
            codigo_nome, _, resto = nome.partition(" - ")
            if not codigo:
                codigo = codigo_nome.strip()
            descricao = resto.strip() or nome
        registros.append((nome, id_sei, codigo, descricao or nome))
    if not registros:
        return
    for nome, id_sei, codigo, descricao in registros:
        existente = conexao.execute(
            "SELECT id, nome FROM assunto_sei WHERE id_sei = ?",
            (id_sei,),
        ).fetchone()
        if existente:
            conexao.execute(
                """
                UPDATE assunto_sei
                SET nome = ?, codigo = ?, descricao = ?
                WHERE id = ?
                """,
                (nome, codigo, descricao, existente["id"]),
            )
            continue
        conexao.execute(
            """
            INSERT INTO assunto_sei (nome, id_sei, codigo, descricao)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(nome) DO UPDATE SET
                id_sei = excluded.id_sei,
                codigo = excluded.codigo,
                descricao = excluded.descricao
            """,
            (nome, id_sei, codigo, descricao),
        )


def _semear_tipo_processo_assunto(conexao):
    """Carrega a relação Tipo de Processo ↔ Assunto a partir do JSON da planilha."""
    arquivo = Path(__file__).resolve().parent / "banco" / "tipo_processo_assunto.json"
    if not arquivo.exists():
        return
    try:
        itens = json.loads(arquivo.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(itens, list):
        return
    for item in itens:
        if not isinstance(item, dict):
            continue
        id_proc = str(item.get("tipo_processo_id_sei") or "").strip()
        nome = str(item.get("tipo_processo_nome") or "").strip()
        id_assunto = str(item.get("assunto_id_sei") or "").strip()
        if not id_proc:
            continue
        if nome:
            conexao.execute(
                """
                INSERT INTO tipo_processo_sei (nome, id_sei)
                VALUES (?, ?)
                ON CONFLICT(nome) DO UPDATE SET id_sei = excluded.id_sei
                """,
                (nome, id_proc),
            )
            # Garante id_sei mesmo se o nome já existia com outro id.
            conexao.execute(
                "UPDATE tipo_processo_sei SET id_sei = ? WHERE nome = ?",
                (id_proc, nome),
            )
        conexao.execute(
            """
            INSERT INTO tipo_processo_assunto (tipo_processo_id_sei, assunto_id_sei)
            VALUES (?, ?)
            ON CONFLICT(tipo_processo_id_sei) DO UPDATE SET
                assunto_id_sei = excluded.assunto_id_sei
            """,
            (id_proc, id_assunto),
        )


def listar_assuntos_sei():
    with conectar() as conexao:
        return [
            {
                "id": linha["id"],
                "nome": linha["nome"],
                "id_sei": linha["id_sei"] or "",
                "codigo": linha["codigo"] or "",
                "descricao": linha["descricao"] or "",
            }
            for linha in conexao.execute(
                """
                SELECT id, nome, id_sei,
                       COALESCE(codigo, '') AS codigo,
                       COALESCE(descricao, '') AS descricao
                FROM assunto_sei
                ORDER BY nome
                """
            ).fetchall()
        ]


def obter_assunto_por_id_sei(id_sei):
    identificador = str(id_sei or "").strip()
    if not identificador:
        return None
    with conectar() as conexao:
        linha = conexao.execute(
            """
            SELECT id, nome, id_sei,
                   COALESCE(codigo, '') AS codigo,
                   COALESCE(descricao, '') AS descricao
            FROM assunto_sei
            WHERE id_sei = ?
            """,
            (identificador,),
        ).fetchone()
    return dict(linha) if linha else None


def obter_id_sei_assunto(nome):
    nome = str(nome or "").strip()
    if not nome:
        return ""
    with conectar() as conexao:
        linha = conexao.execute(
            "SELECT id_sei FROM assunto_sei WHERE nome = ?",
            (nome,),
        ).fetchone()
        if linha:
            return str(linha["id_sei"] or "")
        linha = conexao.execute(
            "SELECT id_sei FROM assunto_sei WHERE id_sei = ?",
            (nome,),
        ).fetchone()
    return str(linha["id_sei"] or "") if linha else ""


def listar_relacoes_processo_assunto():
    with conectar() as conexao:
        linhas = conexao.execute(
            """
            SELECT
                COALESCE(t.id_sei, r.tipo_processo_id_sei) AS tipo_processo_id_sei,
                COALESCE(t.nome, '') AS tipo_processo_nome,
                COALESCE(r.assunto_id_sei, '') AS assunto_id_sei,
                COALESCE(a.nome, '') AS assunto_nome,
                COALESCE(a.codigo, '') AS assunto_codigo,
                COALESCE(a.descricao, '') AS assunto_descricao
            FROM tipo_processo_sei t
            LEFT JOIN tipo_processo_assunto r
                ON r.tipo_processo_id_sei = t.id_sei
            LEFT JOIN assunto_sei a
                ON a.id_sei = r.assunto_id_sei
            WHERE TRIM(COALESCE(t.id_sei, '')) != ''
            ORDER BY t.nome COLLATE NOCASE
            """
        ).fetchall()
        # Inclui relações órfãs (id na planilha sem tipo local).
        orfas = conexao.execute(
            """
            SELECT
                r.tipo_processo_id_sei AS tipo_processo_id_sei,
                '' AS tipo_processo_nome,
                COALESCE(r.assunto_id_sei, '') AS assunto_id_sei,
                COALESCE(a.nome, '') AS assunto_nome,
                COALESCE(a.codigo, '') AS assunto_codigo,
                COALESCE(a.descricao, '') AS assunto_descricao
            FROM tipo_processo_assunto r
            LEFT JOIN tipo_processo_sei t
                ON t.id_sei = r.tipo_processo_id_sei
            LEFT JOIN assunto_sei a
                ON a.id_sei = r.assunto_id_sei
            WHERE t.id IS NULL
            ORDER BY r.tipo_processo_id_sei
            """
        ).fetchall()
    return [dict(linha) for linha in linhas] + [dict(linha) for linha in orfas]


def obter_assunto_do_tipo_processo(tipo_processo_id_sei="", tipo_processo_nome=""):
    id_sei = str(tipo_processo_id_sei or "").strip()
    nome = str(tipo_processo_nome or "").strip()
    with conectar() as conexao:
        if not id_sei and nome:
            linha = conexao.execute(
                "SELECT id_sei FROM tipo_processo_sei WHERE nome = ?",
                (nome,),
            ).fetchone()
            id_sei = str(linha["id_sei"] or "") if linha else ""
        if not id_sei:
            return None
        rel = conexao.execute(
            """
            SELECT assunto_id_sei
            FROM tipo_processo_assunto
            WHERE tipo_processo_id_sei = ?
            """,
            (id_sei,),
        ).fetchone()
    if not rel or not str(rel["assunto_id_sei"] or "").strip():
        return None
    assunto = obter_assunto_por_id_sei(rel["assunto_id_sei"])
    if not assunto:
        return None
    assunto = dict(assunto)
    assunto["tipo_processo_id_sei"] = id_sei
    return assunto


def salvar_relacao_processo_assunto(tipo_processo_id_sei, assunto_id_sei=""):
    id_proc = str(tipo_processo_id_sei or "").strip()
    id_assunto = str(assunto_id_sei or "").strip()
    if not id_proc:
        raise ValueError("Informe o ID SEI do tipo de processo.")
    if id_assunto and not obter_assunto_por_id_sei(id_assunto):
        raise ValueError("Assunto SEI não encontrado.")
    with conectar() as conexao:
        if id_assunto:
            conexao.execute(
                """
                INSERT INTO tipo_processo_assunto (tipo_processo_id_sei, assunto_id_sei)
                VALUES (?, ?)
                ON CONFLICT(tipo_processo_id_sei) DO UPDATE SET
                    assunto_id_sei = excluded.assunto_id_sei
                """,
                (id_proc, id_assunto),
            )
        else:
            conexao.execute(
                "DELETE FROM tipo_processo_assunto WHERE tipo_processo_id_sei = ?",
                (id_proc,),
            )
    return obter_assunto_do_tipo_processo(tipo_processo_id_sei=id_proc)


def persistir_relacoes_processo_assunto_arquivo():
    """Atualiza o JSON de seed com o estado atual do banco."""
    arquivo = Path(__file__).resolve().parent / "banco" / "tipo_processo_assunto.json"
    with conectar() as conexao:
        linhas = conexao.execute(
            """
            SELECT
                COALESCE(t.id_sei, r.tipo_processo_id_sei) AS tipo_processo_id_sei,
                COALESCE(t.nome, '') AS tipo_processo_nome,
                COALESCE(r.assunto_id_sei, '') AS assunto_id_sei
            FROM tipo_processo_sei t
            LEFT JOIN tipo_processo_assunto r
                ON r.tipo_processo_id_sei = t.id_sei
            WHERE TRIM(COALESCE(t.id_sei, '')) != ''
            ORDER BY t.nome COLLATE NOCASE
            """
        ).fetchall()
    payload = []
    for linha in linhas:
        item = {
            "tipo_processo_id_sei": linha["tipo_processo_id_sei"],
            "tipo_processo_nome": linha["tipo_processo_nome"],
        }
        if linha["assunto_id_sei"]:
            item["assunto_id_sei"] = linha["assunto_id_sei"]
        payload.append(item)
    arquivo.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(payload)


def limpar_acervo():
    """Apaga tecnologias, grupos, serviços e perfis do grid."""
    with conectar() as conexao:
        conexao.execute("DELETE FROM servico")
        conexao.execute("DELETE FROM grupo")
        conexao.execute("DELETE FROM perfil")
        conexao.execute("DELETE FROM tecnologia")
        conexao.commit()


def _semear(conexao):
    aws = _inserir_tecnologia(conexao, "Tecnologias AWS")
    _arvore(conexao, aws, {
        "Computação": ["EC2", "EKS", "ECS", "VPC", "Security Group"],
        "Armazenamento": ["S3", "EBS", "Aurora", "DynamoDB", "Redshift", "Amazon Athena", "Amazon CloudSearch", "ElastiCache"],
        "Segurança, identidade e compliance": ["AWS IAM", "GuardDuty", "AWS WAF", "Cognito", "Control Tower"],
        "Machine learning": ["Amazon Polly", "Amazon Lex", "Amazon SageMaker", "Bedrock", "Rekognition"],
        "Integração": ["AWS Step Functions", "Amazon EventBridge", "API Gateway"],
        "Gerenciamento": ["CloudWatch", "CloudFormation", "CloudTrail"],
        "Diversos": ["Lambda", "AWS IoT Core", "AWS IoT Analytics", "Migration Hub", "DataSync", "AWS Server Migration Service", "Database Migration Service"],
    })
    for nome in (
        "Arquiteto de Soluções Cloud Pleno",
        "Arquiteto de Soluções Cloud Sênior",
        "Engenheiro DevOps Cloud Sênior",
        "Desenvolvedor Cloud Pleno",
        "Desenvolvedor Cloud Sênior",
        "Gerente de Projetos Cloud Sênior",
        "Analista de Negócios/Processos/Requisitos Pleno",
        "Analista de Negócios/Processos/Requisitos Sênior",
        "Arquiteto de Infraestrutura Cloud Pleno",
        "Arquiteto de Infraestrutura Cloud Sênior",
        "Engenheiro de Segurança Cloud Sênior",
        "Cientista de Dados Pleno",
        "Cientista de Dados Sênior",
        "Engenheiro de Dados Pleno",
        "Engenheiro de Dados Sênior",
        "Engenheiro de Machine Learning e IA Pleno",
        "Engenheiro de Machine Learning e IA Sênior",
    ):
        _inserir_perfil(conexao, aws, nome)

    dynamics = _inserir_tecnologia(conexao, "Tecnologias Microsoft Dynamics e Power Apps")
    _arvore(conexao, dynamics, {
        "Microsoft Dynamics": [
            "Dynamics Sales",
            "Dynamics Customer Service",
            "Dynamics Marketing (Customer Insights - Journeys)",
            "Dynamics Field Service",
            "Dynamics Contact Center",
            "Dynamics Customer Voice",
            "Dynamics Customer Insights (Data)",
        ],
        "Power Apps": [
            "Power Apps (Canvas e Model-Driven Apps)",
            "Power Pages",
            "Power Automate",
        ],
        "Integração e extensibilidade": [
            "Microsoft Dataverse",
            "Plugins (.NET/C#)",
            "Custom Workflow Activities",
            "Web Resources (JavaScript/HTML)",
            "Power Apps Connectors",
        ],
        "Inteligência artificial": [
            "Microsoft Copilot Studio",
            "AI Builder",
            "Azure OpenAI Service",
        ],
        "Governança e segurança": [
            "Power Apps Center of Excellence",
            "Security Roles",
            "Business Units",
            "DLP Policies",
        ],
    })
    for nome in (
        "Analista Desenvolvedor Dynamics Pleno",
        "Analista Desenvolvedor Dynamics Sênior",
        "Analista de Suporte Dynamics",
        "Analista Desenvolvedor Power Apps",
        "Arquiteto Dynamics/Power Apps",
        "Gerente de Projetos",
        "Agile Scrum Master",
        "Analista de Negócios/Processos/Requisitos",
        "Designer UI/UX",
        "Analista de Teste/Qualidade",
        "Administrador de Dados",
        "Engenheiro de AI",
        "Arquiteto de Infraestrutura",
        "Engenheiro de Automação DevOps",
        "Engenheiro de Segurança SecOps",
    ):
        _inserir_perfil(conexao, dynamics, nome)


def _inserir_tecnologia(conexao, nome):
    cursor = conexao.execute("INSERT INTO tecnologia (nome) VALUES (?)", (nome,))
    return cursor.lastrowid


def _arvore(conexao, tecnologia_id, grupos):
    for grupo, servicos in grupos.items():
        grupo_id = conexao.execute(
            "INSERT INTO grupo (tecnologia_id, nome) VALUES (?, ?)",
            (tecnologia_id, grupo),
        ).lastrowid
        conexao.executemany(
            "INSERT INTO servico (grupo_id, nome) VALUES (?, ?)",
            [(grupo_id, servico) for servico in servicos],
        )


def _inserir_perfil(conexao, tecnologia_id, nome):
    conexao.execute(
        "INSERT INTO perfil (tecnologia_id, nome) VALUES (?, ?)",
        (tecnologia_id, nome),
    )


def listar():
    with conectar() as conexao:
        tecnologias = []
        for tecnologia in conexao.execute("SELECT id, nome FROM tecnologia ORDER BY nome"):
            grupos = []
            for grupo in conexao.execute(
                "SELECT id, nome FROM grupo WHERE tecnologia_id = ? ORDER BY nome",
                (tecnologia["id"],),
            ):
                servicos = [
                    {"id": linha["id"], "nome": linha["nome"]}
                    for linha in conexao.execute(
                        "SELECT id, nome FROM servico WHERE grupo_id = ? ORDER BY nome",
                        (grupo["id"],),
                    )
                ]
                grupos.append({"id": grupo["id"], "nome": grupo["nome"], "servicos": servicos})
            perfis = [
                {"id": linha["id"], "nome": linha["nome"]}
                for linha in conexao.execute(
                    "SELECT id, nome FROM perfil WHERE tecnologia_id = ? ORDER BY nome",
                    (tecnologia["id"],),
                )
            ]
            tecnologias.append({
                "id": tecnologia["id"],
                "nome": tecnologia["nome"],
                "grupos": grupos,
                "perfis": perfis,
            })
        return tecnologias


def criar_tecnologia(nome):
    nome = _nome(nome)
    with conectar() as conexao:
        try:
            cursor = conexao.execute("INSERT INTO tecnologia (nome) VALUES (?)", (nome,))
        except sqlite3.IntegrityError as erro:
            raise ValueError("Essa tecnologia já está na lista.") from erro
        return cursor.lastrowid


def criar_grupo(tecnologia_id, nome):
    nome = _nome(nome)
    with conectar() as conexao:
        if not conexao.execute("SELECT 1 FROM tecnologia WHERE id = ?", (tecnologia_id,)).fetchone():
            raise ValueError("Escolha uma tecnologia antes de gravar o grupo.")
        try:
            cursor = conexao.execute(
                "INSERT INTO grupo (tecnologia_id, nome) VALUES (?, ?)",
                (tecnologia_id, nome),
            )
        except sqlite3.IntegrityError as erro:
            raise ValueError("Esse grupo já existe nesta tecnologia.") from erro
        return cursor.lastrowid


def criar_servico(grupo_id, nome):
    nome = _nome(nome)
    with conectar() as conexao:
        if not conexao.execute("SELECT 1 FROM grupo WHERE id = ?", (grupo_id,)).fetchone():
            raise ValueError("Escolha um grupo antes de gravar o serviço.")
        try:
            cursor = conexao.execute(
                "INSERT INTO servico (grupo_id, nome) VALUES (?, ?)",
                (grupo_id, nome),
            )
        except sqlite3.IntegrityError as erro:
            raise ValueError("Esse serviço já existe neste grupo.") from erro
        return cursor.lastrowid


def criar_perfil(tecnologia_id, nome):
    nome = _nome(nome)
    with conectar() as conexao:
        if not conexao.execute("SELECT 1 FROM tecnologia WHERE id = ?", (tecnologia_id,)).fetchone():
            raise ValueError("Escolha uma tecnologia antes de gravar o perfil.")
        try:
            cursor = conexao.execute(
                "INSERT INTO perfil (tecnologia_id, nome) VALUES (?, ?)",
                (tecnologia_id, nome),
            )
        except sqlite3.IntegrityError as erro:
            raise ValueError("Esse perfil já está na lista desta tecnologia.") from erro
        return cursor.lastrowid


def listar_tipos_processo_sei():
    with conectar() as conexao:
        return [
            {
                "id": linha["id"],
                "nome": linha["nome"],
                "id_sei": linha["id_sei"] or "",
                "assunto_id_sei": linha["assunto_id_sei"] or "",
                "assunto_nome": linha["assunto_nome"] or "",
            }
            for linha in conexao.execute(
                """
                SELECT
                    t.id,
                    t.nome,
                    t.id_sei,
                    COALESCE(r.assunto_id_sei, '') AS assunto_id_sei,
                    COALESCE(a.nome, '') AS assunto_nome
                FROM tipo_processo_sei t
                LEFT JOIN tipo_processo_assunto r
                    ON r.tipo_processo_id_sei = t.id_sei
                LEFT JOIN assunto_sei a
                    ON a.id_sei = r.assunto_id_sei
                ORDER BY t.nome
                """
            )
        ]


def criar_tipo_processo_sei(nome):
    nome = _nome(nome)
    with conectar() as conexao:
        try:
            cursor = conexao.execute(
                "INSERT INTO tipo_processo_sei (nome) VALUES (?)",
                (nome,),
            )
        except sqlite3.IntegrityError as erro:
            raise ValueError("Esse tipo de processo já está na lista.") from erro
        return cursor.lastrowid


def obter_id_sei_tipo_processo(nome):
    with conectar() as conexao:
        linha = conexao.execute(
            "SELECT id_sei FROM tipo_processo_sei WHERE nome = ?",
            (str(nome or "").strip(),),
        ).fetchone()
    return linha["id_sei"] or "" if linha else ""


def _tipo_documento_dict(linha):
    return {
        "id": linha["id"],
        "nome": linha["nome"],
        "precisa_assunto": bool(linha["precisa_assunto"]),
        "precisa_numero": bool(linha["precisa_numero"]),
    }


def listar_tipos_documento_sei():
    with conectar() as conexao:
        linhas = conexao.execute(
            """
            SELECT id, nome, precisa_assunto, precisa_numero
            FROM tipo_documento_sei
            ORDER BY ordem
            """
        ).fetchall()
    return [_tipo_documento_dict(linha) for linha in linhas]


def documentos_mais_usados_por_tipo_processo(tipo_processo, limite=5):
    """Documentos SEI mais usados nos processos locais daquele tipo."""
    tipo = str(tipo_processo or "").strip()
    if not tipo:
        return []
    limite = max(1, min(int(limite or 5), 20))
    with conectar() as conexao:
        linhas = conexao.execute(
            """
            SELECT
                d.id_serie AS id,
                COALESCE(NULLIF(TRIM(d.tipo_documento), ''), t.nome) AS nome,
                COUNT(*) AS usos
            FROM documento_sei d
            JOIN processo p ON p.id = d.processo_id
            LEFT JOIN tipo_documento_sei t ON t.id = d.id_serie
            WHERE TRIM(d.id_serie) != ''
              AND json_extract(p.cadastro, '$.tipo_processo_sei') = ?
            GROUP BY d.id_serie
            ORDER BY usos DESC, nome COLLATE NOCASE
            LIMIT ?
            """,
            (tipo, limite),
        ).fetchall()
    resultado = []
    for linha in linhas:
        item = obter_tipo_documento_sei(linha["id"]) or {
            "id": linha["id"],
            "nome": linha["nome"] or linha["id"],
            "precisa_assunto": False,
            "precisa_numero": False,
        }
        item = dict(item)
        item["usos"] = int(linha["usos"] or 0)
        resultado.append(item)
    return resultado


def obter_tipo_documento_sei(identificador):
    identificador = str(identificador or "").strip()
    with conectar() as conexao:
        linha = conexao.execute(
            """
            SELECT id, nome, precisa_assunto, precisa_numero
            FROM tipo_documento_sei
            WHERE id = ?
            """,
            (identificador,),
        ).fetchone()
    return _tipo_documento_dict(linha) if linha else None


def aplicar_regras_documento_sei(campos):
    """Ajusta o payload do documento conforme a planilha de tipos.
    Número exigido não aparece na tela: vai sempre como DDS001.
    """
    if not isinstance(campos, dict):
        raise ValueError("Os dados do documento são inválidos.")
    tipo = obter_tipo_documento_sei(campos.get("idSerie"))
    if not tipo:
        raise ValueError("Selecione um tipo documental válido.")
    ajustado = dict(campos)
    if tipo["precisa_numero"]:
        ajustado["numero"] = NUMERO_DOCUMENTO_FIXO
    else:
        ajustado.pop("numero", None)
    if tipo["precisa_assunto"] and not str(ajustado.get("assuntos") or "").strip():
        raise ValueError("O tipo documental exige ao menos um assunto. [assuntos]")
    return ajustado, tipo


def adicionar_documento_processo(processo_id, nome, tipo_documento, arquivo_origem, metadados, conteudo_html):
    with conectar() as conexao:
        if not conexao.execute("SELECT 1 FROM processo WHERE id = ?", (processo_id,)).fetchone():
            raise ValueError("Processo não encontrado.")
        cursor = conexao.execute(
            """
            INSERT INTO documento_processo
                (processo_id, nome, tipo_documento, arquivo_origem, metadados, conteudo_html, criado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                processo_id,
                _nome(nome),
                _nome(tipo_documento),
                _nome(arquivo_origem),
                json.dumps(metadados, ensure_ascii=False),
                conteudo_html,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        documento_id = cursor.lastrowid
    return obter_documento_processo(documento_id)


def listar_documentos_processo(processo_id):
    with conectar() as conexao:
        if not conexao.execute("SELECT 1 FROM processo WHERE id = ?", (processo_id,)).fetchone():
            raise ValueError("Processo não encontrado.")
        linhas = conexao.execute(
            """
            SELECT id, processo_id, nome, tipo_documento, arquivo_origem, metadados, criado_em
            FROM documento_processo
            WHERE processo_id = ?
            ORDER BY id
            """,
            (processo_id,),
        ).fetchall()
        return [_linha_documento_processo(linha) for linha in linhas]


def obter_documento_processo(documento_id):
    with conectar() as conexao:
        linha = conexao.execute(
            """
            SELECT id, processo_id, nome, tipo_documento, arquivo_origem, metadados,
                   conteudo_html, criado_em
            FROM documento_processo
            WHERE id = ?
            """,
            (documento_id,),
        ).fetchone()
        if not linha:
            raise ValueError("Documento anexado não encontrado.")
        documento = _linha_documento_processo(linha)
        documento["conteudo_html"] = linha["conteudo_html"]
        return documento


def registrar_documento_sei(processo_id, id_documento, protocolo, descricao, id_serie="", tipo_documento=""):
    identificador = str(id_documento or "").strip()
    if not identificador.isdigit():
        raise ValueError("O SEI não retornou um ID numérico do documento.")
    descricao = str(descricao or "").strip()
    tipo_documento = str(tipo_documento or "").strip()
    id_serie = str(id_serie or "").strip()
    # Se o SEI já confirmou o documento, nunca bloquear o vínculo local por descrição vazia.
    if not descricao:
        descricao = tipo_documento or (f"Documento SEI {identificador}")
    with conectar() as conexao:
        processo = conexao.execute(
            "SELECT id_procedimento_sei FROM processo WHERE id = ?",
            (processo_id,),
        ).fetchone()
        if not processo:
            raise ValueError("Processo não encontrado.")
        if not processo["id_procedimento_sei"]:
            raise ValueError("Crie o processo no SEI antes de registrar o documento.")
        existente = conexao.execute(
            """
            SELECT processo_id, id_documento_sei, protocolo, descricao, id_serie, tipo_documento, criado_em
            FROM documento_sei
            WHERE id_documento_sei = ?
            """,
            (identificador,),
        ).fetchone()
        if existente:
            if existente["processo_id"] != processo_id:
                raise ValueError("O documento SEI já está associado a outro processo local.")
            return dict(existente)
        criado_em = datetime.now().isoformat(timespec="seconds")
        conexao.execute(
            """
            INSERT INTO documento_sei
                (processo_id, id_documento_sei, protocolo, descricao, id_serie, tipo_documento, criado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                processo_id,
                identificador,
                str(protocolo or "").strip(),
                descricao,
                id_serie,
                tipo_documento,
                criado_em,
            ),
        )
    return {
        "processo_id": processo_id,
        "id_documento_sei": identificador,
        "protocolo": str(protocolo or "").strip(),
        "descricao": descricao,
        "id_serie": id_serie,
        "tipo_documento": tipo_documento,
        "criado_em": criado_em,
    }


def obter_documento_sei(processo_id, id_documento):
    identificador = str(id_documento or "").strip()
    if not identificador.isdigit():
        raise ValueError("O ID do documento SEI é inválido.")
    with conectar() as conexao:
        linha = conexao.execute(
            """
            SELECT processo_id, id_documento_sei, protocolo, descricao, id_serie, tipo_documento, criado_em
            FROM documento_sei
            WHERE processo_id = ? AND id_documento_sei = ?
            """,
            (processo_id, identificador),
        ).fetchone()
    if not linha:
        raise ValueError("O documento SEI não está associado a este processo local.")
    return dict(linha)


def listar_documentos_sei(processo_id):
    with conectar() as conexao:
        if not conexao.execute("SELECT 1 FROM processo WHERE id = ?", (processo_id,)).fetchone():
            raise ValueError("Processo não encontrado.")
        linhas = conexao.execute(
            """
            SELECT processo_id, id_documento_sei, protocolo, descricao, id_serie, tipo_documento, criado_em
            FROM documento_sei
            WHERE processo_id = ?
            ORDER BY id
            """,
            (processo_id,),
        ).fetchall()
    return [dict(linha) for linha in linhas]


def validar_documento_sei(processo_id, id_documento):
    obter_documento_sei(processo_id, id_documento)


def _linha_documento_processo(linha):
    try:
        metadados = json.loads(linha["metadados"] or "{}")
    except json.JSONDecodeError:
        metadados = {}
    return {
        "id": linha["id"],
        "processo_id": linha["processo_id"],
        "nome": linha["nome"],
        "tipo_documento": linha["tipo_documento"],
        "arquivo_origem": linha["arquivo_origem"],
        "metadados": metadados,
        "criado_em": linha["criado_em"],
    }


def _linha_processo(linha, com_cadastro=False):
    try:
        cadastro = json.loads(linha["cadastro"] or "null")
    except json.JSONDecodeError:
        cadastro = None
    item = {
        "id": linha["id"],
        "codigo": linha["codigo"],
        "tipo": linha["tipo"],
        "tipo_processo_sei": (
            cadastro.get("tipo_processo_sei", "")
            if isinstance(cadastro, dict)
            else ""
        ),
        "numero_sei": linha["numero_sei"] or "",
        "id_procedimento_sei": linha["id_procedimento_sei"] or "",
        "assunto": linha["assunto"],
        "status": linha["status"],
        "pasta_id": linha["pasta_id"] or "",
        "criado_em": linha["criado_em"],
        "tem_cadastro": bool(linha["cadastro"]),
    }
    if com_cadastro:
        item["cadastro"] = cadastro
    return item


def listar_processos():
    with conectar() as conexao:
        linhas = conexao.execute(
            """
            SELECT id, codigo, tipo, numero_sei, id_procedimento_sei, assunto, status, pasta_id, cadastro, criado_em
            FROM processo
            ORDER BY id DESC
            """
        ).fetchall()
        return [_linha_processo(linha) for linha in linhas]


def obter_processo(processo_id):
    with conectar() as conexao:
        linha = conexao.execute(
            """
            SELECT id, codigo, tipo, numero_sei, id_procedimento_sei, assunto, status, pasta_id, cadastro, criado_em
            FROM processo
            WHERE id = ?
            """,
            (processo_id,),
        ).fetchone()
        if not linha:
            raise ValueError("Processo não encontrado.")
        return _linha_processo(linha, com_cadastro=True)


def criar_processo(tipo, assunto, pasta_id=None, numero_sei=None, cadastro=None):
    tipo = _nome(tipo)
    assunto = _nome(assunto)
    sei = str(numero_sei or "").strip()
    status = "enviado" if sei else "nao_enviado"
    payload = json.dumps(cadastro, ensure_ascii=False) if isinstance(cadastro, dict) else None
    with conectar() as conexao:
        ano = datetime.now().year
        ultimo = conexao.execute(
            "SELECT COUNT(*) AS n FROM processo WHERE codigo LIKE ?",
            (f"GCPD-{ano}-%",),
        ).fetchone()["n"]
        codigo = f"GCPD-{ano}-{ultimo + 1:04d}"
        cursor = conexao.execute(
            """
            INSERT INTO processo (codigo, tipo, numero_sei, assunto, status, pasta_id, cadastro, criado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                codigo,
                tipo,
                sei or None,
                assunto,
                status,
                pasta_id,
                payload,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        return {
            "id": cursor.lastrowid,
            "codigo": codigo,
            "tipo": tipo,
            "numero_sei": sei,
            "assunto": assunto,
            "status": status,
            "pasta_id": pasta_id or "",
            "tem_cadastro": bool(payload),
        }


def atualizar_processo(processo_id, cadastro=None, assunto=None, pasta_id=None):
    atual = obter_processo(processo_id)
    novo_assunto = _nome(assunto) if assunto is not None else atual["assunto"]
    payload = (
        json.dumps(cadastro, ensure_ascii=False)
        if isinstance(cadastro, dict)
        else json.dumps(atual.get("cadastro"), ensure_ascii=False)
        if atual.get("cadastro") is not None
        else None
    )
    nova_pasta = pasta_id if pasta_id is not None else (atual["pasta_id"] or None)
    with conectar() as conexao:
        conexao.execute(
            """
            UPDATE processo
            SET assunto = ?, pasta_id = ?, cadastro = ?
            WHERE id = ?
            """,
            (novo_assunto, nova_pasta, payload, processo_id),
        )
    return obter_processo(processo_id)


def enviar_sei(processo_id, numero_sei):
    sei = str(numero_sei or "").strip()
    if not sei:
        raise ValueError("Informe o número SEI.")
    atual = obter_processo(processo_id)
    if atual["status"] == "enviado" and atual["numero_sei"]:
        raise ValueError("Este processo já foi enviado ao SEI.")
    with conectar() as conexao:
        conexao.execute(
            """
            UPDATE processo
            SET numero_sei = ?, status = 'enviado', tipo = 'Vigente'
            WHERE id = ?
            """,
            (sei, processo_id),
        )
    return obter_processo(processo_id)


def reservar_criacao_sei(processo_id):
    with conectar() as conexao:
        linha = conexao.execute(
            "SELECT status, numero_sei, id_procedimento_sei FROM processo WHERE id = ?",
            (processo_id,),
        ).fetchone()
        if not linha:
            raise ValueError("Processo não encontrado.")
        if linha["id_procedimento_sei"] or linha["numero_sei"]:
            raise ValueError("Este processo já possui um número SEI registrado.")
        if linha["status"] in {"criando_sei", "criacao_indeterminada"}:
            raise ValueError(
                "A criação no SEI já foi iniciada ou ficou sem confirmação. "
                "Verifique o processo no SEI antes de qualquer nova tentativa."
            )
        if linha["status"] != "nao_enviado":
            raise ValueError("Este processo não está disponível para criação no SEI.")
        atualizada = conexao.execute(
            """
            UPDATE processo
            SET status = 'criando_sei'
            WHERE id = ?
              AND status = 'nao_enviado'
              AND COALESCE(numero_sei, '') = ''
              AND COALESCE(id_procedimento_sei, '') = ''
            """,
            (processo_id,),
        )
        if atualizada.rowcount != 1:
            raise ValueError("O estado do processo mudou. Atualize a tela e tente novamente.")


def reservar_novo_processo_sei(tipo, assunto, cadastro):
    tipo = _nome(tipo)
    assunto = _nome(assunto)
    if not isinstance(cadastro, dict):
        raise ValueError("Informe os dados do processo.")
    payload = json.dumps(cadastro, ensure_ascii=False)
    with conectar() as conexao:
        cursor = conexao.execute(
            """
            INSERT INTO processo (codigo, tipo, numero_sei, assunto, status, cadastro, criado_em)
            VALUES (NULL, ?, NULL, ?, 'criando_sei', ?, ?)
            """,
            (
                tipo,
                assunto,
                payload,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        processo_id = cursor.lastrowid
    return obter_processo(processo_id)


def concluir_criacao_sei(processo_id, id_procedimento, protocolo, cadastro=None):
    procedimento = str(id_procedimento or "").strip()
    sei = str(protocolo or "").strip()
    if not procedimento or not sei:
        raise ValueError("O SEI não retornou o ID do procedimento e o protocolo.")
    payload = None
    if isinstance(cadastro, dict):
        payload = json.dumps(cadastro, ensure_ascii=False)
    with conectar() as conexao:
        alterada = conexao.execute(
            """
            UPDATE processo
            SET numero_sei = ?, id_procedimento_sei = ?, status = 'enviado',
                cadastro = COALESCE(?, cadastro)
            WHERE id = ? AND status = 'criando_sei'
            """,
            (sei, procedimento, payload, processo_id),
        )
        if alterada.rowcount != 1:
            raise ValueError("Não foi possível registrar localmente o retorno do SEI.")
    return obter_processo(processo_id)


def falhar_criacao_sei(processo_id, resultado_incerto=False):
    status = "criacao_indeterminada" if resultado_incerto else "nao_enviado"
    with conectar() as conexao:
        conexao.execute(
            "UPDATE processo SET status = ? WHERE id = ? AND status = 'criando_sei'",
            (status, processo_id),
        )


def buscar_por_sei(numero_sei):
    sei = str(numero_sei or "").strip()
    if not sei:
        raise ValueError("Informe o número SEI.")
    with conectar() as conexao:
        linhas = conexao.execute(
            """
            SELECT id, codigo, tipo, numero_sei, id_procedimento_sei, assunto, status, pasta_id, cadastro, criado_em
            FROM processo
            WHERE trim(numero_sei) = ?
            ORDER BY id DESC
            """,
            (sei,),
        ).fetchall()
        if not linhas:
            raise ValueError("Nenhum processo com esse número SEI foi encontrado na grade (simulação).")
        return [_linha_processo(linha, com_cadastro=True) for linha in linhas]


def excluir_processos(ids):
    """Remove um ou mais processos. Devolve os registros excluídos (com pasta_id)."""
    brutos = ids if isinstance(ids, (list, tuple, set)) else [ids]
    ids_limpos = []
    vistos = set()
    for bruto in brutos:
        try:
            valor = int(bruto)
        except (TypeError, ValueError):
            continue
        if valor <= 0 or valor in vistos:
            continue
        vistos.add(valor)
        ids_limpos.append(valor)
    if not ids_limpos:
        raise ValueError("Selecione ao menos um processo para excluir.")

    with conectar() as conexao:
        placeholders = ",".join("?" for _ in ids_limpos)
        linhas = conexao.execute(
            f"""
            SELECT id, codigo, tipo, numero_sei, id_procedimento_sei, assunto, status, pasta_id, cadastro, criado_em
            FROM processo
            WHERE id IN ({placeholders})
            ORDER BY id DESC
            """,
            ids_limpos,
        ).fetchall()
        if not linhas:
            raise ValueError("Nenhum dos processos selecionados foi encontrado.")
        removidos = [_linha_processo(linha) for linha in linhas]
        conexao.execute(
            f"DELETE FROM processo WHERE id IN ({placeholders})",
            ids_limpos,
        )
    return removidos
