import csv
import os
import random
from typing import List
from dataclasses import dataclass

@dataclass
class Paziente:
    id:int #num paziente
    dr:int #giorno di inserimento
    ds:int #giorno operazione
    p:float #tempo dell'operazione
    LOS:int #durata degenza
    
    def w (self) -> int:  
        if self.ds - self.dr > 0 : 
            return self.ds - self.ds 
        else :
            return 0 #giorni di attesa

I = List[Paziente]  #insieme dei pazienti
K = list[int]  #insieme delle sale operatorie
T = list[int]  #insieme dei giorni lavorativi
i:int #num paziente
k: int #num sala operatoria
t: int #num giorno lavorativo

ORs = List[List[int]] #insieme degli interveti assegnati alle sale operatorie
#s =List[List[int]] #tempo della sala operatoria k,t

#imposto il vincolo per cui il LOS del paziente deve essere compreso tra 1 e 3 comprendendo il giorno dell'operazione
def getLOS():
    return random.randint(1,3)
# assert all(LOSrule(p) for p in I), "Errore: La durata di degenza (LOS) deve essere compresa tra 1 e 3 giorni."
x = lambda i, k, t: 1 if (i.ds == t and i in ORs[k][t]) else 0 #variabile binaria che indica se il paziente i è assegnato alla sala operatoria k nel giorno t

def Metodo0(I: List[Paziente], K: List[int], T: List[int], ORs: List[List[List[Paziente]]], s: List[List[float]]) -> float:
    """
    Metodo 0: Massimizzare l'utilizzo delle sale operatorie.
    """
    # Calcolare l'utilizzo totale delle sale operatorie
    utilizzo_totale = sum(
        sum(i.p for i in ORs[k][t]) / s[k][t] if s[k][t] > 0 else 0
        for k in K for t in T
    )
    return utilizzo_totale

def Metodo1(I: List[Paziente], K: List[int], T: List[int], ORs: List[List[List[Paziente]]], s: List[List[float]]) -> float:
    """
    Metodo 1: Minimizzare il tempo di attesa totale dei pazienti.
    """
    # Calcolare il tempo di attesa totale dei pazienti
    tempo_attesa_totale = sum(i.w() for i in I)
    return tempo_attesa_totale

def Metodo2(I: List[Paziente], K: List[int], T: List[int], ORs: List[List[List[Paziente]]], s: List[List[float]]) -> float:
    """
    Metodo 2: Bilanciare l'utilizzo delle sale operatorie e il tempo di attesa dei pazienti.
    """
    utilizzo_totale = Metodo0(I, K, T, ORs, s)
    tempo_attesa_totale = Metodo1(I, K, T, ORs, s)
    
    # Calcolare un punteggio bilanciato (ad esempio, peso 0.5 per entrambi gli obiettivi)
    punteggio_bilanciato = 0.5 * (utilizzo_totale) - 0.5 * (tempo_attesa_totale)
    return punteggio_bilanciato

def Metodo3(I: List[Paziente], K: List[int], T: List[int], ORs: List[List[List[Paziente]]], s: List[List[float]]) -> float:
    """
    Metodo 3: Ottimizzare l'assegnazione dei pazienti alle sale operatorie per minimizzare il tempo di attesa
    e massimizzare l'utilizzo delle sale operatorie.
    """
    utilizzo_totale = Metodo0(I, K, T, ORs, s)
    tempo_attesa_totale = Metodo1(I, K, T, ORs, s)
    
    # Calcolare un punteggio combinato (ad esempio, peso 0.7 per l'utilizzo e 0.3 per il tempo di attesa)
    punteggio_combinato = 0.7 * (utilizzo_totale) - 0.3 * (tempo_attesa_totale)
    return punteggio_combinato



# Esempio di utilizzo
if __name__ == "__main__":
    # Definire un insieme di pazienti
    # I = [
    #     Paziente(id=1, dr=0, ds=2, p=2.0, LOS=2),
    #     Paziente(id=2, dr=1, ds=3, p=1.5, LOS=1),
    #     Paziente(id=3, dr=0, ds=1, p=3.0, LOS=3),
    # ]
    csv_file = 'patients_data.csv'  # Percorso del file CSV
    csv_file =  os.path.abspath('Test\\Prove\\' + csv_file)
    I = []
    with open(csv_file, mode='r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            sp_type = row["Specialty"].strip()
            dr = int(row["Day (Day Added to Waiting List)"])
            w = int(row["MTB (Priority, max waiting days)"])
            ds = random.randint(dr, dr + w)
            los = getLOS()
            I.append(Paziente(
                id=int(row["Patient ID"]),
                p=float(row["EOT (Estimated Operation Time in minutes)"]),
                dr=dr,
                ds= ds, #assegno in modo casuale il giorno dell'operazione tra il giorno di inserimento e il massimo tempo di attesa
                LOS= los #assegno in modo casuale la durata della degenza tra 1 e 3 giorni
            ))


    # Definire sale operatorie e giorni lavorativi
    K = [0, 1]  # Sale operatorie
    T = [0, 1, 2, 3, 4]  # Giorni lavorativi
    
    # Definire gli interventi assegnati alle sale operatorie (esempio fittizio)
    ORs = [
        [  # Sala operatoria 0
            [I[0]],    # Giorno 0
            [I[2]],    # Giorno 1
            [],        # Giorno 2
            [I[1]],    # Giorno 3
            []         # Giorno 4
        ],
        [  # Sala operatoria 1
            [],        # Giorno 0
            [],        # Giorno 1
            [I[0]],    # Giorno 2
            [],        # Giorno 3
            [I[1], I[2]]  # Giorno 4
        ]
    ]
    
    # Definire il tempo disponibile per ogni sala operatoria in ogni giorno (esempio fittizio)
    s = [
        [4.0, 4.0, 4.0, 4.0],  # Sala operatoria 0
        [4.0, 4.0, 4.0, 4.0]   # Sala operatoria 1
    ]
    
    # Calcolare e stampare i risultati dei metodi
    print("Utilizzo totale delle sale operatorie (Metodo 0):", Metodo0(I, K, T, ORs, s))
    print("Tempo di attesa totale dei pazienti (Metodo 1):", Metodo1(I, K, T, ORs, s))
    print("Punteggio bilanciato (Metodo 2):", Metodo2(I, K, T, ORs, s))
    print("Punteggio combinato (Metodo 3):", Metodo3(I, K, T, ORs, s))

