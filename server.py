#!/usr/bin/env python3
"""Bolão Copa do Mundo 2026"""
import sqlite3, json, os, re
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, 'data', 'bolao.db')
PUBLIC_DIR = os.path.join(BASE, 'public')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'copa2026')
PORT = int(os.environ.get('PORT', 3000))

PHASE_POINTS = {'group': 5, 'pre_r32': 10, 'r16': 15, 'qf': 20, 'sf': 25, 'final': 40}
MIME = {'.html':'text/html; charset=utf-8','.css':'text/css','.js':'application/javascript','.json':'application/json','.png':'image/png','.ico':'image/x-icon','.svg':'image/svg+xml'}

# ── Database backend (SQLite local / PostgreSQL production) ───────────────────

_DATABASE_URL = os.environ.get('DATABASE_URL', '')
if _DATABASE_URL.startswith('postgres://'):
    _DATABASE_URL = _DATABASE_URL.replace('postgres://', 'postgresql://', 1)
USE_PG = bool(_DATABASE_URL)

SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    home_team TEXT NOT NULL, away_team TEXT NOT NULL,
    home_flag TEXT DEFAULT '', away_flag TEXT DEFAULT '',
    phase TEXT NOT NULL, group_name TEXT DEFAULT '',
    round_number INTEGER DEFAULT 1, match_time TEXT NOT NULL,
    home_score INTEGER, away_score INTEGER, is_finished INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS bets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL, match_id INTEGER NOT NULL,
    prediction TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, match_id)
);
"""

SCHEMA_PG = """
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS matches (
    id SERIAL PRIMARY KEY,
    home_team TEXT NOT NULL, away_team TEXT NOT NULL,
    home_flag TEXT DEFAULT '', away_flag TEXT DEFAULT '',
    phase TEXT NOT NULL, group_name TEXT DEFAULT '',
    round_number INTEGER DEFAULT 1, match_time TEXT NOT NULL,
    home_score INTEGER, away_score INTEGER, is_finished INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS bets (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL, match_id INTEGER NOT NULL,
    prediction TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, match_id)
);
"""

if USE_PG:
    import psycopg2, psycopg2.extras

    def _pg_conn():
        conn = psycopg2.connect(_DATABASE_URL)
        conn.autocommit = True
        return conn

    _pg = _pg_conn()

    def _pg_ensure():
        global _pg
        try:
            _pg.cursor().execute('SELECT 1')
        except Exception:
            _pg = _pg_conn()

    def _init_pg():
        _pg_ensure()
        with _pg.cursor() as cur:
            for stmt in SCHEMA_PG.split(';'):
                s = stmt.strip()
                if s:
                    cur.execute(s)
    _init_pg()

    def _adapt(sql):
        return sql.replace('?', '%s')

    def q(sql, params=()):
        _pg_ensure()
        with _pg.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(_adapt(sql), params)
            return [dict(r) for r in cur.fetchall()]

    def q1(sql, params=()):
        _pg_ensure()
        with _pg.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(_adapt(sql), params)
            r = cur.fetchone()
            return dict(r) if r else None

    def run(sql, params=()):
        _pg_ensure()
        with _pg.cursor() as cur:
            cur.execute(_adapt(sql), params)
            return cur

else:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    _db = sqlite3.connect(DB_PATH, check_same_thread=False)
    _db.row_factory = sqlite3.Row
    _db.execute("PRAGMA journal_mode=WAL")
    _db.executescript(SCHEMA_SQLITE)
    _db.commit()

    def q(sql, params=()):
        return [dict(r) for r in _db.execute(sql, params).fetchall()]

    def q1(sql, params=()):
        r = _db.execute(sql, params).fetchone()
        return dict(r) if r else None

    def run(sql, params=()):
        c = _db.execute(sql, params)
        _db.commit()
        return c

def get_result(hs, as_):
    if hs > as_: return 'home'
    if hs < as_: return 'away'
    return 'draw'

def now_utc():
    return datetime.utcnow().strftime('%Y-%m-%dT%H:%M')

def round_deadline(phase, rnum):
    r = q1('SELECT MIN(match_time) as d FROM matches WHERE phase=? AND round_number=?', (phase, rnum))
    return r['d'] if r else None

def prev_round_complete(phase, rnum):
    if rnum <= 1:
        return True
    row = q1('SELECT COUNT(*) as total, SUM(is_finished) as done FROM matches WHERE phase=? AND round_number=?', (phase, rnum - 1))
    total, done = row['total'] or 0, row['done'] or 0
    return total > 0 and total == done

def round_status(phase, rnum):
    dl = round_deadline(phase, rnum)
    prev_ok = prev_round_complete(phase, rnum)
    now = now_utc()
    deadline_passed = bool(dl) and now >= dl[:16]
    if not prev_ok:
        row = q1('SELECT COUNT(*) as total, SUM(is_finished) as done FROM matches WHERE phase=? AND round_number=?', (phase, rnum - 1))
        remaining = (row['total'] or 0) - (row['done'] or 0)
        return {'open': False, 'reason': 'waiting_prev', 'prev_remaining': remaining, 'deadline': dl, 'deadline_passed': False}
    if deadline_passed:
        return {'open': False, 'reason': 'deadline_passed', 'deadline': dl, 'deadline_passed': True, 'prev_remaining': 0}
    return {'open': True, 'reason': 'open', 'deadline': dl, 'deadline_passed': False, 'prev_remaining': 0}

def betting_open(match_id):
    m = q1('SELECT * FROM matches WHERE id=?', (match_id,))
    if not m or m['is_finished']:
        return False
    if not prev_round_complete(m['phase'], m['round_number']):
        return False
    # Cada jogo trava no SEU próprio horário
    return bool(m['match_time']) and now_utc() < m['match_time'][:16]

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def body(self):
        n = int(self.headers.get('Content-Length', 0))
        return json.loads(self.rfile.read(n)) if n else {}

    def is_admin(self):
        return self.headers.get('x-admin-password') == ADMIN_PASSWORD

    def static(self, path):
        if path == '/': path = '/index.html'
        fp = PUBLIC_DIR + path.split('?')[0]
        if not os.path.isfile(fp):
            self.send_response(404); self.end_headers(); return
        ext = os.path.splitext(fp)[1]
        data = open(fp, 'rb').read()
        self.send_response(200)
        self.send_header('Content-Type', MIME.get(ext, 'application/octet-stream'))
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def enrich_matches(self, matches):
        cache_prev = {}
        now = now_utc()
        for m in matches:
            key = f"{m['phase']}_{m['round_number']}"
            if key not in cache_prev:
                rnum = m['round_number']
                if rnum <= 1:
                    cache_prev[key] = {'prev_ok': True, 'prev_remaining': 0}
                else:
                    row = q1('SELECT COUNT(*) as total, SUM(is_finished) as done FROM matches WHERE phase=? AND round_number=?', (m['phase'], rnum - 1))
                    total, done = row['total'] or 0, row['done'] or 0
                    cache_prev[key] = {'prev_ok': total > 0 and total == done, 'prev_remaining': total - done}
            prev = cache_prev[key]
            match_started = bool(m['match_time']) and now >= m['match_time'][:16]
            m['round_deadline'] = m['match_time']  # cada jogo tem seu próprio prazo
            m['round_prev_remaining'] = prev['prev_remaining']
            if not prev['prev_ok']:
                m['round_reason'] = 'waiting_prev'
                m['betting_open'] = False
            elif match_started or m['is_finished']:
                m['round_reason'] = 'deadline_passed'
                m['betting_open'] = False
            else:
                m['round_reason'] = 'open'
                m['betting_open'] = True
        return matches

    # ── GET ───────────────────────────────────────────────────────────────
    def do_GET(self):
        p = urlparse(self.path)
        path, qs = p.path, parse_qs(p.query)

        if path == '/api/users':
            self.send_json(q('SELECT id,name,created_at FROM users ORDER BY name'))

        elif path == '/api/matches':
            self.send_json(self.enrich_matches(q('SELECT * FROM matches ORDER BY match_time')))

        elif path == '/api/bets':
            uid = qs.get('user_id', [None])[0]
            if not uid: self.send_json({'error':'user_id required'},400); return
            self.send_json(q('SELECT * FROM bets WHERE user_id=?', (uid,)))

        elif path == '/api/bets/round':
            phase = qs.get('phase',[None])[0]; rnum = qs.get('round_number',[None])[0]
            if not phase or not rnum: self.send_json({'error':'phase e round_number required'},400); return
            self.send_json(q('''
                SELECT b.*, u.name as user_name FROM bets b
                JOIN users u ON b.user_id=u.id
                JOIN matches m ON b.match_id=m.id
                WHERE m.phase=? AND m.round_number=? ORDER BY u.name
            ''', (phase, rnum)))

        elif path == '/api/standings':
            users = q('SELECT * FROM users')
            finished = {m['id']: m for m in q('SELECT * FROM matches WHERE is_finished=1')}
            standings = []
            for u in users:
                bets = q('SELECT * FROM bets WHERE user_id=?', (u['id'],))
                pts = correct = total = 0
                by_phase = {}
                for bet in bets:
                    m = finished.get(bet['match_id'])
                    if not m: continue
                    total += 1
                    if bet['prediction'] == get_result(m['home_score'], m['away_score']):
                        p_ = PHASE_POINTS.get(m['phase'], 0)
                        pts += p_; correct += 1
                        by_phase[m['phase']] = by_phase.get(m['phase'], 0) + p_
                standings.append({'id':u['id'],'name':u['name'],'points':pts,'correct':correct,'total':total,
                    'accuracy': round(correct/total*100) if total else 0,'byPhase':by_phase})
            standings.sort(key=lambda x: (-x['points'], -x['correct'], x['name']))
            self.send_json(standings)

        elif path == '/api/groups':
            matches = q("SELECT * FROM matches WHERE phase='group'")
            groups = {}
            for m in matches:
                g = m['group_name'] or '?'
                if g not in groups: groups[g] = {}
                for team, flag in [(m['home_team'],m['home_flag']),(m['away_team'],m['away_flag'])]:
                    if team not in groups[g]:
                        groups[g][team] = {'team':team,'flag':flag,'played':0,'won':0,'drawn':0,'lost':0,'gf':0,'ga':0,'gd':0,'points':0}
                if not m['is_finished'] or m['home_score'] is None or m['away_score'] is None: continue
                hs, as_ = m['home_score'], m['away_score']
                h, a = groups[g][m['home_team']], groups[g][m['away_team']]
                h['played'] += 1; a['played'] += 1
                h['gf'] += hs; h['ga'] += as_; h['gd'] = h['gf'] - h['ga']
                a['gf'] += as_; a['ga'] += hs; a['gd'] = a['gf'] - a['ga']
                if hs > as_:
                    h['won'] += 1; h['points'] += 3; a['lost'] += 1
                elif hs < as_:
                    a['won'] += 1; a['points'] += 3; h['lost'] += 1
                else:
                    h['drawn'] += 1; h['points'] += 1; a['drawn'] += 1; a['points'] += 1
            result = {}
            for g in sorted(groups):
                result[g] = sorted(groups[g].values(), key=lambda t: (-t['points'],-t['gd'],-t['gf'],t['team']))
            self.send_json(result)

        elif path == '/api/stats':
            if not self.is_admin(): self.send_json({'error':'Não autorizado'},401); return
            self.send_json({
                'users':    q1('SELECT COUNT(*) as c FROM users')['c'],
                'matches':  q1('SELECT COUNT(*) as c FROM matches')['c'],
                'finished': q1('SELECT COUNT(*) as c FROM matches WHERE is_finished=1')['c'],
                'bets':     q1('SELECT COUNT(*) as c FROM bets')['c'],
            })

        else:
            self.static(path)

    # ── POST ──────────────────────────────────────────────────────────────
    def do_POST(self):
        path = urlparse(self.path).path
        b = self.body()

        if path == '/api/users':
            name = (b.get('name') or '').strip()
            if len(name) < 2: self.send_json({'error':'Nome inválido (mínimo 2 caracteres)'},400); return
            try:
                existing = q1('SELECT * FROM users WHERE LOWER(name)=LOWER(?)', (name,))
                if existing: self.send_json({'user':existing,'isNew':False}); return
                run('INSERT INTO users (name) VALUES (?)', (name,))
                user = q1('SELECT * FROM users WHERE LOWER(name)=LOWER(?)', (name,))
                self.send_json({'user':user,'isNew':True})
            except Exception as e: self.send_json({'error':str(e)},500)

        elif path == '/api/matches':
            if not self.is_admin(): self.send_json({'error':'Não autorizado'},401); return
            if not b.get('home_team') or not b.get('away_team') or not b.get('phase') or not b.get('match_time'):
                self.send_json({'error':'Campos obrigatórios faltando'},400); return
            try:
                run('INSERT INTO matches (home_team,away_team,home_flag,away_flag,phase,group_name,round_number,match_time) VALUES (?,?,?,?,?,?,?,?)',
                    (b['home_team'],b['away_team'],b.get('home_flag',''),b.get('away_flag',''),b['phase'],b.get('group_name',''),b.get('round_number',1),b['match_time']))
                match = q1('SELECT * FROM matches ORDER BY id DESC LIMIT 1')
                self.send_json(match)
            except Exception as e: self.send_json({'error':str(e)},500)

        elif path == '/api/matches/bulk':
            if not self.is_admin(): self.send_json({'error':'Não autorizado'},401); return
            matches = b.get('matches',[])
            if not isinstance(matches,list): self.send_json({'error':'matches deve ser array'},400); return
            try:
                for m in matches:
                    run('INSERT INTO matches (home_team,away_team,home_flag,away_flag,phase,group_name,round_number,match_time) VALUES (?,?,?,?,?,?,?,?)',
                        (m['home_team'],m['away_team'],m.get('home_flag',''),m.get('away_flag',''),m['phase'],m.get('group_name',''),m.get('round_number',1),m['match_time']))
                self.send_json({'inserted':len(matches)})
            except Exception as e: self.send_json({'error':str(e)},500)

        elif path == '/api/bets':
            uid, mid, pred = b.get('user_id'), b.get('match_id'), b.get('prediction')
            if not uid or not mid or not pred: self.send_json({'error':'Campos obrigatórios faltando'},400); return
            if pred not in ('home','draw','away'): self.send_json({'error':'Palpite inválido'},400); return
            if not betting_open(mid): self.send_json({'error':'Prazo para apostas encerrado'},403); return
            run('INSERT INTO bets (user_id,match_id,prediction) VALUES (?,?,?) ON CONFLICT(user_id,match_id) DO UPDATE SET prediction=excluded.prediction,created_at=CURRENT_TIMESTAMP',
                (uid, mid, pred))
            self.send_json(q1('SELECT * FROM bets WHERE user_id=? AND match_id=?', (uid, mid)))

        elif path == '/api/admin/bets':
            if not self.is_admin(): self.send_json({'error':'Não autorizado'},401); return
            uid, mid, pred = b.get('user_id'), b.get('match_id'), b.get('prediction')
            if not uid or not mid or not pred: self.send_json({'error':'Campos obrigatórios faltando'},400); return
            if pred not in ('home','draw','away'): self.send_json({'error':'Palpite inválido'},400); return
            run('INSERT INTO bets (user_id,match_id,prediction) VALUES (?,?,?) ON CONFLICT(user_id,match_id) DO UPDATE SET prediction=excluded.prediction',
                (uid, mid, pred))
            self.send_json(q1('SELECT * FROM bets WHERE user_id=? AND match_id=?', (uid, mid)))

        elif path == '/api/admin/bets/bulk':
            if not self.is_admin(): self.send_json({'error':'Não autorizado'},401); return
            bets = b.get('bets',[])
            for bet in bets:
                run('INSERT INTO bets (user_id,match_id,prediction) VALUES (?,?,?) ON CONFLICT(user_id,match_id) DO UPDATE SET prediction=excluded.prediction',
                    (bet['user_id'], bet['match_id'], bet['prediction']))
            self.send_json({'inserted':len(bets)})

        else:
            self.send_json({'error':'Not found'},404)

    # ── PUT ───────────────────────────────────────────────────────────────
    def do_PUT(self):
        path = urlparse(self.path).path
        b = self.body()
        m = re.match(r'^/api/matches/(\d+)$', path)
        if m:
            if not self.is_admin(): self.send_json({'error':'Não autorizado'},401); return
            mid = m.group(1)
            match = q1('SELECT * FROM matches WHERE id=?', (mid,))
            if not match: self.send_json({'error':'Partida não encontrada'},404); return
            allowed = ['home_team','away_team','home_flag','away_flag','phase','group_name','round_number','match_time','home_score','away_score','is_finished']
            updates = {k:b[k] for k in allowed if k in b}
            if updates:
                run(f"UPDATE matches SET {', '.join(k+'=?' for k in updates)} WHERE id=?", (*updates.values(), mid))
            self.send_json(q1('SELECT * FROM matches WHERE id=?', (mid,))); return
        self.send_json({'error':'Not found'},404)

    # ── DELETE ────────────────────────────────────────────────────────────
    def do_DELETE(self):
        path = urlparse(self.path).path
        m = re.match(r'^/api/matches/(\d+)$', path)
        if m:
            if not self.is_admin(): self.send_json({'error':'Não autorizado'},401); return
            run('DELETE FROM bets WHERE match_id=?', (m.group(1),))
            run('DELETE FROM matches WHERE id=?', (m.group(1),))
            self.send_json({'success':True}); return
        m = re.match(r'^/api/users/(\d+)$', path)
        if m:
            if not self.is_admin(): self.send_json({'error':'Não autorizado'},401); return
            run('DELETE FROM bets WHERE user_id=?', (m.group(1),))
            run('DELETE FROM users WHERE id=?', (m.group(1),))
            self.send_json({'success':True}); return
        self.send_json({'error':'Not found'},404)

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', PORT), H)
    print(f'\n🏆 Bolão Copa do Mundo 2026')
    print(f'   Acesse: http://localhost:{PORT}')
    print(f'   Senha admin: {ADMIN_PASSWORD}\n')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n👋 Servidor encerrado.')
