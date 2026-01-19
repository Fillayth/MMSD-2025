import os

from Grafici.Graph import Graphs
from RecordGeneration.PatientRecordGenerator import generate_csv
from settings import Settings
from Simulatore.Simulation import group_daily_with_mtb_logic_rot, group_daily_with_mtb_logic_optimized, read_and_split_by_operation_with_metadata, group_daily_with_mtb_logic, export_json_schedule, ExportCSVResults, ExportCSVAnalysisResults, group_daily_with_mtb_logic_optimized_rot


# Main function to generate patient records and weekly reports
def main():
    """
    Main function to generate patient records and weekly reports.
    """
    #specialties = ["Specialty A"]  # Insert necessary specialties here
    specialties = list(Settings.workstations_config.keys())

    weekly_hours = Settings.week_hours_to_fill  # Total available hours for operations per week
    K2_params = {'distribution': 'lognormal', 'mean': 1.980694593, 'std': 0.5021391517}
    K7_params = {'distribution': 'gamma', 'shape': 3.25036037, 'scale': 4.22461821}
    K8_params = {'distribution': 'lognormal', 'mean': 2.529958165, 'std': 0.7196641252}
    K9_params = {'distribution': 'lognormal', 'mean': 1.238535974, 'std': 0.6021773292}
    K3_params = {'distribution': 'lognormal', 'mean': 1.59782238, 'std': 0.6741858934}

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/Data"
    
    paths = generate_csv(
        specialties=specialties,
        weekly_hours=weekly_hours,
        num_weeks=Settings.weeks_to_fill,
        seed=Settings.GetSeed(), #197558074,
        specialty_params=Settings.specialty_params,
        people_distribution='poisson',
        priority_params=Settings.priority_params,  # <-- passa il nuovo dizionario
        filepath=project_root
    )

    resultsData_folder = os.path.dirname(os.path.abspath(paths[0]))

    all_patient_records = read_and_split_by_operation_with_metadata(paths[0])

    if False:
        schedule = group_daily_with_mtb_logic_optimized(all_patient_records) #togliere il commento per usare la versione precedente

        # try :
        #     schedule = group_daily_with_mtb_logic_optimized(all_patient_records) #togliere il commento per usare la versione precedente
        #     #schedule = group_daily_with_mtb_logic_rot(all_patient_records)
        # except Exception as e:
        #     print("Errore durante l'ottimizzazione giornaliera:", e)
        #     print("Si ripiega sulla versione non ottimizzata.")

        #     schedule = group_daily_with_mtb_logic(all_patient_records) #mi sono finite le licenze di cplex
        
        scheduleJson_path = export_json_schedule(schedule.to_dict(), resultsData_folder)
        # caricare alla fine delle schedulazioni tutti i risultati e gestire in qualche modo la visualizzazione 
        Graphs(f"{resultsData_folder}{Settings.images_folder}").MakeGraphs(schedule)
        ExportCSVResults(schedule, "./Data/Normal/")
        ExportCSVAnalysisResults(schedule, f"{project_root}/Normal")
    else:

        schedule = group_daily_with_mtb_logic_optimized_rot(all_patient_records)
        scheduleJson_path = export_json_schedule(schedule.to_dict(), resultsData_folder + "/Rot")
        # caricare alla fine delle schedulazioni tutti i risultati e gestire in qualche modo la visualizzazione 
        Graphs(f"{resultsData_folder}{Settings.images_folder}/Rot").MakeGraphs(schedule)
        ExportCSVResults(schedule, "./Data/Normal/")
        ExportCSVAnalysisResults(schedule, f"{project_root}/Normal")


if __name__ == "__main__":
    main()  

    