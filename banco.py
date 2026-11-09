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
    id_sei TEXT
);
CREATE TABLE IF NOT EXISTS tipo_documento_sei (
    id TEXT PRIMARY KEY,
    nome TEXT NOT NULL COLLATE NOCASE,
    ordem INTEGER NOT NULL
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

TIPOS_DOCUMENTO_SEI = (
    ("-1", "Externo"),
    ("423", "003T Declaração"),
    ("67", "Ata"),
    ("80", "Carta"),
    ("37", "Contrato"),
    ("940", "DER: Req. para circulação em trecho com restrição"),
    ("935", "DER: Requerimento CADIN Estadual"),
    ("933", "DER: Requerimento de desvinculação de multas"),
    ("417", "DETRAN - Requerimento Agendamento de Exame Prático"),
    ("523", "DOE: Aviso de Licitação"),
    ("518", "DOE: Decreto Não Numerado"),
    ("524", "DOE: Decreto Numerado"),
    ("522", "DOE: Despacho (Executivo I - Normativo)"),
    ("517", "DOE: Resolução (Executivo II - Pessoal)"),
    ("5", "Despacho"),
    ("332", "Ficha de Integração SIAFEM (Formulário)"),
    ("359", "Formulário CFC- Externo (Formulário)"),
    ("358", "Formulário CFC (Formulário)"),
    ("526", "GRAPROHAB Formulário campo identificação (Formulário)"),
    ("1146", "IPEM: Requerimento de restituição"),
    ("92", "Informaçãot"),
    ("741", "Informações Inciais - Oferta de Precatórios"),
    ("1130", "Informações Iniciais - TESTE PGE"),
    ("11", "Ofício"),
    ("996", "PGE Informações iniciais - Certidão positiva"),
    ("1029", "PGE: Ajuizamento Prioritário - Pessoa Física"),
    ("1053", "PGE: ITBI - Inventário/Arrolamento"),
    ("1144", "PGE: Revisão de Multa"),
    ("334", "Relatório de Justificativa - OS"),
    ("361", "Relatório de Justificativa (Formulário)"),
    ("658", "Requerimento Jucesp"),
    ("311", "Requerimento SP"),
    ("64", "Requerimento"),
    ("1068", "SJC - Credenciamento - EDITAL Nº SJC FID 01/2026 (Formulário)"),
    ("1034", "SPPREV Requerimento - Entidades de Classe"),
    ("90", "Termo"),
    ("420", "Z001T Requerimento"),
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
        conexao.executemany(
            """
            INSERT INTO tipo_documento_sei (id, nome, ordem)
            VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET nome = excluded.nome, ordem = excluded.ordem
            """,
            (
                (identificador, nome, ordem)
                for ordem, (identificador, nome) in enumerate(TIPOS_DOCUMENTO_SEI)
            ),
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
        # Semeia a lista oficial de assuntos do SEI.
        _semear_assuntos_sei(conexao)
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
    registros = [
        (str(item.get("nome") or "").strip(), str(item.get("id_sei") or "").strip())
        for item in assuntos
        if isinstance(item, dict) and str(item.get("nome") or "").strip() and str(item.get("id_sei") or "").strip()
    ]
    if not registros:
        return
    conexao.executemany(
        """
        INSERT INTO assunto_sei (nome, id_sei)
        VALUES (?, ?)
        ON CONFLICT(nome) DO UPDATE SET id_sei = excluded.id_sei
        """,
        registros,
    )


def listar_assuntos_sei():
    with conectar() as conexao:
        return [
            dict(linha)
            for linha in conexao.execute(
                "SELECT id, nome, id_sei FROM assunto_sei ORDER BY nome"
            ).fetchall()
        ]


def obter_id_sei_assunto(nome):
    nome = str(nome or "").strip()
    if not nome:
        return ""
    with conectar() as conexao:
        linha = conexao.execute(
            "SELECT id_sei FROM assunto_sei WHERE nome = ?",
            (nome,),
        ).fetchone()
    return str(linha["id_sei"] or "") if linha else ""


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
            {"id": linha["id"], "nome": linha["nome"], "id_sei": linha["id_sei"] or ""}
            for linha in conexao.execute(
                "SELECT id, nome, id_sei FROM tipo_processo_sei ORDER BY nome"
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


def listar_tipos_documento_sei():
    with conectar() as conexao:
        linhas = conexao.execute(
            "SELECT id, nome FROM tipo_documento_sei ORDER BY ordem"
        ).fetchall()
    return [{"id": linha["id"], "nome": linha["nome"]} for linha in linhas]


def obter_tipo_documento_sei(identificador):
    identificador = str(identificador or "").strip()
    with conectar() as conexao:
        linha = conexao.execute(
            "SELECT id, nome FROM tipo_documento_sei WHERE id = ?",
            (identificador,),
        ).fetchone()
    return dict(linha) if linha else None


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
    if not descricao:
        raise ValueError("Informe a descrição do documento SEI.")
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
                str(id_serie or "").strip(),
                str(tipo_documento or "").strip(),
                criado_em,
            ),
        )
    return {
        "processo_id": processo_id,
        "id_documento_sei": identificador,
        "protocolo": str(protocolo or "").strip(),
        "descricao": descricao,
        "id_serie": str(id_serie or "").strip(),
        "tipo_documento": str(tipo_documento or "").strip(),
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
