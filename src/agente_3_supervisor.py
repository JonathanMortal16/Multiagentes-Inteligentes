"""
Agente 3 — Supervisor / Explicador.

Este agente convierte las decisiones del motor en una explicación clara:
productos detectados, coincidencias, desglose, total, referencia e inferencias.
"""

from __future__ import annotations

from typing import Any

from src import agente_2_motor


def formato_pesos(valor: float) -> str:
    """Formato sencillo para precios en pesos mexicanos."""
    if float(valor).is_integer():
        return f"${int(valor)}"
    return f"${valor:,.2f}"


def generar_desglose_markdown(carrito: dict[str, Any]) -> str:
    """Lista de productos del carrito para mostrarse en el chat."""
    if not carrito.get("items"):
        return "No hay productos en la cotización activa."

    lineas = []
    for item in carrito["items"]:
        linea = (
            f"* {item['nombre']}: {formato_pesos(item['precio_unitario'])} "
            f"x {item['cantidad']} = {formato_pesos(item['subtotal'])}"
        )
        if item.get("alerta_stock"):
            linea += f" ⚠️ {item['alerta_stock']}"
        lineas.append(linea)
    return "\n".join(lineas)


def explicar_cotizacion(carrito: dict[str, Any], referencia: str | None = None, estado: str | None = None) -> str:
    """Genera una explicación completa para exposición o revisión administrativa."""
    total = agente_2_motor.calcular_total(carrito)

    partes = ["### Explicación del Agente 3 — Supervisor"]

    if referencia:
        partes.append(f"**Referencia:** {referencia}")
    if estado:
        partes.append(f"**Estado:** {estado}")

    partes.append("\n**Productos detectados por el Agente 1:**")
    if carrito.get("productos_detectados"):
        for p in carrito["productos_detectados"]:
            partes.append(f"- {p['texto']} x {p['cantidad']}")
    else:
        partes.append("- No se detectaron productos todavía.")

    partes.append("\n**Coincidencias aplicadas por el Agente 2:**")
    if carrito.get("coincidencias"):
        for c in carrito["coincidencias"]:
            partes.append(
                f"- '{c['texto_cliente']}' → '{c['producto_real']}' "
                f"({c['tipo']}, alias/base: {c['alias_usado']}, confianza: {c['score']})"
            )
    else:
        partes.append("- No se aplicaron coincidencias todavía.")

    partes.append("\n**Desglose de cotización:**")
    partes.append(generar_desglose_markdown(carrito))
    partes.append(f"\n**Total:** {formato_pesos(total)} pesos")

    partes.append("\n**Inferencias realizadas:**")
    if carrito.get("inferencias"):
        # Se usa dict.fromkeys para evitar repetir inferencias idénticas en pantalla.
        for inf in dict.fromkeys(carrito["inferencias"]):
            partes.append(f"- {inf}")
    else:
        partes.append("- Aún no se han registrado inferencias.")

    if carrito.get("requiere_revision_admin"):
        partes.append("\n⚠️ **Esta cotización requiere revisión del administrador por stock insuficiente.**")

    return "\n".join(partes)


def mensaje_cotizacion_actual(carrito: dict[str, Any]) -> str:
    """Resumen breve para responder al cliente durante la conversación."""
    total = agente_2_motor.calcular_total(carrito)
    return f"{generar_desglose_markdown(carrito)}\n\nEl total actual es de {formato_pesos(total)} pesos."
