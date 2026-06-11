#!/usr/bin/env python3
"""Insert first-round bets for 7 participants into the bolão API."""

import json
import sys
import urllib.request
import urllib.error

BASE_URL = "http://localhost:3000"
ADMIN_PASSWORD = "copa2026"

PARTICIPANTS = ["Brenno", "Igor", "Thyago", "Leandro", "Papai", "Caio", "Obina"]

BETS = {
    ('México', 'África'):       {'Brenno':'draw','Igor':'home','Thyago':'home','Leandro':'home','Papai':'home','Caio':'home','Obina':'home'},
    ('Coreia', 'Tcheca'):       {'Brenno':'away','Igor':'draw','Thyago':'home','Leandro':'home','Papai':'draw','Caio':'draw','Obina':'draw'},
    ('Canadá', 'Bósnia'):       {'Brenno':'away','Igor':'home','Thyago':'home','Leandro':'home','Papai':'home','Caio':'home','Obina':'draw'},
    ('Catar', 'Suíça'):         {'Brenno':'away','Igor':'away','Thyago':'away','Leandro':'away','Papai':'away','Caio':'away','Obina':'away'},
    ('Brasil', 'Marrocos'):     {'Brenno':'draw','Igor':'home','Thyago':'home','Leandro':'home','Papai':'home','Caio':'home','Obina':'home'},
    ('Haiti', 'Escócia'):       {'Brenno':'away','Igor':'away','Thyago':'away','Leandro':'draw','Papai':'away','Caio':'away','Obina':'away'},
    ('Estados', 'Paraguai'):    {'Brenno':'away','Igor':'draw','Thyago':'draw','Leandro':'away','Papai':'home','Caio':'home','Obina':'draw'},
    ('Austrália', 'Turquia'):   {'Brenno':'away','Igor':'away','Thyago':'away','Leandro':'draw','Papai':'draw','Caio':'draw','Obina':'away'},
    ('Alemanha', 'Curaçao'):    {'Brenno':'home','Igor':'home','Thyago':'home','Leandro':'home','Papai':'home','Caio':'home','Obina':'home'},
    ('Holanda', 'Japão'):       {'Brenno':'home','Igor':'draw','Thyago':'draw','Leandro':'away','Papai':'home','Caio':'home','Obina':'draw'},
    ('Costa', 'Equador'):       {'Brenno':'away','Igor':'away','Thyago':'draw','Leandro':'away','Papai':'away','Caio':'away','Obina':'home'},
    ('Suécia', 'Tunísia'):      {'Brenno':'home','Igor':'home','Thyago':'draw','Leandro':'home','Papai':'home','Caio':'home','Obina':'away'},
    ('Espanha', 'Cabo'):        {'Brenno':'home','Igor':'home','Thyago':'home','Leandro':'home','Papai':'home','Caio':'home','Obina':'home'},
    ('Bélgica', 'Egito'):       {'Brenno':'home','Igor':'home','Thyago':'home','Leandro':'home','Papai':'home','Caio':'home','Obina':'home'},
    ('Arábia', 'Uruguai'):      {'Brenno':'away','Igor':'away','Thyago':'draw','Leandro':'away','Papai':'away','Caio':'away','Obina':'away'},
    ('Irã', 'Nova'):            {'Brenno':'away','Igor':'draw','Thyago':'draw','Leandro':'draw','Papai':'draw','Caio':'draw','Obina':'draw'},
    ('França', 'Senegal'):      {'Brenno':'home','Igor':'home','Thyago':'home','Leandro':'home','Papai':'home','Caio':'home','Obina':'home'},
    ('Iraque', 'Noruega'):      {'Brenno':'away','Igor':'away','Thyago':'away','Leandro':'away','Papai':'away','Caio':'away','Obina':'away'},
    ('Argentina', 'Argélia'):   {'Brenno':'home','Igor':'home','Thyago':'home','Leandro':'home','Papai':'home','Caio':'home','Obina':'home'},
    ('Áustria', 'Jordânia'):    {'Brenno':'home','Igor':'home','Thyago':'home','Leandro':'draw','Papai':'home','Caio':'home','Obina':'home'},
    ('Portugal', 'Congo'):      {'Brenno':'home','Igor':'home','Thyago':'home','Leandro':'home','Papai':'home','Caio':'home','Obina':'home'},
    ('Uzbequistão', 'Colômbia'):{'Brenno':'away','Igor':'away','Thyago':'away','Leandro':'away','Papai':'away','Caio':'away','Obina':'draw'},
    ('Inglaterra', 'Croácia'):  {'Brenno':'home','Igor':'home','Thyago':'draw','Leandro':'draw','Papai':'home','Caio':'home','Obina':'home'},
    ('Gana', 'Panamá'):         {'Brenno':'home','Igor':'home','Thyago':'home','Leandro':'home','Papai':'draw','Caio':'draw','Obina':'home'},
}

# Name normalization: bets text name → possible DB substrings
# "Holanda" in bets = "Países Baixos" in DB
# "Congo RD" in DB = "Congo" in bets
HOME_KEYWORD_ALIASES = {
    'Holanda': ['Países', 'Holanda'],
}


def api_request(method, path, data=None, headers=None):
    url = BASE_URL + path
    body = json.dumps(data).encode('utf-8') if data is not None else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header('Content-Type', 'application/json')
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode('utf-8'))
        except Exception:
            body = {}
        return e.code, body


def create_users():
    print("=== Creating users ===")
    user_ids = {}
    for name in PARTICIPANTS:
        status, resp = api_request('POST', '/api/users', {'name': name})
        if status in (200, 201):
            uid = resp.get('id') or resp.get('user', {}).get('id')
            user_ids[name] = uid
            print(f"  Created {name}: id={uid}")
        elif status == 409 or (status == 400 and 'exist' in str(resp).lower()):
            # Already exists — fetch user list to get id
            print(f"  {name} already exists, fetching id...")
            s2, users = api_request('GET', '/api/users')
            if s2 == 200:
                for u in (users if isinstance(users, list) else users.get('users', [])):
                    if u.get('name') == name:
                        user_ids[name] = u['id']
                        print(f"    Found {name}: id={u['id']}")
                        break
        else:
            print(f"  WARNING: Could not create {name}: {status} {resp}")
    return user_ids


def fetch_matches():
    print("\n=== Fetching matches ===")
    status, resp = api_request('GET', '/api/matches')
    if status != 200:
        print(f"ERROR fetching matches: {status} {resp}")
        sys.exit(1)
    matches = resp if isinstance(resp, list) else resp.get('matches', [])
    print(f"  Got {len(matches)} matches total")
    return matches


def build_match_lookup(matches):
    """Build a lookup: (home_keyword, away_keyword) → match_id."""
    lookup = {}
    for (home_kw, away_kw), players in BETS.items():
        # Determine actual search keywords (handle aliases)
        home_search_options = HOME_KEYWORD_ALIASES.get(home_kw, [home_kw])
        found = None
        for m in matches:
            home = m.get('home_team', '')
            away = m.get('away_team', '')
            home_match = any(opt in home for opt in home_search_options)
            away_match = away_kw in away
            if home_match and away_match:
                found = m
                break
        if found:
            lookup[(home_kw, away_kw)] = found['id']
            print(f"  Matched ({home_kw} vs {away_kw}) → id={found['id']} [{found['home_team']} vs {found['away_team']}]")
        else:
            print(f"  WARNING: No match found for ({home_kw} vs {away_kw})")
            # Print candidates for debugging
            for m in matches:
                if any(opt in m.get('home_team','') for opt in home_search_options):
                    print(f"    Candidate home match: {m['home_team']} vs {m['away_team']}")
    return lookup


def insert_bets(user_ids, match_lookup):
    print("\n=== Inserting bets ===")
    total = 0
    errors = 0
    admin_headers = {'x-admin-password': ADMIN_PASSWORD}

    for (home_kw, away_kw), players in BETS.items():
        match_id = match_lookup.get((home_kw, away_kw))
        if match_id is None:
            print(f"  SKIP: No match id for ({home_kw} vs {away_kw})")
            errors += 1
            continue
        for player, prediction in players.items():
            user_id = user_ids.get(player)
            if user_id is None:
                print(f"  SKIP: No user id for {player}")
                errors += 1
                continue
            payload = {
                'user_id': user_id,
                'match_id': match_id,
                'prediction': prediction,
            }
            status, resp = api_request('POST', '/api/admin/bets', payload, admin_headers)
            if status in (200, 201):
                total += 1
            elif status == 409 or (status == 400 and ('already' in str(resp).lower() or 'exist' in str(resp).lower())):
                print(f"  Already exists: {player} on match {match_id} ({home_kw} vs {away_kw}) — skipping")
                total += 1
            else:
                print(f"  ERROR: {player} match={match_id} ({home_kw} vs {away_kw}): {status} {resp}")
                errors += 1

    print(f"\n=== Summary ===")
    print(f"  Bets inserted/confirmed: {total}")
    print(f"  Errors/skips: {errors}")
    expected = len(BETS) * len(PARTICIPANTS)
    print(f"  Expected total: {expected}")


def main():
    user_ids = create_users()
    matches = fetch_matches()
    match_lookup = build_match_lookup(matches)
    insert_bets(user_ids, match_lookup)


if __name__ == '__main__':
    main()
