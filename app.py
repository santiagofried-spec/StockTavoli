import streamlit as st
from db import (
    get_insumos, add_insumo, registrar_movimiento, get_movimientos,
    get_recetas, add_receta, get_ingredientes_receta,
    add_ingrediente_receta, delete_ingrediente_receta, registrar_consumo_receta,
)

# -----------------------
# Configuración de la página
# -----------------------
st.set_page_config(page_title="Control de Stock - Tavoli", layout="wide")

# -----------------------
# Inicialización de session_state
# -----------------------
_defaults = {
    "mostrar_form_insumo": False,
    "mostrar_form_compra": False,
    "mostrar_form_salida": False,
    "mostrar_form_consumo": False,
    "mostrar_form_receta": False,
    "_last_menu": None,
}
for key, val in _defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# -----------------------
# Helper: selectbox de insumos
# -----------------------
def build_opciones(insumos):
    """Returns a dict {label: id} for use in selectboxes."""
    return {f"{row['nombre']} ({row['unidad']})": row["id"] for _, row in insumos.iterrows()}

# -----------------------
# Sidebar: botones de acción rápida
# -----------------------
st.sidebar.subheader("Acciones rápidas")

if st.sidebar.button("➕ Nuevo insumo"):
    st.session_state["menu"] = "Insumos"
    st.session_state.mostrar_form_insumo = True

if st.sidebar.button("📦 Registrar compra"):
    st.session_state["menu"] = "Movimientos"
    st.session_state.mostrar_form_compra = True
    st.session_state.mostrar_form_salida = False
    st.session_state.mostrar_form_consumo = False

if st.sidebar.button("📤 Registrar salida/merma"):
    st.session_state["menu"] = "Movimientos"
    st.session_state.mostrar_form_salida = True
    st.session_state.mostrar_form_compra = False
    st.session_state.mostrar_form_consumo = False

if st.sidebar.button("☕ Registrar consumo"):
    st.session_state["menu"] = "Movimientos"
    st.session_state.mostrar_form_consumo = True
    st.session_state.mostrar_form_compra = False
    st.session_state.mostrar_form_salida = False

if st.sidebar.button("📋 Nueva receta"):
    st.session_state["menu"] = "Recetas"
    st.session_state.mostrar_form_receta = True

st.sidebar.divider()

# -----------------------
# Menú principal (sin las páginas de registro)
# -----------------------
menu_options = ["Dashboard", "Insumos", "Recetas", "Movimientos"]

menu = st.sidebar.radio(
    "Navegación",
    menu_options,
    key="menu",
)

# When the user navigates via radio, clear any open forms
if menu != st.session_state.get("_last_menu"):
    st.session_state.mostrar_form_insumo = False
    st.session_state.mostrar_form_compra = False
    st.session_state.mostrar_form_salida = False
    st.session_state.mostrar_form_consumo = False
    st.session_state.mostrar_form_receta = False
st.session_state["_last_menu"] = menu

# -----------------------
# Dashboard
# -----------------------
if menu == "Dashboard":
    st.subheader("Dashboard")
    insumos = get_insumos()
    if insumos.empty:
        st.info("No hay insumos cargados todavía.")
    else:
        total_insumos = len(insumos)
        stock_bajo = len(insumos[insumos["stock_actual"] <= insumos["stock_minimo"]])
        c1, c2 = st.columns(2)
        c1.metric("Cantidad de insumos", total_insumos)
        c2.metric("Insumos con stock bajo", stock_bajo)

        st.subheader("Stock actual")
        st.dataframe(
            insumos[["nombre", "categoria", "unidad", "stock_actual", "stock_minimo", "costo_unitario"]],
            use_container_width=True,
        )

        st.subheader("Alertas")
        alertas = insumos[insumos["stock_actual"] <= insumos["stock_minimo"]]
        if alertas.empty:
            st.success("No hay alertas de stock.")
        else:
            st.warning("Hay insumos por debajo del stock mínimo:")
            st.dataframe(
                alertas[["nombre", "stock_actual", "stock_minimo", "unidad"]],
                use_container_width=True,
            )

# -----------------------
# Gestión de Insumos
# -----------------------
elif menu == "Insumos":
    st.subheader("Gestión de insumos")

    if st.session_state.mostrar_form_insumo:
        with st.form("form_insumo"):
            nombre = st.text_input("Nombre del insumo")
            categoria = st.text_input("Categoría")
            unidad = st.selectbox("Unidad", ["g", "kg", "ml", "L", "un"])
            stock_actual = st.number_input("Stock actual", min_value=0.0, value=0.0)
            stock_minimo = st.number_input("Stock mínimo", min_value=0.0, value=0.0)
            costo_unitario = st.number_input("Costo unitario", min_value=0.0, value=0.0)
            proveedor = st.text_input("Proveedor")
            submitted = st.form_submit_button("Agregar insumo")

        if submitted:
            if nombre.strip():
                add_insumo(nombre, categoria, unidad, stock_actual, stock_minimo, costo_unitario, proveedor)
                st.success(f"Insumo '{nombre}' agregado correctamente.")
                st.session_state.mostrar_form_insumo = False
            else:
                st.error("El nombre es obligatorio.")

    st.subheader("Listado de insumos")
    insumos = get_insumos()
    if not insumos.empty:
        st.dataframe(insumos, use_container_width=True)
    else:
        st.info("No hay insumos cargados.")

# -----------------------
# Recetas
# -----------------------
elif menu == "Recetas":
    st.subheader("Gestión de recetas")

    # --- Crear nueva receta ---
    if st.session_state.mostrar_form_receta:
        with st.form("form_nueva_receta"):
            nombre_receta = st.text_input("Nombre de la receta")
            submitted = st.form_submit_button("Crear receta")
        if submitted:
            if nombre_receta.strip():
                add_receta(nombre_receta.strip())
                st.success(f"Receta '{nombre_receta}' creada.")
                st.session_state.mostrar_form_receta = False
            else:
                st.error("El nombre es obligatorio.")
        st.divider()

    # --- Listado de recetas con ingredientes ---
    recetas = get_recetas()
    if recetas.empty:
        st.info("No hay recetas cargadas. Usá el botón '📋 Nueva receta' para crear una.")
    else:
        for _, receta in recetas.iterrows():
            with st.expander(f"**{receta['nombre']}**", expanded=False):
                ingredientes = get_ingredientes_receta(receta["id"])

                if not ingredientes.empty:
                    st.dataframe(
                        ingredientes[["insumo", "cantidad", "unidad"]],
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.caption("Sin ingredientes todavía.")

                # Add ingredient form
                insumos = get_insumos()
                if not insumos.empty:
                    with st.form(f"form_ing_{receta['id']}"):
                        opciones = build_opciones(insumos)
                        col1, col2 = st.columns([3, 1])
                        insumo_label = col1.selectbox("Insumo", list(opciones.keys()), key=f"sel_{receta['id']}")
                        cantidad_ing = col2.number_input("Cantidad", min_value=0.01, value=1.0, key=f"qty_{receta['id']}")
                        add_ing = st.form_submit_button("Agregar ingrediente")
                    if add_ing:
                        add_ingrediente_receta(receta["id"], opciones[insumo_label], cantidad_ing)
                        st.success("Ingrediente agregado.")
                        st.rerun()
                else:
                    st.caption("Cargá insumos primero para agregar ingredientes.")



    # --- Formulario: Registrar consumo por receta ---
    if st.session_state.mostrar_form_consumo:
        st.subheader("Registrar consumo")
        recetas = get_recetas()
        if recetas.empty:
            st.info("No hay recetas cargadas. Creá una en la sección Recetas.")
        else:
            with st.form("form_consumo"):
                opciones_recetas = {row["nombre"]: row["id"] for _, row in recetas.iterrows()}
                receta_label = st.selectbox("Receta", list(opciones_recetas.keys()))
                cantidad_vendida = st.number_input("Cantidad vendida", min_value=1, value=1, step=1)
                motivo = st.text_input("Nota (opcional)")
                submitted = st.form_submit_button("Registrar consumo")

            if submitted:
                try:
                    registrar_consumo_receta(
                        opciones_recetas[receta_label],
                        cantidad_vendida,
                        motivo=motivo or receta_label,
                    )
                    st.success(f"Consumo de {cantidad_vendida}x {receta_label} registrado.")
                    st.session_state.mostrar_form_consumo = False
                except ValueError as e:
                    st.error(str(e))

        st.divider()

    # --- Formulario: Registrar compra ---
    if st.session_state.mostrar_form_compra:
        st.subheader("Registrar compra")
        insumos = get_insumos()
        if insumos.empty:
            st.info("Primero debes cargar insumos.")
        else:
            with st.form("form_compra"):
                opciones = build_opciones(insumos)
                insumo_label = st.selectbox("Selecciona un insumo", list(opciones.keys()))
                cantidad = st.number_input("Cantidad comprada", min_value=0.01, value=1.0)
                motivo = st.text_input("Proveedor / detalle")
                submitted = st.form_submit_button("Registrar compra")

            if submitted:
                try:
                    registrar_movimiento("compra", opciones[insumo_label], cantidad, motivo)
                    st.success("Compra registrada correctamente.")
                    st.session_state.mostrar_form_compra = False
                except Exception as e:
                    st.error(str(e))

        st.divider()

    # --- Formulario: Registrar salida/merma ---
    if st.session_state.mostrar_form_salida:
        st.subheader("Registrar salida / merma")
        insumos = get_insumos()
        if insumos.empty:
            st.info("Primero debes cargar insumos.")
        else:
            with st.form("form_salida"):
                opciones = build_opciones(insumos)
                tipo = st.selectbox("Tipo de salida", ["merma", "consumo", "ajuste"])
                insumo_label = st.selectbox("Selecciona un insumo", list(opciones.keys()))
                cantidad = st.number_input("Cantidad a descontar", min_value=0.01, value=1.0)
                motivo = st.text_input("Motivo")
                submitted = st.form_submit_button("Registrar salida")

            if submitted:
                try:
                    registrar_movimiento(tipo, opciones[insumo_label], cantidad, motivo)
                    st.success("Salida registrada correctamente.")
                    st.session_state.mostrar_form_salida = False
                except Exception as e:
                    st.error(str(e))

        st.divider()

    # --- Historial ---
    st.subheader("Historial de movimientos")
    movimientos = get_movimientos()
    if movimientos.empty:
        st.info("No hay movimientos registrados.")
    else:
        st.dataframe(movimientos, use_container_width=True)