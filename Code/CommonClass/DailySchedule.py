
from plotly.graph_objects import Figure
from dataclasses import dataclass
from typing import List
import sys
import os

if os.path.basename(__file__) != "main.py":
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../', 'Code')))

from Code.CommonClass.CommonEnum import Days
from Code.CommonClass.Patient import Patient
from Code.settings import Settings


@dataclass
class DailySchedule:
    day: Days
    patients: List[Patient]
    _minute_of_the_day_: int = Settings.daily_operation_limit

    def __init__ (self, day: Days, patients: List[Patient] = []):
        self.day = day
        self.patients = patients
        self._minute_of_the_day_ = Settings.daily_operation_limit

    def copy(self):
        copy = DailySchedule(self.day, self.patients)
        return copy

    #region: Funzioni 
    def getTime(self) -> int:
        return sum(p.eot for p in self.patients)

    def insertPatient(self, patient: Patient) -> bool:
        if patient.eot + sum(p.eot for p in self.patients) > self._minute_of_the_day_:
            return False
        else:
            self.patients.append(patient)
            return True
    def swapPatient(self, patient1: Patient, patient2: Patient) -> bool:
        list = self.patients.copy()
        list.remove(patient1)
        list.insert(patient2)
        if sum(p.eot for p in list) > self._minute_of_the_day_:
            return False
        else:
            self.patients = list
            return True
    #endregion
    #region: Funzioni Grafiche 
    def setTrace(self, figure: Figure, color_map, text: str) -> Figure:
        mins = round(sum(p.eot for p in self.patients), 2)
        for p in self.patients:
            figure = p.setTrace(figure, color_map, text + f"|Day:{self.day.name}", mins)
        return figure

    #endregion
    #region: Funzioni Json
    def to_dict(self):
        return {
            "day":self.day.name,
            "patients":[p.to_dict() for p in self.patients]
        }

    @classmethod
    def from_dict(cls, data):
        patients = [Patient.from_dict(p) for p in data['patients']]
        return cls(DailySchedule[data['day']], patients)
    #endregion