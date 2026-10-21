/* Booking form: live bed availability for the chosen dates, one-click room choice,
   running cost estimate, and a patient filter. Re-checks every few seconds so a colleague
   taking the last bed shows up straight away (the server also re-checks on save). */
(function () {
  var panel = document.getElementById("panel"); if (!panel) return;
  var url = panel.getAttribute("data-url");
  var room = document.getElementById("id_room"), cin = document.getElementById("id_check_in"), cout = document.getElementById("id_check_out");
  var patient = document.getElementById("id_patient"), pSearch = document.getElementById("pSearch");
  var tiles = document.getElementById("tiles"), sum = document.getElementById("sum"), state = document.getElementById("state");
  var live = document.getElementById("live"), stamp = document.getElementById("liveTime"), btn = document.getElementById("submitBtn");
  var rangeText = document.getElementById("rangeText");
  var data = null, timer = null, t0 = null;

  var todayStr = new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);
  cin.min = todayStr; cout.min = todayStr;
  function money(n) { return "\u20b9" + Math.round(n).toLocaleString("en-IN"); }
  function fmt(s) { var d = new Date(s + "T00:00:00"); return isNaN(d) ? s : d.toLocaleDateString("en-GB", { day: "2-digit", month: "short" }); }

  var nowBox = document.getElementById("nowBox");
  function nowToggle() { if (nowBox) nowBox.style.display = cin.value === todayStr ? "" : "none"; }
  function selected() { return data && data.rooms.filter(function (r) { return String(r.id) === room.value; })[0]; }

  function render() {
    nowToggle();
    if (!data) return;
    rangeText.innerHTML = "<b>" + fmt(cin.value) + "</b> &rarr; <b>" + fmt(cout.value) + "</b> &middot; " + data.nights + " night" + (data.nights === 1 ? "" : "s");
    tiles.innerHTML = "";
    data.rooms.forEach(function (r) {
      var b = document.createElement("button"); b.type = "button";
      b.className = "rtile" + (r.free < 1 ? " full" : "") + (String(r.id) === room.value ? " sel" : "");
      var cls = r.free < 1 ? "free" : (r.free <= 1 && r.beds > 1 ? "free low" : "free");
      b.innerHTML = '<div class="mid"><div class="n">Room ' + r.number + '</div><div class="t">' + r.type + (r.floor ? " &middot; " + r.floor : "") + "</div></div>" +
        '<div class="end"><span class="' + cls + '">' + (r.free < 1 ? "Full" : r.free + " of " + r.beds + " free") + "</span><div>" + money(r.charge) + " / day</div></div>";
      b.addEventListener("click", function () { if (r.free < 1) return; room.value = String(r.id); render(); });
      tiles.appendChild(b);
    });
    if (!data.rooms.length) tiles.innerHTML = '<p class="muted">No active rooms. Add a room first.</p>';

    var r = selected(), ok = false;
    state.className = "rstate";
    if (!data.valid) {
      state.classList.add("bad"); state.textContent = "Admission must be today or later, and discharge must be after admission.";
      sum.hidden = true;
    } else if (!r) {
      state.textContent = "Pick a room to see its availability."; sum.hidden = true;
    } else {
      sum.hidden = false;
      document.getElementById("sRoom").textContent = "Room " + r.number + " (" + r.type + ")";
      document.getElementById("sNights").textContent = data.nights + " night" + (data.nights === 1 ? "" : "s");
      document.getElementById("sRate").textContent = money(r.charge) + " / day";
      document.getElementById("sTotal").textContent = money(r.charge * data.nights);
      if (r.free < 1) { state.classList.add("bad"); state.textContent = "Room " + r.number + " has no free bed for these dates. Choose another room."; }
      else { ok = true; state.classList.add("ok"); state.textContent = r.free + " of " + r.beds + " bed" + (r.beds === 1 ? "" : "s") + " free for these dates."; }
    }
    btn.disabled = !ok; btn.style.opacity = ok ? "" : ".55"; btn.style.cursor = ok ? "" : "not-allowed";
  }

  function load() {
    fetch(url + "?check_in=" + encodeURIComponent(cin.value) + "&check_out=" + encodeURIComponent(cout.value), { credentials: "same-origin" })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (j) {
        data = j; render();
        live.classList.remove("off"); stamp.textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
      })
      .catch(function () { live.classList.add("off"); stamp.textContent = "reconnecting"; });
  }
  function soon() { clearTimeout(t0); t0 = setTimeout(load, 250); }
  function start() { stop(); load(); timer = setInterval(load, 5000); }
  function stop() { if (timer) clearInterval(timer); timer = null; }

  [cin, cout].forEach(function (el) { el.addEventListener("change", soon); el.addEventListener("input", soon); });
  cin.addEventListener("change", nowToggle);
  cin.addEventListener("change", function () {  // keep discharge after admission
    if (cin.value && (!cout.value || cout.value <= cin.value)) {
      var d = new Date(cin.value + "T00:00:00"); d.setDate(d.getDate() + 1);
      cout.value = new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
    }
  });
  room.addEventListener("change", render);
  document.addEventListener("visibilitychange", function () { if (document.hidden) stop(); else start(); });

  // patient filter: rebuild the list from a stored copy so it works in every browser
  var all = [].slice.call(patient.options).map(function (o) { return { v: o.value, t: o.text }; });
  pSearch.addEventListener("input", function () {
    var q = pSearch.value.trim().toLowerCase(), cur = patient.value;
    patient.innerHTML = "";
    all.filter(function (o) { return !o.v || o.t.toLowerCase().indexOf(q) !== -1 || o.v === cur; }).forEach(function (o) {
      var op = document.createElement("option"); op.value = o.v; op.textContent = o.t; if (o.v === cur) op.selected = true; patient.appendChild(op);
    });
  });
  start();
})();
