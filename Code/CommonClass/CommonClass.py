from plotly.graph_objects import Figure 
import plotly.graph_objects as go 
from dataclasses import dataclass
from typing import List 

from enum import Enum

class Day(Enum):
    Lun = 0
    Mar = 1
    Mer = 2
    Gio = 3
    Ven = 4

class Specialty(Enum):
    OpA = "Specialty A" 
    OpB = "Specialty B"
    OpC = "Specialty C"

class PatientListForSpecialties: #PLFS
    """ Classe per gestire le liste di pazienti per specialità    """
    def __init__(self, name: str = "Specialty A"):
        self.list = {
            Specialty.OpA.value: []} 
            # Operation.OpB.value: [], 
            # Operation.OpC.value: []}
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


class OperatingRoom(Enum):
    OR1 = "OR1"
    OR2 = "OR2"
    OR3 = "OR3"

    @classmethod
    def from_string(cls, value: str):
        for room in cls:
            if room.value == value:
                return room
        raise ValueError(f"Invalid operating room: {value}")

class OpratingRoomManager:
    def __init__(self, numRoom: int , specialty: Specialty):
        self.specialty = specialty
        self.numRoom = numRoom
        if numRoom < 1 or numRoom > 3:
            raise ValueError("Number of operating rooms must be between 1 and 3.")
        if numRoom == 1:
            self.rooms = {OperatingRoom.OR1: []}
        elif numRoom == 2:
            self.rooms = {
                OperatingRoom.OR1: [],
                OperatingRoom.OR2: []
            }
        else:  # numRoom == 3
            self.rooms = {
                OperatingRoom.OR1: [],
                OperatingRoom.OR2: [],
                OperatingRoom.OR3: []
            }
    
    def assign_patient(self, room: OperatingRoom, patient: 'Patient'):
        if room in self.rooms:
            self.rooms[room].append(patient)
        else:
            raise ValueError(f"Invalid operating room: {room}")
    
    def get_patients(self, room: OperatingRoom) -> List['Patient']:
        return self.rooms.get(room, [])


@dataclass
class Patient:
    def __init__(self, id: int, eot: float, day: int, mtb: int):
        self.id = id
        self.eot = eot
        self.day = day
        self.mtb = mtb
    
    #region: Funzioni Grafiche
    def setTrace (self, figure: Figure, color_map, text: str, mins: float) -> Figure:
        figure.add_trace(go.Bar(
            x=[text + f"|ToTMin:{mins}"], 
            y=[self.eot], 
            name=f"Patient {self.id}",  
            hoverinfo="text",  
            text=[f"Patient {self.id}: {int(self.eot)}m {int((self.eot % 1) * 60)}s"],  
            marker=dict(color=color_map[self.id]),  
            cliponaxis=True,
            textposition='inside'
        ))
        return figure
    #endregion
    #region: Funzioni Json
    def to_dict(self):
        return {
            "id": self.id,
            "eot": self.eot,
            "day": self.day,
            "mtb": self.mtb
        }
    @classmethod
    def from_dict(cls, data):
        return cls(data['id'], data['eot'], data['day'], data['mtb'])
    #endregion


@dataclass
class DailySchedule:
    day: Day
    patients: List[Patient]
    _minute_of_the_day_: int = 480

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
        return cls(Day[data['day']], patients)
#endregion

@dataclass
class Week:
    def __init__(self, weekNum: int):
        self.weekNum = weekNum
        self.dailySchedule = [
            DailySchedule(day=Day.Lun, patients=[]),
            DailySchedule(day=Day.Mar, patients=[]),
            DailySchedule(day=Day.Mer, patients=[]),
            DailySchedule(day=Day.Gio, patients=[]),
            DailySchedule(day=Day.Ven, patients=[]),
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
        week.dailySchedule = [DailySchedule.from_dict(d) for d in data ["days"]]
        return week
    #endregion


    