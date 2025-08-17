import json
from Grafici.Graph import MakeGraph
from RecordGeneration.PatientRecordGenerator import generate_csv
from Simulatore.Simulation import PatientListForSpecialties, read_and_split_by_operation_with_metadata, group_daily_with_mtb_logic, export_json_schedule
from Code.Simulatore.Optimizer import group_weekly_with_mtb_logic_optimized
import os

def main():
    """
    Main function to generate patient records and weekly reports.
    """
    #specialties = ["Specialty A"]  # Insert necessary specialties here
    workstations_config = {
    "Specialty A": 2
    # "Specialty B": 3,
    # "Specialty C": 1
    }

    specialties = list(workstations_config.keys())

    weekly_hours = 80  # Total available hours for operations per week
    K2_params = {'distribution': 'lognormal', 'mean': 1.980694593, 'std': 0.5021391517}
    K7_params = {'distribution': 'gamma', 'shape': 3.25036037, 'scale': 4.22461821}
    K8_params = {'distribution': 'lognormal', 'mean': 2.529958165, 'std': 0.7196641252}
    K9_params = {'distribution': 'lognormal', 'mean': 1.238535974, 'std': 0.6021773292}
    K3_params = {'distribution': 'lognormal', 'mean': 1.59782238, 'std': 0.6741858934}

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/Data"
    
    paths = generate_csv(
        specialties=specialties,
        weekly_hours=weekly_hours,
        num_weeks=52,
        seed=None,
        K2_params=K2_params,
        K7_params=K7_params,
        K8_params=K8_params,
        K9_params=K9_params,
        K3_params=K3_params,
        people_distribution='poisson',
        priority_distribution='normal',
        priority_mean=15,
        priority_std=5,
        filepath=project_root
    )

    project_root = os.path.dirname(os.path.abspath(paths[0]))

    all_patient_records = read_and_split_by_operation_with_metadata(paths[0])
    
    # gestire le sale operatorie(max 3) per ogni specialità
    #weekly_patient_records = [for specialty in all_patient_records.values() for specialty in specialty.]

    # dividere la lista dei pazienti per specialità
    # selezionare i pazienti della prima (o prime) settimana ed eseguire la schedulazione 
    # ciclare per le segueti settimane le schedulazioni
    
    # schedule = PatientListForSpecialties()
    # for specialty_type in schedule:
    #     schedule[specialty_type] = group_daily_with_mtb_logic(all_patient_records[specialty_type])
    
    
    # creRE operazioni di ottimizzazione dei tempi delle schedulazioni

    schedule = group_weekly_with_mtb_logic_optimized(
        all_patient_records,
        weekly_limit=2400,
        week_length_days=5,
        workstations_per_type=workstations_config,
        seed=2915453889
    )

    scheduleJson_path = export_json_schedule(schedule, project_root)


    # caricare alla fine delle schedulazioni tutti i risultati e gestire in qualche modo la visualizzazione 

    with open(scheduleJson_path, 'r', encoding='utf-8') as file:
        data = json.load(file)
        
    MakeGraph(PatientListForSpecialties.from_dict(data))



if __name__ == "__main__":
    main()  

    