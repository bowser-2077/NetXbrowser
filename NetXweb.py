import sys
import argparse
import subprocess
import sqlite3
from cryptography.fernet import Fernet
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtWebEngineWidgets import *
from PyQt5.QtGui import QKeySequence, QColor
import os

if sys.platform == "win32":
    import ctypes
    ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)


def debug_console():
    print("Successfully launched debug mode.")

# Générer une clé de cryptage pour Fernet
def generate_key():
    """Génère une clé de cryptage"""
    return Fernet.generate_key()

class PasswordManager(QWidget):
    def __init__(self, db_connection, encryption_key):
        super().__init__()

        self.db_connection = db_connection
        self.encryption_key = encryption_key
        self.cipher_suite = Fernet(encryption_key)

        self.setWindowTitle("Password Manager")
        self.setGeometry(100, 100, 400, 300)

        # Appliquer un thème sombre
        self.setStyleSheet("""
            QWidget { background-color: #2d2d2d; color: white; font-family: Arial, sans-serif; }
            QLineEdit { background-color: #444444; color: white; border-radius: 5px; padding: 5px; margin: 10px 0; }
            QPushButton { background-color: #555555; color: white; border-radius: 5px; padding: 8px 15px; }
            QPushButton:hover { background-color: #777777; }
            QListWidget { background-color: #444444; color: white; border-radius: 5px; padding: 10px; margin-bottom: 10px; }
        """)

        layout = QVBoxLayout()
        self.password_list = QListWidget()
        layout.addWidget(self.password_list)

        self.url_input = QLineEdit(self)
        self.url_input.setPlaceholderText("Website URL")
        layout.addWidget(self.url_input)

        self.password_input = QLineEdit(self)
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Password")
        layout.addWidget(self.password_input)

        self.add_button = QPushButton("Add Password", self)
        self.add_button.clicked.connect(self.add_password)
        layout.addWidget(self.add_button)

        self.clear_button = QPushButton("Clear All Passwords", self)
        self.clear_button.clicked.connect(self.clear_passwords)
        layout.addWidget(self.clear_button)

        self.setLayout(layout)
        self.load_passwords()

    def load_passwords(self):
        """Charge les mots de passe depuis la base de données"""
        cursor = self.db_connection.cursor()
        cursor.execute("SELECT url, password FROM passwords")
        rows = cursor.fetchall()

        if not rows:
            self.password_list.addItem("No passwords saved.")

        for url, encrypted_password in rows:
            decrypted_password = self.cipher_suite.decrypt(encrypted_password).decode("utf-8")
            self.password_list.addItem(f"{url}: {decrypted_password}")

    def add_password(self):
        """Ajoute un mot de passe"""
        url = self.url_input.text().strip()
        password = self.password_input.text().strip()

        if url and password:
            encrypted_password = self.cipher_suite.encrypt(password.encode("utf-8"))
            self.db_connection.cursor().execute("INSERT INTO passwords (url, password) VALUES (?, ?)", (url, encrypted_password))
            self.db_connection.commit()

            self.password_list.addItem(f"{url}: {password}")
            self.url_input.clear()
            self.password_input.clear()

    def clear_passwords(self):
        """Efface tous les mots de passe après confirmation"""
        reply = QMessageBox.question(self, "Clear Passwords", "Are you sure you want to delete all passwords?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            cursor = self.db_connection.cursor()
            cursor.execute("DELETE FROM passwords")
            self.db_connection.commit()
            self.password_list.clear()
            QMessageBox.information(self, "Passwords Cleared", "All passwords have been deleted.")

class Browser(QMainWindow):
    def __init__(self, debug_mode=False):
        super().__init__()

        self.setGeometry(100, 100, 1080, 1920)

        self.setWindowTitle("NetXweb Web Browser - V1")

        self.debug_mode = debug_mode

        self.setStyleSheet("""
            QMainWindow { background-color: #2d2d2d; color: white; }
            QTabWidget { background-color: #333333; border: 1px solid #444444; padding: 10px; }
            QLineEdit { background-color: #444444; color: white; border-radius: 5px; padding: 5px; margin: 10px 0; }
            QPushButton { background-color: #555555; color: white; border-radius: 5px; padding: 8px 15px; }
            QPushButton:hover { background-color: #777777; }
        """)

        self.tabs = QTabWidget(self)
        self.setCentralWidget(self.tabs)

        self.add_new_tab("Home Page")

        self.bar = QLineEdit(self)
        self.bar.returnPressed.connect(self.load_url)

        toolbar = self.addToolBar("Address Bar")
        toolbar.addWidget(self.bar)

        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)

        self.shortcut_new_tab = QShortcut(QKeySequence("Ctrl++"), self)
        self.shortcut_new_tab.activated.connect(self.add_new_tab_from_button)

        self.shortcut_reload = QShortcut(QKeySequence("Ctrl+R"), self)
        self.shortcut_reload.activated.connect(self.reload_page)

        self.db_connection = sqlite3.connect("passwords.db")
        self.db_connection.execute('''CREATE TABLE IF NOT EXISTS passwords (url TEXT, password BLOB)''')
        self.encryption_key = generate_key()
        self.password_manager = PasswordManager(self.db_connection, self.encryption_key)

        self.show()

    def reload_page(self):
        current_browser = self.get_current_browser()
        if current_browser:
            current_browser.reload()

    def add_new_tab(self, url):
        browser = QWebEngineView()
        browser.setUrl(QUrl(url))
        tab_index = self.tabs.addTab(browser, url)
        self.tabs.setCurrentIndex(tab_index)
        browser.urlChanged.connect(self.update_address_bar)

    def load_url(self):
        text = self.bar.text().strip()

        if text == "webnav://passwords":
            self.password_manager.show()
        elif text == "webnav://passwords:clear":
            self.clear_all_passwords()
        elif text == "webnav://debug":
            self.restart_with_debug()
        elif text.startswith("http://") or text.startswith("https://"):
            self.get_current_browser().setUrl(QUrl(text))
        else:
            search_url = f"https://www.google.com/search?q={text}"
            self.get_current_browser().setUrl(QUrl(search_url))

    def restart_with_debug(self):
        print("Restarting in debug mode")
        script_path = sys.argv[0]
        subprocess.Popen(["python", script_path, "--debug"])
        self.close()

    def clear_all_passwords(self):
        self.password_manager.clear_passwords()

    def get_current_browser(self):
        current_widget = self.tabs.currentWidget()
        if isinstance(current_widget, QWebEngineView):
            return current_widget
        return None
    
    def update_address_bar(self, url):
        self.bar.setText(url.toString())

    def close_tab(self, index):
        self.tabs.removeTab(index)

    def add_new_tab_from_button(self):
        self.add_new_tab("https://www.google.com/")

def main():
    # Analyse des arguments de ligne de commande
    parser = argparse.ArgumentParser(description="Lance le navigateur avec l'option --debug pour activer la console.")
    parser.add_argument('--debug', action='store_true', help="Activer le mode débogage avec la console.")
    args = parser.parse_args()

    # Si l'argument --debug est présent, affiche la console
    if args.debug:
        debug_console()

    # Lancer l'application PyQt
    app = QApplication(sys.argv)
    window = Browser(debug_mode=args.debug)
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
