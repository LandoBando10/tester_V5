#!/usr/bin/env python3
"""
Visualize hardware test results
Generates plots from the JSON output files of hardware validation tests
"""

import json
import os
import sys
import argparse
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime

def plot_relay_switching_speed(filepath):
    """Plot relay switching speed results"""
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    results = data['results']
    
    # Extract data
    configs = [r['configuration'] for r in results]
    avg_times = [r['avg_switching_ms'] for r in results]
    std_devs = [r['std_dev_ms'] for r in results]
    
    # Create bar plot
    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(configs))
    bars = ax.bar(x, avg_times, yerr=std_devs, capsize=10)
    
    ax.set_xlabel('Configuration')
    ax.set_ylabel('Switching Time (ms)')
    ax.set_title('Relay Switching Speed by Configuration')
    ax.set_xticks(x)
    ax.set_xticklabels(configs, rotation=45, ha='right')
    
    # Add value labels on bars
    for bar, avg in zip(bars, avg_times):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{avg:.1f}ms', ha='center', va='bottom')
    
    plt.tight_layout()
    return fig

def plot_measurement_accuracy(filepath):
    """Plot measurement accuracy results"""
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    results = data['results']
    
    # Create subplots for voltage and current CV
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    
    configs = [r['configuration'] for r in results]
    voltage_cvs = [r['voltage_cv_percent'] for r in results]
    current_cvs = [r['current_cv_percent'] for r in results]
    
    # Voltage CV plot
    x = np.arange(len(configs))
    ax1.bar(x, voltage_cvs, color='blue', alpha=0.7)
    ax1.axhline(y=5.0, color='r', linestyle='--', label='5% limit')
    ax1.set_xlabel('Configuration')
    ax1.set_ylabel('Coefficient of Variation (%)')
    ax1.set_title('Voltage Measurement Consistency')
    ax1.set_xticks(x)
    ax1.set_xticklabels(configs, rotation=45, ha='right')
    ax1.legend()
    
    # Current CV plot
    ax2.bar(x, current_cvs, color='green', alpha=0.7)
    ax2.axhline(y=10.0, color='r', linestyle='--', label='10% limit')
    ax2.set_xlabel('Configuration')
    ax2.set_ylabel('Coefficient of Variation (%)')
    ax2.set_title('Current Measurement Consistency')
    ax2.set_xticks(x)
    ax2.set_xticklabels(configs, rotation=45, ha='right')
    ax2.legend()
    
    plt.tight_layout()
    return fig

def plot_timing_jitter(filepath):
    """Plot timing jitter analysis"""
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    stats = data['statistics']
    samples = data['samples']
    
    # Extract timing errors
    errors = [s['error_ms'] for s in samples]
    
    # Create figure with subplots
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(12, 10))
    
    # Histogram of timing errors
    ax1.hist(errors, bins=30, edgecolor='black', alpha=0.7)
    ax1.axvline(x=0, color='r', linestyle='--', label='Expected')
    ax1.set_xlabel('Timing Error (ms)')
    ax1.set_ylabel('Frequency')
    ax1.set_title('Timing Error Distribution')
    ax1.legend()
    
    # Time series of actual timing
    iterations = [s['iteration'] for s in samples]
    actual_times = [s['actual_ms'] for s in samples]
    expected_time = stats['expected_time_ms']
    
    ax2.plot(iterations, actual_times, 'b-', alpha=0.7, label='Actual')
    ax2.axhline(y=expected_time, color='r', linestyle='--', label='Expected')
    ax2.set_xlabel('Iteration')
    ax2.set_ylabel('Execution Time (ms)')
    ax2.set_title('Timing Consistency Over Iterations')
    ax2.legend()
    
    # Box plot of errors
    ax3.boxplot(errors, vert=True)
    ax3.set_ylabel('Timing Error (ms)')
    ax3.set_title('Timing Error Box Plot')
    ax3.grid(True, alpha=0.3)
    
    # Statistics summary
    stats_text = f"Mean Error: {stats['mean_error_ms']:.2f} ms\n"
    stats_text += f"Std Dev: {stats['std_dev_ms']:.2f} ms\n"
    stats_text += f"Peak-to-Peak: {stats['peak_to_peak_ms']:.2f} ms\n"
    stats_text += f"P95: {stats['percentiles']['p95']:.2f} ms\n"
    stats_text += f"P99: {stats['percentiles']['p99']:.2f} ms"
    
    ax4.text(0.1, 0.5, stats_text, transform=ax4.transAxes,
             fontsize=12, verticalalignment='center',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    ax4.axis('off')
    ax4.set_title('Jitter Statistics')
    
    plt.tight_layout()
    return fig

def plot_thermal_behavior(filepath):
    """Plot thermal behavior over time"""
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    raw_data = data['raw_data']
    analysis = data['analysis']
    
    # Extract time series data
    times = []
    currents_by_channel = {}
    
    for record in raw_data:
        times.append(record['elapsed_minutes'])
        for key, meas in record['measurements'].items():
            if key not in currents_by_channel:
                currents_by_channel[key] = []
            currents_by_channel[key].append(meas['current'])
    
    # Create plot
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Plot each channel
    for channel, currents in currents_by_channel.items():
        ax.plot(times, currents, label=channel, alpha=0.7)
    
    ax.set_xlabel('Time (minutes)')
    ax.set_ylabel('Current (A)')
    ax.set_title('Thermal Behavior - Current vs Time')
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    ax.grid(True, alpha=0.3)
    
    # Add drift annotations
    for channel, stats in analysis.items():
        drift_pct = stats['current_drift_percent']
        ax.text(0.02, 0.98 - 0.05 * list(analysis.keys()).index(channel),
                f"{channel}: {drift_pct:.1f}% drift",
                transform=ax.transAxes,
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    plt.tight_layout()
    return fig

def plot_emi_noise(filepath):
    """Plot EMI/noise test results"""
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    results = data['results']
    
    # Create figure
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    
    # Extract noise data
    test_names = []
    voltage_noise = []
    current_noise = []
    
    for result in results:
        if 'noise' in result:
            test_names.append(result['test'])
            voltage_noise.append(result['noise']['voltage_std'] * 1000)  # Convert to mV
            current_noise.append(result['noise']['current_std'] * 1000)  # Convert to mA
    
    # Voltage noise plot
    x = np.arange(len(test_names))
    ax1.bar(x, voltage_noise, color='blue', alpha=0.7)
    ax1.set_xlabel('Test Condition')
    ax1.set_ylabel('Voltage Noise (mV RMS)')
    ax1.set_title('Voltage Noise by Condition')
    ax1.set_xticks(x)
    ax1.set_xticklabels(test_names)
    
    # Current noise plot
    ax2.bar(x, current_noise, color='green', alpha=0.7)
    ax2.set_xlabel('Test Condition')
    ax2.set_ylabel('Current Noise (mA RMS)')
    ax2.set_title('Current Noise by Condition')
    ax2.set_xticks(x)
    ax2.set_xticklabels(test_names)
    
    # Add crosstalk data if available
    for result in results:
        if result['test'] == 'crosstalk' and 'max_crosstalk' in result:
            crosstalk = result['max_crosstalk']['current'] * 1000  # mA
            ax2.axhline(y=crosstalk, color='r', linestyle='--', 
                       label=f'Max crosstalk: {crosstalk:.1f}mA')
            ax2.legend()
    
    plt.tight_layout()
    return fig

def main():
    parser = argparse.ArgumentParser(description='Visualize hardware test results')
    parser.add_argument('--input-dir', default='.', help='Directory containing test output files')
    parser.add_argument('--output-dir', default='./plots', help='Directory for saving plots')
    parser.add_argument('--show', action='store_true', help='Show plots interactively')
    args = parser.parse_args()
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Test result files and their plot functions
    test_files = {
        'relay_switching_speed.json': ('Relay Switching Speed', plot_relay_switching_speed),
        'measurement_accuracy.json': ('Measurement Accuracy', plot_measurement_accuracy),
        'timing_jitter_analysis.json': ('Timing Jitter', plot_timing_jitter),
        'thermal_behavior.json': ('Thermal Behavior', plot_thermal_behavior),
        'emi_noise_test.json': ('EMI/Noise', plot_emi_noise)
    }
    
    plots_generated = 0
    
    for filename, (title, plot_func) in test_files.items():
        filepath = os.path.join(args.input_dir, filename)
        if os.path.exists(filepath):
            try:
                print(f"Generating {title} plot...")
                fig = plot_func(filepath)
                
                # Save plot
                output_path = os.path.join(args.output_dir, f"{filename.replace('.json', '.png')}")
                fig.savefig(output_path, dpi=300, bbox_inches='tight')
                print(f"  Saved to: {output_path}")
                
                if args.show:
                    plt.show()
                else:
                    plt.close(fig)
                
                plots_generated += 1
                
            except Exception as e:
                print(f"  Error: {e}")
        else:
            print(f"Skipping {title} - file not found: {filepath}")
    
    print(f"\nGenerated {plots_generated} plots in {args.output_dir}")
    
    if plots_generated > 0 and not args.show:
        print("\nUse --show flag to display plots interactively")

if __name__ == "__main__":
    main()