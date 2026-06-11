const HUE = [142, 210, 38, 0]; // 1st:green, 2nd:blue, 3rd:amber, 4th:red

const DISPLAY_NAMES = {
  'Bosnia-Herzegovina': 'Bosnia',
};

function dn(name) {
  return DISPLAY_NAMES[name] || name;
}

let appData     = null;
let displayMode = 'odds'; // 'prob' | 'odds'
let flagT = 20;
const pairsOpen = new Set(); // group names whose pair panel is expanded

// --- formatters ---

function fmt(p) {
  return displayMode === 'prob'
    ? (p * 100).toFixed(1) + '%'
    : (1 / p).toFixed(2);
}

function fmtMatchLine(m) {
  return [m.p_home, m.p_draw, m.p_away]
    .map(p => displayMode === 'prob' ? (p * 100).toFixed(1) + '%' : (1 / p).toFixed(2))
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

function advStyle(prob) {
  const alpha = (prob * 0.65 + 0.04).toFixed(2);
  return `background:hsla(142,50%,48%,${alpha})`;
}

// --- flagging ---

function flagLevel(bf_odds, our_prob) {
  if (!bf_odds || !our_prob || our_prob <= 0) return null;
  const our_odds = 1 / our_prob;
  const pct = (bf_odds - our_odds) / our_odds;
  return pct >= flagT / 100 ? 'flag' : null;
}

function fmtBf(bfOdds) {
  return displayMode === 'prob'
    ? ((1 / bfOdds) * 100).toFixed(1) + '%'
    : bfOdds.toFixed(2);
}

function applyFlags() {
  document.querySelectorAll('[data-bf-gw]').forEach(cell => {
    const bfOdds = parseFloat(cell.dataset.bfGw);
    const prob   = parseFloat(cell.dataset.prob);
    cell.classList.remove('cell-flag');
    const existing = cell.querySelector('.bf-odds');
    if (existing) existing.remove();
    if (!bfOdds || isNaN(bfOdds)) return;
    if (!flagLevel(bfOdds, prob)) return;
    cell.classList.add('cell-flag');
    const span = document.createElement('span');
    span.className   = 'bf-odds';
    span.textContent = fmtBf(bfOdds);
    cell.appendChild(span);
  });

  document.querySelectorAll('[data-bf-tq]').forEach(cell => {
    const bfOdds = parseFloat(cell.dataset.bfTq);
    const prob   = parseFloat(cell.dataset.prob);
    cell.classList.remove('cell-flag');
    const existing = cell.querySelector('.bf-odds');
    if (existing) existing.remove();
    if (!bfOdds || isNaN(bfOdds)) return;
    if (!flagLevel(bfOdds, prob)) return;
    cell.classList.add('cell-flag');
    const span = document.createElement('span');
    span.className   = 'bf-odds';
    span.textContent = fmtBf(bfOdds);
    cell.appendChild(span);
  });
}

// --- rendering ---

function renderGroup(name, group) {
  // --- main table ---
  const ths = ['Team', '1st', '2nd', '3rd', '4th', 'Adv']
    .map((h, i) => `<th${i > 0 ? ' class="num"' : ''}>${h}</th>`)
    .join('');

  const rows = group.teams.map(team => {
    const posCells = team.probs.map((p, pos) => {
      if (pos === 0) {
        return `<td class="num" style="${cellStyle(p, pos)}" data-bf-gw="${team.bf_group_winner_odds || ''}" data-prob="${p}">${fmt(p)}</td>`;
      }
      return `<td class="num" style="${cellStyle(p, pos)}">${fmt(p)}</td>`;
    }).join('');
    const advCell = `<td class="num adv-cell" style="${advStyle(team.adv_prob)}" data-bf-tq="${team.bf_to_qualify_odds || ''}" data-prob="${team.adv_prob}">${fmt(team.adv_prob)}</td>`;
    return `<tr><td>${dn(team.name)}</td>${posCells}${advCell}</tr>`;
  }).join('');

  // --- match list ---
  const matchItems = group.matches.map(m => {
    const date     = `<span class="match-date">${fmtDate(m.date)}</span>`;
    const teams    = `<span class="match-teams">${dn(m.home)} – ${dn(m.away)}</span>`;
    const liveBadge = m.inplay ? '<span class="live-badge">🔴 LIVE</span>' : '';
    if (m.result) {
      let label;
      if (m.result === 'draw') {
        label = 'Draw';
      } else {
        const winner = dn(m.result === 'home' ? m.home : m.away);
        label = `<strong>${winner}</strong> win`;
      }
      return `<li>${date}${teams}<span class="match-ft">FT: ${label}</span>${liveBadge}</li>`;
    }
    return `<li>${date}${teams}<span class="match-odds">${fmtMatchLine(m)}</span>${liveBadge}</li>`;
  }).join('');

  // --- pairs panel (conditionally rendered) ---
  const isOpen   = pairsOpen.has(name);
  const btnLabel = isOpen ? '1st/2nd pairs ▾' : '1st/2nd pairs ▸';

  let pairsHtml = '';
  if (isOpen && group.pairs && group.pairs.length) {
    const pairRows = group.pairs.map(pair => {
      const p  = pair.prob;
      const bg = `background:hsla(270,50%,60%,${(p * 1.8 + 0.05).toFixed(2)})`;
      return `<tr>
        <td>${dn(pair.first)}</td>
        <td>${dn(pair.second)}</td>
        <td class="num" style="${bg}">${fmt(p)}</td>
      </tr>`;
    }).join('');

    pairsHtml = `
      <div class="pairs-panel">
        <table class="pairs-table">
          <thead><tr><th>1st</th><th>2nd</th><th class="num">${displayMode === 'prob' ? 'Prob' : 'Odds'}</th></tr></thead>
          <tbody>${pairRows}</tbody>
        </table>
      </div>`;
  }

  return `
    <div class="card">
      <h2>Group ${name}</h2>
      <table>
        <thead><tr>${ths}</tr></thead>
        <tbody>${rows}</tbody>
      </table>
      <ul class="matches">${matchItems}</ul>
      <button class="pairs-btn" onclick="togglePairs('${name}')">${btnLabel}</button>
      ${pairsHtml}
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
  applyFlags();
}

function togglePairs(name) {
  pairsOpen.has(name) ? pairsOpen.delete(name) : pairsOpen.add(name);
  renderGrid();
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
  const genEl    = document.getElementById('generated');

  try {
    const resp = await fetch('data/group_rankings.json');
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    appData = await resp.json();

    genEl.textContent =
      'Based on bookmaker odds · Updated ' + appData.generated.replace('T', ' ');

    const btn = document.createElement('button');
    btn.id        = 'toggle-btn';
    btn.className = 'toggle-btn';
    btn.textContent = 'Show as %';
    btn.onclick   = toggleMode;
    genEl.insertAdjacentElement('afterend', btn);

    const controls = document.createElement('div');
    controls.className = 'threshold-controls';
    controls.innerHTML =
      'Flag threshold: <input type="number" id="flagT" value="20" min="0" max="100"> %';
    btn.insertAdjacentElement('afterend', controls);

    document.getElementById('flagT').addEventListener('input', e => {
      flagT = parseFloat(e.target.value) || 0; applyFlags();
    });

    renderGrid();
  } catch (err) {
    statusEl.textContent = 'Failed to load data: ' + err.message;
    statusEl.className   = 'status error';
  }
}

init();
