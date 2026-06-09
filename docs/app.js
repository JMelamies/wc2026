const HUE = [142, 210, 38, 0]; // 1st:green, 2nd:blue, 3rd:amber, 4th:red

const DISPLAY_NAMES = {
  'Bosnia-Herzegovina': 'Bosnia',
};

function dn(name) {
  return DISPLAY_NAMES[name] || name;
}

let appData = null;
let displayMode = 'prob'; // 'prob' | 'odds'

// --- formatters ---

function fmtCell(p) {
  return displayMode === 'prob'
    ? (p * 100).toFixed(1) + '%'
    : (1 / p).toFixed(2);
}

function fmtMatchLine(m) {
  if (displayMode === 'prob') {
    return [m.p_home, m.p_draw, m.p_away]
      .map(p => (p * 100).toFixed(1) + '%')
      .join(' / ');
  }
  return [m.p_home, m.p_draw, m.p_away]
    .map(p => (1 / p).toFixed(2))
    .join(' / ');
}

function fmtDate(isoStr) {
  if (!isoStr) return '';
  const d = new Date(isoStr);
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
}

function cellStyle(prob, pos) {
  const alpha = (prob * 0.75 + 0.04).toFixed(2);
  return `background:hsla(${HUE[pos]},65%,52%,${alpha})`;
}

// --- rendering ---

function renderGroup(name, group) {
  const ths = ['Team', '1st', '2nd', '3rd', '4th']
    .map((h, i) => `<th${i > 0 ? ' class="num"' : ''}>${h}</th>`)
    .join('');

  // Team rows — already sorted by probs[0] desc from Python
  const rows = group.teams.map(team => {
    const probCells = team.probs
      .map((p, pos) =>
        `<td class="num" style="${cellStyle(p, pos)}">${fmtCell(p)}</td>`)
      .join('');
    return `<tr><td>${dn(team.name)}</td>${probCells}</tr>`;
  }).join('');

  // Match list — already in chronological order from Python
  // Each <li> is a 3-column grid: date | teams | odds/result
  const matchItems = group.matches.map(m => {
    const date = `<span class="match-date">${fmtDate(m.date)}</span>`;
    const teams = `<span class="match-teams">${dn(m.home)} – ${dn(m.away)}</span>`;

    if (m.result) {
      let label;
      if (m.result === 'draw') {
        label = 'Draw';
      } else {
        const winner = dn(m.result === 'home' ? m.home : m.away);
        label = `<strong>${winner}</strong> win`;
      }
      return `<li>${date}${teams}<span class="match-ft">FT: ${label}</span></li>`;
    }
    return `<li>${date}${teams}<span class="match-odds">${fmtMatchLine(m)}</span></li>`;
  }).join('');

  return `
    <div class="card">
      <h2>Group ${name}</h2>
      <table>
        <thead><tr>${ths}</tr></thead>
        <tbody>${rows}</tbody>
      </table>
      <ul class="matches">${matchItems}</ul>
    </div>`;
}

function renderGrid() {
  document.getElementById('app').innerHTML =
    '<div class="grid">' +
    Object.entries(appData.groups)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([name, group]) => renderGroup(name, group))
      .join('') +
    '</div>';
}

function toggleMode() {
  displayMode = displayMode === 'prob' ? 'odds' : 'prob';
  document.getElementById('toggle-btn').textContent =
    displayMode === 'prob' ? 'Show as odds' : 'Show as %';
  renderGrid();
}

// --- init ---

async function init() {
  const statusEl = document.getElementById('status');
  const genEl = document.getElementById('generated');

  try {
    const resp = await fetch('data/group_rankings.json');
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    appData = await resp.json();

    genEl.textContent =
      'Based on bookmaker odds · Updated ' +
      appData.generated.replace('T', ' ');

    const btn = document.createElement('button');
    btn.id = 'toggle-btn';
    btn.className = 'toggle-btn';
    btn.textContent = 'Show as odds';
    btn.onclick = toggleMode;
    genEl.insertAdjacentElement('afterend', btn);

    renderGrid();
  } catch (err) {
    statusEl.textContent = 'Failed to load data: ' + err.message;
    statusEl.className = 'status error';
  }
}

init();
