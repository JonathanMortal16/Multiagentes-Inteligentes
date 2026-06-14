"""
Agente 2 — Generador de cotización / Motor de inferencia.

Responsabilidades:
- Recibir productos detectados por el Agente 1.
- Resolver nombres reales usando alias y similitud de texto.
- Mantener un carrito de cotización.
- Calcular subtotales, total y alertas de stock.
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any

from src import db


def crear_carrito() -> dict[str, Any]:
    """Estructura base de una cotización activa tipo carrito."""
    return {
        "items": [],
        "inferencias": [],
        "coincidencias": [],
        "productos_detectados": [],
        "requiere_revision_admin": False,
    }


def normalizar_texto(texto: str) -> str:
    """Normaliza texto para comparar nombres aunque tengan acentos o mayúsculas."""
    texto = texto.lower().strip()
    texto = "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    texto = re.sub(r"[^a-z0-9ñ\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def obtener_alias_producto(producto: dict[str, Any]) -> list[str]:
    alias = producto.get("alias") or ""
    nombres = [producto["nombre"]] + [a.strip() for a in alias.split(",") if a.strip()]
    return nombres


def similitud(a: str, b: str) -> float:
    return SequenceMatcher(None, normalizar_texto(a), normalizar_texto(b)).ratio()


def resolver_producto(texto_producto: str) -> dict[str, Any]:
    """
    Busca el producto real por nombre exacto, alias o similitud.
    Devuelve producto, tipo de coincidencia e inferencias realizadas.
    """
    productos = db.obtener_productos_activos()
    texto_norm = normalizar_texto(texto_producto)

    mejor_producto: dict[str, Any] | None = None
    mejor_alias = ""
    mejor_score = 0.0
    tipo = "sin_coincidencia"

    for producto in productos:
        for nombre_o_alias in obtener_alias_producto(producto):
            candidato_norm = normalizar_texto(nombre_o_alias)

            if texto_norm == candidato_norm:
                return {
                    "producto": producto,
                    "score": 1.0,
                    "alias_usado": nombre_o_alias,
                    "tipo": "exacta" if normalizar_texto(producto["nombre"]) == texto_norm else "alias",
                    "inferencia": f"'{texto_producto}' coincidió con '{producto['nombre']}' usando {'nombre exacto' if normalizar_texto(producto['nombre']) == texto_norm else 'alias'}."
                }

            # También se acepta cuando el alias está contenido en la frase completa del cliente.
            if candidato_norm and (candidato_norm in texto_norm or texto_norm in candidato_norm):
                score = 0.96
            else:
                score = similitud(texto_norm, candidato_norm)

            if score > mejor_score:
                mejor_producto = producto
                mejor_alias = nombre_o_alias
                mejor_score = score
                tipo = "similaridad"

    # Umbral moderado para tolerar errores como "bobina se metal" o variaciones simples.
    if mejor_producto and mejor_score >= 0.62:
        return {
            "producto": mejor_producto,
            "score": mejor_score,
            "alias_usado": mejor_alias,
            "tipo": tipo,
            "inferencia": f"'{texto_producto}' no coincidió exacto; se asignó a '{mejor_producto['nombre']}' por similitud/alias '{mejor_alias}' ({mejor_score:.2f})."
        }

    return {
        "producto": None,
        "score": mejor_score,
        "alias_usado": mejor_alias,
        "tipo": "no_encontrado",
        "inferencia": f"No se encontró un producto confiable para '{texto_producto}'."
    }


def normalizar_cantidad(cantidad: Any) -> int:
    """Si el cliente no da cantidad o da un valor inválido, se asume 1."""
    try:
        cantidad_int = int(cantidad)
    except (TypeError, ValueError):
        return 1
    return max(cantidad_int, 1)


def agregar_o_actualizar_item(carrito: dict[str, Any], producto: dict[str, Any], cantidad: int) -> dict[str, Any]:
    """Agrega un producto al carrito o suma cantidad si ya existía."""
    precio = float(producto["precio"])
    id_producto = int(producto["id_producto"])

    for item in carrito["items"]:
        if int(item["id_producto"]) == id_producto:
            item["cantidad"] += cantidad
            item["subtotal"] = item["cantidad"] * item["precio_unitario"]
            item["stock_disponible"] = int(producto["stock"])
            return item

    item = {
        "id_producto": id_producto,
        "nombre": producto["nombre"],
        "cantidad": cantidad,
        "precio_unitario": precio,
        "subtotal": precio * cantidad,
        "stock_disponible": int(producto["stock"]),
        "alerta_stock": "",
    }
    carrito["items"].append(item)
    return item


def validar_stock(carrito: dict[str, Any], item: dict[str, Any]) -> None:
    """Marca la cotización para revisión cuando la cantidad supera el stock."""
    if int(item["cantidad"]) > int(item["stock_disponible"]):
        item["alerta_stock"] = (
            f"Stock insuficiente: solicitado {item['cantidad']}, disponible {item['stock_disponible']}."
        )
        carrito["requiere_revision_admin"] = True
        carrito["inferencias"].append(
            f"El producto '{item['nombre']}' requiere revisión del administrador por falta de stock."
        )
    else:
        item["alerta_stock"] = ""


def recalcular_alertas_stock(carrito: dict[str, Any]) -> None:
    """Revisa todos los items después de sumar cantidades."""
    carrito["requiere_revision_admin"] = False
    for item in carrito.get("items", []):
        if int(item["cantidad"]) > int(item["stock_disponible"]):
            item["alerta_stock"] = (
                f"Stock insuficiente: solicitado {item['cantidad']}, disponible {item['stock_disponible']}."
            )
            carrito["requiere_revision_admin"] = True
        else:
            item["alerta_stock"] = ""


def agregar_productos_a_carrito(
    carrito: dict[str, Any] | None,
    productos_detectados: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Procesa los productos detectados por el Agente 1 y actualiza el carrito.
    Cada producto detectado debe traer: texto_producto y cantidad.
    """
    if carrito is None:
        carrito = crear_carrito()

    no_encontrados: list[str] = []
    agregados: list[dict[str, Any]] = []

    for detectado in productos_detectados:
        texto_producto = detectado.get("texto_producto") or detectado.get("nombre") or ""
        cantidad = normalizar_cantidad(detectado.get("cantidad", 1))

        if not texto_producto.strip():
            continue

        carrito["productos_detectados"].append({"texto": texto_producto, "cantidad": cantidad})

        if "cantidad" not in detectado or detectado.get("cantidad") in (None, ""):
            carrito["inferencias"].append(
                f"No se especificó cantidad para '{texto_producto}', por regla se asumió cantidad 1."
            )

        resultado = resolver_producto(texto_producto)
        carrito["inferencias"].append(resultado["inferencia"])

        producto = resultado["producto"]
        if not producto:
            no_encontrados.append(texto_producto)
            continue

        carrito["coincidencias"].append(
            {
                "texto_cliente": texto_producto,
                "producto_real": producto["nombre"],
                "tipo": resultado["tipo"],
                "alias_usado": resultado["alias_usado"],
                "score": round(float(resultado["score"]), 2),
            }
        )
        item = agregar_o_actualizar_item(carrito, producto, cantidad)
        agregados.append(item)

    recalcular_alertas_stock(carrito)
    total = calcular_total(carrito)

    return {
        "carrito": carrito,
        "agregados": agregados,
        "no_encontrados": no_encontrados,
        "total": total,
    }


def calcular_total(carrito: dict[str, Any]) -> float:
    return sum(float(item["subtotal"]) for item in carrito.get("items", []))


def estado_para_guardar(carrito: dict[str, Any]) -> str:
    return "revision_admin" if carrito.get("requiere_revision_admin") else "generada"


def carrito_tiene_items(carrito: dict[str, Any] | None) -> bool:
    return bool(carrito and carrito.get("items"))
