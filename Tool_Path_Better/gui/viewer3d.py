# 3D Layer Viewer using PyQtGraph and OpenGL
# Visualizes a single G-code layer with a slider to animate extrusion

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QSlider, QLabel
from PyQt5.QtCore import Qt
import pyqtgraph.opengl as gl
import pyqtgraph as pg
import numpy as np

class Layer3DViewer(QWidget):
    """
    3D viewer for a single G-code layer. Shows extruded lines and animates the extruder head.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.label = QLabel("Layer Preview")
        self.layout.addWidget(self.label)
        self.gl_widget = gl.GLViewWidget()
        self.layout.addWidget(self.gl_widget, stretch=1)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.valueChanged.connect(self.update_view)
        self.layout.addWidget(self.slider)
        self.layer_moves = []  # List of (x, y, extrude) tuples
        self.extruder_dot = None
        self.line_items = []
        self.setMinimumHeight(400)
        self._init_view()

    def _init_view(self):
        # Set up a white background and grid for better visibility
        self.gl_widget.setBackgroundColor('w')
        # Remove all items before adding grid
        for item in self.gl_widget.items[:]:
            self.gl_widget.removeItem(item)
        grid = gl.GLGridItem()
        grid.setSize(200, 200)
        grid.setSpacing(10, 10)
        grid.setColor((0.7, 0.7, 0.7, 1))
        self.gl_widget.addItem(grid)
        self.grid = grid
        # Set a fixed top-down camera view and do not move it with the extruder
        self.gl_widget.setCameraPosition(distance=100, elevation=90, azimuth=0)
        self.fixed_camera = True
        self._fit_to_layer = False

    def load_layer(self, moves):
        self.layer_moves = moves
        self.slider.setMaximum(len(moves))
        self.clear_scene()
        self._fit_to_layer = True
        self._layer_bounds = self._compute_layer_bounds()
        self.update_view(0)

    def _compute_layer_bounds(self):
        if not self.layer_moves:
            return (0, 0, 100, 100)
        xs = [move[0] for move in self.layer_moves]
        ys = [move[1] for move in self.layer_moves]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        return (min_x, max_x, min_y, max_y)

    def clear_scene(self):
        for item in self.line_items:
            self.gl_widget.removeItem(item)
        self.line_items = []
        if self.extruder_dot:
            self.gl_widget.removeItem(self.extruder_dot)
            self.extruder_dot = None

    def update_view(self, value):
        self.clear_scene()
        if not self.layer_moves:
            return
        # Fit camera to layer on first load
        if self._fit_to_layer and len(self.layer_moves) > 1:
            min_x, max_x, min_y, max_y = self._layer_bounds
            center_x = (min_x + max_x) / 2
            center_y = (min_y + max_y) / 2
            from pyqtgraph import Vector
            size = max(max_x - min_x, max_y - min_y)
            self.gl_widget.opts['center'] = Vector(center_x, center_y, 0)
            self.gl_widget.setCameraPosition(pos=Vector(center_x, center_y, 0), distance=size*1.5 or 100, elevation=90, azimuth=0)
            self._fit_to_layer = False
        # Draw all lines first
        prev = None
        prev_type = None
        for i in range(value):
            move = self.layer_moves[i]
            x, y, extrude, move_type = move[:4] if len(move) > 3 else (*move, 'other')
            color = (0.7, 0.7, 0.7, 1)  # default: light gray
            width = 2
            style = None
            if move_type == 'external_perimeter':
                color = (0.5, 0, 0.5, 1)  # purple
            elif move_type == 'perimeter':
                color = (0, 0, 1, 1)  # blue
            elif move_type == 'travel':
                color = (0, 1, 0, 1)  # green
                style = 'dotted'
            if prev is not None:
                pts = np.array([[prev[0], prev[1], 0], [x, y, 0]])
                if move_type == 'travel':
                    n_dots = int(np.linalg.norm(pts[1, :2] - pts[0, :2]) / 0.5)
                    n_dots = max(n_dots, 4)
                    dots = np.linspace(0, 1, n_dots)
                    for j in range(n_dots - 1):
                        seg_start = pts[0] * (1 - dots[j]) + pts[1] * dots[j]
                        seg_end = pts[0] * (1 - dots[j+1]) + pts[1] * dots[j+1]
                        if j % 2 == 0:
                            seg = np.array([seg_start, seg_end])
                            line = gl.GLLinePlotItem(pos=seg, color=color, width=width, antialias=True)
                            self.gl_widget.addItem(line)
                            self.line_items.append(line)
                elif move_type in ('external_perimeter', 'perimeter', 'other'):
                    line = gl.GLLinePlotItem(pos=pts, color=color, width=2, antialias=True)
                    self.gl_widget.addItem(line)
                    self.line_items.append(line)
            prev = (x, y)
            prev_type = move_type
        # Draw extruder head as a large, fully opaque red dot at current position (not a line)
        # Always show the dot, even if value == 0
        if value > 0:
            pos = self.layer_moves[value-1][:2]
        else:
            pos = self.layer_moves[0][:2]
        # Use a filled, opaque, always-on-top red circle using OpenGL directly, half previous size
        from pyqtgraph.opengl.GLGraphicsItem import GLGraphicsItem
        from OpenGL.GL import glColor4f, glBegin, glEnd, glVertex3f, GL_TRIANGLE_FAN
        import math
        class ExtruderHeadDot(GLGraphicsItem):
            def __init__(self, pos, radius=1.25, color=(1,0,0,1)):
                super().__init__()
                self.pos = pos
                self.radius = radius
                self.color = color
            def paint(self):
                glColor4f(*self.color)
                glBegin(GL_TRIANGLE_FAN)
                glVertex3f(self.pos[0], self.pos[1], 0.2)
                for i in range(0, 33):
                    angle = 2 * math.pi * i / 32
                    x = self.pos[0] + self.radius * math.cos(angle)
                    y = self.pos[1] + self.radius * math.sin(angle)
                    glVertex3f(x, y, 0.2)
                glEnd()
        dot = ExtruderHeadDot((pos[0], pos[1]))
        self.gl_widget.addItem(dot)
        self.line_items.append(dot)
