import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import text

# Configuración inicial
st.set_page_config(page_title="Control Familiar", layout="wide", page_icon="🏠")

# 1. CONEXIÓN A LA BASE DE DATOS NEON
# Streamlit buscará mágicamente la URL en tu archivo .streamlit/secrets.toml
try:
    conn = st.connection("neon", type="sql")
except Exception as e:
    st.error("⚠️ Error de conexión. Verifica tu archivo secrets.toml")
    st.stop()

st.title("🏠 Control de Presupuesto Familiar")
st.markdown("Ingresa tus gastos mensuales para visualizar tendencias y detectar alzas.")

# 2. FORMULARIO DE INGRESO DE DATOS
with st.expander("➕ Ingresar Nueva Boleta / Gasto", expanded=True):
    with st.form("formulario_gastos", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        
        # Usamos el día 1 de cada mes para agrupar fácilmente
        mes_raw = col1.date_input("Mes del Gasto")
        mes_db = mes_raw.replace(day=1) 
        
        categoria = col2.selectbox("Categoría", [
            "Luz", "Agua", "Gas", "Internet", "Celular", 
            "Dividendo", "Carne", "Feria (Verduras)", "Pan", "Colaciones Niños"
        ])
        
        monto = col3.number_input("Monto Pagado ($ CLP)", min_value=0, step=1000)
        
        # Opcional: Si quieres registrar el consumo (ej. los kWh de luz)
        consumo = col3.number_input("Consumo físico (Opcional - kWh o m3)", min_value=0.0)
        
        btn_guardar = st.form_submit_button("💾 Guardar en la Nube")
        
        if btn_guardar:
            if monto > 0:
                # MAGIA SQL: Inserción directa en Neon
                query = text("""
                    INSERT INTO gastos_familiares (mes, categoria, monto, consumo) 
                    VALUES (:mes, :cat, :monto, :consumo)
                """)
                with conn.session as s:
                    s.execute(query, {"mes": mes_db, "cat": categoria, "monto": monto, "consumo": consumo})
                    s.commit()
                
                st.success(f"✅ ¡${monto:,.0f} registrados en {categoria} exitosamente!")
                st.rerun() # Recarga la app para mostrar el nuevo dato en los gráficos
            else:
                st.warning("El monto debe ser mayor a 0.")

st.markdown("---")

# 3. EXTRACCIÓN Y VISUALIZACIÓN DE DATOS (El Dashboard)
st.subheader("📊 Historial de Consumo")

# Extraemos los datos de Neon. ttl=0 asegura que siempre traiga el dato fresco.
try:
    df = conn.query("SELECT mes, categoria, monto, consumo FROM gastos_familiares ORDER BY mes ASC", ttl=0)
except Exception as e:
    st.info("La tabla aún no existe o está vacía. Ejecuta el CREATE TABLE en Neon primero.")
    st.stop()

if not df.empty:
    # Convertimos la columna mes a formato fecha de Pandas
    df['mes'] = pd.to_datetime(df['mes'])
    
    # KPIs Principales
    gasto_historico = df['monto'].sum()
    mes_actual = df['mes'].max()
    gasto_mes_actual = df[df['mes'] == mes_actual]['monto'].sum()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Gasto Total Histórico", f"${gasto_historico:,.0f}")
    c2.metric(f"Gasto {mes_actual.strftime('%B %Y')}", f"${gasto_mes_actual:,.0f}")
    c3.metric("Registros en BBDD", f"{len(df)} boletas")
    
    st.markdown("---")
    
    # Gráficos Interactivos
    col_izq, col_der = st.columns([2, 1])
    
    with col_izq:
        st.markdown("**📈 Evolución del Gasto por Categoría**")
        # Gráfico de Área Apilada
        evolucion = df.groupby(['mes', 'categoria'])['monto'].sum().reset_index()
        fig_area = px.area(evolucion, x='mes', y='monto', color='categoria', 
                           title="Variación Mensual (Visualiza dónde se te va la plata)",
                           color_discrete_sequence=px.colors.qualitative.Pastel)
        fig_area.update_layout(height=400, xaxis_title="Mes", yaxis_title="Monto ($)")
        st.plotly_chart(fig_area, use_container_width=True)
        
    with col_der:
        st.markdown("**💰 Distribución Total**")
        distribucion = df.groupby('categoria')['monto'].sum().reset_index()
        fig_pie = px.pie(distribucion, values='monto', names='categoria', hole=0.4)
        fig_pie.update_layout(height=400, showlegend=False)
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_pie, use_container_width=True)

    # Tabla de auditoría tipo Excel
    with st.expander("Ver Base de Datos cruda"):
        st.dataframe(df.sort_values(by='mes', ascending=False), use_container_width=True)

else:
    st.info("👋 ¡Base de datos conectada con éxito! Ingresa tu primer gasto arriba para generar los gráficos.")