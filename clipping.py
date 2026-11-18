"""
📱 Solaris — Clipping Automático
================================
Nodo de inteligencia para la nueva economía en México.

Corre cada mañana vía GitHub Actions. Los guiones no se guardan en el repo:
pasan en memoria hacia n8n, que los envía a Telegram para aprobación.
"""

import json
import os
import time
from datetime import date, datetime, timezone

import anthropic
import feedparser
import requests
import trafilatura

from validacion import combinar_semaforo, construir_payload, validar_guion


# ============================================================
# 🗞️ FUENTES
# ============================================================
FEEDS = {
    "El CEO": "https://elceo.com/feed/",
    "Forbes México": "https://forbes.com.mx/feed/",
    "Expansión": "https://expansion.mx/rss",
    "El Financiero Tech": "https://www.elfinanciero.com.mx/arc/outboundfeeds/rss/category/tech/",
    "Startupeable": "https://startupeable.com/feed/",
    "TechCrunch": "https://techcrunch.com/feed/",
    "Contxto": "https://contxto.com/feed/",
    "Bloomberg Línea": "https://bloomberglinea.com/arc/outboundfeeds/rss/",
    "Latitud": "https://latitud.com/blog/feed",
    "Rest of World": "https://restofworld.org/feed/",
    "CoinDesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "Axios Pro Rata": "https://www.axios.com/newsletters/pro-rata.rss",
    "The Hustle": "https://thehustle.co/feed/",
    "The Verge": "https://www.theverge.com/rss/index.xml",
    "Hacker News": "https://news.ycombinator.com/rss",
}

# ============================================================
# ⚙️ CONFIGURACIÓN
# ============================================================
HORAS_FILTRO = 12
CANDIDATOS_MAX = 3                       # Top candidatos que pasan el filtro
MODELO_REDACTOR = "claude-sonnet-4-5"
MODELO_AUDITOR = "claude-sonnet-4-5"     # Idealmente distinto al redactor
N8N_WEBHOOK_URL = os.environ["N8N_WEBHOOK_URL"]   # GitHub Secret

# ============================================================
# 📝 PROMPTS
# ============================================================
PROMPT_REDACTOR = """Eres el guionista de Solaris, un medio digital de inteligencia informativa sobre tecnología, negocios, startups e inversiones en México y Latinoamérica. Tu audiencia son solopreneurs, profesionales tech-curious e inversionistas principiantes. Tu trabajo es convertir UNA noticia en un guion corto para video vertical de 45 a 60 segundos.

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

Si "estado" es "insuficiente", los demás campos pueden ir vacíos, pero el JSON debe ser válido."""

PROMPT_AUDITOR = """Eres un auditor editorial de Solaris. Tu única función es verificar si cada afirmación de un guion está respaldada por el texto fuente. No redactas, no mejoras el estilo y no agregas contenido.

Para cada claim recibirás: el texto de la afirmación, el texto fuente completo y la cita_textual_corta propuesta por el redactor.

Evalúa cada claim con una de estas etiquetas:
- "soportado": el texto fuente afirma exactamente lo mismo, o lo afirma sin cambiar cifras, fechas, nombres ni sentido.
- "parcial": el texto fuente respalda una parte del claim, pero el claim agrega matices, extrapola o cambia un detalle menor.
- "no_soportado": el texto fuente no dice eso, lo contradice, o la cifra/fecha/nombre no aparece.

Reglas adicionales:
- Verifica que la cita_textual_corta existe literalmente en el texto fuente. Si no existe, marca "no_soportado" y explica.
- Verifica cada cifra, fecha, porcentaje y nombre propio uno por uno.
- No evalúes si la noticia es verdadera en el mundo real; evalúa solo si el texto fuente la respalda.
- Marca también como "tono_problematico" cualquier adjetivo o frase de opinión no sustentada por un hecho del texto fuente (lista de términos de riesgo: histórico, revolucionario, brutal, definitivo, épico, explosivo, bomba, sin precedentes, es el momento de, el timing es perfecto, nadie lo vio venir, todo cambia).

Responde EXCLUSIVAMENTE con un objeto JSON válido, sin texto adicional ni bloques de código markdown:

{
  "resultados": [
    {"claim_id": "c1", "veredicto": "soportado" | "parcial" | "no_soportado", "cita_verificada": true | false, "explicacion": "string breve"}
  ],
  "tono_problematico": [
    {"fragmento": "string", "motivo": "string breve"}
  ],
  "semaforo": "verde" | "amarillo" | "rojo"
}

Criterio de semáforo:
- "verde": todos los claims "soportado" y sin tono_problematico.
- "amarillo": uno o más claims "parcial" o tono_problematico, pero ningún "no_soportado".
- "rojo": uno o más claims "no_soportado" o cita_verificada en false."""

client = anthropic.Anthropic()


# ============================================================
# 📥 PASO 1: Leer noticias de los RSS
# ============================================================
def obtener_noticias() -> list[dict]:
    print("📡 Leyendo feeds RSS...")
    noticias = []
    limite = time.time() - HORAS_FILTRO * 3600

    for medio, url_feed in FEEDS.items():
        try:
            feed = feedparser.parse(url_feed)
            n_medio = 0
            for entry in feed.entries:
                fecha_pub = entry.get("published_parsed")
                if fecha_pub and time.mktime(fecha_pub) < limite:
                    continue
                noticias.append({
                    "medio": medio,
                    "titulo": entry.title,
                    "link": getattr(entry, "link", ""),
                    "fecha": getattr(entry, "published", "Sin fecha"),
                })
                n_medio += 1
            print(f"  ✅ {medio}: {n_medio} noticias")
        except Exception as e:
            print(f"  ⚠️  {medio}: error al leer ({e})")

    print(f"\n📚 Total: {len(noticias)} noticias recientes")
    return noticias


# ============================================================
# 🔎 PASO 2: Filtro (por ahora, primeras N; ver nota abajo)
# ============================================================
def filtrar(noticias: list[dict]) -> list[dict]:
    """
    Placeholder: devuelve las primeras CANDIDATOS_MAX noticias.
    El filtro real (listas negras, score, dedupe) se escribe después.
    """
    return noticias[:CANDIDATOS_MAX]


# ============================================================
# 🌐 PASO 3: Texto completo del artículo
# ============================================================
def extraer_texto(url: str) -> tuple[str, str]:
    """Devuelve (texto, calidad). Calidad: 'completo' o 'resumen_limitado'."""
    html = trafilatura.fetch_url(url)
    texto = trafilatura.extract(html) if html else None
    if not texto:
        return "", "sin_texto"
    palabras = len(texto.split())
    return texto, ("completo" if palabras > 300 else "resumen_limitado")


# ============================================================
# 🤖 PASO 4: Llamadas a la API
# ============================================================
def llamar_redactor(candidato: dict, texto: str, calidad: str,
                    correcciones: list[str] | None) -> str:
    user = f"""NOTICIA CANDIDATA
Medio: {candidato['medio']}
URL: {candidato['link']}
Fecha de publicación: {candidato['fecha']}
Calidad del texto: {calidad}

TEXTO FUENTE:
\"\"\"
{texto}
\"\"\"

Genera el guion según las reglas del sistema. Usa como fuente_id "f1" y la URL indicada arriba."""

    if correcciones:
        user += "\n\nCORRECCIONES REQUERIDAS (corrige y responde de nuevo):\n- " + "\n- ".join(correcciones)

    r = client.messages.create(
        model=MODELO_REDACTOR,
        max_tokens=4000,
        system=PROMPT_REDACTOR,
        messages=[{"role": "user", "content": user}],
    )
    return r.content[0].text


def llamar_auditor(texto: str, guion: dict) -> dict:
    user = f"""TEXTO FUENTE:
\"\"\"
{texto}
\"\"\"

GUION A AUDITAR (JSON del redactor):
{json.dumps(guion, ensure_ascii=False)}

Audita cada claim y el tono del guion según las reglas del sistema."""

    r = client.messages.create(
        model=MODELO_AUDITOR,
        max_tokens=2000,
        system=PROMPT_AUDITOR,
        messages=[{"role": "user", "content": user}],
    )
    try:
        return json.loads(r.content[0].text)
    except json.JSONDecodeError:
        return {"resultados": [], "tono_problematico": [], "semaforo": "rojo"}


# ============================================================
# 📤 PASO 5: Envío a n8n (en memoria, sin archivos)
# ============================================================
def enviar_a_n8n(payload: dict, intentos: int = 3) -> None:
    for i in range(1, intentos + 1):
        try:
            r = requests.post(N8N_WEBHOOK_URL, json=payload, timeout=20)
            r.raise_for_status()
            print("✅ Enviado a n8n")
            return
        except requests.RequestException as e:
            print(f"  ⚠️  Intento {i} fallido: {e}")
            time.sleep(5)
    raise RuntimeError("n8n no respondió tras reintentos")


# ============================================================
# 🔁 PROCESAMIENTO
# ============================================================
def procesar_candidatos(candidatos: list[dict]) -> bool:
    for c in candidatos:
        print(f"\n🔎 Procesando: {c['titulo']}")
        texto, calidad = extraer_texto(c["link"])
        if not texto:
            print("  Sin texto extraíble, siguiente.")
            continue

        # Redacción + reglas duras, con un reintento
        guion, reglas, correcciones = None, None, None
        for _ in range(2):
            raw = llamar_redactor(c, texto, calidad, correcciones)
            guion, reglas = validar_guion(raw, texto, calidad, date.today())
            if reglas.ok:
                break
            correcciones = reglas.errores
        if not reglas.ok:
            print(f"  ❌ Reglas duras: {reglas.errores}")
            continue

        # Auditoría LLM + semáforo combinado
        auditoria = llamar_auditor(texto, guion)
        ids = {cl["id"] for cl in guion["claims"]}
        semaforo = combinar_semaforo(reglas, auditoria, ids)
        if semaforo == "rojo":
            print("  ❌ Auditor: rojo")
            continue

        payload = construir_payload(guion, semaforo, reglas, auditoria, c)
        enviar_a_n8n(payload)
        return True

    print("\nNingún candidato pasó la validación. No se publica nada hoy.")
    return False


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
        print("❌ Sin noticias. Revisa conexión o feeds.")
        return

    procesar_candidatos(filtrar(noticias))


if __name__ == "__main__":
    main()

