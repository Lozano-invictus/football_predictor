"""
pages/11_Perfiles.py
Perfiles detallados de Jugadores y Clubes.
Visualizaciones de rendimiento, historial de transferencias y valor de mercado.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from data.database import get_session, Team, Player, PlayerSeasonStats, Transfer, TeamSeasonStats, MarketValueHistory, Coach
from data.loader import DataLoader
import config

st.set_page_config(page_title="Perfiles UCL", page_icon="👤", layout="wide")

def show_player_profile(player_id):
    session = get_session()
    player = session.query(Player).get(player_id)
    if not player:
        st.error("Jugador no encontrado")
        return

    st.title(f"👤 {player.name}")
    c1, c2 = st.columns([1, 2])
    
    with c1:
        if player.image_url:
            st.image(player.image_url, width=200)
        st.write(f"**Nombre Completo:** {player.full_name or player.name}")
        st.write(f"**Nacionalidad:** {player.nationality}")
        st.write(f"**Posición:** {player.position_main}")
        
    with c2:
        st.subheader("📊 Estadísticas por Temporada")
        stats = session.query(PlayerSeasonStats, Team.name.label('team_name'))\
            .join(Team, PlayerSeasonStats.team_id == Team.id)\
            .filter(PlayerSeasonStats.player_id == player_id).all()
        
        if stats:
            data = []
            for s, t_name in stats:
                data.append({
                    "Temporada": s.season,
                    "Equipo": t_name,
                    "Goles": s.goals,
                    "Asistencias": s.assists,
                    "Minutos": s.minutes_played,
                    "Rating": s.rating_avg
                })
            df_stats = pd.DataFrame(data)
            st.dataframe(df_stats, use_container_width=True)
            
            # Gráfico de evolución de Rating
            fig = px.line(df_stats, x="Temporada", y="Rating", markers=True, title="Evolución de Rendimiento")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay estadísticas registradas.")

    st.divider()
    col_v, col_t = st.columns(2)
    
    with col_v:
        st.subheader("💰 Evolución de Valor de Mercado")
        values = session.query(MarketValueHistory).filter_by(player_id=player_id).order_by(MarketValueHistory.date).all()
        if values:
            df_val = pd.DataFrame([{"Fecha": v.date, "Valor (M€)": v.value} for v in values])
            fig_val = px.area(df_val, x="Fecha", y="Valor (M€)", title="Market Value Timeline")
            st.plotly_chart(fig_val, use_container_width=True)
        else:
            st.info("No hay historial de valor.")
            
    with col_t:
        st.subheader("🔄 Historial de Transferencias")
        transfers = session.query(Transfer).filter_by(player_id=player_id).all()
        if transfers:
            for t in transfers:
                from_t = session.query(Team).get(t.from_team_id).name if t.from_team_id else "Libre"
                to_t = session.query(Team).get(t.to_team_id).name if t.to_team_id else "Retirado"
                st.write(f"📅 {t.season}: **{from_t}** ➡️ **{to_t}** ({t.fee} M€)")
        else:
            st.info("No hay transferencias registradas.")
    
    session.close()

def show_team_profile(team_id):
    session = get_session()
    team = session.query(Team).get(team_id)
    if not team:
        st.error("Equipo no encontrado")
        return

    st.title(f"🛡️ {team.name}")
    c1, c2 = st.columns([1, 2])
    
    with c1:
        if team.logo_url:
            st.image(team.logo_url, width=150)
        st.write(f"**País:** {team.country}")
        st.write(f"**Estadio:** {team.stadium or 'N/A'}")
        st.write(f"**Títulos UCL:** {team.ucl_titles}")
        
    with c2:
        st.subheader("📈 Rendimiento Histórico")
        stats = session.query(TeamSeasonStats).filter_by(team_id=team_id).all()
        if stats:
            df_stats = pd.DataFrame([{"Temporada": s.season, "Elo": s.elo_rating, "Fase": s.reached_stage} for s in stats])
            fig_elo = px.line(df_stats, x="Temporada", y="Elo", title="Evolución Elo Rating")
            st.plotly_chart(fig_elo, use_container_width=True)
        
    st.divider()
    st.subheader("👥 Plantilla Actual (2025-26)")
    players = session.query(Player.name, PlayerSeasonStats.position, PlayerSeasonStats.market_value)\
        .join(PlayerSeasonStats, Player.id == PlayerSeasonStats.player_id)\
        .filter(PlayerSeasonStats.team_id == team_id, PlayerSeasonStats.season == "2025-2026").all()
    
    if players:
        st.table(pd.DataFrame(players, columns=["Jugador", "Posición", "Valor (M€)"]))
    else:
        st.info("Plantilla no disponible para esta temporada.")
        
    session.close()

# --- MAIN INTERFACE ---
session = get_session()
st.sidebar.title("🔍 Explorador")
type_search = st.sidebar.selectbox("Buscar", ["Jugadores", "Equipos"])

if type_search == "Jugadores":
    players_list = session.query(Player.id, Player.name).all()
    if not players_list:
        st.info("No hay jugadores registrados.")
        session.close()
        st.stop()
    p_choice = st.sidebar.selectbox("Seleccionar Jugador", players_list, format_func=lambda x: x[1])
    if p_choice:
        show_player_profile(p_choice[0])
else:
    teams_list = session.query(Team.id, Team.name).all()
    if not teams_list:
        st.info("No hay equipos registrados.")
        session.close()
        st.stop()
    t_choice = st.sidebar.selectbox("Seleccionar Equipo", teams_list, format_func=lambda x: x[1])
    if t_choice:
        show_team_profile(t_choice[0])

session.close()
