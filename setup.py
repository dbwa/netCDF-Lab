# setup.py
from setuptools import setup, find_packages

setup(
    name="netcdflab",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        'PyQt6',
        'xarray',
        'numpy',
        'pandas',
        'matplotlib',
        'netCDF4',
    ],
    description="A user-friendly GUI application for viewing and editing NetCDF files",
    project_name="NetCDF Lab",
    author="RV - dbwa",
    url="https://github.com/dbwa/netCDF-Lab",
)