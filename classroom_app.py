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

# Page configuration
st.set_page_config(
    page_title="WCA Classroom Manager",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Database initialization
def init_database():
    conn = sqlite3.connect('classroom.db')
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
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
    conn = sqlite3.connect('classroom.db')
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

# Authentication
def authenticate_user(username: str, password: str) -> Optional[Dict]:
    conn = sqlite3.connect('classroom.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        return {
            'id': user[0],
            'username': user[1],
            'role': user[3],
            'email': user[4],
            'phone': user[5]
        }
    return None

def create_default_users():
    conn = sqlite3.connect('classroom.db')
    cursor = conn.cursor()
    
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
    conn = sqlite3.connect('classroom.db')
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
            
            # Mark that we've created a sample newsletter in this session
            st.session_state.sample_newsletter_created = True
    
    conn.commit()
    conn.close()

def debug_users():
    """Debug function to check users in database"""
    conn = sqlite3.connect('classroom.db')
    cursor = conn.cursor()
    cursor.execute('SELECT username, role, email FROM users')
    users = cursor.fetchall()
    conn.close()
    return users

def clear_newsletters():
    """Clear all newsletters from database"""
    conn = sqlite3.connect('classroom.db')
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
                story.append(Paragraph("Test on Fridays, due October 3, 2025.", content_style))
                story.append(Paragraph(right_column['word_list'].replace('\n', '<br/>'), content_style))
                story.append(Paragraph("Bonus: angry, praiseworthy, listen, faithful", content_style))
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

# conn = sqlite3.connect('classroom.db')
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
                st.session_state.user = user
                st.sidebar.success(f"Logged in as {user['role']}: {user['username']}")
                st.rerun()
            else:
                st.sidebar.error("Invalid credentials")
                st.sidebar.info(f"Debug: Username='{username}', Password='{password}'")
        
        st.sidebar.markdown("---")
        st.sidebar.markdown("**Demo Credentials:**")
        st.sidebar.markdown("Teacher: mrs.simms / password123")
        st.sidebar.markdown("Parent: parent1 / password123")
        
        # Debug: Show available users
        with st.sidebar.expander("🔍 Debug: Available Users"):
            users = debug_users()
            for user in users:
                st.write(f"- {user[0]} ({user[1]}) - {user[2]}")
        
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
    st.sidebar.success(f"Welcome, {user['username']}!")
    st.sidebar.info(f"Role: {user['role']}")
    
    if st.sidebar.button("Logout"):
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
    if user['role'] == 'teacher':
        teacher_dashboard()
    elif user['role'] == 'parent':
        parent_dashboard()
    else:
        st.error(f"Invalid user role: {user['role']}")
        st.write(f"Debug info: {user}")

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

def parent_dashboard():
    st.header("👨‍👩‍👧‍👦 Parent Dashboard")
    
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
                conn = sqlite3.connect('classroom.db')
                cursor = conn.cursor()
                
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
        conn = sqlite3.connect('classroom.db')
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
                conn = sqlite3.connect('classroom.db')
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
    conn = sqlite3.connect('classroom.db')
    cursor = conn.cursor()
    limit = None if st.session_state.get('show_all_newsletters', False) else 5
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
            col1, col2, col3 = st.columns([2, 1, 1])
            with col2:
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
            with col3:
                if st.button("🗑️ Delete", key=f"delete_{newsletter[0]}", type="secondary"):
                    st.session_state[f'confirm_delete_{newsletter[0]}'] = True
                    st.write(f"Debug: Delete button clicked for newsletter {newsletter[0]} - {newsletter[1]}")
                    st.rerun()
            
            # Confirmation dialog for individual delete
            if st.session_state.get(f'confirm_delete_{newsletter[0]}', False):
                st.warning(f"⚠️ Are you sure you want to delete '{newsletter[1]}'? This action cannot be undone!")
                st.write(f"Debug: Confirmation dialog showing for newsletter {newsletter[0]}")
                col1, col2, col3 = st.columns([1, 1, 2])
                with col1:
                    if st.button("✅ Yes, Delete", key=f"confirm_yes_{newsletter[0]}", type="primary"):
                        st.write(f"Debug: Confirming delete for newsletter {newsletter[0]} - {newsletter[1]}")
                        conn = sqlite3.connect('classroom.db')
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
                        <p style="margin-bottom: 10px; font-weight: bold;">Test on Fridays, due October 3, 2025.</p>
                        <div style="font-family: 'Courier New', monospace; line-height: 1.8;">
                            {content['right_column']['word_list'].replace(chr(10), '<br>')}
                        </div>
                        <p style="margin-top: 10px; font-weight: bold;">Bonus: angry, praiseworthy, listen, faithful</p>
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
            conn = sqlite3.connect('classroom.db')
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
    conn = sqlite3.connect('classroom.db')
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
            conn = sqlite3.connect('classroom.db')
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
            conn = sqlite3.connect('classroom.db')
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
    conn = sqlite3.connect('classroom.db')
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
    
    # This would typically show student progress, but for MVP we'll show a placeholder
    st.info("Student management features coming soon! This will include:")
    st.markdown("- Student progress tracking")
    st.markdown("- Individual assignment completion")
    st.markdown("- Parent communication logs")
    st.markdown("- Performance analytics")

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
                key="new_student_name"
            )
        
        if st.button("➕ Create Parent Account", type="primary", key="create_parent_btn"):
            if not parent_username or not parent_password or not parent_email:
                st.error("Please fill in at least Username, Password, and Email address.")
            else:
                conn = sqlite3.connect('classroom.db')
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
                        INSERT INTO users (id, username, password, role, email, phone)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (parent_id, parent_username, parent_password, 'parent', parent_email, parent_phone or ''))
                    
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
    
    # Demo accounts warning
    st.markdown("---")
    st.warning("⚠️ **Demo Accounts Note:** The accounts 'parent1', 'parent2', 'parent3' are demo/test accounts. Delete them before production use or keep them separate from real parent accounts.")
    
    # View and manage existing parent accounts
    st.subheader("📋 Existing Parent Accounts")
    
    conn = sqlite3.connect('classroom.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, username, email, phone, created_at 
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
            parent_id, username, email, phone, created_at = parent
            with st.expander(f"👤 {username} - {email or 'No email'}", expanded=False):
                col1, col2, col3 = st.columns([2, 1, 1])
                
                with col1:
                    st.markdown(f"""
                    **Username:** `{username}`  
                    **Email:** {email or 'Not provided'}  
                    **Phone:** {phone or 'Not provided'}  
                    **Created:** {created_at[:10] if created_at else 'N/A'}
                    """)
                
                with col2:
                    if st.button("📋 Show Credentials", key=f"show_creds_{parent_id}"):
                        # Get password from database
                        conn = sqlite3.connect('classroom.db')
                        cursor = conn.cursor()
                        cursor.execute('SELECT password FROM users WHERE id = ?', (parent_id,))
                        password_result = cursor.fetchone()
                        password = password_result[0] if password_result else "Password not found"
                        conn.close()
                        
                        st.info(f"""
                        **Login Credentials for {username}:**
                        - **Username:** `{username}`
                        - **Password:** `{password}`
                        - **Email:** {email or 'Not provided'}
                        - **App Link:** https://classroom-management-app-wca.streamlit.app
                        
                        Share these credentials securely with the parent.
                        """)
                
                with col3:
                    if st.button("🗑️ Delete", key=f"delete_parent_{parent_id}", type="secondary"):
                        if st.session_state.get(f"confirm_delete_parent_{parent_id}", False):
                            conn = sqlite3.connect('classroom.db')
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
                                conn = sqlite3.connect('classroom.db')
                                cursor = conn.cursor()
                                cursor.execute('DELETE FROM users WHERE id = ?', (parent_id,))
                                conn.commit()
                                conn.close()
                                st.success("Parent account deleted!")
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

def reports_dashboard():
    st.subheader("📊 Reports Dashboard")
    
    # Basic statistics
    conn = sqlite3.connect('classroom.db')
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
    
    conn = sqlite3.connect('classroom.db')
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
                    <p style="margin-bottom: 10px; font-weight: bold;">Test on Fridays, due October 3, 2025.</p>
                    <div style="font-family: 'Courier New', monospace; line-height: 1.8;">
                        {content['right_column']['word_list'].replace(chr(10), '<br>')}
                    </div>
                    <p style="margin-top: 10px; font-weight: bold;">Bonus: angry, praiseworthy, listen, faithful</p>
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
    
    conn = sqlite3.connect('classroom.db')
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
    
    conn = sqlite3.connect('classroom.db')
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
    
    st.info("Student progress tracking coming soon! This will show:")
    st.markdown("- Assignment completion status")
    st.markdown("- Word list progress")
    st.markdown("- Memory verse progress")
    st.markdown("- Overall performance metrics")

if __name__ == "__main__":
    main()
