# Cómo probar sico-pandas-lab (localmente)

Todo el código de las Épicas 1, 2 y 3 está implementado. Esto es lo que se
construyó, cómo levantarlo en tu máquina y qué queda pendiente de tu parte.

## Levantar en local

### 1. Backend (Flask)

```bash
cd backend
python -m venv venv
./venv/Scripts/activate        # Windows (o: source venv/bin/activate en Linux/Mac)
pip install -r requirements.txt
python -m pytest               # deben pasar todas
python run_dev.py
```

Backend en http://localhost:5001. Prueba: http://localhost:5001/api/health

**Nota:** usa `python run_dev.py`, no `flask run` — el servidor de Flask por
defecto atiende una sola petición a la vez, así que una consulta lenta a la
RDS bloquea TODO (incluido `/api/health`) hasta que termina. `run_dev.py`
habilita hilos para que eso no pase en desarrollo local. (En producción esto
lo resuelve Gunicorn con `--threads`, pero Gunicorn no corre en Windows.)

### 2. Frontend (Angular)

En otra terminal:

```bash
cd frontend
yarn install
yarn start --port 4300
```

App en http://localhost:4300. El frontend en modo dev apunta al backend en
:5000 (ver `src/environments/environment.development.ts`).

## Qué probar

- **Notebook libre** (pestaña "Notebook"): escribe código pandas en las celdas
  y ejecútalo (botón o Ctrl/Cmd+Enter). El estado persiste entre celdas.
  - Sube un Excel desde el panel de arriba → se carga como `df`.
  - Genera una gráfica (`df.plot(kind='bar')`) → aparece como imagen.
  - Provoca un error (`1/0`) → mensaje claro, la sesión no se rompe.
  - "Reiniciar sesión" → limpia el estado.
- **Módulo guiado** (pestaña "Módulo guiado"): abre la lección, ejecuta cada
  paso, y usa "Continuar en el notebook libre".

## Conectar a los datos reales de sico (conexión directa, como DBeaver)

No hay un usuario de solo-lectura dedicado: se conecta directo con las
credenciales existentes. La app **igual bloquea las escrituras** con dos capas:
(1) el código del usuario nunca toca la conexión —solo recibe DataFrames—, y
(2) cada conexión se pone en **READ ONLY a nivel de sesión**, así MariaDB
rechaza cualquier escritura en esa sesión aunque la cuenta pueda escribir.

Para activar la conexión, configura las variables de entorno del backend (ver
`backend/.env.example`):

```
SICO_DB_HOST=mappale-sico.cdngbntx2q8s.us-west-2.rds.amazonaws.com
SICO_DB_PORT=3306
SICO_DB_USER=<usuario>
SICO_DB_PASSWORD=<clave>
SICO_DB_SSL=require            # solo si decides forzar TLS
SICO_ALLOW_WRITE_USER=true    # confirma que aceptas conectar con cuenta privilegiada
```

Sin `SICO_ALLOW_WRITE_USER=true`, el backend **se niega a arrancar** si detecta
que la cuenta tiene permisos de escritura — es una protección para que no se use
una cuenta privilegiada por accidente. Con el flag en `true`, arranca y registra
una advertencia de que la escritura queda bloqueada solo a nivel de sesión.

En Windows (PowerShell) puedes exportarlas antes de `flask run`, o crear un
archivo `.env` y cargarlo. El endpoint `/api/health` reporta el estado del guard.

**Riesgo residual (consciente):** al usar una cuenta con permisos de escritura,
la barrera a nivel de motor de BD desaparece; queda la barrera de sesión
READ ONLY. Si en el futuro se crea un usuario de solo-lectura, quita el flag y
la protección vuelve a ser a nivel de motor (más fuerte).

## Desplegar en Render.com (Story 1.1, Task 4 — pendiente)

Dos Web Services en modo Docker, uno para `backend/` y otro para `frontend/`.
Detalle en
`_bmad-output/stories-sico-pandas-lab/1-1-ver-la-aplicacion-desplegada-y-funcionando.md`.

**No configures `SICO_DB_*` en Render por ahora**: se cambió el enfoque a
trabajar solo con Excel subido por el usuario (más simple, sin depender de la
conexión a la RDS). El backend arranca igual sin esas variables — el guard de
solo-lectura se salta automáticamente cuando no están configuradas. Cuando se
quiera retomar la conexión a la base de datos real, se configuran ahí mismo.

## Decisiones pendientes (tú)

- Confirmar si se fuerza **TLS** hacia la RDS (variable `SICO_DB_SSL`).
- Completar el despliegue en Render.
