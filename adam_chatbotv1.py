import streamlit as st
import os
import json
import hashlib
import requests
from datetime import datetime
from typing import List, Dict
import PyPDF2
import openpyxl
from pptx import Presentation
import io
from bs4 import BeautifulSoup

# Page configuration
st.set_page_config(
    page_title="A.D.A.M - Agile Digital Assistance for Managers",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for ChatGPT-like styling
st.markdown("""
<style>
    .main {
        background-color: #343541;
    }
    .stTextInput > div > div > input {
        background-color: #40414f;
        color: #ececf1;
        border: 1px solid #565869;
        border-radius: 5px;
    }
    .stButton > button {
        background-color: #10a37f;
        color: white;
        border-radius: 5px;
        border: none;
        padding: 0.5rem 1rem;
    }
    .stButton > button:hover {
        background-color: #0d8c6d;
    }
    .chat-message {
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        display: flex;
        flex-direction: column;
    }
    .user-message {
        background-color: #343541;
        color: #ececf1;
    }
    .assistant-message {
        background-color: #444654;
        color: #ececf1;
    }
    .sidebar .sidebar-content {
        background-color: #202123;
    }
    .follow-up-questions {
        background-color: #2d2e3a;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-top: 1rem;
    }
    .follow-up-btn {
        background-color: #40414f;
        color: #ececf1;
        padding: 0.5rem 1rem;
        margin: 0.3rem;
        border-radius: 5px;
        border: 1px solid #565869;
        cursor: pointer;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
def init_session_state():
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'username' not in st.session_state:
        st.session_state.username = None
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    if 'conversations' not in st.session_state:
        st.session_state.conversations = []
    if 'current_conversation_id' not in st.session_state:
        st.session_state.current_conversation_id = None
    if 'llm_type' not in st.session_state:
        st.session_state.llm_type = 'cloud'
    if 'api_key' not in st.session_state:
        st.session_state.api_key = ''

# User authentication functions
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def load_users():
    if os.path.exists('users.json'):
        with open('users.json', 'r') as f:
            return json.load(f)
    return {}

def save_users(users):
    with open('users.json', 'w') as f:
        json.dump(users, f)

def create_user(username: str, password: str):
    users = load_users()
    if username in users:
        return False
    users[username] = hash_password(password)
    save_users(users)
    return True

def verify_user(username: str, password: str) -> bool:
    users = load_users()
    if username not in users:
        return False
    return users[username] == hash_password(password)

def reset_password(username: str, new_password: str) -> bool:
    users = load_users()
    if username not in users:
        return False
    users[username] = hash_password(new_password)
    save_users(users)
    return True

# Document processing functions
def extract_text_from_pdf(file) -> str:
    pdf_reader = PyPDF2.PdfReader(file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

def extract_text_from_pptx(file) -> str:
    prs = Presentation(file)
    text = ""
    for slide in prs.slides:
        for shape in slide.shapes:
            if hasattr(shape, "text"):
                text += shape.text + "\n"
    return text

def extract_text_from_excel(file) -> str:
    wb = openpyxl.load_workbook(file)
    text = ""
    for sheet in wb.sheetnames:
        ws = wb[sheet]
        text += f"\n--- Sheet: {sheet} ---\n"
        for row in ws.iter_rows(values_only=True):
            text += " | ".join([str(cell) if cell is not None else "" for cell in row]) + "\n"
    return text

def process_uploaded_files(files) -> str:
    combined_text = ""
    for file in files:
        file_extension = file.name.split('.')[-1].lower()
        try:
            if file_extension == 'pdf':
                combined_text += f"\n--- {file.name} ---\n" + extract_text_from_pdf(file)
            elif file_extension == 'pptx' or file_extension == 'ppt':
                combined_text += f"\n--- {file.name} ---\n" + extract_text_from_pptx(file)
            elif file_extension == 'xlsx' or file_extension == 'xls':
                combined_text += f"\n--- {file.name} ---\n" + extract_text_from_excel(file)
        except Exception as e:
            st.error(f"Error processing {file.name}: {str(e)}")
    return combined_text

# Check if query is PM-related
def is_pm_related(query: str) -> bool:
    pm_keywords = [
        'project management', 'program management', 'portfolio management',
        'agile', 'scrum', 'sprint', 'kanban', 'sdlc', 'software engineering',
        'pmbok', 'pmi', 'prince2', 'waterfall', 'stakeholder', 'risk management',
        'project manager', 'backlog', 'standup', 'retrospective', 'velocity',
        'burndown', 'epic', 'user story', 'product owner', 'scrum master'
    ]
    query_lower = query.lower()
    return any(keyword in query_lower for keyword in pm_keywords)

# Web scraping for PM resources
def search_pm_resources(query: str) -> str:
    """Search PM-specific resources"""
    resources = []
    pm_sites = {
        'pmi.org': 'PMI - Project Management Institute',
        'projectmanagement.com': 'ProjectManagement.com',
        'prince2.com': 'PRINCE2'
    }
    
    # Note: In production, implement actual web scraping or API calls
    # This is a placeholder for the structure
    resources.append(f"Searching PM resources for: {query}")
    resources.append("Note: Integrate actual web scraping or API calls to pmi.org, projectmanagement.com, and prince2.com")
    
    return "\n".join(resources)

# LLM interaction functions
def call_ollama_local_stream(prompt: str, model: str = "deepseek-r1"):
    """Call local Ollama instance with streaming"""
    try:
        import ollama
        
        # Add no_think parameter for deepseek-r1
        options = {}
        if model == "deepseek-r1":
            options['no_think'] = True
        
        stream = ollama.chat(
            model=model,
            messages=[{'role': 'user', 'content': prompt}],
            options=options,
            stream=True
        )
        
        for chunk in stream:
            yield chunk['message']['content']
    except Exception as e:
        yield f"Error calling local LLM: {str(e)}"

def call_ollama_cloud_stream(prompt: str, api_key: str, model: str = "deepseek-v3.1:671b-cloud"):
    """Call cloud Ollama instance with streaming"""
    try:
        from ollama import Client
        
        client = Client(
            host="https://ollama.com",
            headers={'Authorization': f'Bearer {api_key}'}
        )
        
        messages = [{'role': 'user', 'content': prompt}]
        
        for part in client.chat(model, messages=messages, stream=True):
            yield part['message']['content']
    except Exception as e:
        yield f"Error calling cloud LLM: {str(e)}"

def generate_response_stream(query: str, context: str = "", llm_type: str = "cloud", api_key: str = ""):
    """Generate streaming response using appropriate LLM"""
    
    # Build the prompt
    prompt = f"You are A.D.A.M (Agile Digital Assistance for Managers), a specialized assistant for project management topics.\n\n"
    
    if context:
        prompt += f"Context from uploaded documents:\n{context}\n\n"
    
    # Check if PM-related and add PM resource context
    if is_pm_related(query):
        pm_context = search_pm_resources(query)
        prompt += f"PM Resource Context:\n{pm_context}\n\n"
    
    prompt += f"User Query: {query}\n\nProvide a comprehensive, well-formatted response."
    
    # Call appropriate LLM with streaming
    if llm_type == "cloud":
        if not api_key:
            yield "Error: API key required for cloud LLM. Please enter your API key in the sidebar."
            return
        for chunk in call_ollama_cloud_stream(prompt, api_key):
            yield chunk
    else:
        for chunk in call_ollama_local_stream(prompt):
            yield chunk

def generate_follow_up_questions(query: str, response: str) -> List[str]:
    """Generate follow-up questions based on the conversation"""
    # This could be enhanced with LLM generation
    # For now, returning template questions
    if is_pm_related(query):
        return [
            "Can you provide more details about best practices?",
            "What are common challenges in implementing this?",
            "How does this relate to other PM methodologies?"
        ]
    else:
        return [
            "Can you elaborate on that?",
            "What are the key considerations?",
            "Are there any examples or case studies?"
        ]

# Login/Registration page
def login_page():
    st.markdown("""
    <div style='text-align: center; padding: 2rem;'>
        <h1 style='color: #10a37f;'>🤖 A.D.A.M</h1>
        <h3 style='color: #ececf1;'>Agile Digital Assistance for Managers</h3>
    </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["Login", "Register", "Reset Password"])
    
    with tab1:
        st.subheader("Login")
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        
        if st.button("Login", key="login_btn"):
            if verify_user(username, password):
                st.session_state.authenticated = True
                st.session_state.username = username
                st.rerun()
            else:
                st.error("Invalid username or password")
    
    with tab2:
        st.subheader("Create New Account")
        new_username = st.text_input("Username", key="reg_username")
        new_password = st.text_input("Password", type="password", key="reg_password")
        confirm_password = st.text_input("Confirm Password", type="password", key="reg_confirm")
        
        if st.button("Register", key="reg_btn"):
            if new_password != confirm_password:
                st.error("Passwords do not match")
            elif len(new_password) < 6:
                st.error("Password must be at least 6 characters")
            elif create_user(new_username, new_password):
                st.success("Account created successfully! Please login.")
            else:
                st.error("Username already exists")
    
    with tab3:
        st.subheader("Reset Password")
        reset_username = st.text_input("Username", key="reset_username")
        new_pass = st.text_input("New Password", type="password", key="reset_new_pass")
        confirm_new_pass = st.text_input("Confirm New Password", type="password", key="reset_confirm")
        
        if st.button("Reset Password", key="reset_btn"):
            if new_pass != confirm_new_pass:
                st.error("Passwords do not match")
            elif len(new_pass) < 6:
                st.error("Password must be at least 6 characters")
            elif reset_password(reset_username, new_pass):
                st.success("Password reset successfully!")
            else:
                st.error("Username not found")

# Main chat interface
def main_page():
    # Sidebar
    with st.sidebar:
        st.markdown("""
        <div style='text-align: center; padding: 1rem;'>
            <h2 style='color: #10a37f;'>🤖 A.D.A.M</h2>
            <p style='color: #ececf1; font-size: 0.8rem;'>Agile Digital Assistance for Managers</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"**User:** {st.session_state.username}")
        
        # LLM Selection
        st.markdown("---")
        st.subheader("LLM Settings")
        st.session_state.llm_type = st.radio(
            "Select LLM Type",
            ["cloud", "local"],
            format_func=lambda x: "Cloud (deepseek-v3.1:671b-cloud)" if x == "cloud" else "Local (deepseek-r1)"
        )
        
        if st.session_state.llm_type == "cloud":
            st.session_state.api_key = st.text_input(
                "API Key",
                type="password",
                value=st.session_state.api_key,
                help="Required for cloud LLM"
            )
        
        # Chat History
        st.markdown("---")
        st.subheader("Chat History")
        
        if st.button("➕ New Chat", use_container_width=True):
            st.session_state.chat_history = []
            st.session_state.current_conversation_id = None
            st.rerun()
        
        if st.button("🗑️ Clear History", use_container_width=True):
            st.session_state.chat_history = []
            st.session_state.conversations = []
            st.session_state.current_conversation_id = None
            st.rerun()
        
        # Display saved conversations
        for idx, conv in enumerate(st.session_state.conversations):
            if st.button(f"💬 {conv['title'][:30]}...", key=f"conv_{idx}", use_container_width=True):
                st.session_state.chat_history = conv['messages']
                st.session_state.current_conversation_id = conv['id']
                st.rerun()
        
        st.markdown("---")
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.username = None
            st.rerun()
    
    # Main chat area
    st.markdown("<h1 style='color: #ececf1;'>A.D.A.M Chat</h1>", unsafe_allow_html=True)
    
    # File upload
    uploaded_files = st.file_uploader(
        "Upload documents (PDF, PPT, Excel, MPP)",
        type=['pdf', 'pptx', 'ppt', 'xlsx', 'xls', 'mpp'],
        accept_multiple_files=True
    )
    
    document_context = ""
    if uploaded_files:
        with st.spinner("Processing documents..."):
            document_context = process_uploaded_files(uploaded_files)
        st.success(f"Processed {len(uploaded_files)} document(s)")
    
    # Display chat history
    chat_container = st.container()
    with chat_container:
        for msg_idx, message in enumerate(st.session_state.chat_history):
            if message['role'] == 'user':
                st.markdown(f"""
                <div class='chat-message user-message'>
                    <strong>You:</strong><br>{message['content']}
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class='chat-message assistant-message'>
                    <strong>A.D.A.M:</strong><br>{message['content']}
                </div>
                """, unsafe_allow_html=True)
                
                # Display follow-up questions only for the last assistant message
                if 'follow_ups' in message and msg_idx == len(st.session_state.chat_history) - 1:
                    st.markdown("<div class='follow-up-questions'><strong>Follow-up questions:</strong></div>", unsafe_allow_html=True)
                    cols = st.columns(len(message['follow_ups']))
                    for idx, follow_up in enumerate(message['follow_ups']):
                        with cols[idx]:
                            if st.button(follow_up, key=f"followup_{message['timestamp']}_{idx}"):
                                st.session_state.pending_query = follow_up
                                st.rerun()
    
    # Chat input at the bottom
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Handle pending query from follow-up
    if 'pending_query' in st.session_state:
        query = st.session_state.pending_query
        del st.session_state.pending_query
    else:
        query = st.chat_input("ADAM> Type your message here...")
    
    if query:
        # Add user message
        st.session_state.chat_history.append({
            'role': 'user',
            'content': query,
            'timestamp': datetime.now().isoformat()
        })
        
        # Create placeholder for streaming response
        response_placeholder = st.empty()
        full_response = ""
        
        # Stream the response
        with response_placeholder.container():
            st.markdown("""
            <div class='chat-message user-message'>
                <strong>You:</strong><br>""" + query + """
            </div>
            """, unsafe_allow_html=True)
            
            # Create assistant message container
            assistant_message = st.markdown("""
            <div class='chat-message assistant-message'>
                <strong>A.D.A.M:</strong><br>
            </div>
            """, unsafe_allow_html=True)
            
            # Stream the response
            for chunk in generate_response_stream(
                query,
                document_context,
                st.session_state.llm_type,
                st.session_state.api_key
            ):
                full_response += chunk
                assistant_message.markdown(f"""
                <div class='chat-message assistant-message'>
                    <strong>A.D.A.M:</strong><br>{full_response}
                </div>
                """, unsafe_allow_html=True)
        
        # Generate follow-up questions after streaming completes
        follow_ups = generate_follow_up_questions(query, full_response)
        
        # Add assistant message to history
        st.session_state.chat_history.append({
            'role': 'assistant',
            'content': full_response,
            'follow_ups': follow_ups,
            'timestamp': datetime.now().isoformat()
        })
        
        # Save conversation
        if not st.session_state.current_conversation_id:
            conv_id = f"conv_{datetime.now().timestamp()}"
            st.session_state.conversations.append({
                'id': conv_id,
                'title': query[:50],
                'messages': st.session_state.chat_history.copy()
            })
            st.session_state.current_conversation_id = conv_id
        else:
            # Update existing conversation
            for conv in st.session_state.conversations:
                if conv['id'] == st.session_state.current_conversation_id:
                    conv['messages'] = st.session_state.chat_history.copy()
                    break
        
        st.rerun()

# Main app
def main():
    init_session_state()
    
    if not st.session_state.authenticated:
        login_page()
    else:
        main_page()

if __name__ == "__main__":
    main()
