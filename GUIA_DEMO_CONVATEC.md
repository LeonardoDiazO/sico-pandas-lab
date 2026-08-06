# Guía para la demo del módulo Convatec

Guía práctica para levantar y mostrar en vivo el módulo de asignación de
representantes + comisión ilustrativa, construido para la primera reunión con
Carlos Reyes (Convatec). Está pensada para que la sigas tú mismo, paso a paso,
el día de la demo — no asume que memorizaste el código.

Contexto de una línea: **el objetivo real de esta reunión no es solo mostrar
que la herramienta funciona — es usarla para conseguir de Carlos las reglas
de comisión que hoy no existen.** Todo lo demás en esta guía está al servicio
de eso.

---

## 0. Qué vas a mostrar (y qué NO)

| Sí muestra | No muestra |
|---|---|
| Asignación automática de representante por las 3 reglas (Continence, convenio, envíos nacionales), incluyendo los splits "Repartir" y las directrices de rotación mensual | Cálculo oficial de comisión — esa regla no existe todavía |
| Marcado de líneas con problemas, sin bloquear el resultado | Acceso externo real para Convatec — hoy corre en tu máquina/entorno interno |
| Un ejercicio **ilustrativo** de comisión con un valor que tú eliges en vivo | Ninguna tasa, meta ni fórmula real de Convatec |

Si Carlos pregunta "¿esto ya calcula mi comisión real?" — la respuesta es no,
y por eso están aquí: para definir juntos cómo se vería.

---

## 1. Levantar la app

```bash
# Terminal 1 — backend
cd sico-pandas-lab/backend
./venv/Scripts/activate
python run_dev.py
```

Backend en `http://localhost:5001`. Confirma con `http://localhost:5001/api/health`.

```bash
# Terminal 2 — frontend
cd sico-pandas-lab/frontend
yarn start --port 4300
```

Abre `http://localhost:4300/convatec` en el navegador.

**Antes de la reunión**, no el día mismo: corre esto una vez completo de
principio a fin tú solo, con los archivos reales, para que no haya sorpresas
en vivo (ver §2 y §4).

---

## 2. Qué archivos usar

Necesitas 4 insumos. Usa los archivos reales de Convatec que ya tienes:

1. **Tablas maestras** — `Flujo del Proceso de Sell Out Convacare para Comisiones - Reglas.xlsx`
2. **Productos** — el detalle de productos del ciclo (reporte SAP)
3. **Servicios** — el detalle de servicios del ciclo
4. **Envíos nacionales** — *(opcional; si no tienes el archivo real a mano, puedes omitir este paso y seguir con solo productos/servicios — la herramienta funciona igual)*

**Importante sobre el tamaño:** un ciclo completo real tiene ~90,000 líneas.
Procesar y descargar ese volumen completo tarda **1-2 minutos** en la
descarga (no es que se cuelgue — es el tamaño del archivo). Dos opciones para
la demo en vivo:

- **Opción A (recomendada):** usa un recorte del Excel de productos/servicios
  con unas 500-1000 filas (un solo día o un solo convenio) antes de la
  reunión. Se procesa y descarga en segundos, y el mecanismo se ve exactamente
  igual.
- **Opción B:** usa el archivo completo, pero avisa antes de hacer clic en
  "Procesar" y en "Descargar Excel" que puede tardar un minuto — no llenes
  ese silencio narrando otra cosa, o va a parecer que algo se rompió.

Si vas a usar la Opción A, prepara el recorte con este comando (ejemplo con
un rango de filas, ajusta el nombre del archivo):

```bash
python -c "
import pandas as pd
df = pd.read_excel('productos.xlsx', engine='openpyxl')
df.head(500).to_excel('productos_demo.xlsx', index=False)
"
```

---

## 3. Paso a paso en la pantalla

Sigue el orden de la pantalla — está numerado igual que aquí.

### Paso 1 — Tablas maestras
Sube el Excel de reglas. Deberías ver una confirmación con el número de filas
cargadas (con el archivo real completo: ~356 productos, ~771 representantes,
~40 convenios).

### Paso 2 — Reportes del ciclo
Sube productos y servicios (y envíos nacionales si lo tienes). Cada uno se
confirma por separado con su número de filas.

### Paso 3 — Procesar el ciclo
Confirma el mes (afecta las directrices de rotación — BMC-PARTICULARES y
CONTINENCE PARTICULARES cambian de representante según si el mes es par o
impar). Haz clic en "Procesar ciclo".

**Lo que vas a ver, y cómo explicarlo si el número de "marcadas" es alto:**
la tabla maestra PRODUCTO de este Excel tiene ~356 productos homologados.
Si el archivo de ventas tiene productos que no están en esa lista, esas
líneas se marcan "producto sin homologar" — **eso no es un error de la
herramienta, es exactamente lo que hace hoy John a mano** (decidir qué hacer
con lo que no está homologado). Enmárcalo así: "esto es lo mismo que hoy
revisas manualmente, pero ya viene separado y contado por ti".

### Paso 4 — Ejercicio ilustrativo de comisión
Aparece marcado en rojo como **valor de ejemplo, no oficial** — dilo en voz
alta también, no dejes que la pantalla hable sola. Ingresa un número
cualquiera (ej. 100) y haz clic en "Calcular comisión ilustrativa".

**Qué explicar aquí, con cuidado:** ese valor se divide entre los
representantes que quedaron asignados en cada sede — si una sede tiene 2
representantes, cada uno "vería" la mitad. **El mismo número se repite en
cada línea de ese representante** (para mostrar "cuánto le tocaría"), no se
prorratea por línea — si alguien suma la columna completa el total va a ser
mayor que el valor que ingresaste. Adelántate a esa pregunta antes de que la
hagan.

Este es el momento de pivotar la conversación: *"Este número es inventado —
para que esto sea real, necesitamos que me digan: ¿sobre qué valor se calcula
la comisión? ¿la tasa es igual para todos o varía? ¿hay metas? ¿hay
retenciones?"* (la lista completa de preguntas está en el addendum del brief,
`_bmad-output/planning-artifacts/briefs/brief-comisiones-convatec-sico-pandas-lab-2026-08-05/addendum.md`,
sección "Comisiones — vacío de reglas").

### Paso 5 — Descargar
Descarga el Excel. Es el mismo formato de entrada + representante, grupo de
vendedor, motivo de excepción y la comisión ilustrativa (etiquetada como no
oficial también dentro del archivo, no solo en pantalla).

---

## 4. Antes de la reunión: ensaya esto tú solo

- [ ] Corriste el flujo completo de principio a fin al menos una vez, con los
      archivos reales, y sabes cuánto tarda cada paso.
- [ ] Tienes listo el recorte pequeño (§2, Opción A) si decides no usar el
      archivo completo en vivo.
- [ ] Tienes un Excel de resultado **ya descargado de antemano** como
      respaldo — si algo falla en vivo (wifi, el servidor, lo que sea),
      puedes mostrar ese archivo en pantalla igual y seguir la conversación.
- [ ] Sabes dónde está el botón "Reiniciar sesión" (arriba a la derecha) si
      necesitas empezar de nuevo a mitad de la demo sin reiniciar el backend.
- [ ] Tienes a la mano las 5 preguntas de comisión (Paso 4) — son el
      verdadero objetivo de la reunión, no un extra.

## 5. Si algo se traba en vivo

- **El backend no responde / tarda mucho:** es casi seguro el volumen de
  datos (§2). Usa el archivo de respaldo ya descargado y sigue hablando de
  las reglas de comisión — no dejes que un tecnicismo se coma el tiempo de la
  parte que realmente importa.
- **Una línea no se asignó y no sabes por qué:** revisa la columna
  `Motivo_Excepcion` en el Excel — siempre tiene una razón concreta ("producto
  sin homologar", "convenio nuevo sin representante", "ciudad sin
  asignación", "duplicado"), nunca un mensaje genérico.
- **Quieres empezar de cero:** botón "Reiniciar sesión" en la pantalla, o
  simplemente recarga la página y vuelve a subir los archivos.
