# Email Configuration Guide for Mrs. Simms

## 📧 **Mrs. Simms' Email**: ksimms@washingtonchristian.org

### **Step 1: Determine Email Provider**

The email `washingtonchristian.org` could be:
- **Microsoft Outlook/Office 365** (most common for schools)
- **Google Workspace for Education**
- **Other email provider**

---

## 🔧 **Option 1: Microsoft Outlook/Office 365**

If Washington Christian Academy uses Microsoft Outlook:

**SMTP Settings:**
- **Sender Email**: `ksimms@washingtonchristian.org`
- **SMTP Server**: `smtp.office365.com` OR `smtp-mail.outlook.com`
- **SMTP Port**: `587`
- **Password**: Her school email password
- **Use TLS**: Yes (checked)

**In the Classroom App:**
1. Sender Email: `ksimms@washingtonchristian.org`
2. SMTP Server: `smtp.office365.com`
3. Email Password: Her school email password
4. SMTP Port: `587`

---

## 🔧 **Option 2: Google Workspace for Education**

If Washington Christian Academy uses Google Workspace:

**SMTP Settings:**
- **Sender Email**: `ksimms@washingtonchristian.org`
- **SMTP Server**: `smtp.gmail.com`
- **SMTP Port**: `587`
- **Password**: Her Google Workspace password OR App Password
- **Use TLS**: Yes (checked)

**Note**: Google Workspace might require App Password if 2FA is enabled.

**In the Classroom App:**
1. Sender Email: `ksimms@washingtonchristian.org`
2. SMTP Server: `smtp.gmail.com`
3. Email Password: Her Google Workspace password or App Password
4. SMTP Port: `587`

---

## 🔍 **How to Find Out Which Provider**

**Ask Mrs. Simms to check:**
1. What email client does she use? (Outlook app, Gmail web, etc.)
2. Where does she log in to check email?
   - If `outlook.com` or `office.com` → Microsoft
   - If `gmail.com` or `mail.google.com` → Google Workspace
3. What does her email signature say?

---

## ✅ **Testing Steps**

1. Try **Option 1** (Microsoft Outlook) first:
   - SMTP Server: `smtp.office365.com`
   - Port: `587`
   - Password: Her school email password

2. If that doesn't work, try **Option 2** (Google Workspace):
   - SMTP Server: `smtp.gmail.com`
   - Port: `587`
   - Password: Her Google Workspace password

3. Use the "🔧 Test Email Connection" button to verify settings

---

## 📞 **If Still Not Working**

Contact the school IT department and ask:
- "What email provider does Washington Christian Academy use?"
- "What are the SMTP settings for sending email?"
- "Do I need an app password for SMTP?"

They should be able to provide the exact SMTP configuration.
