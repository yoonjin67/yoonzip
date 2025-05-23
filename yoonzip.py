#!/usr/bin/python3
import gi
import sys
import os
import traceback
from multiprocessing import Process, Queue
import pyzipper
import zipfile

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib
compress_file_list = []
decompress_file_list = []


def try_open_zip(zip_path, password):
    try:
        zf = zipfile.ZipFile(zip_path)
        if password:
            zf.setpassword(password.encode("utf-8"))
        zf.testzip()
        return zf, 'zipfile'
    except:
        try:
            zf = pyzipper.AESZipFile(zip_path)
            if password:
                zf.pwd = password.encode("utf-8")
            zf.testzip()
            return zf, 'pyzipper'
        except:
            raise

def extract_zip(zip_path, dest_dir, password, queue):
    if zip_path in decompress_file_list:
        queue.put("Zip file is Already in a Queue")
        return
    else:
        decompress_file_list.append(zip_path)
    try:
        zf, typ = try_open_zip(zip_path, password)
        queue.put("Zip file Opened")
        for info in zf.infolist():
            filename = info.filename
            try:
                filename = filename.encode("cp437").decode("euc-kr")
            except:
                pass
            target = os.path.join(dest_dir, filename)
            if info.is_dir() or filename.endswith('/'):
                os.makedirs(target, exist_ok=True)
            else:
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with zf.open(info) as src, open(target, "wb") as dst:
                    dst.write(src.read())
        decompress_file_list.remove(zip_path)
        queue.put(":::DONE:::")
    except:
        decompress_file_list.remove(zip_path)
        queue.put("[ERROR]\n" + traceback.format_exc())
        queue.put(":::DONE:::")

def compress_zip(file_list, zip_path, password, queue):
    if zip_path in compress_file_list:
        queue.put("[ERROR] File Path Already exists")
        return
    else:
        compress_file_list.append(zip_path)
        for i in compress_file_list:
            print(i)
    try:
        queue.put("Started Compression...")
        with zipfile.ZipFile(zip_path, 'w', compression=pyzipper.ZIP_DEFLATED) as zf:
            if len(password) != 0:
                try:
                    zf.setpassword(password.encode("utf-8"))
                except:
                    zf.setpassword(password.encode("cp437").decode("euc-kr"))
                queue.put("ZIP Password Setup Done.")
            for f in file_list:
                if os.path.isdir(f):
                    for root, dirs, files in os.walk(f):
                        for file in files:
                            full_path = os.path.join(root, file)
                            rel_path  = os.path.relpath(full_path, f)
                            zf.write(full_path, arcname=os.path.join(os.path.basename(f), rel_path))
                else:
                    arcname = os.path.basename(f)
                    zf.write(f, arcname)
        queue.put(":::DONE:::")
        compress_file_list.remove(zip_path)
        return
    except:
        try:
            with pyzipper.AESZipFile(zip_path, 'w', compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES) as zf:
                if password:
                    try:
                        zf.setpassword(password.encode("utf-8"))
                    except:
                        zf.setpassword(password.encode("cp437").decode("euc-kr"))
                for f in file_list:
                    if os.path.isdir(f):
                        for root, dirs, files in os.walk(f):
                            for file in files:
                                full_path = os.path.join(root, file)
                                rel_path  = os.path.relpath(full_path, f)
                                zf.write(full_path, arcname=os.path.join(os.path.basename(f), rel_path))
                    else:
                        arcname = os.path.basename(f)
                        zf.write(f, arcname)
            compress_file_list.remove(zip_path)
            queue.put(":::DONE:::")
        except:
            compress_file_list.remove(zip_path)
            queue.put("[ERROR]\n" + traceback.format_exc())
            queue.put(":::DONE:::")

class ZipApp(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self, title="윤ZIP")
        self.set_default_size(700, 500)
        grid = Gtk.Grid(column_spacing=10, row_spacing=20)
        self.add(grid)

        self.mode_combo = Gtk.ComboBoxText()
        self.mode_combo.append_text("압축 해제")
        self.mode_combo.append_text("압축")
        self.mode_combo.set_active(0)
        grid.attach(Gtk.Label(label="모드:"), 0, 0, 1, 1)
        grid.attach(self.mode_combo, 1, 0, 2, 1)
        self.mode_combo.connect("changed", self.on_mode_changed)

        # 압축 해제 관련
        self.unzip_widgets = Gtk.Grid(column_spacing=10, row_spacing=10)
        grid.attach(self.unzip_widgets, 0, 1, 3, 1)

        self.zip_select_btn = Gtk.Button(label="ZIP 파일 선택")
        self.zip_select_btn.connect("clicked", self.on_zip_select_clicked)
        self.unzip_widgets.attach(self.zip_select_btn, 0, 0, 1, 1)
        self.zip_selected_label = Gtk.Label(label="(선택 안됨)")
        self.unzip_widgets.attach(self.zip_selected_label, 1, 0, 2, 1)

        self.folder_select_btn = Gtk.Button(label="압축 해제 폴더 선택")
        self.folder_select_btn.connect("clicked", self.on_folder_select_clicked)
        self.unzip_widgets.attach(self.folder_select_btn, 0, 1, 1, 1)
        self.folder_selected_label = Gtk.Label(label="(선택 안됨)")
        self.unzip_widgets.attach(self.folder_selected_label, 1, 1, 2, 1)

        self.pw_entry_unzip = Gtk.Entry()
        self.pw_entry_unzip.set_visibility(False)
        self.pw_entry_unzip.set_placeholder_text("비밀번호 (선택 사항)")
        self.unzip_widgets.attach(self.pw_entry_unzip, 0, 2, 3, 1)

        # 압축 관련
        self.zip_widgets = Gtk.Grid(column_spacing=10, row_spacing=10)
        grid.attach(self.zip_widgets, 0, 1, 3, 1)
        self.zip_widgets.hide()

        self.compress_files = []
        self.compress_btn = Gtk.Button(label="압축할 파일 선택")
        self.compress_btn.connect("clicked", self.on_file_select_clicked)
        self.zip_widgets.attach(self.compress_btn, 0, 0, 1, 1)
        self.compress_label = Gtk.Label(label="(선택 안됨)")
        self.zip_widgets.attach(self.compress_label, 1, 0, 2, 1)

        self.save_btn = Gtk.Button(label="ZIP 저장 위치 선택")
        self.save_btn.connect("clicked", self.on_save_select_clicked)
        self.zip_widgets.attach(self.save_btn, 0, 1, 1, 1)
        self.save_label = Gtk.Label(label="(선택 안됨)")
        self.zip_widgets.attach(self.save_label, 1, 1, 2, 1)

        self.pw_entry_zip = Gtk.Entry()
        self.pw_entry_zip.set_visibility(False)
        self.pw_entry_zip.set_placeholder_text("비밀번호 (선택 사항)")
        self.zip_widgets.attach(self.pw_entry_zip, 0, 2, 3, 1)

        btn = Gtk.Button(label="실행")
        btn.connect("clicked", self.run)
        grid.attach(btn, 0, 2, 3, 1)

        self.log = Gtk.TextView()
        self.log.set_editable(False)
        self.log_buf = self.log.get_buffer()
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.add(self.log)
        grid.attach(scroll, 0, 3, 3, 1)

        self.q = None
        self.p = None

        self.selected_zip_paths = []
        self.selected_extract_folder = None
        self.selected_compress_files = []
        self.selected_save_path = None

    def on_zip_select_clicked(self, button):
        dialog = Gtk.FileChooserDialog(title="ZIP 파일 선택", parent=self, action=Gtk.FileChooserAction.OPEN)
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
         Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        dialog.set_select_multiple(True)
        zip_filter = Gtk.FileFilter()
        zip_filter.add_mime_type("application/zip")
        dialog.add_filter(zip_filter)

        result = dialog.run() 
        if result == Gtk.ResponseType.OK:
            self.selected_zip_paths = dialog.get_filenames()
            names = [os.path.basename(p) for p in self.selected_zip_paths]
            self.zip_selected_label.set_text(names[0]+"... ("+str(len(names))+"개"+")"  )
        elif result == Gtk.ResponseType.CANCEL:
            dialog.destroy()
        dialog.destroy()

    def on_folder_select_clicked(self, button):
        dialog = Gtk.FileChooserDialog(title="압축 해제 폴더 선택", parent=self, action=Gtk.FileChooserAction.SELECT_FOLDER)
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
         Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        if dialog.run() == Gtk.ResponseType.OK:
            self.selected_extract_folder = dialog.get_filename()
            self.folder_selected_label.set_text(self.selected_extract_folder)
        dialog.destroy()

    def on_file_select_clicked(self, button):
        dialog = Gtk.FileChooserDialog(title="파일 선택", parent=self, action=Gtk.FileChooserAction.OPEN)
        file_filter_allow_all = Gtk.FileFilter()
        file_filter_allow_all.set_name("All Files")
        file_filter_allow_all.add_pattern("*")
        custom_opener = Gtk.Button(label="열기")
        def force_load_folder_or_files(event):
            self.selected_compress_files = dialog.get_filenames()
            names = [os.path.basename(f) for f in self.selected_compress_files]
            self.compress_label.set_text(names[0]+"... ("+str(len(names))+"개"+")"  )
            dialog.destroy()
        custom_opener.connect("clicked", force_load_folder_or_files)
        dialog.add_filter(file_filter_allow_all)
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        box = dialog.get_action_area()
        box.set_orientation(Gtk.Orientation.HORIZONTAL)
        box.add(custom_opener)
        dialog.show_all()
        dialog.set_select_multiple(True)
        if dialog.run() == Gtk.ResponseType.CANCEL:
            dialog.destroy()

    def on_save_select_clicked(self, button):
        dialog = Gtk.FileChooserDialog(title="ZIP 저장 위치", parent=self, action=Gtk.FileChooserAction.SAVE)
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
         Gtk.STOCK_SAVE, Gtk.ResponseType.OK)
        dialog.set_current_name("archive.zip")
        if dialog.run() == Gtk.ResponseType.OK:
            self.selected_save_path = dialog.get_filename()
            self.save_label.set_text(self.selected_save_path)
        dialog.destroy()

    def on_mode_changed(self, combo):
        if combo.get_active_text() == "압축 해제":
            self.unzip_widgets.show_all()
            self.zip_widgets.hide()
        else:
            self.zip_widgets.show_all()
            self.unzip_widgets.hide()

    def run(self, widget):
        self.q = Queue()
        mode = self.mode_combo.get_active_text()

        if mode == "압축 해제":
            if not self.selected_zip_paths:
                self.log_write("[!] ZIP 파일 선택 필요")
                return
            if not self.selected_extract_folder:
                self.log_write("[!] 압축 해제 폴더 선택 필요")
                return
            pw = self.pw_entry_unzip.get_text()
            for zip_path in self.selected_zip_paths:
                p = Process(target=extract_zip, args=(zip_path, self.selected_extract_folder, pw, self.q))
                p.start()
                GLib.timeout_add(100, self.poll_q, p)

        else:
            if not self.selected_compress_files:
                self.log_write("[!] 압축할 파일 선택 필요")
                return
            if not self.selected_save_path:
                self.log_write("[!] 저장 경로 선택 필요")
                return
            pw = self.pw_entry_zip.get_text()
            self.p = Process(target=compress_zip, args=(self.selected_compress_files, self.selected_save_path, pw, self.q))
            self.p.start()
            GLib.timeout_add(100, self.poll_q, self.p)

    def poll_q(self, process):
        if self.q is None:
            return False
        while not self.q.empty():
            m = self.q.get()
            if m == ":::DONE:::":
                self.log_write("[*] 완료")
                process.join()
                return False
            self.log_write(m)
        return True

    def log_write(self, text):
        end = self.log_buf.get_end_iter()
        self.log_buf.insert(end, text + "\n")

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.set_start_method("spawn")
    app = ZipApp()

    app.connect("destroy", Gtk.main_quit)
    app.show_all()
    if app.mode_combo.get_active_text() != "압축":
        app.zip_widgets.hide()
    else:
        app.unzip_widgets.hide()

    if len(sys.argv) > 1:
        zip_files = [p for p in sys.argv[1:] if p.lower().endswith(".zip")]
        other_files = [p for p in sys.argv[1:] if not p.lower().endswith(".zip")]

        if zip_files and not other_files:
            app.mode_combo.set_active(0)  
            app.selected_zip_paths = zip_files
            names = [os.path.basename(p) for p in zip_files]
            app.zip_selected_label.set_text(names[0]+"... ("+str(len(names))+"개"+")"  )
        elif other_files:
            app.mode_combo.set_active(1) 
            app.selected_compress_files = other_files
            names = [os.path.basename(p) for p in other_files]
            app.compress_label.set_text(names[0]+"... ("+str(len(names))+"개"+")"  )

    Gtk.main()

