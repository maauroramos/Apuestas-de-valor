# CLAUDE.md — Software de Apuestas de Valor

## Contexto del usuario
Soy un apostador de valor (value betting). Mi estrategia se basa en identificar apuestas donde mi probabilidad estimada supera la implícita en la cuota del bookie, generando un edge (exceso de valor) positivo. Haciendo volumen de apuestas con edge positivo, estadísticamente gano ese exceso de valor a largo plazo.

## Objetivo del proyecto
Crear un sistema ejecutable donde el usuario pueda:
- Pegar el ticket de una apuesta y que el sistema la registre automáticamente
- Ver el historial de apuestas día a día y bookie a bookie
- Registrar ganancias, pérdidas, stake, cuota, probabilidad estimada, EV (expected value)
- Gestionar entre 6 y 7 bookies distintos (agregables desde dentro del programa)
- Ver estadísticas: ROI, ganancia neta, racha, EV acumulado vs resultado real, etc.

## Notas técnicas
- El programa debe ser fácil de usar: el usuario pega el ticket → el sistema lo parsea y registra
- Los datos deben persistir localmente (archivo JSON o SQLite)
- Interfaz de línea de comandos (CLI) interactiva o con menús claros
- Los bookies se gestionan desde dentro del programa (agregar, listar, etc.)
- Nunca perder datos históricos
