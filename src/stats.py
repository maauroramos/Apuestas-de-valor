"""
Cálculo de estadísticas: ROI, P&L, EV, rachas, por bookie y global.
"""

from datetime import datetime, timedelta
from database import get_stats_raw


def calcular_stats(apuestas: list) -> dict:
    """
    Calcula estadísticas a partir de una lista de dicts de apuestas.
    Retorna un dict con todas las métricas.
    """
    total = len(apuestas)
    pendientes = [a for a in apuestas if a["estado"] == "pendiente"]
    resueltas = [a for a in apuestas if a["estado"] in ("ganada", "perdida", "void")]
    ganadas = [a for a in apuestas if a["estado"] == "ganada"]
    perdidas = [a for a in apuestas if a["estado"] == "perdida"]
    voids = [a for a in apuestas if a["estado"] == "void"]

    stake_total = sum(a["stake"] for a in apuestas)
    stake_pendiente = sum(a["stake"] for a in pendientes)
    stake_resuelto = sum(a["stake"] for a in resueltas if a["estado"] != "void")

    ganancia_neta = sum(
        a["ganancia_neta"] for a in resueltas if a["ganancia_neta"] is not None
    )

    roi = round((ganancia_neta / stake_resuelto * 100), 2) if stake_resuelto > 0 else 0.0

    winrate = round(len(ganadas) / len(resueltas) * 100, 2) if resueltas else 0.0

    ev_acumulado = round(sum(a["ev_percent"] * a["stake"] / 100 for a in apuestas), 2)
    ev_realizado = round(ganancia_neta, 2)

    # Racha actual (basada en las apuestas resueltas ordenadas por fecha desc)
    resueltas_ordenadas = sorted(
        [a for a in resueltas if a["estado"] != "void"],
        key=lambda x: (x["fecha"], x.get("created_at", "")),
        reverse=True,
    )
    racha = _calcular_racha(resueltas_ordenadas)

    # Cuota promedio (solo resueltas no-void)
    no_void = [a for a in resueltas if a["estado"] != "void"]
    cuota_promedio = (
        round(sum(a["cuota"] for a in no_void) / len(no_void), 3) if no_void else 0.0
    )

    # EV promedio por apuesta
    ev_promedio = (
        round(sum(a["ev_percent"] for a in apuestas) / len(apuestas), 2) if apuestas else 0.0
    )

    return {
        "total": total,
        "pendientes": len(pendientes),
        "ganadas": len(ganadas),
        "perdidas": len(perdidas),
        "voids": len(voids),
        "resueltas": len(resueltas),
        "stake_total": round(stake_total, 2),
        "stake_pendiente": round(stake_pendiente, 2),
        "stake_resuelto": round(stake_resuelto, 2),
        "ganancia_neta": round(ganancia_neta, 2),
        "roi": roi,
        "winrate": winrate,
        "ev_acumulado": ev_acumulado,
        "ev_realizado": ev_realizado,
        "racha": racha,
        "cuota_promedio": cuota_promedio,
        "ev_promedio": ev_promedio,
    }


def _calcular_racha(resueltas_desc: list) -> str:
    """
    Calcula la racha actual: "+3" si 3 ganadas seguidas, "-2" si 2 perdidas, "0" si no hay.
    resueltas_desc: apuestas ordenadas de más reciente a más antigua.
    """
    if not resueltas_desc:
        return "0"
    ultimo_estado = resueltas_desc[0]["estado"]
    count = 0
    for a in resueltas_desc:
        if a["estado"] == ultimo_estado:
            count += 1
        else:
            break
    if ultimo_estado == "ganada":
        return f"+{count}"
    else:
        return f"-{count}"


def stats_globales() -> dict:
    """Estadísticas sobre todas las apuestas."""
    return calcular_stats(get_stats_raw())


def stats_por_bookie() -> dict:
    """
    Retorna un dict: { nombre_bookie: stats_dict }
    """
    todas = get_stats_raw()
    por_bookie = {}
    for a in todas:
        nombre = a["bookie_nombre"]
        por_bookie.setdefault(nombre, []).append(a)

    resultado = {}
    for nombre, apuestas in por_bookie.items():
        resultado[nombre] = calcular_stats(apuestas)
    return resultado


def stats_periodo(dias: int) -> dict:
    """Estadísticas de los últimos N días."""
    desde = (datetime.now() - timedelta(days=dias)).strftime("%Y-%m-%d")
    todas = get_stats_raw()
    filtradas = [a for a in todas if a["fecha"] >= desde]
    return calcular_stats(filtradas)


def stats_hoy() -> dict:
    hoy = datetime.now().strftime("%Y-%m-%d")
    todas = get_stats_raw()
    filtradas = [a for a in todas if a["fecha"] == hoy]
    return calcular_stats(filtradas)


def stats_semana() -> dict:
    return stats_periodo(7)
