"""
HR Management System — Enhanced Backend
Indian Payroll (PF/ESI/TDS/80C/HRA), Form-16, Employee Docs, Validation
"""
import sqlite3, os, hashlib, secrets, math
from flask import Flask, request, jsonify, send_file, send_from_directory
from datetime import datetime
from io import BytesIO

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = secrets.token_hex(32)

DB_PATH    = os.path.join(os.path.dirname(__file__), 'hr_data.db')
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
EMP_DOCS   = os.path.join(os.path.dirname(__file__), 'static', 'emp_docs')
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(EMP_DOCS,   exist_ok=True)

ALLOWED_IMG  = {'jpg','jpeg','png','gif','webp'}
ALLOWED_DOCS = {'pdf','jpg','jpeg','png','doc','docx'}
MAX_IMG_MB   = 2
MAX_DOC_MB   = 5

# ─── DB ───────────────────────────────────────────────────────────────────────
import psycopg2
import psycopg2.extras
from supabase import create_client, Client
import urllib.request

DATABASE_URL = os.environ.get("DATABASE_URL")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

class PSCursor:
    def __init__(self, cur):
        self.cur = cur
        self.lastrowid = None

    def execute(self, query, args=None):
        q = query.replace('?', '%s')
        if 'INSERT OR IGNORE' in q:
            q = q.replace('INSERT OR IGNORE', 'INSERT')
            q += ' ON CONFLICT DO NOTHING'
            
        is_insert = q.strip().upper().startswith('INSERT')
        if is_insert and 'ON CONFLICT DO NOTHING' not in q and 'RETURNING id' not in q:
            q += ' RETURNING id'
            
        if args:
            self.cur.execute(q, args)
        else:
            self.cur.execute(q)
            
        if is_insert and 'ON CONFLICT DO NOTHING' not in q:
            try:
                res = self.cur.fetchone()
                if res:
                    self.lastrowid = res['id'] if isinstance(res, dict) or hasattr(res, 'keys') else res[0]
            except:
                pass
        return self

    def fetchone(self):
        try:
            return self.cur.fetchone()
        except:
            return None

    def fetchall(self):
        try:
            return self.cur.fetchall()
        except:
            return []

class PSConnection:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.conn.commit()
        else:
            self.conn.rollback()
        self.conn.close()

    def execute(self, query, args=None):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        pc = PSCursor(cur)
        return pc.execute(query, args)

    def executescript(self, query):
        cur = self.conn.cursor()
        cur.execute(query)
        self.conn.commit()

def get_db():
    if not DATABASE_URL:
        class DummyDB:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def execute(self, *args): return PSCursor(None)
        return DummyDB()
    conn = psycopg2.connect(DATABASE_URL)
    return PSConnection(conn)

def init_db():
    if not DATABASE_URL:
        return
    with get_db() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS company (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL DEFAULT 'My Company',
            address TEXT DEFAULT '', city TEXT DEFAULT '',
            state TEXT DEFAULT '', pincode TEXT DEFAULT '',
            phone TEXT DEFAULT '', email TEXT DEFAULT '',
            website TEXT DEFAULT '', gstin TEXT DEFAULT '',
            pan TEXT DEFAULT '',
            logo_path TEXT DEFAULT '', stamp_path TEXT DEFAULT '',
            hr_signature_path TEXT DEFAULT '',
            hr_name TEXT DEFAULT 'HR Manager',
            hr_designation TEXT DEFAULT 'Human Resources Manager',
            cin TEXT DEFAULT '', tan TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'employee',
            employee_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS employees (
            id SERIAL PRIMARY KEY,
            emp_code TEXT UNIQUE NOT NULL,
            first_name TEXT NOT NULL, last_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL, phone TEXT DEFAULT '',
            date_of_birth TEXT DEFAULT '', date_of_joining TEXT NOT NULL,
            department TEXT DEFAULT '', designation TEXT DEFAULT '',
            employment_type TEXT DEFAULT 'Full-Time',
            status TEXT DEFAULT 'Active',
            basic_salary REAL DEFAULT 0, hra REAL DEFAULT 0,
            transport_allowance REAL DEFAULT 0,
            medical_allowance REAL DEFAULT 0,
            special_allowance REAL DEFAULT 0,
            lta REAL DEFAULT 0, other_allowance REAL DEFAULT 0,
            pf_employee REAL DEFAULT 0, pf_employer REAL DEFAULT 0,
            esi_employee REAL DEFAULT 0, esi_employer REAL DEFAULT 0,
            professional_tax REAL DEFAULT 0, tds REAL DEFAULT 0,
            other_deduction REAL DEFAULT 0,
            gratuity_applicable INTEGER DEFAULT 1,
            pan_number TEXT DEFAULT '', aadhar_number TEXT DEFAULT '',
            uan_number TEXT DEFAULT '',
            bank_name TEXT DEFAULT '', bank_account TEXT DEFAULT '',
            bank_ifsc TEXT DEFAULT '',
            address TEXT DEFAULT '', city TEXT DEFAULT '',
            state TEXT DEFAULT '', pincode TEXT DEFAULT '',
            manager_name TEXT DEFAULT '',
            photo_path TEXT DEFAULT '',
            gender TEXT DEFAULT '', marital_status TEXT DEFAULT '',
            nationality TEXT DEFAULT 'Indian',
            emergency_contact TEXT DEFAULT '', emergency_phone TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS payslips (
            id SERIAL PRIMARY KEY,
            employee_id INTEGER NOT NULL, month INTEGER NOT NULL, year INTEGER NOT NULL,
            basic_salary REAL DEFAULT 0, hra REAL DEFAULT 0,
            transport_allowance REAL DEFAULT 0, medical_allowance REAL DEFAULT 0,
            special_allowance REAL DEFAULT 0, lta REAL DEFAULT 0,
            other_earnings REAL DEFAULT 0,
            pf_employee REAL DEFAULT 0, pf_employer REAL DEFAULT 0,
            esi_employee REAL DEFAULT 0, esi_employer REAL DEFAULT 0,
            professional_tax REAL DEFAULT 0, tds REAL DEFAULT 0,
            other_deduction REAL DEFAULT 0, advance_deduction REAL DEFAULT 0,
            gross_salary REAL DEFAULT 0, total_deductions REAL DEFAULT 0,
            net_salary REAL DEFAULT 0,
            working_days INTEGER DEFAULT 26, paid_days INTEGER DEFAULT 26,
            lop_days INTEGER DEFAULT 0, lop_deduction REAL DEFAULT 0,
            ytd_gross REAL DEFAULT 0, ytd_tds REAL DEFAULT 0,
            notes TEXT DEFAULT '',
            generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(employee_id) REFERENCES employees(id)
        );
        CREATE TABLE IF NOT EXISTS employee_documents (
            id SERIAL PRIMARY KEY,
            employee_id INTEGER NOT NULL,
            doc_name TEXT NOT NULL,
            doc_category TEXT DEFAULT 'other',
            file_path TEXT NOT NULL,
            file_size INTEGER DEFAULT 0,
            file_type TEXT DEFAULT '',
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            uploaded_by TEXT DEFAULT '',
            FOREIGN KEY(employee_id) REFERENCES employees(id)
        );
        CREATE TABLE IF NOT EXISTS generated_documents (
            id SERIAL PRIMARY KEY,
            employee_id INTEGER NOT NULL,
            doc_type TEXT NOT NULL,
            generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            generated_by TEXT DEFAULT '',
            FOREIGN KEY(employee_id) REFERENCES employees(id)
        );
        INSERT INTO company (id,name) VALUES (1,'My Company') ON CONFLICT DO NOTHING;
        ''')
        ph = hashlib.sha256(b"admin123").hexdigest()
        db.execute("INSERT INTO users(username,password_hash,role) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING",
                   ("admin", ph, "admin"))
        
        def _add_col(table, col, typedef):
            ex_query = "SELECT column_name FROM information_schema.columns WHERE table_name=%s"
            ex = [r[0] for r in db.execute(ex_query, (table,)).fetchall()]
            if col not in ex:
                try:
                    db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typedef}")
                except:
                    pass
        
        emp_migrations = [
            ("lta","REAL DEFAULT 0"),("other_allowance","REAL DEFAULT 0"),
            ("pf_employer","REAL DEFAULT 0"),("esi_employer","REAL DEFAULT 0"),
            ("professional_tax","REAL DEFAULT 0"),("uan_number","TEXT DEFAULT ''"),
            ("gender","TEXT DEFAULT ''"),("marital_status","TEXT DEFAULT ''"),
            ("nationality","TEXT DEFAULT 'Indian'"),("emergency_contact","TEXT DEFAULT ''"),
            ("emergency_phone","TEXT DEFAULT ''"),("gratuity_applicable","INTEGER DEFAULT 1"),
        ]
        for col,td in emp_migrations:
            _add_col("employees", col, td)
        pay_migrations = [
            ("lta","REAL DEFAULT 0"),("pf_employer","REAL DEFAULT 0"),
            ("esi_employer","REAL DEFAULT 0"),("professional_tax","REAL DEFAULT 0"),
            ("total_deductions","REAL DEFAULT 0"),("advance_deduction","REAL DEFAULT 0"),
            ("lop_deduction","REAL DEFAULT 0"),("ytd_gross","REAL DEFAULT 0"),
            ("ytd_tds","REAL DEFAULT 0"),("hra_exemption","REAL DEFAULT 0"),
        ]
        for col,td in pay_migrations:
            _add_col("payslips", col, td)
        for col,td in [("cin","TEXT DEFAULT ''"),("tan","TEXT DEFAULT ''")]:
            _add_col("company", col, td)

init_db()

# ─── HELPERS ──────────────────────────────────────────────────────────────────
def hash_pw(p): return hashlib.sha256(p.encode()).hexdigest()

def verify_token(req):
    tok = req.headers.get('Authorization','').replace('Bearer ','')
    if not tok: return None
    with get_db() as db:
        r = db.execute("SELECT * FROM users WHERE username=?", (tok,)).fetchone()
        return dict(r) if r else None

def require_admin(req):
    u = verify_token(req)
    return u if u and u['role'] in ('admin','hr') else None

def img_to_bytes(path):
    if not path: return None
    if path.startswith('http'):
        try:
            req = urllib.request.Request(path, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                return response.read()
        except Exception as e:
            print("Failed to download image from supabase:", e)
            return None
    full = os.path.join(os.path.dirname(__file__), 'static', path)
    return open(full,'rb').read() if os.path.exists(full) else None

def get_co(): 
    with get_db() as db:
        return dict(db.execute("SELECT * FROM company WHERE id=1").fetchone())

def get_emp(eid):
    with get_db() as db:
        r = db.execute("SELECT * FROM employees WHERE id=?", (eid,)).fetchone()
        return dict(r) if r else None

def fmt_inr(n): return f"₹{float(n or 0):,.2f}"

# ─── INDIAN PAYROLL ENGINE ────────────────────────────────────────────────────
def calc_indian_payroll(basic, hra_actual, ta, ma, sa, lta, other_earn,
                        pf_emp_override, esi_emp_override, pt_override,
                        tds_override, other_ded, advance_ded,
                        working_days, paid_days, is_metro=True, ytd_gross_prev=0,
                        financial_year=None):
    """
    Full Indian payroll computation:
    PF  : 12% of basic (employee) | 12% employer (8.33% EPS + 3.67% EPF)
    ESI : 0.75% employee | 3.25% employer (applicable if gross <= 21000)
    PT  : per slab (Maharashtra used as default)
    TDS : computed on annualised income with standard deductions
    HRA : exemption via rent receipt / metro rule
    """
    if financial_year is None:
        now = datetime.now()
        financial_year = now.year if now.month >= 4 else now.year - 1

    # LOP ratio
    lop_days  = max(0, working_days - paid_days)
    lop_ratio = paid_days / working_days if working_days else 1
    
    # Scale all earnings by LOP
    basic_paid = round(basic * lop_ratio, 2)
    hra_paid   = round(hra_actual * lop_ratio, 2)
    ta_paid    = round(ta * lop_ratio, 2)
    ma_paid    = round(ma * lop_ratio, 2)
    sa_paid    = round(sa * lop_ratio, 2)
    lta_paid   = round(lta * lop_ratio, 2)
    oe_paid    = round(other_earn * lop_ratio, 2)

    gross = basic_paid + hra_paid + ta_paid + ma_paid + sa_paid + lta_paid + oe_paid
    
    # ── PF (EPF) ─────────────────────────────────────────────────────────────
    pf_wage = min(basic_paid, 15000)  # capped at 15000 for statutory
    pf_employee = round(pf_emp_override if pf_emp_override > 0 else pf_wage * 0.12, 2)
    pf_employer  = round(pf_wage * 0.12, 2)   # full employer share
    
    # ── ESI ──────────────────────────────────────────────────────────────────
    esi_employee = esi_employer = 0.0
    if gross <= 21000:
        esi_employee = round(esi_emp_override if esi_emp_override > 0 else gross * 0.0075, 2)
        esi_employer = round(gross * 0.0325, 2)
    
    # ── Professional Tax (Maharashtra slab) ──────────────────────────────────
    if pt_override > 0:
        pt = pt_override
    else:
        if gross < 7500:   pt = 0
        elif gross < 10000: pt = 175
        else:               pt = 200
    
    # ── HRA Exemption (Section 10(13A)) ──────────────────────────────────────
    # 50% of basic for metro, 40% for non-metro
    hra_exemption = min(
        hra_paid,
        (0.50 if is_metro else 0.40) * basic_paid,
    )
    
    # ── TDS (New Tax Regime FY 2024-25) ──────────────────────────────────────
    # Standard deduction 75000 from Apr 2024
    if tds_override > 0:
        tds = tds_override
    else:
        annual_gross = (gross - hra_exemption) * 12
        annual_gross += ytd_gross_prev * 12 / 12  # rough YTD carry
        std_deduction = 75000
        taxable = max(0, annual_gross - std_deduction)
        # New regime slabs FY 2024-25
        tax = 0
        slabs = [(300000,0),(400000,0.05),(300000,0.10),(300000,0.15),
                 (300000,0.20),(float('inf'),0.30)]
        rem = taxable
        prev_limit = 0
        for limit, rate in slabs:
            if rem <= 0: break
            chunk = min(rem, limit)
            if prev_limit == 0: chunk = min(rem, 300000)
            tax += chunk * rate
            rem -= chunk
            prev_limit += limit
        # Rebate u/s 87A (if taxable <= 7L, rebate = full tax, new regime)
        if taxable <= 700000: tax = 0
        # 4% cess
        tax = tax * 1.04
        tds = round(tax / 12, 2)

    total_deductions = pf_employee + esi_employee + pt + tds + other_ded + advance_ded
    lop_deduction = gross * (lop_days / working_days) if working_days and lop_days else 0
    net = gross - total_deductions

    return {
        'basic_salary':      basic_paid,
        'hra':               hra_paid,
        'transport_allowance': ta_paid,
        'medical_allowance': ma_paid,
        'special_allowance': sa_paid,
        'lta':               lta_paid,
        'other_earnings':    oe_paid,
        'gross_salary':      round(gross, 2),
        'pf_employee':       pf_employee,
        'pf_employer':       pf_employer,
        'esi_employee':      esi_employee,
        'esi_employer':      esi_employer,
        'professional_tax':  pt,
        'tds':               tds,
        'other_deduction':   other_ded,
        'advance_deduction': advance_ded,
        'total_deductions':  round(total_deductions, 2),
        'net_salary':        round(net, 2),
        'lop_days':          lop_days,
        'lop_deduction':     round(lop_deduction, 2),
        'hra_exemption':     round(hra_exemption, 2),
    }

# ─── AUTH ─────────────────────────────────────────────────────────────────────
@app.route('/api/login', methods=['POST'])
def login():
    d = request.json
    with get_db() as db:
        u = db.execute("SELECT * FROM users WHERE username=? AND password_hash=?",
                       (d['username'], hash_pw(d['password']))).fetchone()
        if not u: return jsonify({'error':'Invalid credentials'}), 401
        u = dict(u)
        emp = None
        if u['employee_id']:
            r = db.execute("SELECT * FROM employees WHERE id=?", (u['employee_id'],)).fetchone()
            emp = dict(r) if r else None
        return jsonify({'token':u['username'],'role':u['role'],'user':u,'employee':emp})

@app.route('/api/users', methods=['GET'])
def get_users():
    if not require_admin(request): return jsonify({'error':'Unauthorized'}), 403
    with get_db() as db:
        rows = db.execute("SELECT id,username,role,employee_id,created_at FROM users").fetchall()
        return jsonify([dict(r) for r in rows])

@app.route('/api/users', methods=['POST'])
def create_user():
    if not require_admin(request): return jsonify({'error':'Unauthorized'}), 403
    d = request.json
    with get_db() as db:
        try:
            db.execute("INSERT INTO users(username,password_hash,role,employee_id) VALUES(?,?,?,?)",
                       (d['username'], hash_pw(d['password']), d['role'], d.get('employee_id')))
            return jsonify({'success':True})
        except Exception as e:
            return jsonify({'error':str(e)}), 400

@app.route('/api/users/<int:uid>', methods=['PUT'])
def update_user(uid):
    if not require_admin(request): return jsonify({'error':'Unauthorized'}), 403
    d = request.json
    with get_db() as db:
        if d.get('password'):
            db.execute("UPDATE users SET role=?,employee_id=?,password_hash=? WHERE id=?",
                       (d['role'],d.get('employee_id'),hash_pw(d['password']),uid))
        else:
            db.execute("UPDATE users SET role=?,employee_id=? WHERE id=?",
                       (d['role'],d.get('employee_id'),uid))
        return jsonify({'success':True})

@app.route('/api/users/<int:uid>', methods=['DELETE'])
def delete_user(uid):
    if not require_admin(request): return jsonify({'error':'Unauthorized'}), 403
    with get_db() as db:
        db.execute("DELETE FROM users WHERE id=?", (uid,))
        return jsonify({'success':True})

# ─── COMPANY ──────────────────────────────────────────────────────────────────
@app.route('/api/company', methods=['GET'])
def get_company():
    return jsonify(get_co())

@app.route('/api/company', methods=['PUT'])
def update_company():
    if not require_admin(request): return jsonify({'error':'Unauthorized'}), 403
    d = request.json
    fields = ['name','address','city','state','pincode','phone','email','website',
              'gstin','pan','cin','tan','hr_name','hr_designation']
    sets = ', '.join(f"{f}=?" for f in fields if f in d)
    vals = [d[f] for f in fields if f in d]
    with get_db() as db:
        db.execute(f"UPDATE company SET {sets} WHERE id=1", vals)
        return jsonify({'success':True})

@app.route('/api/company/upload/<img_type>', methods=['POST'])
def upload_company_image(img_type):
    if not require_admin(request): return jsonify({'error':'Unauthorized'}), 403
    if img_type not in ('logo','stamp','hr_signature'):
        return jsonify({'error':'Invalid type'}), 400
    f = request.files.get('file')
    if not f: return jsonify({'error':'No file'}), 400
    ext = f.filename.rsplit('.',1)[-1].lower()
    if ext not in ALLOWED_IMG:
        return jsonify({'error':f'Only {", ".join(ALLOWED_IMG)} allowed'}), 400
    f.seek(0, 2); size = f.tell(); f.seek(0)
    if size > MAX_IMG_MB * 1024 * 1024:
        return jsonify({'error':f'Max {MAX_IMG_MB}MB allowed'}), 400
    fname = f"company_{img_type}.{ext}"
    url_path = f"uploads/{fname}"
    if supabase:
        supabase.storage.from_("hr-assets").upload(file=f.read(), path=fname, file_options={"content-type": f.content_type})
        url_path = supabase.storage.from_("hr-assets").get_public_url(fname)
    else:
        f.seek(0)
        f.save(os.path.join(UPLOAD_DIR, fname))
    col = f"{img_type}_path"
    with get_db() as db:
        db.execute(f"UPDATE company SET {col}=? WHERE id=1", (url_path,))
    return jsonify({'success':True, 'path':url_path, 'size':size})

# ─── EMPLOYEES ────────────────────────────────────────────────────────────────
@app.route('/api/employees', methods=['GET'])
def get_employees():
    u = verify_token(request)
    if not u: return jsonify({'error':'Unauthorized'}), 403
    with get_db() as db:
        if u['role'] in ('admin','hr'):
            rows = db.execute("SELECT * FROM employees ORDER BY first_name").fetchall()
        else:
            rows = db.execute("SELECT * FROM employees WHERE id=?", (u['employee_id'],)).fetchall()
        return jsonify([dict(r) for r in rows])

@app.route('/api/employees/<int:eid>', methods=['GET'])
def get_employee_route(eid):
    u = verify_token(request)
    if not u: return jsonify({'error':'Unauthorized'}), 403
    if u['role'] not in ('admin','hr') and u['employee_id'] != eid:
        return jsonify({'error':'Unauthorized'}), 403
    e = get_emp(eid)
    return jsonify(e) if e else (jsonify({'error':'Not found'}), 404)

@app.route('/api/employees', methods=['POST'])
def create_employee():
    if not require_admin(request): return jsonify({'error':'Unauthorized'}), 403
    d = request.json
    cols = ['emp_code','first_name','last_name','email','phone','date_of_birth',
            'date_of_joining','department','designation','employment_type','status',
            'basic_salary','hra','transport_allowance','medical_allowance','special_allowance',
            'lta','other_allowance','pf_employee','pf_employer','esi_employee','esi_employer',
            'professional_tax','tds','other_deduction','gratuity_applicable',
            'pan_number','aadhar_number','uan_number',
            'bank_name','bank_account','bank_ifsc',
            'address','city','state','pincode','manager_name',
            'gender','marital_status','nationality','emergency_contact','emergency_phone']
    vals = [d.get(c,'') for c in cols]
    with get_db() as db:
        try:
            cur = db.execute(
                f"INSERT INTO employees ({','.join(cols)}) VALUES ({','.join(['?']*len(cols))})", vals)
            return jsonify({'success':True, 'id':cur.lastrowid})
        except Exception as e:
            return jsonify({'error':str(e)}), 400

@app.route('/api/employees/<int:eid>', methods=['PUT'])
def update_employee(eid):
    if not require_admin(request): return jsonify({'error':'Unauthorized'}), 403
    d = request.json
    cols = ['first_name','last_name','email','phone','date_of_birth','date_of_joining',
            'department','designation','employment_type','status',
            'basic_salary','hra','transport_allowance','medical_allowance','special_allowance',
            'lta','other_allowance','pf_employee','pf_employer','esi_employee','esi_employer',
            'professional_tax','tds','other_deduction','gratuity_applicable',
            'pan_number','aadhar_number','uan_number',
            'bank_name','bank_account','bank_ifsc',
            'address','city','state','pincode','manager_name',
            'gender','marital_status','nationality','emergency_contact','emergency_phone']
    sets = ', '.join(f"{c}=?" for c in cols if c in d)
    vals = [d[c] for c in cols if c in d] + [eid]
    with get_db() as db:
        db.execute(f"UPDATE employees SET {sets}, updated_at=CURRENT_TIMESTAMP WHERE id=?", vals)
        return jsonify({'success':True})

@app.route('/api/employees/<int:eid>', methods=['DELETE'])
def delete_employee(eid):
    if not require_admin(request): return jsonify({'error':'Unauthorized'}), 403
    with get_db() as db:
        db.execute("DELETE FROM employees WHERE id=?", (eid,))
        return jsonify({'success':True})

# ─── EMPLOYEE PHOTO UPLOAD ────────────────────────────────────────────────────
@app.route('/api/employees/<int:eid>/photo', methods=['POST'])
def upload_emp_photo(eid):
    u = verify_token(request)
    if not u: return jsonify({'error':'Unauthorized'}), 403
    if u['role'] not in ('admin','hr') and u['employee_id'] != eid:
        return jsonify({'error':'Unauthorized'}), 403
    f = request.files.get('file')
    if not f: return jsonify({'error':'No file'}), 400
    ext = f.filename.rsplit('.',1)[-1].lower()
    if ext not in ALLOWED_IMG:
        return jsonify({'error':f'Only images allowed: {", ".join(ALLOWED_IMG)}'}), 400
    f.seek(0,2); size = f.tell(); f.seek(0)
    if size > MAX_IMG_MB * 1024 * 1024:
        return jsonify({'error':f'Max {MAX_IMG_MB}MB for photos'}), 400
    fname = f"emp_{eid}_photo.{ext}"
    url_path = f"uploads/{fname}"
    if supabase:
        supabase.storage.from_("hr-assets").upload(file=f.read(), path=fname, file_options={"content-type": f.content_type})
        url_path = supabase.storage.from_("hr-assets").get_public_url(fname)
    else:
        f.seek(0)
        f.save(os.path.join(UPLOAD_DIR, fname))
    with get_db() as db:
        db.execute("UPDATE employees SET photo_path=? WHERE id=?", (url_path, eid))
    return jsonify({'success':True, 'path':url_path, 'size':size})

# ─── EMPLOYEE DOCUMENTS ───────────────────────────────────────────────────────
@app.route('/api/employees/<int:eid>/documents', methods=['GET'])
def get_emp_docs(eid):
    u = verify_token(request)
    if not u: return jsonify({'error':'Unauthorized'}), 403
    if u['role'] not in ('admin','hr') and u['employee_id'] != eid:
        return jsonify({'error':'Unauthorized'}), 403
    with get_db() as db:
        rows = db.execute("SELECT * FROM employee_documents WHERE employee_id=? ORDER BY uploaded_at DESC", (eid,)).fetchall()
        return jsonify([dict(r) for r in rows])

@app.route('/api/employees/<int:eid>/documents', methods=['POST'])
def upload_emp_doc(eid):
    u = verify_token(request)
    if not u: return jsonify({'error':'Unauthorized'}), 403
    if u['role'] not in ('admin','hr') and u['employee_id'] != eid:
        return jsonify({'error':'Unauthorized'}), 403
    f    = request.files.get('file')
    name = request.form.get('doc_name','Document')
    cat  = request.form.get('doc_category','other')
    if not f: return jsonify({'error':'No file'}), 400
    ext = f.filename.rsplit('.',1)[-1].lower()
    if ext not in ALLOWED_DOCS:
        return jsonify({'error':f'Allowed: {", ".join(ALLOWED_DOCS)}'}), 400
    f.seek(0,2); size = f.tell(); f.seek(0)
    if size > MAX_DOC_MB * 1024 * 1024:
        return jsonify({'error':f'Max {MAX_DOC_MB}MB for documents'}), 400
    ts    = datetime.now().strftime('%Y%m%d%H%M%S')
    fname = f"emp_{eid}_{ts}_{f.filename}"
    url_path = f"emp_docs/{fname}"
    if supabase:
        supabase.storage.from_("hr-assets").upload(file=f.read(), path=fname, file_options={"content-type": f.content_type})
        url_path = supabase.storage.from_("hr-assets").get_public_url(fname)
    else:
        f.seek(0)
        f.save(os.path.join(EMP_DOCS, fname))
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO employee_documents(employee_id,doc_name,doc_category,file_path,file_size,file_type,uploaded_by) VALUES(?,?,?,?,?,?,?)",
            (eid, name, cat, url_path, size, ext, u['username']))
        return jsonify({'success':True, 'id':cur.lastrowid, 'size':size})

@app.route('/api/employees/<int:eid>/documents/<int:did>', methods=['DELETE'])
def delete_emp_doc(eid, did):
    if not require_admin(request): return jsonify({'error':'Unauthorized'}), 403
    with get_db() as db:
        row = db.execute("SELECT * FROM employee_documents WHERE id=? AND employee_id=?", (did, eid)).fetchone()
        if row:
            fp = os.path.join(os.path.dirname(__file__), 'static', row['file_path'])
            if os.path.exists(fp): os.remove(fp)
        db.execute("DELETE FROM employee_documents WHERE id=? AND employee_id=?", (did, eid))
        return jsonify({'success':True})

@app.route('/static/emp_docs/<path:filename>')
def serve_emp_doc(filename):
    return send_from_directory(EMP_DOCS, filename)

# ─── PAYSLIPS ─────────────────────────────────────────────────────────────────
@app.route('/api/payroll/compute', methods=['POST'])
def compute_payroll():
    """Preview payroll without saving"""
    u = verify_token(request)
    if not u: return jsonify({'error':'Unauthorized'}), 403
    d = request.json
    result = calc_indian_payroll(
        basic=float(d.get('basic_salary',0)),
        hra_actual=float(d.get('hra',0)),
        ta=float(d.get('transport_allowance',0)),
        ma=float(d.get('medical_allowance',0)),
        sa=float(d.get('special_allowance',0)),
        lta=float(d.get('lta',0)),
        other_earn=float(d.get('other_earnings',0)),
        pf_emp_override=float(d.get('pf_employee',0)),
        esi_emp_override=float(d.get('esi_employee',0)),
        pt_override=float(d.get('professional_tax',0)),
        tds_override=float(d.get('tds',0)),
        other_ded=float(d.get('other_deduction',0)),
        advance_ded=float(d.get('advance_deduction',0)),
        working_days=int(d.get('working_days',26)),
        paid_days=int(d.get('paid_days',26)),
        is_metro=bool(d.get('is_metro',True)),
        ytd_gross_prev=float(d.get('ytd_gross_prev',0)),
    )
    return jsonify(result)

@app.route('/api/payslips', methods=['GET'])
def get_payslips():
    u = verify_token(request)
    if not u: return jsonify({'error':'Unauthorized'}), 403
    eid = request.args.get('employee_id')
    yr  = request.args.get('year')
    with get_db() as db:
        base = "SELECT p.*,e.first_name,e.last_name,e.emp_code,e.department,e.designation FROM payslips p JOIN employees e ON p.employee_id=e.id"
        cond, args = [], []
        if u['role'] not in ('admin','hr'):
            cond.append("p.employee_id=?"); args.append(u['employee_id'])
        else:
            if eid: cond.append("p.employee_id=?"); args.append(eid)
        if yr:  cond.append("p.year=?"); args.append(yr)
        q = base + (" WHERE " + " AND ".join(cond) if cond else "") + " ORDER BY p.year DESC, p.month DESC"
        return jsonify([dict(r) for r in db.execute(q, args).fetchall()])

@app.route('/api/payslips', methods=['POST'])
def create_payslip():
    if not require_admin(request): return jsonify({'error':'Unauthorized'}), 403
    d = request.json
    emp = get_emp(int(d['employee_id']))
    if not emp: return jsonify({'error':'Employee not found'}), 404

    # Compute using Indian payroll engine
    p = calc_indian_payroll(
        basic=float(d.get('basic_salary', emp['basic_salary'])),
        hra_actual=float(d.get('hra', emp['hra'])),
        ta=float(d.get('transport_allowance', emp['transport_allowance'])),
        ma=float(d.get('medical_allowance', emp['medical_allowance'])),
        sa=float(d.get('special_allowance', emp['special_allowance'])),
        lta=float(d.get('lta', emp['lta'])),
        other_earn=float(d.get('other_earnings',0)),
        pf_emp_override=float(d.get('pf_employee',0)),
        esi_emp_override=float(d.get('esi_employee',0)),
        pt_override=float(d.get('professional_tax',0)),
        tds_override=float(d.get('tds',0)),
        other_ded=float(d.get('other_deduction',0)),
        advance_ded=float(d.get('advance_deduction',0)),
        working_days=int(d.get('working_days',26)),
        paid_days=int(d.get('paid_days',26)),
        is_metro=bool(d.get('is_metro',True)),
    )
    # YTD calc
    with get_db() as db:
        ytd = db.execute(
            "SELECT SUM(gross_salary) as s FROM payslips WHERE employee_id=? AND year=?",
            (emp['id'], d['year'])).fetchone()['s'] or 0
        ytd_tds = db.execute(
            "SELECT SUM(tds) as s FROM payslips WHERE employee_id=? AND year=?",
            (emp['id'], d['year'])).fetchone()['s'] or 0

    with get_db() as db:
        cur = db.execute("""INSERT INTO payslips
            (employee_id,month,year,basic_salary,hra,transport_allowance,medical_allowance,
             special_allowance,lta,other_earnings,pf_employee,pf_employer,esi_employee,
             esi_employer,professional_tax,tds,other_deduction,advance_deduction,
             gross_salary,total_deductions,net_salary,working_days,paid_days,lop_days,
             lop_deduction,ytd_gross,ytd_tds,notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (d['employee_id'],d['month'],d['year'],
             p['basic_salary'],p['hra'],p['transport_allowance'],p['medical_allowance'],
             p['special_allowance'],p['lta'],p['other_earnings'],
             p['pf_employee'],p['pf_employer'],p['esi_employee'],p['esi_employer'],
             p['professional_tax'],p['tds'],p['other_deduction'],p['advance_deduction'],
             p['gross_salary'],p['total_deductions'],p['net_salary'],
             d.get('working_days',26),p.get('paid_days',d.get('paid_days',26)),
             p['lop_days'],p['lop_deduction'],
             ytd + p['gross_salary'], ytd_tds + p['tds'],
             d.get('notes','')))
        return jsonify({'success':True, 'id':cur.lastrowid, 'payslip':p})

# ─── PDF GENERATION ENGINE ────────────────────────────────────────────────────
def make_header(story, co, ps_func):
    from reportlab.platypus import Table, TableStyle, Image, Paragraph, HRFlowable
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    BLUE  = colors.HexColor('#1a237e')
    logo_b = img_to_bytes(co.get('logo_path',''))
    title_s = ps_func('HdrT', fontSize=16, fontName='Helvetica-Bold',
                      textColor=BLUE, spaceAfter=3, alignment=TA_CENTER)
    sub_s   = ps_func('HdrS', fontSize=9, fontName='Helvetica',
                      textColor=colors.HexColor('#374151'), spaceAfter=2, alignment=TA_CENTER)
    if logo_b:
        row = [[Image(BytesIO(logo_b), width=1.0*inch, height=1.0*inch),
                [Paragraph(co['name'], title_s),
                 Paragraph(co.get('address',''), sub_s),
                 Paragraph(f"{co.get('city','')} {co.get('state','')} {co.get('pincode','')}", sub_s),
                 Paragraph(f"Ph: {co.get('phone','')}  ·  {co.get('email','')}", sub_s),
                 Paragraph(f"GSTIN: {co.get('gstin','')}  ·  PAN: {co.get('pan','')}", sub_s)]]]
        t = Table(row, colWidths=[1.2*inch, 6.0*inch])
        t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),0)]))
        story.append(t)
    else:
        story.append(Paragraph(co['name'], title_s))
        story.append(Paragraph(f"{co.get('address','')} | {co.get('city','')} {co.get('state','')} {co.get('pincode','')}", sub_s))
        story.append(Paragraph(f"Ph: {co.get('phone','')}  ·  {co.get('email','')}", sub_s))
    story.append(HRFlowable(width="100%", thickness=2, color=BLUE, spaceAfter=10))

def make_title_bar(story, title, ps_func):
    from reportlab.platypus import Table, TableStyle, Paragraph
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    BLUE = colors.HexColor('#1a237e')
    head_s = ps_func('TBar', fontSize=13, fontName='Helvetica-Bold',
                     textColor=colors.white, alignment=1, spaceAfter=6, spaceBefore=6)
    t = Table([[Paragraph(title, head_s)]], colWidths=[7.2*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1), BLUE),
        ('TOPPADDING',(0,0),(-1,-1),8), ('BOTTOMPADDING',(0,0),(-1,-1),8)]))
    story.append(t)

def make_signature(story, co, ps_func):
    from reportlab.platypus import Table, TableStyle, Image, Paragraph, Spacer
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_RIGHT
    sig_b   = img_to_bytes(co.get('hr_signature_path',''))
    stamp_b = img_to_bytes(co.get('stamp_path',''))
    bold_s  = ps_func('SigB', fontSize=10, fontName='Helvetica-Bold',
                      textColor=colors.HexColor('#1f2937'))
    r_s     = ps_func('SigR', fontSize=10, fontName='Helvetica',
                      alignment=TA_RIGHT, textColor=colors.HexColor('#1f2937'))
    story.append(Spacer(1, 28))
    if sig_b or stamp_b:
        imgs = [
            Image(BytesIO(sig_b),   width=1.4*inch, height=0.55*inch) if sig_b   else Spacer(1,1),
            Image(BytesIO(stamp_b), width=1.1*inch, height=1.1*inch)  if stamp_b else Spacer(1,1),
        ]
        t = Table([imgs], colWidths=[3.6*inch, 3.6*inch])
        t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'BOTTOM')]))
        story.append(t)
    story.append(Table([[
        Paragraph(f"<b>{co.get('hr_name','HR Manager')}</b>", bold_s),
        Paragraph(f"<b>For {co['name']}</b>", r_s),
    ]], colWidths=[3.6*inch, 3.6*inch]))
    story.append(Table([[
        Paragraph(co.get('hr_designation','Human Resources'), bold_s),
        Paragraph(co['name'], r_s),
    ]], colWidths=[3.6*inch, 3.6*inch]))

def generate_payslip_pdf(employee_id, payslip_data):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT

    co  = get_co()
    emp = get_emp(employee_id)
    if not emp: return None

    buf  = BytesIO()
    doc  = SimpleDocTemplate(buf, pagesize=A4,
                              rightMargin=55, leftMargin=55, topMargin=45, bottomMargin=70)
    SS   = getSampleStyleSheet()

    def ps(name, **kw):
        return ParagraphStyle(name, parent=SS['Normal'], **kw)

    BLUE  = colors.HexColor('#1a237e')
    GREEN = colors.HexColor('#059669')
    RED   = colors.HexColor('#dc2626')
    LGRAY = colors.HexColor('#f8f9ff')
    DGRID = colors.HexColor('#c5cae9')
    bold_s  = ps('Bd', fontSize=9.5, fontName='Helvetica-Bold',  textColor=colors.HexColor('#1f2937'))
    body_s  = ps('Bo', fontSize=9.5, fontName='Helvetica',       textColor=colors.HexColor('#1f2937'), leading=15)
    right_s = ps('Ri', fontSize=9.5, fontName='Helvetica',       alignment=TA_RIGHT)

    story = []
    make_header(story, co, ps)
    pd = payslip_data
    month_name = datetime(int(pd.get('year',2024)), int(pd.get('month',1)), 1).strftime('%B %Y')
    make_title_bar(story, f'PAY SLIP — {month_name}', ps)
    story.append(Spacer(1,8))

    # Employee info block
    info = [
        ['Employee Name:', f"{emp['first_name']} {emp['last_name']}", 'Emp Code:', emp.get('emp_code','')],
        ['Designation:',   emp.get('designation',''),                  'Department:', emp.get('department','')],
        ['Date of Joining:', emp.get('date_of_joining',''),            'PAN:',        emp.get('pan_number','')],
        ['UAN:',           emp.get('uan_number',''),                   'Bank Account:', emp.get('bank_account','')],
        ['Working Days:',  str(pd.get('working_days',26)),             'Paid Days:',  str(pd.get('paid_days',26))],
        ['LOP Days:',      str(pd.get('lop_days',0)),                  'Bank IFSC:',  emp.get('bank_ifsc','')],
    ]

    def info_tbl(rows, col_w):
        t = Table(rows, colWidths=col_w)
        t.setStyle(TableStyle([
            ('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),
            ('FONTNAME',(2,0),(2,-1),'Helvetica-Bold'),
            ('FONTSIZE',(0,0),(-1,-1),9),
            ('ROWBACKGROUNDS',(0,0),(-1,-1),[LGRAY, colors.white]),
            ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),
            ('LEFTPADDING',(0,0),(-1,-1),6),
            ('BOX',(0,0),(-1,-1),0.5,DGRID),('INNERGRID',(0,0),(-1,-1),0.5,DGRID),
        ]))
        return t

    story.append(info_tbl(info, [1.6*inch,2.1*inch,1.5*inch,2.0*inch]))
    story.append(Spacer(1,10))

    # Earnings & deductions
    def money(v): return f"{float(v or 0):,.2f}"

    earn_rows = [
        [Paragraph('<b>EARNINGS</b>', bold_s), Paragraph('<b>Amount (₹)</b>', bold_s),
         Paragraph('<b>DEDUCTIONS</b>', bold_s), Paragraph('<b>Amount (₹)</b>', bold_s)],
        ['Basic Salary',        money(pd.get('basic_salary',0)),  'PF (Employee 12%)',    money(pd.get('pf_employee',0))],
        ['HRA',                 money(pd.get('hra',0)),            'PF (Employer 12%)',    money(pd.get('pf_employer',0))],
        ['Transport Allowance', money(pd.get('transport_allowance',0)), 'ESI (Employee 0.75%)', money(pd.get('esi_employee',0))],
        ['Medical Allowance',   money(pd.get('medical_allowance',0)),   'ESI (Employer 3.25%)', money(pd.get('esi_employer',0))],
        ['Special Allowance',   money(pd.get('special_allowance',0)),   'Professional Tax',     money(pd.get('professional_tax',0))],
        ['LTA',                 money(pd.get('lta',0)),            'TDS (Income Tax)',     money(pd.get('tds',0))],
        ['Other Earnings',      money(pd.get('other_earnings',0)), 'Other Deductions',     money(pd.get('other_deduction',0))],
        ['',                    '',                                'Advance Deduction',    money(pd.get('advance_deduction',0))],
        ['',                    '',                                'LOP Deduction',        money(pd.get('lop_deduction',0))],
    ]
    total_earn = float(pd.get('gross_salary',0))
    total_ded  = float(pd.get('total_deductions',0))
    earn_rows.append([
        Paragraph('<b>Gross Salary</b>', bold_s),
        Paragraph(f'<b>₹ {total_earn:,.2f}</b>', bold_s),
        Paragraph('<b>Total Deductions</b>', bold_s),
        Paragraph(f'<b>₹ {total_ded:,.2f}</b>', bold_s),
    ])
    et = Table(earn_rows, colWidths=[2.2*inch,1.4*inch,2.2*inch,1.4*inch])
    et.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),BLUE), ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,-1),9),
        ('ROWBACKGROUNDS',(0,1),(-1,-2),[LGRAY,colors.white]),
        ('BACKGROUND',(0,-1),(-1,-1),colors.HexColor('#dde0f5')),
        ('FONTNAME',(0,-1),(-1,-1),'Helvetica-Bold'),
        ('BOX',(0,0),(-1,-1),0.5,DGRID),('INNERGRID',(0,0),(-1,-1),0.5,DGRID),
        ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),
        ('LEFTPADDING',(0,0),(-1,-1),6),
    ]))
    story.append(et)
    story.append(Spacer(1,8))

    # Net pay bar
    net_s = ps('Net', fontSize=12, fontName='Helvetica-Bold', textColor=colors.white)
    nt = Table([[Paragraph(f'NET SALARY (Take Home): ₹ {float(pd.get("net_salary",0)):,.2f}', net_s)]],
               colWidths=[7.2*inch])
    nt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),GREEN),
                             ('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10),
                             ('LEFTPADDING',(0,0),(-1,-1),10)]))
    story.append(nt)

    # YTD & HRA exemption note
    story.append(Spacer(1,6))
    ytd_g = float(pd.get('ytd_gross',0)); ytd_t = float(pd.get('ytd_tds',0))
    ytd_s = ps('YTD', fontSize=8.5, fontName='Helvetica', textColor=colors.HexColor('#6b7280'), leading=13)
    story.append(Paragraph(
        f"YTD Gross: ₹{ytd_g:,.2f}  |  YTD TDS: ₹{ytd_t:,.2f}  |  "
        f"HRA Exemption (10(13A)): ₹{float(pd.get('hra_exemption',0)):,.2f}  |  "
        f"PF Employer share is not part of Net Salary.",
        ytd_s))
    if pd.get('notes'):
        story.append(Paragraph(f"<i>Note: {pd['notes']}</i>", ytd_s))

    # Employee photo in payslip (top-right area via footer)
    photo_b = img_to_bytes(emp.get('photo_path',''))
    if photo_b:
        story.insert(3, Table([[Image(BytesIO(photo_b), width=0.8*inch, height=0.8*inch)]],
                               colWidths=[7.2*inch]))

    make_signature(story, co, ps)
    story.append(Paragraph(
        "This is a system-generated document. No physical signature required.",
        ps('Disc', fontSize=7.5, fontName='Helvetica', textColor=colors.gray, alignment=TA_CENTER)))
    doc.build(story)
    return buf.getvalue()

def generate_letter_pdf(doc_type, employee_id, extra_data):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT

    co  = get_co()
    emp = get_emp(employee_id)
    if not emp: return None

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                             rightMargin=60, leftMargin=60, topMargin=45, bottomMargin=70)
    SS  = getSampleStyleSheet()

    def ps(name, **kw):
        return ParagraphStyle(name, parent=SS['Normal'], **kw)

    BLUE  = colors.HexColor('#1a237e')
    LGRAY = colors.HexColor('#e8eaf6')
    DGRID = colors.HexColor('#c5cae9')
    body_s  = ps('Bo', fontSize=10, fontName='Helvetica', leading=17,
                 textColor=colors.HexColor('#1f2937'), spaceAfter=6)
    bold_s  = ps('Bd', fontSize=10, fontName='Helvetica-Bold', textColor=colors.HexColor('#1f2937'))
    right_s = ps('Ri', fontSize=10, fontName='Helvetica', alignment=TA_RIGHT)

    story = []
    make_header(story, co, ps)

    labels = {
        'offer_letter':'OFFER LETTER', 'appointment_letter':'APPOINTMENT LETTER',
        'relieving_letter':'RELIEVING LETTER', 'experience_letter':'EXPERIENCE CERTIFICATE',
        'increment_letter':'SALARY INCREMENT LETTER', 'warning_letter':'WARNING LETTER',
        'termination_letter':'TERMINATION LETTER',
    }
    make_title_bar(story, labels.get(doc_type, doc_type.upper()), ps)
    story.append(Spacer(1,12))

    today = datetime.now().strftime('%d %B %Y')
    emp_name = f"{emp['first_name']} {emp['last_name']}"
    ed = extra_data or {}

    def detail_table(rows, cw=None):
        cw = cw or [2.4*inch, 4.8*inch]
        t = Table(rows, colWidths=cw)
        t.setStyle(TableStyle([
            ('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),
            ('FONTSIZE',(0,0),(-1,-1),9.5),
            ('ROWBACKGROUNDS',(0,0),(-1,-1),[LGRAY, colors.white]),
            ('BOX',(0,0),(-1,-1),0.5,DGRID),('INNERGRID',(0,0),(-1,-1),0.5,DGRID),
            ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),
            ('LEFTPADDING',(0,0),(-1,-1),6),
        ]))
        return t

    gross_m = sum(float(emp.get(k,0)) for k in
                  ['basic_salary','hra','transport_allowance','medical_allowance','special_allowance','lta'])

    if doc_type in ('offer_letter','appointment_letter'):
        story.append(Paragraph(f"Date: {today}", right_s))
        story.append(Spacer(1,6))
        story.append(Paragraph("To,", body_s))
        story.append(Paragraph(f"<b>{emp_name}</b>", bold_s))
        if emp.get('address'): story.append(Paragraph(emp['address'], body_s))
        story.append(Spacer(1,10))
        subj = f"Offer of Employment – {emp.get('designation','')}" if doc_type=='offer_letter' \
               else f"Appointment as {emp.get('designation','')}"
        story.append(Paragraph(f"Subject: <b>{subj}</b>", body_s))
        story.append(Spacer(1,8))
        story.append(Paragraph(f"Dear {emp['first_name']},", body_s))
        story.append(Spacer(1,6))
        if doc_type == 'offer_letter':
            story.append(Paragraph(
                f"We are pleased to extend an offer of employment for the position of "
                f"<b>{emp.get('designation','')}</b> in the <b>{emp.get('department','')}</b> department "
                f"at <b>{co['name']}</b>. We believe your skills and experience will be a valuable asset.",
                body_s))
        else:
            story.append(Paragraph(
                f"With reference to your application, we are pleased to appoint you as "
                f"<b>{emp.get('designation','')}</b> in the <b>{emp.get('department','')}</b> department "
                f"at <b>{co['name']}</b>, effective <b>{emp.get('date_of_joining','')}</b>.",
                body_s))
        story.append(Spacer(1,8))
        story.append(detail_table([
            ['Position:',        emp.get('designation','')],
            ['Department:',      emp.get('department','')],
            ['Date of Joining:',  emp.get('date_of_joining','')],
            ['Employment Type:',  emp.get('employment_type','Full-Time')],
            ['Gross Monthly:',   f"₹ {gross_m:,.2f}"],
            ['Annual CTC:',      f"₹ {gross_m*12:,.2f}"],
            ['Probation Period:', ed.get('probation','3 Months')],
            ['Notice Period:',   ed.get('notice_period','30 Days')],
            ['Reporting To:',    emp.get('manager_name','')],
            ['Work Location:',   f"{co.get('city','')}"],
        ]))
        story.append(Spacer(1,10))
        story.append(Paragraph(
            "This offer is contingent upon successful background verification. "
            "Kindly sign and return a copy as acknowledgement. We look forward to welcoming you.",
            body_s))

    elif doc_type in ('relieving_letter','experience_letter'):
        story.append(Paragraph(f"Date: {today}", right_s))
        story.append(Spacer(1,8))
        story.append(Paragraph("To Whom It May Concern,", body_s))
        story.append(Spacer(1,10))
        last_date = ed.get('last_working_date', today)
        if doc_type == 'relieving_letter':
            story.append(Paragraph(
                f"This is to certify that <b>{emp_name}</b> (Employee Code: <b>{emp.get('emp_code','')}</b>) "
                f"was employed with <b>{co['name']}</b> as <b>{emp.get('designation','')}</b> in the "
                f"<b>{emp.get('department','')}</b> department from <b>{emp.get('date_of_joining','')}</b> "
                f"to <b>{last_date}</b>.",
                body_s))
            story.append(Spacer(1,8))
            story.append(Paragraph(
                f"{emp['first_name']} has been relieved from duties on {last_date} after completing all handover "
                f"procedures and formalities. We wish them all the very best.",
                body_s))
        else:
            story.append(Paragraph(
                f"This is to certify that <b>{emp_name}</b> (Employee Code: <b>{emp.get('emp_code','')}</b>) "
                f"served as <b>{emp.get('designation','')}</b> – <b>{emp.get('department','')}</b> at "
                f"<b>{co['name']}</b> from <b>{emp.get('date_of_joining','')}</b> to <b>{last_date}</b>.",
                body_s))
            story.append(Spacer(1,8))
            story.append(Paragraph(
                f"During their tenure, {emp['first_name']} demonstrated exceptional professional skills "
                f"and was a valued member of our organisation. We wish them great success ahead.",
                body_s))

    elif doc_type == 'increment_letter':
        story.append(Paragraph(f"Date: {today}", right_s))
        story.append(Spacer(1,6))
        story.append(Paragraph(f"To,\n<b>{emp_name}</b>\n{emp.get('department','')}", body_s))
        story.append(Spacer(1,8))
        story.append(Paragraph("Subject: <b>Salary Increment Letter</b>", body_s))
        story.append(Spacer(1,8))
        story.append(Paragraph(f"Dear {emp['first_name']},", body_s))
        story.append(Spacer(1,6))
        story.append(Paragraph(
            f"In recognition of your performance and contribution to <b>{co['name']}</b>, "
            f"we are pleased to revise your compensation:",
            body_s))
        story.append(Spacer(1,8))
        old_s = float(ed.get('old_salary',0)); new_s = float(ed.get('new_salary', emp.get('basic_salary',0)))
        hike_pct = ((new_s - old_s) / old_s * 100) if old_s else 0
        eff = ed.get('effective_date', today)
        inc_t = Table([
            [Paragraph('<b>Component</b>',bold_s), Paragraph('<b>Previous (₹)</b>',bold_s),
             Paragraph('<b>Revised (₹)</b>',bold_s), Paragraph('<b>Hike %</b>',bold_s)],
            ['Basic Salary', f"{old_s:,.2f}", f"{new_s:,.2f}", f"{hike_pct:.1f}%"],
            ['Effective Date', '', eff, ''],
        ], colWidths=[2.4*inch, 1.8*inch, 1.8*inch, 1.2*inch])
        inc_t.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),BLUE),('TEXTCOLOR',(0,0),(-1,0),colors.white),
            ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),9.5),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[LGRAY,colors.white]),
            ('BOX',(0,0),(-1,-1),0.5,DGRID),('INNERGRID',(0,0),(-1,-1),0.5,DGRID),
            ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),('LEFTPADDING',(0,0),(-1,-1),8),
        ]))
        story.append(inc_t)
        story.append(Spacer(1,10))
        story.append(Paragraph(
            f"This increment is effective from <b>{eff}</b>. We appreciate your continued contributions "
            f"and look forward to your growth with us.",
            body_s))

    elif doc_type in ('warning_letter','termination_letter'):
        story.append(Paragraph(f"Date: {today}", right_s))
        story.append(Spacer(1,6))
        story.append(Paragraph(f"To,\n<b>{emp_name}</b>\nEmp Code: {emp.get('emp_code','')}", body_s))
        story.append(Spacer(1,10))
        subj = "Warning Letter" if doc_type=='warning_letter' else "Termination Letter"
        story.append(Paragraph(f"Subject: <b>{subj}</b>", body_s))
        story.append(Spacer(1,8))
        story.append(Paragraph(f"Dear {emp['first_name']},", body_s))
        story.append(Spacer(1,6))
        if ed.get('body_text'):
            story.append(Paragraph(ed['body_text'], body_s))
        elif doc_type == 'warning_letter':
            story.append(Paragraph(
                f"This letter serves as an official written warning regarding "
                f"{ed.get('reason','your conduct and performance')}. "
                f"Such behaviour is in violation of company policies. "
                f"You are required to improve immediately or face further disciplinary action.",
                body_s))
        else:
            story.append(Paragraph(
                f"After careful deliberation, the management has decided to terminate your employment with "
                f"{co['name']} effective <b>{ed.get('last_date', today)}</b>. "
                f"Reason: {ed.get('reason','As discussed in prior meetings.')} "
                f"Please complete all exit formalities and return company assets.",
                body_s))

    make_signature(story, co, ps)
    doc.build(story)
    return buf.getvalue()

def generate_form16_pdf(employee_id, financial_year, payslips_data):
    """Generate Form 16 (Part A + Part B) per Indian Income Tax rules"""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, PageBreak
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

    co  = get_co()
    emp = get_emp(employee_id)
    if not emp: return None

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                             rightMargin=50, leftMargin=50, topMargin=45, bottomMargin=60)
    SS  = getSampleStyleSheet()

    def ps(name, **kw):
        return ParagraphStyle(name, parent=SS['Normal'], **kw)

    BLUE  = colors.HexColor('#1a237e')
    LGRAY = colors.HexColor('#e8eaf6')
    DGRID = colors.HexColor('#c5cae9')
    GREEN = colors.HexColor('#065f46')
    c_s   = ps('C',  fontSize=9,    fontName='Helvetica',      alignment=TA_CENTER, leading=13)
    bold_s= ps('Bd', fontSize=9.5,  fontName='Helvetica-Bold', textColor=colors.HexColor('#1f2937'))
    body_s= ps('Bo', fontSize=9.5,  fontName='Helvetica',      leading=15, textColor=colors.HexColor('#1f2937'))
    h1_s  = ps('H1', fontSize=12,   fontName='Helvetica-Bold', textColor=BLUE, spaceAfter=4)
    sub_s = ps('Sb', fontSize=8.5,  fontName='Helvetica',      textColor=colors.HexColor('#374151'), alignment=TA_CENTER)
    right_s = ps('Ri', fontSize=9.5, fontName='Helvetica', alignment=TA_RIGHT)

    fy_label = f"FY {financial_year}–{str(financial_year+1)[2:]}"
    ay_label = f"AY {financial_year+1}–{str(financial_year+2)[2:]}"

    # Aggregate annual figures
    annual = {k: sum(float(p.get(k,0)) for p in payslips_data) for k in
              ['basic_salary','hra','transport_allowance','medical_allowance','special_allowance',
               'lta','other_earnings','gross_salary','pf_employee','esi_employee',
               'professional_tax','tds','other_deduction','advance_deduction',
               'total_deductions','net_salary','hra_exemption']}

    # Tax computation
    gross_annual   = annual['gross_salary']
    hra_exempt     = annual['hra_exemption']
    taxable_income = max(0, gross_annual - hra_exempt - 75000)  # std deduction 75000
    pf_80c         = min(annual['pf_employee'], 150000)          # 80C limit
    taxable_income = max(0, taxable_income - pf_80c)
    tax_payable_annual = annual['tds'] * len(payslips_data)

    story = []

    # ── PART A ──────────────────────────────────────────────────────────────
    make_header(story, co, ps)
    story.append(Spacer(1,4))
    fb_t = ps('FBT', fontSize=14, fontName='Helvetica-Bold',
              textColor=BLUE, alignment=TA_CENTER, spaceAfter=2)
    story.append(Paragraph("FORM 16", fb_t))
    story.append(Paragraph(
        f"Certificate under Section 203 of Income Tax Act, 1961 for TDS on Salary | {fy_label} ({ay_label})",
        c_s))
    story.append(HRFlowable(width="100%", thickness=1.5, color=BLUE, spaceAfter=10))

    # Part A label
    pa_t = Table([[Paragraph("PART A — TDS CERTIFICATE", ps('PA',fontSize=11,fontName='Helvetica-Bold',
                                                              textColor=colors.white, alignment=TA_CENTER))]],
                  colWidths=[7.3*inch])
    pa_t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),BLUE),
                               ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
    story.append(pa_t)
    story.append(Spacer(1,8))

    def row2(l1,v1,l2,v2, bold_val=False):
        v1s = ps('V1', fontSize=9.5, fontName='Helvetica-Bold' if bold_val else 'Helvetica',
                 textColor=colors.HexColor('#1f2937'))
        return [l1, Paragraph(str(v1), v1s), l2, Paragraph(str(v2), v1s)]

    employer_info = [
        row2("Employer Name:", co['name'], "Employer PAN:", co.get('pan','')),
        row2("TAN:", co.get('tan',''), "GSTIN:", co.get('gstin','')),
        row2("Address:", f"{co.get('address','')} {co.get('city','')} {co.get('state','')}", "Pincode:", co.get('pincode','')),
    ]
    et = Table(employer_info, colWidths=[1.5*inch,2.2*inch,1.5*inch,2.1*inch])
    et.setStyle(TableStyle([
        ('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),('FONTNAME',(2,0),(2,-1),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,-1),9),
        ('ROWBACKGROUNDS',(0,0),(-1,-1),[LGRAY, colors.white]),
        ('BOX',(0,0),(-1,-1),0.5,DGRID),('INNERGRID',(0,0),(-1,-1),0.5,DGRID),
        ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),('LEFTPADDING',(0,0),(-1,-1),5),
    ]))
    story.append(Paragraph("Employer Details", bold_s))
    story.append(Spacer(1,4))
    story.append(et)
    story.append(Spacer(1,8))

    employee_info = [
        row2("Employee Name:", f"{emp['first_name']} {emp['last_name']}", "Employee Code:", emp.get('emp_code','')),
        row2("PAN:", emp.get('pan_number',''), "UAN:", emp.get('uan_number','')),
        row2("Designation:", emp.get('designation',''), "Department:", emp.get('department','')),
        row2("Date of Joining:", emp.get('date_of_joining',''), "Employment Type:", emp.get('employment_type','')),
        row2("Period (From):", f"01 April {financial_year}", "Period (To):", f"31 March {financial_year+1}"),
    ]
    et2 = Table(employee_info, colWidths=[1.5*inch,2.2*inch,1.5*inch,2.1*inch])
    et2.setStyle(TableStyle([
        ('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),('FONTNAME',(2,0),(2,-1),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,-1),9),
        ('ROWBACKGROUNDS',(0,0),(-1,-1),[LGRAY, colors.white]),
        ('BOX',(0,0),(-1,-1),0.5,DGRID),('INNERGRID',(0,0),(-1,-1),0.5,DGRID),
        ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),('LEFTPADDING',(0,0),(-1,-1),5),
    ]))
    story.append(Paragraph("Employee Details", bold_s))
    story.append(Spacer(1,4))
    story.append(et2)
    story.append(Spacer(1,8))

    # Quarterly TDS summary
    months_per_q = {
        'Q1 (Apr–Jun)': [4,5,6], 'Q2 (Jul–Sep)': [7,8,9],
        'Q3 (Oct–Dec)': [10,11,12], 'Q4 (Jan–Mar)': [1,2,3],
    }
    q_rows = [[
        Paragraph('<b>Quarter</b>', bold_s), Paragraph('<b>TDS Credited (₹)</b>', bold_s),
        Paragraph('<b>Receipt No.</b>', bold_s), Paragraph('<b>Date of Deposit</b>', bold_s),
    ]]
    q_total = 0
    for qlabel, months in months_per_q.items():
        q_tds = sum(float(p.get('tds',0)) for p in payslips_data if int(p.get('month',0)) in months)
        q_total += q_tds
        q_rows.append([qlabel, f"{q_tds:,.2f}", "—", "—"])
    q_rows.append([Paragraph('<b>Total TDS Deducted</b>',bold_s), Paragraph(f'<b>{q_total:,.2f}</b>',bold_s), '', ''])
    qt = Table(q_rows, colWidths=[2.2*inch,2.0*inch,1.5*inch,1.6*inch])
    qt.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),BLUE),('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),9),
        ('ROWBACKGROUNDS',(0,1),(-1,-2),[LGRAY,colors.white]),
        ('BACKGROUND',(0,-1),(-1,-1),colors.HexColor('#dde0f5')),
        ('FONTNAME',(0,-1),(-1,-1),'Helvetica-Bold'),
        ('BOX',(0,0),(-1,-1),0.5,DGRID),('INNERGRID',(0,0),(-1,-1),0.5,DGRID),
        ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),('LEFTPADDING',(0,0),(-1,-1),6),
    ]))
    story.append(Paragraph("Quarterly TDS Details", bold_s))
    story.append(Spacer(1,4))
    story.append(qt)

    make_signature(story, co, ps)
    story.append(PageBreak())

    # ── PART B ──────────────────────────────────────────────────────────────
    make_header(story, co, ps)
    story.append(Spacer(1,4))
    story.append(Paragraph("FORM 16 — PART B", fb_t))
    story.append(Paragraph(
        f"Statement of Particulars as per Section 192(2B) | {fy_label} ({ay_label})",
        c_s))
    story.append(HRFlowable(width="100%", thickness=1.5, color=BLUE, spaceAfter=10))

    pb_t = Table([[Paragraph("PART B — SALARY COMPUTATION & TAX", ps('PB',fontSize=11,fontName='Helvetica-Bold',
                                                                       textColor=colors.white,alignment=TA_CENTER))]],
                  colWidths=[7.3*inch])
    pb_t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#00695c')),
                               ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
    story.append(pb_t)
    story.append(Spacer(1,8))

    # Salary breakup
    sb_rows = [
        [Paragraph('<b>INCOME FROM SALARY</b>',bold_s), ''],
        ['1. Basic Salary',                 f"{annual['basic_salary']:,.2f}"],
        ['2. House Rent Allowance (Gross)',  f"{annual['hra']:,.2f}"],
        ['   Less: HRA Exemption u/s 10(13A)', f"({annual['hra_exemption']:,.2f})"],
        ['   Taxable HRA',                  f"{max(0,annual['hra']-annual['hra_exemption']):,.2f}"],
        ['3. Transport Allowance',           f"{annual['transport_allowance']:,.2f}"],
        ['4. Medical Allowance',             f"{annual['medical_allowance']:,.2f}"],
        ['5. Special Allowance',             f"{annual['special_allowance']:,.2f}"],
        ['6. Leave Travel Allowance',        f"{annual['lta']:,.2f}"],
        ['7. Other Earnings',                f"{annual['other_earnings']:,.2f}"],
        [Paragraph('<b>Gross Salary</b>',bold_s), Paragraph(f"<b>{annual['gross_salary']:,.2f}</b>",bold_s)],
        ['', ''],
        [Paragraph('<b>DEDUCTIONS UNDER CHAPTER VI-A</b>',bold_s),''],
        ['8. Less: Standard Deduction (u/s 16(ia))', '75,000.00'],
        [Paragraph('<b>Income Chargeable under Head Salaries</b>',bold_s),
         Paragraph(f"<b>{max(0,annual['gross_salary']-annual['hra_exemption']-75000):,.2f}</b>",bold_s)],
        ['', ''],
        [Paragraph('<b>DEDUCTION u/s 80C</b>',bold_s),''],
        ['9. Employee PF Contribution',      f"{annual['pf_employee']:,.2f}"],
        ['   Total 80C deduction (max ₹1,50,000)', f"{pf_80c:,.2f}"],
        [Paragraph('<b>Gross Total Income</b>',bold_s),
         Paragraph(f"<b>{taxable_income:,.2f}</b>",bold_s)],
    ]

    # Tax computation rows
    sb_rows += [
        ['', ''],
        [Paragraph('<b>TAX COMPUTATION (New Tax Regime)</b>',bold_s),''],
        ['Tax on Income (as per slabs)',     f"{max(0,tax_payable_annual):,.2f}"],
        ['Less: Rebate u/s 87A (if applicable)', f"{max(0,tax_payable_annual):,.2f}" if taxable_income<=700000 else '0.00'],
        ['Tax after Rebate',                 f"{0 if taxable_income<=700000 else max(0,tax_payable_annual):,.2f}"],
        ['Add: Health & Education Cess @4%', f"{0 if taxable_income<=700000 else max(0,tax_payable_annual*0.04):,.2f}"],
        [Paragraph('<b>Total Tax Payable</b>',bold_s),
         Paragraph(f"<b>{0 if taxable_income<=700000 else tax_payable_annual:,.2f}</b>",bold_s)],
        ['Less: TDS Deducted (Part A)',      f"{q_total:,.2f}"],
        [Paragraph('<b>Balance Tax Payable / (Refundable)</b>',bold_s),
         Paragraph(f"<b>{max(0,(0 if taxable_income<=700000 else tax_payable_annual)-q_total):,.2f}</b>",bold_s)],
    ]

    sbt = Table(sb_rows, colWidths=[5.1*inch, 2.2*inch])
    sbt.setStyle(TableStyle([
        ('FONTSIZE',(0,0),(-1,-1),9),
        ('ROWBACKGROUNDS',(0,0),(-1,-1),[colors.white, LGRAY]),
        ('BOX',(0,0),(-1,-1),0.5,DGRID),('INNERGRID',(0,0),(-1,-1),0.5,DGRID),
        ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),
        ('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),
        ('ALIGN',(1,0),(1,-1),'RIGHT'),
    ]))
    story.append(sbt)
    story.append(Spacer(1,10))

    # Declaration
    dec_s = ps('Dec', fontSize=8.5, fontName='Helvetica',
               textColor=colors.HexColor('#374151'), leading=13)
    story.append(Paragraph(
        "I/We hereby certify that a sum of ₹ " + f"{q_total:,.2f}" +
        f" has been deducted at source and paid to the credit of the Central Government as per provisions "
        f"of the Income Tax Act, 1961.",
        dec_s))
    story.append(Spacer(1,4))
    story.append(Paragraph("Financial Year: " + fy_label + "  |  Assessment Year: " + ay_label, dec_s))

    make_signature(story, co, ps)
    story.append(Paragraph(
        "This is a computer-generated Form 16. Verify with actual tax workings. Not valid without employer seal.",
        ps('Disc', fontSize=7.5, fontName='Helvetica', textColor=colors.gray, alignment=TA_CENTER)))
    doc.build(story)
    return buf.getvalue()

# ─── DOCUMENT GENERATION ROUTES ───────────────────────────────────────────────
@app.route('/api/generate/payslip/<int:employee_id>', methods=['POST'])
def gen_payslip(employee_id):
    u = verify_token(request)
    if not u: return jsonify({'error':'Unauthorized'}), 403
    if u['role'] not in ('admin','hr') and u['employee_id'] != employee_id:
        return jsonify({'error':'Unauthorized'}), 403
    d = request.json or {}
    # load from DB if payslip_id given
    if d.get('payslip_id'):
        with get_db() as db:
            row = db.execute("SELECT * FROM payslips WHERE id=?", (d['payslip_id'],)).fetchone()
            if row: d = {**dict(row), **d}
    pdf = generate_payslip_pdf(employee_id, d)
    if not pdf: return jsonify({'error':'Employee not found'}), 404
    emp = get_emp(employee_id)
    fname = f"payslip_{emp['emp_code']}_{d.get('year','')}{str(d.get('month','')).zfill(2)}.pdf"
    with get_db() as db:
        db.execute("INSERT INTO generated_documents(employee_id,doc_type,generated_by) VALUES(?,?,?)",
                   (employee_id,'payslip',u['username']))
    return send_file(BytesIO(pdf), mimetype='application/pdf', as_attachment=True, download_name=fname)

@app.route('/api/generate/<doc_type>/<int:employee_id>', methods=['POST'])
def gen_doc(doc_type, employee_id):
    u = verify_token(request)
    if not u: return jsonify({'error':'Unauthorized'}), 403
    if u['role'] not in ('admin','hr') and u['employee_id'] != employee_id:
        return jsonify({'error':'Unauthorized'}), 403
    valid = ['offer_letter','appointment_letter','relieving_letter','experience_letter',
             'increment_letter','warning_letter','termination_letter']
    if doc_type not in valid: return jsonify({'error':'Invalid type'}), 400
    ed = request.json or {}
    pdf = generate_letter_pdf(doc_type, employee_id, ed)
    if not pdf: return jsonify({'error':'Employee not found'}), 404
    emp = get_emp(employee_id)
    fname = f"{doc_type}_{emp['emp_code']}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    with get_db() as db:
        db.execute("INSERT INTO generated_documents(employee_id,doc_type,generated_by) VALUES(?,?,?)",
                   (employee_id, doc_type, u['username']))
    return send_file(BytesIO(pdf), mimetype='application/pdf', as_attachment=True, download_name=fname)

@app.route('/api/generate/form16/<int:employee_id>', methods=['POST'])
def gen_form16(employee_id):
    u = verify_token(request)
    if not u: return jsonify({'error':'Unauthorized'}), 403
    if u['role'] not in ('admin','hr') and u['employee_id'] != employee_id:
        return jsonify({'error':'Unauthorized'}), 403
    d = request.json or {}
    fy = int(d.get('financial_year', datetime.now().year if datetime.now().month >= 4 else datetime.now().year - 1))
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM payslips WHERE employee_id=? AND year=? ORDER BY month",
            (employee_id, fy)).fetchall()
    payslips_data = [dict(r) for r in rows]
    if not payslips_data:
        return jsonify({'error':f'No payslips found for FY {fy}'}), 404
    pdf = generate_form16_pdf(employee_id, fy, payslips_data)
    if not pdf: return jsonify({'error':'Employee not found'}), 404
    emp = get_emp(employee_id)
    fname = f"Form16_{emp['emp_code']}_FY{fy}-{str(fy+1)[2:]}.pdf"
    with get_db() as db:
        db.execute("INSERT INTO generated_documents(employee_id,doc_type,generated_by) VALUES(?,?,?)",
                   (employee_id,'form16',u['username']))
    return send_file(BytesIO(pdf), mimetype='application/pdf', as_attachment=True, download_name=fname)

@app.route('/api/documents', methods=['GET'])
def get_gen_docs():
    u = verify_token(request)
    if not u: return jsonify({'error':'Unauthorized'}), 403
    eid = request.args.get('employee_id')
    with get_db() as db:
        if u['role'] in ('admin','hr'):
            q = "SELECT d.*,e.first_name,e.last_name,e.emp_code FROM generated_documents d JOIN employees e ON d.employee_id=e.id"
            args = []
            if eid: q += " WHERE d.employee_id=?"; args.append(eid)
            q += " ORDER BY d.generated_at DESC LIMIT 100"
        else:
            q = "SELECT d.*,e.first_name,e.last_name,e.emp_code FROM generated_documents d JOIN employees e ON d.employee_id=e.id WHERE d.employee_id=? ORDER BY d.generated_at DESC"
            args = [u['employee_id']]
        return jsonify([dict(r) for r in db.execute(q, args).fetchall()])

@app.route('/api/stats', methods=['GET'])
def get_stats():
    if not require_admin(request): return jsonify({'error':'Unauthorized'}), 403
    with get_db() as db:
        total  = db.execute("SELECT COUNT(*) as c FROM employees").fetchone()['c']
        active = db.execute("SELECT COUNT(*) as c FROM employees WHERE status='Active'").fetchone()['c']
        depts  = db.execute("SELECT department,COUNT(*) as c FROM employees WHERE status='Active' GROUP BY department").fetchall()
        docs   = db.execute("SELECT COUNT(*) as c FROM generated_documents WHERE generated_at>date('now','-30 days')").fetchone()['c']
        payroll= db.execute("SELECT SUM(gross_salary) as s FROM payslips WHERE strftime('%Y-%m',generated_at)=strftime('%Y-%m','now')").fetchone()['s'] or 0
        return jsonify({'total_employees':total,'active_employees':active,
                        'departments':[dict(r) for r in depts],
                        'documents_this_month':docs, 'monthly_payroll':payroll})

@app.route('/')
def index(): return send_from_directory('.', 'index.html')

if __name__ == '__main__':
    print("✅ HR Management System — http://localhost:5000")
    print("🔑 Login: admin / admin123")
    app.run(debug=True, host='0.0.0.0', port=5000)
