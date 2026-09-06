const DIFFICULTY_MIN = 1;
const DIFFICULTY_MAX = 26;
const STORAGE_KEY = "piu-matcher-ranges";

const state = {
  p1min: 1, p1max: 26,
  p2min: 1, p2max: 26,
  activeTypes: new Set(["arcade"]),
};

let db = null;

// --- Persistence -----------------------------------------------------
// Ranges persist across visits via localStorage. Note: this only works
// when the page is actually opened in a browser (e.g. hosted on GitHub
// Pages, or opened as a local file) — it will not persist inside a
// sandboxed preview environment that blocks localStorage.

function saveRanges() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      p1min: state.p1min, p1max: state.p1max,
      p2min: state.p2min, p2max: state.p2max,
      activeTypes: [...state.activeTypes],
    }));
  } catch (e) {
    console.warn("Could not save ranges to localStorage:", e);
  }
}

function loadRanges() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const saved = JSON.parse(raw);
    Object.assign(state, saved);
    if (Array.isArray(saved.activeTypes)) {
      state.activeTypes = new Set(saved.activeTypes);
    }
  } catch (e) {
    console.warn("Could not load saved ranges:", e);
  }
}

// --- Stepper UI --------------------------------------------------------

function clamp(value) {
  return Math.max(DIFFICULTY_MIN, Math.min(DIFFICULTY_MAX, value));
}

function updateStepperDisplay() {
  document.getElementById("p1min-display").textContent = state.p1min;
  document.getElementById("p1max-display").textContent = state.p1max;
  document.getElementById("p2min-display").textContent = state.p2min;
  document.getElementById("p2max-display").textContent = state.p2max;
}

function handleStep(target, dir) {
  const isMin = target.endsWith("min");
  const player = target.startsWith("p1") ? "p1" : "p2";
  const minKey = `${player}min`;
  const maxKey = `${player}max`;

  let next = state[target] + dir;
  next = clamp(next);

  if (isMin && next > state[maxKey]) next = state[maxKey];
  if (!isMin && next < state[minKey]) next = state[minKey];

  state[target] = next;
  updateStepperDisplay();
  saveRanges();
  renderResults();
}

function setupSteppers() {
  document.querySelectorAll(".step-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = btn.dataset.target;
      const dir = parseInt(btn.dataset.dir, 10);
      handleStep(target, dir);
    });
  });
}

// --- Filter chips --------------------------------------------------------

function setupFilters() {
  document.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const type = chip.dataset.type;
      const isActive = chip.getAttribute("aria-pressed") === "true";

      // Prevent turning off the last remaining filter — an empty filter
      // set would silently show zero results with no obvious explanation.
      if (isActive && state.activeTypes.size === 1) return;

      if (isActive) {
        state.activeTypes.delete(type);
        chip.setAttribute("aria-pressed", "false");
      } else {
        state.activeTypes.add(type);
        chip.setAttribute("aria-pressed", "true");
      }
      saveRanges();
      renderResults();
    });
  });
}

function syncFilterUI() {
  document.querySelectorAll(".chip").forEach((chip) => {
    const isActive = state.activeTypes.has(chip.dataset.type);
    chip.setAttribute("aria-pressed", isActive ? "true" : "false");
  });
}

// --- Database + matching query --------------------------------------------------------

async function loadDatabase() {
  const SQL = await initSqlJs({
    locateFile: (file) => `https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.10.3/${file}`,
  });
  const response = await fetch("piu_songs_final.db");
  const buffer = await response.arrayBuffer();
  db = new SQL.Database(new Uint8Array(buffer));
}

// A song matches if it has at least one Singles chart within EACH
// player's range independently — the two players don't need to share
// the exact same difficulty number, they each just need something
// playable in the same song.
// A song matches if it has at least one Singles chart within EACH
// player's range independently — the two players don't need to share
// the exact same difficulty number, they each just need something
// playable in the same song. Ordering by newest version first is done
// here in SQL via the versions table, rather than in JS, since the
// version ordering is now data (see version_order.json / build_db.py)
// rather than logic duplicated in the frontend.
function queryMatches() {
  const typeList = [...state.activeTypes].map((t) => `'${t}'`).join(",");
  if (!typeList) return [];

  const sql = `
    SELECT s.song_id, s.title, s.version, s.song_type,
          GROUP_CONCAT(c.difficulty) as difficulties
    FROM songs s
    JOIN charts c ON c.song_id = s.song_id
    LEFT JOIN versions v ON v.version_name = s.version
    WHERE s.song_type IN (${typeList})
      AND (
        c.difficulty BETWEEN ${state.p1min} AND ${state.p1max}
        OR c.difficulty BETWEEN ${state.p2min} AND ${state.p2max}
      )
      AND s.song_id IN (
        SELECT song_id FROM charts
        WHERE difficulty BETWEEN ${state.p1min} AND ${state.p1max}
      )
      AND s.song_id IN (
        SELECT song_id FROM charts
        WHERE difficulty BETWEEN ${state.p2min} AND ${state.p2max}
      )
    GROUP BY s.song_id
    ORDER BY v.release_rank DESC, s.title
  `;

  const result = db.exec(sql);
  if (!result.length) return [];

  const { columns, values } = result[0];
  return values.map((row) => {
    const obj = {};
    columns.forEach((col, i) => (obj[col] = row[i]));
    obj.difficulties = obj.difficulties.split(",").map(Number).sort((a, b) => a - b);
    return obj;
  });
}

// --- Rendering --------------------------------------------------------

function difficultyChipClass(level) {
  const inP1 = level >= state.p1min && level <= state.p1max;
  const inP2 = level >= state.p2min && level <= state.p2max;
  if (inP1 && inP2) return "match-both";
  if (inP1) return "match-p1";
  if (inP2) return "match-p2";
  return "";
}

function renderResults() {
  if (!db) return;

  const matches = queryMatches();

  const listEl = document.getElementById("results-list");
  const countEl = document.getElementById("results-count");

  countEl.textContent = matches.length === 1 ? "1 song" : `${matches.length} songs`;

  if (matches.length === 0) {
    listEl.innerHTML = `<div class="empty-state">No songs match both ranges yet. Try widening a range or a filter.</div>`;
    return;
  }

  listEl.innerHTML = matches.map((song) => `
    <div class="song-card">
      <div class="song-card-top">
        <span class="song-title">${escapeHtml(song.title)}</span>
        <span class="song-version">${escapeHtml(song.version)}</span>
      </div>
      <div class="diff-row">
        ${song.difficulties.map((level) => `
          <span class="diff-chip ${difficultyChipClass(level)}"><span class="diff-number">${level}</span></span>
        `).join("")}
      </div>
    </div>
  `).join("");
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// --- Init --------------------------------------------------------

async function init() {
  loadRanges();
  updateStepperDisplay();
  syncFilterUI();
  setupSteppers();
  setupFilters();

  try {
    await loadDatabase();
    renderResults();
  } catch (e) {
    console.error("Failed to load database:", e);
    document.getElementById("results-list").innerHTML =
      `<div class="empty-state">Could not load song data. Make sure piu_songs_final.db is in the same folder as this page.</div>`;
    document.getElementById("results-count").textContent = "Error";
  }
}

init();