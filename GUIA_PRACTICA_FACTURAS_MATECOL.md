# Guía de práctica: Relación de facturas Matecol en sico-pandas-lab

Guía pensada para alguien que **no sabe Python**. Vas a practicar con tu archivo real
`relacion de facturas matecol.xlsx` dentro del notebook de `sico-pandas-lab`, entendiendo
cada línea de código antes de escribirla.

---

## 0. Qué es esta app y qué vas a hacer

`sico-pandas-lab` es un notebook (como una hoja de cálculo que en vez de fórmulas usa
código Python). Funciona por **celdas**: escribes código en una celda, la ejecutas, y
ves el resultado justo debajo (una tabla, un número o una gráfica).

Ya tiene precargadas 3 herramientas que vas a usar sin necesidad de instalarlas:

| Herramienta | Para qué sirve |
|---|---|
| `pd` (pandas) | Leer y manipular tablas de datos (tu Excel) |
| `plt` (matplotlib) | Dibujar gráficas (tortas, barras, líneas) |
| `sns` (seaborn) | Gráficas más bonitas, construidas sobre matplotlib |

No necesitas instalar nada ni escribir `import` — ya están listas para usar en cada celda.

---

## 1. Preparar el entorno

```bash
# Terminal 1 — backend (usa run_dev.py, no "flask run": el frontend en modo
# desarrollo espera el backend en el puerto 5001, y run_dev.py es el que
# arranca ahí — flask run por defecto usa el puerto 5000 y no conecta)
cd sico-pandas-lab/backend
./venv/Scripts/activate
python run_dev.py

# Terminal 2 — frontend
cd sico-pandas-lab/frontend
yarn start
```

Abre la app en el navegador (normalmente `http://localhost:4200`).

---

## 2. Mini-diccionario de Python (lo mínimo para entender el código de abajo)

No necesitas memorizar esto, solo tenerlo cerca para consultar mientras practicas.

- **Variable**: una caja con nombre que guarda algo. `df = ...` significa "guarda esto en
  una caja llamada `df`".
- **DataFrame**: una tabla (filas y columnas), como una hoja de Excel. Es el tipo de dato
  principal de pandas.
- **Columna**: se accede con corchetes y el nombre entre comillas: `df['vdor']` es "la
  columna llamada vdor de la tabla df".
- **Método**: una acción que se le pide a algo, con un punto y paréntesis:
  `df.head()` significa "a df, muéstrame las primeras filas".
- **Función**: parecido a un método pero no va pegado a una variable: `print(df)`.
- **Comentario**: cualquier texto después de `#` es una nota para humanos; Python lo
  ignora. Los uso en esta guía para explicar cada línea.
- **`=` no es "igual" matemático**: es "asignar". `x = 5` significa "guarda 5 en x".
- **`==` sí es comparar**: `x == 5` pregunta "¿x vale 5?".

---

## 3. Subir el archivo a la app

1. Abre el panel de **origen de datos** (data source) en el notebook.
2. Sube `relacion de facturas matecol.xlsx`.
3. Deja el nombre de variable como `df` (si le pones otro nombre, cámbialo también en
   todo el código de esta guía).

Al subirlo, la app te confirma cuántas filas y columnas detectó. Anótalo, lo vas a
necesitar para comparar más adelante.

---

## 4. Por qué el archivo "no sirve" tal cual (léelo antes de tocar código)

Este Excel no es una tabla limpia: es un **reporte impreso de SICO** convertido a Excel.
Tiene basura mezclada con los datos reales:

- Filas 1 a 5: metadatos del reporte (Hora, Fecha, Usuario, Periodo). No son datos de
  facturas.
- Filas 6 y 7: el encabezado real, pero partido en dos líneas.
- Después vienen las facturas de verdad, **pero intercaladas** con filas como
  `SUBTOTAL TIPO --> 57` y filas completamente vacías.
- Al final: filas de `TOTALES -->`, `TOT.DOCUMENTOS -->`, `TOTALES ACUMULADO -->`.

Por eso el primer paso siempre es **limpiar**, no graficar directo.

Las columnas reales del archivo, de izquierda a derecha:

| Nombre real (columna) | Qué significa |
|---|---|
| `cod_cliente` | Código (NIT/cédula) del cliente |
| `nombre_cliente` | Nombre del cliente |
| `rep_legal` | Representante legal |
| `factura` | Número de factura (ej. `F 00032746`) |
| `dia` | Fecha en formato `20260701` (año-mes-día pegado) |
| `vdor` | **Código** del vendedor (no el nombre) |
| `bod` | **Código** de la bodega/sede (no el nombre) |
| `inv` | Tipo de inventario/documento |
| `gravado`, `excluido`, `bruto`, `descuento`, `subtotal`, `iva5`, `iva19`, `impoconsumo` | Componentes del valor de la factura |
| `neto` | Valor final de la factura (el que usamos para sumar plata) |

> **Importante**: `vdor` y `bod` son códigos numéricos, no nombres. El archivo no trae
> la tabla de equivalencias (código → nombre de vendedor / sede). Si la consigues,
> se puede unir con `pd.merge()` para mostrar nombres en vez de números — es un buen
> reto para más adelante (ver sección 9).

---

## 5. Explorar el archivo *crudo*, antes de limpiar (practica esto primero)

Antes de arreglar nada, mira qué tan "sucio" está. En una celda nueva, prueba una por
una (una celda por línea) y observa qué te muestra cada una:

```python
df.shape        # (filas, columnas) — cuántas filas y columnas tiene la tabla
```

```python
df.head()       # las primeras 5 filas, tal como vienen del Excel
```

```python
df.columns      # lista de nombres de columnas (van a salir feos: "Unnamed: 4", etc.)
```

```python
df.dtypes       # el tipo de dato que pandas detectó en cada columna
```

**Pregúntate**: ¿los nombres de columna tienen sentido? ¿Ves texto raro como
`Unnamed: 4`? Eso es evidencia de que el archivo no tiene un encabezado limpio en la
primera fila — confirma lo explicado en la sección 4.

---

## 6. Limpieza (celda a celda, explicada línea por línea)

**Celda de limpieza:**

```python
df.columns = ['_', 'cod_cliente', 'nombre_cliente', 'rep_legal', 'factura',
              'dia', 'vdor', 'bod', 'inv', 'gravado', 'excluido', 'bruto',
              'descuento', 'subtotal', 'iva5', 'iva19', 'impoconsumo', 'neto']
# Le pusimos nombres nuevos y legibles a las 18 columnas, en el mismo orden
# en que vienen en el Excel.

mask = df['factura'].notna() & df['factura'].astype(str).str.startswith('F')
# "mask" es una lista de True/False, una por fila:
#   True  = esta fila tiene algo en 'factura' Y empieza con la letra F (es una factura real)
#   False = es una fila de metadatos, subtotal, vacía o de totales (basura)

df = df[mask].copy()
# Nos quedamos solo con las filas marcadas True. .copy() evita advertencias de pandas.

df['neto'] = pd.to_numeric(df['neto'], errors='coerce')
# Convierte la columna 'neto' a número. Si algo no se puede convertir, lo vuelve NaN
# (vacío) en vez de dañar toda la ejecución.

df['vdor'] = df['vdor'].astype(str)
df['bod'] = df['bod'].astype(str)
# Convertimos los códigos a texto, porque son categorías (identificadores), no
# cantidades — no tiene sentido "sumar" códigos de vendedor.

df.shape
```

Debe darte `(171, 18)`. Si te da otro número, algo no cuadra — revisa que subiste el
archivo correcto y que no editaste una línea sin querer.

**Verifica que quedó bien:**

```python
df.head()      # ya deberían verse nombres de columna normales y solo facturas reales
```

```python
df.describe()  # estadísticas (promedio, mínimo, máximo...) de las columnas numéricas
```

---

## 7. Exploración básica del `df` limpio (practica esto)

```python
df['vdor'].unique()          # lista de códigos de vendedor distintos que aparecen
```

```python
df['vdor'].value_counts()    # cuántas facturas hizo cada vendedor (conteo, no plata)
```

```python
df['bod'].unique()           # códigos de sede/bodega distintos
```

```python
df['neto'].sum()             # suma total facturada (debería acercarse al TOTALES del Excel)
```

```python
df['neto'].mean()            # valor promedio de una factura
```

```python
df.sort_values('neto', ascending=False).head(10)
# las 10 facturas de mayor valor, de mayor a menor
```

---

## 8. Agregaciones y gráficas (lo que ya probamos, para tenerlo todo junto)

**Torta por vendedor:**

```python
por_vendedor = df.groupby('vdor')['neto'].sum().sort_values(ascending=False)
por_vendedor.plot.pie(autopct='%1.1f%%', ylabel='', figsize=(6, 6))
plt.title('Facturación NETO por vendedor')
```

**Torta por sede (bodega):**

```python
por_sede = df.groupby('bod')['neto'].sum().sort_values(ascending=False)
por_sede.plot.pie(autopct='%1.1f%%', ylabel='', figsize=(6, 6))
plt.title('Facturación NETO por sede (bodega)')
```

**"Dashboard" — ambas juntas en una sola imagen:**

```python
fig, axes = plt.subplots(1, 2, figsize=(12, 6))

por_vendedor = df.groupby('vdor')['neto'].sum().sort_values(ascending=False)
axes[0].pie(por_vendedor, labels=por_vendedor.index, autopct='%1.1f%%')
axes[0].set_title('Facturación NETO por vendedor')

por_sede = df.groupby('bod')['neto'].sum().sort_values(ascending=False)
axes[1].pie(por_sede, labels=por_sede.index, autopct='%1.1f%%')
axes[1].set_title('Facturación NETO por sede (bodega)')

plt.tight_layout()
```

---

## 9. Retos para practicar (de más fácil a más difícil)

Intenta resolverlos tú, usando lo aprendido en las secciones 6-8 como referencia. No
incluyo las soluciones a propósito — si te trabas, vuelve a pedirme ayuda con el reto
puntual.

**Nivel 1 — lectura de tablas**
1. ¿Cuántas facturas hizo el vendedor con más facturas? (pista: `value_counts()`)
2. ¿Cuál es el valor mínimo y máximo de una factura? (pista: `df['neto'].min()` / `.max()`)
3. Muestra solo las facturas del cliente `CONSUMIDOR FINAL`.

**Nivel 2 — agregaciones**
4. Calcula el **promedio** de `neto` por vendedor (no la suma) y ordénalo de mayor a menor.
5. ¿Qué porcentaje del total facturado representa el vendedor más grande? (pista:
   divide su suma entre `df['neto'].sum()` y multiplica por 100).
6. Agrupa por `bod` y muestra tanto la suma como el conteo de facturas al mismo tiempo
   (pista: busca el método `.agg()` de pandas).

**Nivel 3 — gráficas nuevas**
7. Haz un gráfico de **barras** (no torta) con el top 10 de clientes por `neto` total.
8. Haz un **histograma** de la columna `neto` para ver cómo se distribuyen los valores
   de las facturas (pista: `df['neto'].plot.hist()`).
9. Convierte `dia` (que está como `20260701`) a fecha real con
   `pd.to_datetime(df['dia'], format='%Y%m%d')` y grafica el total facturado por día.

**Nivel 4 — combinar datos**
10. Si consigues la tabla de nombres de vendedor (código → nombre), únela a `df` con
    `pd.merge()` y repite la torta de la sección 8, pero mostrando nombres en vez de
    códigos.
11. Compara `bruto` vs `neto` por vendedor: ¿quién tiene más descuentos/impuestos
    relativos a su facturación?

---

## 10. Errores comunes (y qué significan)

- **`KeyError: 'vdor'`** → escribiste mal el nombre de columna, o no corriste la celda
  de limpieza (sección 6) antes de usar `df`.
- **La torta sale vacía o con un solo color** → probablemente `neto` quedó con `NaN` en
  todas las filas; revisa que corriste `pd.to_numeric(..., errors='coerce')`.
- **Al reiniciar la sesión, `df` ya no existe** → cada vez que reinicias (botón restart
  o recargas la página), tienes que volver a subir el Excel y correr la celda de
  limpieza de nuevo. El notebook no guarda `df` entre sesiones.
- **Los números no cuadran con el Excel original** → revisa `df.shape` después de
  limpiar; debe dar `(171, 18)`. Si da menos, el filtro `mask` está descartando
  facturas reales por error.

---

## 11. Glosario rápido

- **Sede / bodega**: en este archivo es la columna `bod`. Solo trae el código, no el
  nombre de la sede.
- **Vendedor**: columna `vdor`. Igual, solo código.
- **NETO**: el valor final de la factura después de impuestos y descuentos — es el
  número que más sentido tiene para medir "cuánto vendió" cada quién.
- **Bruto**: el valor antes de descuentos.
