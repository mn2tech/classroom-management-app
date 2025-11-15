import streamlit as st
import sqlite3
import json
from datetime import datetime, date
import pandas as pd
from typing import Dict, List, Optional
import uuid
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from io import BytesIO
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
from contextlib import contextmanager

# Try to import Supabase (optional - for production)
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

# Page configuration
st.set_page_config(
    page_title="WCA Classroom Manager",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Database configuration - check for Supabase first
def get_supabase_client():
    """Initialize Supabase client if credentials are available"""
    if not SUPABASE_AVAILABLE:
        return None
    
    try:
        # Check for Supabase credentials in Streamlit secrets
        if hasattr(st, 'secrets') and 'supabase' in st.secrets:
            url = st.secrets['supabase']['url']
            key = st.secrets['supabase']['key']
            
            # Validate URL format
            if not url or url == "YOUR_SUPABASE_PROJECT_URL_HERE" or not url.startswith('https://'):
                return None
            if not key or key == "YOUR_SUPABASE_ANON_KEY_HERE":
                return None
            
            return create_client(url, key)
        # Also check environment variables
        elif 'SUPABASE_URL' in os.environ and 'SUPABASE_KEY' in os.environ:
            url = os.environ['SUPABASE_URL']
            key = os.environ['SUPABASE_KEY']
            
            # Validate URL format
            if not url.startswith('https://'):
                return None
            
            return create_client(url, key)
    except Exception as e:
        # Only show error once, not on every page load
        if 'supabase_error_shown' not in st.session_state:
            st.session_state.supabase_error_shown = True
            st.warning(f"⚠️ Supabase not configured. Using SQLite for local development. Error: {str(e)}")
        return None
    
    return None

# Check if we should use Supabase
USE_SUPABASE = get_supabase_client() is not None

# Database connection helper - uses Supabase if configured, otherwise SQLite
def get_db_connection():
    """
    Get a database connection.
    
    Priority:
    1. Supabase (if configured via Streamlit secrets or environment variables)
    2. SQLite (for local development)
    
    ⚠️ CRITICAL: On Streamlit Cloud, SQLite file system is EPHEMERAL.
    The database file is LOST when app restarts. Use Supabase for production!
    """
    # If Supabase is configured, return a Supabase adapter
    supabase_client = get_supabase_client()
    if supabase_client:
        return SupabaseAdapter(supabase_client)
    
    # Otherwise, use SQLite (for local development)
    db_path = 'classroom.db'
    conn = sqlite3.connect(db_path, check_same_thread=False, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    return conn

# Supabase adapter class to make Supabase work like SQLite
class SupabaseAdapter:
    """Adapter class to make Supabase API work like SQLite connection"""
    def __init__(self, client: Client):
        self.client = client
        self.cursor_impl = SupabaseCursorAdapter(client)
    
    def cursor(self):
        return self.cursor_impl
    
    def commit(self):
        # Supabase commits automatically
        pass
    
    def close(self):
        # Supabase doesn't need explicit closing
        pass
    
    def execute(self, query, params=None):
        # For compatibility with existing code
        return self.cursor_impl.execute(query, params)

class SupabaseCursorAdapter:
    """Adapter to make Supabase queries work like SQLite cursor"""
    def __init__(self, client: Client):
        self.client = client
        self.last_result = None
    
    def execute(self, query, params=None):
        # Parse SQL and convert to Supabase calls
        # This is a simplified version - for production, you'd want a full SQL parser
        query_lower = query.strip().lower()
        
        if query_lower.startswith('select'):
            return self._handle_select(query, params)
        elif query_lower.startswith('insert'):
            return self._handle_insert(query, params)
        elif query_lower.startswith('update'):
            return self._handle_update(query, params)
        elif query_lower.startswith('delete'):
            return self._handle_delete(query, params)
        elif query_lower.startswith('create table'):
            return self._handle_create_table(query)
        elif query_lower.startswith('alter table'):
            return self._handle_alter_table(query)
        else:
            # For other queries (PRAGMA, etc.), just return empty result
            return self
    
    def _handle_select(self, query, params):
        # This is complex - would need SQL parsing
        # For now, we'll use a simpler approach: direct Supabase calls
        # The actual implementation will be done in the database helper functions
        return self
    
    def _handle_insert(self, query, params):
        # Similar - needs SQL parsing
        return self
    
    def _handle_update(self, query, params):
        return self
    
    def _handle_delete(self, query, params):
        return self
    
    def _handle_create_table(self, query):
        # Tables should be created via Supabase dashboard or migrations
        return self
    
    def _handle_alter_table(self, query):
        # Alter operations done via Supabase dashboard
        return self
    
    def fetchone(self):
        return self.last_result
    
    def fetchall(self):
        return self.last_result if isinstance(self.last_result, list) else [self.last_result] if self.last_result else []

# Context manager for database operations (ensures proper closing)
@contextmanager
def db_connection():
    """Context manager for database connections - ensures proper cleanup"""
    conn = None
    try:
        conn = get_db_connection()
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()

# Database initialization
def init_database():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT,
            email TEXT,
            phone TEXT,
            name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Add name column if it doesn't exist (for existing databases)
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN name TEXT')
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS newsletters (
            id TEXT PRIMARY KEY,
            title TEXT,
            content TEXT,
            date TEXT,
            teacher_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (teacher_id) REFERENCES users (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            title TEXT,
            description TEXT,
            event_date TEXT,
            event_time TEXT,
            location TEXT,
            max_attendees INTEGER,
            teacher_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (teacher_id) REFERENCES users (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS event_rsvps (
            id TEXT PRIMARY KEY,
            event_id TEXT,
            parent_id TEXT,
            attendees_count INTEGER,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (event_id) REFERENCES events (id),
            FOREIGN KEY (parent_id) REFERENCES users (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS assignments (
            id TEXT PRIMARY KEY,
            title TEXT,
            description TEXT,
            subject TEXT,
            due_date TEXT,
            word_list TEXT,
            memory_verse TEXT,
            teacher_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (teacher_id) REFERENCES users (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_progress (
            id TEXT PRIMARY KEY,
            student_id TEXT,
            assignment_id TEXT,
            word_list_progress TEXT,
            memory_verse_progress TEXT,
            completed BOOLEAN DEFAULT FALSE,
            submitted_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES users (id),
            FOREIGN KEY (assignment_id) REFERENCES assignments (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_activity (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            username TEXT,
            role TEXT,
            activity_type TEXT,
            ip_address TEXT,
            user_agent TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()

# Initialize database
init_database()

# Email configuration and functions
def get_email_config():
    """Get email configuration from session state or return defaults"""
    if 'email_config' not in st.session_state:
        st.session_state.email_config = {
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': 587,
            'sender_email': '',
            'sender_password': '',
            'use_tls': True
        }
    return st.session_state.email_config

def send_newsletter_email(newsletter_data, recipient_emails, pdf_data=None):
    """Send newsletter email to recipients"""
    try:
        config = get_email_config()
        
        if not config['sender_email'] or not config['sender_password']:
            return False, "Email configuration not set. Please configure email settings first."
        
        if not recipient_emails:
            return False, "No recipient email addresses found. Please add parent users with email addresses."
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = config['sender_email']
        msg['Subject'] = f"Classroom Newsletter: {newsletter_data['title']}"
        
        # Email body
        # Format newsletter content properly
        content_text = ""
        if 'left_column' in newsletter_data:
            content_text += "UPCOMING EVENTS:\n" + newsletter_data['left_column'].get('upcoming_events', '') + "\n\n"
            content_text += "LEARNING SNAPSHOT:\n" + newsletter_data['left_column'].get('learning_snapshot', '') + "\n\n"
            content_text += "IMPORTANT NEWS:\n" + newsletter_data['left_column'].get('important_news', '') + "\n\n"
        if 'right_column' in newsletter_data:
            content_text += "WORD LIST:\n" + newsletter_data['right_column'].get('word_list', '') + "\n\n"
            content_text += "PRACTICE AT HOME:\n" + newsletter_data['right_column'].get('practice_home', '') + "\n\n"
            content_text += "MEMORY VERSE:\n" + newsletter_data['right_column'].get('memory_verse', '') + "\n\n"
        
        body = f"""
Dear Parents and Students,

Please find attached the latest classroom newsletter from Mrs. Simms' 2nd Grade Class.

Newsletter: {newsletter_data['title']}
Date: {newsletter_data['date']}

{content_text}

Best regards,
Mrs. Simms
Washington Christian Academy
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Attach PDF if provided
        if pdf_data:
            attachment = MIMEBase('application', 'octet-stream')
            attachment.set_payload(pdf_data)
            encoders.encode_base64(attachment)
            attachment.add_header(
                'Content-Disposition',
                f'attachment; filename= "newsletter_{newsletter_data["date"]}.pdf"'
            )
            msg.attach(attachment)
        
        # Send email to all recipients
        server = smtplib.SMTP(config['smtp_server'], config['smtp_port'])
        
        if config['use_tls']:
            server.starttls()
        
        server.login(config['sender_email'], config['sender_password'])
        
        # Send to all recipients
        for recipient in recipient_emails:
            msg['To'] = recipient
            server.send_message(msg)
            del msg['To']  # Remove To field for next recipient
        
        server.quit()
        return True, f"Newsletter sent successfully to {len(recipient_emails)} recipients!"
        
    except Exception as e:
        return False, f"Error sending email: {str(e)}"

def get_parent_emails():
    """Get all parent email addresses from the database"""
    conn = get_db_connection()
    
    if isinstance(conn, SupabaseAdapter):
        supabase_client = conn.client
        parents_result = supabase_client.table('users').select('email').eq('role', 'parent').not_.is_('email', 'null').neq('email', '').execute()
        emails = [row.get('email') for row in parents_result.data] if parents_result.data else []
        conn.close()
    else:
        cursor = conn.cursor()
        cursor.execute('SELECT email FROM users WHERE role = "parent" AND email IS NOT NULL AND email != ""')
        emails = [row[0] for row in cursor.fetchall()]
        conn.close()
    return emails

def test_email_connection():
    """Test email connection without sending"""
    try:
        config = get_email_config()
        
        if not config['sender_email'] or not config['sender_password']:
            return False, "Email configuration not set"
        
        # Test SMTP connection
        server = smtplib.SMTP(config['smtp_server'], config['smtp_port'])
        if config['use_tls']:
            server.starttls()
        server.login(config['sender_email'], config['sender_password'])
        server.quit()
        
        return True, "Email connection test successful!"
        
    except Exception as e:
        return False, f"Email connection test failed: {str(e)}"

# Chatbot Functions
def chatbot_response(user_message: str, user_role: str) -> str:
    """Chatbot that answers common questions based on user role"""
    user_message_lower = user_message.lower().strip()
    
    # General questions (all users)
    if any(word in user_message_lower for word in ['hello', 'hi', 'hey', 'greeting']):
        return "Hello! I'm here to help you with the Classroom Management App. What would you like to know?"
    
    if any(word in user_message_lower for word in ['help', 'what can', 'how to', 'guide']):
        if user_role == 'admin':
            return """As an Admin, you can:
• Manage all users (admins, teachers, parents)
• Create teacher accounts
• Create parent accounts
• View system statistics
• Manage newsletters
• Full system access

What would you like to know more about?"""
        elif user_role == 'teacher':
            return """As a Teacher, you can:
• Create and manage newsletters
• Create events and manage RSVPs
• Create assignments
• View and manage students
• Create parent accounts
• Generate reports

What would you like help with?"""
        else:
            return """As a Parent, you can:
• View newsletters
• See upcoming events and RSVP
• View assignments
• Track your child's progress
• Download PDF newsletters

How can I help you today?"""
    
    if any(word in user_message_lower for word in ['newsletter', 'newsletters']):
        if user_role == 'teacher' or user_role == 'admin':
            return """To create a newsletter:
1. Go to the "Newsletter" tab
2. Click "Create New Newsletter"
3. Fill in the title, date, and content sections
4. Click "Create Newsletter"

To share with parents:
• Parents log in and view newsletters anytime
• You can download PDFs to share manually
• All newsletters are saved and accessible to parents"""
        else:
            return """To view newsletters:
1. Go to the "Newsletter" tab in your dashboard
2. Click on any newsletter to view it
3. Click "Download PDF" if you want a copy
4. All past newsletters are available here"""
    
    if any(word in user_message_lower for word in ['login', 'password', 'credentials']):
        return """Login Issues:
• Make sure you're using the correct username and password
• Contact your administrator if you forgot your password
• The app URL is: https://classroom-management-app-wca.streamlit.app

For new accounts, contact the administrator who created your account."""
    
    if any(word in user_message_lower for word in ['parent account', 'create parent', 'add parent']):
        if user_role == 'admin' or user_role == 'teacher':
            return """To create a parent account:
1. Go to the "Parents" tab
2. Click "Add New Parent Account"
3. Fill in: Username, Email, Password, Name, Phone, Student Name
4. Click "Create Parent Account"
5. Share the credentials with the parent securely"""
        else:
            return "Only teachers and admins can create parent accounts. Please contact your teacher or administrator."
    
    if any(word in user_message_lower for word in ['event', 'events', 'rsvp']):
        if user_role == 'teacher' or user_role == 'admin':
            return """To create an event:
1. Go to the "Events" tab
2. Click "Create New Event"
3. Fill in: Title, Description, Date, Time, Location, Max Attendees
4. Click "Create Event"

Parents can then RSVP through the Events tab."""
        else:
            return """To RSVP to an event:
1. Go to the "Events" tab
2. Find the event you want to attend
3. Click "RSVP" and enter the number of attendees
4. Add any notes if needed
5. Click "Submit RSVP"

You can see all upcoming events in the Events tab."""
    
    if any(word in user_message_lower for word in ['assignment', 'assignments', 'homework']):
        if user_role == 'teacher' or user_role == 'admin':
            return """To create an assignment:
1. Go to the "Assignments" tab
2. Click "Create New Assignment"
3. Fill in: Title, Description, Subject, Due Date, Word List, Memory Verse
4. Click "Create Assignment"

Parents and students can view assignments in their dashboard."""
        else:
            return """To view assignments:
1. Go to the "Assignments" tab
2. See all assignments with due dates
3. View word lists and memory verses
4. Track your child's progress on assignments"""
    
    if any(word in user_message_lower for word in ['app url', 'website', 'link', 'access']):
        return """The app is available at:
🌐 https://classroom-management-app-wca.streamlit.app

Works on any device - computer, tablet, or phone. Just open in your web browser!"""
    
    if any(word in user_message_lower for word in ['child', 'student', 'progress', 'my child']):
        if user_role == 'parent':
            return """To view your child's progress:
1. Go to the "My Child" tab
2. See assignments and progress
3. View performance on different subjects
4. Track completion of tasks

If you don't see your child's information, contact the teacher to link your account to your child."""
        else:
            return "This feature is for parents to view their child's progress. If you're a teacher, use the Students tab to manage student information."
    
    if any(word in user_message_lower for word in ['admin', 'administrator', 'system']):
        if user_role == 'admin':
            return """As an Admin, you have full system access:
• User Management: View and manage all users
• Teacher Management: Create and manage teacher accounts
• Parent Management: Create and manage parent accounts
• Newsletters: Full access to all newsletters
• System Info: View statistics and system details
• Settings: Configure system settings

What would you like to manage?"""
        else:
            return "Only users with admin role can access admin features. Please contact your administrator for admin-related requests."
    
    if any(word in user_message_lower for word in ['download', 'pdf', 'save']):
        return """To download newsletters as PDF:
1. Go to the Newsletter tab
2. Find the newsletter you want
3. Click "Download PDF" button
4. The PDF will download to your device

You can then save or share the PDF as needed."""
    
    if any(word in user_message_lower for word in ['contact', 'support', 'help', 'problem', 'issue', 'error']):
        return """For support:
• Contact your teacher or administrator
• Check the instructions document provided
• Make sure you're using the correct login credentials
• Try refreshing the page if something doesn't work

Technical support: Contact NM2TECH LLC at https://www.nm2tech.com"""
    
    if any(word in user_message_lower for word in ['forgot', 'reset', 'change password']):
        return """To reset or change your password:
• Contact your administrator (admin user)
• The administrator can view or reset your password
• In the future, a password change feature will be available

For now, only administrators can manage passwords."""
    
    # Default response if no match
    return """I'm here to help! Here are some things I can answer:
• How to use newsletters
• Creating events and RSVPs
• Managing assignments
• Parent account setup
• Login issues
• App features by role

Can you rephrase your question or ask about one of these topics?"""

def chatbot_interface(user_role: str):
    """Display chatbot interface"""
    st.subheader("💬 Help Chatbot")
    st.markdown("**Ask me anything about using the Classroom Management App!**")
    
    # Initialize chat history
    if "chatbot_messages" not in st.session_state:
        st.session_state.chatbot_messages = [
            {"role": "assistant", "content": "Hello! I'm your Classroom Management App assistant. How can I help you today?"}
        ]
    
    # Display chat messages
    for message in st.session_state.chatbot_messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Ask a question about the app..."):
        # Add user message
        st.session_state.chatbot_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)
        
        # Get chatbot response
        response = chatbot_response(prompt, user_role)
        
        # Add assistant response
        st.session_state.chatbot_messages.append({"role": "assistant", "content": response})
        with st.chat_message("assistant"):
            st.write(response)
    
    # Quick action buttons
    st.markdown("**Quick Questions:**")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📰 How to create newsletter?", key="chatbot_newsletter"):
            st.session_state.chatbot_messages.append({"role": "user", "content": "How do I create a newsletter?"})
            response = chatbot_response("How do I create a newsletter?", user_role)
            st.session_state.chatbot_messages.append({"role": "assistant", "content": response})
            st.rerun()
    
    with col2:
        if st.button("👥 Create parent account?", key="chatbot_parent"):
            st.session_state.chatbot_messages.append({"role": "user", "content": "How do I create a parent account?"})
            response = chatbot_response("How do I create a parent account?", user_role)
            st.session_state.chatbot_messages.append({"role": "assistant", "content": response})
            st.rerun()
    
    with col3:
        if st.button("❓ What can I do?", key="chatbot_help"):
            st.session_state.chatbot_messages.append({"role": "user", "content": "What can I do?"})
            response = chatbot_response("What can I do?", user_role)
            st.session_state.chatbot_messages.append({"role": "assistant", "content": response})
            st.rerun()
    
    # Clear chat button
    if st.button("🗑️ Clear Chat", key="chatbot_clear"):
        st.session_state.chatbot_messages = [
            {"role": "assistant", "content": "Chat cleared! How can I help you?"}
        ]
        st.rerun()

def chatbot_interface_compact(user_role: str):
    """Compact chatbot interface for popup"""
    # Initialize chat history (use same messages as main chatbot)
    if "chatbot_messages" not in st.session_state:
        st.session_state.chatbot_messages = [
            {"role": "assistant", "content": "Hello! I'm your Classroom Management App assistant. How can I help you today?"}
        ]
    
    # Display chat messages in a scrollable container
    st.markdown('<div style="max-height: 400px; overflow-y: auto; margin-bottom: 10px;">', unsafe_allow_html=True)
    for message in st.session_state.chatbot_messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Chat input
    if prompt := st.chat_input("Ask a question..."):
        # Add user message
        st.session_state.chatbot_messages.append({"role": "user", "content": prompt})
        
        # Get chatbot response
        response = chatbot_response(prompt, user_role)
        
        # Add assistant response
        st.session_state.chatbot_messages.append({"role": "assistant", "content": response})
        st.rerun()
    
    # Quick action buttons (compact)
    with st.expander("💡 Quick Questions", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📰 Newsletter?", key="popup_newsletter"):
                st.session_state.chatbot_messages.append({"role": "user", "content": "How do I create a newsletter?"})
                response = chatbot_response("How do I create a newsletter?", user_role)
                st.session_state.chatbot_messages.append({"role": "assistant", "content": response})
                st.rerun()
            if st.button("👥 Parent account?", key="popup_parent"):
                st.session_state.chatbot_messages.append({"role": "user", "content": "How do I create a parent account?"})
                response = chatbot_response("How do I create a parent account?", user_role)
                st.session_state.chatbot_messages.append({"role": "assistant", "content": response})
                st.rerun()
        with col2:
            if st.button("❓ What can I do?", key="popup_help"):
                st.session_state.chatbot_messages.append({"role": "user", "content": "What can I do?"})
                response = chatbot_response("What can I do?", user_role)
                st.session_state.chatbot_messages.append({"role": "assistant", "content": response})
                st.rerun()
            if st.button("🗑️ Clear", key="popup_clear"):
                st.session_state.chatbot_messages = [
                    {"role": "assistant", "content": "Chat cleared! How can I help you?"}
                ]
                st.rerun()

# Database helper functions for Supabase compatibility
def db_query(conn, query, params=None):
    """Execute a query and return results - works with both SQLite and Supabase"""
    if isinstance(conn, SupabaseAdapter):
        # For Supabase, we need to parse SQL and convert to API calls
        # This is a simplified version - for complex queries, we'll use direct Supabase calls
        supabase_client = conn.client
        
        # Simple SELECT query parser
        query_lower = query.strip().lower()
        if 'select' in query_lower and 'from users' in query_lower:
            # Handle user authentication query
            if 'where username' in query_lower and params:
                result = supabase_client.table('users').select('*').eq('username', params[0]).eq('password', params[1]).execute()
                if result.data:
                    user = result.data[0]
                    # Convert to tuple format for compatibility
                    return type('Row', (), {
                        '__getitem__': lambda self, idx: [
                            user.get('id'),
                            user.get('username'),
                            user.get('password'),
                            user.get('role'),
                            user.get('email'),
                            user.get('phone'),
                            user.get('name', ''),
                            user.get('created_at')
                        ][idx],
                        '__len__': lambda self: 8
                    })()
            # Handle general SELECT from users
            elif 'where username' in query_lower and params:
                result = supabase_client.table('users').select('*').eq('username', params[0]).execute()
                if result.data:
                    user = result.data[0]
                    return type('Row', (), {
                        '__getitem__': lambda self, idx: [
                            user.get('id'),
                            user.get('username'),
                            user.get('password'),
                            user.get('role'),
                            user.get('email'),
                            user.get('phone'),
                            user.get('name', ''),
                            user.get('created_at')
                        ][idx] if idx < 8 else None,
                        '__len__': lambda self: 8
                    })()
        return None
    else:
        # SQLite - use cursor
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        return cursor.fetchone()

def db_execute(conn, query, params=None):
    """Execute a query (INSERT, UPDATE, DELETE) - works with both SQLite and Supabase"""
    if isinstance(conn, SupabaseAdapter):
        supabase_client = conn.client
        query_lower = query.strip().lower()
        
        if 'insert into users' in query_lower and params:
            data = {
                'id': params[0],
                'username': params[1],
                'password': params[2],
                'role': params[3],
                'email': params[4] if len(params) > 4 else None,
                'phone': params[5] if len(params) > 5 else None,
                'name': params[6] if len(params) > 6 else None
            }
            result = supabase_client.table('users').insert(data).execute()
            return result.data[0] if result.data else None
        
        # For other queries, we'd need more parsing
        # For now, return None (will be handled by specific functions)
        return None
    else:
        # SQLite
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        conn.commit()
        return cursor.rowcount

def db_count(conn, table, filters=None):
    """Count rows in a table"""
    if isinstance(conn, SupabaseAdapter):
        supabase_client = conn.client
        query = supabase_client.table(table).select('id', count='exact')
        if filters:
            for key, value in filters.items():
                query = query.eq(key, value)
        result = query.execute()
        return result.count if hasattr(result, 'count') else len(result.data) if result.data else 0
    else:
        cursor = conn.cursor()
        query = f"SELECT COUNT(*) FROM {table}"
        params = []
        if filters:
            conditions = []
            for key, value in filters.items():
                conditions.append(f"{key} = ?")
                params.append(value)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
        cursor.execute(query, params)
        result = cursor.fetchone()
        return result[0] if result else 0

# Authentication
def authenticate_user(username: str, password: str) -> Optional[Dict]:
    conn = get_db_connection()
    
    # Use Supabase if available
    if isinstance(conn, SupabaseAdapter):
        supabase_client = conn.client
        result = supabase_client.table('users').select('*').eq('username', username).eq('password', password).execute()
        
        if result.data and len(result.data) > 0:
            user = result.data[0]
            name_value = user.get('name', '').strip() if user.get('name') else None
            return {
                'id': user.get('id'),
                'username': user.get('username'),
                'role': user.get('role'),
                'email': user.get('email'),
                'phone': user.get('phone'),
                'name': name_value
            }
        conn.close()
        return None
    else:
        # SQLite
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, username, password, role, email, phone, 
                   COALESCE(name, '') as name, created_at
            FROM users 
            WHERE username = ? AND password = ?
        ''', (username, password))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            name_value = user[6].strip() if user[6] and user[6].strip() else None
            return {
                'id': user[0],
                'username': user[1],
                'role': user[3],
                'email': user[4],
                'phone': user[5],
                'name': name_value
            }
        return None

def log_user_activity(user_id: str, username: str, role: str, activity_type: str = "login"):
    """Log user activity (login, logout, etc.) to the database"""
    try:
        conn = get_db_connection()
        activity_id = str(uuid.uuid4())
        
        # Try to get IP address and user agent from Streamlit headers
        ip_address = "Unknown"
        user_agent = "Unknown"
        
        try:
            # Streamlit doesn't directly expose request headers, but we can try to get them
            # For now, we'll use a placeholder - in production, you might want to use
            # a custom component or middleware to capture this
            if hasattr(st, 'request') and hasattr(st.request, 'headers'):
                ip_address = st.request.headers.get('X-Forwarded-For', 'Unknown')
                user_agent = st.request.headers.get('User-Agent', 'Unknown')
        except:
            pass
        
        activity_data = {
            'id': activity_id,
            'user_id': user_id,
            'username': username,
            'role': role,
            'activity_type': activity_type,
            'ip_address': ip_address,
            'user_agent': user_agent
        }
        
        if isinstance(conn, SupabaseAdapter):
            # Supabase insert
            supabase_client = conn.client
            try:
                supabase_client.table('user_activity').insert(activity_data).execute()
            except Exception as e:
                # Table might not exist in Supabase yet - that's okay, we'll handle it
                pass
            conn.close()
        else:
            # SQLite insert
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO user_activity (id, user_id, username, role, activity_type, ip_address, user_agent)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                activity_data['id'],
                activity_data['user_id'],
                activity_data['username'],
                activity_data['role'],
                activity_data['activity_type'],
                activity_data['ip_address'],
                activity_data['user_agent']
            ))
            conn.commit()
            conn.close()
    except Exception as e:
        # Silently fail - don't break login if logging fails
        pass

def create_default_users():
    conn = get_db_connection()
    
    # Use Supabase if available
    if isinstance(conn, SupabaseAdapter):
        supabase_client = conn.client
        
        # Check if admin exists
        admin_result = supabase_client.table('users').select('*').eq('username', 'admin').execute()
        if not admin_result.data:
            # Create admin account
            supabase_client.table('users').insert({
                'id': str(uuid.uuid4()),
                'username': 'admin',
                'password': 'admin123',
                'role': 'admin',
                'email': 'admin@nm2tech.com',
                'phone': ''
            }).execute()
        
        # Check total user count
        count_result = supabase_client.table('users').select('id', count='exact').execute()
        user_count = count_result.count if hasattr(count_result, 'count') else len(count_result.data) if count_result.data else 0
        
        if user_count == 0:
            # Create default teacher
            supabase_client.table('users').insert({
                'id': str(uuid.uuid4()),
                'username': 'mrs.simms',
                'password': 'password123',
                'role': 'teacher',
                'email': 'Ksimms@washingtonchristian.org',
                'phone': '240-390-0429'
            }).execute()
            
            # Create sample parents
            parents = [
                {'username': 'parent1', 'password': 'password123', 'role': 'parent', 'email': 'parent1@email.com', 'phone': '555-0001'},
                {'username': 'parent2', 'password': 'password123', 'role': 'parent', 'email': 'parent2@email.com', 'phone': '555-0002'},
                {'username': 'parent3', 'password': 'password123', 'role': 'parent', 'email': 'parent3@email.com', 'phone': '555-0003'}
            ]
            
            for parent in parents:
                parent['id'] = str(uuid.uuid4())
                supabase_client.table('users').insert(parent).execute()
        
        conn.close()
    else:
        # SQLite
        cursor = conn.cursor()
        
        # Always ensure admin account exists (even if database already has users)
        cursor.execute('SELECT * FROM users WHERE username = ?', ('admin',))
        admin_exists = cursor.fetchone()
        
        if not admin_exists:
            # Create admin account if it doesn't exist
            cursor.execute('''
                INSERT INTO users (id, username, password, role, email, phone)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (str(uuid.uuid4()), 'admin', 'admin123', 'admin', 'admin@nm2tech.com', ''))
        
        # Check if users exist
        cursor.execute('SELECT COUNT(*) FROM users')
        count = cursor.fetchone()[0]
        
        if count == 0:
            # Create default teacher
            cursor.execute('''
                INSERT INTO users (id, username, password, role, email, phone)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (str(uuid.uuid4()), 'mrs.simms', 'password123', 'teacher', 'Ksimms@washingtonchristian.org', '240-390-0429'))
            
            # Create sample parents
            parents = [
                ('parent1', 'password123', 'parent', 'parent1@email.com', '555-0001'),
                ('parent2', 'password123', 'parent', 'parent2@email.com', '555-0002'),
                ('parent3', 'password123', 'parent', 'parent3@email.com', '555-0003')
            ]
            
            for username, password, role, email, phone in parents:
                cursor.execute('''
                    INSERT INTO users (id, username, password, role, email, phone)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (str(uuid.uuid4()), username, password, role, email, phone))
        
        conn.commit()
        conn.close()

def create_sample_newsletter():
    conn = get_db_connection()
    
    # Use Supabase if available
    if isinstance(conn, SupabaseAdapter):
        supabase_client = conn.client
        
        # Check if sample newsletter exists
        newsletter_result = supabase_client.table('newsletters').select('id', count='exact').execute()
        count = newsletter_result.count if hasattr(newsletter_result, 'count') else len(newsletter_result.data) if newsletter_result.data else 0
        
        # Also check if we've already created a sample newsletter in this session
        if count == 0 and not st.session_state.get('sample_newsletter_created', False):
            # Get teacher ID
            teacher_result = supabase_client.table('users').select('id').eq('username', 'mrs.simms').execute()
            teacher_data = teacher_result.data[0] if teacher_result.data else None
            
            if teacher_data:
                sample_content = {
                    'title': 'OUR CLASSROOM newsletter',
                    'date': 'October 03, 2025',
                    'is_sample': True,
                    'left_column': {
                        'upcoming_events': '''9/26 - Half day Q1 midterm grading day (school dismisses at 12 noon)
9/26 - Day of Fasting, Prayer & Praise
10/2 - Literacy Night (Next Thursday)
10/9 - Muffins for Moms
10/31 - Field Trip (Bible Museum)''',
                        'learning_snapshot': '''BIBLE/TFT: Unit 1 - The Life of Christ, studying the book of James. TFT: Image Bearers - Who we are as Image Bearers of God. As we learn to respect God and respect others, ourselves, and property.

LANGUAGE ARTS: Handwriting, Skills 1 Activity. Fables and Fairy Tales. We have also read Beauty and the Beast. We are now reading I Am Rosa Parks.

MATH: Sadlier Math 2 Chapter 2 - Subtraction to 20 (related addition facts and strategies). Test next week.

SCIENCE: Cycles of Nature. Seasons, water cycle, life cycles, day & night.

SOCIAL STUDIES: Geography - Maps and landforms.''',
                        'important_news': '''Happy Fall! Our first Field Trip has been posted for 10/31, see details in upcoming events.

We are excited to announce our first ever Literacy Night at WCA. This year's theme is "Get Caught Reading!" We would love to invite families with students in grades K-4 to attend and experience literature in a fun and hands-on way. RSVP's are on flyers with books to sign and chairs are available for purchase as well as several age-appropriate experiences. All family members are welcome. Please sign up soon!'''
                    },
                    'right_column': {
                        'word_list': '''sand sang sank
hunt hung hunk
thin thing think
should why what''',
                        'practice_home': '''Read daily to your child for 20 mins as part of our nightly homework assignments.''',
                        'memory_verse': '''I will exalt you, my God and King; I will praise your name forever and ever. Every day I will praise you and extol your name forever and ever.'''
                    }
                }
                
                newsletter_data = {
                    'id': str(uuid.uuid4()),
                    'title': sample_content['title'],
                    'content': json.dumps(sample_content),
                    'date': '2025-10-03',
                    'teacher_id': teacher_data['id']
                }
                
                supabase_client.table('newsletters').insert(newsletter_data).execute()
                st.session_state.sample_newsletter_created = True
        
        conn.close()
    else:
        # SQLite
        cursor = conn.cursor()
        
        # Check if sample newsletter exists
        cursor.execute('SELECT COUNT(*) FROM newsletters')
        count = cursor.fetchone()[0]
        
        # Also check if we've already created a sample newsletter in this session
        if count == 0 and not st.session_state.get('sample_newsletter_created', False):
            # Get teacher ID
            cursor.execute('SELECT id FROM users WHERE username = ?', ('mrs.simms',))
            teacher = cursor.fetchone()
            
            if teacher:
                sample_content = {
                    'title': 'OUR CLASSROOM newsletter',
                    'date': 'October 03, 2025',
                    'is_sample': True,
                    'left_column': {
                        'upcoming_events': '''9/26 - Half day Q1 midterm grading day (school dismisses at 12 noon)
9/26 - Day of Fasting, Prayer & Praise
10/2 - Literacy Night (Next Thursday)
10/9 - Muffins for Moms
10/31 - Field Trip (Bible Museum)''',
                        'learning_snapshot': '''BIBLE/TFT: Unit 1 - The Life of Christ, studying the book of James. TFT: Image Bearers - Who we are as Image Bearers of God. As we learn to respect God and respect others, ourselves, and property.

LANGUAGE ARTS: Handwriting, Skills 1 Activity. Fables and Fairy Tales. We have also read Beauty and the Beast. We are now reading I Am Rosa Parks.

MATH: Sadlier Math 2 Chapter 2 - Subtraction to 20 (related addition facts and strategies). Test next week.

SCIENCE: Cycles of Nature. Seasons, water cycle, life cycles, day & night.

SOCIAL STUDIES: Geography - Maps and landforms.''',
                        'important_news': '''Happy Fall! Our first Field Trip has been posted for 10/31, see details in upcoming events.

We are excited to announce our first ever Literacy Night at WCA. This year's theme is "Get Caught Reading!" We would love to invite families with students in grades K-4 to attend and experience literature in a fun and hands-on way. RSVP's are on flyers with books to sign and chairs are available for purchase as well as several age-appropriate experiences. All family members are welcome. Please sign up soon!'''
                    },
                    'right_column': {
                        'word_list': '''sand sang sank
hunt hung hunk
thin thing think
should why what''',
                        'practice_home': '''Read daily to your child for 20 mins as part of our nightly homework assignments.''',
                        'memory_verse': '''I will exalt you, my God and King; I will praise your name forever and ever. Every day I will praise you and extol your name forever and ever.'''
                    }
                }
                
                cursor.execute('''
                    INSERT INTO newsletters (id, title, content, date, teacher_id)
                    VALUES (?, ?, ?, ?, ?)
                ''', (str(uuid.uuid4()), sample_content['title'], json.dumps(sample_content), 
                      '2025-10-03', teacher[0]))
                
                st.session_state.sample_newsletter_created = True
        
        conn.commit()
        conn.close()

def debug_users():
    """Debug function to check users in database"""
    conn = get_db_connection()
    
    if isinstance(conn, SupabaseAdapter):
        supabase_client = conn.client
        users_result = supabase_client.table('users').select('username, role, email').execute()
        users_data = users_result.data if users_result.data else []
        users = [(u.get('username'), u.get('role'), u.get('email')) for u in users_data]
        conn.close()
    else:
        cursor = conn.cursor()
        cursor.execute('SELECT username, role, email FROM users')
        users = cursor.fetchall()
        conn.close()
    return users

def clear_newsletters():
    """Clear all newsletters from database"""
    conn = get_db_connection()
    
    if isinstance(conn, SupabaseAdapter):
        supabase_client = conn.client
        try:
            # Delete all newsletters
            supabase_client.table('newsletters').delete().neq('id', '').execute()
            st.success("All newsletters cleared!")
        except Exception as e:
            st.error(f"Error clearing newsletters: {str(e)}")
        conn.close()
    else:
        # SQLite
        cursor = conn.cursor()
        cursor.execute('DELETE FROM newsletters')
        conn.commit()
        conn.close()
        st.success("All newsletters cleared!")

def generate_newsletter_pdf(newsletter_data):
    """Generate a PDF version of the newsletter"""
    try:
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
        
        # Get styles
        styles = getSampleStyleSheet()
        
        # Create custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=1,  # Center alignment
            textColor=colors.HexColor('#2c3e50')
        )
        
        date_style = ParagraphStyle(
            'CustomDate',
            parent=styles['Normal'],
            fontSize=14,
            spaceAfter=20,
            alignment=1,  # Center alignment
            textColor=colors.HexColor('#2c3e50'),
            backColor=colors.HexColor('#f1c40f'),
            borderWidth=1,
            borderColor=colors.HexColor('#f1c40f'),
            borderRadius=5
        )
        
        section_style = ParagraphStyle(
            'CustomSection',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=12,
            spaceBefore=20,
            textColor=colors.HexColor('#2c3e50')
        )
        
        content_style = ParagraphStyle(
            'CustomContent',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=12,
            leftIndent=20
        )
        
        teacher_style = ParagraphStyle(
            'TeacherStyle',
            parent=styles['Normal'],
            fontSize=12,
            spaceAfter=20,
            alignment=2,  # Right alignment
            textColor=colors.HexColor('#2c3e50')
        )
        
        # Build the PDF content
        story = []
        
        # Title
        story.append(Paragraph(newsletter_data.get('title', 'Newsletter'), title_style))
        story.append(Spacer(1, 12))
        
        # Date
        story.append(Paragraph(newsletter_data.get('date', ''), date_style))
        story.append(Spacer(1, 20))
        
        # Teacher info
        teacher_info = """
        <b>MRS. SIMMS</b><br/>
        Ksimms@washingtonchristian.org<br/>
        240-390-0429
        """
        story.append(Paragraph(teacher_info, teacher_style))
        story.append(Spacer(1, 20))
        
        
        # Left column content
        if 'left_column' in newsletter_data:
            left_column = newsletter_data['left_column']
            
            if left_column.get('upcoming_events'):
                story.append(Paragraph("<b>UPCOMING EVENTS</b>", section_style))
                story.append(Paragraph(left_column['upcoming_events'].replace('\n', '<br/>'), content_style))
                story.append(Spacer(1, 12))
            
            if left_column.get('learning_snapshot'):
                story.append(Paragraph("<b>OUR LEARNING SNAPSHOT</b>", section_style))
                story.append(Paragraph(left_column['learning_snapshot'].replace('\n', '<br/>'), content_style))
                story.append(Spacer(1, 12))
            
            if left_column.get('important_news'):
                story.append(Paragraph("<b>IMPORTANT NEWS</b>", section_style))
                story.append(Paragraph(left_column['important_news'].replace('\n', '<br/>'), content_style))
                story.append(Spacer(1, 12))
        
        # Right column content
        if 'right_column' in newsletter_data:
            right_column = newsletter_data['right_column']
            
            if right_column.get('word_list'):
                story.append(Paragraph("<b>WORD LIST</b>", section_style))
                story.append(Paragraph(right_column['word_list'].replace('\n', '<br/>'), content_style))
                story.append(Spacer(1, 12))
            
            if right_column.get('practice_home'):
                story.append(Paragraph("<b>PRACTICE @ HOME</b>", section_style))
                story.append(Paragraph(right_column['practice_home'].replace('\n', '<br/>'), content_style))
                story.append(Spacer(1, 12))
            
            if right_column.get('memory_verse'):
                story.append(Paragraph("<b>MEMORY VERSE</b>", section_style))
                story.append(Paragraph("Psalm 145:1-2 NIV", content_style))
                story.append(Paragraph(right_column['memory_verse'].replace('\n', '<br/>'), content_style))
                story.append(Spacer(1, 12))
        
        # Footer
        footer_style = ParagraphStyle(
            'CustomFooter',
            parent=styles['Normal'],
            fontSize=8,
            alignment=1,  # Center alignment
            textColor=colors.HexColor('#7f8c8d'),
            fontStyle='italic'
        )
        story.append(Paragraph("THE LANGUAGE OF LEARNING", footer_style))
        story.append(Spacer(1, 20))
        story.append(Paragraph("Designed by <b>NM2TECH LLC</b> - Technology Simplified", footer_style))
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()
        
    except Exception as e:
        print(f"Error in PDF generation: {str(e)}")
        raise e

# Create default users and sample data
create_default_users()

# Sample newsletter creation is disabled by default
# It will only be created manually via the "Load Sample Data" button in the UI
# This prevents newsletters from being auto-recreated when deleted
# Uncomment the code below if you want to auto-create sample newsletter on initial setup only

# conn = get_db_connection()
# cursor = conn.cursor()
# cursor.execute('SELECT COUNT(*) FROM newsletters')
# newsletter_count = cursor.fetchone()[0]
# conn.close()
# 
# # Only create sample newsletter once on very first run (completely fresh database)
# # Once users start using the app, this won't run anymore
# if newsletter_count == 0:
#     create_sample_newsletter()

# Main app
def main():
    st.title("🏫 WCA Classroom Manager")
    st.markdown("**Washington Christian Academy - Mrs. Simms' 2nd Grade Class**")
    
    # Sidebar for authentication
    if 'user' not in st.session_state:
        st.sidebar.title("Login")
        username = st.sidebar.text_input("Username")
        password = st.sidebar.text_input("Password", type="password")
        
        if st.sidebar.button("Login"):
            user = authenticate_user(username, password)
            if user:
                # Log user login activity
                log_user_activity(user['id'], user['username'], user['role'], "login")
                st.session_state.user = user
                st.sidebar.success(f"Logged in as {user['role']}: {user['username']}")
                st.rerun()
            else:
                st.sidebar.error("Invalid credentials. Please check your username and password.")
        
        st.sidebar.markdown("---")
        st.sidebar.info("💡 Contact your administrator for login credentials")
        
        # NM2Tech branding in sidebar
        st.sidebar.markdown("---")
        st.sidebar.markdown("""
        <div style="text-align: center; padding: 10px;">
            <p style="color: #6c757d; font-size: 0.8em; margin: 0;">
                <strong>Designed by</strong><br>
                <a href="https://www.nm2tech.com" target="_blank" style="color: #007bff; font-weight: bold; text-decoration: none;">NM2TECH LLC</a><br>
                Technology Simplified
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Show welcome message
        st.info("👋 Welcome! Please login to access the classroom management system.")
        
        # Footer at the bottom of login page
        st.markdown("---")
        st.markdown("""
        <div style="text-align: center; padding: 20px; background-color: #f8f9fa; border-radius: 8px; margin-top: 30px;">
            <p style="color: #6c757d; font-size: 0.9em; margin: 0;">
                <strong>Designed by</strong> 
                <a href="https://www.nm2tech.com" target="_blank" style="color: #007bff; font-weight: bold; text-decoration: none;">NM2TECH LLC</a> 
                - Technology Simplified
            </p>
            <p style="color: #6c757d; font-size: 0.8em; margin: 5px 0 0 0;">
                Empowering Education Through Technology
            </p>
        </div>
        """, unsafe_allow_html=True)
        return
    
    # User is logged in
    user = st.session_state.user
    
    # Floating chatbot button in sidebar (always visible)
    with st.sidebar:
        st.markdown("---")
        # Toggle chatbot visibility
        chatbot_open = st.session_state.get('show_chatbot_popup', False)
        if st.button("💬 Help Chatbot", 
                     type="primary", use_container_width=True, key="toggle_chatbot"):
            st.session_state.show_chatbot_popup = not chatbot_open
            st.rerun()
    
    # Chatbot popup - appears at top of page when button is clicked
    if st.session_state.get('show_chatbot_popup', False):
        # Create prominent chatbot popup at top of page
        st.markdown("---")
        with st.container():
            # Header with close button
            col1, col2 = st.columns([5, 1])
            with col1:
                st.markdown("### 💬 Help Chatbot - Ask Me Anything!")
            with col2:
                if st.button("✕ Close Chatbot", key="close_chatbot", type="secondary"):
                    st.session_state.show_chatbot_popup = False
                    st.rerun()
            
            # Chatbot interface in popup with border
            st.markdown('<div style="border: 2px solid #007bff; border-radius: 10px; padding: 15px; background-color: #f8f9fa; margin: 10px 0;">', unsafe_allow_html=True)
            
            chatbot_interface_compact(user['role'])
            
            st.markdown('</div>', unsafe_allow_html=True)
        st.markdown("---")
    
    # Personalize greeting based on role
    if user['role'] == 'parent':
        # Use stored name first, then fallback to email or username
        parent_name = user.get('name', '')
        if parent_name:
            welcome_message = f"Welcome, {parent_name}!"
        else:
            # Try to extract name from email or use username in a friendly way
            email = user.get('email', '')
            if email:
                # Extract name from email (e.g., "john.smith@email.com" -> "John Smith")
                email_name = email.split('@')[0].replace('.', ' ').title()
                welcome_message = f"Welcome, {email_name}!"
            else:
                # Use username if no email
                username = user['username'].replace('.', ' ').replace('_', ' ').title()
                welcome_message = f"Welcome, {username}!"
        st.sidebar.success(welcome_message)
        st.sidebar.info("👨‍👩‍👧‍👦 Parent Access")
    elif user['role'] == 'teacher':
        # For teachers, use their username or email name
        email = user.get('email', '')
        if email and 'simms' in email.lower():
            st.sidebar.success("Welcome, Mrs. Simms!")
        else:
            username = user['username'].replace('.', ' ').replace('_', ' ').title()
            st.sidebar.success(f"Welcome, {username}!")
        st.sidebar.info("👩‍🏫 Teacher Dashboard")
    elif user['role'] == 'admin':
        st.sidebar.success("Welcome, Administrator!")
        st.sidebar.info("👑 Admin Dashboard")
    else:
        st.sidebar.success(f"Welcome, {user['username']}!")
        st.sidebar.info(f"Role: {user['role']}")
    
    if st.sidebar.button("Logout"):
        # Log user logout activity
        if 'user' in st.session_state:
            user = st.session_state.user
            log_user_activity(user['id'], user['username'], user['role'], "logout")
        del st.session_state.user
        st.rerun()
    
    # NM2Tech branding in sidebar for logged-in users
    st.sidebar.markdown("---")
    st.sidebar.markdown("""
    <div style="text-align: center; padding: 10px;">
        <p style="color: #6c757d; font-size: 0.8em; margin: 0;">
            <strong>Designed by</strong><br>
            <a href="https://www.nm2tech.com" target="_blank" style="color: #007bff; font-weight: bold; text-decoration: none;">NM2TECH LLC</a><br>
            Technology Simplified
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Main content based on user role
    if user['role'] == 'admin':
        admin_dashboard()
    elif user['role'] == 'teacher':
        teacher_dashboard()
    elif user['role'] == 'parent':
        parent_dashboard()
    elif user['role'] == 'student':
        student_dashboard()
    else:
        st.error(f"Invalid user role: {user['role']}")
        st.write(f"Debug info: {user}")

def admin_dashboard():
    st.header("👑 Admin Dashboard")
    st.markdown("**Full System Management - Manage Teachers, Parents, and Everything**")
    
    # Navigation tabs
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "👥 User Management", "👩‍🏫 Teachers", "👨‍👩‍👧‍👦 Parents", "📰 Newsletters", "📊 System Info", "📊 User Activity", "⚙️ Settings"
    ])
    
    with tab1:
        admin_user_management()
    
    with tab2:
        admin_teacher_management()
    
    with tab3:
        parent_user_management()  # Reuse the parent management function
    
    with tab4:
        newsletter_management()  # Reuse newsletter management
    
    with tab5:
        admin_system_info()
    
    with tab6:
        admin_user_activity()
    
    with tab7:
        admin_settings()
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; padding: 20px; background-color: #f8f9fa; border-radius: 8px; margin-top: 30px;">
        <p style="color: #6c757d; font-size: 0.9em; margin: 0;">
            <strong>Designed by</strong> 
            <a href="https://www.nm2tech.com" target="_blank" style="color: #007bff; font-weight: bold; text-decoration: none;">NM2TECH LLC</a> 
            - Technology Simplified
        </p>
    </div>
    """, unsafe_allow_html=True)

def teacher_dashboard():
    st.header("👩‍🏫 Teacher Dashboard")
    
    # Navigation tabs
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📰 Newsletter", "📅 Events", "📝 Assignments", "👥 Students", "👨‍👩‍👧‍👦 Parents", "📊 Reports"
    ])
    
    with tab1:
        newsletter_management()
    
    with tab2:
        event_management()
    
    with tab3:
        assignment_management()
    
    with tab4:
        student_management()
    
    with tab5:
        parent_user_management()
    
    with tab6:
        reports_dashboard()
    
    # Footer at the bottom of teacher dashboard
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; padding: 20px; background-color: #f8f9fa; border-radius: 8px; margin-top: 30px;">
        <p style="color: #6c757d; font-size: 0.9em; margin: 0;">
            <strong>Designed by</strong> 
            <a href="https://www.nm2tech.com" target="_blank" style="color: #007bff; font-weight: bold; text-decoration: none;">NM2TECH LLC</a> 
            - Technology Simplified
        </p>
        <p style="color: #6c757d; font-size: 0.8em; margin: 5px 0 0 0;">
            Empowering Education Through Technology
        </p>
    </div>
    """, unsafe_allow_html=True)

def student_dashboard():
    user = st.session_state.user
    # Personalize dashboard header with student's name
    student_name = user.get('name', '')
    if student_name:
        dashboard_title = f"👨‍🎓 Welcome, {student_name}!"
    else:
        # Fallback to username if name not available
        username = user['username'].replace('.', ' ').replace('_', ' ').title()
        dashboard_title = f"👨‍🎓 Welcome, {username}!"
    
    st.header(dashboard_title)
    st.markdown("**Student Dashboard - View assignments and track your progress**")
    
    # Navigation tabs
    tab1, tab2, tab3 = st.tabs([
        "📝 My Assignments", "📰 Newsletter", "📅 Events"
    ])
    
    with tab1:
        view_student_assignments()
    
    with tab2:
        view_newsletter()
    
    with tab3:
        view_events()
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; padding: 20px; background-color: #f8f9fa; border-radius: 8px; margin-top: 30px;">
        <p style="color: #6c757d; font-size: 0.9em; margin: 0;">
            <strong>Designed by</strong> 
            <a href="https://www.nm2tech.com" target="_blank" style="color: #007bff; font-weight: bold; text-decoration: none;">NM2TECH LLC</a> 
            - Technology Simplified
        </p>
    </div>
    """, unsafe_allow_html=True)

def parent_dashboard():
    user = st.session_state.user
    # Personalize dashboard header with parent's name
    parent_name = user.get('name', '')
    if parent_name:
        dashboard_title = f"👨‍👩‍👧‍👦 Welcome, {parent_name}!"
    else:
        # Fallback to email or username if name not available
        email = user.get('email', '')
        if email:
            parent_name = email.split('@')[0].replace('.', ' ').title()
            dashboard_title = f"👨‍👩‍👧‍👦 Welcome, {parent_name}!"
        else:
            username = user['username'].replace('.', ' ').replace('_', ' ').title()
            dashboard_title = f"👨‍👩‍👧‍👦 Welcome, {username}!"
    
    st.header(dashboard_title)
    st.markdown("**Parent Dashboard - View your child's progress, newsletters, and events**")
    
    # Navigation tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📰 Newsletter", "📅 Events", "📝 Assignments", "👶 My Child"
    ])
    
    with tab1:
        view_newsletter()
    
    with tab2:
        view_events()
    
    with tab3:
        view_assignments()
    
    with tab4:
        view_child_progress()
    
    # Footer at the bottom of parent dashboard
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; padding: 20px; background-color: #f8f9fa; border-radius: 8px; margin-top: 30px;">
        <p style="color: #6c757d; font-size: 0.9em; margin: 0;">
            <strong>Designed by</strong> 
            <a href="https://www.nm2tech.com" target="_blank" style="color: #007bff; font-weight: bold; text-decoration: none;">NM2TECH LLC</a> 
            - Technology Simplified
        </p>
        <p style="color: #6c757d; font-size: 0.8em; margin: 5px 0 0 0;">
            Empowering Education Through Technology
        </p>
    </div>
    """, unsafe_allow_html=True)

def newsletter_management():
    st.subheader("📰 Newsletter Management")
    
    # Create new newsletter
    with st.expander("Create New Newsletter", expanded=True):
        title = st.text_input("Newsletter Title", value="OUR CLASSROOM newsletter", key="newsletter_title")
        newsletter_date = st.date_input("Date", value=date.today(), key="newsletter_date")
        
        # Newsletter sections
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Left Column**")
            upcoming_events = st.text_area("Upcoming Events", height=150, key="newsletter_upcoming_events", 
                placeholder="9/26 - Half day Q1 midterm grading day (school dismisses at 12 noon)\n9/26 - Day of Fasting, Prayer & Praise\n10/2 - Literacy Night (Next Thursday)\n10/9 - Muffins for Moms\n10/31 - Field Trip (Bible Museum)")
            learning_snapshot = st.text_area("Our Learning Snapshot", height=150, key="newsletter_learning_snapshot",
                placeholder="BIBLE/TFT: Unit 1 - The Life of Christ, studying the book of James...\nLANGUAGE ARTS: Handwriting, Skills 1 Activity...\nMATH: Sadlier Math 2 Chapter 2 - Subtraction to 20...")
            important_news = st.text_area("Important News", height=150, key="newsletter_important_news",
                placeholder="Happy Fall! Our first Field Trip has been posted...")
        
        with col2:
            st.markdown("**Right Column**")
            word_list = st.text_area("Word List", height=150, key="newsletter_word_list",
                placeholder="sand sang sank\nhunt hung hunk\nthin thing think\nshould why what")
            practice_home = st.text_area("Practice @ Home", height=150, key="newsletter_practice_home",
                placeholder="Read daily to your child for 20 mins as part of our nightly homework assignments.")
            memory_verse = st.text_area("Memory Verse", height=100, key="newsletter_memory_verse",
                placeholder="I will exalt you, my God and King; I will praise your name forever and ever...")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📝 Create Newsletter", key="create_newsletter"):
                # Save newsletter to database
                conn = get_db_connection()
                
                newsletter_content = {
                    'title': title,
                    'date': newsletter_date.strftime('%B %d, %Y'),
                    'left_column': {
                        'upcoming_events': upcoming_events,
                        'learning_snapshot': learning_snapshot,
                        'important_news': important_news
                    },
                    'right_column': {
                        'word_list': word_list,
                        'practice_home': practice_home,
                        'memory_verse': memory_verse
                    }
                }
                
                # Use Supabase if available
                if isinstance(conn, SupabaseAdapter):
                    supabase_client = conn.client
                    newsletter_data = {
                        'id': str(uuid.uuid4()),
                        'title': title,
                        'content': json.dumps(newsletter_content),
                        'date': newsletter_date.strftime('%Y-%m-%d'),
                        'teacher_id': st.session_state.user['id']
                    }
                    try:
                        supabase_client.table('newsletters').insert(newsletter_data).execute()
                        st.success("Newsletter created successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error creating newsletter: {str(e)}")
                    conn.close()
                else:
                    # SQLite
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO newsletters (id, title, content, date, teacher_id)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (str(uuid.uuid4()), title, json.dumps(newsletter_content), 
                          newsletter_date.strftime('%Y-%m-%d'), st.session_state.user['id']))
                    conn.commit()
                    conn.close()
                    st.success("Newsletter created successfully!")
                    st.rerun()
        
        with col2:
            if st.button("📋 Load Sample Data", key="load_sample"):
                st.info("Sample data loaded! Please refresh the page to see the pre-filled form.")
                st.markdown("**Sample Content Preview:**")
                st.markdown("""
                **Upcoming Events:**
                - 9/26 - Half day Q1 midterm grading day (school dismisses at 12 noon)
                - 9/26 - Day of Fasting, Prayer & Praise
                - 10/2 - Literacy Night (Next Thursday)
                - 10/9 - Muffins for Moms
                - 10/31 - Field Trip (Bible Museum)
                
                **Word List:**
                - sand sang sank
                - hunt hung hunk
                - thin thing think
                - should why what
                
                **Memory Verse:**
                "I will exalt you, my God and King; I will praise your name forever and ever. Every day I will praise you and extol your name forever and ever."
                """)
    
    # View existing newsletters
    st.subheader("📋 Recent Newsletters")
    
    # Debug: Show active confirmation states
    if st.checkbox("Show Debug Info", key="show_debug_info"):
        st.write("Active confirmation states:")
        for key, value in st.session_state.items():
            if key.startswith('confirm_delete_') and value:
                st.write(f"- {key}: {value}")
    
    # Reset sample data button
    if st.button("🔄 Reset Sample Data", key="reset_sample_data", type="secondary"):
        conn = get_db_connection()
        
        if isinstance(conn, SupabaseAdapter):
            supabase_client = conn.client
            try:
                supabase_client.table('newsletters').delete().neq('id', '').execute()
                st.session_state.sample_newsletter_created = False
                st.success("Sample data reset! Refresh the page to see the sample newsletter again.")
                st.rerun()
            except Exception as e:
                st.error(f"Error resetting sample data: {str(e)}")
            conn.close()
        else:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM newsletters')
            conn.commit()
            conn.close()
            st.session_state.sample_newsletter_created = False
            st.success("Sample data reset! Refresh the page to see the sample newsletter again.")
            st.rerun()
    
    # Bulk actions
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    with col1:
        st.markdown("**Newsletter Management**")
    with col2:
        if st.button("🗑️ Delete All", key="delete_all_newsletters", type="secondary"):
            st.session_state.show_delete_confirm = True
    with col3:
        if st.button("📊 View All", key="view_all_newsletters"):
            st.session_state.show_all_newsletters = not st.session_state.get('show_all_newsletters', False)
    with col4:
        if st.button("🗑️ Clear All", key="clear_all_newsletters", type="secondary"):
            if st.session_state.get('confirm_clear_all', False):
                clear_newsletters()
                st.session_state.confirm_clear_all = False
                st.rerun()
            else:
                st.session_state.confirm_clear_all = True
                st.rerun()
    
    # Confirmation dialog for bulk delete
    if st.session_state.get('show_delete_confirm', False):
        st.warning("⚠️ Are you sure you want to delete ALL newsletters? This action cannot be undone!")
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("✅ Yes, Delete All", key="confirm_delete_all", type="primary"):
                conn = get_db_connection()
                
                if isinstance(conn, SupabaseAdapter):
                    supabase_client = conn.client
                    try:
                        supabase_client.table('newsletters').delete().neq('id', '').execute()
                        st.success("All newsletters deleted successfully!")
                        st.session_state.show_delete_confirm = False
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error deleting newsletters: {str(e)}")
                    conn.close()
                else:
                    cursor = conn.cursor()
                    cursor.execute('DELETE FROM newsletters')
                    conn.commit()
                    conn.close()
                    st.success("All newsletters deleted successfully!")
                    st.session_state.show_delete_confirm = False
                    st.rerun()
        with col2:
            if st.button("❌ Cancel", key="cancel_delete_all"):
                st.session_state.show_delete_confirm = False
                st.rerun()
    
    # Confirmation dialog for clear all
    if st.session_state.get('confirm_clear_all', False):
        st.warning("⚠️ Are you sure you want to clear ALL newsletters? This action cannot be undone!")
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("✅ Yes, Clear All", key="confirm_clear_yes", type="primary"):
                clear_newsletters()
                st.session_state.confirm_clear_all = False
                st.rerun()
        with col2:
            if st.button("❌ Cancel", key="cancel_clear"):
                st.session_state.confirm_clear_all = False
                st.rerun()
    
    # Get newsletters (limit based on show_all setting)
    conn = get_db_connection()
    limit = None if st.session_state.get('show_all_newsletters', False) else 5
    
    if isinstance(conn, SupabaseAdapter):
        supabase_client = conn.client
        query = supabase_client.table('newsletters').select('*').order('created_at', desc=True)
        if limit:
            query = query.limit(limit)
        newsletters_result = query.execute()
        newsletters = newsletters_result.data if newsletters_result.data else []
        # Convert to list of tuples for compatibility: (id, title, content, date, teacher_id, created_at)
        newsletters = [(n.get('id'), n.get('title'), n.get('content'), n.get('date'), n.get('teacher_id'), n.get('created_at')) for n in newsletters]
        conn.close()
    else:
        cursor = conn.cursor()
        if limit:
            cursor.execute('SELECT * FROM newsletters ORDER BY created_at DESC LIMIT ?', (limit,))
        else:
            cursor.execute('SELECT * FROM newsletters ORDER BY created_at DESC')
        newsletters = cursor.fetchall()
        conn.close()
    
    for newsletter in newsletters:
        with st.expander(f"📰 {newsletter[1]} - {newsletter[3]}", expanded=True):
            # Parse newsletter content
            content = json.loads(newsletter[2])
            
            # Action buttons
            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
            with col2:
                if st.button("✏️ Edit", key=f"edit_{newsletter[0]}"):
                    st.session_state[f'editing_newsletter_{newsletter[0]}'] = True
                    st.rerun()
            with col3:
                if st.button("📥 Download PDF", key=f"download_{newsletter[0]}", type="primary"):
                    try:
                        pdf_data = generate_newsletter_pdf(content)
                        st.download_button(
                            label="📄 Download Newsletter PDF",
                            data=pdf_data,
                            file_name=f"newsletter_{newsletter[3].replace(' ', '_')}.pdf",
                            mime="application/pdf",
                            key=f"download_btn_{newsletter[0]}"
                        )
                    except Exception as e:
                        st.error(f"Error generating PDF: {str(e)}")
            with col4:
                if st.button("🗑️ Delete", key=f"delete_{newsletter[0]}", type="secondary"):
                    st.session_state[f'confirm_delete_{newsletter[0]}'] = True
                    st.write(f"Debug: Delete button clicked for newsletter {newsletter[0]} - {newsletter[1]}")
                    st.rerun()
            
            # Edit form
            if st.session_state.get(f'editing_newsletter_{newsletter[0]}', False):
                st.markdown("---")
                st.markdown("### ✏️ Edit Newsletter")
                
                # Parse date from string
                try:
                    newsletter_date_obj = datetime.strptime(newsletter[3], '%Y-%m-%d').date()
                except:
                    try:
                        newsletter_date_obj = datetime.strptime(newsletter[3], '%B %d, %Y').date()
                    except:
                        newsletter_date_obj = date.today()
                
                # Pre-fill form with existing data
                edit_title = st.text_input("Newsletter Title", value=newsletter[1], key=f"edit_title_{newsletter[0]}")
                edit_date = st.date_input("Date", value=newsletter_date_obj, key=f"edit_date_{newsletter[0]}")
                
                # Newsletter sections
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**Left Column**")
                    edit_upcoming_events = st.text_area(
                        "Upcoming Events", 
                        value=content.get('left_column', {}).get('upcoming_events', ''),
                        height=150, 
                        key=f"edit_upcoming_{newsletter[0]}"
                    )
                    edit_learning_snapshot = st.text_area(
                        "Our Learning Snapshot", 
                        value=content.get('left_column', {}).get('learning_snapshot', ''),
                        height=150, 
                        key=f"edit_learning_{newsletter[0]}"
                    )
                    edit_important_news = st.text_area(
                        "Important News", 
                        value=content.get('left_column', {}).get('important_news', ''),
                        height=150, 
                        key=f"edit_important_{newsletter[0]}"
                    )
                
                with col2:
                    st.markdown("**Right Column**")
                    edit_word_list = st.text_area(
                        "Word List", 
                        value=content.get('right_column', {}).get('word_list', ''),
                        height=150, 
                        key=f"edit_word_list_{newsletter[0]}"
                    )
                    edit_practice_home = st.text_area(
                        "Practice @ Home", 
                        value=content.get('right_column', {}).get('practice_home', ''),
                        height=150, 
                        key=f"edit_practice_{newsletter[0]}"
                    )
                    edit_memory_verse = st.text_area(
                        "Memory Verse", 
                        value=content.get('right_column', {}).get('memory_verse', ''),
                        height=100, 
                        key=f"edit_memory_{newsletter[0]}"
                    )
                
                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.button("💾 Save Changes", key=f"save_newsletter_{newsletter[0]}", type="primary"):
                        # Update newsletter in database
                        updated_content = {
                            'title': edit_title,
                            'date': edit_date.strftime('%B %d, %Y'),
                            'left_column': {
                                'upcoming_events': edit_upcoming_events,
                                'learning_snapshot': edit_learning_snapshot,
                                'important_news': edit_important_news
                            },
                            'right_column': {
                                'word_list': edit_word_list,
                                'practice_home': edit_practice_home,
                                'memory_verse': edit_memory_verse
                            }
                        }
                        
                        conn = get_db_connection()
                        if isinstance(conn, SupabaseAdapter):
                            supabase_client = conn.client
                            update_data = {
                                'title': edit_title,
                                'content': json.dumps(updated_content),
                                'date': edit_date.strftime('%Y-%m-%d')
                            }
                            try:
                                supabase_client.table('newsletters').update(update_data).eq('id', newsletter[0]).execute()
                                st.success("✅ Newsletter updated successfully!")
                                st.session_state[f'editing_newsletter_{newsletter[0]}'] = False
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error updating newsletter: {str(e)}")
                            conn.close()
                        else:
                            cursor = conn.cursor()
                            cursor.execute('''
                                UPDATE newsletters 
                                SET title = ?, content = ?, date = ?
                                WHERE id = ?
                            ''', (edit_title, json.dumps(updated_content), edit_date.strftime('%Y-%m-%d'), newsletter[0]))
                            conn.commit()
                            conn.close()
                            st.success("✅ Newsletter updated successfully!")
                            st.session_state[f'editing_newsletter_{newsletter[0]}'] = False
                            st.rerun()
                
                with col2:
                    if st.button("❌ Cancel", key=f"cancel_edit_{newsletter[0]}"):
                        st.session_state[f'editing_newsletter_{newsletter[0]}'] = False
                        st.rerun()
                
                st.markdown("---")
            
            # Confirmation dialog for individual delete
            if st.session_state.get(f'confirm_delete_{newsletter[0]}', False):
                st.warning(f"⚠️ Are you sure you want to delete '{newsletter[1]}'? This action cannot be undone!")
                st.write(f"Debug: Confirmation dialog showing for newsletter {newsletter[0]}")
                col1, col2, col3 = st.columns([1, 1, 2])
                with col1:
                    if st.button("✅ Yes, Delete", key=f"confirm_yes_{newsletter[0]}", type="primary"):
                        st.write(f"Debug: Confirming delete for newsletter {newsletter[0]} - {newsletter[1]}")
                        conn = get_db_connection()
                        
                        if isinstance(conn, SupabaseAdapter):
                            supabase_client = conn.client
                            try:
                                supabase_client.table('newsletters').delete().eq('id', newsletter[0]).execute()
                                st.success("Newsletter deleted successfully!")
                            except Exception as e:
                                st.error(f"Error deleting newsletter: {str(e)}")
                            conn.close()
                        else:
                            cursor = conn.cursor()
                            cursor.execute('DELETE FROM newsletters WHERE id = ?', (newsletter[0],))
                            conn.commit()
                            conn.close()
                            st.success("Newsletter deleted successfully!")
                        # Clear only the specific confirmation state
                        if f'confirm_delete_{newsletter[0]}' in st.session_state:
                            del st.session_state[f'confirm_delete_{newsletter[0]}']
                        st.rerun()
                with col2:
                    if st.button("❌ Cancel", key=f"cancel_{newsletter[0]}"):
                        st.session_state[f'confirm_delete_{newsletter[0]}'] = False
                        st.rerun()
            
            # Newsletter Header
            st.markdown(f"""
                <div style="text-align: center; margin-bottom: 30px;">
                    <h1 style="color: #2c3e50; font-size: 2.5em; margin-bottom: 10px; font-family: 'Arial', sans-serif;">
                        {content['title']}
                    </h1>
                    <div style="background-color: #f1c40f; padding: 8px 15px; display: inline-block; border-radius: 5px; margin-bottom: 20px;">
                        <h2 style="color: #2c3e50; margin: 0; font-size: 1.2em;">{content['date']}</h2>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
            # Teacher Info Box
            st.markdown("""
            <div style="background-color: #ecf0f1; padding: 15px; border-radius: 8px; margin-bottom: 20px; text-align: right;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div style="font-size: 0.9em; color: #7f8c8d;">
                        📚📖📕<br>
                        MRS. SIMMS<br>
                        Ksimms@washingtonchristian.org<br>
                        240-390-0429
                    </div>
                    <div style="font-size: 1.1em; font-weight: bold; color: #2c3e50;">
                        MRS. SIMMS
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Two Column Layout
            col1, col2 = st.columns(2, gap="large")
            
            with col1:
                st.markdown("### 📅 UPCOMING EVENTS")
                if content['left_column']['upcoming_events']:
                    st.markdown(f"""
                    <div style="background-color: #fff; padding: 15px; border-left: 4px solid #3498db; margin-bottom: 20px;">
                        {content['left_column']['upcoming_events'].replace(chr(10), '<br>')}
                    </div>
                    """, unsafe_allow_html=True)
                
                st.markdown("### 📚 OUR LEARNING SNAPSHOT")
                if content['left_column']['learning_snapshot']:
                    st.markdown(f"""
                    <div style="background-color: #fff; padding: 15px; border-left: 4px solid #e74c3c; margin-bottom: 20px;">
                        {content['left_column']['learning_snapshot'].replace(chr(10), '<br>')}
                    </div>
                    """, unsafe_allow_html=True)
                
                st.markdown("### 📢 IMPORTANT NEWS")
                if content['left_column']['important_news']:
                    st.markdown(f"""
                    <div style="background-color: #fff; padding: 15px; border-left: 4px solid #f39c12; margin-bottom: 20px;">
                        {content['left_column']['important_news'].replace(chr(10), '<br>')}
                    </div>
                    """, unsafe_allow_html=True)
                
                st.markdown("""
                <div style="text-align: center; margin-top: 30px; color: #7f8c8d; font-style: italic;">
                    THE LANGUAGE OF LEARNING
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown("### 📝 WORD LIST")
                if content['right_column']['word_list']:
                    st.markdown(f"""
                    <div style="background-color: #fff; padding: 15px; border-left: 4px solid #9b59b6; margin-bottom: 20px;">
                        <div style="font-family: 'Courier New', monospace; line-height: 1.8;">
                            {content['right_column']['word_list'].replace(chr(10), '<br>')}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                
                st.markdown("### 🏠 PRACTICE @ HOME")
                if content['right_column']['practice_home']:
                    st.markdown(f"""
                    <div style="background-color: #fff; padding: 15px; border-left: 4px solid #27ae60; margin-bottom: 20px;">
                        {content['right_column']['practice_home'].replace(chr(10), '<br>')}
                    </div>
                    """, unsafe_allow_html=True)
                
                st.markdown("### 🙏 MEMORY VERSE")
                if content['right_column']['memory_verse']:
                    st.markdown(f"""
                    <div style="background-color: #fff; padding: 15px; border-left: 4px solid #e67e22; margin-bottom: 20px;">
                        <p style="font-weight: bold; margin-bottom: 10px;">Psalm 145:1-2 NIV</p>
                        <div style="font-style: italic; line-height: 1.6; text-align: center;">
                            {content['right_column']['memory_verse'].replace(chr(10), '<br>')}
                        </div>
                        <p style="margin-top: 10px; font-size: 0.9em; color: #7f8c8d;">
                            (Our Memory Verse for the next two weeks - Due 10/10/25)
                        </p>
                    </div>
                    """, unsafe_allow_html=True)

def event_management():
    st.subheader("📅 Event Management")
    
    # Create new event
    with st.expander("Create New Event", expanded=True):
        event_title = st.text_input("Event Title", key="event_title")
        event_description = st.text_area("Description", key="event_description")
        event_date = st.date_input("Event Date", key="event_date")
        event_time = st.time_input("Event Time", key="event_time")
        location = st.text_input("Location", key="event_location")
        max_attendees = st.number_input("Max Attendees", min_value=1, value=50, key="event_max_attendees")
        
        if st.button("Create Event", key="create_event"):
            conn = get_db_connection()
            
            if isinstance(conn, SupabaseAdapter):
                supabase_client = conn.client
                event_data = {
                    'id': str(uuid.uuid4()),
                    'title': event_title,
                    'description': event_description,
                    'event_date': event_date.strftime('%Y-%m-%d'),
                    'event_time': event_time.strftime('%H:%M'),
                    'location': location,
                    'max_attendees': max_attendees,
                    'teacher_id': st.session_state.user['id']
                }
                try:
                    supabase_client.table('events').insert(event_data).execute()
                    st.success("Event created successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error creating event: {str(e)}")
                conn.close()
            else:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO events (id, title, description, event_date, event_time, location, max_attendees, teacher_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (str(uuid.uuid4()), event_title, event_description, 
                      event_date.strftime('%Y-%m-%d'), event_time.strftime('%H:%M'), 
                      location, max_attendees, st.session_state.user['id']))
                conn.commit()
                conn.close()
                st.success("Event created successfully!")
                st.rerun()
    
    # View events and RSVPs
    st.subheader("📋 Upcoming Events")
    conn = get_db_connection()
    
    if isinstance(conn, SupabaseAdapter):
        supabase_client = conn.client
        # Get events with date >= today
        from datetime import date as date_obj
        today = date_obj.today().strftime('%Y-%m-%d')
        events_result = supabase_client.table('events').select('*').gte('event_date', today).order('event_date').execute()
        events_data = events_result.data if events_result.data else []
        
        # Get RSVP counts for each event
        events = []
        for event in events_data:
            rsvp_result = supabase_client.table('event_rsvps').select('id', count='exact').eq('event_id', event['id']).execute()
            rsvp_count = rsvp_result.count if hasattr(rsvp_result, 'count') else len(rsvp_result.data) if rsvp_result.data else 0
            # Convert to tuple format: (id, title, description, event_date, event_time, location, max_attendees, teacher_id, created_at, rsvp_count)
            events.append((event.get('id'), event.get('title'), event.get('description'), event.get('event_date'), 
                          event.get('event_time'), event.get('location'), event.get('max_attendees'), 
                          event.get('teacher_id'), event.get('created_at'), rsvp_count))
        conn.close()
    else:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT e.*, COUNT(er.id) as rsvp_count
            FROM events e
            LEFT JOIN event_rsvps er ON e.id = er.event_id
            WHERE e.event_date >= date('now')
            GROUP BY e.id
            ORDER BY e.event_date
        ''')
        events = cursor.fetchall()
        conn.close()
    
    for event in events:
        with st.expander(f"{event[1]} - {event[3]} at {event[4]}"):
            st.markdown(f"**Description:** {event[2]}")
            st.markdown(f"**Location:** {event[5]}")
            st.markdown(f"**Max Attendees:** {event[6]}")
            st.markdown(f"**RSVPs:** {event[8]}")
            
            # Show RSVP details
            conn = get_db_connection()
            
            if isinstance(conn, SupabaseAdapter):
                supabase_client = conn.client
                # Get RSVPs for this event
                rsvps_result = supabase_client.table('event_rsvps').select('parent_id, attendees_count, notes').eq('event_id', event[0]).execute()
                rsvps_data = rsvps_result.data if rsvps_result.data else []
                
                # Get usernames for parent IDs
                rsvps = []
                for rsvp in rsvps_data:
                    user_result = supabase_client.table('users').select('username').eq('id', rsvp['parent_id']).execute()
                    username = user_result.data[0]['username'] if user_result.data else 'Unknown'
                    rsvps.append((username, rsvp.get('attendees_count'), rsvp.get('notes')))
                conn.close()
            else:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT u.username, er.attendees_count, er.notes
                    FROM event_rsvps er
                    JOIN users u ON er.parent_id = u.id
                    WHERE er.event_id = ?
                ''', (event[0],))
                rsvps = cursor.fetchall()
                conn.close()
            
            if rsvps:
                st.markdown("**RSVP Details:**")
                for rsvp in rsvps:
                    st.markdown(f"- {rsvp[0]}: {rsvp[1]} attendees - {rsvp[2] or 'No notes'}")

def assignment_management():
    st.subheader("📝 Assignment Management")
    
    # Create new assignment
    with st.expander("Create New Assignment", expanded=True):
        title = st.text_input("Assignment Title", key="assignment_title")
        description = st.text_area("Description", key="assignment_description")
        subject = st.selectbox("Subject", ["Bible/TFT", "Language Arts", "Math", "Science", "Social Studies"], key="assignment_subject")
        due_date = st.date_input("Due Date", key="assignment_due_date")
        word_list = st.text_area("Word List (one per line)", key="assignment_word_list")
        memory_verse = st.text_area("Memory Verse", key="assignment_memory_verse")
        
        if st.button("Create Assignment", key="create_assignment"):
            conn = get_db_connection()
            
            if isinstance(conn, SupabaseAdapter):
                supabase_client = conn.client
                assignment_data = {
                    'id': str(uuid.uuid4()),
                    'title': title,
                    'description': description,
                    'subject': subject,
                    'due_date': due_date.strftime('%Y-%m-%d'),
                    'word_list': word_list,
                    'memory_verse': memory_verse,
                    'teacher_id': st.session_state.user['id']
                }
                try:
                    supabase_client.table('assignments').insert(assignment_data).execute()
                    st.success("Assignment created successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error creating assignment: {str(e)}")
                conn.close()
            else:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO assignments (id, title, description, subject, due_date, word_list, memory_verse, teacher_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (str(uuid.uuid4()), title, description, subject, 
                      due_date.strftime('%Y-%m-%d'), word_list, memory_verse, st.session_state.user['id']))
                conn.commit()
                conn.close()
                st.success("Assignment created successfully!")
                st.rerun()
    
    # View assignments
    st.subheader("📋 Current Assignments")
    conn = get_db_connection()
    
    if isinstance(conn, SupabaseAdapter):
        supabase_client = conn.client
        from datetime import date as date_obj
        today = date_obj.today().strftime('%Y-%m-%d')
        assignments_result = supabase_client.table('assignments').select('*').gte('due_date', today).order('due_date').execute()
        assignments = assignments_result.data if assignments_result.data else []
        # Convert to list of tuples for compatibility
        assignments = [(a.get('id'), a.get('title'), a.get('description'), a.get('subject'), 
                       a.get('due_date'), a.get('word_list'), a.get('memory_verse'), 
                       a.get('teacher_id'), a.get('created_at')) for a in assignments]
        conn.close()
    else:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM assignments 
            WHERE due_date >= date('now')
            ORDER BY due_date
        ''')
        assignments = cursor.fetchall()
        conn.close()
    
    for assignment in assignments:
        with st.expander(f"{assignment[1]} - Due {assignment[4]}"):
            st.markdown(f"**Subject:** {assignment[3]}")
            st.markdown(f"**Description:** {assignment[2]}")
            if assignment[5]:
                st.markdown(f"**Word List:**\n{assignment[5]}")
            if assignment[6]:
                st.markdown(f"**Memory Verse:**\n{assignment[6]}")

def student_management():
    st.subheader("👥 Student Management")
    st.markdown("**Create and manage student accounts, view progress, and link students to parents**")
    
    conn = get_db_connection()
    
    # Add parent_id column to users table if it doesn't exist (for linking students to parents)
    if not isinstance(conn, SupabaseAdapter):
        try:
            cursor = conn.cursor()
            cursor.execute('ALTER TABLE users ADD COLUMN parent_id TEXT')
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists
    
    # Navigation tabs for student management
    tab1, tab2, tab3 = st.tabs(["📋 All Students", "➕ Add Student", "📊 Student Progress"])
    
    with tab1:
        # View all students
        if isinstance(conn, SupabaseAdapter):
            supabase_client = conn.client
            students_result = supabase_client.table('users').select('*').eq('role', 'student').order('name').order('created_at', desc=True).execute()
            students = students_result.data if students_result.data else []
            conn.close()
        else:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, username, role, email, phone, name, parent_id, created_at
                FROM users 
                WHERE role = 'student'
                ORDER BY name, created_at DESC
            ''')
            students = cursor.fetchall()
            conn.close()
        
        if not students:
            st.info("📭 No students found. Add your first student using the 'Add Student' tab.")
        else:
            st.success(f"Total Students: {len(students)}")
            
            # Display students in expandable cards
            for student in students:
                if isinstance(student, dict):
                    student_id = student.get('id')
                    username = student.get('username', 'N/A')
                    name = student.get('name', username)
                    email = student.get('email', 'No email')
                    phone = student.get('phone', 'No phone')
                    parent_id = student.get('parent_id')
                    created_at = student.get('created_at', 'N/A')
                else:
                    student_id = student[0]
                    username = student[1] if len(student) > 1 else 'N/A'
                    name = student[5] if len(student) > 5 and student[5] else username
                    email = student[3] if len(student) > 3 else 'No email'
                    phone = student[4] if len(student) > 4 else 'No phone'
                    parent_id = student[6] if len(student) > 6 else None
                    created_at = student[7] if len(student) > 7 else 'N/A'
                
                with st.expander(f"👤 {name} ({username})", expanded=False):
                    col1, col2, col3 = st.columns([2, 1, 1])
                    
                    with col1:
                        st.markdown(f"""
                        **Name:** {name}  
                        **Username:** `{username}`  
                        **Email:** {email or 'Not provided'}  
                        **Phone:** {phone or 'Not provided'}  
                        **Created:** {created_at[:10] if created_at else 'N/A'}
                        """)
                        
                        # Show linked parent if exists
                        if parent_id:
                            conn = get_db_connection()
                            if isinstance(conn, SupabaseAdapter):
                                supabase_client = conn.client
                                parent_result = supabase_client.table('users').select('name, username, email').eq('id', parent_id).execute()
                                if parent_result.data:
                                    parent = parent_result.data[0]
                                    st.info(f"👨‍👩‍👧‍👦 **Linked Parent:** {parent.get('name', parent.get('username', 'Unknown'))} ({parent.get('email', 'No email')})")
                                conn.close()
                            else:
                                cursor = conn.cursor()
                                cursor.execute('SELECT name, username, email FROM users WHERE id = ?', (parent_id,))
                                parent = cursor.fetchone()
                                if parent:
                                    parent_name = parent[0] if parent[0] else parent[1]
                                    st.info(f"👨‍👩‍👧‍👦 **Linked Parent:** {parent_name} ({parent[2] if len(parent) > 2 else 'No email'})")
                                conn.close()
                        else:
                            st.warning("⚠️ No parent linked")
                    
                    with col2:
                        if st.button("✏️ Edit", key=f"edit_student_{student_id}"):
                            st.session_state[f'editing_student_{student_id}'] = True
                            st.rerun()
                    
                    # Show edit form if editing
                    if st.session_state.get(f'editing_student_{student_id}', False):
                        st.markdown("---")
                        st.markdown("### ✏️ Edit Student")
                        
                        # Get current student data
                        conn = get_db_connection()
                        if isinstance(conn, SupabaseAdapter):
                            supabase_client = conn.client
                            current_student = supabase_client.table('users').select('*').eq('id', student_id).execute()
                            if current_student.data:
                                current = current_student.data[0]
                                current_name = current.get('name', '')
                                current_email = current.get('email', '')
                                current_phone = current.get('phone', '')
                                current_parent_id = current.get('parent_id')
                            conn.close()
                        else:
                            cursor = conn.cursor()
                            cursor.execute('SELECT name, email, phone, parent_id FROM users WHERE id = ?', (student_id,))
                            current = cursor.fetchone()
                            current_name = current[0] if current and current[0] else ''
                            current_email = current[1] if current and len(current) > 1 and current[1] else ''
                            current_phone = current[2] if current and len(current) > 2 and current[2] else ''
                            current_parent_id = current[3] if current and len(current) > 3 and current[3] else None
                            conn.close()
                        
                        # Get all parents for dropdown
                        conn = get_db_connection()
                        if isinstance(conn, SupabaseAdapter):
                            supabase_client = conn.client
                            parents_result = supabase_client.table('users').select('id, name, username, email').eq('role', 'parent').order('name').execute()
                            parents = parents_result.data if parents_result.data else []
                            conn.close()
                        else:
                            cursor = conn.cursor()
                            cursor.execute('SELECT id, name, username, email FROM users WHERE role = ? ORDER BY name', ('parent',))
                            parents = cursor.fetchall()
                            conn.close()
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            new_name = st.text_input("Student Name", value=current_name, key=f"edit_name_{student_id}")
                            new_email = st.text_input("Email", value=current_email, key=f"edit_email_{student_id}")
                            new_phone = st.text_input("Phone", value=current_phone, key=f"edit_phone_{student_id}")
                        
                        with col2:
                            # Parent selector
                            parent_options = ["None"] + [f"{p.get('name', p.get('username', 'Unknown')) if isinstance(p, dict) else (p[1] if p[1] else p[2])} ({p.get('id') if isinstance(p, dict) else p[0]})" for p in parents]
                            
                            # Find current parent in list
                            current_parent_index = 0
                            if current_parent_id:
                                for idx, p in enumerate(parents):
                                    p_id = p.get('id') if isinstance(p, dict) else p[0]
                                    if p_id == current_parent_id:
                                        current_parent_index = idx + 1  # +1 because "None" is at index 0
                                        break
                            
                            selected_parent = st.selectbox(
                                "Link to Parent",
                                parent_options,
                                index=current_parent_index,
                                key=f"edit_parent_{student_id}"
                            )
                            new_parent_id = None
                            if selected_parent != "None":
                                parent_id_match = selected_parent.split('(')[-1].rstrip(')')
                                new_parent_id = parent_id_match
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("💾 Save Changes", key=f"save_student_{student_id}", type="primary"):
                                conn = get_db_connection()
                                if isinstance(conn, SupabaseAdapter):
                                    supabase_client = conn.client
                                    update_data = {
                                        'name': new_name,
                                        'email': new_email or '',
                                        'phone': new_phone or '',
                                        'parent_id': new_parent_id
                                    }
                                    try:
                                        supabase_client.table('users').update(update_data).eq('id', student_id).execute()
                                        st.success("✅ Student updated successfully!")
                                        st.session_state[f'editing_student_{student_id}'] = False
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error updating student: {str(e)}")
                                    conn.close()
                                else:
                                    cursor = conn.cursor()
                                    cursor.execute('''
                                        UPDATE users 
                                        SET name = ?, email = ?, phone = ?, parent_id = ?
                                        WHERE id = ?
                                    ''', (new_name, new_email or '', new_phone or '', new_parent_id, student_id))
                                    conn.commit()
                                    conn.close()
                                    st.success("✅ Student updated successfully!")
                                    st.session_state[f'editing_student_{student_id}'] = False
                                    st.rerun()
                        
                        with col2:
                            if st.button("❌ Cancel", key=f"cancel_edit_{student_id}"):
                                st.session_state[f'editing_student_{student_id}'] = False
                                st.rerun()
                    
                    with col3:
                        if st.button("🗑️ Delete", key=f"delete_student_{student_id}", type="secondary"):
                            if st.session_state.get(f"confirm_delete_student_{student_id}", False):
                                conn = get_db_connection()
                                if isinstance(conn, SupabaseAdapter):
                                    supabase_client = conn.client
                                    try:
                                        supabase_client.table('users').delete().eq('id', student_id).execute()
                                        st.success(f"Student {name} deleted successfully!")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error deleting student: {str(e)}")
                                    conn.close()
                                else:
                                    cursor = conn.cursor()
                                    cursor.execute('DELETE FROM users WHERE id = ?', (student_id,))
                                    conn.commit()
                                    conn.close()
                                    st.success(f"Student {name} deleted successfully!")
                                    st.rerun()
                            else:
                                st.session_state[f"confirm_delete_student_{student_id}"] = True
                                st.warning(f"⚠️ Delete '{name}'? This cannot be undone!")
                                if st.button("✅ Yes, Delete", key=f"confirm_yes_student_{student_id}"):
                                    conn = get_db_connection()
                                    if isinstance(conn, SupabaseAdapter):
                                        supabase_client = conn.client
                                        try:
                                            supabase_client.table('users').delete().eq('id', student_id).execute()
                                            st.success("Student deleted!")
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Error: {str(e)}")
                                        conn.close()
                                    else:
                                        cursor = conn.cursor()
                                        cursor.execute('DELETE FROM users WHERE id = ?', (student_id,))
                                        conn.commit()
                                        conn.close()
                                        st.success("Student deleted!")
                                        st.rerun()
    
    with tab2:
        # Add new student
        st.markdown("### ➕ Add New Student")
        
        col1, col2 = st.columns(2)
        
        with col1:
            student_username = st.text_input(
                "Student Username",
                help="Unique username for the student (e.g., 'john.doe', 'student1')",
                key="new_student_username"
            )
            student_password = st.text_input(
                "Password",
                type="password",
                help="Password for student login",
                key="new_student_password"
            )
            st.info("💡 Note: Email is not required for second grade students")
        
        with col2:
            student_name = st.text_input(
                "Student Full Name *",
                help="Full name of the student (e.g., 'John Doe')",
                key="new_student_name"
            )
            student_phone = st.text_input(
                "Phone Number (Optional)",
                help="Contact phone number - not required for second graders",
                key="new_student_phone",
                value=""
            )
            student_email = st.text_input(
                "Email Address (Optional)",
                help="Student's email - not required for second graders",
                key="new_student_email",
                value=""
            )
            # Link to parent
            conn = get_db_connection()
            if isinstance(conn, SupabaseAdapter):
                supabase_client = conn.client
                parents_result = supabase_client.table('users').select('id, name, username, email').eq('role', 'parent').order('name').execute()
                parents = parents_result.data if parents_result.data else []
                conn.close()
            else:
                cursor = conn.cursor()
                cursor.execute('SELECT id, name, username, email FROM users WHERE role = ? ORDER BY name', ('parent',))
                parents = cursor.fetchall()
                conn.close()
            
            parent_options = ["None"] + [f"{p.get('name', p.get('username', 'Unknown')) if isinstance(p, dict) else (p[1] if p[1] else p[2])} ({p.get('id') if isinstance(p, dict) else p[0]})" for p in parents]
            selected_parent = st.selectbox(
                "Link to Parent (Optional)",
                parent_options,
                key="new_student_parent"
            )
            selected_parent_id = None
            if selected_parent != "None":
                # Extract parent ID from selection
                parent_id_match = selected_parent.split('(')[-1].rstrip(')')
                selected_parent_id = parent_id_match
        
        if st.button("➕ Create Student Account", type="primary", key="create_student_btn"):
            if not student_username or not student_password or not student_name:
                st.error("Please fill in Username, Password, and Student Name (required fields).")
            else:
                conn = get_db_connection()
                
                if isinstance(conn, SupabaseAdapter):
                    supabase_client = conn.client
                    
                    # Check if username already exists
                    existing_result = supabase_client.table('users').select('*').eq('username', student_username).execute()
                    
                    if existing_result.data and len(existing_result.data) > 0:
                        st.error(f"Username '{student_username}' already exists. Please choose a different username.")
                    else:
                        student_id = str(uuid.uuid4())
                        student_data = {
                            'id': student_id,
                            'username': student_username,
                            'password': student_password,
                            'role': 'student',
                            'email': student_email or '',
                            'phone': student_phone or '',
                            'name': student_name,
                            'parent_id': selected_parent_id
                        }
                        
                        try:
                            supabase_client.table('users').insert(student_data).execute()
                            st.success(f"✅ Student account created successfully!")
                            st.info(f"""
                            **Student Credentials:**
                            - Username: `{student_username}`
                            - Password: `{student_password}`
                            - Name: {student_name}
                            """)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error creating student: {str(e)}")
                        conn.close()
                else:
                    # SQLite
                    cursor = conn.cursor()
                    
                    # Check if username exists
                    cursor.execute('SELECT id FROM users WHERE username = ?', (student_username,))
                    if cursor.fetchone():
                        st.error(f"Username '{student_username}' already exists. Please choose a different username.")
                    else:
                        student_id = str(uuid.uuid4())
                        cursor.execute('''
                            INSERT INTO users (id, username, password, role, email, phone, name, parent_id)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (student_id, student_username, student_password, 'student', 
                              student_email or '', student_phone or '', student_name, selected_parent_id))
                        conn.commit()
                        st.success(f"✅ Student account created successfully!")
                        st.info(f"""
                        **Student Credentials:**
                        - Username: `{student_username}`
                        - Password: `{student_password}`
                        - Name: {student_name}
                        """)
                        st.rerun()
                    conn.close()
    
    with tab3:
        # Student Progress View
        st.markdown("### 📊 Student Progress on Assignments")
        
        conn = get_db_connection()
        
        # Get all students
        if isinstance(conn, SupabaseAdapter):
            supabase_client = conn.client
            students_result = supabase_client.table('users').select('id, name, username').eq('role', 'student').order('name').execute()
            students_list = students_result.data if students_result.data else []
            conn.close()
        else:
            cursor = conn.cursor()
            cursor.execute('SELECT id, name, username FROM users WHERE role = ? ORDER BY name', ('student',))
            students_list = cursor.fetchall()
            conn.close()
        
        if not students_list:
            st.info("No students found. Add students first to view their progress.")
        else:
            # Student selector
            student_options = {}
            for s in students_list:
                if isinstance(s, dict):
                    student_id = s.get('id')
                    name = s.get('name', s.get('username', 'Unknown'))
                else:
                    student_id = s[0]
                    name = s[1] if s[1] else s[2]
                student_options[name] = student_id
            
            selected_student_name = st.selectbox("Select Student", list(student_options.keys()))
            selected_student_id = student_options[selected_student_name]
            
            # Get assignments
            conn = get_db_connection()
            if isinstance(conn, SupabaseAdapter):
                supabase_client = conn.client
                assignments_result = supabase_client.table('assignments').select('*').order('created_at', desc=True).execute()
                assignments = assignments_result.data if assignments_result.data else []
                conn.close()
            else:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM assignments ORDER BY created_at DESC')
                assignments = cursor.fetchall()
                conn.close()
            
            if not assignments:
                st.info("No assignments found. Create assignments first.")
            else:
                # Get student progress
                conn = get_db_connection()
                if isinstance(conn, SupabaseAdapter):
                    supabase_client = conn.client
                    progress_result = supabase_client.table('student_progress').select('*').eq('student_id', selected_student_id).execute()
                    progress_data = progress_result.data if progress_result.data else []
                    conn.close()
                else:
                    cursor = conn.cursor()
                    cursor.execute('SELECT * FROM student_progress WHERE student_id = ?', (selected_student_id,))
                    progress_data = cursor.fetchall()
                    conn.close()
                
                # Create progress lookup
                progress_lookup = {}
                for p in progress_data:
                    if isinstance(p, dict):
                        assignment_id = p.get('assignment_id')
                        completed = p.get('completed', False)
                        submitted_at = p.get('submitted_at')
                    else:
                        assignment_id = p[2] if len(p) > 2 else None
                        completed = p[5] if len(p) > 5 else False
                        submitted_at = p[6] if len(p) > 6 else None
                    if assignment_id:
                        progress_lookup[assignment_id] = {'completed': completed, 'submitted_at': submitted_at}
                
                # Display assignments with progress
                st.markdown(f"### Progress for {selected_student_name}")
                
                for assignment in assignments:
                    if isinstance(assignment, dict):
                        assignment_id = assignment.get('id')
                        title = assignment.get('title', 'N/A')
                        due_date = assignment.get('due_date', 'N/A')
                    else:
                        assignment_id = assignment[0]
                        title = assignment[1] if len(assignment) > 1 else 'N/A'
                        due_date = assignment[4] if len(assignment) > 4 else 'N/A'
                    
                    progress = progress_lookup.get(assignment_id, {})
                    completed = progress.get('completed', False)
                    submitted_at = progress.get('submitted_at')
                    
                    status_icon = "✅" if completed else "⏳"
                    status_text = "Completed" if completed else "Not Started"
                    
                    with st.expander(f"{status_icon} {title} - {status_text}", expanded=False):
                        st.markdown(f"**Due Date:** {due_date}")
                        if completed and submitted_at:
                            st.success(f"✅ Submitted on: {submitted_at[:10] if submitted_at else 'N/A'}")
                        else:
                            st.warning("⏳ Assignment not yet completed")

def parent_user_management():
    st.subheader("👨‍👩‍👧‍👦 Parent Account Management")
    st.markdown("**Create and manage parent accounts for production use**")
    
    # Create new parent account
    with st.expander("➕ Add New Parent Account", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            parent_username = st.text_input(
                "Parent Username",
                help="Choose a unique username for the parent (e.g., 'smith.family' or 'john.smith')",
                key="new_parent_username"
            )
            parent_email = st.text_input(
                "Email Address",
                help="Parent's email address (for newsletters and communication)",
                key="new_parent_email"
            )
            parent_password = st.text_input(
                "Password",
                type="password",
                help="Create a secure password for the parent",
                key="new_parent_password"
            )
        
        with col2:
            parent_name = st.text_input(
                "Parent Name",
                help="Full name (e.g., 'John and Jane Smith')",
                key="new_parent_name"
            )
            parent_phone = st.text_input(
                "Phone Number",
                help="Contact phone number (optional)",
                key="new_parent_phone"
            )
            student_name = st.text_input(
                "Student Name",
                help="Name of the parent's child in your class",
                key="new_parent_student_name"
            )
        
        if st.button("➕ Create Parent Account", type="primary", key="create_parent_btn"):
            if not parent_username or not parent_password or not parent_email:
                st.error("Please fill in at least Username, Password, and Email address.")
            else:
                conn = get_db_connection()
                
                # Use Supabase if available
                if isinstance(conn, SupabaseAdapter):
                    supabase_client = conn.client
                    
                    # Check if username already exists
                    existing_result = supabase_client.table('users').select('*').eq('username', parent_username).execute()
                    
                    if existing_result.data and len(existing_result.data) > 0:
                        st.error(f"Username '{parent_username}' already exists. Please choose a different username.")
                    else:
                        # Create parent account
                        parent_id = str(uuid.uuid4())
                        parent_data = {
                            'id': parent_id,
                            'username': parent_username,
                            'password': parent_password,
                            'role': 'parent',
                            'email': parent_email,
                            'phone': parent_phone or '',
                            'name': parent_name or ''
                        }
                        
                        try:
                            supabase_client.table('users').insert(parent_data).execute()
                            st.success(f"✅ Parent account created successfully!")
                            st.info(f"""
                            **Login Credentials:**
                            - Username: `{parent_username}`
                            - Password: `{parent_password}`
                            - Email: {parent_email}
                            
                            Share these credentials with the parent along with the app link:
                            https://classroom-management-app-wca.streamlit.app
                            """)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error creating parent account: {str(e)}")
                    
                    conn.close()
                else:
                    # SQLite
                    cursor = conn.cursor()
                    
                    # Check if username already exists
                    cursor.execute('SELECT * FROM users WHERE username = ?', (parent_username,))
                    existing = cursor.fetchone()
                    
                    if existing:
                        st.error(f"Username '{parent_username}' already exists. Please choose a different username.")
                    else:
                        # Create parent account
                        parent_id = str(uuid.uuid4())
                        cursor.execute('''
                            INSERT INTO users (id, username, password, role, email, phone, name)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (parent_id, parent_username, parent_password, 'parent', parent_email, parent_phone or '', parent_name or ''))
                        
                        conn.commit()
                        conn.close()
                        st.success(f"✅ Parent account created successfully!")
                        st.info(f"""
                        **Login Credentials:**
                        - Username: `{parent_username}`
                        - Password: `{parent_password}`
                        - Email: {parent_email}
                        
                        Share these credentials with the parent along with the app link:
                        https://classroom-management-app-wca.streamlit.app
                        """)
                        st.rerun()
    
    # Demo accounts warning (dynamic - only shows accounts that exist)
    conn_check = get_db_connection()
    
    demo_accounts = ['parent1', 'parent2', 'parent3']
    existing_demo_accounts = []
    
    if isinstance(conn_check, SupabaseAdapter):
        supabase_client = conn_check.client
        for demo_account in demo_accounts:
            result = supabase_client.table('users').select('username').eq('username', demo_account).eq('role', 'parent').execute()
            if result.data and len(result.data) > 0:
                existing_demo_accounts.append(demo_account)
        conn_check.close()
    else:
        cursor_check = conn_check.cursor()
        for demo_account in demo_accounts:
            cursor_check.execute('SELECT username FROM users WHERE username = ? AND role = "parent"', (demo_account,))
            if cursor_check.fetchone():
                existing_demo_accounts.append(demo_account)
        conn_check.close()
    
    # Only show warning if demo accounts exist
    if existing_demo_accounts:
        st.markdown("---")
        demo_list = ", ".join([f"'{acc}'" for acc in existing_demo_accounts])
        st.warning(f"⚠️ **Demo Accounts Note:** The account(s) {demo_list} are demo/test accounts. Delete them before production use or keep them separate from real parent accounts.")
    
    # View and manage existing parent accounts
    st.subheader("📋 Existing Parent Accounts")
    
    conn = get_db_connection()
    
    # Use Supabase if available
    if isinstance(conn, SupabaseAdapter):
        supabase_client = conn.client
        parents_result = supabase_client.table('users').select('id, username, email, phone, name, created_at').eq('role', 'parent').order('created_at', desc=True).execute()
        parents = parents_result.data if parents_result.data else []
        # Convert to list of tuples for compatibility (handling None name values)
        parents = [(p.get('id'), p.get('username'), p.get('email'), p.get('phone'), p.get('name') or '', p.get('created_at')) for p in parents]
        conn.close()
    else:
        # SQLite
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, username, email, phone, COALESCE(name, '') as name, created_at 
            FROM users 
            WHERE role = "parent" 
            ORDER BY created_at DESC
        ''')
        parents = cursor.fetchall()
        conn.close()
    
    if not parents:
        st.info("No parent accounts created yet. Use the form above to add parent accounts.")
    else:
        st.success(f"Found {len(parents)} parent account(s)")
        
        # Display parents in a table
        for parent in parents:
            parent_id, username, email, phone, name, created_at = parent
            display_name = name if name else "Not set"
            with st.expander(f"👤 {name if name else username} - {email or 'No email'}", expanded=False):
                col1, col2, col3 = st.columns([2, 1, 1])
                
                with col1:
                    st.markdown(f"""
                    **Name:** {display_name}  
                    **Username:** `{username}`  
                    **Email:** {email or 'Not provided'}  
                    **Phone:** {phone or 'Not provided'}  
                    **Created:** {created_at[:10] if created_at else 'N/A'}
                    """)
                
                with col2:
                    if st.button("📋 Show Credentials", key=f"show_creds_{parent_id}"):
                        # Get password from database
                        conn = get_db_connection()
                        
                        if isinstance(conn, SupabaseAdapter):
                            supabase_client = conn.client
                            password_result = supabase_client.table('users').select('password').eq('id', parent_id).execute()
                            password = password_result.data[0].get('password') if password_result.data else "Password not found"
                            conn.close()
                        else:
                            cursor = conn.cursor()
                            cursor.execute('SELECT password FROM users WHERE id = ?', (parent_id,))
                            password_result = cursor.fetchone()
                            password = password_result[0] if password_result else "Password not found"
                            conn.close()
                        
                        display_title = name if name else username
                        st.info(f"""
                        **Login Credentials for {display_title}:**
                        - **Name:** {name if name else 'Not set'}
                        - **Username:** `{username}`
                        - **Password:** `{password}`
                        - **Email:** {email or 'Not provided'}
                        - **App Link:** https://classroom-management-app-wca.streamlit.app
                        
                        Share these credentials securely with the parent.
                        """)
                
                with col3:
                    if st.button("🗑️ Delete", key=f"delete_parent_{parent_id}", type="secondary"):
                        if st.session_state.get(f"confirm_delete_parent_{parent_id}", False):
                            conn = get_db_connection()
                            
                            if isinstance(conn, SupabaseAdapter):
                                supabase_client = conn.client
                                try:
                                    supabase_client.table('users').delete().eq('id', parent_id).execute()
                                    st.success("Parent account deleted successfully!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error deleting parent: {str(e)}")
                                conn.close()
                            else:
                                cursor = conn.cursor()
                                cursor.execute('DELETE FROM users WHERE id = ?', (parent_id,))
                                conn.commit()
                                conn.close()
                                st.success("Parent account deleted successfully!")
                                st.rerun()
                        else:
                            st.session_state[f"confirm_delete_parent_{parent_id}"] = True
                            st.warning(f"⚠️ Are you sure you want to delete '{username}'? This action cannot be undone!")
                            if st.button("✅ Yes, Delete", key=f"confirm_yes_{parent_id}"):
                                conn = get_db_connection()
                                
                                if isinstance(conn, SupabaseAdapter):
                                    supabase_client = conn.client
                                    try:
                                        supabase_client.table('users').delete().eq('id', parent_id).execute()
                                        st.success("Parent account deleted!")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error deleting parent: {str(e)}")
                                    conn.close()
                                else:
                                    cursor = conn.cursor()
                                    cursor.execute('DELETE FROM users WHERE id = ?', (parent_id,))
                                    conn.commit()
                                    conn.close()
                                    st.success("Parent account deleted!")
                                    st.rerun()
                
                # Password change section
                st.markdown("---")
                st.markdown("**🔐 Change Password**")
                col_pwd1, col_pwd2 = st.columns([1, 1])
                
                with col_pwd1:
                    new_password = st.text_input(
                        "New Password",
                        type="password",
                        help="Enter new password for this parent",
                        key=f"parent_new_pwd_{parent_id}"
                    )
                
                with col_pwd2:
                    st.markdown("<br>", unsafe_allow_html=True)  # Spacing
                    if st.button("🔄 Update Password", key=f"parent_change_pwd_{parent_id}", type="primary"):
                        if new_password:
                            if len(new_password) >= 6:
                                conn = get_db_connection()
                                
                                if isinstance(conn, SupabaseAdapter):
                                    supabase_client = conn.client
                                    try:
                                        supabase_client.table('users').update({'password': new_password}).eq('id', parent_id).execute()
                                        st.success(f"✅ Password updated successfully for {username}!")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error updating password: {str(e)}")
                                    conn.close()
                                else:
                                    cursor = conn.cursor()
                                    cursor.execute(
                                        'UPDATE users SET password = ? WHERE id = ?',
                                        (new_password, parent_id)
                                    )
                                    conn.commit()
                                    conn.close()
                                    st.success(f"✅ Password updated successfully for {username}!")
                                    st.rerun()
                            else:
                                st.error("Password must be at least 6 characters long.")
                        else:
                            st.error("Please enter a new password.")
                
                # Name editing section
                st.markdown("---")
                st.markdown("**✏️ Edit Parent Name**")
                col_name1, col_name2 = st.columns([1, 1])
                
                with col_name1:
                    current_name = name if name else ""
                    updated_name = st.text_input(
                        "Parent Name",
                        value=current_name,
                        help="Enter or update the parent's name (e.g., 'John and Jane Smith')",
                        key=f"parent_name_{parent_id}"
                    )
                
                with col_name2:
                    st.markdown("<br>", unsafe_allow_html=True)  # Spacing
                    if st.button("💾 Save Name", key=f"parent_save_name_{parent_id}", type="primary"):
                        # Save the name (trimmed), even if empty
                        name_to_save = updated_name.strip() if updated_name else ""
                        conn = get_db_connection()
                        
                        if isinstance(conn, SupabaseAdapter):
                            supabase_client = conn.client
                            try:
                                supabase_client.table('users').update({'name': name_to_save}).eq('id', parent_id).execute()
                                if name_to_save:
                                    st.success(f"✅ Parent name updated successfully for {username}!")
                                    st.info("ℹ️ The welcome message will now show this name when the parent logs in.")
                                else:
                                    st.success(f"✅ Parent name cleared for {username}!")
                                    st.info("ℹ️ The welcome message will now use email or username as fallback.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error updating name: {str(e)}")
                            conn.close()
                        else:
                            cursor = conn.cursor()
                            cursor.execute(
                                'UPDATE users SET name = ? WHERE id = ?',
                                (name_to_save, parent_id)
                            )
                            conn.commit()
                            conn.close()
                            if name_to_save:
                                st.success(f"✅ Parent name updated successfully for {username}!")
                                st.info("ℹ️ The welcome message will now show this name when the parent logs in.")
                            else:
                                st.success(f"✅ Parent name cleared for {username}!")
                                st.info("ℹ️ The welcome message will now use email or username as fallback.")
                            st.rerun()
    
    # Bulk export credentials
    if parents:
        st.markdown("---")
        st.subheader("📤 Export Parent Credentials")
        if st.button("📋 Copy All Parent Credentials", key="export_all_parents"):
            credentials_text = "**Parent Login Credentials:**\n\n"
            for parent in parents:
                username, email = parent[1], parent[2]
                credentials_text += f"**{email or username}:**\n"
                credentials_text += f"- Username: `{username}`\n"
                credentials_text += f"- Password: (check when account was created)\n"
                credentials_text += f"- App Link: https://classroom-management-app-wca.streamlit.app\n\n"
            
            st.text_area("Copy these credentials:", credentials_text, height=300, key="credentials_export")
            st.info("💡 Copy the text above and share it with parents via email or print.")

def admin_user_management():
    st.subheader("👥 Complete User Management")
    st.markdown("**View and manage ALL users in the system (Admins, Teachers, Parents)**")
    
    # View all users
    conn = get_db_connection()
    
    if isinstance(conn, SupabaseAdapter):
        supabase_client = conn.client
        users_result = supabase_client.table('users').select('id, username, role, email, phone, created_at').order('role').order('created_at', desc=True).execute()
        users_data = users_result.data if users_result.data else []
        # Convert to list of tuples for compatibility
        all_users = [(u.get('id'), u.get('username'), u.get('role'), u.get('email'), u.get('phone'), u.get('created_at')) for u in users_data]
        conn.close()
    else:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, username, role, email, phone, created_at 
            FROM users 
            ORDER BY role, created_at DESC
        ''')
        all_users = cursor.fetchall()
        conn.close()
    
    if not all_users:
        st.info("No users found in the system.")
    else:
        # Group by role
        roles = {'admin': [], 'teacher': [], 'parent': []}
        for user in all_users:
            role = user[2]
            if role in roles:
                roles[role].append(user)
        
        st.success(f"Total Users: {len(all_users)} (Admin: {len(roles['admin'])}, Teachers: {len(roles['teacher'])}, Parents: {len(roles['parent'])})")
        
        # Display users by role
        for role_name, role_display in [('admin', '👑 Admins'), ('teacher', '👩‍🏫 Teachers'), ('parent', '👨‍👩‍👧‍👦 Parents')]:
            if roles[role_name]:
                st.markdown(f"### {role_display} ({len(roles[role_name])})")
                for user in roles[role_name]:
                    user_id, username, role, email, phone, created_at = user
                    with st.expander(f"{username} ({role}) - {email or 'No email'}", expanded=False):
                        col1, col2, col3 = st.columns([2, 1, 1])
                        
                        with col1:
                            st.markdown(f"""
                            **Username:** `{username}`  
                            **Role:** {role}  
                            **Email:** {email or 'Not provided'}  
                            **Phone:** {phone or 'Not provided'}  
                            **Created:** {created_at[:10] if created_at else 'N/A'}
                            """)
                        
                        with col2:
                            if st.button("📋 Show Credentials", key=f"admin_show_creds_{user_id}"):
                                conn = get_db_connection()
                                
                                if isinstance(conn, SupabaseAdapter):
                                    supabase_client = conn.client
                                    password_result = supabase_client.table('users').select('password').eq('id', user_id).execute()
                                    password = password_result.data[0].get('password') if password_result.data else "Password not found"
                                    conn.close()
                                else:
                                    cursor = conn.cursor()
                                    cursor.execute('SELECT password FROM users WHERE id = ?', (user_id,))
                                    password_result = cursor.fetchone()
                                    password = password_result[0] if password_result else "Not found"
                                    conn.close()
                                
                                st.info(f"""
                                **Login Credentials:**
                                - Username: `{username}`
                                - Password: `{password}`
                                - Role: {role}
                                - App: https://classroom-management-app-wca.streamlit.app
                                """)
                        
                        with col3:
                            if user_id != st.session_state.user.get('id'):  # Can't delete yourself
                                if st.button("🗑️ Delete", key=f"admin_delete_{user_id}", type="secondary"):
                                    if st.session_state.get(f"admin_confirm_delete_{user_id}", False):
                                        conn = get_db_connection()
                                        
                                        if isinstance(conn, SupabaseAdapter):
                                            supabase_client = conn.client
                                            try:
                                                supabase_client.table('users').delete().eq('id', user_id).execute()
                                                st.success(f"User {username} deleted successfully!")
                                                st.rerun()
                                            except Exception as e:
                                                st.error(f"Error deleting user: {str(e)}")
                                            conn.close()
                                        else:
                                            cursor = conn.cursor()
                                            cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
                                            conn.commit()
                                            conn.close()
                                            st.success(f"User {username} deleted successfully!")
                                            st.rerun()
                                    else:
                                        st.session_state[f"admin_confirm_delete_{user_id}"] = True
                                        st.warning(f"⚠️ Delete '{username}'? This cannot be undone!")
                                        if st.button("✅ Yes, Delete", key=f"admin_confirm_yes_{user_id}"):
                                            conn = get_db_connection()
                                            
                                            if isinstance(conn, SupabaseAdapter):
                                                supabase_client = conn.client
                                                try:
                                                    supabase_client.table('users').delete().eq('id', user_id).execute()
                                                    st.success("User deleted!")
                                                    st.rerun()
                                                except Exception as e:
                                                    st.error(f"Error deleting user: {str(e)}")
                                                conn.close()
                                            else:
                                                cursor = conn.cursor()
                                                cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
                                                conn.commit()
                                                conn.close()
                                                st.success("User deleted!")
                                                st.rerun()

def admin_teacher_management():
    st.subheader("👩‍🏫 Teacher Account Management")
    st.markdown("**Create and manage teacher accounts**")
    
    # Create new teacher account
    with st.expander("➕ Add New Teacher Account", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            teacher_username = st.text_input(
                "Teacher Username",
                help="Choose a unique username (e.g., 'mrs.simms', 'mr.jones')",
                key="new_teacher_username"
            )
            teacher_email = st.text_input(
                "Email Address",
                help="Teacher's school email address",
                key="new_teacher_email"
            )
            teacher_password = st.text_input(
                "Password",
                type="password",
                help="Create a secure password",
                key="new_teacher_password"
            )
        
        with col2:
            teacher_name = st.text_input(
                "Teacher Name",
                help="Full name (e.g., 'Mrs. Simms')",
                key="new_teacher_name"
            )
            teacher_phone = st.text_input(
                "Phone Number",
                help="Contact phone number",
                key="new_teacher_phone"
            )
        
        if st.button("➕ Create Teacher Account", type="primary", key="create_teacher_btn"):
            if not teacher_username or not teacher_password or not teacher_email:
                st.error("Please fill in at least Username, Password, and Email address.")
            else:
                conn = get_db_connection()
                
                # Use Supabase if available
                if isinstance(conn, SupabaseAdapter):
                    supabase_client = conn.client
                    
                    # Check if username already exists
                    existing_result = supabase_client.table('users').select('*').eq('username', teacher_username).execute()
                    
                    if existing_result.data and len(existing_result.data) > 0:
                        st.error(f"Username '{teacher_username}' already exists.")
                    else:
                        # Create teacher account
                        teacher_id = str(uuid.uuid4())
                        teacher_data = {
                            'id': teacher_id,
                            'username': teacher_username,
                            'password': teacher_password,
                            'role': 'teacher',
                            'email': teacher_email,
                            'phone': teacher_phone or '',
                            'name': teacher_name or ''
                        }
                        
                        try:
                            supabase_client.table('users').insert(teacher_data).execute()
                            st.success(f"✅ Teacher account created successfully!")
                            st.info(f"""
                            **Login Credentials:**
                            - Username: `{teacher_username}`
                            - Password: `{teacher_password}`
                            - Email: {teacher_email}
                            - Role: Teacher
                            - App: https://classroom-management-app-wca.streamlit.app
                            """)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error creating teacher account: {str(e)}")
                    
                    conn.close()
                else:
                    # SQLite
                    cursor = conn.cursor()
                    
                    cursor.execute('SELECT * FROM users WHERE username = ?', (teacher_username,))
                    existing = cursor.fetchone()
                    
                    if existing:
                        st.error(f"Username '{teacher_username}' already exists.")
                    else:
                        teacher_id = str(uuid.uuid4())
                        cursor.execute('''
                            INSERT INTO users (id, username, password, role, email, phone, name)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (teacher_id, teacher_username, teacher_password, 'teacher', teacher_email, teacher_phone or '', teacher_name or ''))
                        
                        conn.commit()
                        conn.close()
                        st.success(f"✅ Teacher account created successfully!")
                        st.info(f"""
                        **Login Credentials:**
                        - Username: `{teacher_username}`
                        - Password: `{teacher_password}`
                        - Email: {teacher_email}
                        - Role: Teacher
                        - App: https://classroom-management-app-wca.streamlit.app
                        """)
                        st.rerun()
    
    # View existing teachers
    st.subheader("📋 Existing Teacher Accounts")
    
    conn = get_db_connection()
    
    # Use Supabase if available
    if isinstance(conn, SupabaseAdapter):
        supabase_client = conn.client
        teachers_result = supabase_client.table('users').select('id, username, email, phone, created_at').eq('role', 'teacher').order('created_at', desc=True).execute()
        teachers = teachers_result.data if teachers_result.data else []
        # Convert to list of tuples for compatibility
        teachers = [(t.get('id'), t.get('username'), t.get('email'), t.get('phone'), t.get('created_at')) for t in teachers]
        conn.close()
    else:
        # SQLite
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, username, email, phone, created_at 
            FROM users 
            WHERE role = "teacher" 
            ORDER BY created_at DESC
        ''')
        teachers = cursor.fetchall()
        conn.close()
    
    if not teachers:
        st.info("No teacher accounts created yet.")
    else:
        st.success(f"Found {len(teachers)} teacher account(s)")
        
        for teacher in teachers:
            teacher_id, username, email, phone, created_at = teacher
            with st.expander(f"👩‍🏫 {username} - {email or 'No email'}", expanded=False):
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.markdown(f"""
                    **Username:** `{username}`  
                    **Email:** {email or 'Not provided'}  
                    **Phone:** {phone or 'Not provided'}  
                    **Created:** {created_at[:10] if created_at else 'N/A'}
                    """)
                
                with col2:
                    if st.button("📋 Show Credentials", key=f"teacher_show_{teacher_id}"):
                        conn = get_db_connection()
                        
                        if isinstance(conn, SupabaseAdapter):
                            supabase_client = conn.client
                            password_result = supabase_client.table('users').select('password').eq('id', teacher_id).execute()
                            password = password_result.data[0].get('password') if password_result.data else "Password not found"
                            conn.close()
                        else:
                            cursor = conn.cursor()
                            cursor.execute('SELECT password FROM users WHERE id = ?', (teacher_id,))
                            password_result = cursor.fetchone()
                            password = password_result[0] if password_result else "Not found"
                            conn.close()
                        
                        st.info(f"""
                        **Login Credentials:**
                        - Username: `{username}`
                        - Password: `{password}`
                        - App: https://classroom-management-app-wca.streamlit.app
                        """)
                
                # Password change section
                st.markdown("---")
                st.markdown("**🔐 Change Password**")
                col_new_pwd1, col_new_pwd2 = st.columns([1, 1])
                
                with col_new_pwd1:
                    new_password = st.text_input(
                        "New Password",
                        type="password",
                        help="Enter new password for this teacher",
                        key=f"teacher_new_pwd_{teacher_id}"
                    )
                
                with col_new_pwd2:
                    st.markdown("<br>", unsafe_allow_html=True)  # Spacing
                    if st.button("🔄 Update Password", key=f"teacher_change_pwd_{teacher_id}", type="primary"):
                        if new_password:
                            if len(new_password) >= 6:
                                conn = get_db_connection()
                                
                                if isinstance(conn, SupabaseAdapter):
                                    supabase_client = conn.client
                                    try:
                                        supabase_client.table('users').update({'password': new_password}).eq('id', teacher_id).execute()
                                        st.success(f"✅ Password updated successfully for {username}!")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error updating password: {str(e)}")
                                    conn.close()
                                else:
                                    cursor = conn.cursor()
                                    cursor.execute(
                                        'UPDATE users SET password = ? WHERE id = ?',
                                        (new_password, teacher_id)
                                    )
                                    conn.commit()
                                    conn.close()
                                    st.success(f"✅ Password updated successfully for {username}!")
                                    st.rerun()
                            else:
                                st.error("Password must be at least 6 characters long.")
                        else:
                            st.error("Please enter a new password.")

def admin_system_info():
    st.subheader("📊 System Information & Statistics")
    
    conn = get_db_connection()
    
    # Use Supabase if available
    if isinstance(conn, SupabaseAdapter):
        supabase_client = conn.client
        
        # User statistics
        st.markdown("### 👥 User Statistics")
        
        # Get all users and count by role
        users_result = supabase_client.table('users').select('role').execute()
        users = users_result.data if users_result.data else []
        
        admin_count = sum(1 for u in users if u.get('role') == 'admin')
        teacher_count = sum(1 for u in users if u.get('role') == 'teacher')
        parent_count = sum(1 for u in users if u.get('role') == 'parent')
        total_users = len(users)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Users", total_users)
        with col2:
            st.metric("Admins", admin_count)
        with col3:
            st.metric("Teachers", teacher_count)
        with col4:
            st.metric("Parents", parent_count)
        
        # Content statistics
        st.markdown("### 📚 Content Statistics")
        
        # Count newsletters
        newsletters_result = supabase_client.table('newsletters').select('id', count='exact').execute()
        newsletter_count = newsletters_result.count if hasattr(newsletters_result, 'count') else len(newsletters_result.data) if newsletters_result.data else 0
        
        # Count events
        events_result = supabase_client.table('events').select('id', count='exact').execute()
        event_count = events_result.count if hasattr(events_result, 'count') else len(events_result.data) if events_result.data else 0
        
        # Count assignments
        assignments_result = supabase_client.table('assignments').select('id', count='exact').execute()
        assignment_count = assignments_result.count if hasattr(assignments_result, 'count') else len(assignments_result.data) if assignments_result.data else 0
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Newsletters", newsletter_count)
        with col2:
            st.metric("Events", event_count)
        with col3:
            st.metric("Assignments", assignment_count)
        
        conn.close()
    else:
        # SQLite
        cursor = conn.cursor()
        
        # User statistics
        st.markdown("### 👥 User Statistics")
        cursor.execute('SELECT role, COUNT(*) FROM users GROUP BY role')
        role_counts = cursor.fetchall()
        
        col1, col2, col3, col4 = st.columns(4)
        
        admin_count = next((count for role, count in role_counts if role == 'admin'), 0)
        teacher_count = next((count for role, count in role_counts if role == 'teacher'), 0)
        parent_count = next((count for role, count in role_counts if role == 'parent'), 0)
        total_users = admin_count + teacher_count + parent_count
        
        with col1:
            st.metric("Total Users", total_users)
        with col2:
            st.metric("Admins", admin_count)
        with col3:
            st.metric("Teachers", teacher_count)
        with col4:
            st.metric("Parents", parent_count)
        
        # Content statistics
        st.markdown("### 📚 Content Statistics")
        cursor.execute('SELECT COUNT(*) FROM newsletters')
        newsletter_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM events')
        event_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM assignments')
        assignment_count = cursor.fetchone()[0]
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Newsletters", newsletter_count)
        with col2:
            st.metric("Events", event_count)
        with col3:
            st.metric("Assignments", assignment_count)
        
        conn.close()
    
    # System details
    st.markdown("### ⚙️ System Details")
    
    # Check database type
    conn_test = get_db_connection()
    db_type = "Supabase (PostgreSQL)" if isinstance(conn_test, SupabaseAdapter) else "SQLite (Local)"
    db_status = "✅ Connected" if conn_test else "❌ Not Connected"
    if not isinstance(conn_test, SupabaseAdapter):
        conn_test.close()
    
    st.info(f"""
    **App Version:** 1.0  
    **Database:** {db_type}  
    **Status:** {db_status}
    **Platform:** Streamlit Cloud  
    **App URL:** https://classroom-management-app-wca.streamlit.app
    """)
    
    # Database persistence warning (only show if using SQLite)
    if not isinstance(conn_test, SupabaseAdapter):
        st.markdown("### 🚨 CRITICAL: Database Persistence Issue")
        st.error("""
        **🚨 URGENT:** On Streamlit Cloud, the file system is **EPHEMERAL** (temporary).
        
        **Your database file is LOST when:**
        - ❌ Code is pushed/redeployed
        - ❌ App restarts (even from inactivity - no code push needed!)
        - ❌ Container restarts (maintenance, resource limits)
        - ❌ Any system restart
        
        **This is why users disappear even without code pushes!**
        
        **⚠️ IMMEDIATE SOLUTION REQUIRED:**
        You **MUST** migrate to Supabase (PostgreSQL database). SQLite on Streamlit Cloud 
        is NOT suitable for production use.
        
        **Setup Instructions:**
        See `SUPABASE_SETUP_GUIDE.md` for step-by-step instructions (15 minutes setup).
        
        **Current Status:** ⚠️ Using local SQLite - Data will be lost on app restarts
        """)
        
        st.info("""
        **💡 Quick Fix:** Follow the setup guide to migrate to Supabase. 
        This will solve the data loss issue permanently!
        """)
    else:
        st.success("""
        **✅ Database Persistence:** Using Supabase (PostgreSQL) - Your data is safe!
        Data will persist across app restarts and deployments.
        """)

def admin_user_activity():
    st.subheader("📊 User Activity & Login Tracking")
    st.markdown("**Track all user logins and activity in the system**")
    
    conn = get_db_connection()
    
    # Use Supabase if available
    if isinstance(conn, SupabaseAdapter):
        supabase_client = conn.client
        
        try:
            # Get all user activity, ordered by most recent first
            activity_result = supabase_client.table('user_activity').select('*').order('created_at', desc=True).limit(1000).execute()
            activities = activity_result.data if activity_result.data else []
            conn.close()
        except Exception as e:
            # Table might not exist in Supabase yet
            st.warning(f"⚠️ User activity table not found in Supabase. Please create it using the SQL script in the setup guide.")
            st.info("""
            **To enable user activity tracking in Supabase:**
            1. Go to Supabase SQL Editor
            2. Run this SQL:
            ```sql
            CREATE TABLE IF NOT EXISTS user_activity (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                username TEXT,
                role TEXT,
                activity_type TEXT,
                ip_address TEXT,
                user_agent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            );
            ```
            """)
            conn.close()
            return
    else:
        # SQLite
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT id, user_id, username, role, activity_type, ip_address, user_agent, created_at
                FROM user_activity
                ORDER BY created_at DESC
                LIMIT 1000
            ''')
            activities = cursor.fetchall()
            conn.close()
        except sqlite3.OperationalError:
            st.warning("⚠️ User activity table not found. It will be created automatically on next app restart.")
            conn.close()
            return
    
    if not activities:
        st.info("📭 No user activity logged yet. Activity will appear here after users log in.")
        return
    
    # Statistics
    st.markdown("### 📈 Activity Statistics")
    
    total_logins = len([a for a in activities if (isinstance(a, dict) and a.get('activity_type') == 'login') or (isinstance(a, tuple) and len(a) > 4 and a[4] == 'login')])
    
    # Count unique users
    unique_users = set()
    for activity in activities:
        if isinstance(activity, dict):
            unique_users.add(activity.get('username', ''))
        else:
            unique_users.add(activity[2] if len(activity) > 2 else '')
    
    # Count by role
    role_counts = {}
    for activity in activities:
        if isinstance(activity, dict):
            role = activity.get('role', 'Unknown')
        else:
            role = activity[3] if len(activity) > 3 else 'Unknown'
        role_counts[role] = role_counts.get(role, 0) + 1
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Activities", len(activities))
    with col2:
        st.metric("Total Logins", total_logins)
    with col3:
        st.metric("Unique Users", len(unique_users))
    with col4:
        st.metric("Most Active Role", max(role_counts.items(), key=lambda x: x[1])[0] if role_counts else "N/A")
    
    st.markdown("---")
    st.markdown("### 📋 Recent Activity Log")
    
    # Filter options
    col1, col2, col3 = st.columns(3)
    with col1:
        filter_role = st.selectbox("Filter by Role", ["All"] + list(set(role_counts.keys())))
    with col2:
        filter_activity = st.selectbox("Filter by Activity", ["All", "login", "logout"])
    with col3:
        limit = st.number_input("Show Last N Records", min_value=10, max_value=1000, value=100, step=10)
    
    # Filter activities
    filtered_activities = activities[:limit]
    if filter_role != "All":
        filtered_activities = [a for a in filtered_activities 
                              if (isinstance(a, dict) and a.get('role') == filter_role) or 
                                 (isinstance(a, tuple) and len(a) > 3 and a[3] == filter_role)]
    if filter_activity != "All":
        filtered_activities = [a for a in filtered_activities 
                              if (isinstance(a, dict) and a.get('activity_type') == filter_activity) or 
                                 (isinstance(a, tuple) and len(a) > 4 and a[4] == filter_activity)]
    
    if not filtered_activities:
        st.info("No activities match the selected filters.")
        return
    
    # Display activities in a table
    activity_data = []
    for activity in filtered_activities:
        if isinstance(activity, dict):
            activity_data.append({
                'Timestamp': activity.get('created_at', 'N/A')[:19] if activity.get('created_at') else 'N/A',
                'Username': activity.get('username', 'N/A'),
                'Role': activity.get('role', 'N/A'),
                'Activity': activity.get('activity_type', 'N/A'),
                'IP Address': activity.get('ip_address', 'N/A'),
            })
        else:
            # SQLite tuple format
            activity_data.append({
                'Timestamp': activity[7][:19] if len(activity) > 7 and activity[7] else 'N/A',
                'Username': activity[2] if len(activity) > 2 else 'N/A',
                'Role': activity[3] if len(activity) > 3 else 'N/A',
                'Activity': activity[4] if len(activity) > 4 else 'N/A',
                'IP Address': activity[5] if len(activity) > 5 else 'N/A',
            })
    
    df = pd.DataFrame(activity_data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # Export option
    st.markdown("---")
    if st.button("📥 Export Activity Log"):
        csv = df.to_csv(index=False)
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name=f"user_activity_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

def admin_settings():
    st.subheader("⚙️ System Settings")
    st.info("System settings and configuration options will be available here.")
    st.markdown("""
    **Future Settings:**
    - System maintenance mode
    - Email notifications
    - Password reset policies
    - Data backup/export
    - System logs
    """)

def reports_dashboard():
    st.subheader("📊 Reports Dashboard")
    
    # Basic statistics
    conn = get_db_connection()
    
    if isinstance(conn, SupabaseAdapter):
        supabase_client = conn.client
        
        # Newsletter count
        newsletter_result = supabase_client.table('newsletters').select('id', count='exact').execute()
        newsletter_count = newsletter_result.count if hasattr(newsletter_result, 'count') else len(newsletter_result.data) if newsletter_result.data else 0
        
        # Event count
        event_result = supabase_client.table('events').select('id', count='exact').execute()
        event_count = event_result.count if hasattr(event_result, 'count') else len(event_result.data) if event_result.data else 0
        
        # Assignment count
        assignment_result = supabase_client.table('assignments').select('id', count='exact').execute()
        assignment_count = assignment_result.count if hasattr(assignment_result, 'count') else len(assignment_result.data) if assignment_result.data else 0
        
        # RSVP count
        rsvp_result = supabase_client.table('event_rsvps').select('id', count='exact').execute()
        rsvp_count = rsvp_result.count if hasattr(rsvp_result, 'count') else len(rsvp_result.data) if rsvp_result.data else 0
        
        conn.close()
    else:
        cursor = conn.cursor()
        
        # Newsletter count
        cursor.execute('SELECT COUNT(*) FROM newsletters')
        newsletter_count = cursor.fetchone()[0]
        
        # Event count
        cursor.execute('SELECT COUNT(*) FROM events')
        event_count = cursor.fetchone()[0]
        
        # Assignment count
        cursor.execute('SELECT COUNT(*) FROM assignments')
        assignment_count = cursor.fetchone()[0]
        
        # RSVP count
        cursor.execute('SELECT COUNT(*) FROM event_rsvps')
        rsvp_count = cursor.fetchone()[0]
        
        conn.close()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Newsletters", newsletter_count)
    with col2:
        st.metric("Events", event_count)
    with col3:
        st.metric("Assignments", assignment_count)
    with col4:
        st.metric("RSVPs", rsvp_count)

def view_newsletter():
    st.subheader("📰 Latest Newsletter")
    
    conn = get_db_connection()
    
    if isinstance(conn, SupabaseAdapter):
        supabase_client = conn.client
        newsletter_result = supabase_client.table('newsletters').select('*').order('created_at', desc=True).limit(1).execute()
        newsletter_data = newsletter_result.data[0] if newsletter_result.data else None
        if newsletter_data:
            newsletter = (newsletter_data.get('id'), newsletter_data.get('title'), newsletter_data.get('content'), 
                         newsletter_data.get('date'), newsletter_data.get('teacher_id'), newsletter_data.get('created_at'))
        else:
            newsletter = None
        conn.close()
    else:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM newsletters ORDER BY created_at DESC LIMIT 1')
        newsletter = cursor.fetchone()
        conn.close()
    
    if newsletter:
        content = json.loads(newsletter[2])
        
        # Download button for parents
        col1, col2 = st.columns([4, 1])
        with col2:
            if st.button("📥 Download PDF", key="parent_download", type="primary"):
                try:
                    pdf_data = generate_newsletter_pdf(content)
                    st.download_button(
                        label="📄 Download Newsletter PDF",
                        data=pdf_data,
                        file_name=f"newsletter_{newsletter[3].replace(' ', '_')}.pdf",
                        mime="application/pdf",
                        key="parent_download_btn"
                    )
                except Exception as e:
                    st.error(f"Error generating PDF: {str(e)}")
        
        # Newsletter Header
        st.markdown(f"""
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="color: #2c3e50; font-size: 2.5em; margin-bottom: 10px; font-family: 'Arial', sans-serif;">
                {content['title']}
            </h1>
            <div style="background-color: #f1c40f; padding: 8px 15px; display: inline-block; border-radius: 5px; margin-bottom: 20px;">
                <h2 style="color: #2c3e50; margin: 0; font-size: 1.2em;">{content['date']}</h2>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Teacher Info Box
        st.markdown("""
        <div style="background-color: #ecf0f1; padding: 15px; border-radius: 8px; margin-bottom: 20px; text-align: right;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div style="font-size: 0.9em; color: #7f8c8d;">
                    📚📖📕<br>
                    MRS. SIMMS<br>
                    Ksimms@washingtonchristian.org<br>
                    240-390-0429
                </div>
                <div style="font-size: 1.1em; font-weight: bold; color: #2c3e50;">
                    MRS. SIMMS
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Two Column Layout
        col1, col2 = st.columns(2, gap="large")
        
        with col1:
            st.markdown("### 📅 UPCOMING EVENTS")
            if content['left_column']['upcoming_events']:
                st.markdown(f"""
                <div style="background-color: #fff; padding: 15px; border-left: 4px solid #3498db; margin-bottom: 20px;">
                    {content['left_column']['upcoming_events'].replace(chr(10), '<br>')}
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("### 📚 OUR LEARNING SNAPSHOT")
            if content['left_column']['learning_snapshot']:
                st.markdown(f"""
                <div style="background-color: #fff; padding: 15px; border-left: 4px solid #e74c3c; margin-bottom: 20px;">
                    {content['left_column']['learning_snapshot'].replace(chr(10), '<br>')}
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("### 📢 IMPORTANT NEWS")
            if content['left_column']['important_news']:
                st.markdown(f"""
                <div style="background-color: #fff; padding: 15px; border-left: 4px solid #f39c12; margin-bottom: 20px;">
                    {content['left_column']['important_news'].replace(chr(10), '<br>')}
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("""
            <div style="text-align: center; margin-top: 30px; color: #7f8c8d; font-style: italic;">
                THE LANGUAGE OF LEARNING
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown("### 📝 WORD LIST")
            if content['right_column']['word_list']:
                st.markdown(f"""
                <div style="background-color: #fff; padding: 15px; border-left: 4px solid #9b59b6; margin-bottom: 20px;">
                    <div style="font-family: 'Courier New', monospace; line-height: 1.8;">
                        {content['right_column']['word_list'].replace(chr(10), '<br>')}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("### 🏠 PRACTICE @ HOME")
            if content['right_column']['practice_home']:
                st.markdown(f"""
                <div style="background-color: #fff; padding: 15px; border-left: 4px solid #27ae60; margin-bottom: 20px;">
                    {content['right_column']['practice_home'].replace(chr(10), '<br>')}
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("### 🙏 MEMORY VERSE")
            if content['right_column']['memory_verse']:
                st.markdown(f"""
                <div style="background-color: #fff; padding: 15px; border-left: 4px solid #e67e22; margin-bottom: 20px;">
                    <p style="font-weight: bold; margin-bottom: 10px;">Psalm 145:1-2 NIV</p>
                    <div style="font-style: italic; line-height: 1.6; text-align: center;">
                        {content['right_column']['memory_verse'].replace(chr(10), '<br>')}
                    </div>
                    <p style="margin-top: 10px; font-size: 0.9em; color: #7f8c8d;">
                        (Our Memory Verse for the next two weeks - Due 10/10/25)
                    </p>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("No newsletters available yet.")

def view_events():
    st.subheader("📅 Upcoming Events")
    
    conn = get_db_connection()
    
    if isinstance(conn, SupabaseAdapter):
        supabase_client = conn.client
        from datetime import date as date_obj
        today = date_obj.today().strftime('%Y-%m-%d')
        events_result = supabase_client.table('events').select('*').gte('event_date', today).order('event_date').execute()
        events_data = events_result.data if events_result.data else []
        # Convert to list of tuples for compatibility
        events = [(e.get('id'), e.get('title'), e.get('description'), e.get('event_date'), 
                  e.get('event_time'), e.get('location'), e.get('max_attendees'), 
                  e.get('teacher_id'), e.get('created_at')) for e in events_data]
        conn.close()
    else:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM events 
            WHERE event_date >= date('now')
            ORDER BY event_date
        ''')
        events = cursor.fetchall()
        conn.close()
    
    for event in events:
        with st.expander(f"{event[1]} - {event[3]} at {event[4]}"):
            st.markdown(f"**Description:** {event[2]}")
            st.markdown(f"**Location:** {event[5]}")
            st.markdown(f"**Max Attendees:** {event[6]}")
            
            # RSVP button
            if st.button(f"RSVP for {event[1]}", key=f"rsvp_{event[0]}"):
                # Simple RSVP - in a real app, this would be more sophisticated
                st.success("RSVP submitted! (This is a demo)")

def view_assignments():
    st.subheader("📝 Current Assignments")
    
    conn = get_db_connection()
    
    if isinstance(conn, SupabaseAdapter):
        supabase_client = conn.client
        from datetime import date as date_obj
        today = date_obj.today().strftime('%Y-%m-%d')
        assignments_result = supabase_client.table('assignments').select('*').gte('due_date', today).order('due_date').execute()
        assignments_data = assignments_result.data if assignments_result.data else []
        # Convert to list of tuples for compatibility
        assignments = [(a.get('id'), a.get('title'), a.get('description'), a.get('subject'), 
                       a.get('due_date'), a.get('word_list'), a.get('memory_verse'), 
                       a.get('teacher_id'), a.get('created_at')) for a in assignments_data]
        conn.close()
    else:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM assignments 
            WHERE due_date >= date('now')
            ORDER BY due_date
        ''')
        assignments = cursor.fetchall()
        conn.close()
    
    for assignment in assignments:
        with st.expander(f"{assignment[1]} - Due {assignment[4]}"):
            st.markdown(f"**Subject:** {assignment[3]}")
            st.markdown(f"**Description:** {assignment[2]}")
            if assignment[5]:
                st.markdown(f"**Word List:**\n{assignment[5]}")
            if assignment[6]:
                st.markdown(f"**Memory Verse:**\n{assignment[6]}")
            
            # Mark as completed (demo)
            if st.button(f"Mark as Completed", key=f"complete_{assignment[0]}"):
                st.success("Assignment marked as completed! (This is a demo)")

def view_child_progress():
    st.subheader("👶 My Child's Progress")
    st.markdown("**View your child's assignment progress and completion status**")
    
    user = st.session_state.user
    parent_id = user.get('id')
    
    conn = get_db_connection()
    
    # Find the student linked to this parent
    if isinstance(conn, SupabaseAdapter):
        supabase_client = conn.client
        student_result = supabase_client.table('users').select('*').eq('parent_id', parent_id).eq('role', 'student').execute()
        students = student_result.data if student_result.data else []
        conn.close()
    else:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE parent_id = ? AND role = ?', (parent_id, 'student'))
        students = cursor.fetchall()
        conn.close()
    
    if not students:
        st.info("""
        👨‍👩‍👧‍👦 **No student linked to your account yet.**
        
        Please contact your child's teacher to link your parent account to your child's student account.
        Once linked, you'll be able to view your child's progress here.
        """)
        return
    
    # If multiple students, let parent select which one
    if len(students) > 1:
        student_options = {}
        for s in students:
            if isinstance(s, dict):
                student_id = s.get('id')
                name = s.get('name', s.get('username', 'Unknown'))
            else:
                student_id = s[0]
                name = s[5] if len(s) > 5 and s[5] else (s[1] if len(s) > 1 else 'Unknown')
            student_options[name] = student_id
        
        selected_student_name = st.selectbox("Select Child", list(student_options.keys()))
        selected_student_id = student_options[selected_student_name]
    else:
        # Single student
        if isinstance(students[0], dict):
            selected_student_id = students[0].get('id')
            selected_student_name = students[0].get('name', students[0].get('username', 'Your Child'))
        else:
            selected_student_id = students[0][0]
            selected_student_name = students[0][5] if len(students[0]) > 5 and students[0][5] else (students[0][1] if len(students[0]) > 1 else 'Your Child')
    
    st.markdown(f"### 📊 Progress for {selected_student_name}")
    
    # Get all assignments
    conn = get_db_connection()
    if isinstance(conn, SupabaseAdapter):
        supabase_client = conn.client
        assignments_result = supabase_client.table('assignments').select('*').order('created_at', desc=True).execute()
        assignments = assignments_result.data if assignments_result.data else []
        conn.close()
    else:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM assignments ORDER BY created_at DESC')
        assignments = cursor.fetchall()
        conn.close()
    
    if not assignments:
        st.info("No assignments found. Assignments will appear here once the teacher creates them.")
        return
    
    # Get student progress
    conn = get_db_connection()
    if isinstance(conn, SupabaseAdapter):
        supabase_client = conn.client
        progress_result = supabase_client.table('student_progress').select('*').eq('student_id', selected_student_id).execute()
        progress_data = progress_result.data if progress_result.data else []
        conn.close()
    else:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM student_progress WHERE student_id = ?', (selected_student_id,))
        progress_data = cursor.fetchall()
        conn.close()
    
    # Create progress lookup
    progress_lookup = {}
    for p in progress_data:
        if isinstance(p, dict):
            assignment_id = p.get('assignment_id')
            completed = p.get('completed', False)
            submitted_at = p.get('submitted_at')
            word_list_progress = p.get('word_list_progress', '')
            memory_verse_progress = p.get('memory_verse_progress', '')
        else:
            assignment_id = p[2] if len(p) > 2 else None
            completed = p[5] if len(p) > 5 else False
            submitted_at = p[6] if len(p) > 6 else None
            word_list_progress = p[3] if len(p) > 3 else ''
            memory_verse_progress = p[4] if len(p) > 4 else ''
        if assignment_id:
            progress_lookup[assignment_id] = {
                'completed': completed,
                'submitted_at': submitted_at,
                'word_list_progress': word_list_progress,
                'memory_verse_progress': memory_verse_progress
            }
    
    # Calculate statistics
    total_assignments = len(assignments)
    completed_count = sum(1 for a in assignments if progress_lookup.get(a.get('id') if isinstance(a, dict) else a[0], {}).get('completed', False))
    completion_rate = (completed_count / total_assignments * 100) if total_assignments > 0 else 0
    
    # Display statistics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Assignments", total_assignments)
    with col2:
        st.metric("Completed", completed_count)
    with col3:
        st.metric("Completion Rate", f"{completion_rate:.0f}%")
    
    st.markdown("---")
    st.markdown("### 📝 Assignment Details")
    
    # Display assignments with progress
    for assignment in assignments:
        if isinstance(assignment, dict):
            assignment_id = assignment.get('id')
            title = assignment.get('title', 'N/A')
            description = assignment.get('description', '')
            due_date = assignment.get('due_date', 'N/A')
            word_list = assignment.get('word_list', '')
            memory_verse = assignment.get('memory_verse', '')
        else:
            assignment_id = assignment[0]
            title = assignment[1] if len(assignment) > 1 else 'N/A'
            description = assignment[2] if len(assignment) > 2 else ''
            due_date = assignment[4] if len(assignment) > 4 else 'N/A'
            word_list = assignment[5] if len(assignment) > 5 else ''
            memory_verse = assignment[6] if len(assignment) > 6 else ''
        
        progress = progress_lookup.get(assignment_id, {})
        completed = progress.get('completed', False)
        submitted_at = progress.get('submitted_at')
        word_list_progress = progress.get('word_list_progress', '')
        memory_verse_progress = progress.get('memory_verse_progress', '')
        
        status_icon = "✅" if completed else "⏳"
        status_text = "Completed" if completed else "In Progress"
        status_color = "🟢" if completed else "🟡"
        
        with st.expander(f"{status_color} {title} - {status_text}", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown(f"**Due Date:** {due_date}")
                if description:
                    st.markdown(f"**Description:**\n{description}")
            
            with col2:
                if completed and submitted_at:
                    st.success(f"✅ **Submitted on:** {submitted_at[:10] if submitted_at else 'N/A'}")
                else:
                    st.warning("⏳ **Not yet completed**")
            
            # Word list progress
            if word_list:
                st.markdown("---")
                st.markdown("**📚 Word List:**")
                if word_list_progress:
                    st.info(f"Progress: {word_list_progress}")
                else:
                    st.warning("Word list not started yet")
                st.text(word_list)
            
            # Memory verse progress
            if memory_verse:
                st.markdown("---")
                st.markdown("**📖 Memory Verse:**")
                if memory_verse_progress:
                    st.info(f"Progress: {memory_verse_progress}")
                else:
                    st.warning("Memory verse not started yet")
                st.text(memory_verse)

def view_student_assignments():
    st.subheader("📝 My Assignments")
    st.markdown("**View and complete your assignments**")
    
    user = st.session_state.user
    student_id = user.get('id')
    
    # Get all assignments
    conn = get_db_connection()
    if isinstance(conn, SupabaseAdapter):
        supabase_client = conn.client
        assignments_result = supabase_client.table('assignments').select('*').order('created_at', desc=True).execute()
        assignments = assignments_result.data if assignments_result.data else []
        conn.close()
    else:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM assignments ORDER BY created_at DESC')
        assignments = cursor.fetchall()
        conn.close()
    
    if not assignments:
        st.info("No assignments found. Your teacher will add assignments here.")
        return
    
    # Get student progress
    conn = get_db_connection()
    if isinstance(conn, SupabaseAdapter):
        supabase_client = conn.client
        progress_result = supabase_client.table('student_progress').select('*').eq('student_id', student_id).execute()
        progress_data = progress_result.data if progress_result.data else []
        conn.close()
    else:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM student_progress WHERE student_id = ?', (student_id,))
        progress_data = cursor.fetchall()
        conn.close()
    
    # Create progress lookup
    progress_lookup = {}
    for p in progress_data:
        if isinstance(p, dict):
            assignment_id = p.get('assignment_id')
            completed = p.get('completed', False)
            word_list_progress = p.get('word_list_progress', '')
            memory_verse_progress = p.get('memory_verse_progress', '')
        else:
            assignment_id = p[2] if len(p) > 2 else None
            completed = p[5] if len(p) > 5 else False
            word_list_progress = p[3] if len(p) > 3 else ''
            memory_verse_progress = p[4] if len(p) > 4 else ''
        if assignment_id:
            progress_lookup[assignment_id] = {
                'completed': completed,
                'word_list_progress': word_list_progress,
                'memory_verse_progress': memory_verse_progress
            }
    
    # Display assignments
    for assignment in assignments:
        if isinstance(assignment, dict):
            assignment_id = assignment.get('id')
            title = assignment.get('title', 'N/A')
            description = assignment.get('description', '')
            due_date = assignment.get('due_date', 'N/A')
            word_list = assignment.get('word_list', '')
            memory_verse = assignment.get('memory_verse', '')
        else:
            assignment_id = assignment[0]
            title = assignment[1] if len(assignment) > 1 else 'N/A'
            description = assignment[2] if len(assignment) > 2 else ''
            due_date = assignment[4] if len(assignment) > 4 else 'N/A'
            word_list = assignment[5] if len(assignment) > 5 else ''
            memory_verse = assignment[6] if len(assignment) > 6 else ''
        
        progress = progress_lookup.get(assignment_id, {})
        completed = progress.get('completed', False)
        
        status_icon = "✅" if completed else "📝"
        status_text = "Completed" if completed else "In Progress"
        
        with st.expander(f"{status_icon} {title} - {status_text}", expanded=not completed):
            st.markdown(f"**Due Date:** {due_date}")
            
            if description:
                st.markdown(f"**Description:**\n{description}")
            
            # Word list section
            if word_list:
                st.markdown("---")
                st.markdown("**📚 Word List:**")
                st.text(word_list)
                
                current_progress = progress.get('word_list_progress', '')
                word_progress = st.text_area(
                    "My Word List Progress",
                    value=current_progress,
                    help="Write your progress on the word list here",
                    key=f"word_progress_{assignment_id}",
                    height=100
                )
            
            # Memory verse section
            if memory_verse:
                st.markdown("---")
                st.markdown("**📖 Memory Verse:**")
                st.text(memory_verse)
                
                current_verse_progress = progress.get('memory_verse_progress', '')
                verse_progress = st.text_area(
                    "My Memory Verse Progress",
                    value=current_verse_progress,
                    help="Write your progress on the memory verse here",
                    key=f"verse_progress_{assignment_id}",
                    height=100
                )
            
            # Save progress button
            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button("💾 Save Progress", key=f"save_progress_{assignment_id}", type="primary"):
                    conn = get_db_connection()
                    progress_id = str(uuid.uuid4())
                    
                    if isinstance(conn, SupabaseAdapter):
                        supabase_client = conn.client
                        # Check if progress exists
                        existing = supabase_client.table('student_progress').select('id').eq('student_id', student_id).eq('assignment_id', assignment_id).execute()
                        
                        progress_data = {
                            'student_id': student_id,
                            'assignment_id': assignment_id,
                            'word_list_progress': word_progress if word_list else '',
                            'memory_verse_progress': verse_progress if memory_verse else '',
                            'completed': False
                        }
                        
                        if existing.data:
                            # Update existing
                            supabase_client.table('student_progress').update(progress_data).eq('id', existing.data[0]['id']).execute()
                        else:
                            # Create new
                            progress_data['id'] = progress_id
                            supabase_client.table('student_progress').insert(progress_data).execute()
                        conn.close()
                    else:
                        cursor = conn.cursor()
                        # Check if progress exists
                        cursor.execute('SELECT id FROM student_progress WHERE student_id = ? AND assignment_id = ?', (student_id, assignment_id))
                        existing = cursor.fetchone()
                        
                        if existing:
                            # Update existing
                            cursor.execute('''
                                UPDATE student_progress 
                                SET word_list_progress = ?, memory_verse_progress = ?
                                WHERE student_id = ? AND assignment_id = ?
                            ''', (word_progress if word_list else '', verse_progress if memory_verse else '', student_id, assignment_id))
                        else:
                            # Create new
                            cursor.execute('''
                                INSERT INTO student_progress (id, student_id, assignment_id, word_list_progress, memory_verse_progress, completed)
                                VALUES (?, ?, ?, ?, ?, ?)
                            ''', (progress_id, student_id, assignment_id, word_progress if word_list else '', verse_progress if memory_verse else '', False))
                        conn.commit()
                        conn.close()
                    
                    st.success("✅ Progress saved!")
                    st.rerun()
            
            with col2:
                if st.button("✅ Mark as Completed", key=f"complete_{assignment_id}"):
                    conn = get_db_connection()
                    
                    if isinstance(conn, SupabaseAdapter):
                        supabase_client = conn.client
                        # Check if progress exists
                        existing = supabase_client.table('student_progress').select('id').eq('student_id', student_id).eq('assignment_id', assignment_id).execute()
                        
                        progress_data = {
                            'student_id': student_id,
                            'assignment_id': assignment_id,
                            'completed': True,
                            'submitted_at': datetime.now().isoformat()
                        }
                        
                        if existing.data:
                            # Update existing
                            supabase_client.table('student_progress').update(progress_data).eq('id', existing.data[0]['id']).execute()
                        else:
                            # Create new
                            progress_data['id'] = str(uuid.uuid4())
                            supabase_client.table('student_progress').insert(progress_data).execute()
                        conn.close()
                    else:
                        cursor = conn.cursor()
                        # Check if progress exists
                        cursor.execute('SELECT id FROM student_progress WHERE student_id = ? AND assignment_id = ?', (student_id, assignment_id))
                        existing = cursor.fetchone()
                        
                        if existing:
                            # Update existing
                            cursor.execute('''
                                UPDATE student_progress 
                                SET completed = ?, submitted_at = ?
                                WHERE student_id = ? AND assignment_id = ?
                            ''', (True, datetime.now().isoformat(), student_id, assignment_id))
                        else:
                            # Create new
                            progress_id = str(uuid.uuid4())
                            cursor.execute('''
                                INSERT INTO student_progress (id, student_id, assignment_id, completed, submitted_at)
                                VALUES (?, ?, ?, ?, ?)
                            ''', (progress_id, student_id, assignment_id, True, datetime.now().isoformat()))
                        conn.commit()
                        conn.close()
                    
                    st.success("🎉 Assignment marked as completed!")
                    st.rerun()

if __name__ == "__main__":
    main()
