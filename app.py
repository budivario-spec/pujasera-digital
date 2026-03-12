import sqlite3
import os
from flask import Flask, render_template, request, redirect, url_for, session
from functools import wraps
from werkzeug.utils import secure_filename
from PIL import Image, ImageOps  # MODUL UNTUK RESIZE DAN CROP

app = Flask(__name__)
app.secret_key = 'rahasia_pujasera_123'
DB_NAME = 'warung_fnb.db'
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- FUNGSI BASIS DATA ---

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS menu (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT NOT NULL,
            harga INTEGER NOT NULL,
            tersedia BOOLEAN NOT NULL DEFAULT 1,
            kategori TEXT NOT NULL,
            foto TEXT DEFAULT 'default.jpg'
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- SISTEM LOGIN ---

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == 'admin123':
            session['logged_in'] = True
            return redirect(url_for('admin'))
    return render_template('login.html')

# --- ROUTES ---

@app.route('/')
def home():
    conn = get_db_connection()
    items = conn.execute("SELECT * FROM menu").fetchall()
    conn.close()
    categories = {
        "makanan": [i for i in items if i['kategori'] == 'makanan'],
        "lauk": [i for i in items if i['kategori'] == 'lauk'],
        "sayur": [i for i in items if i['kategori'] == 'sayur'],
        "minuman": [i for i in items if i['kategori'] == 'minuman'],
        "camilan": [i for i in items if i['kategori'] == 'camilan']
    }
    return render_template('index.html', categories=categories)

@app.route('/admin')
@login_required
def admin():
    conn = get_db_connection()
    items = conn.execute("SELECT * FROM menu").fetchall()
    
    # Query untuk mengambil 10 pencarian terbanyak
    tren = conn.execute("""
        SELECT kata_kunci, COUNT(*) as jumlah 
        FROM log_pencarian 
        GROUP BY kata_kunci 
        ORDER BY jumlah DESC 
        LIMIT 10
    """).fetchall()
    
    conn.close()
    return render_template('admin.html', menu=items, tren_pencarian=tren)

@app.route('/tambah_menu', methods=['POST'])
@login_required
def tambah_menu():
    nama = request.form.get('nama').title()
    harga = request.form.get('harga')
    kategori = request.form.get('kategori')
    
    file = request.files.get('foto')
    filename = 'default.jpg'
    
    if file and file.filename != '':
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # PROSES RESIZE DAN CROP OTOMATIS MENJADI KOTAK
        img = Image.open(file)
        # Mengubah mode ke RGB jika gambar dalam format PNG dengan transparansi
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        
        # Fit ke 400x400 secara proporsional
        img_fit = ImageOps.fit(img, (400, 400), Image.Resampling.LANCZOS)
        img_fit.save(filepath, "JPEG", quality=85, optimize=True)
    
    conn = get_db_connection()
    conn.execute("INSERT INTO menu (nama, harga, tersedia, kategori, foto) VALUES (?, ?, 1, ?, ?)", 
                 (nama, harga, kategori, filename))
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))

@app.route('/edit_menu/<int:item_id>', methods=['POST'])
@login_required
def edit_menu(item_id):
    nama = request.form.get('nama').title()
    harga = request.form.get('harga')
    kategori = request.form.get('kategori')
    file = request.files.get('foto')

    conn = get_db_connection()
    # Jika ada foto baru, proses dan update kolom foto
    if file and file.filename != '':
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        img = Image.open(file)
        if img.mode in ('RGBA', 'P'): img = img.convert('RGB')
        img_fit = ImageOps.fit(img, (400, 400), Image.Resampling.LANCZOS)
        img_fit.save(filepath, "JPEG", quality=85, optimize=True)
        
        conn.execute("UPDATE menu SET nama=?, harga=?, kategori=?, foto=? WHERE id=?", 
                     (nama, harga, kategori, filename, item_id))
    else:
        # Jika tidak ada foto baru, hanya update teks
        conn.execute("UPDATE menu SET nama=?, harga=?, kategori=? WHERE id=?", 
                     (nama, harga, kategori, item_id))
    
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))

@app.route('/delete_menu/<int:item_id>')
@login_required
def delete_menu(item_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM menu WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))

@app.route('/toggle/<int:item_id>')
@login_required
def toggle_stok(item_id):
    conn = get_db_connection()
    conn.execute("UPDATE menu SET tersedia = NOT tersedia WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    # Arahkan kembali ke halaman login agar tidak 404
    return redirect(url_for('login'))

# Tambahkan rute ini di app.py
@app.route('/search')
def search():
    query = request.args.get('q', '').lower()
    conn = get_db_connection()
    
    # 1. Catat pencarian jika ada kata kunci
    if query:
        conn.execute("INSERT INTO log_pencarian (kata_kunci) VALUES (?)", (query,))
        conn.commit()
    
    # 2. Ambil data menu yang cocok
    items = conn.execute("SELECT * FROM menu WHERE nama LIKE ?", ('%' + query + '%',)).fetchall()
    conn.close()
    
    # Bungkus hasil pencarian ke dalam dictionary agar bisa dirender index.html
    results = {'Hasil Pencarian': items}
    return render_template('index.html', categories=results, query=query)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
