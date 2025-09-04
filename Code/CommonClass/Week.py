import sys
import os

if os.path.basename(__file__) != "main.py":
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../', 'Code')))


from CommonClass.CommonEnum import Days
from CommonClass.Day import Day
from CommonClass.OperatingRoomShedule import OperatingRoomShedule
from CommonClass.Patient import Patient
from settings import Settings


from plotly.graph_objects import Figure


from dataclasses import dataclass
from typing import List


@dataclass
class Week:
    def __init__(self, weekNum: int, specialty: str = "Specialty A"):
        self.weekNum = weekNum
        # if isinstance(specialty, str):
        #     specialty_enum = next(s for s in Specialty if s.value == specialty)
        #     self.specialty = specialty_enum
        # else:
        #     self.specialty = specialty
        if specialty not in Settings.workstations_config:
            raise ValueError(f"Specialty '{specialty}' non è configurata in Settings.")

        self.specialty = specialty
        self.dailySchedule = [
            Day(
                day=day_enum,
                operatingRooms=[
                    OperatingRoomShedule(id=orId)
                    for orId in range(Settings.workstations_config[self.specialty])
                ]
            )
            for day_enum in Days
        ]

    #region: Funzioni 
    def insertPatient(self, patient: Patient) -> bool:
        # #per mantenere il bool sull urgenza 
        # p = OperationPatient(patient)
        # p.overdue = (self.weekNum + 1) * 5 >= patient.day+patient.mtb

        for d in self.dailySchedule:
            if d.insertPatient(patient=patient):
                return True
        # se non ritorna true, vuoldire che nella settimana non c'è spazio
        return False
    def patients(self) -> List[Patient]:
        patients = []
        for d in self.dailySchedule:
            patients.extend(d.patients())
        return patients

    #endregion
    #region: Funzioni Grafiche
    def setTrace (self, figure: Figure, color_map) -> Figure:
        for day in self.dailySchedule:
            figure = day.setTrace(figure, color_map, f"Week:{self.weekNum}")
        return figure
    #endregion
    #region: Funzioni Json
    def to_dict(self):
        return {
            "week":self.weekNum,
            "days":[day.to_dict() for day in self.dailySchedule]
        }



    @classmethod
    def from_dict(cls, data):
        week = cls(data['week'])
        week.dailySchedule = [Day.from_dict(d) for d in data["days"]]
        # week.dailySchedule = [DailySchedule.from_dict(d) for d in data["days"]]
        return week
    #endregion