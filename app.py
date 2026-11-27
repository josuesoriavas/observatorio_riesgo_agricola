"""Publica el tablero (salida/index.html) en Streamlit.

La corrida diaria (correr.bat) arma salida/. Esta app solo muestra lo último que haya ahí.
  Local:  streamlit run app.py
  Nube:   subir app.py, requirements.txt, .streamlit/config.toml, salida/index.html y static/ a GitHub
          (antes de cada subida: py app.py  -> copia el logo y las imágenes de evolución a static/).
Streamlit sirve static/ en /app/static/ (enableStaticServing en .streamlit/config.toml): de ahí salen el logo y las imágenes."""
import base64
import json
import re
import shutil
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import streamlit as st

RAIZ = Path(__file__).parent
SALIDA = RAIZ / "salida"
STATIC = RAIZ / "static"
ALTO = 820  # alto del tablero en px; el tablero se escala solo al ancho y alto disponibles

# --- Aviso vigente, preguntado por la propia app (27-11-2026): así las «zonas del aviso» no dependen de la PC.
# Sale del mapa público de SENAMHI (GeoServer IDESEP, sin clave). El navegador no puede consultarlo (sin CORS), el servidor sí.
WFS_AVISO = ("https://idesep.senamhi.gob.pe/geoserver/wfs?service=WFS&version=2.0.0&request=GetFeature&typeNames=g_aviso:view_aviso"
             "&outputFormat=application/json&propertyName=cod_even,nivel,fech_ini&viewparams=qry:{n}_{dia}_{anio}")
EVENTOS = {"1": "lluvia", "8": "lluvia", "2": "helada", "4": "helada"}   # cod_even: precipitaciones, lluvia, descenso de temperatura, friaje
PERU = timezone(timedelta(hours=-5))
CADA_S, REINTENTO_S = 3600, 600


def _mapa(n, dia, anio):
    """Datos del día `dia` del aviso n; None si no existe. Lanza si SENAMHI no responde."""
    for intento in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(WFS_AVISO.format(n=n, dia=dia, anio=anio),
                                                               headers={"User-Agent": "Mozilla/5.0"}), timeout=25) as r:
                f = [x["properties"] for x in json.loads(r.read())["features"]]
            break
        except Exception:  # noqa: BLE001
            if intento == 2:
                raise
            time.sleep(2)
    if not f:
        return None
    ini = min(datetime.fromisoformat(x["fech_ini"].replace("Z", "+00:00")) for x in f).astimezone(PERU).date()
    return {"even": str(int(f[0]["cod_even"])), "fecha": ini, "nivel": max(int(str(x["nivel"]).split()[-1]) for x in f)}


def buscar_avisos(base, hoy, conocidos=None):
    """(avisos de lluvia y helada vigentes `hoy`, último número visto, completo). Recorre números alrededor del último conocido.
    `conocidos` guarda lo ya leído de cada aviso (no cambia): las búsquedas siguientes solo preguntan por los nuevos."""
    fallos, vistos = [], {}
    conocidos = {} if conocidos is None else conocidos

    def uno(n):
        try:
            if (hoy.year, n) not in conocidos:
                w = _mapa(n, 1, hoy.year)
                if not w:
                    return n, None   # todavía no existe: se vuelve a preguntar la próxima vez
                conocidos[(hoy.year, n)] = w
            return n, conocidos[(hoy.year, n)]
        except Exception:  # noqa: BLE001
            fallos.append(n)
            return n, None

    desde = max(1, base - 8)
    with ThreadPoolExecutor(4) as ex:
        while desde < base + 60:
            bloque = dict(ex.map(uno, range(desde, desde + 12)))
            vistos.update({n: w for n, w in bloque.items() if w})
            if not any(bloque.values()) and not fallos:
                break
            desde += 12
    vigentes = []
    for n, w in sorted(vistos.items()):
        pel, k = EVENTOS.get(w["even"]), (hoy - w["fecha"]).days + 1
        if not pel or not 1 <= k <= 10:
            continue
        if k > 1:
            try:
                w = _mapa(n, k, hoy.year)
            except Exception:  # noqa: BLE001
                fallos.append(n)
                continue
            if not w or w["fecha"] != hoy:
                continue
        vigentes.append({"peligro": pel, "numero": n, "dia": k, "anio": hoy.year, "nivel": w["nivel"], "fecha": str(hoy)})
    return vigentes, max(vistos, default=base), not fallos


@st.cache_resource
def memoria():
    return {"lista": None, "dia": None, "ultimo": 0, "visto": 0, "hilo": None, "conocidos": {}}


def avisos_de_la_app(base, espera_s=6):
    """Lo último que halló la app para hoy (None si aún no hay). La consulta corre aparte: no frena la página."""
    m, hoy = memoria(), datetime.now(PERU).date()

    def consultar():
        lista, visto, completo = buscar_avisos(max(base, m["visto"]), hoy, m["conocidos"])
        if completo or lista:
            m.update(lista=lista, dia=str(hoy), visto=visto)
        m["ultimo"] = time.time() if completo else time.time() - CADA_S + REINTENTO_S

    if (time.time() - m["ultimo"] > CADA_S or m["dia"] != str(hoy)) and not (m["hilo"] and m["hilo"].is_alive()):
        if time.time() - m["ultimo"] > REINTENTO_S:
            m["hilo"] = threading.Thread(target=consultar, daemon=True)
            m["hilo"].start()
            if m["dia"] != str(hoy):
                m["hilo"].join(espera_s)
    return m["lista"] if m["dia"] == str(hoy) else None


def poner_avisos(html):
    """Escribe en la página los avisos vigentes hallados por la app; si no los tiene, deja solo los de HOY que trajo la PC."""
    m = re.search(r'"avzonas":(\[[^\]]*\])', html)
    if not m:
        return html
    de_la_pc = json.loads(m[1])
    numeros = [a["numero"] for a in de_la_pc] + [int(x) for x in re.findall(r'"(?:lluvia|helada)-(\d+)"', html)]
    try:
        lista = avisos_de_la_app(max(numeros, default=450))
    except Exception:  # noqa: BLE001
        lista = None
    if lista is None:
        lista = [a for a in de_la_pc if a.get("fecha") == str(datetime.now(PERU).date())]
    return html[:m.start(1)] + json.dumps(lista) + html[m.end(1):]


def sincronizar():
    """Copia el logo y las imágenes de evolución en tierra de salida/ a static/ cuando hay versiones nuevas."""
    for sub in ("img", "evolucion", "capas", "exposicion"):
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
    # hora de la última revisión automática (static/revisado.json se sube cada hora aunque los datos no cambien)
    rev = STATIC / "revisado.json"
    if rev.exists():
        html = html.replace('"generado":"', '"revisado":"' + json.loads(rev.read_text(encoding="utf-8"))["revisado"] + '","generado":"', 1)
    html = html.replace('"evolucion/', '"app/static/evolucion/').replace('"capas/', '"app/static/capas/').replace('"exposicion/', '"app/static/exposicion/')
    return poner_avisos(html)


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
