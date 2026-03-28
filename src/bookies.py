"""
Gestión de bookies: agregar, listar, activar/desactivar.
"""

from database import get_bookies, add_bookie, toggle_bookie, get_bookie_by_id


def listar_bookies(solo_activos=False):
    return get_bookies(solo_activos=solo_activos)


def agregar_bookie(nombre: str):
    """
    Agrega un nuevo bookie. Retorna el id si tuvo éxito, None si ya existía.
    """
    nombre = nombre.strip()
    if not nombre:
        raise ValueError("El nombre del bookie no puede estar vacío")
    return add_bookie(nombre)


def desactivar_bookie(bookie_id: int):
    bookie = get_bookie_by_id(bookie_id)
    if not bookie:
        raise ValueError(f"No se encontró el bookie con id {bookie_id}")
    toggle_bookie(bookie_id, activo=False)


def activar_bookie(bookie_id: int):
    bookie = get_bookie_by_id(bookie_id)
    if not bookie:
        raise ValueError(f"No se encontró el bookie con id {bookie_id}")
    toggle_bookie(bookie_id, activo=True)
