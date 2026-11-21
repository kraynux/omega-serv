/* Administration web omega-serv - affichage du tableau de bord (lot 4).
   Regle de securite : tout ce qui vient du serveur (et donc des journaux, ou n'importe qui ecrit) est affiche comme
   du TEXTE (textContent), jamais comme du HTML. Aucune chaine a traduire ici : libelles deja traduits par le serveur,
   ou lus dans les attributs data-* de la page. */
"use strict";

const REFRESH_MS = 2000;
const FLEET_REFRESH_MS = 5000;
const INSTANCE_ID = /^[0-9a-f]{12}$/;
const MAX_LOG_LINES = 2000;

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

async function getJson(url) {
  const response = await fetch(url, { credentials: "same-origin", cache: "no-store" });
  if (response.status === 401) {
    window.location.assign("/connexion");
    throw new Error("session");
  }
  if (!response.ok) throw new Error(String(response.status));
  return response.json();
}

function renderSection(section) {
  const box = el("section", "panel");
  if (section.title) box.appendChild(el("h2", "", section.title));
  if (section.rows.length) {
    const list = el("dl", "rows");
    for (const row of section.rows) {
      list.appendChild(el("dt", "", row.label));
      const value = el("dd", row.tone ? "tone-" + row.tone : "");
      if (row.gauge !== null && row.gauge !== undefined) {
        const bar = el("span", "gauge");
        const fill = el("span", "fill" + (row.tone ? " tone-bg-" + row.tone : ""));
        fill.style.width = Math.max(0, Math.min(100, row.gauge)) + "%";
        bar.appendChild(fill);
        value.appendChild(bar);
      }
      value.appendChild(el("span", "", row.value));
      list.appendChild(value);
    }
    box.appendChild(list);
  }
  if (section.note) box.appendChild(el("p", "hint", section.note));
  if (section.table.length) {
    const wrap = el("div", "table-wrap");
    const table = el("table");
    if (section.headers.length) {
      const head = el("tr");
      for (const header of section.headers) head.appendChild(el("th", "", header));
      table.appendChild(head);
    }
    for (const cells of section.table) {
      const line = el("tr");
      for (const cell of cells) line.appendChild(el("td", "", cell));
      table.appendChild(line);
    }
    wrap.appendChild(table);
    box.appendChild(wrap);
  }
  return box;
}

function showUpdated(stamp) {
  const target = document.querySelector(".updated");
  if (target && stamp) target.textContent = target.dataset.updatedLabel + " " + stamp;
}

async function refreshPanel(container) {
  try {
    const payload = await getJson(container.dataset.api);
    const fragment = document.createDocumentFragment();
    if (container.dataset.title) fragment.appendChild(el("h1", "column-title", container.dataset.title));
    if (payload.loading) fragment.appendChild(el("p", "hint", payload.loading));
    if (payload.error) fragment.appendChild(el("p", "error", payload.error));
    for (const section of payload.sections || []) fragment.appendChild(renderSection(section));
    container.replaceChildren(fragment);
    showUpdated(payload.updated);
  } catch (error) {
    /* serveur momentanement injoignable : on garde l'affichage precedent et on reessaie */
  }
}

function startPanels() {
  const panels = document.querySelectorAll("[data-api]");
  if (!panels.length) return;
  const tick = () => panels.forEach(refreshPanel);
  tick();
  setInterval(tick, REFRESH_MS);
}

async function startLines() {
  const target = document.querySelector("[data-lines]");
  if (!target) return;
  const tick = async () => {
    try {
      const payload = await getJson(target.dataset.lines);
      target.textContent = (payload.lines || []).join("\n");
    } catch (error) { /* on reessaie */ }
  };
  tick();
  setInterval(tick, REFRESH_MS * 5);
}

function startLogs() {
  const select = document.getElementById("log-select");
  if (!select) return;
  const output = document.getElementById("log-output");
  const status = document.getElementById("log-status");
  const linesInput = document.getElementById("log-lines");
  const filterInput = document.getElementById("log-filter");
  const followButton = document.getElementById("log-follow");
  let cursor = 0;
  let timer = null;
  let shown = [];

  const draw = () => {
    output.textContent = shown.join("\n");
    output.scrollTop = output.scrollHeight;
  };

  /* Nombre de lignes choisi (1 a MAX_LOG_LINES) : il borne aussi le direct. */
  const wanted = () => {
    const value = parseInt(linesInput.value, 10);
    return Number.isFinite(value) ? Math.max(1, Math.min(MAX_LOG_LINES, value)) : MAX_LOG_LINES;
  };

  /* Chaque lecture porte un numero : une reponse plus ancienne que la derniere demandee est ignoree (sinon une
     frappe rapide dans le filtre pouvait afficher le resultat d'une valeur deja remplacee). */
  let request = 0;
  const snapshot = async () => {
    const mine = ++request;
    const query = new URLSearchParams({ id: select.value, lignes: linesInput.value, filtre: filterInput.value });
    try {
      const payload = await getJson("/api/journal?" + query.toString());
      if (mine !== request) return;
      shown = payload.lines || [];
      cursor = payload.cursor || 0;
      status.textContent = payload.problem || "";
      draw();
    } catch (error) { /* on reessaie a la prochaine modification */ }
  };

  const follow = async () => {
    try {
      const query = new URLSearchParams({ id: select.value, curseur: String(cursor) });
      const mine = request;
      const payload = await getJson("/api/journal/suite?" + query.toString());
      if (mine !== request) return;  /* un instantane a ete relu entre-temps : il a son propre curseur */
      cursor = payload.cursor;
      const needle = filterInput.value.toLowerCase();
      const added = (payload.lines || []).filter((line) => !needle || line.toLowerCase().includes(needle));
      if (payload.rotated) shown = [];
      status.textContent = payload.problem || payload.rotated || "";
      if (added.length || payload.rotated) {
        shown = shown.concat(added).slice(-wanted());
        draw();
      }
    } catch (error) { /* on reessaie */ }
  };

  const stopFollowing = () => {
    if (timer !== null) clearInterval(timer);
    timer = null;
    followButton.textContent = followButton.dataset.off;
  };

  document.getElementById("log-snapshot").addEventListener("click", () => { stopFollowing(); snapshot(); });
  followButton.addEventListener("click", async () => {
    if (timer !== null) { stopFollowing(); return; }
    await snapshot();
    timer = setInterval(follow, REFRESH_MS);
    followButton.textContent = followButton.dataset.on;
  });
  select.addEventListener("change", () => { stopFollowing(); snapshot(); });
  /* Retour de l'auteur du 2026-11-17 : modifier le nombre de lignes ou le filtre relit le journal aussitot (avant,
     il fallait passer par un autre journal). Le direct continue s'il etait lance. */
  let typing = null;
  const reread = () => { if (typing !== null) clearTimeout(typing); typing = null; snapshot(); };
  const rereadSoon = () => { if (typing !== null) clearTimeout(typing); typing = setTimeout(reread, 400); };
  for (const input of [linesInput, filterInput]) {
    input.addEventListener("input", rereadSoon);
    input.addEventListener("change", reread);
    input.addEventListener("keydown", (event) => { if (event.key === "Enter") { event.preventDefault(); reread(); } });
  }

  getJson("/api/journaux").then((payload) => {
    for (const log of payload.logs || []) {
      const option = el("option", "", log.label);
      option.value = log.id;
      select.appendChild(option);
    }
    if (select.options.length) snapshot();
  }).catch(() => {});
}

/* Page Instances d'un maitre (lot 6) : une ligne par instance suivie, toutes les 5 s. Le lien n'est construit que
   pour un identifiant de 12 caracteres hexadecimaux ; le reste est du texte. */
function startFleet() {
  const target = document.querySelector("[data-fleet]");
  if (!target) return;
  const tick = async () => {
    try {
      const payload = await getJson(target.dataset.fleet);
      const fragment = document.createDocumentFragment();
      if (payload.empty) fragment.appendChild(el("p", "hint", payload.empty));
      if ((payload.rows || []).length) {
        const wrap = el("div", "table-wrap");
        const table = el("table");
        const head = el("tr");
        for (const header of payload.headers || []) head.appendChild(el("th", "", header));
        table.appendChild(head);
        for (const row of payload.rows) {
          const line = el("tr", row.tone ? "tone-" + row.tone : "");
          row.cells.forEach((cell, index) => {
            const td = el("td");
            if (index === 0 && row.link && INSTANCE_ID.test(row.id)) {
              const link = el("a", "", cell);
              link.href = "/instances/" + row.id;
              td.appendChild(link);
            } else {
              td.textContent = String(cell);
            }
            line.appendChild(td);
          });
          table.appendChild(line);
        }
        wrap.appendChild(table);
        fragment.appendChild(wrap);
      }
      target.replaceChildren(fragment);
      showUpdated(payload.updated);
    } catch (error) { /* on reessaie */ }
  };
  tick();
  setInterval(tick, FLEET_REFRESH_MS);
}

/* Historique (lots 7 et 9) : graphes SVG, six plages, « Moyenne » ou « Max 1 min », relus toutes les 10 s. Aucun
   texte du serveur n'est interprete : les points sont des nombres, les libelles viennent des attributs data-* de la
   page. Un graphe sans aucune valeur sur la plage (pas de capteur, pas de batterie...) est masque. */
const HISTORY_REFRESH_MS = 10000;
const SVG_NS = "http://www.w3.org/2000/svg";
const CHART_W = 600, CHART_H = 170, PAD_L = 70, PAD_R = 8, PAD_T = 10, PAD_B = 22;

function svg(tag, attributes) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [name, value] of Object.entries(attributes || {})) node.setAttribute(name, String(value));
  return node;
}

function niceMax(value) {
  if (!(value > 0)) return 1;
  const power = Math.pow(10, Math.floor(Math.log10(value)));
  for (const factor of [1, 2, 2.5, 5, 10]) if (factor * power >= value) return factor * power;
  return 10 * power;
}

/* Unites a paliers : octets/s et tailles en base 1024 (comme le reste d'omega-serv), bits/s en base 1000. */
const SCALED = { bytes: ["units", 1024, 1], size: ["unitsSize", 1024, 1], bits: ["unitsBits", 1000, 8] };

function formatValue(value, unit, labels) {
  const lang = document.documentElement.lang || undefined;
  if (value === null || value === undefined) return "-";
  if (unit === "%") return value.toLocaleString(lang, { maximumFractionDigits: 1 }) + " %";
  if (unit === "celsius") return value.toLocaleString(lang, { maximumFractionDigits: 1 }) + " °C";
  if (SCALED[unit]) {
    const [name, base, factor] = SCALED[unit];
    const units = labels[name].split("|");
    let index = 0;
    value *= factor;
    while (value >= base && index < units.length - 1) { value /= base; index += 1; }
    return value.toLocaleString(lang, { maximumFractionDigits: value < 10 ? 1 : 0 }) + " " + units[index];
  }
  return value.toLocaleString(lang, { maximumFractionDigits: value < 10 ? 2 : 0 });
}

function axisTop(top, unit) {
  if (unit === "%") return 100;
  if (SCALED[unit]) {  /* graduations rondes dans l'unite affichee (Ko/s, Mbit/s...) */
    const [, base, factor] = SCALED[unit];
    let scale = 1;
    while (top * factor / scale >= base) scale *= base;
    return niceMax(top * factor / scale) * scale / factor;
  }
  return niceMax(top);
}

function linePath(points, key, x, y, gap) {
  let d = "", previous = null;
  for (const point of points) {
    const value = point[key];
    if (value === null || value === undefined) { previous = null; continue; }
    const command = previous === null || point.t - previous > gap ? "M" : "L";
    d += command + x(point.t).toFixed(1) + " " + y(value).toFixed(1) + " ";
    previous = point.t;
  }
  return d.trim();
}

/* Surface sous la courbe (graphes a capacite : memoire, swap, disque, omega-serv, batterie) : un polygone par
   morceau continu, ferme sur la ligne du zero. */
function areaPath(points, key, x, y, gap) {
  let d = "", run = [];
  const flush = () => {
    if (run.length) {
      d += "M" + run[0][0].toFixed(1) + " " + y(0).toFixed(1) + " ";
      for (const [px, py] of run) d += "L" + px.toFixed(1) + " " + py.toFixed(1) + " ";
      d += "L" + run[run.length - 1][0].toFixed(1) + " " + y(0).toFixed(1) + " Z ";
    }
    run = [];
  };
  let previous = null;
  for (const point of points) {
    const value = point[key];
    if (value === null || value === undefined) { flush(); previous = null; continue; }
    if (previous !== null && point.t - previous > gap) flush();
    run.push([x(point.t), y(value)]);
    previous = point.t;
  }
  flush();
  return d.trim();
}

function fill(template, values) {
  return template.replace(/\{(\w+)\}/g, (all, name) => (name in values ? values[name] : all));
}

/* Haut a droite des graphes a capacite (lot 9c) : « utilise / total · % » d'apres la derniere mesure et les tailles
   totales lues a l'affichage ; sans taille connue, le pourcentage seul. */
function detailText(kind, value, capacities, labels) {
  const lang = document.documentElement.lang || undefined;
  if (value === null || value === undefined) return "-";
  const caps = capacities || {};
  if (kind === "memoire-octets") {
    const total = caps.memoire;
    if (!total) return formatValue(value, "size", labels);
    return fill(labels.of, { used: formatValue(value, "size", labels), total: formatValue(total, "size", labels),
                             percent: formatValue(value / total * 100, "%", labels) });
  }
  const percent = formatValue(value, "%", labels);
  if (kind === "coeurs" && caps.coeurs) {
    const used = value / 100 * caps.coeurs;
    return fill(labels.cores, { used: used.toLocaleString(lang, { maximumFractionDigits: used < 1 ? 2 : 1 }),
                                total: caps.coeurs.toLocaleString(lang), percent });
  }
  if (kind === "batterie" && caps.batterie) {
    if (caps.batterie.secteur) return fill(labels.plugged, { percent });
    const left = caps.batterie.restant;
    if (left) return fill(labels.left, { hours: Math.floor(left / 3600), minutes: Math.floor(left % 3600 / 60), percent });
    return percent;
  }
  const total = caps[kind];
  if (!total || !["memoire", "swap", "disque"].includes(kind)) return percent;
  return fill(labels.of, { used: formatValue(value / 100 * total, "size", labels),
                           total: formatValue(total, "size", labels), percent });
}

function drawChart(figure, payload, labels, ago) {
  const unit = figure.dataset.unit;
  const keys = figure.dataset.series.split(",");
  const legend = figure.dataset.legend ? figure.dataset.legend.split("|") : [];
  const points = payload.points || [];
  const measured = points.some(point => keys.some(key => point[key] !== null && point[key] !== undefined));
  figure.hidden = points.length > 0 && !measured;
  if (figure.hidden) return;
  let top = 0;
  for (const point of points) for (const key of keys) if (point[key] > top) top = point[key];
  top = axisTop(top, unit);
  const low = 0;
  const x = t => PAD_L + (t - payload.from) / Math.max(1, payload.now - payload.from) * (CHART_W - PAD_L - PAD_R);
  const y = v => PAD_T + (1 - (v - low) / Math.max(1e-9, top - low)) * (CHART_H - PAD_T - PAD_B);
  const chart = svg("svg", { viewBox: `0 0 ${CHART_W} ${CHART_H}`, role: "img", class: "chart-svg" });
  for (const fraction of [0, 0.5, 1]) {
    const level = PAD_T + fraction * (CHART_H - PAD_T - PAD_B);
    chart.appendChild(svg("line", { x1: PAD_L, x2: CHART_W - PAD_R, y1: level, y2: level, class: "grid" }));
    const label = svg("text", { x: PAD_L - 6, y: level + 4, class: "axis", "text-anchor": "end" });
    label.textContent = formatValue(top - fraction * (top - low), unit, labels);
    chart.appendChild(label);
  }
  const start = svg("text", { x: PAD_L, y: CHART_H - 6, class: "axis" });
  start.textContent = ago;
  const end = svg("text", { x: CHART_W - PAD_R, y: CHART_H - 6, class: "axis", "text-anchor": "end" });
  end.textContent = labels.now;
  chart.append(start, end);
  const detail = figure.dataset.detail || "";
  if (detail) {
    const area = areaPath(points, keys[0], x, y, payload.step * 2.5);
    if (area) chart.appendChild(svg("path", { d: area, class: "area area-0" }));
  }
  keys.forEach((key, index) => {
    const d = linePath(points, key, x, y, payload.step * 2.5);
    if (d) chart.appendChild(svg("path", { d, class: "line line-" + index }));
  });
  const plot = figure.querySelector(".plot");
  const last = points.length ? points[points.length - 1] : null;
  const caption = figure.querySelector(".last") || figure.querySelector("figcaption").appendChild(el("span", "last"));
  caption.replaceChildren();
  if (last && keys.length > 1) {
    keys.forEach((key, index) => {
      if (index) caption.append(" · ");
      caption.append(el("span", "key-" + index, "■ " + (legend[index] || key) + " " + formatValue(last[key], unit, labels)));
    });
  } else if (last && detail) {
    caption.textContent = detailText(detail, last[keys[0]], payload.capacites, labels);
  } else if (last) {
    caption.textContent = formatValue(last[keys[0]], unit, labels);
  }
  plot.replaceChildren(points.length ? chart : el("p", "hint", labels.empty));
}

function startHistory() {
  const target = document.querySelector("[data-history]");
  if (!target) return;
  const labels = {};
  for (const [name, value] of Object.entries(target.dataset)) {
    if (name.startsWith("label")) labels[name.slice(5).replace(/^./, c => c.toLowerCase())] = value;
  }
  let range = "1h", mode = "avg", request = 0;
  const rangeButtons = target.querySelectorAll("[data-range]");
  const modeButtons = target.querySelectorAll("[data-mode]");
  const note = target.querySelector(".mode-note");
  const tick = async () => {
    const mine = ++request;
    try {
      const query = "?plage=" + encodeURIComponent(range) + "&mode=" + encodeURIComponent(mode);
      const payload = await getJson(target.dataset.history + query);
      if (mine !== request) return;  /* une plage choisie entre-temps : sa reponse a elle seule compte */
      const active = Array.from(rangeButtons).find(button => button.dataset.range === range);
      const ago = active ? active.dataset.ago : "";
      note.hidden = mode !== "max" || payload.has_max;
      note.textContent = labels.sameMax;
      target.querySelectorAll("figure.chart").forEach(figure => drawChart(figure, payload, labels, ago));
    } catch (error) { /* on reessaie */ }
  };
  const choose = (buttons, attribute, value) => buttons.forEach(button =>
    button.classList.toggle("active", button.dataset[attribute] === value));
  rangeButtons.forEach(button => button.addEventListener("click", () => {
    range = button.dataset.range;
    choose(rangeButtons, "range", range);
    tick();
  }));
  modeButtons.forEach(button => button.addEventListener("click", () => {
    mode = button.dataset.mode;
    choose(modeButtons, "mode", mode);
    tick();
  }));
  choose(rangeButtons, "range", range);
  choose(modeButtons, "mode", mode);
  tick();
  setInterval(tick, HISTORY_REFRESH_MS);
}

startPanels();
startLines();
startLogs();
startFleet();
startHistory();
