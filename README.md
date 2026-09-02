# sico-pandas-lab

Herramienta web de análisis de datos: sube un Excel y obtén un tablero de
análisis automático sin escribir código, o practica pandas con un notebook y
un módulo guiado. Repositorio standalone, no adjunto todavía a la
arquitectura oficial de SICO — pendiente de aprobación del dueño del
producto.

**Documentación canónica (no duplicada aquí):**

- PRD: `../_bmad-output/prd-sico-pandas-lab-2026-07-12.md`
- Arquitectura: `../_bmad-output/architecture-sico-pandas-lab-2026-07-12.md`
- Épicas e Historias: `../_bmad-output/epics-sico-pandas-lab-2026-07-12.md`
- Sprint status: `../_bmad-output/sprint-status-sico-pandas-lab.yaml`
- Cómo probar/levantar en local, y qué hacer si algo se cae: **[COMO_PROBAR.md](./COMO_PROBAR.md)**

## Módulos

- **Sin código** (`/sin-codigo`) — sube un Excel, confirma qué es cada
  columna (sugerido por IA, corregible con un clic) y obtén un tablero de
  análisis Pareto generado automáticamente. Puro pandas por debajo; la IA
  solo clasifica columnas y redacta texto — nunca calcula.
- **Notebook** (`/notebook`) — celdas de código pandas libres, para quien
  quiere escribir Python de verdad.
- **Módulo guiado** (`/guiado`) — 6 lecciones progresivas de pandas, con
  retos verificados en el servidor. Usa tus propios datos si ya subiste un
  Excel; si no, cae en un ejemplo sintético.
- **Convatec** (`frontend/src/app/convatec`, `backend/app/convatec`) —
  módulo de negocio para un cliente específico, sin relación con
  aprendizaje. **Desconectado** de la navegación y las rutas activas por
  decisión explícita — el código queda en el repo por si se retoma.

## Estructura

- `backend/` — Flask 3.1.3, application factory (`app/__init__.py`),
  Blueprints por feature (`notebook/`, `guided/`, `data_access/`).
- `frontend/` — Angular 20.2.x, NgModules (no standalone), yarn. Sistema de
  diseño compartido en `src/styles.scss` (tokens de color/tipografía) — no
  declares colores sueltos en un componente nuevo, usa `var(--token)`.

## Desarrollo local

Ver **[COMO_PROBAR.md](./COMO_PROBAR.md)** para el paso a paso completo,
incluida la sección "Si algo se cae" para reiniciar backend/frontend a mano.
Resumen rápido:

```bash
# backend (una terminal)
cd backend
python -m venv venv
./venv/Scripts/activate      # Windows
pip install -r requirements.txt
python -m pytest             # deben pasar todas (las de Convatec quedan skipped)
python run_dev.py            # NO uses `flask run` / `flask --app wsgi run` en local, ver COMO_PROBAR.md

# frontend (otra terminal)
cd frontend
yarn install
yarn start --port 4300
```

`wsgi.py` (`app = create_app()`) es el entry point real para
producción/Docker (Gunicorn) — no lo uses para levantar en tu máquina.

## Despliegue

MVP: dos Web Services en Render.com (modo Docker). Ver Arquitectura →
Infrastructure & Deployment para el detalle y el plan de migración a AWS
ECS/EC2.
