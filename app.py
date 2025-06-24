from flask import Flask, render_template, request, redirect, url_for, session, jsonify, Response
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from camera import VideoCamera, music_rec
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
import smtplib
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
from flask import flash, redirect, url_for
from threading import Thread
import json
import os
from flask import Flask, send_from_directory
import json
import random
from flask import Flask, jsonify
from flask_login import current_user
# from werkzeug.security import generate_password_hash, check_password_hash # <--- PASTIKAN BARIS INI ADA DAN BENAR
from flask_login import UserMixin
from werkzeug.security import check_password_hash
from datetime import datetime




app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost/music'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'dwirizqianthoro@gmail.com'  # Ganti dengan email Anda
app.config['MAIL_PASSWORD'] = 'msysyhnqpxpuhtxl'   # Ganti dengan password aplikasi
app.config['MAIL_DEFAULT_SENDER'] = 'dwirizqianthoro@gmail.com'
mail = Mail(app)

serializer = URLSafeTimedSerializer(app.secret_key)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)


DATA_FOLDER = "songs" 
    
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    tanggal_lahir = db.Column(db.Date, nullable=False)
    is_verified = db.Column(db.Boolean, default=False)

    # --- @property SEKARANG DI DALAM CLASS ---
    # Dengan ini, Anda bisa memanggil `user.umur` dan kode ini akan berjalan
    @property
    def umur(self):
        """Menghitung umur pengguna secara dinamis dari tanggal lahir."""
        if not self.tanggal_lahir:
            return None
        
        today = date.today()
        # Logika perhitungan umur yang akurat
        age = today.year - self.tanggal_lahir.year - ((today.month, today.day) < (self.tanggal_lahir.month, self.tanggal_lahir.day))
        return age
    
    # --- __repr__ SEKARANG JUGA DI DALAM CLASS ---
    def __repr__(self):
        return f'<User {self.username}>'

    
class History(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    # --- TAMBAHKAN BARIS INI ---
    age = db.Column(db.String(50), nullable=False, default='Dewasa') # default bisa disesuaikan
    # -------------------------
    emotion = db.Column(db.String(50), nullable=False)
    genre = db.Column(db.String(50), nullable=False)
    song_name = db.Column(db.String(200), nullable=False)
    artist_name = db.Column(db.String(200), nullable=False)
    youtube_link = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
        
    def __repr__(self):
        # Perbaikan kecil pada __repr__ Anda
        return f'<History ID: {self.id}, Song: {self.song_name}>'

def send_reset_email(user): # Sekarang menerima objek user
    token_expiration = 1800 # 30 menit
    token = serializer.dumps(user.email, salt='password-reset-salt')

    reset_url = url_for('reset_with_token', token=token, _external=True)

    subject = "Permintaan Reset Password - Moodify"
    # Anda bisa menggunakan user.username jika ingin menyapa dengan nama pengguna
    html_body = render_template('reset_password_email.html',
                                username=user.username, # Menggunakan username dari objek user
                                reset_url=reset_url)

    msg = Message(subject=subject,
                  recipients=[user.email], # Menggunakan email dari objek user
                  html=html_body)
    try:
        mail.send(msg)
        return True
    except Exception as e:
        app.logger.error(f"Gagal mengirim email reset ke {user.email}: {str(e)}")
        # Anda mungkin ingin log error yang lebih detail atau menanganinya secara berbeda
        print(f"Error sending email: {str(e)}") # Untuk debugging
        return False

# --- Route untuk Lupa Password ---
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        # Menggunakan model User SQLAlchemy untuk mencari pengguna
        user = User.query.filter_by(email=email).first()

        if user:
            if send_reset_email(user): # Mengirim objek user
                flash('Jika email Anda terdaftar, instruksi untuk mereset password telah dikirim. Silakan periksa inbox dan folder spam Anda.', 'success')
            else:
                flash('Maaf, terjadi kesalahan saat mengirim email reset. Silakan coba lagi nanti.', 'danger')
            return redirect(url_for('login'))
        else:
            # Tetap berikan pesan yang sama untuk keamanan (mencegah enumerasi akun)
            flash('Jika email Anda terdaftar, instruksi untuk mereset password telah dikirim. Silakan periksa inbox dan folder spam Anda.', 'info')
            # Tidak redirect ke login di sini agar pengguna bisa mencoba lagi jika salah ketik,
            # atau bisa juga redirect ke login jika itu preferensi Anda.
            return redirect(url_for('forgot_password'))


    return render_template('forgot-password.html') # Template HTML Lupa Password Anda

# --- Route untuk Menangani Reset Password dengan Token ---
@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_with_token(token):
    try:
        email = serializer.loads(token, salt='password-reset-salt', max_age=1800) # 30 menit expiration
    except: # SignatureExpired, BadTimeSignature, BadSignature, dll.
        flash('Tautan reset password tidak valid atau sudah kedaluwarsa. Silakan coba minta reset lagi.', 'danger')
        return redirect(url_for('forgot_password'))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash('Pengguna tidak ditemukan atau tautan tidak valid.', 'danger')
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not new_password or len(new_password) < 6: # Sesuaikan aturan panjang password
            flash('Password baru harus terdiri dari minimal 6 karakter.', 'warning')
            return render_template('reset_password_form.html', token=token) # Kirim token kembali ke template

        if new_password != confirm_password:
            flash('Password baru dan konfirmasi password tidak cocok.', 'warning')
            return render_template('reset_password_form.html', token=token) # Kirim token kembali ke template

        # Update password pengguna di database
        user.password = bcrypt.generate_password_hash(new_password).decode('utf-8') # Hash password baru
        try:
            db.session.commit() # Simpan perubahan ke database
            flash('Password Anda telah berhasil direset! Silakan login dengan password baru Anda.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback() # Batalkan perubahan jika ada error
            app.logger.error(f"Gagal update password untuk {user.email}: {str(e)}")
            flash('Terjadi kesalahan saat memperbarui password Anda. Silakan coba lagi.', 'danger')
            return render_template('reset_password_form.html', token=token)


    # Untuk GET request, tampilkan form reset password
    return render_template('reset_password_form.html', token=token)

@login_manager.user_loader
def load_user(user_id):
    if user_id.isdigit():
        return User.query.get(int(user_id))
    return None

# @app.route('/')
# def index():
#     if current_user.is_authenticated:
#         return redirect(url_for('home'))
#     return redirect(url_for('login'))


@app.route('/')
# @login_required
def home():
    return render_template('home.html')

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    # Bagian ini akan dieksekusi saat user MENYIMPAN form (method POST)
    if request.method == 'POST':
        # 1. Ambil data dari form yang baru (umur & phone sudah tidak ada)
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        tanggal_lahir_str = request.form.get('tanggal_lahir') # <-- BARU

        # 2. Validasi input baru
        if not username or not email or not tanggal_lahir_str:
            flash("Username, email, dan tanggal lahir wajib diisi!", "danger")
            return redirect(url_for('profile'))

        try:
            # 3. Update data user di database
            current_user.username = username
            current_user.email = email
            
            # Ubah string tanggal lahir dari form menjadi objek date sebelum disimpan
            current_user.tanggal_lahir = datetime.strptime(tanggal_lahir_str, '%Y-%m-%d').date()

            # Jika password diisi, update juga password (logika ini sudah benar)
            if password:
                current_user.password = bcrypt.generate_password_hash(password).decode('utf-8')

            # Simpan semua perubahan
            db.session.commit()
            flash("Profil berhasil diperbarui!", "success")

        except Exception as e:
            db.session.rollback()
            flash(f"Terjadi kesalahan: {str(e)}", "danger")

        return redirect(url_for('profile'))

    # Bagian ini akan dieksekusi saat user MEMBUKA halaman profil (method GET)
    # 4. Hitung umur user untuk ditampilkan di halaman
    today = date.today()
    # Pastikan tanggal lahir tidak kosong untuk menghindari error
    if current_user.tanggal_lahir:
        age = today.year - current_user.tanggal_lahir.year - ((today.month, today.day) < (current_user.tanggal_lahir.month, current_user.tanggal_lahir.day))
    else:
        age = "N/A" # Teks jika tanggal lahir tidak ada

    # 5. Kirim data user DAN umur yang sudah dihitung ke template
    return render_template('profile.html', user=current_user, age=age)


@app.route('/detect.html', methods=['GET', 'POST'])
@login_required
def detect():
    return render_template("detect.html")

# Sesuaikan headings dengan kolom yang ada di DataFrame Anda ("Name", "Artist", "Link")
headings = ("Name", "Artist", "Link") 
df1 = music_rec() # df1 global diinisialisasi dengan DataFrame yang memiliki kolom Name, Artist, Link
# df1 = df1.head(15) # .head(15) sudah dilakukan di dalam music_rec()

@app.route('/index.html')
@login_required
def index():
    # Pastikan df1 yang digunakan di sini memiliki kolom yang sesuai dengan 'headings'
    # print(df1.to_json(orient='records')) # Ini akan mencetak JSON dari df1
    return render_template('index.html', headings=headings, data=df1)

def gen(camera_instance): # Ubah nama parameter agar tidak bentrok dengan nama modul 'camera'
    global df1 # Mengacu pada df1 global di app.py
    while True:
        try:
            frame, new_df1_from_camera = camera_instance.get_frame()
            df1 = new_df1_from_camera # Update df1 global
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')
        except Exception as e:
            print(f"Error di gen function: {e}")
            # Anda bisa yield frame error atau break loop
            # Contoh: frame error
            # error_img = np.zeros((500, 600, 3), dtype=np.uint8)
            # cv2.putText(error_img, "Stream Error", (180, 250), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2)
            # ret, jpeg_error = cv2.imencode('.jpg', error_img)
            # yield (b'--frame\r\n'
            #        b'Content-Type: image/jpeg\r\n\r\n' + jpeg_error.tobytes() + b'\r\n\r\n')
            # time.sleep(1) # Beri jeda jika ada error berulang
            break # Atau hentikan streaming jika error parah


@app.route('/video_feed')
def video_feed():
    # Buat instance VideoCamera di sini agar setiap sesi video_feed menggunakan instance baru
    # atau kelola instance secara global jika memang diinginkan hanya satu instance.
    # Jika VideoCamera() di sini, maka __init__ akan dipanggil setiap kali /video_feed diakses.
    return Response(gen(VideoCamera()),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

# emotion_dict dan music_dist ini duplikat dengan yang ada di camera.py.
# Sebaiknya didefinisikan di satu tempat (misalnya file config atau di app.py jika camera.py mengimpornya)
# atau pastikan keduanya sinkron. Untuk endpoint /t, ini diperlukan di app.py.
emotion_dict = {0: "Marah", 1: "Menjijikkan", 2: "Takut", 3: "Senang", 4: "Netral", 5: "Sedih", 6: "Terkejut"}
music_dist = {
    0: "songs/angry.json",
    1: "songs/disgusted.json",
    2: "songs/fearful.json",
    3: "songs/happy.json",
    4: "songs/neutral.json",
    5: "songs/sad.json",
    6: "songs/surprised.json" # Pastikan nama file ini benar (sebelumnya ada "surprised.json")
}

@app.route('/t')
def get_songs():
    # Untuk endpoint /t, Anda mensimulasikan emosi.
    # Pastikan file JSON yang diload di sini juga memiliki struktur "Name", "Artist", "Link"
    # dan tidak lagi "Album" jika Anda ingin konsisten.
    # Jika file JSON untuk /t masih punya "Album", maka HTML yang menggunakan /t perlu handle itu.
    # Namun, idealnya semua file JSON Anda (baik yang dipakai camera.py maupun /t) punya struktur yang sama.

    emotion_id = random.randint(0, 6)  # Simulasi emosi terdeteksi
    file_path = music_dist[emotion_id]
    
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            songs_data = json.load(file) # songs_data bisa berupa array atau objek {"songs": [...]}

            # Jika file JSON Anda adalah array langsung: [{...}, {...}]
            if isinstance(songs_data, list):
                # Jika Anda ingin memastikan hanya kolom Name, Artist, Link yang dikirim:
                processed_songs = []
                for song in songs_data:
                    processed_songs.append({
                        "Name": song.get("Name"),
                        "Artist": song.get("Artist"),
                        "Link": song.get("Link")
                    })
                return jsonify(processed_songs)
            # Jika file JSON Anda adalah objek: {"status": "...", "songs": [{...}, {...}]}
            elif isinstance(songs_data, dict) and 'songs' in songs_data and isinstance(songs_data['songs'], list):
                 # Jika Anda ingin memastikan hanya kolom Name, Artist, Link yang dikirim:
                processed_songs_list = []
                for song in songs_data['songs']:
                    processed_songs_list.append({
                        "Name": song.get("Name"),
                        "Artist": song.get("Artist"),
                        "Link": song.get("Link")
                    })
                # Kembalikan dengan struktur yang sama jika frontend mengharapkannya, atau hanya listnya
                return jsonify({"status": songs_data.get("status", "success"), "songs": processed_songs_list})
                # Atau jika frontend HANYA butuh list lagunya:
                # return jsonify(processed_songs_list)
            else:
                # Format tidak dikenal, kembalikan error atau data apa adanya
                print(f"Peringatan: Format JSON dari {file_path} tidak dikenal untuk endpoint /t.")
                return jsonify(songs_data) # Kembalikan apa adanya, HTML akan menanganinya (atau gagal)

    except FileNotFoundError:
        return jsonify({"error": f"File musik tidak ditemukan: {file_path}"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# @app.route('/login', methods=['GET', 'POST'])
# def login():
#     if request.method == 'POST':
#         username = request.form['username']
#         password = request.form['password']
#         user = User.query.filter_by(username=username).first()
#         if user and bcrypt.check_password_hash(user.password, password):
#             login_user(user)
#             return redirect(url_for('home'))
#         return 'Invalid credentials'
#     return render_template('login.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user:
            if not user.is_verified:
                flash("Akun Anda belum diverifikasi. Silakan cek email untuk verifikasi.", "error")
                return redirect(url_for('login'))

            if bcrypt.check_password_hash(user.password, password):
                login_user(user)
                flash("Login berhasil!", "success")

                if user.is_admin:
                    return redirect(url_for('admin_dashboard'))
                else:
                    return redirect(url_for('home'))
            else:
                flash("Nama pengguna atau kata sandi salah!", "error")
        else:
            flash("Nama pengguna atau kata sandi salah!", "error")

        return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/admin_dashboard')
@login_required  # You can add this to ensure only logged-in users can access the admin dashboard
def admin_dashboard():
    # Check if the logged-in user is an admin
    if current_user.is_admin == 1:  # Assuming `current_user` is used to represent the logged-in user
        return render_template('admin/index.html')  # Your admin dashboard template
    else:
        return redirect(url_for('login'))  # Redirect non-admins to the home page



@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        tanggal_lahir_str = request.form.get('tanggal_lahir')

        # --- Validasi form ---
        if not tanggal_lahir_str:
            flash('Tanggal lahir wajib diisi.', 'error')
            return redirect(url_for('register'))

        if password != confirm_password:
            flash('Password tidak cocok.', 'error')
            return redirect(url_for('register'))
            
        # --- Konversi string tanggal lahir ke objek Date ---
        try:
            tanggal_lahir_obj = datetime.strptime(tanggal_lahir_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Format tanggal lahir tidak valid.', 'error')
            return redirect(url_for('register'))

        # --- BARU: Logika Pengecekan Umur ---
        today = date.today()
        # Hitung umur dengan mengurangi tahun, lalu kurangi 1 jika ulang tahun belum tiba tahun ini
        umur = today.year - tanggal_lahir_obj.year - ((today.month, today.day) < (tanggal_lahir_obj.month, tanggal_lahir_obj.day))
        
        kategori = None
        if 5 <= umur <= 13:
            kategori = "Anak-anak"
        elif 18 <= umur <= 40:
            kategori = "Dewasa"
        
        # Jika umur tidak masuk dalam kategori yang diizinkan
        if kategori is None:
            flash(f'Maaf, pendaftaran hanya untuk kategori umur 5-13 tahun atau 18-40 tahun. Umur Anda adalah {umur} tahun.', 'error')
            return redirect(url_for('register'))
        # --- AKHIR BAGIAN BARU ---

        # Cek apakah email sudah terdaftar
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email sudah terdaftar.', 'error')
            return redirect(url_for('register'))

        # Hash password dan simpan ke database
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        
        # Membuat user baru dengan 'tanggal_lahir' dan 'kategori'
        new_user = User(
            username=username, 
            email=email, 
            password=hashed_password,
            tanggal_lahir=tanggal_lahir_obj,
            is_verified=False
            # Anda bisa juga menambahkan kolom 'kategori' di model User Anda jika ingin menyimpannya
            # kategori=kategori 
        )
        db.session.add(new_user)
        db.session.commit()

        # Buat token verifikasi
        token = serializer.dumps(email, salt='email-confirm')
        confirm_url = url_for('confirm_email', token=token, _external=True)

        # Kirim email verifikasi
        try:
            msg = Message(
                subject='Verifikasi Email Anda',
                sender=app.config['MAIL_USERNAME'],
                recipients=[email]
            )
            msg.body = f'Halo {username}, silakan verifikasi email Anda: {confirm_url}'
            mail.send(msg)
        except Exception as e:
            db.session.rollback()
            flash(f'Gagal mengirim email verifikasi: {e}', 'error')
            return redirect(url_for('register'))
                
        flash('Pendaftaran berhasil! Silakan periksa email Anda untuk verifikasi.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')



@app.route('/logout')
@login_required
def logout():
    logout_user()  # Logout pengguna
    return redirect(url_for('home'))  # Redirect ke halaman login admin

# @app.route('/admin/login_admin', methods=['GET', 'POST'])
# def login_admin():
#     if request.method == 'POST':
#         username = request.form['username']
#         password = request.form['password']

#         # Cari user berdasarkan username
#         user = User.query.filter_by(username=username).first()

#         # Validasi user dan password
#         if user and bcrypt.check_password_hash(user.password, password) and user.is_admin:
#             login_user(user)  # Fungsi ini biasanya digunakan bersama Flask-Login
#             return redirect(url_for('home_admin'))  # Redirect ke halaman admin setelah login
#         else:
#             # Pesan error jika login gagal
#             error = "Username, password salah, atau Anda bukan admin!"
#             return render_template('/admin/login_admin.html', error=error)

#     return render_template('admin/login_admin.html')

@app.route('/login_admin', methods=['GET', 'POST'])
def login_admin():
    if request.method == 'POST':
        # Proses autentikasi admin
        pass  
    return render_template('login.html')  # Pastikan template ini tersedia


@app.route('/view')
@login_required
def view():
    if not current_user.is_admin:
        logout_user()  # Logout pengguna jika bukan admin
        return redirect(url_for('login_admin'))  # Redirect ke halaman login admin
    
    users = User.query.all()  # Fetch all users from the database
    return render_template('view.html', users=users)  # Pass the users to the template


    users = User.query.all()  # Fetch all users from the database
    return render_template('view.html', users=users)  # Pass the users to the template

@app.route('/home_admin')
@login_required
def home_admin():
    if not current_user.is_admin:
        return "Access Denied: Admins Only"
    return render_template('home_admin.html')


with app.app_context():
    db.create_all()
    
@app.route('/t')
def real_time():
    # Data real-time contoh
    data = [{"Nama": "Live Song 1", "Album": "Live Album A", "Artist": "Artist X"}]
    return jsonify(data)


@app.route('/confirm/<token>')
def confirm_email(token):
    try:
        email = serializer.loads(token, salt='email-confirm', max_age=3600)  # Token berlaku selama 1 jam
    except:
        flash('Link konfirmasi tidak valid atau telah kedaluwarsa.', 'error')
        return redirect(url_for('login'))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash('User tidak ditemukan.', 'error')
        return redirect(url_for('login'))

    if user.is_verified:
        flash('Akun sudah terverifikasi, silakan masuk.', 'info')
        return redirect(url_for('login'))

    user.is_verified = True
    db.session.commit()
    
    flash('Email Anda telah dikonfirmasi. Silakan masuk.', 'success')
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if not current_user.is_authenticated or not current_user.is_verified:
        return 'Please verify your email to access this page.'
    return 'Welcome to your dashboard!'


@app.route('/send_test_email')
def send_test_email():
    try:
        msg = Message('Test Email', sender=app.config['MAIL_USERNAME'], recipients=['recipient_email@gmail.com'])
        msg.body = 'This is a test email from Flask.'
        mail.send(msg)
        return 'Email sent successfully!'
    except Exception as e:
        return f'Failed to send email: {e}'

# FUNGSI BARU (GUNAKAN INI)
# Pastikan Anda sudah mengimpor datetime dan date
from datetime import datetime, date

@app.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    if request.method == 'POST':
        # Ambil data dari form
        user.username = request.form['username']
        user.email = request.form['email']
        
        # Ambil tanggal lahir sebagai string dan ubah ke objek date
        tanggal_lahir_str = request.form['tanggal_lahir']
        user.tanggal_lahir = datetime.strptime(tanggal_lahir_str, '%Y-%m-%d').date()

        # Logika untuk memperbarui password hanya jika diisi
        new_password = request.form.get('password')
        if new_password:
            user.password = bcrypt.generate_password_hash(new_password).decode('utf-8')

        db.session.commit()
        flash('Data user berhasil diperbarui!', 'success')
        return redirect(url_for('view'))
        
    return render_template('edit_user.html', user=user)

@app.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    # Mengambil user berdasarkan ID, ini sudah benar
    user = User.query.get(user_id)
    
    if user:
        # ----------------------------------------------------------------------
        # LANGKAH 1 (TAMBAHAN PENTING): 
        # Hapus semua 'History' yang terkait dengan user ini TERLEBIH DAHULU.
        # Ini adalah baris kunci untuk memperbaiki error.
        History.query.filter_by(user_id=user.id).delete()
        # ----------------------------------------------------------------------

        # LANGKAH 2: Setelah history bersih, sekarang aman untuk menghapus user.
        db.session.delete(user)

        # LANGKAH 3: Commit/simpan semua perubahan (penghapusan history dan user).
        db.session.commit()

        # Pesan sukses yang lebih informatif
        flash('User dan semua riwayatnya telah berhasil dihapus.', 'success')
    else:
        # Ini sudah benar, menangani jika user tidak ditemukan
        flash('User tidak ditemukan.', 'error')
        
    # Redirect kembali ke halaman daftar user
    return redirect(url_for('view'))

# Dictionary emosi dan mapping ke file JSON
emotion_dict = {0: "Marah", 1: "Menjijikkan", 2: "Takut", 3: "Senang", 4: "Netral", 5: "Sedih", 6: "Terkejut"}
music_dist = {
    0: "songs/angry.json",
    1: "songs/disgusted.json",
    2: "songs/fearful.json",
    3: "songs/happy.json",
    4: "songs/neutral.json",
    5: "songs/sad.json",
    6: "songs/surprised.json"
}

def get_songs_by_emotion(emotion_id):
    """Membaca file JSON berdasarkan emosi yang dipilih"""
    file_path = music_dist.get(emotion_id)

    if not file_path or not os.path.exists(file_path):
        return []  # Jika file tidak ditemukan, kembalikan list kosong

    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)  # Membaca file JSON
            if isinstance(data, list):  # Pastikan JSON berupa list
                return data
            else:
                print(f"Format JSON tidak valid di: {file_path}")
                return []
    except json.JSONDecodeError:
        print(f"Error membaca JSON: {file_path}")
        return []

@app.route('/filtering')
def filtering():
    """Menampilkan halaman filtering dengan emotion_dict"""
    return render_template("filtering.html", emotion_dict=emotion_dict)


@app.route('/filter', methods=['POST'])
def filter():
    """Mengembalikan lagu berdasarkan emosi yang dipilih"""
    data = request.json
    emotion_id = int(data.get("emotion_id", -1))

    if emotion_id in music_dist:
        songs = get_songs_by_emotion(emotion_id)
        return jsonify({"status": "success", "emotion": emotion_dict[emotion_id], "songs": songs})

    return jsonify({"status": "error", "message": "Invalid emotion ID"}), 400


@app.route('/recommend', methods=['POST'])
def recommend():
    data = request.get_json()

    if not data:
        return jsonify({"status": "error", "message": "Data request tidak valid", "songs": []})

    emotion = data.get('emotion')
    genre = data.get('genre')  # Bisa None

    if not emotion:
        return jsonify({"status": "error", "message": "Emotion harus diberikan", "songs": []})

    if current_user.is_authenticated:
        user_age = current_user.umur

        if 5 <= user_age < 13:
            age_category = "anak_anak"
        elif 18 <= user_age <= 40:
            age_category = "dewasa"
        else:
            return jsonify({"status": "error", "message": "Umur tidak sesuai dengan kategori lagu", "songs": []})

        # Anak-anak boleh tanpa genre
        if age_category == "anak_anak" and not genre:
            file_path = os.path.join(DATA_FOLDER, age_category, f"{emotion.lower()}.json")
        else:
            if not genre:
                return jsonify({"status": "error", "message": "Genre harus diberikan untuk kategori ini", "songs": []})
            file_path = os.path.join(DATA_FOLDER, age_category, emotion.lower(), f"{genre.lower()}.json")
    else:
        # User belum login → ambil lagu berdasarkan emosi saja
        file_path = os.path.join(DATA_FOLDER, f"{emotion.lower()}.json")

    # Debugging prints
    print("Requested Emotion:", emotion)
    print("Requested Genre:", genre)
    print("User Logged In:", current_user.is_authenticated)
    print("File Path:", file_path)

    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as file:
            songs_data = json.load(file)
            songs = songs_data.get("songs", [])[:10]
            songs_data["songs"] = songs
        return jsonify({"status": "success", "songs_data": songs_data})
    else:
        return jsonify({"status": "error", "message": "Data lagu tidak ditemukan", "songs": []})
    
    

@app.route('/recommend_guest', methods=['POST'])
def recommend_guest():
    data = request.get_json()
    emotion = data.get('emotion')
    genre = data.get('genre', 'pop')  # default ke 'pop' jika tidak dikirim

    # Gunakan kategori default untuk tamu
    age_category = "dewasa"

    file_path = os.path.join(DATA_FOLDER, age_category, emotion.lower(), f"{genre.lower()}.json")

    if not os.path.exists(file_path):
        # fallback jika genre default tidak tersedia
        available_genres = ["pop", "rock", "jazz"]  
        for g in available_genres:
            alt_path = os.path.join(DATA_FOLDER, age_category, emotion.lower(), f"{g}.json")
            if os.path.exists(alt_path):
                file_path = alt_path
                break
        else:
            return jsonify({"status": "error", "message": "Tidak ada lagu ditemukan", "songs": []})

    with open(file_path, "r", encoding="utf-8") as file:
        songs_data = json.load(file)

    return jsonify({"status": "success", "songs_data": songs_data})



VALID_EMOTIONS = ['angry', 'disgusted', 'fearful', 'happy', 'neutral', 'sad', 'surprised']

@app.route('/songs/<emotion>.json')
def serve_song_json(emotion):
    if emotion not in VALID_EMOTIONS:
        return {'error': 'Invalid emotion'}, 400
    try:
        return send_from_directory('static/songs', f'{emotion}.json')
    except FileNotFoundError:
        return {'error': 'File not found'}, 404

    
# Halaman About (menggunakan route filtering sesuai template)
@app.route("/about")
def about():
    return render_template("about.html")


@app.route('/log_history', methods=['POST'])
@login_required
def log_history():
    data = request.get_json()

    # 1. Validasi: Tambahkan 'age' ke kunci yang dibutuhkan
    required_keys = ['name', 'artist', 'link', 'emotion', 'genre', 'age'] # Tambahkan 'age'
    if not data or not all(key in data for key in required_keys):
        return jsonify({'status': 'error', 'message': 'Data yang dikirim tidak lengkap.'}), 400

    try:
        # 2. Buat entri baru, masukkan 'age'
        history_entry = History(
            user_id=current_user.id,
            song_name=data['name'],
            artist_name=data['artist'],
            youtube_link=data['link'],
            emotion=data['emotion'].capitalize(),
            genre=data['genre'].capitalize(),
            # --- TAMBAHKAN BARIS INI ---
            age=data['age'].capitalize()  # Ambil data umur dari request
            # -------------------------
        )
        db.session.add(history_entry)
        db.session.commit()
        
        return jsonify({'status': 'success', 'message': 'Riwayat berhasil disimpan.'})

    except Exception as e:
        db.session.rollback()
        print(f"ERROR: Gagal menyimpan riwayat ke database: {e}")
        return jsonify({'status': 'error', 'message': 'Terjadi kesalahan pada server saat menyimpan riwayat.'}), 500

@app.route('/history')
@login_required # Hanya user yang sudah login bisa akses halaman ini
def history():
    # Ambil semua data riwayat untuk pengguna yang sedang login
    # Urutkan berdasarkan waktu terbaru (descending)
    user_history = History.query.filter_by(user_id=current_user.id).order_by(History.timestamp.desc()).all()
    
    return render_template("history.html", history_records=user_history)



@app.route('/riwayat')
# @admin_required # <- Tambahkan ini jika Anda punya decorator untuk memastikan hanya admin yang bisa akses
def admin_history():
    """
    Menampilkan halaman yang berisi riwayat dari SEMUA pengguna untuk admin.
    """
    all_user_history = db.session.query(
        History, User
    ).join(
        User, History.user_id == User.id
    ).order_by(
        History.timestamp.desc()
    ).all()
    
    # Kirim data hasil query ke template
    return render_template('riwayat.html', all_history=all_user_history)



@app.route('/hapus_riwayat/<int:history_id>', methods=['POST'])
# @admin_required # Pastikan route ini juga diamankan
def delete_history(history_id):
    """
    Menghapus satu entri riwayat berdasarkan ID-nya.
    """
    # Cari riwayat di database berdasarkan ID yang diberikan
    history_to_delete = History.query.get_or_404(history_id)
    
    try:
        # Hapus objek dari sesi database
        db.session.delete(history_to_delete)
        # Simpan perubahan ke database
        db.session.commit()
        # Kirim respons sukses dalam format JSON
        return jsonify({'success': True, 'message': 'Riwayat berhasil dihapus.'})
    except Exception as e:
        # Jika terjadi error, batalkan perubahan dan kirim pesan error
        db.session.rollback()
        # Cetak error ke konsol untuk debugging
        print(f"Error saat menghapus: {e}") 
        return jsonify({'success': False, 'message': 'Gagal menghapus riwayat.'}), 500


def format_date_smartly(value, format_str='%d %B %Y'):
    """
    Filter Jinja2 yang bisa memformat objek date maupun string tanggal.
    Aman jika nilai yang diberikan None atau tidak valid.
    """
    if value is None:
        return ""

    # Perbaikan di sini: kita menggunakan 'date' yang sudah diimpor secara langsung
    if isinstance(value, (datetime,)):
        # Jika sudah objek date/datetime, kita bisa langsung format dengan cara yang lebih canggih
        months = [
            "Januari", "Februari", "Maret", "April", "Mei", "Juni",
            "Juli", "Agustus", "September", "Oktober", "November", "Desember"
        ]
        return f"{value.day} {months[value.month - 1]} {value.year}"
    
    if isinstance(value, str):
        try:
            # Coba parsing format YYYY-MM-DD
            date_obj = datetime.strptime(value, '%Y-%m-%d').date()
            months = [
                "Januari", "Februari", "Maret", "April", "Mei", "Juni",
                "Juli", "Agustus", "September", "Oktober", "November", "Desember"
            ]
            return f"{date_obj.day} {months[date_obj.month - 1]} {date_obj.year}"
        except ValueError:
            return value # Jika format string salah, kembalikan apa adanya
            
    return str(value)

# Pastikan filter ini tetap terdaftar
app.jinja_env.filters['smart_date'] = format_date_smartly



if __name__ == '__main__':
    app.run(debug=True)
    