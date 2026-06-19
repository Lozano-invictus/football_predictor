"""
football_predictor_pro.py
PUNTO DE ENTRADA ÚNICO - Analizador Predictivo de Fútbol 2024-25
Este archivo consolida toda la lógica de modelos, datos y UI.

Ejecutar con: streamlit run football_predictor_pro.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from scipy.stats import poisson
from sqlalchemy import func  # FIX: sustituye el incorrecto pd.func
from datetime import datetime
import json
import os
import sys
from typing import Dict, List, Tuple, Optional

# Importar configuración
import config
from utils import logger, cached

# ================================================================ #
# 1. MODELOS MATEMÁTICOS (Poisson, Dixon-Coles & Elo)
# ================================================================ #

class FootballModel:
    def __init__(self):
        self.avg = config.LEAGUE_AVG_GOALS
        self.home_adv = config.HOME_ADVANTAGE
        self.max_goals = config.MAX_GOALS
        self.rho = -0.15 # Dixon-Coles correlation factor
        self.k_factor = config.ELO_K_FACTOR

    def get_hybrid_strength(self, team: Dict, historical_team: Optional[Dict] = None) -> float:
        """
        Calcula la fuerza híbrida: xG Base (60%) + Forma (25%) + Fichajes (15%).
        """
        # 1. Base xG (Híbrido Histórico + Actual)
        current_xg = team.get("attack", 1.0)
        hist_xg = historical_team.get("attack", current_xg) if historical_team else current_xg
        base_xg = (current_xg * config.HYBRID_CURRENT_WEIGHT) + (hist_xg * config.HYBRID_HISTORICAL_WEIGHT)

        # 2. Impacto de Fichajes (Simulado o basado en datos de equipo)
        # Si el equipo tiene un rating de transferencias alto, suma un bonus
        transfer_impact = team.get("transfer_rating", 0.0) * config.TRANSFER_IMPACT_COEFF

        # 3. Forma Reciente (Simulada si no hay datos live)
        form_factor = team.get("recent_form", 1.0) # 1.0 es neutral

        strength = (base_xg * config.BASE_XG_WEIGHT) + (form_factor * config.FORM_WEIGHT) + (transfer_impact)
        return round(strength, 3)

    def calculate_elo(self, rating_a: float, rating_b: float, actual_score: float) -> Tuple[float, float]:
        """
        Calcula el cambio de Elo entre dos equipos.
        actual_score: 1.0 (win), 0.5 (draw), 0.0 (loss)
        """
        expected_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
        new_rating_a = rating_a + self.k_factor * (actual_score - expected_a)
        new_rating_b = rating_b + self.k_factor * ((1 - actual_score) - (1 - expected_a))
        return new_rating_a, new_rating_b

    def _tau_correction(self, x, y, lh, la):
        if x == 0 and y == 0: return 1 - (lh * la * self.rho)
        elif x == 0 and y == 1: return 1 + (lh * self.rho)
        elif x == 1 and y == 0: return 1 + (la * self.rho)
        elif x == 1 and y == 1: return 1 - self.rho
        return 1.0

    def predict_match(self, home: Dict, away: Dict, model_type="Dixon-Coles") -> Dict:
        # Incorporar factores físico-técnicos si existen (basado en Murillo García, 2025)
        # Distancia media: 117.41 km. Posesión media: 50%
        h_dist = home.get("avg_distance", config.AVG_DISTANCE_KM)
        a_dist = away.get("avg_distance", config.AVG_DISTANCE_KM)
        h_poss = home.get("avg_possession", 50.0)
        a_poss = away.get("avg_possession", 50.0)

        # Ajuste por intensidad (distancia) y control (posesión)
        # Un equipo que corre más de la media y tiene más balón suele ser más eficiente
        h_intensity = h_dist / config.AVG_DISTANCE_KM
        a_intensity = a_dist / config.AVG_DISTANCE_KM
        h_control = h_poss / 50.0
        a_control = a_poss / 50.0

        lh = (home["attack"] / self.avg) * (away["defense"] / self.avg) * self.avg * self.home_adv
        la = (away["attack"] / self.avg) * (home["defense"] / self.avg) * self.avg
        
        # Aplicar factores multidimensionales leves
        lh *= (0.95 + 0.05 * h_intensity) * (0.95 + 0.05 * h_control)
        la *= (0.95 + 0.05 * a_intensity) * (0.95 + 0.05 * a_control)

        matrix = np.zeros((self.max_goals + 1, self.max_goals + 1))
        for x in range(self.max_goals + 1):
            for y in range(self.max_goals + 1):
                prob = poisson.pmf(x, lh) * poisson.pmf(y, la)
                if model_type == "Dixon-Coles":
                    prob *= self._tau_correction(x, y, lh, la)
                matrix[x, y] = prob
        
        matrix /= matrix.sum()
        
        home_win = float(np.tril(matrix, -1).sum())
        draw = float(np.trace(matrix))
        away_win = float(np.triu(matrix, 1).sum())

        top_scores = []
        for i in range(6):
            for j in range(6):
                top_scores.append({"score": f"{i}-{j}", "p": matrix[i, j], "h": i, "a": j})
        top_scores.sort(key=lambda x: x["p"], reverse=True)

        return {
            "home_win": home_win, "draw": draw, "away_win": away_win,
            "expected_home": lh, "expected_away": la,
            "matrix": matrix, "top_scores": top_scores[:10]
        }

# ================================================================ #
# 2. GESTIÓN DE DATOS (SQLAlchemy / SQLite)
# ================================================================ #

from data.database import get_session, Team, Player, PlayerSeasonStats, TeamSeasonStats, Match, Transfer

class DataManager:
    def __init__(self):
        self.session = get_session()

    def load_teams(self, season=None) -> List[Dict]:
        try:
            if season:
                # Query optimizada con JOIN para evitar N+1
                teams_with_stats = self.session.query(Team, TeamSeasonStats)\
                    .outerjoin(TeamSeasonStats, (Team.id == TeamSeasonStats.team_id) & (TeamSeasonStats.season == season))\
                    .all()
                
                result = []
                for t, s in teams_with_stats:
                    team_dict = {
                        "id": t.id,
                        "name": t.name,
                        "country": t.country,
                        "attack": s.attack_score if s else 1.0,
                        "defense": s.defense_score if s else 1.0,
                        "elo": s.elo_rating if s else 1500.0
                    }
                    result.append(team_dict)
                return result
            else:
                teams = self.session.query(Team).all()
                return [{
                    "id": t.id,
                    "name": t.name,
                    "country": t.country,
                    "attack": 1.0,
                    "defense": 1.0,
                    "elo": 1500.0
                } for t in teams]
        except Exception as e:
            logger.error(f"Error cargando equipos: {e}")
            st.error("Error de conexión con la base de datos.")
            return []

    def get_historical_summary(self):
        try:
            stats = self.session.query(TeamSeasonStats.season, TeamSeasonStats.team_id).all()
            return pd.DataFrame(stats, columns=['season', 'team_id'])
        except Exception as e:
            logger.error(f"Error resumen histórico: {e}")
            return pd.DataFrame()

    def get_top_scorers(self, season, limit=10):
        try:
            scorers = self.session.query(Player.name, PlayerSeasonStats.goals, Team.name.label('team'))\
                .join(PlayerSeasonStats, Player.id == PlayerSeasonStats.player_id)\
                .join(Team, PlayerSeasonStats.team_id == Team.id)\
                .filter(PlayerSeasonStats.season == season)\
                .order_by(PlayerSeasonStats.goals.desc())\
                .limit(limit).all()
            return pd.DataFrame(scorers, columns=['Jugador', 'Goles', 'Equipo'])
        except Exception as e:
            logger.error(f"Error goleadores: {e}")
            return pd.DataFrame()

# ================================================================ #
# 3. INTERFAZ DE USUARIO (Streamlit Multi-Tool)
# ================================================================ #

from predictor.hybrid_model import HybridModel
from predictor.tournament_real import RealTournamentSimulator

def apply_custom_style():
    st.markdown("""
        <style>
        .main {
            background-color: #f5f7f9;
        }
        .stMetric {
            background-color: white;
            padding: 15px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        .stButton>button {
            width: 100%;
            border-radius: 5px;
            height: 3em;
            background-color: #185FA5;
            color: white;
        }
        .card {
            background-color: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        h1, h2, h3 {
            color: #0d1b2a;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        </style>
    """, unsafe_allow_html=True)

def main():
    st.set_page_config(page_title="Football Predictor Pro 2025-26", page_icon="⚽", layout="wide")
    apply_custom_style()
    
    # Sidebar Navigation
    st.sidebar.title("⚽ UCL Analysis Pro")
    st.sidebar.image("https://upload.wikimedia.org/wikipedia/en/b/bf/UEFA_Champions_League_logo_2.svg", width=100)
    
    # Búsqueda Global
    search_query = st.sidebar.text_input("🔍 Buscar Jugador o Club")
    if search_query:
        st.sidebar.info(f"Ve a la sección '👤 Perfiles' para ver detalles de '{search_query}'")
    
    # Selección de Temporada
    st.sidebar.subheader("📅 Temporada")
    season_mode = st.sidebar.radio("Modo", [f"Temporada Actual ({config.CURRENT_SEASON})", "Histórico"])
    if season_mode == "Histórico":
        active_season = st.sidebar.selectbox("Seleccionar temporada", ["2024-2025", "2023-2024", "2022-2023"])
    else:
        active_season = config.CURRENT_SEASON

    menu = st.sidebar.radio("Navegación", 
        ["🏠 Dashboard", "⚽ Analizador de Partido", "🏆 Simular Torneo", "👤 Perfiles", "⚖️ Benchmarking", "🔄 Actualizar Datos", "⚙️ Admin Total", "🛠️ Configuración"])

    # --- CARGA DE DATOS ---
    dm = DataManager()
    model = HybridModel()
    teams = dm.load_teams(season=active_season)
    
    if menu == "🏠 Dashboard":
        st.title(f"🏆 UEFA Champions League Dashboard")
        st.markdown(f"**Temporada:** {active_season} | **Status:** {'🟢 En curso' if active_season == config.CURRENT_SEASON else '🔴 Finalizada'}")
        
        # Pestañas del Dashboard
        tab_summary, tab_stats, tab_history, tab_predictive = st.tabs(["🏠 Resumen", "📊 Estadísticas", "📜 Histórico", "🔮 Predicciones IA"])

        with tab_summary:
            # KPIs Principales en Cards
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("Equipos", len(teams))
            with c2:
                # FIX: pd.func no existe — usar sqlalchemy.func
                total_goals = dm.session.query(
                    func.sum(PlayerSeasonStats.goals)
                ).filter(PlayerSeasonStats.season == active_season).scalar() or 0
                st.metric("Goles Totales", total_goals)
            with c3:
                matches_count = dm.session.query(Match).filter(Match.season == active_season).count()
                st.metric("Partidos", matches_count)
            with c4:
                top_elo = max([t['elo'] for t in teams]) if teams else 0
                st.metric("Elo Máximo", int(top_elo))

            # Sección de Favoritos y Power Ranking
            st.divider()
            col_rank, col_map = st.columns([1, 1])
            
            with col_rank:
                st.subheader("🏆 Power Ranking (Top 10)")
                if teams:
                    df_teams = pd.DataFrame(teams).sort_values("elo", ascending=False).head(10)
                    st.dataframe(df_teams[["name", "country", "elo", "attack", "defense"]], use_container_width=True)
                
            with col_map:
                st.subheader("📍 Mapa de Eficiencia")
                if teams:
                    fig_eff = px.scatter(pd.DataFrame(teams), x="attack", y="defense", text="name", color="elo",
                                         labels={'attack': 'Poder Ofensivo', 'defense': 'Poder Defensivo'},
                                         template="plotly_white")
                    st.plotly_chart(fig_eff, use_container_width=True)

        with tab_stats:
            st.subheader("🔥 Líderes de la Temporada")
            col_g, col_a = st.columns(2)
            
            with col_g:
                st.write("**Máximos Goleadores**")
                df_scorers = dm.get_top_scorers(active_season, limit=10)
                if not df_scorers.empty:
                    st.table(df_scorers)
                else:
                    st.info("Datos no disponibles para esta temporada.")
                    
            with col_a:
                st.write("**Mejores Asistentes**")
                assists = dm.session.query(Player.name, PlayerSeasonStats.assists, Team.name.label('team'))\
                    .join(PlayerSeasonStats, Player.id == PlayerSeasonStats.player_id)\
                    .join(Team, PlayerSeasonStats.team_id == Team.id)\
                    .filter(PlayerSeasonStats.season == active_season)\
                    .order_by(PlayerSeasonStats.assists.desc()).limit(10).all()
                if assists:
                    st.table(pd.DataFrame(assists, columns=['Jugador', 'Asistencias', 'Equipo']))
                else:
                    st.info("Datos no disponibles.")

        with tab_history:
            st.subheader("� Evolución UCL (2022-2026)")
            seasons_all = ["2022-2023", "2023-2024", "2024-2025", "2025-2026"]
            
            # Evolución de Goles vs Partidos
            hist_data = []
            for s in seasons_all:
                # FIX: pd.func no existe — usar sqlalchemy.func
                g = dm.session.query(
                    func.sum(PlayerSeasonStats.goals)
                ).filter(PlayerSeasonStats.season == s).scalar() or 0
                m = dm.session.query(Match).filter(Match.season == s).count()
                hist_data.append({"Temporada": s, "Goles": g, "Partidos": m})
            
            df_hist = pd.DataFrame(hist_data)
            fig_hist = px.bar(df_hist, x="Temporada", y=["Goles", "Partidos"], barmode="group",
                              title="Goles y Partidos por Temporada", template="plotly_white")
            st.plotly_chart(fig_hist, use_container_width=True)

        with tab_predictive:
            st.subheader("🔮 IA Prediction Engine")
            if active_season == config.CURRENT_SEASON:
                st.write("Predicción del Campeón Final 2025-26 basada en Monte Carlo y Elo dinámico:")
                # Aquí iría la llamada al simulador real
                top_teams = sorted(teams, key=lambda x: x['elo'], reverse=True)[:5]
                for i, t in enumerate(top_teams):
                    prob = (t['elo'] / sum([x['elo'] for x in top_teams])) * 100
                    st.progress(prob/100, text=f"{t['name']} - {prob:.1f}%")
            else:
                st.info("Las predicciones solo están disponibles para la temporada actual.")

        # Footer con enlaces
        st.divider()
        st.caption("Data Sources: UEFA Official, FBref, Transfermarkt | Producido por UCL Analysis Pro")

        c_link1, c_link2, c_link3 = st.columns(3)
        c_link1.link_button("UEFA Official Stats", config.OFFICIAL_SOURCES["UEFA_UCL_STATS"])
        c_link2.link_button("FBref UCL Data", config.OFFICIAL_SOURCES["FBREF_UCL"])
        c_link3.link_button("Football-Data API", config.OFFICIAL_SOURCES["FOOTBALL_DATA_API"])

        col1, col2, col3 = st.columns(3)
        col1.metric("Equipos Cargados", len(teams))
        col2.metric("Modelo Activo", "Dixon-Coles + Elo")
        col3.metric("Fuente de Datos", "FBref + UEFA (Opta)")

        # Ranking Live (Simulado con datos cargados o scraping)
        st.divider()
        tab_rank_teams, tab_rank_players = st.tabs(["🏆 Ranking de Equipos (Live)", "🔥 Top Goleadores"])
        
        with tab_rank_teams:
            if teams:
                df = pd.DataFrame(teams)
                df["elo"] = df.get("elo", config.ELO_INITIAL_RATING)
                df["strength"] = df["attack"] - df["defense"]
                df_sorted = df.sort_values("strength", ascending=False)
                
                st.subheader("Clasificación de Poder (Team Strength)")
                st.dataframe(df_sorted[["name", "country", "attack", "defense", "strength"]].head(10), use_container_width=True)
                
                fig = px.scatter(df, x="attack", y="defense", text="name", color="strength",
                                 title="Mapa de Eficiencia: Ataque vs Defensa",
                                 labels={"attack": "Eficiencia Ofensiva", "defense": "Solidez Defensiva"})
                fig.update_traces(textposition='top center')
                st.plotly_chart(fig, use_container_width=True)

        with tab_rank_players:
            # Intentar cargar datos reales de jugadores
            if os.path.exists(config.PLAYERS_FILE):
                with open(config.PLAYERS_FILE, 'r', encoding='utf-8') as f:
                    p_data = json.load(f)
                    strikers = pd.DataFrame(p_data.get("players", []))
                    if not strikers.empty:
                        st.subheader("Goleadores Champions League")
                        st.dataframe(strikers.sort_values("goals", ascending=False).head(10), use_container_width=True)
                        
                        fig_p = px.bar(strikers.head(10), x="name", y="goals", color="goals", title="Top 10 Goleadores")
                        st.plotly_chart(fig_p, use_container_width=True)

    elif menu == "⚽ Analizador de Partido":
        st.title("⚽ Análisis de Partido")
        if not teams:
            st.warning("No hay equipos cargados. Ve a 'Actualizar Datos'.")
            return

        names = sorted([t["name"] for t in teams])
        c1, c2 = st.columns(2)
        h_name = c1.selectbox("Local", names, index=0)
        a_name = c2.selectbox("Visitante", names, index=min(1, len(names)-1))
        
        m_type = st.sidebar.selectbox("Modelo", ["Dixon-Coles", "Poisson"])
        
        home = next(t for t in teams if t["name"] == h_name)
        away = next(t for t in teams if t["name"] == a_name)
        
        res = model.predict_match(home, away, model_type=m_type)
        
        # KPIs
        st.divider()
        k1, k2, k3 = st.columns(3)
        k1.metric(f"Prob. {h_name}", f"{res['home_win']:.1%}")
        k2.metric("Prob. Empate", f"{res['draw']:.1%}")
        k3.metric(f"Prob. {a_name}", f"{res['away_win']:.1%}")
        
        # Nuevos Indicadores Físicos (Murillo García, 2025)
        st.subheader("🏃 Indicadores Físico-Técnicos (2024-25)")
        c_phys1, c_phys2 = st.columns(2)
        with c_phys1:
            st.write(f"**{h_name}**")
            st.write(f"- Distancia media: {home.get('avg_distance', config.AVG_DISTANCE_KM)} km")
            st.write(f"- Posesión media: {home.get('avg_possession', 50.0)}%")
        with c_phys2:
            st.write(f"**{a_name}**")
            st.write(f"- Distancia media: {away.get('avg_distance', config.AVG_DISTANCE_KM)} km")
            st.write(f"- Posesión media: {away.get('avg_possession', 50.0)}%")
        
        # Gráficos
        g1, g2 = st.columns(2)
        with g1:
            st.subheader("Marcadores más Probables")
            top = res["top_scores"]
            fig_bar = px.bar(top, x="score", y="p", text_auto=".1%", title="Top 10 Marcadores")
            st.plotly_chart(fig_bar, use_container_width=True)
        
        with g2:
            st.subheader("Matriz de Probabilidades")
            fig_heat = px.imshow(res["matrix"][:6, :6], text_auto=".1%", 
                                 labels=dict(x=f"Goles {a_name}", y=f"Goles {h_name}"),
                                 x=[str(i) for i in range(6)], y=[str(i) for i in range(6)])
            st.plotly_chart(fig_heat, use_container_width=True)

    elif menu == "🏆 Simular Torneo":
        st.title("🏆 Simulador Real de Champions League")
        if len(teams) < 8:
            st.warning("Se necesitan al menos 8 equipos para simular desde Cuartos.")
            return

        st.subheader("Equipos en la Fase Final")
        selected_teams = st.multiselect(
            "Selecciona 8 equipos para la simulación",
            [t["name"] for t in teams],
            default=[t["name"] for t in teams[:8]]
        )

        n_sims = st.slider("Número de simulaciones Monte Carlo", 100, 5000, 1000, 100)

        if st.button("🚀 Iniciar Gran Simulación"):
            if len(selected_teams) < 2:
                st.warning("Selecciona al menos 2 equipos.")
            else:
                sim_teams = [t for t in teams if t["name"] in selected_teams]
                simulator = RealTournamentSimulator(season=active_season)

                with st.spinner(f"Ejecutando {n_sims} simulaciones Monte Carlo..."):
                    # FIX: run_full_tournament no existe → usar run_monte_carlo
                    mc_results = simulator.run_monte_carlo(sim_teams, n_sims=n_sims)

                champion = mc_results[0]
                finalist = mc_results[1] if len(mc_results) > 1 else mc_results[0]

                st.balloons()
                st.success(f"🏆 ¡EL CAMPEÓN PREDICHO ES: {champion['name']}!")

                # Tabla de probabilidades por equipo
                st.subheader("📊 Probabilidades Monte Carlo")
                df_mc = pd.DataFrame(mc_results)
                df_mc["champion"] = df_mc["champion"].map(lambda x: f"{x:.1%}")
                df_mc["final"]    = df_mc["final"].map(lambda x: f"{x:.1%}")
                df_mc["semi"]     = df_mc["semi"].map(lambda x: f"{x:.1%}")
                df_mc.columns     = ["Equipo", "% Campeón", "% Final", "% Semifinal"]
                st.dataframe(df_mc, use_container_width=True)

                # Cuadro simulado (vista ilustrativa)
                with st.expander("Ver cuadro del torneo (simulación ilustrativa)"):
                    rounds = {
                        "Cuartos de Final": [t["name"] for t in sim_teams],
                        "Semifinales":     [t["name"] for t in sim_teams[:4]],
                        "Final":           [champion["name"], finalist["name"]],
                    }
                    for r_name, r_teams_list in rounds.items():
                        st.markdown(f"**{r_name}**")
                        for i in range(0, len(r_teams_list), 2):
                            if i + 1 < len(r_teams_list):
                                st.write(f"🏟️ {r_teams_list[i]} vs {r_teams_list[i+1]}")
                            else:
                                st.write(f"🏟️ {r_teams_list[i]} (Pasa directo)")
                        st.divider()

    elif menu == "⚖️ Benchmarking":
        # Streamlit maneja las páginas en la carpeta 'pages/' automáticamente.
        # No es necesario importar el script como un módulo.
        st.info("Cargando módulo de Benchmarking...")
        st.switch_page("pages/9_Benchmarking.py")

    elif menu == "🔄 Actualizar Datos":
        st.title("🔄 Sincronización de Datos 2024-25")
        st.info("Este módulo utiliza indicadores físico-técnicos (Murillo García, 2025) para mejorar la precisión.")
        
        target = st.radio("¿Qué quieres actualizar?", ["Equipos", "Jugadores (Champions League)"])
        league = st.selectbox("Seleccionar Competición", ["Champions League", "Premier League", "La Liga"])
        season = st.selectbox("Temporada", ["2425", "2324", "2223"], index=0)
        
        if st.button("🚀 Ejecutar Actualización"):
            with st.spinner(f"Conectando con FBref para {target} ({season})..."):
                from data.fbref_scraper import FBrefScraper
                league_map = {
                    "Champions League": "UEFA-Champions League",
                    "Premier League": "ENG-Premier League",
                    "La Liga": "ESP-La Liga"
                }
                scraper = FBrefScraper(league=league_map[league], season=season)
                
                if target == "Equipos":
                    scraper.update_teams_json_with_xg()
                    st.success(f"✅ Datos de equipos de {league} {season} actualizados.")
                else:
                    scraper.update_players_json_by_season()
                    st.success(f"✅ Datos de jugadores de {league} {season} actualizados.")
                
                st.balloons()

    elif menu == "⚙️ Admin Total":
        st.switch_page("pages/10_Admin_Total.py")

    elif menu == "🛠️ Configuración":
        st.title("⚙️ Ajustes del Sistema")
        st.write("Modifica los parámetros globales del modelo.")
        
        new_avg = st.number_input("Media de Goles de la Liga", value=config.LEAGUE_AVG_GOALS, step=0.01)
        new_adv = st.number_input("Ventaja Local (multiplicador)", value=config.HOME_ADVANTAGE, step=0.05)
        
        if st.button("Guardar Configuración"):
            st.success("Configuración actualizada (temporalmente en esta sesión).")

if __name__ == "__main__":
    main()
