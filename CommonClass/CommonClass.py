
from dataclasses import dataclass
from typing import List 

@dataclass
class Patient:
    id: int
    eot: int
    day: int
    mtb: int
    overdue: int

@dataclass
class Week:
    week: int
    patients: List[Patient]