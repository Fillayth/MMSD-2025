import os

from Grafici.Graph import MakeGraphs
from RecordGeneration.PatientRecordGenerator import generate_csv
from settings import Settings
from Simulatore.Simulation import group_daily_with_mtb_logic_optimized, read_and_split_by_operation_with_metadata, group_daily_with_mtb_logic, export_json_schedule, ExportCSVResults, ExportCSVAnalysisResults


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
        # seed=None,
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

    # schedule = group_weekly_with_mtb_logic_optimized(
    #     all_patient_records,
    #     weekly_limit=Settings.weekly_operation_limit,
    #     week_length_days=5,
    #     workstations_per_type=Settings.workstations_config,
    #     seed=2915453889
    # )
    try :
        schedule = group_daily_with_mtb_logic_optimized(all_patient_records) 
    except Exception as e:
        print("Errore durante l'ottimizzazione giornaliera:", e)
        print("Si ripiega sulla versione non ottimizzata.")
        schedule = group_daily_with_mtb_logic(all_patient_records) #mi sono finite le licenze di cplex
    # schedule = group_daily_with_mtb_logic(all_patient_records) #mi sono finite le licenze di cplex
    
    scheduleJson_path = export_json_schedule(schedule.to_dict(), project_root)


    # caricare alla fine delle schedulazioni tutti i risultati e gestire in qualche modo la visualizzazione 

    MakeGraphs(schedule)
    ExportCSVResults(schedule)
    ExportCSVAnalysisResults(schedule, project_root)


if __name__ == "__main__":
    main()  

    