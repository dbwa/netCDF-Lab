import sys
import os
from PyQt6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, 
                                 QVBoxLayout, QSplitter, QFileDialog, QMessageBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut, QDragEnterEvent, QDropEvent
from .data_panel import DataPanel
from .visualization_panel import VisualizationPanel
from .menu_bar import MenuBar

from netcdflab.utils.translations import Translator

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.translator = Translator()
        
        # Créer d'abord la barre de menu
        self.menu_bar = MenuBar(self)
        self.setMenuBar(self.menu_bar)
        
        # Maintenant on peut charger les préférences
        app_data_path = self.menu_bar.get_app_data_path()
        if app_data_path:
            self.translator.load_preferences(app_data_path)
        
        # Configurer le reste de l'interface
        self.setup_ui()

        # Signal de chargement de fichier
        self.data_panel.file_loaded.connect(self.menu_bar.add_recent_file)
        
    def setup_ui(self):
        """Configure l'interface utilisateur"""
        self.setWindowTitle(self.translator.get_text("app_title"))

        self.setWindowTitle("NetCDF Viewer")
        self.resize(1200, 800)
        
        # Activer le glisser-déposer sur la fenêtre principale
        self.setAcceptDrops(True)
        
        # Créer la barre de menu
        self.menu_bar = MenuBar(self)
        self.setMenuBar(self.menu_bar)
        
        # Widget principal
        main_widget = QWidget()
        main_widget.setAcceptDrops(True)  # Activer sur le widget principal
        self.setCentralWidget(main_widget)
        
        # Layout horizontal principal
        layout = QHBoxLayout(main_widget)
        
        # Splitter pour diviser l'écran
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setAcceptDrops(True)  # Activer sur le splitter
        
        # Panneau de données (gauche)
        self.data_panel = DataPanel()
        self.data_panel.setAcceptDrops(True)  # Activer sur le data_panel
        splitter.addWidget(self.data_panel)
        
        # Panneau de visualisation (droite)
        self.visualization_panel = VisualizationPanel()
        splitter.addWidget(self.visualization_panel)
        
        # Connecter les panneaux avec debug
        self.data_panel.dataset_loaded.connect(self.visualization_panel.update_dataset)
        self.data_panel.dataset_modified.connect(self.handle_dataset_modified)
        
        # Connexion explicite avec fonction lambda pour debug
        self.data_panel.visualization_requested.connect(
            lambda f, v, d, i: self._debug_visualization_request(f, v, d, i)
        )
        
        # Définir les tailles relatives des panneaux
        splitter.setSizes([400, 800])
        
        layout.addWidget(splitter)
        
        # Raccourcis clavier
        self.setup_shortcuts()
        
        # Fichier courant
        self.current_file = None
        
        # Activer le glisser-déposer
        self.setAcceptDrops(True)
        
        # Mettre à jour l'état initial du menu
        self.update_menu_state()
        
        # Connecter l'événement closeEvent
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        
    def retranslate_ui(self):
        """Met à jour les textes de l'interface après un changement de langue"""
        self.setWindowTitle(self.translator.get_text("app_title"))
        self.menu_bar.retranslate_ui()
        self.data_panel.retranslate_ui()
        self.visualization_panel.retranslate_ui()

    def setup_shortcuts(self):
        """Configurer les raccourcis clavier"""
        # Ctrl+S pour sauvegarder tout
        QShortcut(QKeySequence.StandardKey.Save, self, self.save_all_files)
        
        # Ctrl+N pour ouvrir un fichier (on utilise Open car il n'y a pas de StandardKey.New)
        QShortcut(QKeySequence.StandardKey.Open, self, self.open_file)
            
    def open_file(self):
        """Ouvrir un ou plusieurs fichiers"""
        file_names, _ = QFileDialog.getOpenFileNames(
            self,
            "Ouvrir des fichiers NetCDF",
            "",
            "NetCDF Files (*.nc);;All Files (*)"
        )
        for file_name in file_names:
            self.data_panel.load_netcdf(file_name)
            self.menu_bar.add_recent_file(file_name)
            
    def save_file(self):
        """Sauvegarder avec Ctrl+S"""
        if self.current_file:
            self.data_panel.save_netcdf(self.current_file)
        else:
            self.save_file_as()
            
    def save_file_as(self):
        """Sauvegarder sous"""
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Sauvegarder le fichier NetCDF",
            "",
            "NetCDF Files (*.nc);;All Files (*)"
        )
        if file_name:
            self.current_file = file_name
            self.data_panel.save_netcdf(file_name)
            
    def export_macro(self):
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Exporter la macro Python",
            "",
            "Python Files (*.py);;All Files (*)"
        )
        if file_name:
            self.data_panel.export_macro(file_name)
            
    def handle_dataset_modified(self, filename):
        """Gérer les modifications du dataset"""
        if filename in self.data_panel.open_files:
            dataset = self.data_panel.open_files[filename]
            self.visualization_panel.update_dataset(dataset, filename)
    
    def dragEnterEvent(self, event):
        """Gérer l'entrée d'un glisser-déposer"""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            # Accepter si au moins un fichier est .nc
            if any(url.toLocalFile().lower().endswith('.nc') for url in urls):
                event.accept()
            else:
                event.ignore()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        """Gérer le mouvement pendant le glisser-déposer"""
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        """Gérer la sortie du glisser-déposer"""
        event.accept()

    def dropEvent(self, event):
        """Gérer le dépôt d'un ou plusieurs fichiers"""
        urls = event.mimeData().urls()
        for url in urls:
            file_path = url.toLocalFile()
            if file_path.lower().endswith('.nc'):
                self.data_panel.load_netcdf(file_path)
                self.menu_bar.add_recent_file(file_path)
        event.accept()

    def save_all_files(self):
        """Sauvegarder tous les fichiers ouverts"""
        # Créer une liste des fichiers à sauvegarder avant de commencer
        files_to_save = [filename for filename in self.data_panel.open_files.keys()
                        if self.data_panel.is_modified.get(filename, False)]
        
        if not files_to_save:
            return True

        saved_files = []
        failed_files = []
        
        # Sauvegarder chaque fichier de la liste
        for filename in files_to_save:
            if filename in self.data_panel.open_files:  # Vérifier que le fichier existe toujours
                try:
                    self.data_panel.save_file(filename, show_success_message=False)  # Nouveau paramètre
                    saved_files.append(filename)
                except Exception as e:
                    failed_files.append((filename, str(e)))
        
        # Afficher un seul message récapitulatif
        if failed_files:
            error_message = "Erreurs lors de la sauvegarde :\n\n"
            for filename, error in failed_files:
                error_message += f"{filename}: {error}\n"
            QMessageBox.critical(self, "Erreur", error_message)
            return False
        elif saved_files:
            QMessageBox.information(self, "Succès", 
                f"{len(saved_files)} fichier(s) sauvegardé(s) avec succès!")
        
        return True
    
    def update_menu_state(self):
        """Mettre à jour l'état du menu"""
        has_files = len(self.data_panel.open_files) > 0
        self.menu_bar.update_save_action(has_files)
    
    def closeEvent(self, event):
        """Gérer la fermeture de l'application"""
        if self.check_unsaved_changes():
            event.accept()
        else:
            event.ignore()
    
    def check_unsaved_changes(self):
        """Vérifier s'il y a des modifications non sauvegardées"""
        modified_files = [filename for filename, modified in 
                         self.data_panel.is_modified.items() if modified]
        
        if modified_files:
            message = "Les fichiers suivants ont des modifications non sauvegardées :\n\n"
            message += "\n".join(modified_files)
            message += "\n\nVoulez-vous sauvegarder les modifications ?"
            
            reply = QMessageBox.question(
                self,
                "Modifications non sauvegardées",
                message,
                QMessageBox.StandardButton.Save |
                QMessageBox.StandardButton.Discard |
                QMessageBox.StandardButton.Cancel
            )
            
            if reply == QMessageBox.StandardButton.Save:
                return self.save_all_files()
            elif reply == QMessageBox.StandardButton.Cancel:
                return False
                
        return True
    
    def close_all_files(self):
        """Fermer tous les fichiers ouverts"""
        if not self.check_unsaved_changes():
            return False
            
        # Créer une copie de la liste des fichiers car elle va être modifiée
        files_to_close = list(self.data_panel.open_files.keys())
        
        for filename in files_to_close:
            if not self.data_panel.close_file(filename):
                return False
                
        return True
    
    def _debug_visualization_request(self, filename, var_name, dim_name, index):
        """Fonction de debug pour la visualisation"""
        print(f"\n=== Signal visualization_requested reçu dans MainWindow ===")
        print(f"Fichier: {filename}")
        print(f"Variable: {var_name}")
        print(f"Dimension: {dim_name}")
        print(f"Index: {index}")
        self.visualization_panel.handle_visualization_request(filename, var_name, dim_name, index)