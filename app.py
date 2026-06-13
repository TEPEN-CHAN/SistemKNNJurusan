import cloudinary
import cloudinary.uploader
from flask import Flask, render_template, request, redirect, session, jsonify, g, send_file, flash
import pymysql
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from knn import knn_predict
from chatbot import chatbot_response
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from werkzeug.utils import secure_filename
import pandas as pd
import config

# =========================================================
# INISIALISASI APP
# =========================================================
app = Flask(__name__)

# =========================================================
# CONFIG DATABASE
# =========================================================
app.config['MYSQL_HOST'] = getattr(config, 'MYSQL_HOST', None) or os.getenv('MYSQL_HOST')
app.config['MYSQL_USER'] = getattr(config, 'MYSQL_USER', None) or os.getenv('MYSQL_USER')
app.config['MYSQL_PASSWORD'] = getattr(config, 'MYSQL_PASSWORD', None) or os.getenv('MYSQL_PASSWORD')
app.config['MYSQL_DB'] = getattr(config, 'MYSQL_DB', None) or os.getenv('MYSQL_DB')
app.config['MYSQL_PORT'] = int(getattr(config, 'MYSQL_PORT', None) or os.getenv('MYSQL_PORT', 3306))
app.secret_key = getattr(config, 'SECRET_KEY', None) or os.getenv('SECRET_KEY', 'default-secret-key')

try:

    WIB = ZoneInfo('Asia/Jakarta')

except Exception:

    WIB = timezone(timedelta(hours=7))


def waktu_indonesia():

    return datetime.now(WIB).replace(tzinfo=None)

cloudinary.config(
    cloud_name=getattr(config, 'CLOUDINARY_CLOUD_NAME', None) or os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=getattr(config, 'CLOUDINARY_API_KEY', None) or os.getenv('CLOUDINARY_API_KEY'),
    api_secret=getattr(config, 'CLOUDINARY_API_SECRET', None) or os.getenv('CLOUDINARY_API_SECRET'),
    secure=True
)

# =========================================================
# KONEKSI DATABASE MYSQL DENGAN PYMYSQL
# Cocok untuk Vercel / Serverless
# =========================================================
class MySQLConnection:

    def __init__(self, app):

        self.app = app

        app.teardown_appcontext(self.close_connection)

    @property
    def connection(self):

        if 'mysql_connection' not in g:

            required_config = [
                self.app.config.get('MYSQL_HOST'),
                self.app.config.get('MYSQL_USER'),
                self.app.config.get('MYSQL_DB')
            ]

            if not all(required_config):
                raise RuntimeError(
                    'Konfigurasi database belum lengkap. Pastikan MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB, dan MYSQL_PORT sudah diisi.'
                )

            g.mysql_connection = pymysql.connect(
                host=self.app.config['MYSQL_HOST'],
                user=self.app.config['MYSQL_USER'],
                password=self.app.config['MYSQL_PASSWORD'],
                database=self.app.config['MYSQL_DB'],
                port=int(self.app.config.get('MYSQL_PORT', 3306)),
                charset='utf8mb4',
                cursorclass=pymysql.cursors.Cursor,
                autocommit=False,
                ssl={}
            )

        return g.mysql_connection

    def close_connection(self, exception=None):

        db = g.pop('mysql_connection', None)

        if db is not None:

            db.close()


mysql = MySQLConnection(app)
# =========================================================
# HITUNG METRIK EVALUASI KNN
# Accuracy, Precision, Recall, F1-Score
# =========================================================
def hitung_metrik_evaluasi(y_true, y_pred):

    total_data = len(y_true)

    if total_data == 0:

        return {
            'accuracy': 0,
            'precision': 0,
            'recall': 0,
            'f1_score': 0
        }

    benar = 0

    for i in range(total_data):

        if y_true[i] == y_pred[i]:

            benar += 1

    accuracy = benar / total_data

    labels = list(set(y_true))

    precision_total = 0
    recall_total = 0
    f1_total = 0

    for label in labels:

        tp = 0
        fp = 0
        fn = 0

        for i in range(total_data):

            if y_true[i] == label and y_pred[i] == label:

                tp += 1

            elif y_true[i] != label and y_pred[i] == label:

                fp += 1

            elif y_true[i] == label and y_pred[i] != label:

                fn += 1

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0

        if precision + recall > 0:

            f1 = 2 * precision * recall / (precision + recall)

        else:

            f1 = 0

        precision_total += precision
        recall_total += recall
        f1_total += f1

    jumlah_label = len(labels)

    return {
        'accuracy': round(accuracy * 100, 2),
        'precision': round((precision_total / jumlah_label) * 100, 2),
        'recall': round((recall_total / jumlah_label) * 100, 2),
        'f1_score': round((f1_total / jumlah_label) * 100, 2)
    }


# =========================================================
# HELPER FITUR KNN
# Variabel skripsi:
# 1. Mapel      = nilai Pancasila, Matematika,
#                 Bahasa Indonesia, Bahasa Inggris
# 2. Minat bakat = 0 / 1
# 3. Lanjut PT   = 0 / 1
# =========================================================
def to_float(value, default=0):

    try:

        if value is None:

            return default

        return float(str(value).replace(',', '.').strip())

    except:

        return default


def encode_minat_bakat(value):

    if value is None:

        return 0

    nilai = str(value).strip().upper()

    if nilai == '':

        return 0

    try:

        return 1 if float(nilai.replace(',', '.')) >= 1 else 0

    except:

        pass

    nilai_tidak = {
        '0',
        'TIDAK',
        'TIDAK ADA',
        'BELUM',
        'BELUM MENGISI',
        'NONE',
        '-'
    }

    if nilai in nilai_tidak:

        return 0

    return 1


def encode_lanjut_pt(value):

    if value is None:

        return 0

    nilai = str(value).strip().upper()

    if nilai == '':

        return 0

    try:

        return 1 if float(nilai.replace(',', '.')) >= 1 else 0

    except:

        pass

    nilai_ya = {
        '1',
        'IYA',
        'YA',
        'YES',
        'LANJUT',
        'MELANJUTKAN'
    }

    return 1 if nilai in nilai_ya else 0


def buat_fitur_knn(
    nilai_pancasila,
    nilai_matematika,
    nilai_bahasa_indonesia,
    nilai_bahasa_inggris,
    minat_bakat,
    lanjut_pt
):

    return [
        to_float(nilai_pancasila),
        to_float(nilai_matematika),
        to_float(nilai_bahasa_indonesia),
        to_float(nilai_bahasa_inggris),
        encode_minat_bakat(minat_bakat),
        encode_lanjut_pt(lanjut_pt)
    ]
# =========================================================
# SIMPAN LOG AKTIVITAS
# =========================================================
def simpan_log(aktivitas):

    try:

        username = session.get('username', 'System')
        id_role = session.get('id_role', 0)

        if id_role == 1:

            role = 'Admin'

        elif id_role == 2:

            role = 'Guru BK'

        elif id_role == 3:

            role = 'Siswa'

        else:

            role = 'Tidak Diketahui'

        cur = mysql.connection.cursor()

        cur.execute("""
            INSERT INTO log_aktivitas(
                username,
                role,
                aktivitas,
                tanggal
            )
            VALUES(%s,%s,%s,%s)
        """, (
            username,
            role,
            aktivitas,
            waktu_indonesia()
        ))

        mysql.connection.commit()

        cur.close()

    except Exception as e:

        print("Gagal menyimpan log:", e)
# =========================================================
# CONFIG UPLOAD FOTO PROFIL
# =========================================================
UPLOAD_FOLDER = 'static/uploads/profil'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


def allowed_file(filename):

    return (
        '.' in filename
        and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def is_serverless_environment():

    return bool(
        os.getenv('VERCEL')
        or os.getenv('AWS_LAMBDA_FUNCTION_NAME')
        or os.getenv('K_SERVICE')
    )


def simpan_file_profil(file, prefix, id_ref):

    if not file or file.filename == '':

        return False, None, 'Silakan pilih foto terlebih dahulu'

    if not allowed_file(file.filename):

        return False, None, 'Format foto harus PNG, JPG, JPEG, atau WEBP'

    cloud_name = getattr(config, 'CLOUDINARY_CLOUD_NAME', None) or os.getenv('CLOUDINARY_CLOUD_NAME')
    api_key = getattr(config, 'CLOUDINARY_API_KEY', None) or os.getenv('CLOUDINARY_API_KEY')
    api_secret = getattr(config, 'CLOUDINARY_API_SECRET', None) or os.getenv('CLOUDINARY_API_SECRET')

    if not cloud_name or not api_key or not api_secret:

        return False, None, 'Konfigurasi Cloudinary belum lengkap. Isi CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, dan CLOUDINARY_API_SECRET.'

    try:

        upload_result = cloudinary.uploader.upload(
            file,
            folder='sistem_knn_jurusan',
            public_id=f'{prefix}_{id_ref}',
            overwrite=True,
            resource_type='image'
        )

        foto_url = upload_result.get('secure_url')

        if not foto_url:

            return False, None, 'Gagal mendapatkan URL foto dari Cloudinary'

        return True, foto_url, 'Foto profil berhasil diperbarui'

    except Exception as e:

        return False, None, f'Upload foto gagal: {str(e)}'


def get_temp_excel_path(filename='data_alumni.xlsx'):

    if os.getenv('VERCEL') or os.getenv('AWS_LAMBDA_FUNCTION_NAME'):

        return os.path.join('/tmp', filename)

    return filename


def redirect_alumni_page():

    if session.get('id_role') == 2:

        return redirect('/input_alumni')

    return redirect('/admin/input_alumni')



# =========================================================
# HELPER HASIL KNN / WAKTU WIB
# =========================================================
def fetch_hasil_knn_data():

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT
            hasil_knn.id_hasil,
            hasil_knn.nis,
            siswa.nama_siswa,
            siswa.kelas,
            COALESCE(chatbot_terakhir.minat_bakat, 'BELUM MENGISI') AS minat_bakat,
            COALESCE(chatbot_terakhir.kelompok_mapel, 'BELUM MENGISI') AS kelompok_mapel,
            hasil_knn.hasil_jurusan,
            hasil_knn.nilai_k,
            hasil_knn.rata_jarak,
            hasil_knn.confidence,
            DATE_FORMAT(
                hasil_knn.tanggal,
                '%d-%m-%Y %H:%i:%s WIB'
            ) AS tanggal_wib
        FROM hasil_knn

        JOIN siswa
            ON hasil_knn.nis = siswa.nis

        LEFT JOIN (
            SELECT hc.*
            FROM hasil_chatbot hc
            INNER JOIN (
                SELECT nis, MAX(id) AS max_id
                FROM hasil_chatbot
                GROUP BY nis
            ) latest
                ON hc.nis = latest.nis
                AND hc.id = latest.max_id
        ) chatbot_terakhir
            ON hasil_knn.nis = chatbot_terakhir.nis

        ORDER BY hasil_knn.id_hasil DESC
    """)

    hasil_data = cur.fetchall()

    cur.close()

    return hasil_data

def hitung_grafik_jurusan(hasil_data):

    jurusan_count = {}

    for h in hasil_data:

        jurusan = h[6] if h[6] else 'Belum Ada'

        if jurusan in jurusan_count:

            jurusan_count[jurusan] += 1

        else:

            jurusan_count[jurusan] = 1

    labels = list(jurusan_count.keys())
    values = list(jurusan_count.values())

    return labels, values


def buat_file_excel_hasil_rekomendasi(hasil_data, filename='hasil_rekomendasi_knn.xlsx'):

    kolom = [
        'NIS',
        'Nama Siswa',
        'Kelas',
        'Minat Bakat',
        'Kelompok Mapel',
        'Hasil Jurusan',
        'K',
        'Rata Jarak',
        'Confidence (%)',
        'Tanggal WIB'
    ]

    # hasil_data dari fetch_hasil_knn_data membawa id_hasil pada index 0.
    # id_hasil diperlukan untuk tombol hapus di tampilan, tetapi tidak perlu ditampilkan di file Excel.
    data_excel = [row[1:] for row in hasil_data]

    df = pd.DataFrame(
        data_excel,
        columns=kolom
    )

    file_path = get_temp_excel_path(filename)

    df.to_excel(
        file_path,
        index=False
    )

    return file_path


# =========================================================
# DECORATOR LOGIN
# =========================================================
def login_required(roles=None):

    def wrapper(fn):

        @wraps(fn)
        def decorated_view(*args, **kwargs):

            if 'login' not in session:

                return redirect('/')

            if roles:

                if session.get('id_role') not in roles:

                    return redirect('/')

            return fn(*args, **kwargs)

        return decorated_view

    return wrapper

# =========================================================
# LANDING PAGE
# =========================================================
@app.route('/')
def landing_page():

    return render_template(
        'auth/landing_page.html'
    )

# =========================================================
# LOGIN SISWA
# =========================================================
@app.route('/login_siswa')
def login_siswa():

    return render_template(
        'auth/login_siswa.html'
    )

# =========================================================
# LOGIN GURU
# =========================================================
@app.route('/login_guru')
def login_guru():

    return render_template(
        'auth/login_guru.html'
    )

# =========================================================
# PROSES LOGIN SISWA
# =========================================================
@app.route('/proses_login_siswa', methods=['POST'])
def proses_login_siswa():

    username = request.form['username']
    password = request.form['password']

    cur = mysql.connection.cursor()

    cur.execute("""
    SELECT 
        akun.id_akun,
        akun.username,
        akun.password,
        akun.id_role,
        akun.id_ref,
        siswa.foto_profil
    FROM akun

    LEFT JOIN siswa
        ON akun.id_ref = siswa.nis

    WHERE akun.username=%s
    AND akun.id_role=3
""", [username])

    akun = cur.fetchone()

    cur.close()

    if akun:

        password_db = akun[2]

        if check_password_hash(
            password_db,
            password
        ):

            session['login'] = True
            session['id_akun'] = akun[0]
            session['username'] = akun[1]
            session['id_role'] = akun[3]
            session['id_ref'] = akun[4]
            session['foto_profil'] = akun[5]

            simpan_log('Login sebagai siswa')

            return redirect('/dashboard_siswa')

    return render_template(
        'auth/login_siswa.html',
        error='Username atau password siswa salah'
    )

# =========================================================
# PROSES LOGIN GURU
# =========================================================
@app.route('/proses_login_guru', methods=['POST'])
def proses_login_guru():

    username = request.form['username']
    password = request.form['password']

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT
            akun.id_akun,
            akun.username,
            akun.password,
            akun.id_role,
            akun.id_ref,
            guru_bk.foto_profil
        FROM akun

        LEFT JOIN guru_bk
            ON akun.id_role = 2
            AND akun.id_ref = guru_bk.id_guru

        WHERE akun.username=%s
        AND akun.id_role IN (1,2)
    """, [username])

    akun = cur.fetchone()

    cur.close()

    if akun:

        password_db = akun[2]

        if check_password_hash(password_db, password):

            session['login'] = True
            session['id_akun'] = akun[0]
            session['username'] = akun[1]
            session['id_role'] = akun[3]
            session['id_ref'] = akun[4]
            session['foto_profil'] = akun[5]

            # ADMIN
            if akun[3] == 1:

                simpan_log('Login sebagai admin')

                return redirect('/dashboard_admin')

            # GURU BK
            elif akun[3] == 2:

                simpan_log('Login sebagai Guru BK')

                return redirect('/dashboard_guru')

    return render_template(
        'auth/login_guru.html',
        error='Username atau password salah'
    )

# =========================================================
# REGISTER SISWA
# =========================================================
@app.route('/register_siswa', methods=['GET', 'POST'])
def register_siswa():

    if request.method == 'POST':

        nis = request.form['nis']
        nama = request.form['nama']
        kelas = request.form['kelas']
        username = request.form['username']

        password = generate_password_hash(
            request.form['password']
        )

        cur = mysql.connection.cursor()

        # =================================================
        # CEK USERNAME
        # =================================================
        cur.execute("""
            SELECT *
            FROM akun
            WHERE username=%s
        """, [username])

        cek_username = cur.fetchone()

        if cek_username:

            cur.close()

            return render_template(
                'auth/register_siswa.html',
                error='Username sudah digunakan'
            )

        # =================================================
        # CEK NIS
        # =================================================
        cur.execute("""
            SELECT *
            FROM siswa
            WHERE nis=%s
        """, [nis])

        cek_nis = cur.fetchone()

        if cek_nis:

            cur.close()

            return render_template(
                'auth/register_siswa.html',
                error='NIS sudah terdaftar'
            )

        # =================================================
        # INSERT SISWA
        # =================================================
        cur.execute("""
            INSERT INTO siswa(
                nis,
                nama_siswa,
                kelas
            )
            VALUES(%s,%s,%s)
        """, (
            nis,
            nama,
            kelas
        ))

        # =================================================
        # INSERT AKUN SISWA
        # =================================================
        cur.execute("""
            INSERT INTO akun(
                username,
                password,
                id_role,
                id_ref
            )
            VALUES(%s,%s,%s,%s)
        """, (
            username,
            password,
            3,
            nis
        ))

        mysql.connection.commit()

        simpan_log(f'Registrasi akun siswa dengan NIS {nis}')

        cur.close()

        return redirect('/login_siswa')

    return render_template(
        'auth/register_siswa.html'
    )

# =========================================================
# REGISTER GURU
# =========================================================
@app.route('/register_guru', methods=['GET', 'POST'])
def register_guru():

    if request.method == 'POST':

        nip = request.form['nip']
        nama = request.form['nama']
        username = request.form['username']

        password = generate_password_hash(
            request.form['password']
        )

        cur = mysql.connection.cursor()

        # =================================================
        # CEK USERNAME
        # =================================================
        cur.execute("""
            SELECT *
            FROM akun
            WHERE username=%s
        """, [username])

        cek_username = cur.fetchone()

        if cek_username:

            cur.close()

            return render_template(
                'auth/register_guru.html',
                error='Username sudah digunakan'
            )

        # =================================================
        # CEK NIP
        # =================================================
        cur.execute("""
            SELECT *
            FROM guru_bk
            WHERE nip=%s
        """, [nip])

        cek_nip = cur.fetchone()

        if cek_nip:

            cur.close()

            return render_template(
                'auth/register_guru.html',
                error='NIP sudah terdaftar'
            )

        # =================================================
        # INSERT GURU
        # =================================================
        cur.execute("""
            INSERT INTO guru_bk(
                nip,
                nama_guru
            )
            VALUES(%s,%s)
        """, (
            nip,
            nama
        ))

        mysql.connection.commit()

        id_guru = cur.lastrowid

        # =================================================
        # INSERT AKUN GURU
        # =================================================
        cur.execute("""
            INSERT INTO akun(
                username,
                password,
                id_role,
                id_ref
            )
            VALUES(%s,%s,%s,%s)
        """, (
            username,
            password,
            2,
            id_guru
        ))

        mysql.connection.commit()

        simpan_log(f'Registrasi akun Guru BK dengan nama {nama}')

        cur.close()

        return redirect('/login_guru')

    return render_template(
        'auth/register_guru.html'
    )
# =========================================================
# DASHBOARD ADMIN
# =========================================================
@app.route('/dashboard_admin')
@login_required(roles=[1])
def dashboard_admin():

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT COUNT(*)
        FROM siswa
    """)
    total_siswa = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM alumni
    """)
    total_alumni = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM guru_bk
    """)
    total_guru = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM akun
    """)
    total_akun = cur.fetchone()[0]

    cur.close()

    return render_template(
        'admin/dashboard_admin.html',
        total_siswa=total_siswa,
        total_alumni=total_alumni,
        total_guru=total_guru,
        total_akun=total_akun
    )
# =========================================================
# DASHBOARD GURU
# =========================================================
@app.route('/dashboard_guru')
@login_required(roles=[2])
def dashboard_guru():

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT COUNT(*)
        FROM siswa
    """)

    total_siswa = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM alumni
    """)

    total_alumni = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM hasil_knn
    """)

    total_hasil = cur.fetchone()[0]

    cur.close()

    return render_template(
        'guru/dashboard_guru.html',
        total_siswa=total_siswa,
        total_alumni=total_alumni,
        total_hasil=total_hasil
    )

# =========================================================
# DASHBOARD SISWA
# =========================================================
@app.route('/dashboard_siswa')
@login_required(roles=[3])
def dashboard_siswa():

    nis = session['id_ref']

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT *
        FROM siswa
        WHERE nis=%s
    """, [nis])

    siswa = cur.fetchone()

    if not siswa:

        cur.close()

        return "Data siswa tidak ditemukan"

    # =====================================================
    # CEK HASIL CHATBOT SISWA TERAKHIR
    # Jika data ada, dashboard akan menampilkan hasil dan
    # tombol MULAI pada chatbot harus dibatasi dari HTML/JS.
    # =====================================================
    cur.execute("""
        SELECT
            minat_bakat,
            kelompok_mapel,
            detail_mapel,
            lanjut_pt,
            DATE_FORMAT(
                tanggal,
                '%%d-%%m-%%Y %%H:%%i:%%s WIB'
            ) AS tanggal_wib
        FROM hasil_chatbot
        WHERE nis=%s
        ORDER BY id DESC
        LIMIT 1
    """, [nis])

    hasil_chatbot_lama = cur.fetchone()

    # =====================================================
    # CEK HASIL REKOMENDASI KNN TERAKHIR
    # Data ini sama dengan hasil rekomendasi yang tampil
    # pada role Guru/Admin di tabel hasil_knn.
    # =====================================================
    cur.execute("""
        SELECT
            hasil_jurusan,
            nilai_k,
            rata_jarak,
            confidence,
            DATE_FORMAT(
                tanggal,
                '%%d-%%m-%%Y %%H:%%i:%%s WIB'
            ) AS tanggal_wib
        FROM hasil_knn
        WHERE nis=%s
        ORDER BY id_hasil DESC
        LIMIT 1
    """, [nis])

    hasil_knn_lama = cur.fetchone()

    cur.close()

    return render_template(
        'siswa/dashboard_siswa.html',
        siswa=siswa,
        hasil_chatbot_lama=hasil_chatbot_lama,
        hasil_knn_lama=hasil_knn_lama
    )
# =========================================================
# INPUT DATA ALUMNI
# =========================================================
@app.route('/admin/input_alumni', methods=['GET', 'POST'])
@login_required(roles=[1, 2])
def admin_input_alumni():

    if session.get('id_role') == 2 and request.method == 'GET':

        return redirect('/input_alumni')

    # ==================================================
    # PROSES UPLOAD EXCEL
    # ==================================================
    if request.method == 'POST':

        if 'file_excel' not in request.files:

            return "File tidak ditemukan"

        file = request.files['file_excel']

        if file.filename == '':

            return "File belum dipilih"

        if not file.filename.lower().endswith('.xlsx'):

            return "Format file harus .xlsx"

        try:

            df = pd.read_excel(file)

            cur = mysql.connection.cursor()

            for index, row in df.iterrows():

                cur.execute("""

                    REPLACE INTO alumni(

                        id_alumni,
                        nama_alumni,
                        nilai_pancasila,
                        nilai_matematika,
                        nilai_bahasaindo,
                        nilai_bahasaingg,
                        minat_bakat,
                        lanjut_pt,
                        hasil_jurusan,
                        tanggal_input

                    )

                    VALUES(

                        %s,%s,%s,%s,%s,
                        %s,%s,%s,%s,%s

                    )

                """, (

                    row['id_alumni'],
                    row['nama_alumni'],
                    row['nilai_pancasila'],
                    row['nilai_matematika'],
                    row['nilai_bahasaindo'],
                    row['nilai_bahasaingg'],
                    row['minat_bakat'],
                    row['lanjut_pt'],
                    row['hasil_jurusan'],
                    waktu_indonesia()

                ))

            mysql.connection.commit()

            simpan_log(f'Mengupload data alumni sebanyak {len(df)} baris')

            cur.close()

            flash('Data alumni berhasil diupload', 'success')

            return redirect_alumni_page()

        except Exception as e:

            return f"Terjadi error: {str(e)}"

    # ==================================================
    # TAMPILKAN DATA ALUMNI
    # ==================================================

    cur = mysql.connection.cursor()

    cur.execute("""

        SELECT

            id_alumni,
            nama_alumni,
            nilai_pancasila,
            nilai_matematika,
            nilai_bahasaindo,
            nilai_bahasaingg,
            minat_bakat,
            lanjut_pt,
            hasil_jurusan

        FROM alumni

        ORDER BY id_alumni DESC

    """)

    data_alumni = cur.fetchall()

    cur.close()

    return render_template(

        'admin/input_alumni.html',

        data_alumni=data_alumni

    )
@app.route('/download_alumni')
@app.route('/admin/download_alumni')
@login_required(roles=[1, 2])
def download_alumni():

    cur = mysql.connection.cursor()

    cur.execute("""

        SELECT *

        FROM alumni

    """)

    data = cur.fetchall()

    cur.close()

    kolom = [

        'id_alumni',
        'nama_alumni',
        'nilai_pancasila',
        'nilai_matematika',
        'nilai_bahasaindo',
        'nilai_bahasaingg',
        'minat_bakat',
        'lanjut_pt',
        'hasil_jurusan',
        'tanggal_input'

    ]

    df = pd.DataFrame(
        data,
        columns=kolom
    )

    file_excel = get_temp_excel_path('data_alumni.xlsx')

    df.to_excel(
        file_excel,
        index=False
    )

    simpan_log('Mendownload data alumni')

    return send_file(
        file_excel,
        as_attachment=True
    )

# =========================================================
# ADMIN - HAPUS SATU DATA ALUMNI
# =========================================================
@app.route('/hapus_alumni/<int:id_alumni>')
@app.route('/admin/hapus_alumni/<int:id_alumni>')
@login_required(roles=[1, 2])
def admin_hapus_alumni(id_alumni):

    cur = mysql.connection.cursor()

    try:

        cur.execute("""
            DELETE FROM alumni
            WHERE id_alumni=%s
        """, [id_alumni])

        mysql.connection.commit()

        simpan_log(f'Menghapus data alumni dengan ID {id_alumni}')

        flash('Data alumni berhasil dihapus', 'success')

    except Exception as e:

        mysql.connection.rollback()

        flash(f'Gagal menghapus data alumni: {str(e)}', 'danger')

    finally:

        cur.close()

    return redirect_alumni_page()


# =========================================================
# ADMIN - HAPUS DATA ALUMNI MASSAL
# =========================================================
@app.route('/hapus_alumni_massal', methods=['POST'])
@app.route('/admin/hapus_alumni_massal', methods=['POST'])
@login_required(roles=[1, 2])
def admin_hapus_alumni_massal():

    data = request.get_json(silent=True) or {}
    ids = data.get('ids', [])

    if not ids:

        return jsonify({
            'status': 'error',
            'message': 'Tidak ada data alumni yang dipilih'
        }), 400

    try:

        ids = [int(id_alumni) for id_alumni in ids]

    except Exception:

        return jsonify({
            'status': 'error',
            'message': 'Format ID alumni tidak valid'
        }), 400

    cur = mysql.connection.cursor()

    try:

        placeholders = ','.join(['%s'] * len(ids))

        cur.execute(f"""
            DELETE FROM alumni
            WHERE id_alumni IN ({placeholders})
        """, ids)

        mysql.connection.commit()

        simpan_log(f'Menghapus data alumni massal sebanyak {len(ids)} data')

        return jsonify({
            'status': 'success',
            'message': 'Data alumni terpilih berhasil dihapus'
        })

    except Exception as e:

        mysql.connection.rollback()

        return jsonify({
            'status': 'error',
            'message': f'Gagal menghapus data alumni: {str(e)}'
        }), 500

    finally:

        cur.close()


# =========================================================
# INPUT NILAI SISWA
# =========================================================
@app.route('/input_nilai', methods=['GET', 'POST'])
@login_required(roles=[2])
def input_nilai():

    cur = mysql.connection.cursor()

    # ============================================
    # AMBIL DATA SISWA UNTUK DROPDOWN
    # ============================================
    cur.execute("""
        SELECT
            nis,
            nama_siswa
        FROM siswa
        ORDER BY nama_siswa ASC
    """)

    siswa = cur.fetchall()

    # ============================================
    # SIMPAN DATA NILAI SISWA
    # ============================================
    if request.method == 'POST':

        nis = request.form['nis']

        nilai_matematika = request.form['nilai_matematika']
        nilai_indonesia = request.form['nilai_indonesia']
        nilai_inggris = request.form['nilai_inggris']
        nilai_pancasila = request.form['nilai_pancasila']

        # ============================================
        # AMBIL HASIL CHATBOT
        # ============================================
        cur.execute("""
            SELECT
                minat_bakat,
                kelompok_mapel,
                lanjut_pt
            FROM hasil_chatbot
            WHERE nis=%s
            ORDER BY id DESC
            LIMIT 1
        """, [nis])

        hasil_chatbot = cur.fetchone()

        if not hasil_chatbot:

            minat_bakat = 'BELUM MENGISI'
            kelompok_mapel = 'BELUM MENGISI'
            lanjut_pt = 'BELUM MENGISI'

            flash(
                'Siswa belum mengisi chatbot RIASEC. Nilai tetap disimpan, tetapi minat bakat diset BELUM MENGISI.',
                'warning'
            )

        else:

            minat_bakat = hasil_chatbot[0]
            kelompok_mapel = hasil_chatbot[1]
            lanjut_pt = hasil_chatbot[2] if hasil_chatbot[2] else 'BELUM MENGISI'

        # ============================================
        # CEK APAKAH DATA NILAI SISWA SUDAH ADA
        # ============================================
        cur.execute("""
            SELECT id_input
            FROM input_siswa
            WHERE nis=%s
            ORDER BY id_input DESC
            LIMIT 1
        """, [nis])

        cek_nilai = cur.fetchone()

        # ============================================
        # UPDATE JIKA SUDAH ADA
        # ============================================
        if cek_nilai:

            cur.execute("""
                UPDATE input_siswa
                SET
                    nilai_matematika=%s,
                    nilai_indonesia=%s,
                    nilai_inggris=%s,
                    nilai_pancasila=%s,
                    minat_bakat=%s,
                    lanjut_pt=%s,
                    tanggal_input=%s,
                    status_proses=%s
                WHERE id_input=%s
            """, (
                nilai_matematika,
                nilai_indonesia,
                nilai_inggris,
                nilai_pancasila,
                minat_bakat,
                lanjut_pt,
                waktu_indonesia(),
                'belum',
                cek_nilai[0]
            ))

            flash('Data nilai siswa berhasil diperbarui', 'success')

        # ============================================
        # INSERT JIKA BELUM ADA
        # ============================================
        else:

            cur.execute("""
                INSERT INTO input_siswa(
                    nis,
                    nilai_matematika,
                    nilai_indonesia,
                    nilai_inggris,
                    nilai_pancasila,
                    minat_bakat,
                    lanjut_pt,
                    tanggal_input,
                    status_proses
                )
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                nis,
                nilai_matematika,
                nilai_indonesia,
                nilai_inggris,
                nilai_pancasila,
                minat_bakat,
                lanjut_pt,
                waktu_indonesia(),
                'belum'
            ))

            flash('Data nilai siswa berhasil ditambahkan', 'success')

        mysql.connection.commit()

        simpan_log(f'Guru BK menyimpan nilai siswa dengan NIS {nis}')

        cur.close()

        return redirect('/input_nilai')

    # ============================================
    # PENCARIAN DATA NILAI SISWA
    # ============================================
    keyword = request.args.get('keyword', '')

    if keyword:

        search = f"%{keyword}%"

        cur.execute("""
            SELECT
                input_siswa.id_input,
                input_siswa.nis,
                siswa.nama_siswa,
                siswa.kelas,
                input_siswa.nilai_matematika,
                input_siswa.nilai_indonesia,
                input_siswa.nilai_inggris,
                input_siswa.nilai_pancasila,
                input_siswa.minat_bakat,
                input_siswa.lanjut_pt,
                input_siswa.status_proses,
                input_siswa.tanggal_input
            FROM input_siswa

            JOIN siswa
                ON input_siswa.nis = siswa.nis

            WHERE
                input_siswa.nis LIKE %s
                OR siswa.nama_siswa LIKE %s
                OR siswa.kelas LIKE %s
                OR input_siswa.status_proses LIKE %s

            ORDER BY input_siswa.id_input DESC
        """, (
            search,
            search,
            search,
            search
        ))

    else:

        cur.execute("""
            SELECT
                input_siswa.id_input,
                input_siswa.nis,
                siswa.nama_siswa,
                siswa.kelas,
                input_siswa.nilai_matematika,
                input_siswa.nilai_indonesia,
                input_siswa.nilai_inggris,
                input_siswa.nilai_pancasila,
                input_siswa.minat_bakat,
                input_siswa.lanjut_pt,
                input_siswa.status_proses,
                input_siswa.tanggal_input
            FROM input_siswa

            JOIN siswa
                ON input_siswa.nis = siswa.nis

            ORDER BY input_siswa.id_input DESC
        """)

    data_nilai = cur.fetchall()

    cur.close()

    return render_template(
        'guru/input_nilai.html',
        siswa=siswa,
        data_nilai=data_nilai,
        keyword=keyword
    )
# =========================================================
# INPUT DATA ALUMNI
# =========================================================
@app.route('/input_alumni', methods=['GET', 'POST'])
@login_required(roles=[2])
def input_alumni():

    # ==================================================
    # PROSES UPLOAD EXCEL
    # ==================================================
    if request.method == 'POST':

        if 'file_excel' not in request.files:

            return "File tidak ditemukan"

        file = request.files['file_excel']

        if file.filename == '':

            return "File belum dipilih"

        if not file.filename.lower().endswith('.xlsx'):

            return "Format file harus .xlsx"

        try:

            df = pd.read_excel(file)

            cur = mysql.connection.cursor()

            for index, row in df.iterrows():

                cur.execute("""

                    REPLACE INTO alumni(

                        id_alumni,
                        nama_alumni,
                        nilai_pancasila,
                        nilai_matematika,
                        nilai_bahasaindo,
                        nilai_bahasaingg,
                        minat_bakat,
                        lanjut_pt,
                        hasil_jurusan,
                        tanggal_input

                    )

                    VALUES(

                        %s,%s,%s,%s,%s,
                        %s,%s,%s,%s,%s

                    )

                """, (

                    row['id_alumni'],
                    row['nama_alumni'],
                    row['nilai_pancasila'],
                    row['nilai_matematika'],
                    row['nilai_bahasaindo'],
                    row['nilai_bahasaingg'],
                    row['minat_bakat'],
                    row['lanjut_pt'],
                    row['hasil_jurusan'],
                    waktu_indonesia()

                ))

            mysql.connection.commit()

            simpan_log(f'Mengupload data alumni Guru BK sebanyak {len(df)} baris')

            cur.close()

            flash('Data alumni berhasil diupload', 'success')

            return redirect('/input_alumni')

        except Exception as e:

            return f"Terjadi error: {str(e)}"

    # ==================================================
    # TAMPILKAN DATA ALUMNI
    # ==================================================

    cur = mysql.connection.cursor()

    cur.execute("""

        SELECT

            id_alumni,
            nama_alumni,
            nilai_pancasila,
            nilai_matematika,
            nilai_bahasaindo,
            nilai_bahasaingg,
            minat_bakat,
            lanjut_pt,
            hasil_jurusan

        FROM alumni

        ORDER BY id_alumni DESC

    """)

    data_alumni = cur.fetchall()

    cur.close()

    return render_template(

        'guru/input_alumni.html',

        data_alumni=data_alumni

    )

# =========================================================
# HALAMAN PROSES KNN
# =========================================================
@app.route('/proses_knn')
@login_required(roles=[2])
def proses_knn():

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT COUNT(*)
        FROM input_siswa
    """)

    total_siswa = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM alumni
    """)

    total_alumni = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM hasil_knn
    """)

    total_hasil = cur.fetchone()[0]

    cur.close()

    return render_template(
        'guru/proses_knn.html',
        total_siswa=total_siswa,
        total_alumni=total_alumni,
        total_hasil=total_hasil
    )

# =========================================================
# EKSEKUSI PROSES KNN
# =========================================================
@app.route('/proses_semua_knn')
@login_required(roles=[2])
def proses_semua_knn():

    cur = mysql.connection.cursor()

    try:

        nilai_k = 3

        # =====================================================
        # DATA SISWA UJI
        # Fitur KNN:
        # mapel, minat bakat, lanjut PT
        # =====================================================
        cur.execute("""
            SELECT
                id_input,
                nis,
                nilai_pancasila,
                nilai_matematika,
                nilai_indonesia,
                nilai_inggris,
                minat_bakat,
                lanjut_pt
            FROM input_siswa
            WHERE status_proses='belum'
        """)

        semua_siswa = cur.fetchall()

        if len(semua_siswa) == 0:

            flash('Tidak ada data siswa yang siap diproses KNN', 'warning')

            cur.close()

            return redirect('/proses_knn')

        # =====================================================
        # DATA ALUMNI / DATA LATIH
        # =====================================================
        cur.execute("""
            SELECT
                nilai_pancasila,
                nilai_matematika,
                nilai_bahasaindo,
                nilai_bahasaingg,
                minat_bakat,
                lanjut_pt,
                hasil_jurusan
            FROM alumni
            WHERE hasil_jurusan IS NOT NULL
            AND hasil_jurusan != ''
        """)

        alumni = cur.fetchall()

        if len(alumni) == 0:

            flash('Data alumni belum tersedia', 'danger')

            cur.close()

            return redirect('/proses_knn')

        if nilai_k > len(alumni):
            nilai_k = len(alumni)

        data_latih = []
        label_latih = []

        for a in alumni:

            fitur = buat_fitur_knn(
                a[0],
                a[1],
                a[2],
                a[3],
                a[4],
                a[5]
            )

            data_latih.append(fitur)
            label_latih.append(a[6])

        jumlah_diproses = 0

        # =====================================================
        # LOOP PROSES KNN
        # =====================================================
        for siswa_uji in semua_siswa:

            id_input = siswa_uji[0]
            nis = siswa_uji[1]

            fitur_uji = buat_fitur_knn(
                siswa_uji[2],
                siswa_uji[3],
                siswa_uji[4],
                siswa_uji[5],
                siswa_uji[6],
                siswa_uji[7]
            )

            hasil_knn = knn_predict(
                data_latih,
                label_latih,
                fitur_uji,
                k=nilai_k
            )

            nama_jurusan = hasil_knn['hasil']
            confidence = hasil_knn['confidence']
            neighbors = hasil_knn.get('neighbors', [])

            rata_jarak = (
                sum(float(n['distance']) for n in neighbors) / len(neighbors)
            ) if neighbors else 0

            # Hapus hasil lama siswa agar tidak dobel saat proses ulang.
            cur.execute("""
                DELETE FROM hasil_knn
                WHERE nis=%s
            """, [nis])

            cur.execute("""
                INSERT INTO hasil_knn(
                    nis,
                    hasil_jurusan,
                    nilai_k,
                    jumlah_tetangga,
                    rata_jarak,
                    confidence,
                    tanggal
                )
                VALUES(%s,%s,%s,%s,%s,%s,%s)
            """, (
                nis,
                nama_jurusan,
                nilai_k,
                len(neighbors),
                round(rata_jarak, 4),
                confidence,
                waktu_indonesia()
            ))

            cur.execute("""
                UPDATE input_siswa
                SET status_proses='sudah'
                WHERE id_input=%s
            """, [id_input])

            jumlah_diproses += 1

        mysql.connection.commit()

        simpan_log(f'Menjalankan proses KNN guru dengan K={nilai_k} untuk {jumlah_diproses} siswa')

        flash(f'Proses KNN berhasil. {jumlah_diproses} siswa diproses dengan K={nilai_k}', 'success')

    except Exception as e:

        mysql.connection.rollback()

        flash(f'Gagal memproses KNN: {str(e)}', 'danger')

    finally:

        cur.close()

    return redirect('/hasil_rekomendasi')

# =========================================================
# HASIL SISWA
# =========================================================
@app.route('/hasil')
@login_required(roles=[3])
def hasil():

    nis = session['id_ref']

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT *
        FROM hasil_knn
        WHERE nis=%s
        ORDER BY id_hasil DESC
        LIMIT 1
    """, [nis])

    hasil = cur.fetchone()

    cur.close()

    return render_template(
        'siswa/hasil.html',
        hasil=hasil
    )

@app.route('/hasil_rekomendasi')
@login_required(roles=[2])
def hasil_rekomendasi():

    hasil_data = fetch_hasil_knn_data()

    total_hasil = len(hasil_data)
    total_siswa = len(set([h[1] for h in hasil_data]))

    labels, values = hitung_grafik_jurusan(hasil_data)

    return render_template(
        'guru/hasil_rekomendasi.html',
        hasil_data=hasil_data,
        total_hasil=total_hasil,
        total_siswa=total_siswa,
        labels=labels,
        values=values
    )
# =========================================================
# HAPUS HASIL REKOMENDASI - GURU
# =========================================================
@app.route('/hapus_hasil_rekomendasi/<int:id_hasil>')
@login_required(roles=[2])
def hapus_hasil_rekomendasi_guru(id_hasil):

    cur = mysql.connection.cursor()

    try:

        cur.execute("""
            DELETE FROM hasil_knn
            WHERE id_hasil=%s
        """, [id_hasil])

        mysql.connection.commit()

        simpan_log(f'Guru BK menghapus hasil rekomendasi dengan ID {id_hasil}')

        flash('Hasil rekomendasi berhasil dihapus', 'success')

    except Exception as e:

        mysql.connection.rollback()

        flash(f'Gagal menghapus hasil rekomendasi: {str(e)}', 'danger')

    finally:

        cur.close()

    return redirect('/hasil_rekomendasi')


# =========================================================
# HAPUS HASIL REKOMENDASI - ADMIN
# =========================================================
@app.route('/admin/hapus_hasil_rekomendasi/<int:id_hasil>')
@login_required(roles=[1])
def hapus_hasil_rekomendasi_admin(id_hasil):

    cur = mysql.connection.cursor()

    try:

        cur.execute("""
            DELETE FROM hasil_knn
            WHERE id_hasil=%s
        """, [id_hasil])

        mysql.connection.commit()

        simpan_log(f'Admin menghapus hasil rekomendasi dengan ID {id_hasil}')

        flash('Hasil rekomendasi berhasil dihapus', 'success')

    except Exception as e:

        mysql.connection.rollback()

        flash(f'Gagal menghapus hasil rekomendasi: {str(e)}', 'danger')

    finally:

        cur.close()

    return redirect('/admin/hasil_rekomendasi')

# =========================================================
# DOWNLOAD HASIL REKOMENDASI - ADMIN DAN GURU
# =========================================================
@app.route('/download_hasil_rekomendasi')
@app.route('/admin/download_hasil_rekomendasi')
@login_required(roles=[1, 2])
def download_hasil_rekomendasi():

    hasil_data = fetch_hasil_knn_data()

    file_path = buat_file_excel_hasil_rekomendasi(
        hasil_data,
        'hasil_rekomendasi_knn_wib.xlsx'
    )

    simpan_log('Mendownload hasil rekomendasi KNN')

    return send_file(
        file_path,
        as_attachment=True,
        download_name='hasil_rekomendasi_knn_wib.xlsx'
    )


# =========================================================
# CHATBOT RIASEC
# =========================================================

@app.route('/chatbot', methods=['GET', 'POST'])
@login_required(roles=[3])
def chatbot():

    # =====================================================
    # LIST PERTANYAAN
    # =====================================================
    pertanyaan_list = [
        {'text': 'Apakah kamu suka memperbaiki mesin atau alat elektronik?', 'kategori': 'REALISTIC'},
        {'text': 'Apakah kamu suka melakukan penelitian atau eksperimen?', 'kategori': 'INVESTIGATIVE'},
        {'text': 'Apakah kamu suka menggambar atau membuat desain?', 'kategori': 'ARTISTIC'},
        {'text': 'Apakah kamu suka membantu dan mengajar orang lain?', 'kategori': 'SOCIAL'},
        {'text': 'Apakah kamu suka memimpin organisasi atau bisnis?', 'kategori': 'ENTERPRISING'},
        {'text': 'Apakah kamu suka mengatur data dan administrasi?', 'kategori': 'CONVENTIONAL'}
    ]

    nis = session['id_ref']
    cur = mysql.connection.cursor()

    # =====================================================
    # AMBIL DATA SISWA
    # =====================================================
    cur.execute("""
        SELECT
            nis,
            nama_siswa,
            kelas
        FROM siswa
        WHERE nis=%s
    """, [nis])

    siswa = cur.fetchone()

    if not siswa:
        cur.close()
        return "Data siswa tidak ditemukan"

    nama_siswa = siswa[1]
    kelas = siswa[2]

    # =====================================================
    # CEK APAKAH SISWA SUDAH PERNAH MENGISI CHATBOT
    # =====================================================
    cur.execute("""
        SELECT
            minat_bakat,
            kelompok_mapel,
            detail_mapel,
            lanjut_pt,
            DATE_FORMAT(
                tanggal,
                '%%d-%%m-%%Y %%H:%%i:%%s WIB'
            ) AS tanggal_wib
        FROM hasil_chatbot
        WHERE nis=%s
        ORDER BY id DESC
        LIMIT 1
    """, [nis])

    hasil_chatbot_lama = cur.fetchone()

    # =====================================================
    # AMBIL HASIL REKOMENDASI KNN YANG ADA DI GURU/ADMIN
    # =====================================================
    cur.execute("""
        SELECT
            hasil_jurusan,
            nilai_k,
            rata_jarak,
            confidence,
            DATE_FORMAT(
                tanggal,
                '%%d-%%m-%%Y %%H:%%i:%%s WIB'
            ) AS tanggal_wib
        FROM hasil_knn
        WHERE nis=%s
        ORDER BY id_hasil DESC
        LIMIT 1
    """, [nis])

    hasil_knn_lama = cur.fetchone()

    # =====================================================
    # GET /chatbot diarahkan ke dashboard siswa
    # Karena halaman chatbot kamu berada di dashboard_siswa.html
    # =====================================================
    if request.method == 'GET':

        cur.close()

        return redirect('/dashboard_siswa')

    # =====================================================
    # SIMPAN HASIL CHATBOT DARI JAVASCRIPT
    # =====================================================
    if request.method == 'POST':

        # Jika sudah pernah isi, jangan timpa hasil lama.
        # Kirim juga hasil KNN supaya frontend bisa menampilkan
        # rekomendasi yang sama dengan halaman Guru/Admin.
        if hasil_chatbot_lama:
            cur.close()
            return jsonify({
                'status': 'already_exists',
                'message': 'Anda telah mengisi chatbot RIASEC sebelumnya. Hasil rekomendasi sudah tersedia.',
                'hasil_chatbot': {
                    'minat_bakat': hasil_chatbot_lama[0],
                    'kelompok_mapel': hasil_chatbot_lama[1],
                    'detail_mapel': hasil_chatbot_lama[2],
                    'lanjut_pt': hasil_chatbot_lama[3],
                    'tanggal': hasil_chatbot_lama[4]
                },
                'hasil_knn': {
                    'hasil_jurusan': hasil_knn_lama[0] if hasil_knn_lama else None,
                    'nilai_k': hasil_knn_lama[1] if hasil_knn_lama else None,
                    'rata_jarak': hasil_knn_lama[2] if hasil_knn_lama else None,
                    'confidence': hasil_knn_lama[3] if hasil_knn_lama else None,
                    'tanggal': hasil_knn_lama[4] if hasil_knn_lama else None
                }
            })

        data = request.get_json(silent=True) or {}

        rekomendasi = data.get('minat_bakat')
        kelompok_mapel = data.get('kelompok_mapel')
        lanjut_kuliah = data.get('status_kuliah')

        if not rekomendasi or not kelompok_mapel or not lanjut_kuliah:
            cur.close()
            return jsonify({
                'status': 'error',
                'message': 'Data chatbot tidak lengkap'
            }), 400

        detail_mapel_by_kelompok = {
            'Kelompok Mapel 1': """
Matematika Tingkat Lanjut
Ekonomi
PKWu
Biologi
Fisika
""",
            'Kelompok Mapel 2': """
Biologi
Ekonomi
PKWu
Bahasa Inggris Tingkat Lanjut
Informatika
"""
        }

        if kelompok_mapel not in detail_mapel_by_kelompok:

            cur.close()

            return jsonify({
                'status': 'error',
                'message': 'Kelompok mapel tidak valid'
            }), 400

        detail_mapel = detail_mapel_by_kelompok.get(kelompok_mapel, '')

        try:
            cur.execute("""
                INSERT INTO hasil_chatbot(
                    nis,
                    nama_siswa,
                    kelas,
                    minat_bakat,
                    kelompok_mapel,
                    detail_mapel,
                    lanjut_pt,
                    tanggal
                )
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                nis,
                nama_siswa,
                kelas,
                rekomendasi,
                kelompok_mapel,
                detail_mapel,
                lanjut_kuliah,
                waktu_indonesia()
            ))

            mysql.connection.commit()
            simpan_log(f'Menyimpan hasil chatbot RIASEC: {rekomendasi}')

            cur.close()

            return jsonify({
                'status': 'success',
                'message': 'Data chatbot berhasil disimpan'
            })

        except Exception as e:
            mysql.connection.rollback()
            cur.close()

            return jsonify({
                'status': 'error',
                'message': f'Gagal menyimpan data chatbot: {str(e)}'
            }), 500

# =========================================
# PROFIL SISWA
# =========================================
@app.route('/profil_siswa', methods=['GET', 'POST'])
@login_required(roles=[3])
def profil_siswa():

    nis = session['id_ref']

    cur = mysql.connection.cursor()

    # =====================================================
    # UPDATE FOTO PROFIL
    # =====================================================
    if request.method == 'POST':

        if 'foto_profil' not in request.files:

            flash('File foto tidak ditemukan', 'danger')

            cur.close()

            return redirect('/profil_siswa')

        file = request.files['foto_profil']

        berhasil_upload, foto_url, pesan_upload = simpan_file_profil(
            file,
            'profil_siswa',
            nis
        )

        if not berhasil_upload:

            flash(pesan_upload, 'warning')

            cur.close()

            return redirect('/profil_siswa')

        cur.execute("""
            UPDATE siswa
            SET foto_profil=%s
            WHERE nis=%s
        """, (
            foto_url,
            nis
        ))

        mysql.connection.commit()
        session['foto_profil'] = foto_url

        simpan_log('Memperbarui foto profil siswa')

        cur.close()

        flash(pesan_upload, 'success')

        return redirect('/profil_siswa')

    # =====================================================
    # AMBIL DATA SISWA
    # =====================================================
    cur.execute("""

        SELECT

            nis,
            nama_siswa,
            kelas,
            foto_profil

        FROM siswa

        WHERE nis=%s

    """, [nis])

    siswa = cur.fetchone()

    cur.close()

    return render_template(

        'siswa/profil_siswa.html',

        siswa=siswa

    )
# =========================================================
# MANAJEMEN AKUN
# =========================================================
@app.route('/manajemen_akun', methods=['GET', 'POST'])
@app.route('/admin/manajemen_akun', methods=['GET', 'POST'])
@login_required(roles=[1])
def manajemen_akun():

    cur = mysql.connection.cursor()

    # =====================================================
    # TAMBAH AKUN
    # =====================================================
    if request.method == 'POST':

        role = request.form['role']
        username = request.form['username']
        password = generate_password_hash(request.form['password'])

        nama = request.form.get('nama')
        nis = request.form.get('nis')
        kelas = request.form.get('kelas')

        jenis_kelamin = request.form.get('jenis_kelamin')
        no_hp = request.form.get('no_hp')
        email = request.form.get('email')

        # =================================================
        # CEK USERNAME
        # =================================================
        cur.execute("""
            SELECT id_akun
            FROM akun
            WHERE username=%s
        """, [username])

        cek_username = cur.fetchone()

        if cek_username:

            flash('Username sudah digunakan', 'danger')

            cur.close()

            return redirect('/manajemen_akun')

        # =================================================
        # ROLE ADMIN
        # =================================================
        if role == '1':

            cur.execute("""
                INSERT INTO akun(
                    username,
                    password,
                    id_role,
                    id_ref
                )
                VALUES(%s,%s,%s,%s)
            """, (
                username,
                password,
                1,
                None
            ))

        # =================================================
        # ROLE GURU BK
        # =================================================
        elif role == '2':

            if not nama:

                flash('Nama guru wajib diisi', 'danger')

                cur.close()

                return redirect('/manajemen_akun')

            cur.execute("""
                INSERT INTO guru_bk(
                    nama_guru,
                    jenis_kelamin,
                    no_hp,
                    email
                )
                VALUES(%s,%s,%s,%s)
            """, (
                nama,
                jenis_kelamin,
                no_hp,
                email
            ))

            mysql.connection.commit()

            id_guru = cur.lastrowid

            cur.execute("""
                INSERT INTO akun(
                    username,
                    password,
                    id_role,
                    id_ref
                )
                VALUES(%s,%s,%s,%s)
            """, (
                username,
                password,
                2,
                id_guru
            ))

        # =================================================
        # ROLE SISWA
        # =================================================
        elif role == '3':

            if not nis or not nama or not kelas:

                flash('NIS, nama siswa, dan kelas wajib diisi', 'danger')

                cur.close()

                return redirect('/manajemen_akun')

            cur.execute("""
                SELECT nis
                FROM siswa
                WHERE nis=%s
            """, [nis])

            cek_nis = cur.fetchone()

            if cek_nis:

                flash('NIS sudah terdaftar', 'danger')

                cur.close()

                return redirect('/manajemen_akun')

            cur.execute("""
                INSERT INTO siswa(
                    nis,
                    nama_siswa,
                    kelas
                )
                VALUES(%s,%s,%s)
            """, (
                nis,
                nama,
                kelas
            ))

            cur.execute("""
                INSERT INTO akun(
                    username,
                    password,
                    id_role,
                    id_ref
                )
                VALUES(%s,%s,%s,%s)
            """, (
                username,
                password,
                3,
                nis
            ))

        mysql.connection.commit()

        simpan_log(f'Menambahkan akun dengan username {username}')

        cur.close()

        flash('Akun berhasil ditambahkan', 'success')

        return redirect('/manajemen_akun')

    # =====================================================
    # PENCARIAN AKUN
    # =====================================================
    keyword = request.args.get('keyword', '')

    if keyword:

        search = f"%{keyword}%"

        cur.execute("""
            SELECT
                akun.id_akun,
                akun.username,
                akun.id_role,
                akun.id_ref,

                CASE
                    WHEN akun.id_role = 1 THEN 'Admin'
                    WHEN akun.id_role = 2 THEN 'Guru BK'
                    WHEN akun.id_role = 3 THEN 'Siswa'
                    ELSE 'Tidak Diketahui'
                END AS nama_role,

                CASE
                    WHEN akun.id_role = 2 THEN guru_bk.nama_guru
                    WHEN akun.id_role = 3 THEN siswa.nama_siswa
                    ELSE 'Administrator'
                END AS nama_pengguna,

                siswa.kelas,
                guru_bk.jenis_kelamin,
                guru_bk.no_hp,
                guru_bk.email

            FROM akun

            LEFT JOIN siswa
                ON akun.id_role = 3
                AND akun.id_ref = siswa.nis

            LEFT JOIN guru_bk
                ON akun.id_role = 2
                AND akun.id_ref = guru_bk.id_guru

            WHERE
                akun.username LIKE %s
                OR siswa.nama_siswa LIKE %s
                OR siswa.nis LIKE %s
                OR guru_bk.nama_guru LIKE %s
                OR guru_bk.no_hp LIKE %s
                OR guru_bk.email LIKE %s

            ORDER BY akun.id_akun DESC
        """, (
            search,
            search,
            search,
            search,
            search,
            search
        ))

    else:

        cur.execute("""
            SELECT
                akun.id_akun,
                akun.username,
                akun.id_role,
                akun.id_ref,

                CASE
                    WHEN akun.id_role = 1 THEN 'Admin'
                    WHEN akun.id_role = 2 THEN 'Guru BK'
                    WHEN akun.id_role = 3 THEN 'Siswa'
                    ELSE 'Tidak Diketahui'
                END AS nama_role,

                CASE
                    WHEN akun.id_role = 2 THEN guru_bk.nama_guru
                    WHEN akun.id_role = 3 THEN siswa.nama_siswa
                    ELSE 'Administrator'
                END AS nama_pengguna,

                siswa.kelas,
                guru_bk.jenis_kelamin,
                guru_bk.no_hp,
                guru_bk.email

            FROM akun

            LEFT JOIN siswa
                ON akun.id_role = 3
                AND akun.id_ref = siswa.nis

            LEFT JOIN guru_bk
                ON akun.id_role = 2
                AND akun.id_ref = guru_bk.id_guru

            ORDER BY akun.id_akun DESC
        """)

    data_akun = cur.fetchall()

    cur.close()

    return render_template(
        'admin/manajemen_akun.html',
        data_akun=data_akun,
        keyword=keyword
    )
# =========================================================
# HAPUS AKUN
# =========================================================
@app.route('/hapus_akun/<int:id_akun>')
@app.route('/admin/hapus_akun/<int:id_akun>')
@login_required(roles=[1])
def hapus_akun(id_akun):

    cur = mysql.connection.cursor()

    try:

        # =================================================
        # AMBIL DATA AKUN
        # =================================================
        cur.execute("""
            SELECT
                id_akun,
                id_role,
                id_ref
            FROM akun
            WHERE id_akun=%s
        """, [id_akun])

        akun = cur.fetchone()

        if not akun:

            flash('Akun tidak ditemukan', 'danger')

            cur.close()

            return redirect('/manajemen_akun')

        id_role = akun[1]
        id_ref = akun[2]

        # =================================================
        # CEGAH ADMIN HAPUS AKUN SENDIRI
        # =================================================
        if id_akun == session.get('id_akun'):

            flash('Akun yang sedang login tidak boleh dihapus', 'danger')

            cur.close()

            return redirect('/manajemen_akun')

        # =================================================
        # JIKA AKUN SISWA
        # =================================================
        if id_role == 3:

            nis = id_ref

            # Hapus akun login siswa dulu
            cur.execute("""
                DELETE FROM akun
                WHERE id_akun=%s
            """, [id_akun])

            # Hapus data hasil chatbot siswa
            cur.execute("""
                DELETE FROM hasil_chatbot
                WHERE nis=%s
            """, [nis])

            # Hapus data nilai/input siswa
            cur.execute("""
                DELETE FROM input_siswa
                WHERE nis=%s
            """, [nis])

            # Hapus data hasil KNN siswa
            cur.execute("""
                DELETE FROM hasil_knn
                WHERE nis=%s
            """, [nis])

            # Baru hapus data utama siswa
            cur.execute("""
                DELETE FROM siswa
                WHERE nis=%s
            """, [nis])

        # =================================================
        # JIKA AKUN GURU BK
        # =================================================
        elif id_role == 2:

            id_guru = id_ref

            cur.execute("""
                DELETE FROM akun
                WHERE id_akun=%s
            """, [id_akun])

            cur.execute("""
                DELETE FROM guru_bk
                WHERE id_guru=%s
            """, [id_guru])

        # =================================================
        # JIKA AKUN ADMIN
        # =================================================
        elif id_role == 1:

            cur.execute("""
                DELETE FROM akun
                WHERE id_akun=%s
            """, [id_akun])

        mysql.connection.commit()

        simpan_log(f'Menghapus akun dengan ID {id_akun}')

        flash('Akun berhasil dihapus', 'success')

    except Exception as e:

        mysql.connection.rollback()

        flash(f'Gagal menghapus akun: {str(e)}', 'danger')

    finally:

        cur.close()

    return redirect('/manajemen_akun')
# =========================================================
# ADMIN - NILAI SISWA
# =========================================================
@app.route('/admin/nilai_siswa', methods=['GET', 'POST'])
@login_required(roles=[1])
def admin_nilai_siswa():

    cur = mysql.connection.cursor()

    # =====================================================
    # AMBIL DATA SISWA UNTUK DROPDOWN
    # =====================================================
    cur.execute("""
        SELECT
            nis,
            nama_siswa,
            kelas
        FROM siswa
        ORDER BY nama_siswa ASC
    """)

    siswa_list = cur.fetchall()

    # =====================================================
    # TAMBAH / UPDATE NILAI SISWA
    # =====================================================
    if request.method == 'POST':

        nis = request.form['nis']

        nilai_matematika = request.form['nilai_matematika']
        nilai_indonesia = request.form['nilai_indonesia']
        nilai_inggris = request.form['nilai_inggris']
        nilai_pancasila = request.form['nilai_pancasila']

        # =================================================
        # AMBIL HASIL CHATBOT
        # =================================================
        cur.execute("""
            SELECT
                minat_bakat,
                kelompok_mapel,
                lanjut_pt
            FROM hasil_chatbot
            WHERE nis=%s
            ORDER BY id DESC
            LIMIT 1
        """, [nis])

        hasil_chatbot = cur.fetchone()

        if not hasil_chatbot:

            minat_bakat = 'BELUM MENGISI'
            kelompok_mapel = 'BELUM MENGISI'
            lanjut_pt = 'BELUM MENGISI'

            flash(
                'Siswa belum mengisi chatbot RIASEC. Nilai tetap disimpan, tetapi minat bakat diset BELUM MENGISI.',
                'warning'
            )

        else:

            minat_bakat = hasil_chatbot[0]
            kelompok_mapel = hasil_chatbot[1]
            lanjut_pt = hasil_chatbot[2] if hasil_chatbot[2] else 'BELUM MENGISI'

        # =================================================
        # CEK APAKAH NILAI SISWA SUDAH ADA
        # =================================================
        cur.execute("""
            SELECT id_input
            FROM input_siswa
            WHERE nis=%s
            ORDER BY id_input DESC
            LIMIT 1
        """, [nis])

        cek_nilai = cur.fetchone()

        # =================================================
        # UPDATE JIKA SUDAH ADA
        # =================================================
        if cek_nilai:

            cur.execute("""
                UPDATE input_siswa
                SET
                    nilai_matematika=%s,
                    nilai_indonesia=%s,
                    nilai_inggris=%s,
                    nilai_pancasila=%s,
                    minat_bakat=%s,
                    lanjut_pt=%s,
                    tanggal_input=%s,
                    status_proses=%s
                WHERE id_input=%s
            """, (
                nilai_matematika,
                nilai_indonesia,
                nilai_inggris,
                nilai_pancasila,
                minat_bakat,
                lanjut_pt,
                waktu_indonesia(),
                'belum',
                cek_nilai[0]
            ))

            flash('Nilai siswa berhasil diperbarui', 'success')

        # =================================================
        # INSERT JIKA BELUM ADA
        # =================================================
        else:

            cur.execute("""
                INSERT INTO input_siswa(
                    nis,
                    nilai_matematika,
                    nilai_indonesia,
                    nilai_inggris,
                    nilai_pancasila,
                    minat_bakat,
                    lanjut_pt,
                    tanggal_input,
                    status_proses
                )
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                nis,
                nilai_matematika,
                nilai_indonesia,
                nilai_inggris,
                nilai_pancasila,
                minat_bakat,
                lanjut_pt,
                waktu_indonesia(),
                'belum'
            ))

            flash('Nilai siswa berhasil ditambahkan', 'success')

        mysql.connection.commit()

        simpan_log(f'Menambahkan/memperbarui nilai siswa dengan NIS {nis}')

        cur.close()

        return redirect('/admin/nilai_siswa')

    # =====================================================
    # PENCARIAN NILAI SISWA
    # =====================================================
    keyword = request.args.get('keyword', '')

    if keyword:

        search = f"%{keyword}%"

        cur.execute("""
            SELECT
                input_siswa.id_input,
                input_siswa.nis,
                siswa.nama_siswa,
                siswa.kelas,
                input_siswa.nilai_matematika,
                input_siswa.nilai_indonesia,
                input_siswa.nilai_inggris,
                input_siswa.nilai_pancasila,
                input_siswa.minat_bakat,
                input_siswa.lanjut_pt,
                input_siswa.status_proses,
                input_siswa.tanggal_input
            FROM input_siswa

            JOIN siswa
                ON input_siswa.nis = siswa.nis

            WHERE
                input_siswa.nis LIKE %s
                OR siswa.nama_siswa LIKE %s
                OR siswa.kelas LIKE %s
                OR input_siswa.minat_bakat LIKE %s
                OR input_siswa.lanjut_pt LIKE %s
                OR input_siswa.status_proses LIKE %s

            ORDER BY input_siswa.id_input DESC
        """, (
            search,
            search,
            search,
            search,
            search,
            search
        ))

    else:

        cur.execute("""
            SELECT
                input_siswa.id_input,
                input_siswa.nis,
                siswa.nama_siswa,
                siswa.kelas,
                input_siswa.nilai_matematika,
                input_siswa.nilai_indonesia,
                input_siswa.nilai_inggris,
                input_siswa.nilai_pancasila,
                input_siswa.minat_bakat,
                input_siswa.lanjut_pt,
                input_siswa.status_proses,
                input_siswa.tanggal_input
            FROM input_siswa

            JOIN siswa
                ON input_siswa.nis = siswa.nis

            ORDER BY input_siswa.id_input DESC
        """)

    data_nilai = cur.fetchall()

    cur.close()

    return render_template(
        'admin/nilai_siswa.html',
        siswa_list=siswa_list,
        data_nilai=data_nilai,
        keyword=keyword
    )


# =========================================================
# ADMIN - HAPUS NILAI SISWA
# =========================================================
@app.route('/admin/hapus_nilai_siswa/<int:id_input>')
@login_required(roles=[1])
def admin_hapus_nilai_siswa(id_input):

    cur = mysql.connection.cursor()

    cur.execute("""
        DELETE FROM input_siswa
        WHERE id_input=%s
    """, [id_input])

    mysql.connection.commit()

    simpan_log(f'Menghapus data nilai siswa dengan id_input {id_input}')

    cur.close()

    flash('Data nilai siswa berhasil dihapus', 'success')

    return redirect('/admin/nilai_siswa')
# =========================================================
# ADMIN - HASIL REKOMENDASI
# =========================================================
@app.route('/admin/hasil_rekomendasi')
@login_required(roles=[1])
def admin_hasil_rekomendasi():

    hasil_data = fetch_hasil_knn_data()

    total_hasil = len(hasil_data)
    total_siswa = len(set([h[1] for h in hasil_data]))

    labels, values = hitung_grafik_jurusan(hasil_data)

    return render_template(
        'admin/hasil_rekomendasi.html',
        hasil_data=hasil_data,
        total_hasil=total_hasil,
        total_siswa=total_siswa,
        labels=labels,
        values=values
    )

# =========================================================
# ADMIN - EVALUASI SISTEM
# =========================================================
@app.route('/admin/evaluasi_sistem')
@login_required(roles=[1])
def admin_evaluasi_sistem():

    cur = mysql.connection.cursor()

    # =====================================================
    # TOTAL DATA HASIL KNN
    # =====================================================
    cur.execute("""
        SELECT COUNT(*)
        FROM hasil_knn
    """)

    total_hasil = cur.fetchone()[0]

    # =====================================================
    # TOTAL SISWA YANG SUDAH DIREKOMENDASIKAN
    # =====================================================
    cur.execute("""
        SELECT COUNT(DISTINCT nis)
        FROM hasil_knn
    """)

    total_siswa = cur.fetchone()[0]

    # =====================================================
    # RATA-RATA CONFIDENCE DAN RATA-RATA JARAK
    # =====================================================
    cur.execute("""
        SELECT
            COALESCE(AVG(confidence), 0),
            COALESCE(AVG(rata_jarak), 0)
        FROM hasil_knn
    """)

    evaluasi = cur.fetchone()

    rata_confidence = round(float(evaluasi[0]), 2)
    rata_jarak = round(float(evaluasi[1]), 4)

    # =====================================================
    # JUMLAH BERDASARKAN TINGKAT CONFIDENCE
    # =====================================================
    cur.execute("""
        SELECT
            SUM(CASE WHEN confidence >= 70 THEN 1 ELSE 0 END) AS tinggi,
            SUM(CASE WHEN confidence >= 40 AND confidence < 70 THEN 1 ELSE 0 END) AS sedang,
            SUM(CASE WHEN confidence < 40 THEN 1 ELSE 0 END) AS rendah
        FROM hasil_knn
    """)

    confidence_data = cur.fetchone()

    confidence_tinggi = confidence_data[0] if confidence_data[0] else 0
    confidence_sedang = confidence_data[1] if confidence_data[1] else 0
    confidence_rendah = confidence_data[2] if confidence_data[2] else 0

    # =====================================================
    # DISTRIBUSI HASIL JURUSAN
    # =====================================================
    cur.execute("""
        SELECT
            hasil_jurusan,
            COUNT(*) AS jumlah
        FROM hasil_knn
        GROUP BY hasil_jurusan
        ORDER BY jumlah DESC
    """)

    jurusan_data = cur.fetchall()

    labels_jurusan = []
    values_jurusan = []

    for row in jurusan_data:

        labels_jurusan.append(row[0])
        values_jurusan.append(row[1])

    # =====================================================
    # DATA DETAIL EVALUASI HASIL KNN SISWA
    # =====================================================
    cur.execute("""
        SELECT
            hasil_knn.nis,
            siswa.nama_siswa,
            siswa.kelas,
            hasil_knn.hasil_jurusan,
            hasil_knn.nilai_k,
            hasil_knn.jumlah_tetangga,
            hasil_knn.rata_jarak,
            hasil_knn.confidence,
            DATE_FORMAT(
                hasil_knn.tanggal,
                '%d-%m-%Y %H:%i:%s WIB'
            ) AS tanggal_wib
        FROM hasil_knn

        JOIN siswa
            ON hasil_knn.nis = siswa.nis

        ORDER BY hasil_knn.id_hasil DESC
    """)

    data_evaluasi = cur.fetchall()

    # =====================================================
    # EVALUASI AKURASI SISTEM MENGGUNAKAN DATA ALUMNI
    # Metode: Leave-One-Out
    # Satu data alumni diuji, data alumni lainnya jadi data latih
    # =====================================================
    nilai_k_evaluasi = 3
    jumlah_data_evaluasi = 0
    metrik = {
        'accuracy': 0,
        'precision': 0,
        'recall': 0,
        'f1_score': 0
    }

    try:

        cur.execute("""
            SELECT
                nilai_pancasila,
                nilai_matematika,
                nilai_bahasaindo,
                nilai_bahasaingg,
                minat_bakat,
                lanjut_pt,
                hasil_jurusan
            FROM alumni
            WHERE hasil_jurusan IS NOT NULL
            AND hasil_jurusan != ''
        """)

        data_alumni = cur.fetchall()

        y_true = []
        y_pred = []

        jumlah_data_evaluasi = len(data_alumni)

        if jumlah_data_evaluasi > 1:

            for i in range(jumlah_data_evaluasi):

                fitur_uji = buat_fitur_knn(
                    data_alumni[i][0],
                    data_alumni[i][1],
                    data_alumni[i][2],
                    data_alumni[i][3],
                    data_alumni[i][4],
                    data_alumni[i][5]
                )

                label_asli = data_alumni[i][6]

                data_latih = []
                label_latih = []

                for j in range(jumlah_data_evaluasi):

                    if i != j:

                        fitur_latih = buat_fitur_knn(
                            data_alumni[j][0],
                            data_alumni[j][1],
                            data_alumni[j][2],
                            data_alumni[j][3],
                            data_alumni[j][4],
                            data_alumni[j][5]
                        )

                        data_latih.append(fitur_latih)
                        label_latih.append(data_alumni[j][6])

                k_dipakai = nilai_k_evaluasi

                if k_dipakai > len(data_latih):

                    k_dipakai = len(data_latih)

                hasil_prediksi = knn_predict(
                    data_latih,
                    label_latih,
                    fitur_uji,
                    k=k_dipakai
                )

                y_true.append(label_asli)
                y_pred.append(hasil_prediksi['hasil'])

            metrik = hitung_metrik_evaluasi(y_true, y_pred)

    except Exception as e:

        flash(
            f'Gagal menghitung metrik evaluasi KNN: {str(e)}',
            'warning'
        )

    cur.close()

    return render_template(
        'admin/evaluasi_sistem.html',

        total_hasil=total_hasil,
        total_siswa=total_siswa,
        rata_confidence=rata_confidence,
        rata_jarak=rata_jarak,

        confidence_tinggi=confidence_tinggi,
        confidence_sedang=confidence_sedang,
        confidence_rendah=confidence_rendah,

        labels_jurusan=labels_jurusan,
        values_jurusan=values_jurusan,
        data_evaluasi=data_evaluasi,

        accuracy=metrik['accuracy'],
        precision=metrik['precision'],
        recall=metrik['recall'],
        f1_score=metrik['f1_score'],
        jumlah_data_evaluasi=jumlah_data_evaluasi,
        nilai_k_evaluasi=nilai_k_evaluasi
    )
# =========================================================
# ADMIN - HASIL CHATBOT
# =========================================================
@app.route('/admin/hasil_chatbot')
@login_required(roles=[1])
def admin_hasil_chatbot():

    cur = mysql.connection.cursor()

    keyword = request.args.get('keyword', '')

    if keyword:

        search = f"%{keyword}%"

        cur.execute("""
            SELECT
                id,
                nis,
                nama_siswa,
                kelas,
                minat_bakat,
                kelompok_mapel,
                detail_mapel,
                lanjut_pt,
                tanggal
            FROM hasil_chatbot
            WHERE
                nis LIKE %s
                OR nama_siswa LIKE %s
                OR kelas LIKE %s
                OR minat_bakat LIKE %s
                OR kelompok_mapel LIKE %s
                OR lanjut_pt LIKE %s
            ORDER BY id DESC
        """, (
            search,
            search,
            search,
            search,
            search,
            search
        ))

    else:

        cur.execute("""
            SELECT
                id,
                nis,
                nama_siswa,
                kelas,
                minat_bakat,
                kelompok_mapel,
                detail_mapel,
                lanjut_pt,
                tanggal
            FROM hasil_chatbot
            ORDER BY id DESC
        """)

    data_chatbot = cur.fetchall()

    total_chatbot = len(data_chatbot)

    cur.close()

    return render_template(
        'admin/hasil_chatbot.html',
        data_chatbot=data_chatbot,
        total_chatbot=total_chatbot,
        keyword=keyword
    )


# =========================================================
# ADMIN - HAPUS HASIL CHATBOT
# =========================================================
@app.route('/admin/hapus_hasil_chatbot/<int:id_chatbot>')
@login_required(roles=[1])
def admin_hapus_hasil_chatbot(id_chatbot):

    cur = mysql.connection.cursor()

    cur.execute("""
        DELETE FROM hasil_chatbot
        WHERE id=%s
    """, [id_chatbot])

    mysql.connection.commit()

    simpan_log(f'Menghapus hasil chatbot dengan ID {id_chatbot}')

    cur.close()

    flash('Data hasil chatbot berhasil dihapus', 'success')

    return redirect('/admin/hasil_chatbot')
# =========================================================
# ADMIN - DATA SISWA
# =========================================================
@app.route('/admin/data_siswa', methods=['GET', 'POST'])
@login_required(roles=[1])
def admin_data_siswa():

    cur = mysql.connection.cursor()

    # =====================================================
    # TAMBAH DATA SISWA
    # =====================================================
    if request.method == 'POST':

        nis = request.form['nis']
        nama_siswa = request.form['nama_siswa']
        kelas = request.form['kelas']

        # =================================================
        # CEK NIS
        # =================================================
        cur.execute("""
            SELECT nis
            FROM siswa
            WHERE nis=%s
        """, [nis])

        cek_siswa = cur.fetchone()

        if cek_siswa:

            flash('NIS sudah terdaftar', 'danger')

            cur.close()

            return redirect('/admin/data_siswa')

        cur.execute("""
            INSERT INTO siswa(
                nis,
                nama_siswa,
                kelas
            )
            VALUES(%s,%s,%s)
        """, (
            nis,
            nama_siswa,
            kelas
        ))

        mysql.connection.commit()

        simpan_log(f'Menambahkan data siswa dengan NIS {nis}')

        cur.close()

        flash('Data siswa berhasil ditambahkan', 'success')

        return redirect('/admin/data_siswa')

    # =====================================================
    # PENCARIAN DATA SISWA
    # =====================================================
    keyword = request.args.get('keyword', '')

    if keyword:

        search = f"%{keyword}%"

        cur.execute("""
            SELECT
                nis,
                nama_siswa,
                kelas,
                foto_profil
            FROM siswa
            WHERE
                nis LIKE %s
                OR nama_siswa LIKE %s
                OR kelas LIKE %s
            ORDER BY nama_siswa ASC
        """, (
            search,
            search,
            search
        ))

    else:

        cur.execute("""
            SELECT
                nis,
                nama_siswa,
                kelas,
                foto_profil
            FROM siswa
            ORDER BY nama_siswa ASC
        """)

    data_siswa = cur.fetchall()

    total_siswa = len(data_siswa)

    cur.close()

    return render_template(
        'admin/data_siswa.html',
        data_siswa=data_siswa,
        total_siswa=total_siswa,
        keyword=keyword
    )


# =========================================================
# ADMIN - EDIT DATA SISWA
# =========================================================
@app.route('/admin/edit_siswa/<nis>', methods=['POST'])
@login_required(roles=[1])
def admin_edit_siswa(nis):

    cur = mysql.connection.cursor()

    nama_siswa = request.form['nama_siswa']
    kelas = request.form['kelas']

    cur.execute("""
        UPDATE siswa
        SET
            nama_siswa=%s,
            kelas=%s
        WHERE nis=%s
    """, (
        nama_siswa,
        kelas,
        nis
    ))

    # Update nama dan kelas di hasil_chatbot juga biar sinkron
    cur.execute("""
        UPDATE hasil_chatbot
        SET
            nama_siswa=%s,
            kelas=%s
        WHERE nis=%s
    """, (
        nama_siswa,
        kelas,
        nis
    ))

    mysql.connection.commit()

    simpan_log(f'Memperbarui data siswa dengan NIS {nis}')

    cur.close()

    flash('Data siswa berhasil diperbarui', 'success')

    return redirect('/admin/data_siswa')


# =========================================================
# ADMIN - HAPUS DATA SISWA
# =========================================================
@app.route('/admin/hapus_siswa/<nis>')
@login_required(roles=[1])
def admin_hapus_siswa(nis):

    cur = mysql.connection.cursor()

    try:

        # =================================================
        # HAPUS AKUN SISWA
        # =================================================
        cur.execute("""
            DELETE FROM akun
            WHERE id_role=3
            AND id_ref=%s
        """, [nis])

        # =================================================
        # HAPUS DATA TURUNAN SISWA
        # =================================================
        cur.execute("""
            DELETE FROM hasil_chatbot
            WHERE nis=%s
        """, [nis])

        cur.execute("""
            DELETE FROM input_siswa
            WHERE nis=%s
        """, [nis])

        cur.execute("""
            DELETE FROM hasil_knn
            WHERE nis=%s
        """, [nis])

        # =================================================
        # HAPUS DATA UTAMA SISWA
        # =================================================
        cur.execute("""
            DELETE FROM siswa
            WHERE nis=%s
        """, [nis])

        mysql.connection.commit()

        simpan_log(f'Menghapus data siswa dengan NIS {nis}')

        flash('Data siswa berhasil dihapus', 'success')

    except Exception as e:

        mysql.connection.rollback()

        flash(f'Gagal menghapus siswa: {str(e)}', 'danger')

    finally:

        cur.close()

    return redirect('/admin/data_siswa')
# =========================================================
# ADMIN - LOG AKTIVITAS
# =========================================================
@app.route('/admin/log_aktivitas')
@login_required(roles=[1])
def admin_log_aktivitas():

    simpan_log('Membuka halaman log aktivitas')

    cur = mysql.connection.cursor()

    keyword = request.args.get('keyword', '')

    if keyword:

        search = f"%{keyword}%"

        cur.execute("""
            SELECT
                id_log,
                username,
                role,
                aktivitas,
                tanggal
            FROM log_aktivitas
            WHERE
                username LIKE %s
                OR role LIKE %s
                OR aktivitas LIKE %s
            ORDER BY id_log DESC
        """, (
            search,
            search,
            search
        ))

    else:

        cur.execute("""
            SELECT
                id_log,
                username,
                role,
                aktivitas,
                tanggal
            FROM log_aktivitas
            ORDER BY id_log DESC
        """)

    data_log = cur.fetchall()

    total_log = len(data_log)

    cur.close()

    return render_template(
        'admin/log_aktivitas.html',
        data_log=data_log,
        total_log=total_log,
        keyword=keyword
    )

# =========================================================
# ADMIN - HAPUS SEMUA LOG AKTIVITAS
# =========================================================
@app.route('/admin/hapus_semua_log')
@login_required(roles=[1])
def admin_hapus_semua_log():

    cur = mysql.connection.cursor()

    cur.execute("""
        DELETE FROM log_aktivitas
    """)

    mysql.connection.commit()

    cur.close()

    simpan_log('Menghapus semua log aktivitas')

    flash('Semua log aktivitas berhasil dihapus', 'success')

    return redirect('/admin/log_aktivitas')
# =========================================================
# ADMIN - HALAMAN PROSES KNN
# =========================================================
@app.route('/admin/proses_knn')
@login_required(roles=[1])
def admin_proses_knn():

    cur = mysql.connection.cursor()

    # =====================================================
    # TOTAL SISWA YANG SIAP DIPROSES
    # Syarat:
    # 1. Sudah punya nilai di input_siswa
    # 2. Sudah punya hasil chatbot
    # 3. Status proses masih belum
    # =====================================================
    cur.execute("""
        SELECT COUNT(*)
        FROM input_siswa

        JOIN siswa
            ON input_siswa.nis = siswa.nis

        WHERE input_siswa.status_proses='belum'
    """)

    total_siswa = cur.fetchone()[0]

    # =====================================================
    # TOTAL DATA LATIH ALUMNI
    # =====================================================
    cur.execute("""
        SELECT COUNT(*)
        FROM alumni
    """)

    total_alumni = cur.fetchone()[0]

    # =====================================================
    # TOTAL HASIL KNN
    # =====================================================
    cur.execute("""
        SELECT COUNT(*)
        FROM hasil_knn
    """)

    total_hasil = cur.fetchone()[0]

    # =====================================================
    # PREVIEW DATA SISWA YANG SIAP DIPROSES
    # =====================================================
    cur.execute("""
        SELECT
            input_siswa.nis,
            siswa.nama_siswa,
            siswa.kelas,
            COALESCE(input_siswa.minat_bakat, hasil_chatbot.minat_bakat, 'BELUM MENGISI') AS minat_bakat,
            COALESCE(input_siswa.lanjut_pt, hasil_chatbot.lanjut_pt, 'BELUM MENGISI') AS lanjut_pt,
            input_siswa.nilai_pancasila,
            input_siswa.nilai_matematika,
            input_siswa.nilai_indonesia,
            input_siswa.nilai_inggris,
            input_siswa.status_proses
        FROM input_siswa

        JOIN siswa
            ON input_siswa.nis = siswa.nis

        LEFT JOIN (
            SELECT hc.*
            FROM hasil_chatbot hc
            INNER JOIN (
                SELECT nis, MAX(id) AS max_id
                FROM hasil_chatbot
                GROUP BY nis
            ) latest
                ON hc.nis = latest.nis
                AND hc.id = latest.max_id
        ) hasil_chatbot
            ON input_siswa.nis = hasil_chatbot.nis

        WHERE input_siswa.status_proses='belum'

        ORDER BY input_siswa.id_input DESC
    """)

    data_siap = cur.fetchall()

    cur.close()

    return render_template(
        'admin/proses_knn.html',
        total_siswa=total_siswa,
        total_alumni=total_alumni,
        total_hasil=total_hasil,
        data_siap=data_siap
    )


# =========================================================
# ADMIN - EKSEKUSI PROSES KNN
# =========================================================
@app.route('/admin/proses_semua_knn', methods=['POST'])
@login_required(roles=[1])
def admin_proses_semua_knn():

    cur = mysql.connection.cursor()

    try:

        # =================================================
        # AMBIL NILAI K DARI FORM
        # =================================================
        nilai_k = request.form.get('nilai_k', 3)

        try:

            nilai_k = int(nilai_k)

        except:

            nilai_k = 3

        if nilai_k < 1:

            nilai_k = 1

        # =================================================
        # DATA SISWA UJI
        # Gabungan:
        # input_siswa + siswa + hasil_chatbot
        # =================================================
        cur.execute("""
            SELECT
                input_siswa.id_input,
                input_siswa.nis,
                siswa.nama_siswa,
                siswa.kelas,
                COALESCE(input_siswa.minat_bakat, hasil_chatbot.minat_bakat, 'BELUM MENGISI') AS minat_bakat,
                COALESCE(input_siswa.lanjut_pt, hasil_chatbot.lanjut_pt, 'BELUM MENGISI') AS lanjut_pt,

                input_siswa.nilai_pancasila,
                input_siswa.nilai_matematika,
                input_siswa.nilai_indonesia,
                input_siswa.nilai_inggris

            FROM input_siswa

            JOIN siswa
                ON input_siswa.nis = siswa.nis

            LEFT JOIN (
                SELECT hc.*
                FROM hasil_chatbot hc
                INNER JOIN (
                    SELECT nis, MAX(id) AS max_id
                    FROM hasil_chatbot
                    GROUP BY nis
                ) latest
                    ON hc.nis = latest.nis
                    AND hc.id = latest.max_id
            ) hasil_chatbot
                ON input_siswa.nis = hasil_chatbot.nis

            WHERE input_siswa.status_proses='belum'
        """)

        semua_siswa = cur.fetchall()

        if len(semua_siswa) == 0:

            flash('Tidak ada data siswa yang siap diproses KNN', 'danger')

            cur.close()

            return redirect('/admin/proses_knn')

        # =================================================
        # DATA LATIH ALUMNI
        # =================================================
        cur.execute("""
            SELECT
                id_alumni,
                nama_alumni,
                nilai_pancasila,
                nilai_matematika,
                nilai_bahasaindo,
                nilai_bahasaingg,
                minat_bakat,
                lanjut_pt,
                hasil_jurusan
            FROM alumni
            WHERE hasil_jurusan IS NOT NULL
            AND hasil_jurusan != ''
        """)

        alumni = cur.fetchall()

        if len(alumni) == 0:

            flash('Data latih alumni belum tersedia', 'danger')

            cur.close()

            return redirect('/admin/proses_knn')

        # =================================================
        # VALIDASI K
        # K tidak boleh lebih besar dari jumlah data alumni
        # =================================================
        if nilai_k > len(alumni):

            nilai_k = len(alumni)

            flash(
                f'Nilai K melebihi jumlah data alumni. Sistem menggunakan K={nilai_k}',
                'warning'
            )

        # =================================================
        # SUSUN DATA LATIH
        # Fitur KNN:
        # mapel, minat bakat, lanjut PT
        # =================================================
        data_latih = []
        label_latih = []

        for a in alumni:

            fitur_latih = buat_fitur_knn(
                a[2],
                a[3],
                a[4],
                a[5],
                a[6],
                a[7]
            )

            data_latih.append(fitur_latih)

            label_latih.append(a[8])

        jumlah_diproses = 0

        # =================================================
        # LOOP PROSES KNN
        # =================================================
        for siswa_uji in semua_siswa:

            id_input = siswa_uji[0]
            nis = siswa_uji[1]

            fitur_uji = buat_fitur_knn(
                siswa_uji[6],
                siswa_uji[7],
                siswa_uji[8],
                siswa_uji[9],
                siswa_uji[4],
                siswa_uji[5]
            )

            hasil_knn = knn_predict(
                data_latih,
                label_latih,
                fitur_uji,
                k=nilai_k
            )

            nama_jurusan = hasil_knn['hasil']
            confidence = hasil_knn['confidence']
            neighbors = hasil_knn['neighbors']

            rata_jarak = (
                sum(float(n['distance']) for n in neighbors)
                / len(neighbors)
            ) if neighbors else 0

            # =================================================
            # HAPUS HASIL LAMA SISWA AGAR TIDAK DOBEL
            # =================================================
            cur.execute("""
                DELETE FROM hasil_knn
                WHERE nis=%s
            """, [nis])

            # =================================================
            # SIMPAN HASIL KNN
            # =================================================
            cur.execute("""
                INSERT INTO hasil_knn(
                    nis,
                    hasil_jurusan,
                    nilai_k,
                    jumlah_tetangga,
                    rata_jarak,
                    confidence,
                    tanggal
                )
                VALUES(%s,%s,%s,%s,%s,%s,%s)
            """, (
                nis,
                nama_jurusan,
                nilai_k,
                len(neighbors),
                round(rata_jarak, 4),
                confidence,
                waktu_indonesia()
            ))

            # =================================================
            # UPDATE STATUS INPUT SISWA
            # Pakai id_input supaya aman walau NIS sama pernah dobel
            # =================================================
            cur.execute("""
                UPDATE input_siswa
                SET status_proses='sudah'
                WHERE id_input=%s
            """, [id_input])

            jumlah_diproses += 1

        mysql.connection.commit()

        # =================================================
        # SIMPAN LOG AKTIVITAS
        # =================================================
        simpan_log(
            f'Menjalankan proses KNN admin dengan K={nilai_k} untuk {jumlah_diproses} siswa'
        )

        flash(
            f'Proses KNN berhasil. {jumlah_diproses} siswa diproses dengan K={nilai_k}',
            'success'
        )

    except Exception as e:

        mysql.connection.rollback()

        flash(f'Gagal memproses KNN: {str(e)}', 'danger')

    finally:

        cur.close()

    return redirect('/admin/hasil_rekomendasi')

# =========================================================
# PROFIL GURU BK
# =========================================================
@app.route('/profil_guru', methods=['GET', 'POST'])
@login_required(roles=[2])
def profil_guru():

    id_guru = session['id_ref']

    cur = mysql.connection.cursor()

    # =====================================================
    # UPDATE FOTO PROFIL GURU
    # =====================================================
    if request.method == 'POST':

        if 'foto_profil' not in request.files:

            flash('File foto tidak ditemukan', 'danger')

            cur.close()

            return redirect('/profil_guru')

        file = request.files['foto_profil']

        berhasil_upload, foto_url, pesan_upload = simpan_file_profil(
            file,
            'profil_guru',
            id_guru
        )

        if not berhasil_upload:

            flash(pesan_upload, 'warning')

            cur.close()

            return redirect('/profil_guru')

        cur.execute("""
            UPDATE guru_bk
            SET foto_profil=%s
            WHERE id_guru=%s
        """, (
            foto_url,
            id_guru
        ))

        mysql.connection.commit()

        session['foto_profil'] = foto_url

        simpan_log('Memperbarui foto profil Guru BK')

        cur.close()

        flash(pesan_upload, 'success')

        return redirect('/profil_guru')

    # =====================================================
    # AMBIL DATA GURU
    # =====================================================
    cur.execute("""
        SELECT
            id_guru,
            nama_guru,
            jenis_kelamin,
            no_hp,
            email,
            foto_profil
        FROM guru_bk
        WHERE id_guru=%s
    """, [id_guru])

    guru = cur.fetchone()

    cur.close()

    return render_template(
        'guru/profil_guru.html',
        guru=guru
    )


# =========================================================
# LOGOUT
# =========================================================
@app.route('/logout')
def logout():

    simpan_log('Logout dari sistem')

    session.clear()

    return redirect('/')

# =========================================================
# RUN APP
# =========================================================
if __name__ == '__main__':

    app.run(
        debug=True
    )
