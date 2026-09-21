# CEREST Cacoal - Painel de Acidentes de Trabalho Graves

Este projeto é um painel de monitoramento epidemiológico desenvolvido em **Python** utilizando **Streamlit**. O sistema processa, analisa e exibe dados sobre acidentes de trabalho graves ocorridos nos 14 municípios de abrangência do CEREST Regional de Cacoal/RO (Região do Café e Zona da Mata).

## 🚀 Funcionalidades

- **Processamento de Dados do SINAN:** Lê arquivos proprietários do DATASUS (`.dbc`) diretamente, fazendo a descompressão para o formato padrão via Pandas de forma otimizada.
- **Painel Interativo de Indicadores (KPIs):** Exibe métricas de evolução dos casos, como alta, incapacidades parciais/totais, óbitos relacionados ou não ao acidente, entre outros.
- **Gráficos Setoriais e Profissionais:**
  - Ranking Geral de Acidentes por Ocupação (CBO)
  - Distribuição de Óbitos por Vínculo Empregatício
  - Setores Econômicos (CNAE) com maiores índices de acidentes
- **Tabelas Interativas e Relatórios:** Comparativo anual e evolução clínica filtrada por município.
- **Identificação da Persona:** Gera o perfil sociodemográfico predominante (moda) da vítima de acidentes de trabalho por município.

## 🛠️ Tecnologias Utilizadas

- [Python](https://www.python.org/) 
- [Streamlit](https://streamlit.io/) - Framework para construção do Dashboard web interativo
- [Pandas](https://pandas.pydata.org/) - Manipulação e limpeza dos dados
- [Plotly](https://plotly.com/python/) - Construção dos gráficos e tabelas
- [PyReaddbc / DBFRead](https://pypi.org/project/pyreaddbc/) - Leitura dos bancos de dados (.dbc e .dbf) nativos do DATASUS

## 📦 Como Instalar e Executar

1. Clone o repositório para o seu ambiente local:
   ```bash
   git clone https://github.com/Cesajulio/Analise-Cerest.git
   ```

2. Crie e ative um ambiente virtual (opcional, porém recomendado):
   ```bash
   python -m venv venv
   # No Windows:
   venv\Scripts\activate
   # No Linux/Mac:
   source venv/bin/activate
   ```

3. Instale as dependências listadas:
   ```bash
   pip install -r requirements.txt
   ```
   *(Caso não exista o arquivo requirements.txt, instale as bibliotecas principais: `pip install pandas streamlit plotly pyreaddbc dbfread pysus`)*

4. **Bases de Dados:**
   Certifique-se de baixar os arquivos de dados do SINAN com extensão `.dbc` (ex: `ACGRBR23.dbc`, `ACGRBR24.dbc`) para o diretório raiz do projeto. Por razões de tamanho e proteção de dados, esses arquivos **não são versionados** no repositório.

5. Execute a aplicação Streamlit:
   ```bash
   streamlit run app.py
   ```

6. O aplicativo abrirá automaticamente no seu navegador padrão (geralmente na porta `8501`).

## 📊 Abrangência Geográfica

Os dados contemplam a análise regional focada nas seguintes localidades:
- **Região do Café:** Cacoal, Espigão D'Oeste, Ministro Andreazza, Pimenta Bueno, Primavera de Rondônia, São Felipe D'Oeste.
- **Região da Zona da Mata:** Alta Floresta D'Oeste, Alto Alegre dos Parecis, Castanheiras, Nova Brasilândia D'Oeste, Novo Horizonte do Oeste, Parecis, Rolim de Moura, Santa Luzia D'Oeste.
