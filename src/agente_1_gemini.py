"""
Agente 1 — Interpretación con Gemini API.

Este módulo intenta usar Gemini para entender lenguaje natural. Si no existe
GEMINI_API_KEY o falla la llamada, usa un intérprete local por reglas.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from dotenv import load_dotenv

from src.agente_2_motor import normalizar_texto

load_dotenv()


def gemini_disponible() -> bool:
    return bool(os.getenv("GEMINI_API_KEY"))


def _limpiar_json_respuesta(texto: str) -> str:
    """Elimina fences de markdown para poder convertir a JSON."""
    texto = texto.strip()
    texto = re.sub(r"^```json\s*", "", texto, flags=re.IGNORECASE)
    texto = re.sub(r"^```\s*", "", texto)
    texto = re.sub(r"\s*```$", "", texto)
    return texto.strip()


def interpretar_con_gemini(texto_usuario: str, productos: list[dict[str, Any]], contexto: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """
    Usa Gemini para clasificar intención y extraer productos/cantidades.
    Si falla, devuelve None para que el sistema use reglas locales.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    try:
        from google import genai
    except Exception:
        return None

    contexto = contexto or {}
    lista_productos = [
        {
            "nombre": p["nombre"],
            "categoria": p.get("categoria", ""),
            "precio": p.get("precio", 0),
            "alias": p.get("alias", ""),
        }
        for p in productos
    ]

    prompt = f"""
Eres el Agente 1 de un sistema experto multiagente para una tienda de máquinas de coser,
refacciones y accesorios. Tu tarea es interpretar mensajes de clientes.

Productos reales disponibles en la base de datos:
{json.dumps(lista_productos, ensure_ascii=False, indent=2)}

Contexto de conversación:
{json.dumps(contexto, ensure_ascii=False, indent=2)}

Mensaje del cliente:
"{texto_usuario}"

Responde SOLO con JSON válido, sin markdown, con esta estructura:
{{
  "intencion": "cotizar | agregar | finalizar | nueva_cotizacion | despedida | consultar_stock | ayuda | desconocido",
  "productos": [
    {{"texto_producto": "texto escrito por el cliente", "cantidad": 1}}
  ],
  "respuesta_natural": "frase breve opcional para apoyar la respuesta"
}}

Reglas:
- Si el cliente dice solo "no", "no gracias" o equivalente, usa intencion "finalizar" si hay carrito activo.
- Si el cliente dice "sí, 5 carretes", detecta intención "agregar" y producto "carretes" cantidad 5.
- Si el cliente escribe mal un producto, conserva el texto como lo escribió; el Agente 2 resolverá alias/similitud.
- Si no hay cantidad, usa cantidad 1.
"""

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt,
        )
        texto = getattr(response, "text", "") or ""
        datos = json.loads(_limpiar_json_respuesta(texto))
        if "productos" not in datos:
            datos["productos"] = []
        return datos
    except Exception:
        return None


def _cantidad_cerca_de(texto_norm: str, indice: int) -> int | None:
    """Busca un número antes del producto: '5 carretes'."""
    prefijo = texto_norm[max(0, indice - 25):indice]
    numeros = re.findall(r"\b(\d+)\b", prefijo)
    if numeros:
        return int(numeros[-1])
    return None


def _extraer_por_alias(texto_usuario: str, productos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extrae productos cuando un nombre o alias aparece dentro del mensaje.

    Se conserva el orden en que aparecen en la frase del cliente, por ejemplo:
    "pie de teflón y bobina se metal" → prensatela primero, bobina después.
    """
    texto_norm = normalizar_texto(texto_usuario)
    candidatos: list[dict[str, Any]] = []

    for producto in productos:
        nombres = [producto["nombre"]]
        alias = producto.get("alias") or ""
        nombres.extend([a.strip() for a in alias.split(",") if a.strip()])
        nombres = sorted(nombres, key=len, reverse=True)

        for nombre_o_alias in nombres:
            alias_norm = normalizar_texto(nombre_o_alias)
            if not alias_norm:
                continue

            match = re.search(rf"\b{re.escape(alias_norm)}\b", texto_norm)
            if match:
                cantidad = _cantidad_cerca_de(texto_norm, match.start()) or 1
                candidatos.append({
                    "id_producto": int(producto["id_producto"]),
                    "posicion": match.start(),
                    "longitud": len(alias_norm),
                    "texto_producto": nombre_o_alias,
                    "cantidad": cantidad,
                })
                break

    # Si dos alias del mismo producto coincidieron, se conserva el primero en aparecer.
    candidatos.sort(key=lambda x: (x["posicion"], -x["longitud"]))
    detectados: list[dict[str, Any]] = []
    ids_detectados: set[int] = set()
    for c in candidatos:
        if c["id_producto"] in ids_detectados:
            continue
        detectados.append({"texto_producto": c["texto_producto"], "cantidad": c["cantidad"]})
        ids_detectados.add(c["id_producto"])

    return detectados


def _extraer_fragmentos_libres(texto_usuario: str) -> list[dict[str, Any]]:
    """
    Si no se encontró alias directo, crea candidatos a partir de frases del cliente.
    Esto permite que el Agente 2 intente resolver por similitud.
    """
    texto = normalizar_texto(texto_usuario)
    reemplazos = [
        "quisiera una cotizacion para", "quiero una cotizacion para", "cotizacion para",
        "necesito", "quiero", "quisiera", "agrega", "agregar", "dame", "para el", "para la",
        "si", "sí", "por favor", "una", "un", "unos", "unas"
    ]
    for r in reemplazos:
        texto = texto.replace(normalizar_texto(r), " ")
    partes = [p.strip() for p in re.split(r"\s+y\s+|,|;", texto) if p.strip()]

    detectados = []
    for parte in partes:
        cantidad = 1
        m = re.match(r"^(\d+)\s+(.+)$", parte)
        if m:
            cantidad = int(m.group(1))
            parte = m.group(2).strip()
        if len(parte) >= 3:
            detectados.append({"texto_producto": parte, "cantidad": cantidad})
    return detectados


def interpretar_por_reglas(texto_usuario: str, productos: list[dict[str, Any]], contexto: dict[str, Any] | None = None) -> dict[str, Any]:
    """Interpretación básica local cuando Gemini no está configurado."""
    contexto = contexto or {}
    texto_norm = normalizar_texto(texto_usuario)
    carrito_activo = bool(contexto.get("carrito_activo"))
    esperando_nueva = bool(contexto.get("esperando_nueva_cotizacion"))

    negativos = {"no", "nop", "no gracias", "ya no", "negativo", "eso es todo"}
    positivos = {"si", "sí", "claro", "ok", "dale", "va", "de acuerdo"}

    # Primero se extraen productos, porque "sí, 5 carretes" no significa cerrar ni nueva cotización.
    detectados = _extraer_por_alias(texto_usuario, productos)
    if not detectados:
        detectados = _extraer_fragmentos_libres(texto_usuario)

    if detectados:
        return {
            "intencion": "agregar" if carrito_activo else "cotizar",
            "productos": detectados,
            "respuesta_natural": "Detecté productos para cotizar.",
            "fuente": "reglas",
        }

    if texto_norm in negativos:
        return {
            "intencion": "despedida" if esperando_nueva else "finalizar",
            "productos": [],
            "respuesta_natural": "El cliente no desea agregar más.",
            "fuente": "reglas",
        }

    if texto_norm in positivos:
        return {
            "intencion": "nueva_cotizacion" if esperando_nueva else "ayuda",
            "productos": [],
            "respuesta_natural": "Respuesta afirmativa del cliente.",
            "fuente": "reglas",
        }

    if any(palabra in texto_norm for palabra in ["stock", "catalogo", "catálogo", "productos", "precio", "lista"]):
        return {"intencion": "consultar_stock", "productos": [], "respuesta_natural": "Consulta de productos.", "fuente": "reglas"}

    if any(palabra in texto_norm for palabra in ["ayuda", "help", "como funciona"]):
        return {"intencion": "ayuda", "productos": [], "respuesta_natural": "Solicitud de ayuda.", "fuente": "reglas"}

    return {"intencion": "desconocido", "productos": [], "respuesta_natural": "No se detectó una intención clara.", "fuente": "reglas"}


def interpretar_mensaje(texto_usuario: str, productos: list[dict[str, Any]], contexto: dict[str, Any] | None = None) -> dict[str, Any]:
    """Punto de entrada del Agente 1: Gemini primero, reglas como respaldo."""
    datos = interpretar_con_gemini(texto_usuario, productos, contexto)
    if datos:
        datos["fuente"] = "gemini"
        # Asegura cantidad 1 cuando Gemini omite cantidad.
        for producto in datos.get("productos", []):
            producto["cantidad"] = producto.get("cantidad") or 1
        return datos

    return interpretar_por_reglas(texto_usuario, productos, contexto)
