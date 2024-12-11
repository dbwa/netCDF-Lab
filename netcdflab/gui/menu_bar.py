from PyQt6.QtWidgets import QMenuBar, QMenu, QMessageBox
from PyQt6.QtGui import QAction
import json
import os
import platform
import sys

from netcdflab.utils.translations import Translator, Language

class MenuBar(QMenuBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.translator = Translator()
        self.has_storage_access = True  # Flag pour indiquer si on peut stocker l'historique
        
        # Menu Fichier
        self.file_menu = QMenu(self.translator.get_text("file_menu"), self)
        self.file_menu.addAction(self.translator.get_text("open"), self.parent.open_file)
        self.save_action = self.file_menu.addAction(self.translator.get_text("save_all"), 
                                                self.parent.save_all_files)
        self.save_action.setEnabled(False)
            
        self.file_menu.addSeparator()
        
        # Sous-menu Fichiers récents
        self.recent_menu = QMenu(self.translator.get_text("recent_files"), self.file_menu)
        self.file_menu.addMenu(self.recent_menu)
        
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.translator.get_text("export_macro"), self.parent.export_macro)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.translator.get_text("close_all"), self.parent.close_all_files)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.translator.get_text("quit"), self.parent.close)
        
        # Menu Edition
        edit_menu = QMenu(self.translator.get_text("edit_menu"), self)
        edit_menu.addAction(self.translator.get_text("copy"))
        edit_menu.addAction(self.translator.get_text("paste"))
        edit_menu.addAction(self.translator.get_text("delete"))
        
        # Menu Aide
        help_menu = QMenu(self.translator.get_text("help_menu"), self)
        help_menu.addAction(self.translator.get_text("about"), self.show_about)
        
        # Menu Langue (un seul menu)
        self.language_menu = QMenu(self.translator.get_text("language_menu"), self)
        self.language_actions = {}  # Pour stocker les actions de langue
        
        # Ajouter les menus
        self.addMenu(self.file_menu)
        self.addMenu(edit_menu)
        self.addMenu(help_menu)
        self.addMenu(self.language_menu)  # Un seul menu langue
        
        # Charger l'historique
        self.load_recent_files()
        
        # Menu Langue
        language_menu = QMenu(self.translator.get_text("language_menu"), self)
        
        # Ajouter les langues disponibles
        for lang in Language:
            action = self.language_menu.addAction(lang.value.upper())
            action.setCheckable(True)
            action.setChecked(self.translator.current_language == lang)
            action.triggered.connect(lambda checked, l=lang: self.change_language(l))
            self.language_actions[lang] = action
        
        # Ajouter le menu langue
        #self.addMenu(language_menu)
        
    def change_language(self, language: Language):
        """Change la langue de l'application"""
        # Décocher toutes les actions sauf celle sélectionnée
        for lang, action in self.language_actions.items():
            action.setChecked(lang == language)
        
        self.translator.set_language(language)
        self.translator.save_preferences(self.get_app_data_path())
        
        # Mettre à jour l'interface
        self.parent.retranslate_ui()

    def get_app_data_path(self):
        """Obtenir le chemin du dossier de données de l'application selon l'OS"""
        try:
            app_name = 'NetCDFViewer'
            
            if platform.system() == 'Windows':
                base_path = os.getenv('LOCALAPPDATA')
                if base_path is None:
                    base_path = os.path.join(os.path.expanduser('~'), 'AppData', 'Local')
                app_path = os.path.join(base_path, app_name)
                
            elif platform.system() == 'Darwin':
                app_path = os.path.join(os.path.expanduser('~'), 
                                      'Library', 'Application Support', app_name)
                
            else:  # Linux et autres Unix
                xdg_data_home = os.getenv('XDG_DATA_HOME', 
                                        os.path.join(os.path.expanduser('~'), '.local', 'share'))
                app_path = os.path.join(xdg_data_home, app_name)
            
            # Tester si on peut écrire dans le dossier
            if not os.path.exists(app_path):
                os.makedirs(app_path)
            
            # Test d'écriture
            test_file = os.path.join(app_path, 'test_write')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            
            return app_path
            
        except (OSError, IOError) as e:
            self.has_storage_access = False
            return None

    def load_recent_files(self):
        """Charger l'historique des fichiers récents"""
        self.recent_files = []
        
        try:
            app_path = self.get_app_data_path()
            if app_path is None:
                return
                
            history_file = os.path.join(app_path, 'recent_files.json')
            if os.path.exists(history_file):
                with open(history_file, 'r') as f:
                    self.recent_files = json.load(f)
                    # Filtrer les fichiers qui n'existent plus
                    self.recent_files = [f for f in self.recent_files if os.path.exists(f)]
                    
        except Exception as e:
            print(f"Erreur lors du chargement de l'historique: {e}")
            self.recent_files = []
            
        self.update_recent_menu()
        
    def save_recent_files(self):
        """Sauvegarder l'historique des fichiers récents"""
        if not self.has_storage_access:
            return
            
        try:
            app_path = self.get_app_data_path()
            if app_path is None:
                return
                
            history_file = os.path.join(app_path, 'recent_files.json')
            with open(history_file, 'w') as f:
                json.dump(self.recent_files, f)
        except Exception as e:
            print(f"Erreur lors de la sauvegarde de l'historique: {e}")
            self.has_storage_access = False  # Désactiver pour les futures tentatives
    
    def add_recent_file(self, filename):
        """Ajouter un fichier à l'historique"""
        if not self.has_storage_access:
            return
            
        filename = os.path.abspath(filename)
        if filename in self.recent_files:
            self.recent_files.remove(filename)
        self.recent_files.insert(0, filename)
        self.recent_files = self.recent_files[:10]
        self.update_recent_menu()
        self.save_recent_files()
    
    def update_recent_menu(self):
        """Mettre à jour le menu des fichiers récents"""
        self.recent_menu.clear()
        
        if not self.recent_files:
            action = QAction(self.translator.get_text("no_recent_files"), self)
            action.setEnabled(False)
            self.recent_menu.addAction(action)
            return
            
        # Ajouter les fichiers récents existants
        for filename in self.recent_files:
            if os.path.exists(filename):
                action = QAction(os.path.basename(filename), self)
                action.setStatusTip(filename)
                action.triggered.connect(lambda checked, f=filename: self.parent.data_panel.load_netcdf(f))
                self.recent_menu.addAction(action)
        
        if self.recent_files:
            self.recent_menu.addSeparator()
            clear_action = QAction(self.translator.get_text("clear_history"), self)
            clear_action.triggered.connect(self.clear_recent_files)
            self.recent_menu.addAction(clear_action)
    
    def clear_recent_files(self):
        """Effacer l'historique des fichiers récents"""
        self.recent_files = []
        self.update_recent_menu()
        self.save_recent_files()
    
    def update_save_action(self, has_files):
        """Activer/désactiver le bouton sauvegarder"""
        self.save_action.setEnabled(has_files)
    
    def show_about(self):
        """Afficher la fenêtre À propos"""
        QMessageBox.about(
            self, 
            self.translator.get_text("about_title"),
            self.translator.get_text("about_text")
        )

    def retranslate_ui(self):
        """Mettre à jour les textes après un changement de langue"""
        # Mettre à jour les menus principaux
        self.file_menu.setTitle(self.translator.get_text("file_menu"))
        self.recent_menu.setTitle(self.translator.get_text("recent_files"))
        
        # Mettre à jour les actions du menu Fichier
        # Recréer toutes les actions avec les nouveaux textes
        self.file_menu.clear()
        self.file_menu.addAction(self.translator.get_text("open"), self.parent.open_file)
        self.save_action = self.file_menu.addAction(self.translator.get_text("save_all"), 
                                                self.parent.save_all_files)
        self.save_action.setEnabled(False)
        
        self.file_menu.addSeparator()
        self.file_menu.addMenu(self.recent_menu)
        self.file_menu.addSeparator()
        
        self.file_menu.addAction(self.translator.get_text("export_macro"), self.parent.export_macro)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.translator.get_text("close_all"), self.parent.close_all_files)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.translator.get_text("quit"), self.parent.close)
        
        # Mettre à jour le menu des fichiers récents
        self.update_recent_menu()