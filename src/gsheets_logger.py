import os
import json
import logging
from datetime import datetime
from google.oauth2.service_account import Credentials
import gspread
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

logger = logging.getLogger(__name__)

# Scopes necessários para acessar e editar planilhas e o drive (para permissões)
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Nome da planilha no Google Drive
SHEET_TITLE = "Acompanhamento Testes A/B"

# Cabeçalhos esperados
HEADERS = [
    "Nome do Teste",
    "Link do Relatório",
    "Data da Análise",
    "Descrição",
    "Período Inicial",
    "Período Final",
    "Grupos",
    "Grupo Controle",
    "Variante Vencedora",
    "Resultado Estatístico",
    "Decisão"
]

def get_credentials(credentials_path_or_json: str) -> Credentials:
    """
    Carrega as credenciais a partir de um arquivo JSON ou string JSON.
    """
    try:
        if credentials_path_or_json.strip().startswith("{"):
            # É um JSON embutido na string
            info = json.loads(credentials_path_or_json)
            return Credentials.from_service_account_info(info, scopes=SCOPES)
        else:
            # É um caminho de arquivo
            if not os.path.isfile(credentials_path_or_json):
                raise FileNotFoundError(f"Arquivo de credenciais não encontrado: {credentials_path_or_json}")
            return Credentials.from_service_account_file(credentials_path_or_json, scopes=SCOPES)
    except Exception as e:
        logger.error(f"Erro ao carregar credenciais do Google: {e}")
        raise

def log_test_result(test_data: dict, credentials_path: str) -> str:
    """
    Registra um resultado de teste A/B no Google Sheets.
    Retorna a URL pública da planilha.
    """
    creds = get_credentials(credentials_path)
    client = gspread.authorize(creds)
    
    # Tenta abrir a planilha existente
    try:
        spreadsheet = client.open(SHEET_TITLE)
    except gspread.exceptions.SpreadsheetNotFound:
        # Se não existir, cria
        logger.info(f"Planilha '{SHEET_TITLE}' não encontrada. Criando nova planilha...")
        try:
            # email do dono da service account ou default
            spreadsheet = client.create(SHEET_TITLE)
            # Compartilha com "anyone with link can view"
            spreadsheet.share(None, perm_type='anyone', role='reader')
            
            # Garante que o cabeçalho existe
            worksheet = spreadsheet.sheet1
            worksheet.append_row(HEADERS)
        except Exception as e:
            logger.error(f"Erro ao criar/compartilhar a planilha: {e}")
            raise

    worksheet = spreadsheet.sheet1
    
    # Prepara a linha (garantindo ordem e default para keys ausentes)
    row_data = [
        test_data.get("nome_teste", ""),
        test_data.get("link_relatorio", ""),
        test_data.get("data_analise", datetime.now().strftime('%d/%m/%Y')),
        test_data.get("descricao", ""),
        test_data.get("periodo_inicio", ""),
        test_data.get("periodo_fim", ""),
        test_data.get("grupos", ""),
        test_data.get("grupo_controle", ""),
        test_data.get("variante_vencedora", ""),
        test_data.get("resultado_estatistico", ""),
        test_data.get("decisao", "")
    ]
    
    # Append
    try:
        # Verifica se a primeira linha tem cabeçalho, se não, adiciona
        first_row = worksheet.row_values(1)
        if not first_row:
            worksheet.append_row(HEADERS)
        
        worksheet.append_row(row_data)
        logger.info(f"Linha adicionada com sucesso na planilha {SHEET_TITLE}.")
    except Exception as e:
        logger.error(f"Erro ao inserir linha na planilha: {e}")
        raise
        
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet.id}"
    return url

def upload_pdf_to_drive(pdf_path: str, credentials_path: str) -> str:
    """
    Faz upload de um PDF para uma pasta específica no Google Drive e retorna o link público.
    Requer que GOOGLE_DRIVE_FOLDER_ID esteja configurado no .env.
    """
    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    if not folder_id:
        logger.warning("GOOGLE_DRIVE_FOLDER_ID não configurado. Pulando upload do PDF.")
        return ""
    
    creds = get_credentials(credentials_path)
    drive_service = build('drive', 'v3', credentials=creds)
    
    file_metadata = {
        'name': os.path.basename(pdf_path),
        'parents': [folder_id]
    }
    media = MediaFileUpload(pdf_path, mimetype='application/pdf', resumable=True)
    
    try:
        file = drive_service.files().create(
            body=file_metadata, 
            media_body=media, 
            fields='id, webViewLink',
            supportsAllDrives=True
        ).execute()
        file_id = file.get('id')
        link = file.get('webViewLink')
        
        # Compartilhar para qualquer um com link ver
        permission = {
            'type': 'anyone',
            'role': 'reader'
        }
        drive_service.permissions().create(fileId=file_id, body=permission).execute()
        
        logger.info(f"PDF {os.path.basename(pdf_path)} enviado para o Drive com sucesso: {link}")
        return link
    except Exception as e:
        logger.error(f"Erro ao fazer upload do PDF para o Drive: {e}")
        return ""
