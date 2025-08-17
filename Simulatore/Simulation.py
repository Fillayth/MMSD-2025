import csv
import json
import random
from Optimizer import group_weekly_with_mtb_logic_optimized

# Reads the CSV file and organizes patient data by operation type
def read_and_split_by_operation_with_metadata(csv_file):
    with open(csv_file, mode='r', newline='', encoding='utf-8') as f:
        content = f.readlines()[2:]  # Skip the first two header lines
        reader = csv.reader(content)
        lines = list(reader)

    ops = {"Operazione A": [], "Operazione B": [], "Operazione C": []}

    for row in lines:
        patient_id, op_type, eot, day, mtb = row
        patient = {
            "id": int(patient_id),
            "eot": float(eot),
            "day": int(day),
            "mtb": int(mtb)
        }
        ops[op_type].append(patient)

    return ops

# Exports the weekly schedule to a JSON file
def export_json_schedule(data, filename="weekly_schedule.json"):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    print(f"JSON exported to {filename}")

# Main program execution
if __name__ == "__main__":
    csv_file = "../ListGeneration/lista_attesa_simulata.csv"
    ops = read_and_split_by_operation_with_metadata(csv_file)

    workstations_config = {
        "Operazione A": 2,  # Example: 2 workstations for Operazione A
        "Operazione B": 3,
        "Operazione C": 1
    }

    # Call the optimized scheduling function
    schedule = group_weekly_with_mtb_logic_optimized(
        ops,
        weekly_limit=2400,
        week_length_days=5,
        workstations_per_type=workstations_config,
        seed=2915453889
    )

    export_json_schedule(schedule)
    print("Schedule generata con successo.")

