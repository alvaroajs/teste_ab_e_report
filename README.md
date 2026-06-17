# Pipeline de Análise de Testes A/B — Plataforma de Cashback

> Motor estatístico completo para processar dados de Testes A/B de parceiros de cashback, com geração de gráficos de séries temporais, exportação de relatórios em CSV/Excel e, opcionalmente, criação de **relatórios executivos em PDF** escritos por IA via Google Gemini.

---

## ⚡ Interface Web Interativa (Streamlit)

O projeto conta com uma interface gráfica moderna e amigável desenvolvida em **Streamlit**. Ela permite fazer upload dos CSVs de parceiros diretamente no seu navegador, acompanhar o progresso das etapas em tempo real e baixar os arquivos compilados (PDFs gerados pela IA, CSVs de estatísticas e gráficos) sem precisar interagir com o terminal.

### 🌐 Acesse a Aplicação Online
A versão implantada e pronta para uso em produção está disponível em:  
**👉 [https://reportt.streamlit.app/](https://reportt.streamlit.app/)**

---

## O que esse projeto faz?

O pipeline funciona em duas etapas independentes:

### 1. Análise Estatística (sempre executada)

Para cada arquivo CSV de parceiro encontrado na pasta `datasets/`, o pipeline:

1. **Lê e limpa os dados** — converte valores monetários em BRL, remove linhas inválidas, detecta inconsistências e gera alertas.
2. **Calcula estatísticas descritivas** — média, mediana, desvio padrão, quartis, skewness, kurtosis e mais.
3. **Executa testes de hipótese** — Teste T de Welch, Mann-Whitney U, Shapiro-Wilk, Cohen's d e Intervalo de Confiança de 95%.
4. **Gera gráficos de séries temporais** — evolução das métricas principais (lucro, vendas, compradores, ROI) ao longo do tempo, separadas por grupo. Também gera um heatmap de p-values.
5. **Exporta os resultados** — CSVs por parceiro, JSON completo com todos os dados e uma planilha Excel consolidada com todos os parceiros.

### 2. Relatório Executivo com IA (opcional, requer chave Gemini)

Quando a flag `--gemini` é usada, o pipeline envia os resultados da análise para o Google Gemini e recebe um **relatório executivo completo em PDF**, com narrativa profissional, interpretação dos testes estatísticos e os gráficos embutidos diretamente no documento.

---

## Estrutura do Projeto

```
Teste_A_B/
│
├── datasets/                       ← Coloque seus CSVs aqui
│
├── outputs/                        ← CSVs e JSONs gerados por parceiro
│   ├── parceiro_a_estatisticas_descritivas.csv
│   ├── parceiro_a_testes_hipotese.csv
│   └── parceiro_a_resumo_completo.json
│
├── reports/                        ← Relatórios consolidados e PDFs
│   ├── consolidado_descritivo.csv
│   ├── consolidado_hipoteses.csv
│   ├── consolidado_resumo.xlsx
│   └── gemini/
│       └── relatorio_executivo_parceiro_a.pdf
│
├── charts/                         ← Gráficos PNG gerados
│   ├── parceiro_a_linha_lucro.png
│   ├── parceiro_a_linha_vendas_totais.png
│   └── parceiro_a_heatmap_pvalues.png
│
├── logs/
│   └── pipeline.log
│
├── prompts/
│   └── prompt_gemini.md            ← Template do prompt enviado ao Gemini
│
├── src/
│   ├── analysis.py                 ← Pré-processamento e limpeza
│   ├── statistics.py               ← Motor estatístico (descritiva + inferência)
│   ├── visualizations.py           ← Gráficos de série temporal e heatmap
│   ├── reporting.py                ← Exportação CSV + JSON
│   ├── sheets.py                   ← Consolidação cross-parceiro + Excel
│   ├── gemini_report.py            ← Geração de PDFs via Google Gemini
│   └── main.py                     ← Orquestrador principal
│
├── config.py                       ← Configurações centrais
├── .env.example                    ← Modelo do arquivo de variáveis de ambiente
├── .env                            ← Suas credenciais reais (NÃO commitar!)
├── requirements.txt
└── README.md
```

---

## Instalação

### Pré-requisitos
- Python 3.10 ou superior

### 1. Clone o repositório

```bash
git clone https://github.com/alvaroajs/teste_ab_e_report.git
cd teste_ab_e_report
```

### 2. Instalação com uma única linha (Recomendado)

Crie o ambiente virtual, ative e instale todas as dependências rodando apenas um comando:

**Para Linux e macOS:**
```bash
python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
```

**Para Windows (Prompt de Comando):**
```cmd
python3 -m venv venv && venv\Scripts\activate && pip install -r requirements.txt
```

> **Nota:** Após a execução, o ambiente virtual (`venv`) já estará ativado no seu terminal.

---

## Como Usar

### Rodar a análise completa (sem IA)

Processa todos os CSVs da pasta `datasets/` e gera os outputs estatísticos:

```bash
python3 src/main.py
```

### Rodar apenas um arquivo específico

```bash
python3 src/main.py --file datasets/dataset_01_parceiroA.csv
```

### Rodar com geração de relatório PDF pelo Gemini

```bash
python3 src/main.py --gemini
```

> **Atenção:** para usar esta opção, você precisa configurar sua chave de API do Google Gemini. Veja a seção abaixo.

### Outras opções

```bash
# Processar CSVs de uma pasta customizada
python3 src/main.py --dir /caminho/para/seus/dados

# Ativar logs detalhados
python3 src/main.py --log DEBUG

# Usar o gerador de relatórios de forma standalone
python3 src/gemini_report.py --all
python3 src/gemini_report.py --json outputs/parceiro_a_resumo_completo.json
```

### Rodar a interface web interativa (Streamlit) localmente

Para rodar a interface gráfica localmente no seu computador, execute o comando:

```bash
streamlit run app.py
```

O Streamlit irá carregar o aplicativo em segundo plano e abrir a página automaticamente no seu navegador padrão no endereço `http://localhost:8501`. Nela você pode fazer o upload dos CSVs de parceiros, visualizar gráficos interativos e fazer o download de todos os relatórios gerados de forma visual.

---

## Configurando a API do Google Gemini

O relatório executivo em PDF é gerado pelo **Google Gemini 2.5 Flash** via API. O uso é **gratuito** dentro dos limites da cota do Google AI Studio.

### Passo 1 — Obtenha sua chave de API

1. Acesse [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Clique em **"Create API key in new project"** para criar uma chave vinculada a um projeto novo (isso garante que você terá cota gratuita disponível)
3. Copie a chave gerada — ela terá o formato `AIzaSy...` ou similar

> **Importante:** Crie sempre uma chave em um **projeto novo**. Chaves de projetos antigos podem ter cota zerada ou configurações diferentes.

### Passo 2 — Configure o arquivo `.env`

Na raiz do projeto existe um arquivo `.env.example` com o formato esperado:

```env
# Copie este arquivo para .env e preencha com sua chave real:
#   cp .env.example .env

# ─── Google Gemini API ─────────────────────────────────────────
GEMINI_API_KEY=sua_chave_aqui

# ─── (Opcional) Modelo padrão ──────────────────────────────────
GEMINI_MODEL=gemini-2.5-flash
```

Crie seu próprio `.env` a partir do exemplo:

```bash
cp .env.example .env
```

Abra o arquivo `.env` e substitua `sua_chave_aqui` pela chave que você copiou:

```env
GEMINI_API_KEY=AIzaSyAbCdEfGhIjKlMnOpQrSt...
```

### Passo 3 — Pronto!

O arquivo `.env` é carregado automaticamente pelo pipeline. Ele está no `.gitignore` e **nunca será commitado** — suas credenciais ficam apenas na sua máquina.

```bash
# Agora você pode rodar localmente com suporte ao Gemini:
python3 src/main.py --gemini
```

### Passo 4 — Configuração de segredos no Streamlit Cloud (Para Deploy)

Ao colocar a aplicação no ar na nuvem do Streamlit, adicione a sua chave de API nas **Secrets** da plataforma:
1. No painel de controle do Streamlit Cloud, acesse as configurações (**Settings**) da sua aplicação implantada.
2. Navegue até a seção **Secrets**.
3. Adicione a variável de ambiente no formato TOML:
   ```toml
   GEMINI_API_KEY = "sua_chave_aqui_AIzaSy..."
   ```
4. Salve as modificações. O app passará a usar a chave configurada automaticamente e de forma segura.

---

## Configurando o Google Sheets

O pipeline permite registrar os resultados de cada análise automaticamente em uma planilha pública no Google Sheets ("Méliuz — Acompanhamento Testes A/B").

### Passo 1 — Crie uma Service Account no Google Cloud Console

1. Acesse o [Google Cloud Console](https://console.cloud.google.com/).
2. Crie um novo projeto ou selecione um existente.
3. No menu de navegação, vá em **APIs e Serviços** > **Biblioteca**. Pesquise por "Google Sheets API" e "Google Drive API" e ative ambas.
4. Vá em **APIs e Serviços** > **Credenciais**.
5. Clique em **Criar Credenciais** e selecione **Conta de Serviço (Service Account)**.
6. Preencha os dados e conclua a criação.

### Passo 2 — Baixe o JSON de credenciais

1. Na lista de Service Accounts, clique na conta que você acabou de criar.
2. Vá na aba **Chaves** (Keys).
3. Clique em **Adicionar chave** > **Criar nova chave**.
4. Selecione o tipo **JSON** e clique em **Criar**. O download do arquivo começará automaticamente.

### Passo 3 — Configure a variável no `.env`

Copie o arquivo baixado para a raiz do seu projeto (ou para um local seguro). Em seguida, no seu arquivo `.env`, adicione a seguinte variável apontando para o arquivo:

```env
GOOGLE_SERVICE_ACCOUNT_JSON=caminho/para/seu/arquivo-de-credenciais.json
```

### Passo 4 — Configuração no Streamlit Cloud (Secrets)

Para uso online, em vez de subir o arquivo de credenciais (que por padrão está no `.gitignore`), você pode adicionar o JSON inteiro como uma string na variável no Streamlit Cloud.
1. No seu app do Streamlit Cloud, vá em **Settings** > **Secrets**.
2. Cole todo o conteúdo do JSON como uma string (uma única linha, escapando as aspas duplas, ou formatando o TOML adequadamente) para a variável correspondente:
   ```toml
   GOOGLE_SERVICE_ACCOUNT_JSON = '{"type": "service_account", "project_id": "..."}'
   ```
   > Outra alternativa suportada é criar o dicionário/json de forma embutida.

### O que acontece quando não está configurado?

Se a variável `GOOGLE_SERVICE_ACCOUNT_JSON` não for encontrada, o **pipeline continua normalmente** sem gerar logs de erro críticos. Apenas não será feita a inclusão da linha no Google Sheets. No aplicativo Web (Streamlit), aparecerá uma mensagem informativa lembrando da possibilidade de registrar a análise.

---

## Schema dos Dados de Entrada

O CSV deve ter as seguintes colunas:

| Coluna | Tipo | Exemplo |
|---|---|---|
| `Data` | YYYY-MM-DD | `2011-01-01` |
| `Grupos de usuários` | string | `Grupo 1` |
| `Parceiro` | string | `Parceiro A` |
| `compradores` | int | `196` |
| `comissão` | string (BRL) | `R$ 10.273` ou `R$ 2.911,50` |
| `cashback` | string (BRL) | `R$ 3.267` |
| `vendas totais` | string (BRL) | `R$ 93.390` |

---

## Outputs Gerados

### Por Parceiro (pasta `outputs/`)

| Arquivo | Descrição |
|---|---|
| `[parceiro]_estatisticas_descritivas.csv` | Soma, média, mediana, std, CV, quartis, skewness, kurtosis |
| `[parceiro]_testes_hipotese.csv` | Teste T, Mann-Whitney, Cohen's d, IC 95%, Uplift |
| `[parceiro]_resumo_completo.json` | JSON completo com todos os dados, usado como input do Gemini |

### Gráficos (pasta `charts/`)

| Arquivo | Descrição |
|---|---|
| `[parceiro]_linha_[metrica].png` | Evolução temporal da métrica por grupo ao longo dos dias |
| `[parceiro]_heatmap_pvalues.png` | Heatmap de p-values: visão geral de significância por grupo × métrica |

### Consolidados (pasta `reports/`)

| Arquivo | Descrição |
|---|---|
| `consolidado_descritivo.csv` | Todos os parceiros — descritivo unificado |
| `consolidado_hipoteses.csv` | Todos os parceiros — hipóteses unificadas |
| `consolidado_resumo.xlsx` | Excel multi-aba com descritivo, hipóteses e pivot KPI |
| `gemini/relatorio_executivo_[parceiro].pdf` | Relatório executivo em PDF gerado pelo Gemini (se `--gemini` usado) |

---

## Métricas Analisadas

| Métrica | Origem |
|---|---|
| `compradores` | Dados brutos |
| `vendas_totais` | GMV — dados brutos |
| `comissao` | Dados brutos |
| `cashback` | Dados brutos |
| `lucro` | `comissão - cashback` |
| `roi_cashback` | `vendas_totais / cashback` |
| `ticket_medio` | `vendas_totais / compradores` |

---

## Estatísticas Calculadas

### Descritivas
- Soma, Média, Mediana, Desvio Padrão, Variância, CV%
- Mínimo, Máximo, Amplitude
- Q1 (25%), Q2 (50%), Q3 (75%), IQR
- Skewness (assimetria), Kurtosis (curtose — Fisher)

### Inferenciais (variante vs. Grupo Controle)
- **Teste T de Welch** — robusto a variâncias desiguais
- **Mann-Whitney U** — não-paramétrico, sem assumir normalidade
- **Shapiro-Wilk** — teste de normalidade por grupo
- **Cohen's d** — tamanho de efeito (negligível / pequeno / médio / grande)
- **IC 95%** — intervalo de confiança para a diferença das médias
- **Uplift absoluto e relativo %**

---

## Configurações

Edite `config.py` para personalizar o comportamento do pipeline:

```python
ALPHA = 0.05              # Nível de significância dos testes
CONTROL_GROUP = "Grupo 1" # Nome do grupo controle nos dados
MIN_OBSERVATIONS = 5      # Mínimo de observações para rodar os testes
CHART_DPI = 150           # Resolução (DPI) dos gráficos exportados
CSV_SEPARATOR = ";"       # Separador dos CSVs de saída
```

---

## Dependências Principais

| Pacote | Uso |
|---|---|
| `pandas` | Manipulação de dados |
| `numpy` | Computação numérica |
| `scipy` | Testes estatísticos |
| `matplotlib` | Geração de gráficos |
| `openpyxl` | Export Excel |
| `google-genai` | Integração com a API do Gemini |
| `weasyprint` | Conversão de HTML/Markdown para PDF |
| `markdown` | Parsing do Markdown gerado pelo Gemini |
| `python-dotenv` | Carregamento do arquivo `.env` |

---

## Logs

O pipeline gera logs detalhados em `logs/pipeline.log`, incluindo:
- Alertas de qualidade de dados (valores negativos, nulos, codificação)
- Progresso de cada etapa por parceiro
- Erros com stack trace completo
