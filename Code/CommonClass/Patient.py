from dataclasses import dataclass

import sys
import os

if os.path.basename(__file__) != "main.py":
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../', 'Code')))

@dataclass
class Patient:
    def __init__(self, id: int, eot: float, day: int, mtb: int,rot: float = -1, opDay = -1, workstation: int = -1, overdue: bool = False):
        self.id = id
        self.eot = eot
        self.rot = rot
        self.day = day
        self.mtb = mtb
        self.opDay = opDay
        self.workstation = workstation
        self.overdue = overdue

    #region
    def __eq__(self, other):
        return isinstance(other, Patient) and self.id == other.id

    # def __hash__(self):
    #     return hash((self.id, self.day))
    #endregion


    #region: Funzioni Json
    def to_dict(self):
        return {
            "id": self.id,
            "eot": self.eot,
            "rot": self.rot,
            "day": self.day,
            "mtb": self.mtb,
            "opDay": self.opDay,
            "workstation": self.workstation,
            "overdue": self.overdue
        }        
    
    def to_json(self):
        return {
            "id": self.id,
            "eot": self.eot,
            "rot": self.rot,
            "day": self.day,
            "mtb": self.mtb,
            "opDay": self.opDay,
            "workstation": self.workstation,
            "overdue": self.overdue
        }

    @classmethod
    def from_dict(cls, data):
        return cls(data['id'], data['eot'], data['day'], data['mtb'], data['rot'], data['opDay'], data['workstation'], data['overdue'])
    
    #endregion