from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.core.text import LabelBase
from kivy.uix.button import Button
from kivy.properties import StringProperty, BooleanProperty, NumericProperty
from kivy.properties import ObjectProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.filechooser import FileChooserListView 
from kivy.core.clipboard import Clipboard
from kivy.uix.filechooser import FileChooserIconView
from kivy.lang import Builder 
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from kivy.metrics import dp
from kivy.core.window import Window
from kivy.factory import Factory
from Crypto.Random import get_random_bytes
from datetime import datetime
import time
from kivy.utils import platform
from io import BytesIO
import shutil
import socket
import string
import threading
import os
from os.path import expanduser, join


LabelBase.register(name="FontAwesome", fn_regular="assets/FontAwesome_Regular.ttf")
LabelBase.register(name="FontAwesomeSolid", fn_regular="assets/FontAwesome_Solid.ttf")
LabelBase.register(name="FontText", fn_regular="assets/customFont.ttf")

def adjust_key_length(user_key: str, target_length: int = 24) -> bytes:
    """Menyesuaikan panjang kunci untuk AES 192-bit."""
    key_bytes = user_key.encode('utf-8')

    if len(key_bytes) < target_length:
        padded_key = pad(key_bytes, target_length)[:target_length]
    else:
        padded_key = key_bytes[:target_length]

    return padded_key


class BaseScreen(Screen):
    def show_message(self, message, title="Pesan", duration=None):
        popup = Factory.MessagePopup()
        popup.title = title
        popup.ids.message_label.text = message
        popup.open()

        if duration:
            Clock.schedule_once(lambda dt: popup.dismiss(), duration)
    
    def show_temporary_message(self, message, title="Status"):
        popup = Factory.MessagePopup()
        popup.title = title
        popup.ids.message_label.text = message
        popup.open()
        return popup

class FileChooserPopup(Popup):
    def __init__(self, file_type=None, parent_screen=None, on_select_callback=None, **kwargs):
        super().__init__(**kwargs)
        self.title = f"Pilih File {file_type.capitalize() if file_type else ''}"
        self.file_type = file_type  # Simpan file_type agar bisa digunakan nanti
        self.parent_screen = parent_screen
        self.on_select_callback= on_select_callback
    
    def on_open(self):  
        # Dipanggil ketika popup terbuka
        try:
                if platform == "android":
                    default_path ="/sdcard/" 
                else:
                    default_path = os.path.expanduser("~")
                self.ids.file_chooser.path = default_path

        except Exception as e:
            print("Gagal set path default:", e)
 
        self.set_filter()

    def set_filter(self):
            """Atur filter berdasarkan tipe file."""
            if hasattr(self, "ids") and "file_chooser" in self.ids:
                if self.file_type == "Dokumen":
                    self.ids.file_chooser.filters = ['*.txt', '*.docx', '*.pdf']
                elif self.file_type  in ("Media", "DecryptMedia"):
                    self.ids.file_chooser.filters = ['*.jpg', '*.jpeg', '*.png', '*.mp3', '*.wav']
                else:
                    self.ids.file_chooser.filters = ['*.*']  # Default: semua file
                
    def on_select(self):
        selected = self.ids.file_chooser.selection
        if selected:
            self.dismiss()
            # Untuk EncryptScreen
            if self.parent_screen:
                self.parent_screen.set_selected_file(selected[0], self.file_type)
            # Untuk DecryptScreen
            elif self.on_select_callback:
                self.on_select_callback(selected)
        else:
            self.dismiss()

class CustomButton(Button):
    icon_source = StringProperty("")  # Unicode ikon (contoh: "\uf015" untuk Home)
    text_label = StringProperty("Button")  # Teks tombol
    is_nav = BooleanProperty(False)  # Jika tombol ini adalah navigasi

#kelas Screen Manager
class SplashScreen(BaseScreen):
    def on_enter(self):
        Clock.schedule_once(self.switch_to_main, 7)

    def switch_to_main(self, dt):
        self.manager.current = 'main'


class MainScreen(BaseScreen):
    pass

class InstructionScreen(BaseScreen):
    pass

class EncryptScreen(BaseScreen):
    """Screen utama untuk memilih file dan melakukan enkripsi."""
    document_path = StringProperty(None, allownone= True)
    media_path = StringProperty(None, allownone= True)
    encrypted_file_path = StringProperty(None, allownone= True)

    def on_leave(self):
        Clock.schedule_once(lambda dt: self.reset_fields())

    def select_document(self):
        popup = FileChooserPopup(
            file_type="Dokumen", 
            parent_screen=self
        )  
        popup.open()

    def select_media(self):
        popup = FileChooserPopup(
            file_type="Media", 
            parent_screen=self
        )  
        popup.open()

    def set_selected_file(self, file_path, file_type):
        if not file_path:
            self.show_message("File tidak valid atau kosong.")
            return
        
        file_name = os.path.basename(file_path)
        
        if file_type == "Dokumen":
            self.document_path = file_path  
            self.ids.document_label.text = f"File: {os.path.basename(file_path)}"
        elif file_type == "Media":
            self.media_path = file_path  # Simpan path file
            self.ids.media_label.text = f"File: {os.path.basename(file_path)}"


    def encrypt_file(self):
        """Melakukan enkripsi dokumen & menyisipkannya ke media."""
        if not self.document_path or not self.media_path:
            self.show_message("Pilih file dokumen dan media terlebih dahulu!")
            return

        try:
            start_enc = time.perf_counter()
            secret_key = self.ids.secret_key.text
            if not secret_key:
                self.show_message("Masukkan kunci enkripsi!")
                return

            secret_key = adjust_key_length(secret_key)
            iv = get_random_bytes(AES.block_size)

            with open(self.document_path, "rb") as file:
                data = file.read()
            
            original_filename = os.path.basename(self.document_path).encode()
            if len(original_filename) > 65535:
                self.show_message("Nama file terlalu panjang untuk dienkripsi.")
                return
            
            filename_len = len(original_filename).to_bytes(2, 'big')  # Panjang nama file: 2 byte
            data_with_filename = filename_len + original_filename + data

            cipher = AES.new(secret_key, AES.MODE_CBC, iv)
            encrypted_data = cipher.encrypt(pad(data_with_filename, AES.block_size))

            with open(self.media_path, 'rb') as media:
                media_data = media.read()

            # Simpan hasil final ke buffer sementara
            self.encrypted_buffer = media_data + b'E0F' + iv + encrypted_data

            # Simpan nama file sementara
            self.encrypted_filename = os.path.splitext(os.path.basename(self.media_path))[0] + "_stego" + os.path.splitext(self.media_path)[1]
            self.ids.encrypted_file_label.text = f"File: {self.encrypted_filename}"
            self.show_message(f"File berhasil dienkripsi dan siap diunduh.")

            end_enc = time.perf_counter()
            enc_time = end_enc - start_enc
            print(f"Enkripsi file:{os.path.basename(self.document_path)} ke dalam {os.path.basename(self.media_path)} selesai dalam {enc_time:.3f} detik\n")

        except Exception as e:
            self.show_message(f"Terjadi kesalahan: {str(e)}")


    def download_encrypted_file(self):
        """Membuka dialog pemilihan folder untuk menyimpan file."""
        if not hasattr(self, 'encrypted_buffer') or not self.encrypted_buffer:
            self.show_message("Tidak ada file yang dapat diunduh.")
            return

        content = BoxLayout(orientation='vertical')
        file_chooser = FileChooserListView(dirselect=True)

        file_chooser.filters = [lambda folder, filename: os.path.isdir(os.path.join(folder, filename))]
        file_chooser.path = os.path.expanduser("~")  # Mulai dari folder Home/User

        save_button = Button(text="Simpan", size_hint_y=None, height=50)

        popup = Popup(title="Pilih Folder Penyimpanan", content=content, size_hint=(0.9, 0.9))

        def save_file(_):
            if file_chooser.selection:
                save_folder = file_chooser.selection[0]
                if os.path.isdir(save_folder):
                    # Gunakan nama yang ditentukan sebelumnya
                    filename = getattr(self, 'encrypted_filename', 'hasil_enkripsi_stego.png')
                    timestamp = datetime.now().strftime("%Y%m%d")
                    name_only, ext = os.path.splitext(filename)
                    save_path = os.path.join(save_folder, f"{name_only}_{timestamp}{ext}")

                    # Simpan buffer ke file
                    with open(save_path, 'wb') as f:
                        f.write(self.encrypted_buffer)

                    popup.dismiss()
                    self.show_message(f"File berhasil disimpan di:\n{save_path}")

                     # Ganti dari reset_encryption_screen ke reload
                    App.get_running_app().reload_screen('encrypt')
                else:
                    self.show_message("Harap pilih folder, bukan file!")

        save_button.bind(on_release=save_file)
        content.add_widget(file_chooser)
        content.add_widget(save_button)
        popup.open()


    def transfer_file(self):
        print("Tombol transfer diklik!")

        sender_screen = self.manager.get_screen("sender")

        if not hasattr(self, 'encrypted_buffer') or not self.encrypted_buffer:
           self.show_message("Tidak Ada file stego untuk di transfer!")
           return

        temp_filename = self.encrypted_filename if hasattr(self, 'encrypted_filename') else "temp_encrypted_stego.png"
        temp_path = os.path.join(os.getcwd(), temp_filename)

        with open(temp_path, 'wb') as f:
            f.write(self.encrypted_buffer)

        sender_screen.selected_file = temp_path
        sender_screen.temp_file_label = f"File: {os.path.basename(temp_path)}"
        self.manager.current = "sender"

        if hasattr(sender_screen, 'ids') and hasattr(sender_screen.ids, 'file_sender_label'):
            # sender_screen.ids.file_sender_label.text = f"File: {os.path.basename(temp_path)}"
            Clock.schedule_once(lambda dt: setattr(sender_screen.ids.file_sender_label, "text", f"File: {os.path.basename(temp_path)}"))
        else:
            print("Label file_sender_label tidak ditemukan di halaman sender.")

        if hasattr(self, 'ids') and hasattr(self.ids, 'media_label'):
            self.ids.media_label.text = f"File: {os.path.basename(temp_path)}"
        else:
            print("Label media_label tidak ditemukan di halaman ini.")

        encrypt_screen = App.get_running_app().root.get_screen('encrypt')
        Clock.schedule_once(lambda dt: encrypt_screen.reset_fields())

    def reset_fields(self):
        self.document_path = None
        self.media_path = None
        self.encrypted_file_path = None
        self.encrypted_buffer = None
        self.encrypted_filename = None

        if hasattr(self.ids, 'document_label'):
            self.ids.document_label.text = "File: Belum dipilih"
        if hasattr(self.ids, 'media_label'):
            self.ids.media_label.text = "File: Belum dipilih"
        if hasattr(self.ids, 'encrypted_file_label'):
            self.ids.encrypted_file_label.text = "Belum ada file terenkripsi"
        if hasattr(self.ids, 'secret_key'):
            self.ids.secret_key.text = ""


class DecryptScreen(BaseScreen):
    selected_file = StringProperty(None, allownone=True)
    decrypted_file_path = StringProperty(None, allownone=True)

    def on_leave(self):
        Clock.schedule_once(lambda dt: self.reset_halaman())

    def select_media(self):
        """Buka FileChooserPopup hanya untuk file media (gambar/audio)."""
        popup = FileChooserPopup(
            file_type="DecryptMedia",
            parent_screen=self
        )
        popup.open()

    def set_selected_file(self, file_path, file_type=None):
        if not file_path:
            self.show_message("File tidak valid.")
            return

        self.selected_file = file_path
        file_name = os.path.basename(file_path)
        if "dekripsi_label" in self.ids:
            self.ids.dekripsi_label.text = f"File: {file_name}"
        else:
            print("Label 'dekripsi_label' tidak ditemukan di .kv")

    def decrypt_file(self):
        """Melakukan dekripsi file dari media stego."""
        if not self.selected_file:
            self.show_message("Pilih file stego terlebih dahulu!")
            return

        try:
            start_dec = time.perf_counter()
            secret_key = self.ids.secret_key.text
            if not secret_key:
                self.show_message("Masukkan kunci dekripsi!")
                return

            secret_key = adjust_key_length(secret_key)

            with open(self.selected_file, "rb") as f:
                content = f.read()

            eof_marker = b'E0F'
            if eof_marker not in content:
                self.show_message("File tidak valid atau bukan file hasil steganografi.")
                return

            marker_index = content.index(eof_marker)
            iv = content[marker_index + len(eof_marker): marker_index + len(eof_marker) + AES.block_size]
            encrypted_data = content[marker_index + len(eof_marker) + AES.block_size:]

            cipher = AES.new(secret_key, AES.MODE_CBC, iv)
            decrypted_padded = cipher.decrypt(encrypted_data)
            decrypted = unpad(decrypted_padded, AES.block_size)

            filename_len = int.from_bytes(decrypted[:2], 'big')
            original_filename = decrypted[2:2 + filename_len].decode(errors='ignore')
            file_content = decrypted[2 + filename_len:]

            # Simpan ke buffer dan nama
            self.decrypted_file_data = file_content
            self.decrypted_file_name = original_filename
            self.ids.decrypt_file_label.text = f"File: {original_filename}"

            self.show_message("File berhasil didekripsi dan siap diunduh.")
            end_dec = time.perf_counter()
            print(f"dekripsi file: selesai dalam {end_dec - start_dec:.3f} detik\n")

        except Exception as e:
            self.show_message(f"Terjadi kesalahan: {str(e)}")


    def download_decrypted_file(self):
        """Membuka dialog pemilihan folder untuk menyimpan file hasil dekripsi."""
        if not hasattr(self, 'decrypted_file_data') or not self.decrypted_file_data:
            self.show_message("Tidak ada file yang dapat diunduh.")
            return

        content = BoxLayout(orientation='vertical')
        file_chooser = FileChooserListView(dirselect=True)

        file_chooser.filters = [lambda folder, filename: os.path.isdir(os.path.join(folder, filename))]
        file_chooser.path = os.path.expanduser("~")

        save_button = Button(text="Simpan", size_hint_y=None, height=50)
        popup = Popup(title="Pilih Folder Penyimpanan", content=content, size_hint=(0.9, 0.9))

        def save_file(_):
            if file_chooser.selection:
                save_folder = file_chooser.selection[0]
                if os.path.isdir(save_folder):
                    filename = getattr(self, 'decrypted_file_name', 'hasil_dekripsi.pdf')
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    name_only, ext = os.path.splitext(filename)
                    save_path = os.path.join(save_folder, f"{name_only}_{timestamp}{ext}")

                    with open(save_path, 'wb') as f:
                        f.write(self.decrypted_file_data)

                    popup.dismiss()
                    self.show_message(f"File berhasil disimpan di:\n{save_path}")
                    App.get_running_app().reload_screen('decrypt')
                else:
                    self.show_message("Harap pilih folder, bukan file!")

        save_button.bind(on_release=save_file)
        content.add_widget(file_chooser)
        content.add_widget(save_button)
        popup.open()

    def reset_halaman(self):
        self.selected_file = None
        self.decrypted_file_path = None
        self.decrypted_file_data = None
        self.decrypted_file_name = None

        if hasattr(self.ids, 'dekripsi_label'):
            self.ids.dekripsi_label.text = "File: Belum dipilih"
        if hasattr(self.ids, 'decrypt_file_label'):
            self.ids.decrypt_file_label.text = "Belum ada file terdekripsi"
        if hasattr(self.ids, 'secret_key'):
            self.ids.secret_key.text = ""


class TransferScreen(BaseScreen):
    pass

class SenderScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.selected_file = None
        self.temp_file_label = ""
        self.popup = None  # Simpan referensi popup agar bisa ditutup di mana saja

    def on_enter(self):
        if self.selected_file and hasattr(self, 'temp_file_label'):
            if "file_sender_label" in self.ids:
                self.ids.file_sender_label.text = self.temp_file_label
            else:
                print("Label file_sender_label tidak ditemukan saat on_enter SenderScreen.")

    # def on_leave(self):
    #     self.reset_transfer()
    
    def select_file(self):
        """Buka FileChooserPopup hanya untuk file media (gambar/audio)."""
        popup = FileChooserPopup(
        file_type="Dokumen/Media",
            parent_screen=self
        )
        popup.open()

    def set_selected_file(self, file_path, file_type=None):
        if not file_path:
            self.show_message("File tidak valid.")
            return

        self.selected_file = file_path
        file_name = os.path.basename(file_path)
        if "file_sender_label" in self.ids:
            self.ids.file_sender_label.text = f"File: {file_name}"
        else:
            print("Label 'dekripsi_label' tidak ditemukan di .kv")

    def send_file(self):
        """Mengirim file ke receiver melalui TCP"""
        receiver_ip = self.ids.ip_input.text.strip()
        port = 12345  # Port default

        if not self.selected_file:
            self.show_message("Pilih file terlebih dahulu!")
            return
        
        if not receiver_ip:
            self.show_message("Masukkan IP receiver!")
            return

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
                client_socket.settimeout(10)  # Batasi waktu koneksi
                client_socket.connect((receiver_ip, port))
                print("mengatur waktu koneksi")

                # Kirim nama file terlebih dahulu
                print("mengirim nama file")
                filename = os.path.basename(self.selected_file)
                client_socket.send(filename.encode())
                filesize = str(os.path.getsize(self.selected_file))
                #filesize = str(os.path.getsize("C:\\Users\\ACER\\Documents\\"+filename))
                time.sleep(0.5)
                print(f"Ukuran file dalam byte : {filesize}")
                client_socket.send(filesize.encode())
                
                # Kirim isi file
                print("Membaca dan mengirim isi file..")
                popup_ref = [None]
                Clock.schedule_once(lambda dt: popup_ref.__setitem__(0, self.show_temporary_message("Sedang mengirim file...")))
                with open(self.selected_file, "rb") as file:
                    data_kirim = file.read()
                    client_socket.sendall(data_kirim)

                Clock.schedule_once(lambda dt: popup_ref[0].dismiss() if popup_ref[0] else None)
                Clock.schedule_once(lambda dt: self.show_message("Semua data berhasil dikirim."))
                
                # Menerima konfirmasi dari receiver
                print("Konfirmasi dari penerima")
                time.sleep(0.5)
                confirmation = client_socket.recv(1024).decode()
                if confirmation == "RECEIVED":
                    self.show_message("File berhasil dikirim!")
                    App.get_running_app().reload_screen('sender')
                else:
                    self.show_message("Gagal mengirim file!", duration=3)
                
                # Tutup socket
                client_socket.close()
                print("Socket di tutup!")
                

        except socket.timeout:
            self.ids.status_label.text = "Koneksi timeout! Periksa IP penerima."
        except Exception as e:
            self.ids.status_label.text = f"Error: {e}"

    # def reset_transfer(self):
    #     self.selected_file = None

    #     if "file_sender_label" in self.ids:
    #         self.ids.file_sender_label.text = "File: Belum dipilih"

    #     if "ip_input" in self.ids:
    #         self.ids.ip_input.text = ""

    #     if "status_label" in self.ids:
    #         self.ids.status_label.text = ""


class ReceiverScreen(BaseScreen):
    receiver_file_path = StringProperty("") 


    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.file_data = None
        self.nama_file = None

    def on_enter(self):
        """Dipanggil saat masuk ke halaman, IP disembunyikan"""
        self.hide_ip()

    def on_leave(self):
        """Dipanggil saat keluar dari halaman, IP disembunyikan"""
        self.hide_ip()

    def get_ip_address(self):
        """Mendapatkan alamat IP perangkat"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip_address = s.getsockname()[0]
            s.close()
        except:
            ip_address = "Tidak dapat mengambil IP"

        self.ids.ip_label.text = f"IP: {ip_address}"
        return ip_address

    def refresh_ip(self):
        self.get_ip_address()

    def hide_ip(self):
        self.ids.ip_label.text = "IP: ********"


    def start_server(self):
        """Membuka server untuk menerima koneksi"""
        print("membuka server ")
        server_thread = threading.Thread(target=self.run_server, daemon=True)
        server_thread.start()

    def run_server(self):
        """Membuka koneksi dan menerima data"""
        try:
            print("Menunggu koneksi masuk...")
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.bind(("0.0.0.0", 12345))  # Menerima dari semua alamat pada port 12345
            server_socket.listen(1)
        

            conn, addr = server_socket.accept()
            
            Clock.schedule_once(lambda dt: self.show_message(f"Koneksi diterima dari {addr}", duration=1))

            # Menerima data (bisa diubah sesuai format yang dikirimkan oleh sender)
            with conn:
                # Menerima nama file
                self.nama_file = conn.recv(1024).decode()
                print("Nama file diterima : ", self.nama_file)
                # Menerima ukuran file
                ukuran_file = conn.recv(1024).decode()
                print("Ukuran file diterima : ", ukuran_file)
                # Menerima isi file
                popup_ref = [None]
                Clock.schedule_once(lambda dt: popup_ref.__setitem__(0, self.show_temporary_message("Sedang menerima file...")))

                data_diterima = 0
                file_data = b''
                while data_diterima < int(ukuran_file):
                    data = conn.recv(int(ukuran_file))
                    if not data:
                        break
                    file_data += data
                    data_diterima += len(data)
                    print(f"Data diterima: {len(file_data)} bytes")

                Clock.schedule_once(lambda dt: popup_ref[0].dismiss() if popup_ref[0] else None)
                print("Mengirim sinyal RECEIVED..")
                conn.send("RECEIVED".encode())

                self.file_data = file_data
                # self.receiver_file_path = f"File diterima: {self.nama_file}"
                Clock.schedule_once(lambda dt: setattr(self, 'receiver_file_path', f"File diterima: {self.nama_file}"))

            server_socket.close()
            print("Socket telah ditutup..")
        except Exception as e:
            self.show_message(f"errornya:{e}") 

    def download_File_Diterima(self):
        if not self.file_data:
            self.show_message("Belum ada file yang diterima!")
            return

        content = BoxLayout(orientation='vertical')
        default_folder = join(expanduser("~"), "Documents")
        filechooser = FileChooserListView(path=default_folder, dirselect=True)
        button_save = Button(text="Simpan di folder ini", size_hint_y=None, height=40)

        def save_file(instance):
            folder_path = filechooser.path
            full_path = os.path.join(folder_path, self.nama_file)
            with open(full_path, "wb") as f:
                f.write(self.file_data)
            self.receiver_file_path = f"File disimpan: {self.nama_file}"
            popup.dismiss()
            self.show_message("Sukses", f"File berhasil disimpan di:\n{full_path}")
            App.get_running_app().reload_screen('receiver')

        content.add_widget(filechooser)
        content.add_widget(button_save)

        popup = Popup(title="Pilih folder penyimpanan",
                      content=content,
                      size_hint=(0.9, 0.9))
        button_save.bind(on_press=save_file)
        popup.open()

class HIDEasyApp(App):
    screen_ratio = NumericProperty(0)

    def build(self):
        Builder.load_file("custom_widgets.kv")
        Builder.load_file("myapp.kv")  
        sm = ScreenManager()
        sm.add_widget(SplashScreen(name='splash'))
        sm.add_widget(MainScreen(name='main'))
        sm.add_widget(InstructionScreen(name='instruction'))
        sm.add_widget(EncryptScreen(name='encrypt'))
        sm.add_widget(DecryptScreen(name='decrypt'))
        sm.add_widget(TransferScreen(name='transfer'))
        sm.add_widget(SenderScreen(name='sender'))
        sm.add_widget(ReceiverScreen(name='receiver'))
        return sm
    
    def reload_screen(self, screen_name):
        sm = self.root
        existing_screen = sm.get_screen(screen_name)
        
        screen_classes = {
            'encrypt': EncryptScreen,
            'decrypt': DecryptScreen,
            'sender': SenderScreen,
            'receiver': ReceiverScreen,
            'transfer': TransferScreen,
            'main': MainScreen,
            'instruction': InstructionScreen,
            'splash': SplashScreen
        }

        if screen_name in screen_classes:
            screen_class = screen_classes[screen_name]
            sm.remove_widget(existing_screen)
            sm.add_widget(screen_class(name=screen_name))
            sm.current = screen_name
        else:
            print(f"[!] Screen '{screen_name}' tidak ditemukan dalam mapping.")


if __name__ == '__main__':
    HIDEasyApp().run()
