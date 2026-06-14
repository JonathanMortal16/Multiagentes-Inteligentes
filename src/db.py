"""
Módulo de acceso a datos.
Centraliza todas las operaciones de SQLite para que los agentes y app.py
no tengan que escribir SQL directamente.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

DB_PATH = os.getenv("SEWINGBOT_DB_PATH", "database/tienda_maquinas_coser.db")
SCHEMA_PATH = Path("database/schema.sql")


class DatabaseError(Exception):
    """Error controlado para mostrar mensajes claros en Streamlit."""


def existe_bd() -> bool:
    return Path(DB_PATH).exists()


def obtener_conexion() -> sqlite3.Connection:
    """Crea una conexión a SQLite y devuelve filas como diccionarios."""
    if not existe_bd():
        raise DatabaseError(f"No se encontró la base de datos en '{DB_PATH}'. Ejecuta primero: py seed.py")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def crear_conexion_para_seed() -> sqlite3.Connection:
    """Crea la carpeta database y abre la conexión usada por seed.py."""
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def inicializar_esquema() -> None:
    """Ejecuta database/schema.sql para crear las tablas requeridas."""
    if not SCHEMA_PATH.exists():
        raise DatabaseError("No existe database/schema.sql")

    with crear_conexion_para_seed() as conn:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.commit()


def filas_a_diccionarios(filas: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(fila) for fila in filas]


def ejecutar_select(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    try:
        with obtener_conexion() as conn:
            cur = conn.execute(sql, params)
            return filas_a_diccionarios(cur.fetchall())
    except sqlite3.Error as exc:
        raise DatabaseError(f"Error al consultar la base de datos: {exc}") from exc


def ejecutar_accion(sql: str, params: tuple = ()) -> int:
    try:
        with obtener_conexion() as conn:
            cur = conn.execute(sql, params)
            conn.commit()
            return int(cur.lastrowid)
    except sqlite3.IntegrityError as exc:
        raise DatabaseError(f"No se pudo guardar porque ya existe un dato repetido o inválido: {exc}") from exc
    except sqlite3.Error as exc:
        raise DatabaseError(f"Error al guardar cambios en la base de datos: {exc}") from exc


# ============================================================
# Seguridad básica de usuarios
# ============================================================

def hash_password(password: str) -> str:
    """Genera hash SHA-256 para no guardar contraseñas en texto plano."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def crear_usuario(nombre: str, apellido: str, celular: str, password: str, rol: str = "cliente") -> int:
    """Registra un usuario nuevo. El celular es único."""
    nombre = nombre.strip()
    apellido = apellido.strip()
    celular = limpiar_celular(celular)

    if not nombre or not apellido or not celular or not password:
        raise DatabaseError("Nombre, apellido, celular y contraseña son obligatorios.")

    if rol not in {"cliente", "administrador"}:
        raise DatabaseError("Rol inválido.")

    if obtener_usuario_por_celular(celular):
        raise DatabaseError("Ya existe una cuenta registrada con ese número de celular.")

    return ejecutar_accion(
        """
        INSERT INTO usuarios (nombre, apellido, celular, password_hash, rol, fecha_creacion)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
        """,
        (nombre, apellido, celular, hash_password(password), rol),
    )


def limpiar_celular(celular: str) -> str:
    """Deja únicamente los dígitos del celular para evitar duplicados por espacios o guiones."""
    return "".join(ch for ch in str(celular) if ch.isdigit())


def obtener_usuario_por_celular(celular: str) -> dict[str, Any] | None:
    filas = ejecutar_select(
        """
        SELECT id_usuario, nombre, apellido, celular, password_hash, rol, fecha_creacion
        FROM usuarios
        WHERE celular = ?;
        """,
        (limpiar_celular(celular),),
    )
    return filas[0] if filas else None


def autenticar_usuario(celular: str, password: str) -> dict[str, Any] | None:
    """Valida celular y contraseña. Regresa el usuario sin exponer el hash."""
    usuario = obtener_usuario_por_celular(celular)
    if not usuario:
        return None

    if usuario["password_hash"] != hash_password(password):
        return None

    usuario = dict(usuario)
    usuario.pop("password_hash", None)
    return usuario


# ============================================================
# Productos
# ============================================================

def estado_producto(stock: int, activo: int) -> str:
    if not activo:
        return "Inactivo"
    if stock <= 0:
        return "Agotado"
    if stock <= 3:
        return "Bajo stock"
    return "Disponible"


def listar_productos_cliente() -> list[dict[str, Any]]:
    """Stock visible para cliente: solo nombre y precio."""
    return ejecutar_select(
        """
        SELECT nombre AS Producto, precio AS Precio
        FROM productos
        WHERE activo = 1
        ORDER BY nombre;
        """
    )


def listar_productos_admin() -> list[dict[str, Any]]:
    """Stock completo para administrador, incluyendo estado calculado."""
    filas = ejecutar_select(
        """
        SELECT id_producto, nombre, categoria, precio, stock, alias, activo
        FROM productos
        ORDER BY id_producto;
        """
    )
    salida: list[dict[str, Any]] = []
    for fila in filas:
        salida.append(
            {
                "ID": fila["id_producto"],
                "Nombre": fila["nombre"],
                "Categoría": fila["categoria"],
                "Precio": fila["precio"],
                "Stock": fila["stock"],
                "Alias": fila.get("alias") or "",
                "Estado": estado_producto(int(fila["stock"]), int(fila["activo"])),
            }
        )
    return salida


def obtener_productos_activos() -> list[dict[str, Any]]:
    return ejecutar_select(
        """
        SELECT id_producto, nombre, categoria, precio, stock, alias, activo
        FROM productos
        WHERE activo = 1
        ORDER BY nombre;
        """
    )


def obtener_producto_por_id(id_producto: int) -> dict[str, Any] | None:
    filas = ejecutar_select(
        """
        SELECT id_producto, nombre, categoria, precio, stock, alias, activo
        FROM productos
        WHERE id_producto = ?;
        """,
        (id_producto,),
    )
    return filas[0] if filas else None


def agregar_producto(nombre: str, categoria: str, precio: float, stock: int, alias: str = "", activo: bool = True) -> int:
    if not nombre.strip() or not categoria.strip():
        raise DatabaseError("Nombre y categoría son obligatorios.")
    if precio < 0 or stock < 0:
        raise DatabaseError("Precio y stock no pueden ser negativos.")

    return ejecutar_accion(
        """
        INSERT INTO productos (nombre, categoria, precio, stock, alias, activo)
        VALUES (?, ?, ?, ?, ?, ?);
        """,
        (nombre.strip(), categoria.strip(), float(precio), int(stock), alias.strip(), 1 if activo else 0),
    )


def modificar_producto(
    id_producto: int,
    nombre: str,
    categoria: str,
    precio: float,
    stock: int,
    alias: str,
    activo: bool = True,
) -> None:
    if not nombre.strip() or not categoria.strip():
        raise DatabaseError("Nombre y categoría son obligatorios.")
    if precio < 0 or stock < 0:
        raise DatabaseError("Precio y stock no pueden ser negativos.")

    ejecutar_accion(
        """
        UPDATE productos
        SET nombre = ?, categoria = ?, precio = ?, stock = ?, alias = ?, activo = ?
        WHERE id_producto = ?;
        """,
        (nombre.strip(), categoria.strip(), float(precio), int(stock), alias.strip(), 1 if activo else 0, id_producto),
    )


def upsert_producto_seed(nombre: str, categoria: str, precio: float, stock: int, alias: str, activo: bool = True) -> None:
    """Inserta o actualiza productos iniciales desde seed.py."""
    with obtener_conexion() as conn:
        conn.execute(
            """
            INSERT INTO productos (nombre, categoria, precio, stock, alias, activo)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(nombre) DO UPDATE SET
                categoria = excluded.categoria,
                precio = excluded.precio,
                stock = excluded.stock,
                alias = excluded.alias,
                activo = excluded.activo;
            """,
            (nombre, categoria, float(precio), int(stock), alias, 1 if activo else 0),
        )
        conn.commit()


# ============================================================
# Cotizaciones
# ============================================================

def generar_referencia(conn: sqlite3.Connection) -> str:
    """Genera referencia DDMMYYYY + consecutivo de 4 dígitos."""
    prefijo = datetime.now().strftime("%d%m%Y")
    fila = conn.execute(
        "SELECT COUNT(*) AS total FROM cotizaciones WHERE referencia LIKE ?;",
        (f"{prefijo}%",),
    ).fetchone()
    consecutivo = int(fila["total"]) + 1
    return f"{prefijo}{consecutivo:04d}"


def guardar_cotizacion(id_usuario: int, carrito: dict[str, Any], estado: str = "generada") -> dict[str, Any]:
    """Guarda la cotización y su detalle en SQLite en una sola transacción."""
    items = carrito.get("items", [])
    if not items:
        raise DatabaseError("No se puede guardar una cotización vacía.")

    total = sum(float(item["subtotal"]) for item in items)

    try:
        with obtener_conexion() as conn:
            referencia = generar_referencia(conn)
            cur = conn.execute(
                """
                INSERT INTO cotizaciones (id_usuario, referencia, total, fecha, estado)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?);
                """,
                (id_usuario, referencia, total, estado),
            )
            id_cotizacion = int(cur.lastrowid)

            for item in items:
                conn.execute(
                    """
                    INSERT INTO cotizacion_detalle
                    (id_cotizacion, id_producto, nombre_producto, cantidad, precio_unitario, subtotal)
                    VALUES (?, ?, ?, ?, ?, ?);
                    """,
                    (
                        id_cotizacion,
                        item.get("id_producto"),
                        item["nombre"],
                        int(item["cantidad"]),
                        float(item["precio_unitario"]),
                        float(item["subtotal"]),
                    ),
                )

            conn.commit()
            return {"id_cotizacion": id_cotizacion, "referencia": referencia, "total": total, "estado": estado}
    except sqlite3.Error as exc:
        raise DatabaseError(f"Error al guardar la cotización: {exc}") from exc


def listar_cotizaciones_admin() -> list[dict[str, Any]]:
    """Devuelve las cotizaciones con cliente y productos en formato de tabla."""
    return ejecutar_select(
        """
        SELECT
            u.nombre || ' ' || u.apellido AS 'Nombre del cliente',
            u.celular AS 'Número de celular',
            c.referencia AS Referencia,
            GROUP_CONCAT(d.nombre_producto || ' x' || d.cantidad, ', ') AS Productos,
            c.total AS Total,
            c.fecha AS Fecha,
            c.estado AS Estado
        FROM cotizaciones c
        JOIN usuarios u ON u.id_usuario = c.id_usuario
        JOIN cotizacion_detalle d ON d.id_cotizacion = c.id_cotizacion
        GROUP BY c.id_cotizacion
        ORDER BY c.fecha DESC, c.id_cotizacion DESC;
        """
    )
