# GUI module for Tool Path Customization
# Contains the main window and GUI logic

from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog, QWidget, QVBoxLayout, QPushButton, QLabel, QListWidget, QMessageBox, QTextEdit, QTabWidget, QDialog, QDialogButtonBox, QComboBox, QAction
from PyQt5.QtCore import Qt
from gui.viewer3d import Layer3DViewer
import sys
import os

class MainWindow(QMainWindow):
    """
    Main application window for Tool Path Customization.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tool Path Customization")
        self.setGeometry(100, 100, 600, 400)
        self.gcode_file = None
        self.gcode_content = None  # Store loaded G-code content
        self.layers = []
        self.init_ui()

    def init_ui(self):
        widget = QWidget()
        layout = QVBoxLayout()

        self.open_button = QPushButton("Open G-code File")
        self.open_button.clicked.connect(self.open_gcode_file)
        layout.addWidget(self.open_button)

        self.layer_label = QLabel("Total layers: 0")
        layout.addWidget(self.layer_label)

        self.select_layers_button = QPushButton("Select Layers")
        self.select_layers_button.clicked.connect(self.toggle_layer_selection)
        layout.addWidget(self.select_layers_button)

        self.layer_dropdown = QListWidget()
        self.layer_dropdown.setSelectionMode(QListWidget.MultiSelection)
        self.layer_dropdown.setVisible(False)
        layout.addWidget(self.layer_dropdown)

        self.selected_layers_label = QLabel("Selected layers:")
        layout.addWidget(self.selected_layers_label)
        self.selected_layers_frame = QTextEdit()
        self.selected_layers_frame.setReadOnly(True)
        layout.addWidget(self.selected_layers_frame)

        self.view_layer_button = QPushButton("View Selected Layer in 3D")
        self.view_layer_button.clicked.connect(self.open_layer_viewer_dialog)
        self.view_layer_button.setEnabled(False)
        layout.addWidget(self.view_layer_button)

        self.save_button = QPushButton("Save Modified G-code")
        self.save_button.clicked.connect(self.save_gcode_file)
        self.save_button.setEnabled(False)
        layout.addWidget(self.save_button)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Add fullscreen action for 3D viewer
        self.fullscreen_action = QAction("Toggle Fullscreen", self)
        self.fullscreen_action.setShortcut("F11")
        self.fullscreen_action.triggered.connect(self.toggle_fullscreen)
        self.addAction(self.fullscreen_action)
        self.is_fullscreen = False
        self.viewer3d_ref = None  # Keep reference to current 3D viewer

        widget.setLayout(layout)
        self.setCentralWidget(widget)

        self.layer_selection_active = False
        self.selected_layers = []

    def open_gcode_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open G-code File", os.getcwd(), "G-code Files (*.gcode);;All Files (*)")
        if not file_path:
            QMessageBox.warning(self, "No File Selected", "Please select a G-code file.")
            return
        self.gcode_file = file_path
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            # Remove all thumbnail_QOI and thumbnail blocks
            import re
            content = re.sub(r';\s*thumbnail_QOI begin[\s\S]*?;\s*thumbnail_QOI end\s*;', '', content, flags=re.MULTILINE)
            content = re.sub(r';\s*thumbnail begin[\s\S]*?;\s*thumbnail end\s*;', '', content, flags=re.MULTILINE)
            self.gcode_content = content
            # Count layers by ;LAYER_CHANGE
            layer_indices = [i for i, line in enumerate(content.splitlines()) if line.strip().startswith(';LAYER_CHANGE')]
            total_layers = len(layer_indices)
            self.layer_label.setText(f"Total layers: {total_layers}")
            self.layer_dropdown.clear()
            for i in range(total_layers):
                self.layer_dropdown.addItem(f"Layer {i}")
            self.save_button.setEnabled(True)
            self.selected_layers_frame.clear()
            QMessageBox.information(self, "G-code Loaded", f"Loaded: {os.path.basename(file_path)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open or parse G-code: {e}")
            self.save_button.setEnabled(False)

    def toggle_layer_selection(self):
        if not self.layer_dropdown.count():
            QMessageBox.warning(self, "No Layers", "No layers to select. Please load a G-code file first.")
            return
        if not self.layer_selection_active:
            # Show dropdown for selection
            self.layer_dropdown.setVisible(True)
            self.select_layers_button.setText("Confirm Selection")
            self.layer_selection_active = True
        else:
            # Confirm selection and hide dropdown
            selected = self.layer_dropdown.selectedItems()
            self.selected_layers = [item.text() for item in selected]
            self.selected_layers_frame.setPlainText("\n".join(self.selected_layers) if self.selected_layers else "None")
            self.layer_dropdown.setVisible(False)
            self.select_layers_button.setText("Select Layers")
            self.layer_selection_active = False
            self.view_layer_button.setEnabled(bool(self.selected_layers))

    def open_layer_viewer_dialog(self):
        if not self.selected_layers:
            QMessageBox.warning(self, "No Layer Selected", "Please select at least one layer.")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Layer to View in 3D")
        vbox = QVBoxLayout(dialog)
        label = QLabel("Pick a layer to view:")
        vbox.addWidget(label)
        combo = QComboBox()
        combo.addItems(self.selected_layers)
        vbox.addWidget(combo)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        vbox.addWidget(buttons)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        if dialog.exec_() == QDialog.Accepted:
            layer_text = combo.currentText()
            if layer_text:
                layer_idx = int(layer_text.split()[-1])
                self.open_3d_viewer_tab(layer_idx, layer_text)

    def open_3d_viewer_tab(self, layer_idx, layer_text):
        # Open the 3D viewer in a separate window, not as a tab
        from gui.viewer3d import Layer3DViewer
        viewer = Layer3DViewer()
        moves = self.get_layer_moves(layer_idx)
        viewer.load_layer(moves)
        viewer.setWindowTitle(f"3D View: {layer_text}")
        viewer.setAttribute(Qt.WA_DeleteOnClose)
        viewer.show()
        self.viewer3d_ref = viewer

    def toggle_fullscreen(self):
        if self.viewer3d_ref is not None:
            if not self.is_fullscreen:
                self.viewer3d_ref.setWindowFlags(Qt.Window)
                self.viewer3d_ref.showFullScreen()
                self.is_fullscreen = True
            else:
                self.viewer3d_ref.setWindowFlags(Qt.Widget)
                self.viewer3d_ref.showNormal()
                self.is_fullscreen = False

    def save_gcode_file(self):
        if not self.gcode_content:
            QMessageBox.warning(self, "No G-code", "No G-code loaded to save.")
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Modified G-code", os.getcwd(), "G-code Files (*.gcode);;All Files (*)")
        if not file_path:
            return
        try:
            with open(file_path, 'w') as f:
                f.write(self.gcode_content)
            QMessageBox.information(self, "Saved", f"Modified G-code saved to: {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save G-code: {e}")

    def get_layer_moves(self, layer_idx):
        """
        Parse G-code content and return a list of (x, y, extrude, move_type) for the given layer index.
        move_type: 'external_perimeter', 'perimeter', 'travel', or 'other'.
        All extruded lines (any time E increases) are drawn, even if a retraction occurs during extrusion.
        """
        if not self.gcode_content:
            return []
        lines = self.gcode_content.splitlines()
        current_layer = -1
        moves = []
        x = y = e = None
        last_e = None
        in_external = False
        in_perimeter = False
        for i, line in enumerate(lines):
            if line.strip().startswith(';LAYER_CHANGE'):
                current_layer += 1
            if current_layer == layer_idx:
                # Detect external perimeter and perimeter by comments
                if line.strip().startswith(';TYPE:External perimeter'):
                    in_external = True
                    in_perimeter = False
                elif line.strip().startswith(';TYPE:Perimeter'):
                    in_perimeter = True
                    in_external = False
                elif line.strip().startswith(';TYPE:'):
                    in_external = False
                    in_perimeter = False
                if line.startswith('G1') or line.startswith('G0'):
                    parts = line.split()
                    x_val = y_val = e_val = None
                    for p in parts:
                        if p.startswith('X'):
                            x_val = float(p[1:])
                        elif p.startswith('Y'):
                            y_val = float(p[1:])
                        elif p.startswith('E'):
                            e_val = float(p[1:])
                    if x_val is not None:
                        x = x_val
                    if y_val is not None:
                        y = y_val
                    extrude = False
                    move_type = 'other'
                    # Draw all extruded lines: any time E increases, regardless of retraction/deretraction
                    if last_e is not None and e_val is not None and e_val > last_e:
                        extrude = True
                    elif last_e is None and e_val is not None:
                        extrude = True
                    # Determine move type
                    if extrude:
                        if in_external:
                            move_type = 'external_perimeter'
                        elif in_perimeter:
                            move_type = 'perimeter'
                        else:
                            move_type = 'other'
                    else:
                        move_type = 'travel'
                    last_e = e_val if e_val is not None else last_e
                    if x is not None and y is not None:
                        moves.append((x, y, extrude, move_type))
            elif current_layer > layer_idx:
                break
        if not moves:
            moves = [(0,0,False,'other')]
        return moves

# Entry point for launching the app

def launch_app():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

# TODO: Add advanced GUI customization and 3D rendering hooks
