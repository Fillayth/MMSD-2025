import pyomo.environ as pyo
import time


class Settings:
    """Configuration settings for the simulation."""
    #region Global Settings


    seed = 1 # Random seed for reproducibility
    #seed = None  # Random seed for reproducibility
    # Specialities and number of workstations per specialty
    workstations_config = {
        "Specialty A": 2
        # "Specialty B": 3,
        # "Specialty C": 1
        }
    
    solver_tee = False  # Whether to display solver output
    def GetSeed():
        if Settings.seed is None:
            Settings.seed = int(time.time() * 1000) % (2**32 - 1)
        return Settings.seed
    #endregion
     
    #region CSV Patient Generation Settings
    # Total hours to fill per week
    week_hours_to_fill = 80  # 80 hours
    # Number of weeks to fill
    weeks_to_fill = 4

    specialty_params = {
        "Specialty A": {
            'K2': {'distribution': 'lognormal', 'mean': 1.98, 'std': 0.50},
            'K7': {'distribution': 'gamma', 'shape': 3.25, 'scale': 4.22},
            'K8': {'distribution': 'lognormal', 'mean': 2.53, 'std': 0.72},
            'K9': {'distribution': 'lognormal', 'mean': 1.24, 'std': 0.60},
            'K3': {'distribution': 'lognormal', 'mean': 1.60, 'std': 0.67}
        },
        "Specialty B": {
            'K2': {'distribution': 'lognormal', 'mean': 2.10, 'std': 0.55},
            'K7': {'distribution': 'gamma', 'shape': 3.50, 'scale': 4.50},
            'K8': {'distribution': 'lognormal', 'mean': 2.70, 'std': 0.80},
            'K9': {'distribution': 'lognormal', 'mean': 1.30, 'std': 0.65},
            'K3': {'distribution': 'lognormal', 'mean': 1.70, 'std': 0.70}
        }
    }

    priority_params = {
        "Specialty A": {
            "distribution": "normal",
            "mean": 15,
            "std": 5
        },
        "Specialty B": {
            "distribution": "normal",
            "mean": 20,
            "std": 7
        }
    }

    #endregion

    #region CSV Results Settings
    results_filepath = "./Data/"
    
    results_filename = "Results.csv"
    #endregion

    #region Optimization Settings
    start_week_scheduling = 1  # Week number to start scheduling from (1-indexed)
    # Daily operation time limit in minutes
    daily_operation_limit = 480  # 8 hours
    # Weekly operation time limit in minutes
    weekly_operation_limit = 2400  # 40 hours
    # Length of a week in days 
    week_length_days = 5    
    # Solver configuration
    solver = pyo.SolverFactory('cplex')  # Use CPLEX solver
    #endregion

