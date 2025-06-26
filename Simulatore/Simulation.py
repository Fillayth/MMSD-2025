import csv
import json

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
            "id": int(patient_id),      # Patient ID
            "eot": float(eot),          # Estimated Operation Time
            "day": int(day),            # Day added to the waiting list
            "mtb": int(mtb)             # Maximum time before overdue
        }
        ops[op_type].append(patient)   # Add patient to the corresponding operation list

    return ops

# Groups patients into weekly batches with prioritization based on MTB (Max Time Before overdue)
def group_weekly_with_mtb_logic(ops_dict, weekly_limit=2400, week_length_days=5):
    grouped_schedule = {}

    for op_type, patients in ops_dict.items():
        remaining = patients.copy()  # Patients not yet scheduled
        week_number = 0
        grouped_schedule[op_type] = []  # Initialize weekly schedule for this operation type

        while remaining:
            current_week_start = week_number * week_length_days
            current_week_end = current_week_start + week_length_days - 1
            next_week_end = current_week_end + week_length_days

            batch = []
            total_time = 0

            # Patients overdue this week
            overdue_now = [p for p in remaining if current_week_end - p["day"] >= p["mtb"]]
            # Patients overdue next week
            overdue_next = [p for p in remaining if next_week_end - p["day"] >= p["mtb"]
                            and p not in overdue_now]
            # Patients not yet overdue
            normal = [p for p in remaining if p not in overdue_now and p not in overdue_next]

            # Prioritize: overdue now > overdue next > normal
            ordered = overdue_now + overdue_next + normal

            i = 0
            while i < len(ordered):
                p = ordered[i]
                # Check if patient fits within the weekly EOT limit
                if total_time + p["eot"] <= weekly_limit:
                    batch.append({
                        "id": p["id"],
                        "eot": round(p["eot"], 2),
                        "day": p["day"],
                        "mtb": p["mtb"],
                        "overdue": current_week_end - p["day"] >= p["mtb"]
                    })
                    total_time += p["eot"]
                    remaining.remove(p)
                    ordered.pop(i)  # Patient scheduled, remove from list
                else:
                    i += 1  # Move to next patient

            # Sort patients in batch by descending EOT
            batch.sort(key=lambda x: x["eot"], reverse=True)

            # Add the current week's batch to the schedule
            grouped_schedule[op_type].append({
                "week": week_number + 1,
                "patients": batch
            })

            week_number += 1  # Move to the next week

    return grouped_schedule

# Exports the weekly schedule to a JSON file
def export_json_schedule(data, filename="weekly_schedule.json"):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    print(f"JSON exported to {filename}")

# Main program execution
if __name__ == "__main__":
    ops = read_and_split_by_operation_with_metadata("../ListGeneration/lista_attesa_simulata.csv")
    schedule = group_weekly_with_mtb_logic(ops)
    export_json_schedule(schedule)
