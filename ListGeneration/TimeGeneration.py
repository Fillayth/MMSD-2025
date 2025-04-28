import numpy as np
import random

def generate_time(distribution, **kwargs):
    """
    Genera un tempo in minuti basato sulla distribuzione di probabilità selezionata.

    Parametri:
        distribution (str): Nome della distribuzione ('uniform', 'normal', 'exponential').
        **kwargs: Parametri aggiuntivi per le distribuzioni.

    Ritorna:
        float: Un tempo generato in minuti.
    """
    if distribution == 'uniform':
        # Ottieni il valore minimo (default: 0)
        low = kwargs.get('low', 0)
        # Ottieni il valore massimo (default: 60)
        high = kwargs.get('high', 60)
        # Genera un numero casuale uniformemente distribuito tra low e high
        return round(np.random.uniform(low, high), 4)
    
    elif distribution == 'normal':
        # Ottieni il valore medio (default: 30)
        mean = kwargs.get('mean', 30)
        # Ottieni la deviazione standard (default: 10)
        std_dev = kwargs.get('std_dev', 10)
        # Genera un numero casuale con distribuzione normale
        return round(np.random.normal(mean, std_dev), 4)
    
    elif distribution == 'exponential':
        # Ottieni il parametro di scala (default: 10, corrisponde a 1/lambda)
        scale = kwargs.get('scale', 10)
        # Genera un numero casuale con distribuzione esponenziale
        return round(np.random.exponential(scale), 4)
    
    else:
        # Solleva un'eccezione se la distribuzione non è supportata
        raise ValueError("Distribuzione non supportata. Scegli 'uniform', 'normal' o 'exponential'.")