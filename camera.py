# camera.py

import numpy as np
import cv2
# from PIL import Image # Tidak digunakan secara eksplisit jika cv2.imencode cukup
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout, Flatten
from tensorflow.keras.layers import Conv2D
# from tensorflow.keras.optimizers import Adam # Adam tidak digunakan dalam pendefinisian model Anda
from tensorflow.keras.layers import MaxPooling2D
# from tensorflow.keras.preprocessing.image import ImageDataGenerator # Tidak digunakan
# from pandastable import Table, TableModel # Tidak digunakan
# from tensorflow.keras.preprocessing import image # Tidak digunakan
import datetime
from threading import Thread
# from Spotipy import * # Tidak digunakan
# import time # Tidak digunakan secara eksplisit
# import glob # glob.glob("songs/*.json") tidak digunakan setelahnya
import pandas as pd

face_cascade=cv2.CascadeClassifier("haarcascade_frontalface_default.xml") # Pastikan file ini ada
ds_factor=0.6 # Tidak digunakan

# file_paths = glob.glob("songs/*.json") # Tidak digunakan

emotion_model = Sequential()
emotion_model.add(Conv2D(32, kernel_size=(3, 3), activation='relu', input_shape=(48,48,1)))
emotion_model.add(Conv2D(64, kernel_size=(3, 3), activation='relu'))
emotion_model.add(MaxPooling2D(pool_size=(2, 2)))
emotion_model.add(Dropout(0.25))
emotion_model.add(Conv2D(128, kernel_size=(3, 3), activation='relu'))
emotion_model.add(MaxPooling2D(pool_size=(2, 2)))
emotion_model.add(Conv2D(128, kernel_size=(3, 3), activation='relu'))
emotion_model.add(MaxPooling2D(pool_size=(2, 2)))
emotion_model.add(Dropout(0.25))
emotion_model.add(Flatten())
emotion_model.add(Dense(1024, activation='relu'))
emotion_model.add(Dropout(0.5))
emotion_model.add(Dense(7, activation='softmax'))
emotion_model.load_weights('model.h5') # Pastikan file model.h5 ada dan path-nya benar

cv2.ocl.setUseOpenCL(False)

emotion_dict = {0:"Marah",1:"Menjijikkan",2:"Takut",3:"Senang",4:"Netral",5:"Sedih",6:"Terkejut"}
music_dist = {
    0: "songs/angry.json",    # Pastikan file-file JSON ini ada
    1: "songs/disgusted.json",# dan berisi kolom "Name", "Artist", "Link"
    2: "songs/fearful.json",
    3: "songs/happy.json",
    4: "songs/neutral.json",
    5: "songs/sad.json",
    6: "songs/surprised.json" # Anda sebelumnya menulis "surprised.json", pastikan nama file benar
}

global last_frame1
last_frame1 = np.zeros((480, 640, 3), dtype=np.uint8)
global cap1
show_text=[0] # Default emosi awal (misalnya, Netral jika index 4) -> Anda menggunakan [0] (Marah)

class FPS:
    def __init__(self):
        self._start = None
        self._end = None
        self._numFrames = 0
    def start(self):
        self._start = datetime.datetime.now()
        return self
    def stop(self):
        self._end = datetime.datetime.now()
    def update(self):
        self._numFrames += 1
    def elapsed(self):
        return (self._end - self._start).total_seconds()
    def fps(self):
        return self._numFrames / self.elapsed()

class WebcamVideoStream:
    def __init__(self, src=0):
        self.stream = cv2.VideoCapture(src,cv2.CAP_DSHOW)
        (self.grabbed, self.frame) = self.stream.read()
        self.stopped = False

    def start(self):
        Thread(target=self.update, args=()).start()
        return self
        
    def update(self):
        while True:
            if self.stopped:
                return
            (self.grabbed, self.frame) = self.stream.read()

    def read(self):
        return self.frame
    def stop(self):
        self.stopped = True

class VideoCamera(object):
    def __init__(self): # Tambahkan __init__ untuk inisialisasi cap1 sekali saja
        global cap1
        if 'cap1' not in globals() or cap1 is None: # Cek jika cap1 belum diinisialisasi
             cap1 = WebcamVideoStream(src=0).start()
        self.cap = cap1 # Gunakan instance cap1 yang sudah ada

    def get_frame(self):
        # global cap1 # Tidak perlu jika sudah dihandle di __init__ dan self.cap
        global df1 # df1 global yang akan diupdate
        global show_text
        global face_cascade
        global emotion_model
        global emotion_dict
        global music_dist
        global last_frame1

        # Hapus baris ini jika cap1 diinisialisasi di __init__
        # cap1 = WebcamVideoStream(src=0).start() # <<< INI MEMBUAT CAPTURE BARU SETIAP FRAME, KURANG EFISIEN
        
        image = self.cap.read() # Baca dari self.cap
        if image is None:
            print("Error: Frame kosong dari webcam.")
            # Return frame placeholder atau tangani error
            placeholder_img = np.zeros((500, 600, 3), dtype=np.uint8)
            cv2.putText(placeholder_img, "No Frame", (200, 250), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
            ret, jpeg = cv2.imencode('.jpg', placeholder_img)
            # Kembalikan DataFrame kosong jika tidak ada frame
            return jpeg.tobytes(), pd.DataFrame(columns=['Name', 'Artist', 'Link']).head(15)


        image_resized =cv2.resize(image,(600,500)) # Ganti nama variabel agar tidak menimpa 'image' asli
        gray=cv2.cvtColor(image_resized,cv2.COLOR_BGR2GRAY)
        
        if face_cascade is None:
            print("Error: face_cascade tidak dimuat.")
            # Kembalikan frame tanpa deteksi dan df1 yang ada atau default
            ret, jpeg = cv2.imencode('.jpg', image_resized)
            return jpeg.tobytes(), df1 # df1 di sini adalah global df1 dari app.py
        
        face_rects=face_cascade.detectMultiScale(gray,1.3,5)
        
        # Bagian ini akan mencoba memuat df1 berdasarkan emosi awal atau terakhir
        # sebelum loop deteksi wajah. Jika tidak ada wajah terdeteksi, df1 ini yang akan dikembalikan.
        try:
            # Menggunakan music_rec() untuk memuat dan memproses DataFrame awal
            # Ini memastikan konsistensi dalam bagaimana DataFrame musik dimuat
            current_songs_df = music_rec() 
        except Exception as e:
            print(f"Error saat memuat musik awal di get_frame: {e}")
            current_songs_df = pd.DataFrame(columns=['Name', 'Artist', 'Link']).head(15)

        for (x,y,w,h) in face_rects:
            cv2.rectangle(image_resized,(x,y-50),(x+w,y+h+10),(0,255,0),2)
            roi_gray_frame = gray[y:y + h, x:x + w]
            
            if roi_gray_frame.size == 0: # Hindari error jika roi kosong
                continue

            cropped_img = np.expand_dims(np.expand_dims(cv2.resize(roi_gray_frame, (48, 48)), -1), 0)
            
            if emotion_model is None:
                print("Error: emotion_model tidak dimuat.")
                cv2.putText(image_resized, "Model Error", (x + 20, y - 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2, cv2.LINE_AA)
                break # Keluar dari loop wajah jika model error

            prediction = emotion_model.predict(cropped_img)
            maxindex = int(np.argmax(prediction))
            show_text[0] = maxindex 
            
            if 0 <= maxindex < len(emotion_dict):
                 cv2.putText(image_resized, emotion_dict[maxindex], (x+20, y-60), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv2.LINE_AA)
            else:
                 cv2.putText(image_resized, "Emosi?", (x+20, y-60), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255),2,cv2.LINE_AA)

            # Setelah emosi terdeteksi, panggil music_rec() untuk mendapatkan DataFrame yang sesuai
            current_songs_df = music_rec() 
            break # Proses hanya wajah pertama agar tidak terlalu banyak update df1 dalam satu frame

        df1 = current_songs_df # Update df1 global dengan DataFrame yang baru diproses
            
        last_frame1 = image_resized.copy()
        # pic = cv2.cvtColor(last_frame1, cv2.COLOR_BGR2RGB) # Tidak perlu jika encode langsung
        # img = Image.fromarray(last_frame1) # Tidak perlu, last_frame1 sudah numpy array
        # img = np.array(img) # Redundan
        ret, jpeg = cv2.imencode('.jpg', last_frame1) # Encode image_resized yang sudah ada teks dan kotak
        
        if not ret:
            print("Error: Gagal encode frame ke JPEG.")
            # Handle error encoding
            placeholder_img = np.zeros((500, 600, 3), dtype=np.uint8)
            cv2.putText(placeholder_img, "Encode Error", (180, 250), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
            _, jpeg = cv2.imencode('.jpg', placeholder_img)

        return jpeg.tobytes(), df1

# Fungsi music_rec yang sudah diperbaiki
def music_rec():
    global show_text # show_text digunakan untuk menentukan file JSON mana yang akan dibaca
    global music_dist
    
    # Kolom yang diharapkan berdasarkan struktur JSON Anda ("Name", "Artist", "Link")
    expected_cols = ['Name', 'Artist', 'Link']
    
    try:
        emotion_idx = show_text[0]
        if not (0 <= emotion_idx < len(music_dist)): # Pastikan index valid
            print(f"Peringatan: Indeks emosi {emotion_idx} tidak valid. Menggunakan default Netral (4).")
            emotion_idx = 4 # Default ke Netral jika tidak valid
            show_text[0] = 4 # Update juga show_text global

        file_path = music_dist[emotion_idx]
        df = pd.read_json(file_path)
        
        # Proses DataFrame untuk memastikan kolom yang diharapkan ada dan sesuai urutan
        # Jika ada kolom yang tidak ada di JSON, akan diisi dengan None (NaN oleh Pandas)
        df_processed = pd.DataFrame(columns=expected_cols) 
        available_cols_in_df = []
        for col in expected_cols:
            if col in df.columns:
                df_processed[col] = df[col]
                available_cols_in_df.append(col)
            else:
                df_processed[col] = None # Atau pd.NA, atau string kosong ""
                print(f"Peringatan di music_rec: Kolom '{col}' tidak ditemukan di file {file_path}.")
        
        # Jika Anda hanya ingin kolom yang benar-benar ada dari expected_cols:
        # df_final = df_processed[available_cols_in_df]
        # Namun, untuk konsistensi, lebih baik mengembalikan semua expected_cols
        df_final = df_processed

    except FileNotFoundError:
        print(f"Error di music_rec: File JSON tidak ditemukan di {music_dist.get(show_text[0], 'Path Tidak Diketahui')}")
        df_final = pd.DataFrame(columns=expected_cols) # Kembalikan DataFrame kosong dengan kolom yang diharapkan
    except KeyError: # Jika show_text[0] menghasilkan kunci yang tidak ada di music_dist
        print(f"Error di music_rec: Kunci emosi {show_text[0]} tidak valid untuk music_dist.")
        df_final = pd.DataFrame(columns=expected_cols)
    except ValueError as ve: # Jika JSON tidak valid atau tidak bisa diparsing oleh read_json
        print(f"Error di music_rec saat membaca JSON dari {music_dist.get(show_text[0], 'Path Tidak Diketahui')}: {ve}")
        df_final = pd.DataFrame(columns=expected_cols)
    except Exception as e:
        print(f"Error tidak terduga di music_rec: {e}")
        df_final = pd.DataFrame(columns=expected_cols) # Fallback aman

    return df_final.head(15)