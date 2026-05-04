#!/usr/bin/env python3
"""Verificar integridad de datos"""
import sys
sys.path.insert(0, '.')
from data.loader import DataLoader

loader = DataLoader()
teams = loader.load_teams()
players = loader.load_players()

print('✅ Datos cargados correctamente:')
print(f'   - {len(teams)} equipos')

# players es una lista o dict, hay que verificar
if isinstance(players, list):
    print(f'   - {len(players)} jugadores (lista)')
    print('\n✅ Top 3 goleadores:')
    for i, p in enumerate(players[:3], 1):
        print(f'   {i}. {p.get("name", "N/A")}: {p.get("goals", 0)} goles')
elif isinstance(players, dict):
    print(f'   - {len(players.get("strikers", []))} goleadores')
    print(f'   - {len(players.get("goalkeepers", []))} porteros')
    print(f'   - {len(players.get("defenders", []))} defensas')
    print('\n✅ Top 3 goleadores:')
    for i, p in enumerate(players.get("strikers", [])[:3], 1):
        print(f'   {i}. {p.get("name", "N/A")}: {p.get("goals", 0)} goles (xG: {p.get("xg", 0)})')
else:
    print(f'   - Tipo de players: {type(players)}')

print('\n✅ Top 3 equipos por poder:')
sorted_teams = sorted(teams, key=lambda t: t['attack'] - t['defense'], reverse=True)
for i, t in enumerate(sorted_teams[:3], 1):
    strength = t['attack'] - t['defense']
    print(f'   {i}. {t["name"]}: {strength:.2f} (A:{t["attack"]} D:{t["defense"]})')
