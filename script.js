const DIFFICULTY_MIN = 1;
const DIFFICULTY_MAX = 26;
const STORAGE_KEY = "piu-matcher-ranges";

const state = {
  p1min: 1, p1max: 26,
  p2min: 1, p2max: 26,
  activeTypes: new Set(["arcade"]),
    activeVersions: new Set(), // empty = all versions (populated once DB loads)
};

let db = null;

// --- Persistence -----------------------------------------------------
// Ranges persist across visits via localStorage. Note: this only works
// when the page is actually opened in a browser (e.g. hosted on GitHub
// Pages, or opened as a local file) — it will not persist inside a
// sandboxed preview environment that blocks localStorage.

function loadRanges() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const saved = JSON.parse(raw);
    Object.assign(state, saved);
    if (Array.isArray(saved.activeTypes)) {
      state.activeTypes = new Set(saved.activeTypes);
    }
    if (Array.isArray(saved.activeVersions)) {
      state.activeVersions = new Set(saved.activeVersions);
    }
  } catch (e) {
    console.warn("Could not load saved ranges:", e);
  }
}

function saveRanges() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      p1min: state.p1min, p1max: state.p1max,
      p2min: state.p2min, p2max: state.p2max,
      activeTypes: [...state.activeTypes],
      activeVersions: [...state.activeVersions],
    }));
  } catch (e) {
    console.warn("Could not save ranges to localStorage:", e);
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
    let holdTimeout = null;
    let holdInterval = null;
    let pointerSteppedThisPress = false;

    const step = () => {
      const target = btn.dataset.target;
      const dir = parseInt(btn.dataset.dir, 10);
      handleStep(target, dir);
    };

    btn.addEventListener("pointerdown", (e) => {
      e.preventDefault();
      pointerSteppedThisPress = true;
      step();

      holdTimeout = setTimeout(() => {
        holdInterval = setInterval(step, 100);
      }, 400);
    });

    const stopHold = () => {
      clearTimeout(holdTimeout);
      clearInterval(holdInterval);
      holdTimeout = null;
      holdInterval = null;
    };

    btn.addEventListener("pointerup", stopHold);
    btn.addEventListener("pointercancel", stopHold);
    btn.addEventListener("pointerleave", stopHold);

    // Keyboard accessibility: Enter/Space fires a "click" event, but never
    // pointerdown/pointerup, so without this keyboard and screen-reader
    // users couldn't use the steppers at all. Skip when a pointer already
    // handled this press, since a real click also fires right after
    // pointerup on mouse/touch.
    btn.addEventListener("click", () => {
      if (pointerSteppedThisPress) {
        pointerSteppedThisPress = false;
        return;
      }
      step();
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

let allVersions = [];

function getAllVersions() {
  const result = db.exec(`
    SELECT DISTINCT s.version, v.release_rank
    FROM songs s
    LEFT JOIN versions v ON v.version_name = s.version
    ORDER BY v.release_rank DESC
  `);
  if (!result.length) return [];
  return result[0].values.map((row) => row[0]);
}

function updateVersionDropdownLabel() {
  const label = document.getElementById("version-dropdown-label");
  const total = allVersions.length;
  const selected = state.activeVersions.size;
  if (selected === 0) {
    label.textContent = "No versions selected";
  } else if (selected === total) {
    label.textContent = "All versions";
  } else if (selected === 1) {
    label.textContent = [...state.activeVersions][0];
  } else {
    label.textContent = `${selected} versions selected`;
  }
}

function setupVersionDropdown() {
  allVersions = getAllVersions();

  // Nothing saved yet (fresh visitor) -> default to all versions included
  if (state.activeVersions.size === 0) {
    state.activeVersions = new Set(allVersions);
  }

  const menu = document.getElementById("version-dropdown-menu");
  menu.innerHTML = allVersions.map((v) => `
    <label class="version-option">
      <input type="checkbox" value="${escapeHtml(v)}" ${state.activeVersions.has(v) ? "checked" : ""}>
      ${escapeHtml(v)}
    </label>
  `).join("");

  menu.querySelectorAll("input").forEach((box) => {
    box.addEventListener("change", () => {
      if (box.checked) {
        state.activeVersions.add(box.value);
      } else {
        state.activeVersions.delete(box.value);
      }
      updateVersionDropdownLabel();
      saveRanges();
      renderResults();
    });
  });

  function refreshVersionCheckboxes() {
    document.querySelectorAll("#version-dropdown-menu input").forEach((box) => {
      box.checked = state.activeVersions.has(box.value);
    });
  }

  document.getElementById("version-select-all").addEventListener("click", () => {
    state.activeVersions = new Set(allVersions);
    refreshVersionCheckboxes();
    updateVersionDropdownLabel();
    saveRanges();
    renderResults();
  });

  document.getElementById("version-deselect-all").addEventListener("click", () => {
    state.activeVersions = new Set();
    refreshVersionCheckboxes();
    updateVersionDropdownLabel();
    saveRanges();
    renderResults();
  });

  const toggle = document.getElementById("version-dropdown-toggle");
  toggle.addEventListener("click", () => {
    const isOpen = !menu.hidden;
    menu.hidden = isOpen;
    toggle.setAttribute("aria-expanded", String(!isOpen));
  });

  document.addEventListener("click", (e) => {
    const dropdown = document.getElementById("version-dropdown");
    if (!dropdown.contains(e.target)) {
      menu.hidden = true;
      toggle.setAttribute("aria-expanded", "false");
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !menu.hidden) {
      menu.hidden = true;
      toggle.setAttribute("aria-expanded", "false");
      toggle.focus();
    }
  });

  updateVersionDropdownLabel();
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
// playable in the same song. Ordering by newest version first is done
// here in SQL via the versions table, rather than in JS, since the
// version ordering is now data (see version_order.json / build_db.py)
// rather than logic duplicated in the frontend.
function queryMatches() {
  const typeList = [...state.activeTypes].map((t) => `'${t}'`).join(",");
  if (!typeList) return [];
  if (state.activeVersions.size === 0) return [];

  const versionFilter = state.activeVersions.size < allVersions.length
    ? `AND s.version IN (${[...state.activeVersions].map((v) => `'${v.replace(/'/g, "''")}'`).join(",")})`
    : "";

  const sql = `
    SELECT s.song_id, s.title, s.version, s.song_type, n.note,
          GROUP_CONCAT(c.difficulty) as difficulties
    FROM songs s
    JOIN charts c ON c.song_id = s.song_id
    LEFT JOIN versions v ON v.version_name = s.version
    LEFT JOIN song_notes n ON n.song_id = s.song_id
    WHERE s.song_type IN (${typeList})
      ${versionFilter}
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
        <span class="song-title">${escapeHtml(song.title)}${song.note ? ` <span class="song-note">${escapeHtml(song.note)}</span>` : ""}</span>
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
    setupVersionDropdown();
    renderResults();
  } catch (e) {
    console.error("Failed to load database:", e);
    document.getElementById("results-list").innerHTML =
      `<div class="empty-state">Could not load song data. Make sure piu_songs_final.db is in the same folder as this page.</div>`;
    document.getElementById("results-count").textContent = "Error";
  }
}

init();