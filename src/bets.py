"""
Lógica de apuestas: CRUD y cálculo de EV.
"""

from datetime import datetime
from database import (
    insert_apuesta,
    get_apuestas,
    get_apuesta_by_id,
    resolver_apuesta as db_resolver,
)


def calcular_ev(prob_estimada: float, cuota: float) -> float:
    """
    Calcula el Expected Value en porcentaje.
    EV% = (prob_estimada * cuota - 1) * 100
    prob_estimada debe estar entre 0 y 1.
    """
    return round((prob_estimada * cuota - 1) * 100, 2)


def registrar_apuesta(
    bookie_id: int,
    fecha: str,
    evento: str,
    mercado: str,
    seleccion: str,
    cuota: float,
    stake: float,
    prob_estimada: float,
    notas: str = "",
    ticket_raw: str = "",
) -> dict:
    """
    Registra una nueva apuesta y retorna el dict con todos los datos incluyendo EV.
    prob_estimada: float entre 0 y 1 (ej: 0.55 = 55%)
    """
    ev_percent = calcular_ev(prob_estimada, cuota)

    data = {
        "bookie_id": bookie_id,
        "fecha": fecha,
        "evento": evento,
        "mercado": mercado,
        "seleccion": seleccion,
        "cuota": cuota,
        "stake": stake,
        "prob_estimada": prob_estimada,
        "ev_percent": ev_percent,
        "estado": "pendiente",
        "ganancia_neta": None,
        "notas": notas,
        "ticket_raw": ticket_raw,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    new_id = insert_apuesta(data)
    data["id"] = new_id
    return data


def resolver_apuesta(apuesta_id: int, estado: str) -> dict:
    """
    Resuelve una apuesta pendiente.
    estado: 'ganada' | 'perdida' | 'void' | 'anulada'
    Calcula ganancia_neta:
      - ganada:  stake * (cuota - 1)
      - perdida: -stake
      - void:    0  (devuelve el stake)
      - anulada: 0  (devuelve el stake)
    Retorna el dict actualizado de la apuesta.
    """
    apuesta = get_apuesta_by_id(apuesta_id)
    if not apuesta:
        raise ValueError(f"No se encontró la apuesta con id {apuesta_id}")
    if apuesta["estado"] != "pendiente":
        raise ValueError(f"La apuesta ya está resuelta: {apuesta['estado']}")

    stake = apuesta["stake"]
    cuota = apuesta["cuota"]

    if estado == "ganada":
        ganancia_neta = round(stake * (cuota - 1), 2)
    elif estado == "perdida":
        ganancia_neta = round(-stake, 2)
    elif estado in ("void", "anulada"):
        ganancia_neta = 0.0
    else:
        raise ValueError(f"Estado inválido: {estado}")

    db_resolver(apuesta_id, estado, ganancia_neta)
    apuesta["estado"] = estado
    apuesta["ganancia_neta"] = ganancia_neta
    return apuesta


def listar_apuestas(bookie_id=None, estado=None, fecha_desde=None, fecha_hasta=None):
    """Wrapper para obtener apuestas con filtros."""
    return get_apuestas(
        bookie_id=bookie_id,
        estado=estado,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )
