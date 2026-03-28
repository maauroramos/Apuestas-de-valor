"""
Componentes de UI con rich: tablas, paneles, dashboard.
"""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich import box
from datetime import datetime

console = Console()


# ──────────────────────────────────────────────
# HELPERS DE COLOR
# ──────────────────────────────────────────────

def color_valor(valor: float, invertir=False) -> str:
    """Retorna el string con color según si el valor es positivo/negativo."""
    if valor > 0:
        color = "red" if invertir else "green"
    elif valor < 0:
        color = "green" if invertir else "red"
    else:
        color = "yellow"
    return f"[{color}]{valor:+.2f}[/{color}]"


def color_estado(estado: str) -> str:
    colores = {
        "pendiente": "[yellow]pendiente[/yellow]",
        "ganada": "[green]ganada[/green]",
        "perdida": "[red]perdida[/red]",
        "void": "[dim]void[/dim]",
    }
    return colores.get(estado, estado)


def color_ev(ev: float) -> str:
    if ev > 0:
        return f"[green]{ev:+.2f}%[/green]"
    elif ev < 0:
        return f"[red]{ev:+.2f}%[/red]"
    return f"[yellow]{ev:+.2f}%[/yellow]"


# ──────────────────────────────────────────────
# DASHBOARD
# ──────────────────────────────────────────────

def mostrar_dashboard(stats_global, stats_hoy, stats_semana, bankroll_activo):
    """Muestra el dashboard principal al iniciar."""
    console.print()

    # Título
    console.print(Panel(
        "[bold cyan]VALUE BETTING TRACKER[/bold cyan]",
        subtitle=f"[dim]{datetime.now().strftime('%d/%m/%Y %H:%M')}[/dim]",
        box=box.DOUBLE_EDGE,
        expand=False,
        padding=(0, 4),
    ))

    # ── Fila 1: Resumen global ─────────────────────────────────────────────
    gn = stats_global["ganancia_neta"]
    ev = stats_global["ev_acumulado"]
    roi = stats_global["roi"]

    panel_global = Panel(
        f"[bold]Apuestas:[/bold] {stats_global['total']} ({stats_global['ganadas']}G / {stats_global['perdidas']}P / {stats_global['pendientes']}⏳)\n"
        f"[bold]P&L Total:[/bold] {color_valor(gn)}\n"
        f"[bold]ROI:[/bold] {color_valor(roi)}%\n"
        f"[bold]Winrate:[/bold] {stats_global['winrate']:.1f}%\n"
        f"[bold]EV acumulado:[/bold] {color_ev(ev)}\n"
        f"[bold]Racha actual:[/bold] {_color_racha(stats_global['racha'])}",
        title="[bold]Global[/bold]",
        border_style="cyan",
        padding=(0, 1),
    )

    # ── Fila 2: Hoy / Semana ──────────────────────────────────────────────
    gh = stats_hoy["ganancia_neta"]
    gs = stats_semana["ganancia_neta"]

    panel_hoy = Panel(
        f"[bold]Apuestas:[/bold] {stats_hoy['total']}\n"
        f"[bold]P&L:[/bold] {color_valor(gh)}\n"
        f"[bold]Stake:[/bold] {stats_hoy['stake_total']:.2f}",
        title="[bold]Hoy[/bold]",
        border_style="blue",
        padding=(0, 1),
    )

    panel_semana = Panel(
        f"[bold]Apuestas:[/bold] {stats_semana['total']}\n"
        f"[bold]P&L:[/bold] {color_valor(gs)}\n"
        f"[bold]Stake:[/bold] {stats_semana['stake_total']:.2f}",
        title="[bold]Esta semana[/bold]",
        border_style="blue",
        padding=(0, 1),
    )

    panel_bankroll = Panel(
        f"[bold yellow]{bankroll_activo:.2f}[/bold yellow]\n"
        f"[dim]en apuestas pendientes[/dim]",
        title="[bold]Bankroll activo[/bold]",
        border_style="yellow",
        padding=(0, 1),
    )

    console.print(Columns([panel_global, panel_hoy, panel_semana, panel_bankroll]))
    console.print()


def _color_racha(racha: str) -> str:
    if racha.startswith("+"):
        return f"[green]{racha}[/green]"
    elif racha.startswith("-"):
        return f"[red]{racha}[/red]"
    return racha


# ──────────────────────────────────────────────
# TABLA DE APUESTAS
# ──────────────────────────────────────────────

def tabla_apuestas(apuestas: list, titulo="Apuestas"):
    """Renderiza una tabla de apuestas con rich."""
    if not apuestas:
        console.print(f"[yellow]No hay apuestas para mostrar.[/yellow]")
        return

    table = Table(
        title=titulo,
        box=box.ROUNDED,
        show_header=True,
        header_style="bold magenta",
        row_styles=["", "dim"],
    )
    table.add_column("#", style="dim", width=5, justify="right")
    table.add_column("Fecha", width=10)
    table.add_column("Evento", min_width=20, max_width=35)
    table.add_column("Mercado", max_width=18)
    table.add_column("Selección", max_width=18)
    table.add_column("Cuota", justify="right", width=7)
    table.add_column("Stake", justify="right", width=8)
    table.add_column("EV%", justify="right", width=8)
    table.add_column("Estado", width=10)
    table.add_column("P&L", justify="right", width=9)
    table.add_column("Bookie", width=10)

    for a in apuestas:
        pnl = ""
        if a.get("ganancia_neta") is not None:
            pnl = color_valor(a["ganancia_neta"])

        table.add_row(
            str(a["id"]),
            a["fecha"],
            a["evento"],
            a.get("mercado") or "—",
            a.get("seleccion") or "—",
            f"{a['cuota']:.2f}",
            f"{a['stake']:.2f}",
            color_ev(a["ev_percent"]),
            color_estado(a["estado"]),
            pnl or "—",
            a.get("bookie_nombre") or "—",
        )

    console.print(table)


# ──────────────────────────────────────────────
# TABLA DE ESTADÍSTICAS POR BOOKIE
# ──────────────────────────────────────────────

def tabla_stats_bookie(stats_por_bookie: dict):
    if not stats_por_bookie:
        console.print("[yellow]Sin datos por bookie.[/yellow]")
        return

    table = Table(
        title="Estadísticas por bookie",
        box=box.ROUNDED,
        header_style="bold magenta",
    )
    table.add_column("Bookie", min_width=12)
    table.add_column("Total", justify="right")
    table.add_column("G/P/⏳", justify="center")
    table.add_column("Winrate", justify="right")
    table.add_column("Stake", justify="right")
    table.add_column("P&L", justify="right")
    table.add_column("ROI", justify="right")
    table.add_column("EV acum.", justify="right")

    for nombre, s in sorted(stats_por_bookie.items()):
        gp = f"{s['ganadas']}/{s['perdidas']}/{s['pendientes']}"
        table.add_row(
            nombre,
            str(s["total"]),
            gp,
            f"{s['winrate']:.1f}%",
            f"{s['stake_total']:.2f}",
            color_valor(s["ganancia_neta"]),
            color_valor(s["roi"]) + "%",
            color_ev(s["ev_acumulado"]),
        )
    console.print(table)


# ──────────────────────────────────────────────
# TABLA DE BOOKIES
# ──────────────────────────────────────────────

def tabla_bookies(bookies: list):
    if not bookies:
        console.print("[yellow]No hay bookies registrados.[/yellow]")
        return

    table = Table(title="Bookies", box=box.ROUNDED, header_style="bold magenta")
    table.add_column("ID", justify="right", width=5)
    table.add_column("Nombre", min_width=14)
    table.add_column("Estado", width=10)

    for b in bookies:
        estado = "[green]activo[/green]" if b["activo"] else "[red]inactivo[/red]"
        table.add_row(str(b["id"]), b["nombre"], estado)

    console.print(table)


# ──────────────────────────────────────────────
# PANEL DE CONFIRMACIÓN DE APUESTA
# ──────────────────────────────────────────────

def mostrar_resumen_apuesta(data: dict, bookie_nombre: str, ev: float):
    """Muestra un panel con el resumen de la apuesta antes de confirmar."""
    ev_text = color_ev(ev)
    es_valor = "[green]SI - Es apuesta de valor[/green]" if ev > 0 else "[red]NO - EV negativo[/red]"

    contenido = (
        f"[bold]Evento:[/bold]     {data.get('evento', '—')}\n"
        f"[bold]Mercado:[/bold]    {data.get('mercado', '—')}\n"
        f"[bold]Selección:[/bold]  {data.get('seleccion', '—')}\n"
        f"[bold]Cuota:[/bold]      {data.get('cuota', 0):.2f}\n"
        f"[bold]Stake:[/bold]      {data.get('stake', 0):.2f}\n"
        f"[bold]Fecha:[/bold]      {data.get('fecha', '—')}\n"
        f"[bold]Bookie:[/bold]     {bookie_nombre}\n"
        f"[bold]Prob. est.:[/bold] {data.get('prob_estimada', 0)*100:.1f}%\n"
        f"[bold]EV%:[/bold]        {ev_text}\n"
        f"[bold]Valor:[/bold]      {es_valor}"
    )
    console.print(Panel(contenido, title="[bold cyan]Resumen de apuesta[/bold cyan]", border_style="cyan"))


# ──────────────────────────────────────────────
# STATS GLOBALES DETALLADAS
# ──────────────────────────────────────────────

def mostrar_stats_globales(s: dict):
    contenido = (
        f"[bold]Total apuestas:[/bold]   {s['total']}\n"
        f"[bold]Ganadas:[/bold]          [green]{s['ganadas']}[/green]\n"
        f"[bold]Perdidas:[/bold]         [red]{s['perdidas']}[/red]\n"
        f"[bold]Void:[/bold]             [dim]{s['voids']}[/dim]\n"
        f"[bold]Pendientes:[/bold]       [yellow]{s['pendientes']}[/yellow]\n"
        f"─────────────────────────────\n"
        f"[bold]Stake total:[/bold]      {s['stake_total']:.2f}\n"
        f"[bold]Stake pendiente:[/bold]  {s['stake_pendiente']:.2f}\n"
        f"[bold]P&L neto:[/bold]         {color_valor(s['ganancia_neta'])}\n"
        f"[bold]ROI:[/bold]              {color_valor(s['roi'])}%\n"
        f"[bold]Winrate:[/bold]          {s['winrate']:.2f}%\n"
        f"[bold]Cuota promedio:[/bold]   {s['cuota_promedio']:.3f}\n"
        f"─────────────────────────────\n"
        f"[bold]EV acumulado:[/bold]     {color_ev(s['ev_acumulado'])}\n"
        f"[bold]EV promedio/ap.:[/bold]  {color_ev(s['ev_promedio'])}\n"
        f"[bold]EV realizado:[/bold]     {color_valor(s['ev_realizado'])}\n"
        f"[bold]Racha actual:[/bold]     {_color_racha(s['racha'])}"
    )
    console.print(Panel(contenido, title="[bold]Estadísticas Globales[/bold]", border_style="magenta"))
