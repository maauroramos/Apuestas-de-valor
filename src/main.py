"""
Entry point del sistema de seguimiento de apuestas de valor.
Ejecutar con: python src/main.py
"""

import sys
import os

# Asegurarse de que el directorio src esté en el path para imports relativos
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime

import questionary
from rich.console import Console

from database import init_db, get_bookie_by_id
from bets import registrar_apuesta, resolver_apuesta, listar_apuestas, calcular_ev
from bookies import listar_bookies, agregar_bookie, desactivar_bookie, activar_bookie
from stats import stats_globales, stats_por_bookie, stats_hoy, stats_semana
from parser import parse_ticket
from ui import (
    console,
    mostrar_dashboard,
    tabla_apuestas,
    tabla_stats_bookie,
    tabla_bookies,
    mostrar_resumen_apuesta,
    mostrar_stats_globales,
)

# ──────────────────────────────────────────────
# HELPERS DE INPUT
# ──────────────────────────────────────────────

def pedir_float(mensaje: str, default=None, minimo=None, maximo=None) -> float:
    """Pide un float al usuario con validación."""
    while True:
        if default is not None:
            raw = questionary.text(
                mensaje, default=str(default)
            ).ask()
        else:
            raw = questionary.text(mensaje).ask()

        if raw is None:
            raise KeyboardInterrupt

        try:
            valor = float(raw.replace(",", "."))
            if minimo is not None and valor < minimo:
                console.print(f"[red]Debe ser mayor o igual a {minimo}[/red]")
                continue
            if maximo is not None and valor > maximo:
                console.print(f"[red]Debe ser menor o igual a {maximo}[/red]")
                continue
            return valor
        except ValueError:
            console.print("[red]Ingresá un número válido (ej: 1.85)[/red]")


def pedir_fecha(mensaje: str, default=None) -> str:
    """Pide una fecha en formato YYYY-MM-DD."""
    if default is None:
        default = datetime.now().strftime("%Y-%m-%d")
    while True:
        raw = questionary.text(mensaje, default=default).ask()
        if raw is None:
            raise KeyboardInterrupt
        try:
            datetime.strptime(raw.strip(), "%Y-%m-%d")
            return raw.strip()
        except ValueError:
            console.print("[red]Formato inválido. Usá YYYY-MM-DD (ej: 2025-03-20)[/red]")


def pedir_texto(mensaje: str, default="", requerido=False) -> str:
    """Pide un string al usuario."""
    while True:
        raw = questionary.text(mensaje, default=default).ask()
        if raw is None:
            raise KeyboardInterrupt
        raw = raw.strip()
        if requerido and not raw:
            console.print("[red]Este campo es requerido.[/red]")
            continue
        return raw


def elegir_bookie() -> dict:
    """Muestra lista de bookies activos para elegir."""
    bookies = listar_bookies(solo_activos=True)
    if not bookies:
        console.print("[red]No hay bookies activos. Agregá uno primero.[/red]")
        return None

    opciones = {b["nombre"]: b for b in bookies}
    opciones["[+ Agregar nuevo bookie]"] = None

    eleccion = questionary.select(
        "Seleccioná el bookie:",
        choices=list(opciones.keys()),
    ).ask()

    if eleccion is None:
        raise KeyboardInterrupt

    if eleccion == "[+ Agregar nuevo bookie]":
        nombre = pedir_texto("Nombre del nuevo bookie:", requerido=True)
        new_id = agregar_bookie(nombre)
        if new_id is None:
            console.print(f"[yellow]El bookie '{nombre}' ya existe.[/yellow]")
            return elegir_bookie()
        console.print(f"[green]Bookie '{nombre}' agregado.[/green]")
        return {"id": new_id, "nombre": nombre, "activo": 1}

    return opciones[eleccion]


# ──────────────────────────────────────────────
# FLUJO: REGISTRAR APUESTA
# ──────────────────────────────────────────────

def flujo_registrar_apuesta():
    console.print("\n[bold cyan]── Registrar apuesta ──[/bold cyan]")

    # Pegar ticket (opcional)
    tiene_ticket = questionary.confirm(
        "¿Querés pegar el ticket de la apuesta para que el sistema lo parsee?",
        default=True,
    ).ask()

    parsed = {}
    ticket_raw = ""

    if tiene_ticket:
        console.print("[dim]Pegá el texto del ticket y presioná Enter dos veces cuando termines:[/dim]")
        lines = []
        while True:
            try:
                line = input()
                if line == "" and lines and lines[-1] == "":
                    break
                lines.append(line)
            except EOFError:
                break
        ticket_raw = "\n".join(lines).strip()
        if ticket_raw:
            parsed = parse_ticket(ticket_raw)
            console.print("[green]Ticket parseado. Revisá y completá los datos faltantes:[/green]")
        else:
            console.print("[yellow]Ticket vacío, ingresá los datos manualmente.[/yellow]")

    # ── Datos del evento ──────────────────────────────────────────────────
    evento = pedir_texto(
        "Evento (ej: Real Madrid vs Barcelona):",
        default=parsed.get("evento") or "",
        requerido=True,
    )
    mercado = pedir_texto(
        "Mercado (ej: 1X2, Over/Under, Handicap):",
        default=parsed.get("mercado") or "",
    )
    seleccion = pedir_texto(
        "Selección (ej: Real Madrid, Over 2.5):",
        default=parsed.get("seleccion") or "",
    )

    # ── Cuota ─────────────────────────────────────────────────────────────
    cuota_default = parsed.get("cuota")
    if cuota_default:
        console.print(f"[dim]Cuota detectada: {cuota_default}[/dim]")
    cuota = pedir_float(
        "Cuota:",
        default=cuota_default,
        minimo=1.01,
    )

    # ── Stake ─────────────────────────────────────────────────────────────
    stake_default = parsed.get("stake")
    if stake_default:
        console.print(f"[dim]Stake detectado: {stake_default}[/dim]")
    stake = pedir_float(
        "Stake (monto apostado):",
        default=stake_default,
        minimo=0.01,
    )

    # ── Fecha ─────────────────────────────────────────────────────────────
    fecha_default = parsed.get("fecha") or datetime.now().strftime("%Y-%m-%d")
    fecha = pedir_fecha("Fecha (YYYY-MM-DD):", default=fecha_default)

    # ── Probabilidad estimada ─────────────────────────────────────────────
    console.print()
    console.print("[bold]Probabilidad estimada[/bold] (tu estimación de que esta apuesta gane)")
    console.print("[dim]Ingresá un porcentaje entre 1 y 99 (ej: 55 para 55%)[/dim]")
    prob_pct = pedir_float("Probabilidad estimada (%):", minimo=1.0, maximo=99.0)
    prob_estimada = prob_pct / 100.0

    # ── Calcular y mostrar EV antes de confirmar ──────────────────────────
    ev = calcular_ev(prob_estimada, cuota)

    # ── Bookie ────────────────────────────────────────────────────────────
    bookie = elegir_bookie()
    if not bookie:
        return

    # ── Notas opcionales ──────────────────────────────────────────────────
    notas = pedir_texto("Notas (opcional):", default="")

    # ── Mostrar resumen ───────────────────────────────────────────────────
    datos_preview = {
        "evento": evento,
        "mercado": mercado,
        "seleccion": seleccion,
        "cuota": cuota,
        "stake": stake,
        "fecha": fecha,
        "prob_estimada": prob_estimada,
    }
    mostrar_resumen_apuesta(datos_preview, bookie["nombre"], ev)

    confirmar = questionary.confirm("¿Confirmar registro?", default=True).ask()
    if not confirmar:
        console.print("[yellow]Apuesta cancelada.[/yellow]")
        return

    # ── Registrar ─────────────────────────────────────────────────────────
    apuesta = registrar_apuesta(
        bookie_id=bookie["id"],
        fecha=fecha,
        evento=evento,
        mercado=mercado,
        seleccion=seleccion,
        cuota=cuota,
        stake=stake,
        prob_estimada=prob_estimada,
        notas=notas,
        ticket_raw=ticket_raw,
    )

    console.print(f"\n[green bold]Apuesta registrada con ID #{apuesta['id']}[/green bold]")


# ──────────────────────────────────────────────
# FLUJO: RESOLVER APUESTA
# ──────────────────────────────────────────────

def flujo_resolver_apuesta():
    console.print("\n[bold cyan]── Resolver apuesta ──[/bold cyan]")

    pendientes = listar_apuestas(estado="pendiente")
    if not pendientes:
        console.print("[yellow]No hay apuestas pendientes.[/yellow]")
        return

    tabla_apuestas(pendientes, titulo="Apuestas pendientes")

    id_raw = pedir_texto("ID de la apuesta a resolver:", requerido=True)
    try:
        apuesta_id = int(id_raw)
    except ValueError:
        console.print("[red]ID inválido.[/red]")
        return

    # Verificar que está en la lista de pendientes
    ids_pendientes = {a["id"] for a in pendientes}
    if apuesta_id not in ids_pendientes:
        console.print(f"[red]No se encontró una apuesta pendiente con ID {apuesta_id}.[/red]")
        return

    estado = questionary.select(
        "Resultado:",
        choices=["ganada", "perdida", "void"],
    ).ask()
    if estado is None:
        raise KeyboardInterrupt

    apuesta = resolver_apuesta(apuesta_id, estado)

    pnl = apuesta["ganancia_neta"]
    if pnl > 0:
        pnl_str = f"[green]+{pnl:.2f}[/green]"
    elif pnl < 0:
        pnl_str = f"[red]{pnl:.2f}[/red]"
    else:
        pnl_str = f"[dim]{pnl:.2f}[/dim]"

    console.print(f"\n[bold]Apuesta #{apuesta_id} marcada como [cyan]{estado}[/cyan]. P&L: {pnl_str}[/bold]")


# ──────────────────────────────────────────────
# FLUJO: VER HISTORIAL
# ──────────────────────────────────────────────

def flujo_ver_historial():
    console.print("\n[bold cyan]── Historial de apuestas ──[/bold cyan]")

    # Filtros opcionales
    filtrar = questionary.confirm("¿Querés aplicar filtros?", default=False).ask()

    bookie_id = None
    estado = None
    fecha_desde = None
    fecha_hasta = None

    if filtrar:
        # Filtro por estado
        estado_op = questionary.select(
            "Filtrar por estado:",
            choices=["Todos", "pendiente", "ganada", "perdida", "void"],
        ).ask()
        if estado_op != "Todos":
            estado = estado_op

        # Filtro por bookie
        bookies = listar_bookies()
        opciones_bookie = ["Todos"] + [b["nombre"] for b in bookies]
        bookie_op = questionary.select("Filtrar por bookie:", choices=opciones_bookie).ask()
        if bookie_op != "Todos":
            bookie = next((b for b in bookies if b["nombre"] == bookie_op), None)
            if bookie:
                bookie_id = bookie["id"]

        # Filtro por fechas
        usar_fechas = questionary.confirm("¿Filtrar por rango de fechas?", default=False).ask()
        if usar_fechas:
            fecha_desde = pedir_fecha("Fecha desde (YYYY-MM-DD):")
            fecha_hasta = pedir_fecha("Fecha hasta (YYYY-MM-DD):")

    apuestas = listar_apuestas(
        bookie_id=bookie_id,
        estado=estado,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )

    titulo = "Historial"
    if estado:
        titulo += f" — {estado}"
    tabla_apuestas(apuestas, titulo=titulo)
    console.print(f"[dim]Total: {len(apuestas)} apuesta(s)[/dim]")


# ──────────────────────────────────────────────
# FLUJO: ESTADÍSTICAS
# ──────────────────────────────────────────────

def flujo_estadisticas():
    console.print("\n[bold cyan]── Estadísticas ──[/bold cyan]")

    opcion = questionary.select(
        "¿Qué estadísticas querés ver?",
        choices=[
            "Globales",
            "Por bookie",
            "Últimos 7 días",
            "Últimos 30 días",
            "Volver",
        ],
    ).ask()

    if opcion == "Globales":
        s = stats_globales()
        mostrar_stats_globales(s)

    elif opcion == "Por bookie":
        s = stats_por_bookie()
        tabla_stats_bookie(s)

    elif opcion == "Últimos 7 días":
        from stats import stats_periodo
        s = stats_periodo(7)
        console.print("\n[bold]Últimos 7 días[/bold]")
        mostrar_stats_globales(s)

    elif opcion == "Últimos 30 días":
        from stats import stats_periodo
        s = stats_periodo(30)
        console.print("\n[bold]Últimos 30 días[/bold]")
        mostrar_stats_globales(s)


# ──────────────────────────────────────────────
# FLUJO: GESTIONAR BOOKIES
# ──────────────────────────────────────────────

def flujo_gestionar_bookies():
    console.print("\n[bold cyan]── Gestionar bookies ──[/bold cyan]")

    opcion = questionary.select(
        "¿Qué querés hacer?",
        choices=[
            "Ver todos los bookies",
            "Agregar bookie",
            "Desactivar bookie",
            "Activar bookie",
            "Volver",
        ],
    ).ask()

    if opcion == "Ver todos los bookies":
        bookies = listar_bookies()
        tabla_bookies(bookies)

    elif opcion == "Agregar bookie":
        nombre = pedir_texto("Nombre del nuevo bookie:", requerido=True)
        new_id = agregar_bookie(nombre)
        if new_id is None:
            console.print(f"[yellow]Ya existe un bookie con el nombre '{nombre}'.[/yellow]")
        else:
            console.print(f"[green]Bookie '{nombre}' (ID {new_id}) agregado correctamente.[/green]")

    elif opcion == "Desactivar bookie":
        bookies = listar_bookies(solo_activos=True)
        if not bookies:
            console.print("[yellow]No hay bookies activos.[/yellow]")
            return
        tabla_bookies(bookies)
        id_raw = pedir_texto("ID del bookie a desactivar:", requerido=True)
        try:
            desactivar_bookie(int(id_raw))
            console.print(f"[green]Bookie desactivado.[/green]")
        except (ValueError, Exception) as e:
            console.print(f"[red]Error: {e}[/red]")

    elif opcion == "Activar bookie":
        bookies = listar_bookies(solo_activos=False)
        inactivos = [b for b in bookies if not b["activo"]]
        if not inactivos:
            console.print("[yellow]No hay bookies inactivos.[/yellow]")
            return
        tabla_bookies(inactivos)
        id_raw = pedir_texto("ID del bookie a activar:", requerido=True)
        try:
            activar_bookie(int(id_raw))
            console.print(f"[green]Bookie activado.[/green]")
        except (ValueError, Exception) as e:
            console.print(f"[red]Error: {e}[/red]")


# ──────────────────────────────────────────────
# MENÚ PRINCIPAL
# ──────────────────────────────────────────────

MENU_OPCIONES = [
    "1. Registrar apuesta",
    "2. Resolver apuesta",
    "3. Ver historial",
    "4. Estadísticas",
    "5. Gestionar bookies",
    "6. Salir",
]


def menu_principal():
    eleccion = questionary.select(
        "¿Qué querés hacer?",
        choices=MENU_OPCIONES,
    ).ask()
    return eleccion


def main():
    # Inicializar base de datos
    init_db()

    while True:
        try:
            # Mostrar dashboard
            sg = stats_globales()
            sh = stats_hoy()
            ss = stats_semana()
            bankroll = sg["stake_pendiente"]
            mostrar_dashboard(sg, sh, ss, bankroll)

            opcion = menu_principal()
            if opcion is None or opcion == "6. Salir":
                console.print("\n[cyan]Hasta la próxima. ¡Buenas apuestas![/cyan]\n")
                break

            if opcion == "1. Registrar apuesta":
                flujo_registrar_apuesta()
            elif opcion == "2. Resolver apuesta":
                flujo_resolver_apuesta()
            elif opcion == "3. Ver historial":
                flujo_ver_historial()
            elif opcion == "4. Estadísticas":
                flujo_estadisticas()
            elif opcion == "5. Gestionar bookies":
                flujo_gestionar_bookies()

            # Pausa antes de volver al menú
            console.print()
            questionary.press_any_key_to_continue("Presioná cualquier tecla para continuar...").ask()

        except KeyboardInterrupt:
            console.print("\n[yellow]Operación cancelada.[/yellow]")
            continuar = questionary.confirm("¿Querés volver al menú principal?", default=True).ask()
            if not continuar:
                console.print("\n[cyan]Hasta la próxima. ¡Buenas apuestas![/cyan]\n")
                break


if __name__ == "__main__":
    main()
