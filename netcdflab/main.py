import sys
import os
from PyQt6.QtWidgets import QApplication
from netcdflab.gui.main_window import MainWindow

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from netcdflab.utils.translations import Translator

def main():
    app = QApplication(sys.argv)
    
    # Créer l'instance du traducteur et charger les préférences
    translator = Translator()
    
    window = MainWindow()
    window.show()
    
    # Ouvrir tous les fichiers passés en arguments
    for arg in sys.argv[1:]:
        if arg.lower().endswith('.nc'):
            window.data_panel.load_netcdf(arg)
            window.menu_bar.add_recent_file(arg)
        elif arg.lower().endswith('.netcdf'):
            window.data_panel.load_netcdf(arg)
            window.menu_bar.add_recent_file(arg)
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main()