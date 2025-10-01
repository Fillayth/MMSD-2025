import sys
import os

if os.path.basename(__file__) != "main.py":
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../', 'Code')))

from CommonClass.Week import Week


class PatientListForSpecialties: #PLFS 
    """ Classe per gestire le liste di pazienti e liste di settimane create dividendole per specialità    """
    def __init__(self):
        self.list = {
            "Specialty A": [],
            #Specialty.OpA.value: []}
            # Operation.OpB.value: [], 
            # Operation.OpC.value: []
            }
    def __setitem__(self, key, value):
        self.list[key] = value
    def __getitem__(self, key):
        return self.list[key]
    def __iter__(self):
        return iter(self.list)
    def values(self):
        return self.list.values()
    def items(self):
        return self.list.items()
    def keys(self):
        return self.list.keys()

    #region: Funzioni Json
    def to_dict(self):
        return {
            key: [w.to_dict() for w in weeks] for key, weeks in self.list.items()
        }

    @classmethod
    def from_dict(cls, data):
        obj = cls()
        for key, value in data.items():
            if key not in obj.list:
                raise ValueError(f"Chiave non valida: {key}")
            obj[key] = [Week.from_dict(w) for w in value]
        return obj
    #endregion
