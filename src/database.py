"""
Módulo de base de datos: setup de SQLite y queries principales.
"""

import sqlite3
import os
from datetime import datetime

# Ruta a la base de datos (relativa al directorio raíz del proyecto)
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "apuestas.db")

BOOKIES_INICIALES = [
    "Bet365",
    "Betano",
    "Unibet",
    "Pinnacle",
    "Betsson",
    "Codere",
]


def get_connection():
    """Retorna una conexión a la base de datos con row_factory configurado."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Crea las tablas si no existen e inserta bookies iniciales."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS bookies (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre           TEXT NOT NULL UNIQUE,
            activo           INTEGER NOT NULL DEFAULT 1,
            fondos_iniciales REAL NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS apuestas (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            bookie_id      INTEGER NOT NULL REFERENCES bookies(id),
            fecha          TEXT NOT NULL,
            evento         TEXT NOT NULL,
            mercado        TEXT NOT NULL DEFAULT '',
            seleccion      TEXT NOT NULL DEFAULT '',
            cuota          REAL NOT NULL,
            stake          REAL NOT NULL,
            prob_estimada  REAL NOT NULL,
            ev_percent     REAL NOT NULL,
            estado         TEXT NOT NULL DEFAULT 'pendiente'
                              CHECK(estado IN ('pendiente','ganada','perdida','void')),
            ganancia_neta  REAL,
            notas          TEXT DEFAULT '',
            ticket_raw     TEXT DEFAULT '',
            created_at     TEXT NOT NULL
        );
    """)

    # Insertar bookies iniciales si la tabla está vacía
    count = cursor.execute("SELECT COUNT(*) FROM bookies").fetchone()[0]
    if count == 0:
        cursor.executemany(
            "INSERT INTO bookies (nombre, activo) VALUES (?, 1)",
            [(b,) for b in BOOKIES_INICIALES],
        )

    # Migración: agregar fondos_iniciales si la columna no existe aún
    try:
        cursor.execute("ALTER TABLE bookies ADD COLUMN fondos_iniciales REAL NOT NULL DEFAULT 0")
    except Exception:
        pass  # Ya existe

    # Migración: agregar estado 'anulada' recreando la tabla con el CHECK actualizado
    schema = cursor.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='apuestas'"
    ).fetchone()
    if schema and "anulada" not in schema[0]:
        cursor.executescript("""
            ALTER TABLE apuestas RENAME TO apuestas_old;

            CREATE TABLE apuestas (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                bookie_id      INTEGER NOT NULL REFERENCES bookies(id),
                fecha          TEXT NOT NULL,
                evento         TEXT NOT NULL,
                mercado        TEXT NOT NULL DEFAULT '',
                seleccion      TEXT NOT NULL DEFAULT '',
                cuota          REAL NOT NULL,
                stake          REAL NOT NULL,
                prob_estimada  REAL NOT NULL,
                ev_percent     REAL NOT NULL,
                estado         TEXT NOT NULL DEFAULT 'pendiente'
                                  CHECK(estado IN ('pendiente','ganada','perdida','void','anulada')),
                ganancia_neta  REAL,
                notas          TEXT DEFAULT '',
                ticket_raw     TEXT DEFAULT '',
                created_at     TEXT NOT NULL
            );

            INSERT INTO apuestas SELECT * FROM apuestas_old;
            DROP TABLE apuestas_old;
        """)

    # Migración: crear tabla retiros si no existe
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS retiros (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            bookie_id  INTEGER NOT NULL REFERENCES bookies(id),
            fecha      TEXT NOT NULL,
            monto      REAL NOT NULL,
            notas      TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


# ──────────────────────────────────────────────
# BOOKIES
# ──────────────────────────────────────────────

def get_bookies(solo_activos=False):
    conn = get_connection()
    query = """
        SELECT b.*,
               COALESCE(b.fondos_iniciales + SUM(CASE WHEN a.estado NOT IN ('void','anulada') THEN COALESCE(a.ganancia_neta, 0) ELSE 0 END), b.fondos_iniciales) AS fondos_sin_retiros,
               COALESCE(SUM(r.monto), 0) AS retiros_acumulados,
               COALESCE(b.fondos_iniciales + SUM(CASE WHEN a.estado NOT IN ('void','anulada') THEN COALESCE(a.ganancia_neta, 0) ELSE 0 END), b.fondos_iniciales)
               - COALESCE((SELECT SUM(monto) FROM retiros WHERE bookie_id = b.id), 0) AS fondos_actuales
        FROM bookies b
        LEFT JOIN apuestas a ON a.bookie_id = b.id
        LEFT JOIN retiros r ON r.bookie_id = b.id
        {}
        GROUP BY b.id
        ORDER BY b.nombre
    """
    where = "WHERE b.activo = 1" if solo_activos else ""
    rows = conn.execute(query.format(where)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_bookie_by_id(bookie_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM bookies WHERE id = ?", (bookie_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_bookie(nombre, fondos_iniciales=0):
    conn = get_connection()
    try:
        conn.execute("INSERT INTO bookies (nombre, activo, fondos_iniciales) VALUES (?, 1, ?)", (nombre, fondos_iniciales or 0))
        conn.commit()
        bookie_id = conn.execute("SELECT id FROM bookies WHERE nombre = ?", (nombre,)).fetchone()["id"]
        conn.close()
        return bookie_id
    except sqlite3.IntegrityError:
        conn.close()
        return None  # Ya existe


def update_fondos_bookie(bookie_id, fondos_iniciales):
    conn = get_connection()
    conn.execute("UPDATE bookies SET fondos_iniciales = ? WHERE id = ?", (fondos_iniciales, bookie_id))
    conn.commit()
    conn.close()


def toggle_bookie(bookie_id, activo):
    conn = get_connection()
    conn.execute("UPDATE bookies SET activo = ? WHERE id = ?", (1 if activo else 0, bookie_id))
    conn.commit()
    conn.close()


# ──────────────────────────────────────────────
# RETIROS
# ──────────────────────────────────────────────

def insert_retiro(bookie_id, monto, notas=""):
    """monto > 0 = retiro, monto < 0 = re-fondeo."""
    conn = get_connection()
    created_at = datetime.now().isoformat()
    fecha = created_at[:10]
    cursor = conn.execute(
        "INSERT INTO retiros (bookie_id, fecha, monto, notas, created_at) VALUES (?, ?, ?, ?, ?)",
        (bookie_id, fecha, monto, notas, created_at)
    )
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()
    return row_id


def get_retiros(bookie_id=None):
    conn = get_connection()
    if bookie_id:
        rows = conn.execute(
            "SELECT r.*, b.nombre AS bookie_nombre FROM retiros r JOIN bookies b ON r.bookie_id = b.id WHERE r.bookie_id = ? ORDER BY r.created_at DESC",
            (bookie_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT r.*, b.nombre AS bookie_nombre FROM retiros r JOIN bookies b ON r.bookie_id = b.id ORDER BY r.created_at DESC"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_retiro(retiro_id):
    conn = get_connection()
    cursor = conn.execute("DELETE FROM retiros WHERE id = ?", (retiro_id,))
    conn.commit()
    eliminado = cursor.rowcount > 0
    conn.close()
    return eliminado


# ──────────────────────────────────────────────
# APUESTAS
# ──────────────────────────────────────────────

def insert_apuesta(data: dict) -> int:
    """Inserta una apuesta y retorna su id."""
    conn = get_connection()
    cursor = conn.execute(
        """
        INSERT INTO apuestas
            (bookie_id, fecha, evento, mercado, seleccion, cuota, stake,
             prob_estimada, ev_percent, estado, ganancia_neta, notas, ticket_raw, created_at)
        VALUES
            (:bookie_id, :fecha, :evento, :mercado, :seleccion, :cuota, :stake,
             :prob_estimada, :ev_percent, :estado, :ganancia_neta, :notas, :ticket_raw, :created_at)
        """,
        data,
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id


def get_apuestas(bookie_id=None, estado=None, fecha_desde=None, fecha_hasta=None):
    """Retorna apuestas con filtros opcionales."""
    conn = get_connection()
    query = """
        SELECT a.*, b.nombre AS bookie_nombre
        FROM apuestas a
        JOIN bookies b ON a.bookie_id = b.id
        WHERE 1=1
    """
    params = []
    if bookie_id:
        query += " AND a.bookie_id = ?"
        params.append(bookie_id)
    if estado:
        query += " AND a.estado = ?"
        params.append(estado)
    if fecha_desde:
        query += " AND a.fecha >= ?"
        params.append(fecha_desde)
    if fecha_hasta:
        query += " AND a.fecha <= ?"
        params.append(fecha_hasta)
    query += " ORDER BY a.fecha DESC, a.created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_apuesta_by_id(apuesta_id):
    conn = get_connection()
    row = conn.execute(
        """
        SELECT a.*, b.nombre AS bookie_nombre
        FROM apuestas a JOIN bookies b ON a.bookie_id = b.id
        WHERE a.id = ?
        """,
        (apuesta_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_bookie(bookie_id):
    conn = get_connection()
    bookie = conn.execute("SELECT id FROM bookies WHERE id = ?", (bookie_id,)).fetchone()
    if not bookie:
        conn.close()
        return "not_found"
    count = conn.execute("SELECT COUNT(*) FROM apuestas WHERE bookie_id = ?", (bookie_id,)).fetchone()[0]
    if count > 0:
        conn.close()
        return "tiene_apuestas"
    conn.execute("DELETE FROM bookies WHERE id = ?", (bookie_id,))
    conn.commit()
    conn.close()
    return "ok"


def delete_apuesta(apuesta_id):
    conn = get_connection()
    cursor = conn.execute("DELETE FROM apuestas WHERE id = ?", (apuesta_id,))
    conn.commit()
    eliminadas = cursor.rowcount
    conn.close()
    return eliminadas > 0


def resolver_apuesta(apuesta_id, estado, ganancia_neta):
    conn = get_connection()
    conn.execute(
        "UPDATE apuestas SET estado = ?, ganancia_neta = ? WHERE id = ?",
        (estado, ganancia_neta, apuesta_id),
    )
    conn.commit()
    conn.close()


def get_stats_raw():
    """Devuelve todas las apuestas para calcular estadísticas."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT a.*, b.nombre AS bookie_nombre
        FROM apuestas a JOIN bookies b ON a.bookie_id = b.id
        ORDER BY a.fecha ASC
        """
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
