import sys
import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                                 QComboBox, QPushButton, QLabel, QSpinBox,
                                 QScrollArea, QMenu, QInputDialog, QLineEdit,
                                 QFileDialog, QMessageBox, QApplication)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
import numpy as np
from datetime import datetime, timedelta

from netcdflab.utils.translations import Translator

class DimensionSelector(QWidget):
    def __init__(self, name, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.label = QLabel(name)
        self.combo = QComboBox()
        
        layout.addWidget(self.label)
        layout.addWidget(self.combo)

class VisualizationPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.translator = Translator()
        self.layout = QVBoxLayout(self)
        
        # Scroll area pour les contrôles
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        self.controls_layout = QVBoxLayout(scroll_widget)
        scroll.setWidget(scroll_widget)
        
        # Layout pour les sélecteurs de dimensions
        self.dim_selectors = {}
        
        # Layout pour les options de visualisation
        viz_options = QHBoxLayout()
        
        # Ajouter un sélecteur de fichier
        self.file_selector = QComboBox()
        self.file_selector.currentTextChanged.connect(self.file_changed)
        viz_options.insertWidget(0, QLabel(self.translator.get_text("file") + ":"))
        viz_options.insertWidget(1, self.file_selector)
        
        # Sélecteur de variable
        self.var_selector = QComboBox()
        self.var_selector.currentIndexChanged.connect(self.variable_changed)
        viz_options.addWidget(QLabel(self.translator.get_text("variable") + ":"))
        viz_options.addWidget(self.var_selector)
        
        # Colormap
        self.colormap_selector = QComboBox()
        self.colormap_selector.addItems(['viridis', 'plasma', 'inferno', 'magma'])
        self.colormap_selector.currentTextChanged.connect(self.update_plot)
        viz_options.addWidget(QLabel(self.translator.get_text("colormap") + ":"))
        viz_options.addWidget(self.colormap_selector)
        
        self.controls_layout.addLayout(viz_options)
        
        # Ajouter le scroll area au layout principal
        self.layout.addWidget(scroll)
        
        # Figure matplotlib avec barre d'outils
        self.figure = Figure(figsize=(8, 6))
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        
        # Connecter le menu contextuel
        self.canvas.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.canvas.customContextMenuRequested.connect(self.show_plot_context_menu)
        
        # Stocker le titre actuel
        self.current_title = ""
        
        self.layout.addWidget(self.toolbar)
        self.layout.addWidget(self.canvas)
        
        # Données
        self.dataset = None
        self.current_var = None
        
        # Dictionnaire des datasets
        self.datasets = {}  # filename: dataset
        
        self.current_filename = None
        
    def update_dataset(self, dataset, filename):
        """Mettre à jour ou ajouter un dataset"""
        
        self.datasets[filename] = dataset
        
        # Mettre à jour le sélecteur de fichiers
        current = self.file_selector.currentText()
        
        self.file_selector.clear()
        self.file_selector.addItems(sorted(self.datasets.keys()))
        
        # Restaurer la sélection ou sélectionner le nouveau fichier
        if current in self.datasets:
            self.file_selector.setCurrentText(current)
        else:
            self.file_selector.setCurrentText(filename)
            
        self.current_filename = filename
        
    def get_dimension_values(self, dim_name):
        """Récupérer les valeurs d'une dimension, y compris pour les variables de type caractère"""
        if dim_name not in self.dataset.dims:
            return []
            
        # Chercher une variable qui pourrait contenir les noms pour cette dimension
        for var_name, var in self.dataset.variables.items():
            if dim_name in var.dims and var.dtype.kind in ['S', 'U']:  # Variables de type caractère
                if len(var.dims) == 2 and 'name_strlen' in var.dims:  # Cas spécial pour les tableaux de chaînes
                    # Convertir le tableau 2D de caractères en liste de chaînes
                    values = [''.join(row.astype(str)).strip() for row in var.values]
                    return values
                elif len(var.dims) == 1:
                    return [str(v).strip() for v in var.values]
                    
        # Si aucune variable de nom n'est trouvée, utiliser les indices
        return [str(i) for i in range(self.dataset.dims[dim_name])]
            
    def variable_changed(self):
        """Gérer le changement de variable"""
        if self.dataset is None or self.var_selector.currentText() == '':
            return
            
        # Récupérer la variable sélectionnée
        var_name = self.var_selector.currentText()
        var = self.dataset[var_name]
        self.current_var = var_name
        
        # Déconnecter temporairement les signaux
        for selector in self.dim_selectors.values():
            try:
                selector.combo.currentIndexChanged.disconnect()
            except:
                pass
        
        # Nettoyer les anciens sélecteurs
        for selector in self.dim_selectors.values():
            selector.setParent(None)
        self.dim_selectors.clear()
        
        # Créer les sélecteurs pour chaque dimension
        for dim_name in var.dims:
            selector = DimensionSelector(dim_name)
            self.dim_selectors[dim_name] = selector
            self.controls_layout.addWidget(selector)
            
            # Remplir le sélecteur avec les valeurs
            if dim_name in self.dataset.dims:
                values = self.get_dimension_values(dim_name)
                selector.combo.addItems(values)
                selector.combo.currentIndexChanged.connect(self.update_plot)
        
        # Mettre à jour le graphique
        self.update_plot()
            
    def update_plot(self):
        """Mettre à jour le graphique"""
        if self.dataset is None or self.current_var is None:
            return
        
        var = self.dataset[self.current_var]
        
        # Créer un dictionnaire des indices pour chaque dimension
        selection = {}
        for dim_name, selector in self.dim_selectors.items():
            selection[dim_name] = selector.combo.currentIndex()
        
        # Adapter l'affichage selon le nombre de dimensions
        ndims = len(var.dims)
        
        if ndims == 0:  # Variable scalaire
            self.plot_scalar(var)
        elif ndims == 1:  # Variable 1D
            self.plot_1d(var)
        elif ndims == 2:  # Variable 2D (carte ou autre)
            self.plot_2d(var)
        else:  # Variables avec plus de dimensions
            # Extraire les deux dernières dimensions pour l'affichage
            plot_dims = list(var.dims)[-2:]
            
            # Créer la sélection pour extraire les données
            for dim in var.dims:
                if dim not in plot_dims:
                    var = var.isel({dim: selection[dim]})
                    
            # Extraire les données et les coordonnées
            data = var.values
            x_coords = self.dataset[plot_dims[1]].values
            y_coords = self.dataset[plot_dims[0]].values
            
            self.plot_data(data, x_coords, y_coords, plot_dims)

    def plot_scalar(self, var):
        """Afficher une variable scalaire"""
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        
        # Afficher la valeur comme texte
        ax.text(0.5, 0.5, f"Valeur: {var.values.item()}", 
                horizontalalignment='center', verticalalignment='center')
        ax.set_axis_off()
        
        self.current_title = f"Valeur de {var.name}"
        ax.set_title(self.current_title)
        
        self.canvas.draw()

    def plot_1d(self, var):
        """Afficher une variable 1D"""
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        
        # Créer l'axe x (indices ou coordonnées si disponibles)
        dim_name = var.dims[0]
        if dim_name in self.dataset:
            x = self.dataset[dim_name].values
        else:
            x = np.arange(len(var))
        
        # Tracer la ligne
        ax.plot(x, var.values)
        
        # Labels
        ax.set_xlabel(dim_name)
        ax.set_ylabel(var.name)
        if hasattr(var, 'units'):
            ax.set_ylabel(f"{var.name} ({var.units})")
        
        ax.grid(True)
        self.current_title = f"Variable {var.name}"
        ax.set_title(self.current_title)
        
        self.canvas.draw()

    def plot_2d(self, var):
        """Afficher une variable 2D"""
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        
        # Extraire les dimensions
        dim_names = list(var.dims)
        
        # Obtenir les coordonnées
        if dim_names[1] in self.dataset:
            x_coords = self.dataset[dim_names[1]].values
        else:
            x_coords = np.arange(var.shape[1])
        
        if dim_names[0] in self.dataset:
            y_coords = self.dataset[dim_names[0]].values
        else:
            y_coords = np.arange(var.shape[0])
        
        # Créer le graphique
        im = ax.pcolormesh(x_coords, y_coords, var.values,
                          cmap=self.colormap_selector.currentText(),
                          shading='auto')
        
        # Ajouter une barre de couleur
        units = var.attrs.get('units', '')
        self.figure.colorbar(im, ax=ax, label=units)
        
        # Configurer les axes
        ax.set_xlabel(dim_names[1])
        ax.set_ylabel(dim_names[0])
        self.current_title = var.name
        ax.set_title(self.current_title)
        
        self.canvas.draw()

    def plot_data(self, data, x_coords, y_coords, dims):
        """Tracer les données"""
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        
        # Créer le graphique
        im = ax.pcolormesh(x_coords, y_coords, data,
                          cmap=self.colormap_selector.currentText(),
                          shading='auto')
        
        # Ajouter une barre de couleur
        var = self.dataset[self.current_var]
        units = var.attrs.get('units', '')
        self.figure.colorbar(im, ax=ax, label=units)
        
        # Configurer les axes
        ax.set_xlabel(dims[1])
        ax.set_ylabel(dims[0])
        
        # Titre
        title_parts = [self.current_var]
        for dim_name, selector in self.dim_selectors.items():
            if dim_name not in dims:
                title_parts.append(f"{dim_name}: {selector.combo.currentText()}")
        self.current_title = ' | '.join(title_parts)
        ax.set_title(self.current_title)
        
        self.canvas.draw()
        
    def file_changed(self):
        """Gérer le changement de fichier"""
        filename = self.file_selector.currentText()
        if filename in self.datasets:
            self.dataset = self.datasets[filename]
            
            # Mettre à jour le sélecteur de variables
            self.var_selector.clear()
            self.var_selector.addItems(sorted(self.dataset.variables.keys()))
            
            # Sélectionner la première variable si disponible
            if self.var_selector.count() > 0:
                self.var_selector.setCurrentIndex(0)
            else:
                self.variable_changed()  # Nettoyer l'affichage si pas de variables

    def show_plot_context_menu(self, pos):
        """Afficher le menu contextuel pour le graphique"""
        menu = QMenu(self)
        
        # Option pour modifier le titre
        edit_title_action = menu.addAction(self.translator.get_text("edit_title"))
        edit_title_action.triggered.connect(self.edit_plot_title)
        
        # Option pour exporter l'image
        export_submenu = QMenu(self.translator.get_text("export_image"), menu)
        export_png = export_submenu.addAction("PNG")
        export_svg = export_submenu.addAction("SVG")
        export_pdf = export_submenu.addAction("PDF")
        menu.addMenu(export_submenu)
        
        # Options de personnalisation
        customize_submenu = QMenu(self.translator.get_text("customize"), menu)
        toggle_grid = customize_submenu.addAction(self.translator.get_text("toggle_grid"))
        toggle_grid.setCheckable(True)
        
        # Vérifier l'état de la grille
        ax = self.figure.gca()
        grid_visible = any(line.get_visible() for line in ax.get_xgridlines() + ax.get_ygridlines())
        toggle_grid.setChecked(grid_visible)
        
        # Option pour ajuster les limites automatiquement
        auto_scale = customize_submenu.addAction("Ajuster l'échelle")
        menu.addMenu(customize_submenu)
        
        # Connecter les actions
        export_png.triggered.connect(lambda: self.export_plot("png"))
        export_svg.triggered.connect(lambda: self.export_plot("svg"))
        export_pdf.triggered.connect(lambda: self.export_plot("pdf"))
        toggle_grid.triggered.connect(self.toggle_grid)
        auto_scale.triggered.connect(self.auto_scale)
        
        menu.exec(self.canvas.mapToGlobal(pos))

    def edit_plot_title(self):
        """Modifier le titre du graphique"""
        current_title = self.current_title or self.figure.gca().get_title()
        new_title, ok = QInputDialog.getText(
            self,
            self.translator.get_text("edit_title"),
            self.translator.get_text("new_title") + ":",
            QLineEdit.EchoMode.Normal,
            current_title
        )
        
        if ok:
            self.current_title = new_title
            self.figure.gca().set_title(new_title)
            self.canvas.draw()

    def export_plot(self, format_):
        """Exporter le graphique dans différents formats"""
        default_name = f"{self.translator.get_text('plot')}.{format_}"
        filters = {
            "png": self.translator.get_text("png_files"),
            "svg": self.translator.get_text("svg_files"),
            "pdf": self.translator.get_text("pdf_files")
        }
        
        filename, _ = QFileDialog.getSaveFileName(
            self,
            self.translator.get_text("export_plot"),
            default_name,
            filters[format_]
        )
        
        if filename:
            try:
                self.figure.savefig(filename, format=format_, bbox_inches='tight', dpi=300)
                QMessageBox.information(
                    self, 
                    self.translator.get_text("success"),
                    self.translator.get_text("export_success")
                )
            except Exception as e:
                QMessageBox.critical(
                    self, 
                    self.translator.get_text("error"),
                    self.translator.get_text("export_error", str(e))
                )

    def toggle_grid(self):
        """Activer/désactiver la grille"""
        ax = self.figure.gca()
        ax.grid(not ax.grid())
        self.canvas.draw()

    def auto_scale(self):
        """Ajuster automatiquement l'échelle"""
        self.figure.gca().autoscale()
        self.canvas.draw()

    def handle_visualization_request(self, filename, var_name, dim_name, index):
        """Gérer une demande de visualisation depuis le DataPanel"""
        
        # S'assurer que le dataset est disponible
        if filename not in self.datasets:
            print(f"Dataset {filename} non trouvé")
            return
        
        # Changer de fichier si nécessaire
        if self.file_selector.currentText() != filename:
            self.file_selector.setCurrentText(filename)
            QApplication.processEvents()
        
        # Sélectionner la variable
        var_index = self.var_selector.findText(var_name)
        if var_index >= 0:
            self.var_selector.setCurrentIndex(var_index)
            QApplication.processEvents()
            
            # Mettre à jour l'index de la dimension demandée
            if dim_name and index is not None:
                if dim_name in self.dim_selectors:
                    selector = self.dim_selectors[dim_name]
                    if 0 <= index < selector.combo.count():
                        selector.combo.setCurrentIndex(index)
                        # Pas besoin d'appeler update_plot() car le signal currentIndexChanged le fera

    def retranslate_ui(self):
        """Mettre à jour les textes après un changement de langue"""
        # Mettre à jour les labels des sélecteurs
        for i, label_text in enumerate(["file", "variable", "colormap"]):
            label_widget = self.controls_layout.itemAt(0).layout().itemAt(i * 2).widget()
            if isinstance(label_widget, QLabel):
                label_widget.setText(self.translator.get_text(label_text) + ":")