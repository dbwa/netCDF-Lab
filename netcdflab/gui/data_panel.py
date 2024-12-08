from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTreeWidget, 
                           QTreeWidgetItem, QPushButton, QMenu,
                           QInputDialog, QMessageBox, QFileDialog,
                           QScrollArea, QSizePolicy)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor

import xarray as xr
import numpy as np
import pandas as pd
from datetime import datetime
import re
import cftime
import sys
import os
import tempfile
import shutil

from ..utils.translations import Translator

class EditableTreeWidget(QTreeWidget):
    def __init__(self):
        super().__init__()
        self.setEditTriggers(QTreeWidget.EditTrigger.DoubleClicked |
                            QTreeWidget.EditTrigger.EditKeyPressed)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F2:
            if self.currentItem():
                self.editItem(self.currentItem(), 0)
        else:
            super().keyPressEvent(event)


class DataPanel(QWidget):
    dataset_loaded = pyqtSignal(object, str)  # dataset, filename
    dataset_modified = pyqtSignal(str)  # filename
    visualization_requested = pyqtSignal(str, str, str, int)  # filename, var_name, dim_name, index
    
    def __init__(self):
        super().__init__()
        self.translator = Translator()
        self.layout = QVBoxLayout(self)
        
        # Un seul arbre pour tous les fichiers
        self.tree = EditableTreeWidget()
        self.tree.setHeaderLabels(["Fichiers NetCDF"])
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)
        self.tree.itemChanged.connect(self.handle_item_edit)
        
        self.layout.addWidget(self.tree)
        
        # Dictionnaire des datasets ouverts
        self.open_files = {}  # filename: dataset
        self.is_modified = {}  # filename: bool
        self.date_formats = {}  # (filename, var_name, index): format
        self._is_updating_tree = False

        # Activer le glisser-déposer
        self.setAcceptDrops(True)
        
        # Créer les icônes pour les états modifié/non-modifié
        self.modified_icon = self._create_dot_icon(QColor(74, 144, 226))  # Bleu
        self.unmodified_icon = self._create_dot_icon(QColor(255, 255, 255, 0))  # Transparent

        # Ajouter un flag pour éviter la récursion
        self._is_updating_icon = False

    def _create_dot_icon(self, color, size=12):
        """Créer une icône avec un point coloré"""
        pixmap = QPixmap(size, size)
        pixmap.fill(QColor(0, 0, 0, 0))  # Transparent
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, size-4, size-4)
        painter.end()
        
        return QIcon(pixmap)

    def load_netcdf(self, filename):
        """Charger un nouveau fichier NetCDF"""
        if filename in self.open_files:
            QMessageBox.warning(
                self, 
                self.translator.get_text("warning"),  # "Attention"
                self.translator.get_text("file_already_open", filename)
            )
            return
            
        try:
            # Ouvrir le dataset
            original_dataset = xr.open_dataset(filename)
            # Faire une copie et fermer l'original
            dataset = original_dataset.copy(deep=True)
            original_dataset.close()
                          
            self.open_files[filename] = dataset
            self.is_modified[filename] = False
            
            # Ajouter au même arbre
            self.add_file_to_tree(filename, dataset)
            
            self.dataset_loaded.emit(dataset, filename)
            
        except Exception as e:
            QMessageBox.critical(
                self, 
                self.translator.get_text("error"),  # "Erreur"
                self.translator.get_text("error_loading_file", str(e))
            )

    def decode_bytes(self, value):
        """Décoder une valeur bytes en string"""
        if isinstance(value, bytes):
            return value.decode('utf-8')
        return value
        
    def format_value(self, value):
        """Formater une valeur pour l'affichage"""
        if isinstance(value, bytes):
            return value.decode('utf-8')
        elif isinstance(value, (np.ndarray, list)) and len(value) > 0:
            if isinstance(value[0], bytes):
                return [v.decode('utf-8') for v in value]
        elif isinstance(value, np.datetime64):
            dt = pd.Timestamp(value).to_pydatetime()
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        return str(value).strip()
        
    def detect_date_format(self, value_str):
        """Détecter le format d'une date"""
        formats = [
            ('%Y-%m-%d %H:%M:%S', r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}'),
            ('%Y-%m-%d', r'\d{4}-\d{2}-\d{2}'),
            ('%Y%m%d', r'\d{8}'),
            ('%Y-%m-%d %H:%M', r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}')
        ]
        for fmt, pattern in formats:
            if re.match(pattern, value_str):
                return fmt
        return None
        
    def parse_value(self, value_str, dtype, original_format=None):
        """Convertir une chaîne en valeur selon le type"""
        if dtype.kind in ['U', 'S']:
            return value_str
        elif dtype.kind == 'M':
            try:
                if original_format:
                    dt = datetime.strptime(value_str, original_format)
                else:
                    fmt = self.detect_date_format(value_str)
                    if not fmt:
                        raise ValueError("Format de date non reconnu")
                    dt = datetime.strptime(value_str, fmt)
                return np.datetime64(dt)
            except ValueError as e:
                raise ValueError(f"Erreur de conversion de date: {str(e)}")
        elif dtype.kind == 'f':
            return float(value_str)
        elif dtype.kind in ['i', 'u']:
            return int(value_str)
        else:
            raise ValueError(f"Type non supporté: {dtype}")

    def parse_attribute(self, attr_str):
        """Parser une chaîne d'attribut 'nom: valeur'"""
        parts = attr_str.split(':', 1)
        if len(parts) != 2:
            raise ValueError("Format d'attribut invalide. Utilisez 'nom: valeur'")
        return parts[0].strip(), parts[1].strip()

    def add_file_to_tree(self, filename, dataset):
        """Ajouter un fichier à l'arbre"""
        self._is_updating_tree = True
        
        # Créer l'item racine pour ce fichier
        root_item = QTreeWidgetItem(self.tree)
        base_name = os.path.basename(filename)
        root_item.setText(0, base_name)
        root_item.setFlags(root_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        root_item.setData(0, Qt.ItemDataRole.UserRole, filename)
        
        # Informations sur le fichier
        info_item = QTreeWidgetItem(root_item)
        dims_info = ", ".join([f"{k}: {v}" for k, v in dataset.dims.items()])
        info_item.setText(0, f"{self.translator.get_text('dimensions')}: {dims_info}")
        info_item.setFlags(info_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        
        # Variables
        vars_item = QTreeWidgetItem(root_item)
        vars_item.setText(0, self.translator.get_text("variables"))
        vars_item.setFlags(vars_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        
        for var_name, var in dataset.variables.items():
            var_child = QTreeWidgetItem(vars_item)
            var_child.setText(0, var_name)
            var_child.setFlags(var_child.flags() | Qt.ItemFlag.ItemIsEditable)
            # Stocker le nom original de la variable
            var_child.setData(0, Qt.ItemDataRole.UserRole, var_name)
            
            # Info sur la variable
            info_child = QTreeWidgetItem(var_child)
            info_text = f"Dims: {var.dims}, Type: {var.dtype}"
            info_child.setText(0, info_text)
            info_child.setFlags(info_child.flags() & ~Qt.ItemFlag.ItemIsEditable)
            
            # Valeurs de la variable
            if var.size < 100 or var_name in dataset.dims:
                values_child = QTreeWidgetItem(var_child)
                values_child.setText(0, "Valeurs")
                values_child.setFlags(values_child.flags() & ~Qt.ItemFlag.ItemIsEditable)
                
                for i, val in enumerate(var.values):
                    val_item = QTreeWidgetItem(values_child)
                    formatted_val = self.format_value(val)
                    val_item.setText(0, f"[{i}]: {formatted_val}")
                    val_item.setFlags(val_item.flags() | Qt.ItemFlag.ItemIsEditable)
                    if var.dtype.kind == 'M':
                        fmt = self.detect_date_format(formatted_val)
                        self.date_formats[(filename, var_name, i)] = fmt
                    val_item.setData(0, Qt.ItemDataRole.UserRole, (i, var.dtype))
            
            # Attributs de la variable
            attrs_child = QTreeWidgetItem(var_child)
            attrs_child.setText(0, "Attributs")
            attrs_child.setFlags(attrs_child.flags() & ~Qt.ItemFlag.ItemIsEditable)
            
            for attr_name, attr_value in var.attrs.items():
                attr_item = QTreeWidgetItem(attrs_child)
                attr_item.setText(0, f"{attr_name}: {self.format_value(attr_value)}")
                attr_item.setFlags(attr_item.flags() | Qt.ItemFlag.ItemIsEditable)
        
        # Attributs globaux
        attrs_item = QTreeWidgetItem(root_item)
        attrs_item.setText(0, self.translator.get_text("global_attributes"))
        attrs_item.setFlags(attrs_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        
        for attr_name, attr_value in dataset.attrs.items():
            attr_child = QTreeWidgetItem(attrs_item)
            attr_child.setText(0, f"{attr_name}: {self.format_value(attr_value)}")
            attr_child.setFlags(attr_child.flags() | Qt.ItemFlag.ItemIsEditable)
        
        root_item.setExpanded(True)
        self._is_updating_tree = False
                        
    def dragEnterEvent(self, event):
        """Gérer l'entrée d'un glisser-déposer"""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if len(urls) == 1 and (urls[0].toLocalFile().lower().endswith('.nc') or urls[0].toLocalFile().lower().endswith('.netcdf') ):
                event.accept()
            else:
                pass
        else:
            pass

    def dropEvent(self, event):
        """Gérer le dépôt d'un fichier"""
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if file_path.lower().endswith('.nc') or file_path.lower().endswith('.netcdf'):
                self.load_netcdf(file_path)
                event.accept()
            else:
                print("DataPanel: Extension non .nc ou .netcdf - événement ignoré")

    def show_context_menu(self, position):
        """Afficher le menu contextuel"""
        item = self.tree.itemAt(position)
        if not item:
            return

        menu = QMenu()
        
        # Obtenir le fichier parent et le dataset
        root_item = item
        while root_item.parent():
            root_item = root_item.parent()
        filename = root_item.data(0, Qt.ItemDataRole.UserRole)
        dataset = self.open_files.get(filename)
        
        if not dataset:
            return
        
        # Déterminer le type d'item
        path = []
        current = item
        while current and current != root_item:
            path.insert(0, current.text(0))
            current = current.parent()

        # Ajouter les options de visualisation si on est sur une valeur
        if "Valeurs" in path:
            var_name = path[1]  # Le nom de la variable
            value_text = item.text(0)
            var = dataset[var_name]
            
            # Extraire l'index
            match = re.match(r'\[(\d+)\]:', value_text)
            if match:
                index = int(match.group(1))
                value = value_text.split(':')[1].strip()
                
                # Trouver toutes les variables qui utilisent cette dimension
                related_vars = []
                dim_name = path[3] if len(path) > 3 else var.dims[0] if var.dims else None
                
                if dim_name:
                    for v_name, v_data in dataset.variables.items():
                        if dim_name in v_data.dims and len(v_data.dims) >= 2:
                            related_vars.append(v_name)
                
                if related_vars:
                    # Créer un sous-menu pour chaque variable liée
                    visualize_submenu = menu.addMenu(f"Visualiser {value} dans...")
                    for v_name in related_vars:
                        action = visualize_submenu.addAction(v_name)
                        action.triggered.connect(
                            lambda checked=False, f=filename, v=v_name, d=dim_name, i=index: 
                                self._emit_visualization_request(f, v, d, i)
                        )
                else:
                    # Si pas de variable liée, proposer de visualiser la variable actuelle
                    visualize_action = menu.addAction(f"Visualiser {value}")
                    visualize_action.triggered.connect(
                        lambda checked=False, f=filename, v=var_name, d=dim_name, i=index: 
                            self._emit_visualization_request(f, v, d, i)
                    )
                
                menu.addSeparator()

        # Ajouter les options existantes du menu
        if not path:  # C'est la racine (le fichier)
            menu.addAction(self.translator.get_text("save"), 
                         lambda: self.save_file(filename))
            menu.addAction(self.translator.get_text("save_as"), 
                         lambda: self.save_file_as(filename))
            menu.addAction(self.translator.get_text("close"), 
                         lambda: self.close_file(filename))
        
        elif "Variables" in path:
            if len(path) == 2:  # C'est une variable
                var_name = path[1]
                menu.addAction(self.translator.get_text("rename"), 
                             lambda: self.tree.editItem(item, 0))
                menu.addAction(self.translator.get_text("delete"), 
                             lambda: self.delete_variable(filename, var_name))
                menu.addAction(self.translator.get_text("duplicate"), 
                             lambda: self.duplicate_variable(filename, var_name))
                
                menu.addSeparator()
                menu.addAction("Créer une nouvelle variable", 
                             lambda: self.create_new_variable(filename))
        
        if menu.actions():
            menu.exec(self.tree.viewport().mapToGlobal(position))

    def _emit_visualization_request(self, filename, var_name, dim_name, index):
        """Émettre le signal de visualisation avec debug"""
        dataset = self.open_files[filename]
        var = dataset[var_name]
        
        # Récupérer la vraie dimension (la première dimension de la variable)
        real_dim_name = var.dims[0] if var.dims else None
        
        # Collecter toutes les variables qui utilisent cette dimension
        potential_vars = []
        for v_name, v_data in dataset.variables.items():
            if real_dim_name in v_data.dims:
                potential_vars.append((v_name, len(v_data.dims)))
        
        # Trier les variables par nombre de dimensions
        potential_vars.sort(key=lambda x: x[1], reverse=True)
        
        if potential_vars:
            target_var = potential_vars[0][0]
        else:
            target_var = var_name
               
        # Émettre le signal avec la vraie dimension
        self.visualization_requested.emit(filename, target_var, real_dim_name, index)

    def handle_item_edit(self, item, column):
        """Gérer l'édition d'un item dans l'arbre"""
        if self._is_updating_tree or self._is_updating_icon:  # Ajouter la vérification ici aussi
            return
            
        try:
            # Obtenir le fichier parent
            root_item = item
            while root_item.parent():
                root_item = root_item.parent()
            filename = root_item.data(0, Qt.ItemDataRole.UserRole)
            dataset = self.open_files[filename]
            
            # Obtenir le chemin complet de l'item
            path = []
            current = item
            while current and current != root_item:
                path.insert(0, current.text(0))
                current = current.parent()
                        
            # Traiter selon le type d'item
            if "Variables" in path:
                if len(path) == 2:  # C'est le nom de la variable lui-même
                    new_name = item.text(0)
                    old_name = item.data(0, Qt.ItemDataRole.UserRole)
                    
                    if old_name != new_name:
                        # Vérifier que le nouveau nom n'existe pas déjà
                        if new_name in dataset.variables:
                            raise ValueError(f"Une variable nommée '{new_name}' existe déjà")
                        
                        # Renommer la variable directement
                        dataset[new_name] = dataset[old_name]
                        del dataset[old_name]
                        
                        # Mettre à jour les données utilisateur de l'item
                        item.setData(0, Qt.ItemDataRole.UserRole, new_name)
                        
                        self.mark_modified(filename)
                    return
                        
                var_name = path[1]
                if "Valeurs" in path:
                    # Édition d'une valeur de variable
                    value_str = item.text(0)
                    index, dtype = item.data(0, Qt.ItemDataRole.UserRole)
                    
                    # Extraire la valeur du texte [index]: valeur
                    match = re.match(r'\[(\d+)\]:\s*(.*)', value_str)
                    if match:
                        value_str = match.group(2)
                        
                    # Parser la valeur
                    if (filename, var_name, index) in self.date_formats:
                        value = self.parse_value(value_str, dtype, 
                                            self.date_formats[(filename, var_name, index)])
                    else:
                        value = self.parse_value(value_str, dtype)
                        
                    # Mettre à jour la valeur
                    var_data = dataset[var_name].values.copy()
                    var_data[index] = value
                    dataset[var_name].values = var_data
                    
                elif "Attributs" in path:
                    # Édition d'un attribut de variable
                    attr_str = item.text(0)
                    name, value = self.parse_attribute(attr_str)
                    dataset[var_name].attrs[name] = value
                    
            elif "Attributs globaux" in path:
                # Édition d'un attribut global
                attr_str = item.text(0)
                name, value = self.parse_attribute(attr_str)
                dataset.attrs[name] = value
                
            self.mark_modified(filename)
            
        except Exception as e:
            QMessageBox.critical(self, "Erreur", str(e))
            # Recharger le fichier dans l'arbre
            if filename in self.open_files:
                # Trouver et supprimer l'ancien item
                root = self.tree.invisibleRootItem()
                for i in range(root.childCount()):
                    if root.child(i).data(0, Qt.ItemDataRole.UserRole) == filename:
                        root.removeChild(root.child(i))
                        break
                # Rajouter le fichier à l'arbre
                self.add_file_to_tree(filename, self.open_files[filename])

    def delete_variable(self, filename, var_name):
        """Supprimer une variable"""
        reply = QMessageBox.question(
            self,
            "Confirmation",
            f"Êtes-vous sûr de vouloir supprimer la variable '{var_name}' ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                dataset = self.open_files[filename]
                
                # Vérifier si la variable n'est pas une dimension
                if var_name in dataset.dims:
                    QMessageBox.warning(
                        self,
                        "Attention",
                        f"Impossible de supprimer '{var_name}' car c'est une dimension du fichier."
                    )
                    return
                
                # Supprimer la variable
                del dataset[var_name]
                
                # Mettre à jour l'arbre
                root = self.tree.invisibleRootItem()
                for i in range(root.childCount()):
                    item = root.child(i)
                    if item.data(0, Qt.ItemDataRole.UserRole) == filename:
                        vars_item = self.find_variables_item(item)
                        if vars_item:
                            for j in range(vars_item.childCount()):
                                if vars_item.child(j).text(0) == var_name:
                                    vars_item.removeChild(vars_item.child(j))
                                    break
                        break
                
                self.mark_modified(filename)
                
            except Exception as e:
                QMessageBox.critical(self, "Erreur", str(e))

    def delete_value(self, filename, var_name, index):
        """Supprimer une valeur"""
        try:
            dataset = self.open_files[filename]
            var_data = dataset[var_name].values
            value_to_delete = var_data[index]
            
            # Nettoyer la valeur si c'est une chaîne de caractères
            if isinstance(value_to_delete, (bytes, np.bytes_)):
                value_to_delete = value_to_delete.decode('utf-8')
            display_value = str(value_to_delete).strip("'")
            
            # Obtenir la dimension de la variable
            var_dims = dataset[var_name].dims
            if not var_dims:
                raise ValueError(f"La variable {var_name} n'a pas de dimension associée")
            dim_name = var_dims[0]
            
            reply = QMessageBox.question(
                self,
                "Confirmation",
                f"Êtes-vous sûr de vouloir supprimer la valeur '{display_value}' ?\n"
                f"(Variable: {var_name}, Dimension: {dim_name})",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # Vérifier si on doit utiliser l'index ou la valeur
                if isinstance(dataset[dim_name].values[0], (np.integer, int)):
                    # Dimension indexée (comme pour les polluants)
                    new_dataset = dataset.drop_sel({dim_name: index})
                else:
                    # Dimension non indexée (comme pour le temps)
                    new_dataset = dataset.drop_sel({dim_name: value_to_delete})
                
                # Fermer l'ancien dataset
                dataset.close()
                
                # Stocker le nouveau dataset
                self.open_files[filename] = new_dataset
                
                # Mettre à jour l'arbre
                root = self.tree.invisibleRootItem()
                for i in range(root.childCount()):
                    item = root.child(i)
                    if item.data(0, Qt.ItemDataRole.UserRole) == filename:
                        root.removeChild(item)
                        self.add_file_to_tree(filename, new_dataset)
                        break
                
                self.mark_modified(filename)
                
        except Exception as e:
            QMessageBox.critical(self, "Erreur", 
                f"Erreur lors de la suppression:\n{str(e)}")

    def set_value_to_nan(self, filename, var_name, index):
        """Remplacer une valeur par NaN (alias pour delete_value)"""
        self.delete_value(filename, var_name, index)

    def update_value_in_tree(self, root_item, var_name, index, new_value):
        """Mettre à jour l'affichage d'une valeur dans l'arbre"""
        # Trouver l'item Variables
        for i in range(root_item.childCount()):
            vars_item = root_item.child(i)
            if vars_item.text(0) == "Variables":
                # Trouver la variable
                for j in range(vars_item.childCount()):
                    var_item = vars_item.child(j)
                    if var_item.text(0) == var_name:
                        # Trouver l'item Valeurs
                        for k in range(var_item.childCount()):
                            vals_item = var_item.child(k)
                            if vals_item.text(0) == "Valeurs":
                                # Trouver la valeur spécifique
                                for l in range(vals_item.childCount()):
                                    val_item = vals_item.child(l)
                                    item_index, dtype = val_item.data(0, Qt.ItemDataRole.UserRole)
                                    if item_index == index:
                                        val_item.setText(0, f"[{index}]: {self.format_value(new_value)}")
                                        break
                                break
                        break
                break

    def find_variables_item(self, root_item):
        """Trouver l'item 'Variables' dans l'arbre"""
        for i in range(root_item.childCount()):
            item = root_item.child(i)
            if item.text(0) == "Variables":
                return item
        return None

    def mark_modified(self, filename, modified=True, emit_signal=True):
        """Marquer le fichier comme modifié avec un point"""
        if self._is_updating_icon:  # Éviter la récursion
            return
            
        try:
            self._is_updating_icon = True
            self.is_modified[filename] = modified
            
            # Mettre à jour l'icône dans l'arbre
            root = self.tree.invisibleRootItem()
            for i in range(root.childCount()):
                item = root.child(i)
                if item.data(0, Qt.ItemDataRole.UserRole) == filename:
                    item.setIcon(0, self.modified_icon if modified else self.unmodified_icon)
                    break
            
            if emit_signal:
                self.dataset_modified.emit(filename)
        finally:
            self._is_updating_icon = False

    def save_file(self, filename, show_success_message=True):
        """Sauvegarder le fichier NetCDF"""
        if filename in self.open_files:
            try:                
                dataset = self.open_files[filename]
                
                # Créer un fichier temporaire
                temp_dir = tempfile.gettempdir()
                temp_fd, temp_path = tempfile.mkstemp(suffix='.nc', dir=temp_dir)
                os.close(temp_fd)
                
                try:
                    # Fermer explicitement le dataset xarray
                    dataset.close()
                    del self.open_files[filename]
                    
                    # Forcer le garbage collector
                    import gc
                    gc.collect()
                    
                    # Sauvegarder avec netCDF4 directement
                    import netCDF4
                    
                    # Créer le fichier temporaire
                    with netCDF4.Dataset(temp_path, 'w', format='NETCDF4') as dst:
                        # Copier les dimensions
                        for name, size in dataset.dims.items():
                            dst.createDimension(name, size)
                        
                        # Copier les variables
                        for name, var in dataset.variables.items():
                            # Gérer les types spéciaux
                            if var.dtype == 'datetime64[ns]':
                                # Créer une variable de type double pour le temps
                                var_out = dst.createVariable(name, 'f8', var.dims)
                                # Convertir les dates en nombres
                                if 'units' in var.attrs:
                                    units = var.attrs['units']
                                else:
                                    units = 'seconds since 1970-01-01 00:00:00'
                                # Convertir les valeurs en nombres
                                dates = netCDF4.date2num(var.values.astype('datetime64[s]').astype(datetime),
                                                       units=units)
                                var_out[:] = dates
                                # Ajouter l'attribut units
                                var_out.units = units
                            else:
                                # Pour les autres types
                                var_out = dst.createVariable(name, var.dtype, var.dims)
                                var_out[:] = var.values
                            
                            # Copier les attributs
                            for attr_name, attr_value in var.attrs.items():
                                if attr_name != 'units' or var.dtype != 'datetime64[ns]':
                                    setattr(var_out, attr_name, attr_value)
                        
                        # Copier les attributs globaux
                        for attr_name, attr_value in dataset.attrs.items():
                            setattr(dst, attr_name, attr_value)
                    
                    try:
                        # Sous Windows, supprimer d'abord le fichier existant
                        if os.path.exists(filename):
                            os.remove(filename)
                        
                        # Copier le fichier temporaire vers la destination
                        shutil.copy2(temp_path, filename)
                        
                    except Exception as e:
                        # Si la copie échoue, essayer avec un appel système
                        if os.name == 'nt':  # Windows
                            import subprocess
                            subprocess.run(['copy', temp_path, filename], shell=True, check=True)
                        else:  # Unix
                            subprocess.run(['cp', temp_path, filename], check=True)
                    
                    # Rouvrir le dataset
                    self.open_files[filename] = xr.open_dataset(filename)
                    
                    # Forcer la mise à jour du marqueur de modification
                    self.mark_modified(filename, modified=False, emit_signal=False)
                    
                    # Forcer la mise à jour visuelle
                    self.tree.update()
                    
                    # Après une sauvegarde réussie
                    self.is_modified[filename] = False
                    self.mark_modified(filename, modified=False, emit_signal=False)
                    
                    # N'afficher le message que si demandé
                    if show_success_message:
                        QMessageBox.information(self, "Succès", 
                                            "Fichier sauvegardé avec succès!")
                    
                    return True
                    
                finally:
                    # Nettoyer le fichier temporaire
                    if os.path.exists(temp_path):
                        try:
                            os.remove(temp_path)
                        except:
                            pass
                    
            except Exception as e:
                if show_success_message:
                    QMessageBox.critical(self, "Erreur", 
                        f"Erreur lors de la sauvegarde: {str(e)}")
                raise  # Propager l'erreur pour la gestion dans save_all_files

    def save_file_as(self, filename):
        """Sauvegarder sous un nouveau nom"""
        try:
            new_filename, _ = QFileDialog.getSaveFileName(
                self,
                "Sauvegarder sous",
                os.path.dirname(filename),
                "Fichiers NetCDF (*.nc);;Tous les fichiers (*.*)"
            )
            
            if new_filename:
                if not new_filename.lower().endswith('.nc'):
                    new_filename += '.nc'
                    
                # Créer une copie du dataset
                dataset = self.open_files[filename].copy(deep=True)
                
                try:
                    # Sauvegarder directement avec le nouveau nom
                    xr.backends.file_manager.FILE_CACHE.clear()
                    dataset.to_netcdf(new_filename)
                    
                    # Charger le nouveau fichier
                    new_dataset = xr.open_dataset(new_filename)
                    
                    # Mettre à jour les références
                    self.open_files[new_filename] = new_dataset
                    self.is_modified[new_filename] = False
                    
                    # Mettre à jour l'arbre
                    root = self.tree.invisibleRootItem()
                    for i in range(root.childCount()):
                        item = root.child(i)
                        if item.data(0, Qt.ItemDataRole.UserRole) == filename:
                            item.setData(0, Qt.ItemDataRole.UserRole, new_filename)
                            item.setText(0, os.path.basename(new_filename))
                            # Mettre à jour l'icône pour montrer que le fichier n'est plus modifié
                            self.mark_modified(new_filename, modified=False, emit_signal=False)
                            break
                            
                    return True
                    
                except Exception as e:
                    QMessageBox.critical(self, "Erreur", 
                        f"Erreur lors de la sauvegarde:\n{str(e)}\n\nChemin du fichier: {new_filename}")
                    if os.path.exists(new_filename):
                        try:
                            os.remove(new_filename)
                        except:
                            pass
                    return False
                    
        except Exception as e:
            QMessageBox.critical(self, "Erreur", 
                f"Erreur lors de la sauvegarde:\n{str(e)}")
            return False

    def close_file(self, filename):
        """Fermer un fichier"""
        if filename in self.open_files:
            # Fermer le dataset
            self.open_files[filename].close()
            del self.open_files[filename]
            del self.is_modified[filename]
            
            # Retirer de l'arbre
            root = self.tree.invisibleRootItem()
            for i in range(root.childCount()):
                item = root.child(i)
                if item.data(0, Qt.ItemDataRole.UserRole) == filename:
                    root.removeChild(item)
                    break
                    
            return True
        return False

    def close_all_files(self):
        """Fermer tous les fichiers"""
        filenames = list(self.open_files.keys())
        for filename in filenames:
            if not self.close_file(filename):
                break

    def retranslate_ui(self):
        """Mettre à jour les textes après un changement de langue"""
        self.tree.setHeaderLabels([self.translator.get_text("netcdf_files")])
        
        # Mettre à jour les textes dans l'arbre
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            file_item = root.child(i)
            
            # Mettre à jour les libellés standards
            for j in range(file_item.childCount()):
                item = file_item.child(j)
                text = item.text(0)
                
                if text.startswith("Dimensions:"):
                    dims_info = text.split(":", 1)[1]
                    item.setText(0, f"{self.translator.get_text('dimensions')}:{dims_info}")
                elif text == "Variables":
                    item.setText(0, self.translator.get_text("variables"))
                elif text == "Attributs globaux":
                    item.setText(0, self.translator.get_text("global_attributes"))
                elif text == "Valeurs":
                    item.setText(0, self.translator.get_text("values"))
                elif text == "Attributs":
                    item.setText(0, self.translator.get_text("attributes"))