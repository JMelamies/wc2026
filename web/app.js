// Per-position colour hue: 1st=green, 2nd=blue, 3rd=amber, 4th=red
const HUE = [142, 210, 38, 0];

function cellStyle(prob, pos) {
  const alpha = (prob * 0.75 + 0.04).toFixed(2);
  return `background:hsla(${HUE[pos]},65%,52%,${alpha})`;
}

function renderGroup(name, group) {
  // Table header
  const ths = ['Team', '1st', '2nd', '3rd', '4th']
    .map((h, i) => `<th${i > 0 ? ' class="num"' : ''}>${h}</th>`)
    .join('');

  // Team rows — already sorted by probs[0] desc from Python
  const rows = group.teams.map(team => {
    const probCells = team.probs
      .map((p, pos) => `<td class="num" style="${cellStyle(p, pos)}">${(p * 100).toFixed(1)}%</td>`)
      .join('');
    return `<tr><td>${team.name}</td>${probCells}</tr>`;
  }).join('');

  // Match list below the table
  const matchItems = group.matches.map(m => {
    const teams = `<span class="match-teams">${m.home} vs ${m.away}</span>`;
    if (m.result) {
      let label;
      if (m.result === 'draw') {
        label = 'Draw';
      } else {
        const winner = m.result === 'home' ? m.home : m.away;
        label = `<strong>${winner}</strong> win`;
      }
      return `<li>${teams}<span class="match-ft">FT: ${label}</span></li>`;
    }
    const odds = [m.p_home, m.p_draw, m.p_away]
      .map(p => `${(p * 100).toFixed(1)}%`)
      .join(' / ');
    return `<li>${teams}<span class="match-odds">${odds}</span></li>`;
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

async function init() {
  const statusEl = document.getElementById('status');
  const appEl = document.getElementById('app');
  const genEl = document.getElementById('generated');

  try {
    const resp = await fetch('data/group_rankings.json');
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();

    genEl.textContent =
      'Based on bookmaker odds · Updated ' + data.generated.replace('T', ' ');

    const cards = Object.entries(data.groups)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([name, group]) => renderGroup(name, group))
      .join('');

    appEl.innerHTML = `<div class="grid">${cards}</div>`;
  } catch (err) {
    statusEl.textContent = 'Failed to load data: ' + err.message;
    statusEl.className = 'status error';
  }
}

init();
