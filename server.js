const express = require('express');
const Database = require('better-sqlite3');
const path = require('path');
const fs = require('fs');

const app = express();
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

if (!fs.existsSync('./data')) fs.mkdirSync('./data');
const db = new Database('./data/bolao.db');
db.pragma('journal_mode = WAL');

db.exec(`
  CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );
  CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    home_flag TEXT DEFAULT '',
    away_flag TEXT DEFAULT '',
    phase TEXT NOT NULL,
    group_name TEXT DEFAULT '',
    round_number INTEGER DEFAULT 1,
    match_time TEXT NOT NULL,
    home_score INTEGER,
    away_score INTEGER,
    is_finished INTEGER DEFAULT 0
  );
  CREATE TABLE IF NOT EXISTS bets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    match_id INTEGER NOT NULL,
    prediction TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, match_id)
  );
`);

const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || 'copa2026';

const PHASE_POINTS = { group: 5, pre_r32: 10, r16: 15, qf: 20, sf: 25, final: 40 };

function getResult(hs, as_) {
  if (hs > as_) return 'home';
  if (hs < as_) return 'away';
  return 'draw';
}

function getRoundDeadline(phase, round_number) {
  const row = db.prepare('SELECT MIN(match_time) as d FROM matches WHERE phase = ? AND round_number = ?').get(phase, round_number);
  return row?.d || null;
}

function canBet(matchId) {
  const match = db.prepare('SELECT * FROM matches WHERE id = ?').get(matchId);
  if (!match || match.is_finished) return false;
  const deadline = getRoundDeadline(match.phase, match.round_number);
  if (!deadline) return false;
  return new Date() < new Date(deadline);
}

function adminAuth(req, res, next) {
  if (req.headers['x-admin-password'] !== ADMIN_PASSWORD) return res.status(401).json({ error: 'Senha incorreta' });
  next();
}

// ── Users ──────────────────────────────────────────────────────────────────
app.post('/api/users', (req, res) => {
  const name = req.body?.name?.trim();
  if (!name || name.length < 2) return res.status(400).json({ error: 'Nome inválido (mínimo 2 caracteres)' });
  try {
    const existing = db.prepare('SELECT * FROM users WHERE LOWER(name) = LOWER(?)').get(name);
    if (existing) return res.json({ user: existing, isNew: false });
    const r = db.prepare('INSERT INTO users (name) VALUES (?)').run(name);
    res.json({ user: db.prepare('SELECT * FROM users WHERE id = ?').get(r.lastInsertRowid), isNew: true });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.get('/api/users', (req, res) => {
  res.json(db.prepare('SELECT id, name, created_at FROM users ORDER BY name').all());
});

app.delete('/api/users/:id', adminAuth, (req, res) => {
  db.prepare('DELETE FROM bets WHERE user_id = ?').run(req.params.id);
  db.prepare('DELETE FROM users WHERE id = ?').run(req.params.id);
  res.json({ success: true });
});

// ── Matches ────────────────────────────────────────────────────────────────
app.get('/api/matches', (req, res) => {
  const matches = db.prepare('SELECT * FROM matches ORDER BY match_time').all();
  const deadlineCache = {};
  matches.forEach(m => {
    const key = `${m.phase}_${m.round_number}`;
    if (!deadlineCache[key]) deadlineCache[key] = getRoundDeadline(m.phase, m.round_number);
    m.round_deadline = deadlineCache[key];
    m.betting_open = !!m.round_deadline && new Date() < new Date(m.round_deadline);
  });
  res.json(matches);
});

app.post('/api/matches', adminAuth, (req, res) => {
  const { home_team, away_team, home_flag, away_flag, phase, group_name, round_number, match_time } = req.body;
  if (!home_team || !away_team || !phase || !match_time) return res.status(400).json({ error: 'Campos obrigatórios faltando' });
  const r = db.prepare(
    'INSERT INTO matches (home_team, away_team, home_flag, away_flag, phase, group_name, round_number, match_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
  ).run(home_team, away_team, home_flag || '', away_flag || '', phase, group_name || '', round_number || 1, match_time);
  res.json(db.prepare('SELECT * FROM matches WHERE id = ?').get(r.lastInsertRowid));
});

app.put('/api/matches/:id', adminAuth, (req, res) => {
  const match = db.prepare('SELECT * FROM matches WHERE id = ?').get(req.params.id);
  if (!match) return res.status(404).json({ error: 'Partida não encontrada' });
  const allowed = ['home_team', 'away_team', 'home_flag', 'away_flag', 'phase', 'group_name', 'round_number', 'match_time', 'home_score', 'away_score', 'is_finished'];
  const updates = {};
  allowed.forEach(f => { if (req.body[f] !== undefined) updates[f] = req.body[f]; });
  if (!Object.keys(updates).length) return res.json(match);
  db.prepare(`UPDATE matches SET ${Object.keys(updates).map(f => `${f} = ?`).join(', ')} WHERE id = ?`).run(...Object.values(updates), req.params.id);
  res.json(db.prepare('SELECT * FROM matches WHERE id = ?').get(req.params.id));
});

app.delete('/api/matches/:id', adminAuth, (req, res) => {
  db.prepare('DELETE FROM bets WHERE match_id = ?').run(req.params.id);
  db.prepare('DELETE FROM matches WHERE id = ?').run(req.params.id);
  res.json({ success: true });
});

// Bulk import
app.post('/api/matches/bulk', adminAuth, (req, res) => {
  const { matches } = req.body;
  if (!Array.isArray(matches)) return res.status(400).json({ error: 'matches deve ser um array' });
  const insert = db.prepare('INSERT INTO matches (home_team, away_team, home_flag, away_flag, phase, group_name, round_number, match_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?)');
  const insertMany = db.transaction((rows) => rows.map(m => {
    const r = insert.run(m.home_team, m.away_team, m.home_flag || '', m.away_flag || '', m.phase, m.group_name || '', m.round_number || 1, m.match_time);
    return r.lastInsertRowid;
  }));
  const ids = insertMany(matches);
  res.json({ inserted: ids.length, ids });
});

// ── Bets ───────────────────────────────────────────────────────────────────
app.get('/api/bets', (req, res) => {
  const { user_id } = req.query;
  if (!user_id) return res.status(400).json({ error: 'user_id required' });
  res.json(db.prepare('SELECT * FROM bets WHERE user_id = ?').all(user_id));
});

app.get('/api/bets/round', (req, res) => {
  const { phase, round_number } = req.query;
  if (!phase || !round_number) return res.status(400).json({ error: 'phase e round_number required' });
  const bets = db.prepare(`
    SELECT b.*, u.name as user_name
    FROM bets b
    JOIN users u ON b.user_id = u.id
    JOIN matches m ON b.match_id = m.id
    WHERE m.phase = ? AND m.round_number = ?
    ORDER BY u.name
  `).all(phase, round_number);
  res.json(bets);
});

app.post('/api/bets', (req, res) => {
  const { user_id, match_id, prediction } = req.body;
  if (!user_id || !match_id || !prediction) return res.status(400).json({ error: 'Campos obrigatórios faltando' });
  if (!['home', 'draw', 'away'].includes(prediction)) return res.status(400).json({ error: 'Palpite inválido' });
  if (!canBet(match_id)) return res.status(403).json({ error: 'Prazo para apostas encerrado' });
  db.prepare('INSERT INTO bets (user_id, match_id, prediction) VALUES (?, ?, ?) ON CONFLICT(user_id, match_id) DO UPDATE SET prediction = excluded.prediction, created_at = CURRENT_TIMESTAMP').run(user_id, match_id, prediction);
  res.json(db.prepare('SELECT * FROM bets WHERE user_id = ? AND match_id = ?').get(user_id, match_id));
});

// Admin: insert bet bypassing deadline
app.post('/api/admin/bets', adminAuth, (req, res) => {
  const { user_id, match_id, prediction } = req.body;
  if (!user_id || !match_id || !prediction) return res.status(400).json({ error: 'Campos obrigatórios faltando' });
  if (!['home', 'draw', 'away'].includes(prediction)) return res.status(400).json({ error: 'Palpite inválido' });
  db.prepare('INSERT INTO bets (user_id, match_id, prediction) VALUES (?, ?, ?) ON CONFLICT(user_id, match_id) DO UPDATE SET prediction = excluded.prediction').run(user_id, match_id, prediction);
  res.json(db.prepare('SELECT * FROM bets WHERE user_id = ? AND match_id = ?').get(user_id, match_id));
});

// Admin: bulk bets for first round
app.post('/api/admin/bets/bulk', adminAuth, (req, res) => {
  const { bets } = req.body;
  if (!Array.isArray(bets)) return res.status(400).json({ error: 'bets deve ser um array' });
  const upsert = db.prepare('INSERT INTO bets (user_id, match_id, prediction) VALUES (?, ?, ?) ON CONFLICT(user_id, match_id) DO UPDATE SET prediction = excluded.prediction');
  const insertMany = db.transaction((rows) => rows.forEach(b => upsert.run(b.user_id, b.match_id, b.prediction)));
  insertMany(bets);
  res.json({ inserted: bets.length });
});

// ── Standings ──────────────────────────────────────────────────────────────
app.get('/api/standings', (req, res) => {
  const users = db.prepare('SELECT * FROM users').all();
  const finished = db.prepare('SELECT * FROM matches WHERE is_finished = 1').all();

  const standings = users.map(user => {
    const bets = db.prepare('SELECT * FROM bets WHERE user_id = ?').all(user.id);
    let points = 0, correct = 0, total = 0;
    const byPhase = {};

    bets.forEach(bet => {
      const match = finished.find(m => m.id === bet.match_id);
      if (!match) return;
      total++;
      if (bet.prediction === getResult(match.home_score, match.away_score)) {
        const pts = PHASE_POINTS[match.phase] || 0;
        points += pts;
        correct++;
        byPhase[match.phase] = (byPhase[match.phase] || 0) + pts;
      }
    });

    return { id: user.id, name: user.name, points, correct, total, accuracy: total > 0 ? Math.round(correct / total * 100) : 0, byPhase };
  });

  standings.sort((a, b) => b.points - a.points || b.correct - a.correct || a.name.localeCompare(b.name));
  res.json(standings);
});

// ── Group Tables ───────────────────────────────────────────────────────────
app.get('/api/groups', (req, res) => {
  const matches = db.prepare("SELECT * FROM matches WHERE phase = 'group'").all();
  const groups = {};

  matches.forEach(m => {
    const g = m.group_name || '?';
    if (!groups[g]) groups[g] = {};
    [[m.home_team, m.home_flag], [m.away_team, m.away_flag]].forEach(([team, flag]) => {
      if (!groups[g][team]) groups[g][team] = { team, flag, played: 0, won: 0, drawn: 0, lost: 0, gf: 0, ga: 0, gd: 0, points: 0 };
    });
    if (!m.is_finished || m.home_score === null || m.away_score === null) return;
    const h = groups[g][m.home_team], a = groups[g][m.away_team];
    h.played++; a.played++;
    h.gf += m.home_score; h.ga += m.away_score; h.gd = h.gf - h.ga;
    a.gf += m.away_score; a.ga += m.home_score; a.gd = a.gf - a.ga;
    if (m.home_score > m.away_score) { h.won++; h.points += 3; a.lost++; }
    else if (m.home_score < m.away_score) { a.won++; a.points += 3; h.lost++; }
    else { h.drawn++; h.points++; a.drawn++; a.points++; }
  });

  const result = {};
  Object.entries(groups).sort(([a], [b]) => a.localeCompare(b)).forEach(([g, teams]) => {
    result[g] = Object.values(teams).sort((a, b) => b.points - a.points || b.gd - a.gd || b.gf - a.gf || a.team.localeCompare(b.team));
  });
  res.json(result);
});

// ── Stats ──────────────────────────────────────────────────────────────────
app.get('/api/stats', (req, res) => {
  res.json({
    users: db.prepare('SELECT COUNT(*) as c FROM users').get().c,
    matches: db.prepare('SELECT COUNT(*) as c FROM matches').get().c,
    finished: db.prepare('SELECT COUNT(*) as c FROM matches WHERE is_finished=1').get().c,
    bets: db.prepare('SELECT COUNT(*) as c FROM bets').get().c,
  });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`\n🏆 Bolão Copa do Mundo 2026`);
  console.log(`   Acesse: http://localhost:${PORT}`);
  console.log(`   Senha admin: ${ADMIN_PASSWORD}\n`);
});
