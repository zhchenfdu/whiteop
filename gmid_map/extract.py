import os
import re
# Thresholds used to filter candidate circuits
thresholds = {
    'gain': 100,     # Example value, adjust as needed
    'gbw': 700000,   # Example value, adjust as needed
    'pw': 1000,      # Example value, adjust as needed
    'pm': 60         # Example value, adjust as needed
}
# Regex patterns to extract performance metrics from log
'''performance_patterns = {
    'gain': re.compile(r'\\i gain = .*?\\n\\t\s+([+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?)'),
    'gbw': re.compile(r'\\i gbw = .*?\\n\\t\s+([+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?)'),
    'pw': re.compile(r'\\i pw = .*?\\n\\t\s+([+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?)'),
    'pm': re.compile(r'\\i pm = .*?\\n\\t\s+([+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?)'),
}'''
performance_patterns = {
    'gain': re.compile(r'\\i gain = .*?\n\\t (.+)'),
    'pm': re.compile(r'\\i pm = .*?\n\\t (.+)'),
    'gbw': re.compile(r'\\i gbw = .*?\n\\t (.+)'),
    'pw': re.compile(r'\\i pw = .*?\n\\t (.+)'),
}
# Extract performance values from a single Spectre/Ocean log file
def extract_performance_values(file_path):
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
        content = file.read()
    performance_values = {}
    for key, pattern in performance_patterns.items():
        match = pattern.search(content)
        if match:
            if match.group(1) == 'nil':
                performance_values[key] = 0
            else:
                performance_values[key] = float(match.group(1))
    return performance_values
# Walk directories and collect performance values
def process_directories(first_level_dirs, thresholds):
    performance_data = []
    for dir in first_level_dirs:
        for subdir in os.listdir(dir):
            file_path = os.path.join(dir, os.path.join(subdir, 'sim.log'))
            values = extract_performance_values(file_path)
            # Keep only results that satisfy all threshold conditions
            if (values['gain'] > thresholds['gain'] and values['gbw'] > thresholds['gbw'] and values['pm'] > thresholds['pm'] and values['pw'] < thresholds['pw']):
                performance_data.append({'file': file_path, **values})
    # Sort by GBW/PW ratio in descending order
    performance_data.sort(key=lambda x: x['gbw'] / x['pw'], reverse=True)
    return performance_data
# Top-level directories to search
first_level_directories = [
    'mapped_circuits',
    #'mapped_circuits_033_40_200',
    #'mapped_circuits_033_30',
    #'mapped_circuits_033_10',
    #'mapped_circuits_033_20_500_low_gain_good28',
    #'mapped_circuits_033_30_500_low_gain_good2',
    #'mapped_circuits_033_40_500_low_gain',
    #'mapped_circuits_033_50_500_low_gain'
    # ... more directory paths if needed
]
# Process directories and obtain sorted performance data
sorted_performance_data = process_directories(first_level_directories, thresholds)
# Print top-ranked performance data
s = 0
for data in sorted_performance_data[:10]:
    s += data['gbw'] / data['pw'] / 1e8
    print(f"File: {data['file']}, Gain: {data['gain']}, GBW: {data['gbw']}, PW: {data['pw']}, PM: {data['pm']}, GBW/PW: {data['gbw'] / data['pw'] / 1e8}")
print(s)