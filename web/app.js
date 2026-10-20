/* ============ STATSPHERE v6 app ============ */
"use strict";
const $ = (s, r) => (r || document).querySelector(s);
const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
const esc = (v) => String(v == null ? "" : v).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const CIS = "https://api.dicebear.com/7.x/bottts/svg?seed=";
const img = (src, seed, cls) => `<img class="${cls || ""}" src="${esc(src || "")}" alt="" loading="lazy" onerror="this.onerror=null;this.src='${CIS}${encodeURIComponent(seed || "x")}'">`;

const S = {
  view: "matches",
  fixtures: [], currentMd: 1, shownMd: 1,
  clubs: [], standings: [], players: [],
  match: null, forecast: null, sim: null,
  engine: localStorage.getItem("statsphere_engine") || "gut",
  cmpA: null, cmpB: null, clubA: null, clubB: null,
  compareMode: false, clubCompareMode: false,
};

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg; t.hidden = false;
  clearTimeout(t._h); t._h = setTimeout(() => (t.hidden = true), 2600);
}
async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error("HTTP " + r.status);
  return r.json();
}

/* ---------- nav / theme / clock ---------- */
function switchView(name) {
  S.view = name;
  $$(".view").forEach((v) => (v.hidden = v.id !== "view-" + name));
  $$("#mainNav .navbtn").forEach((b) => b.classList.toggle("is-active", b.dataset.nav === name));
  $("#mainNav").classList.remove("open");
  window.scrollTo({ top: 0 });
  if (name === "matches" && !S.fixtures.length) loadMatches();
  if (name === "players" && !S.players.length) loadPlayers();
  if (name === "clubs" && !S.clubs.length) loadClubs();
  if (name === "table" && !S.standings.length) loadTable();
}
function initChrome() {
  document.addEventListener("click", (e) => {
    const nav = e.target.closest("[data-nav]");
    if (nav) { switchView(nav.dataset.nav); return; }
    if (e.target.closest("[data-close]")) { e.target.closest(".modal-veil").hidden = true; return; }
    if (e.target.classList && e.target.classList.contains("modal-veil")) { e.target.hidden = true; return; }
  });
  $("#burger").onclick = () => $("#mainNav").classList.toggle("open");
  $("#themeBtn").onclick = () => {
    const cur = document.documentElement.getAttribute("data-theme") === "light" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", cur);
    try { localStorage.setItem("statsphere-theme", cur); } catch (e) {}
  };
  setInterval(() => {
    const d = new Date();
    $("#clock").textContent = d.toISOString().slice(11, 19) + " UTC";
  }, 1000);
}

/* ---------- global search ---------- */
let searchTimer = null;
function initSearch() {
  const inp = $("#globalSearch"), box = $("#searchResults");
  inp.addEventListener("input", () => {
    clearTimeout(searchTimer);
    const q = inp.value.trim();
    if (q.length < 2) { box.hidden = true; return; }
    searchTimer = setTimeout(async () => {
      try {
        const [p, c] = await Promise.all([
          getJSON("/api/players?q=" + encodeURIComponent(q) + "&limit=6"),
          getJSON("/api/clubs"),
        ]);
        const clubs = (c.clubs || []).filter((x) => {
          const m = x.club || {};
          return ((m.nickname || "") + " " + (m.name || "")).toLowerCase().includes(q.toLowerCase());
        }).slice(0, 3);
        let html = "";
        (p.players || []).forEach((pl) => {
          html += `<div class="sr-item" data-pslug="${esc(pl.slug)}">${img(pl.photo_url || pl.cutout_url, pl.nickname, "")}<div><div class="t">${esc(pl.nickname || pl.name)}</div><div class="s">${esc(pl.club_nickname || "")} · ${esc(pl.position_name || "")}</div></div></div>`;
        });
        clubs.forEach((x) => {
          const m = x.club || {};
          html += `<div class="sr-item" data-cslug="${esc(m.slug)}">${img(m.shield_url, m.nickname, "")}<div><div class="t">${esc(m.nickname || m.name)}</div><div class="s">Club</div></div></div>`;
        });
        box.innerHTML = html || `<div class="sr-item">No results</div>`;
        box.hidden = false;
      } catch (e) { box.hidden = true; }
    }, 280);
  });
  box.addEventListener("click", async (e) => {
    const p = e.target.closest("[data-pslug]"), c = e.target.closest("[data-cslug]");
    box.hidden = true; inp.value = "";
    if (p) openPlayer(p.dataset.pslug);
    if (c) openClub(c.dataset.cslug);
  });
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".topbar-search")) box.hidden = true;
  });
}

/* ---------- matches ---------- */
async function loadMatches() {
  try {
    const [fx, live, lead] = await Promise.all([
      getJSON("/api/fixtures"),
      getJSON("/api/live").catch(() => ({ live_matches: [] })),
      getJSON("/api/leaders?stat=goals&limit=8").catch(() => ({ leaders: [] })),
    ]);
    S.fixtures = fx.fixtures || [];
    S.currentMd = fx.current_matchday || 1;
    if (!S.shownMd) S.shownMd = S.currentMd;
    renderMatches(live.live_matches || [], lead.leaders || []);
    getJSON("/api/sync-status").then((s) => {
      $("#syncNote").textContent = "MD " + s.current_matchday + " · " + (s.database_totals ? s.database_totals.total_finished + "/" + s.database_totals.total_fixtures + " played" : "");
    }).catch(() => {});
  } catch (e) { $("#fixtureGrid").innerHTML = `<div class="empty">Could not load fixtures.</div>`; }
}
function renderMatches(liveMatches, leaders) {
  const pill = $("#livePill");
  if (liveMatches.length) { pill.hidden = false; $("#liveCount").textContent = liveMatches.length; }
  else pill.hidden = true;

  let html = "";
  liveMatches.slice(0, 4).forEach((m) => {
    html += `<div class="card livecard"><div class="fx-top"><span class="pill live">● ${esc(m.status_long || "LIVE")} ${m.elapsed ? m.elapsed + "'" : ""}</span><span>${esc(m.league || "")}</span></div>
      <div class="fx-teams"><div class="fx-team">${img(m.home_logo, m.home_name, "")}<span>${esc(m.home_name)}</span></div>
      <div class="fx-score">${m.home_score} - ${m.away_score}</div>
      <div class="fx-team">${img(m.away_logo, m.away_name, "")}<span>${esc(m.away_name)}</span></div></div></div>`;
  });
  $("#liveStrip").innerHTML = html;

  $("#leadersStrip").innerHTML = `<div class="leader-chip" style="cursor:default"><span class="c">TOP SCORERS</span></div>` + leaders.map((l) =>
    `<div class="leader-chip" data-pslug="${esc(l.slug || "")}" data-pname="${esc(l.nickname || l.name || "")}">${img(l.photo_url, l.nickname || l.name, "")}<div><div class="n">${esc(l.nickname || l.name)}</div><div class="c">${esc(l.club_nickname || "")}</div></div><span class="v">${l.stat_value != null ? l.stat_value : ((l.stats || {}).goals || 0)}</span></div>`
  ).join("");
  $$("#leadersStrip .leader-chip[data-pname]").forEach((el) => {
    el.onclick = async () => {
      if (el.dataset.pslug) { openPlayer(el.dataset.pslug); return; }
      try {
        const r = await getJSON("/api/players?q=" + encodeURIComponent(el.dataset.pname) + "&limit=1");
        if (r.players && r.players.length) openPlayer(r.players[0].slug);
        else toast("Player dossier not found");
      } catch (e) { toast("Player dossier not found"); }
    };
  });

  renderMatchday();
}
function renderMatchday() {
  const md = S.shownMd;
  $("#mdNow").textContent = "MD " + md;
  $("#matchdayLabel").textContent = "Matchday " + md + (md === S.currentMd ? " · current" : "") + " · " + S.fixtures.filter((f) => f.matchday === md).length + " fixtures";
  const list = S.fixtures.filter((f) => f.matchday === md);
  if (!list.length) { $("#fixtureGrid").innerHTML = `<div class="empty">No fixtures for matchday ${md}.</div>`; return; }
  $("#fixtureGrid").innerHTML = list.map((f) => {
    const st = f.status === "FINISHED" ? `<span class="pill fin">FT</span>`
      : f.status === "LIVE" ? `<span class="pill live">● LIVE ${f.elapsed ? f.elapsed + "'" : ""}</span>`
      : `<span class="pill sched">${esc((f.kickoff_time || "").slice(0, 10))}</span>`;
    const score = (f.status === "FINISHED" || f.status === "LIVE") ? `${f.home_score} - ${f.away_score}` : "vs";
    return `<div class="fx" data-fid="${f.id}">
      <div class="fx-top">${st}<span>MD ${f.matchday}</span></div>
      <div class="fx-teams">
        <div class="fx-team">${img(f.home_shield, f.home_nickname, "")}<span>${esc(f.home_nickname || f.home_name)}</span></div>
        <div class="fx-score">${score}</div>
        <div class="fx-team">${img(f.away_shield, f.away_nickname, "")}<span>${esc(f.away_nickname || f.away_name)}</span></div>
      </div>
      <div class="fx-foot"><span>Preview · forecast · sim</span><span>→</span></div>
    </div>`;
  }).join("");
  $$("#fixtureGrid .fx").forEach((el) => (el.onclick = () => openMatch(Number(el.dataset.fid))));
}
function initMatchday() {
  $("#mdPrev").onclick = () => { if (S.shownMd > 1) { S.shownMd--; renderMatchday(); } };
  $("#mdNext").onclick = () => { if (S.shownMd < 38) { S.shownMd++; renderMatchday(); } };
  S.shownMd = S.currentMd;
}

/* ---------- radar ---------- */
function radarSVG(axes, a, b, labels) {
  // axes: [{key,label}], a/b: {key:0-100}
  const n = axes.length, R = 78, cx = 95, cy = 88;
  const pt = (i, v) => {
    const ang = (Math.PI * 2 * i) / n - Math.PI / 2;
    const r = (R * Math.max(0, Math.min(100, v))) / 100;
    return [cx + r * Math.cos(ang), cy + r * Math.sin(ang)];
  };
  let grid = "";
  [25, 50, 75, 100].forEach((g) => {
    grid += `<polygon points="${axes.map((_, i) => pt(i, g).join(",")).join(" ")}" fill="none" stroke="currentColor" stroke-opacity=".15"/>`;
  });
  let spokes = "", labs = "";
  axes.forEach((ax, i) => {
    const [x, y] = pt(i, 100);
    spokes += `<line x1="${cx}" y1="${cy}" x2="${x}" y2="${y}" stroke="currentColor" stroke-opacity=".15"/>`;
    const lx = cx + (R + 26) * Math.cos((Math.PI * 2 * i) / n - Math.PI / 2);
    const ly = cy + (R + 26) * Math.sin((Math.PI * 2 * i) / n - Math.PI / 2);
    labs += `<text x="${lx}" y="${ly}" text-anchor="middle" font-size="9" fill="currentColor" opacity=".75">${esc(ax.label)}</text>`;
  });
  const poly = (vals, color, op) =>
    `<polygon points="${axes.map((ax, i) => pt(i, vals[ax.key] || 50).join(",")).join(" ")}" fill="${color}" fill-opacity="${op}" stroke="${color}" stroke-width="2"/>`;
  return `<svg viewBox="0 0 190 180" width="220" height="208">${grid}${spokes}${labs}${b ? poly(b, "#f59e0b", 0.25) : ""}${poly(a, "#00c389", 0.35)}</svg>`;
}

/* ---------- match detail ---------- */
async function openMatch(fid) {
  switchView("match");
  $("#matchDetail").innerHTML = `<div class="skeleton-cards"></div>`;
  try {
    const d = await getJSON("/api/match/" + fid + "?engine=" + (S.engine || "gut"));
    S.match = d; S.forecast = d.forecast || null; S.sim = null;
    renderMatchDetail(d);
  } catch (e) { $("#matchDetail").innerHTML = `<div class="empty">Could not load match.</div>`; }
}
function probCells(fc) {
  return `<div class="probbar"><div class="h" style="flex:${fc.home_win_pct}">1 · ${fc.home_win_pct}%</div><div class="d" style="flex:${fc.draw_pct}">X · ${fc.draw_pct}%</div><div class="a" style="flex:${fc.away_win_pct}">2 · ${fc.away_win_pct}%</div></div>`;
}
function renderMatchDetail(d) {
  const f = d.fixture, h = d.home_team, a = d.away_team;
  const fc = d.forecast || {};
  const isGut = (S.engine || "gut") === "gut";
  const gf = d.gut_feeling || {};
  const activeProbs = (isGut && gf.home_win_pct != null) ? gf : fc;
  const clash = d.tactical_clash || fc.tactical_clash || {};
  const xg = isGut && gf.projected_xg ? gf.projected_xg : (fc.projected_xg || {});
  const sl = (fc.top_scorelines || []).map((s) => `<span class="chip">${esc(s.score)} <b>${s.probability}%</b></span>`).join("");
  const radar = d.tactical_radar
    ? radarSVG(d.tactical_radar.axes, d.tactical_radar.home, d.tactical_radar.away)
    : "";
  const clashHtml = clash.home ? `<div class="kv"><span>${esc(h.name)} shape</span><b>${esc(clash.home.tactical_identity || "")}</b></div>
    <div class="kv"><span>${esc(a.name)} shape</span><b>${esc(clash.away.tactical_identity || "")}</b></div>
    <div class="kv"><span>Possession split</span><b>${clash.expected_possession.home}% – ${clash.expected_possession.away}%</b></div>
    <p class="sub">${esc(clash.key_battle || clash.verdict || "")}</p>` : "";
  const ref = d.referee || (fc.referee || {});
  const refImp = d.referee_impact || (fc.referee_impact || {});
  const refHtml = ref.name ? `
    <div class="card" style="margin-top:.9rem">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.5rem">
        <h2 style="margin:0">👨‍⚖️ Match Official · ${esc(ref.name)} <span style="font-size:1.1rem">${ref.badge_emoji || "⚖️"}</span></h2>
        <span class="chip" style="background:rgba(255,255,255,0.06);font-size:.78rem">${esc(ref.experience_level || "Accredited")}</span>
      </div>
      <div class="kv"><span>Archetype</span><b>${esc(ref.archetype || "Match Referee")}</b></div>
      <div class="kv"><span>Strictness</span><b>${ref.strictness_index || 50}/100 · ${esc(ref.card_hazard || "")}</b></div>
      <div class="kv"><span>Whistle Tendencies</span><b>${ref.fouls_per_game || 25} FPG · ${ref.yellow_cards_per_game || 4.5} YC · ${ref.penalties_per_game || 0.28} PK/g</b></div>
      <div class="kv"><span>Home Whistle Bias</span><b>${ref.home_bias_ratio || 1.0}x away/home foul split</b></div>
      <p class="sub" style="margin-top:.6rem;color:var(--text, #e6edf3)"><b>Tactical Whistle Impact:</b> <i>${esc(refImp.tactical_narrative || ref.bio_summary || "")}</i></p>
    </div>` : "";
  const lineup = (t) => {
    const xi = (t.tactics || {}).starting_xi || [];
    const dots = xi.map((p) => `<div class="pdot" style="left:${p.x}%;top:${p.y}%" title="${esc(p.name)} · ${p.overall_rating}">${"<i>" + esc(p.shirt_number || "?") + "</i>"}${esc((p.nickname || p.name || "").split(" ").slice(-1))}</div>`).join("");
    const list = xi.map((p) => `<div><span>${p.shirt_number || ""} · ${esc(p.nickname || p.name)} <span class="pm">${esc(p.slot || "")}</span></span><b>${p.effective_rating || p.overall_rating}</b></div>`).join("");
    return { dots, list };
  };
  const lh = lineup(h), la = lineup(a);
  $("#matchDetail").innerHTML = `
    <div class="card md-head">
      <div class="fx-top"><span class="pill">${f.status === "FINISHED" ? "FT · " + f.home_score + " - " + f.away_score : "MD " + f.matchday}</span><span>${esc((f.kickoff_time || "").slice(0, 10))}</span></div>
      <div class="md-teams">
        <div class="md-team">${img(h.shield, h.nickname, "")}<span>${esc(h.nickname || h.name)}</span></div>
        <div><div class="md-score">${f.status === "FINISHED" ? f.home_score + " - " + f.away_score : "VS"}</div>
        <div class="md-kick">${esc(h.stadium || "")}</div></div>
        <div class="md-team">${img(a.shield, a.nickname, "")}<span>${esc(a.nickname || a.name)}</span></div>
      </div>
    </div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin:.8rem 0;padding:.5rem .9rem;background:var(--card, #1c2128);border:1px solid var(--border, rgba(255,255,255,0.08));border-radius:10px">
      <span style="font-size:.85rem;font-weight:600">${isGut ? "🔮 Active Engine: <b>Gut Feeling (10k Monte Carlo)</b>" : "📐 Active Engine: <b>Classic Dixon-Coles</b>"}</span>
      <div style="display:flex;gap:.4rem">
        <button class="chip" style="cursor:pointer;background:${isGut ? '#00985f' : 'transparent'};color:${isGut ? '#fff' : 'inherit'}" onclick="setAppEngine('gut')">🔮 Gut Feeling</button>
        <button class="chip" style="cursor:pointer;background:${!isGut ? '#00985f' : 'transparent'};color:${!isGut ? '#fff' : 'inherit'}" onclick="setAppEngine('dixon')">📐 Dixon-Coles</button>
      </div>
    </div>
    <div class="grid2">
      <div class="card"><h2>Win probability <span class="pm">· ${isGut ? "10,000-draw Gut Feeling" : "Dixon-Coles closed-form"}</span></h2>${probCells(activeProbs)}
        <div class="chips"><span class="chip">xG <b>${xg.home ?? "–"} – ${xg.away ?? "–"}</b></span>
        <span class="chip">O2.5 <b>${fc.over_2_5_pct ?? "–"}%</b></span><span class="chip">BTTS <b>${fc.btts_yes_pct ?? "–"}%</b></span></div>
        <h3 style="margin-top:.8rem">Likely scorelines</h3><div class="chips">${sl || "–"}</div>
      </div>
      <div class="card"><h2>Tactical clash</h2>${clashHtml}<div class="radar-wrap">${radar}</div></div>
    </div>
    <div class="grid2">
      <div class="card"><h2>${esc(h.nickname)} · ${esc((h.tactics || {}).formation || "")}</h2>
        <p class="sub">${esc((h.tactics || {}).manager || "")} · ${esc((h.tactics || {}).style || "")}</p>
        <div class="pitch">${lh.dots}</div><div class="xi-list">${lh.list}</div></div>
      <div class="card"><h2>${esc(a.nickname)} · ${esc((a.tactics || {}).formation || "")}</h2>
        <p class="sub">${esc((a.tactics || {}).manager || "")} · ${esc((a.tactics || {}).style || "")}</p>
        <div class="pitch">${la.dots}</div><div class="xi-list">${la.list}</div></div>
    </div>
    ${refHtml}
    <div class="card" style="margin-top:.9rem"><h2>Match simulation</h2>
      <p class="sub">${isGut ? "Gut Feeling 10,000-draw Monte Carlo engine · Stochastic Lognormal-Poisson" : "Deterministic Dixon-Coles engine · Bivariate Poisson"}</p>
      <div style="display:flex;gap:.6rem;margin:.7rem 0"><button class="btn" id="simBtn">Simulate match</button><span class="mono" id="simScore" style="align-self:center"></span></div>
      <div id="simOut"></div>
    </div>`;
  $("#simBtn").onclick = runSim;
}
async function runSim() {
  const btn = $("#simBtn");
  btn.disabled = true; btn.textContent = "Simulating…";
  try {
    const sim = await getJSON("/api/simulate-match/" + S.match.fixture.id + "?engine=" + (S.engine || "gut"));
    S.sim = sim;
    $("#simScore").textContent = sim.home_score + " - " + sim.away_score;
    const ev = (sim.events || []).map((e) =>
      `<div class="tl-row ${e.team === "away" ? "away" : ""}"><span class="tl-min">${e.minute}'</span><span>${esc(e.description || (e.scorer ? "Goal: " + e.scorer : e.type))}</span></div>`
    ).join("");
    const st = sim.stats || {};
    const refSim = sim.referee ? `<div class="kv"><span>Match Official</span><b>${esc(sim.referee.name)} (${sim.referee.strictness_index}/100 strictness)</b></div>` : "";
    const cardSim = st.yellow_cards ? `<div class="kv"><span>Cards</span><b>🟨 ${st.yellow_cards.home} vs ${st.yellow_cards.away}${st.red_cards && (st.red_cards.home || st.red_cards.away) ? ` · 🟥 ${st.red_cards.home} vs ${st.red_cards.away}` : ""}</b></div>` : "";
    $("#simOut").innerHTML = `<div class="grid2"><div><h3>Timeline</h3><div class="timeline">${ev || "No events"}</div></div>
      <div><h3>Stats</h3>
      ${refSim}
      <div class="kv"><span>Possession</span><b>${st.possession ? st.possession.home + "% – " + st.possession.away + "%" : "–"}</b></div>
      <div class="kv"><span>xG</span><b>${st.xg ? st.xg.home + " – " + st.xg.away : "–"}</b></div>
      <div class="kv"><span>Shots (on target)</span><b>${st.shots ? st.shots.home + " (" + st.shots_on_target.home + ") – " + st.shots.away + " (" + st.shots_on_target.away + ")" : "–"}</b></div>
      <div class="kv"><span>Corners</span><b>${st.corners ? st.corners.home + " – " + st.corners.away : "–"}</b></div>
      <div class="kv"><span>Fouls</span><b>${st.fouls ? st.fouls.home + " – " + st.fouls.away : "–"}</b></div>
      ${cardSim}</div></div>`;
  } catch (e) { toast("Simulation failed"); }
  btn.disabled = false; btn.textContent = "Simulate match";
}
window.setAppEngine = function(eng) {
  S.engine = eng;
  localStorage.setItem("statsphere_engine", eng);
  if (S.match && S.match.fixture) {
    openMatch(S.match.fixture.id);
  }
};

/* ---------- players ---------- */
async function loadPlayers() {
  try {
    const [pl, cl] = await Promise.all([getJSON("/api/players?limit=600"), getJSON("/api/clubs")]);
    S.players = pl.players || [];
    S.clubs = (cl.clubs || []).map((x) => x.club || {});
    $("#clubFilter").innerHTML = `<option value="">All clubs</option>` + S.clubs.map((c) => `<option value="${esc(c.slug)}">${esc(c.nickname || c.name)}</option>`).join("");
    renderPlayers();
  } catch (e) { $("#playerGrid").innerHTML = `<div class="empty">Could not load players.</div>`; }
}
function filteredPlayers() {
  const q = $("#playerSearch").value.trim().toLowerCase();
  const pos = $("#posFilter").value, club = $("#clubFilter").value, sort = $("#sortFilter").value;
  let list = S.players.filter((p) =>
    (!q || ((p.nickname || "") + " " + (p.name || "")).toLowerCase().includes(q)) &&
    (!pos || (p.position_name || "") === pos) &&
    (!club || (p.club_slug || "") === club));
  const val = (p) => sort === "overall_rating" ? (p.overall_rating || 0) : ((p.stats || {})[sort] || 0);
  return list.sort((a, b) => val(b) - val(a)).slice(0, 120);
}
function renderPlayers() {
  const list = filteredPlayers();
  $("#playersCount").textContent = list.length + " shown · " + S.players.length + " in database";
  $("#playerGrid").innerHTML = list.map((p) => `
    <div class="pcard ${S.cmpA === p.slug || S.cmpB === p.slug ? "sel" : ""}" data-slug="${esc(p.slug)}">
      <span class="ovr">${p.overall_rating || "–"}</span>
      ${img(p.photo_url || p.cutout_url, p.nickname, "")}
      <div class="pn">${esc(p.nickname || p.name)}</div>
      <div class="pm">${esc(p.club_nickname || "")} · ${esc(p.position_name || "")}</div>
      <div class="pstats"><span>G <b>${(p.stats || {}).goals || 0}</b></span><span>A <b>${(p.stats || {}).assists || 0}</b></span><span class="pm">${esc(p.archetype || "")}</span></div>
    </div>`).join("") || `<div class="empty">No players match.</div>`;
  $$("#playerGrid .pcard").forEach((el) => (el.onclick = () => {
    if (S.compareMode) pickCompare(el.dataset.slug);
    else openPlayer(el.dataset.slug);
  }));
}
function initPlayers() {
  ["playerSearch", "posFilter", "clubFilter", "sortFilter"].forEach((id) => {
    $("#" + id).addEventListener("input", renderPlayers);
    $("#" + id).addEventListener("change", renderPlayers);
  });
  $("#compareToggle").onclick = () => {
    S.compareMode = !S.compareMode;
    $("#compareBar").hidden = !S.compareMode;
    $("#compareToggle").textContent = S.compareMode ? "Done comparing" : "Compare two players";
    if (!S.compareMode) { S.cmpA = S.cmpB = null; $("#h2hPanel").innerHTML = ""; renderPlayers(); }
  };
  $("#cmpClear").onclick = () => { S.cmpA = S.cmpB = null; updCmp(); renderPlayers(); $("#h2hPanel").innerHTML = ""; };
  $("#cmpGo").onclick = async () => {
    try {
      const c = await getJSON(`/api/compare?p1=${encodeURIComponent(S.cmpA)}&p2=${encodeURIComponent(S.cmpB)}`);
      const rows = (c.metrics || []).map((m) => `<tr><td class="${m.advantage === "p1" ? "win" : ""}">${m.player1_value}</td><td class="lbl">${esc(m.label)}</td><td class="${m.advantage === "p2" ? "win" : ""}">${m.player2_value}</td></tr>`).join("");
      const n1 = (c.player1.bio.nickname || c.player1.bio.name), n2 = (c.player2.bio.nickname || c.player2.bio.name);
      $("#h2hPanel").innerHTML = `<div class="card"><h2>${esc(n1)} vs ${esc(n2)}</h2>
        <table class="h2h-table"><tr><th>${esc(n1)}</th><th></th><th>${esc(n2)}</th></tr>${rows}</table>
        <p class="sub">${esc(c.verdict || "")}</p></div>`;
    } catch (e) { toast("Comparison failed"); }
  };
}
function pickCompare(slug) {
  if (S.cmpA === slug) S.cmpA = null;
  else if (S.cmpB === slug) S.cmpB = null;
  else if (!S.cmpA) S.cmpA = slug;
  else if (!S.cmpB) S.cmpB = slug;
  else S.cmpA = slug;
  updCmp(); renderPlayers();
}
function updCmp() {
  const nm = (s) => { const p = S.players.find((x) => x.slug === s); return p ? p.nickname || p.name : null; };
  $("#cmpSlotA").textContent = nm(S.cmpA) || "Pick player A ↓";
  $("#cmpSlotB").textContent = nm(S.cmpB) || "Pick player B ↓";
  $("#cmpGo").disabled = !(S.cmpA && S.cmpB);
}
async function openPlayer(slug) {
  $("#playerModal").hidden = false;
  $("#playerModalBody").innerHTML = `<div class="skeleton-cards"></div>`;
  try {
    const p = await getJSON("/api/players/" + encodeURIComponent(slug));
    const b = p.bio || {}, st = p.stats || {}, sc = p.scores || {};
    const bars = [["Attacking", sc.attacking], ["Playmaking", sc.playmaking], ["Defending", sc.defending], ["Physical", sc.physical_duels], ["Discipline", sc.discipline_reliability]]
      .map(([l, v]) => `<div class="bar-row"><span>${l}</span><div class="tr"><div class="fl" style="width:${v || 0}%"></div></div><b>${v ?? "–"}</b></div>`).join("");
    const radar = radarSVG(
      [{ key: "att", label: "ATT" }, { key: "ply", label: "PLY" }, { key: "def", label: "DEF" }, { key: "phy", label: "PHY" }, { key: "dsc", label: "DSC" }],
      { att: sc.attacking, ply: sc.playmaking, def: sc.defending, phy: sc.physical_duels, dsc: sc.discipline_reliability });
    $("#playerModalBody").innerHTML = `
      <div class="dossier-head">${img(b.photo_url, b.nickname, "")}
        <div><h2>${esc(b.nickname || b.name)}</h2>
        <p class="sub">${esc(b.club_name || "")} · ${esc(b.position_name || "")} ${b.shirt_number ? "#" + b.shirt_number : ""} · <b class="mono">${sc.overall_rating || ""} OVR</b></p>
        <p class="sub">${esc(p.archetype || "")}${p.secondary_archetype ? " · " + esc(p.secondary_archetype) : ""}</p></div></div>
      <div class="grid2"><div><h3>Attributes</h3><div class="bars">${bars}</div></div><div class="radar-wrap">${radar}</div></div>
      <div class="grid2"><div><h3>Season</h3>
        <div class="kv"><span>Apps / minutes</span><b>${st.games_played || 0} / ${st.minutes_played || 0}</b></div>
        <div class="kv"><span>Goals / assists</span><b>${st.goals || 0} / ${st.assists || 0}</b></div>
        <div class="kv"><span>Shots (on target)</span><b>${st.shots || 0} (${st.shots_on_target || 0})</b></div>
        <div class="kv"><span>Key passes</span><b>${st.key_passes || 0}</b></div>
        <div class="kv"><span>Tackles won</span><b>${st.tackles_won || 0}</b></div>
        <div class="kv"><span>Cards Y/R</span><b>${st.yellow_cards || 0}/${st.red_cards || 0}</b></div></div>
        <div><h3>Scout report</h3><ul class="scout">${(p.strengths || []).map((s) => `<li>✔ ${esc(s)}</li>`).join("")}${(p.weaknesses || []).map((w) => `<li>✖ ${esc(w)}</li>`).join("")}</ul></div></div>`;
  } catch (e) { $("#playerModalBody").innerHTML = `<div class="empty">Player not found.</div>`; }
}

/* ---------- clubs ---------- */
async function loadClubs() {
  try {
    const c = await getJSON("/api/clubs");
    S.clubs = c.clubs || [];
    renderClubs();
  } catch (e) { $("#clubGrid").innerHTML = `<div class="empty">Could not load clubs.</div>`; }
}
function renderClubs() {
  $("#clubGrid").innerHTML = S.clubs.map((x) => {
    const m = x.club || {}, s = x.scores || {};
    return `<div class="card ccard ${S.clubA === m.slug || S.clubB === m.slug ? "sel" : ""}" data-slug="${esc(m.slug)}">
      ${img(m.shield_url, m.nickname, "")}
      <div><div class="cn">${esc(m.nickname || m.name)}</div>
      <div class="cm">#${m.position || "–"} · ${m.points || 0} pts · OVR ${s.overall_rating || "–"}</div>
      <div class="cm">${esc(x.archetype || "")}</div></div></div>`;
  }).join("");
  $$("#clubGrid .ccard").forEach((el) => (el.onclick = () => {
    if (S.clubCompareMode) pickClub(el.dataset.slug);
    else openClub(el.dataset.slug);
  }));
}
function initClubs() {
  $("#clubCompareToggle").onclick = () => {
    S.clubCompareMode = !S.clubCompareMode;
    $("#clubCompareBar").hidden = !S.clubCompareMode;
    $("#clubCompareToggle").textContent = S.clubCompareMode ? "Done comparing" : "Compare two clubs";
    if (!S.clubCompareMode) { S.clubA = S.clubB = null; $("#clubH2h").innerHTML = ""; renderClubs(); }
  };
  $("#clubCmpClear").onclick = () => { S.clubA = S.clubB = null; updClubCmp(); renderClubs(); $("#clubH2h").innerHTML = ""; };
  $("#clubCmpGo").onclick = async () => {
    try {
      const c = await getJSON(`/api/compare-clubs?c1=${encodeURIComponent(S.clubA)}&c2=${encodeURIComponent(S.clubB)}`);
      const rows = (c.metrics || []).map((m) => `<tr><td class="${m.advantage === "c1" ? "win" : ""}">${m.club1_value}</td><td class="lbl">${esc(m.label)}</td><td class="${m.advantage === "c2" ? "win" : ""}">${m.club2_value}</td></tr>`).join("");
      $("#clubH2h").innerHTML = `<div class="card"><h2>${esc(c.club1.meta.nickname)} vs ${esc(c.club2.meta.nickname)}</h2>
        <table class="h2h-table">${rows}</table><p class="sub">${esc(c.verdict || "")}</p></div>`;
    } catch (e) { toast("Comparison failed"); }
  };
}
function pickClub(slug) {
  if (S.clubA === slug) S.clubA = null;
  else if (S.clubB === slug) S.clubB = null;
  else if (!S.clubA) S.clubA = slug;
  else if (!S.clubB) S.clubB = slug;
  else S.clubA = slug;
  updClubCmp(); renderClubs();
}
function updClubCmp() {
  const nm = (s) => { const x = S.clubs.find((c) => (c.club || {}).slug === s); return x ? x.club.nickname || x.club.name : null; };
  $("#clubSlotA").textContent = nm(S.clubA) || "Pick club A ↓";
  $("#clubSlotB").textContent = nm(S.clubB) || "Pick club B ↓";
  $("#clubCmpGo").disabled = !(S.clubA && S.clubB);
}
async function openClub(slug) {
  $("#clubModal").hidden = false;
  $("#clubModalBody").innerHTML = `<div class="skeleton-cards"></div>`;
  try {
    const x = await getJSON("/api/clubs/" + encodeURIComponent(slug));
    const m = x.club || {}, s = x.scores || {}, st = x.stats || {};
    const bars = [["Attack", s.att_rating], ["Midfield", s.mid_rating], ["Defense", s.def_rating], ["Possession", s.possession_control], ["Pressing", s.pressing_workrate]]
      .map(([l, v]) => `<div class="bar-row"><span>${l}</span><div class="tr"><div class="fl" style="width:${v || 0}%"></div></div><b>${v ?? "–"}</b></div>`).join("");
    const lead = (t, l) => t ? `<div class="kv"><span>${l}</span><b>${esc(t.name)} (${esc(t.stat_val ?? t.overall_rating ?? "")})</b></div>` : "";
    $("#clubModalBody").innerHTML = `
      <div class="dossier-head">${img(m.shield_url, m.nickname, "")}
        <div><h2>${esc(m.nickname || m.name)}</h2>
        <p class="sub">#${m.position || "–"} · ${m.points || 0} pts (${m.won || 0}W-${m.drawn || 0}D-${m.lost || 0}L) · <b class="mono">${s.overall_rating || ""} OVR</b></p>
        <p class="sub">${esc(x.archetype || "")}</p></div></div>
      <div class="grid2"><div><h3>Ratings</h3><div class="bars">${bars}</div></div>
      <div><h3>Key men</h3>${lead(x.top_scorer, "Top scorer")}${lead(x.top_assister, "Playmaker")}${lead(x.defensive_leader, "Anchor")}${lead(x.star_player, "Star") || "<p class='sub'>–</p>"}
      <h3 style="margin-top:.7rem">Scout notes</h3><ul class="scout">${(x.strengths || []).slice(0, 3).map((t) => `<li>✔ ${esc(t)}</li>`).join("")}${(x.weaknesses || []).slice(0, 2).map((t) => `<li>✖ ${esc(t)}</li>`).join("")}</ul></div></div>`;
  } catch (e) { $("#clubModalBody").innerHTML = `<div class="empty">Club not found.</div>`; }
}

/* ---------- table ---------- */
async function loadTable() {
  try {
    const t = await getJSON("/api/standings");
    S.standings = t.standings || [];
    const qual = (q) => (q || "").toLowerCase();
    $("tbody", $("#standingsTable")).innerHTML = S.standings.map((c) => {
      const q = qual(c.qualification);
      const z = q.includes("champion") ? "z-ucl" : q.includes("europa") ? "z-uel" : q.includes("releg") ? "z-rel"
        : c.position <= 4 ? "z-ucl" : c.position === 5 ? "z-uel" : c.position >= 18 ? "z-rel" : "";
      const gd = (c.goal_difference || 0) > 0 ? "+" + c.goal_difference : c.goal_difference;
      return `<tr data-slug="${esc(c.slug)}"><td class="${z}">${c.position}</td>
        <td><span class="teamcell">${img(c.shield_url, c.nickname, "")}${esc(c.nickname || c.name)}</span></td>
        <td>${c.played}</td><td>${c.won}</td><td>${c.drawn}</td><td>${c.lost}</td><td>${gd}</td><td><b>${c.points}</b></td><td>${c.overall_rating || "–"}</td></tr>`;
    }).join("");
    $$("#standingsTable tbody tr").forEach((el) => (el.onclick = () => openClub(el.dataset.slug)));
    $("#tableSub").textContent = S.standings.length + " teams · official standings";
  } catch (e) { }
}

/* ---------- boot ---------- */
document.addEventListener("DOMContentLoaded", () => {
  initChrome(); initSearch(); initMatchday(); initPlayers(); initClubs();
  S.shownMd = 1;
  loadMatches().then(() => { S.shownMd = S.currentMd; renderMatchday(); });
});
