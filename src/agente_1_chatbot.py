"""
Orquestador del chat.

Conecta los 3 agentes:
- Agente 1: interpreta lenguaje natural con Gemini o reglas.
- Agente 2: resuelve productos, aplica inferencias y actualiza carrito.
- Agente 3: explica y formatea el desglose de cotización.
"""

from __future__ import annotations

from typing import Any

from src import agente_2_motor, agente_3_supervisor, db
from src.agente_1_gemini import interpretar_mensaje

HORARIO = """Horario:
Lunes a viernes de 10:00 a.m. a 7:00 p.m.
Sábados de 10:00 a.m. a 3:00 p.m."""

CLABE_INTERBANCARIA = "1234567890"


def obtener_mensaje_bienvenida(nombre: str | None = None) -> str:
    saludo = f"Hola, {nombre}." if nombre else "Hola."
    return (
        f"{saludo} Soy el asistente de cotizaciones de la tienda de máquinas de coser.\n\n"
        "Puedes escribirme en lenguaje natural, por ejemplo:\n"
        "**Quisiera una cotización para el pie de teflón y una bobina se metal**"
    )


def _respuesta_stock_cliente() -> str:
    productos = db.listar_productos_cliente()
    if not productos:
        return "Por el momento no hay productos activos para mostrar."

    lineas = ["Estos son los productos disponibles para cotización:"]
    for p in productos:
        lineas.append(f"* {p['Producto']}: {agente_3_supervisor.formato_pesos(float(p['Precio']))}")
    return "\n".join(lineas)


def _texto_productos_detectados(productos_detectados: list[dict[str, Any]]) -> str:
    if not productos_detectados:
        return "productos"
    partes = []
    for p in productos_detectados:
        cantidad = p.get("cantidad", 1) or 1
        texto = p.get("texto_producto") or p.get("nombre") or "producto"
        partes.append(f"{cantidad} {texto}")
    return ", ".join(partes)


def _respuesta_carrito_actual(carrito: dict[str, Any], prefijo: str, no_encontrados: list[str] | None = None) -> str:
    no_encontrados = no_encontrados or []
    respuesta = [prefijo, "", agente_3_supervisor.mensaje_cotizacion_actual(carrito)]

    if no_encontrados:
        respuesta.append("\nNo pude identificar con seguridad estos productos:")
        for producto in no_encontrados:
            respuesta.append(f"* {producto}")
        respuesta.append("Puedes intentar escribirlos con otro nombre o pedir revisión al administrador.")

    if carrito.get("requiere_revision_admin"):
        respuesta.append(
            "\n⚠️ Hay productos con stock insuficiente. La cotización puede guardarse, "
            "pero quedará marcada para revisión del administrador."
        )

    respuesta.append("\n¿Desea agregar algo más?")
    return "\n".join(respuesta)


def _guardar_y_responder(usuario: dict[str, Any], carrito: dict[str, Any]) -> dict[str, Any]:
    estado = agente_2_motor.estado_para_guardar(carrito)
    guardado = db.guardar_cotizacion(usuario["id_usuario"], carrito, estado=estado)
    referencia = guardado["referencia"]

    respuesta = (
        "Su cotización ha sido generada correctamente.\n\n"
        f"Referencia: **{referencia}**\n\n"
        "Puede pasar a la tienda por sus productos.\n"
        f"{HORARIO}\n\n"
        "Si desea transferir, esta es la clave interbancaria:\n"
        f"**{CLABE_INTERBANCARIA}**\n\n"
        "Por favor coloque su referencia en el concepto de pago.\n\n"
    )

    if estado == "revision_admin":
        respuesta += (
            "⚠️ Nota: la cotización quedó marcada para revisión del administrador "
            "porque uno o más productos superan el stock disponible.\n\n"
        )

    respuesta += "¿Desea crear una nueva cotización?"

    return {
        "respuesta": respuesta,
        "carrito": agente_2_motor.crear_carrito(),
        "esperando_nueva_cotizacion": True,
        "referencia": referencia,
        "estado": estado,
    }


def generar_respuesta(
    texto_usuario: str,
    usuario: dict[str, Any],
    carrito: dict[str, Any] | None,
    esperando_nueva_cotizacion: bool = False,
) -> dict[str, Any]:
    """
    Procesa un mensaje del usuario y regresa respuesta + estado actualizado.
    app.py guarda el nuevo carrito y la bandera en st.session_state.
    """
    if carrito is None:
        carrito = agente_2_motor.crear_carrito()

    productos_db = db.obtener_productos_activos()
    contexto = {
        "carrito_activo": agente_2_motor.carrito_tiene_items(carrito),
        "esperando_nueva_cotizacion": esperando_nueva_cotizacion,
        "rol": usuario.get("rol", "cliente"),
    }
    interpretacion = interpretar_mensaje(texto_usuario, productos_db, contexto)
    intencion = interpretacion.get("intencion", "desconocido")
    productos_detectados = interpretacion.get("productos", []) or []

    # Caso posterior al cierre: el sistema pregunta si desea crear una nueva cotización.
    if esperando_nueva_cotizacion:
        if intencion == "nueva_cotizacion":
            nuevo = agente_2_motor.crear_carrito()
            return {
                "respuesta": "Claro, iniciemos una nueva cotización. ¿Qué productos necesita?",
                "carrito": nuevo,
                "esperando_nueva_cotizacion": False,
            }
        if intencion == "despedida":
            return {
                "respuesta": "Gracias por su visita, que tenga buen día.",
                "carrito": agente_2_motor.crear_carrito(),
                "esperando_nueva_cotizacion": False,
            }
        if productos_detectados:
            # Si el cliente escribe directamente otros productos, se inicia una cotización nueva.
            carrito = agente_2_motor.crear_carrito()
            esperando_nueva_cotizacion = False

    if intencion == "consultar_stock":
        return {
            "respuesta": _respuesta_stock_cliente(),
            "carrito": carrito,
            "esperando_nueva_cotizacion": False,
        }

    if intencion == "ayuda":
        return {
            "respuesta": obtener_mensaje_bienvenida(usuario.get("nombre")),
            "carrito": carrito,
            "esperando_nueva_cotizacion": esperando_nueva_cotizacion,
        }

    if intencion == "finalizar":
        if agente_2_motor.carrito_tiene_items(carrito):
            return _guardar_y_responder(usuario, carrito)
        return {
            "respuesta": "Aún no hay productos en la cotización. Puede escribir qué necesita cotizar.",
            "carrito": carrito,
            "esperando_nueva_cotizacion": False,
        }

    if productos_detectados:
        resultado = agente_2_motor.agregar_productos_a_carrito(carrito, productos_detectados)
        carrito = resultado["carrito"]

        if intencion == "agregar" and len(productos_detectados) == 1:
            prefijo = f"Agregué {_texto_productos_detectados(productos_detectados)} a la cotización:"
        elif intencion == "agregar":
            prefijo = "Agregué estos productos a la cotización:"
        else:
            prefijo = "Encontré estos productos:"

        return {
            "respuesta": _respuesta_carrito_actual(carrito, prefijo, resultado.get("no_encontrados")),
            "carrito": carrito,
            "esperando_nueva_cotizacion": False,
        }

    return {
        "respuesta": (
            "No pude identificar un producto o una instrucción clara. "
            "Puede escribir algo como: **quiero una cotización para pie de teflón y bobina de metal**."
        ),
        "carrito": carrito,
        "esperando_nueva_cotizacion": esperando_nueva_cotizacion,
    }
