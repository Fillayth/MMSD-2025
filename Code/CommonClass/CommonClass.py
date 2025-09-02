from plotly.graph_objects import Figure 
import plotly.graph_objects as go 
from dataclasses import dataclass
from typing import List 

from enum import Enum
from settings import Settings


class Days(Enum):
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
    """ Classe per gestire le liste di pazienti create dividendole per specialità    """
    def __init__(self):
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

@dataclass
class Patient:
    def __init__(self, id: int, eot: float, day: int, mtb: int, workstation: int = -1, overdue: bool = False):
        self.id = id
        self.eot = eot
        self.day = day
        self.mtb = mtb
        self.workstation = workstation
        self.overdue = overdue
    
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
            "mtb": self.mtb,
            "workstation": self.workstation,
            "overdue": self.overdue
        }
    @classmethod
    def from_dict(cls, data):
        return cls(data['id'], data['eot'], data['day'], data['mtb'], data['workstation'], data['overdue'])
    #endregion

@dataclass 
class OperatingRoomShedule:
    id: int
    daily_schedules: List[Patient]
    
    def __init__ (self, id: int, max_time_per_day: int = Settings.daily_operation_limit, patients: List[Patient] = []):
        self.id = id
        self._max_time_per_day_ = max_time_per_day
        self.daily_schedules = patients
    
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
    #region: Funzioni Grafiche 
    def setTrace(self, figure: Figure, color_map, text: str) -> Figure:
        mins = round(self.getTime(), 2)
        for p in self.daily_schedules:
            figure = p.setTrace(figure, color_map, text + f"|Day:{self.day.name}", mins)
        return figure

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


@dataclass
class Day:
    day: Days
    operatingRooms: List[OperatingRoomShedule]
    _minute_of_the_day_: int = Settings.daily_operation_limit

    def __init__ (self, day: Days, operatingRooms: List[OperatingRoomShedule] = []):
        self.day = day
        self.operatingRooms = operatingRooms
        self._minute_of_the_day_ = Settings.daily_operation_limit

    def copy(self):
        copy = Day(self.day, self.operatingRooms)
        return copy

    #region: Funzioni 
    def getTime(self) -> int: 
        return sum(p.eot for p in self.patients)

    def insertPatient(self, patient: Patient) -> bool:
        return self.operatingRooms[patient.workstation-1].insertPatient(patient)
       
        
    def swapPatient(self, patient1: Patient, patient2: Patient) -> bool:
        #toDo
        list = self.patients.copy()
        list.remove(patient1)
        list.insert(patient2)
        if sum(p.eot for p in list) > self._minute_of_the_day_:
            return False
        else:
            self.patients = list
            return True
    
    def patients(self) -> List[Patient]:
        patients = []
        for oroom in self.operatingRooms:
            patients.extend(oroom.daily_schedules)
        return patients
    
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
            "workstations":[opRoom.to_dict() for opRoom in self.operatingRooms]
            #"patients":[p.to_dict() for p in self.patients]
        }
    
    @classmethod
    def from_dict(cls, data):
        #patients = [Patient.from_dict(p) for p in data['patients']]
        operatingRooms = [OperatingRoomShedule.from_dict(opRoom) for opRoom in data['workstations']] 
        return cls(Day[data['day']], operatingRooms)
#endregion


@dataclass
class Week:
    def __init__(self, weekNum: int, specialty: Specialty = Specialty.OpA):
        self.weekNum = weekNum
        if isinstance(specialty, str):
            specialty_enum = next(s for s in Specialty if s.value == specialty)
            self.specialty = specialty_enum
        else:
            self.specialty = specialty
        operatingRooms = []
        for orId in range(Settings.workstations_config[self.specialty.value]):
            operatingRooms.append(OperatingRoomShedule(id=orId))
        self.dailySchedule = [
            # DailySchedule(day=Days.Lun, patients=[]),
            # DailySchedule(day=Days.Mar, patients=[]),
            # DailySchedule(day=Days.Mer, patients=[]),
            # DailySchedule(day=Days.Gio, patients=[]),
            # DailySchedule(day=Days.Ven, patients=[]),
            Day(day=Days.Lun, operatingRooms = operatingRooms.copy()),
            Day(day=Days.Mar, operatingRooms = operatingRooms.copy()),
            Day(day=Days.Mer, operatingRooms = operatingRooms.copy()),
            Day(day=Days.Gio, operatingRooms = operatingRooms.copy()),
            Day(day=Days.Ven, operatingRooms = operatingRooms.copy()),
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
        week.dailySchedule = [Patient.from_dict(d) for d in data["patients"]]
        # week.dailySchedule = [DailySchedule.from_dict(d) for d in data["days"]]
        return week
    #endregion


    