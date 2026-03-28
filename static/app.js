/* ================================================
   APUESTAS DE VALOR — Lógica frontend SPA
   ================================================ */

// ── Estado global de la app ──────────────────
const state = {
  bookies: [],
  chartBankroll: null,
  chartBookie: null,
};

// ── Sidebar mobile ────────────────────────────
function toggleSidebar() {
  document.getElementById("sidebar").classList.toggle("open");
  document.getElementById("sidebar-overlay").classList.toggle("open");
}
function closeSidebar() {
  document.getElementById("sidebar").classList.remove("open");
  document.getElementById("sidebar-overlay").classList.remove("open");
}

// ── Navegación entre secciones ───────────────
function showSection(name) {
  closeSidebar();
  document.querySelectorAll(".section").forEach(s => s.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach(n => n.classList.remove("active"));

  document.getElementById(`section-${name}`).classList.add("active");
  document.querySelector(`[data-section="${name}"]`).classList.add("active");

  // Cargar datos de la sección
  if (name === "dashboard")   loadDashboard();
  if (name === "apuestas")    loadApuestas();
  if (name === "stats")       loadStats();
  if (name === "bookies")     loadBookies();
  if (name === "nueva")       prepNuevaApuesta();
  if (name === "cola")        loadCola();
  if (name === "calendario")  loadCalendario();
  if (name === "reglas")      loadReglas();
  if (name === "retiros")     loadRetiros();
}

// ── Toast notifications ───────────────────────
function toast(msg, type = "info") {
  const container = document.getElementById("toast-container");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = msg;
  container.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

// ── Helpers ───────────────────────────────────
function fmt(n, decimals = 2) {
  if (n === null || n === undefined || isNaN(n)) return "—";
  const num = parseFloat(n).toFixed(decimals);
  return num;
}

function fmtMoney(n) {
  if (n === null || n === undefined || isNaN(n)) return "—";
  const sign = n >= 0 ? "+" : "";
  return `${sign}$${parseFloat(n).toFixed(2)}`;
}

function colorMoney(n) {
  if (n > 0) return "text-green";
  if (n < 0) return "text-red";
  return "text-muted";
}

function badgeEstado(estado) {
  const map = {
    ganada:    { cls: "badge-ganada",    label: "W" },
    perdida:   { cls: "badge-perdida",   label: "L" },
    pendiente: { cls: "badge-pendiente", label: "Pendiente" },
    void:      { cls: "badge-void",      label: "D" },
    anulada:   { cls: "badge-void",      label: "D" },
  };
  const e = map[estado] || { cls: "", label: estado };
  return `<span class="badge ${e.cls}">${e.label}</span>`;
}

// ── API helper ────────────────────────────────
async function api(path, method = "GET", body = null) {
  const opts = {
    method,
    headers: { "Content-Type": "application/json" },
  };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Error desconocido");
  return data;
}

// ═══════════════════════════════════════════
// DASHBOARD
// ═══════════════════════════════════════════
async function loadDashboard() {
  try {
    const [data, pendientes] = await Promise.all([
      api("/api/dashboard"),
      api("/api/apuestas?estado=pendiente"),
    ]);
    renderDashboardStats(data.stats);
    renderBankrollChart(data.bankroll);
    renderPendientesDashboard(pendientes);
    renderUltimasApuestas(data.ultimas_apuestas);
    renderFondosDashboard(data.fondos);
    renderStakeUpdateInfo(data.stake_info);
  } catch (e) {
    toast("Error cargando dashboard: " + e.message, "error");
  }
}

function renderPendientesDashboard(apuestas) {
  const tbody = document.getElementById("dash-pendientes-tbody");
  const badge = document.getElementById("dash-pendientes-badge");

  badge.textContent = apuestas.length || "";
  badge.style.display = apuestas.length ? "inline" : "none";

  if (!apuestas.length) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:24px;color:var(--text-muted)">No tenés apuestas pendientes 🎉</td></tr>`;
    return;
  }

  tbody.innerHTML = apuestas.map(a => {
    const evClass = a.ev_percent >= 0 ? "text-green" : "text-red";
    return `
      <tr>
        <td>${a.fecha}</td>
        <td>${a.bookie_nombre}</td>
        <td style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${a.evento}">${a.evento}</td>
        <td>${fmt(a.cuota, 3)}</td>
        <td>$${fmt(a.stake)}</td>
        <td class="${evClass}">${a.ev_percent >= 0 ? '+' : ''}${fmt(a.ev_percent)}%</td>
        <td>
          <div class="flex gap-8">
            <button class="btn btn-success btn-sm" onclick="resolverApuestaDesdePanel(${a.id},'ganada')">W</button>
            <button class="btn btn-danger btn-sm"  onclick="resolverApuestaDesdePanel(${a.id},'perdida')">L</button>
            <button class="btn btn-ghost btn-sm"   onclick="resolverApuestaDesdePanel(${a.id},'anulada')">D</button>
          </div>
        </td>
      </tr>
    `;
  }).join("");
}

async function resolverApuestaDesdePanel(id, estado) {
  try {
    await api(`/api/apuestas/${id}/resolver`, "PUT", { estado });
    const labels = { ganada: "W", perdida: "L", void: "D", anulada: "D" };
    toast(`Apuesta marcada como ${labels[estado]}`, "success");
    loadDashboard(); // refresca todo el dashboard
  } catch (e) {
    toast("Error al resolver: " + e.message, "error");
  }
}

function renderFondosDashboard(fondos) {
  if (!fondos) return;

  const diff = fondos.actuales - fondos.iniciales;
  const diffPct = fondos.iniciales > 0 ? (diff / fondos.iniciales * 100) : 0;
  const diffClass = diff > 0 ? "hero-up" : diff < 0 ? "hero-down" : "hero-neutral";
  const diffSign = diff >= 0 ? "+" : "";
  const stakeRecomendado = fondos.actuales * 0.03;

  document.getElementById("dash-hero-total").textContent = `$${fmt(fondos.actuales)}`;
  document.getElementById("dash-hero-total").className = `bankroll-hero-value ${diffClass}`;

  const diffLabel = fondos.iniciales > 0
    ? `${diffSign}$${fmt(Math.abs(diff))} (${diffSign}${fmt(diffPct)}%) vs inicio`
    : "Sin fondos iniciales cargados";
  document.getElementById("dash-hero-diff").textContent = diffLabel;
  document.getElementById("dash-hero-diff").className = `bankroll-hero-sub ${diffClass}`;

  document.getElementById("dash-hero-stake").textContent =
    `Stake sugerido (3%): $${fmt(stakeRecomendado)}`;

  // Desglose por bookie
  const bookies = fondos.por_bookie || [];
  document.getElementById("dash-hero-bookies").innerHTML = bookies.length
    ? bookies.map(b => {
        const d = b.actuales - b.iniciales;
        const cls = d > 0 ? "hero-up" : d < 0 ? "hero-down" : "hero-neutral";
        const sign = d >= 0 ? "+" : "";
        return `
          <div class="bookie-chip">
            <span class="bookie-chip-name">${b.nombre}</span>
            <span class="bookie-chip-amount">$${fmt(b.actuales)}</span>
            <span class="bookie-chip-diff ${cls}">${sign}$${fmt(Math.abs(d))}</span>
          </div>
        `;
      }).join("")
    : `<div style="color:var(--text-muted);font-size:13px">Agregá bookies para ver el desglose</div>`;
}

function renderStakeUpdateInfo(info) {
  const el = document.getElementById("dash-stake-update");
  if (!el) return;
  if (!info || !info.proxima_actualizacion) {
    el.innerHTML = `<span style="font-size:12px;color:var(--text-muted)">Cargá tu primera apuesta para activar el ciclo de 15 días</span>`;
    return;
  }
  const dias = info.dias_restantes;
  const fecha = info.proxima_actualizacion;
  const urgente = dias <= 2;
  const color = urgente ? "var(--accent-red)" : dias <= 5 ? "var(--accent-yellow)" : "var(--text-muted)";
  el.innerHTML = `
    <span style="font-size:12px;color:${color};border:1px solid ${color};border-radius:4px;padding:3px 8px;display:inline-block">
      ${urgente ? "⚠️ " : "🗓 "}Próximo ajuste de stake: ${fecha} — ${dias} día${dias !== 1 ? "s" : ""}
    </span>
  `;
}

// ═══════════════════════════════════════════
// REGLAS DE STAKE
// ═══════════════════════════════════════════

// Tablas base calibradas para stake $40
const REGLAS_EV = [
  { min: 2.5,  max: 3.99,  label: "2.5% – 3.99%",  base: 0  },
  { min: 4,    max: 5.99,  label: "4% – 5.99%",     base: 5  },
  { min: 6,    max: 7.99,  label: "6% – 7.99%",     base: 10 },
  { min: 8,    max: 11.99, label: "8% – 11.99%",    base: 15 },
  { min: 12,   max: 14.99, label: "12% – 14.99%",   base: 20 },
  { min: 15,   max: 19.99, label: "15% – 19.99%",   base: 25 },
  { min: 20,   max: 24.99, label: "20% – 24.99%",   base: 30 },
  { min: 25,   max: 29.99, label: "25% – 29.99%",   base: 40 },
  { min: 30,   max: 34.99, label: "30% – 34.99%",   base: 55 },
  { min: 35,   max: 40.99, label: "35% – 40.99%",   base: 70 },
];

const REGLAS_PROB = [
  { min: 25, max: 30, label: "25% – 30%", base: -35 },
  { min: 30, max: 35, label: "30% – 35%", base: -25 },
  { min: 35, max: 40, label: "35% – 40%", base: -15 },
  { min: 40, max: 45, label: "40% – 45%", base: -5  },
  { min: 45, max: 55, label: "45% – 55%", base: 0   },
  { min: 55, max: 60, label: "55% – 60%", base: 5   },
  { min: 60, max: 65, label: "60% – 65%", base: 15  },
  { min: 65, max: 70, label: "65% – 70%", base: 25  },
  { min: 70, max: 75, label: "70% – 75%", base: 40  },
  { min: 75, max: 80, label: "75% – 80%", base: 55  },
];

async function loadReglas() {
  try {
    const [dash, cfg] = await Promise.all([
      api("/api/dashboard"),
      api("/api/config"),
    ]);
    const stakeBase = round2(dash.fondos.actuales * 0.03);
    renderReglasTablas(stakeBase);

    document.getElementById("reglas-stake-base").textContent = `$${fmt(stakeBase)}`;
    if (cfg.stake_start_date) {
      document.getElementById("reglas-fecha-inicio").value = cfg.stake_start_date;
    }
  } catch (e) {
    toast("Error cargando reglas: " + e.message, "error");
  }
}

function renderReglasTablas(stakeBase) {
  const ratio = stakeBase / 40;

  document.getElementById("reglas-ev-tbody").innerHTML = REGLAS_EV.map(r => {
    const ajuste = round2(r.base * ratio);
    const final  = round2(stakeBase + ajuste);
    const cls    = ajuste > 0 ? "text-green" : ajuste < 0 ? "text-red" : "text-muted";
    const sign   = ajuste >= 0 ? "+" : "";
    return `
      <tr>
        <td>${r.label}</td>
        <td class="${cls}">${sign}$${fmt(ajuste)}</td>
        <td style="font-weight:700">$${fmt(final)}</td>
      </tr>
    `;
  }).join("");

  document.getElementById("reglas-prob-tbody").innerHTML = REGLAS_PROB.map(r => {
    const ajuste = round2(r.base * ratio);
    const final  = round2(stakeBase + ajuste);
    const cls    = ajuste > 0 ? "text-green" : ajuste < 0 ? "text-red" : "text-muted";
    const sign   = ajuste >= 0 ? "+" : "";
    return `
      <tr>
        <td>${r.label}</td>
        <td class="${cls}">${sign}$${fmt(ajuste)}</td>
        <td style="font-weight:700">$${fmt(final)}</td>
      </tr>
    `;
  }).join("");
}

function round2(n) { return Math.round(n * 100) / 100; }

// ═══════════════════════════════════════════
// RETIROS DE GANANCIA
// ═══════════════════════════════════════════
async function loadRetiros() {
  try {
    const retiros = await api("/api/retiros");
    renderRetiros(retiros);
  } catch (e) {
    toast("Error cargando retiros: " + e.message, "error");
  }
}

function renderRetiros(retiros) {
  const totalRetirado  = retiros.filter(r => r.monto > 0).reduce((s, r) => s + r.monto, 0);
  const totalRefondeo  = retiros.filter(r => r.monto < 0).reduce((s, r) => s + Math.abs(r.monto), 0);
  const neto           = totalRetirado - totalRefondeo;

  document.getElementById("retiros-total-monto").textContent   = `$${fmt(totalRetirado)}`;
  document.getElementById("retiros-refondeo-monto").textContent = `$${fmt(totalRefondeo)}`;
  document.getElementById("retiros-neto-monto").textContent    = `$${fmt(neto)}`;
  document.getElementById("retiros-neto-monto").className      = `stat-value ${neto >= 0 ? "positive" : "negative"}`;

  const tbody = document.getElementById("retiros-tbody");
  if (!retiros.length) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:32px;color:var(--text-muted)">Sin retiros registrados</td></tr>`;
    return;
  }

  tbody.innerHTML = retiros.map(r => {
    const esRetiro = r.monto > 0;
    const tipo     = esRetiro ? `<span class="badge badge-ganada">Retiro</span>` : `<span class="badge badge-pendiente">Re-fondeo</span>`;
    const montoStr = esRetiro
      ? `<span class="text-green">+$${fmt(r.monto)}</span>`
      : `<span class="text-red">-$${fmt(Math.abs(r.monto))}</span>`;
    return `
      <tr>
        <td>${r.fecha}</td>
        <td>${r.bookie_nombre}</td>
        <td>${tipo}</td>
        <td style="font-weight:600">${montoStr}</td>
        <td>
          <button class="btn btn-ghost btn-sm" onclick="eliminarRetiro(${r.id})" title="Eliminar" style="color:var(--text-muted)">🗑</button>
        </td>
      </tr>
    `;
  }).join("");
}

async function eliminarRetiro(id) {
  if (!confirm("¿Eliminar este registro? El balance del bookie no se revertirá automáticamente.")) return;
  try {
    await api(`/api/retiros/${id}`, "DELETE");
    toast("Registro eliminado", "success");
    loadRetiros();
  } catch (e) {
    toast("Error: " + e.message, "error");
  }
}

async function guardarFechaInicio() {
  const fecha = document.getElementById("reglas-fecha-inicio").value;
  if (!fecha) { toast("Seleccioná una fecha", "error"); return; }
  try {
    await api("/api/config", "POST", { stake_start_date: fecha });
    toast("Fecha de inicio guardada", "success");
    loadDashboard();
  } catch (e) {
    toast("Error: " + e.message, "error");
  }
}

function renderDashboardStats(s) {
  const pnlClass = s.ganancia_neta >= 0 ? "positive" : "negative";
  const roiClass = s.roi >= 0 ? "positive" : "negative";

  document.getElementById("dash-pnl").innerHTML = `
    <div class="stat-label">P&L Total</div>
    <div class="stat-value ${pnlClass}">${fmtMoney(s.ganancia_neta)}</div>
    <div class="stat-sub">Ganancia neta acumulada</div>
  `;
  document.getElementById("dash-roi").innerHTML = `
    <div class="stat-label">ROI %</div>
    <div class="stat-value ${roiClass}">${fmt(s.roi)}%</div>
    <div class="stat-sub">Sobre stake resuelto</div>
  `;
  document.getElementById("dash-ev").innerHTML = `
    <div class="stat-label">EV Acumulado</div>
    <div class="stat-value neutral">$${fmt(s.ev_acumulado)}</div>
    <div class="stat-sub">Expected value total</div>
  `;
  document.getElementById("dash-stake").innerHTML = `
    <div class="stat-label">Stake en Juego</div>
    <div class="stat-value warning">$${fmt(s.stake_pendiente)}</div>
    <div class="stat-sub">${s.pendientes} apuesta${s.pendientes !== 1 ? "s" : ""} pendiente${s.pendientes !== 1 ? "s" : ""}</div>
  `;
  document.getElementById("dash-winrate").innerHTML = `
    <div class="stat-label">Win Rate</div>
    <div class="stat-value neutral">${fmt(s.winrate)}%</div>
    <div class="stat-sub">${s.ganadas}W / ${s.perdidas}L</div>
  `;
  document.getElementById("dash-racha").innerHTML = `
    <div class="stat-label">Racha actual</div>
    <div class="stat-value ${s.racha.startsWith('+') ? 'positive' : s.racha === '0' ? '' : 'negative'}">${s.racha}</div>
    <div class="stat-sub">${s.total} apuestas totales</div>
  `;
}

function renderBankrollChart(bankroll) {
  const ctx = document.getElementById("chart-bankroll").getContext("2d");

  if (state.chartBankroll) {
    state.chartBankroll.destroy();
  }

  if (!bankroll.labels.length) {
    document.getElementById("chart-bankroll").style.display = "none";
    document.getElementById("chart-bankroll-empty").style.display = "block";
    return;
  }

  document.getElementById("chart-bankroll").style.display = "block";
  document.getElementById("chart-bankroll-empty").style.display = "none";

  // Colores del gradiente
  const gradient = ctx.createLinearGradient(0, 0, 0, 260);
  gradient.addColorStop(0, "rgba(59, 130, 246, 0.25)");
  gradient.addColorStop(1, "rgba(59, 130, 246, 0.0)");

  state.chartBankroll = new Chart(ctx, {
    type: "line",
    data: {
      labels: bankroll.labels,
      datasets: [{
        label: "P&L Acumulado ($)",
        data: bankroll.data,
        borderColor: "#3b82f6",
        backgroundColor: gradient,
        borderWidth: 2.5,
        pointRadius: bankroll.labels.length > 30 ? 0 : 4,
        pointHoverRadius: 6,
        pointBackgroundColor: "#3b82f6",
        fill: true,
        tension: 0.35,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "#1c2333",
          borderColor: "#2a3650",
          borderWidth: 1,
          titleColor: "#94a3b8",
          bodyColor: "#e2e8f0",
          callbacks: {
            label: ctx => ` $${ctx.parsed.y.toFixed(2)}`,
          },
        },
      },
      scales: {
        x: {
          grid: { color: "rgba(42,54,80,0.5)" },
          ticks: { color: "#64748b", maxTicksLimit: 8, font: { size: 11 } },
        },
        y: {
          grid: { color: "rgba(42,54,80,0.5)" },
          ticks: {
            color: "#64748b",
            font: { size: 11 },
            callback: v => `$${v}`,
          },
        },
      },
    },
  });
}

function renderUltimasApuestas(apuestas) {
  const tbody = document.getElementById("dash-ultimas-tbody");
  if (!apuestas.length) {
    tbody.innerHTML = `<tr><td colspan="6" class="text-muted" style="text-align:center;padding:24px">Sin apuestas registradas</td></tr>`;
    return;
  }
  tbody.innerHTML = apuestas.map(a => `
    <tr>
      <td>${a.fecha}</td>
      <td>${a.bookie_nombre}</td>
      <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${a.evento}">${a.evento}</td>
      <td>${fmt(a.cuota, 3)}</td>
      <td>$${fmt(a.stake)}</td>
      <td>${badgeEstado(a.estado)}</td>
    </tr>
  `).join("");
}

// ═══════════════════════════════════════════
// NUEVA APUESTA
// ═══════════════════════════════════════════
async function prepNuevaApuesta() {
  // Cargar bookies en el select
  await loadBookiesIntoSelect("nueva-bookie");
  // Poner fecha de hoy por defecto
  const today = new Date().toISOString().split("T")[0];
  document.getElementById("nueva-fecha").value = today;
  calcularEVPreview();
}

async function loadBookiesIntoSelect(selectId) {
  try {
    const bookies = await api("/api/bookies?solo_activos=true");
    state.bookies = bookies;
    const select = document.getElementById(selectId);
    const currentVal = select.value; // preservar selección actual antes de reconstruir
    const defaultLabel = selectId === "filtro-bookie" ? "Todos" : "— Seleccionar —";
    select.innerHTML = `<option value="">${defaultLabel}</option>` +
      bookies.map(b => `<option value="${b.id}">${b.nombre}</option>`).join("");
    if (currentVal) select.value = currentVal; // restaurar selección
  } catch (e) {
    toast("Error cargando bookies", "error");
  }
}

function calcularEVPreview() {
  const cuota = parseFloat(document.getElementById("nueva-cuota").value);
  const prob  = parseFloat(document.getElementById("nueva-prob").value);
  const evEl  = document.getElementById("ev-preview");

  if (isNaN(cuota) || isNaN(prob) || cuota <= 0 || prob <= 0) {
    evEl.textContent = "—";
    evEl.className = "ev-value";
    return;
  }

  const ev = (prob / 100) * cuota - 1;
  const evPct = (ev * 100).toFixed(2);

  evEl.textContent = `${evPct > 0 ? "+" : ""}${evPct}%`;
  evEl.className = `ev-value ${evPct > 0 ? "positive" : "negative"}`;
}

// ═══════════════════════════════════════════
// IMAGEN — captura de pantalla
// ═══════════════════════════════════════════
let imagenDataUrl = null;

function switchTicketTab(tab) {
  document.getElementById("tab-texto").classList.toggle("active", tab === "texto");
  document.getElementById("tab-imagen").classList.toggle("active", tab === "imagen");
  document.getElementById("panel-texto").style.display = tab === "texto" ? "" : "none";
  document.getElementById("panel-imagen").style.display = tab === "imagen" ? "" : "none";
}

function setImagenPreview(dataUrl) {
  imagenDataUrl = dataUrl;
  const preview = document.getElementById("imagen-preview");
  const content = document.getElementById("drop-zone-content");
  const zone    = document.getElementById("drop-zone");
  const btnAnal = document.getElementById("btn-analizar-imagen");
  const btnLimp = document.getElementById("btn-limpiar-imagen");

  preview.src = dataUrl;
  preview.style.display = "block";
  content.style.display = "none";
  zone.classList.add("has-image");
  btnAnal.disabled = false;
  btnLimp.style.display = "";
  document.getElementById("imagen-status").textContent = "Imagen lista. Hacé clic en Analizar con IA.";
}

function limpiarImagen() {
  imagenDataUrl = null;
  const preview = document.getElementById("imagen-preview");
  const content = document.getElementById("drop-zone-content");
  const zone    = document.getElementById("drop-zone");

  preview.src = "";
  preview.style.display = "none";
  content.style.display = "";
  zone.classList.remove("has-image");
  document.getElementById("btn-analizar-imagen").disabled = true;
  document.getElementById("btn-limpiar-imagen").style.display = "none";
  document.getElementById("imagen-status").textContent = "";
  document.getElementById("file-input-imagen").value = "";
}

function handleImagenFile(input) {
  const file = input.files[0];
  if (!file || !file.type.startsWith("image/")) return;
  const reader = new FileReader();
  reader.onload = e => setImagenPreview(e.target.result);
  reader.readAsDataURL(file);
}

async function analizarImagen() {
  if (!imagenDataUrl) { toast("No hay imagen cargada", "error"); return; }

  const btn = document.getElementById("btn-analizar-imagen");
  const status = document.getElementById("imagen-status");
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> Analizando...`;
  status.textContent = "Claude está analizando el ticket...";

  try {
    const data = await api("/api/parse-imagen", "POST", { imagen: imagenDataUrl });

    if (data.cuota)     document.getElementById("nueva-cuota").value = data.cuota;
    if (data.stake)     document.getElementById("nueva-stake").value = data.stake;
    if (data.fecha)     document.getElementById("nueva-fecha").value = data.fecha;
    if (data.evento)    document.getElementById("nueva-evento").value = data.evento;
    if (data.mercado)   document.getElementById("nueva-mercado").value = data.mercado;
    if (data.seleccion) document.getElementById("nueva-seleccion").value = data.seleccion;

    // Intentar preseleccionar bookie si lo detectó
    if (data.bookie) {
      const sel = document.getElementById("nueva-bookie");
      for (const opt of sel.options) {
        if (opt.text.toLowerCase().includes(data.bookie.toLowerCase())) {
          sel.value = opt.value;
          break;
        }
      }
    }

    calcularEVPreview();
    const found = Object.values(data).filter((v, k) => v !== null && k !== 'texto_ocr').length;
    status.textContent = `✓ ${found} campos detectados. Revisá y completá los datos.`;
    toast(`Imagen analizada — ${found} campos detectados`, "success");

    // Mostrar texto OCR para debug
    if (data.texto_ocr) {
      let debugEl = document.getElementById("ocr-debug");
      if (!debugEl) {
        debugEl = document.createElement("div");
        debugEl.id = "ocr-debug";
        debugEl.style.cssText = "margin-top:12px;padding:12px;background:#0f1117;border:1px solid #2a3650;border-radius:8px;font-size:12px;color:#64748b;white-space:pre-wrap;max-height:150px;overflow-y:auto";
        document.getElementById("panel-imagen").appendChild(debugEl);
      }
      debugEl.textContent = "Texto OCR extraído:\n" + data.texto_ocr;
    }
  } catch (e) {
    status.textContent = "";
    toast("Error al analizar imagen: " + e.message, "error");
  } finally {
    btn.disabled = false;
    btn.innerHTML = `🤖 Analizar con IA`;
  }
}

// Capturar Ctrl+V en cualquier lugar cuando el panel imagen está visible
document.addEventListener("paste", e => {
  const panelImagen = document.getElementById("panel-imagen");
  if (!panelImagen || panelImagen.style.display === "none") return;
  const items = e.clipboardData?.items;
  if (!items) return;
  for (const item of items) {
    if (item.type.startsWith("image/")) {
      const blob = item.getAsFile();
      const reader = new FileReader();
      reader.onload = ev => setImagenPreview(ev.target.result);
      reader.readAsDataURL(blob);
      e.preventDefault();
      break;
    }
  }
});

// Drag & drop sobre la drop zone
document.addEventListener("DOMContentLoaded", () => {
  const zone = document.getElementById("drop-zone");
  if (!zone) return;
  zone.addEventListener("dragover", e => { e.preventDefault(); zone.classList.add("drag-over"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("drag-over"));
  zone.addEventListener("drop", e => {
    e.preventDefault();
    zone.classList.remove("drag-over");
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith("image/")) {
      const reader = new FileReader();
      reader.onload = ev => setImagenPreview(ev.target.result);
      reader.readAsDataURL(file);
    }
  });
});

async function parsearTicket() {
  const texto = document.getElementById("ticket-raw").value.trim();
  if (!texto) { toast("Pegá el ticket primero", "error"); return; }

  const btn = document.getElementById("btn-parsear");
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> Parseando...`;

  try {
    const data = await api("/api/parse-ticket", "POST", { texto });
    // Rellenar campos
    if (data.cuota)    document.getElementById("nueva-cuota").value = data.cuota;
    if (data.stake)    document.getElementById("nueva-stake").value = data.stake;
    if (data.fecha)    document.getElementById("nueva-fecha").value = data.fecha;
    if (data.evento)   document.getElementById("nueva-evento").value = data.evento;
    if (data.mercado)  document.getElementById("nueva-mercado").value = data.mercado;
    if (data.seleccion) document.getElementById("nueva-seleccion").value = data.seleccion;

    calcularEVPreview();

    const found = Object.values(data).filter(v => v !== null).length;
    toast(`Ticket parseado — ${found} campo${found !== 1 ? "s" : ""} detectado${found !== 1 ? "s" : ""}`, "success");
  } catch (e) {
    toast("Error al parsear: " + e.message, "error");
  } finally {
    btn.disabled = false;
    btn.innerHTML = `🔍 Parsear ticket`;
  }
}

async function guardarApuesta() {
  const bookie_id = document.getElementById("nueva-bookie").value;
  const fecha     = document.getElementById("nueva-fecha").value;
  const evento    = document.getElementById("nueva-evento").value.trim();
  const mercado   = document.getElementById("nueva-mercado").value.trim();
  const seleccion = document.getElementById("nueva-seleccion").value.trim();
  const cuota     = document.getElementById("nueva-cuota").value;
  const stake     = document.getElementById("nueva-stake").value;
  const prob      = document.getElementById("nueva-prob").value;
  const notas     = document.getElementById("nueva-notas").value.trim();
  const ticket_raw = document.getElementById("ticket-raw").value.trim();

  // Validaciones frontend
  if (!bookie_id) { toast("Seleccioná un bookie", "error"); return; }
  if (!fecha)     { toast("Ingresá la fecha", "error"); return; }
  if (!evento)    { toast("Ingresá el evento", "error"); return; }
  if (!cuota || isNaN(cuota) || parseFloat(cuota) <= 1) {
    toast("Cuota inválida (debe ser > 1)", "error"); return;
  }
  if (!stake || isNaN(stake) || parseFloat(stake) <= 0) {
    toast("Stake inválido", "error"); return;
  }
  if (!prob || isNaN(prob) || parseFloat(prob) <= 0 || parseFloat(prob) >= 100) {
    toast("Probabilidad inválida (1–99%)", "error"); return;
  }

  const btn = document.getElementById("btn-guardar");
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> Guardando...`;

  try {
    await api("/api/apuestas", "POST", {
      bookie_id: parseInt(bookie_id),
      fecha,
      evento,
      mercado,
      seleccion,
      cuota: parseFloat(cuota),
      stake: parseFloat(stake),
      prob_estimada: parseFloat(prob),
      notas,
      ticket_raw,
    });

    toast("Apuesta guardada correctamente", "success");
    limpiarFormularioNueva();
    showSection("apuestas");
  } catch (e) {
    toast("Error al guardar: " + e.message, "error");
  } finally {
    btn.disabled = false;
    btn.innerHTML = `💾 Guardar apuesta`;
  }
}

function limpiarFormularioNueva() {
  ["ticket-raw","nueva-evento","nueva-mercado","nueva-seleccion",
   "nueva-cuota","nueva-stake","nueva-notas"].forEach(id => {
    document.getElementById(id).value = "";
  });
  document.getElementById("nueva-prob").value = "";
  document.getElementById("nueva-bookie").value = "";
  const today = new Date().toISOString().split("T")[0];
  document.getElementById("nueva-fecha").value = today;
  calcularEVPreview();
}

// ═══════════════════════════════════════════
// MIS APUESTAS
// ═══════════════════════════════════════════
async function loadApuestas() {
  // Cargar bookies en el filtro solo si aún no están cargados
  const filtroSelect = document.getElementById("filtro-bookie");
  if (filtroSelect.options.length <= 1) {
    await loadBookiesIntoSelect("filtro-bookie");
  }

  const bookie_id  = document.getElementById("filtro-bookie").value;
  const estado     = document.getElementById("filtro-estado").value;
  const fecha_desde = document.getElementById("filtro-desde").value;
  const fecha_hasta = document.getElementById("filtro-hasta").value;

  let url = "/api/apuestas?";
  if (bookie_id)   url += `bookie_id=${bookie_id}&`;
  if (estado)      url += `estado=${estado}&`;
  if (fecha_desde) url += `fecha_desde=${fecha_desde}&`;
  if (fecha_hasta) url += `fecha_hasta=${fecha_hasta}&`;

  try {
    const apuestas = await api(url);
    renderTablaApuestas(apuestas);
  } catch (e) {
    toast("Error cargando apuestas: " + e.message, "error");
  }
}

function renderTablaApuestas(apuestas) {
  const tbody = document.getElementById("apuestas-tbody");

  if (!apuestas.length) {
    tbody.innerHTML = `<tr><td colspan="9" style="text-align:center;padding:32px;color:var(--text-muted)">No hay apuestas con esos filtros</td></tr>`;
    return;
  }

  tbody.innerHTML = apuestas.map(a => {
    const pnlStr = a.ganancia_neta !== null
      ? `<span class="${colorMoney(a.ganancia_neta)}">${fmtMoney(a.ganancia_neta)}</span>`
      : "—";

    const acciones = a.estado === "pendiente" ? `
      <div class="flex gap-8">
        <button class="btn btn-success btn-sm" onclick="resolverApuesta(${a.id},'ganada')">W</button>
        <button class="btn btn-danger btn-sm"  onclick="resolverApuesta(${a.id},'perdida')">L</button>
        <button class="btn btn-ghost btn-sm"   onclick="resolverApuesta(${a.id},'anulada')">D</button>
        <button class="btn btn-ghost btn-sm"   onclick="eliminarApuesta(${a.id})" title="Eliminar" style="color:var(--text-muted)">🗑</button>
      </div>
    ` : `<button class="btn btn-ghost btn-sm" onclick="eliminarApuesta(${a.id})" title="Eliminar" style="color:var(--text-muted)">🗑</button>`;

    const evClass = a.ev_percent >= 0 ? "text-green" : "text-red";

    return `
      <tr>
        <td>${a.fecha}</td>
        <td>${a.bookie_nombre}</td>
        <td style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${a.evento}">${a.evento}</td>
        <td>${fmt(a.cuota, 3)}</td>
        <td>$${fmt(a.stake)}</td>
        <td class="${evClass}">${a.ev_percent >= 0 ? '+' : ''}${fmt(a.ev_percent)}%</td>
        <td>${badgeEstado(a.estado)}</td>
        <td>${pnlStr}</td>
        <td>${acciones}</td>
      </tr>
    `;
  }).join("");
}

async function resolverApuesta(id, estado) {
  try {
    await api(`/api/apuestas/${id}/resolver`, "PUT", { estado });
    const labels = { ganada: "W", perdida: "L", void: "D", anulada: "D" };
    toast(`Apuesta marcada como ${labels[estado]}`, "success");
    loadApuestas();
  } catch (e) {
    toast("Error al resolver: " + e.message, "error");
  }
}

async function eliminarApuesta(id) {
  if (!confirm("¿Eliminar esta apuesta? Esta acción no se puede deshacer.")) return;
  try {
    await api(`/api/apuestas/${id}`, "DELETE");
    toast("Apuesta eliminada", "success");
    loadApuestas();
  } catch (e) {
    toast("Error al eliminar: " + e.message, "error");
  }
}

// ═══════════════════════════════════════════
// ESTADÍSTICAS
// ═══════════════════════════════════════════
async function loadStats() {
  try {
    const data = await api("/api/stats");
    renderStatsCards(data.globales);
    renderStatsPorBookie(data.por_bookie);
    renderChartBookie(data.grafico_bookie);
  } catch (e) {
    toast("Error cargando estadísticas: " + e.message, "error");
  }
}

function renderStatsCards(s) {
  document.getElementById("stats-cards").innerHTML = `
    <div class="stat-card">
      <div class="stat-label">P&L Neto</div>
      <div class="stat-value ${s.ganancia_neta >= 0 ? 'positive' : 'negative'}">${fmtMoney(s.ganancia_neta)}</div>
      <div class="stat-sub">Ganancia real acumulada</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">ROI %</div>
      <div class="stat-value ${s.roi >= 0 ? 'positive' : 'negative'}">${fmt(s.roi)}%</div>
      <div class="stat-sub">Return on Investment</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Total Apostado</div>
      <div class="stat-value neutral">$${fmt(s.stake_total)}</div>
      <div class="stat-sub">Stake acumulado</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">EV Esperado</div>
      <div class="stat-value neutral">$${fmt(s.ev_acumulado)}</div>
      <div class="stat-sub">EV real: $${fmt(s.ev_realizado)}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Win Rate</div>
      <div class="stat-value">${fmt(s.winrate)}%</div>
      <div class="stat-sub">${s.ganadas}G / ${s.perdidas}P / ${s.voids}V</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Cuota Promedio</div>
      <div class="stat-value">${fmt(s.cuota_promedio, 3)}</div>
      <div class="stat-sub">EV prom: ${fmt(s.ev_promedio)}%</div>
    </div>
  `;
}

function renderStatsPorBookie(por_bookie) {
  const tbody = document.getElementById("stats-bookie-tbody");
  const entries = Object.entries(por_bookie);

  if (!entries.length) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:24px;color:var(--text-muted)">Sin datos</td></tr>`;
    return;
  }

  tbody.innerHTML = entries.map(([nombre, s]) => `
    <tr>
      <td><strong>${nombre}</strong></td>
      <td>${s.total}</td>
      <td class="text-green">${s.ganadas}</td>
      <td class="text-red">${s.perdidas}</td>
      <td class="${s.roi >= 0 ? 'text-green' : 'text-red'}">${fmt(s.roi)}%</td>
      <td class="${colorMoney(s.ganancia_neta)}">${fmtMoney(s.ganancia_neta)}</td>
      <td>$${fmt(s.stake_total)}</td>
    </tr>
  `).join("");
}

function renderChartBookie(grafico) {
  const ctx = document.getElementById("chart-bookie").getContext("2d");

  if (state.chartBookie) {
    state.chartBookie.destroy();
  }

  if (!grafico.labels.length) {
    return;
  }

  const colors = grafico.pnl.map(v => v >= 0 ? "rgba(34,197,94,0.7)" : "rgba(239,68,68,0.7)");
  const borderColors = grafico.pnl.map(v => v >= 0 ? "#22c55e" : "#ef4444");

  state.chartBookie = new Chart(ctx, {
    type: "bar",
    data: {
      labels: grafico.labels,
      datasets: [{
        label: "P&L ($)",
        data: grafico.pnl,
        backgroundColor: colors,
        borderColor: borderColors,
        borderWidth: 1,
        borderRadius: 4,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "#1c2333",
          borderColor: "#2a3650",
          borderWidth: 1,
          titleColor: "#94a3b8",
          bodyColor: "#e2e8f0",
          callbacks: {
            label: ctx => ` $${ctx.parsed.y.toFixed(2)}`,
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: "#64748b", font: { size: 12 } },
        },
        y: {
          grid: { color: "rgba(42,54,80,0.5)" },
          ticks: {
            color: "#64748b",
            font: { size: 11 },
            callback: v => `$${v}`,
          },
        },
      },
    },
  });
}

// ═══════════════════════════════════════════
// BOOKIES
// ═══════════════════════════════════════════
async function loadBookies() {
  try {
    const bookies = await api("/api/bookies");
    renderBookiesList(bookies);
  } catch (e) {
    toast("Error cargando bookies: " + e.message, "error");
  }
}

function renderBookiesList(bookies) {
  const container = document.getElementById("bookies-list");

  if (!bookies.length) {
    container.innerHTML = `<div class="empty-state"><div class="empty-icon">📋</div><p>Sin bookies registrados</p></div>`;
    return;
  }

  container.innerHTML = bookies.map(b => {
    const fondosIni = b.fondos_iniciales || 0;
    const fondosAct = b.fondos_actuales != null ? b.fondos_actuales : fondosIni;
    const diff = fondosAct - fondosIni;
    const diffClass = diff > 0 ? "text-green" : diff < 0 ? "text-red" : "text-muted";
    const diffStr = diff >= 0 ? `+$${fmt(diff)}` : `-$${fmt(Math.abs(diff))}`;
    const sinFondos = fondosIni === 0;

    return `
    <div class="bookie-card ${b.activo ? '' : 'inactive'}" id="bookie-card-${b.id}">
      <div style="flex:1">
        <div class="bookie-name">${b.nombre}</div>
        <div class="bookie-status">${b.activo ? "Activo" : "Inactivo"}</div>
        ${sinFondos ? `
          <div style="margin-top:10px">
            <button class="btn btn-ghost btn-sm" onclick="openEditarFondosModal(${b.id}, '${b.nombre}', ${fondosIni})">
              + Agregar fondos iniciales
            </button>
          </div>
        ` : `
          <div class="fondos-info" style="margin-top:10px;display:flex;gap:24px;align-items:center;flex-wrap:wrap">
            <div>
              <div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;letter-spacing:.05em">Fondos iniciales</div>
              <div style="font-size:16px;font-weight:600;color:var(--text-primary)">$${fmt(fondosIni)}</div>
            </div>
            <div>
              <div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;letter-spacing:.05em">Fondos actuales</div>
              <div style="font-size:16px;font-weight:600;color:var(--text-primary)">$${fmt(fondosAct)}</div>
            </div>
            <div>
              <div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;letter-spacing:.05em">Resultado</div>
              <div style="font-size:16px;font-weight:600" class="${diffClass}">${diffStr}</div>
            </div>
            <button class="btn btn-ghost btn-sm" onclick="openEditarFondosModal(${b.id}, '${b.nombre}', ${fondosIni})" style="margin-left:auto">
              ✏️ Editar
            </button>
          </div>
        `}
      </div>
      <div style="display:flex;flex-direction:column;align-items:center;gap:12px;margin-left:16px;flex-shrink:0">
        <label class="toggle" title="${b.activo ? 'Desactivar' : 'Activar'}">
          <input type="checkbox" ${b.activo ? "checked" : ""}
                 onchange="toggleBookie(${b.id}, this.checked)">
          <span class="toggle-slider"></span>
        </label>
        <button class="btn btn-ghost btn-sm" onclick="eliminarBookie(${b.id}, '${b.nombre}')"
                title="Eliminar bookie" style="color:var(--text-muted)">🗑</button>
      </div>
    </div>
  `;
  }).join("");
}

async function toggleBookie(id, activo) {
  try {
    await api(`/api/bookies/${id}`, "PUT", { activo: activo ? 1 : 0 });
    const card = document.getElementById(`bookie-card-${id}`);
    const statusEl = card.querySelector(".bookie-status");
    if (activo) {
      card.classList.remove("inactive");
      statusEl.textContent = "Activo";
    } else {
      card.classList.add("inactive");
      statusEl.textContent = "Inactivo";
    }
    toast(`Bookie ${activo ? "activado" : "desactivado"}`, "success");
  } catch (e) {
    toast("Error: " + e.message, "error");
  }
}

async function eliminarBookie(id, nombre) {
  if (!confirm(`¿Eliminar el bookie "${nombre}"?\n\nSolo se puede eliminar si no tiene apuestas registradas.`)) return;
  try {
    await api(`/api/bookies/${id}`, "DELETE");
    toast(`Bookie "${nombre}" eliminado`, "success");
    loadBookies();
  } catch (e) {
    toast(e.message, "error");
  }
}

// Modal agregar bookie
function openAddBookieModal() {
  document.getElementById("modal-nuevo-bookie").classList.add("open");
  document.getElementById("input-nuevo-bookie").value = "";
  document.getElementById("input-fondos-iniciales").value = "";
  document.getElementById("input-nuevo-bookie").focus();
}

function closeAddBookieModal() {
  document.getElementById("modal-nuevo-bookie").classList.remove("open");
}

async function confirmarNuevoBookie() {
  const nombre = document.getElementById("input-nuevo-bookie").value.trim();
  if (!nombre) { toast("Ingresá un nombre", "error"); return; }
  const fondos = parseFloat(document.getElementById("input-fondos-iniciales").value) || 0;

  try {
    await api("/api/bookies", "POST", { nombre, fondos_iniciales: fondos });
    toast(`Bookie "${nombre}" agregado`, "success");
    closeAddBookieModal();
    loadBookies();
  } catch (e) {
    toast("Error: " + e.message, "error");
  }
}

// Modal editar fondos de bookie existente
function openEditarFondosModal(id, nombre, fondosActuales) {
  document.getElementById("modal-editar-fondos").classList.add("open");
  document.getElementById("modal-fondos-bookie-nombre").textContent = nombre;
  document.getElementById("modal-fondos-bookie-actual").textContent = `Balance actual: $${fmt(fondosActuales)}`;
  document.getElementById("input-editar-fondos").value = "";
  document.getElementById("input-editar-fondos-id").value = id;
  document.getElementById("input-editar-fondos").focus();
}

function closeEditarFondosModal() {
  document.getElementById("modal-editar-fondos").classList.remove("open");
}

async function confirmarEditarFondos() {
  const id = parseInt(document.getElementById("input-editar-fondos-id").value);
  const nuevoBalance = parseFloat(document.getElementById("input-editar-fondos").value);
  if (isNaN(nuevoBalance) || nuevoBalance < 0) { toast("Ingresá un monto válido", "error"); return; }

  try {
    await api(`/api/bookies/${id}`, "PUT", { nuevo_balance: nuevoBalance });
    toast("Balance actualizado", "success");
    closeEditarFondosModal();
    loadBookies();
  } catch (e) {
    toast("Error: " + e.message, "error");
  }
}

// Enter en modales
document.addEventListener("DOMContentLoaded", () => {
  const addListener = (id, event, fn) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener(event, fn);
  };

  addListener("input-nuevo-bookie", "keydown", e => {
    if (e.key === "Enter") confirmarNuevoBookie();
    if (e.key === "Escape") closeAddBookieModal();
  });
  addListener("input-fondos-iniciales", "keydown", e => {
    if (e.key === "Enter") confirmarNuevoBookie();
    if (e.key === "Escape") closeAddBookieModal();
  });
  addListener("modal-nuevo-bookie", "click", e => {
    if (e.target === e.currentTarget) closeAddBookieModal();
  });

  addListener("input-editar-fondos", "keydown", e => {
    if (e.key === "Enter") confirmarEditarFondos();
    if (e.key === "Escape") closeEditarFondosModal();
  });
  addListener("modal-editar-fondos", "click", e => {
    if (e.target === e.currentTarget) closeEditarFondosModal();
  });
});

// ═══════════════════════════════════════════
// COLA DE TICKETS
// ═══════════════════════════════════════════

async function loadCola() {
  try {
    const capturas = await api("/api/capturas");
    renderColaGrid(capturas);
    actualizarBadgeCola(capturas.length);
  } catch (e) {
    toast("Error cargando cola: " + e.message, "error");
  }
}

function actualizarBadgeCola(cantidad) {
  // Badge en el nav item
  const navBadge = document.getElementById("nav-cola-badge");
  if (navBadge) {
    navBadge.textContent = cantidad;
    navBadge.classList.toggle("visible", cantidad > 0);
  }
  // Badge en el header de la sección
  const countBadge = document.getElementById("cola-count-badge");
  if (countBadge) {
    countBadge.textContent = `${cantidad} pendiente${cantidad !== 1 ? "s" : ""}`;
    countBadge.classList.toggle("visible", cantidad > 0);
  }
}

function renderColaGrid(capturas) {
  const grid = document.getElementById("cola-grid");
  if (!capturas.length) {
    grid.innerHTML = `
      <div class="empty-state" style="grid-column:1/-1">
        <div class="empty-icon">📭</div>
        <p>No hay capturas guardadas. Usá Ctrl+V para pegar una.</p>
      </div>
    `;
    return;
  }

  grid.innerHTML = capturas.map(c => `
    <div class="cola-card" id="cola-card-${c.id}">
      <div class="cola-card-thumb">
        <img src="${c.url}" alt="Captura ${c.timestamp}" loading="lazy" />
      </div>
      <div class="cola-card-footer">
        <span class="cola-card-date">${c.timestamp}</span>
        <button class="cola-card-delete" onclick="eliminarCaptura('${c.id}')" title="Eliminar">✕</button>
      </div>
    </div>
  `).join("");
}

async function eliminarCaptura(id) {
  try {
    await api(`/api/capturas/${id}`, "DELETE");
    toast("Captura eliminada", "success");
    loadCola();
  } catch (e) {
    toast("Error al eliminar: " + e.message, "error");
  }
}

// Pegar imagen con Ctrl+V cuando la sección cola está activa
document.addEventListener("paste", e => {
  const seccionCola = document.getElementById("section-cola");
  if (!seccionCola || !seccionCola.classList.contains("active")) return;

  const items = e.clipboardData?.items;
  if (!items) return;

  for (const item of items) {
    if (item.type.startsWith("image/")) {
      const blob = item.getAsFile();
      const reader = new FileReader();
      reader.onload = async ev => {
        try {
          await api("/api/capturas", "POST", { imagen: ev.target.result });
          toast("Captura guardada", "success");
          loadCola();
        } catch (err) {
          toast("Error al guardar captura: " + err.message, "error");
        }
      };
      reader.readAsDataURL(blob);
      e.preventDefault();
      break;
    }
  }
});

// Drag & drop en la cola drop zone
document.addEventListener("DOMContentLoaded", () => {
  const zone = document.getElementById("cola-drop-zone");
  if (!zone) return;

  zone.addEventListener("dragover", e => {
    e.preventDefault();
    zone.classList.add("drag-over");
  });
  zone.addEventListener("dragleave", () => zone.classList.remove("drag-over"));
  zone.addEventListener("drop", async e => {
    e.preventDefault();
    zone.classList.remove("drag-over");
    const file = e.dataTransfer.files[0];
    if (!file || !file.type.startsWith("image/")) return;

    const reader = new FileReader();
    reader.onload = async ev => {
      try {
        await api("/api/capturas", "POST", { imagen: ev.target.result });
        toast("Captura guardada", "success");
        loadCola();
      } catch (err) {
        toast("Error al guardar captura: " + err.message, "error");
      }
    };
    reader.readAsDataURL(file);
  });
});

// ═══════════════════════════════════════════
// CALENDARIO
// ═══════════════════════════════════════════
const calState = { year: new Date().getFullYear(), month: new Date().getMonth() + 1 };

async function loadCalendario() {
  try {
    const data = await api(`/api/calendario?year=${calState.year}&month=${calState.month}`);
    renderCalTitulo();
    renderCalResumen(data.resumen);
    renderCalGrid(data.year, data.month, data.dias);
    document.getElementById("cal-detalle-card").style.display = "none";
  } catch (e) {
    toast("Error cargando calendario: " + e.message, "error");
  }
}

function calCambiarMes(delta) {
  calState.month += delta;
  if (calState.month > 12) { calState.month = 1;  calState.year++; }
  if (calState.month < 1)  { calState.month = 12; calState.year--; }
  loadCalendario();
}

function renderCalTitulo() {
  const meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                 "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"];
  document.getElementById("cal-titulo").textContent =
    `${meses[calState.month - 1]} ${calState.year}`;
}

function renderCalResumen(r) {
  const pnlClass = r.ganancia_neta >= 0 ? "positive" : "negative";
  document.getElementById("cal-resumen").innerHTML = `
    <div class="stat-card">
      <div class="stat-label">Apuestas del mes</div>
      <div class="stat-value neutral">${r.apuestas}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Stake del mes</div>
      <div class="stat-value neutral">$${fmt(r.stake)}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">P&L del mes</div>
      <div class="stat-value ${pnlClass}">${fmtMoney(r.ganancia_neta)}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Días positivos</div>
      <div class="stat-value positive">${r.dias_positivos}</div>
    </div>
  `;
}

function renderCalGrid(year, month, dias) {
  const grid = document.getElementById("cal-grid");
  const totalDias = new Date(year, month, 0).getDate();
  // Lunes=0 ... Domingo=6
  let primerDia = new Date(year, month - 1, 1).getDay();
  primerDia = primerDia === 0 ? 6 : primerDia - 1; // ajustar lunes=0

  let html = "";

  // Celdas vacías antes del primer día
  for (let i = 0; i < primerDia; i++) {
    html += `<div class="cal-day cal-day-empty"></div>`;
  }

  for (let d = 1; d <= totalDias; d++) {
    const key = `${year}-${String(month).padStart(2,"0")}-${String(d).padStart(2,"0")}`;
    const info = dias[key];
    const hoy = new Date();
    const esHoy = (d === hoy.getDate() && month === hoy.getMonth()+1 && year === hoy.getFullYear());

    let clase = "cal-day";
    let contenido = "";

    if (info) {
      const pnl = info.ganancia_neta;
      const tienePendientes = info.pendientes > 0;
      if (tienePendientes && pnl === 0) clase += " cal-day-pendiente";
      else if (pnl > 0)  clase += " cal-day-ganado";
      else if (pnl < 0)  clase += " cal-day-perdido";
      else               clase += " cal-day-neutro";

      const pnlStr = pnl >= 0
        ? `<span class="cal-pnl positive">+$${fmt(Math.abs(pnl))}</span>`
        : `<span class="cal-pnl negative">-$${fmt(Math.abs(pnl))}</span>`;

      contenido = `
        <div class="cal-day-num">${d}</div>
        <div class="cal-day-bets">${info.apuestas} apuesta${info.apuestas !== 1 ? "s" : ""}</div>
        ${pnlStr}
        ${info.pendientes > 0 ? `<span class="cal-pending">${info.pendientes} pend.</span>` : ""}
      `;
    } else {
      contenido = `<div class="cal-day-num">${d}</div>`;
    }

    if (esHoy) clase += " cal-day-hoy";

    html += `<div class="${clase}" onclick="calVerDia('${key}')">${contenido}</div>`;
  }

  grid.innerHTML = html;
}

async function calVerDia(fecha) {
  try {
    const apuestas = await api(`/api/apuestas?fecha_desde=${fecha}&fecha_hasta=${fecha}`);
    const card = document.getElementById("cal-detalle-card");
    const titulo = document.getElementById("cal-detalle-titulo");
    const tbody = document.getElementById("cal-detalle-tbody");

    // Formatear fecha para mostrar
    const [y, m, d] = fecha.split("-");
    titulo.textContent = `${d}/${m}/${y}`;

    if (!apuestas.length) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:20px;color:var(--text-muted)">Sin apuestas este día</td></tr>`;
    } else {
      tbody.innerHTML = apuestas.map(a => {
        const pnl = a.ganancia_neta !== null
          ? `<span class="${a.ganancia_neta >= 0 ? 'text-green' : 'text-red'}">${fmtMoney(a.ganancia_neta)}</span>`
          : "—";
        return `<tr>
          <td>${a.bookie_nombre}</td>
          <td style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${a.evento}</td>
          <td>${a.seleccion || "—"}</td>
          <td>${fmt(a.cuota, 3)}</td>
          <td>$${fmt(a.stake)}</td>
          <td>${badgeEstado(a.estado)}</td>
          <td>${pnl}</td>
        </tr>`;
      }).join("");
    }

    card.style.display = "block";
    card.scrollIntoView({ behavior: "smooth", block: "nearest" });
  } catch (e) {
    toast("Error cargando detalle: " + e.message, "error");
  }
}

// ── Inicialización ────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  showSection("dashboard");
  // Cargar badge de cola en segundo plano
  api("/api/capturas").then(c => actualizarBadgeCola(c.length)).catch(() => {});
});
