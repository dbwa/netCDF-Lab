import numpy as np
from netCDF4 import Dataset
from datetime import datetime, timedelta
from netCDF4 import stringtochar

# Paramètres de la grille
nx, ny = 100, 100  # dimensions spatiales
nb_temps = 24  # nombre de pas de temps (24 heures)

# Liste des polluants
polluants = ["NOx", "PM10", "CO2", "O3"]
nb_polluants = len(polluants)

# Création du fichier NetCDF
rootgrp = Dataset("pollution_data.nc", "w", format="NETCDF4")

# Création des dimensions
time = rootgrp.createDimension("time", nb_temps)
lat = rootgrp.createDimension("lat", ny)
lon = rootgrp.createDimension("lon", nx)
pollutant = rootgrp.createDimension("pollutant", nb_polluants)  # dimension fixe
name_strlen = rootgrp.createDimension("name_strlen", 10)  # longueur max des noms de polluants

# Création des variables
times = rootgrp.createVariable("time", "f8", ("time",))
latitudes = rootgrp.createVariable("latitude", "f4", ("lat",))
longitudes = rootgrp.createVariable("longitude", "f4", ("lon",))
pollutants = rootgrp.createVariable("pollutant_name", "S1", ("pollutant", "name_strlen"))
concentrations = rootgrp.createVariable("concentration", "f4", ("pollutant", "time", "lat", "lon",))

# Définition des attributs
rootgrp.description = "Données de pollution atmosphérique"
rootgrp.history = f"Créé le {datetime.now().strftime('%Y-%m-%d')}"
rootgrp.source = "Données simulées"

times.units = "hours since 2024-01-01 00:00:00"
times.calendar = "gregorian"
latitudes.units = "degrees_north"
longitudes.units = "degrees_east"
concentrations.units = "µg/m³"

# Remplissage des données
# Coordonnées temporelles
time_values = np.arange(nb_temps, dtype=float)
times[:] = time_values

# Coordonnées spatiales
lat_values = np.linspace(43.0, 44.0, ny)
lon_values = np.linspace(1.0, 2.0, nx)
latitudes[:] = lat_values
longitudes[:] = lon_values

# Stockage des noms de polluants
for i, pol in enumerate(polluants):
    pollutants[i] = stringtochar(np.array(pol.ljust(10), dtype="S10"))

# Génération de données aléatoires pour chaque polluant
for i, pol in enumerate(polluants):
    # Paramètres spécifiques à chaque polluant
    if pol == "NOx":
        mean, std = 40, 15
    elif pol == "PM10":
        mean, std = 20, 8
    elif pol == "CO2":
        mean, std = 400, 50
    else:  # O3
        mean, std = 60, 20
    
    # Génération des données avec variation spatiale et temporelle
    for t in range(nb_temps):
        # Création d'une carte de base avec gradient spatial
        base = np.zeros((ny, nx))
        for y in range(ny):
            for x in range(nx):
                # Ajout d'un gradient spatial
                dist = np.sqrt((x - nx/2)**2 + (y - ny/2)**2)
                base[y, x] = np.exp(-dist/50)  # Décroissance exponentielle depuis le centre
        
        # Ajout de bruit gaussien
        noise = np.random.normal(mean, std, (ny, nx))
        # Combinaison du gradient et du bruit
        concentrations[i, t, :, :] = base * noise

# Fermeture du fichier
rootgrp.close()