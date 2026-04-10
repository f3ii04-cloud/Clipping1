"""
📱 Solaris — Clipping Automático
==================================
Nodo de inteligencia para la nueva economía en México.
Tecnología, finanzas y startups en cápsulas de alto impacto.

Corre automáticamente cada mañana vía GitHub Actions.
"""

import feedparser
import anthropic
import time
from datetime import datetime, timezone
from pathlib import Path


# ============================================================
# 🗞️ FUENTES — Tecnología, Finanzas y Startups
# ============================================================
FEEDS = {
    # México - Negocios y Tech
    "El CEO":               "https://elceo.com/feed/",
    "Forbes México":        "https://www.forbes.com.mx/feed/",
    "Expansión":            "https://expansion.mx/rss",
    "El Financiero Tech":   "https://www.elfinanciero.com.mx/arc/outboundfeeds/rss/category/tech/",
    "Startupeable":         "https://startupeable.com/feed/",
    # Internacional con enfoque Latam
    "TechCrunch":           "https://techcrunch.com/feed/",
    "Contxto":              "https://contxto.com/feed/",
    "Bloomberg Línea":      "https://bloomberglinea.com/arc/outboundfeeds/rss/",
    # Finanzas y crypto
    "CoinDesk":             "https://www.coindesk.com/arc/outboundfeeds/rss/",
}

# ============================================================
# ⚙️ CONFIGURACIÓN
# ============================================================
NOTICIAS_POR_FUENTE = 5      # Cuántas noticias leer de cada medio
NOTICIAS_FINALES = 5         # Cuántas incluir en el clipping final
HORAS_FILTRO = 12            # Solo noticias de las últimas N horas
CARPETA_SALIDA = "clippings"  # Carpeta donde se guardan los archivos


# ============================================================
# 📥 PASO 1: Leer las noticias de los RSS
# ============================================================
def obtener_noticias():
    """
    Recorre cada feed RSS y extrae solo las noticias
    publicadas en las últimas HORAS_FILTRO horas.
    """
    print("📡 Leyendo feeds RSS...")
    todas_las_noticias = []

    ahora = datetime.now(timezone.utc)
    limite = ahora.timestamp() - (HORAS_FILTRO * 60 * 60)

    for nombre_medio, url_feed in FEEDS.items():
        noticias_medio = 0
        try:
            feed = feedparser.parse(url_feed)

            for entry in feed.entries:
                # Filtro por fecha
                fecha_pub = entry.get('published_parsed')
                if fecha_pub:
                    if time.mktime(fecha_pub) < limite:
                        continue

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

            print(f"  ✅ {nombre_medio}: {noticias_medio} noticias (últimas {HORAS_FILTRO}h)")

        except Exception as e:
            print(f"  ⚠️  {nombre_medio}: Error al leer ({e})")

    print(f"\n📚 Total noticias recientes: {len(todas_las_noticias)}")
    return todas_las_noticias


# ============================================================
# 🤖 PASO 2: Claude selecciona y analiza las mejores
# ============================================================
def generar_clipping(noticias: list) -> str:
    """
    Envía las noticias a Claude con el perfil editorial de Solaris
    para que seleccione y analice las más relevantes.
    """
    print("\n🤖 Claude analizando noticias...")

    noticias_texto = ""
    for i, n in enumerate(noticias, 1):
        noticias_texto += f"""
[{i}] {n['medio'].upper()}
Título: {n['titulo']}
Resumen: {n['resumen']}
Link: {n['link']}
---"""

    prompt = f"""Eres el editor de Solaris, un medio digital especializado en tecnología, 
finanzas y startups para la nueva economía en México y Latinoamérica.

Tu trabajo es revisar una lista de noticias y seleccionar las {NOTICIAS_FINALES} más 
relevantes para una audiencia de founders, inversionistas, profesionales tech y 
entusiastas de la innovación.

CRITERIOS DE SELECCIÓN (en orden de prioridad):
1. Impacto directo en el ecosistema de startups, VC o tecnología en México/Latam
2. Innovación genuina: nuevas rondas de inversión, productos, regulaciones o tendencias
3. Conexión entre capital global y talento nacional mexicano
4. Potencial de debate o sorpresa en una audiencia sofisticada
5. Variedad temática (tech, finanzas, startups, política de innovación)
6. Variedad mediática (evita seleccionar noticias de la misma fuente)

DESCARTA noticias sobre:
- Política electoral o nota roja
- Entretenimiento o deportes
- Cualquier tema sin conexión con tecnología, finanzas o innovación

Para cada noticia seleccionada escribe:

## [NÚMERO]. [TÍTULO ATRACTIVO PARA TIKTOK]
**Medio:** [nombre del medio]
**Por qué importa:** [1-2 frases sobre el impacto en el ecosistema mexicano]
**Ángulo TikTok:** [cómo enfocarías esto en 60 segundos para una audiencia tech]
**Gancho de apertura:** [primera frase del video que engancharía al espectador]
**Link:** [URL]

---

Al final añade:
## 🎯 ORDEN SUGERIDO DE PUBLICACIÓN
[Lista del 1 al {NOTICIAS_FINALES} con el orden recomendado y por qué]

NOTICIAS DEL DÍA:
{noticias_texto}
"""

    client = anthropic.Anthropic()
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
    """
    Path(CARPETA_SALIDA).mkdir(exist_ok=True)

    fecha_hoy = datetime.now().strftime("%Y-%m-%d_%H%M")
    nombre_archivo = f"{CARPETA_SALIDA}/clipping_{fecha_hoy}.md"

    encabezado = f"""# 📱 Solaris Clipping — {datetime.now().strftime("%d/%m/%Y %H:%M")}
*Tecnología · Finanzas · Startups · Nueva economía México*

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
    print("📱 SOLARIS — CLIPPING DIARIO")
    print(f"   {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 50)

    noticias = obtener_noticias()

    if not noticias:
        print("❌ No se pudieron obtener noticias. Revisa tu conexión y los URLs de los feeds.")
        return

    clipping = generar_clipping(noticias)
    archivo = guardar_clipping(clipping)

    print("\n" + "=" * 50)
    print(clipping)
    print("=" * 50)
    print(f"\n✅ Clipping guardado en: {archivo}")
    print("🎬 ¡Listo para Solaris!")


if __name__ == "__main__":
    main()
