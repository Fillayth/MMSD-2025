import sys
import os
from dataclasses import dataclass
from typing import List

if os.path.basename(__file__) != "main.py":
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../', 'Code')))

from CommonClass.Patient import Patient
from settings import Settings

@dataclass
class OperatingRoomShedule:
    id: int
    daily_schedules: List[Patient]

    def __init__ (self, id: int, max_time_per_day: int = Settings.daily_operation_limit, patients: List[Patient] = None):
        self.id = id
        self._max_time_per_day_ = max_time_per_day
        self.daily_schedules = patients if patients is not None else []

    def copy(self):
        copy = OperatingRoomShedule(self.day, self._max_time_per_day_, self.daily_schedules)
        return copy

    #region: Funzioni 
    def getTime(self) -> int:
        return sum(p.eot for p in self.daily_schedules)

    def insertPatient(self, patient: Patient) -> bool:
        if patient.eot + self.getTime() > self._max_time_per_day_:
            return False
        else:
            self.daily_schedules.append(patient)
            return True

    def swapPatient(self, patient1: Patient, patient2: Patient) -> bool:
        list = self.daily_schedules.copy()
        list.remove(patient1)
        list.insert(patient2)
        if sum(p.eot for p in list) > self._max_time_per_day_:
            return False
        else:
            self.daily_schedules = list
            return True

    #endregion
    #region: Funzioni Json
    def to_dict(self):
        return {
            "operatingRoom":self.id,
            "maxTimePerDay":self._max_time_per_day_,
            "patients":[p.to_dict() for p in self.daily_schedules]
        }

    @classmethod
    def from_dict(cls, data):
        patients = [Patient.from_dict(p) for p in data['patients']]
        return cls(data['operatingRoom'], data['maxTimePerDay'], patients)
    
    #endregion