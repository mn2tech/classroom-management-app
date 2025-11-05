# Database Persistence Issue - Users Disappearing

## Problem
User accounts and teacher accounts are disappearing within a day, **even when code is not pushed**.

## Root Cause
The app is deployed on **Streamlit Cloud**, which uses an **EPHEMERAL file system**. This means:

- **The database file is LOST when:**
  - Code is pushed/redeployed ❌
  - App restarts from inactivity ❌
  - Container restarts (maintenance, resource limits) ❌
  - Any system restart ❌

**Even without code pushes, the app can restart due to:**
- Inactivity timeouts
- Resource limits
- System maintenance
- Container restarts

### What Happens:
1. You create users/teachers in the app ✅
2. Data is saved to `classroom.db` ✅
3. You push code changes to GitHub ❌
4. Streamlit Cloud redeploys the app ❌
5. **Database file is reset to empty** ❌
6. Only default users are recreated (admin, mrs.simms, sample parents) ❌

## Solutions

### Option 1: Use External Database (Recommended for Production)
Move to a cloud database service that persists independently of code deployments:

**Recommended Services:**
- **Supabase** (PostgreSQL) - Free tier available
- **PlanetScale** (MySQL) - Free tier available
- **Railway** (PostgreSQL) - Free tier available
- **AWS RDS** - Paid but reliable
- **Google Cloud SQL** - Paid but reliable

**Benefits:**
- ✅ Data persists across code deployments
- ✅ Better performance and scalability
- ✅ Automatic backups
- ✅ Multi-user support

### Option 2: Manual Backup Before Deployments
Before pushing code changes:
1. Export all user data from Admin dashboard
2. Push code changes
3. After redeploy, manually recreate users OR import data

**Limitations:**
- ⚠️ Manual process - easy to forget
- ⚠️ Not suitable for frequent updates
- ⚠️ Risk of data loss if backup is missed

### Option 3: Reduce Code Deployments
- Only push code when absolutely necessary
- Batch multiple changes together
- Use feature branches for testing

**Limitations:**
- ⚠️ Slows down development
- ⚠️ Doesn't solve the root problem

## Current Status
- **Database:** SQLite (local file)
- **Location:** `classroom.db` (in app directory)
- **Persistence:** Only between sessions, NOT across deployments
- **Risk Level:** ⚠️ HIGH - Data loss on every code push

## Immediate Actions
1. ✅ **Code Fix Applied:** Centralized database connection function
2. ⚠️ **Warning Added:** Admin dashboard now shows persistence warning
3. 📝 **Documentation:** This file explains the issue

## Next Steps (Recommended)
1. **Short-term:** Export user data before any code pushes
2. **Medium-term:** Set up external database (Supabase recommended)
3. **Long-term:** Migrate to external database for production use

## Migration Guide (When Ready)
When moving to an external database:
1. Update `get_db_connection()` to use external DB
2. Migrate existing data (if any)
3. Update `.gitignore` to continue excluding local DB
4. Test thoroughly before production deployment

---
**Note:** This is a common issue with Streamlit Cloud apps using SQLite. For production apps, an external database is strongly recommended.

