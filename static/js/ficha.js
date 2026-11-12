// Mostra a soma dos atributos (orientação de 21 pontos) e os máximos iniciais. Não bloqueia o envio.
(function () {
  var campos = document.querySelectorAll("[data-atributo]");
  var resumo = document.getElementById("pontos-resumo");
  var maximos = document.getElementById("maximos-resumo");
  if (!campos.length || !resumo) return;
  var meta = parseInt(resumo.getAttribute("data-meta"), 10) || 21;

  function valor(nome) {
    var el = document.querySelector('[data-atributo="' + nome + '"]');
    return el ? parseInt(el.value, 10) || 0 : 0;
  }

  function atualizar() {
    var total = 0;
    campos.forEach(function (c) { total += parseInt(c.value, 10) || 0; });
    var texto = "Pontos usados: " + total + " de " + meta;
    if (total < meta) texto += " (faltam " + (meta - total) + ")";
    else if (total > meta) texto += " (passou " + (total - meta) + ")";
    else texto += " (total sugerido pelo livro)";
    resumo.textContent = texto;
    if (maximos) {
      maximos.textContent = "Máximos iniciais: Sangue Frio " + valor("sangue_frio") * 3 +
        " (SF × 3) e Anticorpos " + valor("resistencia") * 10 + " (RES × 10).";
    }
  }

  campos.forEach(function (c) { c.addEventListener("input", atualizar); });
  atualizar();
})();

// Prévia da foto escolhida (só no navegador; o servidor valida e reduz a imagem ao salvar).
(function () {
  var entrada = document.querySelector("input[type=file][data-previa]");
  if (!entrada) return;
  var imagem = document.getElementById(entrada.getAttribute("data-previa"));
  var vazio = document.getElementById("foto-vazia");
  if (!imagem) return;
  entrada.addEventListener("change", function () {
    var arquivo = entrada.files && entrada.files[0];
    if (!arquivo || arquivo.type.indexOf("image/") !== 0) return;
    var leitor = new FileReader();
    leitor.onload = function (e) {
      imagem.src = e.target.result;
      imagem.hidden = false;
      if (vazio) vazio.hidden = true;
    };
    leitor.readAsDataURL(arquivo);
  });
})();

// Contador de slots da mochila (comum = 10, militar = 15). O servidor também valida.
(function () {
  var seletor = document.getElementById("id_tipo_mochila");
  var resumo = document.getElementById("mochila-resumo");
  if (!seletor || !resumo) return;
  var capacidades = {};
  (seletor.getAttribute("data-capacidades") || "").split(",").forEach(function (par) {
    var p = par.split(":");
    if (p.length === 2) capacidades[p[0]] = parseInt(p[1], 10);
  });

  function atualizar() {
    var capacidade = capacidades[seletor.value] || 10;
    var ocupados = 0;
    document.querySelectorAll("[data-mochila-item]").forEach(function (campo) {
      var linha = campo.closest("li");
      var remover = linha && linha.querySelector("input[type=checkbox]");
      if (campo.value.trim() && !(remover && remover.checked)) ocupados += 1;
    });
    var texto = "Mochila: " + ocupados + " de " + capacidade + " slots usados";
    if (ocupados > capacidade) texto += " (acima do limite: remova itens ou escolha a mochila militar)";
    resumo.textContent = texto;
  }

  seletor.addEventListener("change", atualizar);
  document.querySelectorAll("[data-mochila-item], .mochila-form input[type=checkbox]").forEach(function (el) {
    el.addEventListener("input", atualizar);
    el.addEventListener("change", atualizar);
  });
  atualizar();
})();
