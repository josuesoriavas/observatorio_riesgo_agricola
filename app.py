"""Publica el tablero (salida/index.html) en Streamlit.

La corrida diaria (correr.bat) arma salida/. Esta app solo muestra lo último que haya ahí.
  Local:  streamlit run app.py
  Nube:   subir app.py, requirements.txt, .streamlit/config.toml, salida/index.html y static/ a GitHub
          (antes de cada subida: py app.py  -> copia el logo y las imágenes de evolución a static/).
Streamlit sirve static/ en /app/static/ (enableStaticServing en .streamlit/config.toml): de ahí salen el logo y las imágenes."""
import base64
import shutil
from pathlib import Path

import streamlit as st

RAIZ = Path(__file__).parent
SALIDA = RAIZ / "salida"
STATIC = RAIZ / "static"
ALTO = 820  # alto del tablero en px; el tablero se escala solo al ancho y alto disponibles


def sincronizar():
    """Copia el logo y las imágenes de evolución en tierra de salida/ a static/ cuando hay versiones nuevas."""
    for sub in ("img", "evolucion", "capas"):
        origen = SALIDA / sub
        if not origen.exists():
            continue
        for f in origen.rglob("*"):  # incluye subcarpetas (evolucion/<ubigeo>/...)
            d = STATIC / sub / f.relative_to(origen)
            if f.is_file() and (not d.exists() or f.stat().st_mtime > d.stat().st_mtime):
                d.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, d)


def tablero():
    html = (SALIDA / "index.html").read_text(encoding="utf-8")
    # el logo va incrustado (en Streamlit Cloud la app vive en una subruta y /app/static/ no siempre resuelve)
    logo = next((f for f in (STATIC / "img" / "logo_midagri.png", SALIDA / "img" / "logo_midagri.png") if f.exists()), None)
    if logo:
        html = html.replace('src="img/logo_midagri.png"', 'src="data:image/png;base64,' + base64.b64encode(logo.read_bytes()).decode() + '"')
    # imágenes de evolución en tierra: ruta relativa a la app (sirve en local y en la nube)
    html = html.replace('"evolucion/', '"app/static/evolucion/').replace('"capas/', '"app/static/capas/')
    return html


if __name__ == "__main__" and not st.runtime.exists():
    sincronizar()  # py app.py: solo prepara static/ para subirlo
    print("static/ al día")
else:
    st.set_page_config(page_title="Observatorio de Riesgo Agrícola", layout="wide", initial_sidebar_state="collapsed")
    # el tablero ocupa exactamente la ventana: sin márgenes ni desplazamiento de la página de Streamlit
    st.markdown("""<style>
      header[data-testid="stHeader"], footer, #MainMenu, [data-testid="stToolbar"], [data-testid="stDecoration"] { display: none !important }
      html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"], section.main { overflow: hidden !important; height: 100vh !important }
      .block-container, [data-testid="stMainBlockContainer"] { padding: 0 !important; margin: 0 !important; max-width: 100% !important }
      [data-testid="stVerticalBlock"] { gap: 0 !important }
      [data-testid="stElementContainer"]:has(> .stMarkdown style), .element-container:has(style) { display: none !important }
      iframe { display: block; border: 0; width: 100% !important; height: 100vh !important }
    </style>""", unsafe_allow_html=True)
    sincronizar()
    if not (SALIDA / "index.html").exists():
        st.error("Todavía no hay tablero: falta salida/index.html (se genera con correr.bat).")
    else:
        st.components.v1.html(tablero(), height=ALTO, scrolling=False)
