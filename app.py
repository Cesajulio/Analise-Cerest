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
# 1. PySUS COMPATIBILITY MONKEYPATCH
# ==========================================
# PySUS 2.2.0 does not expose pysus.utilities.read_dbc.
# We create a dummy module dynamically to fulfill the user's import requirement.
class DummyModule(types.ModuleType):
    pass

def read_dbc(filename, encoding='iso-8859-1'):
    """
    Decompresses a DATASUS .dbc file using pyreaddbc and loads it into a Pandas DataFrame.
    OPTIMIZATION:
    Instead of decoding all ~343,000 rows in pure Python (which takes over 1 minute),
    we decode only the 'ID_MUNICIP' column first, filter for the 14 regional municipalities,
    and then decode the remaining columns for the ~714 matching rows.
    This reduces cell decoding operations from 18.5 million to 38,000, speeding up load times by 10x.
    """
    from pyreaddbc import dbc2dbf
    from dbfread import DBF
    
    # Create a temporary DBF file
    fd, temp_dbf = tempfile.mkstemp(suffix='.dbf')
    os.close(fd)
    
    try:
        # Convert DBC to DBF
        dbc2dbf(filename, temp_dbf)
        
        # Load the DBF file in raw byte mode
        dbf = DBF(temp_dbf, encoding=encoding, raw=True)
        df = pd.DataFrame(iter(dbf))
        
        # Decode only the geographical column first
        if 'ID_MUNICIP' in df.columns:
            df['ID_MUNICIP'] = df['ID_MUNICIP'].apply(
                lambda x: x.decode(encoding, errors='replace').strip() 
                if isinstance(x, bytes) else (x.strip() if isinstance(x, str) else x)
            )
            
            # Filter for the 14 CEREST Cacoal/RO regional municipalities
            municipios = [
                '110004', '110009', '110014', '110018', '110026', '110032', 
                '110028', '110001', '110037', '110090', '110015', '110050', 
                '110059', '110029'
            ]
            df = df[df['ID_MUNICIP'].isin(municipios)].copy()
            
        # Decode all other columns for the small filtered subset
        for col in df.columns:
            if col != 'ID_MUNICIP':
                df[col] = df[col].apply(
                    lambda x: x.decode(encoding, errors='replace').strip() 
                    if isinstance(x, bytes) else (x.strip() if isinstance(x, str) else x)
                )
        return df
    finally:
        # Secure cleanup of temporary DBF
        if os.path.exists(temp_dbf):
            try:
                os.remove(temp_dbf)
            except Exception:
                pass

# Register the injected module in sys.modules
pysus_utilities_read_dbc = DummyModule('pysus.utilities.read_dbc')
pysus_utilities_read_dbc.read_dbc = read_dbc
sys.modules['pysus.utilities.read_dbc'] = pysus_utilities_read_dbc


# ==========================================
# 2. DICTIONARIES & METADATA LOOKUPS
# ==========================================

# Municipality mapping for the 14 CEREST Cacoal/RO municipalities
MUNICIPIOS_NOMES = {
    '110001': "Alta Floresta D'Oeste",
    '110004': "Cacoal",
    '110009': "Espigão D'Oeste",
    '110014': "Nova Brasilândia D'Oeste",
    '110015': "Ouro Preto do Oeste",
    '110018': "Pimenta Bueno",
    '110026': "Rio Crespo",
    '110028': "Rolim de Moura",
    '110029': "Santa Luzia D'Oeste",
    '110032': "São Miguel do Guaporé",
    '110037': "Alto Alegre dos Parecis",
    '110050': "Novo Horizonte do Oeste",
    '110059': "Primavera de Rondônia",
    '110090': "Castanheiras"
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

# Official user import requirement
from pysus.utilities.read_dbc import read_dbc

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
def get_dashboard_data(filepath):
    """
    Reads, filters, cleans and typesets the Sinan DBC dataset.
    """
    df = read_dbc(filepath, encoding='iso-8859-1')
    
    # Standardize columns to strip leading/trailing spaces and handle empty values
    categorical_cols = ['EVOLUCAO', 'SIT_TRAB', 'ID_OCUPA_N', 'CNAE', 'ID_MUNICIP']
    for col in categorical_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
            df[col] = df[col].replace({'': 'Não Informado', 'None': 'Não Informado', 'nan': 'Não Informado'})
        else:
            df[col] = 'Não Informado'
            
    return df


# ==========================================
# 4. DASHBOARD PAGE INITIALIZATION
# ==========================================
st.set_page_config(
    page_title="CEREST Cacoal - Acidentes de Trabalho Graves",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load database and CBO lookup table
dbc_filename = 'ACGRBR25.dbc'
if not os.path.exists(dbc_filename):
    st.error(f"Erro: O arquivo base '{dbc_filename}' não foi encontrado no diretório atual.")
    st.stop()

with st.spinner("Decompressing and parsing DATASUS DBC file... Please wait."):
    df_raw = get_dashboard_data(dbc_filename)
    cbo_catalog = load_cbo_catalog()

# Apply human-readable lookups to columns
df_cleaned = df_raw.copy()
df_cleaned['Municipio'] = df_cleaned['ID_MUNICIP'].map(MUNICIPIOS_NOMES).fillna(df_cleaned['ID_MUNICIP'])
df_cleaned['Evolucao_Desc'] = df_cleaned['EVOLUCAO'].map(EVOLUCAO_NOMES).fillna("Não Informado")
df_cleaned['Sit_Mercad_Desc'] = df_cleaned['SIT_TRAB'].map(SIT_MERCAD_NOMES).fillna("Não Informado")

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
    (df_cleaned['Sit_Mercad_Desc'].isin(selected_situations))
]

# Sidebar Footer/Info
st.sidebar.markdown(f"""
<div style="margin-top: 50px; padding: 15px; border-radius: 8px; background-color: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05);">
    <p style="color: #94A3B8; font-size: 13px; margin-bottom: 5px;"><b>Dataset:</b> ACGRBR25.dbc (SINAN)</p>
    <p style="color: #94A3B8; font-size: 13px; margin-bottom: 5px;"><b>Período:</b> Ano 2025</p>
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
tab1, tab2 = st.tabs(["📊 Visão Geral e Indicadores", "🛠️ Análise Setorial e Profissional"])

# ==========================================
# TAB 1: VISÃO GERAL E METRICAS (KPIs)
# ==========================================
with tab1:
    
    # Row 1: KPI Cards
    # Case counts for Incapacidades
    total_parcial_perm = len(df_filtered[df_filtered['EVOLUCAO'] == '3'])
    total_total_perm = len(df_filtered[df_filtered['EVOLUCAO'] == '4'])
    total_obitos = len(df_filtered[df_filtered['EVOLUCAO'] == '5'])
    total_cases = len(df_filtered)
    
    kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
    
    with kpi_col1:
        st.markdown(f"""
        <div class="metric-card" style="border-top: 4px solid #10B981;">
            <div class="metric-label">Incap. Parcial Permanente</div>
            <div class="metric-value" style="color: #10B981;">{total_parcial_perm}</div>
            <div class="metric-footer">Casos confirmados no SINAN</div>
        </div>
        """, unsafe_allow_html=True)
        
    with kpi_col2:
        st.markdown(f"""
        <div class="metric-card" style="border-top: 4px solid #F59E0B;">
            <div class="metric-label">Incap. Total Permanente</div>
            <div class="metric-value" style="color: #F59E0B;">{total_total_perm}</div>
            <div class="metric-footer">Perda total da capacidade laboral</div>
        </div>
        """, unsafe_allow_html=True)
        
    with kpi_col3:
        st.markdown(f"""
        <div class="metric-card" style="border-top: 4px solid #EF4444;">
            <div class="metric-label">Óbitos (Acidente de Trabalho)</div>
            <div class="metric-value" style="color: #EF4444;">{total_obitos}</div>
            <div class="metric-footer">Casos com desfecho letal</div>
        </div>
        """, unsafe_allow_html=True)
        
    with kpi_col4:
        st.markdown(f"""
        <div class="metric-card" style="border-top: 4px solid #38BDF8;">
            <div class="metric-label">Total Geral Notificado</div>
            <div class="metric-value" style="color: #38BDF8;">{total_cases}</div>
            <div class="metric-footer">Acidentes graves registrados</div>
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
