# Pipeline de Análise de Testes A/B e Geração de Relatórios

Este projeto é um pipeline completo que automatiza a análise estatística de testes A/B, extrai insights utilizando Inteligência Artificial e gera relatórios executivos em PDF. Além do processamento robusto de dados, o sistema possui integração nativa na nuvem, exportando os PDFs diretamente para o Google Drive e registrando o histórico de análises em uma planilha no Google Sheets.

## Acessos Rápidos

Se você quiser ver o projeto funcionando de imediato, sem precisar instalar ou rodar código localmente, acesse os links abaixo:

- 🌐 **Aplicação Web (Streamlit):** [https://reportt.streamlit.app/](https://reportt.streamlit.app/)
- 📊 **Planilha de Acompanhamento (Google Sheets):** [Acessar Planilha](https://docs.google.com/spreadsheets/d/16mc0DiY_T4XXVXHuKi_ui82lbvDVAamtnTUt3mGWqQU/edit?gid=0#gid=0)
- 📁 **Arquivos Gerados (Google Drive):** [Ver Relatórios PDF](https://drive.google.com/drive/folders/1Rwafm-vzCGXtpKbYVLjxNkNWj2nQPAxf?hl=pt-br)

## Sobre a Arquitetura

Este projeto foi desenhado com um foco claro na separação de responsabilidades. Todo o processamento de dados e os cálculos estatísticos (como p-value, significância e intervalos de confiança) ocorrem de forma local e determinística. Vale destacar que **o motor estatístico do pipeline foi construído "na raça", utilizando puramente Pandas e SciPy**, em vez de recorrer à geração de código ou cálculos delegados à IA. O objetivo é demonstrar fundamentos sólidos de engenharia de software e análise de dados.

A API do Gemini entra em cena apenas na última etapa do fluxo: ela recebe os resultados exatos e pré-calculados, focando-se naquilo em que a IA generativa realmente brilha — interpretar os números, redigir um parecer executivo claro e gerar a estrutura HTML que será posteriormente convertida em um relatório PDF elegante por meio do WeasyPrint.

## Como executar o projeto localmente

Quer testar o código na sua máquina? É muito simples! Siga este passo a passo:

### 1. Preparar o Ambiente Virtual

Recomendo fortemente a criação de um ambiente virtual para isolar as dependências deste projeto das demais bibliotecas do seu sistema, garantindo que tudo rode sem conflitos.

Abra o seu terminal e crie o ambiente virtual com o seguinte comando:
```bash
python -m venv venv
```

Em seguida, ative-o:
- No **Linux/macOS**:
  ```bash
  source venv/bin/activate
  ```
- No **Windows**:
  ```bash
  venv\Scripts\activate
  ```

### 2. Instalar as Dependências

Com o ambiente ativado, instale todas as bibliotecas necessárias de uma só vez:
```bash
pip install -r requirements.txt
```

### 3. Configurar as Variáveis de Ambiente

O projeto precisa se comunicar com a IA do Google para redigir o relatório, além de utilizar as credenciais para acessar o Google Sheets e Google Drive. Crie um arquivo chamado `.env` na raiz do repositório e adicione suas credenciais da seguinte forma:

> **Dica:** Você pode gerar a sua `GEMINI_API_KEY` gratuitamente acessando o [Google AI Studio](https://aistudio.google.com/app/apikey).

```env
GEMINI_API_KEY=sua_chave_aqui

# Credenciais e configurações do Google Workspace
GOOGLE_SERVICE_ACCOUNT_JSON=credenciais.json
GOOGLE_DRIVE_FOLDER_ID=1Rwafm-vzCGXtpKbYVLjxNkNWj2nQPAxf
GOOGLE_CLIENT_SECRET_JSON=client_secret.json
GOOGLE_TOKEN_JSON=token.json
```

> **Aviso Importante sobre Credenciais:** Por motivos óbvios de segurança, os arquivos JSON mencionados acima (`credenciais.json`, etc.) não foram enviados para o GitHub. **A ausência deles não quebra o projeto!** Se você rodar localmente apenas com a chave do Gemini, o pipeline fará todas as análises e gerará o PDF normalmente na sua máquina, pulando de forma silenciosa apenas a etapa de upload para o Sheets e Drive.

### 3.1. Como habilitar a exportação para o Google Sheets e Drive (Opcional)

Se você quiser testar a exportação completa dos resultados para a nuvem, precisará gerar as suas próprias credenciais OAuth 2.0 no Google Cloud:

1. Acesse o [Google Cloud Console](https://console.cloud.google.com/).
2. Crie um novo projeto e ative as APIs: **Google Sheets API** e **Google Drive API**.
3. No menu lateral, acesse **APIs e Serviços > Credenciais**.
4. Clique em **Criar Credenciais > ID do Cliente OAuth** (Escolha o tipo **Aplicativo de Computador / Desktop App**).
5. Baixe o arquivo JSON gerado, renomeie para `client_secret.json` e coloque na raiz do projeto. O formato do arquivo será parecido com este:

```json
{
  "installed": {
    "client_id": "SEU_CLIENT_ID.apps.googleusercontent.com",
    "project_id": "nome-do-seu-projeto",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_secret": "SEU_CLIENT_SECRET",
    "redirect_uris": ["http://localhost"]
  }
}
```

6. Configure o `.env` com a variável `GOOGLE_DRIVE_FOLDER_ID` apontando para o ID da pasta do Drive onde você quer salvar os PDFs.
7. Na primeira vez que você rodar o projeto (seja via CLI ou Streamlit), o seu navegador abrirá pedindo para fazer login com o Google e autorizar os acessos. Após o login, o projeto criará automaticamente o arquivo `token.json` e fará os uploads futuros sem precisar perguntar novamente!

### 4. Executar a Aplicação

Você tem duas formas de rodar o projeto, dependendo da sua preferência:

**Para usar a Interface Gráfica (Web App):**
A forma mais visual e interativa de testar é através da aplicação desenvolvida em Streamlit. No terminal, execute:
```bash
streamlit run app.py
```

**Para executar a versão CLI (Linha de Comando):**
Caso prefire uma abordagem mais direta via terminal, você pode rodar o script principal:
```bash
python src/main.py
```

## Estrutura do Projeto

```text
Teste_A_B/
│
├── datasets/                       ← Coloque os seus arquivos CSV de input aqui!
│
├── outputs/                        ← CSVs e JSONs gerados pela análise local
├── reports/                        ← Relatórios consolidados e PDFs finais
├── charts/                         ← Gráficos PNG gerados localmente
├── src/                            ← Código fonte do motor estatístico e integrações
├── app.py                          ← Interface gráfica (Streamlit)
├── .env                            ← Suas credenciais da IA e Google Workspace
├── requirements.txt
└── README.md
```

## Formato dos Dados de Entrada

Os arquivos CSV que você colocar na pasta `datasets/` devem conter as seguintes 7 colunas obrigatórias:

| Coluna | Formato/Exemplo |
|---|---|
| `Data` | `YYYY-MM-DD` (Ex: `2023-01-01`) |
| `Grupos de usuários` | Texto indicando o grupo (Ex: `Grupo 1`, `Grupo 2`) |
| `Parceiro` | Texto identificando o parceiro/campanha |
| `compradores` | Inteiro numérico |
| `comissão` | Monetário BRL (Ex: `R$ 10.273,50`) |
| `cashback` | Monetário BRL |
| `vendas totais` | Monetário BRL |

> **Dica:** O pipeline aceita separadores por vírgula `,` ou ponto e vírgula `;`. O grupo base de controle está fixado no código como **Grupo 1**.

## Como o Pipeline Funciona (Fluxo de Execução)

A aplicação processa tudo em etapas lógicas e bem delimitadas:

1. **Carregamento e Limpeza (Data Prep):** Validação dos dados brutos, remoção de caracteres de moeda (BRL) e transformação para floats. Valores anômalos geram alertas automáticos.
2. **Estatísticas Descritivas:** O motor calcula métricas como média, mediana, desvio padrão, CV% e quartis por cada grupo.
3. **Testes de Hipótese (Inferência):** Execução rigorosa do Teste T de Welch (robusto para variâncias desiguais) e Mann-Whitney U, validando a significância estatística do A/B e o *uplift* entre os grupos.
4. **Visualização:** Geração de gráficos temporais comparando as métricas principais ao longo dos dias, e heatmaps para ilustrar os *p-values*.
5. **Geração do Relatório Executivo (IA):** Os números matemáticos puros e consolidados são enviados ao Google Gemini, que interpreta a significância dos resultados e redige uma narrativa. O texto é mesclado aos gráficos e convertido para um PDF final via WeasyPrint.
6. **Integração Cloud:** O PDF é automaticamente upado no Google Drive e a conclusão matemática é guardada em uma linha no Google Sheets.

E pronto! Fique à vontade para explorar, testar com os seus próprios CSVs, sugerir melhorias ou entrar em contato caso tenha alguma dúvida! 🚀

---

## Autor

Este projeto foi desenvolvido por **Álvaro Silva** Fico à disposição para dúvidas, sugestões ou colaborações. Sinta-se à vontade para entrar em contato!

<a href="https://www.linkedin.com/in/alvarosilvamg/" target="_blank">
  <img align="center" height="28px" src="https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white"/>
</a>&nbsp;&nbsp;
<a href="https://github.com/alvaroajs" target="_blank">
  <img align="center" height="28px" src="https://img.shields.io/badge/GitHub-100000?style=for-the-badge&logo=github&logoColor=white"/>
</a>

<br>

<a style="color:black" href="mailto:alvaro.ajsilva@gmail.com?subject=[GitHub]%20Projeto%20Pipeline%20A/B">
✉️ <i>alvaro.ajsilva@gmail.com</i>
</a>
