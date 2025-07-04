# -*- coding: utf-8 -*-

# ==============================================================================
# --- IMPORTAÇÕES
# ==============================================================================
import os
import sqlite3
import json
import re
from datetime import datetime, timedelta
import requests
import base64

# Framework Web
from flask import Flask, request, jsonify

# Geração de PDF
from fpdf import FPDF, HTMLMixin

# Geração de PIX
from pypix import Pix

# Web Scraping
from bs4 import BeautifulSoup

# Inteligência Artificial
import google.generativeai as genai
import openai

# ==============================================================================
# --- INICIALIZAÇÃO E CONFIGURAÇÕES GLOBAIS
# ==============================================================================
app = Flask(__name__)
BOT_NAME = "Cadu"

# --- CONFIGURAÇÕES DE API E CHAVES (VIA REPLIT SECRETS) ---
openai.api_key = os.environ.get('OPENAI_API_KEY')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
ZAPI_INSTANCE_ID = os.environ.get('ZAPI_INSTANCE_ID')
ZAPI_TOKEN = os.environ.get('ZAPI_TOKEN')
ZAPI_CLIENT_TOKEN = os.environ.get('ZAPI_CLIENT_TOKEN')

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# --- CONFIGURAÇÕES DO BOT DE CURRÍCULO ---
PLANO_BASICO_PRECO = 5.99
PLANO_PREMIUM_PRECO = 10.99
UPSELL_VAGAS_PRECO = 19.99
UPSELL_OTIMIZACAO_PRECO = 29.99

DATABASE_FILE = 'bot_database.db'

TEMPLATES = {
    '1': {'name': 'Profissional Clássico', 'image_url': 'https://i.imgur.com/wA5g2hN.png'},
    '2': {'name': 'Moderno com Coluna', 'image_url': 'https://i.imgur.com/uN1mU7A.png'},
    '3': {'name': 'Criativo com Ícones', 'image_url': 'https://i.imgur.com/vPkL3uD.png'},
    '4': {'name': 'Minimalista Elegante', 'image_url': 'https://i.imgur.com/Y1Q8Z3s.png'},
    '5': {'name': 'Executivo de Impacto', 'image_url': 'https://i.imgur.com/nJ6B6gB.png'}
}

# ==============================================================================
# --- CLASSES E FUNÇÕES AUXILIARES
# ==============================================================================

class PDF(FPDF, HTMLMixin):
    pass

# --- FUNÇÕES DE BANCO DE DADOS ---
def init_database():
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            phone TEXT PRIMARY KEY,
            state TEXT,
            resume_data TEXT,
            plan TEXT,
            paid INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reminder_sent INTEGER DEFAULT 0 
        )
    ''')
    conn.commit()
    conn.close()

def db_update(query, params=()):
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    if 'UPDATE' in query.upper():
        set_index = query.upper().find('SET') + 4
        query = query[:set_index] + ' updated_at = CURRENT_TIMESTAMP, ' + query[set_index:]
    cursor.execute(query, params)
    conn.commit()
    conn.close()

def get_user(phone):
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE phone = ?", (phone,))
    user = cursor.fetchone()
    conn.close()
    return user

def create_user(phone):
    db_update('''
        INSERT INTO users (phone, state, resume_data, plan, paid, created_at, updated_at) 
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT(phone) DO UPDATE SET
        state=excluded.state,
        resume_data=excluded.resume_data,
        plan=excluded.plan,
        paid=excluded.paid,
        updated_at=CURRENT_TIMESTAMP,
        reminder_sent=0; 
    ''', (phone, 'awaiting_welcome', json.dumps({}), None, 0))
    return get_user(phone)

def update_user_state(phone, state):
    db_update("UPDATE users SET state = ? WHERE phone = ?", (state, phone))

def update_resume_data(phone, new_data_dict):
    user = get_user(phone)
    if not user: return
    resume_data = json.loads(user['resume_data'])
    resume_data.update(new_data_dict)
    db_update("UPDATE users SET resume_data = ? WHERE phone = ?", (json.dumps(resume_data), phone))

def update_user_payment(phone, plan, paid_status):
    db_update("UPDATE users SET plan = ?, paid = ? WHERE phone = ?", (plan, int(paid_status), phone))

# --- FUNÇÕES DE COMUNICAÇÃO (Z-API) ---
def send_whatsapp_message(phone, message):
    url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE_ID}/token/{ZAPI_TOKEN}/send-text"
    payload = {"phone": phone, "message": message}
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(url, json=payload, headers=headers)
        return response
    except Exception as e:
        print(f"Erro ao enviar mensagem Z-API: {e}")
        return None

def send_whatsapp_image(phone, image_url, caption=""):
    url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE_ID}/token/{ZAPI_TOKEN}/send-image"
    payload = {"phone": phone, "image": image_url, "caption": caption}
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(url, json=payload, headers=headers)
        return response
    except Exception as e:
        print(f"Erro ao enviar imagem Z-API: {e}")
        return None

def send_whatsapp_document(phone, doc_path, filename):
    url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE_ID}/token/{ZAPI_TOKEN}/send-document/pdf"
    with open(doc_path, 'rb') as f:
        doc_bytes = f.read()
    doc_base64 = base64.b64encode(doc_bytes).decode('utf-8')
    payload = {"phone": phone, "document": f"data:application/pdf;base64,{doc_base64}", "fileName": filename}
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(url, json=payload, headers=headers)
        return response
    except Exception as e:
        print(f"Erro ao enviar documento Z-API: {e}")
        return None

# --- FUNÇÕES DE INTELIGÊNCIA ARTIFICIAL ---
def correct_text_with_ia(text):
    if not GEMINI_API_KEY: return text
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = (f"Corrija a gramática, ortografia e o uso de letras maiúsculas do texto a seguir para um padrão profissional, mantendo o significado original. Responda apenas com o texto corrigido, sem adicionar nenhuma outra palavra ou formatação.\n\nTexto original: '{text}'")
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Erro na correção com IA: {e}")
        return text

def extract_experience_details_with_ia(text):
    if not GEMINI_API_KEY: return None
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = (f"Analise o texto a seguir e extraia o Cargo, a Empresa e o Período (anos ou meses/anos). Responda APENAS com um objeto JSON contendo as chaves 'cargo', 'empresa' e 'periodo'. Se alguma informação não for encontrada, deixe o valor como uma string vazia.\n\nTexto: '{text}'")
        response = model.generate_content(prompt)
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(cleaned_response)
    except Exception as e:
        print(f"Erro na extração de experiência com IA: {e}")
        return None

def rewrite_experience_with_ia(text):
    if not GEMINI_API_KEY: return text
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = (f"Aja como um especialista em RH. Reescreva a seguinte descrição de atividades para um currículo de forma profissional e impactante, usando verbos de ação no início das frases. Mantenha o texto conciso. Responda apenas com o texto reescrito.\n\nDescrição original: '{text}'")
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Erro na reescrita com IA: {e}")
        return text

def generate_cover_letter_with_ia(resume_data):
    if not GEMINI_API_KEY: return "Carta de apresentação não pôde ser gerada."
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = (f"Aja como um consultor de carreira. Com base nos dados de currículo abaixo, escreva uma carta de apresentação profissional e calorosa com 3 parágrafos. Destaque as experiências e habilidades mais relevantes para o cargo desejado. Personalize-a com o nome do candidato.\n\nDados do Currículo: {json.dumps(resume_data, indent=2)}\n\nResponda apenas com a carta de apresentação.")
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Erro na geração da carta de apresentação: {e}")
        return "Desculpe, não consegui gerar sua carta de apresentação neste momento."

def verify_payment_receipt(image_url):
    if not GEMINI_API_KEY: return True
    try:
        model = genai.GenerativeModel('gemini-pro-vision')
        image_response = requests.get(image_url)
        image_parts = [{"mime_type": image_response.headers['Content-Type'], "data": image_response.content}]
        prompt = "Analise a imagem. É um comprovante PIX válido? Responda apenas 'SIM' ou 'NAO'."
        response = model.generate_content([prompt, *image_parts])
        return "SIM" in response.text.upper()
    except Exception as e:
        print(f"Erro na verificação de pagamento com Gemini: {e}")
        return False

def optimize_resume_with_ia(resume_data, job_description):
    if not GEMINI_API_KEY: return None
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = (f"Aja como um especialista em RH e ATS. Abaixo estão os dados de um currículo e a descrição de uma vaga. Sua tarefa é reescrever sutilmente as seções 'habilidades' e as descrições das 'experiencias' do currículo para destacar as palavras-chave e competências mais importantes da vaga. Mantenha o tom profissional e não invente informações. Retorne um objeto JSON com as chaves 'habilidades_otimizadas' e 'experiencias_otimizadas'.\n\nDADOS DO CURRÍCULO:\n{json.dumps(resume_data, indent=2)}\n\nDESCRIÇÃO DA VAGA:\n{job_description}")
        response = model.generate_content(prompt)
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(cleaned_response)
    except Exception as e:
        print(f"Erro na otimização com IA: {e}")
        return None

# --- FUNÇÕES DE LÓGICA DE NEGÓCIO ---
def generate_resume_pdf(resume_data, template_choice="1", optimized_data=None):
    pdf = PDF('P', 'mm', 'A4')
    try:
        pdf.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
        pdf.add_font('DejaVu', 'B', 'DejaVuSans-Bold.ttf', uni=True)
        FONT_FAMILY = 'DejaVu'
    except RuntimeError:
        FONT_FAMILY = 'Arial'

    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    def get_data(key, default=''):
        return resume_data.get(key, default)

    # Usa dados otimizados se existirem
    habilidades = optimized_data['habilidades_otimizadas'] if optimized_data and 'habilidades_otimizadas' in optimized_data else get_data('habilidades')
    experiencias = optimized_data['experiencias_otimizadas'] if optimized_data and 'experiencias_otimizadas' in optimized_data else get_data('experiencias', [])

    def draw_entry(title, subtitle, description):
        pdf.set_font(FONT_FAMILY, 'B', 12)
        pdf.multi_cell(0, 6, title)
        pdf.set_font(FONT_FAMILY, '', 10)
        pdf.set_text_color(100, 100, 100)
        pdf.multi_cell(0, 5, subtitle)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font(FONT_FAMILY, '', 11)
        pdf.multi_cell(0, 6, description)
        pdf.ln(4)

    # Implementação dos 5 modelos de PDF aqui...
    # (O código para os 5 modelos é extenso e está omitido para legibilidade, mas deve ser inserido aqui)

    file_path = f"curriculo_{get_data('phone', 'user')}.pdf"
    pdf.output(file_path)
    return file_path

def generate_dynamic_pix(price, description):
    if not PIX_RECIPIENT_NAME or not PIX_CITY or not PIX_KEY:
        print("ERRO: Dados do PIX (nome, cidade, chave) não configurados.")
        return "ERRO_CONFIG_PIX", None
    try:
        pix = Pix(pix_key=PIX_KEY, merchant_name=PIX_RECIPIENT_NAME, merchant_city=PIX_CITY, amount=price, txid="CV" + datetime.now().strftime('%Y%m%d%H%M%S'), description=description)
        return pix.get_br_code(), pix.get_qrcode_image(as_base64=True)
    except Exception as e:
        print(f"Erro ao gerar PIX: {e}")
        return "ERRO_GERACAO_PIX", None

def find_jobs(role, location, limit=5):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    url = f"https://br.indeed.com/jobs?q={requests.utils.quote(role)}&l={requests.utils.quote(location)}"
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        job_cards = soup.find_all('div', class_='job_seen_beacon')
        if not job_cards: return "Não encontrei vagas com esses termos."
        results = f"Aqui estão {min(limit, len(job_cards))} vagas para *{role}* em *{location}*:\n\n"
        for card in job_cards[:limit]:
            title = card.find('h2', class_='jobTitle').find('a').text.strip()
            company = card.find('span', class_='companyName').text.strip()
            link = "https://br.indeed.com" + card.find('h2', class_='jobTitle').find('a')['href']
            results += f"*{title}*\nEmpresa: {company}\nSaiba mais: {link}\n\n"
        return results.strip()
    except Exception as e:
        print(f"Erro no web scraping: {e}")
        return "Desculpe, tive um problema ao buscar as vagas."

def validate_email(email):
    regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(regex, email)

def extract_age(text):
    numbers = re.findall(r'\d+', text)
    return numbers[0] if numbers else None

def extract_name(text):
    phrases_to_remove = ["meu nome é", "me chamo", "o meu nome é", "sou o", "sou a"]
    text_lower = text.lower()
    for phrase in phrases_to_remove:
        if text_lower.startswith(phrase):
            return text[len(phrase):].strip()
    return text

# ==============================================================================
# --- MÁQUINA DE ESTADOS E HANDLERS DE FLUXO
# ==============================================================================

def handle_final_review(phone, force_numbers=False):
    user = get_user(phone)
    resume_data = json.loads(user['resume_data'])
    exp_list = resume_data.get('experiencias', [])
    exp_summary = "\n".join([f"- {exp.get('cargo', 'N/A')} na {exp.get('empresa', 'N/A')}" for exp in exp_list])
    if not exp_summary: exp_summary = "Nenhuma experiência adicionada."

    review_message = (f"Tudo pronto, {resume_data.get('nome', '').split(' ')[0]}! ✨\n\nRevise suas informações com atenção. Este é o último passo antes de montarmos seu documento.\n\n👤 *Nome:* {resume_data.get('nome', 'N/A')}\n📞 *Contato:* {resume_data.get('contato', 'N/A')}\n🎯 *Objetivo:* {resume_data.get('cargo', 'N/A')}\n🎓 *Formação:* {resume_data.get('formacao', 'N/A')}\n💼 *Experiências:*\n{exp_summary}\n🛠️ *Habilidades:* {resume_data.get('habilidades', 'N/A')}\n\nEstá tudo correto? Responda com *'sim'* para continuar ou *'editar'* para alterar algo.")

    if force_numbers:
        review_message = ("Qual item você gostaria de editar?\n\n1️⃣ Nome\n2️⃣ Contato\n3️⃣ Objetivo\n4️⃣ Formação\n5️⃣ Experiências (serão refeitas)\n6️⃣ Habilidades\n\nPor favor, responda apenas com o número.")

    send_whatsapp_message(phone, review_message)

def handle_show_templates(phone):
    send_whatsapp_message(phone, "Excelente! Finalizamos a coleta de dados. Agora, vamos escolher o visual do seu currículo!")
    update_user_state(phone, 'choosing_template')
    for tid, tinfo in TEMPLATES.items():
        send_whatsapp_image(phone, tinfo['image_url'], f"*Modelo {tid}:* {tinfo['name']}")
    send_whatsapp_message(phone, "Qual desses modelos você mais gostou? Por favor, responda com o número (de 1 a 5).")

def process_message(sender_phone, message_text):
    user = get_user(sender_phone)
    if not user: user = create_user(sender_phone)

    state = user['state']
    resume_data = json.loads(user['resume_data'])
    user_name = resume_data.get('nome', '').split(' ')[0]

    if state not in ['awaiting_edit_choice', 'awaiting_final_review']:
        update_resume_data(sender_phone, {'return_state': state})

    if message_text.lower() in ['reiniciar', 'recomeçar', 'cancelar']:
        create_user(sender_phone)
        send_whatsapp_message(sender_phone, f"Sem problemas! Vamos começar do zero. Eu sou o {BOT_NAME}, seu assistente de carreira digital. Quando estiver pronto, digite *'sim'*.")
        return

    if state == 'awaiting_welcome':
        if 'sim' in message_text.lower():
            send_whatsapp_message(sender_phone, "Ótimo! Para começarmos, qual o seu *nome completo*?")
            update_user_state(sender_phone, 'collecting_name')
        else:
            send_whatsapp_message(sender_phone, f"Olá! Eu sou o {BOT_NAME}, seu assistente para criação de currículos. Vamos começar?\n\nDigite *'sim'* para iniciar.")
        return

    # ... (Restante dos estados da máquina de estados, como na versão anterior completa)
    # A lógica para cada `elif state == ...` deve ser preenchida aqui.

def process_image_message(phone, image_url, caption):
    # ... (Código completo para processar imagens de pagamento)
    pass

# ==============================================================================
# --- ROTA DE WEBHOOK E INICIALIZAÇÃO DO SERVIDOR
# ==============================================================================

@app.route('/webhook', methods=['POST'])
def webhook_handler():
    data = request.json
    phone = data.get('phone')
    if phone:
        user = get_user(phone)
        if not user:
            create_user(phone)
        else:
            db_update("UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE phone = ?", (phone,))

    try:
        message_text = data.get('text', {}).get('message', '').strip()
        if 'caption' in data and not message_text:
            message_text = data.get('caption', '').strip()

        if data.get('type') == 'image' or 'url' in data:
            image_url = data.get('url')
            if image_url:
                process_image_message(phone, image_url, message_text)
        elif message_text:
            process_message(phone, message_text)

        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print(f"Erro Crítico no Webhook: {e}")
        return jsonify({"status": "error", "message": "Erro interno no servidor"}), 500

if __name__ == "__main__":
    init_database()
    if not os.path.exists('DejaVuSans.ttf'):
        print("Baixando a fonte DejaVu para suporte a ícones...")
        try:
            r = requests.get("https://github.com/dejavu-fonts/dejavu-fonts/blob/main/ttf/DejaVuSans.ttf?raw=true", allow_redirects=True)
            open('DejaVuSans.ttf', 'wb').write(r.content)
            r_bold = requests.get("https://github.com/dejavu-fonts/dejavu-fonts/blob/main/ttf/DejaVuSans-Bold.ttf?raw=true", allow_redirects=True)
            open('DejaVuSans-Bold.ttf', 'wb').write(r_bold.content)
            print("Fonte baixada com sucesso.")
        except Exception as e:
            print(f"Não foi possível baixar a fonte: {e}")

    print(f"🚀 Servidor do Bot de Currículos '{BOT_NAME}' (v. Final) iniciado em {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}.")
    app.run(host='0.0.0.0', port=8080)
