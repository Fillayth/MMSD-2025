import csv
import os
import random
from typing import List
from dataclasses import dataclass

@dataclass
class Paziente:
    id:int #num paziente
    dr:int #giorno di inserimento in giorni
    mtb:int #massimo tempo di attesa in giorni
    p:float #tempo dell'operazione in minuti
    ds:int = -1 #giorno operazione in giorni popolato quando viene assegnato a una sala operatoria


I = List[Paziente]  #insieme dei pazienti
K = list[int]  #insieme delle sale operatorie
T = list[int]  #insieme dei giorni lavorativi
i:int #num paziente
k: int #num sala operatoria
t: int #num giorno lavorativo

ORs = List[List[List[Paziente]]] #insieme degli interveti assegnati alle sale operatorie, registro gli id dei pazienti
s =List[List[int]] #tempo della sala operatoria k,t

#Metodo0 = popolo la lista delle sale operatorie per Massimizzare l'utilizzo delle sale operatorie
def Metodo0(I: List[Paziente], K: List[int], T: List[int], ORs: List[List[List[Paziente]]], s: List[List[float]]) -> List[List[List[Paziente]]]:
    """
    Metodo 0: Massimizzare l'utilizzo delle sale operatorie.
    """
    # Ordina i pazienti per tempo di operazione decrescente e giorno di inserimento crescente
    pazienti_ordinati = sorted(sorted(I, key=lambda x: x.p, reverse=True), key=lambda x: x.dr)
    
    for paziente in pazienti_ordinati:
        assegnato = False
        for t in T:
            if t >= paziente.dr and t <= paziente.dr + paziente.mtb: # per vedere i pazienti che escono dai tempi massimi di attesa
            # if t >= paziente.dr : # per avere tutti i pazienti assegnati
                for k in K:
                    tempo_disponibile = s[k][t] - sum(i.p for i in ORs[k][t])
                    if tempo_disponibile >= paziente.p:
                        ORs[k][t].append(paziente)
                        paziente.ds = t
                        assegnato = True
                        break
                if assegnato:
                    break
    return ORs
 
#verifica funzionamento dei metodi 
def stampaAssegnazioni(ORs: List[List[List[Paziente]]], K: List[int], T: List[int]) -> None:
    for k in K:
        for t in T:
            if ORs[k][t]:
                pazienti_ids = [p.id for p in ORs[k][t]]
                print(f"Sala Operatoria {k}, Giorno {t}: Pazienti {pazienti_ids}")

if __name__ == "__main__":
    #leggo i dati da file csv
    pazienti: I = []
    csv_file = 'patients_data.csv'  # Percorso del file CSV
    csv_file =  os.path.abspath('Test\\Prove\\' + csv_file)
    with open(csv_file, mode='r', newline='', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            _ = row["Specialty"].strip()
            paziente = Paziente(
                id=int(row["Patient ID"]),
                dr=int(row["Day (Day Added to Waiting List)"]),
                mtb=int(row["MTB (Priority, max waiting days)"]),
                p=float(row["EOT (Estimated Operation Time in minutes)"])
            )
            pazienti.append(paziente)
    # Definire sale operatorie e giorni lavorativi
    num_sale_operatorie = 2
    num_giorni_lavorativi = 40
    sale_operatorie: K = list(range(num_sale_operatorie))
    giorni_lavorativi: T = list(range(num_giorni_lavorativi))
    tempo_disponibile: List[List[float]] = [[480 for _ in giorni_lavorativi] for _ in sale_operatorie]  # 8 ore per giorno
    # Definire il tempo disponibile per ogni sala operatoria in ogni giorno (in minuti)

    assegnazioni: ORs = [[[] for _ in giorni_lavorativi] for _ in sale_operatorie]
    # Eseguire il Metodo 0
    assegnazioni = Metodo0(pazienti, sale_operatorie, giorni_lavorativi, assegnazioni, tempo_disponibile)
    # Stampare le assegnazioni      
    stampaAssegnazioni(assegnazioni, sale_operatorie, giorni_lavorativi)
    # stampo le assegnazioni e i pazienti su csv
    with open('Test/Prove/assegnazioni.csv', mode='w', newline='') as file:
        fieldnames = ['id', 'dr', 'mtb', 'p', 'ds']
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        pazienti_ordinati = sorted(pazienti, key=lambda x: x.ds)
        for paziente in pazienti_ordinati:
            writer.writerow({
                'id': paziente.id,
                'dr': paziente.dr,
                'mtb': paziente.mtb,
                'p': paziente.p,
                'ds': paziente.ds
            })            
    
