import streamlit as st
import pandas as pd

from src import agente_2_motor, agente_3_supervisor, db
from src.agente_1_chatbot import generar_respuesta, obtener_mensaje_bienvenida

st.set_page_config(
    page_title="SewingBot Prototipo",
    page_icon="🧵",
    layout="wide",
)


# ============================================================
# Estado de sesión
# ============================================================

def inicializar_estado() -> None:
    """Variables necesarias para login, chat y carrito activo."""
    if "usuario" not in st.session_state:
        st.session_state.usuario = None
    if "carrito" not in st.session_state:
        st.session_state.carrito = agente_2_motor.crear_carrito()
    if "mensajes" not in st.session_state:
        st.session_state.mensajes = []
    if "esperando_nueva_cotizacion" not in st.session_state:
        st.session_state.esperando_nueva_cotizacion = False


def reiniciar_chat(nombre: str | None = None) -> None:
    st.session_state.carrito = agente_2_motor.crear_carrito()
    st.session_state.esperando_nueva_cotizacion = False
    st.session_state.mensajes = [
        {"rol": "assistant", "contenido": obtener_mensaje_bienvenida(nombre)}
    ]


def cerrar_sesion() -> None:
    st.session_state.usuario = None
    reiniciar_chat()
    st.rerun()


# ============================================================
# Login y creación de cuenta
# ============================================================

def mostrar_pantalla_acceso() -> None:
    st.title("🧵 SewingBot — Sistema experto multiagente")
    st.caption("Tienda de máquinas de coser, refacciones y accesorios")

    if not db.existe_bd():
        st.error("No se encontró la base de datos. Ejecuta primero: `py seed.py`")
        st.info("Después inicia el sistema con: `py -m streamlit run app.py`")
        return

    opcion = st.radio(
        "Seleccione una opción",
        ["Iniciar sesión", "Crear cuenta"],
        horizontal=True,
    )

    if opcion == "Iniciar sesión":
        with st.form("form_login"):
            celular = st.text_input("Número de celular")
            password = st.text_input("Contraseña", type="password")
            enviado = st.form_submit_button("Entrar")

            if enviado:
                usuario = db.autenticar_usuario(celular, password)
                if usuario:
                    st.session_state.usuario = usuario
                    reiniciar_chat(usuario["nombre"])
                    st.success("Sesión iniciada correctamente.")
                    st.rerun()
                else:
                    st.error("Número de celular o contraseña incorrectos.")

    else:
        with st.form("form_crear_cuenta"):
            col1, col2 = st.columns(2)
            with col1:
                nombre = st.text_input("Nombre")
                celular = st.text_input("Número de celular")
            with col2:
                apellido = st.text_input("Apellido")
                password = st.text_input("Contraseña", type="password")

            enviado = st.form_submit_button("Crear cuenta")

            if enviado:
                try:
                    db.crear_usuario(nombre, apellido, celular, password, rol="cliente")
                    st.success("Cuenta creada correctamente. Ahora puede iniciar sesión.")
                except db.DatabaseError as exc:
                    st.error(str(exc))


# ============================================================
# Vistas comunes
# ============================================================

def mostrar_encabezado_usuario() -> None:
    usuario = st.session_state.usuario
    st.title("🧵 SewingBot Prototipo")
    st.caption("Sistema experto multiagente con Streamlit, SQLite y Gemini API")

    with st.sidebar:
        st.write(f"**Usuario:** {usuario['nombre']} {usuario['apellido']}")
        st.write(f"**Rol:** {usuario['rol']}")
        if st.button("Cerrar sesión", use_container_width=True):
            cerrar_sesion()

        st.divider()
        st.write("**Agentes del sistema**")
        st.write("✅ Agente 1: Atención con Gemini/reglas")
        st.write("✅ Agente 2: Motor de cotización")
        st.write("✅ Agente 3: Supervisor/explicador")


def mostrar_chat() -> None:
    st.subheader("💬 Chat de cotización")

    col_chat, col_exp = st.columns([2, 1])

    with col_chat:
        for mensaje in st.session_state.mensajes:
            with st.chat_message(mensaje["rol"]):
                st.markdown(mensaje["contenido"])

        texto_usuario = st.chat_input("Escriba su mensaje...")
        if texto_usuario:
            st.session_state.mensajes.append({"rol": "user", "contenido": texto_usuario})

            resultado = generar_respuesta(
                texto_usuario=texto_usuario,
                usuario=st.session_state.usuario,
                carrito=st.session_state.carrito,
                esperando_nueva_cotizacion=st.session_state.esperando_nueva_cotizacion,
            )

            st.session_state.carrito = resultado.get("carrito", st.session_state.carrito)
            st.session_state.esperando_nueva_cotizacion = resultado.get("esperando_nueva_cotizacion", False)
            st.session_state.mensajes.append({"rol": "assistant", "contenido": resultado["respuesta"]})
            st.rerun()

    with col_exp:
        st.markdown("### 🧠 Agente 3")
        st.caption("Explicación de la cotización activa")
        if agente_2_motor.carrito_tiene_items(st.session_state.carrito):
            st.markdown(agente_3_supervisor.explicar_cotizacion(st.session_state.carrito))
        else:
            st.info("Cuando el cliente agregue productos, aquí aparecerán las inferencias y coincidencias.")

        if st.button("🧹 Limpiar chat y carrito", use_container_width=True):
            reiniciar_chat(st.session_state.usuario.get("nombre"))
            st.rerun()


def mostrar_stock_cliente() -> None:
    st.subheader("🛍️ Stock disponible para cliente")
    st.caption("Vista pública: solo se muestra nombre y precio.")
    filas = db.listar_productos_cliente()
    if filas:
        st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)
    else:
        st.info("No hay productos activos disponibles.")


# ============================================================
# Vistas de administrador
# ============================================================

def mostrar_stock_admin() -> None:
    st.subheader("📦 Stock completo")
    filas = db.listar_productos_admin()
    if filas:
        st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)
    else:
        st.info("No hay productos registrados.")


def mostrar_agregar_producto() -> None:
    st.subheader("➕ Agregar producto")
    with st.form("form_agregar_producto"):
        col1, col2 = st.columns(2)
        with col1:
            nombre = st.text_input("Nombre")
            categoria = st.text_input("Categoría")
            precio = st.number_input("Precio", min_value=0.0, value=0.0, step=1.0)
        with col2:
            stock = st.number_input("Stock", min_value=0, value=0, step=1)
            alias = st.text_area("Alias o nombres alternativos", placeholder="Separar por comas")
            activo = st.checkbox("Producto activo", value=True)

        enviado = st.form_submit_button("Guardar producto")
        if enviado:
            try:
                nuevo_id = db.agregar_producto(nombre, categoria, precio, int(stock), alias, activo)
                st.success(f"Producto guardado correctamente. ID: {nuevo_id}")
            except db.DatabaseError as exc:
                st.error(str(exc))


def mostrar_modificar_producto() -> None:
    st.subheader("✏️ Modificar producto")
    productos = db.ejecutar_select(
        """
        SELECT id_producto, nombre, categoria, precio, stock, alias, activo
        FROM productos
        ORDER BY nombre;
        """
    )

    if not productos:
        st.info("No hay productos para modificar.")
        return

    seleccionado = st.selectbox(
        "Seleccione producto",
        productos,
        format_func=lambda p: f"{p['id_producto']} — {p['nombre']}",
    )

    with st.form("form_modificar_producto"):
        col1, col2 = st.columns(2)
        with col1:
            nombre = st.text_input("Nombre", value=seleccionado["nombre"])
            categoria = st.text_input("Categoría", value=seleccionado["categoria"])
            precio = st.number_input("Precio", min_value=0.0, value=float(seleccionado["precio"]), step=1.0)
        with col2:
            stock = st.number_input("Stock", min_value=0, value=int(seleccionado["stock"]), step=1)
            alias = st.text_area("Alias", value=seleccionado.get("alias") or "")
            activo = st.checkbox("Producto activo", value=bool(seleccionado["activo"]))

        enviado = st.form_submit_button("Guardar cambios")
        if enviado:
            try:
                db.modificar_producto(
                    id_producto=int(seleccionado["id_producto"]),
                    nombre=nombre,
                    categoria=categoria,
                    precio=float(precio),
                    stock=int(stock),
                    alias=alias,
                    activo=activo,
                )
                st.success("Producto actualizado correctamente.")
                st.rerun()
            except db.DatabaseError as exc:
                st.error(str(exc))


def mostrar_cotizaciones_admin() -> None:
    st.subheader("🧾 Cotizaciones")
    filas = db.listar_cotizaciones_admin()
    if filas:
        st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)
    else:
        st.info("Todavía no hay cotizaciones guardadas.")


# ============================================================
# Navegación por rol
# ============================================================

def vista_cliente() -> None:
    opcion = st.sidebar.radio(
        "Menú cliente",
        ["Chat de cotización", "Stock disponible para cliente"],
    )

    if opcion == "Chat de cotización":
        mostrar_chat()
    else:
        mostrar_stock_cliente()


def vista_administrador() -> None:
    opcion = st.sidebar.radio(
        "Menú administrador",
        ["Chat", "Stock completo", "Agregar producto", "Modificar producto", "Ver cotizaciones"],
    )

    if opcion == "Chat":
        mostrar_chat()
    elif opcion == "Stock completo":
        mostrar_stock_admin()
    elif opcion == "Agregar producto":
        mostrar_agregar_producto()
    elif opcion == "Modificar producto":
        mostrar_modificar_producto()
    elif opcion == "Ver cotizaciones":
        mostrar_cotizaciones_admin()


def main() -> None:
    inicializar_estado()

    if st.session_state.usuario is None:
        mostrar_pantalla_acceso()
        return

    mostrar_encabezado_usuario()

    if st.session_state.usuario["rol"] == "administrador":
        vista_administrador()
    else:
        vista_cliente()


if __name__ == "__main__":
    main()
