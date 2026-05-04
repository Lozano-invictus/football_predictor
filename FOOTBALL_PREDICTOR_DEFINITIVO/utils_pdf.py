"""
utils_pdf.py
Generación de reportes en PDF para las predicciones.
"""
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import cm
import io

def generate_prediction_pdf(home_name, away_name, result):
    """Genera un buffer de bytes con el PDF de la predicción."""
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Título
    p.setFont("Helvetica-Bold", 20)
    p.drawString(2 * cm, height - 2 * cm, "Reporte de Predicción de Fútbol")
    
    p.setFont("Helvetica", 12)
    p.drawString(2 * cm, height - 3 * cm, f"Partido: {home_name} vs {away_name}")
    p.drawString(2 * cm, height - 3.5 * cm, f"Fecha: {result.get('date', 'N/A')}")
    
    # KPIs
    p.setStrokeColor(colors.black)
    p.line(2 * cm, height - 4 * cm, width - 2 * cm, height - 4 * cm)
    
    p.setFont("Helvetica-Bold", 14)
    p.drawString(2 * cm, height - 5 * cm, "Probabilidades:")
    p.setFont("Helvetica", 12)
    p.drawString(3 * cm, height - 6 * cm, f"Victoria {home_name}: {result['home_win']:.1%}")
    p.drawString(3 * cm, height - 6.5 * cm, f"Empate: {result['draw']:.1%}")
    p.drawString(3 * cm, height - 7 * cm, f"Victoria {away_name}: {result['away_win']:.1%}")
    
    p.setFont("Helvetica-Bold", 14)
    p.drawString(2 * cm, height - 8 * cm, "Goles Esperados (xG):")
    p.setFont("Helvetica", 12)
    p.drawString(3 * cm, height - 9 * cm, f"{home_name}: {result['expected_home']:.2f}")
    p.drawString(3 * cm, height - 9.5 * cm, f"{away_name}: {result['expected_away']:.2f}")
    
    # Marcadores más probables
    p.setFont("Helvetica-Bold", 14)
    p.drawString(2 * cm, height - 11 * cm, "Top 5 Marcadores:")
    y = 12 * cm
    for i, score in enumerate(result['top_scores'][:5]):
        p.setFont("Helvetica", 12)
        p.drawString(3 * cm, height - y, f"{score['home_goals']} - {score['away_goals']}: {score['probability']:.1%}")
        y += 0.5 * cm

    p.showPage()
    p.save()
    
    buffer.seek(0)
    return buffer
