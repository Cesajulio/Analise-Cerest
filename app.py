import os
import sys
import types
import tempfile
import urllib.request
import json
import pandas as pd
import streamlit as st
import plotly.express as px

# ==========================================
# 1. PARQUET OPTIMIZATION
# ==========================================
# O processamento pesado dos arquivos DBC (DATASUS) foi substituído
# por uma base pré-processada em Parquet local.


# ==========================================
# 2. DICTIONARIES & METADATA LOOKUPS
# ==========================================

# Municipality mapping for the 14 CEREST Cacoal/RO municipalities (Região do Café e Zona da Mata)
MUNICIPIOS_NOMES = {
    # Região do Café
    '110004': "Cacoal",
    '110009': "Espigão D'Oeste",
    '110120': "Ministro Andreazza",
    '110018': "Pimenta Bueno",
    '110147': "Primavera de Rondônia",
    '110148': "São Felipe D'Oeste",
    # Região da Zona da Mata
    '110001': "Alta Floresta D'Oeste",
    '110037': "Alto Alegre dos Parecis",
    '110090': "Castanheiras",
    '110014': "Nova Brasilândia D'Oeste",
    '110050': "Novo Horizonte do Oeste",
    '110145': "Parecis",
    '110028': "Rolim de Moura",
    '110029': "Santa Luzia D'Oeste",
    # Fallbacks de códigos antigos do SINAN
    '110059': "Primavera de Rondônia"
}

# EVOLUCAO mapping dictionary
EVOLUCAO_NOMES = {
    '1': 'Cura',
    '2': 'Incap. Parcial Temp',
    '3': 'Incap. Parcial Perm',
    '4': 'Incap. Total Perm',
    '5': 'Óbito',
    '6': 'Óbito outras causas',
    '9': 'Ignorado'
}

# TIPO_ACID mapping dictionary
TIPO_ACID_NOMES = {
    '1': 'Típico',
    '2': 'Trajeto',
    '3': 'Doença do Trabalho',
    '9': 'Ignorado'
}

# SEXO mapping
SEXO_NOMES = {
    'M': 'Masculino',
    'F': 'Feminino',
    'I': 'Ignorado'
}

# RACA mapping
RACA_NOMES = {
    '1': 'Branca',
    '2': 'Preta',
    '3': 'Amarela',
    '4': 'Parda',
    '5': 'Indígena',
    '9': 'Ignorado'
}

# SIT_MERCAD (column: SIT_TRAB) mapping dictionary
SIT_MERCAD_NOMES = {
    '01': 'Empregado Registrado',
    '1': 'Empregado Registrado',
    '02': 'Empregado sem Registro',
    '2': 'Empregado sem Registro',
    '03': 'Autônomo',
    '3': 'Autônomo',
    '04': 'Trabalhador Temporário',
    '4': 'Trabalhador Temporário',
    '05': 'Trabalhador Avulso',
    '5': 'Trabalhador Avulso',
    '06': 'Trabalhador Doméstico',
    '6': 'Trabalhador Doméstico',
    '07': 'Trabalhador Não Remunerado',
    '7': 'Trabalhador Não Remunerado',
    '08': 'Empregador',
    '8': 'Empregador',
    '09': 'Cooperado',
    '9': 'Cooperado',
    '10': 'Membro de Inst. Não Governamental',
    '11': 'Outros',
    '12': 'Servidor Público',
    '99': 'Ignorado'
}

# CNAE 95 Top Categories Description (Sector)
CNAE_NOMES = {
    '15121': "Abate e prep. aves/coelhos",
    '05126': "Aquicultura",
    '85111': "Atividades hospitalares",
    '01610': "Apoio à agricultura",
    '01619': "Serviços agrícolas terceiros",
    '50202': "Manutenção/reparação veículos",
    '95001': "Serviços domésticos",
    '20109': "Serrarias de madeira",
    '81117': "Tratamento/eliminação resíduos",
    '85200': "Atendimento médico",
    '60267': "Transporte rodoviário de carga",
    '42995': "Obras de engenharia civil",
    '13242': "Extração de minério de ferro"
}

# Offline CBO lookup fallback dictionary
CBO_FALLBACK = {
    '784205': "Operador de processo de produção",
    '512105': "Empregado doméstico nos serviços gerais",
    '621005': "Trabalhador rural na agropecuária",
    '622020': "Volante na agricultura (Bóia-fria)",
    '715210': "Pedreiro de reforma geral",
    '622005': "Trabalhador no cultivo de fruteiras",
    '322205': "Técnico de enfermagem",
    '848510': "Magarefe (Abatedouro)",
    '782510': "Motorista de caminhão",
    '848505': "Desossador",
    '914405': "Mecânico de máquinas agrícolas",
    '771105': "Operador de motosserra",
    '848520': "Abatedor",
    '411045': "Auxiliar de escritório",
    '724315': "Soldador"
}


# ==========================================
# 3. STREAMLIT DATA LOADING & CACHING
# ==========================================

@st.cache_data
def load_cbo_catalog():
    """
    Downloads the official Brazilian CBO dataset from GitHub and creates a dictionary.
    Falls back to a common subset if offline.
    """
    try:
        url = 'https://raw.githubusercontent.com/datasets-br/cbo/master/data/lista.csv'
        df_cbo = pd.read_csv(url)
        df_cbo['codigo_clean'] = df_cbo['codigo'].astype(str).str.replace('-', '')
        cbo_map = dict(zip(df_cbo['codigo_clean'], df_cbo['termo']))
        return cbo_map
    except Exception:
        # Fallback to local hardcoded dictionary if offline
        return CBO_FALLBACK

@st.cache_data
def get_dashboard_data():
    """
    Lê a base de dados otimizada em formato Parquet.
    """
    if os.path.exists('dados_cerest.parquet'):
        return pd.read_parquet('dados_cerest.parquet')
    return pd.DataFrame()


# ==========================================
# 4. DASHBOARD PAGE INITIALIZATION
# ==========================================
st.set_page_config(
    page_title="CEREST Cacoal - Acidentes de Trabalho Graves",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load database and CBO lookup table
if not os.path.exists('dados_cerest.parquet'):
    st.error("Erro: O arquivo de dados otimizado (dados_cerest.parquet) não foi encontrado no diretório atual.")
    st.stop()

with st.spinner("Carregando base de dados..."):
    df_raw = get_dashboard_data()
    cbo_catalog = load_cbo_catalog()

# Apply human-readable lookups to columns
df_cleaned = df_raw.copy()
df_cleaned['Municipio'] = df_cleaned['ID_MUNICIP'].map(MUNICIPIOS_NOMES).fillna(df_cleaned['ID_MUNICIP'].apply(lambda x: f"Outro ({x})"))
df_cleaned['Evolucao_Desc'] = df_cleaned['EVOLUCAO'].map(EVOLUCAO_NOMES).fillna("Não Informado")
df_cleaned['Sit_Mercad_Desc'] = df_cleaned['SIT_TRAB'].map(SIT_MERCAD_NOMES).fillna("Não Informado")
df_cleaned['Sexo_Desc'] = df_cleaned['CS_SEXO'].map(SEXO_NOMES).fillna("Não Informado")
df_cleaned['Raca_Desc'] = df_cleaned['CS_RACA'].map(RACA_NOMES).fillna("Não Informado")
df_cleaned['Tipo_Acid_Desc'] = df_cleaned['TIPO_ACID'].map(TIPO_ACID_NOMES).fillna("Não Informado")

# CBO mapper helper
def map_cbo(code):
    if code == 'Não Informado' or not code:
        return "Não Informado"
    # Try CBO catalog first, then fallback, and finally format code
    return cbo_catalog.get(code, CBO_FALLBACK.get(code, f"CBO {code}"))

df_cleaned['CBO_Desc'] = df_cleaned['ID_OCUPA_N'].apply(map_cbo)

# CNAE mapper helper
def map_cnae(code):
    if code == 'Não Informado' or not code:
        return "Não Informado"
    return CNAE_NOMES.get(code, f"CNAE {code}")

df_cleaned['CNAE_Desc'] = df_cleaned['CNAE'].apply(map_cnae)


# ==========================================
# 5. CUSTOM STYLING (CSS)
# ==========================================
# Premium dark mode and glassmorphism styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"], .stApp {
        font-family: 'Outfit', sans-serif;
    }
    
    /* Transparent Background for elements */
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
        background-color: transparent;
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: rgba(255, 255, 255, 0.03);
        border-radius: 8px;
        padding: 0 24px;
        color: #94A3B8;
        font-weight: 600;
        border: 1px solid rgba(255, 255, 255, 0.05);
        transition: all 0.3s ease;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        color: #E2E8F0;
        background-color: rgba(255, 255, 255, 0.08);
        border-color: rgba(255, 255, 255, 0.1);
    }
    
    .stTabs [aria-selected="true"] {
        color: #38BDF8 !important;
        background-color: rgba(56, 189, 248, 0.1) !important;
        border-color: rgba(56, 189, 248, 0.3) !important;
    }
    
    /* Metrics Custom Glass Cards */
    .metric-card {
        padding: 24px;
        border-radius: 16px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.05) 0%, rgba(255, 255, 255, 0.02) 100%);
        backdrop-filter: blur(10px);
        margin-bottom: 20px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2);
        transition: transform 0.2s ease-in-out;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        border-color: rgba(255, 255, 255, 0.12);
    }
    .metric-value {
        font-size: 38px;
        font-weight: 700;
        line-height: 1.1;
        margin-bottom: 4px;
    }
    .metric-label {
        font-size: 14px;
        color: #94A3B8;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-weight: 600;
    }
    .metric-footer {
        font-size: 12px;
        margin-top: 8px;
        color: #38BDF8;
    }
</style>
""", unsafe_allow_html=True)


# ==========================================
# 6. SIDEBAR CONTROLS & FILTERING
# ==========================================
# Sidebar Header
st.sidebar.markdown("""
<div style="text-align: center; padding-bottom: 20px;">
    <h2 style="color: #38BDF8; margin-bottom: 5px; font-weight:700;">CEREST Cacoal/RO</h2>
    <p style="color: #94A3B8; font-size:14px; margin: 0;">Filtros de Análise Epidemiológica</p>
</div>
<hr style="border-color: rgba(255,255,255,0.08); margin-top:0;" />
""", unsafe_allow_html=True)

# Filter: Year (Ano)
if 'Ano_Notificacao' in df_cleaned.columns:
    all_anos = sorted(df_cleaned['Ano_Notificacao'].unique())
else:
    all_anos = []
    
selected_anos = st.sidebar.multiselect(
    "Selecione o Ano de Notificação:",
    options=all_anos,
    default=all_anos
)

# Filter 1: Municipalities
all_municipalities = sorted(df_cleaned['Municipio'].unique())
selected_municipalities = st.sidebar.multiselect(
    "Selecione os Municípios de Notificação:",
    options=all_municipalities,
    default=all_municipalities
)

# Filter 2: Employment Type (Situação de Mercado)
all_situations = sorted(df_cleaned['Sit_Mercad_Desc'].unique())
selected_situations = st.sidebar.multiselect(
    "Selecione os Vínculos Empregatícios:",
    options=all_situations,
    default=all_situations
)

# Apply filters
df_filtered = df_cleaned[
    (df_cleaned['Municipio'].isin(selected_municipalities)) & 
    (df_cleaned['Sit_Mercad_Desc'].isin(selected_situations)) &
    (df_cleaned['Ano_Notificacao'].isin(selected_anos) if 'Ano_Notificacao' in df_cleaned.columns else True)
]

# Sidebar Footer/Info
st.sidebar.markdown(f"""
<div style="margin-top: 50px; padding: 15px; border-radius: 8px; background-color: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05);">
    <p style="color: #94A3B8; font-size: 13px; margin-bottom: 5px;"><b>Dataset:</b> SINAN (Acidentes de Trabalho)</p>
    <p style="color: #94A3B8; font-size: 13px; margin-bottom: 5px;"><b>Período:</b> {', '.join(selected_anos) if selected_anos else 'Nenhum'}</p>
    <p style="color: #94A3B8; font-size: 13px; margin-bottom: 5px;"><b>Casos Filtrados:</b> {len(df_filtered)} / {len(df_cleaned)}</p>
</div>
""", unsafe_allow_html=True)


# ==========================================
# 7. MAIN DASHBOARD CONTENT
# ==========================================

# Main Header
st.markdown("""
<div style="background: linear-gradient(90deg, rgba(56, 189, 248, 0.1) 0%, rgba(0,0,0,0) 100%); padding: 20px; border-radius: 12px; border-left: 5px solid #38BDF8; margin-bottom: 25px;">
    <h1 style="margin: 0; color: #F8FAFC; font-weight: 700; font-size: 32px;">Acidentes de Trabalho Graves - CEREST Regional de Cacoal/RO</h1>
    <p style="margin: 5px 0 0 0; color: #94A3B8; font-size: 16px;">Painel de Monitoramento Epidemiológico do SINAN contendo os 14 municípios de abrangência</p>
</div>
""", unsafe_allow_html=True)

# Tabs definitions
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Visão Geral", "🛠️ Setorial", "👤 Persona", "📈 Perfil x Evolução", "📅 Comparativo Anual"])

# ==========================================
# TAB 1: VISÃO GERAL E METRICAS (KPIs)
# ==========================================
with tab1:
    
    # Row 1: KPI Cards
    # Case counts for Evolução
    total_cura = len(df_filtered[df_filtered['EVOLUCAO'] == '1'])
    total_parcial_temp = len(df_filtered[df_filtered['EVOLUCAO'] == '2'])
    total_parcial_perm = len(df_filtered[df_filtered['EVOLUCAO'] == '3'])
    total_total_perm = len(df_filtered[df_filtered['EVOLUCAO'] == '4'])
    total_obito = len(df_filtered[df_filtered['EVOLUCAO'] == '5'])
    total_obito_outras = len(df_filtered[df_filtered['EVOLUCAO'] == '6'])
    total_ignorado = len(df_filtered[df_filtered['EVOLUCAO'].isin(['9', 'Não Informado'])])
    total_cases = len(df_filtered)
    
    # First row of KPIs
    kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
    
    with kpi_col1:
        st.markdown(f"""
        <div class="metric-card" style="border-top: 4px solid #10B981;">
            <div class="metric-label">Cura</div>
            <div class="metric-value" style="color: #10B981;">{total_cura}</div>
            <div class="metric-footer">Recuperação completa</div>
        </div>
        """, unsafe_allow_html=True)
        
    with kpi_col2:
        st.markdown(f"""
        <div class="metric-card" style="border-top: 4px solid #0EA5E9;">
            <div class="metric-label">Incap. Parcial Temp</div>
            <div class="metric-value" style="color: #0EA5E9;">{total_parcial_temp}</div>
            <div class="metric-footer">Afastamento temporário</div>
        </div>
        """, unsafe_allow_html=True)
        
    with kpi_col3:
        st.markdown(f"""
        <div class="metric-card" style="border-top: 4px solid #F59E0B;">
            <div class="metric-label">Incap. Parcial Perm</div>
            <div class="metric-value" style="color: #F59E0B;">{total_parcial_perm}</div>
            <div class="metric-footer">Redução permanente</div>
        </div>
        """, unsafe_allow_html=True)
        
    with kpi_col4:
        st.markdown(f"""
        <div class="metric-card" style="border-top: 4px solid #EA580C;">
            <div class="metric-label">Incap. Total Perm</div>
            <div class="metric-value" style="color: #EA580C;">{total_total_perm}</div>
            <div class="metric-footer">Perda total da capacidade</div>
        </div>
        """, unsafe_allow_html=True)

    # Second row of KPIs
    kpi_col5, kpi_col6, kpi_col7, kpi_col8 = st.columns(4)
    
    with kpi_col5:
        st.markdown(f"""
        <div class="metric-card" style="border-top: 4px solid #EF4444;">
            <div class="metric-label">Óbito (Pelo Acidente)</div>
            <div class="metric-value" style="color: #EF4444;">{total_obito}</div>
            <div class="metric-footer">Desfecho letal</div>
        </div>
        """, unsafe_allow_html=True)
        
    with kpi_col6:
        st.markdown(f"""
        <div class="metric-card" style="border-top: 4px solid #D946EF;">
            <div class="metric-label">Óbito (Outras Causas)</div>
            <div class="metric-value" style="color: #D946EF;">{total_obito_outras}</div>
            <div class="metric-footer">Óbito não relacionado</div>
        </div>
        """, unsafe_allow_html=True)
        
    with kpi_col7:
        st.markdown(f"""
        <div class="metric-card" style="border-top: 4px solid #94A3B8;">
            <div class="metric-label">Ignorado / Branco</div>
            <div class="metric-value" style="color: #94A3B8;">{total_ignorado}</div>
            <div class="metric-footer">Sem informação evolutiva</div>
        </div>
        """, unsafe_allow_html=True)
        
    with kpi_col8:
        st.markdown(f"""
        <div class="metric-card" style="border-top: 4px solid #38BDF8;">
            <div class="metric-label">Total Geral Notificado</div>
            <div class="metric-value" style="color: #38BDF8;">{total_cases}</div>
            <div class="metric-footer">Acidentes registrados</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Row 2: Charts for Overview
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        # Chart 1: Ranking Geral de CBO
        st.markdown("<h3 style='color: #F8FAFC; font-weight:600; font-size:18px;'>Ranking Geral de Acidentes por Ocupação (CBO)</h3>", unsafe_allow_html=True)
        
        # Calculate CBO general counts
        cbo_counts = df_filtered['CBO_Desc'].value_counts().reset_index()
        cbo_counts.columns = ['Ocupação (CBO)', 'Volume Notificado']
        
        # Filter out "Não Informado" if necessary or keep it. Let's keep the top 10 valid ones.
        cbo_counts = cbo_counts[cbo_counts['Ocupação (CBO)'] != 'Não Informado'].head(10)
        
        if len(cbo_counts) > 0:
            fig_cbo_gen = px.bar(
                cbo_counts,
                x='Volume Notificado',
                y='Ocupação (CBO)',
                orientation='h',
                color='Volume Notificado',
                color_continuous_scale='Blues',
                labels={'Volume Notificado': 'Volume de Acidentes'},
                template='plotly_dark'
            )
            fig_cbo_gen.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font={'family': 'Outfit, sans-serif', 'color': '#E2E8F0'},
                xaxis={'gridcolor': 'rgba(255,255,255,0.05)', 'zeroline': False},
                yaxis={'gridcolor': 'rgba(255,255,255,0.05)', 'zeroline': False, 'autorange': 'reversed'},
                margin={'t': 10, 'b': 20, 'l': 10, 'r': 10},
                coloraxis_showscale=False,
                height=350
            )
            st.plotly_chart(fig_cbo_gen, use_container_width=True)
        else:
            st.info("Nenhum dado de CBO disponível com os filtros atuais.")

    with chart_col2:
        # Chart 2: Óbitos por Situação de Mercado
        st.markdown("<h3 style='color: #F8FAFC; font-weight:600; font-size:18px;'>Óbitos por Vínculo Empregatício (Situação no Mercado)</h3>", unsafe_allow_html=True)
        
        # Filter for deaths (EVOLUCAO == '5')
        deaths_df = df_filtered[df_filtered['EVOLUCAO'] == '5']
        
        if len(deaths_df) > 0:
            sit_deaths = deaths_df['Sit_Mercad_Desc'].value_counts().reset_index()
            sit_deaths.columns = ['Vínculo Empregatício', 'Óbitos']
            
            fig_sit_deaths = px.pie(
                sit_deaths,
                values='Óbitos',
                names='Vínculo Empregatício',
                color_discrete_sequence=px.colors.sequential.Reds_r,
                hole=0.4,
                template='plotly_dark'
            )
            fig_sit_deaths.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font={'family': 'Outfit, sans-serif', 'color': '#E2E8F0'},
                margin={'t': 10, 'b': 20, 'l': 10, 'r': 10},
                height=350,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=-0.2,
                    xanchor="center",
                    x=0.5
                )
            )
            st.plotly_chart(fig_sit_deaths, use_container_width=True)
        else:
            st.info("Nenhum óbito registrado para os filtros selecionados.")


# ==========================================
# TAB 2: ANALISE DETALHADA E SETORIAL
# ==========================================
with tab2:
    
    chart_col3, chart_col4 = st.columns(2)
    
    with chart_col3:
        # Chart 3: Ranking de CBO em Óbitos
        st.markdown("<h3 style='color: #F8FAFC; font-weight:600; font-size:18px;'>Ranking de Profissões (CBO) com mais Óbitos</h3>", unsafe_allow_html=True)
        
        # Filter deaths
        deaths_df = df_filtered[df_filtered['EVOLUCAO'] == '5']
        
        if len(deaths_df) > 0:
            cbo_deaths = deaths_df['CBO_Desc'].value_counts().reset_index()
            cbo_deaths.columns = ['Ocupação (CBO)', 'Óbitos']
            cbo_deaths = cbo_deaths[cbo_deaths['Ocupação (CBO)'] != 'Não Informado'].head(10)
            
            fig_cbo_deaths = px.bar(
                cbo_deaths,
                x='Óbitos',
                y='Ocupação (CBO)',
                orientation='h',
                color='Óbitos',
                color_continuous_scale='Reds',
                labels={'Óbitos': 'Número de Óbitos'},
                template='plotly_dark'
            )
            fig_cbo_deaths.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font={'family': 'Outfit, sans-serif', 'color': '#E2E8F0'},
                xaxis={'gridcolor': 'rgba(255,255,255,0.05)', 'zeroline': False, 'tickformat': ',d'},
                yaxis={'gridcolor': 'rgba(255,255,255,0.05)', 'zeroline': False, 'autorange': 'reversed'},
                margin={'t': 10, 'b': 20, 'l': 10, 'r': 10},
                coloraxis_showscale=False,
                height=350
            )
            st.plotly_chart(fig_cbo_deaths, use_container_width=True)
        else:
            st.info("Nenhum óbito registrado para os filtros selecionados.")
            
    with chart_col4:
        # Chart 4: Setores Econômicos (CNAE) com mais acidentes gerais
        st.markdown("<h3 style='color: #F8FAFC; font-weight:600; font-size:18px;'>Setores Econômicos (CNAE) com maior número de acidentes</h3>", unsafe_allow_html=True)
        
        # Calculate CNAE counts
        cnae_counts = df_filtered['CNAE_Desc'].value_counts().reset_index()
        cnae_counts.columns = ['Setor Econômico (CNAE)', 'Acidentes Registrados']
        
        # Remove "Não Informado" or show it. Let's filter out to show actual sectors.
        cnae_counts_valid = cnae_counts[cnae_counts['Setor Econômico (CNAE)'] != 'Não Informado'].head(10)
        
        if len(cnae_counts_valid) > 0:
            fig_cnae = px.bar(
                cnae_counts_valid,
                x='Acidentes Registrados',
                y='Setor Econômico (CNAE)',
                orientation='h',
                color='Acidentes Registrados',
                color_continuous_scale='Tealgrn',
                labels={'Acidentes Registrados': 'Volume de Acidentes'},
                template='plotly_dark'
            )
            fig_cnae.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font={'family': 'Outfit, sans-serif', 'color': '#E2E8F0'},
                xaxis={'gridcolor': 'rgba(255,255,255,0.05)', 'zeroline': False},
                yaxis={'gridcolor': 'rgba(255,255,255,0.05)', 'zeroline': False, 'autorange': 'reversed'},
                margin={'t': 10, 'b': 20, 'l': 10, 'r': 10},
                coloraxis_showscale=False,
                height=350
            )
            st.plotly_chart(fig_cnae, use_container_width=True)
        else:
            st.info("Nenhum dado setorial de CNAE disponível.")

    st.markdown("<hr style='border-color: rgba(255,255,255,0.08); margin: 30px 0 20px 0;' />", unsafe_allow_html=True)
    
    # Tabular Data Section
    st.markdown("<h3 style='color: #F8FAFC; font-weight:600; font-size:18px;'>Tabela Interativa - Detalhamento por Município e Evolução</h3>", unsafe_allow_html=True)
    st.markdown("<p style='color: #94A3B8; font-size:14px; margin-top:-10px; margin-bottom:15px;'>Visão analítica cruzando a localidade e o desfecho clínico do acidente de trabalho grave</p>", unsafe_allow_html=True)
    
    # Pivot/Groupby table of Municipality vs Evolucao
    if len(df_filtered) > 0:
        table_df = pd.crosstab(
            df_filtered['Municipio'], 
            df_filtered['Evolucao_Desc'], 
            margins=True, 
            margins_name='Total Geral'
        )
        
        # Reorder columns to put "Total Geral" at the end if necessary, and ensure columns list is readable
        st.dataframe(table_df, use_container_width=True)
    else:
        st.info("Nenhum dado disponível para compor a tabela comparativa.")

# ==========================================
# TAB 3: ANÁLISE POR MUNICÍPIO (PERSONA)
# ==========================================
with tab3:
    st.markdown("<h3 style='color: #F8FAFC; font-weight:600; font-size:18px;'>Perfil Predominante do Trabalhador Atingido (Persona)</h3>", unsafe_allow_html=True)
    st.markdown("<p style='color: #94A3B8; font-size:14px; margin-top:-10px; margin-bottom:20px;'>Selecione um município para gerar o perfil característico das vítimas de acidente de trabalho grave baseando-se nos dados mais frequentes (Moda).</p>", unsafe_allow_html=True)
    
    # Municipality selector for Persona (independent of sidebar)
    persona_municipio = st.selectbox(
        "Selecione o Município para traçar o perfil:",
        options=all_municipalities,
        key="persona_mun"
    )
    
    # Filter dataset strictly for the chosen municipality from the original cleaned df
    df_persona = df_cleaned[df_cleaned['Municipio'] == persona_municipio].copy()
    
    if len(df_persona) == 0:
        st.info("Nenhum dado encontrado para o município selecionado.")
    else:
        # Calculate Mode (most frequent)
        def get_mode(series, fallback="Não Informado"):
            valid = series[series != "Não Informado"].dropna()
            if len(valid) == 0:
                return fallback
            return valid.mode().iloc[0]
            
        persona_sexo = get_mode(df_persona['Sexo_Desc'])
        persona_raca = get_mode(df_persona['Raca_Desc'])
        persona_tipo_acid = get_mode(df_persona['Tipo_Acid_Desc'])
        persona_evolucao = get_mode(df_persona['Evolucao_Desc'])
        persona_sit = get_mode(df_persona['Sit_Mercad_Desc'])
        persona_cbo = get_mode(df_persona['CBO_Desc'])
        persona_cnae = get_mode(df_persona['CNAE_Desc'])
        
        # Calculate Age average
        if df_persona['Idade_Anos'].notna().sum() > 0:
            idade_media = int(df_persona['Idade_Anos'].mean())
            faixa_etaria = f"média de {idade_media} anos"
        else:
            faixa_etaria = "idade não identificada"
            
        # Text phrasing based on gender
        artigo = "O" if persona_sexo == "Masculino" else ("A" if persona_sexo == "Feminino" else "O(a)")
        trabalhador = "trabalhador" if persona_sexo == "Masculino" else ("trabalhadora" if persona_sexo == "Feminino" else "trabalhador(a)")
        
        # Color coding for Outcome (Evolucao)
        cor_evolucao = "#EF4444" if "Óbito" in persona_evolucao or "Total" in persona_evolucao else ("#F59E0B" if "Parcial" in persona_evolucao else "#10B981")
        
        # Determine avatar image based on demographics and occupation
        avatar_file = "assets/man_brown.png" # default
        
        cbo_lower = str(persona_cbo).lower()
        if "rural" in cbo_lower or "agricultura" in cbo_lower or "agropecuária" in cbo_lower:
            avatar_file = "assets/farmer_brown.png"
        elif persona_sexo == "Masculino" and persona_raca in ["Branca", "Amarela"]:
            avatar_file = "assets/man_white.png"
        elif persona_sexo == "Feminino" and persona_raca in ["Branca", "Amarela"]:
            avatar_file = "assets/woman_white.png"
        elif persona_sexo == "Feminino":
            avatar_file = "assets/woman_brown.png"

        html_persona = f"""
<div style="padding: 30px; border-radius: 16px; background: linear-gradient(135deg, rgba(56, 189, 248, 0.05) 0%, rgba(255, 255, 255, 0.02) 100%); border: 1px solid rgba(56, 189, 248, 0.2); margin-bottom: 25px; box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2);">
    <div style="display:flex; align-items:center; margin-bottom: 15px;">
        <div style="background-color: rgba(56, 189, 248, 0.2); padding: 10px; border-radius: 50%; margin-right: 15px;">
            <span style="font-size: 24px;">👤</span>
        </div>
        <h2 style="color: #38BDF8; margin: 0;">Persona de {persona_municipio}</h2>
    </div>
    <p style="font-size: 18px; color: var(--text-color); line-height: 1.6; margin-top: 10px;">
        {artigo} {trabalhador} mais atingido por acidentes graves nesta localidade é tipicamente do sexo <strong style="color: var(--text-color); font-weight: 800;">{persona_sexo}</strong>, raça/cor <strong style="color: var(--text-color); font-weight: 800;">{persona_raca}</strong> e possui <strong style="color: var(--text-color); font-weight: 800;">{faixa_etaria}</strong>.
    </p>
    <p style="font-size: 18px; color: var(--text-color); line-height: 1.6;">
        Trabalha na maior parte das vezes como <strong style="color: #38BDF8;">{persona_cbo}</strong> atuando no setor de <strong style="color: #38BDF8;">{persona_cnae}</strong>, com o vínculo de <strong style="color: #38BDF8;">{persona_sit}</strong>.
    </p>
    <p style="font-size: 18px; color: var(--text-color); line-height: 1.6;">
        A característica dos acidentes indica que é predominantemente um Acidente <strong style="color: var(--text-color); font-weight: 800;">{persona_tipo_acid}</strong>. A evolução clínica que mais se repete para este perfil é: <strong style="color: white; background-color: {cor_evolucao}; padding: 2px 8px; border-radius: 4px;">{persona_evolucao}</strong>.
    </p>
</div>
"""
        col_av, col_tx = st.columns([1, 2.5])
        with col_av:
            try:
                st.image(avatar_file, use_container_width=True)
            except:
                pass
        with col_tx:
            st.markdown(html_persona, unsafe_allow_html=True)
        
        st.markdown("<hr style='border-color: rgba(255,255,255,0.08); margin: 20px 0;' />", unsafe_allow_html=True)
        
        # Secondary charts to complement Tab 3
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            st.markdown(f"<h4 style='color: #F8FAFC; font-weight:600;'>Distribuição de Acidentes por Gênero ({persona_municipio})</h4>", unsafe_allow_html=True)
            gen_counts = df_persona['Sexo_Desc'].value_counts().reset_index()
            gen_counts.columns = ['Gênero', 'Quantidade']
            gen_counts = gen_counts[gen_counts['Gênero'] != 'Não Informado']
            if len(gen_counts) > 0:
                fig_gen = px.pie(gen_counts, values='Quantidade', names='Gênero', hole=0.5, template='plotly_dark', color_discrete_sequence=['#38BDF8', '#F472B6'])
                fig_gen.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin={'t':10, 'b':10, 'l':0, 'r':0}, height=250)
                st.plotly_chart(fig_gen, use_container_width=True)
            else:
                st.info("Sem dados de gênero.")
                
        with col_p2:
            st.markdown(f"<h4 style='color: #F8FAFC; font-weight:600;'>Tipos de Acidente mais Comuns ({persona_municipio})</h4>", unsafe_allow_html=True)
            acid_counts = df_persona['Tipo_Acid_Desc'].value_counts().reset_index()
            acid_counts.columns = ['Tipo', 'Quantidade']
            acid_counts = acid_counts[acid_counts['Tipo'] != 'Não Informado']
            if len(acid_counts) > 0:
                fig_acid = px.bar(acid_counts, x='Quantidade', y='Tipo', orientation='h', template='plotly_dark', color_discrete_sequence=['#F59E0B'])
                fig_acid.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin={'t':10, 'b':10, 'l':0, 'r':0}, height=250, yaxis={'autorange':'reversed'})
                st.plotly_chart(fig_acid, use_container_width=True)
            else:
                st.info("Sem dados de tipo de acidente.")

# ==========================================
# TAB 4: CRUZAMENTO DE PERFIL POR EVOLUÇÃO
# ==========================================
with tab4:
    st.markdown("<h3 style='color: #F8FAFC; font-weight:600; font-size:18px;'>Análise Geral de Vínculo e Ocupação</h3>", unsafe_allow_html=True)
    st.markdown("<p style='color: #94A3B8; font-size:14px; margin-top:-10px; margin-bottom:20px;'>Quais situações de mercado e ocupações registraram mais acidentes no total.</p>", unsafe_allow_html=True)
    
    col_geral1, col_geral2 = st.columns(2)
    
    with col_geral1:
        st.markdown("<h4 style='color: #38BDF8; font-weight:600; font-size:16px;'>Top Situação no Mercado de Trabalho (Geral)</h4>", unsafe_allow_html=True)
        top_sit_geral = df_filtered['Sit_Mercad_Desc'].value_counts().reset_index()
        top_sit_geral.columns = ['Vínculo Empregatício', 'Total de Acidentes']
        top_sit_geral = top_sit_geral[top_sit_geral['Vínculo Empregatício'] != 'Não Informado']
        st.dataframe(top_sit_geral, use_container_width=True, hide_index=True)

    with col_geral2:
        st.markdown("<h4 style='color: #38BDF8; font-weight:600; font-size:16px;'>Top Ocupações CBO (Geral)</h4>", unsafe_allow_html=True)
        top_cbo_geral = df_filtered['CBO_Desc'].value_counts().reset_index()
        top_cbo_geral.columns = ['Ocupação (CBO)', 'Total de Acidentes']
        top_cbo_geral = top_cbo_geral[top_cbo_geral['Ocupação (CBO)'] != 'Não Informado']
        st.dataframe(top_cbo_geral, use_container_width=True, hide_index=True)

    st.markdown("<hr style='border-color: rgba(255,255,255,0.08); margin: 30px 0 20px 0;' />", unsafe_allow_html=True)
    
    st.markdown("<h3 style='color: #F8FAFC; font-weight:600; font-size:18px;'>Análise Específica por Evolução do Caso</h3>", unsafe_allow_html=True)
    st.markdown("<p style='color: #94A3B8; font-size:14px; margin-top:-10px; margin-bottom:20px;'>Selecione um tipo de evolução clínica para descobrir quais vínculos e ocupações mais registraram esse desfecho.</p>", unsafe_allow_html=True)
    
    todas_evolucoes = sorted([ev for ev in df_filtered['Evolucao_Desc'].unique() if ev != 'Não Informado'])
    if len(todas_evolucoes) == 0:
        st.info("Nenhuma evolução clínica com informação válida para os filtros atuais.")
    else:
        evolucao_selecionada = st.selectbox("Selecione o tipo de Evolução:", options=todas_evolucoes, key="select_evolucao")
        
        df_evol_filtrado = df_filtered[df_filtered['Evolucao_Desc'] == evolucao_selecionada]
        
        col_esp1, col_esp2 = st.columns(2)
        
        with col_esp1:
            st.markdown(f"<h4 style='color: #10B981; font-weight:600; font-size:16px;'>Vínculo Empregatício com mais '{evolucao_selecionada}'</h4>", unsafe_allow_html=True)
            top_sit_esp = df_evol_filtrado['Sit_Mercad_Desc'].value_counts().reset_index()
            top_sit_esp.columns = ['Vínculo Empregatício', f'Total de casos']
            top_sit_esp = top_sit_esp[top_sit_esp['Vínculo Empregatício'] != 'Não Informado']
            if len(top_sit_esp) > 0:
                st.dataframe(top_sit_esp, use_container_width=True, hide_index=True)
            else:
                st.info("Sem dados informados.")
                
        with col_esp2:
            st.markdown(f"<h4 style='color: #10B981; font-weight:600; font-size:16px;'>Ocupação CBO com mais '{evolucao_selecionada}'</h4>", unsafe_allow_html=True)
            top_cbo_esp = df_evol_filtrado['CBO_Desc'].value_counts().reset_index()
            top_cbo_esp.columns = ['Ocupação (CBO)', f'Total de casos']
            top_cbo_esp = top_cbo_esp[top_cbo_esp['Ocupação (CBO)'] != 'Não Informado']
            if len(top_cbo_esp) > 0:
                st.dataframe(top_cbo_esp, use_container_width=True, hide_index=True)
            else:
                st.info("Sem dados informados.")

# ==========================================
# TAB 5: COMPARATIVO ANUAL (2024-2026)
# ==========================================
with tab5:
    st.markdown("<h3 style='color: #F8FAFC; font-weight:600; font-size:18px;'>Evolução Histórica</h3>", unsafe_allow_html=True)
    st.markdown("<p style='color: #94A3B8; font-size:14px; margin-top:-10px; margin-bottom:20px;'>Comparativo de volume de acidentes e perfil entre os anos selecionados.</p>", unsafe_allow_html=True)
    
    if len(df_filtered) > 0 and 'Ano_Notificacao' in df_filtered.columns:
        # Chart 1: Total by Year
        col_hist1, col_hist2 = st.columns(2)
        
        with col_hist1:
            st.markdown("<h4 style='color: #38BDF8; font-weight:600; font-size:16px;'>Volume Total por Ano</h4>", unsafe_allow_html=True)
            vol_ano = df_filtered['Ano_Notificacao'].value_counts().reset_index()
            vol_ano.columns = ['Ano', 'Total']
            vol_ano = vol_ano.sort_values('Ano')
            
            fig_vol = px.line(vol_ano, x='Ano', y='Total', markers=True, template='plotly_dark', color_discrete_sequence=['#38BDF8'])
            fig_vol.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin={'t':10, 'b':10, 'l':0, 'r':0}, height=280)
            fig_vol.update_xaxes(type='category')
            st.plotly_chart(fig_vol, use_container_width=True)
            
        with col_hist2:
            st.markdown("<h4 style='color: #F59E0B; font-weight:600; font-size:16px;'>Top 5 Ocupações por Ano</h4>", unsafe_allow_html=True)
            # Group by Ano and CBO
            top_cbo_ano = df_filtered[df_filtered['CBO_Desc'] != 'Não Informado'].groupby(['Ano_Notificacao', 'CBO_Desc']).size().reset_index(name='Total')
            # Get Top 5 overall to filter
            top_cbos_overall = df_filtered[df_filtered['CBO_Desc'] != 'Não Informado']['CBO_Desc'].value_counts().head(5).index.tolist()
            top_cbo_ano_filtered = top_cbo_ano[top_cbo_ano['CBO_Desc'].isin(top_cbos_overall)]
            
            fig_cbo_ano = px.bar(top_cbo_ano_filtered, x='Ano_Notificacao', y='Total', color='CBO_Desc', barmode='group', template='plotly_dark')
            fig_cbo_ano.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin={'t':10, 'b':10, 'l':0, 'r':0}, height=280, legend=dict(orientation="h", y=-0.2))
            fig_cbo_ano.update_xaxes(type='category')
            st.plotly_chart(fig_cbo_ano, use_container_width=True)
            
        st.markdown("<hr style='border-color: rgba(255,255,255,0.08); margin: 20px 0;' />", unsafe_allow_html=True)
        
        # Chart 3: Vínculo by Year
        st.markdown("<h4 style='color: #10B981; font-weight:600; font-size:16px;'>Evolução do Vínculo Empregatício (Top 5)</h4>", unsafe_allow_html=True)
        sit_ano = df_filtered[df_filtered['Sit_Mercad_Desc'] != 'Não Informado'].groupby(['Ano_Notificacao', 'Sit_Mercad_Desc']).size().reset_index(name='Total')
        
        # Filter to top 5 Vínculos overall
        top_sit_overall = df_filtered[df_filtered['Sit_Mercad_Desc'] != 'Não Informado']['Sit_Mercad_Desc'].value_counts().head(5).index.tolist()
        sit_ano_filtered = sit_ano[sit_ano['Sit_Mercad_Desc'].isin(top_sit_overall)]
        
        fig_sit_ano = px.bar(sit_ano_filtered, x='Ano_Notificacao', y='Total', color='Sit_Mercad_Desc', barmode='group', template='plotly_dark')
        fig_sit_ano.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin={'t':10, 'b':10, 'l':0, 'r':0}, height=300, legend=dict(orientation="h", y=-0.2))
        fig_sit_ano.update_xaxes(type='category')
        st.plotly_chart(fig_sit_ano, use_container_width=True)
    else:
        st.info("Dados insuficientes para análise histórica.")
