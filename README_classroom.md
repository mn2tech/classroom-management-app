# WCA Classroom Manager MVP

A comprehensive classroom management application for Washington Christian Academy, specifically designed for Mrs. Simms' 2nd grade class.

## Features

### 🏫 Teacher Features
- **Newsletter Management**: Create and manage digital newsletters with sections for events, learning snapshots, and assignments
- **Event Management**: Create events with RSVP functionality for parents
- **Assignment Tracking**: Manage homework, word lists, and memory verses
- **Student Progress**: Track individual student progress and completion
- **Reports Dashboard**: View analytics and statistics

### 👨‍👩‍👧‍👦 Parent Features
- **Newsletter Access**: View latest classroom newsletters
- **Event RSVP**: RSVP for classroom events and field trips
- **Assignment Tracking**: View current assignments and due dates
- **Child Progress**: Monitor your child's academic progress

## Quick Start

1. **Install Dependencies**
   ```bash
   pip install -r requirements_classroom.txt
   ```

2. **Run the Application**
   ```bash
   streamlit run classroom_app.py
   ```

3. **Login with Demo Credentials**
   - **Teacher**: `mrs.simms` / `password123`
   - **Parent**: `parent1` / `password123`

## Database Schema

The app uses SQLite with the following tables:
- `users` - Teacher and parent accounts
- `newsletters` - Newsletter content and metadata
- `events` - Classroom events and field trips
- `event_rsvps` - Parent RSVPs for events
- `assignments` - Homework and assignments
- `student_progress` - Individual student progress tracking

## Key Features Implemented

### Newsletter System
- Template-based newsletter creation
- Left/right column layout matching the original design
- Sections for events, learning snapshots, word lists, and memory verses
- Digital distribution to parents

### Event Management
- Create events with date, time, location, and capacity
- RSVP system for parents
- Event tracking and analytics

### Assignment Management
- Subject-specific assignments (Bible/TFT, Language Arts, Math, Science, Social Studies)
- Word list management
- Memory verse tracking
- Due date management

### User Authentication
- Role-based access (Teacher vs Parent)
- Secure login system
- User management

## Future Enhancements

- Real-time notifications
- Mobile app version
- Integration with school systems
- Advanced analytics and reporting
- Parent-teacher messaging
- Student portfolio management
- Grade book integration

## Technical Stack

- **Frontend**: Streamlit
- **Backend**: Python
- **Database**: SQLite
- **Authentication**: Custom session-based
- **Deployment**: Local/Cloud ready

## Development Notes

This MVP is designed to be easily extensible and can be deployed to cloud platforms like Heroku, AWS, or Google Cloud. The modular design allows for easy addition of new features and integration with existing school systems.

## Contact

For questions or support, contact NM2Tech development team.
