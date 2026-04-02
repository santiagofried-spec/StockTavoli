import streamlit as st
from db import get_insumos, add_insumo, registrar_movimiento, get_movimientos

# -----------------------
# Configuración de la página
# -----------------------
st.set_page_config(page_title="Control de Stock - Tavoli", layout="wide")

# -----------------------
# Inicialización de session_state
# -----------------------
if "menu" not in st.session_state:
    st.session_state.menu = "Dashboard"

# Formularios visibles o no
for key in ["mostrar_form_insumo", "mostrar_form_compra", "mostrar_form_salida"]:
    if key not in st.session_state:
        st.session_state[key] = False

# -----------------------
# Función callback para radio menu
# -----------------------
def cambiar_menu():
    st.session_state.menu = st.session_state.radio_menu

# -----------------------
# Botones de barra lateral
# -----------------------
st.sidebar.subheader("Opciones")

if st.sidebar.button("Nuevo insumo"):
    st.session_state.menu = "Insumos"
    st.session_state.mostrar_form_insumo = True
    st.rerun()

if st.sidebar.button("Nuevo movimiento"):
    st.session_state.menu = "Registrar compra"
    st.session_state.mostrar_form_compra = True
    st.session_state.mostrar_form_salida = True
    st.rerun()

# -----------------------
# Menú principal con radio (sincronizado)
# -----------------------
menu_opciones = ["Dashboard", "Insumos", "Registrar compra", "Registrar salida/merma", "Movimientos"]

st.sidebar.radio(
    "Navegación",
    menu_opciones,
    index=menu_opciones.index(st.session_state.get("menu", "Dashboard")),
    key="radio_menu",
    on_change=cambiar_menu  # callback para mantener session_state actualizado
)

# -----------------------
# DASHBOARD
# -----------------------
if st.session_state.menu == "Dashboard":
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
            use_container_width=True
        )

        st.subheader("Alertas")
        alertas = insumos[insumos["stock_actual"] <= insumos["stock_minimo"]]
        if alertas.empty:
            st.success("No hay alertas de stock.")
        else:
            st.warning("Hay insumos por debajo del stock mínimo:")
            st.dataframe(
                alertas[["nombre", "stock_actual", "stock_minimo", "unidad"]],
                use_container_width=True
            )

# -----------------------
# INSUMOS
# -----------------------
elif st.session_state.menu == "Insumos":
    st.subheader("Gestión de insumos")

    if st.session_state.mostrar_form_insumo:
        st.subheader("Agregar nuevo insumo")
        nombre = st.text_input("Nombre del insumo")
        categoria = st.text_input("Categoría")
        unidad = st.selectbox("Unidad", ["g", "kg", "ml", "L", "un"])
        stock_actual = st.number_input("Stock actual", min_value=0.0, value=0.0)
        stock_minimo = st.number_input("Stock mínimo", min_value=0.0, value=0.0)
        costo_unitario = st.number_input("Costo unitario", min_value=0.0, value=0.0)
        proveedor = st.text_input("Proveedor")

        if st.button("Agregar insumo"):
            if nombre.strip():
                add_insumo(nombre, categoria, unidad, stock_actual, stock_minimo, costo_unitario, proveedor)
                st.success(f"Insumo '{nombre}' agregado correctamente.")
                st.session_state.mostrar_form_insumo = False
                st.rerun()
            else:
                st.error("El nombre es obligatorio.")

    # Listado de insumos
    st.subheader("Listado de insumos")
    insumos = get_insumos()
    if not insumos.empty:
        st.dataframe(insumos, use_container_width=True)
    else:
        st.info("No hay insumos cargados.")

# -----------------------
# REGISTRAR COMPRA
# -----------------------
elif st.session_state.menu == "Registrar compra":
    st.subheader("Registrar compra")
    insumos = get_insumos()
    if insumos.empty:
        st.info("Primero debes cargar insumos.")
    else:
        if st.session_state.mostrar_form_compra:
            opciones = {f"{row['nombre']} ({row['unidad']})": row["id"] for _, row in insumos.iterrows()}
            insumo_label = st.selectbox("Selecciona un insumo", list(opciones.keys()))
            cantidad = st.number_input("Cantidad comprada", min_value=0.01, value=1.0)
            motivo = st.text_input("Proveedor / detalle")

            if st.button("Registrar compra"):
                try:
                    registrar_movimiento("compra", opciones[insumo_label], cantidad, motivo)
                    st.success("Compra registrada correctamente.")
                    st.session_state.mostrar_form_compra = False
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

# -----------------------
# REGISTRAR SALIDA / MERMA
# -----------------------
elif st.session_state.menu == "Registrar salida/merma":
    st.subheader("Registrar salida / merma")
    insumos = get_insumos()
    if insumos.empty:
        st.info("Primero debes cargar insumos.")
    else:
        if st.session_state.mostrar_form_salida:
            opciones = {f"{row['nombre']} ({row['unidad']})": row["id"] for _, row in insumos.iterrows()}
            tipo = st.selectbox("Tipo de salida", ["merma", "consumo", "ajuste"])
            insumo_label = st.selectbox("Selecciona un insumo", list(opciones.keys()))
            cantidad = st.number_input("Cantidad a descontar", min_value=0.01, value=1.0)
            motivo = st.text_input("Motivo")

            if st.button("Registrar salida"):
                try:
                    registrar_movimiento(tipo, opciones[insumo_label], cantidad, motivo)
                    st.success("Salida registrada correctamente.")
                    st.session_state.mostrar_form_salida = False
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

# -----------------------
# MOVIMIENTOS
# -----------------------
elif st.session_state.menu == "Movimientos":
    st.subheader("Historial de movimientos")
    movimientos = get_movimientos()
    if movimientos.empty:
        st.info("No hay movimientos registrados.")
    else:
        st.dataframe(movimientos, use_container_width=True)