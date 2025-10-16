import sys
import os

from dataclasses import dataclass
from typing import List

if os.path.basename(__file__) != "main.py":
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../', 'Code')))

from CommonClass.CommonEnum import Days
from CommonClass.Day import Day
from CommonClass.OperatingRoomShedule import OperatingRoomShedule
from CommonClass.Patient import Patient
from settings import Settings

@dataclass
class Week:
    def __init__(self, weekNum: int, specialty: str = "Specialty A"):
        self.weekNum = weekNum
        if specialty not in Settings.workstations_config:
            raise ValueError(f"Specialty '{specialty}' non è configurata in Settings.")

        self.specialty = specialty
        self.dailySchedule = [
            Day(
                day=Days(day_enum),
                operatingRooms=[
                    OperatingRoomShedule(id=orId)
                    for orId in range(Settings.workstations_config[self.specialty])
                ]
            )
            for day_enum in range(Settings.week_length_days)
        ]
    #region: Funzioni 
    def insertPatient(self, patient: Patient) -> bool:
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
    def getNumberOpDayByPatientID(self, patientID: int) -> int:
        for d in self.dailySchedule:
            for p in d.patients():
                if p.id == patientID:
                    return self.weekNum * Settings.week_length_days + d.day.value
        return -1
    
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
        return week
    #endregion