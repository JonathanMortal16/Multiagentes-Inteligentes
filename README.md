# SewingBot — Sistema Experto Multiagente

Sistema experto multiagente para una tienda de máquinas de coser, refacciones y accesorios. El prototipo está hecho con **Streamlit**, **SQLite** y **Gemini API**.

El sistema conserva la arquitectura de 3 agentes:

- **Agente 1 — Atención al cliente:** interpreta mensajes en lenguaje natural con Gemini API. Si no hay API Key configurada, usa reglas locales básicas.
- **Agente 2 — Motor de inferencia / cotización:** busca productos por nombre, alias o similitud, mantiene un carrito activo, calcula subtotal y total, valida stock y guarda cotizaciones.
- **Agente 3 — Supervisor / Explicador:** muestra productos detectados, coincidencias aplicadas, desglose, total, referencia e inferencias realizadas.

---

## Estructura del proyecto

```text
app.py
seed.py
requirements.txt
.env.example
README.md
database/
  schema.sql
src/
  db.py
  agente_1_chatbot.py
  agente_1_gemini.py
  agente_2_motor.py
  agente_3_supervisor.py
docs/
```

---

## Instalación

Desde la carpeta principal del proyecto, crea o activa tu entorno de Python y ejecuta:

```bash
py -m pip install -r requirements.txt
```

---

## Configurar Gemini API

Copia el archivo `.env.example` como `.env`:

```bash
copy .env.example .env
```

Dentro de `.env`, coloca tu clave:

```env
GEMINI_API_KEY=TU_API_KEY_AQUI
```

Si no configuras `GEMINI_API_KEY`, el sistema seguirá funcionando con reglas básicas locales. Esto sirve para probar el proyecto sin internet o sin API Key.

---

## Crear base de datos y datos iniciales

Ejecuta:

```bash
py seed.py
```

Esto crea la base de datos SQLite en:

```text
database/tienda_maquinas_coser.db
```

También crea automáticamente la cuenta de administrador:

```text
Número: 3331995635
Contraseña: 123456789
Rol: administrador
```

---

## Ejecutar el sistema

Ejecuta:

```bash
py -m streamlit run app.py
```

Al abrir la página aparecen dos opciones:

1. **Iniciar sesión**
2. **Crear cuenta**

---

## Flujo del cliente

El cliente puede crear una cuenta con:

- Nombre
- Apellido
- Número de celular
- Contraseña

Reglas:

- Solo puede existir una cuenta por número de celular.
- La contraseña se guarda con hash SHA-256, no en texto plano.

Después de iniciar sesión como cliente, aparecen estas opciones:

- **Chat de cotización**
- **Stock disponible para cliente**

En el stock para cliente solo se muestra:

- Nombre del producto
- Precio

No se muestra stock, costo interno, ID ni datos administrativos.

---

## Flujo del administrador

Al iniciar sesión como administrador, aparecen estas opciones:

- **Chat**
- **Stock completo**
- **Agregar producto**
- **Modificar producto**
- **Ver cotizaciones**

En **Stock completo** se muestra:

- ID
- Nombre
- Categoría
- Precio
- Stock
- Alias
- Estado

En **Agregar producto**, el administrador puede registrar:

- Nombre
- Categoría
- Precio
- Stock
- Alias o nombres alternativos
- Estado activo/inactivo

En **Modificar producto**, puede actualizar esos mismos datos.

En **Ver cotizaciones**, se muestra una tabla con:

- Nombre del cliente
- Número de celular
- Referencia
- Productos
- Total
- Fecha
- Estado

---

## Ejemplo de uso del chat

Cliente:

```text
Quisiera una cotización para el pie de teflón y una bobina se metal
```

El sistema interpreta:

- `pie de teflón` como **Prensatela de teflón**
- `bobina se metal` como **Bobina de metal**

Respuesta esperada:

```text
Encontré estos productos:

* Prensatela de teflón: $49 x 1 = $49
* Bobina de metal: $49 x 1 = $49

El total actual es de $98 pesos.
¿Desea agregar algo más?
```

Cliente:

```text
Sí, 5 carretes
```

Respuesta esperada:

```text
Agregué 5 carretes a la cotización:

* Prensatela de teflón: $49 x 1 = $49
* Bobina de metal: $49 x 1 = $49
* Carrete: $5 x 5 = $25

El total actual es de $123 pesos.
¿Desea agregar algo más?
```

Cliente:

```text
No
```

El sistema guarda la cotización en SQLite y genera una referencia automática:

```text
DDMMYYYY + consecutivo de 4 dígitos
Ejemplo: 010220260001
```

---

## Base de datos

Tablas principales:

### usuarios

- id_usuario
- nombre
- apellido
- celular
- password_hash
- rol
- fecha_creacion

### productos

- id_producto
- nombre
- categoria
- precio
- stock
- alias
- activo

### cotizaciones

- id_cotizacion
- id_usuario
- referencia
- total
- fecha
- estado

### cotizacion_detalle

- id_detalle
- id_cotizacion
- id_producto
- nombre_producto
- cantidad
- precio_unitario
- subtotal

---

## Productos iniciales

`seed.py` carga estos productos iniciales:

- Prensatela de teflón — precio 49 — alias: pie de teflón, pie teflón, prensatela teflon
- Bobina de metal — precio 49 — alias: bobina metal, bobina se metal, bobina metálica
- Carrete — precio 5 — alias: carretes, hilo carrete
- Aguja para máquina familiar
- Aguja para máquina industrial
- Aceite para máquina de coser
- Banda para máquina de coser
- Pedal para máquina de coser

---

## Inferencias implementadas

El sistema aplica inferencias como:

- Si el producto no coincide exactamente, se busca por alias.
- Si no hay alias exacto, se usa similitud de texto.
- Si el usuario no indica cantidad, se asume cantidad 1.
- Si el cliente dice “sí, 5 carretes”, se agregan 5 unidades al carrito activo.
- Si el cliente dice “no”, se cierra y guarda la cotización.
- Si no hay stock suficiente, la cotización se marca como `revision_admin`.

---

## Archivos principales

- `app.py`: interfaz Streamlit, login, roles y navegación.
- `seed.py`: crea tablas, administrador y productos iniciales.
- `src/db.py`: funciones de acceso a SQLite.
- `src/agente_1_gemini.py`: interpretación con Gemini API o reglas locales.
- `src/agente_1_chatbot.py`: orquestación del chat.
- `src/agente_2_motor.py`: motor de inferencia y carrito.
- `src/agente_3_supervisor.py`: explicación de cotizaciones e inferencias.

---

## Comandos rápidos

```bash
py -m pip install -r requirements.txt
py seed.py
py -m streamlit run app.py
```
