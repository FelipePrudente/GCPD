/* Configurações — catálogo de documentos com tags vinculadas a cada documento. */
(function () {
  let estado = {
    tags: [],
    grupos: [],
    secoes: [],
    tags_formulario: [],
    documento: "",
    ativo: "",
    nome: "",
    documentos: [],
    origem: "",
  };
  let editandoDocumento = false;
  let documentoAntes = "";
  let secoesAntes = [];
  let nomeAntes = "";
  let tagEmEdicao = null;
  let tagSelecionadaId = null;
  let tagCopiada = null;
  // Drill: true = expandido (drill down), false = recolhido (drill up).
  let drillTagsAberto = {};
  let drillDocsAberto = {};
  const MIME_TAG = "application/x-gcpd-tag";
  const MIME_TAG_MOVE = "application/x-gcpd-tag-move";
  const MIME_ORDEM = "application/x-gcpd-tag-ordem";
  let tagDocEmMovimento = null;

  function chaveDrill(prefixo) {
    return `gcpd-drill-${prefixo}-${estado.ativo || "geral"}`;
  }

  function lerDrill(prefixo) {
    try {
      const bruto = JSON.parse(localStorage.getItem(chaveDrill(prefixo)) || "{}");
      return bruto && typeof bruto === "object" ? bruto : {};
    } catch (erro) {
      return {};
    }
  }

  function salvarDrill(prefixo, mapa) {
    try {
      localStorage.setItem(chaveDrill(prefixo), JSON.stringify(mapa || {}));
    } catch (erro) {
      /* ignore quota */
    }
  }

  function carregarDrillDoDocumento() {
    drillTagsAberto = lerDrill("tags");
    drillDocsAberto = lerDrill("docs");
  }

  function grupoExpandido(mapa, nome, padrao = true) {
    if (!nome) return padrao;
    if (Object.prototype.hasOwnProperty.call(mapa, nome)) return Boolean(mapa[nome]);
    return padrao;
  }

  function definirDrillGrupo(mapa, prefixo, nome, aberto) {
    if (!nome) return;
    mapa[nome] = Boolean(aberto);
    salvarDrill(prefixo, mapa);
  }

  function definirDrillTodos(mapa, prefixo, nomes, aberto) {
    (nomes || []).forEach((nome) => {
      if (nome) mapa[nome] = Boolean(aberto);
    });
    salvarDrill(prefixo, mapa);
  }

  function escHtml(texto) {
    return String(texto ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function metaTag(id) {
    return estado.tags.find((item) => item.id === id) || null;
  }

  function folhaDocumento(raiz) {
    const base = raiz || document.getElementById("preview-rj");
    return base?.querySelector("article.folha-rj, article.folha-doc, article") || null;
  }

  function corposEditaveis(raiz) {
    const base = raiz || document.getElementById("preview-rj");
    return [...(base?.querySelectorAll(".card-bloco-corpo") || [])];
  }

  function sincronizarSecoesComGrupos() {
    const mapa = Object.fromEntries(
      (estado.secoes || [])
        .filter((s) => s && s.grupo)
        .map((s) => [s.grupo, s.html || "<p></p>"]),
    );
    estado.secoes = (estado.grupos || []).map((grupo) => ({
      grupo,
      html: mapa[grupo] || "<p></p>",
    }));
    estado.documento = montarDocumentoDeSecoes(estado.secoes);
  }

  function montarDocumentoDeSecoes(secoes) {
    const cards = (secoes || []).map((secao) => {
      const nomeGrupo = secao.grupo || "";
      const grupo = escHtml(nomeGrupo);
      const corpo = secao.html || "<p></p>";
      const aberto = grupoExpandido(drillDocsAberto, nomeGrupo, true);
      return `<section class="card-bloco${aberto ? "" : " recolhido"}" data-grupo="${grupo}">
        <header class="card-bloco-cabecalho" data-drill-doc="${grupo}" role="button" tabindex="0" aria-expanded="${aberto ? "true" : "false"}" title="Clique para ${aberto ? "recolher" : "expandir"}">
          <span class="drill-seta" aria-hidden="true"></span>
          <h3>${grupo}</h3>
          <span class="drill-meta">${aberto ? "aberto" : "recolhido"}</span>
        </header>
        <div class="card-bloco-corpo">${corpo}</div>
      </section>`;
    }).join("");
    return `<article class="folha-doc">${cards}</article>`;
  }

  function lerSecoesDoDom() {
    const preview = document.getElementById("preview-rj");
    if (!preview) return estado.secoes || [];
    return [...preview.querySelectorAll(".card-bloco")].map((card) => {
      const grupo = card.dataset.grupo || card.querySelector(".card-bloco-cabecalho h3")?.textContent || "";
      const corpo = card.querySelector(".card-bloco-corpo");
      const clone = corpo ? corpo.cloneNode(true) : null;
      if (clone) {
        clone.querySelectorAll(".tag-doc").forEach((el) => {
          const id = el.dataset.tag || "";
          el.replaceWith(document.createTextNode(`{{${id}}}`));
        });
      }
      return { grupo, html: (clone?.innerHTML || "<p></p>").trim() || "<p></p>" };
    });
  }

  function status(mensagem, tipo) {
    const el = document.getElementById("config-rj-status");
    if (!el) return;
    el.textContent = mensagem || "";
    el.className = tipo === "erro" ? "erro" : tipo === "ok" ? "ok" : "total";
  }

  function chipHtml(id) {
    const meta = metaTag(id);
    const classe = meta?.calculado ? "tag-doc calculado" : "tag-doc";
    const titulo = escHtml(meta?.rotulo || id);
    const dica = editandoDocumento
      ? `${titulo} — arraste para mover no texto`
      : titulo;
    return `<span class="${classe}" data-tag="${escHtml(id)}" contenteditable="false" draggable="${editandoDocumento ? "true" : "false"}" title="${dica}">{{${escHtml(id)}}}</span>`;
  }

  function prepararTagsDocEditaveis(raiz) {
    const base = raiz || document.getElementById("preview-rj");
    base?.querySelectorAll(".tag-doc").forEach((el) => {
      el.draggable = Boolean(editandoDocumento);
      const id = el.dataset.tag || "";
      const meta = metaTag(id);
      const titulo = meta?.rotulo || id;
      el.title = editandoDocumento
        ? `${titulo} — arraste para mover no texto`
        : titulo;
    });
  }

  function documentoParaVisual(html) {
    return String(html || "").replace(/\{\{\s*([a-zA-Z][a-zA-Z0-9_]*)\s*\}\}/g, (_, id) => chipHtml(id));
  }

  function aplicarEstadoApi(corpo) {
    const brutoDoc = corpo.documento;
    const doc = brutoDoc && typeof brutoDoc === "object" ? brutoDoc : {};
    const tagsDoc = Array.isArray(doc.tags) ? doc.tags : (corpo.tags || []);
    const gruposDoc = Array.isArray(doc.grupos) ? doc.grupos : (corpo.grupos || []);
    const secoesDoc = Array.isArray(doc.secoes) ? doc.secoes : (corpo.secoes || []);
    estado = {
      tags: tagsDoc,
      grupos: gruposDoc,
      secoes: secoesDoc,
      tags_formulario: corpo.tags_formulario || tagsDoc,
      documento: doc.documento || (typeof brutoDoc === "string" ? brutoDoc : "") || "",
      ativo: corpo.ativo || doc.id || "",
      nome: doc.nome || estado.nome || "",
      documentos: corpo.documentos || [],
      origem: doc.origem || "",
    };
    carregarDrillDoDocumento();
    sincronizarSecoesComGrupos();
  }

  async function carregar() {
    status("Carregando configuração…");
    const resposta = await fetch("/api/config/catalogo");
    const corpo = await resposta.json();
    if (!resposta.ok) throw new Error(corpo.mensagem || "Falha ao carregar configuração.");
    aplicarEstadoApi(corpo);
    status("");
  }

  function avisarFormulario() {
    const tagsForm = estado.tags_formulario || estado.tags || [];
    document.dispatchEvent(new CustomEvent("gcpd:tags-atualizadas", { detail: { tags: tagsForm } }));
    if (window.GCPD?.sincronizarCamposTags) window.GCPD.sincronizarCamposTags(tagsForm);
  }

  function tagPertenceAoGrupo(tag, grupo) {
    if (!tag || !grupo) return false;
    if (tag.grupo === grupo) return true;
    return Array.isArray(tag.reuso_em) && tag.reuso_em.includes(grupo);
  }

  function idsDoGrupo(grupo) {
    // Ordenação só vale para tags cujo grupo principal é este bloco.
    return estado.tags.filter((tag) => tag.grupo === grupo).map((tag) => tag.id);
  }

  function aplicarOrdemNoGrupo(grupo, ordemIds) {
    const doGrupo = estado.tags.filter((tag) => tag.grupo === grupo);
    const mapa = Object.fromEntries(doGrupo.map((tag) => [tag.id, tag]));
    const reordenadas = ordemIds.map((id) => mapa[id]).filter(Boolean);
    if (reordenadas.length !== doGrupo.length) return false;
    const nova = [];
    let inseriu = false;
    estado.tags.forEach((tag) => {
      if (tag.grupo !== grupo) {
        nova.push(tag);
        return;
      }
      if (!inseriu) {
        nova.push(...reordenadas);
        inseriu = true;
      }
    });
    estado.tags = nova;
    return true;
  }

  function moverTagNoGrupo(idMovida, idReferencia, colocarDepois) {
    const movida = metaTag(idMovida);
    const referencia = metaTag(idReferencia);
    if (!movida || !referencia || movida.grupo !== referencia.grupo || idMovida === idReferencia) return false;
    const ordem = idsDoGrupo(movida.grupo).filter((id) => id !== idMovida);
    let indice = ordem.indexOf(idReferencia);
    if (indice < 0) return false;
    if (colocarDepois) indice += 1;
    ordem.splice(indice, 0, idMovida);
    return aplicarOrdemNoGrupo(movida.grupo, ordem);
  }

  function moverTagDirecao(id, direcao) {
    const tag = metaTag(id);
    if (!tag) return false;
    const ordem = idsDoGrupo(tag.grupo);
    const indice = ordem.indexOf(id);
    const destino = indice + direcao;
    if (indice < 0 || destino < 0 || destino >= ordem.length) return false;
    ordem.splice(indice, 1);
    ordem.splice(destino, 0, id);
    return aplicarOrdemNoGrupo(tag.grupo, ordem);
  }

  async function persistirOrdem(mensagem) {
    try {
      await salvarTudo(mensagem || "Ordem das tags atualizada.");
      renderTags();
      renderDocumento();
    } catch (falha) {
      status(falha.message, "erro");
    }
  }

  async function salvarTudo(mensagemOk) {
    status("Salvando…");
    const nomeEl = document.getElementById("doc-nome-ativo");
    const nome = (nomeEl && !nomeEl.classList.contains("oculto") ? nomeEl.value : estado.nome) || estado.nome;
    const resposta = await fetch("/api/config/catalogo", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tags: estado.tags,
        grupos: estado.grupos,
        secoes: estado.secoes,
        ativo: estado.ativo,
        nome,
        documento: estado.documento,
      }),
    });
    const corpo = await resposta.json();
    if (!resposta.ok) throw new Error(corpo.mensagem || "Falha ao salvar.");
    aplicarEstadoApi(corpo);
    avisarFormulario();
    renderListaDocumentos();
    renderGrupos();
    atualizarCabecalhoDocumento();
    status(mensagemOk || "Configuração salva.", "ok");
  }

  function atualizarCabecalhoDocumento() {
    const titulo = document.getElementById("doc-titulo-ativo");
    const nomeEl = document.getElementById("doc-nome-ativo");
    if (titulo) titulo.textContent = estado.nome || "Documento";
    if (nomeEl) nomeEl.value = estado.nome || "";
    const excluir = document.getElementById("doc-excluir");
    if (excluir) excluir.disabled = false;
  }

  function atualizarBotaoExcluirDocs() {
    const botao = document.getElementById("doc-excluir-selecionados");
    if (!botao) return;
    const marcados = document.querySelectorAll("#lista-documentos input[data-doc-check]:checked").length;
    botao.disabled = marcados === 0;
    botao.textContent = marcados > 1 ? `Excluir marcados (${marcados})` : "Excluir marcados";
  }

  function renderListaDocumentos() {
    const lista = document.getElementById("lista-documentos");
    if (!lista) return;
    const docs = estado.documentos || [];
    if (!docs.length) {
      lista.innerHTML = `<p class="ajuda">Nenhum documento. Crie um novo ou envie Word/PDF.</p>`;
      atualizarBotaoExcluirDocs();
      return;
    }
    lista.innerHTML = docs.map((doc) => `
      <div class="doc-item-linha${doc.id === estado.ativo ? " ativo" : ""}" data-doc-linha="${escHtml(doc.id)}">
        <label class="doc-check" title="Selecionar para excluir">
          <input type="checkbox" data-doc-check="${escHtml(doc.id)}" aria-label="Selecionar ${escHtml(doc.nome)}" />
        </label>
        <button type="button" class="doc-item" data-doc-id="${escHtml(doc.id)}" title="Abrir documento">
          <span class="doc-item-nome">${escHtml(doc.nome)}</span>
          <span class="doc-item-meta">${escHtml(doc.origem === "upload" ? "Enviado" : doc.origem === "nativo" ? "Padrão" : "Manual")} · ${Number(doc.qtd_grupos || 0)} grupo(s) · ${Number(doc.qtd_tags || 0)} tag(s)</span>
        </button>
        <button type="button" class="doc-excluir-item" data-doc-excluir="${escHtml(doc.id)}" title="Excluir documento" aria-label="Excluir ${escHtml(doc.nome)}">Excluir</button>
      </div>`).join("");
    lista.querySelectorAll("[data-doc-id]").forEach((botao) => {
      botao.addEventListener("click", () => selecionarDocumento(botao.dataset.docId));
    });
    lista.querySelectorAll("[data-doc-excluir]").forEach((botao) => {
      botao.addEventListener("click", (evento) => {
        evento.preventDefault();
        evento.stopPropagation();
        excluirDocumentos([botao.dataset.docExcluir]);
      });
    });
    lista.querySelectorAll("[data-doc-check]").forEach((input) => {
      input.addEventListener("click", (evento) => evento.stopPropagation());
      input.addEventListener("change", atualizarBotaoExcluirDocs);
    });
    atualizarBotaoExcluirDocs();
  }

  async function selecionarDocumento(docId) {
    if (!docId || docId === estado.ativo) return;
    if (editandoDocumento) {
      status("Salve ou cancele a edição antes de trocar de documento.", "erro");
      return;
    }
    status("Abrindo documento…");
    const resposta = await fetch("/api/config/catalogo/ativo", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: docId }),
    });
    const corpo = await resposta.json();
    if (!resposta.ok) {
      status(corpo.mensagem || "Não foi possível abrir o documento.", "erro");
      return;
    }
    aplicarEstadoApi(corpo);
    renderListaDocumentos();
    atualizarCabecalhoDocumento();
    renderGrupos();
    renderTags();
    renderDocumento();
    avisarFormulario();
    status(`Documento “${estado.nome}” aberto.`, "ok");
  }

  async function criarDocumentoNovo() {
    if (editandoDocumento) {
      status("Salve ou cancele a edição antes de criar outro documento.", "erro");
      return;
    }
    const nome = window.prompt("Nome do novo documento:", "Novo documento");
    if (nome == null) return;
    status("Criando documento…");
    const resposta = await fetch("/api/config/catalogo/documento", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nome: nome.trim() || "Novo documento" }),
    });
    const corpo = await resposta.json();
    if (!resposta.ok) {
      status(corpo.mensagem || "Falha ao criar documento.", "erro");
      return;
    }
    aplicarEstadoApi(corpo);
    renderListaDocumentos();
    atualizarCabecalhoDocumento();
    renderGrupos();
    renderTags();
    renderDocumento();
    avisarFormulario();
    status("Documento criado. Defina os grupos/blocos antes de criar as tags.", "ok");
  }

  async function enviarDocumentoArquivo(arquivo) {
    if (!arquivo) return;
    if (editandoDocumento) {
      status("Salve ou cancele a edição antes de enviar outro arquivo.", "erro");
      return;
    }
    status("Lendo documento e tags…");
    const form = new FormData();
    form.append("arquivo", arquivo);
    const resposta = await fetch("/api/config/catalogo/upload", { method: "POST", body: form });
    const corpo = await resposta.json();
    if (!resposta.ok) {
      status(corpo.mensagem || "Falha ao importar arquivo.", "erro");
      return;
    }
    aplicarEstadoApi(corpo);
    renderListaDocumentos();
    atualizarCabecalhoDocumento();
    renderGrupos();
    renderTags();
    renderDocumento();
    avisarFormulario();
    const qtd = Number(corpo.qtd_tags || 0);
    status(
      corpo.mensagem
        || (qtd
          ? `Documento importado com ${qtd} tag(s). Formulário atualizado.`
          : "Documento importado. Defina os grupos e tags."),
      "ok",
    );
  }

  async function excluirDocumentos(ids) {
    const lista = [...new Set((ids || []).map((id) => String(id || "").trim()).filter(Boolean))];
    if (!lista.length) {
      status("Selecione ao menos um documento para excluir.", "erro");
      return;
    }
    if (editandoDocumento) {
      // Não bloqueia a exclusão: cancela a edição em andamento.
      editandoDocumento = false;
      status("Edição cancelada para permitir a exclusão.", "ok");
    }
    const nomes = lista.map((id) => {
      const alvo = (estado.documentos || []).find((doc) => doc.id === id);
      return alvo?.nome || id;
    });
    const apagaTodos = lista.length >= (estado.documentos || []).length;
    const aviso = lista.length === 1
      ? (apagaTodos
        ? `Excluir o documento “${nomes[0]}”? Como é o único do catálogo, será criado um “Novo documento” em branco.`
        : `Excluir o documento “${nomes[0]}”?`)
      : (apagaTodos
        ? `Excluir os ${lista.length} documentos? O catálogo ficará com um “Novo documento” em branco.`
        : `Excluir ${lista.length} documentos?\n- ${nomes.join("\n- ")}`);
    if (!window.confirm(aviso)) return;

    status(lista.length === 1 ? "Excluindo documento…" : `Excluindo ${lista.length} documentos…`);
    try {
      const resposta = await fetch("/api/config/catalogo/documentos", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids: lista }),
      });
      let corpo = {};
      try {
        corpo = await resposta.json();
      } catch (erroJson) {
        throw new Error("O servidor não retornou JSON válido ao excluir.");
      }
      if (!resposta.ok) throw new Error(corpo.mensagem || "Falha ao excluir.");
      aplicarEstadoApi(corpo);
      renderListaDocumentos();
      atualizarCabecalhoDocumento();
      renderGrupos();
      renderTags();
      renderDocumento();
      avisarFormulario();
      status(corpo.mensagem || "Documento(s) excluído(s).", "ok");
    } catch (erro) {
      status(erro.message || "Falha ao excluir documento.", "erro");
    }
  }

  async function excluirDocumento(docId) {
    const id = String(docId || estado.ativo || "").trim();
    if (!id) return;
    return excluirDocumentos([id]);
  }

  async function excluirDocumentoAtivo() {
    return excluirDocumentos([estado.ativo]);
  }

  function atualizarSelectGruposTag(selecionado) {
    const select = document.getElementById("tag-grupo");
    if (!select) return;
    const grupos = estado.grupos || [];
    select.innerHTML = `<option value="">Selecione um grupo</option>` + grupos.map(
      (grupo) => `<option value="${escHtml(grupo)}">${escHtml(grupo)}</option>`,
    ).join("");
    if (selecionado && grupos.includes(selecionado)) select.value = selecionado;
    else select.value = "";
    atualizarReusoGruposTag();
  }

  function atualizarReusoGruposTag(selecionados) {
    const host = document.getElementById("tag-reuso-lista");
    if (!host) return;
    const principal = document.getElementById("tag-grupo")?.value || "";
    const marcados = new Set(
      Array.isArray(selecionados)
        ? selecionados
        : [...host.querySelectorAll("input[data-reuso-grupo]:checked")].map((el) => el.value),
    );
    const outros = (estado.grupos || []).filter((g) => g !== principal);
    if (!outros.length) {
      host.innerHTML = `<span class="ajuda">Cadastre outros grupos neste documento para reutilizar a tag.</span>`;
      return;
    }
    host.innerHTML = outros.map((grupo) => `
      <label>
        <input type="checkbox" data-reuso-grupo value="${escHtml(grupo)}"${marcados.has(grupo) ? " checked" : ""} />
        ${escHtml(grupo)}
      </label>`).join("");
  }

  function lerReusoGruposTag() {
    return [...document.querySelectorAll("#tag-reuso-lista input[data-reuso-grupo]:checked")]
      .map((el) => el.value)
      .filter(Boolean);
  }

  function renderGrupos() {
    const lista = document.getElementById("lista-grupos-doc");
    const botaoTag = document.getElementById("tag-nova");
    if (botaoTag) botaoTag.disabled = !(estado.grupos || []).length;
    if (!lista) return;
    const grupos = estado.grupos || [];
    if (!grupos.length) {
      lista.innerHTML = `<p class="ajuda">Nenhum grupo neste documento. Crie os blocos antes das tags.</p>`;
      return;
    }
    lista.innerHTML = grupos.map((grupo, indice) => `
      <div class="grupo-doc-linha" data-grupo-idx="${indice}">
        <input type="text" value="${escHtml(grupo)}" maxlength="80" aria-label="Nome do grupo" data-grupo-nome />
        <div class="grupo-doc-acoes">
          <button type="button" class="tag-mini" data-grupo-acao="cima" title="Subir" ${indice === 0 ? "disabled" : ""}>↑</button>
          <button type="button" class="tag-mini" data-grupo-acao="baixo" title="Descer" ${indice === grupos.length - 1 ? "disabled" : ""}>↓</button>
          <button type="button" class="tag-mini perigo" data-grupo-acao="excluir" title="Excluir grupo">×</button>
        </div>
      </div>`).join("");

    lista.querySelectorAll("[data-grupo-nome]").forEach((input) => {
      input.addEventListener("change", () => renomearGrupoNaLinha(input));
      input.addEventListener("keydown", (evento) => {
        if (evento.key === "Enter") {
          evento.preventDefault();
          input.blur();
        }
      });
    });
    lista.querySelectorAll("[data-grupo-acao]").forEach((botao) => {
      botao.addEventListener("click", () => {
        const linha = botao.closest("[data-grupo-idx]");
        const idx = Number(linha?.dataset.grupoIdx);
        const acao = botao.dataset.grupoAcao;
        if (acao === "cima") moverGrupo(idx, -1);
        else if (acao === "baixo") moverGrupo(idx, 1);
        else if (acao === "excluir") excluirGrupo(idx);
      });
    });
  }

  async function persistirGrupos(mensagem) {
    sincronizarSecoesComGrupos();
    try {
      await salvarTudo(mensagem || "Grupos atualizados.");
      renderGrupos();
      renderTags();
      renderDocumento();
      atualizarSelectGruposTag();
    } catch (falha) {
      status(falha.message, "erro");
    }
  }

  function adicionarGrupo() {
    if (editandoDocumento) {
      status("Salve ou cancele a edição do texto antes de criar um grupo.", "erro");
      return;
    }
    const nome = window.prompt("Nome do grupo / bloco:", "");
    if (nome == null) return;
    const limpo = nome.trim();
    if (!limpo) {
      status("Informe um nome para o grupo.", "erro");
      return;
    }
    if ((estado.grupos || []).some((g) => g.toLowerCase() === limpo.toLowerCase())) {
      status("Já existe um grupo com este nome neste documento.", "erro");
      return;
    }
    let htmlInicial = "<p></p>";
    if (!(estado.grupos || []).length && estado.documento && !String(estado.documento).includes("card-bloco")) {
      const tmp = document.createElement("div");
      tmp.innerHTML = estado.documento;
      const art = tmp.querySelector("article");
      htmlInicial = (art ? art.innerHTML : tmp.innerHTML).trim() || "<p></p>";
    }
    estado.grupos = [...(estado.grupos || []), limpo];
    estado.secoes = [...(estado.secoes || []), { grupo: limpo, html: htmlInicial }];
    sincronizarSecoesComGrupos();
    persistirGrupos(`Grupo “${limpo}” criado com um card no documento.`);
  }

  function renomearGrupoNaLinha(input) {
    const linha = input.closest("[data-grupo-idx]");
    const idx = Number(linha?.dataset.grupoIdx);
    const antigo = estado.grupos[idx];
    const novo = input.value.trim();
    if (!antigo) return;
    if (!novo) {
      input.value = antigo;
      status("O nome do grupo não pode ficar vazio.", "erro");
      return;
    }
    if (novo === antigo) return;
    if (estado.grupos.some((g, i) => i !== idx && g.toLowerCase() === novo.toLowerCase())) {
      input.value = antigo;
      status("Já existe um grupo com este nome.", "erro");
      return;
    }
    estado.grupos[idx] = novo;
    estado.tags.forEach((tag) => {
      if (tag.grupo === antigo) tag.grupo = novo;
      if (Array.isArray(tag.reuso_em)) {
        tag.reuso_em = tag.reuso_em.map((g) => (g === antigo ? novo : g)).filter((g) => g !== tag.grupo);
      }
    });
    (estado.secoes || []).forEach((secao) => {
      if (secao.grupo === antigo) secao.grupo = novo;
    });
    sincronizarSecoesComGrupos();
    persistirGrupos(`Grupo renomeado para “${novo}”.`);
  }

  function moverGrupo(indice, direcao) {
    const destino = indice + direcao;
    if (destino < 0 || destino >= estado.grupos.length) return;
    const copia = [...estado.grupos];
    const [item] = copia.splice(indice, 1);
    copia.splice(destino, 0, item);
    estado.grupos = copia;
    sincronizarSecoesComGrupos();
    persistirGrupos("Ordem dos grupos e cards atualizada.");
  }

  function excluirGrupo(indice) {
    const nome = estado.grupos[indice];
    if (!nome) return;
    const usadas = estado.tags.filter((tag) => tag.grupo === nome);
    if (usadas.length) {
      status(`Não é possível excluir “${nome}”: há ${usadas.length} tag(s) neste grupo. Mova ou exclua as tags antes.`, "erro");
      return;
    }
    if (!window.confirm(`Excluir o grupo “${nome}” e o card correspondente no documento?`)) return;
    estado.grupos = estado.grupos.filter((_, i) => i !== indice);
    estado.secoes = (estado.secoes || []).filter((s) => s.grupo !== nome);
    estado.tags.forEach((tag) => {
      if (Array.isArray(tag.reuso_em)) {
        tag.reuso_em = tag.reuso_em.filter((g) => g !== nome);
      }
    });
    sincronizarSecoesComGrupos();
    persistirGrupos(`Grupo “${nome}” e respectivo card excluídos.`);
  }

  function renderTags() {
    const lista = document.getElementById("lista-tags-rj");
    if (!lista) return;
    const grupos = [...(estado.grupos || [])];
    estado.tags.forEach((tag) => {
      if (tag.grupo && !grupos.includes(tag.grupo)) grupos.push(tag.grupo);
    });
    if (!grupos.length) {
      lista.innerHTML = `<p class="ajuda">Defina ao menos um grupo/bloco para começar a criar tags em “${escHtml(estado.nome || "este documento")}”.</p>`;
      return;
    }
    if (!estado.tags.length) {
      lista.innerHTML = `<p class="ajuda">Nenhuma tag neste documento. Clique em Nova tag.</p>`;
      return;
    }
    lista.innerHTML = grupos.map((grupo) => {
      const itens = estado.tags.filter((tag) => tagPertenceAoGrupo(tag, grupo));
      const aberto = grupoExpandido(drillTagsAberto, grupo, true);
      const qtd = itens.length;
      const resumo = qtd ? `${qtd} tag(s)` : "vazio";
      if (!itens.length) {
        return `
          <div class="grupo-tags${aberto ? "" : " recolhido"}" data-grupo-tags="${escHtml(grupo)}">
            <button type="button" class="grupo-tags-cabeca" data-drill-tags="${escHtml(grupo)}" aria-expanded="${aberto ? "true" : "false"}">
              <span class="drill-seta" aria-hidden="true"></span>
              <span class="grupo-tags-titulo">${escHtml(grupo)}</span>
              <span class="drill-meta">${resumo}</span>
            </button>
            <div class="grupo-tags-corpo">
              <p class="ajuda">Sem tags neste bloco.</p>
            </div>
          </div>`;
      }
      return `
        <div class="grupo-tags${aberto ? "" : " recolhido"}" data-grupo-tags="${escHtml(grupo)}">
          <button type="button" class="grupo-tags-cabeca" data-drill-tags="${escHtml(grupo)}" aria-expanded="${aberto ? "true" : "false"}">
            <span class="drill-seta" aria-hidden="true"></span>
            <span class="grupo-tags-titulo">${escHtml(grupo)}</span>
            <span class="drill-meta">${resumo}</span>
          </button>
          <div class="grupo-tags-corpo">
            <div class="chips">
              ${itens.map((tag, indice) => {
                const reuso = tag.grupo !== grupo;
                return `
                <div class="tag-linha${tag.calculado ? " calculado" : ""}${tagSelecionadaId === tag.id ? " ativa" : ""}" data-tag="${escHtml(tag.id)}" data-grupo="${escHtml(grupo)}">
                  <button type="button" class="tag-handle" draggable="true" data-acao="ordenar" title="Arrastar para reordenar neste bloco" aria-label="Reordenar {{${escHtml(tag.id)}}}">⋮⋮</button>
                  <button type="button" class="tag-chip" data-acao="usar" draggable="true" title="Arraste para o documento ou Ctrl+C / Ctrl+V">
                    <code>{{${escHtml(tag.id)}}}</code>
                    <span>${escHtml(tag.rotulo)}</span>
                    ${reuso ? `<span class="reuso-badge" title="Reuso — valor preenchido em ${escHtml(tag.grupo)}">reuso</span>` : ""}
                  </button>
                  <div class="tag-acoes">
                    <button type="button" class="tag-mini" data-acao="cima" title="Subir no bloco" aria-label="Subir" ${indice === 0 ? "disabled" : ""}>↑</button>
                    <button type="button" class="tag-mini" data-acao="baixo" title="Descer no bloco" aria-label="Descer" ${indice === itens.length - 1 ? "disabled" : ""}>↓</button>
                    <button type="button" class="tag-mini" data-acao="editar" title="Editar tag" aria-label="Editar ${escHtml(tag.id)}">✎</button>
                    <button type="button" class="tag-mini perigo" data-acao="excluir" title="Excluir tag" aria-label="Excluir ${escHtml(tag.id)}">×</button>
                  </div>
                </div>`;
              }).join("")}
            </div>
          </div>
        </div>`;
    }).join("");
  }

  function alternarDrillTags(grupo) {
    if (!grupo) return;
    const aberto = !grupoExpandido(drillTagsAberto, grupo, true);
    definirDrillGrupo(drillTagsAberto, "tags", grupo, aberto);
    renderTags();
  }

  function atualizarCabecaDrillDoc(card, aberto) {
    if (!card) return;
    card.classList.toggle("recolhido", !aberto);
    const cabeca = card.querySelector(".card-bloco-cabecalho");
    if (cabeca) {
      cabeca.setAttribute("aria-expanded", aberto ? "true" : "false");
      cabeca.title = `Clique para ${aberto ? "recolher" : "expandir"}`;
    }
    const meta = card.querySelector(".drill-meta");
    if (meta) meta.textContent = aberto ? "aberto" : "recolhido";
  }

  function aplicarDrillDocsNoDom() {
    document.querySelectorAll("#preview-rj .card-bloco[data-grupo]").forEach((card) => {
      const grupo = card.dataset.grupo || "";
      const aberto = grupoExpandido(drillDocsAberto, grupo, true);
      atualizarCabecaDrillDoc(card, aberto);
    });
  }

  function alternarDrillDoc(grupo) {
    if (!grupo) return;
    const aberto = !grupoExpandido(drillDocsAberto, grupo, true);
    definirDrillGrupo(drillDocsAberto, "docs", grupo, aberto);
    const card = document.querySelector(`#preview-rj .card-bloco[data-grupo="${CSS.escape(grupo)}"]`);
    if (card) {
      atualizarCabecaDrillDoc(card, aberto);
      return;
    }
    // Sem DOM (ainda não renderizou): reaplica pelo estado.
    if (editandoDocumento) {
      estado.secoes = lerSecoesDoDom();
      sincronizarSecoesComGrupos();
    }
    renderDocumento();
  }

  function expandirGrupoTags(grupo) {
    if (!grupo) return;
    if (grupoExpandido(drillTagsAberto, grupo, true)) return;
    definirDrillGrupo(drillTagsAberto, "tags", grupo, true);
    renderTags();
  }

  function expandirCardDoc(grupo) {
    if (!grupo) return;
    if (grupoExpandido(drillDocsAberto, grupo, true)) return;
    definirDrillGrupo(drillDocsAberto, "docs", grupo, true);
    const card = document.querySelector(`#preview-rj .card-bloco[data-grupo="${CSS.escape(grupo)}"]`);
    if (card) {
      atualizarCabecaDrillDoc(card, true);
      return;
    }
    if (editandoDocumento) {
      estado.secoes = lerSecoesDoDom();
      sincronizarSecoesComGrupos();
    }
    renderDocumento();
  }

  function atualizarToolbarFormatacao() {
    const barra = document.getElementById("doc-toolbar");
    if (!barra) return;
    barra.classList.toggle("oculto", !editandoDocumento);
    if (!editandoDocumento) return;
    barra.querySelectorAll(".doc-fmt[data-fmt]").forEach((botao) => {
      const cmd = botao.dataset.fmt;
      let ativo = false;
      try {
        ativo = Boolean(document.queryCommandState(cmd));
      } catch (erro) {
        ativo = false;
      }
      botao.classList.toggle("ativo", ativo);
    });
  }

  function corpoComFoco() {
    const selecao = window.getSelection();
    const no = selecao?.anchorNode;
    if (!no) return null;
    const el = no.nodeType === 1 ? no : no.parentElement;
    return el?.closest?.(".card-bloco-corpo.editando") || null;
  }

  function aplicarFormatacao(comando) {
    if (!editandoDocumento) return;
    const corpo = corpoComFoco() || corposEditaveis()[0];
    if (!corpo) {
      status("Clique no texto do card antes de formatar.", "erro");
      return;
    }
    corpo.focus();
    try {
      document.execCommand(comando, false, null);
    } catch (erro) {
      status("Não foi possível aplicar a formatação.", "erro");
      return;
    }
    atualizarToolbarFormatacao();
  }

  function renderDocumento() {
    const preview = document.getElementById("preview-rj");
    if (!preview) return;
    sincronizarSecoesComGrupos();
    if (!(estado.grupos || []).length) {
      preview.innerHTML = `<div class="ajuda doc-sem-grupos">Crie um grupo/bloco para gerar o primeiro card deste documento.</div>`;
    } else {
      preview.innerHTML = documentoParaVisual(montarDocumentoDeSecoes(estado.secoes));
    }
    const folha = folhaDocumento(preview);
    if (folha) {
      folha.classList.add("folha-doc");
      folha.contentEditable = "false";
      folha.classList.toggle("editando", editandoDocumento);
    }
    corposEditaveis(preview).forEach((corpo) => {
      corpo.contentEditable = editandoDocumento ? "true" : "false";
      corpo.classList.toggle("editando", editandoDocumento);
      if (editandoDocumento) {
        corpo.addEventListener("keyup", atualizarToolbarFormatacao);
        corpo.addEventListener("mouseup", atualizarToolbarFormatacao);
        corpo.addEventListener("focus", atualizarToolbarFormatacao);
      }
    });
    prepararTagsDocEditaveis(preview);
    document.getElementById("doc-editar")?.classList.toggle("oculto", editandoDocumento || !(estado.grupos || []).length);
    document.getElementById("doc-salvar")?.classList.toggle("oculto", !editandoDocumento);
    document.getElementById("doc-cancelar")?.classList.toggle("oculto", !editandoDocumento);
    const nomeEl = document.getElementById("doc-nome-ativo");
    const titulo = document.getElementById("doc-titulo-ativo");
    if (nomeEl && titulo) {
      nomeEl.classList.toggle("oculto", !editandoDocumento);
      titulo.classList.toggle("oculto", editandoDocumento);
      if (editandoDocumento) nomeEl.value = estado.nome || "";
    }
    atualizarToolbarFormatacao();
    atualizarCabecalhoDocumento();
  }

  function selecionarTag(id) {
    if (!id) return;
    tagSelecionadaId = id;
    const tag = metaTag(id);
    if (tag?.grupo) expandirGrupoTags(tag.grupo);
    document.querySelectorAll(".tag-linha").forEach((el) => {
      el.classList.toggle("ativa", el.dataset.tag === id);
    });
    document.querySelectorAll(".tag-doc").forEach((el) => {
      el.classList.toggle("destaque", el.dataset.tag === id);
    });
  }

  function destacarTag(id) {
    selecionarTag(id);
    const primeira = document.querySelector(`.tag-doc[data-tag="${id}"]`);
    if (primeira) {
      const card = primeira.closest(".card-bloco");
      const grupo = card?.dataset.grupo;
      if (grupo) expandirCardDoc(grupo);
      if (!editandoDocumento) {
        primeira.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }
  }

  function criarNoTag(id) {
    const temp = document.createElement("div");
    temp.innerHTML = chipHtml(id);
    return temp.firstChild;
  }

  function rangeNoPonto(x, y) {
    if (document.caretRangeFromPoint) return document.caretRangeFromPoint(x, y);
    if (document.caretPositionFromPoint) {
      const pos = document.caretPositionFromPoint(x, y);
      if (!pos) return null;
      const range = document.createRange();
      range.setStart(pos.offsetNode, pos.offset);
      range.collapse(true);
      return range;
    }
    return null;
  }

  function inserirTagNoRange(id, range) {
    const folha = folhaDocumento();
    if (!folha || !editandoDocumento || !id) return;
    const corpos = corposEditaveis();
    let corpoAtivo = null;
    const selecao = window.getSelection();
    if (selecao?.anchorNode) {
      corpoAtivo = (selecao.anchorNode.nodeType === 1 ? selecao.anchorNode : selecao.anchorNode.parentElement)
        ?.closest?.(".card-bloco-corpo");
    }
    if (!corpoAtivo) corpoAtivo = corpos[0] || null;
    if (!corpoAtivo) return;
    corpoAtivo.focus();
    let alvo = range;
    if (!alvo) {
      if (selecao && selecao.rangeCount && corpoAtivo.contains(selecao.getRangeAt(0).commonAncestorContainer)) {
        alvo = selecao.getRangeAt(0);
      }
    }
    const no = criarNoTag(id);
    if (!alvo || !corpoAtivo.contains(alvo.commonAncestorContainer)) {
      corpoAtivo.appendChild(no);
    } else {
      alvo.deleteContents();
      alvo.insertNode(no);
    }
    if (selecao) {
      selecao.removeAllRanges();
      const cursor = document.createRange();
      cursor.setStartAfter(no);
      cursor.collapse(true);
      selecao.addRange(cursor);
    }
    selecionarTag(id);
  }

  function inserirTagNoDocumento(id) {
    if (!editandoDocumento) {
      destacarTag(id);
      status("Clique em Editar texto para arrastar ou colar tags no documento.", "erro");
      return;
    }
    inserirTagNoRange(id, null);
  }

  function inserirTagNoPonto(id, x, y) {
    if (!editandoDocumento) return;
    const folha = folhaDocumento();
    if (!folha) return;
    const alvoEl = document.elementFromPoint(x, y)?.closest?.(".card-bloco-corpo");
    if (alvoEl) alvoEl.focus();
    const range = rangeNoPonto(x, y);
    if (range && folha.contains(range.commonAncestorContainer)) {
      inserirTagNoRange(id, range);
      return;
    }
    inserirTagNoRange(id, null);
  }

  function rangeValidoParaMoverTag(range, elTag, folha) {
    if (!range || !folha || !elTag) return false;
    const ancora = range.commonAncestorContainer;
    if (!folha.contains(ancora)) return false;
    // Não soltar dentro da própria tag.
    if (elTag === ancora || elTag.contains(ancora)) return false;
    const corpo = (ancora.nodeType === 1 ? ancora : ancora.parentElement)?.closest?.(".card-bloco-corpo");
    return Boolean(corpo);
  }

  function moverTagDocNoPonto(elTag, x, y) {
    if (!editandoDocumento || !elTag?.isConnected) return false;
    const folha = folhaDocumento();
    if (!folha) return false;
    // Esconde temporariamente para o caret achar o ponto sob o cursor.
    const prevVis = elTag.style.visibility;
    elTag.style.visibility = "hidden";
    const alvoEl = document.elementFromPoint(x, y)?.closest?.(".card-bloco-corpo");
    const range = rangeNoPonto(x, y);
    elTag.style.visibility = prevVis;
    if (alvoEl) {
      // Abre o card se estiver recolhido.
      const card = alvoEl.closest(".card-bloco");
      if (card?.classList.contains("recolhido")) {
        expandirCardDoc(card.dataset.grupo || "");
      }
      alvoEl.focus();
    }
    if (!rangeValidoParaMoverTag(range, elTag, folha)) return false;
    // Move o mesmo nó (não duplica).
    elTag.remove();
    range.insertNode(elTag);
    const selecao = window.getSelection();
    if (selecao) {
      selecao.removeAllRanges();
      const cursor = document.createRange();
      cursor.setStartAfter(elTag);
      cursor.collapse(true);
      selecao.addRange(cursor);
    }
    prepararTagsDocEditaveis();
    selecionarTag(elTag.dataset.tag);
    return true;
  }

  function lerIdTagTransferida(transfer) {
    if (!transfer) return "";
    return (
      transfer.getData(MIME_TAG)
      || transfer.getData("text/plain").replace(/^\{\{\s*|\s*\}\}$/g, "").trim()
      || ""
    );
  }

  function extrairIdTagTexto(texto) {
    const match = String(texto || "").trim().match(/^\{\{\s*([a-z][a-z0-9_]*)\s*\}\}$/i);
    return match ? match[1].toLowerCase() : "";
  }

  function copiarTag(id) {
    if (!id || !metaTag(id)) return false;
    tagCopiada = id;
    selecionarTag(id);
    const payload = `{{${id}}}`;
    try {
      navigator.clipboard.writeText(payload);
    } catch (_) {
      /* clipboard pode falhar sem foco/permissão */
    }
    status(`Tag {{${id}}} copiada. Posicione o cursor no documento e use Ctrl+V.`, "ok");
    return true;
  }

  function painelConfigAtivo() {
    return document.getElementById("painel-configuracoes")?.classList.contains("ativa");
  }

  function alvoEhCampoSimples(alvo) {
    return Boolean(alvo?.closest?.("input, textarea, select, [contenteditable='true']:not(.folha-rj):not(.folha-doc):not(.card-bloco-corpo)"));
  }

  let colunasEmEdicao = [];

  function slugifyColuna(texto) {
    return slugify(texto);
  }

  function lerColunasDoPainel() {
    const host = document.getElementById("tag-colunas-lista");
    if (!host) return [];
    return [...host.querySelectorAll("[data-coluna-idx]")].map((linha) => {
      const rotulo = linha.querySelector("[data-col-rotulo]")?.value.trim() || "";
      let id = linha.querySelector("[data-col-id]")?.value.trim() || "";
      if (!id) id = slugifyColuna(rotulo);
      const tipo = linha.querySelector("[data-col-tipo]")?.value || "texto";
      return { id, rotulo, tipo };
    }).filter((col) => col.id || col.rotulo);
  }

  function preencherSelectsTabela() {
    const cols = lerColunasDoPainel();
    const agrupar = document.getElementById("tag-agrupar-por");
    const somar = document.getElementById("tag-somar");
    const agruparAtual = agrupar?.value || "";
    const somarAtual = somar?.value || "";
    if (agrupar) {
      agrupar.innerHTML = `<option value="">Sem agrupamento</option>` + cols.map(
        (c) => `<option value="${escHtml(c.id)}">${escHtml(c.rotulo || c.id)}</option>`,
      ).join("");
      agrupar.value = cols.some((c) => c.id === agruparAtual) ? agruparAtual : "";
    }
    if (somar) {
      somar.innerHTML = `<option value="">Sem total</option>` + cols.map(
        (c) => `<option value="${escHtml(c.id)}">${escHtml(c.rotulo || c.id)}</option>`,
      ).join("");
      somar.value = cols.some((c) => c.id === somarAtual) ? somarAtual : "";
    }
  }

  function renderColunasPainel() {
    const host = document.getElementById("tag-colunas-lista");
    if (!host) return;
    if (!colunasEmEdicao.length) {
      colunasEmEdicao = [{ id: "", rotulo: "", tipo: "texto" }];
    }
    host.innerHTML = colunasEmEdicao.map((col, idx) => `
      <div class="tag-coluna-linha" data-coluna-idx="${idx}">
        <input data-col-rotulo type="text" value="${escHtml(col.rotulo || "")}" placeholder="Rótulo (ex.: Perfil técnico)" />
        <input data-col-id type="text" value="${escHtml(col.id || "")}" placeholder="id (opcional)" />
        <select data-col-tipo>
          <option value="texto"${col.tipo !== "numero" ? " selected" : ""}>Texto</option>
          <option value="numero"${col.tipo === "numero" ? " selected" : ""}>Número</option>
        </select>
        <button type="button" class="acao" data-remover-coluna="${idx}" title="Remover coluna">×</button>
      </div>`).join("");
    host.querySelectorAll("[data-col-rotulo], [data-col-id], [data-col-tipo]").forEach((el) => {
      el.addEventListener("input", () => {
        colunasEmEdicao = lerColunasDoPainel();
        preencherSelectsTabela();
      });
      el.addEventListener("change", () => {
        colunasEmEdicao = lerColunasDoPainel();
        preencherSelectsTabela();
      });
    });
    host.querySelectorAll("[data-remover-coluna]").forEach((botao) => {
      botao.addEventListener("click", () => {
        const idx = Number(botao.dataset.removerColuna);
        colunasEmEdicao = lerColunasDoPainel().filter((_, i) => i !== idx);
        renderColunasPainel();
        preencherSelectsTabela();
      });
    });
    preencherSelectsTabela();
  }

  function atualizarOpcoesCampoTag() {
    const calculado = document.getElementById("tag-calculado")?.checked;
    const tipo = document.getElementById("tag-tipo")?.value || "texto_curto";
    const consulta = document.getElementById("campo-tag-consulta");
    const tabela = document.getElementById("campo-tag-tabela");
    const tipoEl = document.getElementById("tag-tipo");
    const larguraEl = document.getElementById("tag-largura");
    const calculadoEl = document.getElementById("tag-calculado");
    if (tipoEl) tipoEl.disabled = Boolean(calculado);
    if (larguraEl) {
      larguraEl.disabled = Boolean(calculado) || tipo === "tabela";
      if (tipo === "tabela") larguraEl.value = "4";
    }
    if (calculadoEl && tipo === "tabela") {
      calculadoEl.checked = false;
      calculadoEl.disabled = true;
    } else if (calculadoEl) {
      calculadoEl.disabled = false;
    }
    consulta?.classList.toggle("oculto", Boolean(calculado) || tipo !== "ia_web");
    tabela?.classList.toggle("oculto", Boolean(calculado) || tipo !== "tabela");
    document.getElementById("painel-tag")?.querySelector(".ficha-tag")?.classList.toggle("ficha-tag-ampla", tipo === "tabela");
  }

  function abrirPainelTag(tag) {
    tagEmEdicao = tag ? { ...tag } : null;
    document.getElementById("tag-titulo").textContent = tag ? "Editar tag" : "Nova tag";
    document.getElementById("tag-id").value = tag?.id || "";
    document.getElementById("tag-id").disabled = Boolean(tag);
    document.getElementById("tag-id").dataset.tocado = tag ? "1" : "";
    document.getElementById("tag-rotulo").value = tag?.rotulo || "";
    atualizarSelectGruposTag(tag?.grupo || "");
    atualizarReusoGruposTag(tag?.reuso_em || []);
    document.getElementById("tag-tipo").value = tag?.tipo || "texto_curto";
    document.getElementById("tag-largura").value = String(tag?.largura || (tag?.tipo === "texto" || tag?.tipo === "ia_web" || tag?.tipo === "tabela" ? 4 : 2));
    document.getElementById("tag-consulta-ia").value = tag?.consulta_ia || "";
    document.getElementById("tag-calculado").checked = Boolean(tag?.calculado);
    colunasEmEdicao = Array.isArray(tag?.colunas) && tag.colunas.length
      ? tag.colunas.map((c) => ({ ...c }))
      : [
        { id: "item", rotulo: "Item", tipo: "texto" },
        { id: "perfil", rotulo: "Perfil técnico", tipo: "texto" },
        { id: "experiencia", rotulo: "Experiência mínima (anos)", tipo: "numero" },
        { id: "horas", rotulo: "Total de horas", tipo: "numero" },
      ];
    renderColunasPainel();
    const agrupar = document.getElementById("tag-agrupar-por");
    const somar = document.getElementById("tag-somar");
    if (agrupar) agrupar.value = tag?.agrupar_por || (tag?.tipo === "tabela" ? "item" : "");
    if (somar) somar.value = tag?.somar || (tag?.tipo === "tabela" ? "horas" : "");
    document.getElementById("tag-erro").classList.add("oculto");
    document.getElementById("tag-erro").textContent = "";
    atualizarOpcoesCampoTag();
    document.getElementById("painel-tag").classList.remove("oculto");
    (tag ? document.getElementById("tag-rotulo") : document.getElementById("tag-id")).focus();
  }

  function fecharPainelTag() {
    document.getElementById("painel-tag").classList.add("oculto");
    tagEmEdicao = null;
  }

  function slugify(texto) {
    return String(texto || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "")
      .replace(/_+/g, "_");
  }

  async function confirmarTag() {
    const erro = document.getElementById("tag-erro");
    const idBruto = tagEmEdicao?.id || document.getElementById("tag-id").value.trim() || slugify(document.getElementById("tag-rotulo").value);
    const tipo = document.getElementById("tag-tipo").value || "texto_curto";
    const colunas = tipo === "tabela" ? lerColunasDoPainel().map((col) => ({
      id: col.id || slugifyColuna(col.rotulo),
      rotulo: col.rotulo || col.id,
      tipo: col.tipo === "numero" ? "numero" : "texto",
    })).filter((col) => col.id) : [];
    const grupoPrincipal = document.getElementById("tag-grupo").value.trim();
    const nova = {
      id: idBruto,
      rotulo: document.getElementById("tag-rotulo").value.trim(),
      grupo: grupoPrincipal,
      reuso_em: lerReusoGruposTag().filter((g) => g && g !== grupoPrincipal),
      calculado: tipo === "tabela" ? false : document.getElementById("tag-calculado").checked,
      tipo,
      largura: tipo === "tabela" ? 4 : Number(document.getElementById("tag-largura").value || 2),
      consulta_ia: tipo === "ia_web" ? document.getElementById("tag-consulta-ia").value.trim() : "",
      colunas,
      agrupar_por: tipo === "tabela" ? (document.getElementById("tag-agrupar-por")?.value || "") : "",
      somar: tipo === "tabela" ? (document.getElementById("tag-somar")?.value || "") : "",
    };
    if (!nova.id || !/^[a-z][a-z0-9_]*$/.test(nova.id)) {
      erro.className = "erro";
      erro.textContent = "Identificador inválido. Use letras minúsculas, números e _.";
      return;
    }
    if (!nova.rotulo) {
      erro.className = "erro";
      erro.textContent = "Informe o rótulo da tag.";
      return;
    }
    if (!nova.grupo || !(estado.grupos || []).includes(nova.grupo)) {
      erro.className = "erro";
      erro.textContent = "Selecione um grupo/bloco cadastrado neste documento.";
      return;
    }
    if (tipo === "tabela" && !colunas.length) {
      erro.className = "erro";
      erro.textContent = "Informe ao menos uma coluna para a tabela.";
      return;
    }
    if (tipo === "tabela") {
      const ids = new Set();
      for (const col of colunas) {
        if (!/^[a-z][a-z0-9_]*$/.test(col.id)) {
          erro.className = "erro";
          erro.textContent = `Identificador de coluna inválido: ${col.id || "(vazio)"}`;
          return;
        }
        if (ids.has(col.id)) {
          erro.className = "erro";
          erro.textContent = `Coluna duplicada: ${col.id}`;
          return;
        }
        ids.add(col.id);
      }
    }
    if (tagEmEdicao) {
      const indice = estado.tags.findIndex((item) => item.id === tagEmEdicao.id);
      if (indice < 0) return;
      estado.tags[indice] = nova;
    } else {
      if (estado.tags.some((item) => item.id === nova.id)) {
        erro.className = "erro";
        erro.textContent = "Já existe uma tag com este identificador.";
        return;
      }
      estado.tags.push(nova);
    }
    try {
      await salvarTudo(tagEmEdicao ? "Tag atualizada." : "Tag criada.");
      fecharPainelTag();
      renderTags();
      renderDocumento();
    } catch (falha) {
      erro.className = "erro";
      erro.textContent = falha.message;
    }
  }

  async function excluirTag(id) {
    if (!window.confirm(`Excluir a tag {{${id}}}? As ocorrências no documento serão removidas.`)) return;
    estado.tags = estado.tags.filter((item) => item.id !== id);
    const padrao = new RegExp(`\\{\\{\\s*${id}\\s*\\}\\}`, "g");
    estado.secoes = (estado.secoes || []).map((secao) => ({
      ...secao,
      html: String(secao.html || "").replace(padrao, ""),
    }));
    sincronizarSecoesComGrupos();
    try {
      await salvarTudo("Tag excluída.");
      renderTags();
      renderDocumento();
    } catch (falha) {
      status(falha.message, "erro");
    }
  }

  function iniciarEdicaoDocumento() {
    if (editandoDocumento) return;
    if (!(estado.grupos || []).length) {
      status("Crie um grupo/bloco para editar o documento em cards.", "erro");
      return;
    }
    documentoAntes = estado.documento;
    secoesAntes = JSON.parse(JSON.stringify(estado.secoes || []));
    nomeAntes = estado.nome;
    editandoDocumento = true;
    renderDocumento();
    status("Editando: arraste tags no texto para mover; formate com N/I/S; use Expandir/Recolher nos cards.", "ok");
    const primeiroAberto = corposEditaveis().find((el) => !el.closest(".card-bloco.recolhido")) || corposEditaveis()[0];
    primeiroAberto?.focus();
    atualizarToolbarFormatacao();
  }

  function cancelarEdicaoDocumento() {
    if (!editandoDocumento) return;
    editandoDocumento = false;
    estado.documento = documentoAntes;
    estado.secoes = secoesAntes;
    estado.nome = nomeAntes;
    renderDocumento();
    status("Edição cancelada.");
  }

  async function salvarEdicaoDocumento() {
    if (!folhaDocumento()) return;
    estado.secoes = lerSecoesDoDom();
    sincronizarSecoesComGrupos();
    const nomeEl = document.getElementById("doc-nome-ativo");
    if (nomeEl) estado.nome = nomeEl.value.trim() || estado.nome;
    try {
      await salvarTudo("Texto dos cards salvo.");
      editandoDocumento = false;
      renderDocumento();
    } catch (falha) {
      status(falha.message, "erro");
    }
  }

  async function carregarPainelIaConfig() {
    const resposta = await fetch("/api/config/ia");
    const corpo = await resposta.json();
    if (!resposta.ok) throw new Error(corpo.mensagem || "Falha ao carregar configuração de IA.");
    document.getElementById("ia-provedor").value = corpo.provedor || "google";
    document.getElementById("ia-modelo-google").value = corpo.modelo_google || "gemini-3.5-flash";
    document.getElementById("ia-google-key").value = "";
    document.getElementById("ia-openai-key").value = "";
    document.getElementById("ia-google-key").placeholder = corpo.google_configurado
      ? `Configurada: ${corpo.google_api_key_mascarada}`
      : "Cole a chave aqui";
    document.getElementById("ia-openai-key").placeholder = corpo.openai_configurado
      ? `Configurada: ${corpo.openai_api_key_mascarada}`
      : "Opcional";
    document.getElementById("ia-google-status").textContent = corpo.google_configurado
      ? "Chave Google já salva neste computador."
      : "Nenhuma chave Google salva ainda.";
    document.getElementById("ia-openai-status").textContent = corpo.openai_configurado
      ? "Chave OpenAI já salva neste computador."
      : "";
    const botao = document.getElementById("ia-config-abrir");
    if (botao) botao.textContent = corpo.pronto ? "IA pronta" : "IA / API";
    return corpo;
  }

  async function abrirPainelIaConfig() {
    const painel = document.getElementById("painel-ia-config");
    const erro = document.getElementById("ia-config-erro");
    if (erro) {
      erro.classList.add("oculto");
      erro.textContent = "";
    }
    try {
      await carregarPainelIaConfig();
      painel?.classList.remove("oculto");
    } catch (falha) {
      status(falha.message, "erro");
    }
  }

  function fecharPainelIaConfig() {
    document.getElementById("painel-ia-config")?.classList.add("oculto");
  }

  async function salvarPainelIaConfig() {
    const erro = document.getElementById("ia-config-erro");
    if (erro) {
      erro.classList.add("oculto");
      erro.textContent = "";
    }
    const googleKey = document.getElementById("ia-google-key")?.value.trim() || "";
    const openaiKey = document.getElementById("ia-openai-key")?.value.trim() || "";
    const corpoEnvio = {
      provedor: document.getElementById("ia-provedor")?.value || "google",
      modelo_google: document.getElementById("ia-modelo-google")?.value.trim() || "gemini-3.5-flash",
    };
    // Só sobrescreve a chave se o usuário colou uma nova.
    if (googleKey) corpoEnvio.google_api_key = googleKey;
    if (openaiKey) corpoEnvio.openai_api_key = openaiKey;
    try {
      const resposta = await fetch("/api/config/ia", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(corpoEnvio),
      });
      const corpo = await resposta.json();
      if (!resposta.ok) throw new Error(corpo.mensagem || "Não foi possível salvar.");
      fecharPainelIaConfig();
      status(corpo.pronto ? "Chave de IA salva. Já pode testar o campo IA no Formulário." : "Configuração salva.", "ok");
      const botao = document.getElementById("ia-config-abrir");
      if (botao) botao.textContent = corpo.pronto ? "IA pronta" : "IA / API";
    } catch (falha) {
      if (erro) {
        erro.classList.remove("oculto");
        erro.textContent = falha.message;
      }
    }
  }

  function ligarEventos() {
    document.getElementById("grupo-novo")?.addEventListener("click", () => adicionarGrupo());
    document.getElementById("tag-nova")?.addEventListener("click", () => {
      if (!(estado.grupos || []).length) {
        status("Crie ao menos um grupo/bloco neste documento antes de adicionar tags.", "erro");
        return;
      }
      abrirPainelTag(null);
    });
    document.getElementById("tag-fechar")?.addEventListener("click", fecharPainelTag);
    document.getElementById("tag-cancelar")?.addEventListener("click", fecharPainelTag);
    document.getElementById("tag-confirmar")?.addEventListener("click", () => { confirmarTag(); });
    document.getElementById("painel-tag")?.addEventListener("click", (evento) => {
      if (evento.target.id === "painel-tag") fecharPainelTag();
    });
    document.getElementById("ia-config-abrir")?.addEventListener("click", () => { abrirPainelIaConfig(); });
    document.getElementById("ia-config-fechar")?.addEventListener("click", fecharPainelIaConfig);
    document.getElementById("ia-config-cancelar")?.addEventListener("click", fecharPainelIaConfig);
    document.getElementById("ia-config-salvar")?.addEventListener("click", () => { salvarPainelIaConfig(); });
    document.getElementById("painel-ia-config")?.addEventListener("click", (evento) => {
      if (evento.target.id === "painel-ia-config") fecharPainelIaConfig();
    });

    const lista = document.getElementById("lista-tags-rj");
    const preview = document.getElementById("preview-rj");

    lista?.addEventListener("click", (evento) => {
      const drill = evento.target.closest("[data-drill-tags]");
      if (drill) {
        alternarDrillTags(drill.dataset.drillTags);
        return;
      }
      const linha = evento.target.closest(".tag-linha");
      if (!linha) return;
      const id = linha.dataset.tag;
      const acao = evento.target.closest("[data-acao]")?.dataset.acao;
      if (acao === "ordenar") return;
      if (acao === "editar") {
        abrirPainelTag(metaTag(id));
        return;
      }
      if (acao === "excluir") {
        excluirTag(id);
        return;
      }
      if (acao === "cima") {
        if (moverTagDirecao(id, -1)) persistirOrdem(`Tag {{${id}}} movida para cima no bloco.`);
        return;
      }
      if (acao === "baixo") {
        if (moverTagDirecao(id, 1)) persistirOrdem(`Tag {{${id}}} movida para baixo no bloco.`);
        return;
      }
      selecionarTag(id);
      status(`Tag {{${id}}} selecionada. Use ⋮⋮ para ordenar, ou arraste para o documento / Ctrl+C.`, "ok");
    });

    lista?.addEventListener("dragstart", (evento) => {
      const handle = evento.target.closest(".tag-handle");
      const chip = evento.target.closest(".tag-chip");
      const linha = evento.target.closest(".tag-linha");
      if (!linha) return;
      const id = linha.dataset.tag;
      selecionarTag(id);
      if (handle) {
        evento.dataTransfer.setData(MIME_ORDEM, id);
        evento.dataTransfer.setData("text/plain", id);
        evento.dataTransfer.effectAllowed = "move";
        linha.classList.add("arrastando-ordem");
        return;
      }
      if (!chip) return;
      evento.dataTransfer.setData(MIME_TAG, id);
      evento.dataTransfer.setData("text/plain", `{{${id}}}`);
      evento.dataTransfer.effectAllowed = "copy";
      chip.classList.add("arrastando");
    });

    lista?.addEventListener("dragend", (evento) => {
      evento.target.closest(".tag-chip")?.classList.remove("arrastando");
      lista.querySelectorAll(".tag-linha").forEach((el) => {
        el.classList.remove("arrastando-ordem", "soltar-antes", "soltar-depois");
      });
      preview?.classList.remove("soltar-tag");
    });

    lista?.addEventListener("dragover", (evento) => {
      const tipos = [...(evento.dataTransfer?.types || [])].map((item) => String(item).toLowerCase());
      const ordenando = tipos.includes(MIME_ORDEM) || Boolean(lista.querySelector(".arrastando-ordem"));
      if (!ordenando) return;
      const alvo = evento.target.closest(".tag-linha");
      if (!alvo) return;
      const idMovida = tagSelecionadaId;
      if (!idMovida || alvo.dataset.tag === idMovida) return;
      const movida = metaTag(idMovida);
      if (!movida || movida.grupo !== alvo.dataset.grupo) return;
      evento.preventDefault();
      evento.dataTransfer.dropEffect = "move";
      const ret = alvo.getBoundingClientRect();
      const depois = evento.clientY > ret.top + ret.height / 2;
      lista.querySelectorAll(".tag-linha").forEach((el) => el.classList.remove("soltar-antes", "soltar-depois"));
      alvo.classList.add(depois ? "soltar-depois" : "soltar-antes");
    });

    lista?.addEventListener("drop", (evento) => {
      const ordenando = Boolean(lista.querySelector(".arrastando-ordem"))
        || [...(evento.dataTransfer?.types || [])].map((item) => String(item).toLowerCase()).includes(MIME_ORDEM);
      if (!ordenando) return;
      const alvo = evento.target.closest(".tag-linha");
      if (!alvo) return;
      evento.preventDefault();
      evento.stopPropagation();
      const idMovida = evento.dataTransfer.getData(MIME_ORDEM)
        || evento.dataTransfer.getData("text/plain")
        || tagSelecionadaId;
      const idAlvo = alvo.dataset.tag;
      const ret = alvo.getBoundingClientRect();
      const depois = evento.clientY > ret.top + ret.height / 2;
      lista.querySelectorAll(".tag-linha").forEach((el) => el.classList.remove("soltar-antes", "soltar-depois", "arrastando-ordem"));
      if (!idMovida || !idAlvo) return;
      if (moverTagNoGrupo(idMovida, idAlvo, depois)) {
        persistirOrdem(`Ordem atualizada no bloco ${alvo.dataset.grupo}.`);
      }
    });

    preview?.addEventListener("dragstart", (evento) => {
      if (!editandoDocumento) return;
      const tag = evento.target.closest(".tag-doc");
      if (!tag || !preview.contains(tag)) return;
      const id = tag.dataset.tag;
      if (!id || !metaTag(id)) return;
      tagDocEmMovimento = tag;
      tag.classList.add("arrastando");
      selecionarTag(id);
      try {
        evento.dataTransfer.setData(MIME_TAG, id);
        evento.dataTransfer.setData(MIME_TAG_MOVE, "1");
        evento.dataTransfer.setData("text/plain", `{{${id}}}`);
        evento.dataTransfer.effectAllowed = "copyMove";
      } catch (erro) {
        /* alguns navegadores restringem tipos */
      }
    });

    preview?.addEventListener("dragend", () => {
      tagDocEmMovimento?.classList.remove("arrastando");
      tagDocEmMovimento = null;
      preview.classList.remove("soltar-tag");
    });

    preview?.addEventListener("dragover", (evento) => {
      if (!editandoDocumento) return;
      const tipos = [...(evento.dataTransfer?.types || [])].map((t) => String(t).toLowerCase());
      if (!tipos.includes(MIME_TAG) && !tipos.includes("text/plain") && !tipos.includes(MIME_TAG_MOVE)) return;
      evento.preventDefault();
      const movendo = Boolean(tagDocEmMovimento) || tipos.includes(MIME_TAG_MOVE);
      evento.dataTransfer.dropEffect = movendo ? "move" : "copy";
      preview.classList.add("soltar-tag");
    });

    preview?.addEventListener("dragleave", (evento) => {
      if (!preview.contains(evento.relatedTarget)) preview.classList.remove("soltar-tag");
    });

    preview?.addEventListener("drop", (evento) => {
      preview.classList.remove("soltar-tag");
      if (!editandoDocumento) {
        status("Clique em Editar texto antes de soltar a tag no documento.", "erro");
        return;
      }
      evento.preventDefault();
      const tipos = [...(evento.dataTransfer?.types || [])].map((t) => String(t).toLowerCase());
      const movendo = Boolean(tagDocEmMovimento?.isConnected) || tipos.includes(MIME_TAG_MOVE);
      if (movendo && tagDocEmMovimento?.isConnected) {
        const ok = moverTagDocNoPonto(tagDocEmMovimento, evento.clientX, evento.clientY);
        const id = tagDocEmMovimento.dataset.tag;
        tagDocEmMovimento.classList.remove("arrastando");
        tagDocEmMovimento = null;
        status(ok ? `Tag {{${id}}} reposicionada.` : "Solte a tag em um ponto válido do texto.", ok ? "ok" : "erro");
        return;
      }
      const id = lerIdTagTransferida(evento.dataTransfer);
      if (!id || !metaTag(id)) return;
      inserirTagNoPonto(id, evento.clientX, evento.clientY);
      status(`Tag {{${id}}} inserida no documento.`, "ok");
    });

    preview?.addEventListener("click", (evento) => {
      const cabeca = evento.target.closest("[data-drill-doc]");
      if (cabeca) {
        alternarDrillDoc(cabeca.dataset.drillDoc);
        return;
      }
      const tag = evento.target.closest(".tag-doc");
      if (!tag) return;
      selecionarTag(tag.dataset.tag);
      status(
        editandoDocumento
          ? `Tag {{${tag.dataset.tag}}} selecionada. Arraste para mover no texto.`
          : `Tag {{${tag.dataset.tag}}} selecionada. Use Ctrl+C e Ctrl+V para repetir.`,
        "ok",
      );
    });
    preview?.addEventListener("keydown", (evento) => {
      if (evento.key !== "Enter" && evento.key !== " ") return;
      const cabeca = evento.target.closest("[data-drill-doc]");
      if (!cabeca) return;
      evento.preventDefault();
      alternarDrillDoc(cabeca.dataset.drillDoc);
    });

    document.getElementById("tags-drill-down")?.addEventListener("click", () => {
      const grupos = [...(estado.grupos || [])];
      estado.tags.forEach((tag) => {
        if (tag.grupo && !grupos.includes(tag.grupo)) grupos.push(tag.grupo);
      });
      definirDrillTodos(drillTagsAberto, "tags", grupos, true);
      renderTags();
      status("Grupos de tags expandidos.", "ok");
    });
    document.getElementById("tags-drill-up")?.addEventListener("click", () => {
      const grupos = [...(estado.grupos || [])];
      estado.tags.forEach((tag) => {
        if (tag.grupo && !grupos.includes(tag.grupo)) grupos.push(tag.grupo);
      });
      definirDrillTodos(drillTagsAberto, "tags", grupos, false);
      renderTags();
      status("Grupos de tags recolhidos.");
    });
    document.getElementById("doc-drill-down")?.addEventListener("click", () => {
      definirDrillTodos(drillDocsAberto, "docs", estado.grupos || [], true);
      // Em edição, só altera classes — não remonta o HTML (preserva o texto digitado).
      if (editandoDocumento) aplicarDrillDocsNoDom();
      else renderDocumento();
      status("Cards do documento expandidos.", "ok");
    });
    document.getElementById("doc-drill-up")?.addEventListener("click", () => {
      definirDrillTodos(drillDocsAberto, "docs", estado.grupos || [], false);
      if (editandoDocumento) aplicarDrillDocsNoDom();
      else renderDocumento();
      status("Cards do documento recolhidos.");
    });

    document.addEventListener("keydown", (evento) => {
      if (!painelConfigAtivo()) return;
      if (alvoEhCampoSimples(evento.target) && !evento.target.closest?.(".folha-rj, .folha-doc, .card-bloco-corpo")) return;
      const tecla = evento.key.toLowerCase();
      const comAtalho = evento.ctrlKey || evento.metaKey;
      if (!comAtalho) return;

      if (tecla === "c") {
        const selecao = window.getSelection();
        const no = selecao?.anchorNode;
        const tagDoc = (no?.nodeType === 1 ? no : no?.parentElement)?.closest?.(".tag-doc");
        const id = tagDoc?.dataset.tag || tagSelecionadaId;
        if (!id) return;
        if (selecao && !selecao.isCollapsed && !tagDoc) {
          const texto = selecao.toString().trim();
          if (texto && !/^\{\{[a-z0-9_]+\}\}$/i.test(texto)) return;
        }
        if (copiarTag(id)) evento.preventDefault();
        return;
      }

      if (tecla === "v") {
        if (!editandoDocumento) return;
        const noFoco = evento.target.closest?.(".card-bloco-corpo, .folha-rj, .folha-doc")
          || document.activeElement?.closest?.(".card-bloco-corpo, .folha-rj, .folha-doc");
        if (!noFoco) {
          corposEditaveis()[0]?.focus();
        }
        const colarId = (id) => {
          if (!id || !metaTag(id)) return false;
          evento.preventDefault();
          inserirTagNoDocumento(id);
          status(`Tag {{${id}}} colada no documento.`, "ok");
          return true;
        };
        if (tagCopiada && colarId(tagCopiada)) return;
        if (navigator.clipboard?.readText) {
          evento.preventDefault();
          navigator.clipboard.readText().then((texto) => {
            const id = extrairIdTagTexto(texto);
            if (id && metaTag(id)) {
              inserirTagNoDocumento(id);
              status(`Tag {{${id}}} colada no documento.`, "ok");
              return;
            }
            if (texto) document.execCommand("insertText", false, texto);
          }).catch(() => {});
        }
      }
    });

    document.getElementById("doc-editar")?.addEventListener("click", iniciarEdicaoDocumento);
    document.getElementById("doc-cancelar")?.addEventListener("click", cancelarEdicaoDocumento);
    document.getElementById("doc-salvar")?.addEventListener("click", () => { salvarEdicaoDocumento(); });
    document.getElementById("doc-novo")?.addEventListener("click", () => { criarDocumentoNovo(); });
    document.getElementById("doc-excluir")?.addEventListener("click", () => { excluirDocumentoAtivo(); });
    document.getElementById("doc-excluir-selecionados")?.addEventListener("click", () => {
      const ids = [...document.querySelectorAll("#lista-documentos input[data-doc-check]:checked")]
        .map((input) => input.dataset.docCheck)
        .filter(Boolean);
      excluirDocumentos(ids);
    });
    document.getElementById("doc-upload-btn")?.addEventListener("click", () => {
      document.getElementById("doc-upload")?.click();
    });
    document.getElementById("doc-upload")?.addEventListener("change", (evento) => {
      const arquivo = evento.target.files?.[0];
      evento.target.value = "";
      enviarDocumentoArquivo(arquivo);
    });
    document.getElementById("doc-toolbar")?.addEventListener("mousedown", (evento) => {
      // Mantém a seleção do texto no card ao clicar na barra.
      if (evento.target.closest(".doc-fmt")) evento.preventDefault();
    });
    document.getElementById("doc-toolbar")?.addEventListener("click", (evento) => {
      const botao = evento.target.closest(".doc-fmt[data-fmt]");
      if (!botao) return;
      aplicarFormatacao(botao.dataset.fmt);
    });
    document.addEventListener("selectionchange", () => {
      if (!editandoDocumento) return;
      if (!corpoComFoco()) return;
      atualizarToolbarFormatacao();
    });

    document.getElementById("tag-rotulo")?.addEventListener("input", () => {
      if (tagEmEdicao) return;
      const id = document.getElementById("tag-id");
      if (!id.dataset.tocado) id.value = slugify(document.getElementById("tag-rotulo").value);
    });
    document.getElementById("tag-id")?.addEventListener("input", () => {
      document.getElementById("tag-id").dataset.tocado = "1";
    });
    document.getElementById("tag-tipo")?.addEventListener("change", atualizarOpcoesCampoTag);
    document.getElementById("tag-calculado")?.addEventListener("change", atualizarOpcoesCampoTag);
    document.getElementById("tag-grupo")?.addEventListener("change", () => atualizarReusoGruposTag());
    document.getElementById("tag-coluna-add")?.addEventListener("click", () => {
      colunasEmEdicao = lerColunasDoPainel();
      colunasEmEdicao.push({ id: "", rotulo: "", tipo: "texto" });
      renderColunasPainel();
    });
  }

  async function iniciar() {
    ligarEventos();
    try {
      await carregar();
      renderListaDocumentos();
      atualizarCabecalhoDocumento();
      renderGrupos();
      renderTags();
      renderDocumento();
      avisarFormulario();
      try {
        await carregarPainelIaConfig();
      } catch (erroIa) {
        /* IA opcional na carga inicial */
      }
    } catch (falha) {
      status(falha.message, "erro");
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", iniciar);
  } else {
    iniciar();
  }
})();
