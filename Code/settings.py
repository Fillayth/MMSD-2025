import pyomo.environ as pyo


class Settings:
    """Configuration settings for the simulation."""
    #region Global Settings
    # Number of workstations per specialty
    workstations_config = {
        "Specialty A": 2
        # "Specialty B": 3,
        # "Specialty C": 1
        }
    #endregion
    # 
    #     
    #region CSV Generation Settings
    # Total hours to fill per week
    week_hours_to_fill = 80  # 80 hours
    # Number of weeks to fill
    weeks_to_fill = 3
    #endregion

    #region Optimization Settings
    # Daily operation time limit in minutes
    daily_operation_limit = 480  # 8 hours
    # Weekly operation time limit in minutes
    weekly_operation_limit = 2400  # 40 hours
    # Length of a week in days
    week_length_days = 5    
    # Solver configuration
    solver = pyo.SolverFactory('cplex_direct')
    #endregion

