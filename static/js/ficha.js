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
