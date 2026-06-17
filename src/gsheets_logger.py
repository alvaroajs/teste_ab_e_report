import os
import json
import logging
from datetime import datetime
from google.oauth2.service_account import Credentials
import gspread
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as UserCredentials
from google_auth_oauthlib.flow import InstalledAppFlow

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

def get_credentials(credentials_path_or_json: str) -> Credentials | UserCredentials:
    """
    Carrega as credenciais a partir de um arquivo JSON ou string JSON.
    Suporta tanto Service Account quanto OAuth2 Client Secret (usuário).
    """
    try:
        # Se for um OAuth2 token já salvo (prioridade para não abrir o browser)
        token_path = os.getenv("GOOGLE_TOKEN_JSON", "token.json")
        creds = None
        if os.path.exists(token_path):
            with open(token_path, "r") as token:
                creds = UserCredentials.from_authorized_user_info(json.load(token), SCOPES)
        
        # Se as credenciais do token são válidas, retorna elas
        if creds and creds.valid:
            return creds
            
        # Se as credenciais do token expiraram e há um refresh token, tenta renovar
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                with open(token_path, "w") as token:
                    token.write(creds.to_json())
                return creds
            except Exception as refresh_error:
                logger.warning(f"Erro ao renovar token OAuth2 (pedindo novo login): {refresh_error}")
                creds = None
        
        # Se não há token válido, lê o JSON fornecido (que pode ser SA ou Client Secret)
        info = None
        if credentials_path_or_json.strip().startswith("{"):
            info = json.loads(credentials_path_or_json)
        else:
            if not os.path.isfile(credentials_path_or_json):
                raise FileNotFoundError(f"Arquivo de credenciais não encontrado: {credentials_path_or_json}")
            with open(credentials_path_or_json, "r") as f:
                info = json.load(f)
                
        # Se for Service Account
        if info.get("type") == "service_account":
            return Credentials.from_service_account_info(info, scopes=SCOPES)
            
        # Se for um OAuth2 token inline (ex: do Streamlit Secrets)
        elif "refresh_token" in info and "client_id" in info:
            logger.info("Credencial OAuth2 Token Inline detectada.")
            inline_creds = UserCredentials.from_authorized_user_info(info, SCOPES)
            if inline_creds and inline_creds.expired and inline_creds.refresh_token:
                try:
                    inline_creds.refresh(Request())
                except Exception as e:
                    logger.warning(f"Falha ao renovar token inline: {e}")
            return inline_creds
            
        # Se for OAuth2 Client Secret ("installed" ou "web")
        elif "installed" in info or "web" in info:
            logger.info("Credencial OAuth2 detectada. Abrindo navegador para autorização...")
            if credentials_path_or_json.strip().startswith("{"):
                flow = InstalledAppFlow.from_client_config(info, SCOPES)
            else:
                flow = InstalledAppFlow.from_client_secrets_file(credentials_path_or_json, SCOPES)
            
            # Porta 0 escolhe uma porta livre automaticamente
            creds = flow.run_local_server(port=0)
            
            # Salva para as próximas vezes
            with open(token_path, "w") as token:
                token.write(creds.to_json())
            logger.info(f"Login bem sucedido! Token salvo em {token_path}")
            return creds
            
        else:
            raise ValueError("Formato de JSON de credencial desconhecido.")
            
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
