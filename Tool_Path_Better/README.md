# Tool Path Customization GUI

This project is a Python-based desktop application for customizing 3D printer G-code toolpaths. The application features a modular, extensible GUI (using PyQt5) that allows users to:

- Open and parse G-code files
- Select layers for toolpath modification
- (Planned) Visualize the model and toolpaths in 2D/3D
- (Planned) Edit and save modified toolpaths

## Getting Started

1. Ensure you have Python 3.8+ installed.
2. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
3. Run the application:
   ```powershell
   python main.py
   ```

## Project Structure
- `main.py` — Application entry point
- `gui/` — GUI components (PyQt5)
- `gcode/` — G-code parsing and manipulation logic
- `utils/` — Utility functions
- `.github/copilot-instructions.md` — Copilot custom instructions

## Roadmap
- [x] Basic GUI for file selection and layer selection
- [ ] G-code parsing and layer extraction
- [ ] Toolpath editing interface
- [ ] 2D/3D visualization of toolpaths
- [ ] Save/export modified G-code

## Contributing
Contributions are welcome! Please follow the modular structure and add docstrings to all new functions/classes.
