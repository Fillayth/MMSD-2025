import sys
import os
from plotly.graph_objects import Figure
from dataclasses import dataclass
from typing import List

if os.path.basename(__file__) != "main.py":
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../', 'Code')))

from CommonClass.CommonEnum import Days
from CommonClass.OperatingRoomShedule import OperatingRoomShedule
from CommonClass.Patient import Patient



@dataclass
class Day:
    day: Days
    operatingRooms: List[OperatingRoomShedule]
    #_minute_of_the_day_: int = Settings.daily_operation_limit

    def __init__ (self, day: Days, operatingRooms: List[OperatingRoomShedule] = []):
        self.day = day
        self.operatingRooms = operatingRooms
        #self._minute_of_the_day_ = Settings.daily_operation_limit

    def copy(self):
        copy = Day(self.day, self.operatingRooms)
        return copy

    #region: Funzioni 
    def getTime(self) -> int:
        return sum(p.eot for p in self.patients())

    def insertPatient(self, patient: Patient) -> bool:
        return self.operatingRooms[patient.workstation].insertPatient(patient)


    # def swapPatient(self, patient1: Patient, patient2: Patient) -> bool:
    #     #toDo
    #     list = self.patients().copy()
    #     list.remove(patient1)
    #     list.insert(patient2)
    #     if sum(p.eot for p in list) > self._minute_of_the_day_:
    #         return False
    #     else:
    #         self.patients = list
    #         return True

    def patients(self) -> List[Patient]:
        patients = []
        for oroom in self.operatingRooms:
            patients.extend(oroom.daily_schedules)
        return patients

    #endregion
    #region: Funzioni Grafiche 
    def setTrace(self, figure: Figure, color_map, text: str) -> Figure:
        mins = round(sum(p.eot for p in self.patients()), 2)
        for p in self.patients():
            figure = p.setTrace(figure, color_map, text + f"|Day:{self.day.name}", mins)
        return figure

    #endregion
    #region: Funzioni Json
    def to_dict(self):
        return {
            "day":self.day.name,
            "workstations":[opRoom.to_dict() for opRoom in self.operatingRooms]
            #"patients":[p.to_dict() for p in self.patients]
        }

    @classmethod
    def from_dict(cls, data):
        #patients = [Patient.from_dict(p) for p in data['patients']]
        operatingRooms = [OperatingRoomShedule.from_dict(opRoom) for opRoom in data['workstations']]
        return cls(Days[data['day']], operatingRooms)
    #endregion