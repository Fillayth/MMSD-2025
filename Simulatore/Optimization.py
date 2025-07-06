import json

from typing import List 

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'CommonClass'))) ## se si crea un file comune in MMSD-2025 che poi orchestra tutte le risorse questo comando non serve 

from CommonClass import Operations, Patient, Week, DailySchedule

#carica i dati della soluzione 
class GreedySolution:
    def __init__(self):
        file_path = "weekly_schedule.json"
        with open(file_path, mode='r', newline='', encoding='utf-8') as f:
            data = json.load(f)
        
        self.operations = Operations.from_dict(data)

class BasicTabuSearch:
    currentSolution = Operations()
    def __init__(self):
        self.startSolution = GreedySolution()
        pass

    def __setitem__(self, key, value):
        self.currentSolution[key] = value

    def __getitem__(self, key):
        return self.currentSolution[key]

    def p_SwapInIn(day1 : DailySchedule, day2 : DailySchedule):
        #seleziono i due giorni 
        # remaingTime = day1._minute_of_the_day_ - day1.getTime()
        # listPatients = [Patient(p.id, p.eot + remaingTime, p.day, p.mtb) for p in day1.patients] 
        #in un ciclo muovo solo un paziente volta dal giorno due con al posto di uno del giorno uno per vedere se il tempo restante diminuisce  
        copyDay1 = day1.copy()
        copyDay2 = day2.copy()
        remaingTime = lambda day: day._minute_of_the_day_ - day.getTime()   
        for p1 in copyDay1.patients:
            for p2 in copyDay2.patients:
                #verifico che sia accettabile 
                if copyDay1.swapPatient(p1,p2):
                    if copyDay2.swapPatient(p2, p1):
                        pass
                    else:
                        copyDay1.swapPatient(p2, p1)
                #verfico se è milgiorante o peggiorante 
                temp = remaingTime(day1) - remaingTime(copyDay1) 
                if temp == 0:
                    #non cambia
                    pass
                elif temp > 0:
                    #migliorativo 
                    pass
                else: # temp < 0
                    #peggiorativo 
                    pass

        pass

    def p_SwapInOut():
        pass
    
    def p_SwapOutIn():
        pass

    def s_SwapInIN():
        pass
        
    def p_DropFromIn():
        pass

    def intensification():
        pass

    def diversification():
        pass

    def FindBest():
        pass