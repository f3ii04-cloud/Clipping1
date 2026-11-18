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
    "El CEO": "https://elceo.com/feed/",
    "Forbes México": "https://forbes.com.mx/feed/",
    "Expansión": "https://expansion.mx/rss",
    "El Financiero Tech": "https://www.elfinanciero.com.mx/arc/outboundfeeds/rss/category/tech/",
    "Startupeable": "https://startupeable.com/feed/",
    
    # Internacional con enfoque Latam / VC
    "TechCrunch": "https://techcrunch.com/feed/",
    "Contxto": "https://contxto.com/feed/",
    "Bloomberg Línea": "https://bloomberglinea.com/arc/outboundfeeds/rss/",
    "Latitud": "https://latitud.com/blog/feed",
    "Rest of World": "https://restofworld.org/feed/",
    
    # Finanzas, Crypto y Global
    "CoinDesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "Axios Pro Rata": "https://www.axios.com/newsletters/pro-rata.rss",
    "The Hustle": "https://thehustle.co/feed/",
    "The Verge": "https://www.theverge.com/rss/index.xml",
    "Hacker News": "https://news.ycombinator.com/rss"
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
    print("\n🤖 Claude analizando noticias...")

    noticias_texto = ""
    for i, n in enumerate(noticias, 1):
        noticias_texto += f"""
[{i}] {n['medio'].upper()}
Título: {n['titulo']}
Resumen: {n['resumen']}
Link: {n['link']}
---"""

    prompt = f"""Eres el guionista de Solaris, un medio digital de inteligencia informativa sobre tecnología, negocios, startups e inversiones en México y Latinoamérica. Tu audiencia son solopreneurs, profesionales tech-curious e inversionistas principiantes. Tu trabajo es convertir UNA noticia en un guion corto para video vertical de 45 a 60 segundos.

REGLAS DE CONTENIDO (no negociables):
1. Usa únicamente hechos presentes en el TEXTO FUENTE que se te proporciona. No agregues datos de tu conocimiento propio ni de fuentes externas.
2. Cada cifra, fecha, nombre propio, porcentaje o afirmación factual del guion debe corresponder a un "claim" en el JSON, y cada claim debe apuntar a una fuente.
3. Prohibido el sensacionalismo. No uses adjetivos fuertes ("histórico", "revolucionario", "brutal", "definitivo", "explosivo", "bomba", "épico", "es el momento de", "el timing es perfecto") salvo que el texto fuente use ese mismo término Y lo respalde con un dato. Prefiere verbos y datos concretos.
4. No opines en nombre de Solaris ni de Fer. Presenta lo que dicen los hechos, lo que afirman las fuentes y lo que no se sabe. Si hay una interpretación, atribúyela explícitamente (por ejemplo: "según el reporte de X...", "analistas citados por Y sostienen...").
5. Si el texto fuente tiene un dato incierto o contradictorio, dilo. No lo resuelvas a favor de una versión.
6. Prohibido el chisme: no cubras vida privada de personas salvo que tenga impacto legal o institucional documentado.
7. Prohibido describir víctimas de violencia de forma morbosa o que incite al pánico.
8. Si el texto fuente es insuficiente para un guion sólido (menos de ~150 palabras de contenido informativo, o solo un titular), responde con "estado": "insuficiente" y no generes guion.

REGLAS DE FORMA:
- Idioma: español neutro con tono semi-formal, directo y cercano. Sin lenguaje corporativo frío.
- Guion de 110 a 150 palabras en total.
- Estructura: "hook" (máximo 15 palabras, primera frase que detiene el scroll; puede ser una pregunta o un dato concreto del texto fuente, nunca una afirmación no verificada), 3 "beats" (desarrollo: qué pasó, por qué importa, qué dicen las fuentes o qué falta saber), y "cta_ctw" (una pregunta abierta para comentarios, relacionada con el tema, sin inducir una respuesta).
- Cada término en inglés (Series A, unicorn, seed, burn rate, IPO, SPAC, stablecoin, etc.) debe explicarse en español dentro del guion o en "glosario".
- No menciones marcas de apuestas, casinos, criptomonedas memecoin, trading sin respaldo, partidos políticos en campaña ni productos sin relación con la noticia.

FORMATO DE SALIDA:
Responde EXCLUSIVAMENTE con un objeto JSON válido. Sin texto antes ni después, sin bloques de código markdown. Esquema:

{
  "estado": "ok" | "insuficiente",
  "hook": "string, máximo 15 palabras",
  "beats": [
    {"texto": "string", "claim_ids": ["c1"]}
  ],
  "cta_ctw": "string, una pregunta",
  "claims": [
    {"id": "c1", "texto": "afirmación factual exacta del guion", "fuente_id": "f1", "cita_textual_corta": "fragmento literal del texto fuente, máximo 20 palabras, que respalda el claim"}
  ],
  "fuentes": [
    {"id": "f1", "medio": "string", "url": "string", "fecha": "YYYY-MM-DD"}
  ],
  "glosario": [
    {"termino_en": "string", "explicacion_es": "string"}
  ],
  "palabras_guion": 0
}

Si "estado" es "insuficiente", los demás campos pueden ir vacíos, pero el JSON debe ser válido.

"""

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text

    except Exception as e:
        import traceback
        print("❌ Error al llamar a Claude:")
        print(type(e).__name__, str(e))
        traceback.print_exc()
        raise

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
