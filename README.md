# Value Betting Tracker

Sistema de seguimiento de apuestas de valor (value betting) en terminal. Registrá tus apuestas, calculá el EV, analizá tu rendimiento y gestioná tus bookies, todo desde la línea de comandos.

---

## Características

- **Parseo de tickets**: pegás el texto del ticket de tu bookie y el sistema extrae cuota, stake, fecha y evento automáticamente.
- **Cálculo de EV**: ingresás tu probabilidad estimada y el sistema calcula el Expected Value al instante.
- **Dashboard**: resumen visual al iniciar con P&L del día, semana, total y bankroll activo.
- **Historial filtrable**: por bookie, estado y rango de fechas.
- **Estadísticas completas**: ROI, winrate, EV acumulado, EV real vs esperado, racha actual, desglose por bookie.
- **Gestión de bookies**: incluye Bet365, Betano, Unibet, Pinnacle, Betsson y Codere por defecto.

---

## Instalación

### 1. Clonar / tener el proyecto

```bash
cd "Software Apuestas de valor"
```

### 2. Crear entorno virtual (recomendado)

```bash
python3 -m venv venv
source venv/bin/activate   # macOS/Linux
# venv\Scripts\activate    # Windows
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

---

## Uso

```bash
python src/main.py
```

Al iniciar verás el dashboard con tu resumen. Navegá el menú con las flechas del teclado y Enter.

---

## Menú principal

| Opción | Descripción |
|--------|-------------|
| **1. Registrar apuesta** | Pegá un ticket o ingresá datos manualmente. Pide tu prob. estimada y muestra el EV antes de confirmar. |
| **2. Resolver apuesta** | Marcá una apuesta pendiente como ganada, perdida o void. Calcula automáticamente el P&L. |
| **3. Ver historial** | Listado de todas las apuestas con filtros opcionales. |
| **4. Estadísticas** | ROI, winrate, EV, rachas — global, por bookie o por período. |
| **5. Gestionar bookies** | Agregar, activar o desactivar bookies. |

---

## Cómo funciona el parseo de tickets

Cuando seleccionás "Registrar apuesta" y elegís pegar un ticket, el sistema intenta extraer:

- **Cuota**: detecta patrones como `@1.85`, `cuota: 1.85`, `2.50x`
- **Stake**: detecta `$50`, `stake: 100`, `€25`
- **Fecha**: formatos `DD/MM/YYYY`, `YYYY-MM-DD`, `20 de marzo de 2025`
- **Evento**: busca el patrón `Equipo A vs Equipo B`

Los campos que no se puedan extraer los tenés que completar vos manualmente.

---

## Cálculo de EV

```
EV% = (probabilidad_estimada × cuota - 1) × 100
```

- EV% positivo = apuesta de valor (verde)
- EV% negativo = sin valor (rojo)

Ejemplo: si estimás 55% de probabilidad a cuota 2.10
`EV% = (0.55 × 2.10 - 1) × 100 = +15.5%`

---

## Estructura del proyecto

```
proyecto/
├── src/
│   ├── main.py        # Entry point y menús
│   ├── database.py    # SQLite, tablas y queries
│   ├── parser.py      # Parseo de tickets en texto libre
│   ├── bets.py        # Lógica de apuestas y EV
│   ├── bookies.py     # Gestión de bookies
│   ├── stats.py       # Estadísticas y ROI
│   └── ui.py          # Componentes visuales con rich
├── data/              # Base de datos (ignorada en git)
├── requirements.txt
├── .gitignore
└── README.md
```

---

## Dependencias

- [rich](https://github.com/Textualize/rich) — tablas y colores en terminal
- [questionary](https://github.com/tmbo/questionary) — menús interactivos
