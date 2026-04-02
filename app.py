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

if "mostrar_form_insumo" not in st.session_state:
    st.session_state.mostrar_form_insumo = False
if "mostrar_form_compra" not in st.session_state:
    st.session_state.mostrar_form_compra = False
if "mostrar_form_salida" not in st.session_state:
    st.session_state.mostrar_form_salida = False

# -----------------------
# Botones de barra lateral
# -----------------------
st.sidebar.subheader("Opciones")

if st.sidebar.button("Nuevo insumo"):
    st.session_state.menu = "Insumos"
    st.session_state.mostrar_form_insumo = True

if st.sidebar.button("Nuevo movimiento"):
    # Preguntar qué tipo de movimiento abrir
    tipo = st.sidebar.radio("Tipo de nuevo movimiento", ["Compra", "Salida/Merma"], key="nuevo_movimiento_tipo")
    if tipo == "Compra":
        st.session_state.menu = "Registrar compra"
        st.session_state.mostrar_form_compra = True
    else:
        st.session_state.menu = "Registrar salida/merma"
        st.session_state.mostrar_form_salida = True

# -----------------------
# Menú principal con radio
# -----------------------
menu_options = ["Dashboard", "Insumos", "Registrar compra", "Registrar salida/merma", "Movimientos"]
menu = st.sidebar.radio("Navegación", menu_options, index=menu_options.index(st.session_state.menu))
st.session_state.menu = menu  # sincronizar

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
# Gestión de Insumos
# -----------------------
elif menu == "Insumos":
    st.subheader("Gestión de insumos")

    if st.session_state.mostrar_form_insumo:
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
            else:
                st.error("El nombre es obligatorio.")

    st.subheader("Listado de insumos")
    insumos = get_insumos()
    if not insumos.empty:
        st.dataframe(insumos, use_container_width=True)
    else:
        st.info("No hay insumos cargados.")

# -----------------------
# Registrar Compra
# -----------------------
elif menu == "Registrar compra":
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
                except Exception as e:
                    st.error(str(e))

# -----------------------
# Registrar Salida / Merma
# -----------------------
elif menu == "Registrar salida/merma":
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
                except Exception as e:
                    st.error(str(e))

# -----------------------
# Movimientos
# -----------------------
elif menu == "Movimientos":
    st.subheader("Historial de movimientos")
    movimientos = get_movimientos()
    if movimientos.empty:
        st.info("No hay movimientos registrados.")
    else:
        st.dataframe(movimientos, use_container_width=True)