"""
Módulo de base de datos.
- Con DATABASE_URL: usa PostgreSQL (Supabase / Vercel)
- Sin DATABASE_URL: usa SQLite (local)
"""

import os
from datetime import datetime

DATABASE_URL = os.environ.get("DATABASE_URL")
USE_PG = bool(DATABASE_URL)

# ── Rutas locales (SQLite) ────────────────────
if not USE_PG:
    import sqlite3
    DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "apuestas.db")

BOOKIES_INICIALES = ["Bet365", "Betano", "Unibet", "Pinnacle", "Betsson", "Codere"]


# ──────────────────────────────────────────────
# CONEXIÓN
# ──────────────────────────────────────────────

def get_connection():
    if USE_PG:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        return conn
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn


def _execute(conn, query, params=None):
    """Ejecuta una query y retorna el cursor. Abstrae SQLite vs PostgreSQL."""
    if USE_PG:
        cur = conn.cursor()
        cur.execute(query, params or ())
        return cur
    else:
        return conn.execute(query, params or ())


def _fetchall(cur):
    rows = cur.fetchall()
    return [dict(r) for r in rows]


def _fetchone(cur):
    row = cur.fetchone()
    return dict(row) if row else None


# Placeholder para parámetros
P = "%s" if USE_PG else "?"


# ──────────────────────────────────────────────
# INICIALIZACIÓN
# ──────────────────────────────────────────────

def init_db():
    if not USE_PG:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = get_connection()

    if USE_PG:
        _init_pg(conn)
    else:
        _init_sqlite(conn)

    conn.commit()
    conn.close()


def _init_pg(conn):
    stmts = [
        """
        CREATE TABLE IF NOT EXISTS bookies (
            id               SERIAL PRIMARY KEY,
            nombre           TEXT NOT NULL UNIQUE,
            activo           INTEGER NOT NULL DEFAULT 1,
            fondos_iniciales FLOAT NOT NULL DEFAULT 0
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS apuestas (
            id             SERIAL PRIMARY KEY,
            bookie_id      INTEGER NOT NULL REFERENCES bookies(id),
            fecha          TEXT NOT NULL,
            evento         TEXT NOT NULL,
            mercado        TEXT NOT NULL DEFAULT '',
            seleccion      TEXT NOT NULL DEFAULT '',
            cuota          FLOAT NOT NULL,
            stake          FLOAT NOT NULL,
            prob_estimada  FLOAT NOT NULL,
            ev_percent     FLOAT NOT NULL,
            estado         TEXT NOT NULL DEFAULT 'pendiente'
                              CHECK(estado IN ('pendiente','ganada','perdida','void','anulada')),
            ganancia_neta  FLOAT,
            notas          TEXT DEFAULT '',
            ticket_raw     TEXT DEFAULT '',
            created_at     TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS retiros (
            id         SERIAL PRIMARY KEY,
            bookie_id  INTEGER NOT NULL REFERENCES bookies(id),
            fecha      TEXT NOT NULL,
            monto      FLOAT NOT NULL,
            notas      TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
        """,
    ]
    for stmt in stmts:
        _execute(conn, stmt)

    # Insertar bookies iniciales si la tabla está vacía
    cur = _execute(conn, "SELECT COUNT(*) AS cnt FROM bookies")
    row = _fetchone(cur)
    if row and row["cnt"] == 0:
        for b in BOOKIES_INICIALES:
            _execute(conn, "INSERT INTO bookies (nombre, activo) VALUES (%s, 1)", (b,))


def _init_sqlite(conn):
    cur = conn.cursor()
    cur.executescript("""
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
                              CHECK(estado IN ('pendiente','ganada','perdida','void','anulada')),
            ganancia_neta  REAL,
            notas          TEXT DEFAULT '',
            ticket_raw     TEXT DEFAULT '',
            created_at     TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS retiros (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            bookie_id  INTEGER NOT NULL REFERENCES bookies(id),
            fecha      TEXT NOT NULL,
            monto      REAL NOT NULL,
            notas      TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
    """)

    count = cur.execute("SELECT COUNT(*) FROM bookies").fetchone()[0]
    if count == 0:
        cur.executemany(
            "INSERT INTO bookies (nombre, activo) VALUES (?, 1)",
            [(b,) for b in BOOKIES_INICIALES],
        )

    # Migraciones SQLite
    try:
        cur.execute("ALTER TABLE bookies ADD COLUMN fondos_iniciales REAL NOT NULL DEFAULT 0")
    except Exception:
        pass


# ──────────────────────────────────────────────
# BOOKIES
# ──────────────────────────────────────────────

def get_bookies(solo_activos=False):
    conn = get_connection()
    where = "WHERE b.activo = 1" if solo_activos else ""
    query = f"""
        SELECT b.id, b.nombre, b.activo, b.fondos_iniciales,
               COALESCE(b.fondos_iniciales + SUM(CASE WHEN a.estado NOT IN ('void','anulada')
                   THEN COALESCE(a.ganancia_neta, 0) ELSE 0 END), b.fondos_iniciales)
               - COALESCE((SELECT SUM(monto) FROM retiros WHERE bookie_id = b.id), 0)
               AS fondos_actuales
        FROM bookies b
        LEFT JOIN apuestas a ON a.bookie_id = b.id
        {where}
        GROUP BY b.id, b.nombre, b.activo, b.fondos_iniciales
        ORDER BY b.nombre
    """
    cur = _execute(conn, query)
    rows = _fetchall(cur)
    conn.close()
    return rows


def get_bookie_by_id(bookie_id):
    conn = get_connection()
    cur = _execute(conn, f"SELECT * FROM bookies WHERE id = {P}", (bookie_id,))
    row = _fetchone(cur)
    conn.close()
    return row


def add_bookie(nombre, fondos_iniciales=0):
    conn = get_connection()
    try:
        if USE_PG:
            cur = _execute(conn,
                "INSERT INTO bookies (nombre, activo, fondos_iniciales) VALUES (%s, 1, %s) RETURNING id",
                (nombre, fondos_iniciales or 0))
            bookie_id = cur.fetchone()["id"]
        else:
            conn.execute("INSERT INTO bookies (nombre, activo, fondos_iniciales) VALUES (?, 1, ?)",
                         (nombre, fondos_iniciales or 0))
            bookie_id = conn.execute("SELECT id FROM bookies WHERE nombre = ?", (nombre,)).fetchone()["id"]
        conn.commit()
        conn.close()
        return bookie_id
    except Exception:
        conn.close()
        return None


def update_fondos_bookie(bookie_id, fondos_iniciales):
    conn = get_connection()
    _execute(conn, f"UPDATE bookies SET fondos_iniciales = {P} WHERE id = {P}",
             (fondos_iniciales, bookie_id))
    conn.commit()
    conn.close()


def toggle_bookie(bookie_id, activo):
    conn = get_connection()
    _execute(conn, f"UPDATE bookies SET activo = {P} WHERE id = {P}",
             (1 if activo else 0, bookie_id))
    conn.commit()
    conn.close()


def delete_bookie(bookie_id):
    conn = get_connection()
    cur = _execute(conn, f"SELECT id FROM bookies WHERE id = {P}", (bookie_id,))
    if not _fetchone(cur):
        conn.close()
        return "not_found"
    cur = _execute(conn, f"SELECT COUNT(*) AS cnt FROM apuestas WHERE bookie_id = {P}", (bookie_id,))
    row = _fetchone(cur)
    if row and row["cnt"] > 0:
        conn.close()
        return "tiene_apuestas"
    _execute(conn, f"DELETE FROM bookies WHERE id = {P}", (bookie_id,))
    conn.commit()
    conn.close()
    return "ok"


# ──────────────────────────────────────────────
# RETIROS
# ──────────────────────────────────────────────

def insert_retiro(bookie_id, monto, notas=""):
    conn = get_connection()
    created_at = datetime.now().isoformat()
    fecha = created_at[:10]
    if USE_PG:
        cur = _execute(conn,
            "INSERT INTO retiros (bookie_id, fecha, monto, notas, created_at) VALUES (%s,%s,%s,%s,%s) RETURNING id",
            (bookie_id, fecha, monto, notas, created_at))
        row_id = cur.fetchone()["id"]
    else:
        cur = conn.execute(
            "INSERT INTO retiros (bookie_id, fecha, monto, notas, created_at) VALUES (?,?,?,?,?)",
            (bookie_id, fecha, monto, notas, created_at))
        row_id = cur.lastrowid
    conn.commit()
    conn.close()
    return row_id


def get_retiros(bookie_id=None):
    conn = get_connection()
    base = "SELECT r.*, b.nombre AS bookie_nombre FROM retiros r JOIN bookies b ON r.bookie_id = b.id"
    if bookie_id:
        cur = _execute(conn, f"{base} WHERE r.bookie_id = {P} ORDER BY r.created_at DESC", (bookie_id,))
    else:
        cur = _execute(conn, f"{base} ORDER BY r.created_at DESC")
    rows = _fetchall(cur)
    conn.close()
    return rows


def delete_retiro(retiro_id):
    conn = get_connection()
    cur = _execute(conn, f"DELETE FROM retiros WHERE id = {P}", (retiro_id,))
    conn.commit()
    eliminado = cur.rowcount > 0
    conn.close()
    return eliminado


# ──────────────────────────────────────────────
# APUESTAS
# ──────────────────────────────────────────────

def insert_apuesta(data: dict) -> int:
    conn = get_connection()
    if USE_PG:
        cur = _execute(conn, """
            INSERT INTO apuestas
                (bookie_id, fecha, evento, mercado, seleccion, cuota, stake,
                 prob_estimada, ev_percent, estado, ganancia_neta, notas, ticket_raw, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (data["bookie_id"], data["fecha"], data["evento"], data["mercado"],
              data["seleccion"], data["cuota"], data["stake"], data["prob_estimada"],
              data["ev_percent"], data["estado"], data["ganancia_neta"],
              data["notas"], data["ticket_raw"], data["created_at"]))
        new_id = cur.fetchone()["id"]
    else:
        cur = conn.execute("""
            INSERT INTO apuestas
                (bookie_id, fecha, evento, mercado, seleccion, cuota, stake,
                 prob_estimada, ev_percent, estado, ganancia_neta, notas, ticket_raw, created_at)
            VALUES
                (:bookie_id,:fecha,:evento,:mercado,:seleccion,:cuota,:stake,
                 :prob_estimada,:ev_percent,:estado,:ganancia_neta,:notas,:ticket_raw,:created_at)
        """, data)
        new_id = cur.lastrowid
    conn.commit()
    conn.close()
    return new_id


def get_apuestas(bookie_id=None, estado=None, fecha_desde=None, fecha_hasta=None):
    conn = get_connection()
    query = "SELECT a.*, b.nombre AS bookie_nombre FROM apuestas a JOIN bookies b ON a.bookie_id = b.id WHERE 1=1"
    params = []
    if bookie_id:
        query += f" AND a.bookie_id = {P}"; params.append(bookie_id)
    if estado:
        query += f" AND a.estado = {P}"; params.append(estado)
    if fecha_desde:
        query += f" AND a.fecha >= {P}"; params.append(fecha_desde)
    if fecha_hasta:
        query += f" AND a.fecha <= {P}"; params.append(fecha_hasta)
    query += " ORDER BY a.fecha DESC, a.created_at DESC"
    cur = _execute(conn, query, params)
    rows = _fetchall(cur)
    conn.close()
    return rows


def get_apuesta_by_id(apuesta_id):
    conn = get_connection()
    cur = _execute(conn,
        f"SELECT a.*, b.nombre AS bookie_nombre FROM apuestas a JOIN bookies b ON a.bookie_id = b.id WHERE a.id = {P}",
        (apuesta_id,))
    row = _fetchone(cur)
    conn.close()
    return row


def delete_apuesta(apuesta_id):
    conn = get_connection()
    cur = _execute(conn, f"DELETE FROM apuestas WHERE id = {P}", (apuesta_id,))
    conn.commit()
    eliminado = cur.rowcount > 0
    conn.close()
    return eliminado


def resolver_apuesta(apuesta_id, estado, ganancia_neta):
    conn = get_connection()
    _execute(conn, f"UPDATE apuestas SET estado = {P}, ganancia_neta = {P} WHERE id = {P}",
             (estado, ganancia_neta, apuesta_id))
    conn.commit()
    conn.close()


def get_stats_raw():
    conn = get_connection()
    cur = _execute(conn, """
        SELECT a.*, b.nombre AS bookie_nombre
        FROM apuestas a JOIN bookies b ON a.bookie_id = b.id
        ORDER BY a.fecha ASC
    """)
    rows = _fetchall(cur)
    conn.close()
    return rows
