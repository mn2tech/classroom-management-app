# Local Testing Guide - Supabase Integration

## Quick Setup (2 minutes)

### Step 1: Get Your Supabase Credentials

1. Go to [https://supabase.com](https://supabase.com)
2. Sign in and select your project
3. Click **Settings** (gear icon) → **API**
4. Copy:
   - **Project URL** (e.g., `https://xxxxx.supabase.co`)
   - **anon public key** (long string starting with `eyJ...`)

### Step 2: Add Credentials to Local Secrets

1. Open `.streamlit/secrets.toml` in your project
2. Replace the placeholder values:
   ```toml
   [supabase]
   url = "https://your-actual-project-url.supabase.co"
   key = "your-actual-anon-key-here"
   ```
3. Save the file

### Step 3: Install Dependencies

Make sure Supabase is installed:
```bash
pip install -r requirements.txt
```

### Step 4: Run the App Locally

```bash
streamlit run classroom_app.py
```

### Step 5: Verify Supabase Connection

1. Log in to the app (admin/admin123)
2. Go to **Admin Dashboard** → **System Info** tab
3. You should see:
   - **Database:** Supabase (PostgreSQL) ✅
   - **Status:** ✅ Connected

## Expected Behavior

- ✅ App connects to Supabase instead of SQLite
- ✅ Data persists (users, newsletters, etc.)
- ✅ Admin dashboard shows Supabase status
- ✅ No more data loss warnings

## Troubleshooting

### "Supabase configuration error"
- Check that `.streamlit/secrets.toml` exists
- Verify URL and key are correct (no extra spaces)
- Make sure URL starts with `https://`

### "Table does not exist"
- Go to Supabase dashboard → SQL Editor
- Run the table creation SQL script again
- Verify tables exist in Database → Tables

### Still using SQLite?
- Check that secrets file is in `.streamlit/secrets.toml` (not `.streamlit/config.toml`)
- Verify credentials are correct
- Restart Streamlit app

### App won't start
- Check that Supabase package is installed: `pip install supabase`
- Check terminal for error messages
- Verify Python version (3.7+)

## Testing Checklist

- [ ] Can log in with admin/admin123
- [ ] Admin dashboard shows "Supabase (PostgreSQL)"
- [ ] Can create a new user account
- [ ] User account persists after app restart
- [ ] Can create a newsletter
- [ ] Newsletter persists after app restart

## Security Notes

- ✅ `.streamlit/secrets.toml` is in `.gitignore` (won't be committed)
- ✅ Never commit your Supabase credentials
- ✅ Use different Supabase projects for dev and production if needed

## Next Steps

Once local testing works:
1. Test all features (users, newsletters, events, assignments)
2. Verify data persists after restarting the app
3. Push code to GitHub (secrets won't be committed)
4. Add same secrets to Streamlit Cloud dashboard
5. Deploy to production

---

**Note:** The app will use Supabase if credentials are found, otherwise it falls back to SQLite for local development.

