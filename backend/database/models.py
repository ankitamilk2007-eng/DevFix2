import json
from datetime import datetime
from .db import get_db_connection

class SessionModel:
    @staticmethod
    def get_all():
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM sessions ORDER BY created_at DESC')
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for row in rows:
            results.append(SessionModel._format_row(row))
        return results

    @staticmethod
    def get_by_id(session_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM sessions WHERE id = ?', (session_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return SessionModel._format_row(row)
        return None

    @staticmethod
    def upsert(session_data):
        session_id = session_data.get('id')
        if not session_id:
            session_id = f"session_{int(datetime.now().timestamp() * 1000)}"

        now = datetime.now().isoformat()
        created_at = session_data.get('createdAt') or session_data.get('created_at') or now
        updated_at = now

        title = session_data.get('title', 'Python Debug Session')
        language = session_data.get('language', 'python')
        code = session_data.get('code', '')
        traceback = session_data.get('traceback', '')
        context = session_data.get('context', '')
        workflow_status = session_data.get('workflowStatus') or session_data.get('workflow_status', 'diagnosis')
        verification_status = session_data.get('verificationStatus') or session_data.get('verification_status', 'in_progress')

        diagnosis_json = json.dumps(session_data.get('diagnosis')) if session_data.get('diagnosis') else None
        proposed_fix_json = json.dumps(session_data.get('proposedFix') or session_data.get('proposed_fix')) if (session_data.get('proposedFix') or session_data.get('proposed_fix')) else None
        verification_json = json.dumps(session_data.get('verification')) if session_data.get('verification') else None

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO sessions (
                id, title, language, code, traceback, context,
                workflow_status, verification_status,
                diagnosis_json, proposed_fix_json, verification_json,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                language = excluded.language,
                code = excluded.code,
                traceback = excluded.traceback,
                context = excluded.context,
                workflow_status = excluded.workflow_status,
                verification_status = excluded.verification_status,
                diagnosis_json = excluded.diagnosis_json,
                proposed_fix_json = excluded.proposed_fix_json,
                verification_json = excluded.verification_json,
                updated_at = excluded.updated_at
        ''', (
            session_id, title, language, code, traceback, context,
            workflow_status, verification_status,
            diagnosis_json, proposed_fix_json, verification_json,
            created_at, updated_at
        ))
        conn.commit()
        conn.close()

        return SessionModel.get_by_id(session_id)

    @staticmethod
    def delete(session_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM sessions WHERE id = ?', (session_id,))
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted_count > 0

    @staticmethod
    def _format_row(row):
        return {
            'id': row['id'],
            'title': row['title'],
            'language': row['language'],
            'code': row['code'],
            'traceback': row['traceback'],
            'context': row['context'],
            'workflowStatus': row['workflow_status'],
            'verificationStatus': row['verification_status'],
            'diagnosis': json.loads(row['diagnosis_json']) if row['diagnosis_json'] else None,
            'proposedFix': json.loads(row['proposed_fix_json']) if row['proposed_fix_json'] else None,
            'verification': json.loads(row['verification_json']) if row['verification_json'] else None,
            'createdAt': row['created_at'],
            'updatedAt': row['updated_at']
        }
