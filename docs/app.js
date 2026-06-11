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
let flagSort  = { col: 'pct', dir: -1 }; // dir: -1=desc, 1=asc
let flagLimit = 10;
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

function liveMinute(dateStr) {
  if (!dateStr) return null;
  const start = new Date(dateStr).getTime();
  if (isNaN(start)) return null;
  const elapsed = Math.floor((Date.now() - start) / 60000);
  if (elapsed <= 0) return null;
  if (elapsed <= 48) return Math.min(elapsed, 45);
  if (elapsed <= 63) return 45;        // half-time window
  return Math.min(elapsed - 15, 90);  // second half, subtract HT break
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

function calcPct(sourceOdds, prob) {
  if (!sourceOdds || !prob || prob <= 0) return null;
  return (sourceOdds - 1 / prob) / (1 / prob);
}

function collectFlags() {
  if (!appData) return [];
  const items = [];

  for (const [groupName, group] of Object.entries(appData.groups)) {
    for (const team of group.teams) {
      const push = (type, prob, source, sourceOdds) => {
        const pct = calcPct(sourceOdds, prob);
        if (pct != null && pct >= flagT / 100)
          items.push({ group: groupName, type, label: dn(team.name), prob, source, sourceOdds, pct });
      };
      push('Winner',   team.probs[0],  'BF', team.bf_group_winner_odds);
      push('Winner',   team.probs[0],  'UB', team.ub_group_winner_odds);
      push('Advances', team.adv_prob,  'BF', team.bf_to_qualify_odds);
      push('4th',      team.probs[3],  'UB', team.ub_fourth_place_odds);
    }
    for (const pair of (group.pairs || [])) {
      const pct = calcPct(pair.ub_odds, pair.prob);
      if (pct != null && pct >= flagT / 100)
        items.push({
          group: groupName, type: '1st/2nd',
          label: `${dn(pair.first)} / ${dn(pair.second)}`,
          prob: pair.prob, source: 'UB', sourceOdds: pair.ub_odds, pct,
        });
    }
  }

  items.sort((a, b) => b.pct - a.pct);
  return items;
}

const FLAG_COLS = [
  { key: 'group',      label: 'Grp',        num: false },
  { key: 'type',       label: 'Type',       num: false },
  { key: 'label',      label: 'Team(s)',    num: false },
  { key: 'prob',       label: 'Our odds',   num: true  },
  { key: 'source',     label: 'Src',        num: true  },
  { key: 'sourceOdds', label: 'Their odds', num: true  },
  { key: 'pct',        label: 'Edge',       num: true  },
];

function sortedFlags(items) {
  const { col, dir } = flagSort;
  return [...items].sort((a, b) => {
    const av = a[col], bv = b[col];
    return typeof av === 'string' ? dir * av.localeCompare(bv) : dir * (av - bv);
  });
}

function renderFlags() {
  const el = document.getElementById('flags-section');
  if (!el) return;

  const all    = sortedFlags(collectFlags());
  const total  = all.length;
  if (!total) { el.innerHTML = ''; return; }

  const shown = all.slice(0, flagLimit);

  const isPct = displayMode === 'prob';
  const ths = FLAG_COLS.map(c => {
    let label = c.label;
    if (isPct && c.key === 'prob')       label = 'Our %';
    if (isPct && c.key === 'sourceOdds') label = 'Their %';
    const active = flagSort.col === c.key;
    const arrow  = active ? (flagSort.dir === -1 ? ' ▾' : ' ▴') : '';
    const cls    = 'sortable' + (c.num ? ' num' : '');
    return `<th class="${cls}" data-col="${c.key}">${label}${arrow}</th>`;
  }).join('');

  const rows = shown.map(item => `
    <tr>
      <td>${item.group}</td>
      <td>${item.type}</td>
      <td>${item.label}</td>
      <td class="num">${fmt(item.prob)}</td>
      <td class="num src-col">${item.source}</td>
      <td class="num">${fmtBf(item.sourceOdds)}</td>
      <td class="num flag-edge">+${(item.pct * 100).toFixed(0)}%</td>
    </tr>`).join('');

  const remaining = total - flagLimit;
  const moreBtn = remaining > 0
    ? `<button class="flags-more-btn" onclick="showMoreFlags()">Show ${Math.min(remaining, 10)} more (${remaining} remaining)</button>`
    : '';

  el.innerHTML = `
    <div class="flags-wrap">
      <div class="flags-card">
        <h2>Value flags (${total})</h2>
        <div class="flags-table-wrap">
          <table class="flags-table">
            <thead><tr>${ths}</tr></thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
        ${moreBtn}
      </div>
    </div>`;

  el.querySelectorAll('th[data-col]').forEach(th => {
    th.addEventListener('click', () => {
      const col = th.dataset.col;
      flagSort.dir = flagSort.col === col ? flagSort.dir * -1 : -1;
      flagSort.col = col;
      renderFlags();
    });
  });
}

function showMoreFlags() {
  flagLimit += 10;
  renderFlags();
}

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

  // Unibet: group winner (1st cells)
  document.querySelectorAll('[data-ub-gw]').forEach(cell => {
    const ubOdds = parseFloat(cell.dataset.ubGw);
    const prob   = parseFloat(cell.dataset.prob);
    cell.classList.remove('cell-ub-flag');
    const existing = cell.querySelector('.ub-odds');
    if (existing) existing.remove();
    if (!ubOdds || isNaN(ubOdds)) return;
    if (!flagLevel(ubOdds, prob)) return;
    cell.classList.add('cell-ub-flag');
    const span = document.createElement('span');
    span.className   = 'ub-odds';
    span.textContent = fmtBf(ubOdds);
    cell.appendChild(span);
  });

  // Unibet: 4th place cells
  document.querySelectorAll('[data-ub-fp]').forEach(cell => {
    const ubOdds = parseFloat(cell.dataset.ubFp);
    const prob   = parseFloat(cell.dataset.prob);
    cell.classList.remove('cell-ub-flag');
    const existing = cell.querySelector('.ub-odds');
    if (existing) existing.remove();
    if (!ubOdds || isNaN(ubOdds)) return;
    if (!flagLevel(ubOdds, prob)) return;
    cell.classList.add('cell-ub-flag');
    const span = document.createElement('span');
    span.className   = 'ub-odds';
    span.textContent = fmtBf(ubOdds);
    cell.appendChild(span);
  });

  // Unibet: pair odds cells
  document.querySelectorAll('[data-ub-pair]').forEach(cell => {
    const ubOdds = parseFloat(cell.dataset.ubPair);
    const prob   = parseFloat(cell.dataset.prob);
    cell.classList.remove('cell-ub-flag');
    const existing = cell.querySelector('.ub-odds');
    if (existing) existing.remove();
    if (!ubOdds || isNaN(ubOdds)) return;
    if (!flagLevel(ubOdds, prob)) return;
    cell.classList.add('cell-ub-flag');
    const span = document.createElement('span');
    span.className   = 'ub-odds';
    span.textContent = fmtBf(ubOdds);
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
        return `<td class="num" style="${cellStyle(p, pos)}" data-bf-gw="${team.bf_group_winner_odds || ''}" data-ub-gw="${team.ub_group_winner_odds || ''}" data-prob="${p}">${fmt(p)}</td>`;
      }
      if (pos === 3) {
        return `<td class="num" style="${cellStyle(p, pos)}" data-ub-fp="${team.ub_fourth_place_odds || ''}" data-prob="${p}">${fmt(p)}</td>`;
      }
      return `<td class="num" style="${cellStyle(p, pos)}">${fmt(p)}</td>`;
    }).join('');
    const advCell = `<td class="num adv-cell" style="${advStyle(team.adv_prob)}" data-bf-tq="${team.bf_to_qualify_odds || ''}" data-prob="${team.adv_prob}">${fmt(team.adv_prob)}</td>`;
    return `<tr><td>${dn(team.name)}</td>${posCells}${advCell}</tr>`;
  }).join('');

  // --- match list ---
  const matchItems = group.matches.map(m => {
    const date = `<span class="match-date">${fmtDate(m.date)}</span>`;

    let liveBadge = '';
    if (m.inplay) {
      const min = liveMinute(m.date);
      const minStr = min != null ? ` ${min}'` : '';
      const scoreStr = (m.score_home != null && m.score_away != null)
        ? ` ${m.score_home}–${m.score_away}` : '';
      liveBadge = `<span class="live-badge">🔴 LIVE${minStr}${scoreStr}</span>`;
    }

    // Live badge sits inside the teams span so the 3-column grid stays intact
    const teams = `<span class="match-teams">${dn(m.home)} – ${dn(m.away)}${liveBadge}</span>`;

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

  // --- pairs panel (conditionally rendered) ---
  const isOpen   = pairsOpen.has(name);
  const btnLabel = isOpen ? '1st/2nd pairs ▾' : '1st/2nd pairs ▸';
  const hasPairFlag = (group.pairs || []).some(pair =>
    pair.ub_odds && flagLevel(pair.ub_odds, pair.prob)
  );
  const pairFlagDot = hasPairFlag ? ' <span class="pair-flag-dot">check odds</span>' : '';

  let pairsHtml = '';
  if (isOpen && group.pairs && group.pairs.length) {
    const pairRows = group.pairs.map(pair => {
      const p  = pair.prob;
      const bg = `background:hsla(270,50%,60%,${(p * 1.8 + 0.05).toFixed(2)})`;
      return `<tr>
        <td>${dn(pair.first)}</td>
        <td>${dn(pair.second)}</td>
        <td class="num" style="${bg}" data-ub-pair="${pair.ub_odds || ''}" data-prob="${p}">${fmt(p)}</td>
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
      <button class="pairs-btn" onclick="togglePairs('${name}')">${btnLabel}${pairFlagDot}</button>
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
  renderFlags();
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
      flagT = parseFloat(e.target.value) || 0;
      flagLimit = 10;
      renderGrid();
    });

    renderGrid();
  } catch (err) {
    statusEl.textContent = 'Failed to load data: ' + err.message;
    statusEl.className   = 'status error';
  }
}

init();
