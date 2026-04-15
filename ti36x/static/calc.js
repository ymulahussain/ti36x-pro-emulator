// TI-36X Pro emulator — frontend
async function fetchJSON(url, opts) {
  const r = await fetch(url, opts);
  return r.json();
}

async function press(name, el) {
  if (el) {
    el.classList.add("pressed");
    setTimeout(() => el.classList.remove("pressed"), 140);
  }
  await fetchJSON("/press", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key: name }),
  });
}

function makeKeyButton(name, meta) {
  const div = document.createElement("button");
  div.className = `key ${meta.group}`;
  div.dataset.name = name;
  if (meta.shift) {
    const s = document.createElement("div");
    s.className = "shift";
    s.textContent = meta.shift;
    div.appendChild(s);
  }
  const lbl = document.createElement("div");
  lbl.className = "label";
  lbl.textContent = meta.label;
  div.appendChild(lbl);
  div.addEventListener("click", () => press(name, div));
  return div;
}

async function buildKeypad() {
  const data = await fetchJSON("/keys");

  // menu row (3 wider shortcut keys above main grid)
  const menuEl = document.getElementById("menu-row");
  menuEl.innerHTML = "";
  for (const name of data.menu) {
    menuEl.appendChild(makeKeyButton(name, data.keys[name]));
  }

  // main grid
  const keysEl = document.getElementById("keys");
  const grid = data.grid;
  const rows = grid.length;
  const cols = grid[0].length;
  keysEl.style.gridTemplateColumns = `repeat(${cols}, 1fr)`;
  keysEl.innerHTML = "";
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const name = grid[r][c];
      if (!name) {
        const ph = document.createElement("div");
        ph.className = "key hidden";
        keysEl.appendChild(ph);
        continue;
      }
      keysEl.appendChild(makeKeyButton(name, data.keys[name]));
    }
  }

  // wire top-strip keys (2nd / mode / delete / nav pad arrows) — these live
  // in index.html so we just attach listeners by data-name
  document.querySelectorAll("[data-name]").forEach((el) => {
    if (el.closest("#keys")) return; // already wired
    const name = el.dataset.name;
    el.addEventListener("click", () => press(name, el));
  });
}

function renderState(s) {
  document.getElementById("entry-line").textContent = s.entry || "\u00a0";
  document.getElementById("result-line").textContent = s.result;
  document.getElementById("error-line").textContent = s.error || "";

  document.getElementById("status-2nd").classList.toggle("active", !!s.is_2nd);
  const angle = document.getElementById("status-angle");
  angle.textContent = s.angle;
  angle.classList.add("active");
  const mode = document.getElementById("status-mode");
  mode.textContent = s.mode;
  mode.classList.toggle("active", s.mode !== "NORMAL");
  document.getElementById("status-fmt").textContent = s.float_format;

  const ul = document.getElementById("history");
  ul.innerHTML = "";
  for (const [e, r] of s.history.slice().reverse()) {
    const li = document.createElement("li");
    const left = document.createElement("span");
    left.textContent = e;
    const right = document.createElement("span");
    right.className = "res";
    right.textContent = r;
    li.appendChild(left);
    li.appendChild(right);
    ul.appendChild(li);
  }

  const btn2 = document.querySelector('[data-name="2nd"]');
  if (btn2) btn2.classList.toggle("active", !!s.is_2nd);
}

function flashKey(name) {
  const el = document.querySelector(`[data-name="${name}"]`);
  if (!el) return;
  el.classList.add("flash");
  setTimeout(() => el.classList.remove("flash"), 350);
}

function connectEvents() {
  const es = new EventSource("/events");
  es.onmessage = (ev) => {
    const s = JSON.parse(ev.data);
    renderState(s);
  };
  es.onerror = () => setTimeout(connectEvents, 1500);
}

document.getElementById("reset-btn").addEventListener("click", async () => {
  await fetchJSON("/reset", { method: "POST" });
});

document.addEventListener("keydown", async (ev) => {
  const map = {
    "0":"0","1":"1","2":"2","3":"3","4":"4","5":"5","6":"6","7":"7","8":"8","9":"9",
    ".":"dot", "+":"add", "-":"sub", "*":"mul", "/":"div",
    "(":"lparen", ")":"rparen", "^":"power", "=":"enter", "Enter":"enter",
    "Backspace":"delete", "Escape":"clear",
    "ArrowLeft":"left", "ArrowRight":"right", "ArrowUp":"up", "ArrowDown":"down",
  };
  const n = map[ev.key];
  if (n) {
    ev.preventDefault();
    flashKey(n);
    await press(n);
  }
});

(async () => {
  await buildKeypad();
  const s = await fetchJSON("/state");
  renderState(s);
  connectEvents();
})();
