import sys
import os
from enum import Enum

if os.path.basename(__file__) != "main.py":
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../', 'Code')))
from settings import Settings


class Days(Enum):
    Lun = 0
    Mar = 1
    Mer = 2
    Gio = 3
    Ven = 4

#lo sto rimuovendo per ora
class Specialty(Enum):
    OpA = "Specialty A" 
    OpB = "Specialty B"
    OpC = "Specialty C"
