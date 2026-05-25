'use strict';

// ══════════════════════════════════════════════════════════════
// STATE
// ══════════════════════════════════════════════════════════════
const state = {
  testSpec:     null,
  students:     null,
  results:      null,
  questionStats:null,
  sectionStats: null,
  studentStats: null,
  charts:       {}
};

// ══════════════════════════════════════════════════════════════
// LLM PROMPT TEMPLATE (JSON FORMAT)
// ══════════════════════════════════════════════════════════════
const LLM_PROMPT = `You are an expert curriculum designer creating a Concept Inventory — a diagnostic multiple-choice assessment designed to reveal specific student misconceptions.

Generate a Concept Inventory for the following specification:

  Subject:        [e.g. IB DP Computer Science]
  Topic:          [e.g. Topic A1 — Computer Architecture]
  Subtopics:      [e.g. A1.1 CPU, A1.2 Memory, A1.3 Operating Systems]
  Total questions:[e.g. 30]
  Target level:   [e.g. Year 12, pre-exam diagnostic]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT — produce a JSON array with this structure:

[
  {
    "question_number": 1,
    "topic_code": "A1.1",
    "topic_name": "CPU Architecture",
    "question": "Full question stem text here",
    "options": {
      "A": "Text of option A",
      "B": "Text of option B",
      "C": "Text of option C",
      "D": "Text of option D"
    },
    "correct_answer": "B",
    "misconceptions": {
      "A": "SHORT phrase (5-15 words) describing the misconception if a student chooses A",
      "C": "SHORT phrase describing the misconception if a student chooses C",
      "D": "SHORT phrase describing the misconception if a student chooses D"
    }
  }
]

Field definitions:
  question_number — sequential integer starting at 1
  topic_code      — hierarchical code e.g. A1.1, B2.3 (same for all questions in the same subtopic)
  topic_name      — human-readable subtopic name (same for all questions with the same topic_code)
  question        — full question stem text (standalone, no references to other questions)
  options         — object with exactly four keys: "A", "B", "C", "D" (no letter prefix in the values)
  correct_answer  — exactly one uppercase letter: "A", "B", "C", or "D"
  misconceptions  — object containing ONLY the wrong answer letters as keys;
                    each value is a SHORT phrase (5-15 words) describing the misconception;
                    DO NOT include the correct answer letter in this object at all

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DESIGN RULES:
  1. Every distractor (wrong answer) must target ONE specific, named student misconception
  2. Misconceptions should reflect: confusing similar concepts, reversing cause/effect,
     overgeneralising rules, misapplying definitions, or conflating related terms
  3. Questions test CONCEPTUAL UNDERSTANDING — not memorisation, recall, or calculation
  4. Distribute correct answers roughly evenly across A, B, C, D
  5. Group questions so consecutive elements share the same topic_code
  6. No "all of the above", "none of the above", or negative phrasing ("Which is NOT...")
  7. Each question must be answerable in 30-60 seconds

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT RULES:
  • Output ONLY the raw JSON array — no markdown code fences, no preamble, no explanation
  • Start directly with [ and end with ]
  • Use standard JSON: double-quoted strings, no trailing commas
  • The misconceptions object must omit the correct answer key entirely (not set it to null or "")`;


// ══════════════════════════════════════════════════════════════
// CSV PARSING
// ══════════════════════════════════════════════════════════════

function parseTestSpecCsv(csvText) {
  const result = Papa.parse(csvText.trim(), {
    header: true,
    skipEmptyLines: true,
    transformHeader: h => h.trim().toLowerCase().replace(/[\s\-]+/g, '_')
  });

  if (result.errors.length > 0 && result.data.length === 0) {
    throw new Error('Test spec CSV could not be parsed: ' + result.errors[0].message);
  }

  return result.data
    .filter(row => row.question_number || row.question)
    .map((row, i) => {
      const topicCode = (row.topic_code || '').trim();
      const topicName = (row.topic_name || row.section || '').trim();
      const section   = topicCode && topicName
        ? `${topicCode} — ${topicName}`
        : (topicName || topicCode || 'General');
      return {
        index:   i,
        number:  (row.question_number || String(i + 1)).trim(),
        topicCode,
        topicName,
        section,
        question: (row.question || '').trim(),
        answers: {
          A: (row.answer_a || '').trim(),
          B: (row.answer_b || '').trim(),
          C: (row.answer_c || '').trim(),
          D: (row.answer_d || '').trim()
        },
        correct: (row.correct_answer || '').trim().toUpperCase(),
        misconceptions: {
          A: (row.misconception_a || '').trim(),
          B: (row.misconception_b || '').trim(),
          C: (row.misconception_c || '').trim(),
          D: (row.misconception_d || '').trim()
        }
      };
    });
}

function parseTestSpecJson(jsonText) {
  let data;
  try {
    data = JSON.parse(jsonText);
  } catch (e) {
    throw new Error('Test spec JSON could not be parsed: ' + e.message);
  }

  if (!Array.isArray(data)) {
    throw new Error('Test spec JSON must be an array of question objects.');
  }

  return data
    .filter(item => item.question_number || item.question)
    .map((item, i) => {
      const topicCode = String(item.topic_code || '').trim();
      const topicName = String(item.topic_name || '').trim();
      const section   = topicCode && topicName
        ? `${topicCode} — ${topicName}`
        : (topicName || topicCode || 'General');

      const opts = item.options || {};
      const mc   = item.misconceptions || {};
      const correct = String(item.correct_answer || '').trim().toUpperCase();

      return {
        index:   i,
        number:  String(item.question_number || i + 1).trim(),
        topicCode,
        topicName,
        section,
        question: String(item.question || '').trim(),
        answers: {
          A: String(opts.A || '').trim(),
          B: String(opts.B || '').trim(),
          C: String(opts.C || '').trim(),
          D: String(opts.D || '').trim()
        },
        correct,
        misconceptions: {
          A: String(mc.A || '').trim(),
          B: String(mc.B || '').trim(),
          C: String(mc.C || '').trim(),
          D: String(mc.D || '').trim()
        }
      };
    });
}

function parseTestSpec(text, isJson) {
  return isJson ? parseTestSpecJson(text) : parseTestSpecCsv(text);
}

function parseStudentAnswers(csvText) {
  const result = Papa.parse(csvText.trim(), { skipEmptyLines: true });

  if (result.errors.length > 0 && result.data.length === 0) {
    throw new Error('Student answers CSV could not be parsed: ' + result.errors[0].message);
  }

  const rows = result.data;
  if (rows.length < 2) throw new Error('Student answers CSV has no data rows');

  // col 0 = timestamp (skip), col 1 = email, col 2 = name, col 3+ = answers
  return rows.slice(1)
    .map(row => ({
      email:   (row[1] || '').trim(),
      name:    (row[2] || '').trim(),
      answers: row.slice(3).map(a => extractAnswer(a))
    }))
    .filter(s => s.name);
}

function extractAnswer(raw) {
  if (!raw) return '';
  raw = String(raw).trim();
  if (raw.length === 1 && 'ABCD'.includes(raw.toUpperCase())) return raw.toUpperCase();
  if (raw.length >= 2 && 'ABCD'.includes(raw[0].toUpperCase()) && '.): -'.includes(raw[1])) {
    return raw[0].toUpperCase();
  }
  const first = raw[0] ? raw[0].toUpperCase() : '';
  return 'ABCD'.includes(first) ? first : '';
}


// ══════════════════════════════════════════════════════════════
// COMPUTATION
// ══════════════════════════════════════════════════════════════

function computeAll() {
  const { testSpec, students } = state;
  const numQ = testSpec.length;

  // Results[studentIdx][questionIdx] = boolean
  const results = students.map(student =>
    testSpec.map((q, qi) => {
      const ans = student.answers[qi] || '';
      return ans !== '' && ans === q.correct;
    })
  );

  // Per-question stats
  const questionStats = testSpec.map((q, qi) => {
    const counts = { A: 0, B: 0, C: 0, D: 0 };
    students.forEach(student => {
      const ans = student.answers[qi] || '';
      if (ans in counts) counts[ans]++;
    });
    const total = students.length;
    const percentages = {};
    ['A','B','C','D'].forEach(k => {
      percentages[k] = total > 0 ? (counts[k] / total * 100) : 0;
    });
    return { total, counts, percentages, correctPct: percentages[q.correct] || 0 };
  });

  // Per-section stats (preserve order of first appearance)
  const sectionOrder = [];
  const sectionMap   = {};
  testSpec.forEach((q, qi) => {
    if (!sectionMap[q.section]) {
      sectionMap[q.section] = { name: q.section, topicCode: q.topicCode, questionIndices: [] };
      sectionOrder.push(q.section);
    }
    sectionMap[q.section].questionIndices.push(qi);
  });

  const sectionStats = sectionOrder.map(key => {
    const s = sectionMap[key];
    let totalCorrect = 0, totalPossible = 0;
    s.questionIndices.forEach(qi => {
      students.forEach((_, si) => {
        if (results[si][qi]) totalCorrect++;
        totalPossible++;
      });
    });
    return {
      name:           s.name,
      topicCode:      s.topicCode,
      questionIndices: s.questionIndices,
      questionCount:  s.questionIndices.length,
      avgCorrect:     totalPossible > 0 ? (totalCorrect / totalPossible * 100) : 0
    };
  });

  // Per-student stats
  const studentStats = students.map((student, si) => {
    const correct = results[si].filter(Boolean).length;
    return {
      name:    student.name,
      email:   student.email,
      answers: student.answers,
      correct,
      total:   numQ,
      pct:     numQ > 0 ? (correct / numQ * 100) : 0
    };
  });

  state.results      = results;
  state.questionStats= questionStats;
  state.sectionStats = sectionStats;
  state.studentStats = studentStats;
}


// ══════════════════════════════════════════════════════════════
// COLOR UTILITIES
// ══════════════════════════════════════════════════════════════

function heatColor(pct) {
  const t = Math.max(0, Math.min(100, pct)) / 100;
  const r = Math.round(240 - t * (240 -  3));
  const g = Math.round(249 - t * (249 - 105));
  const b = Math.round(255 - t * (255 - 161));
  return `rgb(${r},${g},${b})`;
}

function heatTextColor(pct) {
  const t = pct / 100;
  const r = 240 - t * 237, g = 249 - t * 144, b = 255 - t * 94;
  const lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return lum < 0.55 ? '#ffffff' : '#0f172a';
}

function perfColor(pct) {
  if (pct >= 70) return '#16a34a';
  if (pct >= 50) return '#d97706';
  return '#dc2626';
}

function perfBgColor(pct) {
  if (pct >= 70) return '#f0fdf4';
  if (pct >= 50) return '#fffbeb';
  return '#fff1f2';
}

function bandLabel(pct) {
  if (pct >= 90) return 'Excellent';
  if (pct >= 75) return 'Strong foundation';
  if (pct >= 60) return 'Good — isolated gaps';
  if (pct >= 40) return 'Mixed — targeted review needed';
  if (pct >= 25) return 'Significant gaps';
  return 'Weak foundations — re-teaching needed';
}


// ══════════════════════════════════════════════════════════════
// DASHBOARD ENTRY POINT
// ══════════════════════════════════════════════════════════════

function renderDashboard() {
  // Reset lazy-render flags for new analysis
  Object.keys(tabRendered).forEach(k => delete tabRendered[k]);
  tabRendered['overview']   = true;
  tabRendered['questions']  = true;
  tabRendered['register']   = true;
  tabRendered['student']    = true;

  const avgPct = state.studentStats.reduce((a, s) => a + s.pct, 0) / state.studentStats.length;
  document.getElementById('stat-students').textContent  = state.students.length;
  document.getElementById('stat-questions').textContent = state.testSpec.length;
  document.getElementById('stat-sections').textContent  = state.sectionStats.length;
  document.getElementById('stat-average').textContent   = avgPct.toFixed(1) + '%';

  renderOverview();
  renderQuestionHeatmap();
  // Section chart deferred: rendered when tab is first clicked (avoids 0-width canvas in hidden tab)
  populateSectionPlaceholder();
  renderRegisterHeatmap('name');
  populateStudentDropdown();
}

function populateSectionPlaceholder() {
  // Pre-populate section cards (no chart) so content is ready; chart renders on tab click
  renderSectionTabCards();
}


// ══════════════════════════════════════════════════════════════
// OVERVIEW TAB
// ══════════════════════════════════════════════════════════════

function renderOverview() {
  const { studentStats, sectionStats, testSpec, questionStats } = state;

  // Score distribution histogram
  const bins = Array(10).fill(0);
  studentStats.forEach(s => { bins[Math.min(9, Math.floor(s.pct / 10))]++; });

  const ctxDist = document.getElementById('chart-score-dist');
  if (state.charts.scoreDist) state.charts.scoreDist.destroy();
  state.charts.scoreDist = new Chart(ctxDist, {
    type: 'bar',
    data: {
      labels: ['0–9%','10–19%','20–29%','30–39%','40–49%','50–59%','60–69%','70–79%','80–89%','90–100%'],
      datasets: [{
        data: bins,
        backgroundColor: bins.map((_, i) => perfColor(i * 10 + 5)),
        borderRadius: 4,
        borderSkipped: false
      }]
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        y: { beginAtZero: true, ticks: { precision: 0 }, title: { display: true, text: 'Students' } },
        x: { title: { display: true, text: 'Score range' } }
      }
    }
  });

  // Section overview chart
  const ctxSec = document.getElementById('chart-section-overview');
  if (state.charts.sectionOverview) state.charts.sectionOverview.destroy();
  state.charts.sectionOverview = new Chart(ctxSec, {
    type: 'bar',
    data: {
      labels: sectionStats.map(s => s.name.length > 30 ? s.name.slice(0, 30) + '…' : s.name),
      datasets: [{
        data: sectionStats.map(s => parseFloat(s.avgCorrect.toFixed(1))),
        backgroundColor: sectionStats.map(s => perfColor(s.avgCorrect)),
        borderRadius: 4,
        borderSkipped: false
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => `${ctx.raw}% correct (${sectionStats[ctx.dataIndex].questionCount} questions)`
          }
        }
      },
      scales: {
        x: { beginAtZero: true, max: 100, title: { display: true, text: '% Correct' } }
      }
    }
  });

  // Insights: top/bottom questions
  const sorted = questionStats
    .map((qs, i) => ({ qs, i, q: testSpec[i] }))
    .sort((a, b) => a.qs.correctPct - b.qs.correctPct);

  const bottom = sorted.slice(0, Math.min(3, sorted.length));
  const top    = sorted.slice(-Math.min(3, sorted.length)).reverse();

  document.getElementById('insights-container').innerHTML = `
    <div class="insight-box">
      <h3 class="insight-title insight-challenging">Most Challenging Questions</h3>
      ${bottom.map(({ q, qs }) => `
        <div class="insight-item">
          <span class="insight-qnum">${esc(q.number)}</span>
          <span class="insight-qtext">${esc(trunc(q.question || q.section, 80))}</span>
          <span class="insight-pct" style="color:${perfColor(qs.correctPct)}">${qs.correctPct.toFixed(0)}%</span>
        </div>`).join('')}
    </div>
    <div class="insight-box">
      <h3 class="insight-title insight-best">Best Understood Questions</h3>
      ${top.map(({ q, qs }) => `
        <div class="insight-item">
          <span class="insight-qnum">${esc(q.number)}</span>
          <span class="insight-qtext">${esc(trunc(q.question || q.section, 80))}</span>
          <span class="insight-pct" style="color:${perfColor(qs.correctPct)}">${qs.correctPct.toFixed(0)}%</span>
        </div>`).join('')}
    </div>`;
}


// ══════════════════════════════════════════════════════════════
// QUESTION HEATMAP
// ══════════════════════════════════════════════════════════════

const cellDataMap = new Map();

function renderQuestionHeatmap() {
  const { testSpec, questionStats } = state;
  cellDataMap.clear();

  // Group by section preserving order
  const sections = [];
  const sectionIdx = {};
  testSpec.forEach((q, i) => {
    if (!(q.section in sectionIdx)) {
      sectionIdx[q.section] = sections.length;
      sections.push({ name: q.section, rows: [] });
    }
    sections[sectionIdx[q.section]].rows.push(i);
  });

  let html = `
    <table class="heatmap-table">
      <thead>
        <tr>
          <th class="col-qnum">Q#</th>
          <th class="col-section">Section</th>
          <th>Question</th>
          <th class="col-answer">A</th>
          <th class="col-answer">B</th>
          <th class="col-answer">C</th>
          <th class="col-answer">D</th>
          <th class="col-correct-pct">Correct&nbsp;%</th>
        </tr>
      </thead>
      <tbody>`;

  sections.forEach(sec => {
    sec.rows.forEach((qi, rowInSec) => {
      const q  = testSpec[qi];
      const qs = questionStats[qi];

      html += `<tr>`;
      html += `<td class="col-qnum">${esc(q.number)}</td>`;
      html += `<td class="col-section">${rowInSec === 0 ? esc(q.section) : ''}</td>`;

      const qText = q.question || q.section;
      html += `<td class="col-question" title="${esc(qText)}">${esc(trunc(qText, 75))}</td>`;

      ['A','B','C','D'].forEach(letter => {
        const pct     = qs.percentages[letter];
        const count   = qs.counts[letter];
        const correct = letter === q.correct;
        const key     = `${qi}-${letter}`;

        cellDataMap.set(key, {
          letter,
          answer:       q.answers[letter],
          count,
          pct:          pct.toFixed(1),
          isCorrect:    correct,
          misconception: correct ? '' : q.misconceptions[letter]
        });

        html += `<td class="answer-cell${correct ? ' correct-cell' : ''}"
          style="background:${heatColor(pct)};color:${heatTextColor(pct)}"
          data-key="${key}">
          ${correct ? '<span class="correct-dot">&#10003;</span>' : ''}
          ${pct.toFixed(0)}%
        </td>`;
      });

      const cp = qs.correctPct;
      html += `<td class="col-correct-pct-td" style="color:${perfColor(cp)}">${cp.toFixed(0)}%</td>`;
      html += `</tr>`;
    });
  });

  html += `</tbody></table>`;
  const container = document.getElementById('question-heatmap-container');
  container.innerHTML = html;

  container.querySelectorAll('.answer-cell').forEach(cell => {
    cell.addEventListener('mouseenter', e => {
      const data = cellDataMap.get(cell.dataset.key);
      if (data) showTooltip(e, data);
    });
    cell.addEventListener('mouseleave', hideTooltip);
  });
}


// ══════════════════════════════════════════════════════════════
// SECTION SUMMARY
// ══════════════════════════════════════════════════════════════

function renderSectionTab() {
  renderSectionChart();
  renderSectionTabCards();
}

function renderSectionChart() {
  const { sectionStats } = state;
  const ctx = document.getElementById('chart-sections');
  if (state.charts.sections) state.charts.sections.destroy();
  state.charts.sections = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: sectionStats.map(s => s.name.length > 40 ? s.name.slice(0, 40) + '…' : s.name),
      datasets: [{
        data: sectionStats.map(s => parseFloat(s.avgCorrect.toFixed(1))),
        backgroundColor: sectionStats.map(s => perfColor(s.avgCorrect)),
        borderRadius: 6,
        borderSkipped: false
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => `${ctx.raw}% average correct`
          }
        }
      },
      scales: {
        x: {
          beginAtZero: true,
          max: 100,
          title: { display: true, text: '% Correct' },
          ticks: { callback: v => v + '%' }
        }
      }
    }
  });
}

function renderSectionTabCards() {
  const { sectionStats, testSpec, questionStats } = state;

  const cards = sectionStats.map(sec => {
    const qRows = sec.questionIndices.map(qi => {
      const q  = testSpec[qi];
      const qs = questionStats[qi];
      const qText = q.question || q.section;
      return `<div class="section-q-row">
        <span class="section-q-num">${esc(q.number)}</span>
        <span class="section-q-text">${esc(trunc(qText, 90))}</span>
        <span class="section-q-pct" style="color:${perfColor(qs.correctPct)}">${qs.correctPct.toFixed(0)}%</span>
      </div>`;
    }).join('');

    return `<div class="section-card">
      <div class="section-card-header" style="border-left-color:${perfColor(sec.avgCorrect)}">
        <h3>${esc(sec.name)}</h3>
        <span class="section-card-avg" style="color:${perfColor(sec.avgCorrect)}">${sec.avgCorrect.toFixed(0)}% avg</span>
      </div>
      <div class="section-q-list">${qRows}</div>
    </div>`;
  }).join('');

  document.getElementById('section-detail-container').innerHTML = cards;
}


// ══════════════════════════════════════════════════════════════
// CLASS REGISTER
// ══════════════════════════════════════════════════════════════

function renderRegisterHeatmap(sortBy) {
  const { testSpec, studentStats, results, students } = state;

  let indices = studentStats.map((_, i) => i);
  if      (sortBy === 'score-desc') indices.sort((a, b) => studentStats[b].pct - studentStats[a].pct);
  else if (sortBy === 'score-asc')  indices.sort((a, b) => studentStats[a].pct - studentStats[b].pct);
  else                              indices.sort((a, b) => studentStats[a].name.localeCompare(studentStats[b].name));

  const qHeaders = testSpec.map(q =>
    `<th title="${esc(q.question || q.section)}">${esc(q.number)}</th>`
  ).join('');

  let rows = indices.map(si => {
    const s = studentStats[si];
    const cells = results[si].map((correct, qi) => {
      const ans = (students[si].answers[qi] || '?');
      const title = `${trunc(testSpec[qi].question || testSpec[qi].section, 50)}\nYou: ${ans} | Correct: ${testSpec[qi].correct}`;
      return `<td class="${correct ? 'cell-correct' : 'cell-incorrect'}" title="${esc(title)}">${esc(ans)}</td>`;
    }).join('');

    return `<tr>
      <td class="reg-name-cell">${esc(s.name)}</td>
      ${cells}
      <td class="reg-score-cell" style="color:${perfColor(s.pct)}">${s.correct}/${s.total}</td>
      <td class="reg-pct-cell"   style="color:${perfColor(s.pct)}">${s.pct.toFixed(0)}%</td>
    </tr>`;
  }).join('');

  document.getElementById('register-heatmap-container').innerHTML = `
    <table class="register-table">
      <thead>
        <tr>
          <th class="reg-name-h">Student</th>
          ${qHeaders}
          <th>Score</th>
          <th>%</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>`;
}


// ══════════════════════════════════════════════════════════════
// INDIVIDUAL STUDENT REPORT
// ══════════════════════════════════════════════════════════════

function populateStudentDropdown() {
  const select = document.getElementById('student-select');
  const sorted = state.studentStats
    .map((s, i) => ({ ...s, i }))
    .sort((a, b) => a.name.localeCompare(b.name));

  select.innerHTML = '<option value="">-- Select a student --</option>' +
    sorted.map(s => `<option value="${s.i}">${esc(s.name)}</option>`).join('');
}

function renderStudentReport(idx) {
  const container = document.getElementById('student-report-container');
  if (idx === '' || idx === null) { container.innerHTML = ''; return; }

  const si  = parseInt(idx);
  const s   = state.studentStats[si];
  const row = state.results[si];
  const { testSpec } = state;

  const correct   = row.map((r, qi) => ({ r, qi })).filter(x => x.r);
  const incorrect = row.map((r, qi) => ({ r, qi })).filter(x => !x.r);
  const pc        = perfColor(s.pct);

  const incorrectHtml = incorrect.length === 0
    ? '<p class="no-items">All questions answered correctly!</p>'
    : incorrect.map(({ qi }) => {
        const q   = testSpec[qi];
        const ans = s.answers[qi] || '?';
        const mc  = q.misconceptions[ans] || 'No misconception data available for this answer.';
        return `<div class="student-incorrect-item">
          <div class="student-q-header">
            <span class="student-q-num">${esc(q.number)}</span>
            <span class="student-q-section">${esc(q.section)}</span>
          </div>
          <p class="student-q-text">${esc(q.question || q.section)}</p>
          <div class="student-answer-comparison">
            <div class="student-wrong-answer">
              <span class="answer-label wrong-label">Answered: ${esc(ans)}</span>
              <span class="answer-text">${esc(q.answers[ans] || '(no text)')}</span>
            </div>
            <div class="student-right-answer">
              <span class="answer-label right-label">Correct: ${esc(q.correct)}</span>
              <span class="answer-text">${esc(q.answers[q.correct] || '')}</span>
            </div>
          </div>
          <div class="misconception-box">
            <strong>Possible misconception:</strong> ${esc(mc)}
          </div>
        </div>`;
      }).join('');

  const correctHtml = correct.length === 0
    ? '<p class="no-items">No correct answers.</p>'
    : `<div class="correct-list">${correct.map(({ qi }) => {
        const q = testSpec[qi];
        return `<div class="student-correct-item">
          <span class="student-q-num">${esc(q.number)}</span>
          <span class="student-q-section">${esc(q.section)}</span>
          <span class="student-q-text-short">${esc(trunc(q.question || q.section, 75))}</span>
        </div>`;
      }).join('')}</div>`;

  container.innerHTML = `
    <div class="student-report">
      <div class="student-score-header">
        <div class="student-score-big" style="color:${pc}">${s.correct}<span class="score-denom">/${s.total}</span></div>
        <div>
          <div class="student-name">${esc(s.name)}</div>
          <div class="student-email">${esc(s.email)}</div>
          <div class="student-pct" style="color:${pc}">${s.pct.toFixed(1)}%</div>
          <div class="student-band" style="color:${pc}">${bandLabel(s.pct)}</div>
        </div>
      </div>
      <div class="score-bar-container">
        <div class="score-bar" style="width:${s.pct}%;background:${pc}"></div>
      </div>
      <div class="student-sections">
        <div class="student-section-panel">
          <h3 class="incorrect-heading">Incorrect (${incorrect.length})</h3>
          ${incorrectHtml}
        </div>
        <div class="student-section-panel">
          <h3 class="correct-heading">Correct (${correct.length})</h3>
          ${correctHtml}
        </div>
      </div>
    </div>`;
}


// ══════════════════════════════════════════════════════════════
// TOOLTIP
// ══════════════════════════════════════════════════════════════

const tooltip = document.getElementById('tooltip');

function showTooltip(event, data) {
  let html = `<div class="tt-letter">${esc(data.letter)}</div>`;
  if (data.answer) html += `<div class="tt-answer">${esc(data.answer)}</div>`;
  html += `<div class="tt-stats">${data.count} students (${data.pct}%)</div>`;
  if (data.isCorrect) {
    html += `<div class="tt-correct">&#10003; Correct answer</div>`;
  } else if (data.misconception) {
    html += `<div class="tt-misconception"><strong>Misconception:</strong> ${esc(data.misconception)}</div>`;
  }
  tooltip.innerHTML = html;
  tooltip.style.display = 'block';
  positionTooltip(event);
}

function hideTooltip() {
  tooltip.style.display = 'none';
}

function positionTooltip(e) {
  const x = e.clientX + 18;
  const y = e.clientY - 10;
  const mw = window.innerWidth  - tooltip.offsetWidth  - 16;
  const mh = window.innerHeight - tooltip.offsetHeight - 16;
  tooltip.style.left = Math.max(8, Math.min(x, mw)) + 'px';
  tooltip.style.top  = Math.max(8, Math.min(y, mh)) + 'px';
}

document.addEventListener('mousemove', e => {
  if (tooltip.style.display === 'block') positionTooltip(e);
});


// ══════════════════════════════════════════════════════════════
// UTILITIES
// ══════════════════════════════════════════════════════════════

function esc(str) {
  return String(str || '')
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#039;');
}

function trunc(str, len) {
  if (!str) return '';
  return str.length > len ? str.slice(0, len) + '…' : str;
}


// ══════════════════════════════════════════════════════════════
// UI: TABS
// ══════════════════════════════════════════════════════════════

const tabRendered = {};

function switchTab(name) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('active', p.id === `tab-${name}`));

  // Charts in hidden tabs may render with 0 width; (re)draw when tab becomes visible
  if (state.results && !tabRendered[name]) {
    tabRendered[name] = true;
    if (name === 'sections') renderSectionTab();
    if (name === 'overview') renderOverview();
  }
}


// ══════════════════════════════════════════════════════════════
// PRINTABLE TEST GENERATOR
// ══════════════════════════════════════════════════════════════

function generatePrintableTest(questions) {
  try {
    if (!questions || questions.length === 0) {
      throw new Error('No questions available. Please upload a test specification first.');
    }

    const questionsHtml = questions.map(q => {
      return `
        <li class="question">
          <p class="stem"><strong>${q.number}.</strong> ${q.question || q.section}</p>
          <ul class="options">
            <li>A. ${q.answers.A}</li>
            <li>B. ${q.answers.B}</li>
            <li>C. ${q.answers.C}</li>
            <li>D. ${q.answers.D}</li>
          </ul>
        </li>
      `;
    }).join('');

    const totalQuestions = questions.length;

    const html = `
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Student Assessment</title>
  <style>
    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }

    html, body {
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      line-height: 1.6;
      color: #000;
      background: #fff;
    }

    body {
      max-width: 720px;
      margin: 0 auto;
      padding: 20px;
    }

    .test-header {
      margin-bottom: 30px;
      border-bottom: 2px solid #000;
      padding-bottom: 15px;
    }

    h1 {
      font-size: 24px;
      margin-bottom: 15px;
      text-align: center;
    }

    .student-fields {
      display: flex;
      gap: 30px;
      margin-top: 15px;
      font-size: 14px;
    }

    .student-fields > div {
      flex: 1;
    }

    .student-fields input-line {
      border-bottom: 1px solid #000;
      width: 100%;
      display: inline-block;
    }

    .questions {
      list-style: none;
      padding: 0;
    }

    .question {
      page-break-inside: avoid;
      margin-bottom: 25px;
      break-inside: avoid;
    }

    .stem {
      font-size: 15px;
      margin-bottom: 10px;
      line-height: 1.5;
    }

    .options {
      list-style: none;
      padding-left: 0;
      margin-left: 20px;
    }

    .options li {
      margin-bottom: 8px;
      font-size: 14px;
    }

    .footer {
      margin-top: 40px;
      text-align: center;
      font-size: 12px;
      color: #666;
      border-top: 1px solid #ccc;
      padding-top: 20px;
    }

    @media print {
      body {
        max-width: 100%;
        margin: 0;
        padding: 1.5cm;
      }

      .test-header {
        margin-bottom: 1.5cm;
      }

      .question {
        margin-bottom: 1.5cm;
      }
    }
  </style>
</head>
<body>
  <div class="test-header">
    <h1>Student Assessment</h1>
    <div class="student-fields">
      <div>Name: <span style="border-bottom: 1px solid #000; display: inline-block; width: 180px;">&nbsp;</span></div>
      <div>Date: <span style="border-bottom: 1px solid #000; display: inline-block; width: 100px;">&nbsp;</span></div>
      <div>Score: <span style="border-bottom: 1px solid #000; display: inline-block; width: 40px;">&nbsp;</span> / ${totalQuestions}</div>
    </div>
  </div>

  <ol class="questions">
    ${questionsHtml}
  </ol>

  <p class="footer">Generated by Concept Inventory Analyser</p>
</body>
</html>
    `;

    // Open in a new tab
    const newTab = window.open('', '_blank');
    newTab.document.write(html);
    newTab.document.close();

  } catch (err) {
    // Show detailed error in browser console for debugging
    console.error('Printable test generation error:', err);
    alert('Error generating printable test:\n\n' + err.message);
  }
}


// ══════════════════════════════════════════════════════════════
// FILE UPLOAD HANDLERS
// ══════════════════════════════════════════════════════════════

let testSpecText   = null;
let testSpecIsJson = false;
let parsedTestSpec = null;
let answersCsvText = null;

function updateAnalyseBtn() {
  document.getElementById('btn-analyse').disabled = !(testSpecText && answersCsvText);
}

document.getElementById('input-test').addEventListener('change', function () {
  const file = this.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = e => {
    const content = e.target.result;
    const ext     = file.name.split('.').pop().toLowerCase();

    testSpecIsJson = (ext === 'json') ||
                     (ext !== 'csv' && content.trimStart().startsWith('['));

    testSpecText   = content;
    parsedTestSpec = null;

    document.getElementById('label-test').textContent   = file.name;
    document.getElementById('status-test').textContent  = '✓ ' + file.name + ' loaded';
    document.getElementById('status-test').className    = 'file-status status-ok';
    document.getElementById('card-test').classList.add('card-loaded');
    document.getElementById('btn-print-test').disabled  = false;
    updateAnalyseBtn();
  };
  reader.readAsText(file);
});

document.getElementById('input-answers').addEventListener('change', function () {
  const file = this.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = e => {
    answersCsvText = e.target.result;
    document.getElementById('label-answers').textContent  = file.name;
    document.getElementById('status-answers').textContent = '✓ ' + file.name + ' loaded';
    document.getElementById('status-answers').className   = 'file-status status-ok';
    document.getElementById('card-answers').classList.add('card-loaded');
    updateAnalyseBtn();
  };
  reader.readAsText(file);
});

document.getElementById('btn-analyse').addEventListener('click', () => {
  try {
    parsedTestSpec = parseTestSpec(testSpecText, testSpecIsJson);
    state.testSpec = parsedTestSpec;
    state.students = parseStudentAnswers(answersCsvText);

    if (state.testSpec.length === 0) throw new Error('No questions found in the test specification.');
    if (state.students.length  === 0) throw new Error('No students found in the student answers CSV.');

    computeAll();

    document.getElementById('section-upload').style.display    = 'none';
    document.getElementById('section-dashboard').style.display = 'block';
    document.getElementById('btn-new-analysis').style.display  = 'inline-flex';

    renderDashboard();
    switchTab('overview');

  } catch (err) {
    alert('Error: ' + err.message);
  }
});

document.getElementById('btn-new-analysis').addEventListener('click', () => {
  if (confirm('Start a new analysis? The current data will be cleared.')) location.reload();
});

document.getElementById('btn-print-test').addEventListener('click', () => {
  if (!parsedTestSpec) {
    try {
      parsedTestSpec = parseTestSpec(testSpecText, testSpecIsJson);
    } catch (err) {
      alert('Error reading test specification: ' + err.message);
      return;
    }
  }
  generatePrintableTest(parsedTestSpec);
});


// ══════════════════════════════════════════════════════════════
// TAB & CONTROL EVENTS
// ══════════════════════════════════════════════════════════════

document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => switchTab(btn.dataset.tab));
});

document.getElementById('register-sort').addEventListener('change', function () {
  renderRegisterHeatmap(this.value);
});

document.getElementById('student-select').addEventListener('change', function () {
  renderStudentReport(this.value);
});


// ══════════════════════════════════════════════════════════════
// AI PROMPT MODAL
// ══════════════════════════════════════════════════════════════

function openPromptModal() {
  document.getElementById('llm-prompt-text').textContent = LLM_PROMPT;
  document.getElementById('modal-ai-prompt').style.display = 'flex';
}

function closePromptModal() {
  document.getElementById('modal-ai-prompt').style.display = 'none';
}

document.getElementById('btn-ai-prompt').addEventListener('click', openPromptModal);
document.getElementById('link-format-guide').addEventListener('click', e => { e.preventDefault(); openPromptModal(); });
document.getElementById('btn-close-modal').addEventListener('click', closePromptModal);
document.getElementById('modal-ai-prompt').addEventListener('click', function (e) {
  if (e.target === this) closePromptModal();
});

document.getElementById('btn-copy-prompt').addEventListener('click', () => {
  navigator.clipboard.writeText(LLM_PROMPT).then(() => {
    const btn = document.getElementById('btn-copy-prompt');
    btn.textContent = 'Copied!';
    setTimeout(() => { btn.textContent = 'Copy to Clipboard'; }, 2000);
  }).catch(() => {
    // Fallback for environments without clipboard API
    const ta = document.createElement('textarea');
    ta.value = LLM_PROMPT;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    const btn = document.getElementById('btn-copy-prompt');
    btn.textContent = 'Copied!';
    setTimeout(() => { btn.textContent = 'Copy to Clipboard'; }, 2000);
  });
});
