from flask import Flask, render_template, request, redirect, session, jsonify
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime

from knn import knn_predict
from chatbot import chatbot_response

import pandas as pd
import config

# =========================================================
# INISIALISASI APP
# =========================================================
app = Flask(__name__)

# =========================================================
# CONFIG DATABASE
# =========================================================
app.config['MYSQL_HOST'] = config.MYSQL_HOST
app.config['MYSQL_USER'] = config.MYSQL_USER
app.config['MYSQL_PASSWORD'] = config.MYSQL_PASSWORD
app.config['MYSQL_DB'] = config.MYSQL_DB

app.secret_key = config.SECRET_KEY

mysql = MySQL(app)

# =========================================================
# DECORATOR LOGIN
# =========================================================
def login_required(role=None):

    def wrapper(fn):

        @wraps(fn)
        def decorated_view(*args, **kwargs):

            if 'login' not in session:

                return redirect('/')

            if role and session.get('id_role') != role:

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
        SELECT *
        FROM akun
        WHERE username=%s
        AND id_role=3
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
        SELECT *
        FROM akun
        WHERE username=%s
        AND id_role=2
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

            return redirect('/dashboard_guru')

    return render_template(
        'auth/login_guru.html',
        error='Username atau password guru salah'
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

        cur.close()

        return redirect('/login_guru')

    return render_template(
        'auth/register_guru.html'
    )

# =========================================================
# DASHBOARD GURU
# =========================================================
@app.route('/dashboard_guru')
@login_required(role=2)
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
@login_required(role=3)
def dashboard_siswa():

    nis = session['id_ref']

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT *
        FROM siswa
        WHERE nis=%s
    """, [nis])

    siswa = cur.fetchone()

    cur.close()

    return render_template(
        'siswa/dashboard_siswa.html',
        siswa=siswa
    )

# =========================================================
# INPUT NILAI SISWA
# =========================================================
@app.route('/input_nilai', methods=['GET', 'POST'])
@login_required(role=2)
def input_nilai():

    if request.method == 'POST':

        file = request.files['file_excel']

        if file.filename == '':

            return "File belum dipilih"

        if not file.filename.endswith('.xlsx'):

            return "Format file harus .xlsx"

        df = pd.read_excel(file)

        cur = mysql.connection.cursor()

        for index, row in df.iterrows():

            cur.execute("""
                INSERT INTO input_siswa(
                    nis,
                    nilai_matematika,
                    nilai_bahasa_indonesia,
                    nilai_bahasa_inggris,
                    nilai_ipa,
                    nilai_ips,
                    realistic_score,
                    investigative_score,
                    artistic_score,
                    social_score,
                    enterprising_score,
                    conventional_score,
                    tanggal_input,
                    status_proses
                )
                VALUES(
                    %s,%s,%s,%s,%s,%s,
                    %s,%s,%s,%s,%s,%s,
                    %s,%s
                )
            """, (
                row['nis'],
                row['matematika'],
                row['indonesia'],
                row['inggris'],
                row['ipa'],
                row['ips'],
                row['realistic'],
                row['investigative'],
                row['artistic'],
                row['social'],
                row['enterprising'],
                row['conventional'],
                datetime.now(),
                'belum'
            ))

        mysql.connection.commit()

        cur.close()

        return redirect('/dashboard_guru')

    return render_template(
        'guru/input_nilai.html'
    )

# =========================================================
# INPUT DATA ALUMNI
# =========================================================
@app.route('/input_alumni', methods=['GET', 'POST'])
@login_required(role=2)
def input_alumni():

    if request.method == 'POST':

        file = request.files['file_excel']

        if file.filename == '':

            return "File belum dipilih"

        if not file.filename.endswith('.xlsx'):

            return "Format file harus .xlsx"

        df = pd.read_excel(file)

        cur = mysql.connection.cursor()

        for index, row in df.iterrows():

            cur.execute("""
                INSERT INTO alumni(
                    nama_alumni,
                    pilihan_mapel,
                    nilai_matematika,
                    nilai_bahasa_indonesia,
                    nilai_bahasa_inggris,
                    nilai_ipa,
                    nilai_ips,
                    realistic_score,
                    investigative_score,
                    artistic_score,
                    social_score,
                    enterprising_score,
                    conventional_score
                )
                VALUES(
                    %s,%s,%s,%s,%s,%s,
                    %s,%s,%s,%s,%s,%s,%s
                )
            """, (
                row['nama_alumni'],
                row['pilihan_mapel'],
                row['matematika'],
                row['indonesia'],
                row['inggris'],
                row['ipa'],
                row['ips'],
                row['realistic'],
                row['investigative'],
                row['artistic'],
                row['social'],
                row['enterprising'],
                row['conventional']
            ))

        mysql.connection.commit()

        cur.close()

        return redirect('/dashboard_guru')

    return render_template(
        'guru/input_alumni.html'
    )

# =========================================================
# HALAMAN PROSES KNN
# =========================================================
@app.route('/proses_knn')
@login_required(role=2)
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
@login_required(role=2)
def proses_semua_knn():

    cur = mysql.connection.cursor()

    # =====================================================
    # DATA SISWA
    # =====================================================
    cur.execute("""
        SELECT *
        FROM input_siswa
        WHERE status_proses='belum'
    """)

    semua_siswa = cur.fetchall()

    # =====================================================
    # DATA ALUMNI
    # =====================================================
    cur.execute("""
        SELECT *
        FROM alumni
    """)

    alumni = cur.fetchall()

    if len(alumni) == 0:

        cur.close()

        return "Data alumni belum tersedia"

    # =====================================================
    # DATA LATIH
    # =====================================================
    data_latih = []
    label_latih = []

    for a in alumni:

        fitur = [

            float(a[3]),
            float(a[4]),
            float(a[5]),
            float(a[6]),
            float(a[7]),

            float(a[8]),
            float(a[9]),
            float(a[10]),
            float(a[11]),
            float(a[12])
        ]

        data_latih.append(fitur)

        label_latih.append(a[2])

    # =====================================================
    # LOOP PROSES KNN
    # =====================================================
    for siswa in semua_siswa:

        nis = siswa[1]

        fitur_uji = [

            float(siswa[2]),
            float(siswa[3]),
            float(siswa[4]),
            float(siswa[5]),
            float(siswa[6]),

            float(siswa[7]),
            float(siswa[8]),
            float(siswa[9]),
            float(siswa[10]),
            float(siswa[11])
        ]

        hasil = knn_predict(
            data_latih,
            label_latih,
            fitur_uji,
            k=3
        )

        # =================================================
        # SIMPAN HASIL
        # =================================================
        cur.execute("""
            INSERT INTO hasil_knn(
                nis,
                nilai_k,
                hasil_jurusan,
                jumlah_tetangga
            )
            VALUES(%s,%s,%s,%s)
        """, (
            nis,
            3,
            hasil,
            3
        ))

        # =================================================
        # UPDATE STATUS
        # =================================================
        cur.execute("""
            UPDATE input_siswa
            SET status_proses='sudah'
            WHERE nis=%s
        """, [nis])

    mysql.connection.commit()

    cur.close()

    return redirect('/hasil_rekomendasi')

# =========================================================
# HASIL SISWA
# =========================================================
@app.route('/hasil')
@login_required(role=3)
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

# =========================================================
# HASIL REKOMENDASI GURU
# =========================================================
@app.route('/hasil_rekomendasi')
@login_required(role=2)
def hasil_rekomendasi():

    cur = mysql.connection.cursor()

    cur.execute("""

        SELECT
            hasil_chatbot.nis,
            siswa.nama_siswa,
            siswa.kelas,
            hasil_chatbot.minat_bakat,
            hasil_chatbot.kelompok_mapel,
            hasil_chatbot.detail_mapel,
            hasil_chatbot.tanggal

        FROM hasil_chatbot

        JOIN siswa
        ON hasil_chatbot.nis = siswa.nis

        ORDER BY hasil_chatbot.id DESC

    """)

    hasil_data = cur.fetchall()

    total_hasil = len(hasil_data)

    total_siswa = len(hasil_data)

    cur.close()

    return render_template(

        'guru/hasil_rekomendasi.html',

        hasil_data=hasil_data,

        total_hasil=total_hasil,

        total_siswa=total_siswa
    )

# =========================================================
# CHATBOT RIASEC
# =========================================================
@app.route('/chatbot', methods=['GET', 'POST'])
@login_required(role=3)
def chatbot():

    # =====================================================
    # LIST PERTANYAAN
    # =====================================================
    pertanyaan_list = [

        {
            'text': 'Apakah kamu suka memperbaiki mesin atau alat elektronik?',
            'kategori': 'REALISTIC'
        },

        {
            'text': 'Apakah kamu suka melakukan penelitian atau eksperimen?',
            'kategori': 'INVESTIGATIVE'
        },

        {
            'text': 'Apakah kamu suka menggambar atau membuat desain?',
            'kategori': 'ARTISTIC'
        },

        {
            'text': 'Apakah kamu suka membantu dan mengajar orang lain?',
            'kategori': 'SOCIAL'
        },

        {
            'text': 'Apakah kamu suka memimpin organisasi atau bisnis?',
            'kategori': 'ENTERPRISING'
        },

        {
            'text': 'Apakah kamu suka mengatur data dan administrasi?',
            'kategori': 'CONVENTIONAL'
        }

    ]

    nis = session['id_ref']

    cur = mysql.connection.cursor()

    # =====================================================
    # AMBIL DATA SISWA
    # =====================================================
    cur.execute("""
        SELECT nama_siswa, kelas
        FROM siswa
        WHERE nis=%s
    """, [nis])

    siswa = cur.fetchone()

    nama_siswa = siswa[0]
    kelas = siswa[1]

    # =====================================================
    # METHOD POST DARI JAVASCRIPT
    # =====================================================
    if request.method == 'POST':

        data = request.get_json()

        rekomendasi = data.get('minat_bakat')
        kelompok_mapel = data.get('kelompok_mapel')

        # =================================================
        # DETAIL MAPEL
        # =================================================
        detail_mapel = ''

        if rekomendasi == 'REALISTIC':

            detail_mapel = '''
Biologi,
Ekonomi,
PKWu,
Bahasa Inggris Tingkat Lanjut,
Informatika
'''

        elif rekomendasi == 'INVESTIGATIVE':

            detail_mapel = '''
Matematika Tingkat Lanjut,
Ekonomi,
PKWu,
Biologi,
Fisika
'''

        elif rekomendasi == 'ARTISTIC':

            detail_mapel = '''
Seni Musik,
Seni Rupa,
Bahasa Inggris,
Desain,
Multimedia
'''

        elif rekomendasi == 'SOCIAL':

            detail_mapel = '''
Sosiologi,
Geografi,
Bahasa Indonesia,
Ekonomi,
PPKn
'''

        elif rekomendasi == 'ENTERPRISING':

            detail_mapel = '''
Ekonomi,
Matematika,
PKWu,
Bahasa Inggris,
Bisnis Digital
'''

        elif rekomendasi == 'CONVENTIONAL':

            detail_mapel = '''
Akuntansi,
Ekonomi,
Administrasi,
Matematika,
Informatika
'''

        # =================================================
        # CEK DATA SUDAH ADA / BELUM
        # =================================================
        cur.execute("""
            SELECT *
            FROM hasil_chatbot
            WHERE nis=%s
        """, [nis])

        cek_data = cur.fetchone()

        # =================================================
        # UPDATE DATA
        # =================================================
        if cek_data:

            cur.execute("""
                UPDATE hasil_chatbot
                SET
                    nama_siswa=%s,
                    kelas=%s,
                    minat_bakat=%s,
                    kelompok_mapel=%s,
                    detail_mapel=%s,
                    tanggal=%s
                WHERE nis=%s
            """, (

                nama_siswa,
                kelas,
                rekomendasi,
                kelompok_mapel,
                detail_mapel,
                datetime.now(),
                nis

            ))

        # =================================================
        # INSERT DATA
        # =================================================
        else:

            cur.execute("""
                INSERT INTO hasil_chatbot(

                    nis,
                    nama_siswa,
                    kelas,
                    minat_bakat,
                    kelompok_mapel,
                    detail_mapel,
                    tanggal

                )

                VALUES(%s,%s,%s,%s,%s,%s,%s)

            """, (

                nis,
                nama_siswa,
                kelas,
                rekomendasi,
                kelompok_mapel,
                detail_mapel,
                datetime.now()

            ))

        # =================================================
        # COMMIT DATABASE
        # =================================================
        mysql.connection.commit()

        cur.close()

        return jsonify({
            'status': 'success'
        })

    # =====================================================
    # TAMPIL HALAMAN CHATBOT
    # =====================================================
    cur.close()

    return render_template(

        'siswa/chatbot.html',

        nama_siswa=nama_siswa,

        nomor=1,

        progress=0,

        pertanyaan=pertanyaan_list[0]['text'],

        hasil_riasec=None,

        rekomendasi=None,

        kelompok_mapel=None,

        detail_mapel=None
    )
    
# =========================================================
# LOGOUT
# =========================================================
@app.route('/logout')
def logout():

    session.clear()

    return redirect('/')

# =========================================================
# RUN APP
# =========================================================
if __name__ == '__main__':

    app.run(
        debug=True
    )