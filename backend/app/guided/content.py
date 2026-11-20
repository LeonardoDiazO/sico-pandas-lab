"""Guided-learning content: a small progressive pandas course for beginners.

Nine lessons, easiest to most advanced (Lesson 0 assumes zero prior Python
knowledge), each closed by a challenge checked server-side (challenges.py). Each step carries a plain-language
explanation plus a runnable code cell, executed through the exact same engine
as the free notebook (FR16), so the guided module teaches the real workflow
the learner will reuse on their own (FR14, FR15, FR17).

Every code cell that needs a table falls back to a small synthetic DataFrame
(via `except NameError`) when the real sico table has not been loaded yet from
the panel, so every lesson always runs — but each explanation says explicitly
what to load first, since practicing on real data is the whole point.

Available in every cell: pd (pandas), np (numpy), plt (matplotlib.pyplot),
sns (seaborn), stats (scipy.stats). Lesson 1 explains what each one is for.
"""
import re

from app.guided import data_context

_TRY_EXCEPT_EXPLAINER = (
    "Este patrón se repite en todas las lecciones, así que vale la pena entenderlo una vez: "
    "`try: df_02_movimiento` intenta *leer* la variable. Si ya cargaste la tabla real desde el "
    "panel de arriba, esa variable existe y el `try` no hace nada más (la línea se limita a "
    "\"tocarla\" para confirmar que existe). Si no la cargaste, Python no encuentra la variable y "
    "lanza un `NameError` — el `except NameError:` lo atrapa y crea una tabla de ejemplo con la "
    "misma forma, para que puedas seguir practicando igual. En resumen: usa tus datos reales si "
    "los cargaste, y si no, no se rompe nada."
)

LESSONS = [
    {
        "id": "00-python-desde-cero",
        "title": "0. Python desde cero (antes de pandas)",
        "summary": "Si nunca has escrito una línea de código: qué es una variable, qué es print, qué es un import y qué significa el punto en df.head(). Empieza aquí.",
        "challenge_id": "00-python-desde-cero:reto-1",
        "steps": [
            {
                "title": "0.1 Ejecutar código: qué es una celda",
                "explanation": (
                    "Cada caja de código de abajo es una **celda**. Escribes código Python dentro y "
                    "presionas el botón ▶ (o Ctrl/Cmd+Enter) para ejecutarlo. Lo que devuelve la "
                    "última línea de la celda se muestra como resultado, debajo. Prueba con la "
                    "celda más simple posible: solo un número."
                ),
                "code": "5 + 3",
            },
            {
                "title": "0.2 Variables: guardar un valor con un nombre",
                "explanation": (
                    "Una **variable** es un nombre que apunta a un valor, para poder reusarlo. "
                    "`nombre = valor` crea (o reemplaza) la variable. El signo `=` aquí NO significa "
                    "'igual' como en matemáticas — significa 'guarda esto en la variable de la "
                    "izquierda'. Puedes usar la variable en cualquier celda posterior de esta misma "
                    "sesión."
                ),
                "code": (
                    "precio = 45000\n"
                    "cantidad = 3\n"
                    "total = precio * cantidad\n"
                    "total"
                ),
            },
            {
                "title": "0.3 print(): mostrar cosas en pantalla",
                "explanation": (
                    "`print(algo)` muestra `algo` en pantalla inmediatamente, ahí donde está escrito "
                    "— a diferencia del resultado de la última línea (que solo se muestra al final "
                    "de la celda). Por eso `print()` es la forma de mostrar VARIAS cosas en una "
                    "misma celda, no solo la última. Puedes separar varias piezas con comas dentro "
                    "del paréntesis."
                ),
                "code": (
                    "producto = 'Camisa'\n"
                    "precio = 45000\n"
                    "print('Producto:', producto)\n"
                    "print('Precio:', precio)\n"
                    "print('Precio con IVA:', precio * 1.19)"
                ),
            },
            {
                "title": "0.4 Comentarios: notas que Python ignora",
                "explanation": (
                    "Todo lo que sigue a un `#` en una línea es un **comentario**: Python no lo "
                    "ejecuta, es solo una nota para quien lee el código (tú mismo, en el futuro). Se "
                    "usan constantemente en las lecciones para explicar qué hace cada línea sin "
                    "estorbar la ejecución."
                ),
                "code": (
                    "# Esta línea es un comentario, no hace nada al ejecutarla\n"
                    "edad = 30  # esto también es un comentario, al final de una línea con código\n"
                    "edad"
                ),
            },
            {
                "title": "0.5 Tipos de datos básicos",
                "explanation": (
                    "Cada valor en Python tiene un **tipo**. Los que más vas a usar: `int` (número "
                    "entero, `3`), `float` (número con decimales, `3.5`), `str` (texto, siempre "
                    "entre comillas: `'hola'`), `bool` (`True`/`False`), y `list` (una colección "
                    "ordenada de valores, entre corchetes: `[1, 2, 3]`). La función `type(x)` te dice "
                    "el tipo de cualquier valor."
                ),
                "code": (
                    "print(type(3))\n"
                    "print(type(3.5))\n"
                    "print(type('hola'))\n"
                    "print(type(True))\n"
                    "print(type([1, 2, 3]))"
                ),
            },
            {
                "title": "0.6 import: traer una librería, y el 'as' como apodo",
                "explanation": (
                    "Python trae muy poco incorporado por defecto; el resto se **importa** desde "
                    "librerías. `import pandas as pd` significa: 'trae la librería pandas, y de aquí "
                    "en adelante llámala `pd`' — es solo un apodo para escribir menos. Por eso en "
                    "todas las lecciones ves `pd.algo()`: `pd` ES pandas. Ya está importado en cada "
                    "celda (junto con `np`, `plt`, `sns`, `stats`), así que normalmente no necesitas "
                    "escribir el `import` tú mismo — pero ahora ya sabes qué significa cuando lo "
                    "veas en internet o en otro código."
                ),
                "code": (
                    "import pandas as pd  # 'pd' es solo un apodo para 'pandas'\n"
                    "import numpy as np   # 'np' es el apodo de numpy\n"
                    "\n"
                    "print('pandas está disponible como pd:', pd)\n"
                    "print('numpy está disponible como np:', np)"
                ),
            },
            {
                "title": "0.7 El punto: métodos y atributos (objeto.algo)",
                "explanation": (
                    "Verás constantemente código como `df.head()` o `df.shape`. El punto `.` "
                    "significa 'dentro de este objeto, usa esto'. Si después del punto hay "
                    "paréntesis (`.head()`), es un **método**: una acción/función que pertenece a "
                    "ese objeto. Si no hay paréntesis (`.shape`), es un **atributo**: un dato que ya "
                    "trae guardado. `pd.DataFrame(...)` es un método de `pd` que crea una tabla; esa "
                    "tabla resultante es un objeto que a su vez tiene sus propios métodos, como "
                    "`.head()`."
                ),
                "code": (
                    "tabla = pd.DataFrame({'nombre': ['Ana', 'Luis'], 'edad': [28, 35]})\n"
                    "\n"
                    "print('Método .head() -- una acción, por eso lleva paréntesis:')\n"
                    "print(tabla.head())\n"
                    "\n"
                    "print()\n"
                    "print('Atributo .shape -- un dato guardado, sin paréntesis:')\n"
                    "print(tabla.shape)"
                ),
            },
            {
                "title": "0.8 Listo: ya puedes empezar con pandas de verdad",
                "explanation": (
                    "Con esto ya tienes lo esencial: celdas, variables, print, comentarios, tipos, "
                    "import/apodo y el punto para métodos/atributos. La Lección 1 retoma justo desde "
                    "aquí, ahora enfocada 100% en `pd.DataFrame` — la tabla de datos con la que vas a "
                    "trabajar en el resto del curso."
                ),
                "code": (
                    "print('Repaso rápido:')\n"
                    "mensaje = 'Ya sé qué es una variable, un print y un import.'  # variable de tipo str\n"
                    "print(mensaje)\n"
                    "print('Filas x columnas de mi primera tabla:', tabla.shape)  # atributo, sin ()\n"
                    "tabla.head()  # método, con ()"
                ),
            },
        ],
    },
    {
        "id": "01-fundamentos",
        "title": "1. Fundamentos: tu primer DataFrame",
        "summary": "Qué es pandas, cómo se ve una tabla de datos, y cómo explorarla. Empieza aquí si nunca has usado pandas.",
        "challenge_id": "01-fundamentos:reto-1",
        "steps": [
            {
                "title": "1.1 ¿Qué es pandas y qué es un DataFrame?",
                "explanation": (
                    "pandas es la librería de Python para trabajar con datos en forma de tabla "
                    "(filas y columnas, como una hoja de Excel). Esa tabla se llama **DataFrame**. "
                    "Ya tienes disponibles en cada celda: `pd` (pandas), `np` (numpy, para cálculos "
                    "numéricos), `plt` (matplotlib, para gráficas), `sns` (seaborn, gráficas "
                    "estadísticas más simples de usar) y `stats` (scipy, para estadística). No "
                    "necesitas escribir ningún `import` — ya están cargados. Ejecuta esta celda para "
                    "crear tu primer DataFrame a mano y ver cómo se ve:"
                ),
                "code": (
                    "mi_primera_tabla = pd.DataFrame({\n"
                    "    'producto': ['Camisa', 'Pantalón', 'Zapatos'],\n"
                    "    'precio': [45000, 80000, 120000],\n"
                    "})\n"
                    "mi_primera_tabla"
                ),
            },
            {
                "title": "1.2 Cargar una tabla real (y qué significa ese código con 'try')",
                "explanation": (
                    "Antes de correr esta celda, sube al panel de arriba la tabla "
                    "'02_movimiento' (botón 'cargar' junto a su nombre). Quedará disponible como "
                    "la variable `df_02_movimiento`. " + _TRY_EXCEPT_EXPLAINER
                ),
                "code": (
                    "try:\n"
                    "    df_02_movimiento\n"
                    "except NameError:\n"
                    "    df_02_movimiento = pd.DataFrame({\n"
                    "        'mov_item': ['A100', 'B200', 'A100', 'C300', 'B200'],\n"
                    "        'mov_cantidad': [3, 1, 5, 2, 4],\n"
                    "        'mov_neto': [30000, 12000, 50000, 8000, 40000],\n"
                    "    })\n"
                    "df_02_movimiento"
                ),
            },
            {
                "title": "1.3 Ver el tamaño y los tipos de datos",
                "explanation": (
                    "`.shape` devuelve (filas, columnas). `.dtypes` muestra el tipo de cada "
                    "columna (número, texto, fecha...) — importante porque, por ejemplo, no puedes "
                    "sumar una columna de texto. `.columns` lista los nombres de columna, útiles "
                    "para copiar y pegar en tu propio código."
                ),
                "code": (
                    "print('Forma (filas, columnas):', df_02_movimiento.shape)\n"
                    "print()\n"
                    "print('Tipos de dato por columna:')\n"
                    "print(df_02_movimiento.dtypes)\n"
                    "print()\n"
                    "print('Nombres de columna:', list(df_02_movimiento.columns))"
                ),
            },
            {
                "title": "1.4 Ver una muestra: head, tail y sample",
                "explanation": (
                    "`.head(n)` muestra las primeras n filas (5 por defecto) — lo primero que "
                    "deberías hacer con cualquier tabla nueva. `.tail(n)` muestra las últimas. "
                    "`.sample(n)` muestra n filas al azar, útil para no ver siempre el mismo inicio."
                ),
                "code": (
                    "print('Primeras 3 filas:')\n"
                    "display_head = df_02_movimiento.head(3)\n"
                    "display_head"
                ),
            },
            {
                "title": "1.5 Seleccionar una o varias columnas",
                "explanation": (
                    "`df['columna']` te da una sola columna (se llama Series). `df[['col1', "
                    "'col2']]` — con doble corchete — te da varias columnas como un DataFrame más "
                    "pequeño. Esto es lo que usarás constantemente para quedarte solo con lo que "
                    "necesitas."
                ),
                "code": (
                    "una_columna = df_02_movimiento['mov_cantidad']\n"
                    "print(type(una_columna), '- una sola columna')\n"
                    "\n"
                    "varias_columnas = df_02_movimiento[['mov_item', 'mov_cantidad']]\n"
                    "varias_columnas"
                ),
            },
            {
                "title": "1.6 Estadísticas descriptivas rápidas",
                "explanation": (
                    "`.describe()` resume todas las columnas numéricas de una vez: promedio "
                    "(mean), mínimo, máximo, cuartiles. `.mean()`, `.sum()`, `.max()`, `.min()` "
                    "funcionan sobre una columna específica. `.value_counts()` cuenta cuántas veces "
                    "aparece cada valor — perfecto para columnas de texto/categorías."
                ),
                "code": (
                    "print('Resumen numérico:')\n"
                    "print(df_02_movimiento.describe())\n"
                    "print()\n"
                    "print('Cantidad total movida:', df_02_movimiento['mov_cantidad'].sum())\n"
                    "print()\n"
                    "print('Conteo por ítem:')\n"
                    "df_02_movimiento['mov_item'].value_counts()"
                ),
            },
        ],
    },
    {
        "id": "02-filtrar-ordenar",
        "title": "2. Filtrar y ordenar",
        "summary": "Quédate solo con las filas que te interesan, y ordénalas. La base de casi cualquier análisis.",
        "challenge_id": "02-filtrar-ordenar:reto-1",
        "steps": [
            {
                "title": "2.1 Cargar datos (mismo patrón que ya conoces)",
                "explanation": (
                    "Carga '02_movimiento' desde el panel si aún no lo has hecho en esta sesión. "
                    "Usamos el mismo patrón try/except de la Lección 1."
                ),
                "code": (
                    "try:\n"
                    "    df_02_movimiento\n"
                    "except NameError:\n"
                    "    df_02_movimiento = pd.DataFrame({\n"
                    "        'mov_cia': ['01'] * 8,\n"
                    "        'mov_item': ['A100', 'B200', 'A100', 'C300', 'B200', 'A100', 'C300', 'B200'],\n"
                    "        'mov_cantidad': [3, 1, 5, 2, 4, -1, 0, 6],\n"
                    "        'mov_neto': [30000, 12000, 50000, 8000, 40000, -10000, 0, 60000],\n"
                    "    })\n"
                    "df_02_movimiento"
                ),
            },
            {
                "title": "2.2 Filtrar con una condición",
                "explanation": (
                    "`df[df['columna'] > valor]` es el patrón central de pandas: dentro de los "
                    "corchetes va una condición que da True/False por cada fila, y pandas se queda "
                    "solo con las filas True. Aquí descartamos cantidades negativas o cero (que "
                    "suelen ser anulaciones)."
                ),
                "code": (
                    "positivos = df_02_movimiento[df_02_movimiento['mov_cantidad'] > 0]\n"
                    "print('Filas originales:', len(df_02_movimiento), '-> después de filtrar:', len(positivos))\n"
                    "positivos"
                ),
            },
            {
                "title": "2.3 Combinar varias condiciones",
                "explanation": (
                    "Para varias condiciones a la vez se usa `&` (Y) o `|` (O) — no `and`/`or` de "
                    "Python normal — y cada condición va entre paréntesis. Aquí pedimos cantidad "
                    "positiva Y que sea del ítem 'A100'."
                ),
                "code": (
                    "filtro = (df_02_movimiento['mov_cantidad'] > 0) & (df_02_movimiento['mov_item'] == 'A100')\n"
                    "df_02_movimiento[filtro]"
                ),
            },
            {
                "title": "2.4 Ordenar filas",
                "explanation": (
                    "`.sort_values('columna')` ordena de menor a mayor; con `ascending=False` es de "
                    "mayor a menor. Muy útil para encontrar los valores más altos o más bajos."
                ),
                "code": (
                    "positivos.sort_values('mov_neto', ascending=False)"
                ),
            },
            {
                "title": "2.5 Los N más grandes/pequeños, directo",
                "explanation": (
                    "`.nlargest(n, 'columna')` y `.nsmallest(n, 'columna')` son un atajo para "
                    "'ordenar y quedarme con los primeros n', sin dos pasos."
                ),
                "code": (
                    "positivos.nlargest(2, 'mov_neto')"
                ),
            },
        ],
    },
    {
        "id": "03-agrupar",
        "title": "3. Agrupar y resumir (groupby)",
        "summary": "La herramienta más poderosa de pandas: resumir muchas filas en pocas, por categoría.",
        "challenge_id": "03-agrupar:reto-1",
        "steps": [
            {
                "title": "3.1 Cargar datos",
                "explanation": "Mismo patrón de siempre — carga '02_movimiento' desde el panel para practicar con datos reales.",
                "code": (
                    "try:\n"
                    "    df_02_movimiento\n"
                    "except NameError:\n"
                    "    df_02_movimiento = pd.DataFrame({\n"
                    "        'mov_item': ['A100', 'B200', 'A100', 'C300', 'B200', 'A100'],\n"
                    "        'mov_cantidad': [3, 1, 5, 2, 4, 2],\n"
                    "        'mov_neto': [30000, 12000, 50000, 8000, 40000, 20000],\n"
                    "    })\n"
                    "df_02_movimiento"
                ),
            },
            {
                "title": "3.2 groupby básico: sumar por categoría",
                "explanation": (
                    "`.groupby('columna')` agrupa las filas que comparten el mismo valor en esa "
                    "columna. Solo no hace nada visible por sí solo — hay que decirle qué hacer con "
                    "cada grupo, por ejemplo `.sum()`. Piensa: 'agrupa por ítem, y suma la cantidad "
                    "de cada grupo'."
                ),
                "code": (
                    "por_item = df_02_movimiento.groupby('mov_item')['mov_cantidad'].sum()\n"
                    "por_item.sort_values(ascending=False)"
                ),
            },
            {
                "title": "3.3 Varias métricas a la vez con .agg()",
                "explanation": (
                    "`.agg([...])` aplica varias funciones al mismo grupo de una sola vez. Aquí "
                    "vemos suma, promedio y conteo de movimientos, por ítem, en una sola tabla."
                ),
                "code": (
                    "resumen = df_02_movimiento.groupby('mov_item')['mov_neto'].agg(['sum', 'mean', 'count'])\n"
                    "resumen"
                ),
            },
            {
                "title": "3.4 Tabla dinámica con pivot_table",
                "explanation": (
                    "`.pivot_table()` es como una tabla dinámica de Excel: agrupa por una columna "
                    "en las filas y resume otra, con la función que elijas (por defecto, el "
                    "promedio)."
                ),
                "code": (
                    "df_02_movimiento.pivot_table(\n"
                    "    index='mov_item', values='mov_neto', aggfunc='sum'\n"
                    ")"
                ),
            },
            {
                "title": "3.5 De agrupado a gráfica en una línea",
                "explanation": (
                    "Cualquier resultado de groupby es en el fondo una tabla, y las tablas de "
                    "pandas se pueden graficar directo con `.plot(kind=...)`. En la Lección 5 vemos "
                    "esto a fondo — aquí solo un adelanto."
                ),
                "code": (
                    "por_item.plot(kind='bar', title='Cantidad por ítem')\n"
                    "plt.tight_layout()"
                ),
            },
        ],
    },
    {
        "id": "04-combinar-tablas",
        "title": "4. Combinar tablas con merge (el 'join' en pandas)",
        "summary": "Cómo cruzar dos o más tablas usando una columna en común — el equivalente pandas de un JOIN de SQL.",
        "challenge_id": "04-combinar-tablas:reto-1",
        "steps": [
            {
                "title": "4.1 Por qué combinar tablas",
                "explanation": (
                    "Los datos reales casi siempre están repartidos en varias tablas: "
                    "'02_movimiento' tiene el código del ítem (`mov_item`), pero no su nombre — eso "
                    "vive en '02_item' (`item_codigo`, `item_descripcion`). Para ver el nombre junto "
                    "al movimiento hay que **combinar** ambas tablas. En SQL esto se llama JOIN; en "
                    "pandas se llama merge, y lo haces tú mismo con código — así entiendes "
                    "exactamente qué se está cruzando con qué."
                ),
                "code": (
                    "try:\n"
                    "    df_02_movimiento\n"
                    "except NameError:\n"
                    "    df_02_movimiento = pd.DataFrame({\n"
                    "        'mov_item': ['A100', 'B200', 'A100', 'C300'],\n"
                    "        'mov_cantidad': [3, 1, 5, 2],\n"
                    "    })\n"
                    "\n"
                    "try:\n"
                    "    df_02_item\n"
                    "except NameError:\n"
                    "    df_02_item = pd.DataFrame({\n"
                    "        'item_codigo': ['A100', 'B200', 'C300'],\n"
                    "        'item_descripcion': ['Producto A', 'Producto B', 'Producto C'],\n"
                    "    })\n"
                    "\n"
                    "print('movimiento tiene', df_02_movimiento.shape[0], 'filas; item tiene', df_02_item.shape[0])"
                ),
            },
            {
                "title": "4.2 pd.merge: el cruce básico",
                "explanation": (
                    "`pd.merge(tabla_izquierda, tabla_derecha, left_on='columna_en_izquierda', "
                    "right_on='columna_en_derecha')` busca, para cada fila de la izquierda, la fila "
                    "de la derecha donde esas dos columnas coinciden, y las pega en una sola fila. "
                    "Antes de esta celda, carga también '02_item' desde el panel para usar datos "
                    "reales."
                ),
                "code": (
                    "combinado = pd.merge(\n"
                    "    df_02_movimiento, df_02_item,\n"
                    "    left_on='mov_item', right_on='item_codigo',\n"
                    "    how='left',\n"
                    ")\n"
                    "combinado[['mov_item', 'item_descripcion', 'mov_cantidad']]"
                ),
            },
            {
                "title": "4.3 ¿Qué significa how='left'?",
                "explanation": (
                    "`how='left'` significa: conserva TODAS las filas de la tabla izquierda "
                    "(movimiento), aunque no encuentren pareja en la derecha (en ese caso, las "
                    "columnas de la derecha quedan en NaN, vacío). Es la opción más segura cuando "
                    "no quieres perder movimientos por un ítem mal codificado. Otras opciones: "
                    "`'inner'` (solo las que sí coinciden en ambas), `'right'` (todas las de la "
                    "derecha), `'outer'` (todas, de ambos lados)."
                ),
                "code": (
                    "# Cuántas filas quedaron sin descripción (sin pareja en df_02_item)\n"
                    "sin_pareja = combinado[combinado['item_descripcion'].isna()]\n"
                    "print('Movimientos sin ítem coincidente:', len(sin_pareja))\n"
                    "sin_pareja"
                ),
            },
            {
                "title": "4.4 Encadenar varios merge (tres tablas)",
                "explanation": (
                    "Se pueden encadenar varios merge para cruzar más de dos tablas. Aquí sumamos "
                    "'02_itemprecios' (que trae varios atributos por ítem, uno por fila — cada uno "
                    "identificado por `tipo_campo_adicional`). Si cargaste esa tabla real desde el "
                    "panel, este merge la cruza también; si no, se usa un ejemplo pequeño."
                ),
                "code": (
                    "try:\n"
                    "    df_02_itemprecios\n"
                    "except NameError:\n"
                    "    df_02_itemprecios = pd.DataFrame({\n"
                    "        'codigo_item': ['A100', 'B200', 'C300'],\n"
                    "        'tipo_campo_adicional': ['PRECIO1', 'PRECIO1', 'PRECIO1'],\n"
                    "        'valor': ['15000', '22000', '9000'],\n"
                    "    })\n"
                    "\n"
                    "completo = pd.merge(\n"
                    "    combinado, df_02_itemprecios,\n"
                    "    left_on='item_codigo', right_on='codigo_item',\n"
                    "    how='left',\n"
                    ")\n"
                    "completo[['mov_item', 'item_descripcion', 'mov_cantidad', 'valor']]"
                ),
            },
        ],
    },
    {
        "id": "05-graficas",
        "title": "5. Gráficas con matplotlib y seaborn",
        "summary": "Convierte tablas en gráficas: barras, líneas, histogramas y dispersión, con dos librerías distintas.",
        "challenge_id": "05-graficas:reto-1",
        "steps": [
            {
                "title": "5.1 La forma más rápida: .plot()",
                "explanation": (
                    "Cualquier DataFrame o columna tiene un método `.plot()` que usa matplotlib por "
                    "debajo. `kind='bar'` hace barras. Prueba también `kind='line'`, `'hist'`, "
                    "`'box'`, `'scatter'` (este último necesita `x=` e `y=`)."
                ),
                "code": (
                    "try:\n"
                    "    df_02_movimiento\n"
                    "except NameError:\n"
                    "    df_02_movimiento = pd.DataFrame({\n"
                    "        'mov_item': ['A100', 'B200', 'C300'],\n"
                    "        'mov_cantidad': [8, 5, 2],\n"
                    "    })\n"
                    "\n"
                    "df_02_movimiento.set_index('mov_item')['mov_cantidad'].plot(kind='bar')\n"
                    "plt.title('Cantidad por ítem')\n"
                    "plt.tight_layout()"
                ),
            },
            {
                "title": "5.2 Personalizar: título, ejes y tamaño",
                "explanation": (
                    "`plt.title()`, `plt.xlabel()`, `plt.ylabel()` agregan texto. `figsize=(ancho, "
                    "alto)` dentro de `.plot()` controla el tamaño. Sin título ni ejes claros, una "
                    "gráfica no dice nada a quien la vea."
                ),
                "code": (
                    "df_02_movimiento.set_index('mov_item')['mov_cantidad'].plot(\n"
                    "    kind='bar', figsize=(6, 4), color='#51599b'\n"
                    ")\n"
                    "plt.title('Cantidad movida por ítem')\n"
                    "plt.xlabel('Ítem')\n"
                    "plt.ylabel('Cantidad')\n"
                    "plt.tight_layout()"
                ),
            },
            {
                "title": "5.3 seaborn: gráficas estadísticas con menos código",
                "explanation": (
                    "seaborn (`sns`) está construido sobre matplotlib pero simplifica gráficas "
                    "estadísticas comunes. `sns.barplot(data=df, x=..., y=...)` hace barras "
                    "directamente desde un DataFrame sin agrupar primero a mano. Úsalo cuando "
                    "quieras algo rápido y ya con buen estilo por defecto."
                ),
                "code": (
                    "sns.barplot(data=df_02_movimiento, x='mov_item', y='mov_cantidad')\n"
                    "plt.title('Cantidad por ítem (seaborn)')\n"
                    "plt.tight_layout()"
                ),
            },
            {
                "title": "5.4 Histogramas y distribución con seaborn",
                "explanation": (
                    "`sns.histplot()` muestra cómo se distribuyen los valores de una columna "
                    "numérica — cuántas veces cae en cada rango. Útil para detectar valores "
                    "atípicos o entender la variabilidad de tus datos."
                ),
                "code": (
                    "import numpy as np\n"
                    "datos_ejemplo = pd.DataFrame({'valor': np.random.normal(100, 20, 200)})\n"
                    "sns.histplot(data=datos_ejemplo, x='valor', bins=20)\n"
                    "plt.title('Distribución de ejemplo')\n"
                    "plt.tight_layout()"
                ),
            },
            {
                "title": "5.5 Flujo completo: agrupar + graficar en datos reales",
                "explanation": (
                    "Así se ve un análisis completo: cargar, agrupar y graficar en pocas líneas. "
                    "Si cargaste '02_movimiento' real desde el panel, esta celda usa tus datos "
                    "reales de sico."
                ),
                "code": (
                    "resumen_final = (df_02_movimiento.groupby('mov_item')['mov_cantidad']\n"
                    "                 .sum()\n"
                    "                 .sort_values(ascending=False))\n"
                    "resumen_final.plot(kind='bar', figsize=(7, 4), title='Resumen final por ítem')\n"
                    "plt.tight_layout()"
                ),
            },
        ],
    },
    {
        "id": "06-limpieza",
        "title": "6. Limpiar datos: vacíos, duplicados y texto",
        "summary": "Antes de sumar o agrupar, revisa la calidad: celdas vacías, filas repetidas y textos mal escritos cambian los resultados.",
        "challenge_id": "06-limpieza:reto-1",
        "steps": [
            {
                "title": "6.1 Una tabla con problemas típicos",
                "explanation": (
                    "Los archivos reales casi nunca vienen limpios. Esta tabla de ejemplo tiene, a "
                    "propósito, los tres problemas más comunes: filas repetidas, celdas vacías y "
                    "textos escritos de formas distintas ('Bogotá' y 'bogotá'). Mismo patrón "
                    "try/except de siempre: si ya existe `df_clientes`, se usa la tuya."
                ),
                "code": (
                    "try:\n"
                    "    df_clientes\n"
                    "except NameError:\n"
                    "    df_clientes = pd.DataFrame({\n"
                    "        'cliente': ['Ana Gómez', 'Luis Pérez', 'Ana Gómez', 'Marta Ruiz', ' Carlos Díaz ', 'Luis Pérez', 'Sofía León'],\n"
                    "        'ciudad': ['Bogotá', 'Medellín', 'Bogotá', None, 'Cali', 'Medellín', 'bogotá'],\n"
                    "        'compras': [120000, 85000, 120000, 40000, None, 85000, 60000],\n"
                    "    })\n"
                    "df_clientes"
                ),
            },
            {
                "title": "6.2 Contar las celdas vacías",
                "explanation": (
                    "`.isna()` marca con True cada celda vacía (NaN/None) y `.sum()` cuenta cuántas "
                    "hay por columna. Una métrica con vacíos suma menos de lo que debería, y una "
                    "categoría vacía termina en un grupo '(vacío)' en los reportes."
                ),
                "code": "df_clientes.isna().sum()",
            },
            {
                "title": "6.3 Encontrar y quitar filas duplicadas",
                "explanation": (
                    "`.duplicated()` marca las filas que repiten exactamente a una anterior. Si una "
                    "venta aparece dos veces, cualquier total queda inflado. `.drop_duplicates()` "
                    "devuelve la tabla sin esas repeticiones (no modifica la original: hay que "
                    "guardar el resultado en una variable)."
                ),
                "code": (
                    "print('Filas duplicadas:', df_clientes.duplicated().sum())\n"
                    "sin_duplicados = df_clientes.drop_duplicates()\n"
                    "sin_duplicados"
                ),
            },
            {
                "title": "6.4 Qué hacer con los vacíos: quitar o rellenar",
                "explanation": (
                    "`.dropna(subset=['col'])` quita las filas donde esa columna está vacía. "
                    "`.fillna(valor)` las rellena. Decide según el caso: un cliente sin ciudad no "
                    "se puede agrupar por ciudad (mejor quitarlo de ESE análisis), pero unas "
                    "compras vacías a veces significan 0."
                ),
                "code": (
                    "con_ciudad = sin_duplicados.dropna(subset=['ciudad']).copy()\n"
                    "con_ciudad['compras'] = con_ciudad['compras'].fillna(0)\n"
                    "con_ciudad"
                ),
            },
            {
                "title": "6.5 Normalizar textos",
                "explanation": (
                    "Para pandas, 'Bogotá' y 'bogotá' son dos ciudades distintas, y ' Carlos Díaz ' "
                    "(con espacios) no es igual a 'Carlos Díaz'. `.str.strip()` quita los espacios de "
                    "los extremos y `.str.title()` deja cada palabra con mayúscula inicial."
                ),
                "code": (
                    "con_ciudad['cliente'] = con_ciudad['cliente'].str.strip()\n"
                    "con_ciudad['ciudad'] = con_ciudad['ciudad'].str.title()\n"
                    "con_ciudad.groupby('ciudad')['compras'].sum()"
                ),
            },
        ],
    },
    {
        "id": "07-fechas",
        "title": "7. Trabajar con fechas",
        "summary": "Convierte texto en fechas de verdad, extrae año y mes, filtra por periodos y mira la tendencia mes a mes.",
        "challenge_id": "07-fechas:reto-1",
        "steps": [
            {
                "title": "7.1 Ventas con fecha",
                "explanation": (
                    "Esta tabla de ejemplo tiene una venta por fila, con su fecha, cliente y valor "
                    "neto. Los valores negativos son notas crédito (devoluciones). Lo usamos también "
                    "en la Lección 8."
                ),
                "code": (
                    "try:\n"
                    "    df_ventas\n"
                    "except NameError:\n"
                    "    df_ventas = pd.DataFrame({\n"
                    "        'fecha': ['2026-01-05', '2026-01-18', '2026-01-25', '2026-02-02', '2026-02-14', '2026-02-20', '2026-03-03', '2026-03-09', '2026-03-15', '2026-03-28'],\n"
                    "        'cliente': ['Ana', 'Luis', 'Marta', 'Ana', 'Pedro', 'Luis', 'Ana', 'Pedro', 'Marta', 'Sofía'],\n"
                    "        'neto': [500000, 300000, 150000, 450000, 80000, -300000, 600000, -120000, 200000, 90000],\n"
                    "    })\n"
                    "print(df_ventas.dtypes)\n"
                    "df_ventas"
                ),
            },
            {
                "title": "7.2 Convertir texto en fecha con pd.to_datetime",
                "explanation": (
                    "Mientras `fecha` sea texto (dtype `object`), pandas no sabe que '2026-02-02' va "
                    "después de '2026-01-25' ni qué mes es. `pd.to_datetime()` la convierte a "
                    "`datetime64`. Con `errors='coerce'` un valor que no se entiende queda vacío "
                    "(NaT) en lugar de detener todo."
                ),
                "code": (
                    "fechas = pd.to_datetime(df_ventas['fecha'], errors='coerce')\n"
                    "print('Tipo después de convertir:', fechas.dtype)\n"
                    "fechas"
                ),
            },
            {
                "title": "7.3 Extraer año, mes y día de la semana",
                "explanation": (
                    "Una columna de fechas tiene el accesor `.dt`, que da sus partes: `.dt.year`, "
                    "`.dt.month`, `.dt.day_name()`. Así puedes agrupar por cualquiera de ellas."
                ),
                "code": (
                    "con_partes = df_ventas.assign(\n"
                    "    fecha=fechas,\n"
                    "    anio=fechas.dt.year,\n"
                    "    mes=fechas.dt.month,\n"
                    "    dia=fechas.dt.day_name(),\n"
                    ")\n"
                    "con_partes"
                ),
            },
            {
                "title": "7.4 Filtrar un periodo",
                "explanation": (
                    "Con fechas reales se puede comparar: `fechas >= '2026-02-01'` da True/False por "
                    "fila, igual que cualquier filtro de la Lección 2."
                ),
                "code": (
                    "desde_febrero = df_ventas[fechas >= '2026-02-01']\n"
                    "desde_febrero"
                ),
            },
            {
                "title": "7.5 Tendencia mes a mes",
                "explanation": (
                    "`.dt.to_period('M')` convierte cada fecha en su mes ('2026-01'). Agrupar por "
                    "ese mes y sumar da la serie mensual, y `.pct_change()` calcula cuánto subió o "
                    "bajó cada mes frente al anterior."
                ),
                "code": (
                    "por_mes = df_ventas.groupby(fechas.dt.to_period('M'))['neto'].sum()\n"
                    "print('Variación % frente al mes anterior:')\n"
                    "print((por_mes.pct_change() * 100).round(1))\n"
                    "por_mes.plot(kind='line', marker='o', title='Neto por mes')\n"
                    "plt.tight_layout()"
                ),
            },
        ],
    },
    {
        "id": "08-razonamiento",
        "title": "8. Razonar con los datos: netos, 80/20 y lo que queda fuera",
        "summary": "Cómo llega el tablero sin código a sus conclusiones: totales netos por cliente, el punto del 80% y por qué algunos grupos salen del ranking.",
        "challenge_id": "08-razonamiento:reto-1",
        "steps": [
            {
                "title": "8.1 Los mismos datos de ventas",
                "explanation": (
                    "Usamos `df_ventas` de la Lección 7 (si no la corriste, esta celda la crea). "
                    "Fíjate en Luis y Pedro: tienen ventas, pero también notas crédito."
                ),
                "code": (
                    "try:\n"
                    "    df_ventas\n"
                    "except NameError:\n"
                    "    df_ventas = pd.DataFrame({\n"
                    "        'fecha': ['2026-01-05', '2026-01-18', '2026-01-25', '2026-02-02', '2026-02-14', '2026-02-20', '2026-03-03', '2026-03-09', '2026-03-15', '2026-03-28'],\n"
                    "        'cliente': ['Ana', 'Luis', 'Marta', 'Ana', 'Pedro', 'Luis', 'Ana', 'Pedro', 'Marta', 'Sofía'],\n"
                    "        'neto': [500000, 300000, 150000, 450000, 80000, -300000, 600000, -120000, 200000, 90000],\n"
                    "    })\n"
                    "df_ventas"
                ),
            },
            {
                "title": "8.2 El total NETO de cada cliente",
                "explanation": (
                    "Sumar por cliente descuenta automáticamente sus notas crédito: el resultado es "
                    "lo que de verdad dejó cada uno. Luis quedó en 0 y Pedro en negativo."
                ),
                "code": (
                    "netos = df_ventas.groupby('cliente')['neto'].sum().sort_values(ascending=False)\n"
                    "netos"
                ),
            },
            {
                "title": "8.3 Por qué los netos ≤ 0 salen del ranking",
                "explanation": (
                    "Un 80/20 responde '¿quiénes concentran el valor?'. Un cliente con neto 0 o "
                    "negativo no aporta valor: si lo dejas, el '% del total' de los demás pasa de "
                    "100% y el punto del 80% se mueve. Por eso el tablero sin código los saca del "
                    "ranking y los muestra aparte, con su monto, en vez de esconderlos."
                ),
                "code": (
                    "fuera = netos[netos <= 0]\n"
                    "en_ranking = netos[netos > 0]\n"
                    "print('Fuera del ranking:')\n"
                    "print(fuera)\n"
                    "en_ranking"
                ),
            },
            {
                "title": "8.4 % del total y % acumulado",
                "explanation": (
                    "Con el ranking limpio, cada cliente se divide por el total (`% del total`) y "
                    "`.cumsum()` va sumando de arriba hacia abajo (`% acumulado`). Son exactamente "
                    "las columnas que ves en el tablero."
                ),
                "code": (
                    "pct = (en_ranking / en_ranking.sum() * 100).round(1)\n"
                    "acumulado = (en_ranking.cumsum() / en_ranking.sum() * 100).round(1)\n"
                    "pd.DataFrame({'neto': en_ranking, '% del total': pct, '% acumulado': acumulado})"
                ),
            },
            {
                "title": "8.5 Encontrar el punto del 80%",
                "explanation": (
                    "El primer cliente cuyo acumulado llega a 80% marca el corte: él y todos los de "
                    "arriba son 'los pocos que concentran la mayoría'. Esa es la frase '80/20' del "
                    "tablero, calculada a mano."
                ),
                "code": (
                    "n_cruce = int((acumulado < 80).sum()) + 1\n"
                    "print(f'{n_cruce} de {len(en_ranking)} clientes concentran el {acumulado.iloc[n_cruce - 1]:.0f}% del neto.')"
                ),
            },
        ],
    },
]


def canonical_table_sources(table_var):
    """Server-side constructors for a lesson synthetic table: the body of
    every `except NameError:` branch that creates `table_var` in a lesson
    step, dedented into standalone code. challenges.py executes these in a
    namespace of its own to get the reference data for a check - so the
    reference is the lesson's own code, never whatever the learner has in
    their namespace under the same name."""
    pattern = re.compile(
        rf"try:\n    {re.escape(table_var)}\nexcept NameError:\n((?:    [^\n]*(?:\n|$))+)"
    )
    sources = []
    for lesson in LESSONS:
        for step in lesson["steps"]:
            for match in pattern.finditer(step["code"]):
                body = "\n".join(line[4:] for line in match.group(1).splitlines())
                if body not in sources:
                    sources.append(body)
    return sources


def list_lessons(learner_profile=None):
    """``learner_profile`` (optional): same shape as ``get_lesson()``'s
    parameter -- {"variable", "columns"} from WorkerManager.get_known_profile(),
    or None. Exposes ``usa_datos_reales`` per lesson (Story 11.3) by reusing
    data_context.resolve_context() -- None (no profile, an out-of-scope
    lesson, or an insufficient profile) always yields False."""
    return [
        {
            "id": l["id"],
            "title": l["title"],
            "summary": l["summary"],
            "usa_datos_reales": data_context.resolve_context(l["id"], learner_profile) is not None,
        }
        for l in LESSONS
    ]


def get_lesson(lesson_id, learner_profile=None):
    """``learner_profile`` (optional): {"variable", "columns"} from
    WorkerManager.get_known_profile() -- the column profile of whatever
    Excel this session already has bound. When the lesson is in scope for
    dynamic content (see data_context.LESSON_ROLES) and the profile has
    enough columns, every step's example code/explanation and the
    challenge's prompt get the learner's own variable/column names
    substituted in, instead of the fixed synthetic sico example. None (no
    profile, or the lesson isn't in scope, or the profile is missing a
    needed column type) leaves the content byte-identical to before this
    parameter existed."""
    from app.guided.challenges import get_challenge_meta

    for index, lesson in enumerate(LESSONS):
        if lesson["id"] == lesson_id:
            next_lesson = LESSONS[index + 1] if index + 1 < len(LESSONS) else None
            challenge_id = lesson.get("challenge_id")
            challenge = None
            if challenge_id:
                meta = get_challenge_meta(challenge_id)
                if meta:
                    challenge = {"id": challenge_id, **meta}

            context = data_context.resolve_context(lesson_id, learner_profile)
            steps = lesson["steps"]
            if context is not None:
                steps = [
                    {
                        **step,
                        "code": data_context.substitute_identifiers(step["code"], lesson_id, context),
                        "explanation": data_context.substitute_identifiers(
                            step["explanation"], lesson_id, context
                        ),
                    }
                    for step in steps
                ]
                if challenge is not None:
                    challenge = {
                        **challenge,
                        "prompt": data_context.substitute_identifiers(challenge["prompt"], lesson_id, context),
                    }

            return {
                **{k: v for k, v in lesson.items() if k not in ("challenge_id", "steps")},
                "steps": steps,
                "challenge": challenge,
                "next_lesson_id": next_lesson["id"] if next_lesson else None,
                "next_lesson_title": next_lesson["title"] if next_lesson else None,
            }
    return None
