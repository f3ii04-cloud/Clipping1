"""
📱 TikTok News Clipping Automático
====================================
Este script lee RSS de tus medios favoritos,
selecciona las noticias más relevantes y genera
un clipping listo para estar informada.
"""

import feedparser
import anthropic
import re
import calendar
import time
import os
from datetime import datetime, timezone
from pathlib import Path


# ============================================================
# 🗞️ CONFIGURA TUS FUENTES AQUÍ
# ============================================================
FEEDS = {
    "NYT":           "https://rss.nytimes.com/services/xml/rss/nyt/es.xml",
    "BBC Mundo":     "https://feeds.bbci.co.uk/mundo/rss.xml",
    "Reuters":       "https://feeds.reuters.com/reuters/topNews",
    "El País":       "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/mexico/portada",
    "El Financiero": "https://www.elfinanciero.com.mx/arc/outboundfeeds/rss/?outputType=xml",
}

# ============================================================
# ⚙️ CONFIGURACIÓN GENERAL
# ============================================================
NOTICIAS_POR_FUENTE = 3
NOTICIAS_FINALES    = 6
CARPETA_SALIDA      = "clippings"


# ============================================================
# 📥 PASO 1: Leer las noticias de los RSS
# ============================================================
def obtener_noticias():
    """
    Recorre cada feed RSS y extrae las noticias
    publicadas en las últimas 12 horas.
    """
    print("📡 Leyendo feeds RSS...")
    todas_las_noticias = []

    ahora = datetime.now(timezone.utc)
    limite = ahora.timestamp() - (12 * 60 * 60)

    for nombre_medio, url_feed in FEEDS.items():
        noticias_medio = 0
        try:
            feed = feedparser.parse(url_feed)

            for entry in feed.entries:
                if noticias_medio >= NOTICIAS_POR_FUENTE:  # ✅ indentación correcta
                    break

                fecha_pub = entry.get('published_parsed')
                if fecha_pub:
                    fecha_timestamp = calendar.timegm(fecha_pub)  # ✅ ya no está en el loop
                    if fecha_timestamp < limite:
                        continue

                resumen = getattr(entry, 'summary', entry.title)
                resumen_limpio = re.sub(r'<[^>]+>', '', resumen).strip()  # ✅ ya no está en el loop

                todas_las_noticias.append({
                    "medio":   nombre_medio,
                    "titulo":  entry.title,
                    "resumen": resumen_limpio[:300],
                    "link":    getattr(entry, 'link', ''),
                    "fecha":   getattr(entry, 'published', 'Sin fecha'),
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
    Envía las noticias a Claude y genera el clipping editorial.
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

    prompt = f"""Eres la jefa de redacción de Solaris, un medio digital para mexicanos 
de 18 a 34 años escépticos de los medios tradicionales. Tu voz es la 
de un "amigo informado": directa, transparente y sin relleno.

Tu tarea es analizar la siguiente lista de noticias del día y construir 
un reporte editorial consolidado por tema, NO por medio.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITERIOS DE SELECCIÓN (en orden de prioridad):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. PESO NOTICIOSO ("De ocho columnas"): Prioriza los temas que 
   aparecen en 2 o más fuentes distintas. Si un tema domina la agenda 
   de varios medios, es la noticia del día.

2. IMPACTO DIRECTO EN LA AUDIENCIA SOLARIS: ¿Afecta el bolsillo, 
   la seguridad, el trabajo o la vida cotidiana de un mexicano de 
   18-34 años? Si la respuesta es sí, sube en la lista.

3. CATEGORÍA EDITORIAL (selecciona al menos una noticia por 
   categoría, en este orden de jerarquía):
   - 🔴 Categoría 1 — Política / Seguridad MX
   - 🟡 Categoría 2 — Economía / Mundo  
   - 🟢 Categoría 3 — Estilo de Vida / Tech / Cultura

4. COBERTURA MÚLTIPLE: Si dos o más fuentes cubren el mismo tema, 
   consolídalas en un solo reporte. No repitas el mismo hecho dos 
   veces por venir de medios distintos.

5. INDEPENDENCIA: Da preferencia a temas que los medios 
   tradicionales cubren de forma superficial o que tienen un ángulo 
   que la audiencia joven necesita escuchar sin filtro político.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FORMATO DE SALIDA:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Selecciona las {NOTICIAS_FINALES} noticias más importantes y 
presenta cada una así:

---

## [CATEGORÍA EMOJI] NOTICIA [NÚMERO]: [TÍTULO DIRECTO Y SIN CLICKBAIT]

**Peso en la agenda:** [¿Cuántos medios lo cubren?]

**Qué pasó (en 2 líneas):** [Resumen de los hechos duros. Sin adjetivos. Solo datos.]

**Por qué le importa a tu audiencia:** [1 frase conectando el hecho
con la vida real de un mexicano de 18-34 años]

**Lo que dicen las fuentes:** [Si hay 2+ fuentes, anota si coinciden
o si hay matices distintos]

**Gancho de apertura para Solaris:** ["Oigan, esto está pasando..."
— primera frase en tono cercano para abrir el video]

**Fuentes consultadas:** [Lista de links]

---

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REGLAS EDITORIALES ADICIONALES:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- Si una noticia solo aparece en UNA fuente y no cumple criterios 
  1 o 2, descártala salvo que sea excepcionalmente relevante para 
  la Categoría 3.
- Nunca repitas una noticia con distinto encabezado por venir de 
  medios diferentes. Consolida.
- El tono del campo "Gancho de apertura" debe sonar como Fer 
  Solaris: cercano, sin alarmar, sin sensacionalismo.
- Máximo 2 noticias de la misma categoría en la selección final, 
  salvo que el peso noticioso lo justifique.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NOTICIAS DEL DÍA PARA ANALIZAR:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{noticias_texto}
"""

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.content[0].text


# ============================================================
# 💾 PASO 3: Guardar el resultado
# ============================================================
def guardar_clipping(contenido: str) -> str:
    """
    Guarda el clipping en un archivo .md con fecha y hora.
    """
    Path(CARPETA_SALIDA).mkdir(exist_ok=True)

    fecha_hoy = datetime.now().strftime("%Y-%m-%d_%H%M")
    nombre_archivo = f"{CARPETA_SALIDA}/clipping_{fecha_hoy}.md"

    encabezado = f"""# 📱 Clipping Solaris — {datetime.now().strftime("%d/%m/%Y %H:%M")}
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
    print("📱 SOLARIS — NEWS CLIPPING")
    print(f"   {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 50)

    noticias = obtener_noticias()

    if not noticias:
        print("❌ No se pudieron obtener noticias.")
        return

    if len(noticias) < 3:                    # ✅ aquí sí existe la variable
        print("⚠️  Menos de 3 noticias encontradas.")
        return

    clipping = generar_clipping(noticias)
    archivo  = guardar_clipping(clipping)

    print("\n" + "=" * 50)
    print(clipping)
    print("=" * 50)
    print(f"\n✅ Clipping guardado en: {archivo}")
    print("🎬 ¡Listo para pasar a tu LLM de redacción!")


if __name__ == "__main__":
    main()
