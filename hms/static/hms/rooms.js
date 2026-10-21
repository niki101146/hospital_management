/* Keeps the room pages live: re-fetches the page fragment every few seconds and swaps it in
   only when something actually changed (so colleagues' bookings appear without a reload). */
(function () {
  var box = document.querySelector("[data-live]");
  if (!box) return;
  var url = box.getAttribute("data-url"), last = null, timer = null, filter = "";
  var live = document.getElementById("live"), stamp = document.getElementById("liveTime");
  var search = document.getElementById("rowSearch"), form = document.getElementById("liveForm");

  function endpoint() { return form ? url + "&" + new URLSearchParams(new FormData(form)).toString() : url; }  // pages with date filters
  function clean(html) { return html.replace(/name="csrfmiddlewaretoken" value="[^"]*"/g, ""); }  // token changes on every render

  function apply() {
    box.querySelectorAll(".chip[data-type]").forEach(function (c) { c.classList.toggle("on", c.getAttribute("data-type") === filter); });
    box.querySelectorAll(".rcard").forEach(function (c) { c.style.display = !filter || c.getAttribute("data-type") === filter ? "" : "none"; });
    var q = search ? search.value.trim().toLowerCase() : "";
    box.querySelectorAll(".rb-card tr").forEach(function (r) {
      if (r.querySelector("th")) return;  // header rows
      r.style.display = !q || r.textContent.toLowerCase().indexOf(q) !== -1 ? "" : "none";
    });
  }

  function status(ok) {
    if (!live) return;
    live.classList.toggle("off", !ok);
    var t = new Date();
    stamp.textContent = ok ? t.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "reconnecting";
  }

  function tick() {
    fetch(endpoint(), { credentials: "same-origin", headers: { "X-Requested-With": "fetch" } })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.text(); })
      .then(function (html) {
        var changed = last !== null && clean(html) !== last;
        if (last === null || changed) {
          box.innerHTML = html; apply();
          if (changed) { box.classList.remove("updated"); void box.offsetWidth; box.classList.add("updated"); }
        }
        last = clean(html); status(true);
      })
      .catch(function () { status(false); });
  }
  function start() { stop(); tick(); timer = setInterval(tick, 5000); }
  function stop() { if (timer) clearInterval(timer); timer = null; }

  box.addEventListener("click", function (e) {
    var chip = e.target.closest(".chip[data-type]");
    if (chip) { filter = chip.getAttribute("data-type"); apply(); }
  });
  if (search) search.addEventListener("input", apply);
  if (form) {
    form.addEventListener("submit", function (e) { e.preventDefault(); last = null; tick(); });
    form.addEventListener("change", function () { last = null; tick(); });
  }
  document.addEventListener("visibilitychange", function () { if (document.hidden) stop(); else start(); });
  apply(); start();
})();
