const chave = "gcpd-cadastro-v2";
const chaveDocumentoSeiPrefixo = "gcpd-documento-sei-em-andamento-";
const listas = {
  clientes: () => ({ cliente: "", projeto: "" }),
  perfis: () => ({ item: "", perfil: "", experiencia: "", horas: "", proporcao: "" }),
  certificacoes: () => "",
  aprovadores: () => ({ nome: "", matricula: "", cargo: "" }),
};

const CAMPOS_FORMULARIO_NATIVOS = new Set([
  "mes_ano", "prazo_meses", "codigo_relatorio", "versao_relatorio", "assunto",
  "tecnologia", "catalogo", "fatos", "cliente", "projeto", "item", "perfil",
  "experiencia", "horas", "proporcao", "total_horas", "total_por_extenso",
  "perfil_referencia", "horas_por_pf", "regra_vma", "parceria", "estudo_mercado",
  "atestados", "horas_professional", "regime_certificacao", "certificacoes",
  "area_elaboracao", "local_data", "nome", "matricula", "cargo",
  "codigo_termo", "versao_termo", "versao_sisp", "texto_elaboracao", "incluir_snap",
]);

let tagsConfiguracao = [];
let tagsCatalogoCompleto = [];
let documentosGeracao = [];
let documentosSelecionados = [];
let csrfSei = "";
const DOCS_FORMULARIO_COMPLETO = new Set([
  "relatorio_justificativa",
]);
const chaveDocsSel = "gcpd-docs-selecionados-v3";
const ASSUNTOS_SEI_IDS = {
  "006.01.10.004 - Expediente de atendimento": "708",
};
const ASSUNTO_DECRETO_PADRAO =
  "001.01.01.001 - Decreto, estatuto, código, regulamento, regimento, instrução, normativa, norma, resolução, deliberação, portaria";
const ASSUNTO_CONTRATACAO_PADRAO = "006.01.10.004 - Expediente de atendimento";
const INTERESSADO_UNIDADE_PADRAO = "GESP - TUPP";
const TIPO_PROCESSO_CONTRATACAO =
  "Processo de Contratação de Serviço Técnico Profissional Especializado";

function vazio() {
  return {
    mes_ano: "",
    codigo_relatorio: "",
    versao_relatorio: "V1.0",
    codigo_termo: "",
    versao_termo: "V1.0",
    assunto: "",
    tipo_processo_sei: "",
    tipo_processo_sei_id: "",
    processo_sei: {
      protocolo: "automatico",
      numero_protocolo: "",
      especificacao: "",
      prioridade: "",
      assuntos: [ASSUNTO_DECRETO_PADRAO],
      interessados: [],
      observacoes: "",
      nivel_acesso: "publico",
    },
    processo_contratacao: {
      especificacao: "",
      prioridade: "",
      interessados: [],
      assuntos: [],
      observacoes: "",
      nivel_acesso: "publico",
    },
    tecnologia: "",
    prazo_meses: "12",
    fatos: "",
    catalogo: [],
    clientes: [listas.clientes()],
    perfis: [listas.perfis()],
    perfil_referencia: "",
    horas_por_pf: "",
    regra_vma: "",
    versao_sisp: "3.0",
    incluir_snap: false,
    parceria: "",
    estudo_mercado: "",
    atestados: "",
    regime_certificacao: "Obrigatória no ato da contratação",
    certificacoes: [""],
    horas_professional: "",
    area_elaboracao: "",
    texto_elaboracao: "",
    local_data: "",
    aprovadores: [listas.aprovadores()],
    extras: {},
  };
}

let dados = carregar();
let acervo = [];
let tecnologiaDaArvore = dados.tecnologia;
let arvoreTecnologia = null;
let gruposAbertos = new Set();
let abrirGrupoNome = "";
let processoEmEdicao = null;
let processoSei = null;
let modoOperacao = "Abertura";
let buscaSeiModo = null;
let tiposProcessoSei = [];
let tipoProcessoSelecionado = "";
let documentosGeradosAtuais = [];
let tipoDocumentoInclusao = "DOE: Decreto Não Numerado";
let arquivoDocumentoOrigem = "";
let avisosConversaoDocumento = [];
let secoesDocumentoInternoSei = [];
let documentoSeiAtivoId = "";
let formulariosDocumentoSei = [];
let formularioDocumentoSeiSelecionado = null;
let valoresFormularioDocumentoSei = {};
let conteudoHtmlFormularioSei = "";

function carregar() {
  try {
    const salvo = JSON.parse(localStorage.getItem(chave) || "null");
    if (salvo && typeof salvo === "object") {
      const base = { ...vazio(), ...salvo };
      base.processo_sei = { ...vazio().processo_sei, ...(base.processo_sei || {}) };
      if (!Array.isArray(base.processo_sei.assuntos)) base.processo_sei.assuntos = [ASSUNTO_DECRETO_PADRAO];
      if (!Array.isArray(base.processo_sei.interessados)) base.processo_sei.interessados = [];
      base.processo_contratacao = {
        ...vazio().processo_contratacao,
        ...(base.processo_contratacao || {}),
      };
      if (!Array.isArray(base.processo_contratacao.assuntos)) {
        base.processo_contratacao.assuntos = [];
      }
      if (!Array.isArray(base.processo_contratacao.interessados)) {
        base.processo_contratacao.interessados = [];
      }
      if (!("especificacao" in base.processo_contratacao) && base.processo_contratacao.descricao) {
        base.processo_contratacao.especificacao = base.processo_contratacao.descricao;
      }
      ["processo", "interessado", "unidade", "contrato_vigente"].forEach((chaveAntiga) => delete base[chaveAntiga]);
      if (!base.extras || typeof base.extras !== "object" || Array.isArray(base.extras)) base.extras = {};
      return base;
    }
  } catch (erro) {
    /* cadastro anterior inválido */
  }
  return vazio();
}

function salvar() {
  lerFormulario();
  lerFormularioProcessoSei();
  lerFormularioContratacao();
  localStorage.setItem(chave, JSON.stringify(dados));
  atualizarTotal();
}

function lerFormularioProcessoSei() {
  const protocolo = document.querySelector('input[name="decreto-protocolo"]:checked');
  const nivelAcesso = document.querySelector('input[name="decreto-nivel-acesso"]:checked');
  const atual = dados.processo_sei || vazio().processo_sei;
  dados.processo_sei = {
    ...atual,
    protocolo: protocolo?.value || atual.protocolo,
    numero_protocolo: campo("decreto-numero-protocolo")?.value.trim() || "",
    especificacao: campo("decreto-especificacao")?.value.trim() || "",
    prioridade: campo("decreto-prioridade")?.value || "",
    observacoes: campo("decreto-observacoes")?.value.trim() || "",
    nivel_acesso: nivelAcesso?.value || atual.nivel_acesso,
  };
}

function lerFormularioContratacao() {
  if (campo("painel-contratacao")?.classList.contains("oculto")) return;
  const nivelAcesso = document.querySelector('input[name="contratacao-nivel-acesso"]:checked');
  const atual = dados.processo_contratacao || vazio().processo_contratacao;
  const especificacao = campo("contratacao-especificacao")?.value.trim() || "";
  dados.processo_contratacao = {
    ...atual,
    especificacao,
    // Compatibilidade com payload antigo que usava "descricao".
    descricao: especificacao,
    prioridade: campo("contratacao-prioridade")?.value || "",
    observacoes: campo("contratacao-observacoes")?.value.trim() || "",
    nivel_acesso: nivelAcesso?.value || atual.nivel_acesso,
  };
}

function campo(id) {
  return document.getElementById(id);
}

function tagsParaCamposExtra(tags, { forcarExtras = false } = {}) {
  return (tags || []).filter((tag) => {
    if (!tag?.id || tag.calculado) return false;
    // No modo só-catálogo, tags homônimas de campos nativos do RJ também viram extras do documento.
    if (forcarExtras) return true;
    return !CAMPOS_FORMULARIO_NATIVOS.has(tag.id);
  });
}

function gruposDaTag(tag) {
  const principal = String(tag?.grupo || "").trim();
  const lista = [];
  if (principal) lista.push(principal);
  (tag?.reuso_em || []).forEach((grupo) => {
    const nome = String(grupo || "").trim();
    if (nome && !lista.includes(nome)) lista.push(nome);
  });
  return lista;
}

function htmlCampoReuso(tag) {
  const id = escHtml(tag.id);
  const rotulo = escHtml(tag.rotulo || tag.id);
  const origem = escHtml(tag.grupo || "outro bloco");
  return `
    <div class="campo span-${larguraBaseTag(tag)} campo-reuso-ref" data-tag-id="${id}" data-tag-reuso="1" data-tag-tipo="${escHtml(tag.tipo || "texto")}">
      <label>${rotulo} <code class="tag-rotulo">{{${id}}}</code></label>
      <p class="reuso-texto">Mesmo valor de <strong>${origem}</strong> — não precisa preencher de novo.</p>
    </div>`;
}

function normalizarChaveBloco(nome) {
  return String(nome || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
}

function nomeBlocoFormulario(grupoTag) {
  const mapa = {
    identificacao: "Identificação",
    objeto: "Objeto",
    "clientes e projetos": "Clientes e projetos",
    perfis: "Perfis",
    medicao: "Medição e julgamento",
    "medicao e julgamento": "Medição e julgamento",
    habilitacao: "Habilitação da tecnologia",
    "habilitacao da tecnologia": "Habilitação da tecnologia",
    elaboracao: "Elaboração e aprovação",
    aprovacao: "Elaboração e aprovação",
    "elaboracao e aprovacao": "Elaboração e aprovação",
  };
  const chave = normalizarChaveBloco(grupoTag);
  if (mapa[chave]) return mapa[chave];
  const texto = String(grupoTag || "").trim();
  return texto || "Geral";
}

function larguraBaseTag(tag) {
  const n = Number(tag?.largura);
  return [1, 2, 3, 4].includes(n) ? n : 4;
}

function larguraDinamicaIa(tag, texto) {
  const base = larguraBaseTag(tag);
  const valor = String(texto || "");
  if (!valor.trim()) return base;
  if (valor.length > 120 || valor.includes("\n") || valor.split(/\s+/).length > 18) return 4;
  if (valor.length > 60) return Math.max(base, 3);
  return Math.max(base, 2);
}

function autoAlturaCampoIa(el) {
  if (!el || el.tagName !== "TEXTAREA") return;
  el.style.height = "auto";
  el.style.height = `${Math.max(42, el.scrollHeight)}px`;
}

function ajustarCampoIa(tagId) {
  const tag = tagsConfiguracao.find((item) => item.id === tagId);
  const campoEl = document.getElementById(`extra-${tagId}`);
  const wrap = campoEl?.closest(".campo");
  if (!campoEl || !wrap) return;
  const texto = campoEl.value || "";
  const largura = tag?.tipo === "ia_web" ? larguraDinamicaIa(tag, texto) : larguraBaseTag(tag);
  wrap.classList.remove("span-1", "span-2", "span-3", "span-4", "ia-expandido");
  wrap.classList.add(`span-${largura}`);
  if (largura === 4) wrap.classList.add("ia-expandido");
  autoAlturaCampoIa(campoEl);
}

function colunasDaTagTabela(tag) {
  return Array.isArray(tag?.colunas) ? tag.colunas.filter((c) => c?.id) : [];
}

function linhasDaTabelaExtra(tag) {
  const bruto = dados.extras?.[tag.id];
  let linhas = [];
  if (bruto && typeof bruto === "object" && !Array.isArray(bruto) && Array.isArray(bruto.linhas)) {
    linhas = bruto.linhas;
  } else if (Array.isArray(bruto)) {
    linhas = bruto;
  }
  linhas = linhas.filter((l) => l && typeof l === "object");
  if (!linhas.length) linhas = [{}];
  return linhas;
}

function valorPadraoTabela(tag) {
  const colunas = colunasDaTagTabela(tag);
  const linha = {};
  colunas.forEach((c) => { linha[c.id] = ""; });
  return { linhas: [linha] };
}

function htmlEditorTabela(tag) {
  const colunas = colunasDaTagTabela(tag);
  const linhas = linhasDaTabelaExtra(tag);
  const id = escHtml(tag.id);
  if (!colunas.length) {
    return `<p class="ajuda">Defina as colunas desta tabela em Configurações.</p>`;
  }
  const cab = colunas.map((c) => `<div class="celula-cab">${escHtml(c.rotulo || c.id)}</div>`).join("") + `<div class="celula-cab acao-cab"></div>`;
  const corpo = linhas.map((linha, idx) => {
    const celulas = colunas.map((c) => {
      const tipo = c.tipo === "numero" ? "number" : "text";
      const valor = escHtml(linha?.[c.id] ?? "");
      return `<input data-tabela-id="${id}" data-linha="${idx}" data-coluna="${escHtml(c.id)}" type="${tipo}"${tipo === "number" ? ' step="any"' : ""} value="${valor}" placeholder="${escHtml(c.rotulo || c.id)}" />`;
    }).join("");
    return `<div class="linha-tabela-extra" data-linha-idx="${idx}">${celulas}<button type="button" class="acao" data-remover-linha-tabela="${id}" data-linha="${idx}" title="Remover linha">×</button></div>`;
  }).join("");
  return `
    <div class="editor-tabela" data-editor-tabela="${id}">
      <div class="cab-tabela-extra" style="--cols:${colunas.length}">${cab}</div>
      <div class="corpo-tabela-extra" style="--cols:${colunas.length}">${corpo}</div>
      <button type="button" class="acao" data-add-linha-tabela="${id}">+ Linha</button>
    </div>`;
}

function lerTabelaDoDom(tagId) {
  const tag = tagsConfiguracao.find((item) => item.id === tagId);
  const colunas = colunasDaTagTabela(tag);
  const inputs = [...document.querySelectorAll(`[data-tabela-id="${tagId}"][data-linha][data-coluna]`)];
  const mapa = new Map();
  inputs.forEach((el) => {
    const idx = Number(el.dataset.linha);
    if (!mapa.has(idx)) mapa.set(idx, {});
    mapa.get(idx)[el.dataset.coluna] = el.value.trim();
  });
  const indices = [...mapa.keys()].sort((a, b) => a - b);
  let linhas = indices.map((idx) => {
    const linha = {};
    colunas.forEach((c) => { linha[c.id] = mapa.get(idx)?.[c.id] || ""; });
    return linha;
  });
  if (!linhas.length) {
    const vazia = {};
    colunas.forEach((c) => { vazia[c.id] = ""; });
    linhas = [vazia];
  }
  return { linhas };
}

function htmlCampoExtra(tag) {
  const tipo = tag.tipo || "texto";
  const valorBruto = dados.extras?.[tag.id] || "";
  const valor = tipo === "tabela" ? "" : escHtml(typeof valorBruto === "string" ? valorBruto : "");
  const id = escHtml(tag.id);
  const rotulo = escHtml(tag.rotulo || tag.id);
  const largura = tipo === "tabela" ? 4 : (tipo === "ia_web" ? larguraDinamicaIa(tag, valorBruto) : larguraBaseTag(tag));
  let controle = "";
  if (tipo === "tabela") {
    controle = htmlEditorTabela(tag);
  } else if (tipo === "numero") {
    controle = `<input id="extra-${id}" type="number" step="any" data-extra-id="${id}" value="${valor}" placeholder="0" />`;
  } else if (tipo === "texto_curto") {
    controle = `<input id="extra-${id}" type="text" data-extra-id="${id}" value="${valor}" placeholder="Valor para {{${id}}}" />`;
  } else if (tipo === "ia_web") {
    // Campos legados ia_web passam a ser texto comum; a busca fica no Assistente IA.
    const linhas = Math.min(12, Math.max(2, String(valorBruto).split("\n").length + (String(valorBruto).length > 80 ? 2 : 0)));
    controle = `<textarea id="extra-${id}" data-extra-id="${id}" rows="${linhas}" placeholder="Valor para {{${id}}}">${valor}</textarea>`;
  } else {
    controle = `<textarea id="extra-${id}" data-extra-id="${id}" rows="3" placeholder="Valor para {{${id}}}">${valor}</textarea>`;
  }
  const rotuloHtml = tipo === "tabela"
    ? `<label>${rotulo} <code class="tag-rotulo">{{${id}}}</code></label>`
    : `<label for="extra-${id}">${rotulo} <code class="tag-rotulo">{{${id}}}</code></label>`;
  return `
    <div class="campo span-${largura}${tipo === "ia_web" && largura === 4 ? " ia-expandido" : ""}${tipo === "tabela" ? " campo-tabela" : ""}" data-tag-tipo="${escHtml(tipo)}" data-tag-id="${id}">
      ${rotuloHtml}
      ${controle}
    </div>`;
}

let iaCampoAtual = null;

function fecharPainelIaCampo() {
  document.getElementById("painel-ia-campo")?.classList.add("oculto");
  iaCampoAtual = null;
}

function montarTextoSelecionadoIa() {
  const lista = document.getElementById("ia-campo-resultados");
  let itens = [];
  try {
    itens = JSON.parse(lista?.dataset.payload || "[]");
  } catch (erro) {
    itens = [];
  }
  const escolhidos = [...(lista?.querySelectorAll("input[data-ia-idx]:checked") || [])]
    .map((input) => itens[Number(input.dataset.iaIdx)]?.texto || "")
    .filter(Boolean);
  // Respostas objetivas curtas entram na mesma linha; textos longos preservam quebras.
  const curtas = escolhidos.every((item) => item.length <= 80 && !item.includes("\n"));
  return escolhidos.join(curtas ? "; " : "\n\n").slice(0, 2500);
}

function atualizarContadorIaCampo() {
  const destino = document.getElementById("ia-campo-texto-final");
  const contador = document.getElementById("ia-campo-contador");
  if (!destino || !contador) return;
  const n = (destino.value || "").length;
  contador.textContent = `(${n}/2500)`;
}

function sincronizarTextoFinalIa(forcar = false) {
  const destino = document.getElementById("ia-campo-texto-final");
  if (!destino) return;
  if (!forcar && destino.dataset.editado === "1") {
    atualizarContadorIaCampo();
    atualizarBotaoInserirIa();
    return;
  }
  destino.value = montarTextoSelecionadoIa();
  destino.dataset.editado = "";
  atualizarContadorIaCampo();
  atualizarBotaoInserirIa();
}

function atualizarBotaoInserirIa() {
  const botao = document.getElementById("ia-campo-inserir");
  if (!botao) return;
  const texto = document.getElementById("ia-campo-texto-final")?.value.trim() || "";
  botao.disabled = !texto;
}

function abrirPainelIaCampo(tagId) {
  const tag = tagsConfiguracao.find((item) => item.id === tagId)
    || formulariosDocumentoSei.flatMap((f) => f.tags || []).find((item) => item.id === tagId);
  const campoEl = document.getElementById(`extra-${tagId}`)
    || document.querySelector(`[data-form-sei-tag="${tagId}"]`);
  if (!tag || !campoEl) return;
  iaCampoAtual = { id: tagId, tag, historico: [], destinoSei: Boolean(campoEl.dataset.formSeiTag) };
  document.getElementById("ia-campo-titulo").textContent = `Busca por IA — ${tag.rotulo || tag.id}`;
  document.getElementById("ia-campo-ajuda").textContent =
    `O texto escolhido será inserido no campo “${tag.rotulo || tag.id}”. Definições e justificativas podem ter até 2500 caracteres.`;
  document.getElementById("ia-campo-prompt").value = tag.consulta_ia || "";
  const usarTec = document.getElementById("ia-campo-usar-tecnologia");
  if (usarTec) usarTec.checked = false;
  document.getElementById("ia-campo-resultados").innerHTML = "";
  const refino = document.getElementById("ia-campo-refino");
  if (refino) {
    refino.innerHTML = "";
    refino.classList.add("oculto");
  }
  const final = document.getElementById("ia-campo-texto-final");
  if (final) {
    final.value = "";
    final.dataset.editado = "";
  }
  document.getElementById("ia-campo-estado").textContent = "";
  const erro = document.getElementById("ia-campo-erro");
  erro.classList.add("oculto");
  erro.textContent = "";
  atualizarContadorIaCampo();
  atualizarBotaoInserirIa();
  document.getElementById("painel-ia-campo").classList.remove("oculto");
  document.getElementById("ia-campo-prompt").focus();
}

function renderRefinoIa(perguntas) {
  const host = document.getElementById("ia-campo-refino");
  if (!host) return;
  if (!perguntas?.length) {
    host.innerHTML = "";
    host.classList.add("oculto");
    return;
  }
  host.classList.remove("oculto");
  host.innerHTML = perguntas.map((perg) => `
    <div class="refino-card" data-refino-id="${escHtml(perg.id || "")}">
      <strong>${escHtml(perg.pergunta || "Detalhe necessário")}</strong>
      <div class="refino-opcoes">
        ${(perg.opcoes || []).map((opcao) => `
          <button type="button" data-refino-opcao="${escHtml(opcao)}">${escHtml(opcao)}</button>
        `).join("")}
      </div>
    </div>
  `).join("");
}

function aplicarRefinoIa(opcao, pergunta) {
  if (!iaCampoAtual) return;
  const detalhe = pergunta ? `${pergunta} ${opcao}` : opcao;
  iaCampoAtual.historico = [...(iaCampoAtual.historico || []), detalhe];
  const prompt = document.getElementById("ia-campo-prompt");
  const base = prompt.value.trim();
  if (opcao && !base.toLowerCase().includes(String(opcao).toLowerCase())) {
    prompt.value = `${base}${base ? " — " : ""}${opcao}`;
  }
  executarBuscaIaCampo();
}

async function executarBuscaIaCampo() {
  if (!iaCampoAtual) return;
  const prompt = document.getElementById("ia-campo-prompt").value.trim();
  const estado = document.getElementById("ia-campo-estado");
  const erro = document.getElementById("ia-campo-erro");
  const botao = document.getElementById("ia-campo-buscar");
  const lista = document.getElementById("ia-campo-resultados");
  erro.classList.add("oculto");
  erro.textContent = "";
  if (!prompt) {
    erro.className = "erro";
    erro.textContent = "Escreva o que você quer buscar.";
    return;
  }
  botao.disabled = true;
  estado.textContent = "Gerando resposta com IA…";
  lista.innerHTML = "";
  renderRefinoIa([]);
  atualizarBotaoInserirIa();
  try {
    const resposta = await fetch("/api/campos/sugerir", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        consulta: prompt,
        consulta_ia: prompt,
        rotulo: iaCampoAtual.tag.rotulo,
        tecnologia: dados.tecnologia || document.getElementById("tecnologia")?.value || "",
        usar_tecnologia: Boolean(document.getElementById("ia-campo-usar-tecnologia")?.checked),
        historico: iaCampoAtual.historico || [],
      }),
    });
    const corpo = await resposta.json();
    if (!resposta.ok) throw new Error(corpo.mensagem || "Falha na busca.");

    if (corpo.modo === "refinar") {
      renderRefinoIa(corpo.perguntas || []);
      estado.textContent = corpo.mensagem || "Responda as perguntas para afinar a busca.";
      sincronizarTextoFinalIa(true);
      return;
    }

    const itens = corpo.itens || [];
    if (!itens.length) throw new Error("Nenhuma resposta retornada pela IA.");
    lista.innerHTML = itens.map((item, indice) => {
      const longo = String(item.texto || "").length > 180 || String(item.texto || "").includes("\n");
      return `
      <label class="sugestao-cert${longo ? " sugestao-longa" : ""}">
        <input type="checkbox" data-ia-idx="${indice}" ${indice === 0 ? "checked" : ""} />
        <span>
          <strong>Resposta ${indice + 1}</strong>
          <span class="sugestao-texto">${escHtml(item.texto)}</span>
        </span>
      </label>`;
    }).join("");
    lista.dataset.payload = JSON.stringify(itens);
    estado.textContent = corpo.mensagem || `${itens.length} resposta(s) pronta(s).`;
    sincronizarTextoFinalIa(true);
  } catch (falha) {
    estado.textContent = "";
    erro.className = "erro";
    erro.textContent = falha.message;
  } finally {
    botao.disabled = false;
  }
}

function inserirSelecaoIaNoCampo() {
  if (!iaCampoAtual?.id) return;
  const texto = document.getElementById("ia-campo-texto-final")?.value.trim() || "";
  if (!texto) {
    const erro = document.getElementById("ia-campo-erro");
    erro.className = "erro";
    erro.textContent = "Selecione trechos ou edite o texto que será inserido no campo.";
    return;
  }
  const campoEl = iaCampoAtual.destinoSei
    ? document.querySelector(`[data-form-sei-tag="${iaCampoAtual.id}"]`)
    : document.getElementById(`extra-${iaCampoAtual.id}`);
  if (!campoEl) {
    const erro = document.getElementById("ia-campo-erro");
    erro.className = "erro";
    erro.textContent = "Não foi possível localizar o campo do formulário.";
    return;
  }
  campoEl.value = texto;
  const destinoSei = iaCampoAtual.destinoSei;
  const rotulo = iaCampoAtual.tag?.rotulo || iaCampoAtual.id;
  if (!destinoSei) {
    if (!dados.extras || typeof dados.extras !== "object") dados.extras = {};
    dados.extras[iaCampoAtual.id] = texto;
    salvar();
    ajustarCampoIa(iaCampoAtual.id);
  }
  fecharPainelIaCampo();
  const msg = destinoSei ? mensagemConteudoDocumentoInternoSei : mensagem;
  if (typeof msg === "function") msg(`Texto inserido no campo “${rotulo}”.`, "ok");
  campoEl.focus();
  campoEl.scrollIntoView({ behavior: "smooth", block: "center" });
}

function sincronizarCamposTags(tags) {
  tagsConfiguracao = Array.isArray(tags) ? tags : [];
  if (!dados.extras || typeof dados.extras !== "object") dados.extras = {};
  const forcarExtras = !precisaFormularioCompleto() && documentosSelecionados.length > 0;
  const extras = tagsParaCamposExtra(tagsConfiguracao, { forcarExtras });
  extras.forEach((tag) => {
    if (!(tag.id in dados.extras)) {
      dados.extras[tag.id] = tag.tipo === "tabela" ? valorPadraoTabela(tag) : "";
      return;
    }
    if (tag.tipo === "tabela") {
      const atual = dados.extras[tag.id];
      if (!atual || typeof atual !== "object") {
        dados.extras[tag.id] = valorPadraoTabela(tag);
      } else if (Array.isArray(atual)) {
        dados.extras[tag.id] = { linhas: atual.length ? atual : valorPadraoTabela(tag).linhas };
      } else if (!Array.isArray(atual.linhas)) {
        dados.extras[tag.id] = valorPadraoTabela(tag);
      }
    }
  });
  desenharCamposTags({ forcarExtras });
  aplicarOrdemCamposNoFormulario();
  atualizarVisibilidadeSecoesNativas();
}

function obterSecaoBloco(nomeBloco) {
  const form = document.getElementById("cadastro");
  if (!form) return null;
  const chave = normalizarChaveBloco(nomeBloco);
  return [...form.querySelectorAll("section[data-bloco-form]")].find(
    (item) => normalizarChaveBloco(item.dataset.blocoForm) === chave,
  ) || null;
}

function obterHostExtrasDoBloco(nomeBloco) {
  let secao = obterSecaoBloco(nomeBloco);
  if (!secao) {
    const dinamicos = document.getElementById("blocos-tags-dinamicos");
    secao = document.createElement("section");
    secao.dataset.blocoForm = nomeBloco;
    secao.dataset.blocoDinamico = "1";
    secao.innerHTML = `
      <div class="secao-topo"><h2>${escHtml(nomeBloco)}</h2></div>
      <p class="ajuda">Campos criados a partir das tags do grupo “${escHtml(nomeBloco)}” em Configurações.</p>
      <div class="grade campos-extra-bloco"></div>`;
    dinamicos?.appendChild(secao);
  }
  let host = secao.querySelector(".campos-extra-bloco");
  if (!host) {
    host = document.createElement("div");
    host.className = "grade campos-extra-bloco";
    secao.appendChild(host);
  }
  return host;
}

function localizarNosDoCampo(tagId) {
  const nos = [];
  const porTag = document.querySelector(`.campo[data-tag-id="${tagId}"]`);
  if (porTag) {
    nos.push(porTag);
    return nos;
  }
  const extra = document.getElementById(`extra-${tagId}`)?.closest(".campo");
  if (extra) {
    nos.push(extra);
    return nos;
  }
  const el = document.getElementById(tagId);
  if (!el) return nos;
  const campo = el.closest(".campo");
  if (!campo) return nos;
  nos.push(campo);
  if (tagId === "tecnologia") {
    const nova = document.getElementById("nome-tecnologia")?.closest(".nova-linha");
    if (nova) nos.push(nova);
  }
  return nos;
}

function destinoOrdenacaoBloco(secao) {
  let destino = secao.querySelector(".grade.campos-ordenados");
  if (destino) return destino;
  destino = secao.querySelector(".grade:not(.campos-extra-bloco)");
  if (destino) {
    destino.classList.add("campos-ordenados");
    return destino;
  }
  destino = document.createElement("div");
  destino.className = "grade campos-ordenados";
  const topo = secao.querySelector(".secao-topo");
  if (topo?.nextSibling) secao.insertBefore(destino, topo.nextSibling);
  else secao.prepend(destino);
  return destino;
}

function aplicarOrdemCamposNoFormulario() {
  const porBloco = new Map();
  tagsConfiguracao.forEach((tag) => {
    if (!tag?.id || tag.calculado) return;
    gruposDaTag(tag).forEach((grupo) => {
      const bloco = nomeBlocoFormulario(grupo);
      if (!porBloco.has(bloco)) porBloco.set(bloco, []);
      porBloco.get(bloco).push({ tag, grupo });
    });
  });

  porBloco.forEach((itens, bloco) => {
    const secao = obterSecaoBloco(bloco);
    if (!secao) return;
    const destino = destinoOrdenacaoBloco(secao);
    const fragment = document.createDocumentFragment();
    const usados = new Set();
    itens.forEach(({ tag, grupo }) => {
      const noNaSecao = [...secao.querySelectorAll(`.campo[data-tag-id="${tag.id}"]`)][0];
      let no = noNaSecao;
      if (!no && grupo === tag.grupo) {
        no = localizarNosDoCampo(tag.id)[0] || null;
      }
      if (!no || usados.has(no)) return;
      // Campo editável só fica no bloco principal.
      if (!no.dataset.tagReuso && grupo !== tag.grupo) return;
      usados.add(no);
      fragment.appendChild(no);
    });
    if (!fragment.childNodes.length) return;
    const resto = [...destino.children].filter((no) => !usados.has(no));
    destino.appendChild(fragment);
    resto.forEach((no) => destino.appendChild(no));
  });
}

function limparCamposTagsDoFormulario() {
  const form = document.getElementById("cadastro");
  if (!form) return;
  // Remove tags já reordenadas para .campos-ordenados (fora de .campos-extra-bloco).
  form.querySelectorAll(".campo[data-tag-id], .campo[data-tag-reuso]").forEach((el) => el.remove());
  form.querySelectorAll(".campos-extra-bloco").forEach((host) => {
    host.innerHTML = "";
  });
  document.getElementById("blocos-tags-dinamicos")?.replaceChildren();
}

function desenharCamposTags({ forcarExtras = false } = {}) {
  const form = document.getElementById("cadastro");
  if (!form) return;
  limparCamposTagsDoFormulario();

  const extras = tagsParaCamposExtra(tagsConfiguracao, { forcarExtras });
  const porBloco = new Map();
  const campoJaCriado = new Set();
  extras.forEach((tag) => {
    gruposDaTag(tag).forEach((grupo) => {
      const bloco = nomeBlocoFormulario(grupo);
      if (!porBloco.has(bloco)) porBloco.set(bloco, []);
      const ehPrincipal = grupo === tag.grupo && !campoJaCriado.has(tag.id);
      if (ehPrincipal) campoJaCriado.add(tag.id);
      porBloco.get(bloco).push({ tag, reuso: !ehPrincipal });
    });
  });

  porBloco.forEach((lista, bloco) => {
    const host = obterHostExtrasDoBloco(bloco);
    if (!host) return;
    host.innerHTML = lista.map(({ tag, reuso }) => (
      reuso ? htmlCampoReuso(tag) : htmlCampoExtra(tag)
    )).join("");
  });

  form.querySelectorAll("[data-extra-id]").forEach((el) => {
    el.addEventListener("input", () => {
      salvar();
      const tagId = el.dataset.extraId;
      const tag = tagsConfiguracao.find((item) => item.id === tagId);
      if (tag?.tipo === "ia_web") ajustarCampoIa(tagId);
    });
  });
  form.querySelectorAll("[data-buscar-ia]").forEach((botao) => {
    botao.addEventListener("click", () => abrirPainelIaCampo(botao.dataset.buscarIa));
  });
  form.querySelectorAll("[data-tabela-id][data-coluna]").forEach((el) => {
    el.addEventListener("input", () => {
      const tagId = el.dataset.tabelaId;
      if (!dados.extras) dados.extras = {};
      dados.extras[tagId] = lerTabelaDoDom(tagId);
      salvar();
    });
  });
  form.querySelectorAll("[data-add-linha-tabela]").forEach((botao) => {
    botao.addEventListener("click", () => {
      const tagId = botao.dataset.addLinhaTabela;
      const atual = lerTabelaDoDom(tagId);
      const tag = tagsConfiguracao.find((item) => item.id === tagId);
      const vazia = {};
      colunasDaTagTabela(tag).forEach((c) => { vazia[c.id] = ""; });
      atual.linhas.push(vazia);
      if (!dados.extras || typeof dados.extras !== "object") dados.extras = {};
      dados.extras[tagId] = atual;
      // Redesenha antes de salvar: salvar() relê o DOM e apagaria a linha nova.
      const forcarExtras = !precisaFormularioCompleto() && documentosSelecionados.length > 0;
      desenharCamposTags({ forcarExtras });
      aplicarOrdemCamposNoFormulario();
      atualizarVisibilidadeSecoesNativas();
      salvar();
    });
  });
  form.querySelectorAll("[data-remover-linha-tabela]").forEach((botao) => {
    botao.addEventListener("click", () => {
      const tagId = botao.dataset.removerLinhaTabela;
      const idx = Number(botao.dataset.linha);
      const atual = lerTabelaDoDom(tagId);
      atual.linhas.splice(idx, 1);
      if (!atual.linhas.length) {
        const tag = tagsConfiguracao.find((item) => item.id === tagId);
        const vazia = {};
        colunasDaTagTabela(tag).forEach((c) => { vazia[c.id] = ""; });
        atual.linhas = [vazia];
      }
      if (!dados.extras || typeof dados.extras !== "object") dados.extras = {};
      dados.extras[tagId] = atual;
      const forcarExtras = !precisaFormularioCompleto() && documentosSelecionados.length > 0;
      desenharCamposTags({ forcarExtras });
      aplicarOrdemCamposNoFormulario();
      atualizarVisibilidadeSecoesNativas();
      salvar();
    });
  });
  tagsConfiguracao.filter((tag) => tag.tipo === "ia_web").forEach((tag) => ajustarCampoIa(tag.id));
}

function lerDocsSelecionadosSalvos() {
  try {
    const bruto = JSON.parse(localStorage.getItem(chaveDocsSel) || "[]");
    return Array.isArray(bruto) ? bruto.map(String) : [];
  } catch (erro) {
    return [];
  }
}

function salvarDocsSelecionados() {
  localStorage.setItem(chaveDocsSel, JSON.stringify(documentosSelecionados));
}

function tagsDosDocumentosSelecionados() {
  const ids = new Set(documentosSelecionados);
  const unidos = [];
  const vistos = new Set();
  documentosGeracao.forEach((doc) => {
    if (!ids.has(doc.id)) return;
    (doc.tags || []).forEach((tag) => {
      if (!tag?.id || vistos.has(tag.id)) return;
      vistos.add(tag.id);
      unidos.push(tag);
    });
  });
  return unidos;
}

function precisaFormularioCompleto() {
  return documentosSelecionados.some((id) => DOCS_FORMULARIO_COMPLETO.has(id));
}

function secaoTemCamposDeTag(secao) {
  return Boolean(secao.querySelector(
    ".campo[data-tag-id], .campo[data-tag-reuso], .campos-extra-bloco .campo, .editor-tabela",
  ));
}

function atualizarVisibilidadeSecoesNativas() {
  const completo = precisaFormularioCompleto();
  const form = document.getElementById("cadastro");
  if (!form) return;
  form.classList.toggle("modo-catalogo-somente", !completo && documentosSelecionados.length > 0);
  form.classList.toggle("modo-sem-docs", !documentosSelecionados.length);

  form.querySelectorAll("section[data-bloco-form]").forEach((secao) => {
    const dinamico = secao.dataset.blocoDinamico === "1";
    const temExtras = secaoTemCamposDeTag(secao);

    if (dinamico) {
      secao.classList.toggle("form-sec-oculto", !documentosSelecionados.length || !temExtras);
      secao.classList.remove("so-extras");
      return;
    }

    if (completo) {
      // Pacote clássico (RJ/Termo/Pesquisa): seção nativa completa.
      secao.classList.remove("form-sec-oculto", "so-extras");
      secao.querySelectorAll("input, textarea, select").forEach((el) => {
        if (el.dataset.reqOriginal === "1") el.required = true;
      });
      return;
    }

    // Só documento de catálogo: esconde seções nativas do RJ sem tags do doc selecionado.
    if (!temExtras) {
      secao.classList.add("form-sec-oculto");
      secao.classList.remove("so-extras");
      secao.querySelectorAll("input[required], textarea[required], select[required]").forEach((el) => {
        el.dataset.reqOriginal = "1";
        el.required = false;
      });
      return;
    }

    // Bloco nativo reaproveitado só pelas tags do catálogo.
    secao.classList.remove("form-sec-oculto");
    secao.classList.add("so-extras");
    secao.querySelectorAll("input[required], textarea[required], select[required]").forEach((el) => {
      if (el.closest(".campo[data-tag-id], .campos-extra-bloco, .editor-tabela")) return;
      el.dataset.reqOriginal = "1";
      el.required = false;
    });
  });
}

function atualizarRotuloMultiDocs() {
  const rotulo = document.getElementById("multi-docs-rotulo");
  const ajuda = document.getElementById("multi-docs-ajuda");
  const nomes = documentosGeracao
    .filter((doc) => documentosSelecionados.includes(doc.id))
    .map((doc) => doc.nome);
  if (rotulo) {
    rotulo.textContent = nomes.length
      ? `${nomes.length} selecionado(s): ${nomes.join(", ")}`
      : "Selecione os documentos";
  }
  if (ajuda) {
    ajuda.textContent = nomes.length
      ? `Serão gerados: ${nomes.join("; ")}.`
      : "Nenhum documento selecionado.";
  }
}

function renderMultiDocs() {
  const painel = document.getElementById("multi-docs-painel");
  if (!painel) return;
  if (!documentosGeracao.length) {
    painel.innerHTML = `<p class="ajuda">Nenhum documento no catálogo.</p>`;
    atualizarRotuloMultiDocs();
    return;
  }
  painel.innerHTML = documentosGeracao.map((doc) => `
    <label>
      <input type="checkbox" data-doc-geracao="${escHtml(doc.id)}"${documentosSelecionados.includes(doc.id) ? " checked" : ""} />
      <span>
        <strong>${escHtml(doc.nome)}</strong>
        <small style="display:block;color:var(--muted)">${escHtml(doc.origem === "sistema" ? "Pacote clássico" : doc.origem === "nativo" ? "Catálogo" : "Catálogo")} · ${Number(doc.qtd_tags || (doc.tags || []).length)} tag(s)</small>
      </span>
    </label>`).join("");
  painel.querySelectorAll("[data-doc-geracao]").forEach((input) => {
    input.addEventListener("change", () => {
      documentosSelecionados = [...painel.querySelectorAll("[data-doc-geracao]:checked")].map((el) => el.dataset.docGeracao);
      salvarDocsSelecionados();
      atualizarRotuloMultiDocs();
      aplicarFiltroDocumentosNoFormulario();
    });
  });
  atualizarRotuloMultiDocs();
}

function aplicarFiltroDocumentosNoFormulario() {
  const tags = documentosSelecionados.length ? tagsDosDocumentosSelecionados() : [];
  sincronizarCamposTags(tags);
  atualizarVisibilidadeSecoesNativas();
}

function ligarMultiDocsUi() {
  const toggle = document.getElementById("multi-docs-toggle");
  const painel = document.getElementById("multi-docs-painel");
  const secao = document.querySelector(".selecao-documentos-geracao");
  if (!toggle || !painel) return;
  const fechar = () => {
    painel.classList.add("oculto");
    secao?.classList.remove("aberta");
    toggle.setAttribute("aria-expanded", "false");
  };
  const abrir = () => {
    painel.classList.remove("oculto");
    secao?.classList.add("aberta");
    toggle.setAttribute("aria-expanded", "true");
  };
  toggle.addEventListener("click", (evento) => {
    evento.stopPropagation();
    if (painel.classList.contains("oculto")) abrir();
    else fechar();
  });
  document.addEventListener("click", (evento) => {
    if (evento.target.closest("#multi-docs") || evento.target.closest(".selecao-documentos-geracao")) return;
    fechar();
  });
}

async function carregarTagsConfiguracao() {
  try {
    const resposta = await fetch("/api/config/catalogo");
    const corpo = await resposta.json();
    if (!resposta.ok) return;
    tagsCatalogoCompleto = corpo.tags_formulario || corpo.tags || [];
    documentosGeracao = corpo.documentos_geracao || corpo.documentos || [];
    const salvos = lerDocsSelecionadosSalvos();
    const idsValidos = new Set(documentosGeracao.map((d) => d.id));
    documentosSelecionados = salvos.filter((id) => idsValidos.has(id));
    if (!documentosSelecionados.length) {
      documentosSelecionados = documentosGeracao.slice(0, 1).map((d) => d.id);
    }
    salvarDocsSelecionados();
    renderMultiDocs();
    aplicarFiltroDocumentosNoFormulario();
  } catch (erro) {
    /* configuração ainda indisponível */
  }
}

function lerFormulario() {
  ["mes_ano", "codigo_relatorio", "versao_relatorio",
    "codigo_termo", "versao_termo", "assunto", "tecnologia", "prazo_meses", "fatos",
    "perfil_referencia", "horas_por_pf", "regra_vma", "versao_sisp", "parceria", "estudo_mercado",
    "atestados", "regime_certificacao", "horas_professional", "area_elaboracao", "texto_elaboracao",
    "local_data"].forEach((id) => {
    dados[id] = campo(id).value.trim();
  });
  dados.incluir_snap = campo("incluir_snap").checked;
  if (!dados.extras || typeof dados.extras !== "object") dados.extras = {};
  document.querySelectorAll("[data-extra-id]").forEach((el) => {
    dados.extras[el.dataset.extraId] = el.value.trim();
  });
  tagsConfiguracao.filter((tag) => tag.tipo === "tabela").forEach((tag) => {
    dados.extras[tag.id] = lerTabelaDoDom(tag.id);
  });
}

function assuntoPadrao(tecnologia) {
  const nome = String(tecnologia || "").trim();
  return nome
    ? `CONTRATAÇÃO DE SERVIÇOS DE APOIO TÉCNICO ESPECIALIZADO EM ${nome.toUpperCase()}`
    : "";
}

function preencherFixos() {
  Object.keys(dados).forEach((id) => {
    const el = campo(id);
    if (!el || el.type === "checkbox") return;
    if (typeof dados[id] === "string") el.value = dados[id];
  });
  campo("incluir_snap").checked = Boolean(dados.incluir_snap);
}

function linha(tipo, indice) {
  const item = dados[tipo][indice];
  const artigo = document.createElement("div");
  artigo.className = "linha " + (tipo === "certificacoes" ? "simples" : tipo);
  const entrada = (rotulo, valor, aoDigitar) => {
    const caixa = document.createElement("label");
    caixa.className = "campo";
    caixa.textContent = rotulo;
    const input = document.createElement("input");
    input.value = valor || "";
    input.addEventListener("input", () => {
      aoDigitar(input.value);
      salvar();
    });
    caixa.appendChild(input);
    return caixa;
  };
  if (tipo === "catalogo") {
    artigo.append(entrada("Grupo", item.grupo, (v) => { item.grupo = v; }), entrada("Serviços", item.servicos, (v) => { item.servicos = v; }));
  } else if (tipo === "clientes") {
    artigo.append(entrada("Cliente", item.cliente, (v) => { item.cliente = v; }), entrada("Projeto/sistema", item.projeto, (v) => { item.projeto = v; }));
  } else if (tipo === "perfis") {
    artigo.append(
      entrada("Item", item.item, (v) => { item.item = v; }),
      selecaoPerfil(item),
      entrada("Experiência", item.experiencia, (v) => { item.experiencia = v; }),
      entrada("Horas", item.horas, (v) => { item.horas = v; }),
      entrada("Proporção", item.proporcao, (v) => { item.proporcao = v; }),
    );
  } else if (tipo === "certificacoes") {
    artigo.append(entrada("Certificação", item, (v) => { dados.certificacoes[indice] = v; }));
  } else {
    artigo.append(
      entrada("Nome", item.nome, (v) => { item.nome = v; }),
      entrada("Matrícula", item.matricula, (v) => { item.matricula = v; }),
      entrada("Cargo", item.cargo, (v) => { item.cargo = v; }),
    );
  }
  const remover = document.createElement("button");
  remover.type = "button";
  remover.className = "remover";
  remover.textContent = "Remover";
  remover.addEventListener("click", () => {
    dados[tipo].splice(indice, 1);
    if (!dados[tipo].length) dados[tipo].push(listas[tipo]());
    desenhar();
    salvar();
  });
  artigo.appendChild(remover);
  return artigo;
}

function tecnologiaAtual() {
  return acervo.find((item) => item.nome === dados.tecnologia) || null;
}

function nomesMarcados(grupo) {
  const linha = (dados.catalogo || []).find((item) => item.grupo === grupo);
  if (!linha) return [];
  return String(linha.servicos || "").split(",").map((parte) => parte.trim()).filter(Boolean);
}

function preencherTecnologias() {
  const select = campo("tecnologia");
  const atual = dados.tecnologia;
  select.innerHTML = "";
  const vazioOpcao = document.createElement("option");
  vazioOpcao.value = "";
  vazioOpcao.textContent = "Selecione";
  select.appendChild(vazioOpcao);
  acervo.forEach((item) => {
    const opcao = document.createElement("option");
    opcao.value = item.nome;
    opcao.textContent = item.nome;
    select.appendChild(opcao);
  });
  if (atual && !acervo.some((item) => item.nome === atual)) {
    const opcao = document.createElement("option");
    opcao.value = atual;
    opcao.textContent = atual;
    select.appendChild(opcao);
  }
  select.value = atual || "";
  const lista = document.getElementById("perfis-conhecidos");
  lista.innerHTML = "";
  (tecnologiaAtual()?.perfis || []).forEach((perfil) => {
    const opcao = document.createElement("option");
    opcao.value = perfil.nome;
    lista.appendChild(opcao);
  });
}

function prepararAbertos(tecnologia) {
  if (arvoreTecnologia === tecnologia.id) return;
  arvoreTecnologia = tecnologia.id;
  gruposAbertos = new Set();
}

function textoContagem(total, marcados) {
  if (!total) return "Nenhum serviço";
  if (!marcados) return total === 1 ? "1 serviço" : `${total} serviços`;
  return `${marcados} de ${total}`;
}

function desenharArvore() {
  const host = document.getElementById("arvore");
  host.innerHTML = "";
  const tecnologia = tecnologiaAtual();
  if (!tecnologia) {
    host.textContent = "Escolha uma tecnologia para ver os grupos e serviços.";
    return;
  }
  if (!tecnologia.grupos.length) {
    const aviso = document.createElement("p");
    aviso.className = "ajuda";
    aviso.textContent = "Esta tecnologia ainda não tem grupos. Grave o primeiro abaixo.";
    host.appendChild(aviso);
    return;
  }
  prepararAbertos(tecnologia);
  if (abrirGrupoNome) {
    const novoGrupo = tecnologia.grupos.find((grupo) => grupo.nome.toLowerCase() === abrirGrupoNome.toLowerCase());
    if (novoGrupo) gruposAbertos.add(novoGrupo.id);
    abrirGrupoNome = "";
  }
  tecnologia.grupos.forEach((grupo) => {
    const escolhidos = nomesMarcados(grupo.nome);
    const aberto = gruposAbertos.has(grupo.id);
    const bloco = document.createElement("div");
    bloco.className = "grupo-bloco";
    const barra = document.createElement("div");
    barra.className = "grupo-barra";
    const alternar = document.createElement("button");
    alternar.type = "button";
    alternar.className = "drill";
    alternar.textContent = aberto ? "▾" : "▸";
    alternar.setAttribute("aria-expanded", aberto ? "true" : "false");
    alternar.setAttribute("aria-label", `${aberto ? "Ocultar" : "Mostrar"} serviços de ${grupo.nome}`);
    const rotulo = document.createElement("label");
    const caixa = document.createElement("input");
    caixa.type = "checkbox";
    caixa.className = "marca-grupo";
    caixa.checked = Boolean((dados.catalogo || []).find((item) => item.grupo === grupo.nome));
    caixa.addEventListener("change", () => {
      if (!caixa.checked) bloco.querySelectorAll(".servicos input").forEach((item) => { item.checked = false; });
      sincronizarCatalogo();
      atualizarContagem();
    });
    rotulo.append(caixa, document.createTextNode(grupo.nome));
    const contagem = document.createElement("span");
    contagem.className = "contagem";
    const detalhe = document.createElement("div");
    detalhe.className = aberto ? "grupo-detalhe" : "grupo-detalhe oculto";
    const servicos = document.createElement("div");
    servicos.className = "servicos";
    grupo.servicos.forEach((servico) => {
      const item = document.createElement("label");
      const marca = document.createElement("input");
      marca.type = "checkbox";
      marca.checked = escolhidos.includes(servico.nome);
      marca.addEventListener("change", () => {
        if (marca.checked) caixa.checked = true;
        if (!bloco.querySelector(".servicos input:checked")) caixa.checked = false;
        sincronizarCatalogo();
        atualizarContagem();
      });
      item.append(marca, document.createTextNode(servico.nome));
      servicos.appendChild(item);
    });
    const novo = document.createElement("div");
    novo.className = "novo-servico";
    const entrada = document.createElement("input");
    entrada.placeholder = "Novo serviço deste grupo";
    const botao = document.createElement("button");
    botao.type = "button";
    botao.textContent = "Gravar serviço";
    botao.addEventListener("click", () => {
      gruposAbertos.add(grupo.id);
      gravarServico(grupo.id, entrada);
    });
    novo.append(entrada, botao);
    detalhe.append(servicos, novo);
    function atualizarContagem() {
      const marcados = bloco.querySelectorAll(".servicos input:checked").length;
      contagem.textContent = textoContagem(grupo.servicos.length, marcados);
    }
    alternar.addEventListener("click", () => {
      const vaiAbrir = detalhe.classList.contains("oculto");
      detalhe.classList.toggle("oculto", !vaiAbrir);
      alternar.textContent = vaiAbrir ? "▾" : "▸";
      alternar.setAttribute("aria-expanded", vaiAbrir ? "true" : "false");
      alternar.setAttribute("aria-label", `${vaiAbrir ? "Ocultar" : "Mostrar"} serviços de ${grupo.nome}`);
      if (vaiAbrir) gruposAbertos.add(grupo.id);
      else gruposAbertos.delete(grupo.id);
    });
    barra.append(alternar, rotulo, contagem);
    bloco.append(barra, detalhe);
    atualizarContagem();
    host.appendChild(bloco);
  });
}

function sincronizarCatalogo() {
  const tecnologia = tecnologiaAtual();
  const marcados = [];
  if (tecnologia) {
    document.querySelectorAll("#arvore .grupo-bloco").forEach((bloco, indice) => {
      const grupo = tecnologia.grupos[indice];
      const nomes = [];
      bloco.querySelectorAll(".servicos label").forEach((rotulo, posicao) => {
        if (rotulo.querySelector("input").checked) nomes.push(grupo.servicos[posicao].nome);
      });
      if (bloco.querySelector(".marca-grupo").checked || nomes.length) {
        marcados.push({ grupo: grupo.nome, servicos: nomes.join(", ") });
      }
    });
  }
  dados.catalogo = marcados;
  salvar();
}

function selecaoPerfil(item) {
  const caixa = document.createElement("label");
  caixa.className = "campo";
  caixa.appendChild(document.createTextNode("Perfil"));
  const select = document.createElement("select");
  const vazioOpcao = document.createElement("option");
  vazioOpcao.value = "";
  vazioOpcao.textContent = "Selecione";
  select.appendChild(vazioOpcao);
  const nomes = (tecnologiaAtual()?.perfis || []).map((perfil) => perfil.nome);
  if (item.perfil && !nomes.includes(item.perfil)) nomes.unshift(item.perfil);
  nomes.forEach((nome) => {
    const opcao = document.createElement("option");
    opcao.value = nome;
    opcao.textContent = nome;
    select.appendChild(opcao);
  });
  const outro = document.createElement("option");
  outro.value = "__novo__";
  outro.textContent = "Gravar outro perfil…";
  select.appendChild(outro);
  select.value = item.perfil || "";
  const novo = document.createElement("input");
  novo.placeholder = "Nome do novo perfil";
  novo.hidden = select.value !== "__novo__";
  const gravar = document.createElement("button");
  gravar.type = "button";
  gravar.textContent = "Gravar perfil";
  gravar.hidden = select.value !== "__novo__";
  select.addEventListener("change", () => {
    const novoPerfil = select.value === "__novo__";
    novo.hidden = !novoPerfil;
    gravar.hidden = !novoPerfil;
    item.perfil = novoPerfil ? "" : select.value;
    salvar();
  });
  gravar.addEventListener("click", () => gravarPerfil(novo.value, item));
  caixa.append(select, novo, gravar);
  return caixa;
}

async function postarLista(url, corpo) {
  const resposta = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(corpo),
  });
  const json = await resposta.json();
  if (!resposta.ok) throw new Error(json.mensagem || "Não foi possível gravar na lista.");
  acervo = json.tecnologias || [];
  preencherTecnologias();
  desenharArvore();
  desenhar();
  mensagem("Gravado na lista.", "ok");
}

async function gravarTecnologia() {
  const nome = campo("nome-tecnologia").value.trim();
  dados.tecnologia = nome;
  dados.catalogo = [];
  tecnologiaDaArvore = nome;
  try {
    await postarLista("/api/tecnologias", { nome });
    campo("nome-tecnologia").value = "";
    salvar();
  } catch (erro) {
    mensagem(erro.message, "erro");
  }
}

async function gravarGrupo() {
  const tecnologia = tecnologiaAtual();
  if (!tecnologia) {
    mensagem("Escolha a tecnologia antes de gravar o grupo.", "erro");
    return;
  }
  try {
    abrirGrupoNome = campo("nome-grupo").value.trim();
    await postarLista("/api/grupos", { tecnologia_id: tecnologia.id, nome: abrirGrupoNome });
    campo("nome-grupo").value = "";
  } catch (erro) {
    mensagem(erro.message, "erro");
  }
}

async function gravarServico(grupoId, entrada) {
  try {
    await postarLista("/api/servicos", { grupo_id: grupoId, nome: entrada.value.trim() });
    entrada.value = "";
  } catch (erro) {
    mensagem(erro.message, "erro");
  }
}

async function gravarPerfil(nome, item) {
  const tecnologia = tecnologiaAtual();
  if (!tecnologia) {
    mensagem("Escolha a tecnologia antes de gravar o perfil.", "erro");
    return;
  }
  try {
    await postarLista("/api/perfis", { tecnologia_id: tecnologia.id, nome });
    item.perfil = nome.trim();
    desenhar();
    salvar();
  } catch (erro) {
    mensagem(erro.message, "erro");
  }
}

async function carregarAcervo() {
  const resposta = await fetch("/api/catalogo");
  const corpo = await resposta.json();
  acervo = corpo.tecnologias || [];
  preencherTecnologias();
  desenharArvore();
  desenhar();
}

function desenhar() {
  Object.keys(listas).forEach((tipo) => {
    const host = document.getElementById(tipo);
    host.innerHTML = "";
    dados[tipo].forEach((_, indice) => host.appendChild(linha(tipo, indice)));
  });
  atualizarTotal();
}

function atualizarTotal() {
  const total = dados.perfis.reduce((soma, perfil) => soma + numero(perfil.horas), 0);
  document.getElementById("total-horas").textContent = total
    ? "Total de horas: " + total.toLocaleString("pt-BR")
    : "Total de horas: 0";
}

function numero(valor) {
  let texto = String(valor || "").trim().replace(/\s/g, "");
  if (!texto) return 0;
  if (texto.includes(",") && texto.includes(".")) texto = texto.replace(/\./g, "").replace(",", ".");
  else if (texto.includes(",")) texto = texto.replace(",", ".");
  else if ((texto.match(/\./g) || []).length > 1) texto = texto.replace(/\./g, "");
  else if ((texto.match(/\./g) || []).length === 1) {
    const [inteiro, frac] = texto.split(".");
    if (/^\d+$/.test(inteiro) && /^\d{3}$/.test(frac)) texto = inteiro + frac;
  }
  const n = Number(texto);
  return Number.isFinite(n) ? Math.round(n) : 0;
}

function mensagem(texto, tipo) {
  const el = document.getElementById("mensagem");
  el.textContent = texto || "";
  el.className = tipo || "erro";
  el.classList.toggle("oculto", !texto);
}

document.querySelectorAll("[data-add]").forEach((botao) => {
  botao.addEventListener("click", () => {
    const tipo = botao.dataset.add;
    dados[tipo].push(listas[tipo]());
    desenhar();
    salvar();
  });
});

document.getElementById("cadastro").addEventListener("input", salvar);

document.getElementById("cadastro").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  salvar();
  const botao = document.getElementById("gerar");
  botao.disabled = true;
  if (!documentosSelecionados.length) {
    mensagem("Selecione ao menos um documento para gerar.", "erro");
    return;
  }
  const qtd = documentosSelecionados.length;
  document.getElementById("estado-gerar").textContent = qtd === 1
    ? "Gerando o documento selecionado…"
    : `Gerando ${qtd} documentos selecionados…`;
  mensagem("");
  try {
    const payload = {
      ...dados,
      tipo_processo: modoOperacao || "Abertura",
      documentos_ids: [...documentosSelecionados],
    };
    if (processoEmEdicao?.id) payload.processo_id = processoEmEdicao.id;
    const resposta = await fetch("/api/gerar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const corpo = await resposta.json();
    if (!resposta.ok) throw new Error(corpo.mensagem || "Não foi possível gerar.");
    if (corpo.processo?.id) {
      definirEdicao({
        id: corpo.processo.id,
        codigo: corpo.processo.codigo,
      });
      if (corpo.processo.tipo) modoOperacao = corpo.processo.tipo;
    }
    documentosGeradosAtuais = corpo.documentos || [];
    mostrarResultado(corpo);
    await carregarProcessos();
    if (corpo.processo?.codigo) {
      const acao = payload.processo_id ? "atualizado" : `gravado na Principal como ${corpo.processo.tipo}`;
      mensagem(`Processo ${corpo.processo.codigo} ${acao}. Nº SEI em branco — ainda não enviado.`, "ok");
    }
  } catch (erro) {
    mensagem(erro.message, "erro");
  } finally {
    botao.disabled = false;
    document.getElementById("estado-gerar").textContent = "";
  }
});

function mostrarResultado(corpo, { rolar = true } = {}) {
  const painel = document.getElementById("resultado");
  const lista = document.getElementById("lista-docs");
  lista.innerHTML = "";
  corpo.documentos.forEach((doc) => {
    const cartao = document.createElement("article");
    cartao.className = "cartao-doc";
    const texto = document.createElement("div");
    texto.innerHTML = `<strong>${doc.nome}</strong><span>Word pronto para correção</span>`;
    const acoes = document.createElement("div");
    acoes.className = "acoes";
    const word = document.createElement("a");
    word.className = "acao";
    word.href = `/arquivo/${corpo.id}/${doc.arquivo}`;
    word.textContent = "Baixar Word";
    const pdf = document.createElement("button");
    pdf.type = "button";
    pdf.className = "acao";
    pdf.textContent = "Converter para PDF";
    pdf.addEventListener("click", () => converter(corpo.id, doc.slug, pdf));
    acoes.append(word, pdf);
    cartao.append(texto, acoes);
    lista.appendChild(cartao);
  });
  document.getElementById("incluir-documento").disabled = !corpo.processo?.id || !corpo.documentos?.length;
  document.getElementById("documentos-anexados").replaceChildren();
  painel.classList.remove("oculto");
  if (rolar) painel.scrollIntoView({ behavior: "smooth" });
  if (corpo.processo?.id) carregarDocumentosAnexados(corpo.processo.id);
}

function definirMensagemDocumento(id, texto, tipo = "erro") {
  const el = campo(id);
  el.textContent = texto || "";
  el.className = tipo;
  el.classList.toggle("oculto", !texto);
}

function mostrarEtapaDocumento(id) {
  ["etapa-documento-selecao", "etapa-documento-dados", "etapa-documento-editor"].forEach((etapa) => {
    campo(etapa).classList.toggle("oculto", etapa !== id);
  });
}

async function carregarDocumentosAnexados(processoId) {
  try {
    const resposta = await fetch(`/api/processos/${processoId}/documentos`);
    const corpo = await lerRespostaApi(resposta);
    if (!resposta.ok) throw new Error(corpo.mensagem || "Não foi possível carregar os documentos do processo.");
    desenharDocumentosAnexados(processoId, corpo.anexados || []);
  } catch (erro) {
    definirMensagemDocumento("documentos-anexados-mensagem", erro.message);
  }
}

async function carregarDocumentosProcesso(processo) {
  const resposta = await fetch(`/api/processos/${processo.id}/documentos`);
  const corpo = await lerRespostaApi(resposta);
  if (!resposta.ok) throw new Error(corpo.mensagem || "Não foi possível carregar os documentos do processo.");
  mostrarResultado({
    id: processo.pasta_id,
    processo,
    documentos: corpo.disponiveis || [],
  }, { rolar: false });
  if (!(corpo.disponiveis || []).length && !(corpo.anexados || []).length) {
    campo("resultado").classList.add("oculto");
  }
  desenharDocumentosAnexados(processo.id, corpo.anexados || []);
}

function desenharDocumentosAnexados(processoId, documentos) {
  const lista = campo("documentos-anexados");
  lista.replaceChildren();
  documentos.forEach((documento) => {
    const cartao = document.createElement("article");
    cartao.className = "cartao-doc";
    const informacoes = document.createElement("div");
    const titulo = document.createElement("strong");
    titulo.textContent = documento.nome;
    const tipo = document.createElement("span");
    tipo.textContent = `${documento.tipo_documento} · Demonstração local`;
    informacoes.append(titulo, tipo);
    const baixar = document.createElement("a");
    baixar.className = "acao";
    baixar.href = `/api/processos/${processoId}/documentos/${documento.id}`;
    baixar.textContent = "Baixar conteúdo";
    cartao.append(informacoes, baixar);
    lista.append(cartao);
  });
  definirMensagemDocumento(
    "documentos-anexados-mensagem",
    documentos.length ? `${documentos.length} documento(s) salvo(s) no GCPD. Não foram enviados ao SEI.` : "",
    "ok",
  );
}

async function abrirInclusaoDocumento() {
  const processoId = processoEmEdicao?.id;
  if (!processoId) {
    mensagem("Gere e salve os documentos antes de incluir um documento no processo.", "erro");
    return;
  }
  const botao = campo("incluir-documento");
  botao.disabled = true;
  definirMensagemDocumento("documento-selecao-mensagem", "");
  const select = campo("arquivo-word-documento");
  select.replaceChildren();
  try {
    const resposta = await fetch(`/api/processos/${processoId}/documentos`);
    const corpo = await lerRespostaApi(resposta);
    if (!resposta.ok) throw new Error(corpo.mensagem || "Não foi possível carregar os Word gerados.");
    const disponiveis = corpo.disponiveis || [];
    if (!disponiveis.length) {
      throw new Error("Este processo ainda não tem Word gerado disponível. Volte ao formulário e gere um documento.");
    }
    disponiveis.forEach((documento) => {
      const opcao = document.createElement("option");
      opcao.value = documento.arquivo;
      opcao.textContent = documento.nome;
      select.append(opcao);
    });
    arquivoDocumentoOrigem = select.value;
    tipoDocumentoInclusao = campo("tipo-documento-sei").value;
    mostrarEtapaDocumento("etapa-documento-selecao");
    campo("painel-incluir-documento").classList.remove("oculto");
  } catch (erro) {
    definirMensagemDocumento("documento-selecao-mensagem", erro.message);
    mostrarEtapaDocumento("etapa-documento-selecao");
    campo("painel-incluir-documento").classList.remove("oculto");
  } finally {
    botao.disabled = false;
  }
}

function abrirDadosDocumento() {
  const select = campo("arquivo-word-documento");
  if (!select.value) {
    definirMensagemDocumento("documento-selecao-mensagem", "Selecione um Word para inserir.");
    return;
  }
  arquivoDocumentoOrigem = select.value;
  tipoDocumentoInclusao = campo("tipo-documento-sei").value;
  campo("tipo-documento-escolhido").textContent = tipoDocumentoInclusao;
  campo("documento-descricao").value = tipoDocumentoInclusao;
  campo("documento-nome-arvore").value = tipoDocumentoInclusao;
  campo("documento-assuntos").value = (dados.processo_sei?.assuntos || []).join("\n");
  campo("documento-observacoes").value = dados.processo_sei?.observacoes || "";
  document.querySelectorAll('input[name="documento-nivel-acesso"]').forEach((radio) => {
    radio.checked = radio.value === (dados.processo_sei?.nivel_acesso || "publico");
  });
  definirMensagemDocumento("documento-dados-mensagem", "");
  mostrarEtapaDocumento("etapa-documento-dados");
}

async function abrirEditorDocumento() {
  if (!arquivoDocumentoOrigem || !processoEmEdicao?.id) {
    definirMensagemDocumento("documento-dados-mensagem", "Selecione um Word gerado para este processo.");
    return;
  }
  const botao = campo("documento-ir-editor");
  botao.disabled = true;
  definirMensagemDocumento("documento-dados-mensagem", "");
  try {
    const resposta = await fetch(`/api/processos/${processoEmEdicao.id}/documentos/converter`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ arquivo: arquivoDocumentoOrigem }),
    });
    const corpo = await lerRespostaApi(resposta);
    if (!resposta.ok) throw new Error(corpo.mensagem || "Não foi possível abrir o Word no editor.");
    campo("editor-conteudo-documento").innerHTML = corpo.html || "";
    avisosConversaoDocumento = corpo.avisos || [];
    const aviso = campo("documento-editor-avisos");
    aviso.textContent = avisosConversaoDocumento.length
      ? `A conversão encontrou avisos: ${avisosConversaoDocumento.join(" ")}`
      : "";
    aviso.classList.toggle("oculto", !aviso.textContent);
    definirMensagemDocumento("documento-editor-mensagem", "");
    mostrarEtapaDocumento("etapa-documento-editor");
    campo("editor-conteudo-documento").focus();
  } catch (erro) {
    definirMensagemDocumento("documento-dados-mensagem", erro.message);
  } finally {
    botao.disabled = false;
  }
}

async function salvarDocumentoAnexado() {
  if (!processoEmEdicao?.id) return;
  const botao = campo("documento-salvar-anexo");
  botao.disabled = true;
  definirMensagemDocumento("documento-editor-mensagem", "");
  const nivelAcesso = document.querySelector('input[name="documento-nivel-acesso"]:checked');
  const metadados = {
    texto_inicial: document.querySelector('input[name="texto-inicial-documento"]:checked')?.value || "nenhum",
    descricao: campo("documento-descricao").value.trim(),
    nome_arvore: campo("documento-nome-arvore").value.trim(),
    assuntos: campo("documento-assuntos").value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean),
    observacoes: campo("documento-observacoes").value.trim(),
    nivel_acesso: nivelAcesso?.value || "publico",
  };
  try {
    const resposta = await fetch(`/api/processos/${processoEmEdicao.id}/documentos`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tipo_documento: tipoDocumentoInclusao,
        nome: metadados.nome_arvore || metadados.descricao || tipoDocumentoInclusao,
        arquivo_origem: arquivoDocumentoOrigem,
        metadados,
        conteudo_html: campo("editor-conteudo-documento").innerHTML,
      }),
    });
    const corpo = await lerRespostaApi(resposta);
    if (!resposta.ok) throw new Error(corpo.mensagem || "Não foi possível salvar o documento no processo.");
    fecharPainelInclusaoDocumento();
    await carregarDocumentosAnexados(processoEmEdicao.id);
  } catch (erro) {
    definirMensagemDocumento("documento-editor-mensagem", erro.message);
  } finally {
    botao.disabled = false;
  }
}

function fecharPainelInclusaoDocumento() {
  campo("painel-incluir-documento").classList.add("oculto");
}

async function converter(id, slug, botao) {
  botao.disabled = true;
  botao.textContent = "Convertendo…";
  mensagem("");
  try {
    const resposta = await fetch(`/api/pdf/${id}/${slug}`, { method: "POST" });
    const corpo = await resposta.json();
    if (!resposta.ok) throw new Error(corpo.mensagem || "Falha na conversão.");
    window.location = `/arquivo/${id}/${corpo.arquivo}`;
    botao.textContent = "PDF gerado";
  } catch (erro) {
    mensagem(erro.message, "erro");
    botao.disabled = false;
    botao.textContent = "Converter para PDF";
  }
}

document.getElementById("converter-corrigido").addEventListener("click", async () => {
  const arquivo = document.getElementById("word-corrigido").files[0];
  if (!arquivo) {
    mensagem("Escolha o Word corrigido antes de converter.", "erro");
    return;
  }
  const form = new FormData();
  form.append("arquivo", arquivo);
  mensagem("");
  try {
    const resposta = await fetch("/api/pdf-upload", { method: "POST", body: form });
    const corpo = await resposta.json();
    if (!resposta.ok) throw new Error(corpo.mensagem || "Falha na conversão.");
    const aviso = document.getElementById("pdf-corrigido");
    aviso.classList.remove("oculto");
    aviso.innerHTML = `PDF pronto. <a href="/arquivo/${corpo.id}/${corpo.arquivo}">Baixar PDF</a>`;
  } catch (erro) {
    mensagem(erro.message, "erro");
  }
});

function escHtml(texto) {
  return String(texto ?? "").replace(/[&<>"]/g, (caractere) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;",
  }[caractere]));
}

function marca(texto) {
  const valor = String(texto ?? "").trim();
  return `<mark class="preenche">${escHtml(valor || "a preencher")}</mark>`;
}

function cartao(documento, clausula, corpo) {
  const classe = documento.startsWith("Termo") ? "doc-tr" : "doc-rj";
  return `<article class="clausula"><div class="meta"><span class="doc ${classe}">${escHtml(documento)}</span><span>${escHtml(clausula)}</span></div>${corpo}</article>`;
}

function p(html) {
  return `<p>${html}</p>`;
}

function catalogoItens() {
  return (dados.catalogo || []).filter((item) => item.grupo);
}

function htmlCatalogo() {
  const itens = catalogoItens();
  if (!itens.length) return p(marca(""));
  return itens.map((item) => p(`${marca(item.grupo)}: ${marca(item.servicos)}.`)).join("");
}

function htmlQuadro(comProporcao) {
  const linhas = (dados.perfis || []).filter((perfil) => perfil.perfil || perfil.item || perfil.horas);
  const colunas = ["Perfil técnico", "Experiência mínima (anos)", "Total de horas"];
  if (comProporcao) colunas.push("Proporção do valor-hora");
  const grupos = [];
  linhas.forEach((perfil) => {
    const nome = perfil.item || "";
    let grupo = grupos.find((item) => item.nome === nome);
    if (!grupo) {
      grupo = { nome, perfis: [] };
      grupos.push(grupo);
    }
    grupo.perfis.push(perfil);
  });
  const corpo = grupos.map((grupo) => {
    const horasItem = grupo.perfis.reduce((soma, perfil) => soma + numero(perfil.horas), 0);
    const faixa = `<tr><td>${marca(grupo.nome)}</td><td></td><td>${marca(horasItem.toLocaleString("pt-BR"))}</td>${comProporcao ? "<td></td>" : ""}</tr>`;
    const detalhes = grupo.perfis.map((perfil) => {
      const celulas = [
        marca(perfil.perfil),
        marca(perfil.experiencia),
        marca(numero(perfil.horas).toLocaleString("pt-BR")),
      ];
      if (comProporcao) celulas.push(marca(perfil.proporcao));
      return `<tr>${celulas.map((celula) => `<td>${celula}</td>`).join("")}</tr>`;
    }).join("");
    return faixa + detalhes;
  }).join("");
  const total = (dados.perfis || []).reduce((soma, perfil) => soma + numero(perfil.horas), 0);
  const cabecalho = colunas.map((coluna) => `<th>${escHtml(coluna)}</th>`).join("");
  const vazio = corpo || `<tr><td colspan="${colunas.length}">${marca("")}</td></tr>`;
  const rodape = `<tr><td>Total geral</td><td></td><td>${marca(total.toLocaleString("pt-BR"))}</td>${comProporcao ? "<td></td>" : ""}</tr>`;
  return `<table class="quadro"><thead><tr>${cabecalho}</tr></thead><tbody>${vazio}${rodape}</tbody></table>`;
}

function htmlClientes() {
  const linhas = (dados.clientes || []).filter((item) => item.cliente || item.projeto);
  const corpo = linhas.length
    ? linhas.map((item) => `<tr><td>${marca(item.cliente)}</td><td>${marca(item.projeto)}</td></tr>`).join("")
    : `<tr><td colspan="2">${marca("")}</td></tr>`;
  return `<table class="quadro"><thead><tr><th>Cliente</th><th>Projeto/Sistema</th></tr></thead><tbody>${corpo}</tbody></table>`;
}

function htmlPessoas() {
  const pessoas = (dados.aprovadores || []).filter((pessoa) => pessoa.nome || pessoa.matricula || pessoa.cargo);
  if (!pessoas.length) return p(`${marca("")}<br>Matrícula: ${marca("")}<br>${marca("")}`);
  return pessoas.map((pessoa) => p(`${marca(pessoa.nome)}<br>Matrícula: ${marca(pessoa.matricula)}<br>${marca(pessoa.cargo)}`)).join("");
}

function certificacoesInformadas() {
  return (dados.certificacoes || []).map((item) => String(item || "").trim()).filter(Boolean);
}

function marcasCertificacoes() {
  const itens = certificacoesInformadas();
  if (!itens.length) return marca("");
  return itens.map((item) => marca(item)).join("; ");
}

function htmlCertificacoes() {
  const itens = certificacoesInformadas();
  if (!itens.length) return p(marca(""));
  return itens.map((item) => p(marca(item))).join("");
}

function prazoEscrito(valor) {
  const nomes = { 6: "seis", 12: "doze", 18: "dezoito", 24: "vinte e quatro", 36: "trinta e seis" };
  return nomes[Number(valor)] || "por extenso";
}

const ENCAIXES = {
  identificacao() {
    const mes = marca((dados.mes_ano || "").replace(/\s*\/\s*/g, " / ").toUpperCase());
    const relatorio = `${marca(dados.codigo_relatorio)} ${marca(dados.versao_relatorio)}`;
    const termo = `${marca(dados.codigo_termo)} ${marca(dados.versao_termo)}`;
    const prazo = `${marca(dados.prazo_meses)} (${escHtml(prazoEscrito(dados.prazo_meses))})`;
    return [
      cartao("Relatório de Justificativa", "Corpo, antes do item 1", p(mes)),
      cartao("Termo de Referência", "Corpo, antes do item 1", p(mes)),
      cartao("Relatório de Justificativa", "Capa", p(relatorio)),
      cartao("Termo de Referência", "Capa", p(termo)),
      cartao("Relatório de Justificativa", "Rodapé", p(`Relatório de justificativa ${relatorio}          SEI  / pg.`)),
      cartao("Termo de Referência", "Rodapé", p(`Termo de referência ${termo}          SEI  / pg.`)),
      cartao("Relatório de Justificativa", "8. Conclusão", p(
        `... a serem utilizadas em um período de ${prazo} meses a partir da data de assinatura do contrato, definido em lote único...`,
      )),
      cartao("Termo de Referência", "2.1 Do Objeto", p(
        `Prestação de serviços de apoio técnico especializado em ${marca((dados.tecnologia || "").trim())}, contemplando design, desenvolvimento, configuração, implantação, manutenção e suporte de sistemas de informação e plataformas tecnológicas da PRODESP, pelo período de ${marca(dados.prazo_meses)} meses.`,
      )),
    ].join("");
  },
  objeto() {
    const tecnologia = marca(dados.tecnologia);
    const fato = p(marca(dados.fatos));
    return [
      cartao("Relatório de Justificativa", "1. Objetivo", p(
        `Justificar a necessidade de abertura de Processo Licitatório para contratação de Serviços de Apoio Técnico Especializado contemplando design, desenvolvimento, configuração, implantação, manutenção e suporte de sistemas de informação e plataformas tecnológicas da PRODESP utilizando ${tecnologia}.`,
      )),
      cartao("Relatório de Justificativa", "2.1.1 Definições", p(`${tecnologia} é a plataforma objeto desta contratação, utilizada pela PRODESP para desenvolvimento, implantação, manutenção e suporte de sistemas de informação.`) + htmlCatalogo()),
      cartao("Relatório de Justificativa", "2.3 Situação atual", fato + p("Esses serviços complementam a capacidade interna da PRODESP e apoiam a transferência de conhecimento para o corpo técnico, mediante demandas formalizadas por Ordem de Serviço.")),
      cartao("Relatório de Justificativa", "3.1 Justificativa para a licitação", p(
        `A PRODESP necessita contratar serviços de Apoio Técnico Especializado em ${tecnologia} para assegurar design, desenvolvimento, configuração, implantação, manutenção e suporte de sistemas de informação e plataformas tecnológicas.`,
      ) + fato),
      cartao("Termo de Referência", "2.1 Do Objeto", p(
        `Prestação de serviços de apoio técnico especializado em ${tecnologia}, contemplando design, desenvolvimento, configuração, implantação, manutenção e suporte de sistemas de informação e plataformas tecnológicas da PRODESP, pelo período de ${marca(dados.prazo_meses)} meses.`,
      ) + p(`Deverão ser prestados serviços de Apoio Técnico Especializado em ${tecnologia} à PRODESP, cobrindo a cadeia de valor informada no cadastro, sem inclusão de serviço que não conste do catálogo abaixo.`) + htmlCatalogo()),
    ].join("");
  },
  catalogo() {
    const bloco = htmlCatalogo();
    return [
      cartao("Relatório de Justificativa", "2.1.1 Definições", p("O escopo informado no cadastro contempla os seguintes grupos, sem inclusão de serviço que não tenha sido registrado:") + bloco),
      cartao("Termo de Referência", "2.1 Do Objeto", p("Deverão ser prestados serviços de Apoio Técnico Especializado à PRODESP, cobrindo a cadeia de valor informada no cadastro, sem inclusão de serviço que não conste do catálogo abaixo.") + bloco),
      cartao("Termo de Referência", "3.1.8 Domínio da plataforma", p(`Os profissionais disponibilizados pela CONTRATADA deverão possuir domínio nas tecnologias de ${marca(dados.tecnologia)} informadas no cadastro, não se restringindo somente a estas quando a Ordem de Serviço exigir competência já prevista no catálogo:`) + bloco),
    ].join("");
  },
  clientes() {
    const nomes = (dados.clientes || []).filter((item) => item.cliente || item.projeto).map((item) => {
      const projeto = marca(item.projeto);
      return item.cliente ? `${projeto} (${marca(item.cliente)})` : projeto;
    }).join(", ");
    return [
      cartao("Relatório de Justificativa", "3.1 Justificativa para a licitação", p(`As demandas informadas no cadastro incluem: ${nomes || marca("")}.`)),
      cartao("Relatório de Justificativa", "3.1.2 Demanda atual de serviços", p("Constatou-se que existem projetos em fase de estudo que poderão utilizar os serviços que serão contratados, assim como sistemas que requerem Apoio Técnico Especializado nestas tecnologias para sua manutenção evolutiva, dos quais se destacam os seguintes:") + htmlClientes()),
    ].join("");
  },
  perfis() {
    const horas = (dados.perfis || []).reduce((soma, perfil) => soma + numero(perfil.horas), 0);
    return [
      cartao("Relatório de Justificativa", "3.2 Demanda", p("A demanda apresentada foi apurada frente ao volume de serviços, sistemas e plataformas demandados pela PRODESP, além das novas demandas informadas no cadastro, conforme o quadro a seguir.") + htmlQuadro(false)),
      cartao("Relatório de Justificativa", "3.3 Da licitação", p(`Para a realização dos serviços de Apoio Técnico Especializado previstos, foi estimado um total de ${marca(horas.toLocaleString("pt-BR"))} horas, apresentados no quadro abaixo.`) + htmlQuadro(true)),
      cartao("Termo de Referência", "2.11 Formação de lotes", p(`A licitação de Apoio Técnico Especializado será efetuada em lote único, contemplando as tecnologias elencadas neste documento para ${marca(dados.tecnologia)}, de acordo com os perfis técnicos e quantitativos apresentados no quadro a seguir.`) + htmlQuadro(true)),
      cartao("Termo de Referência", "3.1.5 Experiência mínima", p("O tempo de experiência mínima requerida dos profissionais será de acordo com o quadro abaixo.") + htmlQuadro(false)),
    ].join("");
  },
  medicao() {
    const referencia = marca(dados.perfil_referencia);
    const snap = dados.incluir_snap
      ? `Simple Function Point – SFP, NESMA, ${marca("SNAP")}, COSMIC`
      : "Simple Function Point – SFP, NESMA, COSMIC";
    const avisoSnap = dados.incluir_snap
      ? ""
      : p("A opção SNAP deste cadastro fica de fora desta cláusula.");
    return [
      cartao("Relatório de Justificativa", "3.4.2 Critérios para contratação", p(
        `O critério de julgamento será o de menor valor total do lote, obtido mediante aplicação da relação de proporcionalidade do maior desconto ofertado sobre o item de referência "${referencia}".`,
      )),
      cartao("Relatório de Justificativa", "3.5.2 Pontos de função", p(`VMA = ${marca(dados.regra_vma)}.`) + p(
        `A PRODESP adota como taxa de entrega ou de produtividade mínima, nas tecnologias previstas neste documento, o fator de ${marca(dados.horas_por_pf)} horas por ponto de função.`,
      )),
      cartao("Relatório de Justificativa", "3.6 Proposta comercial", p(
        `A Proposta Comercial com o percentual de desconto proposto no item de referência "${referencia}" deverá ser apresentada juntamente com a planilha dos preços ofertados.`,
      ) + p(
        `A licitante vencedora será definida pela apresentação do menor valor total do lote, apurado a partir do maior desconto percentual ofertado sobre o valor base do item de referência ("${referencia}").`,
      )),
      cartao("Termo de Referência", "2.6 Remuneração por APF", p(`VMA = ${marca(dados.regra_vma)}.`) + p(
        `A PRODESP adota como taxa de entrega ou de produtividade mínima, nas tecnologias previstas neste documento, o fator de ${marca(dados.horas_por_pf)} horas por ponto de função.`,
      ) + p(`2.6.1.3 A medição dos serviços para execução em Pontos de Função será feita de acordo com a técnica de Análise de Pontos de Função (APF), conforme padrão estabelecido pelo IFPUG – International Function Point Users Group, ${snap}.`) + avisoSnap + p(
        `2.6.3 Roteiro de Métricas de Software do SISP, versão ${marca(dados.versao_sisp)}, ou versões posteriores.`,
      )),
      cartao("Termo de Referência", "2.11 Formação de lotes", p(
        `A proposta orçamentária deverá ser apresentada com base no valor ofertado para o nível ou item de referência "${referencia}".`,
      )),
    ].join("");
  },
  habilitacao() {
    return [
      cartao("Relatório de Justificativa", "3.8.1.1 Declarações", p("c) Declaração de ciência quanto aos requisitos de assinatura do contrato, nos termos informados no cadastro:") + p(marca(dados.parceria)) + p(marca(dados.estudo_mercado)) + p(`Certificações profissionais exigidas: ${marcasCertificacoes()}.`) + p(`Regime da exigência: ${marca(dados.regime_certificacao)}.`)),
      cartao("Relatório de Justificativa", "3.8.1.2 Qualificação técnica operacional", p("Atestados específicos informados no cadastro:") + p(marca(dados.atestados)) + p(
        `A empresa deverá comprovar a contratação de serviços profissionais do fabricante nos últimos 12 meses, com volume mínimo de ${marca(dados.horas_professional)} horas.`,
      )),
      cartao("Relatório de Justificativa", "3.11.2 Parceiro, estudo de mercado e certificações", p(marca(dados.parceria)) + p(marca(dados.estudo_mercado)) + htmlCertificacoes()),
    ].join("");
  },
  certificacoes() {
    return [
      cartao("Relatório de Justificativa", "3.8.1.1 Declarações", p(`Certificações profissionais exigidas: ${marcasCertificacoes()}.`) + p(`Regime da exigência: ${marca(dados.regime_certificacao)}.`)),
      cartao("Relatório de Justificativa", "3.11.2 Parceiro, estudo de mercado e certificações", htmlCertificacoes()),
      cartao("Termo de Referência", "3.3 Certificações", p(marca(dados.regime_certificacao)) + htmlCertificacoes()),
    ].join("");
  },
  elaboracao() {
    const pessoas = htmlPessoas();
    const local = p(marca(dados.local_data));
    return [
      cartao("Relatório de Justificativa", "9. Elaboração", p(marca(dados.area_elaboracao))),
      cartao("Relatório de Justificativa", "10. Aprovação", local + pessoas),
      cartao("Termo de Referência", "6. Elaboração", p(marca(dados.texto_elaboracao))),
      cartao("Termo de Referência", "7. Aprovação", local + pessoas),
    ].join("");
  },
};

function abrirEncaixe(chave) {
  lerFormulario();
  const montar = ENCAIXES[chave];
  if (!montar) return;
  const titulos = {
    identificacao: "Identificação",
    objeto: "Objeto",
    catalogo: "Catálogo da tecnologia",
    clientes: "Clientes e projetos",
    perfis: "Perfis",
    medicao: "Medição e julgamento",
    habilitacao: "Habilitação da tecnologia",
    certificacoes: "Certificações",
    elaboracao: "Elaboração e aprovação",
  };
  document.getElementById("encaixe-titulo").textContent = titulos[chave];
  document.getElementById("encaixe-corpo").innerHTML = montar();
  document.getElementById("painel-encaixe").classList.remove("oculto");
}

function fecharEncaixe() {
  document.getElementById("painel-encaixe").classList.add("oculto");
}

document.querySelectorAll(".ver-doc").forEach((botao) => {
  botao.addEventListener("click", () => abrirEncaixe(botao.dataset.encaixe));
});
document.getElementById("encaixe-fechar").addEventListener("click", fecharEncaixe);
document.getElementById("painel-encaixe").addEventListener("click", (evento) => {
  if (evento.target.id === "painel-encaixe") fecharEncaixe();
});
document.addEventListener("keydown", (evento) => {
  if (evento.key !== "Escape") return;
  fecharEncaixe();
  fecharPainelSei();
  fecharPainelTipoProcesso();
  fecharPainelDecreto();
  fecharPainelContratacao();
  fecharPainelInclusaoDocumento();
  fecharPainelNovo();
  fecharBuscaSei();
  fecharPainelCertificacoes();
  fecharPainelIaCampo();
});

document.getElementById("sei-fechar").addEventListener("click", fecharPainelSei);
document.getElementById("sei-cancelar").addEventListener("click", fecharPainelSei);
document.getElementById("sei-confirmar").addEventListener("click", confirmarEnvioSei);
document.getElementById("painel-sei").addEventListener("click", (evento) => {
  if (evento.target.id === "painel-sei") fecharPainelSei();
});
document.getElementById("numero-sei").addEventListener("keydown", (evento) => {
  if (evento.key === "Enter") {
    evento.preventDefault();
    confirmarEnvioSei();
  }
});

async function carregarSessaoSei() {
  const resposta = await fetch("/api/sei/sessao");
  const corpo = await lerRespostaApi(resposta);
  if (!resposta.ok || !corpo.autenticado) {
    window.location.replace("/");
    return false;
  }
  csrfSei = corpo.csrf_token || "";
  campo("sei-sessao-status").textContent = `Conectado ao SEI como ${corpo.usuario}`;
  return true;
}

async function sairDoSei() {
  const botao = campo("sei-logout");
  botao.disabled = true;
  try {
    const resposta = await fetch("/api/sei/logout", {
      method: "POST",
      headers: { "X-CSRF-Token": csrfSei },
    });
    const corpo = await lerRespostaApi(resposta);
    if (!resposta.ok) throw new Error(corpo.mensagem || "Não foi possível encerrar a sessão SEI.");
    window.location.replace("/");
  } catch (erro) {
    mensagemContratacao(erro.message);
  } finally {
    botao.disabled = false;
  }
}

campo("sei-logout").addEventListener("click", sairDoSei);

document.getElementById("novo-fechar").addEventListener("click", fecharPainelNovo);
document.getElementById("painel-novo").addEventListener("click", (evento) => {
  if (evento.target.id === "painel-novo") fecharPainelNovo();
});
document.querySelectorAll("[data-modo]").forEach((botao) => {
  botao.addEventListener("click", () => {
    const modo = botao.dataset.modo;
    if (modo === "novo") iniciarNovoEmBranco();
    if (modo === "aditar") abrirBuscaSei("Aditamento");
    if (modo === "prorrogar") abrirBuscaSei("Prorrogação");
  });
});

document.getElementById("tipo-processo-fechar").addEventListener("click", fecharPainelTipoProcesso);
document.getElementById("tipo-processo-voltar").addEventListener("click", () => {
  fecharPainelTipoProcesso();
  abrirPainelNovo();
});
document.getElementById("painel-tipo-processo").addEventListener("click", (evento) => {
  if (evento.target.id === "painel-tipo-processo") fecharPainelTipoProcesso();
});
document.getElementById("tipo-processo-continuar").addEventListener("click", continuarNovoComTipo);
document.getElementById("adicionar-tipo-processo").addEventListener("click", adicionarTipoProcessoSei);
document.getElementById("novo-tipo-processo").addEventListener("keydown", (evento) => {
  if (evento.key === "Enter") {
    evento.preventDefault();
    adicionarTipoProcessoSei();
  }
});
document.getElementById("lista-tipos-processo").addEventListener("click", (evento) => {
  const botao = evento.target.closest("[data-tipo-processo-id]");
  if (!botao) return;
  const selecionado = tiposProcessoSei.find((tipo) => String(tipo.id) === botao.dataset.tipoProcessoId);
  if (!selecionado) return;
  tipoProcessoSelecionado = selecionado.nome;
  dados.tipo_processo_sei_id = selecionado.id_sei || "";
  desenharTiposProcessoSei();
});
document.getElementById("filtro-tipo-processo").addEventListener("input", desenharTiposProcessoSei);
document.getElementById("filtro-tipo-processo").addEventListener("focus", desenharTiposProcessoSei);
document.getElementById("filtro-tipo-processo").addEventListener("click", desenharTiposProcessoSei);

document.getElementById("decreto-fechar").addEventListener("click", fecharPainelDecreto);
document.getElementById("painel-decreto").addEventListener("click", (evento) => {
  if (evento.target.id === "painel-decreto") fecharPainelDecreto();
});
document.getElementById("decreto-voltar").addEventListener("click", () => {
  lerFormularioProcessoSei();
  localStorage.setItem(chave, JSON.stringify(dados));
  fecharPainelDecreto();
  document.getElementById("painel-tipo-processo").classList.remove("oculto");
});
document.getElementById("decreto-continuar").addEventListener("click", continuarDecretoParaDocumentos);
document.getElementById("decreto-criar-sei").addEventListener("click", criarProcessoNoSei);
document.getElementById("painel-decreto").addEventListener("input", () => {
  salvar();
  marcarDecretoAlterado();
});
document.getElementById("painel-decreto").addEventListener("change", () => {
  salvar();
  marcarDecretoAlterado();
});
document.querySelectorAll('input[name="decreto-protocolo"]').forEach((radio) => {
  radio.addEventListener("change", atualizarCampoNumeroProtocolo);
});
document.getElementById("decreto-adicionar-assunto").addEventListener("click", () => {
  adicionarItemProcessoSei("assuntos", "decreto-assunto-novo");
});
document.getElementById("decreto-adicionar-interessado").addEventListener("click", () => {
  adicionarItemProcessoSei("interessados", "decreto-interessado-novo");
});
["decreto-assunto-novo", "decreto-interessado-novo"].forEach((id) => {
  campo(id).addEventListener("keydown", (evento) => {
    if (evento.key !== "Enter") return;
    evento.preventDefault();
    campo(id === "decreto-assunto-novo" ? "decreto-adicionar-assunto" : "decreto-adicionar-interessado").click();
  });
});
document.getElementById("decreto-assuntos").addEventListener("click", removerItemProcessoSei);
document.getElementById("decreto-interessados").addEventListener("click", removerItemProcessoSei);
document.getElementById("contratacao-fechar").addEventListener("click", fecharPainelContratacao);
document.getElementById("painel-contratacao").addEventListener("click", (evento) => {
  if (evento.target.id === "painel-contratacao") fecharPainelContratacao();
});
document.getElementById("contratacao-voltar").addEventListener("click", () => {
  salvar();
  fecharPainelContratacao();
  document.getElementById("painel-tipo-processo").classList.remove("oculto");
});
document.getElementById("contratacao-criar-sei").addEventListener("click", criarProcessoNoSei);
document.getElementById("contratacao-anexar-documento").addEventListener("click", abrirPainelDocumentoInternoSei);
document.getElementById("documento-interno-sei-fechar").addEventListener("click", fecharPainelDocumentoInternoSei);
document.getElementById("documento-interno-sei-cancelar").addEventListener("click", fecharPainelDocumentoInternoSei);
document.getElementById("painel-documento-interno-sei").addEventListener("click", (evento) => {
  if (evento.target.id === "painel-documento-interno-sei") fecharPainelDocumentoInternoSei();
});
document.getElementById("documento-interno-sei-form").addEventListener("submit", cadastrarDocumentoInternoNoSei);
document.getElementById("sei-doc-id-serie")?.addEventListener("change", () => {
  aplicarSugestoesCamposPorTipoDocumento();
});
campo("sei-doc-assunto-filtro")?.addEventListener("focus", () => desenharListaAssuntosDocumentoSei());
campo("sei-doc-assunto-filtro")?.addEventListener("click", () => desenharListaAssuntosDocumentoSei());
campo("sei-doc-assunto-filtro")?.addEventListener("input", () => desenharListaAssuntosDocumentoSei());
campo("sei-doc-assuntos-lista")?.addEventListener("click", (evento) => {
  const botao = evento.target.closest("[data-assunto-doc-id]");
  if (!botao) return;
  selecionarAssuntoDocumentoSei(botao.dataset.assuntoDocId, botao.dataset.assuntoDocNome);
});
campo("sei-doc-assuntos-selecionados")?.addEventListener("click", (evento) => {
  const botao = evento.target.closest("[data-indice-assunto-doc]");
  if (!botao) return;
  assuntosDocumentoSeiSelecionados.splice(Number(botao.dataset.indiceAssuntoDoc), 1);
  desenharAssuntosDocumentoSeiSelecionados();
  desenharListaAssuntosDocumentoSei();
});
document.querySelectorAll('input[name="sei-doc-texto-inicial"]').forEach((radio) => {
  radio.addEventListener("change", () => {
    const valor = document.querySelector('input[name="sei-doc-texto-inicial"]:checked')?.value || "nenhum";
    if (valor === "nenhum") {
      blocoCampoDocumentoSei("idTextoPadraoInterno")?.classList.add("oculto");
      return;
    }
    revelarCampoDocumentoSei("idTextoPadraoInterno", { focar: false });
  });
});
document.getElementById("documento-interno-sei-revisar").addEventListener("click", liberarNovaTentativaDocumentoSei);
document.getElementById("documento-interno-sei-revisar-lista").addEventListener("click", liberarNovaTentativaDocumentoSei);
document.getElementById("documento-interno-sei-carregar-secoes").addEventListener("click", carregarConteudoDocumentoSei);
document.getElementById("documento-interno-sei-alterar").addEventListener("click", alterarConteudoDocumentoSei);
document.getElementById("documento-interno-sei-revisar-alteracao").addEventListener("click", liberarNovaAlteracaoDocumentoSei);
document.getElementById("documento-interno-sei-formulario-abrir").addEventListener("click", navegarParaFormularioDocumentoSei);
document.getElementById("preencher-secao-fechar")?.addEventListener("click", () => {
  voltarDoFormularioParaListaDocumentos();
});
document.getElementById("preencher-secao-voltar")?.addEventListener("click", () => {
  voltarDoFormularioParaListaDocumentos();
});
document.getElementById("painel-preencher-secao")?.addEventListener("click", (evento) => {
  if (evento.target.id === "painel-preencher-secao") voltarDoFormularioParaListaDocumentos();
});
document.getElementById("documento-interno-sei-formulario-selecionar").addEventListener("click", selecionarFormularioDocumentoSei);
document.getElementById("documento-interno-sei-visualizar").addEventListener("click", visualizarFormularioDocumentoSei);
document.getElementById("documento-interno-sei-criar-novo").addEventListener("click", iniciarOutroDocumentoInternoSei);
document.getElementById("documento-interno-sei-lista").addEventListener("click", abrirDocumentoInternoSeiDaLista);
document.getElementById("documento-interno-sei-voltar-lista").addEventListener("click", mostrarListaDocumentosInternosSei);
document.getElementById("documento-interno-sei-outro").addEventListener("click", iniciarOutroDocumentoInternoSei);
document.getElementById("sei-doc-secao").addEventListener("change", mostrarConteudoSecaoAtual);
document.getElementById("sei-doc-formulario").addEventListener("change", limparPreviaFormularioDocumentoSei);
document.getElementById("documento-interno-sei-formulario-campos").addEventListener("input", limparPreviaFormularioDocumentoSei);
document.getElementById("documento-interno-sei-formulario-campos").addEventListener("change", limparPreviaFormularioDocumentoSei);
document.getElementById("documento-interno-sei-formulario-campos").addEventListener("click", (evento) => {
  manipularTabelaFormularioDocumentoSei(evento);
});

function definirVisibilidadeAssistenteIaFlutuante(visivel) {
  const dock = document.getElementById("assistente-ia-flutuante");
  if (!dock) return;
  dock.classList.toggle("oculto", !visivel);
  if (!visivel) definirEstadoAssistenteIa(false);
}

function definirEstadoAssistenteIa(aberto) {
  const painel = document.getElementById("assistente-ia-painel");
  const botao = document.getElementById("assistente-ia-abrir");
  if (!painel || !botao) return;
  painel.classList.toggle("oculto", !aberto);
  botao.setAttribute("aria-expanded", aberto ? "true" : "false");
  botao.classList.toggle("oculto", aberto);
  if (aberto) document.getElementById("assistente-ia-prompt")?.focus();
}

function atualizarContadorAssistenteIa() {
  const resposta = document.getElementById("assistente-ia-resposta");
  const contador = document.getElementById("assistente-ia-contador");
  const botaoCopiar = document.getElementById("assistente-ia-copiar");
  const n = (resposta?.value || "").length;
  if (contador) contador.textContent = `(${n})`;
  if (botaoCopiar) botaoCopiar.disabled = !n;
}

async function executarAssistenteIa() {
  const prompt = document.getElementById("assistente-ia-prompt")?.value.trim() || "";
  const estado = document.getElementById("assistente-ia-estado");
  const erro = document.getElementById("assistente-ia-erro");
  const botao = document.getElementById("assistente-ia-buscar");
  const resposta = document.getElementById("assistente-ia-resposta");
  if (!erro || !botao || !resposta) return;
  erro.classList.add("oculto");
  erro.textContent = "";
  if (!prompt) {
    erro.className = "erro";
    erro.classList.remove("oculto");
    erro.textContent = "Escreva o que você deseja buscar.";
    return;
  }
  botao.disabled = true;
  if (estado) estado.textContent = "Gerando resposta com IA…";
  resposta.value = "";
  atualizarContadorAssistenteIa();
  try {
    const tecnologia =
      document.querySelector('[data-form-sei-tag="tecnologia"]')?.value?.trim()
      || dados.tecnologia
      || document.getElementById("tecnologia")?.value
      || "";
    const fetchResposta = await fetch("/api/campos/sugerir", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        consulta: prompt,
        consulta_ia: prompt,
        rotulo: "Assistente IA",
        tecnologia,
        usar_tecnologia: Boolean(document.getElementById("assistente-ia-usar-tecnologia")?.checked),
        historico: [],
      }),
    });
    const corpo = await fetchResposta.json().catch(() => ({}));
    if (!fetchResposta.ok) throw new Error(corpo.mensagem || "Falha na busca com IA.");
    if (corpo.modo === "refinar") {
      const perguntas = (corpo.perguntas || [])
        .map((perg) => perg.pergunta || "")
        .filter(Boolean)
        .join("\n");
      resposta.value = perguntas
        ? `${corpo.mensagem || "A IA pediu mais detalhes:"}\n\n${perguntas}\n\nInclua esses detalhes no prompt e busque de novo.`
        : (corpo.mensagem || "A IA pediu mais detalhes. Refine o prompt e busque de novo.");
      if (estado) estado.textContent = "Refine o prompt e busque novamente.";
      atualizarContadorAssistenteIa();
      return;
    }
    const itens = corpo.itens || [];
    if (!itens.length) throw new Error(corpo.mensagem || "Nenhuma resposta retornada pela IA.");
    resposta.value = itens.map((item) => item.texto || "").filter(Boolean).join("\n\n");
    if (estado) estado.textContent = corpo.mensagem || "Resposta pronta. Copie e cole no campo desejado.";
    atualizarContadorAssistenteIa();
  } catch (falha) {
    if (estado) estado.textContent = "";
    erro.className = "erro";
    erro.classList.remove("oculto");
    erro.textContent = falha.message;
  } finally {
    botao.disabled = false;
  }
}

async function copiarRespostaAssistenteIa() {
  const texto = document.getElementById("assistente-ia-resposta")?.value.trim() || "";
  const erro = document.getElementById("assistente-ia-erro");
  const estado = document.getElementById("assistente-ia-estado");
  if (!texto) return;
  try {
    await navigator.clipboard.writeText(texto);
    if (estado) estado.textContent = "Resposta copiada. Cole no campo desejado.";
    if (erro) {
      erro.classList.add("oculto");
      erro.textContent = "";
    }
  } catch (_) {
    const area = document.getElementById("assistente-ia-resposta");
    area?.focus();
    area?.select();
    if (estado) estado.textContent = "Selecione o texto e use Ctrl+C para copiar.";
  }
}

function limparAssistenteIa() {
  const prompt = document.getElementById("assistente-ia-prompt");
  const resposta = document.getElementById("assistente-ia-resposta");
  const estado = document.getElementById("assistente-ia-estado");
  const erro = document.getElementById("assistente-ia-erro");
  if (prompt) prompt.value = "";
  if (resposta) resposta.value = "";
  if (estado) estado.textContent = "";
  if (erro) {
    erro.classList.add("oculto");
    erro.textContent = "";
  }
  atualizarContadorAssistenteIa();
}

document.getElementById("assistente-ia-abrir")?.addEventListener("click", () => {
  const painel = document.getElementById("assistente-ia-painel");
  definirEstadoAssistenteIa(Boolean(painel?.classList.contains("oculto")));
});
document.getElementById("assistente-ia-fechar")?.addEventListener("click", () => definirEstadoAssistenteIa(false));
document.getElementById("assistente-ia-buscar")?.addEventListener("click", executarAssistenteIa);
document.getElementById("assistente-ia-copiar")?.addEventListener("click", copiarRespostaAssistenteIa);
document.getElementById("assistente-ia-limpar")?.addEventListener("click", limparAssistenteIa);
document.getElementById("assistente-ia-prompt")?.addEventListener("keydown", (evento) => {
  if ((evento.ctrlKey || evento.metaKey) && evento.key === "Enter") {
    evento.preventDefault();
    executarAssistenteIa();
  }
});
document.getElementById("painel-contratacao").addEventListener("input", () => {
  salvar();
  marcarContratacaoAlterado();
});
document.getElementById("painel-contratacao").addEventListener("change", () => {
  salvar();
  marcarContratacaoAlterado();
});
document.getElementById("contratacao-adicionar-interessado").addEventListener("click", () => {
  adicionarItemContratacao("interessados", "contratacao-interessado-novo");
});
campo("contratacao-interessado-novo")?.addEventListener("keydown", (evento) => {
  if (evento.key !== "Enter") return;
  evento.preventDefault();
  campo("contratacao-adicionar-interessado")?.click();
});
document.getElementById("contratacao-assuntos").addEventListener("click", removerItemContratacao);
const filtroAssunto = campo("contratacao-assunto-filtro");
filtroAssunto?.addEventListener("focus", () => desenharListaAssuntosContratacao());
filtroAssunto?.addEventListener("click", () => desenharListaAssuntosContratacao());
filtroAssunto?.addEventListener("input", () => desenharListaAssuntosContratacao());
campo("contratacao-assuntos-lista")?.addEventListener("click", (evento) => {
  const botao = evento.target.closest("[data-assunto-nome]");
  if (!botao) return;
  selecionarAssuntoContratacao(botao.dataset.assuntoNome);
});
document.getElementById("contratacao-interessados").addEventListener("click", removerItemContratacao);

document.getElementById("incluir-documento").addEventListener("click", abrirInclusaoDocumento);
document.getElementById("incluir-documento-fechar").addEventListener("click", fecharPainelInclusaoDocumento);
document.querySelectorAll("[data-fechar-inclusao]").forEach((botao) => {
  botao.addEventListener("click", fecharPainelInclusaoDocumento);
});
document.getElementById("painel-incluir-documento").addEventListener("click", (evento) => {
  if (evento.target.id === "painel-incluir-documento") fecharPainelInclusaoDocumento();
});
document.getElementById("documento-ir-dados").addEventListener("click", abrirDadosDocumento);
document.getElementById("documento-voltar-selecao").addEventListener("click", () => mostrarEtapaDocumento("etapa-documento-selecao"));
document.getElementById("documento-ir-editor").addEventListener("click", abrirEditorDocumento);
document.getElementById("documento-voltar-dados").addEventListener("click", () => mostrarEtapaDocumento("etapa-documento-dados"));
document.getElementById("documento-salvar-anexo").addEventListener("click", salvarDocumentoAnexado);
document.getElementById("editor-conteudo-documento").addEventListener("keydown", (evento) => {
  if (evento.key === "Tab") {
    evento.preventDefault();
    document.execCommand("insertText", false, "    ");
  }
});
document.querySelectorAll("[data-editor-command]").forEach((botao) => {
  botao.addEventListener("mousedown", (evento) => evento.preventDefault());
  botao.addEventListener("click", () => {
    document.getElementById("editor-conteudo-documento").focus();
    document.execCommand(botao.dataset.editorCommand, false);
  });
});
document.getElementById("tipo-documento-sei").addEventListener("change", (evento) => {
  tipoDocumentoInclusao = evento.target.value;
});

document.getElementById("busca-sei-fechar").addEventListener("click", fecharBuscaSei);
document.getElementById("busca-sei-cancelar").addEventListener("click", fecharBuscaSei);
document.getElementById("busca-sei-confirmar").addEventListener("click", confirmarBuscaSei);
document.getElementById("painel-busca-sei").addEventListener("click", (evento) => {
  if (evento.target.id === "painel-busca-sei") fecharBuscaSei();
});
document.getElementById("busca-numero-sei").addEventListener("keydown", (evento) => {
  if (evento.key === "Enter") {
    evento.preventDefault();
    confirmarBuscaSei();
  }
});

function fecharPainelCertificacoes() {
  document.getElementById("painel-certificacoes").classList.add("oculto");
}

function abrirPainelCertificacoes(resultado) {
  const lista = document.getElementById("cert-lista");
  const aviso = document.getElementById("cert-aviso");
  const erro = document.getElementById("cert-erro");
  erro.classList.add("oculto");
  erro.textContent = "";
  if (resultado.avisos?.length) {
    aviso.className = "aviso";
    aviso.textContent = resultado.avisos.join(" ");
  } else {
    aviso.classList.add("oculto");
    aviso.textContent = "";
  }
  document.getElementById("cert-ajuda").textContent =
    `Sugestões para ${resultado.tecnologia} com base nos perfis: ${(resultado.perfis || []).join(", ") || "—"}.`;
  lista.innerHTML = (resultado.certificacoes || []).map((item, indice) => `
    <label class="sugestao-cert">
      <input type="checkbox" data-cert-idx="${indice}" checked />
      <span>
        <strong>${escHtml(item.nome)}</strong>
        <span>${escHtml(item.fonte || item.origem || "Sugestão")}</span>
      </span>
    </label>
  `).join("");
  lista.dataset.payload = JSON.stringify(resultado.certificacoes || []);
  document.getElementById("painel-certificacoes").classList.remove("oculto");
}

async function buscarCertificacoes() {
  salvar();
  const botao = document.getElementById("buscar-certificacoes");
  const estado = document.getElementById("estado-certificacoes");
  botao.disabled = true;
  estado.textContent = "Consultando internet e acervo local…";
  mensagem("");
  try {
    const resposta = await fetch("/api/certificacoes/sugerir", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tecnologia: dados.tecnologia,
        perfis: dados.perfis,
      }),
    });
    const corpo = await resposta.json();
    if (!resposta.ok) throw new Error(corpo.mensagem || "Não foi possível sugerir certificações.");
    abrirPainelCertificacoes(corpo);
  } catch (erro) {
    mensagem(erro.message, "erro");
  } finally {
    botao.disabled = false;
    estado.textContent = "";
  }
}

function aplicarCertificacoesSelecionadas() {
  const lista = document.getElementById("cert-lista");
  let sugestoes = [];
  try {
    sugestoes = JSON.parse(lista.dataset.payload || "[]");
  } catch (erro) {
    sugestoes = [];
  }
  const escolhidas = [...lista.querySelectorAll("input[data-cert-idx]:checked")].map((input) => {
    const item = sugestoes[Number(input.dataset.certIdx)];
    return item?.nome || "";
  }).filter(Boolean);
  if (!escolhidas.length) {
    document.getElementById("cert-erro").className = "erro";
    document.getElementById("cert-erro").textContent = "Selecione ao menos uma certificação.";
    return;
  }
  const atuais = certificacoesInformadas();
  const uniao = [...atuais];
  escolhidas.forEach((nome) => {
    if (!uniao.some((item) => item.toLowerCase() === nome.toLowerCase())) uniao.push(nome);
  });
  dados.certificacoes = uniao.length ? uniao : [""];
  localStorage.setItem(chave, JSON.stringify(dados));
  desenhar();
  fecharPainelCertificacoes();
  mensagem(`${escolhidas.length} certificação(ões) aplicada(s) ao formulário. Revise antes de gerar os documentos.`, "ok");
  document.getElementById("certificacoes").scrollIntoView({ behavior: "smooth", block: "center" });
}

document.getElementById("buscar-certificacoes").addEventListener("click", buscarCertificacoes);
document.getElementById("cert-fechar").addEventListener("click", fecharPainelCertificacoes);
document.getElementById("cert-cancelar").addEventListener("click", fecharPainelCertificacoes);
document.getElementById("cert-aplicar").addEventListener("click", aplicarCertificacoesSelecionadas);
document.getElementById("painel-certificacoes").addEventListener("click", (evento) => {
  if (evento.target.id === "painel-certificacoes") fecharPainelCertificacoes();
});

function ativarAba(alvo) {
  document.querySelectorAll(".aba").forEach((item) => {
    const ativa = item.getAttribute("aria-controls") === alvo;
    item.classList.toggle("ativa", ativa);
    item.setAttribute("aria-selected", ativa ? "true" : "false");
  });
  document.querySelectorAll(".painel-aba").forEach((painel) => {
    painel.classList.toggle("ativa", painel.id === alvo);
  });
  if (alvo === "painel-principal") carregarProcessos();
}

function iconeNaoEnviado() {
  return `
    <span class="situacao nao-enviado" title="Ainda não enviado ao SEI">
      <span class="icone-status" aria-hidden="true">
        <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8"/><path d="M12 7v5l3 2"/></svg>
      </span>
      Não enviado
    </span>`;
}

function iconeNumeroRegistrado() {
  return `
    <span class="situacao enviado" title="Número SEI registrado">
      <span class="icone-status" aria-hidden="true">
        <svg viewBox="0 0 24 24"><path d="M5 12.5l4.2 4.2L19 7"/></svg>
      </span>
      Número registrado
    </span>`;
}

function iconeCriadoSEI() {
  return `
    <span class="situacao enviado" title="Processo criado no SEI">
      <span class="icone-status" aria-hidden="true">
        <svg viewBox="0 0 24 24"><path d="M5 12.5l4.2 4.2L19 7"/></svg>
      </span>
      Criado no SEI
    </span>`;
}

function iconePendenteSEI() {
  return `
    <span class="situacao nao-enviado" title="Verifique o SEI antes de qualquer nova tentativa.">
      <span class="icone-status" aria-hidden="true">
        <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8"/><path d="M12 7v5l3 2"/></svg>
      </span>
      Verificar no SEI
    </span>`;
}

function destacarVigencia(ativo) {
  const campo = document.getElementById("campo-vigencia");
  const ajuda = document.getElementById("ajuda-vigencia");
  const rotulo = document.getElementById("rotulo-prazo");
  campo.classList.toggle("destaque-vigencia", Boolean(ativo));
  ajuda.classList.toggle("oculto", !ativo);
  rotulo.textContent = ativo ? "Vigência (prazo em meses)" : "Prazo em meses";
}

function atualizarFaixaOperacao() {
  const faixa = document.getElementById("edicao-atual");
  if (processoEmEdicao) {
    faixa.classList.remove("oculto");
    faixa.className = "ok";
    faixa.textContent = `Editando o processo ${processoEmEdicao.codigo || processoEmEdicao.numero_sei || processoEmEdicao.id} (${modoOperacao}). Use Salvar para gravar alterações no cadastro.`;
    return;
  }
  if (modoOperacao === "Aditamento") {
    faixa.classList.remove("oculto");
    faixa.className = "ok";
    faixa.textContent = "Modo Aditamento: dados carregados do SEI (simulação). Ao gerar, cria um novo registro do tipo Aditamento.";
    return;
  }
  if (modoOperacao === "Prorrogação") {
    faixa.classList.remove("oculto");
    faixa.className = "ok";
    faixa.textContent = "Modo Prorrogação: dados carregados do SEI (simulação). Ajuste a vigência em destaque. Ao gerar, cria um novo registro do tipo Prorrogação.";
    return;
  }
  faixa.classList.add("oculto");
  faixa.textContent = "";
}

function definirEdicao(processo) {
  processoEmEdicao = processo ? {
    id: processo.id,
    codigo: processo.codigo,
    numero_sei: processo.numero_sei || "",
    id_procedimento_sei: processo.id_procedimento_sei || "",
    status: processo.status || "nao_enviado",
  } : null;
  atualizarFaixaOperacao();
}

function definirModoOperacao(modo) {
  modoOperacao = modo || "Abertura";
  destacarVigencia(modoOperacao === "Prorrogação");
  atualizarFaixaOperacao();
}

function aplicarCadastro(cadastro) {
  const base = { ...vazio(), ...(cadastro || {}) };
  ["processo", "interessado", "unidade", "contrato_vigente"].forEach((chaveAntiga) => delete base[chaveAntiga]);
  base.processo_sei = {
    ...vazio().processo_sei,
    ...(base.processo_sei || {}),
  };
  if (!Array.isArray(base.processo_sei.assuntos)) base.processo_sei.assuntos = [ASSUNTO_DECRETO_PADRAO];
  if (!Array.isArray(base.processo_sei.interessados)) base.processo_sei.interessados = [];
  base.processo_contratacao = {
    ...vazio().processo_contratacao,
    ...(base.processo_contratacao || {}),
  };
  if (!Array.isArray(base.processo_contratacao.assuntos)) {
    base.processo_contratacao.assuntos = [];
  }
  if (!Array.isArray(base.processo_contratacao.interessados)) {
    base.processo_contratacao.interessados = [];
  }
  if (!base.processo_contratacao.especificacao && base.processo_contratacao.descricao) {
    base.processo_contratacao.especificacao = base.processo_contratacao.descricao;
  }
  if (!Array.isArray(base.catalogo)) base.catalogo = [];
  if (!Array.isArray(base.clientes) || !base.clientes.length) base.clientes = [listas.clientes()];
  if (!Array.isArray(base.perfis) || !base.perfis.length) base.perfis = [listas.perfis()];
  if (!Array.isArray(base.certificacoes) || !base.certificacoes.length) base.certificacoes = [""];
  if (!Array.isArray(base.aprovadores) || !base.aprovadores.length) base.aprovadores = [listas.aprovadores()];
  dados = base;
  tecnologiaDaArvore = dados.tecnologia;
  arvoreTecnologia = null;
  gruposAbertos = new Set();
  localStorage.setItem(chave, JSON.stringify(dados));
  atualizarTipoProcessoAtual();
  preencherFormularioProcessoSei();
  preencherFormularioContratacao();
  preencherFixos();
  preencherTecnologias();
  desenharArvore();
  desenhar();
  atualizarTotal();
}

function atualizarTipoProcessoAtual() {
  const el = document.getElementById("tipo-processo-atual");
  if (!el) return;
  el.textContent = dados.tipo_processo_sei
    ? `Tipo de processo SEI: ${dados.tipo_processo_sei}`
    : "";
  el.classList.toggle("oculto", !dados.tipo_processo_sei);
}

function abrirPainelNovo() {
  document.getElementById("painel-novo").classList.remove("oculto");
}

function fecharPainelNovo() {
  document.getElementById("painel-novo").classList.add("oculto");
}

function mensagemTipoProcesso(texto, tipo = "erro") {
  const el = document.getElementById("tipo-processo-mensagem");
  el.textContent = texto || "";
  el.className = tipo;
  el.classList.toggle("oculto", !texto);
}

async function lerRespostaApi(resposta) {
  const contentType = resposta.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    if (resposta.status === 404) {
      throw new Error("A rota solicitada não foi encontrada. Reinicie a aplicação e atualize a página.");
    }
    throw new Error(`O servidor respondeu em formato inesperado (HTTP ${resposta.status}).`);
  }
  return resposta.json();
}

function desenharTiposProcessoSei() {
  const lista = document.getElementById("lista-tipos-processo");
  const filtro = document.getElementById("filtro-tipo-processo").value.trim().toLocaleLowerCase();
  const tiposVisiveis = tiposProcessoSei.filter((tipo) => tipo.nome.toLocaleLowerCase().includes(filtro));
  if (!tiposProcessoSei.length) {
    lista.innerHTML = `<p class="lista-tipos-vazia">Nenhum tipo cadastrado. Adicione uma opção para continuar.</p>`;
  } else if (!tiposVisiveis.length) {
    lista.innerHTML = `<p class="lista-tipos-vazia">Nenhum tipo corresponde ao filtro informado.</p>`;
  } else {
    lista.innerHTML = tiposVisiveis.map((tipo) => `
      <button type="button" class="tipo-processo-opcao"
        aria-pressed="${tipo.nome === tipoProcessoSelecionado}"
        data-tipo-processo-id="${tipo.id}">${escHtml(tipo.nome)}</button>
    `).join("");
  }
  document.getElementById("tipo-processo-selecionado").textContent = tipoProcessoSelecionado
    ? `Selecionado: ${tipoProcessoSelecionado}`
    : "Selecione um tipo para continuar.";
  document.getElementById("tipo-processo-continuar").disabled = !tipoProcessoSelecionado;
}

async function carregarTiposProcessoSei() {
  mensagemTipoProcesso("");
  try {
    const resposta = await fetch("/api/tipos-processo-sei");
    const corpo = await lerRespostaApi(resposta);
    if (!resposta.ok) throw new Error(corpo.mensagem || "Não foi possível carregar os tipos de processo.");
    tiposProcessoSei = corpo.tipos || [];
    desenharTiposProcessoSei();
  } catch (erro) {
    tiposProcessoSei = [];
    desenharTiposProcessoSei();
    mensagemTipoProcesso(erro.message);
  }
}

async function adicionarTipoProcessoSei() {
  const entrada = document.getElementById("novo-tipo-processo");
  const nome = entrada.value.trim();
  if (!nome) {
    mensagemTipoProcesso("Informe o nome do tipo de processo.");
    entrada.focus();
    return;
  }
  const botao = document.getElementById("adicionar-tipo-processo");
  botao.disabled = true;
  mensagemTipoProcesso("");
  try {
    const resposta = await fetch("/api/tipos-processo-sei", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nome }),
    });
    const corpo = await lerRespostaApi(resposta);
    if (!resposta.ok) throw new Error(corpo.mensagem || "Não foi possível adicionar o tipo.");
    tiposProcessoSei = corpo.tipos || [];
    tipoProcessoSelecionado = nome;
    dados.tipo_processo_sei_id = tiposProcessoSei.find((tipo) => tipo.nome === nome)?.id_sei || "";
    entrada.value = "";
    document.getElementById("filtro-tipo-processo").value = "";
    desenharTiposProcessoSei();
    mensagemTipoProcesso("Tipo adicionado à lista.", "ok");
  } catch (erro) {
    mensagemTipoProcesso(erro.message);
  } finally {
    botao.disabled = false;
  }
}

function abrirBuscaSei(modo) {
  buscaSeiModo = modo;
  document.getElementById("busca-sei-titulo").textContent =
    modo === "Prorrogação" ? "Prorrogar — buscar SEI" : "Aditivar — buscar SEI";
  document.getElementById("busca-sei-ajuda").textContent =
    "Simulação: digite o número SEI que já aparece na coluna Nº SEI da Principal. Os dados do cadastro serão carregados no formulário.";
  document.getElementById("busca-numero-sei").value = "";
  document.getElementById("busca-sei-erro").classList.add("oculto");
  document.getElementById("busca-sei-erro").textContent = "";
  fecharPainelNovo();
  document.getElementById("painel-busca-sei").classList.remove("oculto");
  document.getElementById("busca-numero-sei").focus();
}

function fecharBuscaSei() {
  buscaSeiModo = null;
  document.getElementById("painel-busca-sei").classList.add("oculto");
}

function iniciarNovoEmBranco() {
  fecharPainelNovo();
  definirEdicao(null);
  definirModoOperacao("Abertura");
  aplicarCadastro(vazio());
  document.getElementById("resultado").classList.add("oculto");
  tipoProcessoSelecionado = "";
  dados.tipo_processo_sei_id = "";
  document.getElementById("novo-tipo-processo").value = "";
  document.getElementById("filtro-tipo-processo").value = "";
  document.getElementById("painel-tipo-processo").classList.remove("oculto");
  desenharTiposProcessoSei();
  carregarTiposProcessoSei();
}

function fecharPainelTipoProcesso() {
  document.getElementById("painel-tipo-processo").classList.add("oculto");
}

function continuarNovoComTipo() {
  if (!tipoProcessoSelecionado) {
    mensagemTipoProcesso("Selecione um tipo de processo para continuar.");
    return;
  }
  dados.tipo_processo_sei = tipoProcessoSelecionado;
  const tipoSelecionado = tiposProcessoSei.find((tipo) => tipo.nome === tipoProcessoSelecionado);
  dados.tipo_processo_sei_id = tipoSelecionado?.id_sei || dados.tipo_processo_sei_id || "";
  salvar();
  atualizarTipoProcessoAtual();
  fecharPainelTipoProcesso();
  // Qualquer tipo abre o formulário Iniciar Processo (ex-Contrato).
  // Decreto mantém o formulário próprio, se ainda for usado.
  if (tipoProcessoSelecionado.trim().toLocaleLowerCase() === "decreto") {
    abrirFormularioDecreto();
    return;
  }
  abrirFormularioContratacao();
}

function irParaFormularioDocumentos() {
  ativarAba("painel-formulario");
  mensagem(`Tipo de processo “${tipoProcessoSelecionado}” selecionado. Continue preenchendo os dados para gerar os documentos.`, "ok");
  document.getElementById("cadastro").scrollIntoView({ behavior: "smooth", block: "start" });
}

function abrirFormularioDecreto() {
  preencherFormularioProcessoSei();
  mensagemDecreto("");
  atualizarEstadoCriacaoSei(processoEmEdicao, "decreto");
  document.getElementById("painel-decreto").classList.remove("oculto");
}

function fecharPainelDecreto() {
  document.getElementById("painel-decreto").classList.add("oculto");
}

function abrirFormularioContratacao() {
  preencherFormularioContratacao();
  mensagemContratacao("");
  atualizarEstadoCriacaoSei();
  campo("painel-contratacao").classList.remove("oculto");
}

function fecharPainelContratacao() {
  campo("painel-contratacao").classList.add("oculto");
}

function normalizarTextoComparacao(texto) {
  return String(texto || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function sugerirAssuntoPorTipoProcesso(tipoNome) {
  const tipoNorm = normalizarTextoComparacao(tipoNome);
  if (!tipoNorm || !assuntosSei.length) return "";
  let melhor = "";
  let melhorScore = 0;
  assuntosSei.forEach((item) => {
    const nome = String(item.nome || "");
    const nomeNorm = normalizarTextoComparacao(nome);
    const semCodigo = nomeNorm.replace(/^\d[\d.\s-]+/, "").trim();
    if (!semCodigo) return;
    if (semCodigo === tipoNorm || nomeNorm.endsWith(tipoNorm) || semCodigo.endsWith(tipoNorm)) {
      melhor = nome;
      melhorScore = Number.MAX_SAFE_INTEGER;
      return;
    }
    if (semCodigo.includes(tipoNorm) || tipoNorm.includes(semCodigo)) {
      const score = Math.min(semCodigo.length, tipoNorm.length);
      if (score > melhorScore) {
        melhorScore = score;
        melhor = nome;
      }
    }
  });
  return melhor;
}

async function obterAssuntoVinculadoTipoProcesso(tipoNome = "", tipoIdSei = "") {
  const idSei = String(tipoIdSei || dados.tipo_processo_sei_id || "").trim();
  const nome = String(tipoNome || dados.tipo_processo_sei || tipoProcessoSelecionado || "").trim();
  if (!idSei && !nome) return null;
  try {
    const params = new URLSearchParams();
    if (idSei) params.set("tipo_processo_id_sei", idSei);
    if (nome) params.set("tipo_processo", nome);
    const resposta = await fetch(`/api/processo-assunto?${params.toString()}`);
    const corpo = await lerRespostaApi(resposta);
    if (!resposta.ok) return null;
    return corpo.assunto || null;
  } catch (_erro) {
    return null;
  }
}

async function aplicarPadroesFormularioContratacao() {
  const processo = dados.processo_contratacao || vazio().processo_contratacao;
  const tipo = dados.tipo_processo_sei || tipoProcessoSelecionado || "";

  if (!(processo.interessados || []).length) {
    processo.interessados = [INTERESSADO_UNIDADE_PADRAO];
  }

  const assuntosAtuais = processo.assuntos || [];
  const soPadraoAntigo = assuntosAtuais.length === 1
    && assuntosAtuais[0] === ASSUNTO_CONTRATACAO_PADRAO;
  if (!assuntosAtuais.length || soPadraoAntigo) {
    const vinculado = await obterAssuntoVinculadoTipoProcesso(tipo, dados.tipo_processo_sei_id);
    if (vinculado?.nome) {
      processo.assuntos = [vinculado.nome];
    } else {
      const sugerido = sugerirAssuntoPorTipoProcesso(tipo);
      processo.assuntos = sugerido ? [sugerido] : [];
    }
  }

  dados.processo_contratacao = processo;
}

function preencherFormularioContratacao() {
  const processo = dados.processo_contratacao || vazio().processo_contratacao;
  const tipo = dados.tipo_processo_sei || tipoProcessoSelecionado || "";
  if (campo("contratacao-tipo")) campo("contratacao-tipo").value = tipo;
  campo("contratacao-especificacao").value = processo.especificacao || processo.descricao || "";
  campo("contratacao-prioridade").value = processo.prioridade || "";
  campo("contratacao-observacoes").value = processo.observacoes || "";
  document.querySelectorAll('input[name="contratacao-nivel-acesso"]').forEach((radio) => {
    radio.checked = radio.value === (processo.nivel_acesso || "publico");
  });
  desenharItensContratacao("assuntos");
  desenharItensContratacao("interessados");
  carregarAssuntosSei().then(async () => {
    await aplicarPadroesFormularioContratacao();
    desenharItensContratacao("assuntos");
    desenharItensContratacao("interessados");
    desenharListaAssuntosContratacao();
    salvar();
  });
}

let assuntosSei = [];

async function carregarAssuntosSei() {
  try {
    const resposta = await fetch("/api/assuntos-sei");
    const corpo = await lerRespostaApi(resposta);
    if (!resposta.ok) throw new Error(corpo.mensagem || "Não foi possível carregar os assuntos.");
    assuntosSei = corpo.assuntos || [];
  } catch (erro) {
    assuntosSei = [];
    mensagemContratacao(erro.message);
  }
  desenharListaAssuntosContratacao();
}

function desenharListaAssuntosContratacao() {
  const lista = campo("contratacao-assuntos-lista");
  const filtroEl = campo("contratacao-assunto-filtro");
  if (!lista || !filtroEl) return;
  const filtro = filtroEl.value.trim().toLocaleLowerCase();
  const selecionados = new Set(
    (dados.processo_contratacao?.assuntos || []).map((item) => String(item).toLocaleLowerCase()),
  );
  const visiveis = assuntosSei.filter((item) =>
    !filtro || String(item.nome || "").toLocaleLowerCase().includes(filtro),
  );
  lista.style.display = "grid";
  if (!assuntosSei.length) {
    lista.innerHTML = `<p class="lista-tipos-vazia">Nenhum assunto cadastrado.</p>`;
    return;
  }
  if (!visiveis.length) {
    lista.innerHTML = `<p class="lista-tipos-vazia">Nenhum assunto corresponde ao termo.</p>`;
    return;
  }
  lista.innerHTML = visiveis.map((item) => `
    <button type="button" class="tipo-processo-opcao"
      aria-pressed="${selecionados.has(String(item.nome).toLocaleLowerCase())}"
      data-assunto-nome="${escHtml(item.nome)}">${escHtml(item.nome)}</button>
  `).join("");
}

function selecionarAssuntoContratacao(nome) {
  const processo = dados.processo_contratacao || vazio().processo_contratacao;
  const itens = processo.assuntos || [];
  const indice = itens.findIndex((item) => item.toLocaleLowerCase() === nome.toLocaleLowerCase());
  if (indice >= 0) {
    itens.splice(indice, 1);
  } else {
    itens.push(nome);
  }
  processo.assuntos = itens;
  dados.processo_contratacao = processo;
  campo("contratacao-assunto-filtro").value = "";
  desenharItensContratacao("assuntos");
  desenharListaAssuntosContratacao();
  salvar();
  marcarContratacaoAlterado();
}

function mensagemContratacao(texto, tipo = "erro") {
  const el = campo("contratacao-mensagem");
  if (!el) return;
  el.textContent = texto || "";
  el.className = tipo;
  el.classList.toggle("oculto", !texto);
}

function atualizarEstadoCriacaoSei(processo = processoEmEdicao, prefixo = "contratacao") {
  const botao = campo(`${prefixo}-criar-sei`);
  const botaoDocumento = prefixo === "contratacao"
    ? campo("contratacao-anexar-documento")
    : null;
  const retorno = campo(`${prefixo}-sei-retorno`);
  const protocolo = campo(prefixo === "decreto" ? "decreto-protocolo-sei" : "contratacao-protocolo-sei");
  const idProcedimento = campo(prefixo === "decreto" ? "decreto-id-procedimento-sei" : "contratacao-id-procedimento-sei");
  const status = campo(prefixo === "decreto" ? "decreto-sei-status" : "contratacao-sei-status");
  const temProtocolo = Boolean(processo?.numero_sei);
  const temProcedimento = Boolean(processo?.id && processo?.id_procedimento_sei);
  const incerto = ["criando_sei", "criacao_indeterminada"].includes(processo?.status);

  botao.disabled = temProtocolo || incerto || processo?.status === "enviado";
  if (botaoDocumento) {
    botaoDocumento.disabled = !temProcedimento || incerto || processo?.status === "criando_sei";
  }
  retorno.classList.toggle("oculto", !temProtocolo && !incerto);
  if (temProtocolo) {
    status.textContent = processo.id_procedimento_sei
      ? "Processo criado no SEI de homologação — protocolo"
      : "Número SEI já registrado";
    protocolo.textContent = processo.numero_sei;
    idProcedimento.textContent = processo.id_procedimento_sei
      ? `ID do procedimento: ${processo.id_procedimento_sei}`
      : "";
  } else if (incerto) {
    status.textContent =
      "A resposta do SEI não foi confirmada. Consulte o SEI antes de qualquer nova tentativa.";
    protocolo.textContent = "";
    idProcedimento.textContent = "";
  } else {
    protocolo.textContent = "";
    idProcedimento.textContent = "";
  }
}

function marcarContratacaoAlterado() {
  atualizarEstadoCriacaoSei(processoEmEdicao);
  if (!processoEmEdicao?.id_procedimento_sei) {
    mensagemContratacao("Os dados serão enviados ao SEI ao criar o processo.", "aviso");
  }
}

function desenharItensContratacao(tipo) {
  const processo = dados.processo_contratacao || vazio().processo_contratacao;
  const hostId = tipo === "assuntos" ? "contratacao-assuntos" : "contratacao-interessados";
  const host = campo(hostId);
  host.replaceChildren();
  (processo[tipo] || []).forEach((valor, indice) => {
    const item = document.createElement("div");
    item.className = "item-decreto";
    const texto = document.createElement("span");
    texto.textContent = valor;
    const remover = document.createElement("button");
    remover.type = "button";
    remover.className = "remover";
    remover.textContent = "Remover";
    remover.dataset.listaContratacao = tipo;
    remover.dataset.indiceContratacao = String(indice);
    remover.setAttribute("aria-label", `Remover ${valor}`);
    item.append(texto, remover);
    host.append(item);
  });
}

function adicionarItemContratacao(tipo, entradaId) {
  const entrada = campo(entradaId);
  const valor = entrada.value.trim();
  const processo = dados.processo_contratacao || vazio().processo_contratacao;
  if (!valor) {
    mensagemContratacao("Digite um item antes de adicionar.");
    return;
  }
  const itens = processo[tipo] || [];
  if (itens.some((item) => item.toLocaleLowerCase() === valor.toLocaleLowerCase())) {
    mensagemContratacao("Esse item já está na lista.");
    return;
  }
  itens.push(valor);
  processo[tipo] = itens;
  dados.processo_contratacao = processo;
  entrada.value = "";
  mensagemContratacao("");
  desenharItensContratacao(tipo);
  salvar();
  marcarContratacaoAlterado();
}

function removerItemContratacao(evento) {
  const botao = evento.target.closest("[data-lista-contratacao]");
  if (!botao) return;
  const tipo = botao.dataset.listaContratacao;
  const indice = Number(botao.dataset.indiceContratacao);
  const processo = dados.processo_contratacao;
  if (!Array.isArray(processo?.[tipo]) || !Number.isInteger(indice)) return;
  processo[tipo].splice(indice, 1);
  desenharItensContratacao(tipo);
  salvar();
  marcarContratacaoAlterado();
}

function preencherFormularioProcessoSei() {
  const processoSei = dados.processo_sei || vazio().processo_sei;
  document.querySelectorAll('input[name="decreto-protocolo"]').forEach((radio) => {
    radio.checked = radio.value === processoSei.protocolo;
  });
  campo("decreto-numero-protocolo").value = processoSei.numero_protocolo || "";
  campo("decreto-especificacao").value = processoSei.especificacao || "";
  campo("decreto-prioridade").value = processoSei.prioridade || "";
  campo("decreto-observacoes").value = processoSei.observacoes || "";
  document.querySelectorAll('input[name="decreto-nivel-acesso"]').forEach((radio) => {
    radio.checked = radio.value === processoSei.nivel_acesso;
  });
  obterAssuntoVinculadoTipoProcesso(dados.tipo_processo_sei, dados.tipo_processo_sei_id).then((vinculado) => {
    if (vinculado?.nome) {
      const atuais = processoSei.assuntos || [];
      const soPadrao = atuais.length === 1 && atuais[0] === ASSUNTO_DECRETO_PADRAO;
      if (!atuais.length || soPadrao) {
        processoSei.assuntos = [vinculado.nome];
        dados.processo_sei = processoSei;
        desenharItensProcessoSei("assuntos");
        salvar();
      }
    }
  });
  desenharItensProcessoSei("assuntos");
  desenharItensProcessoSei("interessados");
  atualizarCampoNumeroProtocolo();
}

function atualizarCampoNumeroProtocolo() {
  const informado = document.querySelector('input[name="decreto-protocolo"]:checked')?.value === "informado";
  const bloco = campo("campo-numero-protocolo");
  bloco.classList.toggle("oculto", !informado);
}

function mensagemDecreto(texto, tipo = "erro") {
  const el = campo("decreto-mensagem");
  el.textContent = texto || "";
  el.className = tipo;
  el.classList.toggle("oculto", !texto);
}

function marcarDecretoAlterado() {
  atualizarEstadoCriacaoSei(processoEmEdicao, "decreto");
  if (!processoEmEdicao?.id_procedimento_sei) {
    mensagemDecreto("Os dados serão enviados ao SEI ao criar o processo.", "aviso");
  }
}

function desenharItensProcessoSei(tipo) {
  const plural = tipo === "assuntos" ? "assuntos" : "interessados";
  const hostId = tipo === "assuntos" ? "decreto-assuntos" : "decreto-interessados";
  const host = campo(hostId);
  host.replaceChildren();
  (dados.processo_sei?.[plural] || []).forEach((valor, indice) => {
    const item = document.createElement("div");
    item.className = "item-decreto";
    const texto = document.createElement("span");
    texto.textContent = valor;
    const remover = document.createElement("button");
    remover.type = "button";
    remover.className = "remover";
    remover.textContent = "Remover";
    remover.dataset.listaDecreto = plural;
    remover.dataset.indiceDecreto = String(indice);
    remover.setAttribute("aria-label", `Remover ${valor}`);
    item.append(texto, remover);
    host.append(item);
  });
}

function adicionarItemProcessoSei(tipo, entradaId) {
  const entrada = campo(entradaId);
  const valor = entrada.value.trim();
  const mensagemEl = campo("decreto-mensagem");
  if (!valor) {
    mensagemEl.textContent = "Digite um item antes de adicionar.";
    mensagemEl.className = "erro";
    return;
  }
  const itens = dados.processo_sei[tipo] || [];
  if (itens.some((item) => item.toLocaleLowerCase() === valor.toLocaleLowerCase())) {
    mensagemEl.textContent = "Esse item já está na lista.";
    mensagemEl.className = "erro";
    return;
  }
  itens.push(valor);
  dados.processo_sei[tipo] = itens;
  entrada.value = "";
  mensagemDecreto("");
  desenharItensProcessoSei(tipo);
  salvar();
  marcarDecretoAlterado();
}

function removerItemProcessoSei(evento) {
  const botao = evento.target.closest("[data-lista-decreto]");
  if (!botao) return;
  const tipo = botao.dataset.listaDecreto;
  const indice = Number(botao.dataset.indiceDecreto);
  if (!Array.isArray(dados.processo_sei?.[tipo]) || !Number.isInteger(indice)) return;
  dados.processo_sei[tipo].splice(indice, 1);
  desenharItensProcessoSei(tipo);
  salvar();
  marcarDecretoAlterado();
}

function continuarDecretoParaDocumentos() {
  if (!processoEmEdicao?.id_procedimento_sei) {
    mensagemDecreto("Crie o processo no SEI antes de continuar.");
    return;
  }
  fecharPainelDecreto();
  irParaFormularioDocumentos();
}

async function criarProcessoNoSei() {
  salvar();
  const ehDecreto = !campo("painel-decreto").classList.contains("oculto");
  const prefixo = ehDecreto ? "decreto" : "contratacao";
  const mostrarMensagem = ehDecreto ? mensagemDecreto : mensagemContratacao;
  const assuntosSelecionados = ehDecreto
    ? (dados.processo_sei?.assuntos || [])
    : (dados.processo_contratacao?.assuntos || []);
  if (!(assuntosSelecionados || []).filter(Boolean).length) {
    mostrarMensagem("Selecione ao menos um assunto na Classificação por Assuntos. Campo obrigatório.");
    return;
  }
  if (!csrfSei) {
    const autenticado = await carregarSessaoSei().then(() => retomarAberturaIaSeHouver());
    if (!autenticado) return;
  }
  if (!window.confirm(
    "Esta ação criará um processo real no SEI de homologação. Deseja continuar?",
  )) return;

  const botao = campo(`${prefixo}-criar-sei`);
  botao.disabled = true;
  mostrarMensagem("Enviando solicitação de criação ao SEI de homologação…", "aviso");
  try {
    const url = processoEmEdicao?.id
      ? `/api/processos/${processoEmEdicao.id}/criar-no-sei`
      : "/api/processos/criar-no-sei";
    const resposta = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfSei,
      },
      body: JSON.stringify({
        ...dados,
        tipo_processo: modoOperacao || "Abertura",
      }),
    });
    const corpo = await lerRespostaApi(resposta);
    if (!resposta.ok) {
      if (resposta.status === 401) {
        window.location.replace("/");
      }
      if (corpo.processo) {
        definirEdicao(corpo.processo);
        atualizarEstadoCriacaoSei(corpo.processo, prefixo);
        await carregarProcessos();
      }
      if (corpo.resultado_incerto && processoEmEdicao) {
        processoEmEdicao.status = "criacao_indeterminada";
        atualizarEstadoCriacaoSei(processoEmEdicao, prefixo);
      }
      throw new Error(corpo.mensagem || "Não foi possível criar o processo no SEI.");
    }
    definirEdicao(corpo.processo);
    if (!dados.extras || typeof dados.extras !== "object") dados.extras = {};
    dados.extras.n_processo_sei = corpo.processo.numero_sei;
    localStorage.setItem(chave, JSON.stringify(dados));
    const campoNumeroProcesso = campo("extra-n_processo_sei");
    if (campoNumeroProcesso) campoNumeroProcesso.value = corpo.processo.numero_sei;
    atualizarEstadoCriacaoSei(corpo.processo, prefixo);
    await carregarProcessos();
    mostrarMensagem(
      `Processo criado no SEI: ${corpo.processo.numero_sei}.`,
      "ok",
    );
  } catch (erro) {
    mostrarMensagem(erro.message);
  } finally {
    if (!processoEmEdicao?.numero_sei && !["criando_sei", "criacao_indeterminada"].includes(processoEmEdicao?.status)) {
      botao.disabled = false;
    }
  }
}

function chaveResultadoIncertoDocumentoSei() {
  return `gcpd-documento-sei-incerto-${processoEmEdicao?.id || ""}`;
}

function chaveEstadoDocumentoInternoSei() {
  return `${chaveDocumentoSeiPrefixo}${processoEmEdicao?.id || ""}-${documentoSeiAtivoId}`;
}

function estadoDocumentoInternoSei(documentoId = documentoSeiAtivoId) {
  const chaveEstado = `${chaveDocumentoSeiPrefixo}${processoEmEdicao?.id || ""}-${documentoId}`;
  const salvo = localStorage.getItem(chaveEstado);
  if (!salvo) return null;
  try {
    return JSON.parse(salvo);
  } catch (erro) {
    throw new Error("O estado local do documento SEI está inválido. Remova os dados locais deste cadastro antes de continuar.");
  }
}

function salvarEstadoDocumentoInternoSei(estado) {
  localStorage.setItem(chaveEstadoDocumentoInternoSei(), JSON.stringify(estado));
}

function migrarEstadoDocumentoSeiLegado(documento) {
  const chaveLegada = `${chaveDocumentoSeiPrefixo}${processoEmEdicao?.id || ""}`;
  const salvo = localStorage.getItem(chaveLegada);
  if (!salvo) return null;
  try {
    const estado = JSON.parse(salvo);
    if (String(estado.id_documento || "") !== String(documento.id_documento_sei)) return null;
    localStorage.setItem(
      `${chaveDocumentoSeiPrefixo}${processoEmEdicao.id}-${documento.id_documento_sei}`,
      JSON.stringify(estado),
    );
    localStorage.removeItem(chaveLegada);
    return estado;
  } catch (erro) {
    throw new Error("O estado local de um documento SEI está inválido. Consulte o administrador antes de continuar.");
  }
}

async function carregarListaDocumentosInternosSei() {
  const itens = campo("documento-interno-sei-itens");
  const vazioLista = campo("documento-interno-sei-lista-vazia");
  const incerto = localStorage.getItem(chaveResultadoIncertoDocumentoSei()) === "1";
  campo("documento-interno-sei-lista-mensagem").textContent = incerto
    ? "A tentativa anterior de cadastro pode ter sido concluída no SEI. Verifique antes de permitir outro cadastro."
    : "";
  campo("documento-interno-sei-lista-mensagem").classList.toggle("oculto", !incerto);
  campo("documento-interno-sei-revisar-lista").classList.toggle("oculto", !incerto);
  campo("documento-interno-sei-criar-novo").disabled = incerto;
  itens.replaceChildren();
  try {
    const resposta = await fetch(`/api/processos/${processoEmEdicao.id}/documentos-sei`);
    const corpo = await lerRespostaApi(resposta);
    if (!resposta.ok) {
      if (resposta.status === 401) window.location.replace("/");
      throw new Error(corpo.mensagem || "Não foi possível carregar os documentos já cadastrados.");
    }
    const documentos = corpo.documentos || [];
    documentos.forEach((documento) => {
      const id = String(documento.id_documento_sei);
      const estado = estadoDocumentoInternoSei(id) || migrarEstadoDocumentoSeiLegado(documento);
      const item = document.createElement("article");
      item.className = "item-documento-sei";
      const descricao = document.createElement("strong");
      descricao.textContent = documento.descricao || `Documento ${id}`;
      const protocolo = document.createElement("span");
      const detalhes = [];
      if (documento.protocolo) detalhes.push(`Protocolo ${documento.protocolo}`);
      if (documento.tipo_documento) {
        detalhes.push(`Tipo ${documento.tipo_documento} (ID ${documento.id_serie})`);
      }
      detalhes.push(`ID ${id}`);
      protocolo.textContent = detalhes.join(" · ");
      const situacao = document.createElement("span");
      situacao.className = "ajuda";
      situacao.textContent = estado?.status === "concluido"
        ? "Conteúdo incluído"
        : "Aguardando inclusão do conteúdo";
      const continuar = document.createElement("button");
      continuar.type = "button";
      continuar.className = "acao";
      continuar.dataset.documentoSeiId = id;
      continuar.textContent = estado?.status === "concluido" ? "Ver documento" : "Incluir conteúdo";
      item.append(descricao, protocolo, situacao, continuar);
      itens.append(item);
    });
    vazioLista.classList.toggle("oculto", documentos.length !== 0);
    return documentos;
  } catch (erro) {
    vazioLista.classList.remove("oculto");
    vazioLista.textContent = erro.message;
    return [];
  }
}

async function mostrarListaDocumentosInternosSei() {
  documentoSeiAtivoId = "";
  formularioDocumentoSeiSelecionado = null;
  valoresFormularioDocumentoSei = {};
  conteudoHtmlFormularioSei = "";
  campo("documento-interno-sei-lista").classList.remove("oculto");
  campo("documento-interno-sei-ajuda-metadados").classList.add("oculto");
  campo("documento-interno-sei-metadados").classList.add("oculto");
  campo("documento-interno-sei-conteudo").classList.add("oculto");
  campo("documento-interno-sei-formulario-painel").classList.add("oculto");
  campo("documento-interno-sei-enviar").classList.add("oculto");
  mensagemDocumentoInternoSei("");
  mensagemConteudoDocumentoInternoSei("");
  await carregarListaDocumentosInternosSei();
}

async function abrirDocumentoInternoSeiDaLista(evento) {
  const botao = evento.target.closest("[data-documento-sei-id]");
  if (!botao) return;
  documentoSeiAtivoId = botao.dataset.documentoSeiId;
  let estado;
  try {
    estado = estadoDocumentoInternoSei();
  } catch (erro) {
    mensagemConteudoDocumentoInternoSei(erro.message);
    return;
  }
  if (!estado) {
    const documento = (await carregarListaDocumentosInternosSei())
      .find((item) => String(item.id_documento_sei) === documentoSeiAtivoId);
    if (!documento) return;
    estado = {
      id_documento: documentoSeiAtivoId,
      protocolo: documento.protocolo || "",
      descricao: documento.descricao || "",
      status: "em_andamento",
      alteracao_incerta: false,
    };
    salvarEstadoDocumentoInternoSei(estado);
  }
  campo("documento-interno-sei-lista").classList.add("oculto");
  await prepararEtapaConteudoDocumentoSei(estado, { irDiretoAoFormulario: true });
}

function mensagemDocumentoInternoSei(texto, tipo = "erro") {
  const el = campo("documento-interno-sei-mensagem");
  el.textContent = texto || "";
  el.className = tipo;
  el.classList.toggle("oculto", !texto);
}

function mensagemConteudoDocumentoInternoSei(texto, tipo = "erro") {
  const el = campo("documento-interno-sei-conteudo-mensagem");
  el.textContent = texto || "";
  el.className = tipo;
  el.classList.toggle("oculto", !texto);
}

function fecharPainelDocumentoInternoSei() {
  campo("painel-documento-interno-sei").classList.add("oculto");
}

async function abrirPainelDocumentoInternoSei() {
  if (!processoEmEdicao?.id || !processoEmEdicao?.id_procedimento_sei) {
    mensagemContratacao("Crie o processo no SEI antes de anexar um documento.");
    return;
  }
  if (!csrfSei) {
    const autenticado = await carregarSessaoSei();
    if (!autenticado) return;
  }
  const processo = dados.processo_contratacao || vazio().processo_contratacao;
  documentoSeiAtivoId = "";
  campo("documento-interno-sei-lista").classList.remove("oculto");
  campo("documento-interno-sei-itens").replaceChildren();
  campo("documento-interno-sei-lista-vazia").classList.add("oculto");
  campo("documento-interno-sei-ajuda-metadados").classList.add("oculto");
  campo("documento-interno-sei-metadados").classList.add("oculto");
  campo("documento-interno-sei-conteudo").classList.add("oculto");
  campo("documento-interno-sei-enviar").classList.add("oculto");
  campo("documento-interno-sei-form").reset();
  campo("sei-doc-unidade-geradora").value = "110000001";
  campo("documento-interno-sei-retorno").textContent = "";
  campo("documento-interno-sei-retorno").classList.add("oculto");
  campo("documento-interno-sei-revisar").classList.add("oculto");
  const incerto = localStorage.getItem(chaveResultadoIncertoDocumentoSei()) === "1";
  mensagemDocumentoInternoSei(
    incerto
      ? "O SEI pode ter cadastrado o documento, mas a resposta não foi confirmada. Consulte o processo no SEI antes de liberar outra tentativa."
      : "",
    incerto ? "aviso" : "erro",
  );
  campo("documento-interno-sei-revisar").classList.toggle("oculto", !incerto);
  campo("documento-interno-sei-enviar").disabled = incerto;
  campo("painel-documento-interno-sei").classList.remove("oculto");
  await carregarListaDocumentosInternosSei();
}

async function prepararEtapaConteudoDocumentoSei(estado, opcoes = {}) {
  const irDiretoAoFormulario =
    Boolean(opcoes.irDiretoAoFormulario) &&
    estado.status === "em_andamento" &&
    !estado.alteracao_incerta;
  campo("documento-interno-sei-lista").classList.add("oculto");
  campo("documento-interno-sei-ajuda-metadados").classList.add("oculto");
  campo("documento-interno-sei-metadados").classList.add("oculto");
  campo("documento-interno-sei-enviar").classList.add("oculto");
  // Tela de seções fica oculta no caminho feliz; só aparece em falhas/estados especiais.
  campo("documento-interno-sei-conteudo").classList.toggle("oculto", irDiretoAoFormulario);
  campo("documento-interno-sei-formulario-painel").classList.add("oculto");
  campo("documento-interno-sei-previa").classList.add("oculto");
  campo("documento-interno-sei-previa-html").replaceChildren();
  campo("documento-interno-sei-formulario-abrir").disabled =
    estado.status !== "em_andamento" || Boolean(estado.alteracao_incerta);
  formularioDocumentoSeiSelecionado = null;
  conteudoHtmlFormularioSei = "";
  campo("documento-interno-sei-alteracao-retorno").classList.add("oculto");
  campo("documento-interno-sei-alterar").disabled = true;
  campo("documento-interno-sei-revisar-alteracao").classList.toggle(
    "oculto",
    !estado.alteracao_incerta,
  );
  if (estado.status === "id_ausente") {
    campo("documento-interno-sei-etapa-status").textContent =
      "O SEI confirmou o cadastro, mas não retornou o ID do documento. Consulte o documento no SEI e não repita o cadastro.";
  } else if (estado.status === "vinculo_pendente") {
    campo("documento-interno-sei-etapa-status").textContent =
      `O SEI confirmou o cadastro do documento ${estado.id_documento}, mas o GCPD não conseguiu associá-lo ao processo. Não repita o cadastro; solicite suporte ao administrador.`;
  } else if (estado.status === "concluido") {
    campo("documento-interno-sei-etapa-status").textContent =
      `Conteúdo enviado ao SEI para o documento ${estado.protocolo || estado.id_documento}.`;
  } else {
    campo("documento-interno-sei-etapa-status").textContent =
      `Documento SEI ${estado.protocolo ? `(${estado.protocolo})` : `ID ${estado.id_documento || "pendente"}`} cadastrado. Abrindo o formulário para incluir o conteúdo…`;
  }
  if (estado.status === "vinculo_pendente") {
    campo("documento-interno-sei-conteudo").classList.remove("oculto");
    mensagemConteudoDocumentoInternoSei(
      "A associação local falhou. Por segurança, o GCPD bloqueou a alteração deste documento.",
      "erro",
    );
    return;
  }
  if (irDiretoAoFormulario) {
    const painel = campo("painel-preencher-secao");
    if (painel) painel.classList.remove("oculto");
    definirVisibilidadeAssistenteIaFlutuante(true);
    const msg = campo("preencher-secao-mensagem");
    if (msg) {
      msg.textContent = "Preparando o documento…";
      msg.className = "aviso";
      msg.classList.remove("oculto");
    }
  }
  await carregarConteudoDocumentoSei({ silencioso: irDiretoAoFormulario });
  if (!irDiretoAoFormulario) return;
  if (actualPodeAlterarDocumentoSei(estadoDocumentoInternoSei())) {
    await navegarParaFormularioDocumentoSei();
    return;
  }
  // Falha ao obter seção: volta a mostrar o painel técnico com a mensagem de erro.
  fecharPainelPreencherSecao();
  campo("documento-interno-sei-conteudo").classList.remove("oculto");
}

async function carregarConteudoDocumentoSei(opcoes = {}) {
  const silencioso = Boolean(opcoes.silencioso);
  let estado;
  try {
    estado = estadoDocumentoInternoSei();
  } catch (erro) {
    if (!silencioso) mensagemConteudoDocumentoInternoSei(erro.message);
    const msg = campo("preencher-secao-mensagem");
    if (silencioso && msg) {
      msg.textContent = erro.message;
      msg.className = "erro";
      msg.classList.remove("oculto");
    }
    return;
  }
  if (!estado?.id_documento) {
    const texto =
      "O documento foi cadastrado, mas o SEI não retornou seu ID; não é possível consultar ou alterar as seções.";
    if (!silencioso) mensagemConteudoDocumentoInternoSei(texto);
    const msg = campo("preencher-secao-mensagem");
    if (silencioso && msg) {
      msg.textContent = texto;
      msg.className = "erro";
      msg.classList.remove("oculto");
    }
    return;
  }
  const botao = campo("documento-interno-sei-carregar-secoes");
  botao.disabled = true;
  campo("documento-interno-sei-formulario-abrir").disabled = true;
  campo("documento-interno-sei-alterar").disabled = true;
  if (!silencioso) {
    mensagemConteudoDocumentoInternoSei("Consultando as seções do documento no SEI…", "aviso");
  }
  try {
    const resposta = await fetch(
      `/api/processos/${processoEmEdicao.id}/documentos/${encodeURIComponent(estado.id_documento)}/secoes`,
    );
    const corpo = await lerRespostaApi(resposta);
    if (!resposta.ok) {
      if (resposta.status === 401) window.location.replace("/");
      throw new Error(corpo.mensagem || "Não foi possível carregar as seções do documento SEI.");
    }

    secoesDocumentoInternoSei = (corpo.secoes || [])
      .filter((secao) => !secao.somente_leitura);
    const seletorSecao = campo("sei-doc-secao");
    const indiceAnterior = seletorSecao.value;
    seletorSecao.replaceChildren();
    secoesDocumentoInternoSei.forEach((secao) => {
      const opcao = document.createElement("option");
      opcao.value = String(secao.indice);
      opcao.textContent = secao.nome;
      seletorSecao.append(opcao);
    });
    if (!secoesDocumentoInternoSei.some((secao) => secao.indice === Number(indiceAnterior))) {
      seletorSecao.selectedIndex = 0;
    }
    if (!corpo.secoes?.length) {
      throw new Error("O SEI não retornou seções para este documento.");
    }
    if (!secoesDocumentoInternoSei.length) {
      throw new Error("O documento não possui seções editáveis no SEI.");
    }
    if (!silencioso) mostrarConteudoSecaoAtual();
    else if (seletorSecao.value) mostrarConteudoSecaoAtual();
    campo("documento-interno-sei-formulario-abrir").disabled =
      estado.status !== "em_andamento" || Boolean(estado.alteracao_incerta);
    if (!silencioso) mensagemConteudoDocumentoInternoSei("");
  } catch (erro) {
    if (!silencioso) mensagemConteudoDocumentoInternoSei(erro.message);
    const msg = campo("preencher-secao-mensagem");
    if (silencioso && msg) {
      msg.textContent = erro.message;
      msg.className = "erro";
      msg.classList.remove("oculto");
    }
  } finally {
    botao.disabled = false;
    const atual = estadoDocumentoInternoSei();
    campo("documento-interno-sei-formulario-abrir").disabled =
      !actualPodeAlterarDocumentoSei(atual);
  }
}

function mostrarConteudoSecaoAtual() {
  const indice = Number(campo("sei-doc-secao").value);
  const secao = secoesDocumentoInternoSei.find((item) => item.indice === indice);
  const visualizador = campo("sei-doc-secao-atual");
  visualizador.replaceChildren();
  if (!secao) {
    visualizador.textContent = "Selecione uma seção editável.";
    return;
  }
  visualizador.innerHTML = secao.conteudo_html || "(A seção não possui conteúdo.)";
  limparPreviaFormularioDocumentoSei();
}

function actualPodeAlterarDocumentoSei(estado) {
  return Boolean(
    estado?.id_documento &&
    estado.status === "em_andamento" &&
    !estado.alteracao_incerta &&
    secoesDocumentoInternoSei.some((secao) => !secao.somente_leitura),
  );
}

function limparPreviaFormularioDocumentoSei() {
  conteudoHtmlFormularioSei = "";
  campo("documento-interno-sei-previa").classList.add("oculto");
  campo("documento-interno-sei-previa-html").replaceChildren();
  campo("documento-interno-sei-alterar").disabled = true;
}

async function carregarListaFormulariosDocumentoSei() {
  const seletor = campo("sei-doc-formulario");
  const valorAnterior = seletor.value;
  seletor.replaceChildren();
  const opcaoVazia = document.createElement("option");
  opcaoVazia.value = "";
  opcaoVazia.textContent = "Carregando formulários…";
  seletor.append(opcaoVazia);
  try {
    const resposta = await fetch("/api/formularios-sei");
    const corpo = await lerRespostaApi(resposta);
    if (!resposta.ok) {
      if (resposta.status === 401) window.location.replace("/");
      throw new Error(corpo.mensagem || "Não foi possível carregar os formulários cadastrados.");
    }
    formulariosDocumentoSei = Array.isArray(corpo.formularios) ? corpo.formularios : [];
    seletor.replaceChildren();
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = formulariosDocumentoSei.length
      ? "Selecione um formulário"
      : "Nenhum formulário cadastrado no catálogo";
    seletor.append(placeholder);
    formulariosDocumentoSei.forEach((formulario) => {
      const opcao = document.createElement("option");
      opcao.value = formulario.id;
      opcao.textContent = formulario.nome || formulario.id;
      seletor.append(opcao);
    });
    if (valorAnterior && formulariosDocumentoSei.some((item) => item.id === valorAnterior)) {
      seletor.value = valorAnterior;
    }
    if (!formulariosDocumentoSei.length) {
      mensagemConteudoDocumentoInternoSei(
        "Cadastre ao menos um documento no catálogo (aba Configurações) para usar como formulário.",
        "aviso",
      );
    }
  } catch (erro) {
    formulariosDocumentoSei = [];
    seletor.replaceChildren();
    const falha = document.createElement("option");
    falha.value = "";
    falha.textContent = "Falha ao carregar formulários";
    seletor.append(falha);
    mensagemConteudoDocumentoInternoSei(erro.message);
  }
}

async function navegarParaFormularioDocumentoSei() {
  if (!actualPodeAlterarDocumentoSei(estadoDocumentoInternoSei())) {
    mensagemConteudoDocumentoInternoSei(
      "Não há seção editável disponível para este documento. Atualize a lista ou tente novamente.",
    );
    return;
  }
  // Garante uma seção selecionada sem exibir a tela intermediária ao usuário.
  const seletor = campo("sei-doc-secao");
  if (seletor && seletor.options.length && seletor.selectedIndex < 0) {
    seletor.selectedIndex = 0;
  }
  if (seletor?.value) mostrarConteudoSecaoAtual();
  const painel = campo("painel-preencher-secao");
  if (painel) painel.classList.remove("oculto");
  definirVisibilidadeAssistenteIaFlutuante(true);
  const painelForm = campo("documento-interno-sei-formulario-painel");
  if (painelForm) painelForm.classList.remove("oculto");
  campo("documento-interno-sei-formulario-campos").replaceChildren();
  campo("documento-interno-sei-visualizar").classList.add("oculto");
  limparPreviaFormularioDocumentoSei();
  formularioDocumentoSeiSelecionado = null;
  conteudoHtmlFormularioSei = "";
  const msg = campo("preencher-secao-mensagem");
  if (msg) {
    msg.textContent = "Carregando formulários do catálogo…";
    msg.className = "aviso";
    msg.classList.remove("oculto");
  }
  await carregarListaFormulariosDocumentoSei();
  if (msg) {
    if (formulariosDocumentoSei.length) {
      msg.textContent = "Selecione o formulário, preencha os campos, gere a prévia e inclua o conteúdo no documento.";
      msg.className = "aviso";
      msg.classList.remove("oculto");
    } else {
      msg.textContent = "";
      msg.classList.add("oculto");
    }
  }
  campo("sei-doc-formulario")?.focus();
}

function fecharPainelPreencherSecao() {
  campo("painel-preencher-secao")?.classList.add("oculto");
  definirVisibilidadeAssistenteIaFlutuante(false);
}

async function voltarDoFormularioParaListaDocumentos() {
  fecharPainelPreencherSecao();
  await mostrarListaDocumentosInternosSei();
}

function lerContextoFormularioIaLocal() {
  try {
    const bruto = sessionStorage.getItem("gcpd-contexto-formulario-ia");
    return bruto ? JSON.parse(bruto) : {};
  } catch (_) {
    return {};
  }
}

function aplicarValoresFormularioDocumentoSei(valores) {
  if (!valores || typeof valores !== "object") return 0;
  const host = campo("documento-interno-sei-formulario-campos");
  let aplicados = 0;
  Object.entries(valores).forEach(([tagId, valor]) => {
    if (valor == null || typeof valor === "object") return;
    const el = host.querySelector(`[data-form-sei-tag="${CSS.escape(tagId)}"]`);
    if (!el) return;
    el.value = String(valor);
    aplicados += 1;
  });
  return aplicados;
}

function montarContextoPreenchimentoFormularioSei() {
  const salvo = lerContextoFormularioIaLocal();
  const interessados =
    dados.processo_contratacao?.interessados ||
    dados.processo_sei?.interessados ||
    [];
  const assuntos =
    dados.processo_contratacao?.assuntos ||
    dados.processo_sei?.assuntos ||
    [];
  return {
    pedido: salvo.pedido || dados.fatos || dados.extras?.pedido || "",
    numero_sei:
      processoEmEdicao?.numero_sei ||
      salvo.numero_sei ||
      dados.extras?.n_processo_sei ||
      dados.extras?.numero_sei ||
      "",
    interessado:
      salvo.interessado ||
      (Array.isArray(interessados) ? interessados[0] : "") ||
      "",
    assunto:
      salvo.assunto ||
      (Array.isArray(assuntos) ? assuntos[0] : "") ||
      dados.assunto ||
      "",
    tipo_processo:
      salvo.tipo_processo ||
      dados.processo_contratacao?.tipo_processo_sei ||
      dados.processo_sei?.tipo_processo_sei ||
      "",
  };
}

async function sugerirPreenchimentoFormularioDocumentoSei() {
  if (!formularioDocumentoSeiSelecionado) return;
  if (!csrfSei) {
    const autenticado = await carregarSessaoSei();
    if (!autenticado) return;
  }
  const msg = campo("preencher-secao-mensagem");
  if (msg) {
    msg.textContent = "A IA está analisando este formulário e sugerindo o preenchimento…";
    msg.className = "aviso";
    msg.classList.remove("oculto");
  }
  try {
    const resposta = await fetch("/api/ia/preencher-formulario", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfSei,
      },
      body: JSON.stringify({
        formulario: {
          id: formularioDocumentoSeiSelecionado.id,
          nome: formularioDocumentoSeiSelecionado.nome,
          tags: (formularioDocumentoSeiSelecionado.tags || []).map((tag) => ({
            id: tag.id,
            rotulo: tag.rotulo,
            tipo: tag.tipo,
            grupo: tag.grupo,
            calculado: Boolean(tag.calculado),
          })),
        },
        contexto: montarContextoPreenchimentoFormularioSei(),
      }),
    });
    const corpo = await lerRespostaApi(resposta);
    if (!resposta.ok || !corpo.ok) {
      throw new Error(corpo.mensagem || "Não foi possível sugerir o preenchimento.");
    }
    const aplicados = aplicarValoresFormularioDocumentoSei(corpo.valores || {});
    limparPreviaFormularioDocumentoSei();
    if (msg) {
      if (corpo.aviso) {
        msg.textContent = aplicados
          ? `${aplicados} campo(s) preenchidos. ${corpo.aviso}`
          : corpo.aviso;
        msg.className = "aviso";
      } else {
        msg.textContent = aplicados
          ? `${aplicados} campo(s) sugerido(s). Revise antes de incluir no SEI${corpo.fonte ? ` · ${corpo.fonte}` : ""}.`
          : "Nenhum campo pôde ser sugerido automaticamente. Preencha manualmente.";
        msg.className = aplicados ? "aviso" : "erro";
      }
      msg.classList.remove("oculto");
    }
  } catch (erro) {
    if (msg) {
      msg.textContent = erro.message || "Falha ao sugerir preenchimento com IA.";
      msg.className = "erro";
      msg.classList.remove("oculto");
    }
  }
}

async function selecionarFormularioDocumentoSei() {
  const id = campo("sei-doc-formulario").value;
  formularioDocumentoSeiSelecionado =
    formulariosDocumentoSei.find((formulario) => formulario.id === id) || null;
  valoresFormularioDocumentoSei = {};
  limparPreviaFormularioDocumentoSei();
  if (!formularioDocumentoSeiSelecionado) {
    campo("documento-interno-sei-formulario-campos").replaceChildren();
    campo("documento-interno-sei-visualizar").classList.add("oculto");
    mensagemConteudoDocumentoInternoSei("Selecione um formulário cadastrado.");
    return;
  }
  const tags = (formularioDocumentoSeiSelecionado.tags || [])
    .filter((tag) => tag?.id && !tag.calculado);
  const grupos = new Map();
  tags.forEach((tag) => {
    const grupo = String(tag.grupo || "Geral").trim() || "Geral";
    if (!grupos.has(grupo)) grupos.set(grupo, []);
    grupos.get(grupo).push(tag);
  });
  const camposFormulario = campo("documento-interno-sei-formulario-campos");
  camposFormulario.innerHTML = grupos.size
    ? [...grupos.entries()].map(([grupo, campos]) => `
      <section class="bloco-formulario-sei">
        <h3>${escHtml(grupo)}</h3>
        <div class="grade">${campos.map(htmlCampoFormularioDocumentoSei).join("")}</div>
      </section>
    `).join("")
    : `<p class="ajuda">Este formulário não possui campos para preencher. Clique em Visualizar para revisar o documento.</p>`;
  campo("documento-interno-sei-visualizar").classList.remove("oculto");
  mensagemConteudoDocumentoInternoSei("");
  // Após a escolha do formulário: a IA analisa as tags daquele formulário e sugere valores.
  await sugerirPreenchimentoFormularioDocumentoSei();
}

function htmlCampoFormularioDocumentoSei(tag) {
  const tipo = tag.tipo || "texto";
  const id = escHtml(tag.id);
  const rotulo = escHtml(tag.rotulo || tag.id);
  const largura = tipo === "tabela" ? 4 : larguraBaseTag(tag);
  if (tipo === "tabela") {
    const colunas = colunasDaTagTabela(tag);
    if (!colunas.length) {
      return `<div class="campo span-4"><label>${rotulo}</label><p class="ajuda">Esta tabela não tem colunas configuradas.</p></div>`;
    }
    valoresFormularioDocumentoSei[tag.id] = {
      linhas: [Object.fromEntries(colunas.map((coluna) => [coluna.id, ""]))],
    };
    const cabecalho = colunas.map((coluna) =>
      `<div class="celula-cab">${escHtml(coluna.rotulo || coluna.id)}</div>`,
    ).join("");
    const campos = colunas.map((coluna) => {
      const tipoColuna = coluna.tipo === "numero" ? "number" : "text";
      return `<input type="${tipoColuna}" data-form-sei-tabela="${id}" data-form-sei-linha="0" data-form-sei-coluna="${escHtml(coluna.id)}"${tipoColuna === "number" ? ' step="any"' : ""} placeholder="${escHtml(coluna.rotulo || coluna.id)}" />`;
    }).join("");
    return `
      <div class="campo span-4 campo-tabela">
        <label>${rotulo}</label>
        <div class="editor-tabela" data-form-sei-editor-tabela="${id}">
          <div class="cab-tabela-extra" style="--cols:${colunas.length}">${cabecalho}<div class="celula-cab acao-cab"></div></div>
          <div class="corpo-tabela-extra" style="--cols:${colunas.length}">
            <div class="linha-tabela-extra" data-form-sei-linha-wrap="0">${campos}<button type="button" class="acao" data-form-sei-remover-linha="${id}" data-linha="0" title="Remover linha">×</button></div>
          </div>
          <button type="button" class="acao" data-form-sei-adicionar-linha="${id}">+ Linha</button>
        </div>
      </div>`;
  }
  const controle = tipo === "numero"
    ? `<input type="number" step="any" data-form-sei-tag="${id}" />`
    : tipo === "texto_curto"
      ? `<input type="text" data-form-sei-tag="${id}" />`
      : `<textarea rows="3" data-form-sei-tag="${id}" placeholder="Valor para {{${id}}}"></textarea>`;
  return `<div class="campo span-${largura}"><label>${rotulo}</label>${controle}</div>`;
}

function lerValoresFormularioDocumentoSei() {
  const valores = {};
  campo("documento-interno-sei-formulario-campos")
    .querySelectorAll("[data-form-sei-tag]")
    .forEach((el) => { valores[el.dataset.formSeiTag] = el.value; });
  const tabelas = new Map();
  campo("documento-interno-sei-formulario-campos")
    .querySelectorAll("[data-form-sei-tabela][data-form-sei-linha][data-form-sei-coluna]")
    .forEach((el) => {
      const tagId = el.dataset.formSeiTabela;
      const indice = Number(el.dataset.formSeiLinha);
      if (!tabelas.has(tagId)) tabelas.set(tagId, new Map());
      const linhas = tabelas.get(tagId);
      if (!linhas.has(indice)) linhas.set(indice, {});
      linhas.get(indice)[el.dataset.formSeiColuna] = el.value;
    });
  tabelas.forEach((linhas, tagId) => {
    valores[tagId] = {
      linhas: [...linhas.entries()]
        .sort(([a], [b]) => a - b)
        .map(([, linha]) => linha),
    };
  });
  valoresFormularioDocumentoSei = valores;
  return valores;
}

function renderizarTabelaFormularioDocumentoSei(tag, valor) {
  const colunas = colunasDaTagTabela(tag);
  const linhas = valor?.linhas?.length ? valor.linhas : [{}];
  const id = escHtml(tag.id);
  const conteudo = linhas.map((linha, indice) => `
    <div class="linha-tabela-extra" data-form-sei-linha-wrap="${indice}">
      ${colunas.map((coluna) => {
        const tipo = coluna.tipo === "numero" ? "number" : "text";
        return `<input type="${tipo}" data-form-sei-tabela="${id}" data-form-sei-linha="${indice}" data-form-sei-coluna="${escHtml(coluna.id)}"${tipo === "number" ? ' step="any"' : ""} value="${escHtml(linha[coluna.id] || "")}" placeholder="${escHtml(coluna.rotulo || coluna.id)}" />`;
      }).join("")}
      <button type="button" class="acao" data-form-sei-remover-linha="${id}" data-linha="${indice}" title="Remover linha">×</button>
    </div>
  `).join("");
  const host = campo("documento-interno-sei-formulario-campos")
    .querySelector(`[data-form-sei-editor-tabela="${id}"] .corpo-tabela-extra`);
  host.innerHTML = conteudo;
}

function manipularTabelaFormularioDocumentoSei(evento) {
  const adicionar = evento.target.closest("[data-form-sei-adicionar-linha]");
  const remover = evento.target.closest("[data-form-sei-remover-linha]");
  if (!adicionar && !remover) return;
  const tagId = (adicionar || remover).dataset.formSeiAdicionarLinha
    || (adicionar || remover).dataset.formSeiRemoverLinha;
  const tag = formularioDocumentoSeiSelecionado?.tags
    ?.find((item) => item.id === tagId);
  if (!tag) return;
  const valores = lerValoresFormularioDocumentoSei();
  const atual = valores[tagId]?.linhas || [];
  if (adicionar) {
    atual.push(Object.fromEntries(colunasDaTagTabela(tag).map((coluna) => [coluna.id, ""])));
  } else {
    atual.splice(Number(remover.dataset.linha), 1);
    if (!atual.length) {
      atual.push(Object.fromEntries(colunasDaTagTabela(tag).map((coluna) => [coluna.id, ""])));
    }
  }
  valoresFormularioDocumentoSei[tagId] = { linhas: atual };
  renderizarTabelaFormularioDocumentoSei(tag, valoresFormularioDocumentoSei[tagId]);
  limparPreviaFormularioDocumentoSei();
}

async function visualizarFormularioDocumentoSei() {
  if (!formularioDocumentoSeiSelecionado) {
    mensagemConteudoDocumentoInternoSei("Selecione um formulário cadastrado.");
    return;
  }
  const valores = lerValoresFormularioDocumentoSei();
  const botao = campo("documento-interno-sei-visualizar");
  botao.disabled = true;
  limparPreviaFormularioDocumentoSei();
  mensagemConteudoDocumentoInternoSei("Gerando a pré-visualização HTML…", "aviso");
  try {
    const resposta = await fetch(
      `/api/processos/${processoEmEdicao.id}/formularios/visualizar`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": csrfSei,
        },
        body: JSON.stringify({
          formulario_id: formularioDocumentoSeiSelecionado.id,
          valores,
        }),
      },
    );
    const corpo = await lerRespostaApi(resposta);
    if (!resposta.ok) {
      if (resposta.status === 401) window.location.replace("/");
      throw new Error(corpo.mensagem || "Não foi possível gerar a pré-visualização HTML.");
    }
    conteudoHtmlFormularioSei = corpo.conteudo_html || "";
    if (!conteudoHtmlFormularioSei) throw new Error("O formulário não gerou conteúdo HTML.");
    campo("documento-interno-sei-previa-html").innerHTML = conteudoHtmlFormularioSei;
    campo("documento-interno-sei-previa").classList.remove("oculto");
    campo("documento-interno-sei-alterar").disabled =
      !actualPodeAlterarDocumentoSei(estadoDocumentoInternoSei());
    mensagemConteudoDocumentoInternoSei("");
  } catch (erro) {
    mensagemConteudoDocumentoInternoSei(erro.message);
  } finally {
    botao.disabled = false;
  }
}

function liberarNovaAlteracaoDocumentoSei() {
  if (!window.confirm(
    "Confirma que verificou a seção no SEI e que a alteração não foi aplicada? Uma nova tentativa pode substituir o conteúdo caso a verificação esteja incorreta.",
  )) return;
  const estado = estadoDocumentoInternoSei();
  if (!estado) return;
  estado.alteracao_incerta = false;
  salvarEstadoDocumentoInternoSei(estado);
  campo("documento-interno-sei-alterar").disabled =
    !conteudoHtmlFormularioSei || !actualPodeAlterarDocumentoSei(estado);
  campo("documento-interno-sei-formulario-abrir").disabled =
    !actualPodeAlterarDocumentoSei(estado);
  campo("documento-interno-sei-revisar-alteracao").classList.add("oculto");
  mensagemConteudoDocumentoInternoSei("");
}

async function alterarConteudoDocumentoSei() {
  const estado = estadoDocumentoInternoSei();
  if (!estado?.id_documento || estado.status === "concluido") return;
  if (estado.alteracao_incerta) {
    mensagemConteudoDocumentoInternoSei(
      "A resposta anterior não foi confirmada. Verifique a seção no SEI antes de liberar outra tentativa.",
      "aviso",
    );
    campo("documento-interno-sei-revisar-alteracao").classList.remove("oculto");
    campo("documento-interno-sei-alterar").disabled = true;
    return;
  }
  const indice = Number(campo("sei-doc-secao").value);
  const secao = secoesDocumentoInternoSei.find((item) => item.indice === indice);
  if (!secao || secao.somente_leitura) {
    mensagemConteudoDocumentoInternoSei("Selecione uma seção editável antes de enviar.");
    return;
  }

  // Preferência: HTML formatado da prévia do formulário.
  // Fallback: texto da caixa → <p>texto</p> (teste da API).
  if (!conteudoHtmlFormularioSei) {
    const caixa = campo("sei-doc-texto-simples");
    const textoBruto = (caixa?.value || "").trim();
    if (!textoBruto) {
      mensagemConteudoDocumentoInternoSei(
        "Gere a prévia do formulário (ou digite um texto simples) antes de enviar.",
      );
      return;
    }
    const normalizarTipografia = (t) =>
      t
        .replace(/[\u2013\u2014\u2015\u2212]/g, "-")
        .replace(/[\u2018\u2019\u201a\u201b]/g, "'")
        .replace(/[\u201c\u201d\u201e\u201f]/g, '"')
        .replace(/\u2026/g, "...")
        .replace(/[\u00a0\u202f\u2007\u2009]/g, " ")
        .replace(/[\u200b\ufeff\u00ad]/g, "");
    const linhas = textoBruto
      .split(/\r?\n/)
      .map((l) => normalizarTipografia(l).trim())
      .filter(Boolean);
    conteudoHtmlFormularioSei = (linhas.length ? linhas : [normalizarTipografia(textoBruto)])
      .map((linha) => {
        const esc = linha
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;")
          .replace(/"/g, "&quot;");
        return `<p>${esc}</p>`;
      })
      .join("");
  }

  const origem = formularioDocumentoSeiSelecionado
    ? `formulário “${formularioDocumentoSeiSelecionado.nome}”`
    : "texto simples";
  if (!window.confirm(
    `O conteúdo atual da seção “${secao.nome}” será substituído pelo HTML do ${origem}. Deseja continuar?`,
  )) return;

  const botao = campo("documento-interno-sei-alterar");
  botao.disabled = true;
  mensagemConteudoDocumentoInternoSei("Enviando o conteúdo HTML ao SEI…", "aviso");
    try {
    const resposta = await fetch(
      `/api/processos/${processoEmEdicao.id}/documentos/${encodeURIComponent(estado.id_documento)}/secoes/alterar`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": csrfSei,
        },
        body: JSON.stringify({
          conteudo_html: conteudoHtmlFormularioSei,
          indice_secao: secao.indice,
          id_secao_modelo: secao.id_secao_modelo,
        }),
      },
    );
    const corpo = await lerRespostaApi(resposta);
    if (!resposta.ok) {
      if (resposta.status === 401) window.location.replace("/");
      if (corpo.resultado_incerto) {
        estado.alteracao_incerta = true;
        salvarEstadoDocumentoInternoSei(estado);
        campo("documento-interno-sei-revisar-alteracao").classList.remove("oculto");
      }
      throw new Error(corpo.mensagem || "Não foi possível alterar a seção do documento no SEI.");
    }
    estado.status = "concluido";
    estado.alteracao_incerta = false;
    estado.secao = secao.nome;
    estado.formulario_id = formularioDocumentoSeiSelecionado?.id || "texto-simples";
    estado.formulario_nome = formularioDocumentoSeiSelecionado?.nome || "Texto simples";
    salvarEstadoDocumentoInternoSei(estado);
    campo("documento-interno-sei-etapa-status").textContent = corpo.mensagem;
    campo("documento-interno-sei-alteracao-retorno").textContent =
      `A seção “${secao.nome}” foi atualizada.`;
    campo("documento-interno-sei-alteracao-retorno").classList.remove("oculto");
    const msgPreencher = campo("preencher-secao-mensagem");
    if (msgPreencher) {
      msgPreencher.textContent = `A seção “${secao.nome}” foi atualizada no SEI.`;
      msgPreencher.className = "ok";
      msgPreencher.classList.remove("oculto");
    }
    await carregarListaDocumentosInternosSei();
    mensagemConteudoDocumentoInternoSei("");
  } catch (erro) {
    mensagemConteudoDocumentoInternoSei(erro.message);
  } finally {
    const atual = estadoDocumentoInternoSei();
    botao.disabled = Boolean(atual?.alteracao_incerta) || atual?.status === "concluido";
  }
}

const CAMPOS_DOC_SEI = {
  idSerie: { id: "sei-doc-id-serie", rotulo: "Tipo documental" },
  descricao: { id: "sei-doc-descricao", rotulo: "Descrição" },
  nomeArvore: { id: "sei-doc-nome-arvore", rotulo: "Nome na Árvore" },
  nivelAcesso: { id: "sei-doc-nivel-acesso", rotulo: "Nível de acesso" },
  idUnidadeGeradoraProtocolo: { id: "sei-doc-unidade-geradora", rotulo: "Unidade geradora de protocolo" },
  assuntos: { id: "sei-doc-assuntos", rotulo: "Assuntos" },
  observacao: { id: "sei-doc-observacao", rotulo: "Observações desta unidade" },
  flagProtocolo: { id: "sei-doc-flag-protocolo", rotulo: "Flag de protocolo" },
  interessados: { id: "sei-doc-interessados", rotulo: "Interessados" },
  destinatarios: { id: "sei-doc-destinatarios", rotulo: "Destinatários" },
  unidadesReabertura: { id: "sei-doc-unidades-reabertura", rotulo: "Unidades para reabertura" },
  idHipoteseLegal: { id: "sei-doc-hipotese-legal", rotulo: "Hipótese legal" },
  grauSigilo: { id: "sei-doc-grau-sigilo", rotulo: "Grau de sigilo" },
  idTextoPadraoInterno: { id: "sei-doc-texto-padrao", rotulo: "Texto padrão interno" },
};

const CAMPOS_DOC_SEI_BASE = new Set([
  "idSerie",
  "descricao",
  "nomeArvore",
  "nivelAcesso",
  "assuntos",
  "observacao",
  "textoInicial",
]);

let assuntosDocumentoSeiSelecionados = [];
let tiposDocumentoSei = [];

function blocoCampoDocumentoSei(nomeApi) {
  return campo("documento-interno-sei-metadados")
    ?.querySelector(`[data-sei-campo="${nomeApi}"]`);
}

function campoDocumentoSeiVisivel(nomeApi) {
  if (nomeApi === "idUnidadeGeradoraProtocolo" || nomeApi === "flagProtocolo") return true;
  const bloco = blocoCampoDocumentoSei(nomeApi);
  if (!bloco) {
    return Boolean(campo(CAMPOS_DOC_SEI[nomeApi]?.id));
  }
  return !bloco.classList.contains("oculto");
}

function revelarCampoDocumentoSei(nomeApi, { obrigatorio = false, focar = true } = {}) {
  const meta = CAMPOS_DOC_SEI[nomeApi];
  const bloco = blocoCampoDocumentoSei(nomeApi);
  if (!meta || !bloco) return false;
  bloco.classList.remove("oculto");
  if (obrigatorio) bloco.dataset.seiObrigatorio = "1";
  const input = campo(meta.id) || bloco.querySelector("input, select, textarea");
  if (input && focar) {
    input.focus();
    input.scrollIntoView({ behavior: "smooth", block: "center" });
  }
  return true;
}

function resetarVisibilidadeCamposDocumentoSei() {
  campo("documento-interno-sei-metadados")
    ?.querySelectorAll("[data-sei-campo]")
    .forEach((bloco) => {
      const nome = bloco.dataset.seiCampo;
      const base = CAMPOS_DOC_SEI_BASE.has(nome) || bloco.dataset.seiBase === "1";
      bloco.classList.toggle("oculto", !base);
      delete bloco.dataset.seiObrigatorio;
      bloco.classList.remove("campo-sei-faltante");
    });
}

function tipoDocumentoSeiSelecionado() {
  const id = campo("sei-doc-id-serie")?.value || "";
  return tiposDocumentoSei.find((tipo) => String(tipo.id) === String(id)) || null;
}

function aplicarSugestoesCamposPorTipoDocumento() {
  const tipo = tipoDocumentoSeiSelecionado();
  const blocoAssunto = blocoCampoDocumentoSei("assuntos");
  if (blocoAssunto) {
    if (tipo?.precisa_assunto) blocoAssunto.dataset.seiObrigatorio = "1";
    else delete blocoAssunto.dataset.seiObrigatorio;
  }
}

function sincronizarAssuntosDocumentoSeiHidden() {
  const hidden = campo("sei-doc-assuntos");
  if (hidden) {
    hidden.value = assuntosDocumentoSeiSelecionados.map((item) => item.id).join(",");
  }
}

function desenharAssuntosDocumentoSeiSelecionados() {
  const host = campo("sei-doc-assuntos-selecionados");
  if (!host) return;
  host.replaceChildren();
  assuntosDocumentoSeiSelecionados.forEach((item, indice) => {
    const linha = document.createElement("div");
    linha.className = "item-decreto";
    const texto = document.createElement("span");
    texto.textContent = item.nome || item.id;
    const remover = document.createElement("button");
    remover.type = "button";
    remover.className = "remover";
    remover.textContent = "Remover";
    remover.dataset.indiceAssuntoDoc = String(indice);
    linha.append(texto, remover);
    host.append(linha);
  });
  sincronizarAssuntosDocumentoSeiHidden();
}

function desenharListaAssuntosDocumentoSei() {
  const lista = campo("sei-doc-assuntos-lista");
  const filtroEl = campo("sei-doc-assunto-filtro");
  if (!lista || !filtroEl) return;
  const filtro = filtroEl.value.trim().toLocaleLowerCase();
  const selecionados = new Set(assuntosDocumentoSeiSelecionados.map((item) => String(item.id)));
  const visiveis = (assuntosSei || []).filter((item) => {
    const nome = String(item.nome || "").toLocaleLowerCase();
    const id = String(item.id_sei || "").toLocaleLowerCase();
    return !filtro || nome.includes(filtro) || id.includes(filtro);
  });
  lista.style.display = "grid";
  if (!(assuntosSei || []).length) {
    lista.innerHTML = `<p class="lista-tipos-vazia">Nenhum assunto cadastrado.</p>`;
    return;
  }
  if (!visiveis.length) {
    lista.innerHTML = `<p class="lista-tipos-vazia">Nenhum assunto corresponde ao termo.</p>`;
    return;
  }
  lista.innerHTML = visiveis.map((item) => `
    <button type="button" class="tipo-processo-opcao"
      aria-pressed="${selecionados.has(String(item.id_sei))}"
      data-assunto-doc-id="${escHtml(item.id_sei)}"
      data-assunto-doc-nome="${escHtml(item.nome)}">${escHtml(item.nome)}</button>
  `).join("");
}

function selecionarAssuntoDocumentoSei(id, nome) {
  if (!id) return;
  const indice = assuntosDocumentoSeiSelecionados.findIndex((item) => String(item.id) === String(id));
  if (indice >= 0) {
    assuntosDocumentoSeiSelecionados.splice(indice, 1);
  } else {
    assuntosDocumentoSeiSelecionados.push({ id: String(id), nome: nome || String(id) });
  }
  campo("sei-doc-assunto-filtro").value = "";
  desenharAssuntosDocumentoSeiSelecionados();
  desenharListaAssuntosDocumentoSei();
}

function preencherAssuntosDocumentoSeiIniciais() {
  const processo = dados.processo_contratacao || vazio().processo_contratacao;
  const nomes = processo.assuntos || [];
  assuntosDocumentoSeiSelecionados = [];
  nomes.forEach((nome) => {
    const hit = (assuntosSei || []).find((item) => item.nome === nome)
      || (assuntosSei || []).find((item) => String(item.id_sei) === String(ASSUNTOS_SEI_IDS[nome] || ""));
    if (hit?.id_sei) {
      assuntosDocumentoSeiSelecionados.push({ id: String(hit.id_sei), nome: hit.nome });
    }
  });
  desenharAssuntosDocumentoSeiSelecionados();
  desenharListaAssuntosDocumentoSei();
}

function coletarCamposDocumentoSeiVisiveis() {
  const payload = {};
  Object.entries(CAMPOS_DOC_SEI).forEach(([nomeApi, meta]) => {
    if (!campoDocumentoSeiVisivel(nomeApi)) return;
    if (nomeApi === "nivelAcesso") {
      payload.nivelAcesso = document.querySelector('input[name="sei-doc-nivel-acesso"]:checked')?.value || "0";
      return;
    }
    if (nomeApi === "assuntos") {
      payload.assuntos = assuntosDocumentoSeiSelecionados.map((item) => item.id).join(",");
      return;
    }
    const el = campo(meta.id);
    if (!el) return;
    payload[nomeApi] = String(el.value || "").trim();
  });

  // Sempre envia unidade geradora (valor técnico padrão).
  payload.idUnidadeGeradoraProtocolo = campo("sei-doc-unidade-geradora")?.value.trim() || "110000001";
  const tipo = tipoDocumentoSeiSelecionado();
  if (tipo?.precisa_numero) payload.numero = "DDS001";
  else delete payload.numero;

  const textoInicial = document.querySelector('input[name="sei-doc-texto-inicial"]:checked')?.value || "nenhum";
  if (textoInicial !== "nenhum") {
    const idTexto = campo("sei-doc-texto-padrao")?.value.trim() || "";
    if (idTexto) payload.idTextoPadraoInterno = idTexto;
  }
  return payload;
}

function validarCamposDocumentoSeiVisiveis(payload) {
  if (!payload.idSerie) return "Selecione o tipo documental.";
  for (const [nomeApi, meta] of Object.entries(CAMPOS_DOC_SEI)) {
    const bloco = blocoCampoDocumentoSei(nomeApi);
    if (!bloco || bloco.classList.contains("oculto")) continue;
    if (bloco.dataset.seiObrigatorio === "1" && !payload[nomeApi]) {
      revelarCampoDocumentoSei(nomeApi, { obrigatorio: true });
      return `Preencha o campo obrigatório: ${meta.rotulo}.`;
    }
  }
  return "";
}

function destacarCampoDocumentoSeiFaltante(nomeApi, mensagem) {
  if (!nomeApi || !revelarCampoDocumentoSei(nomeApi, { obrigatorio: true })) {
    return mensagem;
  }
  const bloco = blocoCampoDocumentoSei(nomeApi);
  bloco?.classList.add("campo-sei-faltante");
  const rotulo = CAMPOS_DOC_SEI[nomeApi]?.rotulo || nomeApi;
  return (
    `O SEI exigiu o campo “${rotulo}”. Preencha-o e clique novamente em Cadastrar documento no SEI.`
    + (mensagem ? ` Detalhe: ${mensagem}` : "")
  );
}

async function iniciarOutroDocumentoInternoSei() {
  if (localStorage.getItem(chaveResultadoIncertoDocumentoSei()) === "1") {
    mensagemDocumentoInternoSei(
      "A tentativa anterior teve resultado incerto. Verifique o SEI antes de liberar um novo cadastro.",
      "aviso",
    );
    return;
  }
  if (!await carregarTiposDocumentoSei()) return;
  mostrarFormularioNovoDocumentoInternoSei();
}

async function carregarTiposDocumentoSei() {
  const select = campo("sei-doc-id-serie");
  try {
    const resposta = await fetch("/api/tipos-documento-sei");
    const corpo = await lerRespostaApi(resposta);
    if (!resposta.ok) {
      if (resposta.status === 401) window.location.replace("/");
      throw new Error(corpo.mensagem || "Não foi possível carregar os tipos documentais.");
    }
    const tipos = corpo.tipos || [];
    tiposDocumentoSei = tipos;
    if (!tipos.length) throw new Error("Não há tipos documentais cadastrados.");
    select.replaceChildren(
      new Option("Selecione o tipo documental", ""),
      ...tipos.map((tipo) => new Option(`${tipo.id} - ${tipo.nome}`, tipo.id)),
    );
    return true;
  } catch (erro) {
    mensagemDocumentoInternoSei(erro.message);
    return false;
  }
}

function mostrarFormularioNovoDocumentoInternoSei() {
  documentoSeiAtivoId = "";
  campo("documento-interno-sei-lista").classList.add("oculto");
  campo("documento-interno-sei-ajuda-metadados").classList.remove("oculto");
  campo("documento-interno-sei-metadados").classList.remove("oculto");
  campo("documento-interno-sei-conteudo").classList.add("oculto");
  campo("documento-interno-sei-enviar").classList.remove("oculto");
  campo("documento-interno-sei-enviar").disabled = false;
  campo("documento-interno-sei-form").reset();
  campo("sei-doc-unidade-geradora").value = "110000001";
  campo("sei-doc-flag-protocolo").value = "";
  campo("documento-interno-sei-revisar").classList.add("oculto");
  mensagemDocumentoInternoSei("");
  mensagemConteudoDocumentoInternoSei("");
  resetarVisibilidadeCamposDocumentoSei();

  const processo = dados.processo_contratacao || vazio().processo_contratacao;
  const nivel = ({
    publico: "0",
    restrito: "1",
    sigiloso: "2",
  })[processo.nivel_acesso] || "0";
  document.querySelectorAll('input[name="sei-doc-nivel-acesso"]').forEach((radio) => {
    radio.checked = radio.value === nivel;
  });
  document.querySelectorAll('input[name="sei-doc-texto-inicial"]').forEach((radio) => {
    radio.checked = radio.value === "nenhum";
  });
  campo("sei-doc-observacao").value = processo.observacoes || "";
  campo("sei-doc-descricao").value = "";
  campo("sei-doc-nome-arvore").value = "";

  const carregar = assuntosSei?.length
    ? Promise.resolve()
    : carregarAssuntosSei().catch(() => {});
  carregar.finally(() => {
    preencherAssuntosDocumentoSeiIniciais();
    aplicarSugestoesCamposPorTipoDocumento();
    campo("sei-doc-id-serie")?.focus();
  });
}

function liberarNovaTentativaDocumentoSei() {
  if (!window.confirm(
    "Confirma que verificou o processo no SEI e que o documento não foi cadastrado? Uma nova tentativa pode criar uma duplicata se a verificação estiver incorreta.",
  )) return;
  localStorage.removeItem(chaveResultadoIncertoDocumentoSei());
  campo("documento-interno-sei-enviar").disabled = false;
  campo("documento-interno-sei-criar-novo").disabled = false;
  campo("documento-interno-sei-revisar").classList.add("oculto");
  campo("documento-interno-sei-revisar-lista").classList.add("oculto");
  campo("documento-interno-sei-lista-mensagem").classList.add("oculto");
  mensagemDocumentoInternoSei("");
}

async function cadastrarDocumentoInternoNoSei(evento) {
  evento.preventDefault();
  if (!processoEmEdicao?.id || !processoEmEdicao?.id_procedimento_sei) {
    mensagemDocumentoInternoSei("Crie o processo no SEI antes de anexar um documento.");
    return;
  }
  if (localStorage.getItem(chaveResultadoIncertoDocumentoSei()) === "1") {
    mensagemDocumentoInternoSei(
      "A tentativa anterior teve resultado incerto. Consulte o SEI antes de liberar outra tentativa.",
      "aviso",
    );
    campo("documento-interno-sei-enviar").disabled = true;
    campo("documento-interno-sei-revisar").classList.remove("oculto");
    return;
  }
  if (!csrfSei) {
    const autenticado = await carregarSessaoSei();
    if (!autenticado) return;
  }

  const campos = coletarCamposDocumentoSeiVisiveis();
  const erroLocal = validarCamposDocumentoSeiVisiveis(campos);
  if (erroLocal) {
    mensagemDocumentoInternoSei(erroLocal, "erro");
    return;
  }

  const botao = campo("documento-interno-sei-enviar");
  let cadastroConcluido = false;
  botao.disabled = true;
  mensagemDocumentoInternoSei("Enviando solicitação ao SEI de homologação…", "aviso");
  try {
    const resposta = await fetch(
      `/api/processos/${processoEmEdicao.id}/documentos/criar-no-sei`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": csrfSei,
        },
        body: JSON.stringify(campos),
      },
    );
    const corpo = await lerRespostaApi(resposta);
    if (!resposta.ok) {
      if (resposta.status === 401) window.location.replace("/");
      if (corpo.cadastro_confirmado) {
        const documento = corpo.documento || {};
        documentoSeiAtivoId = String(documento.id_documento || "");
        const estado = {
          id_documento: documentoSeiAtivoId,
          protocolo: String(documento.protocolo || ""),
          descricao: campos.descricao,
          status: "vinculo_pendente",
          alteracao_incerta: false,
        };
        if (documentoSeiAtivoId) salvarEstadoDocumentoInternoSei(estado);
        cadastroConcluido = true;
        await prepararEtapaConteudoDocumentoSei(estado);
        mensagemConteudoDocumentoInternoSei(corpo.mensagem, "erro");
        return;
      }
      if (corpo.resultado_incerto) {
        localStorage.setItem(chaveResultadoIncertoDocumentoSei(), "1");
        campo("documento-interno-sei-revisar").classList.remove("oculto");
        throw new Error(corpo.mensagem || "Não foi possível cadastrar o documento no SEI.");
      }
      const mensagem = destacarCampoDocumentoSeiFaltante(
        corpo.campo_faltante,
        corpo.mensagem || "Não foi possível cadastrar o documento no SEI.",
      );
      throw new Error(mensagem);
    }
    localStorage.removeItem(chaveResultadoIncertoDocumentoSei());
    const documento = corpo.documento || {};
    documentoSeiAtivoId = String(documento.id_documento || "");
    const estado = {
      id_documento: documentoSeiAtivoId,
      protocolo: String(documento.protocolo || ""),
      descricao: campos.descricao,
      status: documento.id_documento ? "em_andamento" : "id_ausente",
      alteracao_incerta: false,
    };
    salvarEstadoDocumentoInternoSei(estado);
    cadastroConcluido = true;
    mensagemDocumentoInternoSei("");
    await prepararEtapaConteudoDocumentoSei(estado, { irDiretoAoFormulario: true });
  } catch (erro) {
    mensagemDocumentoInternoSei(erro.message, "erro");
  } finally {
    const incerto = localStorage.getItem(chaveResultadoIncertoDocumentoSei()) === "1";
    botao.disabled = incerto || cadastroConcluido;
  }
}

async function confirmarBuscaSei() {
  const numero = document.getElementById("busca-numero-sei").value.trim();
  const erro = document.getElementById("busca-sei-erro");
  if (!numero) {
    erro.className = "erro";
    erro.textContent = "Informe o número SEI.";
    return;
  }
  const botao = document.getElementById("busca-sei-confirmar");
  botao.disabled = true;
  erro.classList.add("oculto");
  try {
    const resposta = await fetch(`/api/processos/por-sei?numero=${encodeURIComponent(numero)}`);
    const corpo = await resposta.json();
    if (!resposta.ok) throw new Error(corpo.mensagem || "Processo não encontrado.");
    const origem = corpo.processo;
    if (!origem?.cadastro) {
      throw new Error("O processo encontrado não tem cadastro gravado para carregar.");
    }
    const modo = buscaSeiModo || "Aditamento";
    fecharBuscaSei();
    definirEdicao(null);
    definirModoOperacao(modo);
    const cadastro = { ...origem.cadastro };
    if (!String(cadastro.assunto || "").trim() && origem.assunto) {
      cadastro.assunto = origem.assunto;
    }
    aplicarCadastro(cadastro);
    document.getElementById("resultado").classList.add("oculto");
    ativarAba("painel-formulario");
    mensagem(
      `${modo} a partir do SEI ${origem.numero_sei} (${origem.codigo}). Ao gerar, um novo registro será criado.`,
      "ok",
    );
    const alvo = modo === "Prorrogação"
      ? document.getElementById("campo-vigencia")
      : document.getElementById("cadastro");
    alvo.scrollIntoView({ behavior: "smooth", block: "center" });
    if (modo === "Prorrogação") document.getElementById("prazo_meses").focus();
  } catch (falha) {
    erro.className = "erro";
    erro.textContent = falha.message;
  } finally {
    botao.disabled = false;
  }
}

function novoCadastro() {
  abrirPainelNovo();
}

async function abrirProcesso(processoId) {
  try {
    const resposta = await fetch(`/api/processos/${processoId}`);
    const corpo = await resposta.json();
    if (!resposta.ok) throw new Error(corpo.mensagem || "Não foi possível abrir o processo.");
    ativarAba("painel-formulario");
    definirModoOperacao(corpo.processo.tipo || "Abertura");
    definirEdicao(corpo.processo);
    if (!corpo.processo?.cadastro) {
      mensagem("Este registro ainda não tem o cadastro gravado. Preencha e use Salvar.", "erro");
      document.getElementById("cadastro").scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    const cadastro = { ...(corpo.processo.cadastro || {}) };
    if (!String(cadastro.assunto || "").trim() && corpo.processo.assunto) {
      cadastro.assunto = corpo.processo.assunto;
    }
    aplicarCadastro(cadastro);
    await carregarDocumentosProcesso(corpo.processo);
    destacarVigencia(corpo.processo.tipo === "Prorrogação");
    if (
      String(cadastro.tipo_processo_sei || "").trim().toLocaleLowerCase()
      === TIPO_PROCESSO_CONTRATACAO.toLocaleLowerCase()
    ) {
      tipoProcessoSelecionado = cadastro.tipo_processo_sei;
      abrirFormularioContratacao();
    } else if (String(cadastro.tipo_processo_sei || "").trim().toLocaleLowerCase() === "decreto") {
      tipoProcessoSelecionado = cadastro.tipo_processo_sei;
      abrirFormularioDecreto();
    }
    mensagem(`Cadastro do processo ${corpo.processo.codigo || corpo.processo.numero_sei || corpo.processo.id} carregado para edição.`, "ok");
    document.getElementById("cadastro").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (erro) {
    mensagem(erro.message, "erro");
  }
}

async function salvarCadastro() {
  if (!processoEmEdicao?.id) {
    mensagem("Abra um processo pelo ícone de editar para salvar alterações neste registro. Em um cadastro novo, use Gerar documentos.", "erro");
    return;
  }
  salvar();
  const botao = document.getElementById("salvar-cadastro");
  botao.disabled = true;
  mensagem("");
  try {
    const resposta = await fetch(`/api/processos/${processoEmEdicao.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(dados),
    });
    const corpo = await resposta.json();
    if (!resposta.ok) throw new Error(corpo.mensagem || "Não foi possível salvar.");
    definirEdicao({ id: corpo.processo.id, codigo: corpo.processo.codigo });
    await carregarProcessos();
    mensagem(`Alterações do processo ${corpo.processo.codigo || corpo.processo.numero_sei || corpo.processo.id} salvas. Nenhum registro novo foi criado.`, "ok");
  } catch (erro) {
    mensagem(erro.message, "erro");
  } finally {
    botao.disabled = false;
  }
}

function iconeEditar() {
  return `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 20h9"/>
      <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/>
    </svg>`;
}

function iconeEnviarSei() {
  return `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M22 2 11 13"/>
      <path d="M22 2 15 22 11 13 2 9 22 2"/>
    </svg>`;
}

function iconeExcluir() {
  return `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M3 6h18"/>
      <path d="M8 6V4h8v2"/>
      <path d="M19 6l-1 14H6L5 6"/>
      <path d="M10 11v6"/>
      <path d="M14 11v6"/>
    </svg>`;
}

function mensagemPrincipal(texto, tipo) {
  const el = document.getElementById("mensagem-principal");
  if (!texto) {
    el.classList.add("oculto");
    el.textContent = "";
    return;
  }
  el.className = tipo === "ok" ? "ok" : (tipo === "aviso" ? "aviso" : "erro");
  el.textContent = texto;
  el.classList.remove("oculto");
}

function abrirPainelSei(item) {
  processoSei = { id: item.id, codigo: item.codigo || item.numero_sei || `ID ${item.id}` };
  document.getElementById("sei-processo").textContent = processoSei.codigo;
  document.getElementById("numero-sei").value = "";
  document.getElementById("sei-erro").classList.add("oculto");
  document.getElementById("sei-erro").textContent = "";
  document.getElementById("painel-sei").classList.remove("oculto");
  document.getElementById("numero-sei").focus();
}

function fecharPainelSei() {
  processoSei = null;
  document.getElementById("painel-sei").classList.add("oculto");
}

async function confirmarEnvioSei() {
  if (!processoSei?.id) return;
  const numero = document.getElementById("numero-sei").value.trim();
  const erro = document.getElementById("sei-erro");
  if (!numero) {
    erro.className = "erro";
    erro.textContent = "Informe o número SEI.";
    return;
  }
  const botao = document.getElementById("sei-confirmar");
  botao.disabled = true;
  erro.classList.add("oculto");
  try {
    const resposta = await fetch(`/api/processos/${processoSei.id}/sei`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ numero_sei: numero }),
    });
    const corpo = await resposta.json();
    if (!resposta.ok) throw new Error(corpo.mensagem || "Não foi possível registrar o envio.");
    fecharPainelSei();
    await carregarProcessos();
    mensagemPrincipal(
      `Número SEI ${corpo.processo.numero_sei} registrado para o processo ${corpo.processo.codigo || corpo.processo.id}.`,
      "ok",
    );
  } catch (falha) {
    erro.className = "erro";
    erro.textContent = falha.message;
  } finally {
    botao.disabled = false;
  }
}

function idsProcessosSelecionados() {
  return [...document.querySelectorAll("#lista-processos input[data-processo-check]:checked")]
    .map((input) => Number(input.dataset.processoCheck))
    .filter((id) => Number.isFinite(id) && id > 0);
}

function atualizarBotaoExcluirProcessos() {
  const botao = document.getElementById("excluir-processos-selecionados");
  const marcarTodos = document.getElementById("processos-marcar-todos");
  const checks = [...document.querySelectorAll("#lista-processos input[data-processo-check]")];
  const marcados = checks.filter((input) => input.checked);
  if (botao) {
    botao.disabled = marcados.length === 0;
    botao.textContent = marcados.length > 1
      ? `Excluir selecionados (${marcados.length})`
      : "Excluir selecionados";
  }
  if (marcarTodos) {
    marcarTodos.disabled = checks.length === 0;
    marcarTodos.checked = checks.length > 0 && marcados.length === checks.length;
    marcarTodos.indeterminate = marcados.length > 0 && marcados.length < checks.length;
  }
}

async function excluirProcessosPorIds(ids, codigos = []) {
  const lista = [...new Set((ids || []).map((id) => Number(id)).filter((id) => Number.isFinite(id) && id > 0))];
  if (!lista.length) {
    mensagemPrincipal("Selecione ao menos um processo para excluir.", "erro");
    return;
  }
  const rotulo = codigos.length === 1
    ? `o processo ${codigos[0]}`
    : lista.length === 1
      ? "este processo"
      : `os ${lista.length} processos selecionados`;
  if (!window.confirm(`Excluir ${rotulo}? Os documentos gerados também serão removidos.`)) return;

  const botaoLote = document.getElementById("excluir-processos-selecionados");
  if (botaoLote) botaoLote.disabled = true;
  try {
    const resposta = await fetch("/api/processos", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids: lista }),
    });
    const corpo = await resposta.json();
    if (!resposta.ok) throw new Error(corpo.mensagem || "Não foi possível excluir.");
    if (processoEmEdicao?.id && lista.includes(Number(processoEmEdicao.id))) {
      processoEmEdicao = null;
      const edicao = document.getElementById("edicao-atual");
      if (edicao) {
        edicao.classList.add("oculto");
        edicao.textContent = "";
      }
    }
    await carregarProcessos();
    mensagemPrincipal(corpo.mensagem || "Processo(s) excluído(s).", "ok");
  } catch (erro) {
    mensagemPrincipal(erro.message, "erro");
    atualizarBotaoExcluirProcessos();
  }
}

function desenharProcessos(lista) {
  const corpo = document.getElementById("lista-processos");
  if (!lista.length) {
    corpo.innerHTML = `<tr class="vazio"><td colspan="7">Nenhum processo criado no SEI ainda. Use Novo cadastro para iniciar.</td></tr>`;
    atualizarBotaoExcluirProcessos();
    return;
  }
  corpo.innerHTML = lista.map((item) => {
    const codigo = item.codigo || "—";
    const identificador = item.numero_sei || item.codigo || `ID ${item.id}`;
    const sei = item.numero_sei
      ? escHtml(item.numero_sei)
      : `<span class="sei-vazio">—</span>`;
    const situacao = item.id_procedimento_sei
      ? iconeCriadoSEI()
      : item.status === "enviado"
        ? iconeNumeroRegistrado()
        : ["criando_sei", "criacao_indeterminada"].includes(item.status)
          ? iconePendenteSEI()
          : iconeNaoEnviado();
    const pendente = ["criando_sei", "criacao_indeterminada"].includes(item.status);
    const podeEnviar = Boolean(item.codigo)
      && !pendente
      && (item.status !== "enviado" || !item.numero_sei);
    const botaoSei = podeEnviar
      ? `<button type="button" class="botao-sei" data-sei-id="${item.id}" data-sei-codigo="${escHtml(identificador)}" title="Registrar número SEI" aria-label="Registrar número SEI do processo ${escHtml(identificador)}">${iconeEnviarSei()}</button>`
      : "";
    return `
      <tr class="linha-processo" data-id="${item.id}">
        <td class="col-check">
          <input type="checkbox" data-processo-check="${item.id}" aria-label="Selecionar processo ${escHtml(identificador)}" />
        </td>
        <td><span class="codigo-processo">${escHtml(codigo)}</span></td>
        <td>${escHtml(item.tipo_processo_sei || item.tipo)}</td>
        <td>${sei}</td>
        <td>${escHtml(item.assunto)}</td>
        <td>${situacao}</td>
        <td class="acoes-processo">
          <div class="grupo-acoes">
            <button type="button" class="botao-editar" data-editar="${item.id}" title="Editar cadastro" aria-label="Editar processo ${escHtml(identificador)}">
              ${iconeEditar()}
            </button>
            ${botaoSei}
            <button type="button" class="botao-excluir-processo" data-excluir-id="${item.id}" data-excluir-codigo="${escHtml(identificador)}" title="Excluir processo" aria-label="Excluir processo ${escHtml(identificador)}">
              ${iconeExcluir()}
            </button>
          </div>
        </td>
      </tr>`;
  }).join("");
  corpo.querySelectorAll("[data-editar]").forEach((botao) => {
    botao.addEventListener("click", () => abrirProcesso(botao.dataset.editar));
  });
  corpo.querySelectorAll("[data-sei-id]").forEach((botao) => {
    botao.addEventListener("click", () => {
      abrirPainelSei({ id: Number(botao.dataset.seiId), codigo: botao.dataset.seiCodigo });
    });
  });
  corpo.querySelectorAll("[data-excluir-id]").forEach((botao) => {
    botao.addEventListener("click", () => {
      excluirProcessosPorIds([Number(botao.dataset.excluirId)], [botao.dataset.excluirCodigo]);
    });
  });
  corpo.querySelectorAll("[data-processo-check]").forEach((input) => {
    input.addEventListener("change", atualizarBotaoExcluirProcessos);
  });
  atualizarBotaoExcluirProcessos();
}

async function carregarProcessos() {
  try {
    const resposta = await fetch("/api/processos");
    const corpo = await resposta.json();
    if (!resposta.ok) {
      const mensagem = resposta.status === 401
        ? "Sessão do SEI expirada; conecte-se novamente para carregar os processos."
        : corpo.mensagem || "Não foi possível carregar os processos.";
      throw new Error(mensagem);
    }
    if (!Array.isArray(corpo.processos)) {
      throw new Error("A resposta do servidor não contém uma lista de processos válida.");
    }
    desenharProcessos(corpo.processos);
  } catch (erro) {
    const linha = document.createElement("tr");
    linha.className = "vazio";
    const celula = document.createElement("td");
    celula.colSpan = 7;
    celula.textContent = erro instanceof Error
      ? erro.message
      : "Não foi possível carregar os processos.";
    linha.append(celula);
    document.getElementById("lista-processos").replaceChildren(linha);
    atualizarBotaoExcluirProcessos();
  }
}

document.getElementById("abrir-ia-abrir")?.addEventListener("click", () => {
  window.location.href = "/processo-sei-ia";
});

async function retomarAberturaIaSeHouver() {
  const bruto = sessionStorage.getItem("gcpd-pos-abertura-ia");
  if (!bruto) return;
  sessionStorage.removeItem("gcpd-pos-abertura-ia");
  let dados;
  try {
    dados = JSON.parse(bruto);
  } catch (_) {
    return;
  }
  if (!dados?.processoId) return;
  try {
    const resposta = await fetch(`/api/processos/${dados.processoId}`);
    const corpo = await resposta.json();
    if (!resposta.ok) throw new Error(corpo.mensagem || "Não foi possível abrir o processo criado.");
    definirEdicao(corpo.processo);
    if (corpo.processo?.cadastro) aplicarCadastro(corpo.processo.cadastro);
    documentoSeiAtivoId = String(dados.documentoId || "");
    const estado = {
      id_documento: documentoSeiAtivoId,
      protocolo: String(dados.protocoloDocumento || ""),
      descricao: dados.descricao || "",
      status: documentoSeiAtivoId ? "em_andamento" : "id_ausente",
      alteracao_incerta: false,
    };
    if (documentoSeiAtivoId) salvarEstadoDocumentoInternoSei(estado);
    await abrirPainelDocumentoInternoSei();
    if (documentoSeiAtivoId) {
      await prepararEtapaConteudoDocumentoSei(estado, { irDiretoAoFormulario: true });
    }
    mensagemPrincipal(
      `Abertura com IA concluída · SEI ${dados.protocolo || corpo.processo.numero_sei || ""}.`,
      "ok",
    );
  } catch (erro) {
    mensagemPrincipal(erro.message, "erro");
  }
}

document.querySelectorAll(".aba").forEach((aba) => {
  aba.addEventListener("click", () => ativarAba(aba.getAttribute("aria-controls")));
});
document.getElementById("ir-formulario").addEventListener("click", novoCadastro);
document.getElementById("salvar-cadastro").addEventListener("click", salvarCadastro);
document.getElementById("excluir-processos-selecionados")?.addEventListener("click", () => {
  const ids = idsProcessosSelecionados();
  const codigos = ids.map((id) => {
    const linha = document.querySelector(`#lista-processos tr[data-id="${id}"] .codigo-processo`);
    return linha?.textContent?.trim() || String(id);
  });
  excluirProcessosPorIds(ids, codigos);
});
document.getElementById("processos-marcar-todos")?.addEventListener("change", (evento) => {
  const marcado = Boolean(evento.target.checked);
  document.querySelectorAll("#lista-processos input[data-processo-check]").forEach((input) => {
    input.checked = marcado;
  });
  atualizarBotaoExcluirProcessos();
});

preencherFormularioProcessoSei();
preencherFixos();
campo("tecnologia").addEventListener("change", () => {
  const nova = campo("tecnologia").value;
  const anterior = tecnologiaDaArvore;
  if (nova !== anterior) dados.catalogo = [];
  dados.tecnologia = nova;
  tecnologiaDaArvore = nova;
  const atualAssunto = campo("assunto").value.trim();
  if (!atualAssunto || atualAssunto === assuntoPadrao(anterior)) {
    const sugerido = assuntoPadrao(nova);
    if (sugerido) {
      campo("assunto").value = sugerido;
      dados.assunto = sugerido;
    }
  }
  salvar();
  preencherTecnologias();
  desenharArvore();
  desenhar();
});
document.getElementById("gravar-tecnologia").addEventListener("click", gravarTecnologia);
document.getElementById("gravar-grupo").addEventListener("click", gravarGrupo);
window.GCPD = window.GCPD || {};
window.GCPD.sincronizarCamposTags = sincronizarCamposTags;
document.addEventListener("gcpd:tags-atualizadas", () => {
  carregarTagsConfiguracao();
});
ligarMultiDocsUi();
document.getElementById("ia-campo-fechar")?.addEventListener("click", fecharPainelIaCampo);
document.getElementById("ia-campo-cancelar")?.addEventListener("click", fecharPainelIaCampo);
document.getElementById("ia-campo-buscar")?.addEventListener("click", () => { executarBuscaIaCampo(); });
document.getElementById("ia-campo-inserir")?.addEventListener("click", inserirSelecaoIaNoCampo);
document.getElementById("painel-ia-campo")?.addEventListener("click", (evento) => {
  if (evento.target.id === "painel-ia-campo") fecharPainelIaCampo();
});
document.getElementById("ia-campo-resultados")?.addEventListener("change", () => sincronizarTextoFinalIa(true));
document.getElementById("ia-campo-refino")?.addEventListener("click", (evento) => {
  const botao = evento.target.closest("[data-refino-opcao]");
  if (!botao) return;
  const card = botao.closest(".refino-card");
  const pergunta = card?.querySelector("strong")?.textContent || "";
  aplicarRefinoIa(botao.dataset.refinoOpcao, pergunta);
});
document.getElementById("ia-campo-texto-final")?.addEventListener("input", () => {
  const final = document.getElementById("ia-campo-texto-final");
  if (final) final.dataset.editado = "1";
  atualizarContadorIaCampo();
  atualizarBotaoInserirIa();
});
document.getElementById("ia-campo-prompt")?.addEventListener("keydown", (evento) => {
  if ((evento.ctrlKey || evento.metaKey) && evento.key === "Enter") {
    evento.preventDefault();
    executarBuscaIaCampo();
  }
});

carregarAcervo();
carregarProcessos();
carregarTagsConfiguracao();
carregarSessaoSei().then(() => retomarAberturaIaSeHouver());
