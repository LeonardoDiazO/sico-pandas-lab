# sico-pandas-lab

Notebook interactivo de práctica de pandas con datos reales de sico (solo-lectura). Repositorio standalone, no adjunto todavía a la arquitectura oficial de SICO — pendiente de aprobación del dueño del producto.

**Documentación canónica (no duplicada aquí):**

- PRD: `../_bmad-output/prd-sico-pandas-lab-2026-07-12.md`
- Arquitectura: `../_bmad-output/architecture-sico-pandas-lab-2026-07-12.md`
- Épicas e Historias: `../_bmad-output/epics-sico-pandas-lab-2026-07-12.md`
- Sprint status: `../_bmad-output/sprint-status-sico-pandas-lab.yaml`

## Estructura

- `backend/` — Flask 3.1.3, application factory, Blueprints por feature.
- `frontend/` — Angular 20.2.x + Angular Material, NgModules (no standalone), yarn.

## Desarrollo local

```bash
# backend
cd backend
python -m venv venv
./venv/Scripts/activate  # Windows
pip install -r requirements.txt
python -m pytest
flask --app wsgi run

# frontend
cd frontend
yarn install
yarn start
```

## Despliegue

MVP: dos Web Services en Render.com (modo Docker). Ver Arquitectura → Infrastructure & Deployment para el detalle y el plan de migración a AWS ECS/EC2.
