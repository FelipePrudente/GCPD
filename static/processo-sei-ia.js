const INTERESSADO_PADRAO = "GESP - TUPP";

let csrfSei = "";
let abrirIaPacote = null;
let tiposProcessoSei = [];
let assuntosSei = [];
let tiposDocumento = [];
let modoEdicao = false;
let edicao = {};
let estadoChat = null;
let enviandoChat = false;

function escHtml(texto) {
  return String(texto ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatarMarkdownLeve(texto) {
  return escHtml(texto)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\n/g, "<br>");
}

function rotuloNivel(valor) {
  if (valor === "restrito") return "Restrito";
  if (valor === "sigiloso") return "Sigiloso";
  return "Público";
}

async function lerJson(resposta) {
  const tipo = resposta.headers.get("content-type") || "";
  if (!tipo.includes("application/json")) {
    throw new Error(`O servidor respondeu em formato inesperado (HTTP ${resposta.status}).`);
  }
  return resposta.json();
}

function mensagem(id, texto, tipo = "erro") {
  const el = document.getElementById(id);
  if (!el) return;
  if (!texto) {
    el.textContent = "";
    el.className = "erro oculto";
    return;
  }
  el.textContent = texto;
  el.className = tipo === "ok" ? "ok" : (tipo === "aviso" ? "aviso" : "erro");
  el.classList.remove("oculto");
}

async function carregarSessao() {
  const resposta = await fetch("/api/sei/sessao");
  const corpo = await lerJson(resposta);
  if (!resposta.ok || !corpo.autenticado) {
    window.location.replace("/");
    return false;
  }
  csrfSei = corpo.csrf_token || "";
  const status = document.getElementById("sei-sessao-status");
  if (status) status.textContent = `Conectado ao SEI como ${corpo.usuario || "usuário"}`;
  return true;
}

async function garantirListas() {
  if (!tiposProcessoSei.length) {
    const resposta = await fetch("/api/tipos-processo-sei");
    const corpo = await lerJson(resposta);
    tiposProcessoSei = corpo.tipos || [];
  }
  if (!assuntosSei.length) {
    const resposta = await fetch("/api/assuntos-sei");
    const corpo = await lerJson(resposta);
    assuntosSei = corpo.assuntos || [];
  }
  if (!tiposDocumento.length) {
    const resposta = await fetch("/api/tipos-documento-sei");
    const corpo = await lerJson(resposta);
    tiposDocumento = corpo.tipos || [];
  }
}

function preencherEdicao(pacote) {
  const p = pacote.preview || {};
  const doc = pacote.documento || {};
  const nomeDoc = String(p.tipo_documento || "").replace(/^\d+\s*[—-]\s*/, "");
  edicao = {
    tipo_processo: p.tipo_processo || pacote.processo?.tipo_processo_sei || "",
    especificacao: p.especificacao || "",
    assunto: p.assunto || "",
    interessado: p.interessado || INTERESSADO_PADRAO,
    nivel_acesso: pacote.processo?.processo_contratacao?.nivel_acesso || "publico",
    idSerie: String(doc.idSerie || ""),
    tipo_documento_nome: nomeDoc,
    assuntoDocumento: p.assunto || "",
  };
  if (!edicao.tipo_documento_nome && edicao.idSerie) {
    const achado = tiposDocumento.find((d) => String(d.id) === edicao.idSerie);
    if (achado) edicao.tipo_documento_nome = achado.nome;
  }
}

function tipoDocumentoSelecionado() {
  return tiposDocumento.find((tipo) => String(tipo.id) === String(edicao.idSerie)) || null;
}

function desenharLeitura() {
  const host = document.getElementById("resumo-leitura");
  const tipoDoc = tipoDocumentoSelecionado();
  const linhas = [
    ["Processo", edicao.tipo_processo],
    ["Assunto", edicao.assunto],
    ["Interessado", edicao.interessado],
    ["Nível de acesso", rotuloNivel(edicao.nivel_acesso)],
    ["Documento", edicao.idSerie ? `${edicao.idSerie} — ${edicao.tipo_documento_nome}` : edicao.tipo_documento_nome],
  ];
  if (tipoDoc?.precisa_assunto) linhas.push(["Assunto do documento", edicao.assuntoDocumento]);
  host.innerHTML = linhas.map(([rotulo, valor]) => `
    <div>
      <dt>${escHtml(rotulo)}</dt>
      <dd>${escHtml(valor || "—")}</dd>
    </div>
  `).join("");
  host.classList.remove("oculto");
  document.getElementById("abrir-ia-edicao").classList.add("oculto");
  document.getElementById("abrir-ia-editar").textContent = "Editar Campos";
  modoEdicao = false;
}

function htmlLista(itens, selecionado, valorChave, rotuloChave, dataAttr) {
  if (!itens.length) {
    return `<div class="abrir-ia-lista"><p class="lista-tipos-vazia">Nenhuma opção disponível.</p></div>`;
  }
  return `<div class="abrir-ia-lista">${itens.map((item) => {
    const valor = String(item[valorChave] ?? "");
    const rotulo = String(item[rotuloChave] ?? valor);
    return `<button type="button" ${dataAttr}="${escHtml(valor)}" aria-pressed="${valor === String(selecionado)}">${escHtml(rotulo)}</button>`;
  }).join("")}</div>`;
}

function desenharListas(filtroTipo = "", filtroAssunto = "", filtroDoc = "") {
  const tipos = tiposProcessoSei.filter((t) => String(t.nome || "").toLocaleLowerCase().includes(filtroTipo.toLocaleLowerCase()));
  const assuntos = assuntosSei.filter((a) => String(a.nome || "").toLocaleLowerCase().includes(filtroAssunto.toLocaleLowerCase()));
  const docs = tiposDocumento
    .filter((d) => `${d.id} ${d.nome}`.toLocaleLowerCase().includes(filtroDoc.toLocaleLowerCase()))
    .map((d) => ({ id: String(d.id), rotulo: `${d.id} — ${d.nome}` }));
  const tipoHost = document.getElementById("abrir-ia-lista-tipo");
  const assuntoHost = document.getElementById("abrir-ia-lista-assunto");
  const docHost = document.getElementById("abrir-ia-lista-documento");
  if (tipoHost) tipoHost.innerHTML = htmlLista(tipos, edicao.tipo_processo, "nome", "nome", "data-tipo");
  if (assuntoHost) assuntoHost.innerHTML = htmlLista(assuntos, edicao.assunto, "nome", "nome", "data-assunto");
  if (docHost) {
    docHost.innerHTML = docs.length
      ? `<div class="abrir-ia-lista">${docs.map((item) => `
          <button type="button" data-doc="${escHtml(item.id)}" aria-pressed="${item.id === String(edicao.idSerie)}">${escHtml(item.rotulo)}</button>
        `).join("")}</div>`
      : `<div class="abrir-ia-lista"><p class="lista-tipos-vazia">Nenhuma opção disponível.</p></div>`;
  }
}

function desenharEdicao() {
  const host = document.getElementById("abrir-ia-edicao");
  host.innerHTML = `
    <div class="abrir-ia-campo">
      <label>Processo</label>
      <input type="search" class="abrir-ia-filtro" id="abrir-ia-filtro-tipo" placeholder="Filtrar tipo de processo" autocomplete="off" />
      <div id="abrir-ia-lista-tipo"></div>
    </div>
    <div class="abrir-ia-campo">
      <label>Assunto</label>
      <input type="search" class="abrir-ia-filtro" id="abrir-ia-filtro-assunto" placeholder="Filtrar assunto" autocomplete="off" />
      <div id="abrir-ia-lista-assunto"></div>
    </div>
    <div class="abrir-ia-campo">
      <label for="abrir-ia-interessado">Interessado</label>
      <input id="abrir-ia-interessado" type="text" value="${escHtml(edicao.interessado)}" />
    </div>
    <div class="abrir-ia-campo">
      <label for="abrir-ia-nivel">Nível de acesso</label>
      <select id="abrir-ia-nivel">
        <option value="publico">Público</option>
        <option value="restrito">Restrito</option>
        <option value="sigiloso">Sigiloso</option>
      </select>
    </div>
    <div class="abrir-ia-campo">
      <label>Documento</label>
      <input type="search" class="abrir-ia-filtro" id="abrir-ia-filtro-documento" placeholder="Filtrar tipo documental" autocomplete="off" />
      <div id="abrir-ia-lista-documento"></div>
    </div>
    <div class="abrir-ia-campo oculto" id="abrir-ia-assunto-doc">
      <label>Assunto do documento</label>
      <input type="search" class="abrir-ia-filtro" id="abrir-ia-filtro-assunto-doc" placeholder="Filtrar assunto do documento" autocomplete="off" />
      <div id="abrir-ia-lista-assunto-doc"></div>
    </div>
  `;
  const nivel = document.getElementById("abrir-ia-nivel");
  if (nivel) nivel.value = edicao.nivel_acesso || "publico";
  desenharListas();
  atualizarAssuntoDocumento();
  host.querySelectorAll('[aria-pressed="true"]').forEach((botao) => {
    botao.scrollIntoView({ block: "nearest" });
  });
  document.getElementById("resumo-leitura").classList.add("oculto");
  host.classList.remove("oculto");
  document.getElementById("abrir-ia-editar").textContent = "Concluir edição";
  modoEdicao = true;
}

function atualizarAssuntoDocumento(filtro = "") {
  const bloco = document.getElementById("abrir-ia-assunto-doc");
  const lista = document.getElementById("abrir-ia-lista-assunto-doc");
  const tipo = tipoDocumentoSelecionado();
  if (!bloco || !lista) return;
  const exige = Boolean(tipo?.precisa_assunto);
  bloco.classList.toggle("oculto", !exige);
  if (!exige) return;
  if (!edicao.assuntoDocumento) edicao.assuntoDocumento = edicao.assunto || "";
  const q = String(filtro || "").toLocaleLowerCase();
  const itens = assuntosSei.filter((item) => !q || String(item.nome || "").toLocaleLowerCase().includes(q));
  lista.innerHTML = htmlLista(itens, edicao.assuntoDocumento, "nome", "nome", "data-assunto-doc");
}

function lerEdicaoDoFormulario() {
  edicao.especificacao = "";
  edicao.interessado = document.getElementById("abrir-ia-interessado")?.value.trim() || INTERESSADO_PADRAO;
  edicao.nivel_acesso = document.getElementById("abrir-ia-nivel")?.value || "publico";
  if (!edicao.tipo_processo) throw new Error("Selecione o tipo de processo na lista.");
  if (!edicao.assunto) throw new Error("Selecione um assunto na lista.");
  if (!edicao.idSerie) throw new Error("Selecione o tipo de documento na lista.");
  if (tipoDocumentoSelecionado()?.precisa_assunto && !edicao.assuntoDocumento) {
    throw new Error("Este tipo documental exige um assunto.");
  }
}

function montarPayload() {
  const tipo = tipoDocumentoSelecionado();
  const assuntoDoc = assuntosSei.find((item) => item.nome === edicao.assuntoDocumento);
  const documento = {
    idSerie: String(edicao.idSerie),
    descricao: "",
    nomeArvore: "",
    nivelAcesso: edicao.nivel_acesso === "sigiloso" ? "2" : (edicao.nivel_acesso === "restrito" ? "1" : "0"),
    assuntos: tipo?.precisa_assunto ? String(assuntoDoc?.id_sei || "") : "",
    observacao: "",
    idUnidadeGeradoraProtocolo: "110000001",
  };
  if (tipo?.precisa_numero) documento.numero = "DDS001";
  return {
    processo: {
      tipo_processo_sei: edicao.tipo_processo,
      assunto: edicao.tipo_processo || "",
      processo_contratacao: {
        especificacao: "",
        descricao: "",
        prioridade: abrirIaPacote?.processo?.processo_contratacao?.prioridade || "",
        interessados: [edicao.interessado],
        assuntos: [edicao.assunto],
        observacoes: abrirIaPacote?.processo?.processo_contratacao?.observacoes || "",
        nivel_acesso: edicao.nivel_acesso,
      },
      processo_sei: {
        protocolo: "automatico",
        especificacao: "",
        prioridade: abrirIaPacote?.processo?.processo_sei?.prioridade || "",
        interessados: [edicao.interessado],
        assuntos: [edicao.assunto],
        observacoes: abrirIaPacote?.processo?.processo_sei?.observacoes || "",
        nivel_acesso: edicao.nivel_acesso,
      },
    },
    documento,
  };
}

function scrollChat() {
  const host = document.getElementById("chat-mensagens");
  if (host) host.scrollTop = host.scrollHeight;
}

function adicionarBolha(papel, html, opcoes = []) {
  const host = document.getElementById("chat-mensagens");
  if (!host) return;
  const bloco = document.createElement("div");
  bloco.className = `chat-bolha chat-papel-${papel}`;
  bloco.innerHTML = `<div class="chat-texto">${html}</div>`;
  if (opcoes.length) {
    const lista = document.createElement("div");
    lista.className = "chat-opcoes";
    opcoes.forEach((opcao) => {
      const botao = document.createElement("button");
      botao.type = "button";
      botao.className = opcao.tipo === "acao" ? "chat-opcao chat-opcao-acao" : "chat-opcao";
      botao.textContent = opcao.rotulo || opcao.valor || opcao.id;
      botao.addEventListener("click", () => enviarChat({ escolha: opcao }));
      lista.appendChild(botao);
    });
    bloco.appendChild(lista);
  }
  host.appendChild(bloco);
  scrollChat();
}

function mostrarDigitando(ativo) {
  const existente = document.getElementById("chat-digitando");
  if (existente) existente.remove();
  if (!ativo) return;
  const host = document.getElementById("chat-mensagens");
  const el = document.createElement("div");
  el.id = "chat-digitando";
  el.className = "chat-bolha chat-papel-assistente chat-digitando";
  el.textContent = "Consultando as listas…";
  host.appendChild(el);
  scrollChat();
}

async function irParaRevisao(pacote) {
  abrirIaPacote = pacote;
  await garantirListas();
  preencherEdicao(pacote);
  document.getElementById("etapa-chat").classList.add("oculto");
  document.getElementById("etapa-revisao").classList.remove("oculto");
  const fonte = document.getElementById("abrir-ia-fonte");
  fonte.textContent = [pacote.resumo, pacote.fonte ? `Fonte: ${pacote.fonte}` : ""].filter(Boolean).join(" · ");
  desenharLeitura();
  mensagem("abrir-ia-mensagem-revisao", "Confira os campos. Se quiser ajustar, use Editar Campos.", "aviso");
}

async function enviarChat({ mensagemTexto = "", escolha = null, silencioso = false } = {}) {
  if (enviandoChat) return;
  const entrada = document.getElementById("chat-entrada");
  const texto = String(mensagemTexto || entrada?.value || "").trim();
  if (!texto && !escolha && !silencioso) return;

  if (texto && !escolha) {
    adicionarBolha("usuario", formatarMarkdownLeve(texto));
    if (entrada) entrada.value = "";
  } else if (escolha && !silencioso) {
    adicionarBolha("usuario", formatarMarkdownLeve(escolha.rotulo || escolha.valor || "Opção selecionada"));
  }

  enviandoChat = true;
  document.getElementById("chat-enviar").disabled = true;
  mostrarDigitando(true);
  mensagem("abrir-ia-mensagem", "");
  try {
    const resposta = await fetch("/api/ia/assistente-abertura", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mensagem: escolha ? "" : texto,
        escolha,
        estado: estadoChat,
      }),
    });
    const corpo = await lerJson(resposta);
    mostrarDigitando(false);
    if (!resposta.ok || !corpo.ok) {
      throw new Error(corpo.mensagem || "Não foi possível falar com o assistente.");
    }
    estadoChat = corpo.estado || estadoChat;
    adicionarBolha("assistente", formatarMarkdownLeve(corpo.mensagem || ""), corpo.opcoes || []);
    if (corpo.pacote?.ok) {
      await irParaRevisao(corpo.pacote);
    }
  } catch (erro) {
    mostrarDigitando(false);
    mensagem("abrir-ia-mensagem", erro.message || "Falha no assistente.");
  } finally {
    enviandoChat = false;
    document.getElementById("chat-enviar").disabled = false;
    document.getElementById("chat-entrada")?.focus();
  }
}

async function iniciarChat() {
  estadoChat = null;
  document.getElementById("chat-mensagens").innerHTML = "";
  document.getElementById("etapa-revisao").classList.add("oculto");
  document.getElementById("etapa-chat").classList.remove("oculto");
  await enviarChat({ silencioso: true });
}

async function confirmar() {
  const botao = document.getElementById("abrir-ia-confirmar");
  botao.disabled = true;
  mensagem("abrir-ia-mensagem-revisao", "Criando processo e documento no SEI…", "aviso");
  try {
    if (modoEdicao) lerEdicaoDoFormulario();
    else if (tipoDocumentoSelecionado()?.precisa_assunto && !edicao.assuntoDocumento) {
      throw new Error("Este tipo documental exige um assunto.");
    }
    const payload = montarPayload();
    const resposta = await fetch("/api/processos/criar-com-documento", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfSei,
      },
      body: JSON.stringify(payload),
    });
    const corpo = await lerJson(resposta);
    if (corpo.ok && corpo.processo && corpo.documento?.id_documento) {
      sessionStorage.setItem("gcpd-pos-abertura-ia", JSON.stringify({
        processoId: corpo.processo.id,
        documentoId: corpo.documento.id_documento,
        protocolo: corpo.protocolo || corpo.processo.numero_sei || "",
        protocoloDocumento: corpo.documento.protocolo || "",
        descricao: payload.documento.descricao || "",
      }));
      sessionStorage.setItem("gcpd-contexto-formulario-ia", JSON.stringify({
        pedido: estadoChat?.pedido || edicao.especificacao || "",
        interessado: edicao.interessado || INTERESSADO_PADRAO,
        assunto: edicao.assunto || "",
        tipo_processo: edicao.tipo_processo || "",
        numero_sei: corpo.protocolo || corpo.processo.numero_sei || "",
      }));
      window.location.href = "/";
      return;
    }
    throw new Error(corpo.mensagem || "Não foi possível criar o processo/documento no SEI.");
  } catch (erro) {
    mensagem("abrir-ia-mensagem-revisao", erro.message || "Falha ao criar no SEI.");
    botao.disabled = false;
  }
}

document.getElementById("chat-form")?.addEventListener("submit", (evento) => {
  evento.preventDefault();
  enviarChat();
});
document.getElementById("chat-entrada")?.addEventListener("keydown", (evento) => {
  if (evento.key === "Enter" && !evento.shiftKey) {
    evento.preventDefault();
    enviarChat();
  }
});
document.getElementById("chat-reiniciar")?.addEventListener("click", () => iniciarChat());
document.getElementById("abrir-ia-voltar-prompt")?.addEventListener("click", () => {
  document.getElementById("etapa-revisao").classList.add("oculto");
  document.getElementById("etapa-chat").classList.remove("oculto");
  modoEdicao = false;
  scrollChat();
});
document.getElementById("abrir-ia-editar")?.addEventListener("click", async () => {
  if (modoEdicao) {
    try {
      lerEdicaoDoFormulario();
      desenharLeitura();
      mensagem("abrir-ia-mensagem-revisao", "Campos atualizados. Confira o resumo antes de criar no SEI.", "aviso");
    } catch (erro) {
      mensagem("abrir-ia-mensagem-revisao", erro.message);
    }
    return;
  }
  await garantirListas();
  desenharEdicao();
  mensagem("abrir-ia-mensagem-revisao", "Edite os campos e clique em Concluir edição para voltar ao resumo.", "aviso");
});
document.getElementById("abrir-ia-confirmar")?.addEventListener("click", confirmar);
document.getElementById("abrir-ia-edicao")?.addEventListener("input", (evento) => {
  const alvo = evento.target;
  if (alvo?.id === "abrir-ia-filtro-tipo") {
    desenharListas(alvo.value, document.getElementById("abrir-ia-filtro-assunto")?.value || "", document.getElementById("abrir-ia-filtro-documento")?.value || "");
  }
  if (alvo?.id === "abrir-ia-filtro-assunto") {
    desenharListas(document.getElementById("abrir-ia-filtro-tipo")?.value || "", alvo.value, document.getElementById("abrir-ia-filtro-documento")?.value || "");
  }
  if (alvo?.id === "abrir-ia-filtro-documento") {
    desenharListas(document.getElementById("abrir-ia-filtro-tipo")?.value || "", document.getElementById("abrir-ia-filtro-assunto")?.value || "", alvo.value);
  }
  if (alvo?.id === "abrir-ia-filtro-assunto-doc") atualizarAssuntoDocumento(alvo.value);
});
document.getElementById("abrir-ia-edicao")?.addEventListener("click", (evento) => {
  const tipo = evento.target.closest("[data-tipo]");
  if (tipo) {
    edicao.tipo_processo = tipo.getAttribute("data-tipo") || "";
    desenharListas(
      document.getElementById("abrir-ia-filtro-tipo")?.value || "",
      document.getElementById("abrir-ia-filtro-assunto")?.value || "",
      document.getElementById("abrir-ia-filtro-documento")?.value || "",
    );
    return;
  }
  const assunto = evento.target.closest("[data-assunto]");
  if (assunto) {
    edicao.assunto = assunto.getAttribute("data-assunto") || "";
    desenharListas(
      document.getElementById("abrir-ia-filtro-tipo")?.value || "",
      document.getElementById("abrir-ia-filtro-assunto")?.value || "",
      document.getElementById("abrir-ia-filtro-documento")?.value || "",
    );
    return;
  }
  const doc = evento.target.closest("[data-doc]");
  if (doc) {
    edicao.idSerie = doc.getAttribute("data-doc") || "";
    const achado = tiposDocumento.find((item) => String(item.id) === edicao.idSerie);
    edicao.tipo_documento_nome = achado?.nome || "";
    desenharListas(
      document.getElementById("abrir-ia-filtro-tipo")?.value || "",
      document.getElementById("abrir-ia-filtro-assunto")?.value || "",
      document.getElementById("abrir-ia-filtro-documento")?.value || "",
    );
    atualizarAssuntoDocumento(document.getElementById("abrir-ia-filtro-assunto-doc")?.value || "");
    return;
  }
  const assuntoDoc = evento.target.closest("[data-assunto-doc]");
  if (assuntoDoc) {
    edicao.assuntoDocumento = assuntoDoc.getAttribute("data-assunto-doc") || "";
    atualizarAssuntoDocumento(document.getElementById("abrir-ia-filtro-assunto-doc")?.value || "");
  }
});
document.getElementById("sei-logout")?.addEventListener("click", async () => {
  try {
    await fetch("/api/sei/logout", { method: "POST", headers: { "X-CSRF-Token": csrfSei } });
  } finally {
    window.location.replace("/");
  }
});

carregarSessao().then((ok) => {
  if (ok) iniciarChat();
});
