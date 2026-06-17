import json
from google.oauth2.credentials import Credentials
import gspread

with open("token.json", "r") as token:
    creds = Credentials.from_authorized_user_info(json.load(token))

client = gspread.authorize(creds)
sheet = client.open_by_key("16mc0DiY_T4XXVXHuKi_ui82lbvDVAamtnTUt3mGWqQU").sheet1

# Clear everything
sheet.clear()

HEADERS = [
    "Nome do Teste",
    "Link do Relatório",
    "Data da Análise",
    "Descrição",
    "Data Início",
    "Data Fim",
    "Grupos Testados",
    "Grupo Controle",
    "Variante Vencedora",
    "Resultado Estatístico",
    "Decisão"
]

row_data = [
    "Teste A/B — Parceiro A",
    "https://drive.google.com/file/d/1mj2IIcYFYXBSpiymxgezAhsvmRCQmBib/view?usp=drivesdk",
    "17/06/2026",
    "Análise automatizada de testes A/B",
    "2011-01-01",
    "2011-04-02",
    "Grupo 1, Grupo 2, Grupo 3",
    "Grupo 1",
    "Grupo 1",
    "Nenhuma variante superou o controle com significância.",
    "Manter Grupo 1"
]

sheet.append_row(HEADERS)
sheet.append_row(row_data)

print("Planilha limpa e reconstruída com sucesso!")
