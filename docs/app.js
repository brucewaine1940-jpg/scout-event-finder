/* Scout Event Finder - all filtering happens in the browser. */
(() => {
  "use strict";
  const $ = (s) => document.querySelector(s);
  const el = (tag, attrs = {}, ...kids) => {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "class") n.className = v; else if (k === "text") n.textContent = v;
      else if (k.startsWith("on")) n.addEventListener(k.slice(2), v); else n.setAttribute(k, v);
    }
    kids.flat().forEach((k) => k != null && n.append(k));
    return n;
  };
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch { /* private mode */ } },
  };

  const PAGE = 40;
  const PROGRAMS = ["Cub Scouts", "Scouts BSA", "Venturing", "Sea Scouts", "Exploring", "Adults / Leaders"];
  const DAY = 86400000;
  let PROV = null;
  let ALL = [], ZIPS = null, origin = null, shown = PAGE, FIRST_RUN = "";

  const S = {  // filter state
    q: "", zip: "", radius: "150", state: "", from: "", to: "", preset: "all",
    programs: [], badges: [], anyBadge: false, topics: [], trainings: [], council: "",
    hideLong: true, hideFund: true, hideAdmin: true, includeOnline: true, newOnly: false, sort: "date", view: "events",
  };

  /* ---------- helpers ---------- */
  const today0 = () => { const d = new Date(); d.setHours(0, 0, 0, 0); return d; };
  const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const ts = (s) => (s ? Date.parse(s.replace("Z", ":00Z")) : NaN);
  const local = (s) => (s ? new Date(s) : null); // "2026-10-29T18:00" in the event's own time zone
  const fmtTime = (d) => d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  const fmtDay = (d) => d.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" });
  function when(e) {
    const a = local(e.start), b = local(e.end);
    if (!a) return "";
    const allDay = a.getHours() === 0 && a.getMinutes() === 0;
    if (!b || iso(a) === iso(b)) return `${fmtDay(a)}${allDay ? "" : ", " + fmtTime(a)}${b && !allDay ? "–" + fmtTime(b) : ""} ${allDay ? "" : e.tz}`.trim();
    return `${fmtDay(a)} – ${fmtDay(b)}${a.getFullYear() !== b.getFullYear() ? ", " + b.getFullYear() : ""}`;
  }
  function miles(a, b) {
    const R = 3958.8, r = Math.PI / 180;
    const dLat = (b[0] - a[0]) * r, dLng = (b[1] - a[1]) * r;
    const h = Math.sin(dLat / 2) ** 2 + Math.cos(a[0] * r) * Math.cos(b[0] * r) * Math.sin(dLng / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(h));
  }
  const stateOf = (loc) => { const p = (loc || "").split(",").map((x) => x.trim()).filter(Boolean); return p.length > 1 ? p[p.length - 1] : ""; };

  /* ---------- URL <-> state ---------- */
  const LISTS = ["programs", "badges", "topics", "trainings"], BOOLS = ["anyBadge", "hideLong", "hideFund", "hideAdmin", "includeOnline", "newOnly"];
  function toHash() {
    const p = new URLSearchParams();
    for (const [k, v] of Object.entries(S)) {
      if (LISTS.includes(k)) { if (v.length) p.set(k, v.join("|")); }
      else if (BOOLS.includes(k)) p.set(k, v ? "1" : "0");
      else if (v) p.set(k, v);
    }
    history.replaceState(null, "", "#" + p.toString());
  }
  const DEFAULTS = JSON.parse(JSON.stringify(S));
  function fromHash() {
    Object.assign(S, JSON.parse(JSON.stringify(DEFAULTS)));  // anything not in the link goes back to default
    const p = new URLSearchParams(location.hash.slice(1));
    for (const k of Object.keys(S)) {
      if (!p.has(k)) continue;
      const v = p.get(k);
      if (LISTS.includes(k)) S[k] = v ? v.split("|") : [];
      else if (BOOLS.includes(k)) S[k] = v === "1";
      else S[k] = v;
    }
    if (!p.has("zip")) S.zip = store.get("zip") || "";
  }

  /* ---------- build filter UI ---------- */
  function checkList(box, values, key, counts) {
    box.replaceChildren(...values.map((v) => {
      const cb = el("input", { type: "checkbox", value: v });
      cb.checked = S[key].includes(v);
      cb.addEventListener("change", () => {
        S[key] = cb.checked ? [...S[key], v] : S[key].filter((x) => x !== v);
        update();
      });
      return el("label", { class: "check" }, cb, el("span", { text: v }), el("span", { class: "n", text: counts[v] || 0 }));
    }));
  }
  function tally(key) {
    const c = {};
    for (const e of ALL) for (const v of e[key]) c[v] = (c[v] || 0) + 1;
    return c;
  }
  function buildUI() {
    const prog = tally("programs"), top = tally("topics"), tr = tally("trainings"), bd = tally("badges");
    checkList($("#programs"), PROGRAMS.filter((p) => prog[p]), "programs", prog);
    checkList($("#topics"), Object.keys(top).sort((a, b) => top[b] - top[a]), "topics", top);
    checkList($("#trainings"), Object.keys(tr).sort(), "trainings", tr);
    $("#badgeList").replaceChildren(...Object.keys(bd).sort().map((b) => el("option", { value: b, label: `${b} (${bd[b]})` })));
    const councils = {}, states = {};
    for (const e of ALL) { councils[e.council] = (councils[e.council] || 0) + 1; const s = stateOf(e.location); if (s) states[s] = (states[s] || 0) + 1; }
    $("#council").append(...Object.keys(councils).sort().map((c) => el("option", { value: c, text: `${c} (${councils[c]})` })));
    $("#state").append(...Object.keys(states).sort().map((s) => el("option", { value: s, text: `${s} (${states[s]})` })));
  }
  function syncInputs() {
    for (const id of ["q", "zip", "radius", "state", "from", "to", "council", "sort"]) $("#" + id).value = S[id];
    for (const id of BOOLS) $("#" + id).checked = S[id];
    document.querySelectorAll("#datePresets button").forEach((b) => b.classList.toggle("on", b.dataset.days === S.preset));
    document.querySelectorAll(".checks input").forEach((cb) => {
      const key = cb.closest(".checks").id; cb.checked = S[key].includes(cb.value);
    });
    renderPicked();
  }
  function renderPicked() {
    $("#badgePicked").replaceChildren(...S.badges.map((b) => el("button", {
      type: "button", title: "Remove", onclick: () => { S.badges = S.badges.filter((x) => x !== b); update(); },
    }, `${b} ✕`)));
  }

  /* ---------- distance ---------- */
  async function setOrigin() {
    const z = (S.zip || "").trim();
    origin = null;
    if (!/^\d{5}$/.test(z)) { $("#zipHint").textContent = z ? "Enter a 5-digit ZIP" : "Add a ZIP to filter by distance"; return; }
    if (!ZIPS) {
      $("#zipHint").textContent = "Loading ZIP codes…";
      try { ZIPS = await fetch("data/zips.json").then((r) => r.json()); } catch { ZIPS = {}; }
    }
    origin = ZIPS[z] || null;
    $("#zipHint").textContent = origin ? `Distances from ${z}` : "ZIP not found";
    if (origin) store.set("zip", z);
  }

  /* ---------- filtering ---------- */
  function dateWindow() {
    const t = today0();
    let a = S.from ? new Date(S.from + "T00:00") : t, b = S.to ? new Date(S.to + "T23:59") : null;
    if (!S.from && !S.to && S.preset !== "all") {
      if (S.preset === "weekend") {
        const dow = t.getDay(); const fri = new Date(t.getTime() + ((5 - dow + 7) % 7) * DAY);
        a = dow === 0 || dow === 6 ? t : fri; b = new Date(fri.getTime() + 2 * DAY + DAY - 1);
        if (dow === 0) b = new Date(t.getTime() + DAY - 1);
      } else b = new Date(t.getTime() + Number(S.preset) * DAY);
    }
    return [a.getTime(), b ? b.getTime() : Infinity];
  }
  function matches(e, now, [wa, wb]) {
    const s = ts(e.startUtc), en = ts(e.endUtc) || s;
    if (en < now) return false;
    if (en < wa || s > wb) return false;
    if (S.hideLong && en - s > 21 * DAY) return false;
    if (S.hideFund && (e.topics.includes("Fundraising / Dinners") || e.categories.includes("Fundraising")) && !e.badges.length && !e.trainings.length) return false;
    if (S.hideAdmin && e.topics.includes("Meetings & Admin") && !S.topics.includes("Meetings & Admin")) return false;
    if (S.newOnly && (e.firstSeen <= FIRST_RUN || (now - Date.parse(e.firstSeen)) > 7 * DAY)) return false;
    if (S.council && e.council !== S.council) return false;
    // Online events can be joined from anywhere, so distance and state don't apply to them.
    const anywhere = e.online && S.includeOnline;
    if (S.state && !anywhere && stateOf(e.location) !== S.state) return false;
    if (S.programs.length && !S.programs.some((p) => e.programs.includes(p))) return false;
    if (S.topics.length && !S.topics.some((p) => e.topics.includes(p))) return false;
    if (S.trainings.length && !S.trainings.some((p) => e.trainings.includes(p))) return false;
    if (S.anyBadge && !e.badges.length) return false;
    if (S.badges.length && !S.badges.some((b) => e.badges.includes(b))) return false;
    if (origin && Number(S.radius) && !anywhere && (e.lat == null || e._d > Number(S.radius))) return false;
    if (S.q) {
      const hay = e._hay || (e._hay = [e.title, e.session, e.council, e.location, e.desc, ...e.badges, ...e.trainings, ...e.topics].join(" ").toLowerCase());
      if (!S.q.toLowerCase().split(/\s+/).every((w) => hay.includes(w))) return false;
    }
    return true;
  }

  function update() {
    toHash(); syncInputs();
    $("#tabEvents").classList.toggle("on", S.view !== "providers");
    $("#tabProviders").classList.toggle("on", S.view === "providers");
    $("#tabEvents").setAttribute("aria-selected", String(S.view !== "providers"));
    $("#tabProviders").setAttribute("aria-selected", String(S.view === "providers"));
    $("#subscribe").hidden = S.view === "providers";
    $("#sort").closest("label").hidden = S.view === "providers";
    if (S.view === "providers") { renderProviders(); return; }
    const now = Date.now(), win = dateWindow();
    for (const e of ALL) e._d = origin && e.lat != null ? miles(origin, [e.lat, e.lng]) : null;
    const hits = ALL.filter((e) => matches(e, now, win));
    // group sessions of the same event
    const groups = new Map();
    for (const e of hits) {
      const g = groups.get(e.eid) || { key: e.eid, items: [] };
      g.items.push(e); groups.set(e.eid, g);
    }
    const list = [...groups.values()];
    for (const g of list) {
      g.items.sort((a, b) => ts(a.startUtc) - ts(b.startUtc));
      g.first = g.items[0];
      g.d = Math.min(...g.items.map((x) => (x._d == null ? Infinity : x._d)));
      g.seen = g.items.reduce((m, x) => (x.firstSeen > m ? x.firstSeen : m), "");
    }
    const byDate = (a, b) => ts(a.first.startUtc) - ts(b.first.startUtc);
    list.sort(S.sort === "dist" && origin ? (a, b) => a.d - b.d || byDate(a, b)
      : S.sort === "new" ? (a, b) => b.seen.localeCompare(a.seen) || byDate(a, b) : byDate);
    render(list, hits.length);
  }

  /* ---------- provider directory ---------- */
  async function loadProviders() {
    if (PROV) return PROV;
    try { PROV = (await fetch("data/providers.json", { cache: "no-cache" }).then((r) => r.json())).providers || []; }
    catch { PROV = []; }
    const known = new Set([...$("#badgeList").options].map((o) => o.value));
    const extra = [...new Set(PROV.flatMap((p) => p.badges))].filter((b) => b !== "*" && !known.has(b));
    $("#badgeList").append(...extra.map((b) => el("option", { value: b })));
    return PROV;
  }
  async function renderProviders() {
    const list = await loadProviders();
    if (S.view !== "providers") return;
    const fmtDate = (d) => new Date(d + "T12:00").toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" });
    const rows = list.map((p) => ({ ...p, online: /online/i.test(p.format),
      d: origin && p.lat != null ? miles(origin, [p.lat, p.lng]) : null }))
      .filter((p) => {
        if (S.badges.length && !p.badges.includes("*") && !S.badges.some((b) => p.badges.includes(b))) return false;
        if (!p.online && origin && Number(S.radius) && (p.d == null || p.d > Number(S.radius))) return false;
        if (p.online && !S.includeOnline) return false;
        if (S.q) {
          const hay = [p.name, p.address, p.schedule, p.notes, p.format, ...p.badges].join(" ").toLowerCase();
          if (!S.q.toLowerCase().split(/\s+/).every((w) => hay.includes(w))) return false;
        }
        return true;
      })
      .sort((a, b) => (a.online - b.online) || ((a.d ?? 1e9) - (b.d ?? 1e9)) || a.name.localeCompare(b.name));
    $("#count").textContent = `${rows.length} provider${rows.length === 1 ? "" : "s"}`;
    const act = [];
    if (origin && Number(S.radius)) act.push(`within ${S.radius} mi of ${S.zip}${S.includeOnline ? " + online" : ""}`);
    S.badges.forEach((b) => act.push(b));
    if (S.q) act.push(`“${S.q}”`);
    $("#activeFilters").replaceChildren(...act.map((a) => el("span", { text: a })));
    $("#more").hidden = true;
    if (!rows.length) {
      $("#list").replaceChildren(el("div", { class: "empty" }, "No providers match. Try a wider distance or another badge."));
      return;
    }
    const recent = (d) => d && (Date.now() - Date.parse(d)) < 14 * DAY;
    $("#list").replaceChildren(
      el("p", { class: "ev-note", text: "Museums, businesses and online programs that teach merit badges. Dated sessions also appear on the Events tab. Each page is re-checked nightly." }),
      ...rows.map((p) => el("article", { class: "card prov" },
        el("h3", {}, el("a", { href: p.url, target: "_blank", rel: "noopener", text: p.name }),
          el("span", { class: "fmt" + (p.online ? " online" : ""), text: p.format })),
        el("div", { class: "meta" },
          p.address ? el("span", { text: p.address }) : null,
          p.d != null && !p.online ? el("span", { class: "dist", text: `${Math.round(p.d)} mi` }) : null),
        el("div", { class: "tags" }, p.badges.includes("*")
          ? el("span", { class: "tag b", text: "Most merit badges" })
          : p.badges.map((b) => el("span", { class: "tag b", text: b }))),
        el("dl", {},
          p.schedule ? [el("dt", { text: "Schedule" }), el("dd", { text: p.schedule })] : null,
          p.cost ? [el("dt", { text: "Cost" }), el("dd", { text: p.cost })] : null,
          p.dates.length ? [el("dt", { text: "Dates on their page" }), el("dd", { class: "dates", text: p.dates.map(fmtDate).join(" · ") })] : null,
          p.notes ? [el("dt", { text: "Notes" }), el("dd", { text: p.notes })] : null,
          recent(p.pageChanged) ? [el("dt", { text: "Updated" }), el("dd", { class: "dates", text: `Their page changed ${fmtDate(p.pageChanged)} - check for new dates` })] : null),
        el("div", { class: "actions" }, el("a", { href: p.url, target: "_blank", rel: "noopener", text: "Visit website" })))));
  }

  /* ---------- rendering ---------- */
  function render(list, nSessions) {
    $("#count").textContent = `${list.length.toLocaleString()} event${list.length === 1 ? "" : "s"}` +
      (nSessions !== list.length ? ` · ${nSessions.toLocaleString()} sessions` : "");
    const act = [];
    if (S.q) act.push(`“${S.q}”`);
    if (origin && Number(S.radius)) act.push(`within ${S.radius} mi of ${S.zip}${S.includeOnline ? " + online" : ""}`);
    [...S.programs, ...S.badges, ...S.topics, ...S.trainings].forEach((x) => act.push(x));
    if (S.anyBadge) act.push("Any merit badge");
    if (S.council) act.push(S.council);
    if (S.state) act.push(S.state);
    $("#activeFilters").replaceChildren(...act.map((a) => el("span", { text: a })));

    const box = $("#list");
    if (!list.length) {
      box.replaceChildren(el("div", { class: "empty" }, "No events match these filters. Try a wider distance or date range."));
      $("#more").hidden = true; return;
    }
    box.replaceChildren(...list.slice(0, shown).map(card));
    $("#more").hidden = list.length <= shown;
  }

  function card(g) {
    const e = g.first, a = local(e.start);
    const now = Date.now(), isNew = e.firstSeen > FIRST_RUN && now - Date.parse(e.firstSeen) <= 7 * DAY;
    const allBadges = [...new Set(g.items.flatMap((x) => x.badges))];
    const allTrain = [...new Set(g.items.flatMap((x) => x.trainings))];
    const tags = [
      isNew ? el("span", { class: "tag new", text: "New" }) : null,
      e.online ? el("span", { class: "tag online", text: "Online" }) : null,
      ...allBadges.slice(0, 12).map((b) => el("span", { class: "tag b", text: b })),
      allBadges.length > 12 ? el("span", { class: "tag b", text: `+${allBadges.length - 12} more` }) : null,
      ...allTrain.map((t) => el("span", { class: "tag t", text: t })),
      ...e.programs.map((p) => el("span", { class: "tag", text: p })),
      ...e.topics.filter((t) => t !== "Merit Badge Program" && t !== "Training" && t !== "Online / Virtual").slice(0, 3).map((t) => el("span", { class: "tag", text: t })),
    ];
    const GENERIC_SESSION = /^(event|registration|participants?|attendees?|youth|adults?|session ?1?|general|scouts?)$/i;
    const sessions = g.items.length > 1
      ? el("ul", { class: "sessions" }, g.items.slice(0, 8).map((x) => el("li", {}, `${when(x)}${x.session ? " — " + x.session : ""}`)),
          g.items.length > 8 ? el("li", {}, `+ ${g.items.length - 8} more sessions`) : null)
      : null;
    const desc = (e.desc || "").replace(/\s+/g, " ").trim();
    return el("article", { class: "card" },
      el("div", { class: "date" },
        el("div", { class: "m", text: a ? a.toLocaleDateString([], { month: "short" }) : "" }),
        el("div", { class: "d", text: a ? a.getDate() : "" }),
        el("div", { class: "w", text: a ? a.toLocaleDateString([], { weekday: "short" }) : "" })),
      el("div", {},
        el("h3", {}, el("a", { href: e.url, target: "_blank", rel: "noopener", text: e.title })),
        g.items.length === 1 && e.session && !GENERIC_SESSION.test(e.session.trim()) ? el("div", { class: "sess", text: e.session }) : null,
        el("div", { class: "meta" },
          el("span", { text: when(e) }),
          el("span", { text: e.council }),
          e.location ? el("span", { text: e.location }) : null,
          e.online ? el("span", { class: "dist", text: "Online" }) :
          g.d !== Infinity && origin ? el("span", { class: "dist", title: e.approx ? "Approximate: measured to the council office (no address listed)" : "",
            text: e.approx ? `~${Math.round(g.d)} mi (council area)` : `${Math.round(g.d)} mi` }) : null,
          e.fees && e.fees.length ? el("span", { text: e.fees.length > 1 ? `${e.fees[0]}–${e.fees[e.fees.length - 1]}` : e.fees[0] }) : null),
        el("div", { class: "tags" }, tags),
        e.provider ? el("p", { class: "ev-note", text: "From the provider's published schedule - confirm the date on their page before you go." }) :
        desc ? el("p", { class: "desc", text: desc.length > 260 ? desc.slice(0, 260) + "…" : desc }) : null,
        sessions,
        el("div", { class: "actions" },
          el("a", { href: e.url, target: "_blank", rel: "noopener", text: "Details & register" }),
          el("button", { type: "button", onclick: () => downloadIcs(g.items) }, "Add to calendar"),
          e.lat != null ? el("a", { href: `https://www.google.com/maps/search/?api=1&query=${e.lat},${e.lng}`, target: "_blank", rel: "noopener", text: "Map" }) : null)));
  }

  function downloadIcs(items) {
    const esc = (s) => String(s || "").replace(/[\\,;]/g, (m) => "\\" + m).replace(/\n/g, "\\n");
    const dt = (s) => s.replace(/[-:]/g, "").replace("Z", "00Z");
    const lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Scout Event Finder//EN"];
    for (const e of items) {
      lines.push("BEGIN:VEVENT", `UID:${e.id}@scout-event-finder`, `DTSTAMP:${dt(new Date().toISOString().slice(0, 16) + "Z")}`,
        `DTSTART:${dt(e.startUtc)}`, `DTEND:${dt(e.endUtc || e.startUtc)}`,
        `SUMMARY:${esc(e.title + (e.session ? " – " + e.session : ""))}`,
        `LOCATION:${esc(e.location)}`, `DESCRIPTION:${esc(e.council + "\n" + e.url)}`, `URL:${e.url}`, "END:VEVENT");
    }
    lines.push("END:VCALENDAR");
    const a = el("a", { href: URL.createObjectURL(new Blob([lines.join("\r\n")], { type: "text/calendar" })), download: "scout-event.ics" });
    document.body.append(a); a.click(); a.remove();
  }

  /* ---------- wire up ---------- */
  function bind() {
    const on = (id, ev, fn) => $("#" + id).addEventListener(ev, fn);
    let t;
    on("q", "input", (e) => { clearTimeout(t); t = setTimeout(() => { S.q = e.target.value.trim(); shown = PAGE; update(); }, 200); });
    on("zip", "input", async (e) => { S.zip = e.target.value.trim(); if (S.zip.length === 5 || !S.zip) { await setOrigin(); shown = PAGE; update(); } });
    for (const id of ["radius", "state", "council", "sort"]) on(id, "change", (e) => { S[id] = e.target.value; shown = PAGE; update(); });
    for (const id of ["from", "to"]) on(id, "change", (e) => { S[id] = e.target.value; S.preset = ""; shown = PAGE; update(); });
    for (const id of BOOLS) on(id, "change", (e) => { S[id] = e.target.checked; shown = PAGE; update(); });
    document.querySelectorAll("#datePresets button").forEach((b) => b.addEventListener("click", () => {
      S.preset = b.dataset.days; S.from = ""; S.to = ""; shown = PAGE; update();
    }));
    on("badgeInput", "change", (e) => {
      const v = e.target.value.trim(); const match = [...$("#badgeList").options].find((o) => o.value.toLowerCase() === v.toLowerCase());
      if (match && !S.badges.includes(match.value)) S.badges.push(match.value);
      e.target.value = ""; shown = PAGE; update();
    });
    on("more", "click", () => { shown += PAGE; update(); });
    on("reset", "click", () => {
      Object.assign(S, { q: "", radius: "150", state: "", from: "", to: "", preset: "all", programs: [], badges: [], anyBadge: false,
        topics: [], trainings: [], council: "", hideLong: true, hideFund: true, hideAdmin: true, includeOnline: true, newOnly: false, sort: "date" });
      shown = PAGE; update();
    });
    window.addEventListener("hashchange", async () => { fromHash(); await setOrigin(); shown = PAGE; update(); });
    on("tabEvents", "click", () => { S.view = "events"; shown = PAGE; update(); });
    on("tabProviders", "click", () => { S.view = "providers"; update(); });
    on("openFilters", "click", () => $("#filters").classList.add("open"));
    on("closeFilters", "click", () => $("#filters").classList.remove("open"));
  }

  async function loadFeeds() {
    const box = $("#feedLinks");
    let idx = [];
    try { idx = await fetch("feeds/index.json", { cache: "no-cache" }).then((r) => r.json()); } catch { /* not built yet */ }
    const base = new URL("feeds/", location.href).href;
    const row = (name, file) => {
      const url = base + file;
      const inp = el("input", { type: "text", readonly: "", value: url, "aria-label": name + " feed URL" });
      inp.addEventListener("focus", () => inp.select());
      return el("div", { class: "feed" }, el("span", { class: "name", text: name }), inp,
        el("button", { type: "button", onclick: (e) => { navigator.clipboard?.writeText(url); e.target.textContent = "Copied"; } }, "Copy"));
    };
    const draw = () => {
      const rows = [row("All merit badge events (US)", "merit-badges.ics"), row("Online merit badges & classes", "online.ics"),
        row("All trainings (US)", "trainings.ics")];
      const pick = idx.filter((x) => !S.state || x.state === S.state);
      for (const x of (S.state ? pick : [])) {
        rows.push(row(`${x.state} – everything`, x.file));
        if (x.mb) rows.push(row(`${x.state} – merit badges`, x.mb));
      }
      if (!S.state) rows.push(el("p", { text: "Pick a state in the filters to get feeds for just that state." }));
      box.replaceChildren(...rows);
    };
    $("#subscribe").addEventListener("toggle", draw);
    $("#state").addEventListener("change", draw);
    draw();
  }

  async function init() {
    fromHash(); bind(); syncInputs();
    $("#list").replaceChildren(el("div", { class: "empty" }, "Loading events…"));
    try {
      const data = await fetch("data/events.json", { cache: "no-cache" }).then((r) => r.json());
      ALL = data.events;
      FIRST_RUN = ALL.reduce((m, e) => (!m || e.firstSeen < m ? e.firstSeen : m), "");
      const u = new Date(data.updated);
      $("#updated").textContent = `${data.count.toLocaleString()} sessions · updated ${u.toLocaleDateString([], { month: "short", day: "numeric" })} ${fmtTime(u)}`;
    } catch {
      $("#updated").textContent = "";
      $("#list").replaceChildren(el("div", { class: "empty" }, "Event data isn't available yet. It appears after the first nightly update runs."));
      return;
    }
    buildUI(); await setOrigin(); update(); loadFeeds();
  }
  init();
})();
