# -*- coding: utf-8 -*-

import os
import re
import json
import base64
import sqlite3
import requests
from flask import Flask, request, jsonify
from fpdf import FPDF
from pypix import Pix

app = Flask(__name__)
BOT_NAME = "Cadu"

# --- Configurações de ambiente e arquivos ---
DATA_DIR = os.environ.get('RENDER_DISK_PATH', '.')
DATABASE_FILE = os.path.join(DATA_DIR, 'bot_database.db')
TEMP_DIR = "/tmp"

ZAPI_INSTANCE_ID = os.environ.get('ZAPI_INSTANCE_ID')
ZAPI_TOKEN = os.environ.get('ZAPI_TOKEN')
ZAPI_CLIENT_TOKEN = os.environ.get('ZAPI_CLIENT_TOKEN')

PIX_RECIPIENT_NAME = os.environ.get('PIX_RECIPIENT_NAME', "Seu Nome Completo")
PIX_CITY = os.environ.get('PIX_CITY', "Sua Cidade")
PIX_KEY = os.environ.get('PIX_KEY')

# Preços dos planos (em reais)
plan_prices = {
    "gratis": 0.0,
    "basico": 9.90,
    "premium": 29.90
}

# Inicializa banco de dados SQLite
def init_database():
    print("-> Verificando e inicializando banco de dados...")
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            phone TEXT PRIMARY KEY,
            state TEXT,
            resume_data TEXT
        )
    ''')
    conn.commit()
    conn.close()
    print(f"Banco pronto em: {DATABASE_FILE}")

init_database()


# Funções banco de dados
def get_user(phone):
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE phone = ?", (phone,))
    user = cursor.fetchone()
    conn.close()
    return user

def create_user(phone):
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    empty_data = json.dumps({"state_index": 0, "is_reviewing": False})
    cursor.execute("INSERT OR REPLACE INTO users (phone, state, resume_data) VALUES (?, ?, ?)", (phone, 'start', empty_data))
    conn.commit()
    conn.close()
    print(f"--> Usuário criado: {phone}")
    return get_user(phone)

def update_user_state(phone, new_state):
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET state = ? WHERE phone = ?", (new_state, phone))
    conn.commit()
    conn.close()

def update_resume_data(phone, new_data_dict):
    user = get_user(phone)
    if not user:
        return
    resume_data = json.loads(user['resume_data'])
    resume_data.update(new_data_dict)
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET resume_data = ? WHERE phone = ?", (json.dumps(resume_data), phone))
    conn.commit()
    conn.close()

# Validações
def is_valid_email(email):
    regex = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(regex, email) is not None

def is_valid_phone(phone):
    digits = re.sub(r'\D', '', phone)
    return len(digits) in [10, 11]

def is_valid_age(age):
    return age.isdigit() and 10 <= int(age) <= 100

# Conversa e coleta de dados
conversation_flow = [
    {"key": "nome_completo", "question": "Qual o seu nome completo? 🤔", "validate": None},
    {"key": "idade", "question": "Quantos anos você tem? 🧓👶", "validate": is_valid_age},
    {"key": "cidade_estado", "question": "Informe sua cidade e estado (ex: Porto Alegre, RS). 🌆", "validate": None},
    {"key": "telefone", "question": "Qual seu telefone com DDD? 📞", "validate": is_valid_phone},
    {"key": "email", "question": "Qual seu melhor e-mail? 📧", "validate": is_valid_email},
    {"key": "cargo_desejado", "question": "Qual cargo ou área deseja trabalhar? 💼", "validate": None},
    {"key": "formacao_escolar", "question": "Qual sua formação escolar? 🎓", "validate": None},
    {"key": "cursos_extras", "question": "Quais cursos extras você fez? (Se não, responda 'nenhum') 📚", "validate": None},
    {"key": "experiencias", "question": "Descreva suas experiências profissionais mais relevantes. 🏢", "validate": None},
    {"key": "habilidades", "question": "Quais suas habilidades? (ex: pacote Office, atendimento) ⚙️", "validate": None},
    {"key": "disponibilidade", "question": "Qual sua disponibilidade? (ex: turno, início imediato) ⏰", "validate": None},
]

# Modelos de currículo disponíveis
available_models = ["simples", "formal", "criativo", "executivo", "ingles"]

def send_whatsapp_message(phone, message):
    url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE_ID}/token/{ZAPI_TOKEN}/send-text"
    payload = {"phone": phone, "message": message}
    headers = {"Content-Type": "application/json", "Client-Token": ZAPI_CLIENT_TOKEN}
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            print(f"--> Mensagem enviada para {phone}")
        else:
            print(f"### ERRO Z-API {response.status_code}: {response.text}")
    except Exception as e:
        print(f"### ERRO conexão Z-API: {e}")

def send_whatsapp_document(phone, doc_path, filename):
    url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE_ID}/token/{ZAPI_TOKEN}/send-document/pdf"
    with open(doc_path, 'rb') as f:
        doc_bytes = f.read()
    doc_base64 = base64.b64encode(doc_bytes).decode('utf-8')
    payload = {"phone": phone, "document": f"data:application/pdf;base64,{doc_base64}", "fileName": filename}
    headers = {"Content-Type": "application/json", "Client-Token": ZAPI_CLIENT_TOKEN}
    try:
        requests.post(url, json=payload, headers=headers)
    except Exception as e:
        print(f"Erro ao enviar documento Z-API: {e}")

def generate_dynamic_pix(price, description):
    if not all([PIX_RECIPIENT_NAME, PIX_CITY, PIX_KEY]):
        print("ERRO: Dados PIX não configurados.")
        return "ERRO_CONFIG_PIX"
    try:
        pix = Pix(pix_key=PIX_KEY, merchant_name=PIX_RECIPIENT_NAME, merchant_city=PIX_CITY, amount=price, description=description)
        return pix.get_br_code()
    except Exception as e:
        print(f"Erro gerar PIX: {e}")
        return "ERRO_GERACAO_PIX"

# Função para gerar PDF com os 5 modelos
def create_pdf(data, modelo):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    nome = data.get('nome_completo', '').strip()
    cargo = data.get('cargo_desejado', '').strip()
    idade = data.get('idade', '').strip()
    cidade_estado = data.get('cidade_estado', '').strip()
    telefone = data.get('telefone', '').strip()
    email = data.get('email', '').strip()
    formacao = data.get('formacao_escolar', '').strip()
    cursos = data.get('cursos_extras', '').strip()
    experiencias = data.get('experiencias', '').strip()
    habilidades = data.get('habilidades', '').strip()
    disponibilidade = data.get('disponibilidade', '').strip()

    if modelo == "simples":
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, nome, ln=True)
        pdf.set_font("Arial", '', 14)
        pdf.cell(0, 8, cargo, ln=True)
        pdf.ln(5)

        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 8, "Contato", ln=True)
        pdf.set_font("Arial", '', 12)
        pdf.cell(0, 6, f"Idade: {idade}", ln=True)
        pdf.cell(0, 6, f"Cidade/Estado: {cidade_estado}", ln=True)
        pdf.cell(0, 6, f"Telefone: {telefone}", ln=True)
        pdf.cell(0, 6, f"E-mail: {email}", ln=True)
        pdf.ln(8)

        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 8, "Formação Escolar", ln=True)
        pdf.set_font("Arial", '', 12)
        pdf.multi_cell(0, 7, formacao)
        pdf.ln(5)

        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 8, "Cursos Extras", ln=True)
        pdf.set_font("Arial", '', 12)
        pdf.multi_cell(0, 7, cursos)
        pdf.ln(5)

        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 8, "Experiência Profissional", ln=True)
        pdf.set_font("Arial", '', 12)
        pdf.multi_cell(0, 7, experiencias)
        pdf.ln(5)

        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 8, "Habilidades", ln=True)
        pdf.set_font("Arial", '', 12)
        pdf.multi_cell(0, 7, habilidades)
        pdf.ln(5)

        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 8, "Disponibilidade", ln=True)
        pdf.set_font("Arial", '', 12)
        pdf.multi_cell(0, 7, disponibilidade)

    elif modelo == "formal":
        pdf.set_font("Times", 'B', 18)
        pdf.cell(0, 12, nome.upper(), ln=True, align='C')
        pdf.set_font("Times", 'I', 14)
        pdf.cell(0, 10, cargo, ln=True, align='C')
        pdf.ln(10)

        pdf.set_font("Times", 'B', 12)
        pdf.cell(0, 10, "Informações de Contato", ln=True)
        pdf.set_font("Times", '', 12)
        pdf.cell(0, 8, f"Idade: {idade}", ln=True)
        pdf.cell(0, 8, f"Cidade/Estado: {cidade_estado}", ln=True)
        pdf.cell(0, 8, f"Telefone: {telefone}", ln=True)
        pdf.cell(0, 8, f"E-mail: {email}", ln=True)
        pdf.ln(10)

        pdf.set_font("Times", 'B', 14)
        pdf.cell(0, 10, "Formação Escolar", ln=True)
        pdf.set_font("Times", '', 12)
        pdf.multi_cell(0, 8, formacao)
        pdf.ln(8)

        pdf.set_font("Times", 'B', 14)
        pdf.cell(0, 10, "Cursos Extras", ln=True)
        pdf.set_font("Times", '', 12)
        pdf.multi_cell(0, 8, cursos)
        pdf.ln(8)

        pdf.set_font("Times", 'B', 14)
        pdf.cell(0, 10, "Experiência Profissional", ln=True)
        pdf.set_font("Times", '', 12)
        pdf.multi_cell(0, 8, experiencias)
        pdf.ln(8)

        pdf.set_font("Times", 'B', 14)
        pdf.cell(0, 10, "Habilidades", ln=True)
        pdf.set_font("Times", '', 12)
        pdf.multi_cell(0, 8, habilidades)
        pdf.ln(8)

        pdf.set_font("Times", 'B', 14)
        pdf.cell(0, 10, "Disponibilidade", ln=True)
        pdf.set_font("Times", '', 12)
        pdf.multi_cell(0, 8, disponibilidade)

    elif modelo == "criativo":
        pdf.set_fill_color(230, 230, 250)  # Lavanda
        pdf.rect(0, 0, 210, 297, 'F')

        pdf.set_text_color(25, 25, 112)  # Azul escuro
        pdf.set_font("Courier", 'B', 20)
        pdf.cell(0, 12, nome, ln=True, align='C')

        pdf.set_font("Courier", 'I', 14)
        pdf.cell(0, 10, cargo, ln=True, align='C')
        pdf.ln(10)

        pdf.set_font("Courier", 'B', 14)
        pdf.cell(0, 10, "Contato", ln=True)
        pdf.set_font("Courier", '', 12)
        pdf.cell(0, 8, f"Idade: {idade}", ln=True)
        pdf.cell(0, 8, f"Cidade/Estado: {cidade_estado}", ln=True)
        pdf.cell(0, 8, f"Telefone: {telefone}", ln=True)
        pdf.cell(0, 8, f"E-mail: {email}", ln=True)
        pdf.ln(10)

        pdf.set_font("Courier", 'B', 14)
        pdf.cell(0, 10, "Formação", ln=True)
        pdf.set_font("Courier", '', 12)
        pdf.multi_cell(0, 8, formacao)
        pdf.ln(8)

        pdf.set_font("Courier", 'B', 14)
        pdf.cell(0, 10, "Cursos", ln=True)
        pdf.set_font("Courier", '', 12)
        pdf.multi_cell(0, 8, cursos)
        pdf.ln(8)

        pdf.set_font("Courier", 'B', 14)
        pdf.cell(0, 10, "Experiências", ln=True)
        pdf.set_font("Courier", '', 12)
        pdf.multi_cell(0, 8, experiencias)
        pdf.ln(8)

        pdf.set_font("Courier", 'B', 14)
        pdf.cell(0, 10, "Habilidades", ln=True)
        pdf.set_font("Courier", '', 12)
        pdf.multi_cell(0, 8, habilidades)
        pdf.ln(8)

        pdf.set_font("Courier", 'B', 14)
        pdf.cell(0, 10, "Disponibilidade", ln=True)
        pdf.set_font("Courier", '', 12)
        pdf.multi_cell(0, 8, disponibilidade)

        pdf.set_text_color(0, 0, 0)

    elif modelo == "executivo":
        pdf.set_font("Helvetica", 'B', 24)
        pdf.set_text_color(0, 51, 102)
        pdf.cell(0, 15, nome, ln=True, align='L')

        pdf.set_font("Helvetica", 'I', 16)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(0, 12, cargo, ln=True, align='L')
        pdf.ln(8)

        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", 'B', 14)
        pdf.cell(0, 10, "Contato", ln=True)
        pdf.set_font("Helvetica", '', 12)
        pdf.cell(0, 8, f"Idade: {idade}", ln=True)
        pdf.cell(0, 8, f"Cidade/Estado: {cidade_estado}", ln=True)
        pdf.cell(0, 8, f"Telefone: {telefone}", ln=True)
        pdf.cell(0, 8, f"E-mail: {email}", ln=True)
        pdf.ln(8)

        pdf.set_font("Helvetica", 'B', 14)
        pdf.cell(0, 10, "Formação Escolar", ln=True)
        pdf.set_font("Helvetica", '', 12)
        pdf.multi_cell(0, 8, formacao)
        pdf.ln(6)

        pdf.set_font("Helvetica", 'B', 14)
        pdf.cell(0, 10, "Cursos Extras", ln=True)
        pdf.set_font("Helvetica", '', 12)
        pdf.multi_cell(0, 8, cursos)
        pdf.ln(6)

        pdf.set_font("Helvetica", 'B', 14)
        pdf.cell(0, 10, "Experiência Profissional", ln=True)
        pdf.set_font("Helvetica", '', 12)
        pdf.multi_cell(0, 8, experiencias)
        pdf.ln(6)

        pdf.set_font("Helvetica", 'B', 14)
        pdf.cell(0, 10, "Habilidades", ln=True)
        pdf.set_font("Helvetica", '', 12)
        pdf.multi_cell(0, 8, habilidades)
        pdf.ln(6)

        pdf.set_font("Helvetica", 'B', 14)
        pdf.cell(0, 10, "Disponibilidade", ln=True)
        pdf.set_font("Helvetica", '', 12)
        pdf.multi_cell(0, 8, disponibilidade)

    elif modelo == "ingles":
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, nome, ln=True)
        pdf.set_font("Arial", 'I', 14)
        pdf.cell(0, 10, cargo, ln=True)
        pdf.ln(10)

        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "Contact Information", ln=True)
        pdf.set_font("Arial", '', 12)
        pdf.cell(0, 8, f"Age: {idade}", ln=True)
        pdf.cell(0, 8, f"City/State: {cidade_estado}", ln=True)
        pdf.cell(0, 8, f"Phone: {telefone}", ln=True)
        pdf.cell(0, 8, f"Email: {email}", ln=True)
        pdf.ln(10)

        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, "Education", ln=True)
        pdf.set_font("Arial", '', 12)
        pdf.multi_cell(0, 8, formacao)
        pdf.ln(8)

        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, "Additional Courses", ln=True)
        pdf.set_font("Arial", '', 12)
        pdf.multi_cell(0, 8, cursos)
        pdf.ln(8)

        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, "Professional Experience", ln=True)
        pdf.set_font("Arial", '', 12)
        pdf.multi_cell(0, 8, experiencias)
        pdf.ln(8)

        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, "Skills", ln=True)
        pdf.set_font("Arial", '', 12)
        pdf.multi_cell(0, 8, habilidades)
        pdf.ln(8)

        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, "Availability", ln=True)
        pdf.set_font("Arial", '', 12)
        pdf.multi_cell(0, 8, disponibilidade)

    else:
        # Default para 'simples'
        return create_pdf(data, "simples")

    nome_clean = re.sub(r'\W+', '', nome)
    file_path = os.path.join(TEMP_DIR, f"curriculo_{nome_clean}_{modelo}.pdf")
    pdf.output(file_path)
    return file_path


# Envia menu de revisão para o usuário
def send_review_menu(phone, user_data):
    msg = f"Tá quase lá, {user_data.get('nome_completo','')}! Confere seus dados abaixo:\n\n"
    for q in conversation_flow:
        valor = user_data.get(q['key'], '(não informado)')
        msg += f"*{q['key'].replace('_', ' ').title()}:* {valor}\n"
    msg += "\nQuer editar algum campo? Digite *editar [campo]*. Exemplo: editar email\n"
    msg += "Se estiver tudo certo, digite *finalizar* para gerar seu currículo em PDF."
    send_whatsapp_message(phone, msg)

# Fluxo principal para processar mensagens do usuário
def process_message(phone, message):
    user = get_user(phone)
    if not user:
        create_user(phone)
        send_whatsapp_message(phone, f"👋 Opa, aqui é o {BOT_NAME}! Seu assistente amigo pra criar currículo. Responda *sim* para começar.")
        return

    user_data = json.loads(user['resume_data'])
    message_clean = message.strip()
    message_lower = message_clean.lower()

    state_index = user_data.get('state_index', 0)
    editing_key = user_data.get('editing_key', None)
    is_reviewing = user_data.get('is_reviewing', False)
    plan_chosen = user_data.get('plan_chosen', 'gratis')

    # Se usuário quiser reiniciar
    if message_lower in ['reiniciar', 'restart', 'começar de novo']:
        create_user(phone)
        send_whatsapp_message(phone, f"Pronto! Vamos começar do zero. Qual seu nome completo? 🤔")
        return

    # Começo da conversa
    if state_index == 0 and not is_reviewing:
        if 'sim' in message_lower or 'oi' in message_lower or 'começar' in message_lower:
            send_whatsapp_message(phone, conversation_flow[0]['question'])
            user_data['state_index'] = 1
            update_resume_data(phone, user_data)
            return
        else:
            send_whatsapp_message(phone, f"Olá! Eu sou o {BOT_NAME}, seu assistente para criar currículos. Responda *sim* para começar.")
            return

    # Se está em modo edição
    if editing_key:
        q_info = next((q for q in conversation_flow if q['key'] == editing_key), None)
        if not q_info:
            user_data['editing_key'] = None
            update_resume_data(phone, user_data)
            send_whatsapp_message(phone, "Campo inválido. Voltando ao menu de revisão.")
            send_review_menu(phone, user_data)
            return

        val_func = q_info.get('validate')
        if val_func and not val_func(message_clean):
            send_whatsapp_message(phone, f"Ops! O valor para *{editing_key.replace('_', ' ')}* não é válido. Tente novamente.")
            return

        user_data[editing_key] = message_clean
        user_data['editing_key'] = None
        update_resume_data(phone, user_data)
        send_whatsapp_message(phone, "Beleza, atualizado! Voltando para o menu de revisão.")
        user_data['is_reviewing'] = True
        update_resume_data(phone, user_data)
        send_review_menu(phone, user_data)
        return

    # Se está revisando dados antes de gerar currículo
    if is_reviewing:
        if message_lower == 'finalizar':
            send_whatsapp_message(phone, "Gerando seu currículo... 🖨️ Pode aguardar!")
            pdf_path = create_pdf(user_data, plan_chosen if plan_chosen in available_models else "simples")
            send_whatsapp_document(phone, pdf_path, f"Curriculo_{user_data.get('nome_completo', 'user')}.pdf")
            if os.path.exists(pdf_path):
                os.remove(pdf_path)

            user_data['state_index'] = -1
            user_data['is_reviewing'] = False
            update_resume_data(phone, user_data)
            send_whatsapp_message(phone,
                "Pronto! Quer deixar seu currículo ainda melhor?\n"
                "Digite *planos* para conhecer nossos planos e serviços extras.")
            return

        elif message_lower.startswith('editar'):
            parts = message_lower.split()
            if len(parts) == 2:
                key_to_edit = parts[1]
                valid_keys = [q['key'] for q in conversation_flow]
                if key_to_edit in valid_keys:
                    user_data['editing_key'] = key_to_edit
                    user_data['is_reviewing'] = False
                    update_resume_data(phone, user_data)
                    q_text = next(q['question'] for q in conversation_flow if q['key'] == key_to_edit)
                    send_whatsapp_message(phone, f"Ok, vamos editar *{key_to_edit.replace('_', ' ')}*.\n{q_text}")
                    return
                else:
                    send_whatsapp_message(phone, "Não entendi qual campo você quer editar. Tente novamente.")
                    return
            else:
                send_whatsapp_message(phone, "Para editar, digite *editar* seguido do nome do campo. Ex: editar email")
                return
        else:
            send_whatsapp_message(phone, "No menu de revisão, digite *finalizar* para gerar o currículo ou *editar [campo]* para alterar alguma informação.")
            return

    # Se usuário pede planos
    if message_lower == 'planos':
        planos_msg = (
            "Confira nossos planos:\n\n"
            "1️⃣ Grátis: currículo básico em PDF.\n"
            "2️⃣ Básico - R$9,90: currículo estilizado + carta de apresentação.\n"
            "3️⃣ Premium - R$29,90: tudo do básico + versão em inglês + revisão humana.\n\n"
            "Digite o número do plano que deseja contratar."
        )
        user_data['awaiting_plan_choice'] = True
        update_resume_data(phone, user_data)
        send_whatsapp_message(phone, planos_msg)
        return

    if user_data.get('awaiting_plan_choice'):
        if message_lower in ['1', '2', '3']:
            plan_map = {'1': 'gratis', '2': 'basico', '3': 'premium'}
            chosen_plan = plan_map[message_lower]
            user_data['plan_chosen'] = chosen_plan
            user_data['awaiting_plan_choice'] = False
            user_data['awaiting_payment_confirmation'] = False
            update_resume_data(phone, user_data)
            if chosen_plan == "gratis":
                send_whatsapp_message(phone, "Você escolheu o plano grátis. Gerando seu currículo simples...")
                pdf_path = create_pdf(user_data, "simples")
                send_whatsapp_document(phone, pdf_path, f"Curriculo_{user_data.get('nome_completo','user')}.pdf")
                if os.path.exists(pdf_path):
                    os.remove(pdf_path)
                send_whatsapp_message(phone, "Se quiser, pode contratar um plano mais completo depois digitando *planos*.")
                return
            else:
                send_whatsapp_message(phone, f"Você escolheu o plano *{chosen_plan}*. Gerando código PIX para pagamento, aguarde...")
                pix_code = generate_dynamic_pix(plan_prices[chosen_plan], f"Plano {chosen_plan} - Currículo")
                send_whatsapp_message(phone, f"🔶 PIX para pagamento:\n{pix_code}\n\nApós pagar, envie *pago* para confirmar.")
                user_data['awaiting_payment_confirmation'] = True
                update_resume_data(phone, user_data)
                return
        else:
            send_whatsapp_message(phone, "Digite o número do plano desejado: 1, 2 ou 3.")
            return

    if user_data.get('awaiting_payment_confirmation'):
        if message_lower == 'pago':
            send_whatsapp_message(phone, "Pagamento recebido! Gerando seu currículo premium...")
            pdf_path = create_pdf(user_data, user_data.get('plan_chosen', 'basico'))
            send_whatsapp_document(phone, pdf_path, f"Curriculo_{user_data.get('nome_completo','user')}.pdf")
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
            user_data['awaiting_payment_confirmation'] = False
            update_resume_data(phone, user_data)
            send_whatsapp_message(phone, "Quer que a gente envie seu currículo para 50 empresas da sua cidade? Digite *envio* para saber mais.")
            return
        else:
            send_whatsapp_message(phone, "Quando fizer o pagamento, envie *pago* para confirmar.")
            return

    if message_lower == 'envio':
        send_whatsapp_message(phone,
            "Serviço extra:\n"
            "Enviamos seu currículo para 50 empresas da sua cidade por R$19,90.\n"
            "Digite *sim* para contratar ou *não* para cancelar."
        )
        user_data['awaiting_envio_confirmation'] = True
        update_resume_data(phone, user_data)
        return

    if user_data.get('awaiting_envio_confirmation'):
        if message_lower == 'sim':
            send_whatsapp_message(phone, "Show! Nosso time vai começar o envio e te avisamos assim que terminar.")
            # Aqui entraria integração para enviar os currículos para empresas (externo)
            user_data['awaiting_envio_confirmation'] = False
            update_resume_data(phone, user_data)
            return
        elif message_lower == 'não':
            send_whatsapp_message(phone, "Beleza, cancelado o envio. Se quiser outra coisa, é só falar!")
            user_data['awaiting_envio_confirmation'] = False
            update_resume_data(phone, user_data)
            return
        else:
            send_whatsapp_message(phone, "Digite *sim* para contratar ou *não* para cancelar.")
            return

    # Fluxo padrão de perguntas e coleta de dados
    if 1 <= state_index <= len(conversation_flow):
        current_q = conversation_flow[state_index - 1]
        val_func = current_q.get('validate')
        if val_func and not val_func(message_clean):
            send_whatsapp_message(phone, f"Ops! O valor para *{current_q['key'].replace('_', ' ')}* não é válido. Tente novamente.")
            return

        user_data[current_q['key']] = message_clean
        user_data['state_index'] = state_index + 1
        update_resume_data(phone, user_data)

        if user_data['state_index'] > len(conversation_flow):
            user_data['is_reviewing'] = True
            update_resume_data(phone, user_data)
            send_review_menu(phone, user_data)
            return
        else:
            next_q = conversation_flow[user_data['state_index'] - 1]['question']
            send_whatsapp_message(phone, next_q)
            return

    send_whatsapp_message(phone, "Se precisar, digite *reiniciar* para começar do zero.")

# Rota do webhook (exemplo para Z-API)
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    try:
        phone = data['message']['from']['phone']
        message = data['message']['text']['body']
        print(f"Mensagem de {phone}: {message}")
        process_message(phone, message)
    except Exception as e:
        print(f"Erro no webhook: {e}")
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(port=5000)

