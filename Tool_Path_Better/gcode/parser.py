# G-code parsing utilities
# This module provides functions to extract layers from a G-code file.

def extract_layers(gcode_path):
    """
    Extracts layer numbers from a G-code file.
    Returns a list of layer indices or identifiers.
    """
    layers = []
    try:
        with open(gcode_path, 'r') as f:
            for line in f:
                if line.startswith(';LAYER:'):
                    layer_num = line.strip().split(':')[1]
                    layers.append(layer_num)
        return layers
    except Exception as e:
        raise RuntimeError(f"Error reading G-code file: {e}")

# TODO: Add more advanced G-code parsing and toolpath extraction
