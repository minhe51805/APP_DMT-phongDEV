import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from typing import List, Tuple, Optional

def load_csi_data(file_path: str) -> pd.DataFrame:
    """Load CSI data from CSV file"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"CSI data file not found: {file_path}")
    
    return pd.read_csv(file_path)

def process_csi_data(df: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
    """Process CSI data from DataFrame into numpy array"""
    # Get list of subcarrier columns
    subcarriers = [col for col in df.columns if "subcarrier" in col and "_im" not in col]
    if not subcarriers:
        # If no subcarrier columns found, try parsing raw_csi column
        if 'raw_csi' in df.columns:
            # Split raw_csi values and convert to float array
            csi_data = np.array([row.split(',') for row in df['raw_csi'].astype(str)])
            csi_data = csi_data.astype(float)
            subcarriers = [f"subcarrier_{i}" for i in range(csi_data.shape[1])]
            return csi_data.T, subcarriers
        else:
            raise ValueError("No CSI data columns found in the file")
    
    # Convert to numpy array
    csi_amplitude = np.array([df[col] for col in subcarriers])
    return csi_amplitude, subcarriers

def plot_csi_timeseries(csi_data: np.ndarray, 
                       subcarriers: List[str], 
                       max_plots: int = 6,
                       figsize: Tuple[int, int] = (12, 8)) -> None:
    """Plot CSI data as time series"""
    num_plots = min(max_plots, len(subcarriers))
    rows = (num_plots + 1) // 2  # Calculate rows needed for subplot grid
    
    # Create subplot grid
    fig, axes = plt.subplots(rows, 2, figsize=figsize)
    axes = axes.flatten() if rows > 1 else [axes]
    
    # Plot data for each subcarrier
    for i in range(num_plots):
        axes[i].plot(csi_data[i], label=f"Subcarrier {i}", linewidth=1)
        axes[i].set_xlabel("Time (Samples)")
        axes[i].set_ylabel("CSI Amplitude")
        axes[i].set_title(f"CSI - {subcarriers[i]}")
        axes[i].legend()
        axes[i].grid(True)
    
    # Remove empty subplots
    for i in range(num_plots, len(axes)):
        fig.delaxes(axes[i])
    
    plt.tight_layout()

def plot_csi_heatmap(csi_data: np.ndarray, 
                     title: str = "CSI Amplitude Heatmap",
                     figsize: Tuple[int, int] = (10, 6)) -> None:
    """Plot CSI data as a heatmap"""
    plt.figure(figsize=figsize)
    plt.imshow(csi_data, aspect='auto', cmap='viridis')
    plt.colorbar(label='Amplitude')
    plt.title(title)
    plt.xlabel('Time Sample')
    plt.ylabel('Subcarrier')
    plt.tight_layout()

def analyze_csi_data(file_path: str, 
                    plot_type: str = 'both',
                    max_subcarriers: int = 6) -> None:
    """
    Analyze CSI data and create visualizations
    
    Parameters:
        file_path: Path to CSI data file
        plot_type: Type of plot ('timeseries', 'heatmap', or 'both')
        max_subcarriers: Maximum number of subcarriers to plot in timeseries
    """
    try:
        # Load and process data
        df = load_csi_data(file_path)
        csi_data, subcarriers = process_csi_data(df)
        
        # Create requested plots
        if plot_type in ['timeseries', 'both']:
            plot_csi_timeseries(csi_data, subcarriers, max_subcarriers)
            
        if plot_type in ['heatmap', 'both']:
            plot_csi_heatmap(csi_data)
        
        plt.show()
        
    except Exception as e:
        print(f"Error analyzing CSI data: {e}")

if __name__ == "__main__":
    # Default file path
    data_file = os.path.join(os.path.dirname(__file__), "csi_data_full.csv")
    
    try:
        # Analyze data with both plot types
        analyze_csi_data(data_file, plot_type='both')
    except KeyboardInterrupt:
        print("\nAnalysis stopped by user")
    except Exception as e:
        print(f"Fatal error: {e}")
