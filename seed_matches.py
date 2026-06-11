#!/usr/bin/env python3
"""
Importa todos os 72 jogos da fase de grupos da Copa 2026.
Horários em UTC (Brasília = UTC-3, então UTC = BRT + 3h).
Fonte: ESPN Brasil / FIFA / verificado com usuário (México x África do Sul = 16h BRT → 19h UTC).
"""
import json, urllib.request, sys

BASE = 'http://localhost:3000'
ADMIN_PWD = 'copa2026'

# Todos os horários em UTC. Para converter: UTC = BRT + 3
# Exemplos: 16h BRT = 19h UTC | 19h BRT = 22h UTC | 22h BRT = 01h UTC(+1dia)
#           00h BRT = 03h UTC(+1dia) | 02h BRT = 05h UTC(+1dia) | 15h BRT = 18h UTC

MATCHES = [
    # ════════════════════════════════════════════════════════════════════════
    # RODADA 1  (24 jogos — prazo: antes de México x África do Sul, 16h BRT 11/jun)
    # ════════════════════════════════════════════════════════════════════════
    # ── Quinta 11/jun ──────────────────────────────────────────────────────
    {"g":"A","r":1,"brt":"11/06 16:00","t":"2026-06-11T19:00","h":"México",           "hf":"🇲🇽","a":"África do Sul",       "af":"🇿🇦"},
    {"g":"A","r":1,"brt":"11/06 23:00","t":"2026-06-12T02:00","h":"Coreia do Sul",    "hf":"🇰🇷","a":"República Tcheca",    "af":"🇨🇿"},
    # ── Sexta 12/jun ───────────────────────────────────────────────────────
    {"g":"B","r":1,"brt":"12/06 16:00","t":"2026-06-12T19:00","h":"Canadá",           "hf":"🇨🇦","a":"Bósnia e Herzegovina","af":"🇧🇦"},
    {"g":"D","r":1,"brt":"12/06 22:00","t":"2026-06-13T01:00","h":"Estados Unidos",   "hf":"🇺🇸","a":"Paraguai",            "af":"🇵🇾"},
    # ── Sábado 13/jun ──────────────────────────────────────────────────────
    {"g":"B","r":1,"brt":"13/06 16:00","t":"2026-06-13T19:00","h":"Catar",            "hf":"🇶🇦","a":"Suíça",               "af":"🇨🇭"},
    {"g":"C","r":1,"brt":"13/06 19:00","t":"2026-06-13T22:00","h":"Brasil",           "hf":"🇧🇷","a":"Marrocos",            "af":"🇲🇦"},
    {"g":"C","r":1,"brt":"13/06 22:00","t":"2026-06-14T01:00","h":"Haiti",            "hf":"🇭🇹","a":"Escócia",             "af":"🏴󠁧󠁢󠁳󠁣󠁴󠁿"},
    {"g":"D","r":1,"brt":"14/06 02:00","t":"2026-06-14T05:00","h":"Austrália",        "hf":"🇦🇺","a":"Turquia",             "af":"🇹🇷"},
    # ── Domingo 14/jun ─────────────────────────────────────────────────────
    {"g":"E","r":1,"brt":"14/06 15:00","t":"2026-06-14T18:00","h":"Alemanha",         "hf":"🇩🇪","a":"Curaçao",             "af":"🇨🇼"},
    {"g":"F","r":1,"brt":"14/06 18:00","t":"2026-06-14T21:00","h":"Holanda",          "hf":"🇳🇱","a":"Japão",               "af":"🇯🇵"},
    {"g":"E","r":1,"brt":"14/06 21:00","t":"2026-06-15T00:00","h":"Costa do Marfim",  "hf":"🇨🇮","a":"Equador",             "af":"🇪🇨"},
    {"g":"F","r":1,"brt":"15/06 00:00","t":"2026-06-15T03:00","h":"Suécia",           "hf":"🇸🇪","a":"Tunísia",             "af":"🇹🇳"},
    # ── Segunda 15/jun ─────────────────────────────────────────────────────
    {"g":"H","r":1,"brt":"15/06 15:00","t":"2026-06-15T18:00","h":"Espanha",          "hf":"🇪🇸","a":"Cabo Verde",          "af":"🇨🇻"},
    {"g":"G","r":1,"brt":"15/06 20:00","t":"2026-06-15T23:00","h":"Bélgica",          "hf":"🇧🇪","a":"Egito",               "af":"🇪🇬"},
    {"g":"H","r":1,"brt":"15/06 20:00","t":"2026-06-15T23:00","h":"Arábia Saudita",   "hf":"🇸🇦","a":"Uruguai",             "af":"🇺🇾"},
    {"g":"G","r":1,"brt":"16/06 02:00","t":"2026-06-16T05:00","h":"Irã",              "hf":"🇮🇷","a":"Nova Zelândia",       "af":"🇳🇿"},
    # ── Terça 16/jun ───────────────────────────────────────────────────────
    {"g":"I","r":1,"brt":"16/06 17:00","t":"2026-06-16T20:00","h":"França",           "hf":"🇫🇷","a":"Senegal",             "af":"🇸🇳"},
    {"g":"I","r":1,"brt":"16/06 20:00","t":"2026-06-16T23:00","h":"Iraque",           "hf":"🇮🇶","a":"Noruega",             "af":"🇳🇴"},
    {"g":"J","r":1,"brt":"16/06 23:00","t":"2026-06-17T02:00","h":"Argentina",        "hf":"🇦🇷","a":"Argélia",             "af":"🇩🇿"},
    {"g":"J","r":1,"brt":"17/06 02:00","t":"2026-06-17T05:00","h":"Áustria",          "hf":"🇦🇹","a":"Jordânia",            "af":"🇯🇴"},
    # ── Quarta 17/jun ──────────────────────────────────────────────────────
    {"g":"K","r":1,"brt":"17/06 15:00","t":"2026-06-17T18:00","h":"Portugal",         "hf":"🇵🇹","a":"Congo RD",            "af":"🇨🇩"},
    {"g":"L","r":1,"brt":"17/06 18:00","t":"2026-06-17T21:00","h":"Inglaterra",       "hf":"🏴󠁧󠁢󠁥󠁮󠁧󠁿","a":"Croácia",             "af":"🇭🇷"},
    {"g":"L","r":1,"brt":"17/06 21:00","t":"2026-06-18T00:00","h":"Gana",             "hf":"🇬🇭","a":"Panamá",              "af":"🇵🇦"},
    {"g":"K","r":1,"brt":"18/06 00:00","t":"2026-06-18T03:00","h":"Uzbequistão",      "hf":"🇺🇿","a":"Colômbia",            "af":"🇨🇴"},

    # ════════════════════════════════════════════════════════════════════════
    # RODADA 2  (24 jogos — abre após FIM da Rodada 1)
    # ════════════════════════════════════════════════════════════════════════
    # ── Quinta 18/jun ──────────────────────────────────────────────────────
    {"g":"A","r":2,"brt":"18/06 15:00","t":"2026-06-18T18:00","h":"República Tcheca", "hf":"🇨🇿","a":"África do Sul",       "af":"🇿🇦"},
    {"g":"B","r":2,"brt":"18/06 17:00","t":"2026-06-18T20:00","h":"Suíça",            "hf":"🇨🇭","a":"Bósnia e Herzegovina","af":"🇧🇦"},
    {"g":"B","r":2,"brt":"18/06 20:00","t":"2026-06-18T23:00","h":"Canadá",           "hf":"🇨🇦","a":"Catar",               "af":"🇶🇦"},
    {"g":"A","r":2,"brt":"19/06 01:00","t":"2026-06-19T04:00","h":"México",           "hf":"🇲🇽","a":"Coreia do Sul",       "af":"🇰🇷"},
    # ── Sexta 19/jun ───────────────────────────────────────────────────────
    {"g":"D","r":2,"brt":"19/06 17:00","t":"2026-06-19T20:00","h":"Estados Unidos",   "hf":"🇺🇸","a":"Austrália",           "af":"🇦🇺"},
    {"g":"C","r":2,"brt":"19/06 20:00","t":"2026-06-19T23:00","h":"Escócia",          "hf":"🏴󠁧󠁢󠁳󠁣󠁴󠁿","a":"Marrocos",            "af":"🇲🇦"},
    {"g":"C","r":2,"brt":"19/06 23:00","t":"2026-06-20T02:00","h":"Brasil",           "hf":"🇧🇷","a":"Haiti",               "af":"🇭🇹"},
    {"g":"D","r":2,"brt":"20/06 02:00","t":"2026-06-20T05:00","h":"Turquia",          "hf":"🇹🇷","a":"Paraguai",            "af":"🇵🇾"},
    # ── Sábado 20/jun ──────────────────────────────────────────────────────
    {"g":"F","r":2,"brt":"20/06 15:00","t":"2026-06-20T18:00","h":"Holanda",          "hf":"🇳🇱","a":"Suécia",              "af":"🇸🇪"},
    {"g":"E","r":2,"brt":"20/06 20:00","t":"2026-06-20T23:00","h":"Alemanha",         "hf":"🇩🇪","a":"Costa do Marfim",     "af":"🇨🇮"},
    {"g":"E","r":2,"brt":"20/06 22:00","t":"2026-06-21T01:00","h":"Equador",          "hf":"🇪🇨","a":"Curaçao",             "af":"🇨🇼"},
    {"g":"F","r":2,"brt":"21/06 00:00","t":"2026-06-21T03:00","h":"Tunísia",          "hf":"🇹🇳","a":"Japão",               "af":"🇯🇵"},
    # ── Domingo 21/jun ─────────────────────────────────────────────────────
    {"g":"H","r":2,"brt":"21/06 15:00","t":"2026-06-21T18:00","h":"Espanha",          "hf":"🇪🇸","a":"Arábia Saudita",      "af":"🇸🇦"},
    {"g":"G","r":2,"brt":"21/06 17:00","t":"2026-06-21T20:00","h":"Bélgica",          "hf":"🇧🇪","a":"Irã",                 "af":"🇮🇷"},
    {"g":"H","r":2,"brt":"21/06 20:00","t":"2026-06-21T23:00","h":"Uruguai",          "hf":"🇺🇾","a":"Cabo Verde",          "af":"🇨🇻"},
    {"g":"G","r":2,"brt":"22/06 02:00","t":"2026-06-22T05:00","h":"Nova Zelândia",    "hf":"🇳🇿","a":"Egito",               "af":"🇪🇬"},
    # ── Segunda 22/jun ─────────────────────────────────────────────────────
    {"g":"J","r":2,"brt":"22/06 15:00","t":"2026-06-22T18:00","h":"Argentina",        "hf":"🇦🇷","a":"Áustria",             "af":"🇦🇹"},
    {"g":"I","r":2,"brt":"22/06 21:00","t":"2026-06-23T00:00","h":"França",           "hf":"🇫🇷","a":"Iraque",              "af":"🇮🇶"},
    {"g":"I","r":2,"brt":"23/06 00:00","t":"2026-06-23T03:00","h":"Noruega",          "hf":"🇳🇴","a":"Senegal",             "af":"🇸🇳"},
    {"g":"J","r":2,"brt":"23/06 03:00","t":"2026-06-23T06:00","h":"Jordânia",         "hf":"🇯🇴","a":"Argélia",             "af":"🇩🇿"},
    # ── Terça 23/jun ───────────────────────────────────────────────────────
    {"g":"K","r":2,"brt":"23/06 15:00","t":"2026-06-23T18:00","h":"Portugal",         "hf":"🇵🇹","a":"Uzbequistão",         "af":"🇺🇿"},
    {"g":"L","r":2,"brt":"23/06 20:00","t":"2026-06-23T23:00","h":"Inglaterra",       "hf":"🏴󠁧󠁢󠁥󠁮󠁧󠁿","a":"Gana",               "af":"🇬🇭"},
    {"g":"K","r":2,"brt":"24/06 00:00","t":"2026-06-24T03:00","h":"Colômbia",         "hf":"🇨🇴","a":"Congo RD",            "af":"🇨🇩"},
    {"g":"L","r":2,"brt":"24/06 11:00","t":"2026-06-24T14:00","h":"Panamá",           "hf":"🇵🇦","a":"Croácia",             "af":"🇭🇷"},

    # ════════════════════════════════════════════════════════════════════════
    # RODADA 3  (24 jogos — jogos simultâneos por grupo, abre após FIM da Rodada 2)
    # ════════════════════════════════════════════════════════════════════════
    # ── Quarta 24/jun ──────────────────────────────────────────────────────
    {"g":"B","r":3,"brt":"24/06 17:00","t":"2026-06-24T20:00","h":"Suíça",            "hf":"🇨🇭","a":"Canadá",              "af":"🇨🇦"},
    {"g":"B","r":3,"brt":"24/06 17:00","t":"2026-06-24T20:00","h":"Bósnia e Herzegovina","hf":"🇧🇦","a":"Catar",            "af":"🇶🇦"},
    {"g":"C","r":3,"brt":"24/06 20:00","t":"2026-06-24T23:00","h":"Escócia",          "hf":"🏴󠁧󠁢󠁳󠁣󠁴󠁿","a":"Brasil",             "af":"🇧🇷"},
    {"g":"C","r":3,"brt":"24/06 20:00","t":"2026-06-24T23:00","h":"Marrocos",         "hf":"🇲🇦","a":"Haiti",               "af":"🇭🇹"},
    # ── Quinta 25/jun ──────────────────────────────────────────────────────
    {"g":"A","r":3,"brt":"25/06 11:00","t":"2026-06-25T14:00","h":"República Tcheca", "hf":"🇨🇿","a":"México",              "af":"🇲🇽"},
    {"g":"A","r":3,"brt":"25/06 11:00","t":"2026-06-25T14:00","h":"África do Sul",    "hf":"🇿🇦","a":"Coreia do Sul",       "af":"🇰🇷"},
    {"g":"D","r":3,"brt":"26/06 01:00","t":"2026-06-26T04:00","h":"Turquia",          "hf":"🇹🇷","a":"Estados Unidos",      "af":"🇺🇸"},
    {"g":"D","r":3,"brt":"26/06 01:00","t":"2026-06-26T04:00","h":"Paraguai",         "hf":"🇵🇾","a":"Austrália",           "af":"🇦🇺"},
    # ── Sexta 26/jun ───────────────────────────────────────────────────────
    {"g":"E","r":3,"brt":"25/06 21:00","t":"2026-06-26T00:00","h":"Equador",          "hf":"🇪🇨","a":"Alemanha",            "af":"🇩🇪"},
    {"g":"E","r":3,"brt":"25/06 21:00","t":"2026-06-26T00:00","h":"Curaçao",          "hf":"🇨🇼","a":"Costa do Marfim",     "af":"🇨🇮"},
    {"g":"F","r":3,"brt":"26/06 21:00","t":"2026-06-27T00:00","h":"Japão",            "hf":"🇯🇵","a":"Suécia",              "af":"🇸🇪"},
    {"g":"F","r":3,"brt":"26/06 21:00","t":"2026-06-27T00:00","h":"Tunísia",          "hf":"🇹🇳","a":"Holanda",             "af":"🇳🇱"},
    # ── Sábado 27/jun ──────────────────────────────────────────────────────
    {"g":"I","r":3,"brt":"27/06 19:00","t":"2026-06-27T22:00","h":"Noruega",          "hf":"🇳🇴","a":"França",              "af":"🇫🇷"},
    {"g":"I","r":3,"brt":"27/06 19:00","t":"2026-06-27T22:00","h":"Senegal",          "hf":"🇸🇳","a":"Iraque",              "af":"🇮🇶"},
    {"g":"G","r":3,"brt":"28/06 03:00","t":"2026-06-28T06:00","h":"Egito",            "hf":"🇪🇬","a":"Irã",                 "af":"🇮🇷"},
    {"g":"G","r":3,"brt":"28/06 03:00","t":"2026-06-28T06:00","h":"Nova Zelândia",    "hf":"🇳🇿","a":"Bélgica",             "af":"🇧🇪"},
    # ── Domingo 28/jun ─────────────────────────────────────────────────────
    {"g":"H","r":3,"brt":"28/06 00:00","t":"2026-06-28T03:00","h":"Cabo Verde",       "hf":"🇨🇻","a":"Arábia Saudita",      "af":"🇸🇦"},
    {"g":"H","r":3,"brt":"28/06 00:00","t":"2026-06-28T03:00","h":"Uruguai",          "hf":"🇺🇾","a":"Espanha",             "af":"🇪🇸"},
    {"g":"L","r":3,"brt":"28/06 13:00","t":"2026-06-28T16:00","h":"Panamá",           "hf":"🇵🇦","a":"Inglaterra",          "af":"🏴󠁧󠁢󠁥󠁮󠁧󠁿"},
    {"g":"L","r":3,"brt":"28/06 13:00","t":"2026-06-28T16:00","h":"Croácia",          "hf":"🇭🇷","a":"Gana",                "af":"🇬🇭"},
    # ── Segunda/Terça 29/jun ───────────────────────────────────────────────
    {"g":"J","r":3,"brt":"29/06 02:00","t":"2026-06-29T05:00","h":"Argélia",          "hf":"🇩🇿","a":"Áustria",             "af":"🇦🇹"},
    {"g":"J","r":3,"brt":"29/06 02:00","t":"2026-06-29T05:00","h":"Jordânia",         "hf":"🇯🇴","a":"Argentina",           "af":"🇦🇷"},
    {"g":"K","r":3,"brt":"29/06 15:30","t":"2026-06-29T18:30","h":"Colômbia",         "hf":"🇨🇴","a":"Portugal",            "af":"🇵🇹"},
    {"g":"K","r":3,"brt":"29/06 15:30","t":"2026-06-29T18:30","h":"Congo RD",         "hf":"🇨🇩","a":"Uzbequistão",         "af":"🇺🇿"},
]

def api(method, path, body=None):
    url = f'{BASE}{path}'
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('Content-Type', 'application/json')
    req.add_header('x-admin-password', ADMIN_PWD)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f'  ❌ Erro: {json.loads(e.read())}'); return None

if __name__ == '__main__':
    payload = [{"home_team":m["h"],"away_team":m["a"],"home_flag":m["hf"],"away_flag":m["af"],
                "phase":"group","group_name":m["g"],"round_number":m["r"],"match_time":m["t"]} for m in MATCHES]

    print(f'📥 Importando {len(payload)} jogos com horários corretos (BRT)...\n')
    result = api('POST', '/api/matches/bulk', {"matches": payload})
    if not result:
        sys.exit(1)

    print(f'✅ {result["inserted"]} jogos importados!\n')

    # Mostrar verificação
    for r_num in [1, 2, 3]:
        ms = [m for m in MATCHES if m["r"] == r_num]
        first = min(ms, key=lambda m: m["t"])
        print(f'  Rodada {r_num}: {len(ms)} jogos | 1º jogo: {first["brt"]} BRT ({first["h"]} x {first["a"]})')

    print(f'\n🔒 Regra de bloqueio:')
    print(f'   Rodada 1: apostas encerram às 16:00 BRT de 11/jun (início de México x África do Sul)')
    print(f'   Rodada 2: abre APÓS todos os jogos da Rodada 1 finalizarem')
    print(f'   Rodada 3: abre APÓS todos os jogos da Rodada 2 finalizarem')
    print(f'\n🔗 http://localhost:3000')
