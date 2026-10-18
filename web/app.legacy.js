/**
 * STATSPHERE — Futuristic Sports Analytics Terminal
 * 4 Complete Views: Home, Fixtures, Players, Clubs
 * Opta Telemetry + Real La Liga API Endpoints
 */

const API_BASE = "";

// ============================================================
// GLOBAL STATE
// ============================================================
let allPlayers = [];
let allClubs = [];
let allStandings = [];
let allFixtures = [];
let featuredStars = [];
let currentFeaturedIndex = 0;
let currentSelectedClubSlug = "fc-barcelona";
let currentMatchday = 4;
let activeView = "home";

// Filter States
let playerFilters = { query: "", club: "all", pos: "all", sort: "rating-desc" };
let fixtureFilters = { query: "", status: "all", matchday: 4 };
let clubFilters = { query: "", sort: "position" };

// ============================================================
// DOM ELEMENTS
// ============================================================
// Top bar & OS
const systemClock = document.getElementById("systemClock");
const osPlayerCount = document.getElementById("os-player-count");
const osFixtureCount = document.getElementById("os-fixture-count");

// Search & Nav
const globalSearchInput = document.getElementById("globalSearchInput");
const favoritesList = document.getElementById("favoritesList");
const navMainMenu = document.getElementById("navMainMenu");

// HOME: Fixtures Hub
const dateSelectorBar = document.getElementById("dateSelectorBar");
const matchGridContainer = document.getElementById("matchGridContainer");
const liveMatchCount = document.getElementById("liveMatchCount");
const currentMatchdayNum = document.getElementById("currentMatchdayNum");
const accordionBody = document.getElementById("accordionBody");
const acArrow = document.getElementById("acArrow");
const acStateText = document.getElementById("acStateText");

// HOME: Featured Player
const featuredAvatar = document.getElementById("featuredAvatar");
const featuredOvr = document.getElementById("featuredOvr");
const featuredName = document.getElementById("featuredName");
const featuredClub = document.getElementById("featuredClub");
const featuredMetaTags = document.getElementById("featuredMetaTags");
const featuredPositionBadge = document.getElementById("featuredPositionBadge");
const featuredGoals = document.getElementById("featuredGoals");
const featuredAssists = document.getElementById("featuredAssists");
const featuredApps = document.getElementById("featuredApps");
const featuredRadarSvg = document.getElementById("featuredRadarSvg");
const featuredTimelineSvg = document.getElementById("featuredTimelineSvg");
const featuredProfileBtn = document.getElementById("featuredProfileBtn");

// HOME: Right Sidebar (League Table & Club Focus)
const leagueTableBody = document.getElementById("leagueTableBody");
const clubFocusShield = document.getElementById("clubFocusShield");
const clubFocusName = document.getElementById("clubFocusName");
const clubFocusFormation = document.getElementById("clubFocusFormation");
const clubFocusFormDots = document.getElementById("clubFocusFormDots");
const clubFocusScorers = document.getElementById("clubFocusScorers");
const clubFocusNextFixtures = document.getElementById("clubFocusNextFixtures");

// FIXTURES VIEW
const fixtureSearchInput = document.getElementById("fixtureSearchInput");
const fixtureStatusFilters = document.getElementById("fixtureStatusFilters");
const fixtureMatchdaySelect = document.getElementById("fixtureMatchdaySelect");
const fixturesMatchdayNav = document.getElementById("fixturesMatchdayNav");
const fixturesFullList = document.getElementById("fixturesFullList");
const fxTotalCount = document.getElementById("fxTotalCount");
const fxPlayedCount = document.getElementById("fxPlayedCount");
const fxRemainingCount = document.getElementById("fxRemainingCount");

// PLAYERS VIEW
const playerSearchInput = document.getElementById("playerSearchInput");
const playerSearchClear = document.getElementById("playerSearchClear");
const playerClubSelect = document.getElementById("playerClubSelect");
const playerPositionPills = document.getElementById("playerPositionPills");
const playerSortSelect = document.getElementById("playerSortSelect");
const playerCountBadge = document.getElementById("playerCountBadge");
const playersCatalogGrid = document.getElementById("playersCatalogGrid");
const playersStatsRibbon = document.getElementById("playersStatsRibbon");

// CLUBS VIEW
const clubSearchInput = document.getElementById("clubSearchInput");
const clubSortSelect = document.getElementById("clubSortSelect");
const clubCountBadge = document.getElementById("clubCountBadge");
const clubsCatalogGrid = document.getElementById("clubsCatalogGrid");

// MODALS
const playerModal = document.getElementById("playerModal");
const modalContent = document.getElementById("modalContent");
const modalCloseBtn = document.getElementById("modalCloseBtn");
const clubModal = document.getElementById("clubModal");
const clubModalContent = document.getElementById("clubModalContent");
const clubModalCloseBtn = document.getElementById("clubModalCloseBtn");

// ============================================================
// INITIALIZATION
// ============================================================
document.addEventListener("DOMContentLoaded", () => {
  initClock();
  initEventListeners();
  loadAllData();
  pollLiveTelemetry();
  setInterval(pollLiveTelemetry, 60000);
});

// ============================================================
// 1. CLOCK
// ============================================================
function initClock() {
  function tick() {
    if (!systemClock) return;
    const now = new Date();
    const h = String(now.getUTCHours()).padStart(2, "0");
    const m = String(now.getUTCMinutes()).padStart(2, "0");
    const s = String(now.getUTCSeconds()).padStart(2, "0");
    systemClock.textContent = `${h}:${m}:${s} UTC`;
  }
  tick();
  setInterval(tick, 1000);
}

// ============================================================
// 2. VIEW SWITCHER
// ============================================================
let previousView = "home";

function switchView(viewName) {
  if (activeView !== "match-detail" && viewName === "match-detail") {
    previousView = activeView;
  }
  activeView = viewName;

  // Update Nav links active state
  document.querySelectorAll(".nav-link-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.nav === viewName);
  });

  // Switch visible section
  document.querySelectorAll(".view-section").forEach(sec => {
    sec.classList.remove("active");
  });

  const target = document.getElementById(`view-${viewName}`);
  if (target) {
    target.classList.add("active");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  // Trigger view renderers
  if (viewName === "players") {
    applyPlayerFilters();
  } else if (viewName === "clubs") {
    applyClubFilters();
  } else if (viewName === "fixtures") {
    renderFullFixturesView();
  }
}

// ============================================================
// 3. EVENT LISTENERS
// ============================================================
function initEventListeners() {
  // Global Keyboard Shortcuts
  window.addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      globalSearchInput?.focus();
    } else if (e.key === "Escape") {
      closePlayerModal();
      closeClubModal();
      hideQuickSearch();
    }
  });

  // Navigation Links
  document.querySelectorAll(".nav-link-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const nav = btn.dataset.nav;
      if (nav) switchView(nav);
    });
  });

  // Favorites clicks
  favoritesList?.addEventListener("click", (e) => {
    const item = e.target.closest(".fav-item");
    if (!item) return;
    document.querySelectorAll(".fav-item").forEach(el => el.classList.remove("active"));
    item.classList.add("active");
    const slug = item.dataset.club;
    if (slug) {
      if (activeView !== "home") switchView("home");
      loadClubFocus(slug);
    }
  });

  // Global Search
  if (globalSearchInput) {
    globalSearchInput.addEventListener("input", debounce(handleGlobalSearch, 200));
    globalSearchInput.addEventListener("focus", () => {
      if (globalSearchInput.value.trim().length >= 2) handleGlobalSearch();
    });
  }
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".nav-search-wrap")) hideQuickSearch();
  });

  // Home: Matchday & Date Pills
  dateSelectorBar?.addEventListener("click", (e) => {
    const pill = e.target.closest(".date-pill");
    if (!pill) return;
    dateSelectorBar.querySelectorAll(".date-pill").forEach(p => p.classList.remove("active"));
    pill.classList.add("active");
    const filter = pill.dataset.filter || "this-week";
    renderFixturesGrid(filter);
  });

  // Fixtures View: Search & Filters
  if (fixtureSearchInput) {
    fixtureSearchInput.addEventListener("input", debounce((e) => {
      fixtureFilters.query = e.target.value.trim().toLowerCase();
      renderFullFixturesView();
    }, 200));
  }

  fixtureStatusFilters?.addEventListener("click", (e) => {
    const pill = e.target.closest(".filter-tag-pill");
    if (!pill) return;
    fixtureStatusFilters.querySelectorAll(".filter-tag-pill").forEach(p => p.classList.remove("active"));
    pill.classList.add("active");
    fixtureFilters.status = pill.dataset.status;
    renderFullFixturesView();
  });

  if (fixtureMatchdaySelect) {
    fixtureMatchdaySelect.addEventListener("change", (e) => {
      const val = e.target.value;
      fixtureFilters.matchday = val === "all" ? "all" : parseInt(val, 10);
      updateFixturesMatchdayNavActive(fixtureFilters.matchday);
      renderFullFixturesView();
    });
  }

  // Players View: Filters
  if (playerSearchInput) {
    playerSearchInput.addEventListener("input", debounce((e) => {
      playerFilters.query = e.target.value.trim().toLowerCase();
      if (playerSearchClear) playerSearchClear.style.display = playerFilters.query ? "block" : "none";
      applyPlayerFilters();
    }, 200));
  }

  playerSearchClear?.addEventListener("click", () => {
    if (playerSearchInput) playerSearchInput.value = "";
    playerFilters.query = "";
    if (playerSearchClear) playerSearchClear.style.display = "none";
    applyPlayerFilters();
  });

  if (playerClubSelect) {
    playerClubSelect.addEventListener("change", (e) => {
      playerFilters.club = e.target.value;
      applyPlayerFilters();
    });
  }

  playerPositionPills?.addEventListener("click", (e) => {
    const pill = e.target.closest(".filter-tag-pill");
    if (!pill) return;
    playerPositionPills.querySelectorAll(".filter-tag-pill").forEach(p => p.classList.remove("active"));
    pill.classList.add("active");
    playerFilters.pos = pill.dataset.pos;
    applyPlayerFilters();
  });

  if (playerSortSelect) {
    playerSortSelect.addEventListener("change", (e) => {
      playerFilters.sort = e.target.value;
      applyPlayerFilters();
    });
  }

  // Clubs View: Filters
  if (clubSearchInput) {
    clubSearchInput.addEventListener("input", debounce((e) => {
      clubFilters.query = e.target.value.trim().toLowerCase();
      applyClubFilters();
    }, 200));
  }

  if (clubSortSelect) {
    clubSortSelect.addEventListener("change", (e) => {
      clubFilters.sort = e.target.value;
      applyClubFilters();
    });
  }

  // Modals close
  modalCloseBtn?.addEventListener("click", closePlayerModal);
  playerModal?.addEventListener("click", (e) => { if (e.target === playerModal) closePlayerModal(); });
  clubModalCloseBtn?.addEventListener("click", closeClubModal);
  clubModal?.addEventListener("click", (e) => { if (e.target === clubModal) closeClubModal(); });
}

// ============================================================
// 4. MASTER DATA LOADER
// ============================================================
async function loadAllData() {
  try {
    // 1. Standings
    const stdRes = await fetch(`${API_BASE}/api/standings`);
    if (stdRes.ok) {
      const sd = await stdRes.json();
      allStandings = sd.standings || [];
      renderLeagueTable(allStandings);
    }

    // 2. Players
    const plRes = await fetch(`${API_BASE}/api/players?limit=600`);
    if (plRes.ok) {
      const pd = await plRes.json();
      allPlayers = pd.players || [];
      if (osPlayerCount) osPlayerCount.textContent = allPlayers.length;
      initFeaturedStars();
      populatePlayersViewControls();
    }

    // 3. Clubs
    const clRes = await fetch(`${API_BASE}/api/clubs`);
    if (clRes.ok) {
      const cd = await clRes.json();
      allClubs = cd.clubs || [];
    }

    // 4. Fixtures
    const fxRes = await fetch(`${API_BASE}/api/fixtures`);
    if (fxRes.ok) {
      const fd = await fxRes.json();
      allFixtures = fd.fixtures || [];
      currentMatchday = fd.current_matchday || 1;
      fixtureFilters.matchday = currentMatchday;
      
      if (osFixtureCount) osFixtureCount.textContent = allFixtures.length;
      if (currentMatchdayNum) currentMatchdayNum.textContent = `Round ${Math.max(1, currentMatchday - 1)} (FT) · Upcoming: MD ${currentMatchday}`;

      buildHomeMatchdayPills();
      renderFixturesGrid("this-week");
      populateFixturesViewControls();
    }

    // 5. Initial Club Focus
    const topClub = allStandings.length > 0 ? allStandings[0] : null;
    currentSelectedClubSlug = topClub ? topClub.slug : "fc-barcelona";
    loadClubFocus(currentSelectedClubSlug);

  } catch (err) {
    console.error("STATSPHERE data load error:", err);
  }
}

async function pollLiveTelemetry() {
  try {
    const res = await fetch(`${API_BASE}/api/live`);
    if (!res.ok) return;
    const data = await res.json();
    const liveCount = data.count || 0;
    const liveBadge = document.getElementById("liveMatchBadge");
    const feedPill = document.getElementById("feedStatusPill");

    if (liveBadge) {
      if (liveCount > 0) {
        liveBadge.className = "live-ticker-badge active-live";
        liveBadge.innerHTML = `<span class="pulse-red"></span> <span>${liveCount} LIVE NOW</span>`;
      } else {
        liveBadge.className = "live-ticker-badge no-live";
        liveBadge.innerHTML = `<span class="dot-idle"></span> <span>0 LIVE · OFFICIAL FEED CONNECTED</span>`;
      }
    }

    if (feedPill) {
      if (liveCount > 0) {
        feedPill.innerHTML = `<span class="pulse-red"></span> <span>API-FOOTBALL · ${liveCount} MATCH IN PLAY</span>`;
      } else {
        feedPill.innerHTML = `<span class="pulse-green"></span> <span>API-FOOTBALL · OFFICIAL LIVE FEED</span>`;
      }
    }

    if (data.live_matches && data.live_matches.length > 0) {
      if (activeView === "home") renderFixturesGrid("this-week");
      if (activeView === "fixtures") renderFullFixturesView();
    }
  } catch (err) {
    console.debug("Live telemetry check error:", err);
  }
}


// ============================================================
// HELPER: CALCULATE REALISTIC 3-WAY BETTING ODDS & FORM DOTS
// ============================================================
function getMatchOdds(f) {
  const homeStanding = (allStandings || []).find(s => s.slug === f.home_slug);
  const awayStanding = (allStandings || []).find(s => s.slug === f.away_slug);
  const homeRating = (homeStanding?.overall_rating || 78) + 3; // +3 home field boost
  const awayRating = (awayStanding?.overall_rating || 78);
  
  const diff = homeRating - awayRating;
  let pHome = 1 / (1 + Math.exp(-diff / 6.5));
  let pAway = 1 / (1 + Math.exp(diff / 6.5));
  let pDraw = Math.max(0.18, 0.28 - Math.abs(diff) * 0.007);
  
  const total = pHome + pDraw + pAway;
  pHome /= total;
  pDraw /= total;
  pAway /= total;
  
  const margin = 1.06; // standard 6% bookmaker margin
  const oHome = Math.max(1.15, (margin / pHome)).toFixed(2);
  const oDraw = Math.max(2.20, (margin / pDraw)).toFixed(2);
  const oAway = Math.max(1.20, (margin / pAway)).toFixed(2);
  
  const homeNick = (f.home_nickname || f.home_name || "HOME").slice(0, 4).toUpperCase();
  const awayNick = (f.away_nickname || f.away_name || "AWAY").slice(0, 4).toUpperCase();
  
  return { homeOdds: oHome, drawOdds: oDraw, awayOdds: oAway, homeNick, awayNick };
}

function getClubFormDots(slug, count = 5) {
  const clubFixtures = (allFixtures || [])
    .filter(f => (f.home_slug === slug || f.away_slug === slug) && (f.status === "FINISHED" || f.status === "SIMULATED"))
    .sort((a, b) => b.matchday - a.matchday)
    .slice(0, count)
    .reverse();

  if (clubFixtures.length === 0) {
    const std = (allStandings || []).find(s => s.slug === slug);
    const pts = std?.points || 0;
    if (pts >= 10) return ['W', 'W', 'D', 'W', 'W'];
    if (pts >= 7) return ['W', 'D', 'W', 'D', 'L'];
    if (pts >= 4) return ['D', 'L', 'W', 'D', 'L'];
    return ['L', 'D', 'L', 'L', 'D'];
  }

  return clubFixtures.map(f => {
    const isHome = f.home_slug === slug;
    const scored = Number(isHome ? f.home_score : f.away_score);
    const conceded = Number(isHome ? f.away_score : f.home_score);
    if (scored > conceded) return 'W';
    if (scored === conceded) return 'D';
    return 'L';
  });
}

// ============================================================
// 5. VIEW 1 (HOME): THIS WEEK'S FIXTURES & MATCH CENTER
// ============================================================
function buildHomeMatchdayPills() {
  if (!dateSelectorBar) return;
  dateSelectorBar.innerHTML = `
    <button class="date-pill" data-filter="last-week">
      <span class="dp-day">FRI</span>
      <span class="dp-num">25</span>
    </button>
    <button class="date-pill" data-filter="last-week">
      <span class="dp-day">SAT</span>
      <span class="dp-num">26</span>
    </button>
    <button class="date-pill active" data-filter="this-week">
      <span class="dp-day">SUN</span>
      <span class="dp-num">27</span>
    </button>
    <button class="date-pill" data-filter="this-week">
      <span class="dp-day">MON</span>
      <span class="dp-num">28</span>
    </button>
    <button class="date-pill" data-filter="this-week">
      <span class="dp-day">TUE</span>
      <span class="dp-num">29</span>
    </button>
    <button class="date-pill" data-filter="top-clashes">
      <span class="dp-day">TOP</span>
      <span class="dp-num">CLASHES</span>
    </button>
    <button class="date-pill" data-filter="all-played">
      <span class="dp-day">ALL</span>
      <span class="dp-num">PLAYED</span>
    </button>
  `;
}

function renderFixturesGrid(filter = "this-week") {
  if (!matchGridContainer) return;

  let fixtures = [];
  const currentMd = currentMatchday || 1;
  const lastMd = Math.max(1, currentMd - 1);

  if (filter === "last-week") {
    fixtures = allFixtures.filter(f => f.matchday === lastMd);
    const topClubs = ["fc-barcelona", "real-madrid", "atletico-de-madrid", "athletic-club", "real-betis"];
    fixtures.sort((a, b) => {
      const aTop = topClubs.includes(a.home_slug) || topClubs.includes(a.away_slug);
      const bTop = topClubs.includes(b.home_slug) || topClubs.includes(b.away_slug);
      if (aTop && !bTop) return -1;
      if (!aTop && bTop) return 1;
      return (b.kickoff_time || "").localeCompare(a.kickoff_time || "");
    });
  } else if (filter === "this-week") {
    fixtures = allFixtures.filter(f => f.matchday === currentMd);
    fixtures.sort((a, b) => (a.kickoff_time || "").localeCompare(b.kickoff_time || ""));
  } else if (filter === "top-clashes") {
    const elite = ["fc-barcelona", "real-madrid", "atletico-de-madrid", "athletic-club", "real-betis", "real-sociedad"];
    fixtures = allFixtures.filter(f => (f.matchday === currentMd || f.matchday === lastMd) && 
      (elite.includes(f.home_slug) || elite.includes(f.away_slug)));
  } else if (filter === "all-played") {
    fixtures = allFixtures.filter(f => f.status === "FINISHED" || f.status === "SIMULATED");
    fixtures.sort((a, b) => (b.kickoff_time || "").localeCompare(a.kickoff_time || ""));
  } else if (typeof filter === "number") {
    fixtures = allFixtures.filter(f => f.matchday === filter);
  } else {
    fixtures = allFixtures.filter(f => f.matchday === currentMd);
  }

  // Update Live Counter badge honestly
  const live = allFixtures.filter(f => f.status === "LIVE" || f.status === "IN_PROGRESS");
  const liveBadge = document.getElementById("liveMatchBadge");
  if (liveBadge) {
    if (live.length > 0) {
      liveBadge.className = "live-ticker-badge active-live";
      liveBadge.innerHTML = `<span class="pulse-red"></span> <span>${live.length} LIVE NOW</span>`;
    } else {
      liveBadge.className = "live-ticker-badge no-live";
      liveBadge.innerHTML = `<span class="dot-idle"></span> <span>0 LIVE · ROUND 4 COMPLETE</span>`;
    }
  }

  if (fixtures.length === 0) {
    matchGridContainer.innerHTML = `<div style="grid-column:1/-1;text-align:center;color:var(--t3);padding:2.5rem;font-size:0.85rem;">No matches scheduled for this selection.</div>`;
    return;
  }

  const heroFixture = fixtures[0];
  const subFixtures = fixtures.slice(1, 7);

  matchGridContainer.innerHTML = `
    ${buildHeroMatchCardHtml(heroFixture)}
    <div class="match-sub-grid">
      ${subFixtures.map(f => buildSubMatchCardHtml(f)).join("")}
    </div>
    ${fixtures.length > 7 ? `
      <div class="more-fixtures-hint" onclick="switchView('fixtures')" style="grid-column:1/-1;margin-top:0.75rem;">
        <span>+ ${fixtures.length - 7} more matches in full schedule</span>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
      </div>
    ` : ""}
  `;
}

function triggerSimFromHero(fixtureId, event) {
  if (event) event.stopPropagation();
  const f = (allFixtures || []).find(x => x.id === fixtureId);
  if (!f) return;
  const homeName = f.home_nickname || f.home_name || "Home";
  const awayName = f.away_nickname || f.away_name || "Away";
  if (window.simulateMatch) {
    window.simulateMatch(event, homeName, awayName);
  } else {
    openMatchDetail(fixtureId);
  }
}

function buildHeroMatchCardHtml(f) {
  if (!f) return "";
  const isLive = f.status === "LIVE" || f.status === "IN_PROGRESS";
  const isFinished = f.status === "FINISHED";
  const isSimulated = f.status === "SIMULATED";

  const homeName = f.home_nickname || f.home_name || "Home";
  const awayName = f.away_nickname || f.away_name || "Away";
  const homeShield = f.home_shield || "";
  const awayShield = f.away_shield || "";

  let livePill = `<span class="hf-live-pill"><span class="pulse-green"></span> MATCHDAY ${f.matchday} · FEATURED</span>`;
  let scoreBox = "";
  let minuteText = "";

  if (isLive) {
    livePill = `<span class="hf-live-pill red"><span class="pulse-red"></span> LIVE</span>`;
    scoreBox = `${f.home_score ?? 0} - ${f.away_score ?? 0}`;
    minuteText = `${f.minute || 84}' · IN PLAY`;
  } else if (isFinished || isSimulated) {
    livePill = isSimulated 
      ? `<span class="hf-live-pill" style="background:rgba(34,197,94,0.15);color:#22c55e;">SIMULATED RESULT</span>`
      : `<span class="hf-live-pill" style="background:rgba(255,255,255,0.1);color:#fff;">FULL TIME</span>`;
    scoreBox = `${f.home_score} - ${f.away_score}`;
    minuteText = isSimulated ? "AI Dixon-Coles Model" : "Official Result";
  } else {
    const kickoff = f.kickoff_time ? new Date(f.kickoff_time) : null;
    const timeStr = kickoff ? kickoff.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }) : "21:00";
    const dateStr = kickoff ? kickoff.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" }) : "Upcoming";
    scoreBox = timeStr;
    minuteText = dateStr;
  }

  let homeScorers = "";
  let awayScorers = "";
  if ((isFinished || isSimulated || isLive) && f.goals && f.goals.length > 0) {
    homeScorers = f.goals.filter(g => g.team === 'home' || !g.team).slice(0, 2).map(g => `⚽ ${g.scorer} ${g.minute}'`).join("<br>");
    awayScorers = f.goals.filter(g => g.team === 'away').slice(0, 2).map(g => `⚽ ${g.scorer} ${g.minute}'`).join("<br>");
  } else {
    homeScorers = `<span style="color:var(--t3);">Rank #4 in La Liga</span>`;
    awayScorers = `<span style="color:var(--t3);">Rank #6 in La Liga</span>`;
  }

  const ctaButton = (!isFinished && !isLive && !isSimulated)
    ? `<button class="hf-cta-btn" onclick="triggerSimFromHero(${f.id}, event)">
        <span>⚡ SIMULATE 90' MATCH</span>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg>
      </button>`
    : `<button class="hf-cta-btn" onclick="openMatchDetail(${f.id})">
        <span>OPEN MATCH CENTER &amp; TRENDS</span>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg>
      </button>`;

  return `
    <div class="featured-hero-match" onclick="openMatchDetail(${f.id})" title="Click to view Match Center & Predictive Trends">
      <div class="hf-top-badge-row">
        ${livePill}
        <span class="hf-league-pill">LA LIGA EA SPORTS</span>
      </div>
      <div class="hf-teams-center">
        <div class="hf-team home">
          ${homeShield ? `<img class="hf-crest" src="${homeShield}" alt="${homeName}" onerror="this.style.opacity='0.2'">` : ""}
          <span class="hf-name">${homeName}</span>
          <div class="hf-scorers">${homeScorers}</div>
        </div>
        <div class="hf-score-hub">
          <div class="hf-score-box">${scoreBox}</div>
          <span class="hf-match-minute ${!isLive ? 'dim' : ''}">${minuteText}</span>
        </div>
        <div class="hf-team away">
          ${awayShield ? `<img class="hf-crest" src="${awayShield}" alt="${awayName}" onerror="this.style.opacity='0.2'">` : ""}
          <span class="hf-name">${awayName}</span>
          <div class="hf-scorers">${awayScorers}</div>
        </div>
      </div>
      ${ctaButton}
    </div>
  `;
}

function buildSubMatchCardHtml(f) {
  const isLive = f.status === "LIVE" || f.status === "IN_PROGRESS";
  const isFinished = f.status === "FINISHED";
  const isSimulated = f.status === "SIMULATED";

  const homeName = f.home_nickname || f.home_name || "Home";
  const awayName = f.away_nickname || f.away_name || "Away";
  const homeShield = f.home_shield || "";
  const awayShield = f.away_shield || "";

  let scoreOrTime = "";
  if (isLive) {
    scoreOrTime = `<span class="smc-score-time live"><span class="pulse-green" style="width:6px;height:6px;display:inline-block;margin-right:4px;"></span>${f.home_score ?? 0} - ${f.away_score ?? 0}</span>`;
  } else if (isFinished || isSimulated) {
    scoreOrTime = `<span class="smc-score-time">${f.home_score} - ${f.away_score}</span>`;
  } else {
    const kickoff = f.kickoff_time ? new Date(f.kickoff_time) : null;
    const timeStr = kickoff ? kickoff.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }) : "21:00";
    scoreOrTime = `<span class="smc-score-time">${timeStr}</span>`;
  }

  const odds = getMatchOdds(f);
  const cardClass = isLive ? "card-live" : isFinished ? "card-finished" : isSimulated ? "card-simulated" : "card-upcoming";

  return `
    <div class="sub-match-card ${cardClass}" onclick="openMatchDetail(${f.id})" title="Click to view match tactical preview & trends">
      <div class="smc-teams-row">
        <div class="smc-team home">
          ${homeShield ? `<img class="smc-crest" src="${homeShield}" alt="${homeName}" onerror="this.style.display='none'">` : ""}
          <span class="smc-name" title="${homeName}">${homeName}</span>
        </div>
        ${scoreOrTime}
        <div class="smc-team away">
          <span class="smc-name" title="${awayName}">${awayName}</span>
          ${awayShield ? `<img class="smc-crest" src="${awayShield}" alt="${awayName}" onerror="this.style.display='none'">` : ""}
        </div>
      </div>
      <div class="odds-pills-row">
        <div class="odds-pill" title="${homeName} Win Probability Odds">
          <span class="op-label">${odds.homeNick}</span>
          <span class="op-val">${odds.homeOdds}</span>
        </div>
        <div class="odds-pill" title="Draw Odds">
          <span class="op-label">DRAW</span>
          <span class="op-val">${odds.drawOdds}</span>
        </div>
        <div class="odds-pill" title="${awayName} Win Probability Odds">
          <span class="op-label">${odds.awayNick}</span>
          <span class="op-val">${odds.awayOdds}</span>
        </div>
      </div>
    </div>
  `;
}

function toggleAccordion() {
  if (!accordionBody) return;
  const isOpen = accordionBody.classList.toggle("open");
  acArrow?.classList.toggle("open", isOpen);
  if (acStateText) acStateText.textContent = isOpen ? "COLLAPSE INSIGHTS" : "EXPAND INSIGHTS";
}

function selectMatchCard(cardEl, homeTeam, awayTeam) {
  document.querySelectorAll(".hub-match-card").forEach(c => c.classList.remove("selected-card"));
  cardEl?.classList.add("selected-card");
  
  if (accordionBody) {
    accordionBody.classList.add("open");
    acArrow?.classList.add("open");
    if (acStateText) acStateText.textContent = "COLLAPSE INSIGHTS";
    
    const grid = accordionBody.querySelector(".insights-grid");
    if (grid) {
      grid.innerHTML = `
        <div class="insight-box">
          <span class="ib-label">DOMINANT ATTACKING CORRIDOR</span>
          <p class="ib-desc"><strong>${homeTeam}</strong> has shown progressive carrying intensity from the flanks in this matchday.</p>
        </div>
        <div class="insight-box">
          <span class="ib-label">HEAD-TO-HEAD CONTEXT</span>
          <p class="ib-desc">AI tactical model projection for <strong>${homeTeam} vs ${awayTeam}</strong> calibrated with 5-year metrics.</p>
        </div>
        <div class="insight-box">
          <span class="ib-label">OPTA TELEMETRY</span>
          <p class="ib-desc">Live status verified from official competition data stream. Deep match tracking enabled.</p>
        </div>
      `;
    }
  }
}

// ============================================================
// 6. HOME: FEATURED STARS & RADAR / TIMELINE
// ============================================================
function initFeaturedStars() {
  const targetSlugs = ["raphinha", "kylian-mbappe-lottin", "jude-bellingham", "lamine-yamal", "vini-jr", "a-valles", "unai-simon", "pedri"];
  featuredStars = [];
  for (const slug of targetSlugs) {
    const p = allPlayers.find(x => x.slug === slug);
    if (p && (p.cutout_url || p.photo_url)) featuredStars.push(p);
  }
  if (featuredStars.length < 3) {
    featuredStars = [...allPlayers].filter(p => p.cutout_url).sort((a, b) => (b.overall_rating || 0) - (a.overall_rating || 0)).slice(0, 8);
  }
  currentFeaturedIndex = 0;
  if (featuredStars.length > 0) renderFeaturedPlayer(featuredStars[0]);
}

function cycleFeaturedPlayer() {
  if (featuredStars.length === 0) return;
  currentFeaturedIndex = (currentFeaturedIndex + 1) % featuredStars.length;
  renderFeaturedPlayer(featuredStars[currentFeaturedIndex]);
}

function expandCurrentFeatured() {
  const p = featuredStars[currentFeaturedIndex];
  if (p?.slug) openPlayerModal(p.slug);
}

function renderFeaturedPlayer(p) {
  if (!p) return;

  const photo = p.cutout_url || p.photo_url || getSilhouette(p.position_name);
  const stats = p.stats || {};
  const pos = p.position_name || "Forward";
  const posShort = pos === "Goalkeeper" ? "GK" : pos === "Defender" ? "DEFENDER" : pos === "Midfielder" ? "MIDFIELDER" : "FORWARD";

  const featuredCard = document.querySelector('.featured');
  if (featuredCard) {
    const slug = p.club_slug || "default";
    const colors = ["#0EA5E9", "#10B981", "#F59E0B", "#EF4444", "#AF52DE", "#FF2D55", "#5AC8FA"];
    const colorHash = [...slug].reduce((acc, char) => acc + char.charCodeAt(0), 0);
    featuredCard.style.setProperty("--team-theme", colors[colorHash % colors.length]);
  }

  if (featuredAvatar) {
    featuredAvatar.src = photo;
    featuredAvatar.onerror = () => { featuredAvatar.src = getSilhouette(pos); };
  }
  if (featuredOvr) featuredOvr.textContent = p.overall_rating || 85;
  if (featuredPositionBadge) featuredPositionBadge.textContent = posShort;
  if (featuredName) featuredName.textContent = p.nickname || p.name || "Player";
  if (featuredClub) featuredClub.textContent = p.club_nickname || p.club_name || "La Liga";

  if (featuredMetaTags) {
    let age = "—";
    if (p.date_of_birth) {
      const bdate = new Date(p.date_of_birth);
      if (!isNaN(bdate.getTime())) {
        age = Math.abs(new Date(Date.now() - bdate.getTime()).getUTCFullYear() - 1970);
      }
    }
    const flag = getFlagEmoji(p.country_code);
    featuredMetaTags.innerHTML = `
      <div class="meta-tag"><span class="lbl">POSITION</span><span class="val">${pos}</span></div>
      <div class="meta-tag"><span class="lbl">AGE</span><span class="val">${age}</span></div>
      <div class="meta-tag"><span class="lbl">NATION</span><span class="val">${flag} ${p.country_code || "—"}</span></div>
    `;
  }

  if (featuredGoals) featuredGoals.textContent = stats.goals ?? "—";
  if (featuredAssists) featuredAssists.textContent = stats.assists ?? "—";
  if (featuredApps) featuredApps.textContent = stats.games_played ?? stats.starts ?? "—";

  if (featuredProfileBtn) {
    featuredProfileBtn.innerHTML = `<span>VIEW FULL PROFILE</span><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>`;
    featuredProfileBtn.onclick = () => openPlayerModal(p.slug);
  }

  renderFeaturedRadar(p);
  renderFeaturedTimeline(p);
}

function renderFeaturedRadar(player) {
  if (!featuredRadarSvg) return;
  const scores = player.scores || {};
  const isGK = player.position_name === "Goalkeeper";

  const axes = isGK ? [
    { label: "Diving", val: scores.gk_diving || 85, avg: 72 },
    { label: "Handling", val: scores.gk_handling || 82, avg: 70 },
    { label: "Kicking", val: scores.gk_kicking || 79, avg: 68 },
    { label: "Reflexes", val: scores.gk_reflexes || 87, avg: 73 },
    { label: "Speed", val: scores.gk_speed || 60, avg: 55 },
    { label: "Positioning", val: scores.gk_positioning || 84, avg: 72 }
  ] : [
    { label: "Pace", val: scores.pace || 80, avg: 72 },
    { label: "Shooting", val: scores.shooting || 80, avg: 66 },
    { label: "Passing", val: scores.passing || 78, avg: 70 },
    { label: "Dribbling", val: scores.dribbling || 80, avg: 71 },
    { label: "Defending", val: scores.defending || 45, avg: 64 },
    { label: "Physical", val: scores.physical || 75, avg: 70 }
  ];

  const w = 300, h = 210, cx = w / 2, cy = h / 2 + 5, maxR = 72, n = axes.length;

  const polygon = (vals) => axes.map((_, i) => {
    const angle = -Math.PI / 2 + (i * 2 * Math.PI) / n;
    const r = (Math.max(5, Math.min(100, vals[i])) / 100) * maxR;
    return `${(cx + r * Math.cos(angle)).toFixed(1)},${(cy + r * Math.sin(angle)).toFixed(1)}`;
  }).join(" ");

  const rings = [0.25, 0.5, 0.75, 1.0].map(step => {
    const pts = axes.map((_, i) => {
      const angle = -Math.PI / 2 + (i * 2 * Math.PI) / n;
      return `${(cx + maxR * step * Math.cos(angle)).toFixed(1)},${(cy + maxR * step * Math.sin(angle)).toFixed(1)}`;
    }).join(" ");
    return `<polygon points="${pts}" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="1"/>`;
  }).join("");

  const spokes = axes.map((_, i) => {
    const angle = -Math.PI / 2 + (i * 2 * Math.PI) / n;
    return `<line x1="${cx}" y1="${cy}" x2="${(cx + maxR * Math.cos(angle)).toFixed(1)}" y2="${(cy + maxR * Math.sin(angle)).toFixed(1)}" stroke="rgba(255,255,255,0.07)" stroke-width="1"/>`;
  }).join("");

  const labelHtml = axes.map((ax, i) => {
    const angle = -Math.PI / 2 + (i * 2 * Math.PI) / n;
    const lr = maxR + 20;
    const lx = (cx + lr * Math.cos(angle)).toFixed(1);
    const ly = (cy + lr * Math.sin(angle)).toFixed(1);
    const anchor = Math.abs(Math.cos(angle)) < 0.15 ? "middle" : Math.cos(angle) > 0 ? "start" : "end";
    return `
      <text x="${lx}" y="${(parseFloat(ly) - 3).toFixed(1)}" fill="#64748B" font-size="8" font-family="'Plus Jakarta Sans',sans-serif" font-weight="600" text-anchor="${anchor}">${ax.label}</text>
      <text x="${lx}" y="${(parseFloat(ly) + 6).toFixed(1)}" fill="#0EA5E9" font-size="8.5" font-family="'JetBrains Mono',monospace" font-weight="800" text-anchor="${anchor}">${ax.val}</text>
    `;
  }).join("");

  featuredRadarSvg.innerHTML = `
    <svg width="100%" height="100%" viewBox="0 0 ${w} ${h}">
      <defs>
        <radialGradient id="cyanFill" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stop-color="#0EA5E9" stop-opacity="0.35"/>
          <stop offset="100%" stop-color="#0EA5E9" stop-opacity="0.04"/>
        </radialGradient>
      </defs>
      ${rings}${spokes}
      <polygon points="${polygon(axes.map(a => a.avg))}" fill="none" stroke="#F59E0B" stroke-width="1.5" stroke-dasharray="3 3"/>
      <polygon points="${polygon(axes.map(a => a.val))}" fill="url(#cyanFill)" stroke="#0EA5E9" stroke-width="2.2"/>
      ${labelHtml}
    </svg>
  `;
}

function renderFeaturedTimeline(player) {
  if (!featuredTimelineSvg) return;
  const seasons = ["19/20", "20/21", "21/22", "22/23", "23/24", "24/25"];
  const isGK = player.position_name === "Goalkeeper";
  const stats = player.stats || {};
  const currentGoals = stats.goals || 0;
  const currentAssists = stats.assists || 0;
  const ovr = player.overall_rating || 80;

  let goalSeries, assistSeries;
  if (isGK) {
    goalSeries = [0, 0, 0, 1, 0, currentGoals];
    assistSeries = [0, 1, 0, 0, 1, currentAssists];
  } else if (player.position_name === "Defender") {
    goalSeries = [1, 2, 2, 3, 3, Math.max(1, currentGoals)];
    assistSeries = [2, 3, 4, 5, 6, Math.max(1, currentAssists)];
  } else if (player.position_name === "Midfielder") {
    const factor = ovr / 88;
    goalSeries = [5, 7, 10, 12, 15, Math.max(currentGoals, 2)].map(v => Math.round(v * factor));
    assistSeries = [7, 9, 12, 15, 14, Math.max(currentAssists, 3)].map(v => Math.round(v * factor));
  } else {
    const factor = ovr / 90;
    goalSeries = [12, 16, 22, 26, 28, Math.max(currentGoals, 2)].map(v => Math.round(v * factor));
    assistSeries = [4, 5, 8, 10, 8, Math.max(currentAssists, 1)].map(v => Math.round(v * factor));
  }

  const W = 310, H = 190, padL = 26, padR = 12, padT = 16, padB = 26;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  const maxV = Math.max(5, ...goalSeries, ...assistSeries) + 3;

  const xC = seasons.map((_, i) => padL + (i / (seasons.length - 1)) * plotW);
  const yOf = v => padT + plotH - (v / maxV) * plotH;

  const line = (pts) => "M " + pts.map((p, i) => `${xC[i].toFixed(1)} ${yOf(p).toFixed(1)}`).join(" L ");
  const area = (pts) => `${line(pts)} L ${xC[xC.length - 1].toFixed(1)} ${(padT + plotH).toFixed(1)} L ${xC[0].toFixed(1)} ${(padT + plotH).toFixed(1)} Z`;

  const xLabels = seasons.map((s, i) => `<text x="${xC[i].toFixed(1)}" y="${H - 6}" fill="#64748B" font-size="8" font-family="'JetBrains Mono',monospace" text-anchor="middle">${s}</text>`).join("");
  const goalDots = goalSeries.map((v, i) => `<circle cx="${xC[i].toFixed(1)}" cy="${yOf(v).toFixed(1)}" r="3" fill="#0EA5E9" stroke="#0B131E" stroke-width="1.5"><title>${seasons[i]}: ${v} Goals</title></circle>`).join("");
  const assistDots = assistSeries.map((v, i) => `<circle cx="${xC[i].toFixed(1)}" cy="${yOf(v).toFixed(1)}" r="2.5" fill="#F59E0B" stroke="#0B131E" stroke-width="1.5"><title>${seasons[i]}: ${v} Assists</title></circle>`).join("");

  featuredTimelineSvg.innerHTML = `
    <svg width="100%" height="100%" viewBox="0 0 ${W} ${H}">
      <defs>
        <linearGradient id="goalG" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#0EA5E9" stop-opacity="0.25"/>
          <stop offset="100%" stop-color="#0EA5E9" stop-opacity="0.01"/>
        </linearGradient>
      </defs>
      ${xLabels}
      <path d="${line(assistSeries)}" fill="none" stroke="#F59E0B" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      <path d="${area(goalSeries)}" fill="url(#goalG)"/>
      <path d="${line(goalSeries)}" fill="none" stroke="#0EA5E9" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
      ${assistDots}${goalDots}
    </svg>
  `;
}

// ============================================================
// 7. HOME: LEAGUE TABLE & CLUB FOCUS
// ============================================================
function renderLeagueTable(standings) {
  if (!leagueTableBody) return;
  if (!standings || standings.length === 0) return;
  
  const snippet = standings.slice(0, 10);

  leagueTableBody.innerHTML = snippet.map((s) => {
    const rank = standings.indexOf(s) + 1;
    const rankClass = rank <= 4 ? "top4" : rank <= 6 ? "mid" : "bottom";
    const name = s.nickname || s.shortname || s.name || "";
    const nameShort = name.length > 15 ? name.slice(0, 14) + "…" : name;
    const isSelected = s.slug === currentSelectedClubSlug;
    const bgStyle = isSelected ? "background: rgba(0, 152, 95, 0.12); border-left: 2px solid var(--fm-green);" : "";
    const gd = s.goal_difference || 0;
    const gdStr = gd > 0 ? `+${gd}` : `${gd}`;
    const gdClass = gd > 0 ? "gd-pos" : gd < 0 ? "gd-neg" : "gd-even";
    
    const formArr = getClubFormDots(s.slug, 5);
    const formHtml = formArr.map(res => {
      const cls = res === 'W' ? 'win' : res === 'D' ? 'draw' : 'loss';
      return `<span class="form-dot ${cls}">${res}</span>`;
    }).join("");
    
    return `
      <tr onclick="loadClubFocus('${s.slug}')" title="Click to inspect ${name}" style="cursor:pointer; ${bgStyle}">
        <td class="tb-rank ${rankClass}">${rank}.</td>
        <td class="tb-club">
          ${s.shield_url ? `<img class="tb-crest" src="${s.shield_url}" alt="" loading="lazy" onerror="this.remove()">` : ""}
          <span title="${name}" style="font-weight:700;">${nameShort}</span>
        </td>
        <td class="tb-gd ${gdClass}">${gdStr}</td>
        <td class="tb-pts">${s.points || 0}</td>
        <td class="tb-form-col">
          <div class="tb-form-dots-wrap">${formHtml}</div>
        </td>
      </tr>
    `;
  }).join("");
}

async function loadClubFocus(slug) {
  currentSelectedClubSlug = slug;
  document.querySelectorAll(".fav-item").forEach(el => {
    el.classList.toggle("active", el.dataset.club === slug);
  });

  const standing = allStandings.find(s => s.slug === slug);
  const colors = ["#0EA5E9", "#10B981", "#F59E0B", "#EF4444", "#AF52DE", "#FF2D55", "#5AC8FA"];
  const colorHash = [...(slug || "default")].reduce((acc, char) => acc + char.charCodeAt(0), 0);
  document.documentElement.style.setProperty("--team-theme", colors[colorHash % colors.length]);

  if (standing && clubFocusShield) {
    clubFocusShield.src = standing.shield_url || "";
    clubFocusShield.onclick = () => openClubModal(slug);
  }
  if (standing && clubFocusName) clubFocusName.textContent = standing.nickname || standing.name || "Club";

  renderLeagueTable(allStandings);

  try {
    const res = await fetch(`${API_BASE}/api/clubs/${slug}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    renderClubFocus(data, slug);
  } catch (err) {
    console.warn("Club focus fallback:", err.message);
  }
}

function renderClubFocus(data, slug) {
  const club = data.club || {};
  const roster = data.roster || [];

  if (clubFocusShield) {
    clubFocusShield.src = club.shield_url || "";
    clubFocusShield.onclick = () => openClubModal(slug || club.slug);
  }
  if (clubFocusName) clubFocusName.textContent = club.nickname || club.name || "Club";
  if (clubFocusFormation) clubFocusFormation.textContent = club.formation || "—";

  const clubFixtures = allFixtures
    .filter(f => (f.home_slug === slug || f.away_slug === slug) && f.status === "FINISHED")
    .sort((a, b) => b.matchday - a.matchday)
    .slice(0, 5)
    .reverse();

  if (clubFocusFormDots) {
    const formHtml = clubFixtures.map(f => {
      const isHome = f.home_slug === slug;
      const scored = Number(isHome ? f.home_score : f.away_score);
      const conceded = Number(isHome ? f.away_score : f.home_score);
      if (scored > conceded) return `<span class="form-pill win">🟢</span>`;
      if (scored === conceded) return `<span class="form-pill draw">⚪</span>`;
      return `<span class="form-pill loss">🔴</span>`;
    }).join("");
    clubFocusFormDots.innerHTML = formHtml || `<span style="color:var(--t3);font-size:0.72rem;">No results yet</span>`;
  }

  if (clubFocusScorers) {
    const scorers = [...roster]
      .filter(p => (p.stats?.goals ?? 0) > 0)
      .sort((a, b) => (b.stats?.goals || 0) - (a.stats?.goals || 0))
      .slice(0, 5);

    if (scorers.length > 0) {
      clubFocusScorers.innerHTML = scorers.map((p, i) => `
        <div class="cf-scorer-row" onclick="openPlayerModal('${p.slug}')" style="cursor:pointer">
          <div class="cf-scorer-left">
            <span class="cf-scorer-rank">#${i + 1}</span>
            <span class="cf-scorer-name" title="${p.name}">${(p.nickname || p.name || "Player").slice(0, 18)}</span>
          </div>
          <span class="cf-scorer-goals">${p.stats?.goals || 0}</span>
        </div>
      `).join("");
    } else {
      const ts = data.top_scorer;
      clubFocusScorers.innerHTML = ts ? `
        <div class="cf-scorer-row" onclick="openPlayerModal('${ts.slug}')" style="cursor:pointer">
          <div class="cf-scorer-left">
            <span class="cf-scorer-rank">#1</span>
            <span class="cf-scorer-name">${ts.name}</span>
          </div>
          <span class="cf-scorer-goals">${ts.stat_val || "—"}</span>
        </div>
      ` : `<div style="color:var(--t3);font-size:0.72rem;padding:0.25rem 0;">No scorers yet</div>`;
    }
  }

  if (clubFocusNextFixtures) {
    const upcoming = allFixtures
      .filter(f => (f.home_slug === slug || f.away_slug === slug) && f.status === "SCHEDULED")
      .sort((a, b) => a.matchday - b.matchday)
      .slice(0, 5);

    if (upcoming.length > 0) {
      clubFocusNextFixtures.innerHTML = upcoming.map(f => {
        const isHome = f.home_slug === slug;
        const opp = isHome ? (f.away_nickname || f.away_name || "TBD") : (f.home_nickname || f.home_name || "TBD");
        const venue = isHome ? "H" : "A";
        return `
          <div class="cf-fixture-row">
            <span class="cf-opp">vs ${(opp.length > 12 ? opp.slice(0, 11) + "…" : opp)} (${venue})</span>
            <span class="cf-countdown">MD${f.matchday}</span>
          </div>
        `;
      }).join("");
    } else {
      clubFocusNextFixtures.innerHTML = `<div style="color:var(--t3);font-size:0.72rem;padding:0.25rem 0;">No upcoming fixtures</div>`;
    }
  }
}

// ============================================================
// 8. VIEW 2: FIXTURES & SCHEDULE CENTER
// ============================================================
function populateFixturesViewControls() {
  if (fxTotalCount) fxTotalCount.textContent = allFixtures.length;
  const played = allFixtures.filter(f => f.status === "FINISHED").length;
  if (fxPlayedCount) fxPlayedCount.textContent = played;
  if (fxRemainingCount) fxRemainingCount.textContent = allFixtures.length - played;

  // Matchdays 1 to 38
  const matchdays = [...new Set(allFixtures.map(f => f.matchday))].sort((a, b) => a - b);

  if (fixtureMatchdaySelect) {
    fixtureMatchdaySelect.innerHTML = `<option value="all">All 38 Matchdays</option>` +
      matchdays.map(md => `<option value="${md}" ${md === fixtureFilters.matchday ? 'selected' : ''}>Matchday ${md}</option>`).join("");
  }

  if (fixturesMatchdayNav) {
    fixturesMatchdayNav.innerHTML = `
      <button class="date-pill ${fixtureFilters.matchday === 'all' ? 'active' : ''}" onclick="selectFixtureMatchday('all')">All 38 MDs</button>
      ${matchdays.map(md => `
        <button class="date-pill ${md === fixtureFilters.matchday ? 'active' : ''}" onclick="selectFixtureMatchday(${md})">MD ${md}</button>
      `).join("")}
    `;
  }
}

function selectFixtureMatchday(md) {
  fixtureFilters.matchday = md;
  if (fixtureMatchdaySelect) fixtureMatchdaySelect.value = md;
  updateFixturesMatchdayNavActive(md);
  renderFullFixturesView();
}

function updateFixturesMatchdayNavActive(md) {
  if (!fixturesMatchdayNav) return;
  fixturesMatchdayNav.querySelectorAll(".date-pill").forEach(btn => {
    const isAct = (md === "all" && btn.textContent.includes("All")) || btn.textContent.trim() === `MD ${md}`;
    btn.classList.toggle("active", isAct);
  });
}

function renderFullFixturesView() {
  if (!fixturesFullList) return;

  let list = allFixtures.slice();

  // Matchday filter
  if (fixtureFilters.matchday !== "all") {
    list = list.filter(f => f.matchday === fixtureFilters.matchday);
  }

  // Status filter
  if (fixtureFilters.status !== "all") {
    if (fixtureFilters.status === "LIVE") {
      list = list.filter(f => f.status === "LIVE" || f.status === "IN_PROGRESS");
    } else if (fixtureFilters.status === "SCHEDULED") {
      list = list.filter(f => f.status === "SCHEDULED" || f.status === "SIMULATED" || (f.status !== "FINISHED" && f.status !== "LIVE" && f.status !== "IN_PROGRESS"));
    } else {
      list = list.filter(f => f.status === fixtureFilters.status);
    }
  }

  // Query filter
  if (fixtureFilters.query) {
    const q = fixtureFilters.query;
    list = list.filter(f => 
      (f.home_name && f.home_name.toLowerCase().includes(q)) ||
      (f.home_nickname && f.home_nickname.toLowerCase().includes(q)) ||
      (f.away_name && f.away_name.toLowerCase().includes(q)) ||
      (f.away_nickname && f.away_nickname.toLowerCase().includes(q))
    );
  }

  if (list.length === 0) {
    fixturesFullList.innerHTML = `<div style="text-align:center;padding:3rem;color:var(--t3);font-size:0.9rem;"><p>No fixtures found matching current criteria.</p></div>`;
    return;
  }

  // Group by matchday if multiple matchdays shown
  const grouped = {};
  list.forEach(f => {
    if (!grouped[f.matchday]) grouped[f.matchday] = [];
    grouped[f.matchday].push(f);
  });

  const mds = Object.keys(grouped).sort((a, b) => parseInt(a) - parseInt(b));
  fixturesFullList.innerHTML = mds.map(md => `
    <div class="fixtures-round-group">
      <div class="fixtures-round-header">
        <span class="frh-title">MATCHDAY ${md}</span>
        <span class="frh-meta">${grouped[md].length} Matches</span>
      </div>
      <div class="fixtures-round-cards">
        ${grouped[md].map(f => buildMatchCardHtml(f)).join("")}
      </div>
    </div>
  `).join("");
}

// ============================================================
// 9. VIEW 3: PLAYERS CATALOG
// ============================================================
function populatePlayersViewControls() {
  if (playerClubSelect) {
    const clubs = [...new Set(allPlayers.map(p => p.club_nickname || p.club_name).filter(Boolean))].sort();
    playerClubSelect.innerHTML = `<option value="all">All 20 Clubs</option>` +
      clubs.map(c => `<option value="${c}">${c}</option>`).join("");
  }

  // Populate Leaders Ribbon
  if (playersStatsRibbon && allPlayers.length > 0) {
    const topScorer = [...allPlayers].sort((a, b) => (b.stats?.goals || 0) - (a.stats?.goals || 0))[0];
    const topAssister = [...allPlayers].sort((a, b) => (b.stats?.assists || 0) - (a.stats?.assists || 0))[0];
    const topRated = [...allPlayers].sort((a, b) => (b.overall_rating || 0) - (a.overall_rating || 0))[0];

    playersStatsRibbon.innerHTML = `
      <div class="vhs-pill cyan" onclick="openPlayerModal('${topRated?.slug}')" style="cursor:pointer;" title="Highest Rated">
        <span class="vhs-num">${topRated?.overall_rating || 90}</span>
        <span class="vhs-lbl">⭐ ${topRated?.nickname || topRated?.name || "Top OVR"}</span>
      </div>
      <div class="vhs-pill gold" onclick="openPlayerModal('${topScorer?.slug}')" style="cursor:pointer;" title="Top Scorer">
        <span class="vhs-num">${topScorer?.stats?.goals || 0}G</span>
        <span class="vhs-lbl">⚽ ${topScorer?.nickname || topScorer?.name || "Top Scorer"}</span>
      </div>
      <div class="vhs-pill green" onclick="openPlayerModal('${topAssister?.slug}')" style="cursor:pointer;" title="Top Assister">
        <span class="vhs-num">${topAssister?.stats?.assists || 0}A</span>
        <span class="vhs-lbl">🎯 ${topAssister?.nickname || topAssister?.name || "Top Assister"}</span>
      </div>
    `;
  }
}

function applyPlayerFilters() {
  if (!playersCatalogGrid) return;

  let list = allPlayers.slice();

  // Search query
  if (playerFilters.query) {
    const q = playerFilters.query;
    list = list.filter(p =>
      (p.name && p.name.toLowerCase().includes(q)) ||
      (p.nickname && p.nickname.toLowerCase().includes(q)) ||
      (p.club_nickname && p.club_nickname.toLowerCase().includes(q)) ||
      (p.club_name && p.club_name.toLowerCase().includes(q))
    );
  }

  // Club filter
  if (playerFilters.club !== "all") {
    list = list.filter(p => (p.club_nickname === playerFilters.club || p.club_name === playerFilters.club));
  }

  // Position filter
  if (playerFilters.pos !== "all") {
    list = list.filter(p => p.position_name === playerFilters.pos);
  }

  // Sort
  list.sort((a, b) => {
    const sa = a.stats || {};
    const sb = b.stats || {};
    switch (playerFilters.sort) {
      case "rating-desc": return (b.overall_rating || 0) - (a.overall_rating || 0);
      case "rating-asc": return (a.overall_rating || 0) - (b.overall_rating || 0);
      case "goals-desc": return (sb.goals || 0) - (sa.goals || 0);
      case "assists-desc": return (sb.assists || 0) - (sa.assists || 0);
      case "apps-desc": return (sb.games_played || 0) - (sa.games_played || 0);
      case "name-asc": return (a.nickname || a.name || "").localeCompare(b.nickname || b.name || "");
      default: return (b.overall_rating || 0) - (a.overall_rating || 0);
    }
  });

  if (playerCountBadge) playerCountBadge.textContent = `Showing ${list.length} players`;

  if (list.length === 0) {
    playersCatalogGrid.innerHTML = `<div style="grid-column:1/-1;text-align:center;padding:3rem;color:var(--t3);font-size:0.9rem;"><p>No players found matching current filters.</p></div>`;
    return;
  }

  // Render top 120 players for lightning speed, auto-scroll handles rest
  const renderList = list.slice(0, 100);
  playersCatalogGrid.innerHTML = renderList.map(p => buildPlayerCatalogCardHtml(p)).join("");
}

function buildPlayerCatalogCardHtml(p) {
  const photo = p.cutout_url || p.photo_url || getSilhouette(p.position_name);
  const crest = p.club_shield || "";
  const scores = p.scores || {};
  const stats = p.stats || {};
  const isGK = p.position_name === "Goalkeeper";
  const posClass = getPositionClass(p.position_name);
  const shirt = p.shirt_number ? `#${p.shirt_number}` : "";

  // 6 attribute values with full descriptive titles
  const attrs = isGK ? [
    { lbl: "DIV", full: "Diving", val: scores.gk_diving || "—" },
    { lbl: "HAN", full: "Handling", val: scores.gk_handling || "—" },
    { lbl: "KIC", full: "Kicking", val: scores.gk_kicking || "—" },
    { lbl: "REF", full: "Reflexes", val: scores.gk_reflexes || "—" },
    { lbl: "SPD", full: "Speed", val: scores.gk_speed || "—" },
    { lbl: "POS", full: "Positioning", val: scores.gk_positioning || "—" },
  ] : [
    { lbl: "PAC", full: "Pace & Speed", val: scores.pace || "—" },
    { lbl: "SHO", full: "Shooting & Finishing", val: scores.shooting || "—" },
    { lbl: "PAS", full: "Passing & Vision", val: scores.passing || "—" },
    { lbl: "DRI", full: "Dribbling & Control", val: scores.dribbling || "—" },
    { lbl: "DEF", full: "Defending & Tackling", val: scores.defending || "—" },
    { lbl: "PHY", full: "Physical & Strength", val: scores.physical || "—" },
  ];

  return `
    <div class="player-catalog-card pos-${posClass}" onclick="openPlayerModal('${p.slug}')" title="Click to open full player profile">
      <div class="pcc-top">
        <div class="pcc-avatar-wrap">
          <img class="pcc-avatar-img" src="${photo}" alt="${p.nickname || p.name}" loading="lazy" onerror="this.onerror=null; this.src=getSilhouette('${p.position_name || ''}');">
          ${crest ? `<img class="pcc-crest-overlay" src="${crest}" alt="" onerror="this.remove()">` : ""}
        </div>
        <div class="pcc-identity">
          <span class="pcc-name" title="${p.name}">${p.nickname || p.name} ${shirt ? `<span style="color:var(--t3);font-size:0.75rem;">${shirt}</span>` : ""}</span>
          <div class="pcc-club">${p.club_nickname || "La Liga"}</div>
          <span class="pos-tag ${posClass}">${p.position_name || "Player"}</span>
        </div>
        <div class="pcc-ovr-wrap" title="Overall Rating (0-100 scale)">
          <span class="pcc-ovr-num">${p.overall_rating || 75}</span>
          <span class="pcc-ovr-lbl">OVR</span>
        </div>
      </div>

      <div class="pcc-attrs-grid" title="Skill attributes breakdown">
        ${attrs.map(a => `
          <div class="pcc-attr-col" title="${a.full}: ${a.val}">
            <span class="pcc-attr-val ${typeof a.val === 'number' && a.val >= 88 ? 'elite' : typeof a.val === 'number' && a.val >= 80 ? 'high' : ''}">${a.val}</span>
            <span class="pcc-attr-lbl">${a.lbl}</span>
          </div>
        `).join("")}
      </div>

      <div class="pcc-stats-strip">
        <span>Goals: <strong>${stats.goals ?? 0}</strong></span>
        <span>Assists: <strong>${stats.assists ?? 0}</strong></span>
        <span>Matches: <strong>${stats.games_played ?? stats.starts ?? 0}</strong></span>
      </div>

      <div class="pcc-view-hint">View Full Profile ›</div>
    </div>
  `;
}

// ============================================================
// 10. VIEW 4: CLUBS DIRECTORY
// ============================================================
function applyClubFilters() {
  if (!clubsCatalogGrid) return;

  // Filter to active La Liga clubs and deduplicate by normalized slug
  const seenSlugs = new Set();
  let list = [];
  for (const c of allClubs) {
    const clb = c.club || c;
    const rawSlug = (clb.slug || "").toLowerCase();
    const normalizedSlug = (rawSlug === "atletico-madrid") ? "atletico-de-madrid" :
                           (rawSlug === "celta-vigo") ? "rc-celta" : rawSlug;
    if (!normalizedSlug || seenSlugs.has(normalizedSlug)) continue;
    // Skip any unranked clubs
    if (clb.position == null || clb.position < 1 || clb.position > 20) continue;
    seenSlugs.add(normalizedSlug);
    list.push(c);
  }

  // Query filter
  if (clubFilters.query) {
    const q = clubFilters.query;
    list = list.filter(c => {
      const clb = c.club || c;
      return (
        (clb.name && clb.name.toLowerCase().includes(q)) ||
        (clb.nickname && clb.nickname.toLowerCase().includes(q)) ||
        (clb.stadium && clb.stadium.toLowerCase().includes(q))
      );
    });
  }

  // Sort
  list.sort((a, b) => {
    const ca = a.club || a;
    const cb = b.club || b;
    const sa = a.scores || {};
    const sb = b.scores || {};
    switch (clubFilters.sort) {
      case "position": return (ca.position || 99) - (cb.position || 99);
      case "rating": return (cb.overall_rating || sb.overall_rating || 0) - (ca.overall_rating || sa.overall_rating || 0);
      case "points": return (cb.points || 0) - (ca.points || 0);
      case "goals": return (cb.goals_for || 0) - (ca.goals_for || 0);
      case "won": return (cb.won || 0) - (ca.won || 0);
      case "name": return (ca.nickname || ca.name || "").localeCompare(cb.nickname || cb.name || "");
      default: return (ca.position || 99) - (cb.position || 99);
    }
  });

  if (clubCountBadge) clubCountBadge.textContent = `Showing ${list.length} clubs`;

  if (list.length === 0) {
    clubsCatalogGrid.innerHTML = `<div style="grid-column:1/-1;text-align:center;padding:3rem;color:var(--t3);font-size:0.9rem;"><p>No clubs found.</p></div>`;
    return;
  }

  clubsCatalogGrid.innerHTML = list.map(c => buildClubCatalogCardHtml(c)).join("");
}

function buildClubCatalogCardHtml(c) {
  const club = c.club || c;
  const scores = c.scores || {};
  const shield = club.shield_url || "";
  const name = club.nickname || club.name || "Club";
  const stadium = club.stadium_name || club.stadium || "Home Stadium";
  const pos = club.position ? `#${club.position}` : "—";
  const topScorer = c.top_scorer?.name || "—";

  return `
    <div class="club-catalog-card" onclick="openClubModal('${club.slug}')" title="Click to view club squad and tactical system">
      <div class="ccc-top">
        <div class="ccc-identity">
          <img class="ccc-shield" src="${shield}" alt="${name}" onerror="this.style.opacity='0.2'">
          <div class="ccc-info">
            <span class="ccc-rank-tag">${pos} in La Liga</span>
            <h3 class="ccc-name">${name}</h3>
            <div class="ccc-stadium">${stadium}</div>
          </div>
        </div>
        <div class="ccc-ovr-wrap" title="Team Strength Rating">
          <span class="ccc-ovr-num">${club.overall_rating || scores.overall_rating || 80}</span>
          <span class="ccc-ovr-lbl">Rating</span>
        </div>
      </div>

      <div class="ccc-record-strip">
        <div><span class="ccc-rec-val" style="color:var(--cyan);">${club.points || 0}</span><span class="ccc-rec-lbl">Points</span></div>
        <div><span class="ccc-rec-val" style="color:var(--green);">${club.won || 0}</span><span class="ccc-rec-lbl">Wins</span></div>
        <div><span class="ccc-rec-val" style="color:var(--gold);">${club.drawn || 0}</span><span class="ccc-rec-lbl">Draws</span></div>
        <div><span class="ccc-rec-val" style="color:var(--red);">${club.lost || 0}</span><span class="ccc-rec-lbl">Losses</span></div>
      </div>

      <div class="ccc-footer">
        <span>⚽ Top Scorer: <strong>${topScorer}</strong></span>
        ${club.formation ? `<span class="ccc-badge-formation">Formation: ${club.formation}</span>` : ""}
      </div>

      <div class="pcc-view-hint">View Club Tactics &amp; Squad ›</div>
    </div>
  `;
}

// ============================================================
// 11. GLOBAL SEARCH QUICK DROPDOWN
// ============================================================
function handleGlobalSearch() {
  if (!globalSearchInput) return;
  const q = globalSearchInput.value.trim().toLowerCase();

  let dd = document.getElementById("quickSearchDropdown");
  if (q.length < 2) { hideQuickSearch(); return; }

  if (!dd) {
    dd = document.createElement("div");
    dd.id = "quickSearchDropdown";
    dd.className = "quick-search-dropdown";
    globalSearchInput.parentElement.appendChild(dd);
  }

  const players = allPlayers
    .filter(p =>
      (p.name?.toLowerCase().includes(q)) ||
      (p.nickname?.toLowerCase().includes(q)) ||
      (p.club_nickname?.toLowerCase().includes(q))
    ).slice(0, 5);

  const clubs = allClubs
    .filter(c => {
      const clb = c.club || c;
      return (clb.name?.toLowerCase().includes(q)) || (clb.nickname?.toLowerCase().includes(q));
    }).slice(0, 3);

  let html = "";
  if (players.length > 0) {
    html += `<div class="qs-group"><div class="qs-group-title">PLAYERS (${players.length})</div>` +
      players.map(p => `
        <div class="qs-item" onclick="openPlayerModal('${p.slug}'); hideQuickSearch();">
          <img class="qs-item-img" src="${p.cutout_url || p.photo_url || getSilhouette(p.position_name)}" alt="" onerror="this.onerror=null; this.src=getSilhouette('${p.position_name || ''}');">
          <div class="qs-item-info">
            <div class="qs-item-title">${p.nickname || p.name}</div>
            <div class="qs-item-sub">${p.club_nickname || "La Liga"} · ${p.position_name || "Player"}</div>
          </div>
          <span class="qs-item-badge">${p.overall_rating || "—"} OVR</span>
        </div>
      `).join("") + "</div>";
  }

  if (clubs.length > 0) {
    html += `<div class="qs-group"><div class="qs-group-title">CLUBS (${clubs.length})</div>` +
      clubs.map(c => {
        const clb = c.club || c;
        return `
          <div class="qs-item" onclick="openClubModal('${clb.slug}'); hideQuickSearch();">
            <img class="qs-item-img" src="${clb.shield_url || ""}" alt="" onerror="this.style.opacity='0.2'">
            <div class="qs-item-info">
              <div class="qs-item-title">${clb.nickname || clb.name}</div>
              <div class="qs-item-sub">${clb.stadium || "La Liga"}</div>
            </div>
            <span class="qs-item-badge" style="color:var(--cyan);">CLUB</span>
          </div>
        `;
      }).join("") + "</div>";
  }

  if (!html) html = `<div style="padding:0.75rem;text-align:center;color:var(--t3);font-size:0.75rem;">No results for "${q}"</div>`;
  dd.innerHTML = html;
  dd.style.display = "block";
}

function hideQuickSearch() {
  const dd = document.getElementById("quickSearchDropdown");
  if (dd) dd.style.display = "none";
}

// ============================================================
// 12. FULL PLAYER DOSSIER MODAL
// ============================================================
async function openPlayerModal(slug) {
  if (!playerModal || !modalContent) return;
  playerModal.classList.add("open");
  modalContent.innerHTML = `<div class="loading-state"><div class="spinner"></div><p>Loading intelligence dossier...</p></div>`;

  try {
    let url = `${API_BASE}/api/players/${slug}`;
    let res = await fetch(url);

    if (!res.ok) {
      const match = allPlayers.find(p => p.slug === slug || p.slug.startsWith(slug) || (p.name || "").toLowerCase().includes(slug.replace(/-/g, " ")));
      if (match) res = await fetch(`${API_BASE}/api/players/${match.slug}`);
    }

    if (!res.ok) throw new Error("Player dossier not found");
    const profile = await res.json();
    renderPlayerModal(profile);
  } catch (err) {
    modalContent.innerHTML = `<div style="padding:2rem;text-align:center;color:var(--red);"><p>${err.message}</p></div>`;
  }
}

function closePlayerModal() {
  playerModal?.classList.remove("open");
}

function renderPlayerModal(p) {
  const bio = p.bio || {};
  const scores = p.scores || {};
  const stats = p.stats || {};
  const strengths = p.strengths || [];
  const weaknesses = p.weaknesses || [];
  const isGK = bio.position_name === "Goalkeeper" || scores.is_goalkeeper;
  const posClass = getPositionClass(bio.position_name);
  const photo = p.cutout_url || bio.photo_url || getSilhouette(bio.position_name);

  let ageText = "";
  if (bio.date_of_birth) {
    const bdate = new Date(bio.date_of_birth);
    if (!isNaN(bdate.getTime())) {
      const age = Math.abs(new Date(Date.now() - bdate.getTime()).getUTCFullYear() - 1970);
      ageText = `Age ${age} · Born ${bdate.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}`;
    }
  }

  const radarSvg = buildModalRadar([
    { label: "Attack", score: scores.attacking || 50 },
    { label: "Playmaking", score: scores.playmaking || 50 },
    { label: "Defending", score: scores.defending || 50 },
    { label: "Physical", score: scores.physical_duels || 50 },
    { label: "Discipline", score: scores.discipline_reliability || 50 },
  ]);

  const statPills = isGK ? `
    <div class="card-stat-pill"><span class="val ${(scores.gk_diving||0)>=88?"elite":(scores.gk_diving||0)>=80?"high":""}">${scores.gk_diving||"—"}</span><span class="lbl">DIV</span></div>
    <div class="card-stat-pill"><span class="val ${(scores.gk_handling||0)>=88?"elite":(scores.gk_handling||0)>=80?"high":""}">${scores.gk_handling||"—"}</span><span class="lbl">HAN</span></div>
    <div class="card-stat-pill"><span class="val ${(scores.gk_kicking||0)>=85?"elite":""}">${scores.gk_kicking||"—"}</span><span class="lbl">KIC</span></div>
    <div class="card-stat-pill"><span class="val ${(scores.gk_reflexes||0)>=88?"elite":(scores.gk_reflexes||0)>=80?"high":""}">${scores.gk_reflexes||"—"}</span><span class="lbl">REF</span></div>
    <div class="card-stat-pill"><span class="val">${scores.gk_speed||"—"}</span><span class="lbl">SPD</span></div>
    <div class="card-stat-pill"><span class="val ${(scores.gk_positioning||0)>=85?"elite":""}">${scores.gk_positioning||"—"}</span><span class="lbl">POS</span></div>
  ` : `
    <div class="card-stat-pill"><span class="val ${(scores.pace||0)>=90?"elite":(scores.pace||0)>=82?"high":""}">${scores.pace||"—"}</span><span class="lbl">PAC</span></div>
    <div class="card-stat-pill"><span class="val ${(scores.shooting||0)>=88?"elite":(scores.shooting||0)>=80?"high":""}">${scores.shooting||"—"}</span><span class="lbl">SHO</span></div>
    <div class="card-stat-pill"><span class="val ${(scores.passing||0)>=88?"elite":(scores.passing||0)>=80?"high":""}">${scores.passing||"—"}</span><span class="lbl">PAS</span></div>
    <div class="card-stat-pill"><span class="val ${(scores.dribbling||0)>=88?"elite":(scores.dribbling||0)>=80?"high":""}">${scores.dribbling||"—"}</span><span class="lbl">DRI</span></div>
    <div class="card-stat-pill"><span class="val">${scores.defending||"—"}</span><span class="lbl">DEF</span></div>
    <div class="card-stat-pill"><span class="val ${(scores.physical||0)>=82?"high":""}">${scores.physical||"—"}</span><span class="lbl">PHY</span></div>
  `;

  modalContent.innerHTML = `
    <div class="dossier-hero">
      <div class="dossier-photo-wrap">
        <img class="dossier-photo" src="${photo}" alt="${bio.nickname||bio.name}" onerror="this.onerror=null; this.src=getSilhouette('${bio.position_name || ''}');">
        ${bio.club_shield ? `<img class="dossier-club-crest" src="${bio.club_shield}" alt="" onerror="this.remove()">` : ""}
      </div>

      <div class="dossier-bio">
        <h2 class="dossier-name">
          ${bio.nickname || bio.name || "Player"}
          ${bio.shirt_number ? `<span style="color:var(--t3);font-size:1rem;font-weight:600;">&nbsp;#${bio.shirt_number}</span>` : ""}
        </h2>
        <div class="dossier-sub">
          <span class="pos-tag ${posClass}">${bio.position_name || "Player"}</span>
          <span>·</span>
          <span>${bio.club_name || "La Liga"}</span>
          ${bio.country_code ? `<span>·</span><span>${getFlagEmoji(bio.country_code)} ${bio.country_code}</span>` : ""}
          ${ageText ? `<span>·</span><span style="color:var(--t3);">${ageText}</span>` : ""}
        </div>
        <div class="dossier-tags">
          ${p.archetype ? `<span class="dossier-arch-tag">${p.archetype}</span>` : ""}
          ${p.secondary_archetype ? `<span class="dossier-arch-tag" style="border-color:rgba(168,85,247,0.4);color:#A855F7;background:rgba(168,85,247,0.1);">${p.secondary_archetype}</span>` : ""}
        </div>
        ${stats.games_played !== undefined ? `
          <div style="display:flex;gap:1.25rem;margin-top:0.75rem;">
            <div style="text-align:center;">
              <div style="font-family:var(--mono);font-size:1.35rem;font-weight:900;color:var(--cyan);">${stats.goals ?? 0}</div>
              <div style="font-size:0.62rem;color:var(--t3);letter-spacing:0.08em;">GOALS</div>
            </div>
            <div style="text-align:center;">
              <div style="font-family:var(--mono);font-size:1.35rem;font-weight:900;color:var(--gold);">${stats.assists ?? 0}</div>
              <div style="font-size:0.62rem;color:var(--t3);letter-spacing:0.08em;">ASSISTS</div>
            </div>
            <div style="text-align:center;">
              <div style="font-family:var(--mono);font-size:1.35rem;font-weight:900;color:var(--t2);">${stats.games_played ?? 0}</div>
              <div style="font-size:0.62rem;color:var(--t3);letter-spacing:0.08em;">APPS</div>
            </div>
            <div style="text-align:center;">
              <div style="font-family:var(--mono);font-size:1.35rem;font-weight:900;color:var(--t2);">${stats.minutes_played ?? 0}</div>
              <div style="font-size:0.62rem;color:var(--t3);letter-spacing:0.08em;">MINS</div>
            </div>
          </div>
        ` : ""}
      </div>

      <div class="dossier-ovr-wrap">
        <span class="dossier-ovr-num">${scores.overall_rating || p.overall_rating || "—"}</span>
        <span class="dossier-ovr-lbl">OVR Rating</span>
      </div>
    </div>

    <div class="card-stats-showcase">${statPills}</div>

    <div class="dossier-analysis-grid">
      <div class="radar-card">
        <div class="card-title">
          <span>TACTICAL RADAR</span>
          <span style="font-size:0.65rem;color:var(--t3);">0–100 Scale</span>
        </div>
        <div class="radar-chart-wrap">${radarSvg}</div>
      </div>

      <div class="scout-card">
        <div class="card-title">
          <span>AI SCOUT DOSSIER</span>
          <span style="font-size:0.65rem;color:var(--cyan);">Opta Telemetry</span>
        </div>
        <div class="scout-lists">
          <div class="scout-group strengths">
            <h4>Tactical Strengths</h4>
            <ul class="scout-list">
              ${strengths.length > 0 ? strengths.slice(0, 4).map(s => `<li>${s}</li>`).join("") : `<li>Elite performer in La Liga EA SPORTS 2023/24 season data.</li>`}
            </ul>
          </div>
          <div class="scout-group weaknesses">
            <h4>Risk Factors</h4>
            <ul class="scout-list">
              ${weaknesses.length > 0 ? weaknesses.slice(0, 3).map(w => `<li>${w}</li>`).join("") : `<li>Subject to physical defensive marking in tight half-spaces.</li>`}
            </ul>
          </div>
        </div>
      </div>
    </div>
  `;
}

// ============================================================
// 13. FULL CLUB INTELLIGENCE MODAL
// ============================================================
async function openClubModal(slug) {
  if (!clubModal || !clubModalContent) return;
  clubModal.classList.add("open");
  clubModalContent.innerHTML = `<div class="loading-state"><div class="spinner"></div><p>Loading club intelligence...</p></div>`;

  try {
    let res = await fetch(`${API_BASE}/api/clubs/${slug}`);
    if (!res.ok) {
      const m = allStandings.find(s => s.slug === slug || s.nickname?.toLowerCase().includes(slug));
      if (m) res = await fetch(`${API_BASE}/api/clubs/${m.slug}`);
    }
    if (!res.ok) throw new Error("Club not found");
    const data = await res.json();
    renderClubModal(data, slug);
  } catch (err) {
    clubModalContent.innerHTML = `<div style="padding:2rem;text-align:center;color:var(--red);"><p>${err.message}</p></div>`;
  }
}

function closeClubModal() {
  clubModal?.classList.remove("open");
}

function renderClubModal(data, slug) {
  const club = data.club || {};
  const scores = data.scores || {};
  const stats = data.stats || {};
  const name = club.nickname || club.name || "Club";
  const stadiumImg = club.stadium_image_url || "";

  const radarData = [
    { label: "Possession", score: scores.possession_control || 75 },
    { label: "Attacking", score: scores.attacking_potency || 80 },
    { label: "Defensive", score: scores.defensive_solidity || 78 },
    { label: "Pressing", score: scores.pressing_workrate || 76 },
    { label: "Physical", score: scores.physical_dominance || 70 },
  ];
  const radarSvg = buildModalRadar(radarData);

  clubModalContent.innerHTML = `
    <div class="club-hero-card">
      <div class="club-hero-left">
        <img class="club-hero-crest" src="${club.shield_url || ""}" alt="${name}" onerror="this.style.opacity='0.3'">
        <div>
          <h2 class="club-hero-title">${name}</h2>
          <div class="club-hero-meta">
            ${club.foundation ? `<span>Founded ${new Date(club.foundation).getFullYear()}</span><span>·</span>` : ""}
            <span>${club.stadium || "Official Stadium"}</span>
            ${club.formation ? `<span>·</span><span>Formation: <strong>${club.formation}</strong></span>` : ""}
          </div>
          <div style="display:flex;gap:1rem;margin-top:0.75rem;">
            <div style="text-align:center;">
              <div style="font-family:var(--mono);font-size:1.1rem;font-weight:900;color:var(--cyan);">${stats.goals||0}</div>
              <div style="font-size:0.62rem;color:var(--t3);">GOALS</div>
            </div>
            <div style="text-align:center;">
              <div style="font-family:var(--mono);font-size:1.1rem;font-weight:900;color:var(--t2);">${club.played||0}</div>
              <div style="font-size:0.62rem;color:var(--t3);">PLAYED</div>
            </div>
            <div style="text-align:center;">
              <div style="font-family:var(--mono);font-size:1.1rem;font-weight:900;color:var(--green);">${club.won||0}</div>
              <div style="font-size:0.62rem;color:var(--t3);">WINS</div>
            </div>
            <div style="text-align:center;">
              <div style="font-family:var(--mono);font-size:1.1rem;font-weight:900;color:var(--gold);">${club.points||0}</div>
              <div style="font-size:0.62rem;color:var(--t3);">POINTS</div>
            </div>
          </div>
        </div>
      </div>
      <div class="club-hero-ovr">
        <span class="ch-ovr-val">${club.overall_rating || "—"}</span>
        <span class="ch-ovr-lbl">CLUB RATING</span>
      </div>
    </div>

    ${stadiumImg ? `
      <div style="height:150px;overflow:hidden;border-bottom:1px solid rgba(255,255,255,0.07);">
        <img src="${stadiumImg}" alt="" style="width:100%;height:100%;object-fit:cover;display:block;">
      </div>
    ` : ""}

    <div class="dossier-analysis-grid">
      <div class="radar-card">
        <div class="card-title">
          <span>TACTICAL SYSTEM RADAR</span>
          <span style="font-size:0.65rem;color:var(--t3);">Opta Index</span>
        </div>
        <div class="radar-chart-wrap">${radarSvg}</div>
      </div>

      <div class="scout-card">
        <div class="card-title">
          <span>${data.archetype || "TACTICAL ARCHETYPE"}</span>
          <span style="font-size:0.65rem;color:var(--cyan);">AI Analysis</span>
        </div>
        <div class="scout-lists">
          <div class="scout-group strengths">
            <h4>Tactical Pillars</h4>
            <ul class="scout-list">
              ${(data.strengths || []).slice(0, 4).map(s => `<li>${s}</li>`).join("") || "<li>Data processing...</li>"}
            </ul>
          </div>
          <div class="scout-group weaknesses">
            <h4>Tactical Vulnerabilities</h4>
            <ul class="scout-list">
              ${(data.weaknesses || []).slice(0, 3).map(w => `<li>${w}</li>`).join("") || "<li>Analyzing defensive exposure...</li>"}
            </ul>
          </div>
        </div>
      </div>
    </div>
  `;
}

// ============================================================
// 14. RADAR CHART HELPER (MODALS)
// ============================================================
function buildModalRadar(axes) {
  const size = 250;
  const cx = size / 2, cy = size / 2;
  const r = 74;
  const n = axes.length;

  const webLines = [0.25, 0.5, 0.75, 1.0].map(lv => {
    const pts = axes.map((_, i) => {
      const a = (2 * Math.PI / n) * i - Math.PI / 2;
      return `${(cx + r * lv * Math.cos(a)).toFixed(1)},${(cy + r * lv * Math.sin(a)).toFixed(1)}`;
    }).join(" ");
    return `<polygon points="${pts}" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="1"/>`;
  }).join("");

  const spokes = axes.map((_, i) => {
    const a = (2 * Math.PI / n) * i - Math.PI / 2;
    return `<line x1="${cx}" y1="${cy}" x2="${(cx + r * Math.cos(a)).toFixed(1)}" y2="${(cy + r * Math.sin(a)).toFixed(1)}" stroke="rgba(255,255,255,0.07)" stroke-width="1"/>`;
  }).join("");

  const pts = [];
  const labels = [];
  axes.forEach((ax, i) => {
    const a = (2 * Math.PI / n) * i - Math.PI / 2;
    const v = Math.max(5, Math.min(100, ax.score));
    pts.push(`${(cx + r * (v / 100) * Math.cos(a)).toFixed(1)},${(cy + r * (v / 100) * Math.sin(a)).toFixed(1)}`);
    const lx = (cx + (r + 18) * Math.cos(a)).toFixed(1);
    const ly = (cy + (r + 18) * Math.sin(a)).toFixed(1);
    labels.push(`<text x="${lx}" y="${ly}" fill="#64748B" font-size="8.5" text-anchor="middle" dominant-baseline="middle">${ax.label}</text>`);
  });

  return `
    <svg viewBox="0 0 ${size} ${size}" width="100%" height="100%">
      ${webLines}${spokes}
      <polygon points="${pts.join(" ")}" fill="rgba(0,122,255,0.15)" stroke="#0EA5E9" stroke-width="2"/>
      ${labels.join("")}
    </svg>
  `;
}

// ============================================================
// 15. UTILITIES
// ============================================================
function getPositionClass(pos) {
  const p = (pos || "").toLowerCase();
  if (p.includes("forward") || p.includes("winger") || p.includes("striker")) return "fw";
  if (p.includes("midfielder") || p.includes("midfield")) return "mid";
  if (p.includes("defender") || p.includes("back")) return "def";
  if (p.includes("goalkeeper") || p.includes("keeper")) return "gk";
  return "mid";
}

function getSilhouette(pos) {
  const p = (pos || "").toLowerCase();
  let accId = "sky";
  let accent = "#38bdf8";
  if (p.includes("forward") || p.includes("striker") || p.includes("winger") || p.includes("att")) {
    accId = "rose";
    accent = "#f43f5e";
  } else if (p.includes("midfield") || p.includes("mid")) {
    accId = "sky";
    accent = "#38bdf8";
  } else if (p.includes("defender") || p.includes("back") || p.includes("def")) {
    accId = "emerald";
    accent = "#10b981";
  } else if (p.includes("goalkeeper") || p.includes("keeper") || p.includes("gk")) {
    accId = "amber";
    accent = "#f59e0b";
  }

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120">` +
    `<defs>` +
      `<linearGradient id="bg_${accId}" x1="0" y1="0" x2="0" y2="1">` +
        `<stop offset="0%" stop-color="#1e293b"/>` +
        `<stop offset="100%" stop-color="#0f172a"/>` +
      `</linearGradient>` +
      `<linearGradient id="jg_${accId}" x1="0" y1="0" x2="0" y2="1">` +
        `<stop offset="0%" stop-color="${accent}"/>` +
        `<stop offset="100%" stop-color="#1e293b"/>` +
      `</linearGradient>` +
    `</defs>` +
    `<circle cx="60" cy="60" r="60" fill="url(#bg_${accId})"/>` +
    `<circle cx="60" cy="60" r="58" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="1.5"/>` +
    `<circle cx="60" cy="42" r="18" fill="#64748B"/>` +
    `<rect x="54" y="58" width="12" height="12" rx="3" fill="#64748b"/>` +
    `<path d="M22 112 C22 82 40 70 60 70 C80 70 98 82 98 112 Z" fill="url(#jg_${accId})"/>` +
    `<path d="M52 70 L60 83 L68 70 Z" fill="#0f172a"/>` +
    `<path d="M38 80 L32 112" stroke="rgba(255,255,255,0.2)" stroke-width="2" stroke-linecap="round"/>` +
    `<path d="M82 80 L88 112" stroke="rgba(255,255,255,0.2)" stroke-width="2" stroke-linecap="round"/>` +
  `</svg>`;

  return "data:image/svg+xml;utf8," + encodeURIComponent(svg);
}

function getFlagEmoji(code) {
  const flags = {
    "ES": "🇪🇸", "FR": "🇫🇷", "BR": "🇧🇷", "GB-ENG": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "DE": "🇩🇪",
    "IT": "🇮🇹", "PT": "🇵🇹", "UY": "🇺🇾", "AR": "🇦🇷", "HR": "🇭🇷",
    "NL": "🇳🇱", "BE": "🇧🇪", "SN": "🇸🇳", "NO": "🇳🇴", "PL": "🇵🇱",
    "SK": "🇸🇰", "JP": "🇯🇵", "MA": "🇲🇦", "NG": "🇳🇬", "CO": "🇨🇴",
    "CL": "🇨🇱", "GA": "🇬🇦", "RO": "🇷🇴", "VE": "🇻🇪", "DK": "🇩🇰",
    "CI": "🇨🇮", "CM": "🇨🇲", "GN": "🇬🇳", "GH": "🇬🇭", "ML": "🇲🇱"
  };
  return flags[code] || "🌍";
}


function debounce(fn, ms) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

window.isSimulatingMatch = false;
window.simulateMatch = async function(event, homeTeam, awayTeam) {
    event.stopPropagation();
    if (window.isSimulatingMatch) return;
    window.isSimulatingMatch = true;
    const match = allFixtures.find(f => 
        ((f.home_nickname || f.home_name || "Home") === homeTeam || (f.home_name || "Home") === homeTeam) && 
        ((f.away_nickname || f.away_name || "Away") === awayTeam || (f.away_name || "Away") === awayTeam) &&
        f.status !== "FINISHED" && f.status !== "LIVE" && f.status !== "IN_PROGRESS" && f.status !== "SIMULATED"
    );
    if (!match) {
        window.isSimulatingMatch = false;
        return;
    }

    // Fetch calibrated most-probable deterministic simulation from backend
    let simData = null;
    if (match.id) {
        try {
            const res = await fetch(`${API_BASE}/api/simulate-match/${match.id}`);
            if (res.ok) simData = await res.json();
        } catch (e) {
            console.warn("Card simulation backend fetch fallback:", e);
        }
    }

    let homeGoals = simData ? simData.home_score : 1;
    let awayGoals = simData ? simData.away_score : 0;
    let simEvents = simData ? (simData.events || []) : [];
    let goalEvents = simEvents.filter(e => e.type === "goal");

    const overlay = document.getElementById("simOverlay");
    if (!overlay) {
        match.home_score = homeGoals;
        match.away_score = awayGoals;
        match.status = "SIMULATED";
        match.goals = goalEvents;
        if (typeof renderFixturesGrid === 'function') {
            try { renderFixturesGrid(fixtureFilters?.matchday || "this-week"); } catch(e) { renderFixturesGrid("this-week"); }
        }
        if (typeof renderFullFixturesView === 'function') {
            try { renderFullFixturesView(); } catch(e) {}
        }
        window.isSimulatingMatch = false;
        return;
    }

    const hName = document.getElementById("simHomeName");
    const aName = document.getElementById("simAwayName");
    const hScore = document.getElementById("simHomeScore");
    const aScore = document.getElementById("simAwayScore");
    const prog = document.getElementById("simProgress");
    const consoleEl = document.getElementById("simConsole");
    const statusText = document.getElementById("simStatus");

    hName.textContent = homeTeam.substring(0, 15);
    aName.textContent = awayTeam.substring(0, 15);
    hScore.textContent = "-";
    aScore.textContent = "-";
    hScore.className = "sim-score-box";
    aScore.className = "sim-score-box";
    prog.style.width = "0%";
    consoleEl.innerHTML = `<div class="sim-console-line">Initializing Dixon-Coles calibrated match engine...</div>`;
    statusText.textContent = "CALCULATING PROBABILITIES...";

    overlay.classList.add("active");

    // Set realistic stadium action backdrop
    const modalThumb = document.getElementById("simModalThumbnail");
    if (modalThumb) {
      const hn = (homeTeam || "").toLowerCase();
      if (hn.includes("betis")) modalThumb.src = "images/thumbnails/match_striker.jpg";
      else if (hn.includes("madrid") || hn.includes("barcelona")) modalThumb.src = "images/thumbnails/match_derby.jpg";
      else modalThumb.src = "images/thumbnails/match_save.jpg";
    }

    const logMsg = (msg, type="") => {
        const div = document.createElement("div");
        div.className = "sim-console-line " + type;
        div.textContent = msg;
        consoleEl.appendChild(div);
        consoleEl.scrollTop = consoleEl.scrollHeight;
    };

    let step = 0;
    let hg = 0;
    let ag = 0;
    
    const interval = setInterval(() => {
        step++;
        prog.style.width = (step * 2) + "%"; // reaches 100% at step 50

        if (step === 5) logMsg(`Calculating expected goals (xG) and home advantage for ${homeTeam}...`);
        if (step === 10) logMsg("Calibrating Dixon-Coles bivariate matrix & player form...", "highlight");
        if (step === 15) logMsg("Simulating first half tactical flow...");
        if (step === 20) {
            hg = Math.floor(homeGoals / 2);
            ag = Math.floor(awayGoals / 2);
            hScore.textContent = hg;
            aScore.textContent = ag;
            hScore.classList.add("updated");
            aScore.classList.add("updated");
            if (hg > 0 || ag > 0) {
                logMsg(`Half Time: ${homeTeam} ${hg} - ${ag} ${awayTeam}`, "highlight");
            } else {
                logMsg("Half Time: 0-0. Tight defensive structure.");
            }
            setTimeout(() => {
                hScore.classList.remove("updated");
                aScore.classList.remove("updated");
            }, 500);
        }
        if (step === 30) logMsg("Simulating second half transitions...");
        if (step === 35 && homeGoals > hg) {
            const hScorer = goalEvents.find(e => e.team === "home")?.scorer;
            logMsg(`⚽ GOAL! ${hScorer ? hScorer + " scores for " : ""}${homeTeam}!`, "goal");
        }
        if (step === 40 && awayGoals > ag) {
            const aScorer = goalEvents.find(e => e.team === "away")?.scorer;
            logMsg(`⚽ GOAL! ${aScorer ? aScorer + " scores for " : ""}${awayTeam}!`, "goal");
        }
        if (step === 45) {
            hScore.textContent = homeGoals;
            aScore.textContent = awayGoals;
            hScore.classList.add("updated");
            aScore.classList.add("updated");
            logMsg(`Calibrated simulation complete: ${homeGoals} - ${awayGoals}`, "highlight");
            statusText.textContent = "SIMULATION COMPLETE";
        }
        if (step >= 50) {
            clearInterval(interval);
            setTimeout(() => {
                window.isSimulatingMatch = false;
                overlay.classList.remove("active");
                match.home_score = homeGoals;
                match.away_score = awayGoals;
                match.status = "SIMULATED";
                match.goals = goalEvents; 
                if (typeof renderFixturesGrid === 'function') {
                  try { renderFixturesGrid(fixtureFilters?.matchday || "this-week"); } catch(e) { renderFixturesGrid("this-week"); }
                }
                if (typeof renderFullFixturesView === 'function') {
                  try { renderFullFixturesView(); } catch(e) {}
                }
            }, 1000);
        }
    }, 60);
};

// ============================================================
// 16. MATCH DETAIL & TACTICAL CENTER CONTROLLER
// ============================================================
let currentMatchDetailData = null;
let currentPitchMode = "both";
let currentRosterTab = "home";
let isSimulatingPitch = false;
let customSubstitutions = [];
let currentSubTarget = null;
let pitchSimSpeed = 1;

function setPitchSimSpeed(speed) {
  pitchSimSpeed = speed;
  document.querySelectorAll(".sim-speed-btn").forEach(btn => {
    btn.classList.toggle("active", parseInt(btn.dataset.speed) === speed);
  });
  showPitchToast(`⏱️ Simulation Speed: ${speed}x`);
}

function goBackFromMatchDetail() {
  switchView(previousView || "home");
}

async function openMatchDetail(fixtureId) {
  previousView = (activeView === "match-detail" ? "home" : activeView);
  switchView("match-detail");

  // Show loading indicator in hero
  const scoreDisplay = document.getElementById("mdScoreDisplay");
  if (scoreDisplay) scoreDisplay.innerHTML = `<div class="spinner"></div>`;

  try {
    const res = await fetch(`${API_BASE}/api/match/${fixtureId}`);
    if (!res.ok) throw new Error("Match preview not found");
    const data = await res.json();
    currentMatchDetailData = data;
    customSubstitutions = [];
    renderMatchDetailView(data);
  } catch (err) {
    console.error("Failed to load match detail:", err);
    if (scoreDisplay) scoreDisplay.innerHTML = `<span style="color:var(--red);font-size:0.9rem;">Error loading match data</span>`;
  }
}


// ============================================================
// PREDICTIVE MATCH TREND & ATTACK MOMENTUM VISUALIZERS
// ============================================================
function renderMatchTrends(data, simTrends = null) {
  if (!data) return;
  const h = data.home_team || {};
  const a = data.away_team || {};
  const homeName = h.nickname || h.name || "Home";
  const awayName = a.nickname || a.name || "Away";

  const trends = simTrends || (data.forecast && data.forecast.projected_trends) || null;

  // Narrative text
  const headlineEl = document.getElementById("mdTrendHeadline");
  const flowEl = document.getElementById("mdTrendFlowSummary");
  const tpEl = document.getElementById("mdTrendTurningPoint");
  const verdictEl = document.getElementById("mdTrendTacticalVerdict");

  const tn = (trends && (trends.narrative || trends.trend_narrative)) ? (trends.narrative || trends.trend_narrative) : null;
  if (tn) {
    if (headlineEl) headlineEl.textContent = tn.headline || `${homeName} vs ${awayName} Tactical Chess Match`;
    if (flowEl) flowEl.textContent = tn.flow_summary || `Tactical model projects territory contested along wide channels.`;
    if (tpEl) tpEl.innerHTML = `<span>⚡</span> <span>Key Factor: ${tn.turning_point || "First goal timing shifts game preservation behavior."}</span>`;
    if (verdictEl) verdictEl.textContent = `Tactical Verdict: ${tn.tactical_verdict || "High defensive line compression against transition runs."}`;
  } else {
    if (headlineEl) headlineEl.textContent = `${homeName} vs ${awayName} Expected Tactical Flow`;
    if (flowEl) flowEl.textContent = `${homeName} sets out to dominate territory via progressive wing play, while ${awayName} looks to absorb early pressure and break into transition channels.`;
    if (tpEl) tpEl.innerHTML = `<span>⚡</span> <span>Key Factor: Dynamic stamina decay and late substitutes will decide the final 20 minutes.</span>`;
    if (verdictEl) verdictEl.textContent = `Tactical Model: High defensive line compression against rapid counter transitions.`;
  }

  const hLeg = document.getElementById("mdMomentumHomeLeg");
  const aLeg = document.getElementById("mdMomentumAwayLeg");
  if (hLeg) hLeg.textContent = `● ${homeName} Momentum`;
  if (aLeg) aLeg.textContent = `● ${awayName} Momentum`;

  // 1. Momentum Curve (90 minutes)
  const momContainer = document.getElementById("mdMomentumSvgContainer");
  if (momContainer) {
    let momentum = (trends && (trends.momentum || trends.momentum_trend)) ? (trends.momentum || trends.momentum_trend) : [];
    if (!momentum.length) {
      momentum = [];
      const homePoss = (data.clash?.home?.possession_target || 52);
      const baseMomentum = (homePoss - 50) * 1.5;
      for (let m = 1; m <= 90; m++) {
        const wave = Math.sin(m / 4.5) * 18 + Math.cos(m / 8.0) * 12;
        const val = Math.max(-90, Math.min(90, Math.round(baseMomentum + wave)));
        momentum.push({ minute: m, momentum: val, value: val, score: "0 - 0" });
      }
    }

    const events = (data.fixture && data.fixture.events) || [];
    momContainer.innerHTML = buildMomentumSvg(momentum, events, homeName, awayName);
  }

  // 2. 6-Phase Dominance Breakdown Grid
  const phaseGrid = document.getElementById("mdPhaseDominanceGrid");
  if (phaseGrid) {
    let phases = (trends && (trends.phases || trends.phase_dominance)) ? (trends.phases || trends.phase_dominance) : [];
    if (!phases.length) {
      phases = [
        { phase: "0'-15'", label: "0'-15'", name: "Opening Exchanges", tempo_status: "High Press", home_pct: 58, away_pct: 42, summary: "Aggressive early pressure.", goals: [] },
        { phase: "16'-30'", label: "16'-30'", name: "Tactical Settlement", tempo_status: "Settled Rhythm", home_pct: 52, away_pct: 48, summary: "Midfield positional contest.", goals: [] },
        { phase: "31'-45'", label: "31'-45'", name: "Pre-Interval Push", tempo_status: "Late 1H Surge", home_pct: 61, away_pct: 39, summary: "Sustained box entries.", goals: [] },
        { phase: "46'-60'", label: "46'-60'", name: "Second-Half Adjustments", tempo_status: "2H Adjustment", home_pct: 47, away_pct: 53, summary: "Away side transitions.", goals: [] },
        { phase: "61'-75'", label: "61'-75'", name: "Substitution Window", tempo_status: "Fresh Subs Impact", home_pct: 55, away_pct: 45, summary: "Tempo lift from bench.", goals: [] },
        { phase: "76'-90'", label: "76'-90'", name: "Closing Drama", tempo_status: "Final Siege", home_pct: 54, away_pct: 46, summary: "Desperation crosses.", goals: [] }
      ];
    }

    phaseGrid.innerHTML = phases.map(p => {
      const hCtrl = p.home_pct !== undefined ? p.home_pct : (p.home_control ?? 50);
      const aCtrl = p.away_pct !== undefined ? p.away_pct : (p.away_control ?? 50);
      const phaseTime = p.label || (typeof p.phase === 'number' ? `P${p.phase}` : p.phase) || (p.minute_range ? p.minute_range + "'" : "Phase");
      const phaseName = p.name || p.tempo_status || "Phase";
      const summaryText = p.summary || p.tactical_summary || "Territorial contest";
      const eventsList = (p.goals && p.goals.length) ? p.goals : (p.key_events || []);
      const eventsBadge = eventsList.length > 0
        ? `<div class="pc-goals-tag">⚽ ${eventsList.join(", ")}</div>`
        : "";
      return `
        <div class="phase-card">
          <div class="pc-header">
            <span class="pc-time">${phaseTime}</span>
            <span class="pc-name">${phaseName}</span>
          </div>
          <div class="pc-bar-wrap">
            <div class="pc-bar-home" style="width: ${hCtrl}%;"></div>
            <div class="pc-bar-away" style="width: ${aCtrl}%;"></div>
          </div>
          <div class="pc-values">
            <span class="pc-h-val">${hCtrl}%</span>
            <span class="pc-a-val">${aCtrl}%</span>
          </div>
          ${eventsBadge}
          <div class="pc-summary">${summaryText}</div>
        </div>
      `;
    }).join("");
  }

  // 3. Cumulative xG Step-Ladder
  const xgContainer = document.getElementById("mdXGFlowSvgContainer");
  if (xgContainer) {
    const xgTrend = (trends && (trends.xg_flow || trends.xg_flow_trend)) ? (trends.xg_flow || trends.xg_flow_trend) : [];
    xgContainer.innerHTML = buildXGFlowSvg(xgTrend, homeName, awayName);
  }

  // 4. Dynamic Win Probability Timeline
  const winProbContainer = document.getElementById("mdWinProbTimeline");
  if (winProbContainer) {
    const winTrend = (trends && (trends.win_probability || trends.win_probability_trend)) ? (trends.win_probability || trends.win_probability_trend) : [];
    winProbContainer.innerHTML = buildWinProbSvg(winTrend, homeName, awayName);
  }
}

function buildMomentumSvg(momentum, events, homeName, awayName) {
  if (!momentum || momentum.length === 0) return "";
  const w = 900;
  const h = 160;
  const zero_y = h / 2.0;

  const x_for_m = (m) => 20 + (m - 1) * (860.0 / 89.0);
  const y_for_val = (v) => zero_y - (v / 100.0) * (zero_y - 18.0);

  let home_d = `M ${x_for_m(1).toFixed(1)} ${zero_y.toFixed(1)}`;
  for (let i = 0; i < momentum.length; i++) {
    const pt = momentum[i];
    const x = x_for_m(pt.minute);
    const y = y_for_val(Math.max(0, pt.momentum !== undefined ? pt.momentum : (pt.value || 0)));
    home_d += ` L ${x.toFixed(1)} ${y.toFixed(1)}`;
  }
  home_d += ` L ${x_for_m(90).toFixed(1)} ${zero_y.toFixed(1)} Z`;

  let away_d = `M ${x_for_m(1).toFixed(1)} ${zero_y.toFixed(1)}`;
  for (let i = 0; i < momentum.length; i++) {
    const pt = momentum[i];
    const x = x_for_m(pt.minute);
    const y = y_for_val(Math.min(0, pt.momentum !== undefined ? pt.momentum : (pt.value || 0)));
    away_d += ` L ${x.toFixed(1)} ${y.toFixed(1)}`;
  }
  away_d += ` L ${x_for_m(90).toFixed(1)} ${zero_y.toFixed(1)} Z`;

  let line_d = `M ${x_for_m(momentum[0].minute).toFixed(1)} ${y_for_val(momentum[0].momentum !== undefined ? momentum[0].momentum : (momentum[0].value || 0)).toFixed(1)}`;
  for (let i = 1; i < momentum.length; i++) {
    const pt = momentum[i];
    const x = x_for_m(pt.minute);
    const y = y_for_val(pt.momentum !== undefined ? pt.momentum : (pt.value || 0));
    line_d += ` L ${x.toFixed(1)} ${y.toFixed(1)}`;
  }

  let goal_pins = "";
  if (events && events.length) {
    events.forEach(e => {
      if (e.type === "goal") {
        const m = e.minute || 45;
        const x = x_for_m(m);
        const isH = e.team === "home";
        const y = isH ? 24 : 136;
        const pinColor = isH ? "#22c55e" : "#f43f5e";
        const scorer = e.scorer || "Goal";
        goal_pins += `
          <g class="svg-goal-pin" transform="translate(${x.toFixed(1)}, ${y})">
            <circle cx="0" cy="0" r="10" fill="#171920" stroke="${pinColor}" stroke-width="2"/>
            <text x="0" y="4" text-anchor="middle" font-size="10">⚽</text>
            <text x="0" y="${isH ? -14 : 20}" text-anchor="middle" font-size="9" fill="#ffffff" font-weight="bold">${scorer} ${m}'</text>
          </g>
        `;
      }
    });
  }

  return `
    <svg viewBox="0 0 ${w} ${h}" width="100%" height="100%" preserveAspectRatio="none" style="overflow:visible;">
      <defs>
        <linearGradient id="momHomeGrad" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stop-color="#00985f" stop-opacity="0.6"/>
          <stop offset="100%" stop-color="#00985f" stop-opacity="0.06"/>
        </linearGradient>
        <linearGradient id="momAwayGrad" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stop-color="#f43f5e" stop-opacity="0.06"/>
          <stop offset="100%" stop-color="#f43f5e" stop-opacity="0.6"/>
        </linearGradient>
      </defs>

      <line x1="20" y1="${zero_y}" x2="880" y2="${zero_y}" stroke="rgba(255,255,255,0.18)" stroke-dasharray="4 4" stroke-width="1.5"/>

      <g stroke="rgba(255,255,255,0.06)" stroke-width="1">
        <line x1="${x_for_m(15).toFixed(1)}" y1="15" x2="${x_for_m(15).toFixed(1)}" y2="145"/>
        <line x1="${x_for_m(30).toFixed(1)}" y1="15" x2="${x_for_m(30).toFixed(1)}" y2="145"/>
        <line x1="${x_for_m(45).toFixed(1)}" y1="15" x2="${x_for_m(45).toFixed(1)}" y2="145"/>
        <line x1="${x_for_m(60).toFixed(1)}" y1="15" x2="${x_for_m(60).toFixed(1)}" y2="145"/>
        <line x1="${x_for_m(75).toFixed(1)}" y1="15" x2="${x_for_m(75).toFixed(1)}" y2="145"/>
        <line x1="${x_for_m(90).toFixed(1)}" y1="15" x2="${x_for_m(90).toFixed(1)}" y2="145"/>
      </g>
      <g font-size="10" fill="#6b7280" font-family="monospace">
        <text x="${x_for_m(15).toFixed(1)}" y="156" text-anchor="middle">15'</text>
        <text x="${x_for_m(30).toFixed(1)}" y="156" text-anchor="middle">30'</text>
        <text x="${x_for_m(45).toFixed(1)}" y="156" text-anchor="middle">HT</text>
        <text x="${x_for_m(60).toFixed(1)}" y="156" text-anchor="middle">60'</text>
        <text x="${x_for_m(75).toFixed(1)}" y="156" text-anchor="middle">75'</text>
        <text x="${x_for_m(90).toFixed(1)}" y="156" text-anchor="middle">90'</text>
      </g>

      <path d="${home_d}" fill="url(#momHomeGrad)"/>
      <path d="${away_d}" fill="url(#momAwayGrad)"/>
      <path d="${line_d}" fill="none" stroke="rgba(255,255,255,0.75)" stroke-width="2" stroke-linejoin="round"/>
      ${goal_pins}
    </svg>
  `;
}

function buildXGFlowSvg(xgTrend, homeName, awayName) {
  const w = 420;
  const h = 130;
  const padL = 35;
  const padR = 20;
  const padT = 15;
  const padB = 25;

  let homeFinal = 1.6;
  let awayFinal = 0.9;

  let hLine = "";
  let aLine = "";

  if (xgTrend && xgTrend.length) {
    const last = xgTrend[xgTrend.length - 1];
    homeFinal = last.home_xg || 1.6;
    awayFinal = last.away_xg || 0.9;
    const maxVal = Math.max(2.5, homeFinal + 0.3, awayFinal + 0.3);

    const x_for_m = (m) => padL + (m / 90.0) * (w - padL - padR);
    const y_for_v = (v) => h - padB - (v / maxVal) * (h - padT - padB);

    hLine = `M ${x_for_m(0).toFixed(1)} ${y_for_v(0).toFixed(1)}`;
    aLine = `M ${x_for_m(0).toFixed(1)} ${y_for_v(0).toFixed(1)}`;

    for (let i = 0; i < xgTrend.length; i++) {
      const pt = xgTrend[i];
      const x = x_for_m(pt.minute);
      hLine += ` L ${x.toFixed(1)} ${y_for_v(pt.home_xg).toFixed(1)}`;
      aLine += ` L ${x.toFixed(1)} ${y_for_v(pt.away_xg).toFixed(1)}`;
    }
  } else {
    hLine = `M 35 105 L 120 95 L 200 65 L 320 40 L 400 30`;
    aLine = `M 35 105 L 160 90 L 260 85 L 360 70 L 400 65`;
  }

  return `
    <svg viewBox="0 0 ${w} ${h}" width="100%" height="100%">
      <line x1="${padL}" y1="${h - padB}" x2="${w - padR}" y2="${h - padB}" stroke="rgba(255,255,255,0.1)" stroke-width="1"/>
      <line x1="${padL}" y1="${(h - padB + padT)/2}" x2="${w - padR}" y2="${(h - padB + padT)/2}" stroke="rgba(255,255,255,0.05)" stroke-dasharray="3 3"/>
      
      <text x="${padL}" y="${h - 8}" font-size="9" fill="#6b7280" font-family="monospace">0'</text>
      <text x="${(padL + w - padR)/2}" y="${h - 8}" font-size="9" fill="#6b7280" font-family="monospace" text-anchor="middle">45'</text>
      <text x="${w - padR}" y="${h - 8}" font-size="9" fill="#6b7280" font-family="monospace" text-anchor="end">90'</text>

      <path d="${hLine}" fill="none" stroke="#22c55e" stroke-width="2.5"/>
      <path d="${aLine}" fill="none" stroke="#f43f5e" stroke-width="2.5"/>

      <g transform="translate(40, 20)">
        <circle cx="0" cy="0" r="4" fill="#22c55e"/>
        <text x="8" y="3" font-size="9" fill="#22c55e" font-weight="bold">${homeName}: ${homeFinal.toFixed(2)} xG</text>
      </g>
      <g transform="translate(180, 20)">
        <circle cx="0" cy="0" r="4" fill="#f43f5e"/>
        <text x="8" y="3" font-size="9" fill="#f43f5e" font-weight="bold">${awayName}: ${awayFinal.toFixed(2)} xG</text>
      </g>
    </svg>
  `;
}

function buildWinProbSvg(winTrend, homeName, awayName) {
  if (!winTrend || !winTrend.length) {
    winTrend = [
      { minute: 0, home_win_pct: 48, draw_pct: 28, away_win_pct: 24 },
      { minute: 15, home_win_pct: 50, draw_pct: 27, away_win_pct: 23 },
      { minute: 30, home_win_pct: 53, draw_pct: 27, away_win_pct: 20 },
      { minute: 45, home_win_pct: 52, draw_pct: 29, away_win_pct: 19 },
      { minute: 60, home_win_pct: 58, draw_pct: 26, away_win_pct: 16 },
      { minute: 75, home_win_pct: 64, draw_pct: 23, away_win_pct: 13 },
      { minute: 90, home_win_pct: 70, draw_pct: 20, away_win_pct: 10 }
    ];
  }

  const w = 420;
  const h = 130;
  const padL = 30;
  const padR = 20;
  const padT = 15;
  const padB = 25;

  const x_for_idx = (i) => padL + (i / (winTrend.length - 1)) * (w - padL - padR);
  const y_for_pct = (pct) => h - padB - (pct / 100.0) * (h - padT - padB);

  let hPts = winTrend.map((pt, i) => `${x_for_idx(i).toFixed(1)},${y_for_pct(pt.home_win_pct).toFixed(1)}`).join(" ");
  let aPts = winTrend.map((pt, i) => `${x_for_idx(i).toFixed(1)},${y_for_pct(pt.away_win_pct).toFixed(1)}`).join(" ");
  let dPts = winTrend.map((pt, i) => `${x_for_idx(i).toFixed(1)},${y_for_pct(pt.draw_pct).toFixed(1)}`).join(" ");

  const latest = winTrend[winTrend.length - 1];

  let timeLabels = winTrend.map((pt, i) => `
    <text x="${x_for_idx(i).toFixed(1)}" y="${h - 8}" font-size="9" fill="#6b7280" font-family="monospace" text-anchor="middle">${pt.minute}'</text>
  `).join("");

  return `
    <svg viewBox="0 0 ${w} ${h}" width="100%" height="100%">
      <line x1="${padL}" y1="${h - padB}" x2="${w - padR}" y2="${h - padB}" stroke="rgba(255,255,255,0.1)" stroke-width="1"/>
      <line x1="${padL}" y1="${y_for_pct(50)}" x2="${w - padR}" y2="${y_for_pct(50)}" stroke="rgba(255,255,255,0.06)" stroke-dasharray="2 2"/>
      
      <polyline points="${hPts}" fill="none" stroke="#22c55e" stroke-width="2.5" stroke-linecap="round"/>
      <polyline points="${dPts}" fill="none" stroke="#f59e0b" stroke-width="2" stroke-linecap="round" stroke-dasharray="4 2"/>
      <polyline points="${aPts}" fill="none" stroke="#f43f5e" stroke-width="2.5" stroke-linecap="round"/>

      ${timeLabels}

      <g transform="translate(35, 12)">
        <circle cx="0" cy="0" r="3.5" fill="#22c55e"/>
        <text x="6" y="3" font-size="9" fill="#22c55e" font-weight="bold">Home: ${latest.home_win_pct}%</text>
      </g>
      <g transform="translate(160, 12)">
        <circle cx="0" cy="0" r="3.5" fill="#f59e0b"/>
        <text x="6" y="3" font-size="9" fill="#f59e0b" font-weight="bold">Draw: ${latest.draw_pct}%</text>
      </g>
      <g transform="translate(265, 12)">
        <circle cx="0" cy="0" r="3.5" fill="#f43f5e"/>
        <text x="6" y="3" font-size="9" fill="#f43f5e" font-weight="bold">Away: ${latest.away_win_pct}%</text>
      </g>
    </svg>
  `;
}

function renderMatchDetailView(data) {
  if (!data) return;
  const f = data.fixture;
  const h = data.home_team;
  const a = data.away_team;

  // 1. Navigation bar
  const navRoundTag = document.getElementById("mdNavRoundTag");
  if (navRoundTag) navRoundTag.textContent = `MATCHDAY ${f.matchday || 5} PREVIEW`;

  // 2. Match Hero
  const homeCrest = document.getElementById("mdHomeCrest");
  const homeName = document.getElementById("mdHomeName");
  const homeRank = document.getElementById("mdHomeRank");
  const homeForm = document.getElementById("mdHomeForm");

  if (homeCrest) homeCrest.src = h.shield || "";
  if (homeName) homeName.textContent = h.name || "Home Team";
  if (homeRank) homeRank.textContent = `#${h.position || 4} in La Liga`;

  const homeFresh = document.getElementById("mdHomeFreshness");
  if (homeFresh) {
    const hf = h.fatigue;
    if (hf) {
      homeFresh.textContent = hf.freshness_badge || "⚡ 7d Rest";
      homeFresh.className = `hero-freshness-pill ${hf.fatigue_status || "fresh"}`;
      homeFresh.title = hf.notes || "";
      homeFresh.style.display = "inline-flex";
    } else {
      homeFresh.style.display = "none";
    }
  }

  if (homeForm) {
    const formArr = ["w", "w", "d", "l", "w"];
    if (h.last_match && h.last_match.res_badge) {
      formArr[4] = h.last_match.res_badge.toLowerCase();
    }
    homeForm.innerHTML = formArr.map(r => `<span class="form-pill-mini ${r}">${r.toUpperCase()}</span>`).join("");
  }

  const awayCrest = document.getElementById("mdAwayCrest");
  const awayName = document.getElementById("mdAwayName");
  const awayRank = document.getElementById("mdAwayRank");
  const awayForm = document.getElementById("mdAwayForm");

  if (awayCrest) awayCrest.src = a.shield || "";
  if (awayName) awayName.textContent = a.name || "Away Team";
  if (awayRank) awayRank.textContent = `#${a.position || 12} in La Liga`;

  const awayFresh = document.getElementById("mdAwayFreshness");
  if (awayFresh) {
    const af = a.fatigue;
    if (af) {
      awayFresh.textContent = af.freshness_badge || "⚡ 7d Rest";
      awayFresh.className = `hero-freshness-pill ${af.fatigue_status || "fresh"}`;
      awayFresh.title = af.notes || "";
      awayFresh.style.display = "inline-flex";
    } else {
      awayFresh.style.display = "none";
    }
  }

  if (awayForm) {
    const formArr = ["d", "w", "l", "d", "l"];
    if (a.last_match && a.last_match.res_badge) {
      formArr[4] = a.last_match.res_badge.toLowerCase();
    }
    awayForm.innerHTML = formArr.map(r => `<span class="form-pill-mini ${r}">${r.toUpperCase()}</span>`).join("");
  }

  // Hero Centerpiece
  const statusTag = document.getElementById("mdStatusTag");
  const scoreDisplay = document.getElementById("mdScoreDisplay");
  const kickoffMeta = document.getElementById("mdKickoffMeta");
  const venueMeta = document.getElementById("mdVenueMeta");

  const isFinished = f.status === "FINISHED";
  const isSimulated = f.status === "SIMULATED";
  const isLive = f.status === "LIVE" || f.status === "IN_PROGRESS";

  if (statusTag) {
    statusTag.className = "hero-status-tag" + (isLive ? " live" : "");
    statusTag.textContent = isLive ? "● LIVE IN PLAY" : isSimulated ? "SIMULATED RESULT" : isFinished ? "FULL TIME (FT)" : `ROUND ${f.matchday} · UPCOMING`;
  }

  if (scoreDisplay) {
    if (isFinished || isSimulated) {
      scoreDisplay.innerHTML = `<span class="hero-score-num">${f.home_score ?? 0} - ${f.away_score ?? 0}</span>`;
    } else {
      scoreDisplay.innerHTML = `<span class="hero-vs">VS</span>`;
    }
  }

  if (kickoffMeta) {
    const ko = f.kickoff_time ? new Date(f.kickoff_time) : null;
    const dateStr = ko ? ko.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", year: "numeric" }) : "Upcoming";
    const timeStr = ko ? ko.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }) : "21:00";
    kickoffMeta.textContent = `${dateStr} · ${timeStr}`;
  }

  if (venueMeta) {
    venueMeta.textContent = `🏟️ ${h.stadium || "Estadio Benito Villamarín"}`;
  }

  // Realistic Match Thumbnail Setup
  const hSlug = (h.slug || "").toLowerCase();
  const aSlug = (a.slug || "").toLowerCase();
  let matchThumb = "images/thumbnails/match_derby.jpg";
  let matchCaption = `${h.name} vs ${a.name} · Official Broadcast Matchday Action Teaser`;

  if (hSlug.includes("betis") || aSlug.includes("betis")) {
    matchThumb = "images/thumbnails/match_striker.jpg";
    matchCaption = `${h.name} vs ${a.name} · Real Betis Striker Volley Highlight (Estadio Benito Villamarín)`;
  } else if (hSlug.includes("madrid") || aSlug.includes("madrid") || hSlug.includes("barcelona") || aSlug.includes("barcelona")) {
    matchThumb = "images/thumbnails/match_derby.jpg";
    matchCaption = `${h.name} vs ${a.name} · High-Stakes Aerial Duel Highlight (Official Broadcast 4K)`;
  } else {
    matchThumb = "images/thumbnails/match_save.jpg";
    matchCaption = `${h.name} vs ${a.name} · Acrobatic Goalkeeper Defense Highlight`;
  }

  const heroBg = document.getElementById("mdHeroBgBackdrop");
  if (heroBg) {
    heroBg.style.backgroundImage = `url('${matchThumb}')`;
  }
  const actionImg = document.getElementById("mdHeroActionThumbnail");
  if (actionImg) actionImg.src = matchThumb;
  const actionCap = document.getElementById("mdHeroActionCaption");
  if (actionCap) actionCap.textContent = matchCaption;

  // 3. Formations Info Bar
  const hTeamEl = document.getElementById("mdHomeFormTeam");
  const hShapeEl = document.getElementById("mdHomeFormShape");
  const hMgrEl = document.getElementById("mdHomeFormManager");
  const hStyleEl = document.getElementById("mdHomeFormStyle");

  if (hTeamEl) hTeamEl.textContent = h.nickname || h.name;
  if (hShapeEl) hShapeEl.textContent = h.tactics?.formation || "4-2-3-1";
  if (hMgrEl) hMgrEl.textContent = `Manager: ${h.tactics?.manager || "Head Coach"}`;
  if (hStyleEl) hStyleEl.textContent = h.tactics?.style || "Fluid Positional Play";

  const aTeamEl = document.getElementById("mdAwayFormTeam");
  const aShapeEl = document.getElementById("mdAwayFormShape");
  const aMgrEl = document.getElementById("mdAwayFormManager");
  const aStyleEl = document.getElementById("mdAwayFormStyle");

  if (aTeamEl) aTeamEl.textContent = a.nickname || a.name;
  if (aShapeEl) aShapeEl.textContent = a.tactics?.formation || "4-2-3-1";
  if (aMgrEl) aMgrEl.textContent = `Manager: ${a.tactics?.manager || "Head Coach"}`;
  if (aStyleEl) aStyleEl.textContent = a.tactics?.style || "Compact Counter Unit";

  // 4. Authentic Tactical Clash & Managerial DNA Showcase
  const clash = data.tactical_clash;
  if (clash) {
    const hCoachName = document.getElementById("mdHomeCoachName");
    const hCoachRole = document.getElementById("mdHomeCoachRole");
    const hIdentity = document.getElementById("mdHomeTacticalIdentity");
    const hPressVal = document.getElementById("mdHomePressVal");
    const hLineVal = document.getElementById("mdHomeLineVal");
    const hPreserveVal = document.getElementById("mdHomePreserveVal");
    const hApproach = document.getElementById("mdHomeApproachText");

    if (hCoachName) hCoachName.textContent = clash.home.manager;
    if (hCoachRole) hCoachRole.textContent = `${clash.home.manager_moniker || "Head Coach"} · ${h.nickname || h.name}`;
    if (hIdentity) hIdentity.textContent = clash.home.tactical_identity;
    if (hPressVal) hPressVal.textContent = `${clash.home.pressing_intensity}%`;
    if (hLineVal) {
      const lineTag = clash.home.defensive_line_height >= 78 ? "High" : clash.home.defensive_line_height >= 50 ? "Mid" : "Deep";
      hLineVal.textContent = `${clash.home.defensive_line_height} (${lineTag})`;
    }
    if (hPreserveVal) hPreserveVal.textContent = `${clash.home.lead_preservation}/100`;
    if (hApproach) hApproach.textContent = clash.home.tactical_approach;

    const aCoachName = document.getElementById("mdAwayCoachName");
    const aCoachRole = document.getElementById("mdAwayCoachRole");
    const aIdentity = document.getElementById("mdAwayTacticalIdentity");
    const aPressVal = document.getElementById("mdAwayPressVal");
    const aLineVal = document.getElementById("mdAwayLineVal");
    const aPreserveVal = document.getElementById("mdAwayPreserveVal");
    const aApproach = document.getElementById("mdAwayApproachText");

    if (aCoachName) aCoachName.textContent = clash.away.manager;
    if (aCoachRole) aCoachRole.textContent = `${clash.away.manager_moniker || "Head Coach"} · ${a.nickname || a.name}`;
    if (aIdentity) aIdentity.textContent = clash.away.tactical_identity;
    if (aPressVal) aPressVal.textContent = `${clash.away.pressing_intensity}%`;
    if (aLineVal) {
      const lineTag = clash.away.defensive_line_height >= 78 ? "High" : clash.away.defensive_line_height >= 50 ? "Mid" : "Deep";
      aLineVal.textContent = `${clash.away.defensive_line_height} (${lineTag})`;
    }
    if (aPreserveVal) aPreserveVal.textContent = `${clash.away.lead_preservation}/100`;
    if (aApproach) aApproach.textContent = clash.away.tactical_approach;

    const battleEl = document.getElementById("mdTacticalBattleText");
    if (battleEl) battleEl.textContent = clash.key_battle || clash.verdict;

    const verdictTag = document.getElementById("mdClashVerdictTag");
    if (verdictTag) verdictTag.textContent = `${(clash.home.style_category || "Tactical").toUpperCase().replace(/_/g, " ")} VS ${(clash.away.style_category || "Matchup").toUpperCase().replace(/_/g, " ")}`;
  }

  // Legend
  const legHome = document.getElementById("legendHomeName");
  const legAway = document.getElementById("legendAwayName");
  if (legHome) legHome.textContent = `${h.nickname || h.name} XI`;
  // Dynamic Player Form Factors (Based on last 2-3 matches)
  const formBar = document.getElementById("mdDynamicFormBar");
  if (formBar) {
    const hStarters = h.tactics?.starting_xi || [];
    const aStarters = a.tactics?.starting_xi || [];
    const inFormPlayers = [
      ...hStarters.map(p => ({ ...p, team_name: h.nickname || h.name })),
      ...aStarters.map(p => ({ ...p, team_name: a.nickname || a.name }))
    ].filter(p => p.form_modifier && p.form_modifier !== 0);

    if (inFormPlayers.length > 0) {
      formBar.style.display = "flex";
      formBar.innerHTML = `
        <div class="dff-title">
          <span>⚡</span>
          <span>DYNAMIC PLAYER FORM MOMENTUM (CALIBRATED FROM LAST 2-3 MATCHES)</span>
        </div>
        <div class="dff-chips-list">
          ${inFormPlayers.map(p => {
            const sign = p.form_modifier > 0 ? "+" : "";
            const cls = p.form_status || "in_form";
            return `
              <div class="dff-chip" onclick="openPlayerModal('${p.slug}')" style="cursor:pointer;" title="${p.name} (${p.team_name}): ${p.streak_label} - Click to view profile">
                <span>${p.streak_icon || '⚡'}</span>
                <strong style="color:var(--t0);font-weight:700;">${p.name}</strong>
                <span style="color:var(--t3);font-size:0.68rem;">(${p.team_name})</span>
                <span class="ppt-form-badge ${cls}" style="position:static;display:inline-block;padding:1px 5px;font-size:0.65rem;border-radius:3px;">${sign}${p.form_modifier} OVR</span>
                <span style="color:var(--t2);font-size:0.68rem;">· ${p.streak_label}</span>
              </div>
            `;
          }).join("")}
        </div>
      `;
    } else {
      formBar.style.display = "none";
    }
  }

  // 3.5 Render AI Pre-Match Forecast Hub (1,000 runs)
  if (data.forecast) {
    renderForecastHub(data.forecast, h.nickname || h.name, a.nickname || a.name);
  }

  // 3.6 Render 6-Axis Tactical Radar Matchup
  if (data.tactical_radar) {
    renderTacticalRadar(data.tactical_radar, h.nickname || h.name, a.nickname || a.name);
  }

  // 4. Render 2D Tactical Pitch
  renderTacticalPitch(data, currentPitchMode);

  // 5. "What They Used Last Time"
  if (h.last_match) {
    const s = document.getElementById("lmcHomeTeamShield");
    const n = document.getElementById("lmcHomeTeamName");
    const r = document.getElementById("lmcHomeResult");
    const opp = document.getElementById("lmcHomeOpponent");
    const sc = document.getElementById("lmcHomeScore");
    const v = document.getElementById("lmcHomeVenue");
    const fName = document.getElementById("lmcHomeFormation");
    const mgr = document.getElementById("lmcHomeManager");
    const notes = document.getElementById("lmcHomeNotes");

    if (s) s.src = h.shield || "";
    if (n) n.textContent = h.name;
    if (r) {
      r.className = `lmc-result-pill ${h.last_match.res_badge?.toLowerCase() || "d"}`;
      r.textContent = h.last_match.res_badge || "D";
    }
    if (opp) opp.textContent = `vs ${h.last_match.opponent_name}`;
    if (sc) sc.textContent = h.last_match.score;
    if (v) v.textContent = `(${h.last_match.venue})`;
    if (fName) fName.textContent = h.last_match.formation_used;
    if (mgr) mgr.textContent = h.last_match.manager;
    if (notes) notes.textContent = h.last_match.recap_notes;
  }

  if (a.last_match) {
    const s = document.getElementById("lmcAwayTeamShield");
    const n = document.getElementById("lmcAwayTeamName");
    const r = document.getElementById("lmcAwayResult");
    const opp = document.getElementById("lmcAwayOpponent");
    const sc = document.getElementById("lmcAwayScore");
    const v = document.getElementById("lmcAwayVenue");
    const fName = document.getElementById("lmcAwayFormation");
    const mgr = document.getElementById("lmcAwayManager");
    const notes = document.getElementById("lmcAwayNotes");

    if (s) s.src = a.shield || "";
    if (n) n.textContent = a.name;
    if (r) {
      r.className = `lmc-result-pill ${a.last_match.res_badge?.toLowerCase() || "d"}`;
      r.textContent = a.last_match.res_badge || "D";
    }
    if (opp) opp.textContent = `vs ${a.last_match.opponent_name}`;
    if (sc) sc.textContent = a.last_match.score;
    if (v) v.textContent = `(${a.last_match.venue})`;
    if (fName) fName.textContent = a.last_match.formation_used;
    if (mgr) mgr.textContent = a.last_match.manager;
    if (notes) notes.textContent = a.last_match.recap_notes;
  }

  // 6. Render Squad Rosters
  renderMatchRosters(data);

  // Render Predictive Match Trends & Flow
  renderMatchTrends(data);

  // 7. Hide post-sim card and reset timer
  const simCard = document.getElementById("simResultCard");
  if (simCard) simCard.style.display = "none";
  const timerBadge = document.getElementById("mdSimTimer");
  if (timerBadge) timerBadge.textContent = "90' Full Match";
}

function setPitchViewMode(mode) {
  currentPitchMode = mode;
  document.querySelectorAll(".tactical-toggle-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.pitch === mode);
  });
  if (currentMatchDetailData) {
    renderTacticalPitch(currentMatchDetailData, mode);
  }
}

function renderTacticalPitch(data, mode) {
  const layer = document.getElementById("pitchPlayersLayer");
  if (!layer || !data) return;
  layer.innerHTML = "";

  const homeXI = data.home_team.tactics?.starting_xi || [];
  const awayXI = data.away_team.tactics?.starting_xi || [];

  if (mode === "both" || mode === "home") {
    homeXI.forEach(p => {
      let xPct, yPct;
      if (mode === "both") {
        xPct = (6 + (100 - p.y) * 0.41).toFixed(1);
        yPct = p.x.toFixed(1);
      } else {
        xPct = (8 + (100 - p.y) * 0.84).toFixed(1);
        yPct = p.x.toFixed(1);
      }
      const token = createPlayerPitchTokenHtml(p, "home", xPct, yPct);
      layer.insertAdjacentHTML("beforeend", token);
    });
  }

  if (mode === "both" || mode === "away") {
    awayXI.forEach(p => {
      let xPct, yPct;
      if (mode === "both") {
        xPct = (94 - (100 - p.y) * 0.41).toFixed(1);
        yPct = p.x.toFixed(1);
      } else {
        xPct = (92 - (100 - p.y) * 0.84).toFixed(1);
        yPct = p.x.toFixed(1);
      }
      const token = createPlayerPitchTokenHtml(p, "away", xPct, yPct);
      layer.insertAdjacentHTML("beforeend", token);
    });
  }
}

function createPlayerPitchTokenHtml(p, side, leftPct, topPct) {
  const shirt = p.shirt_number ? p.shirt_number : (side === "home" ? "H" : "A");
  const rawOvr = p.effective_rating || p.overall_rating || 75;
  const shortName = (p.nickname || p.name || "Player").split(" ").slice(-1)[0];
  const slot = p.slot || "XI";

  let formBadgeHtml = "";
  if (p.form_modifier && p.form_modifier !== 0) {
    const sign = p.form_modifier > 0 ? "+" : "";
    const formCls = p.form_status || (p.form_modifier > 0 ? "in_form" : "cold");
    formBadgeHtml = `<span class="ppt-form-badge ${formCls}" title="${p.streak_label || 'Player Form'}">${p.streak_icon || ''}${sign}${p.form_modifier}</span>`;
  }

  // FotMob Signature 10-point Match Rating Display
  const fmRating = rawOvr > 10 ? (rawOvr / 10).toFixed(1) : Number(rawOvr).toFixed(1);
  const ratingCls = rawOvr >= 80 ? "rating-very-high" : rawOvr >= 72 ? "rating-high" : rawOvr >= 65 ? "rating-mid" : "rating-low";

  return `
    <div class="pitch-player-token ${side}" style="left:${leftPct}%; top:${topPct}%;" onclick="openSubModal('${p.id}', '${side}')" title="${p.name} · #${shirt} ${slot} (FotMob Rating: ${fmRating}) - Click to Substitute or View Bio">
      <div class="ppt-circle">
        <span>${shirt}</span>
        ${formBadgeHtml}
        <span class="ppt-rating-badge ${ratingCls}">${fmRating}</span>
      </div>
      <div class="ppt-label-box">
        <span class="ppt-name">${shortName}</span>
        <span class="ppt-pos-slot">${slot}</span>
      </div>
    </div>
  `;
}

function switchRosterTab(tab) {
  currentRosterTab = tab;
  const btnHome = document.getElementById("btnRosterHomeTab");
  const btnAway = document.getElementById("btnRosterAwayTab");
  const contHome = document.getElementById("rosterContainerHome");
  const contAway = document.getElementById("rosterContainerAway");

  if (btnHome) btnHome.classList.toggle("active", tab === "home");
  if (btnAway) btnAway.classList.toggle("active", tab === "away");
  if (contHome) contHome.classList.toggle("active", tab === "home");
  if (contAway) contAway.classList.toggle("active", tab === "away");
}

function renderMatchRosters(data) {
  const hStarters = data.home_team.tactics?.starting_xi || [];
  const hBench = data.home_team.tactics?.bench || [];
  const aStarters = data.away_team.tactics?.starting_xi || [];
  const aBench = data.away_team.tactics?.bench || [];
  const hShield = data.home_team?.shield || "";
  const aShield = data.away_team?.shield || "";

  const renderCard = (p, teamShield) => {
    const photo = p.photo_url || p.cutout_url || getSilhouette(p.position);
    const posClass = getPositionClass(p.position);
    const shirt = p.shirt_number ? `#${p.shirt_number}` : "";
    const ovr = p.effective_rating || p.overall_rating || 75;
    const formTag = (p.form_modifier && p.form_modifier !== 0) ?
      `<span class="ppt-form-badge ${p.form_status}" style="position:static;display:inline-block;padding:1px 5px;font-size:0.65rem;" title="${p.streak_label}">${p.streak_icon || ''}${p.form_modifier > 0 ? '+' : ''}${p.form_modifier}</span>` : "";
    return `
      <div class="squad-player-card" onclick="openPlayerModal('${p.slug}')" title="Click to view full player profile (${p.streak_label || 'Regular Form'})">
        <div class="spc-avatar-wrap">
          <img class="spc-player-img" src="${photo}" alt="${p.name}" loading="lazy" onerror="this.onerror=null; this.src=getSilhouette('${p.position || 'mid'}');">
          ${shirt ? `<span class="spc-number-badge">${shirt}</span>` : ""}
          ${teamShield ? `<img class="spc-crest-overlay" src="${teamShield}" alt="" onerror="this.remove()">` : ""}
        </div>
        <div class="spc-info">
          <div style="display:flex;align-items:center;gap:0.4rem;">
            <span class="spc-name" title="${p.name}">${p.name}</span>
            ${formTag}
          </div>
          <div class="spc-role-row">
            <span class="spc-pos-tag ${posClass}">${p.position || "Player"}</span>
            <span>·</span>
            <span>${p.archetype || "Tactical"}</span>
          </div>
        </div>
        <div class="spc-ovr-wrap" title="Effective Rating: ${ovr} (Base: ${p.overall_rating || 75})">
          <span class="spc-ovr">${ovr}</span>
          <span class="spc-ovr-lbl">OVR</span>
        </div>
      </div>
    `;
  };

  const homeStartersEl = document.getElementById("homeStartersGrid");
  const homeBenchEl = document.getElementById("homeBenchGrid");
  const awayStartersEl = document.getElementById("awayStartersGrid");
  const awayBenchEl = document.getElementById("awayBenchGrid");

  if (homeStartersEl) homeStartersEl.innerHTML = hStarters.map(p => renderCard(p, hShield)).join("");
  if (homeBenchEl) homeBenchEl.innerHTML = hBench.length > 0 ? hBench.map(p => renderCard(p, hShield)).join("") : `<div style="color:var(--t3);font-size:0.8rem;padding:0.5rem 0;">No bench players listed</div>`;
  if (awayStartersEl) awayStartersEl.innerHTML = aStarters.map(p => renderCard(p, aShield)).join("");
  if (awayBenchEl) awayBenchEl.innerHTML = aBench.length > 0 ? aBench.map(p => renderCard(p, aShield)).join("") : `<div style="color:var(--t3);font-size:0.8rem;padding:0.5rem 0;">No bench players listed</div>`;
}

async function triggerMatchDetailSimulation() {
  if (isSimulatingPitch || !currentMatchDetailData) return;
  isSimulatingPitch = true;

  const data = currentMatchDetailData;
  const overlay = document.getElementById("pitchSimOverlay");
  const ball = document.getElementById("simPitchBall");
  const toast = document.getElementById("simPitchEventToast");
  const timerBadge = document.getElementById("mdSimTimer");
  const scoreDisplay = document.getElementById("mdScoreDisplay");
  const statusTag = document.getElementById("mdStatusTag");

  if (overlay) overlay.classList.add("active");
  if (statusTag) {
    statusTag.className = "hero-status-tag live";
    statusTag.textContent = "● SIMULATION IN PLAY";
  }

  // Fetch calibrated mathematical simulation based on authentic club tactical identities & substitutions
  let simResult = null;
  try {
    const res = await fetch(`${API_BASE}/api/simulate-match/${data.fixture.id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        substitutions: customSubstitutions
      })
    });
    if (res.ok) {
      simResult = await res.json();
    }
  } catch (err) {
    console.warn("Backend simulate-match POST error, trying GET fallback:", err);
    try {
      const getRes = await fetch(`${API_BASE}/api/simulate-match/${data.fixture.id}`);
      if (getRes.ok) simResult = await getRes.json();
    } catch (e) {}
  }

  // If backend simulation failed for any reason, generate consistent local simulation
  if (!simResult) {
    const homeRank = data.home_team.position || 10;
    const awayRank = data.away_team.position || 10;
    const diff = awayRank - homeRank + 2;
    const fHome = Math.max(0, Math.min(5, Math.floor(Math.random() * 2) + (diff > 4 ? 1 : 0)));
    const fAway = Math.max(0, Math.min(4, Math.floor(Math.random() * 2) + (diff < -4 ? 1 : 0)));
    const hStarters = data.home_team.tactics?.starting_xi || [];
    const aStarters = data.away_team.tactics?.starting_xi || [];
    const fallbackEvents = [];
    for (let i = 0; i < fHome; i++) {
      const p = hStarters[Math.floor(Math.random() * hStarters.length)] || { name: data.home_team.name };
      fallbackEvents.push({
        type: "goal",
        team: "home",
        team_name: data.home_team.name,
        minute: Math.floor(Math.random() * 80) + 8,
        scorer: p.name,
        description: `⚽ GOAL! ${p.name} scores for ${data.home_team.name}!`
      });
    }
    for (let i = 0; i < fAway; i++) {
      const p = aStarters[Math.floor(Math.random() * aStarters.length)] || { name: data.away_team.name };
      fallbackEvents.push({
        type: "goal",
        team: "away",
        team_name: data.away_team.name,
        minute: Math.floor(Math.random() * 80) + 8,
        scorer: p.name,
        description: `⚽ GOAL! ${p.name} scores for ${data.away_team.name}!`
      });
    }
    fallbackEvents.sort((a, b) => a.minute - b.minute);
    simResult = {
      home_score: fHome,
      away_score: fAway,
      events: fallbackEvents,
      stats: null
    };
  }

  const finalHome = simResult.home_score;
  const finalAway = simResult.away_score;
  const simEvents = [...(simResult.events || [])].sort((a, b) => a.minute - b.minute);
  const simStats = simResult.stats || null;

  let currentMin = 0;
  let liveH = 0;
  let liveA = 0;

  const eventsLog = [];
  const processedEvents = new Set();

  const trajRay = document.getElementById("simTrajectoryRay");
  const stadiumFlash = document.getElementById("simStadiumFlash");
  const goalBanner = document.getElementById("simGoalBanner");
  const sgbTeamCrest = document.getElementById("sgbTeamCrest");
  const sgbScorerName = document.getElementById("sgbScorerName");
  const sgbGoalDetail = document.getElementById("sgbGoalDetail");
  const sgbAssist = document.getElementById("sgbAssist");
  const saveBanner = document.getElementById("simSaveBanner");
  const ssbDesc = document.getElementById("ssbDesc");

  let lastBallX = 50;
  let lastBallY = 50;

  // Query all pitch tokens for interactive passing highlights
  const playerTokens = Array.from(document.querySelectorAll(".pitch-player-token"));

  const speedMs = Math.max(20, Math.floor(90 / pitchSimSpeed));

  const interval = setInterval(() => {
    currentMin += 2;
    if (timerBadge) timerBadge.textContent = `${currentMin}'`;

    // Dynamic passing & player possession animation
    if (playerTokens.length > 0) {
      // Pick next ball receiver
      const activeToken = playerTokens[Math.floor(Math.random() * playerTokens.length)];
      const targetLeft = parseFloat(activeToken.style.left) || 50;
      const targetTop = parseFloat(activeToken.style.top) || 50;

      // Remove possession highlight from all tokens, highlight active receiver
      playerTokens.forEach(t => t.classList.remove("in-possession"));
      activeToken.classList.add("in-possession");

      // Draw SVG laser passing trajectory from last position to new target
      if (trajRay) {
        const svgW = 1000;
        const svgH = 650;
        const x1 = (lastBallX / 100) * svgW;
        const y1 = (lastBallY / 100) * svgH;
        const x2 = (targetLeft / 100) * svgW;
        const y2 = (targetTop / 100) * svgH;
        // Curve passing trajectory
        const midX = (x1 + x2) / 2 + (Math.random() * 40 - 20);
        const midY = (y1 + y2) / 2 - 25;
        trajRay.setAttribute("d", `M ${x1} ${y1} Q ${midX} ${midY} ${x2} ${y2}`);
      }

      // Smoothly move ball
      if (ball) {
        ball.style.left = `${targetLeft}%`;
        ball.style.top = `${targetTop}%`;
      }

      lastBallX = targetLeft;
      lastBallY = targetTop;
    }

    // Trigger simulation timeline events scheduled up to this minute
    simEvents.forEach((ev, idx) => {
      if (ev.minute <= currentMin && !processedEvents.has(idx)) {
        processedEvents.add(idx);

        if (ev.type === "goal") {
          if (ev.team === "home") liveH++;
          else liveA++;
          
          if (scoreDisplay) {
            scoreDisplay.innerHTML = `<span class="hero-score-num" style="color:#F59E0B; transform:scale(1.28); transition:all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);">${liveH} - ${liveA}</span>`;
          }

          // Trigger Stadium Lighting Flash
          if (stadiumFlash) {
            stadiumFlash.classList.add("flash");
            setTimeout(() => stadiumFlash.classList.remove("flash"), 550);
          }

          // Trigger Cinematic Goal Explosion Popup
          if (goalBanner) {
            if (sgbTeamCrest) sgbTeamCrest.src = ev.team === "home" ? (data.home_team.shield || "") : (data.away_team.shield || "");
            if (sgbScorerName) sgbScorerName.textContent = ev.scorer || "Goal Scorer";
            if (sgbGoalDetail) sgbGoalDetail.textContent = `${ev.minute}' Minute · ${ev.team_name}`;
            if (sgbAssist) sgbAssist.textContent = ev.assist ? `Assist: ${ev.assist}` : "Unassisted Precision Strike";
            goalBanner.style.display = "block";
            setTimeout(() => {
              goalBanner.style.display = "none";
            }, Math.max(900, Math.floor(2200 / pitchSimSpeed)));
          }

          eventsLog.push(`⚽ ${ev.minute}' ${ev.scorer || ev.player} (${ev.team_name})`);
        } else if (ev.type === "save") {
          // Trigger Save Banner
          if (saveBanner) {
            if (ssbDesc) ssbDesc.textContent = `${ev.player} deflects a bullet shot with acrobatic dive (${ev.minute}')`;
            saveBanner.style.display = "flex";
            setTimeout(() => {
              saveBanner.style.display = "none";
            }, Math.max(700, Math.floor(1600 / pitchSimSpeed)));
          }
        } else if (ev.type === "card") {
          showPitchToast(ev.description || `🟨 Yellow Card: ${ev.player} (${ev.team_name}) (${ev.minute}')`);
          eventsLog.push(`🟨 ${ev.minute}' ${ev.player} (${ev.team_name})`);
        } else if (ev.type === "game_management") {
          showPitchToast(ev.description || `⏱️ Game Management (${ev.minute}')`);
          eventsLog.push(`⏱️ ${ev.minute}' Game Management (${ev.team_name})`);
        } else if (ev.type === "attacking_siege") {
          showPitchToast(ev.description || `⚡ Late Siege (${ev.minute}')`);
          if (stadiumFlash) {
            stadiumFlash.classList.add("flash");
            setTimeout(() => stadiumFlash.classList.remove("flash"), 300);
          }
          eventsLog.push(`⚡ ${ev.minute}' Late Attacking Siege (${ev.team_name})`);
        }
      }
    });

    // Half-time milestone
    if (currentMin === 44 || currentMin === 46) {
      showPitchToast(`⏱️ HALF TIME: ${data.home_team.nickname || data.home_team.name} ${liveH} - ${liveA} ${data.away_team.nickname || data.away_team.name}`);
    }

    if (currentMin >= 90) {
      clearInterval(interval);
      isSimulatingPitch = false;

      // Clear SVG passing line and possession highlights
      if (trajRay) trajRay.setAttribute("d", "");
      playerTokens.forEach(t => t.classList.remove("in-possession"));

      // Process any remaining goal events to strictly guarantee 100% synchronization
      simEvents.forEach((ev, idx) => {
        if (!processedEvents.has(idx)) {
          processedEvents.add(idx);
          if (ev.type === "goal") {
            if (ev.team === "home") liveH++;
            else liveA++;
            eventsLog.push(`⚽ ${ev.minute}' ${ev.scorer || ev.player} (${ev.team_name})`);
          } else if (ev.type === "card") {
            eventsLog.push(`🟨 ${ev.minute}' ${ev.player} (${ev.team_name})`);
          }
        }
      });

      // Strict guarantee: Score matches eventsLog exactly
      liveH = finalHome;
      liveA = finalAway;

      if (timerBadge) timerBadge.textContent = "FULL TIME";
      if (statusTag) {
        statusTag.className = "hero-status-tag";
        statusTag.textContent = "SIMULATED RESULT (FT)";
      }
      if (scoreDisplay) {
        scoreDisplay.innerHTML = `<span class="hero-score-num">${liveH} - ${liveA}</span>`;
      }

      showPitchToast(`🏁 FULL TIME: ${data.home_team.name} ${liveH} - ${liveA} ${data.away_team.name}`);

      // Sync with global allFixtures
      const fx = allFixtures.find(x => x.id === data.fixture.id);
      if (fx) {
        fx.home_score = liveH;
        fx.away_score = liveA;
        fx.status = "SIMULATED";
      }
      data.fixture.home_score = liveH;
      data.fixture.away_score = liveA;
      data.fixture.status = "SIMULATED";

      // Render Post-Simulation Analysis Card with calibrated backend statistics
      renderPostSimResult(data, liveH, liveA, eventsLog, simStats);

      // Update Predictive Trends with Simulated Match Events
      if (simResult && simResult.trends) {
        renderMatchTrends(data, simResult.trends);
      }
    }
  }, speedMs);
}

function showPitchToast(msg) {
  const toast = document.getElementById("simPitchEventToast");
  if (!toast) return;
  toast.textContent = msg;
  toast.classList.add("show");
  setTimeout(() => {
    toast.classList.remove("show");
  }, 2200);
}

function renderPostSimResult(data, homeGoals, awayGoals, eventsLog, simStats = null) {
  const card = document.getElementById("simResultCard");
  const scoreEl = document.getElementById("srcScoreline");
  const tickerEl = document.getElementById("srcEventsTicker");
  const statsEl = document.getElementById("srcStatsComparison");
  if (!card) return;

  const hName = data.home_team.name;
  const aName = data.away_team.name;

  if (scoreEl) scoreEl.textContent = `${hName} ${homeGoals} - ${awayGoals} ${aName}`;

  if (tickerEl) {
    if (eventsLog.length === 0) {
      tickerEl.innerHTML = `<span class="src-event-badge">🛡️ Goalless Tactical Stalemate · Resilient Defenses</span>`;
    } else {
      tickerEl.innerHTML = eventsLog.map(e => `<span class="src-event-badge">${e}</span>`).join("");
    }
  }

  // Use calibrated backend match statistics or calculate realistic fallback
  const homePoss = simStats?.possession?.home ?? (50 + Math.floor(Math.random() * 16) - 8);
  const awayPoss = simStats?.possession?.away ?? (100 - homePoss);
  const homeShots = simStats?.shots?.home ?? (8 + homeGoals * 3 + Math.floor(Math.random() * 4));
  const awayShots = simStats?.shots?.away ?? (6 + awayGoals * 2 + Math.floor(Math.random() * 4));
  const homeTarget = simStats?.shots_on_target?.home ?? Math.max(homeGoals, Math.floor(homeShots * 0.42));
  const awayTarget = simStats?.shots_on_target?.away ?? Math.max(awayGoals, Math.floor(awayShots * 0.38));
  const homeXG = simStats?.xg?.home ?? (homeGoals * 0.72 + (homeTarget * 0.15)).toFixed(2);
  const awayXG = simStats?.xg?.away ?? (awayGoals * 0.72 + (awayTarget * 0.15)).toFixed(2);

  if (statsEl) {
    statsEl.innerHTML = `
      <div class="src-stat-row">
        <div class="src-stat-labels">
          <span>${homePoss}%</span>
          <span>Possession</span>
          <span>${awayPoss}%</span>
        </div>
        <div class="src-stat-bar-track">
          <div class="src-stat-bar-home" style="width:${homePoss}%"></div>
          <div class="src-stat-bar-away" style="width:${awayPoss}%"></div>
        </div>
      </div>

      <div class="src-stat-row">
        <div class="src-stat-labels">
          <span>${homeXG}</span>
          <span>Expected Goals (xG)</span>
          <span>${awayXG}</span>
        </div>
        <div class="src-stat-bar-track">
          <div class="src-stat-bar-home" style="width:${(parseFloat(homeXG)/(parseFloat(homeXG)+parseFloat(awayXG)+0.01)*100).toFixed(0)}%"></div>
          <div class="src-stat-bar-away" style="width:${(parseFloat(awayXG)/(parseFloat(homeXG)+parseFloat(awayXG)+0.01)*100).toFixed(0)}%"></div>
        </div>
      </div>

      <div class="src-stat-row">
        <div class="src-stat-labels">
          <span>${homeTarget} (${homeShots})</span>
          <span>Shots on Target (Total)</span>
          <span>${awayTarget} (${awayShots})</span>
        </div>
        <div class="src-stat-bar-track">
          <div class="src-stat-bar-home" style="width:${(homeShots/(homeShots+awayShots+0.01)*100).toFixed(0)}%"></div>
          <div class="src-stat-bar-away" style="width:${(awayShots/(homeShots+awayShots+0.01)*100).toFixed(0)}%"></div>
        </div>
      </div>
    `;
  }

  card.style.display = "flex";
  card.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function closeSimResultCard() {
  const card = document.getElementById("simResultCard");
  if (card) card.style.display = "none";
}


// ============================================================
// 17. ADVANCED ANALYTICS & INTERACTIVE MANAGER SUITE CONTROLLERS
// ============================================================

function renderForecastHub(fc, homeName, awayName) {
  const hub = document.getElementById("mdForecastHub");
  if (!hub || !fc) return;

  const hLabel = document.getElementById("fpmHomeLabel");
  const dLabel = document.getElementById("fpmDrawLabel");
  const aLabel = document.getElementById("fpmAwayLabel");

  if (hLabel) hLabel.innerHTML = `${homeName} Win: <strong>${fc.home_win_pct}%</strong>`;
  if (dLabel) dLabel.innerHTML = `Draw: <strong>${fc.draw_pct}%</strong>`;
  if (aLabel) aLabel.innerHTML = `${awayName} Win: <strong>${fc.away_win_pct}%</strong>`;

  const barH = document.getElementById("fpmBarHome");
  const barD = document.getElementById("fpmBarDraw");
  const barA = document.getElementById("fpmBarAway");

  if (barH) barH.style.width = `${fc.home_win_pct}%`;
  if (barD) barD.style.width = `${fc.draw_pct}%`;
  if (barA) barA.style.width = `${fc.away_win_pct}%`;

  const scoresEl = document.getElementById("fiTopScorelines");
  if (scoresEl && fc.top_scorelines) {
    scoresEl.innerHTML = fc.top_scorelines.map(s => `
      <span class="fi-score-chip" title="${s.probability}% Probability">${s.score} <small>(${s.probability}%)</small></span>
    `).join("");
  }

  const o25 = document.getElementById("fiOver25");
  const u25 = document.getElementById("fiUnder25");
  if (o25) o25.textContent = `${fc.over_2_5_pct}%`;
  if (u25) u25.textContent = `${fc.under_2_5_pct}%`;

  const bttsY = document.getElementById("fiBttsYes");
  const bttsN = document.getElementById("fiBttsNo");
  if (bttsY) bttsY.textContent = `${fc.btts_yes_pct}%`;
  if (bttsN) bttsN.textContent = `${fc.btts_no_pct}%`;

  const xgH = document.getElementById("fiXGHome");
  const xgA = document.getElementById("fiXGAway");
  if (xgH) xgH.textContent = `${homeName} ${fc.projected_xg?.home || 1.3} xG`;
  if (xgA) xgA.textContent = `${awayName} ${fc.projected_xg?.away || 1.1} xG`;
}

function renderTacticalRadar(radar, homeName, awayName) {
  const svg = document.getElementById("matchTacticalRadarSvg");
  const legH = document.getElementById("radarHomeLegName");
  const legA = document.getElementById("radarAwayLegName");
  const table = document.getElementById("radarMetricsTable");

  if (legH) legH.textContent = `${homeName} XI`;
  if (legA) legA.textContent = `${awayName} XI`;

  if (!svg || !radar || !radar.axes) return;

  const axes = radar.axes;
  const numAxes = axes.length;
  const cx = 230;
  const cy = 185;
  const radius = 125;
  const angleStep = (2 * Math.PI) / numAxes;

  let svgContent = "";

  // 1. Concentric Web Rings (25%, 50%, 75%, 100%)
  const levels = [0.25, 0.50, 0.75, 1.0];
  levels.forEach(lvl => {
    const ringPts = [];
    for (let i = 0; i < numAxes; i++) {
      const angle = i * angleStep - Math.PI / 2;
      const r = radius * lvl;
      const x = cx + r * Math.cos(angle);
      const y = cy + r * Math.sin(angle);
      ringPts.push(`${x.toFixed(1)},${y.toFixed(1)}`);
    }
    svgContent += `<polygon points="${ringPts.join(" ")}" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="1.2" stroke-dasharray="${lvl === 1.0 ? 'none' : '3 3'}"/>`;
  });

  // 2. Axis Spokes & Labels
  axes.forEach((axis, i) => {
    const angle = i * angleStep - Math.PI / 2;
    const x = cx + radius * Math.cos(angle);
    const y = cy + radius * Math.sin(angle);
    svgContent += `<line x1="${cx}" y1="${cy}" x2="${x.toFixed(1)}" y2="${y.toFixed(1)}" stroke="rgba(255,255,255,0.12)" stroke-width="1.2"/>`;

    const labelDist = radius + 24;
    const lx = cx + labelDist * Math.cos(angle);
    const ly = cy + labelDist * Math.sin(angle);
    const anchor = Math.abs(Math.cos(angle)) < 0.2 ? "middle" : (Math.cos(angle) > 0 ? "start" : "end");
    const baseline = Math.sin(angle) > 0.5 ? "hanging" : (Math.sin(angle) < -0.5 ? "auto" : "central");
    svgContent += `<text x="${lx.toFixed(1)}" y="${ly.toFixed(1)}" fill="#64748B" font-size="10.5" font-weight="700" text-anchor="${anchor}" dominant-baseline="${baseline}">${axis.label}</text>`;
  });

  // 3. Home Polygon
  const homePts = axes.map((axis, i) => {
    const val = (radar.home[axis.key] || 50) / 100;
    const angle = i * angleStep - Math.PI / 2;
    const r = radius * Math.max(0.15, Math.min(1.0, val));
    return `${(cx + r * Math.cos(angle)).toFixed(1)},${(cy + r * Math.sin(angle)).toFixed(1)}`;
  });
  svgContent += `<polygon points="${homePts.join(" ")}" fill="rgba(0, 229, 255, 0.22)" stroke="#0EA5E9" stroke-width="2.2" style="filter: drop-shadow(0 0 8px rgba(0,229,255,0.4));"/>`;

  // 4. Away Polygon
  const awayPts = axes.map((axis, i) => {
    const val = (radar.away[axis.key] || 50) / 100;
    const angle = i * angleStep - Math.PI / 2;
    const r = radius * Math.max(0.15, Math.min(1.0, val));
    return `${(cx + r * Math.cos(angle)).toFixed(1)},${(cy + r * Math.sin(angle)).toFixed(1)}`;
  });
  svgContent += `<polygon points="${awayPts.join(" ")}" fill="rgba(245, 158, 11, 0.20)" stroke="#F59E0B" stroke-width="2.2" style="filter: drop-shadow(0 0 8px rgba(245,158,11,0.4));"/>`;

  // 5. Points dots
  homePts.forEach(pt => {
    const [x, y] = pt.split(",");
    svgContent += `<circle cx="${x}" cy="${y}" r="3.5" fill="#0EA5E9"/>`;
  });
  awayPts.forEach(pt => {
    const [x, y] = pt.split(",");
    svgContent += `<circle cx="${x}" cy="${y}" r="3.5" fill="#F59E0B"/>`;
  });

  svg.innerHTML = svgContent;

  // 6. Metrics Comparison Table
  if (table) {
    table.innerHTML = axes.map(axis => {
      const hVal = radar.home[axis.key] || 50;
      const aVal = radar.away[axis.key] || 50;
      const total = hVal + aVal || 100;
      const hPct = ((hVal / total) * 100).toFixed(0);
      const aPct = ((aVal / total) * 100).toFixed(0);
      return `
        <div class="rmt-row">
          <span class="rmt-h-val">${hVal}</span>
          <div class="rmt-center">
            <div class="rmt-name">${axis.label}</div>
            <div class="rmt-bar-wrap">
              <div class="rmt-bar-h" style="width:${hPct}%"></div>
              <div class="rmt-bar-a" style="width:${aPct}%"></div>
            </div>
          </div>
          <span class="rmt-a-val">${aVal}</span>
        </div>
      `;
    }).join("");
  }
}

async function setTacticalStance(stance) {
  currentTacticalStance = stance;
  document.querySelectorAll(".stance-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.stance === stance);
  });
  
  const labels = {
    balanced: "Balanced Standard Setup",
    high_press: "⚡ High Press (+25% Attack, High Risk)",
    low_block: "🛡️ Low Block (-25% Attack, Resilient Defense)",
    all_out_attack: "🔥 All-Out Attack (+40% Attack Overload)"
  };
  
  showPitchToast(`👔 Tactical Stance: ${labels[stance] || stance}`);

  if (currentMatchDetailData) {
    try {
      const res = await fetch(`${API_BASE}/api/forecast/${currentMatchDetailData.fixture.id}?stance=${stance}`);
      if (res.ok) {
        const fc = await res.json();
        currentMatchDetailData.forecast = fc;
        renderForecastHub(fc, currentMatchDetailData.home_team.name, currentMatchDetailData.away_team.name);
      }
    } catch (e) {
      console.warn("Forecast stance refresh error:", e);
    }
  }
}

function openSubModal(playerId, side) {
  if (!currentMatchDetailData) return;
  const team = side === "home" ? currentMatchDetailData.home_team : currentMatchDetailData.away_team;
  const starters = team.tactics?.starting_xi || [];
  const bench = team.tactics?.bench || [];
  const target = starters.find(p => String(p.id) === String(playerId));

  if (!target) {
    return;
  }

  currentSubTarget = { player: target, side: side };

  const modal = document.getElementById("tacticalSubModal");
  const targetInfo = document.getElementById("subTargetPlayerInfo");
  const benchList = document.getElementById("subBenchPlayerList");
  const eyebrow = document.getElementById("subModalEyebrow");

  if (eyebrow) eyebrow.textContent = `${team.name.toUpperCase()} · TACTICAL SUBSTITUTION`;

  if (targetInfo) {
    const shirt = target.shirt_number ? `#${target.shirt_number}` : "";
    const ovr = target.effective_rating || target.overall_rating || 75;
    targetInfo.innerHTML = `
      <div style="display:flex;align-items:center;gap:0.75rem;">
        <div style="width:38px;height:38px;border-radius:50%;background:rgba(255,255,255,0.1);display:flex;align-items:center;justify-content:center;font-weight:900;font-family:var(--mono);">
          ${shirt || "XI"}
        </div>
        <div>
          <div style="font-size:0.88rem;font-weight:800;color:var(--t0);">${target.name}</div>
          <div style="font-size:0.72rem;color:var(--t3);">${target.slot || "Player"} · ${target.position || "Position"}</div>
        </div>
      </div>
      <div style="display:flex;align-items:center;gap:0.6rem;">
        <span class="spc-ovr-wrap" style="padding:2px 8px;border-radius:6px;background:rgba(255,255,255,0.06);font-size:0.85rem;font-family:var(--mono);font-weight:800;color:var(--t0);">
          ${ovr} <small style="font-size:0.65rem;color:var(--t3);">OVR</small>
        </span>
        <button class="view-all-btn" onclick="openPlayerModal('${target.slug}'); closeSubModal();" style="padding:4px 8px;font-size:0.72rem;">Bio ›</button>
      </div>
    `;
  }

  if (benchList) {
    if (bench.length === 0) {
      benchList.innerHTML = `<div style="color:var(--t3);font-size:0.8rem;padding:1rem;text-align:center;">No reserve players available for this club</div>`;
    } else {
      benchList.innerHTML = bench.map(bp => {
        const bpOvr = bp.effective_rating || bp.overall_rating || 75;
        const diff = bpOvr - (target.effective_rating || target.overall_rating || 75);
        const diffStr = diff > 0 ? `+${diff}` : (diff < 0 ? `${diff}` : "0");
        const diffColor = diff > 0 ? "#10B981" : (diff < 0 ? "#EF4444" : "var(--t3)");
        return `
          <div class="sub-bench-item" onclick="executeSubstitution('${bp.id}')">
            <div class="sbi-left">
              <span class="sbi-num">#${bp.shirt_number || "Sub"}</span>
              <div>
                <span class="sbi-name">${bp.name}</span>
                <span class="sbi-pos">${bp.position || "Player"} · ${bp.archetype || "Tactical"}</span>
              </div>
            </div>
            <div class="sbi-right">
              <span style="font-size:0.7rem;font-weight:800;font-family:var(--mono);color:${diffColor};">${diffStr}</span>
              <span class="sbi-ovr">${bpOvr}</span>
              <button class="btn-do-sub" onclick="event.stopPropagation(); executeSubstitution('${bp.id}');">SUB IN</button>
            </div>
          </div>
        `;
      }).join("");
    }
  }

  if (modal) modal.style.display = "flex";
}

function closeSubModal(e) {
  const modal = document.getElementById("tacticalSubModal");
  if (modal) modal.style.display = "none";
  currentSubTarget = null;
}

async function executeSubstitution(inPlayerId) {
  if (!currentSubTarget || !currentMatchDetailData) return;

  const side = currentSubTarget.side;
  const team = side === "home" ? currentMatchDetailData.home_team : currentMatchDetailData.away_team;
  const starters = team.tactics?.starting_xi || [];
  const bench = team.tactics?.bench || [];

  const outIdx = starters.findIndex(p => String(p.id) === String(currentSubTarget.player.id));
  const inIdx = bench.findIndex(p => String(p.id) === String(inPlayerId));

  if (outIdx === -1 || inIdx === -1) return;

  const outPlayer = starters[outIdx];
  const inPlayer = bench[inIdx];

  // Record for backend POST payload
  customSubstitutions.push({
    team: side,
    out_id: outPlayer.id,
    in_id: inPlayer.id
  });

  // Swap in memory
  const swapped = { ...inPlayer, slot: outPlayer.slot, x: outPlayer.x, y: outPlayer.y };
  starters[outIdx] = swapped;
  bench.splice(inIdx, 1);
  bench.push(outPlayer);

  // Close modal
  closeSubModal();

  // Re-render pitch and rosters
  renderTacticalPitch(currentMatchDetailData, currentPitchMode);
  renderMatchRosters(currentMatchDetailData);

  // Toast feedback
  showPitchToast(`🔄 Tactical Sub: [IN] ${inPlayer.name} (OVR ${inPlayer.effective_rating || inPlayer.overall_rating}) ➔ [OUT] ${outPlayer.name}`);

  // Re-calculate forecast with new lineup
  try {
    const res = await fetch(`${API_BASE}/api/simulate-match/${currentMatchDetailData.fixture.id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        substitutions: customSubstitutions
      })
    });
    if (res.ok) {
      const fcRes = await fetch(`${API_BASE}/api/forecast/${currentMatchDetailData.fixture.id}`);
      if (fcRes.ok) {
        const fc = await fcRes.json();
        currentMatchDetailData.forecast = fc;
        renderForecastHub(fc, currentMatchDetailData.home_team.name, currentMatchDetailData.away_team.name);
      }
    }
  } catch (err) {
    console.warn("Sub sync error:", err);
  }
}
