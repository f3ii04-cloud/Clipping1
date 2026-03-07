"""
📱 TikTok News Clipping Automático
====================================
Este script lee RSS de tus medios favoritos,
selecciona las noticias más relevantes y genera
un clipping listo para usar con tu LLM de redacción.

Autor: tú (con ayuda de Claude 😄)
"""

import feedparser       # Lee feeds RSS de los medios
import anthropic         # Conecta con Claude API
import json
import os
from datetime import datetime
from pathlib import Path


# ============================================================
# 🗞️ CONFIGURA TUS FUENTES AQUÍ
# Agrega o quita medios según tus preferencias
# ============================================================
FEEDS = {
    # México
    "El Universal":      "http://www.eluniversal.com.mx/rss/mexico.xml",
    "Reforma":           "https://www.reforma.com/rss/nacional.xml",
    "El Financiero" :    "https://www.elfinanciero.com.mx/arc/outboundfeeds/rss/?outputType=xml" ,
    "El País":           "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/mexico/portada",
    
    # Internacionales
    "BBC Mundo":         "https://feeds.bbci.co.uk/mundo/rss.xml",
    "Reuters":           "https://feeds.reuters.com/reuters/topNews",
    "NYT":               "https://rss.nytimes.com/services/xml/rss/nyt/es.xml",
    # Añade los que uses tú:
    # "Medio Custom": "https://url-del-rss.com/feed",
}

# ============================================================
# ⚙️ CONFIGURACIÓN GENERAL
# ============================================================
NOTICIAS_POR_FUENTE = 3      # Cuántas noticias leer de cada medio
NOTICIAS_FINALES = 6         # Cuántas incluir en el clipping final
CARPETA_SALIDA = "clippings"  # Carpeta donde se guardan los archivos


# ============================================================
# 📥 PASO 1: Leer las noticias de los RSS
# ============================================================
from datetime import datetime, timezone
import time

def obtener_noticias():
    """
    Recorre cada feed RSS y extrae solo las noticias
    publicadas en las últimas 12 horas.
    """
    print("📡 Leyendo feeds RSS...")
    todas_las_noticias = []
    
    # Calculamos el límite: hace 12 horas en UTC
    ahora = datetime.now(timezone.utc)
    limite = ahora.timestamp() - (12 * 60 * 60)  # 12h en segundos

    for nombre_medio, url_feed in FEEDS.items():
        noticias_medio = 0
        try:
            feed = feedparser.parse(url_feed)

            for entry in feed.entries:
                # Convertimos la fecha de publicación a timestamp comparable
                fecha_pub = entry.get('published_parsed')
                
                if fecha_pub:
                    fecha_timestamp = time.mktime(fecha_pub)
                    if fecha_timestamp < limite:
                        continue  # ← noticia antigua, la saltamos
                
                resumen = getattr(entry, 'summary', entry.title)
                resumen_limpio = resumen.replace('<p>', '').replace('</p>', '').strip()

                todas_las_noticias.append({
                    "medio": nombre_medio,
                    "titulo": entry.title,
                    "resumen": resumen_limpio[:300],
                    "link": getattr(entry, 'link', ''),
                    "fecha": getattr(entry, 'published', 'Sin fecha'),
                })
                noticias_medio += 1

            print(f"  ✅ {nombre_medio}: {noticias_medio} noticias (últimas 12h)")

        except Exception as e:
            print(f"  ⚠️  {nombre_medio}: Error al leer ({e})")

    print(f"\n📚 Total noticias recientes: {len(todas_las_noticias)}")
    return todas_las_noticias


# ============================================================
# 🤖 PASO 2: Claude selecciona y analiza las mejores
# ============================================================
def generar_clipping(noticias: list) -> str:
    """
    Envía todas las noticias a Claude y le pide que seleccione
    las más relevantes con un análisis orientado a TikTok.
    """
    print("\n🤖 Claude analizando noticias...")

    # Formateamos las noticias como texto para el prompt
    noticias_texto = ""
    for i, n in enumerate(noticias, 1):
        noticias_texto += f"""
[{i}] {n['medio'].upper()}
Título: {n['titulo']}
Resumen: {n['resumen']}
Link: {n['link']}
---"""

    # El prompt que le damos a Claude
    prompt = f"""Eres el editor de un canal de TikTok de noticias en español.
Tu trabajo es revisar una lista de noticias del día y seleccionar las {NOTICIAS_FINALES} más importantes.

CRITERIOS DE SELECCIÓN (en orden de prioridad):
1. Impacto real en la vida cotidiana de las personas
2. Potencial de engagement en redes sociales (sorpresa, emoción, debate)
3. Actualidad e inmediatez
4. Variedad temática (evita seleccionar 5 noticias del mismo tema)
5. Variedad mediática ( evita seleccionar 5 noticias de la misma fuente)

Para cada noticia seleccionada, escribe:

## [NÚMERO]. [TÍTULO ATRACTIVO PARA TIKTOK]
**Medio:** [nombre del medio]
**Por qué importa:** [1-2 frases explicando el impacto real]
**Ángulo TikTok:** [cómo enfocarías esto en un video de 60 segundos]
**Gancho de apertura:** [primera frase del video que engancharía al espectador]
**Link:** [URL]

---

Al final, añade una sección:
## 🎯 ORDEN SUGERIDO DE PUBLICACIÓN
[Lista del 1 al {NOTICIAS_FINALES} con el orden recomendado y por qué]

NOTICIAS DEL DÍA:
{noticias_texto}
"""

    # Llamada a la API de Claude
    client = anthropic.Anthropic()  # Usa automáticamente ANTHROPIC_API_KEY del entorno
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.content[0].text


# ============================================================
# 💾 PASO 3: Guardar el resultado en un archivo
# ============================================================
def guardar_clipping(contenido: str) -> str:
    """
    Guarda el clipping en un archivo .md con la fecha de hoy.
    Markdown es perfecto porque lo puedes abrir en cualquier editor.
    """
    # Crear carpeta si no existe
    Path(CARPETA_SALIDA).mkdir(exist_ok=True)

    # Nombre del archivo con fecha y hora
    fecha_hoy = datetime.now().strftime("%Y-%m-%d_%H%M")
    nombre_archivo = f"{CARPETA_SALIDA}/clipping_{fecha_hoy}.md"

    # Encabezado del documento
    encabezado = f"""# 📱 Clipping TikTok — {datetime.now().strftime("%d/%m/%Y %H:%M")}
*Generado automáticamente*

---

"""

    with open(nombre_archivo, "w", encoding="utf-8") as f:
        f.write(encabezado + contenido)

    return nombre_archivo


# ============================================================
# 🚀 FUNCIÓN PRINCIPAL
# ============================================================
def main():
    print("=" * 50)
    print("📱 TIKTOK NEWS CLIPPING")
    print(f"   {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 50)

    # 1. Recopilar noticias
    noticias = obtener_noticias()

    if not noticias:
        print("❌ No se pudieron obtener noticias. Revisa tu conexión y los URLs de los feeds.")
        return

    # 2. Generar clipping con Claude
    clipping = generar_clipping(noticias)

    # 3. Guardar en archivo
    archivo = guardar_clipping(clipping)

    # 4. Mostrar resultado en pantalla
    print("\n" + "=" * 50)
    print(clipping)
    print("=" * 50)
    print(f"\n✅ Clipping guardado en: {archivo}")
    print("🎬 ¡Listo para pasar a tu LLM de redacción!")


if __name__ == "__main__":
    main()
