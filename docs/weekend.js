// "This weekend" page: reads data/weekend.json (built nightly) and works out the weekend in the browser.
(() => {
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const DAY = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const TROOP = ["Scouts BSA", "Venturing", "Sea Scouts", "Exploring"];
  const state = { wk: 0, mi: 50, online: true };
  let data = null;

  const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const parse = (s) => new Date(+s.slice(0, 4), +s.slice(5, 7) - 1, +s.slice(8, 10));

  function weekend(offset) {
    const t = new Date(); t.setHours(0, 0, 0, 0);
    const dow = t.getDay(); // Sat/Sun = this weekend is under way
    const fri = new Date(t);
    fri.setDate(t.getDate() + (dow === 6 ? -1 : dow === 0 ? -2 : 5 - dow) + 7 * offset);
    const sun = new Date(fri); sun.setDate(fri.getDate() + 2);
    return { fri, sun, lo: iso(fri), hi: iso(sun) };
  }

  function when(e) {
    const d = parse(e.start);
    let s = `${DAY[d.getDay()]} ${MON[d.getMonth()]} ${d.getDate()}`;
    const t = e.time || (e.start.slice(11, 16) !== "00:00" ? fmtTime(e.start.slice(11, 16)) : "");
    if (t) s += `, ${t}`;
    if (e.end && e.end.slice(0, 10) > e.start.slice(0, 10)) {
      const z = parse(e.end);
      s += ` – ${DAY[z.getDay()]} ${MON[z.getMonth()]} ${z.getDate()}`;
    }
    return s;
  }
  function fmtTime(hm) {
    let [h, m] = hm.split(":").map(Number);
    const ap = h >= 12 ? "PM" : "AM"; h = h % 12 || 12;
    return `${h}:${String(m).padStart(2, "0")} ${ap}`;
  }

  function where(e) {
    if (e.online) return "Online";
    const mi = e.miles == null ? "" : e.approx ? ` · ~${e.miles} mi (council area)` : ` · ${e.miles} mi`;
    return esc(e.location || e.council) + mi;
  }

  function card(e) {
    const tags = [...(e.badges || []).map((b) => `<span class="tag b">${esc(b)}</span>`),
      ...(e.fees || []).filter((f) => f === "Free").map(() => `<span class="tag">Free</span>`),
      e.online ? `<span class="tag online">Online</span>` : ""].join("");
    return `<article class="wk-card">
      <div class="wk-when">${esc(when(e))}</div>
      <h4><a href="${esc(e.url)}" target="_blank" rel="noopener">${esc(e.title)}</a>${e.session ? ` <span class="muted">${esc(e.session)}</span>` : ""}</h4>
      <div class="meta">${where(e)}${e.council && !e.online && e.kind === "scout" ? ` · ${esc(e.council)}` : ""}</div>
      ${tags ? `<div class="tags">${tags}</div>` : ""}
    </article>`;
  }

  const empty = (msg) => `<div class="wk-empty">${msg}</div>`;

  function inRange(e, w) {
    return e.start.slice(0, 10) <= w.hi && (e.end || e.start).slice(0, 10) >= w.lo;
  }
  function near(e) {
    if (e.online) return state.online;
    return e.miles == null || e.miles <= state.mi;
  }

  function render() {
    const w = weekend(state.wk);
    $("dates").textContent = `${DAY[5]} ${MON[w.fri.getMonth()]} ${w.fri.getDate()} – ${DAY[0]} ${MON[w.sun.getMonth()]} ${w.sun.getDate()}`;
    const scout = data.scout.filter((e) => inRange(e, w) && near(e));
    const has = (e, list) => e.programs.some((p) => list.includes(p));
    const pack = scout.filter((e) => has(e, ["Cub Scouts"]));
    const troop = scout.filter((e) => has(e, TROOP));
    const adults = scout.filter((e) => e.programs.length && e.programs.every((p) => p === "Adults / Leaders"));
    const open = scout.filter((e) => !e.programs.length);
    $("pack").innerHTML = pack.map(card).join("") || empty("Nothing for Cub Scouts this weekend within range.");
    $("troop").innerHTML = troop.map(card).join("") || empty("Nothing for the troop this weekend within range.");
    $("open").innerHTML = open.map(card).join("") || empty("None.");
    $("adults").innerHTML = adults.map(card).join("") || empty("None.");

    // public programs: ranger programs collapse into one line per program
    const pub = data.public.filter((e) => inRange(e, w) && (e.kind !== "ranger" || e.miles == null || e.miles <= Math.max(state.mi, 300)));
    const others = pub.filter((e) => e.kind !== "ranger" && near(e));
    const rangers = {};
    pub.filter((e) => e.kind === "ranger").forEach((e) => {
      const k = e.council;
      const g = (rangers[k] ||= { park: k, miles: e.miles, url: e.url, items: {} });
      if (e.miles != null && (g.miles == null || e.miles < g.miles)) g.miles = e.miles;
      const d = parse(e.start);
      (rangers[k].items[e.title] ||= { title: e.title, url: e.url, time: e.time, days: [] }).days.push(DAY[d.getDay()]);
    });
    let html = others.map(card).join("");
    const parks = Object.values(rangers).sort((a, b) => (a.miles ?? 999) - (b.miles ?? 999));
    if (parks.length) {
      html += `<h3 class="wk-sub">Ranger programs <span class="muted">free with park entry; farther parks make a weekend trip</span></h3>`;
      html += parks.map((p) => `<article class="wk-card">
        <h4>${esc(p.park)}${p.miles != null ? ` <span class="muted">· ${p.miles} mi</span>` : ""}</h4>
        <ul class="wk-list">${Object.values(p.items).map((i) =>
          `<li><a href="${esc(i.url)}" target="_blank" rel="noopener">${esc(i.title)}</a> <span class="muted">${[...new Set(i.days)].join(", ")}${i.time ? ` · ${esc(i.time)}` : ""}</span></li>`).join("")}</ul>
      </article>`).join("");
    }
    $("public").innerHTML = html || empty("No public programs listed for this weekend.");

    const al = (data.alerts || []).filter((a) => ["Park Closure", "Danger"].includes(a.category));
    $("alertsec").hidden = !al.length;
    $("alerts").innerHTML = al.map((a) => `<article class="wk-card wk-alert">
      <div class="wk-when">${esc(a.category)} · ${esc((data.parks || {})[a.parkCode] || a.parkCode.toUpperCase())}</div>
      <h4><a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.title)}</a></h4>
      <div class="desc">${esc(a.description)}</div></article>`).join("");
  }

  document.querySelectorAll("[data-wk]").forEach((b) => b.addEventListener("click", () => {
    state.wk = +b.dataset.wk;
    document.querySelectorAll("[data-wk]").forEach((x) => x.classList.toggle("on", x === b));
    render();
  }));
  document.querySelectorAll("[data-mi]").forEach((b) => b.addEventListener("click", () => {
    state.mi = +b.dataset.mi;
    document.querySelectorAll("[data-mi]").forEach((x) => x.classList.toggle("on", x === b));
    render();
  }));
  $("online").addEventListener("change", (e) => { state.online = e.target.checked; render(); });

  fetch("data/weekend.json", { cache: "no-cache" }).then((r) => r.json()).then((j) => {
    data = j;
    const u = new Date(j.updated);
    $("updated").textContent = `Updated ${MON[u.getMonth()]} ${u.getDate()}`;
    render();
  }).catch(() => { $("updated").textContent = "Could not load this weekend's list."; });
})();
