from enum import Enum
import json
import os

class Language(Enum):
    FRENCH = "fr"
    ENGLISH = "en"

class Translator:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.initialized = True
            self.current_language = Language.FRENCH
            self.translations = {
                Language.FRENCH: self._get_french_translations(),
                Language.ENGLISH: self._get_english_translations()
            }
    
    def _get_french_translations(self):
        """Retourne toutes les traductions en français"""
        return {
            # Interface générale
            "app_title": "NetCDF Lab",
            "warning": "Attention",
            "error": "Erreur",
            "success": "Succès",
            "cancel": "Annuler",
            
            # Menu principal
            "file_menu": "Fichier",
            "edit_menu": "Edition",
            "help_menu": "Aide",
            "language_menu": "Langue",
            
            # Menu Fichier
            "open": "Ouvrir",
            "save": "Sauvegarder",
            "save_all": "Sauvegarder tout",
            "save_as": "Sauvegarder sous...",
            "recent_files": "Fichiers récents",
            "no_recent_files": "(Aucun fichier récent)",
            "clear_history": "Effacer l'historique",
            "export_macro": "Exporter Macro",
            "close": "Fermer",
            "close_all": "Fermer tout",
            "quit": "Quitter",
            
            # Menu Edition
            "copy": "Copier",
            "paste": "Coller",
            "delete": "Supprimer",
            "rename": "Renommer",
            "duplicate": "Dupliquer",
            "delete_value": "Supprimer la valeur",
            
            # Panneau de données
            "netcdf_files": "Fichiers NetCDF",
            "dimensions": "Dimensions",
            "variables": "Variables",
            "values": "Valeurs",
            "attributes": "Attributs",
            "global_attributes": "Attributs globaux",
            "new_variable": "Nouvelle variable",
            
            # Panneau de visualisation
            "file": "Fichier",
            "variable": "Variable",
            "colormap": "Palette de couleurs",
            "visualize": "Visualiser",
            "plot": "graphique",
            "edit_title": "Modifier le titre",
            "new_title": "Nouveau titre",
            "customize": "Personnaliser",
            "toggle_grid": "Afficher/Masquer la grille",
            "auto_scale": "Ajuster l'échelle",
            
            # Export
            "export_image": "Exporter l'image",
            "export_plot": "Exporter le graphique",
            "png_files": "Images PNG (*.png)",
            "svg_files": "Images SVG (*.svg)",
            "pdf_files": "Documents PDF (*.pdf)",
            "export_success": "Image exportée avec succès !",
            "export_error": "Erreur lors de l'export : {}",
            
            # Messages
            "file_already_open": "Le fichier {} est déjà ouvert!",
            "error_loading_file": "Impossible de charger le fichier: {}",
            "save_success": "Fichier sauvegardé avec succès!",
            "save_error": "Erreur lors de la sauvegarde: {}",
            "unsaved_changes": "Les fichiers suivants ont des modifications non sauvegardées :\n\n{}\n\nVoulez-vous sauvegarder les modifications ?",
            "unsaved_changes_title": "Modifications non sauvegardées",
            "unsaved_changes_message": "Certains fichiers ont des modifications non sauvegardées. Voulez-vous les sauvegarder avant de quitter ?",
            "save_changes": "Sauvegarder les modifications",
            "discard_changes": "Ignorer les modifications",
            
            # À propos
            "about": "À propos",
            "about_title": "À propos de NetCDF Viewer",
            "about_text": """
            <h2>NetCDF Viewer</h2>
            <p>Version: 1.0</p>
            <p>Un outil de visualisation et d'édition de fichiers NetCDF.</p>
            <p>Développé par Robin Voitot</p>
            <p>© 2024 Tous droits réservés</p>
            """
        }
    
    def _get_english_translations(self):
        """Retourne toutes les traductions en anglais"""
        return {
            # General interface
            "app_title": "NetCDF Lab",
            "warning": "Warning",
            "error": "Error",
            "success": "Success",
            "cancel": "Cancel",
            
            # Main menu
            "file_menu": "File",
            "edit_menu": "Edit",
            "help_menu": "Help",
            "language_menu": "Language",
            
            # File menu
            "open": "Open",
            "save": "Save",
            "save_all": "Save All",
            "save_as": "Save as...",
            "recent_files": "Recent Files",
            "no_recent_files": "(No recent files)",
            "clear_history": "Clear History",
            "export_macro": "Export Macro",
            "close": "Close",
            "close_all": "Close All",
            "quit": "Quit",
            
            # Edit menu
            "copy": "Copy",
            "paste": "Paste",
            "delete": "Delete",
            "rename": "Rename",
            "duplicate": "Duplicate",
            "delete_value": "Delete Value",
            
            # Data panel
            "netcdf_files": "NetCDF Files",
            "dimensions": "Dimensions",
            "variables": "Variables",
            "values": "Values",
            "attributes": "Attributes",
            "global_attributes": "Global Attributes",
            "new_variable": "New Variable",
            
            # Visualization panel
            "file": "File",
            "variable": "Variable",
            "colormap": "Colormap",
            "visualize": "Visualize",
            "plot": "plot",
            "edit_title": "Edit Title",
            "new_title": "New title",
            "customize": "Customize",
            "toggle_grid": "Toggle Grid",
            "auto_scale": "Auto Scale",
            
            # Export
            "export_image": "Export Image",
            "export_plot": "Export Plot",
            "png_files": "PNG Images (*.png)",
            "svg_files": "SVG Images (*.svg)",
            "pdf_files": "PDF Documents (*.pdf)",
            "export_success": "Image exported successfully!",
            "export_error": "Export error: {}",
            
            # Messages
            "file_already_open": "File {} is already open!",
            "error_loading_file": "Unable to load file: {}",
            "save_success": "File saved successfully!",
            "save_error": "Error while saving: {}",
            "unsaved_changes": "The following files have unsaved changes:\n\n{}\n\nDo you want to save the changes?",
            "unsaved_changes_title": "Unsaved Changes",
            "unsaved_changes_message": "Some files have unsaved changes. Do you want to save them before quitting?",
            "save_changes": "Save Changes",
            "discard_changes": "Discard Changes",
            
            # About
            "about": "About",
            "about_title": "About NetCDF Viewer",
            "about_text": """
            <h2>NetCDF Viewer</h2>
            <p>Version: 1.0</p>
            <p>A tool for visualizing and editing NetCDF files.</p>
            <p>Developed by Robin Voitot</p>
            <p>© 2024 All rights reserved</p>
            """
        }
    
    def set_language(self, language: Language):
        """Change la langue courante"""
        self.current_language = language
        
    def get_text(self, key: str, *args) -> str:
        """Récupère le texte traduit pour la clé donnée"""
        text = self.translations[self.current_language].get(key, key)
        if args:
            return text.format(*args)
        return text
        
    def save_preferences(self, app_data_path: str):
        """Sauvegarde les préférences de langue"""
        try:
            if not os.path.exists(app_data_path):
                os.makedirs(app_data_path)
            
            prefs_file = os.path.join(app_data_path, 'preferences.json')
            with open(prefs_file, 'w') as f:
                json.dump({
                    'language': self.current_language.value
                }, f)
        except Exception as e:
            print(f"Erreur lors de la sauvegarde des préférences: {e}")
            
    def load_preferences(self, app_data_path: str):
        """Charge les préférences de langue"""
        try:
            prefs_file = os.path.join(app_data_path, 'preferences.json')
            if os.path.exists(prefs_file):
                with open(prefs_file, 'r') as f:
                    prefs = json.load(f)
                    lang_value = prefs.get('language')
                    if lang_value:
                        self.current_language = Language(lang_value)
        except Exception as e:
            print(f"Erreur lors du chargement des préférences: {e}")