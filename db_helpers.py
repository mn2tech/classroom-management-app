"""
Database helper functions for Supabase integration.
These functions abstract away the differences between SQLite and Supabase.
"""

def db_insert(table_name, data, conn=None):
    """Insert data into a table (works with both SQLite and Supabase)"""
    if isinstance(conn, SupabaseAdapter):
        # Supabase insert
        supabase_client = conn.client
        result = supabase_client.table(table_name).insert(data).execute()
        return result.data[0] if result.data else None
    else:
        # SQLite insert
        cursor = conn.cursor()
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?' for _ in data])
        query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
        cursor.execute(query, list(data.values()))
        conn.commit()
        return cursor.lastrowid

def db_select(table_name, filters=None, conn=None):
    """Select data from a table"""
    if isinstance(conn, SupabaseAdapter):
        # Supabase select
        supabase_client = conn.client
        query = supabase_client.table(table_name).select('*')
        
        if filters:
            for key, value in filters.items():
                query = query.eq(key, value)
        
        result = query.execute()
        return result.data if result.data else []
    else:
        # SQLite select
        cursor = conn.cursor()
        query = f"SELECT * FROM {table_name}"
        params = []
        if filters:
            conditions = []
            for key, value in filters.items():
                conditions.append(f"{key} = ?")
                params.append(value)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
        
        cursor.execute(query, params)
        return cursor.fetchall()

def db_update(table_name, data, filters, conn=None):
    """Update data in a table"""
    if isinstance(conn, SupabaseAdapter):
        # Supabase update
        supabase_client = conn.client
        query = supabase_client.table(table_name).update(data)
        
        if filters:
            for key, value in filters.items():
                query = query.eq(key, value)
        
        result = query.execute()
        return result.data
    else:
        # SQLite update
        cursor = conn.cursor()
        set_clause = ', '.join([f"{key} = ?" for key in data.keys()])
        where_clause = ' AND '.join([f"{key} = ?" for key in filters.keys()])
        query = f"UPDATE {table_name} SET {set_clause} WHERE {where_clause}"
        params = list(data.values()) + list(filters.values())
        cursor.execute(query, params)
        conn.commit()
        return cursor.rowcount

def db_delete(table_name, filters, conn=None):
    """Delete data from a table"""
    if isinstance(conn, SupabaseAdapter):
        # Supabase delete
        supabase_client = conn.client
        query = supabase_client.table(table_name).delete()
        
        if filters:
            for key, value in filters.items():
                query = query.eq(key, value)
        
        result = query.execute()
        return result.data
    else:
        # SQLite delete
        cursor = conn.cursor()
        where_clause = ' AND '.join([f"{key} = ?" for key in filters.keys()])
        query = f"DELETE FROM {table_name} WHERE {where_clause}"
        cursor.execute(query, list(filters.values()))
        conn.commit()
        return cursor.rowcount





