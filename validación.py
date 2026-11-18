"""
validacion.py — Reglas duras de Solaris.

Sin dependencias externas ni llamadas a LLM. Cada función es determinista
y se puede probar sin tocar la API.
"""

import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date

MIN_PALABRAS = 110
MAX_PALABRAS = 150
MAX_HOOK_PALABRAS = 15
MAX_CITA_PALABRAS = 20

# Léxico de tono (sin acentos; la comparación ignora acentos y mayúsculas)
LEXICO_PROHIBIDO = [
    "historico", "revolucionario", "brutal", "definitivo", "epico",
    "explosivo", "bomba", "sin precedentes", "es el momento de",
    "el timing es perfecto", "nadie lo vio venir", "todo cambia",
    "increible", "impactante",
]

# Temas excluidos por brand safety
TEMAS_BLOQUEADOS = [
    "casino", "apuesta", "apuestas", "memecoin", "trading",
    "academia de trading", "ganancias garantizadas", "multinivel",
    "get rich", "ponzi",
]

# Términos en inglés que deben estar en el glosario si aparecen en el guion
TERMINOS_EN = [
    "Series A", "Series B", "Series C", "seed", "unicorn", "IPO", "SPAC",
    "stablecoin", "burn rate", "valuation", "layoff", "bellwether",
    "CAPEX", "open source", "startup",
]

CAMPOS_REQUERIDOS = ["estado", "hook", "beats", "cta_ctw", "claims",
                     "fuentes", "glosario", "palabras_guion"]


@dataclass
class Resultado:
    errores: list[str] = field(default_factory=list)
    advertencias: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errores


def normalizar(texto: str) -> str:
    """Minúsculas, sin acentos, espacios colapsados, comas decimales como punto."""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.lower().replace(",", ".")
    return re.sub(r"\s+", " ", texto).strip()


def contar_palabras(texto: str) -> int:
    return len(re.findall(r"\w+", texto))


def validar_guion(
    respuesta_raw: str,
    texto_fuente: str,
    calidad_texto: str,
    hoy: date,
) -> tuple[dict | None, Resultado]:
    """
    Valida la salida del redactor.

    Devuelve (guion, resultado). Si resultado.ok es False, el guion no debe
    avanzar y el pipeline toma el siguiente candidato.
    """
    res = Resultado()

    # 1. JSON parseable
    try:
        guion = json.loads(respuesta_raw)
    except json.JSONDecodeError as e:
        res.errores.append(f"JSON inválido: {e}")
        return None, res

    if not isinstance(guion, dict):
        res.errores.append("La respuesta no es un objeto JSON")
        return None, res

    # 2. Estructura y estado
    faltantes = [c for c in CAMPOS_REQUERIDOS if c not in guion]
    if faltantes:
        res.errores.append(f"Faltan campos: {', '.join(faltantes)}")
        return None, res

    if guion["estado"] != "ok":
        res.errores.append("El redactor reportó estado 'insuficiente'")
        return None, res

    fuente_norm = normalizar(texto_fuente)
    claims = guion["claims"]
    fuentes = guion["fuentes"]
    glosario = guion["glosario"]
    beats = guion["beats"]

    ids_claims = {c.get("id") for c in claims}
    ids_fuentes = {f.get("id") for f in fuentes}

    # 3. Fuentes: URL https y fecha válida no futura
    for f in fuentes:
        url = f.get("url", "")
        if not url.startswith("https://"):
            res.errores.append(f"URL no válida en fuente {f.get('id')}: {url}")
        try:
            fecha = date.fromisoformat(f.get("fecha", ""))
            if fecha > hoy:
                res.errores.append(f"Fecha futura en fuente {f.get('id')}")
        except ValueError:
            res.errores.append(f"Fecha inválida en fuente {f.get('id')}")

    # 4. Claims: fuente existente y cita literal dentro del texto fuente
    for c in claims:
        cid = c.get("id")
        if c.get("fuente_id") not in ids_fuentes:
            res.errores.append(f"Claim {cid} apunta a fuente inexistente")

        cita = c.get("cita_textual_corta", "")
        if not cita:
            res.errores.append(f"Claim {cid} sin cita_textual_corta")
            continue
        if contar_palabras(cita) > MAX_CITA_PALABRAS:
            res.errores.append(f"Cita del claim {cid} excede {MAX_CITA_PALABRAS} palabras")
        if normalizar(cita) not in fuente_norm:
            res.errores.append(f"Cita del claim {cid} no aparece literal en el texto fuente")

    # 5. Beats: claim_ids existentes
    texto_beats = []
    for i, b in enumerate(beats, 1):
        texto_beats.append(b.get("texto", ""))
        for cid in b.get("claim_ids", []):
            if cid not in ids_claims:
                res.errores.append(f"Beat {i} referencia claim inexistente: {cid}")

    # 6. Hook y CTA
    hook = guion["hook"]
    if contar_palabras(hook) > MAX_HOOK_PALABRAS:
        res.errores.append(f"Hook excede {MAX_HOOK_PALABRAS} palabras")
    cta = guion["cta_ctw"].strip()
    if not cta.endswith("?"):
        res.errores.append("El CTA debe ser una pregunta")

    # 7. Conteo de palabras del guion completo
    guion_texto = " ".join([hook, *texto_beats, cta])
    palabras = contar_palabras(guion_texto)
    if not (MIN_PALABRAS <= palabras <= MAX_PALABRAS):
        res.errores.append(f"Guion con {palabras} palabras; rango válido {MIN_PALABRAS}-{MAX_PALABRAS}")
    if abs(palabras - int(guion["palabras_guion"])) > 5:
        res.advertencias.append(
            f"palabras_guion declara {guion['palabras_guion']} pero se contaron {palabras}"
        )

    # 8. Cifras del guion deben existir en el texto fuente
    guion_norm = normalizar(guion_texto)
    for cifra in set(re.findall(r"\d+(?:\.\d+)?", guion_norm)):
        if cifra not in fuente_norm:
            res.errores.append(f"Cifra '{cifra}' del guion no aparece en el texto fuente")

    # 9. Léxico de tono y temas bloqueados
    for termino in LEXICO_PROHIBIDO:
        if re.search(rf"\b{re.escape(termino)}\b", guion_norm):
            res.errores.append(f"Léxico prohibido: '{termino}'")
    for tema in TEMAS_BLOQUEADOS:
        if re.search(rf"\b{re.escape(tema)}\b", guion_norm):
            res.errores.append(f"Tema bloqueado por brand safety: '{tema}'")

    # 10. Términos en inglés deben tener glosario
    glosario_terminos = {normalizar(g.get("termino_en", "")) for g in glosario}
    for termino in TERMINOS_EN:
        t = normalizar(termino)
        if re.search(rf"\b{re.escape(t)}\b", guion_norm) and t not in glosario_terminos:
            res.errores.append(f"Término '{termino}' sin entrada en glosario")

    # 11. Advertencia si la fuente era solo un resumen
    if calidad_texto == "resumen_limitado":
        res.advertencias.append("Fuente con resumen limitado; revisar cifras antes de aprobar")

    return (guion if res.ok else None), res


def combinar_semaforo(
    resultado_reglas: Resultado,
    auditoria: dict,
    ids_claims: set[str],
) -> str:
    """
    Combina reglas duras y auditor LLM en un semáforo final.

    Reglas duras con errores siempre dan rojo. Si el auditor no cubre
    todos los claims, también es rojo: no se acepta una auditoría parcial.
    """
    if not resultado_reglas.ok:
        return "rojo"

    auditados = {r.get("claim_id") for r in auditoria.get("resultados", [])}
    if not ids_claims.issubset(auditados):
        return "rojo"

    if auditoria.get("semaforo") == "rojo":
        return "rojo"
    if auditoria.get("semaforo") == "amarillo":
        return "amarillo"
    return "verde"


def construir_payload(guion: dict, semaforo: str, resultado: Resultado,
                      auditoria: dict, candidato: dict) -> dict:
    """Paquete que se envía por webhook a n8n. Nada se guarda en el repo."""
    return {
        "semaforo": semaforo,
        "guion": guion,
        "reporte": {
            "advertencias": resultado.advertencias,
            "auditor": auditoria,
        },
        "candidato": {
            "medio": candidato.get("medio"),
            "url": candidato.get("url"),
            "fecha": candidato.get("fecha"),
            "calidad_texto": candidato.get("calidad_texto"),
        },
    }
