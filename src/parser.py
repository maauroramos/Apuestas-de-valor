"""
Parser de tickets de apuestas en texto libre.
Maneja formato argentino (puntos como miles, coma como decimal).
"""

import re
from datetime import datetime, date


def parsear_numero(texto: str):
    """
    Convierte un número en cualquier formato a float.
    Soporta: 6.000,00 (AR) | 6,000.00 (US) | 1.85 | 1,85
    """
    texto = texto.strip().replace(" ", "")
    # Formato argentino: 6.000,00 o 23.400,00
    if re.match(r'^\d{1,3}(\.\d{3})+(,\d+)?$', texto):
        texto = texto.replace(".", "").replace(",", ".")
    elif re.match(r'^\d+,\d+$', texto):
        texto = texto.replace(",", ".")
    else:
        texto = texto.replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return None


def limpiar_nombre_equipo(nombre: str) -> str:
    """Elimina ruido OCR al inicio y fin de un nombre de equipo."""
    # Quitar "(número)" al inicio: "(55) San Lorenzo" → "San Lorenzo"
    nombre = re.sub(r'^\s*\(\d+\)\s*', '', nombre)
    # Quitar números al final
    nombre = re.sub(r'\s*\d+\s*$', '', nombre)
    # Quitar caracteres raros
    nombre = re.sub(r'[^\w\sáéíóúÁÉÍÓÚñÑ\.]', '', nombre).strip()
    return nombre


def parse_ticket(text: str) -> dict:
    result = {
        "cuota": None,
        "stake": None,
        "fecha": None,
        "evento": None,
        "mercado": None,
        "seleccion": None,
    }

    if not text or not text.strip():
        return result

    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]

    # ── STAKE ──────────────────────────────────────────────────────────────
    # Prioridad 1: línea con "Apuesta/Ap " + número
    for pat in [
        r'(?:apuesta|stake|monto|importe|amount)\s*\$?\s*([\d.,]+)',
        r'^Ap\s+([\d.,]+)',
    ]:
        m = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
        if m:
            val = parsear_numero(m.group(1))
            if val and val > 0:
                result["stake"] = val
                break

    # Prioridad 2: "Simple X" donde X es el stake
    if not result["stake"]:
        m = re.search(r'(?:simple)[^\d]+([\d.,]+)', text, re.IGNORECASE)
        if m:
            val = parsear_numero(m.group(1))
            if val and val > 0:
                result["stake"] = val

    # Prioridad 3: primer número grande junto a $ (puede que OCR funda $ con dígito)
    if not result["stake"]:
        for m in re.finditer(r'(?:\$\s*)?([\d.,]{4,})', text):
            val = parsear_numero(m.group(1))
            if val and val >= 100:  # stakes suelen ser >= 100 en pesos AR
                result["stake"] = val
                break

    # ── CUOTA ──────────────────────────────────────────────────────────────
    # Buscar en cada línea un número aislado con decimales (cuota pura)
    for line in lines:
        m = re.match(r'^(\d{1,3}[.,]\d{2})\s*$', line)
        if m:
            val = parsear_numero(m.group(1))
            if val and 1.01 <= val <= 50:
                result["cuota"] = val
                break

    # Buscar cuota al final de una línea (ej: "San Lorenzo  3.90")
    if not result["cuota"]:
        for line in lines:
            if '$' in line:
                continue
            m = re.search(r'\b(\d{1,2}[.,]\d{2})\s*$', line)
            if m:
                val = parsear_numero(m.group(1))
                if val and 1.01 <= val <= 50:
                    result["cuota"] = val
                    break

    # Fallback: primer decimal en rango de cuota evitando miles
    if not result["cuota"]:
        for m in re.finditer(r'(?<!\d)(\d{1,2}[.,]\d{2})(?!\d)', text):
            val = parsear_numero(m.group(1))
            if val and 1.01 <= val <= 50:
                result["cuota"] = val
                break

    # ── FECHA ──────────────────────────────────────────────────────────────
    for pat, fmt in [
        (r'\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})\b', "%d/%m/%Y"),
        (r'\b(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})\b', "%Y/%m/%d"),
        (r'\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{2})\b', "%d/%m/%y"),
    ]:
        m = re.search(pat, text)
        if m:
            try:
                d = datetime.strptime(m.group(0).replace("-", "/"), fmt)
                result["fecha"] = d.strftime("%Y-%m-%d")
                break
            except ValueError:
                continue

    # ── MERCADO ────────────────────────────────────────────────────────────
    mercado_map = [
        (r'resultado\s+del\s+partido',        'Resultado del partido'),
        (r'del\s+partido',                     'Resultado del partido'),  # OCR parcial
        (r'ltad\b',                            'Resultado del partido'),  # "Resu-ltad"
        (r'doble\s+oportunidad',               'Doble oportunidad'),
        (r'ambos\s+(?:anotan|marcan)',         'Ambos marcan'),
        (r'over\s+(\d+(?:[.,]\d+)?)',          None),  # captura el número
        (r'under\s+(\d+(?:[.,]\d+)?)',         None),
        (r'handicap',                          'Handicap'),
        (r'ganador\s+del\s+partido',           'Ganador del partido'),
        (r'\b1x2\b',                           '1X2'),
    ]
    for pat, label in mercado_map:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            result["mercado"] = label if label else m.group(0).strip()
            break

    # ── EVENTO ─────────────────────────────────────────────────────────────
    # Patrón 1: "Equipo A vs Equipo B" en una sola línea
    for line in lines:
        m = re.search(
            r'([A-Za-záéíóúÁÉÍÓÚñÑ\w\s\.]+?)\s+(?:vs\.?|versus)\s+([A-Za-záéíóúÁÉÍÓÚñÑ\w\s\.]+)',
            line, re.IGNORECASE
        )
        if m:
            resultado_evt = re.sub(r'\s+\d+[/\-]\d+.*$', '', m.group(0)).strip()
            result["evento"] = resultado_evt
            break

    # Patrón 2 y 3: detectar timer (cualquier formato: "27:36", "2130:", "HT", etc.)
    if not result["evento"]:
        for i, line in enumerate(lines):
            tiene_timer = (re.search(r'\b\d{1,4}:', line)
                           or re.search(r'\b(?:HT|FT|ET|ST)\b', line, re.IGNORECASE))
            if tiene_timer:
                # Equipo 2 = texto de esta línea ANTES del timer/número
                parte_antes = re.split(r'\s+\d{1,4}[:\s]', line)[0].strip()
                e2 = limpiar_nombre_equipo(parte_antes) if parte_antes else None

                # Equipo 1 = línea anterior
                e1 = limpiar_nombre_equipo(lines[i-1]) if i > 0 else None

                if e1 and e2 and len(e1) > 2 and len(e2) > 2:
                    result["evento"] = f"{e1} vs {e2}"
                    break

    # Patrón 4: dos líneas consecutivas que empiezan con mayúscula y parecen equipos
    if not result["evento"]:
        ignorar = {
            'resultado del partido', 'doble oportunidad', 'apuesta', 'simple',
            'ganancias potenciales', 'cash out', 'mostrar montos', 'del partido',
            'sultad', 'el partido', 'ltad', 'ap', 'mostrar'
        }
        equipo_re = re.compile(r'^[A-ZÁÉÍÓÚÑ][A-Za-záéíóúÁÉÍÓÚñÑ\s\.]{2,}$')
        candidatos = []
        for line in lines:
            limpio = limpiar_nombre_equipo(line)
            if (equipo_re.match(limpio)
                    and limpio.lower() not in ignorar
                    and len(limpio) > 3
                    and len(limpio.split()) <= 5):  # máx 5 palabras
                candidatos.append(limpio)
                if len(candidatos) == 2:
                    result["evento"] = f"{candidatos[0]} vs {candidatos[1]}"
                    break
            else:
                candidatos = []

    # ── SELECCIÓN ──────────────────────────────────────────────────────────
    ignorar_seleccion = {'simple', 'ap', 'ganancias', 'cash', 'mostrar', 'apuesta'}
    if result["cuota"]:
        cuota_variants = {
            str(result["cuota"]),
            f"{result['cuota']:.2f}",
            f"{result['cuota']:.2f}".replace(".", ","),
        }
        for line in lines:
            if '$' in line:
                continue
            if any(line.lower().startswith(ign) for ign in ignorar_seleccion):
                continue
            if any(re.search(r'\b' + re.escape(c) + r'\s*$', line) for c in cuota_variants):
                nombre = re.sub(r'\b' + r'\b|\b'.join(re.escape(c) for c in cuota_variants) + r'\b', '', line)
                nombre = limpiar_nombre_equipo(nombre)
                if len(nombre) > 2:
                    result["seleccion"] = nombre
                    break

    return result
