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
