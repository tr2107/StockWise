// app.js - small helpers used on every page. No libraries needed.
(function () {
  // 1. Mobile menu: show / hide the sidebar.
  var menuBtn = document.getElementById("menu-btn");
  var sidebar = document.getElementById("sidebar");
  if (menuBtn && sidebar) {
    menuBtn.addEventListener("click", function () { sidebar.classList.toggle("open"); });
    document.querySelector(".main").addEventListener("click", function () { sidebar.classList.remove("open"); });
  }

  // 2. Dismiss flash messages.
  document.querySelectorAll(".flash-close").forEach(function (btn) {
    btn.addEventListener("click", function () { btn.closest(".flash").remove(); });
  });

  // 3. Ask "Are you sure?" before forms marked with data-confirm (used for Delete).
  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (!window.confirm(form.getAttribute("data-confirm"))) { event.preventDefault(); }
    });
  });

  // 4. Stock in / out form: show how many units are available for the chosen product.
  var movement = document.getElementById("movement-form");
  if (movement) {
    var select = document.getElementById("product_id");
    var qty = document.getElementById("quantity");
    var hint = document.getElementById("stock-hint");
    var isOut = movement.getAttribute("data-kind") === "OUT";

    function update() {
      var option = select.options[select.selectedIndex];
      var available = option && option.dataset.qty;
      if (available === undefined || available === "") { hint.hidden = true; if (isOut) qty.removeAttribute("max"); return; }
      hint.hidden = false;
      hint.textContent = "Currently in stock: " + available;
      if (isOut) { qty.setAttribute("max", available); }
    }
    select.addEventListener("change", update);
    update();
  }
})();
