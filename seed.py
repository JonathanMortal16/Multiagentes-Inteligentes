"""
Inicializa la base de datos del sistema experto multiagente.
Ejecutar desde la raíz del proyecto:

    py seed.py

Crea tablas, cuenta administradora y productos iniciales.
"""

from src import db

ADMIN_CELULAR = "3331995635"
ADMIN_PASSWORD = "123456789"

PRODUCTOS_INICIALES = [
    {
        "nombre": "Prensatela de teflón",
        "categoria": "Refacción",
        "precio": 49,
        "stock": 25,
        "alias": "pie de teflón, pie teflón, prensatela teflon",
    },
    {
        "nombre": "Bobina de metal",
        "categoria": "Refacción",
        "precio": 49,
        "stock": 30,
        "alias": "bobina metal, bobina se metal, bobina metálica",
    },
    {
        "nombre": "Carrete",
        "categoria": "Accesorio",
        "precio": 5,
        "stock": 100,
        "alias": "carretes, hilo carrete",
    },
    {
        "nombre": "Aguja para máquina familiar",
        "categoria": "Aguja",
        "precio": 12,
        "stock": 80,
        "alias": "aguja familiar, agujas familiares, aguja maquina familiar",
    },
    {
        "nombre": "Aguja para máquina industrial",
        "categoria": "Aguja",
        "precio": 15,
        "stock": 70,
        "alias": "aguja industrial, agujas industriales, aguja maquina industrial",
    },
    {
        "nombre": "Aceite para máquina de coser",
        "categoria": "Mantenimiento",
        "precio": 35,
        "stock": 40,
        "alias": "aceite maquina, aceite para coser, aceite de maquina de coser",
    },
    {
        "nombre": "Banda para máquina de coser",
        "categoria": "Refacción",
        "precio": 65,
        "stock": 20,
        "alias": "banda maquina, correa para maquina, banda de maquina de coser",
    },
    {
        "nombre": "Pedal para máquina de coser",
        "categoria": "Refacción",
        "precio": 180,
        "stock": 10,
        "alias": "pedal maquina, pedal de maquina, pedal eléctrico, pedal electrico",
    },
]


def asegurar_admin() -> None:
    """Crea o actualiza la cuenta administradora requerida por el proyecto."""
    try:
        usuario = db.obtener_usuario_por_celular(ADMIN_CELULAR)
        if usuario:
            # Se actualiza por si el alumno ya había creado la cuenta con otro rol.
            db.ejecutar_accion(
                """
                UPDATE usuarios
                SET nombre = ?, apellido = ?, password_hash = ?, rol = ?
                WHERE celular = ?;
                """,
                ("Administrador", "General", db.hash_password(ADMIN_PASSWORD), "administrador", ADMIN_CELULAR),
            )
        else:
            db.crear_usuario("Administrador", "General", ADMIN_CELULAR, ADMIN_PASSWORD, "administrador")
    except db.DatabaseError as exc:
        raise SystemExit(f"Error al crear el administrador: {exc}") from exc


def cargar_productos() -> None:
    """Inserta/actualiza productos base para las pruebas del chatbot."""
    for producto in PRODUCTOS_INICIALES:
        db.upsert_producto_seed(**producto)


def main() -> None:
    db.inicializar_esquema()
    asegurar_admin()
    cargar_productos()

    print("Base de datos inicializada correctamente.")
    print(f"Ruta SQLite: {db.DB_PATH}")
    print("Administrador:")
    print(f"  Celular: {ADMIN_CELULAR}")
    print(f"  Contraseña: {ADMIN_PASSWORD}")


if __name__ == "__main__":
    main()
