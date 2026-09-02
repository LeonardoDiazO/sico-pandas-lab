# Cómo probar sico-pandas-lab (localmente)

Guía operativa: cómo levantar la app en tu máquina, qué probar en cada
módulo, y qué hacer si algo se cae a mitad de una sesión.

## Levantar en local

Necesitas **dos terminales abiertas al mismo tiempo** — el backend y el
frontend son procesos independientes; si cierras la terminal del backend
(o la máquina se reinicia), el frontend sigue "vivo" en el navegador pero
**todas las peticiones a la API empiezan a fallar** (ver [Si algo se
cae](#si-algo-se-cae-reiniciar-a-mano) más abajo).

### 1. Backend (Flask)

```bash
cd backend
python -m venv venv
./venv/Scripts/activate        # Windows (o: source venv/bin/activate en Linux/Mac)
pip install -r requirements.txt
python -m pytest               # deben pasar todas (las de Convatec quedan "skipped", ver nota abajo)
python run_dev.py
```

Backend en http://localhost:5001. Prueba: http://localhost:5001/api/health
— si responde `{"success": true, ...}`, está sano.

**Nota:** usa `python run_dev.py`, no `flask run` ni `flask --app wsgi run`
— el servidor de Flask por defecto atiende una sola petición a la vez, así
que una consulta lenta bloquea TODO (incluido `/api/health`) hasta que
termina. `run_dev.py` habilita hilos para que eso no pase en desarrollo
local. (`wsgi.py` es el entry point real de producción, vía Gunicorn — no
lo uses en tu máquina.)

**Nota (Convatec):** el módulo Convatec está desconectado de la app
(blueprint no registrado, ver `app/__init__.py`) — sus tests en
`tests/test_convatec_routes.py` quedan `skipped`, no fallan. El resto del
código de Convatec sigue en el repo por si se retoma más adelante.

**Opcional — asistente de IA:** el módulo "Sin código" usa Gemini para
sugerir qué es cada columna y para redactar texto (nunca para calcular). Sin
`GEMINI_API_KEY` configurada, todo sigue funcionando igual con una regla
determinística de respaldo — no es necesaria para probar la app. Si quieres
probar la sugerencia real: copia `backend/.env.example` a `backend/.env`,
consigue una key gratis en https://aistudio.google.com/apikey, y ponla en
`GEMINI_API_KEY`.

### 2. Frontend (Angular)

En otra terminal:

```bash
cd frontend
yarn install
yarn start --port 4300
```

App en http://localhost:4300. El frontend en modo dev apunta al backend en
`:5001` (ver `src/environments/environment.development.ts`) — si cambias el
puerto del backend, cambia ese archivo también.

## Si algo se cae (reiniciar a mano)

**Síntoma típico:** subes un Excel (o haces cualquier acción) y te aparece
un mensaje genérico como *"Ocurrió un error al cargar el Excel"*, *"No se
pudo contactar el servidor"*, o algo similar en cualquier pantalla. Casi
siempre significa que **el backend se cayó o nunca se levantó** — el
frontend sigue mostrando la última pantalla que tenías, pero no hay nadie
del otro lado respondiendo peticiones.

**Diagnóstico rápido** — abre una terminal y corre:

```bash
curl http://localhost:5001/api/health
```

- Si responde `{"success": true, ...}` → el backend está sano, el problema
  es otro (revisa la consola del navegador).
- Si da error de conexión (`curl: (7) Failed to connect`) → el backend está
  abajo, sigue con el reinicio.

**Reiniciar el backend:**

```bash
cd backend
./venv/Scripts/activate        # Windows (o: source venv/bin/activate)
python run_dev.py
```

Déjalo corriendo en esa terminal (no la cierres) y vuelve a probar
`http://localhost:5001/api/health`. El frontend (si sigue abierto en
`localhost:4300`) reconecta solo apenas el backend responde — no hace falta
recargar la página, aunque un F5 tampoco hace daño.

**Reiniciar el frontend** (mucho menos frecuente — Angular con `yarn start`
rara vez se cae solo, pero si la terminal se cerró):

```bash
cd frontend
yarn start --port 4300
```

**Si ninguno de los dos arranca:** revisa que el puerto no esté ya ocupado
por un proceso viejo colgado de una sesión anterior —
`netstat -ano | findstr :5001` (Windows) te da el PID que está escuchando
ahí; ciérralo con el Administrador de tareas (o `taskkill /F /PID <pid>`) y
vuelve a intentar `python run_dev.py`.

## Qué probar

- **Sin código** (pestaña "Sin código", el flujo principal para alguien que
  no programa):
  1. Sube un Excel → aparece una sugerencia de qué es cada columna
     (dimensión/métrica/fecha/identificador/descartar) — corrígela si hace
     falta con los selectores, y confirma.
  2. Aparece un tablero automático: resumen ejecutivo arriba (filas,
     dimensiones, métricas), y una tarjeta por combinación con su insight
     destacado ("X de Y concentran el Z% del total"), su gráfica de Pareto,
     y su tabla.
  3. Haz clic en cualquier tabla o gráfica del tablero → se abre en grande.
  4. Debajo del tablero, "Análisis puntual" (plegado) tiene los selectores
     manuales de siempre por si quieres una combinación que el catálogo
     automático no cubrió.
- **Notebook libre** (pestaña "Notebook"): escribe código pandas en las
  celdas y ejecútalo (botón o Ctrl/Cmd+Enter). El estado persiste entre
  celdas.
  - Sube un Excel desde el panel de arriba → se carga como `df`.
  - Genera una gráfica (`df.plot(kind='bar')`) → aparece como imagen.
  - Provoca un error (`1/0`) → mensaje claro, la sesión no se rompe.
  - "Reiniciar sesión" → limpia el estado.
- **Módulo guiado** (pestaña "Módulo guiado"): abre una lección, ejecuta
  cada paso, y usa "Continuar en el notebook libre". Si ya subiste tu
  propio Excel (en Notebook o en Sin código) antes de entrar a una lección
  de las que lo soportan (Fundamentos, Agrupar, Gráficas), el ejemplo usa
  tus columnas reales en vez del ejemplo genérico — sube el archivo primero
  si quieres ver eso en acción.

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

En Windows (PowerShell) puedes exportarlas antes de `python run_dev.py`, o
crear un archivo `.env` y cargarlo. El endpoint `/api/health` reporta el
estado del guard.

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
- Si se retoma Convatec: reconectar su blueprint en `backend/app/__init__.py`
  y su ruta/link en `frontend/src/app/app-routing-module.ts` / `app.html`.
