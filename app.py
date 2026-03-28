"""
Flask backend para la app web de apuestas de valor.
Ejecutar: python3 app.py
"""

import sys
import os
import base64
import random
import string
import json

# Agregar src/ al path para importar los módulos existentes
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from flask import Flask, request, jsonify, render_template, send_from_directory, session, redirect, url_for, send_file
from datetime import datetime, timedelta, date
from functools import wraps

# Cargar variables de entorno desde .env o apikey.env
try:
    from dotenv import load_dotenv
    load_dotenv()           # intenta .env
    load_dotenv("apikey.env")  # también acepta apikey.env
except ImportError:
    pass

from database import init_db, get_stats_raw, get_bookies, get_apuestas
from bets import calcular_ev, registrar_apuesta, resolver_apuesta
from bookies import listar_bookies, agregar_bookie
from database import toggle_bookie, add_bookie, get_bookie_by_id, update_fondos_bookie, delete_apuesta, delete_bookie, insert_retiro, get_retiros, delete_retiro
from stats import calcular_stats, stats_por_bookie
from parser import parse_ticket

# ── Config (data/config.json) ─────────────────
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "data", "config.json")

def _load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {}

def _save_config(data):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=2)

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-cambiar-en-produccion")

# Contraseña de acceso (variable de entorno APP_PASSWORD, default solo para local)
APP_USER     = os.environ.get("APP_USER",     "apuestas")
APP_PASSWORD = os.environ.get("APP_PASSWORD", "Devalor")

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("autenticado"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# ──────────────────────────────────────────────
# INICIALIZACIÓN
# ──────────────────────────────────────────────

@app.before_request
def setup():
    """Inicializa la DB y verifica autenticación."""
    init_db()
    # Proteger todas las rutas excepto login/logout y estáticos
    if not session.get("autenticado"):
        if request.endpoint not in ("login", "logout", "static"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "No autorizado"}), 401
            return redirect(url_for("login"))


# ──────────────────────────────────────────────
# FRONTEND
# ──────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        usuario = request.form.get("usuario", "")
        password = request.form.get("password", "")
        if usuario == APP_USER and password == APP_PASSWORD:
            session["autenticado"] = True
            return redirect(url_for("index"))
        error = "Usuario o contraseña incorrectos"
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
@login_required
def index():
    from flask import make_response
    resp = make_response(render_template("index.html"))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    return resp


# ──────────────────────────────────────────────
# API — DASHBOARD
# ──────────────────────────────────────────────

@app.route("/api/dashboard")
def api_dashboard():
    """Stats resumidas + evolución del bankroll + últimas 5 apuestas."""
    todas = get_stats_raw()
    stats = calcular_stats(todas)

    # Últimas 5 apuestas (ya vienen ordenadas por fecha desc)
    apuestas_all = get_apuestas()
    ultimas = apuestas_all[:5]

    # Evolución del bankroll día a día
    # Acumula ganancia_neta de las apuestas resueltas ordenadas por fecha asc
    resueltas_asc = sorted(
        [a for a in todas if a["estado"] in ("ganada", "perdida") and a["ganancia_neta"] is not None],
        key=lambda x: (x["fecha"], x.get("created_at", "")),
    )

    bankroll_labels = []
    bankroll_data = []
    acumulado = 0.0

    # Agrupar por fecha
    fechas_vistas = {}
    for a in resueltas_asc:
        fecha = a["fecha"]
        if fecha not in fechas_vistas:
            fechas_vistas[fecha] = 0.0
        fechas_vistas[fecha] += a["ganancia_neta"]

    for fecha in sorted(fechas_vistas.keys()):
        acumulado += fechas_vistas[fecha]
        bankroll_labels.append(fecha)
        bankroll_data.append(round(acumulado, 2))

    # Fondos por bookie
    bookies = get_bookies()
    fondos_iniciales_total = sum(b.get("fondos_iniciales") or 0 for b in bookies)
    fondos_actuales_total = sum(b.get("fondos_actuales") or 0 for b in bookies)

    # Próxima actualización de stake (cada 15 días desde fecha de inicio)
    cfg = _load_config()
    inicio_str = cfg.get("stake_start_date")

    # Si no hay fecha guardada, usar la primera apuesta
    if not inicio_str:
        apuestas_all_fechas = get_apuestas()
        if apuestas_all_fechas:
            fechas = sorted(a["fecha"] for a in apuestas_all_fechas)
            inicio_str = fechas[0]

    stake_info = {}
    if inicio_str:
        inicio = date.fromisoformat(inicio_str)
        hoy = date.today()
        dias_transcurridos = (hoy - inicio).days
        periodos = dias_transcurridos // 15
        proxima = inicio + timedelta(days=(periodos + 1) * 15)
        dias_restantes = (proxima - hoy).days
        stake_info = {
            "inicio": inicio_str,
            "proxima_actualizacion": proxima.isoformat(),
            "dias_restantes": dias_restantes,
            "periodo_actual": periodos + 1,
        }

    return jsonify({
        "stats": stats,
        "ultimas_apuestas": ultimas,
        "bankroll": {
            "labels": bankroll_labels,
            "data": bankroll_data,
        },
        "fondos": {
            "iniciales": round(fondos_iniciales_total, 2),
            "actuales": round(fondos_actuales_total, 2),
            "por_bookie": [
                {
                    "nombre": b["nombre"],
                    "actuales": round(b.get("fondos_actuales") or 0, 2),
                    "iniciales": round(b.get("fondos_iniciales") or 0, 2),
                }
                for b in bookies if b.get("activo")
            ],
        },
        "stake_info": stake_info,
        "retiros_total": round(sum(r["monto"] for r in get_retiros()), 2),
    })


# ──────────────────────────────────────────────
# API — PARSER
# ──────────────────────────────────────────────

@app.route("/api/parse-ticket", methods=["POST"])
def api_parse_ticket():
    body = request.get_json(force=True, silent=True) or {}
    texto = body.get("texto", "")
    if not texto.strip():
        return jsonify({"error": "Texto vacío"}), 400
    resultado = parse_ticket(texto)
    return jsonify(resultado)


@app.route("/api/parse-imagen", methods=["POST"])
def api_parse_imagen():
    """Extrae texto de una captura de pantalla con OCR y lo parsea."""
    body = request.get_json(force=True, silent=True) or {}
    imagen_data = body.get("imagen", "")

    if not imagen_data:
        return jsonify({"error": "No se recibió imagen"}), 400

    try:
        import pytesseract
        from PIL import Image
        import io

        # Decodificar imagen base64
        header, b64 = imagen_data.split(",", 1)
        img_bytes = base64.b64decode(b64)
        img = Image.open(io.BytesIO(img_bytes))

        # Extraer texto con OCR (español + inglés)
        texto = pytesseract.image_to_string(img, lang="spa+eng")

        if not texto.strip():
            return jsonify({"error": "No se pudo extraer texto de la imagen. Intentá con una imagen más clara."}), 400

        # Usar el parser existente sobre el texto extraído
        resultado = parse_ticket(texto)
        resultado["texto_ocr"] = texto  # devolver el texto para debug
        return jsonify(resultado)

    except Exception as e:
        return jsonify({"error": f"Error al analizar imagen: {str(e)}"}), 500


# ──────────────────────────────────────────────
# API — APUESTAS
# ──────────────────────────────────────────────

@app.route("/api/apuestas", methods=["GET"])
def api_get_apuestas():
    bookie_id = request.args.get("bookie_id", type=int)
    estado = request.args.get("estado")
    fecha_desde = request.args.get("fecha_desde")
    fecha_hasta = request.args.get("fecha_hasta")

    apuestas = get_apuestas(
        bookie_id=bookie_id,
        estado=estado,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )
    return jsonify(apuestas)


@app.route("/api/apuestas", methods=["POST"])
def api_crear_apuesta():
    body = request.get_json(force=True, silent=True) or {}

    # Validación básica
    campos_requeridos = ["bookie_id", "fecha", "evento", "cuota", "stake", "prob_estimada"]
    for campo in campos_requeridos:
        if campo not in body or body[campo] is None or body[campo] == "":
            return jsonify({"error": f"Campo requerido: {campo}"}), 400

    try:
        apuesta = registrar_apuesta(
            bookie_id=int(body["bookie_id"]),
            fecha=body["fecha"],
            evento=body["evento"],
            mercado=body.get("mercado", ""),
            seleccion=body.get("seleccion", ""),
            cuota=float(body["cuota"]),
            stake=float(body["stake"]),
            prob_estimada=float(body["prob_estimada"]) / 100,  # llega como % (ej: 55 → 0.55)
            notas=body.get("notas", ""),
            ticket_raw=body.get("ticket_raw", ""),
        )
        return jsonify(apuesta), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/apuestas/<int:apuesta_id>/resolver", methods=["PUT"])
def api_resolver_apuesta(apuesta_id):
    body = request.get_json(force=True, silent=True) or {}
    estado = body.get("estado")
    if estado not in ("ganada", "perdida", "void", "anulada"):
        return jsonify({"error": "Estado inválido. Usar: ganada, perdida, void, anulada"}), 400

    try:
        apuesta = resolver_apuesta(apuesta_id, estado)
        return jsonify(apuesta)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/apuestas/<int:apuesta_id>", methods=["DELETE"])
def api_eliminar_apuesta(apuesta_id):
    eliminada = delete_apuesta(apuesta_id)
    if not eliminada:
        return jsonify({"error": "Apuesta no encontrada"}), 404
    return jsonify({"ok": True})


# ──────────────────────────────────────────────
# API — RETIROS
# ──────────────────────────────────────────────

@app.route("/api/retiros", methods=["GET"])
def api_get_retiros():
    bookie_id = request.args.get("bookie_id", type=int)
    return jsonify(get_retiros(bookie_id=bookie_id))

@app.route("/api/retiros/<int:retiro_id>", methods=["DELETE"])
def api_eliminar_retiro(retiro_id):
    eliminado = delete_retiro(retiro_id)
    if not eliminado:
        return jsonify({"error": "Retiro no encontrado"}), 404
    return jsonify({"ok": True})


# ──────────────────────────────────────────────
# API — CONFIG
# ──────────────────────────────────────────────

@app.route("/api/config", methods=["GET"])
def api_get_config():
    return jsonify(_load_config())

@app.route("/api/config", methods=["POST"])
def api_set_config():
    body = request.get_json(force=True, silent=True) or {}
    cfg = _load_config()
    cfg.update(body)
    _save_config(cfg)
    return jsonify(cfg)


# ──────────────────────────────────────────────
# API — STATS
# ──────────────────────────────────────────────

@app.route("/api/stats")
def api_stats():
    todas = get_stats_raw()
    globales = calcular_stats(todas)
    por_bookie = stats_por_bookie()

    # Datos para gráfico de barras P&L por bookie
    bookie_labels = list(por_bookie.keys())
    bookie_pnl = [por_bookie[b]["ganancia_neta"] for b in bookie_labels]
    bookie_roi = [por_bookie[b]["roi"] for b in bookie_labels]

    return jsonify({
        "globales": globales,
        "por_bookie": por_bookie,
        "grafico_bookie": {
            "labels": bookie_labels,
            "pnl": bookie_pnl,
            "roi": bookie_roi,
        },
    })


# ──────────────────────────────────────────────
# API — BOOKIES
# ──────────────────────────────────────────────

@app.route("/api/bookies", methods=["GET"])
def api_get_bookies():
    solo_activos = request.args.get("solo_activos", "false").lower() == "true"
    bookies = listar_bookies(solo_activos=solo_activos)
    return jsonify(bookies)


@app.route("/api/bookies", methods=["POST"])
def api_crear_bookie():
    body = request.get_json(force=True, silent=True) or {}
    nombre = body.get("nombre", "").strip()
    if not nombre:
        return jsonify({"error": "Nombre requerido"}), 400

    fondos_iniciales = body.get("fondos_iniciales", 0) or 0
    bookie_id = add_bookie(nombre, fondos_iniciales)
    if bookie_id is None:
        return jsonify({"error": f"El bookie '{nombre}' ya existe"}), 409

    bookies = get_bookies()
    bookie = next((b for b in bookies if b["id"] == bookie_id), {"id": bookie_id, "nombre": nombre, "activo": 1, "fondos_iniciales": fondos_iniciales, "fondos_actuales": fondos_iniciales})
    return jsonify(bookie), 201


@app.route("/api/bookies/<int:bookie_id>", methods=["PUT"])
def api_actualizar_bookie(bookie_id):
    body = request.get_json(force=True, silent=True) or {}
    bookie = get_bookie_by_id(bookie_id)
    if not bookie:
        return jsonify({"error": "Bookie no encontrado"}), 404

    if "activo" in body:
        toggle_bookie(bookie_id, activo=bool(body["activo"]))

    if "nuevo_balance" in body:
        # El usuario edita el balance actual directamente.
        # Calculamos fondos_actuales actual para saber el delta.
        bookies_list = get_bookies()
        bookie_data = next((b for b in bookies_list if b["id"] == bookie_id), None)
        fondos_actuales = bookie_data["fondos_actuales"] if bookie_data else 0
        nuevo_balance = float(body["nuevo_balance"])
        delta = fondos_actuales - nuevo_balance  # positivo = retiro, negativo = re-fondeo
        if abs(delta) > 0.001:
            notas = "Retiro de ganancias" if delta > 0 else "Re-fondeo"
            insert_retiro(bookie_id, round(delta, 2), notas)

    elif "fondos_iniciales" in body:
        update_fondos_bookie(bookie_id, float(body["fondos_iniciales"]))

    bookies = get_bookies()
    updated = next((b for b in bookies if b["id"] == bookie_id), None) or get_bookie_by_id(bookie_id)
    return jsonify(updated)


@app.route("/api/bookies/<int:bookie_id>", methods=["DELETE"])
def api_eliminar_bookie(bookie_id):
    resultado = delete_bookie(bookie_id)
    if resultado == "not_found":
        return jsonify({"error": "Bookie no encontrado"}), 404
    if resultado == "tiene_apuestas":
        return jsonify({"error": "No se puede eliminar: el bookie tiene apuestas registradas"}), 409
    return jsonify({"ok": True})


# ──────────────────────────────────────────────
# API — CALENDARIO
# ──────────────────────────────────────────────

@app.route("/api/calendario")
def api_calendario():
    year  = request.args.get("year",  type=int, default=datetime.now().year)
    month = request.args.get("month", type=int, default=datetime.now().month)

    # Todas las apuestas del mes
    desde = f"{year:04d}-{month:02d}-01"
    import calendar as cal_mod
    ultimo_dia = cal_mod.monthrange(year, month)[1]
    hasta = f"{year:04d}-{month:02d}-{ultimo_dia:02d}"

    apuestas = get_apuestas(fecha_desde=desde, fecha_hasta=hasta)

    # Agrupar por día
    dias = {}
    for a in apuestas:
        d = a["fecha"]
        if d not in dias:
            dias[d] = {"apuestas": 0, "stake": 0, "ganancia_neta": 0,
                       "ganadas": 0, "perdidas": 0, "pendientes": 0, "items": []}
        dias[d]["apuestas"] += 1
        dias[d]["stake"] += a["stake"] or 0
        if a["estado"] == "ganada":
            dias[d]["ganadas"] += 1
            dias[d]["ganancia_neta"] += a["ganancia_neta"] or 0
        elif a["estado"] == "perdida":
            dias[d]["perdidas"] += 1
            dias[d]["ganancia_neta"] += a["ganancia_neta"] or 0
        elif a["estado"] == "pendiente":
            dias[d]["pendientes"] += 1
        dias[d]["items"].append(a)

    # Resumen del mes
    total_apuestas  = sum(d["apuestas"]      for d in dias.values())
    total_stake     = sum(d["stake"]         for d in dias.values())
    total_ganancia  = sum(d["ganancia_neta"] for d in dias.values())
    dias_positivos  = sum(1 for d in dias.values() if d["ganancia_neta"] > 0)

    return jsonify({
        "year": year, "month": month,
        "dias": dias,
        "resumen": {
            "apuestas":     total_apuestas,
            "stake":        round(total_stake, 2),
            "ganancia_neta":round(total_ganancia, 2),
            "dias_positivos": dias_positivos,
        }
    })


# ──────────────────────────────────────────────
# API — COLA DE CAPTURAS
# ──────────────────────────────────────────────

CAPTURAS_DIR = os.path.join(os.path.dirname(__file__), "data", "capturas")


def _ensure_capturas_dir():
    os.makedirs(CAPTURAS_DIR, exist_ok=True)


@app.route("/capturas/<filename>")
def serve_captura(filename):
    """Sirve una imagen guardada en data/capturas/."""
    _ensure_capturas_dir()
    return send_from_directory(CAPTURAS_DIR, filename)


@app.route("/api/capturas", methods=["GET"])
def api_get_capturas():
    """Lista archivos PNG guardados, ordenados por fecha DESC."""
    _ensure_capturas_dir()
    archivos = []
    for fname in os.listdir(CAPTURAS_DIR):
        if not fname.lower().endswith(".png"):
            continue
        fpath = os.path.join(CAPTURAS_DIR, fname)
        mtime = os.path.getmtime(fpath)
        dt = datetime.fromtimestamp(mtime)
        archivos.append({
            "id": fname[:-4],  # nombre sin extensión
            "filename": fname,
            "timestamp": dt.strftime("%d/%m/%Y %H:%M"),
            "url": f"/capturas/{fname}",
            "_mtime": mtime,
        })
    archivos.sort(key=lambda x: x["_mtime"], reverse=True)
    for a in archivos:
        del a["_mtime"]
    return jsonify(archivos)


@app.route("/api/capturas", methods=["POST"])
def api_guardar_captura():
    """Guarda una imagen base64 como PNG en data/capturas/."""
    _ensure_capturas_dir()
    body = request.get_json(force=True, silent=True) or {}
    imagen_data = body.get("imagen", "")

    if not imagen_data:
        return jsonify({"error": "No se recibió imagen"}), 400

    try:
        # El data URL puede venir con o sin header
        if "," in imagen_data:
            _, b64 = imagen_data.split(",", 1)
        else:
            b64 = imagen_data

        img_bytes = base64.b64decode(b64)

        # Nombre único: timestamp + 4 chars random
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        rand = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
        filename = f"{ts}_{rand}.png"
        fpath = os.path.join(CAPTURAS_DIR, filename)

        with open(fpath, "wb") as f:
            f.write(img_bytes)

        return jsonify({
            "id": filename[:-4],
            "filename": filename,
            "url": f"/capturas/{filename}",
        }), 201

    except Exception as e:
        return jsonify({"error": f"Error al guardar imagen: {str(e)}"}), 500


@app.route("/api/capturas/<captura_id>", methods=["DELETE"])
def api_eliminar_captura(captura_id):
    """Elimina una captura por su id (nombre sin extensión)."""
    _ensure_capturas_dir()
    filename = f"{captura_id}.png"
    fpath = os.path.join(CAPTURAS_DIR, filename)

    if not os.path.exists(fpath):
        return jsonify({"error": "Archivo no encontrado"}), 404

    try:
        os.remove(fpath)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

# ──────────────────────────────────────────────
# BACKUP
# ──────────────────────────────────────────────

@app.route("/api/backup/db")
def api_backup_db():
    """Descarga la base de datos SQLite completa."""
    from database import DB_PATH
    fecha = datetime.now().strftime("%Y-%m-%d_%H-%M")
    return send_file(
        DB_PATH,
        as_attachment=True,
        download_name=f"apuestas_backup_{fecha}.db",
        mimetype="application/octet-stream"
    )

@app.route("/api/backup/csv")
def api_backup_csv():
    """Descarga todas las apuestas como CSV."""
    import csv, io
    apuestas = get_apuestas()
    if not apuestas:
        return jsonify({"error": "Sin datos"}), 404

    output = io.StringIO()
    campos = ["id","fecha","bookie_nombre","evento","mercado","seleccion",
              "cuota","stake","prob_estimada","ev_percent","estado","ganancia_neta","notas"]
    writer = csv.DictWriter(output, fieldnames=campos, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(apuestas)

    fecha = datetime.now().strftime("%Y-%m-%d")
    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8")),
        as_attachment=True,
        download_name=f"apuestas_{fecha}.csv",
        mimetype="text/csv"
    )


if __name__ == "__main__":
    init_db()
    print("╔══════════════════════════════════════╗")
    print("║   Apuestas de Valor — App Web        ║")
    import socket
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        local_ip = "tu-ip-local"
    print(f"║   Local:  http://localhost:8080      ║")
    print(f"║   Red:    http://{local_ip}:8080")
    print("╚══════════════════════════════════════╝")
    app.run(debug=False, host='0.0.0.0', port=8080)
