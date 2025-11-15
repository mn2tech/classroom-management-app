# Supabase Setup Guide - Fix Database Persistence

This guide will help you set up Supabase (PostgreSQL database) to permanently fix the data loss issue on Streamlit Cloud.

## Why Supabase?

- ✅ **Free tier** - Perfect for small apps
- ✅ **Data persists** - Never lose data on app restarts
- ✅ **Easy setup** - 15 minutes to complete
- ✅ **Automatic backups** - Your data is safe
- ✅ **Better performance** - Faster than SQLite

## Step 1: Create Supabase Account

1. Go to [https://supabase.com](https://supabase.com)
2. Click "Start your project" or "Sign up"
3. Sign up with GitHub, Google, or email
4. Verify your email if needed

## Step 2: Create a New Project

1. Click "New Project"
2. Fill in:
   - **Name**: `classroom-management-app` (or any name)
   - **Database Password**: Create a strong password (save it!)
   - **Region**: Choose closest to your users
   - **Pricing Plan**: Free (for development)
3. Click "Create new project"
4. Wait 2-3 minutes for project setup

## Step 3: Get Your Credentials

1. In your Supabase project dashboard, click the **Settings** icon (gear) in the left sidebar
2. Click **API** in the settings menu
3. You'll see:
   - **Project URL** (e.g., `https://xxxxx.supabase.co`)
   - **anon/public key** (long string starting with `eyJ...`)
4. Copy both values - you'll need them in Step 5

## Step 4: Create Database Tables

1. In Supabase dashboard, click **SQL Editor** in the left sidebar
2. Click **New query**
3. Copy and paste the SQL below:

```sql
-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    name TEXT,
    parent_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_id) REFERENCES users (id)
);

-- Create newsletters table
CREATE TABLE IF NOT EXISTS newsletters (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT,
    date TEXT,
    teacher_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (teacher_id) REFERENCES users (id)
);

-- Create events table
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    event_date TEXT,
    event_time TEXT,
    location TEXT,
    max_attendees INTEGER,
    teacher_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (teacher_id) REFERENCES users (id)
);

-- Create event_rsvps table
CREATE TABLE IF NOT EXISTS event_rsvps (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    parent_id TEXT NOT NULL,
    attendees_count INTEGER,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES events (id),
    FOREIGN KEY (parent_id) REFERENCES users (id)
);

-- Create assignments table
CREATE TABLE IF NOT EXISTS assignments (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    subject TEXT,
    due_date TEXT,
    word_list TEXT,
    memory_verse TEXT,
    teacher_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (teacher_id) REFERENCES users (id)
);

-- Create student_progress table
CREATE TABLE IF NOT EXISTS student_progress (
    id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL,
    assignment_id TEXT NOT NULL,
    word_list_progress TEXT,
    memory_verse_progress TEXT,
    completed BOOLEAN DEFAULT FALSE,
    submitted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES users (id),
    FOREIGN KEY (assignment_id) REFERENCES assignments (id)
);

-- Create user_activity table (for tracking logins and user activity)
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

-- Enable Row Level Security (RLS) - Optional but recommended
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE newsletters ENABLE ROW LEVEL SECURITY;
ALTER TABLE events ENABLE ROW LEVEL SECURITY;
ALTER TABLE event_rsvps ENABLE ROW LEVEL SECURITY;
ALTER TABLE assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_progress ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_activity ENABLE ROW LEVEL SECURITY;

-- Create policies to allow all operations (for now - can be restricted later)
-- Note: If policies already exist, you can skip this section or drop them first
-- Drop existing policies if they exist (optional - only if you get "already exists" error)
DROP POLICY IF EXISTS "Enable all operations for users" ON users;
DROP POLICY IF EXISTS "Enable all operations for newsletters" ON newsletters;
DROP POLICY IF EXISTS "Enable all operations for events" ON events;
DROP POLICY IF EXISTS "Enable all operations for event_rsvps" ON event_rsvps;
DROP POLICY IF EXISTS "Enable all operations for assignments" ON assignments;
DROP POLICY IF EXISTS "Enable all operations for student_progress" ON student_progress;
DROP POLICY IF EXISTS "Enable all operations for user_activity" ON user_activity;

-- Create policies
CREATE POLICY "Enable all operations for users" ON users FOR ALL USING (true);
CREATE POLICY "Enable all operations for newsletters" ON newsletters FOR ALL USING (true);
CREATE POLICY "Enable all operations for events" ON events FOR ALL USING (true);
CREATE POLICY "Enable all operations for event_rsvps" ON event_rsvps FOR ALL USING (true);
CREATE POLICY "Enable all operations for assignments" ON assignments FOR ALL USING (true);
CREATE POLICY "Enable all operations for student_progress" ON student_progress FOR ALL USING (true);
CREATE POLICY "Enable all operations for user_activity" ON user_activity FOR ALL USING (true);
```

4. Click **Run** (or press Ctrl+Enter)
5. You should see "Success. No rows returned"

**Note:** If you get an error saying policies already exist, the script now includes `DROP POLICY IF EXISTS` statements that will handle this automatically. 

**For existing databases:** If your `users` table already exists and you need to add the `parent_id` column for student management, run this:

```sql
-- Add parent_id column to existing users table (for linking students to parents)
ALTER TABLE users ADD COLUMN IF NOT EXISTS parent_id TEXT;
ALTER TABLE users ADD CONSTRAINT fk_parent FOREIGN KEY (parent_id) REFERENCES users(id);
```

If you only need to add the `user_activity` table (and other tables already exist), you can run just this:

```sql
-- Create user_activity table (for tracking logins and user activity)
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

ALTER TABLE user_activity ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Enable all operations for user_activity" ON user_activity;
CREATE POLICY "Enable all operations for user_activity" ON user_activity FOR ALL USING (true);
```

## Step 5: Configure Streamlit Cloud

1. Go to your Streamlit Cloud dashboard: [https://share.streamlit.io](https://share.streamlit.io)
2. Click on your app (`classroom-management-app`)
3. Click **⚙️ Settings** (three dots menu)
4. Click **Secrets**
5. Add the following secrets:

```toml
[supabase]
url = "YOUR_PROJECT_URL_HERE"
key = "YOUR_ANON_KEY_HERE"
```

Replace:
- `YOUR_PROJECT_URL_HERE` with your Supabase Project URL
- `YOUR_ANON_KEY_HERE` with your Supabase anon/public key

6. Click **Save**

## Step 6: Deploy and Test

1. Your app will automatically redeploy when you save secrets
2. Wait for deployment to complete
3. Log in to your app
4. Create a test user account
5. Restart the app (or wait for it to restart)
6. Verify the user account still exists ✅

## Troubleshooting

### "Supabase configuration error"
- Check that your secrets are correct
- Make sure there are no extra spaces in the secrets
- Verify the URL starts with `https://`

### "Table does not exist"
- Go back to Step 4 and run the SQL script again
- Check the Supabase SQL Editor for any errors

### "Permission denied"
- Check that RLS policies were created correctly
- Try running the policy creation SQL again

### Still using SQLite?
- Make sure secrets are saved correctly
- Check Streamlit Cloud logs for errors
- Verify Supabase package is installed (check requirements.txt)

## Local Development

For local development, you can either:

**Option A: Use SQLite (default)**
- Just run the app - it will use SQLite automatically
- No configuration needed

**Option B: Use Supabase locally**
1. Create a `.streamlit/secrets.toml` file (create `.streamlit` folder if needed)
2. Add the same secrets as in Step 5
3. Run the app - it will use Supabase

## Verification

After setup, you should see in the Admin Dashboard → System Info:
- **Database:** Supabase (PostgreSQL) ✅
- **Status:** Connected ✅

## Support

If you encounter issues:
1. Check Streamlit Cloud logs
2. Check Supabase dashboard → Logs
3. Verify all steps were completed
4. Contact support if needed

## Next Steps

Once Supabase is working:
- ✅ Data will persist permanently
- ✅ No more data loss on app restarts
- ✅ Better performance
- ✅ Automatic backups
- ✅ Ready for production use

---

**Setup Time:** ~15 minutes  
**Difficulty:** Easy  
**Result:** Permanent data persistence! 🎉


