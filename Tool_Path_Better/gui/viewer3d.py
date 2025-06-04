# 3D Layer Viewer using PyQtGraph and OpenGL
# Visualizes a single G-code layer with a slider to animate extrusion

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QSlider, QLabel
from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QVector3D
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
        self.layer_moves = []  # List of (x, y, extrude, move_type) tuples
        self.extruder_dot = None
        self.line_items = []
        self.setMinimumHeight(400)
        self._init_view()
        # Dragging state
        self.dragging = False
        self.drag_start_pos = None
        self.drag_current_pos = None
        self.drag_preview_line = None
        self.drag_head_dot = None
        self.installEventFilter(self)
        self.gl_widget.mousePressEvent = self._on_mouse_press
        self.gl_widget.mouseMoveEvent = self._on_mouse_move
        self.gl_widget.mouseReleaseEvent = self._on_mouse_release
        self._extruder_head_screen_radius = 20  # for hit test
        # Enable mouse tracking for the GLViewWidget
        self.gl_widget.setMouseTracking(True)
        self.setMouseTracking(True)
        # Disable camera rotation and panning
        self.gl_widget.orbit = lambda *args, **kwargs: None
        self.gl_widget.pan = lambda *args, **kwargs: None
        self.gl_widget.mouseDragEvent = lambda *args, **kwargs: None
        # Store extruder head position for hit testing
        self._extruder_head_world_pos = None

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
            try:
                self.gl_widget.removeItem(item)
            except ValueError:
                pass  # Item was already removed
        self.line_items = []
        self.drag_head_dot = None

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
        # If dragging, show the extruder head at the drag position
        if self.dragging and self.drag_current_pos:
            self._extruder_head_world_pos = self.drag_current_pos
            self._draw_extruder_head_dot(self.drag_current_pos, dragging=True)
            # Draw the drag preview line
            self._draw_drag_preview()
        else:
            self._extruder_head_world_pos = pos
            self._draw_extruder_head_dot(pos, dragging=False)

    def _draw_extruder_head_dot(self, pos, dragging=False):
        # Remove any previous extruder head dot from the scene
        if self.drag_head_dot:
            try:
                self.gl_widget.removeItem(self.drag_head_dot)
            except ValueError:
                pass
            self.drag_head_dot = None
        # Use a filled, opaque, always-on-top circle using OpenGL directly
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
        # Enlarge and change color if dragging
        if dragging:
            color = (0.5, 0, 0, 1)  # maroon
            radius = 2.0
        else:
            color = (1, 0, 0, 1)  # red
            radius = 1.25
        dot = ExtruderHeadDot((pos[0], pos[1]), radius=radius, color=color)
        self.gl_widget.addItem(dot)
        self.line_items.append(dot)
        self.drag_head_dot = dot

    def _is_near_extruder_head(self, world_pos, threshold=3.0):
        # Check if the click is within threshold distance of the extruder head
        if not self.layer_moves:
            return False
        idx = self.slider.value() - 1 if self.slider.value() > 0 else 0
        head_pos = self.layer_moves[idx][:2]
        dx = world_pos[0] - head_pos[0]
        dy = world_pos[1] - head_pos[1]
        return (dx*dx + dy*dy) ** 0.5 < threshold

    def _is_near_extruder_head_screen(self, screen_pos):
        # Use OpenGL projection to map world to screen for accurate hit testing
        if self._extruder_head_world_pos is None:
            print("[DEBUG] No extruder head world position set.")
            return False
        # Get OpenGL projection and view matrices
        try:
            import pyqtgraph.opengl as gl
            import numpy as np
            widget = self.gl_widget
            pos3d = np.array([self._extruder_head_world_pos[0], self._extruder_head_world_pos[1], 0, 1])
            proj = widget.projectionMatrix().data()
            view = widget.viewMatrix().data()
            # Convert to numpy arrays
            proj = np.array(proj).reshape((4,4)).T
            view = np.array(view).reshape((4,4)).T
            mvp = np.dot(proj, view)
            screen = np.dot(mvp, pos3d)
            screen /= screen[3]
            # screen x/y in range [-1, 1], map to widget pixel coordinates
            w, h = widget.width(), widget.height()
            x = (screen[0] * 0.5 + 0.5) * w
            y = (1 - (screen[1] * 0.5 + 0.5)) * h
            dx = screen_pos.x() - x
            dy = screen_pos.y() - y
            dist = (dx*dx + dy*dy) ** 0.5
            print(f"[DEBUG] Click at ({screen_pos.x()}, {screen_pos.y()}) | Head at ({x:.1f}, {y:.1f}) | dist={dist:.1f}")
            return dist < 40
        except Exception as e:
            print(f"[DEBUG] OpenGL projection error: {e}")
            return False

    def _on_mouse_press(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.pos()
            # Use the current extruder head world position as the drag start
            world_pos = self._extruder_head_world_pos
            print(f"[DEBUG] Mouse press at screen {pos.x()}, {pos.y()} | world {world_pos}")
            if world_pos is not None:
                if self._is_near_extruder_head_screen(pos):
                    print("[DEBUG] Extruder head clicked!")
                    self.dragging = True
                    self.drag_start_pos = world_pos
                    self.drag_current_pos = world_pos
                    self._drag_offset = (pos.x(), pos.y(), world_pos[0], world_pos[1])
                    self._draw_drag_preview()
                    self.update_view(self.slider.value())
                    event.accept()
                    return
                else:
                    print("[DEBUG] Click NOT on extruder head.")
        event.ignore()

    def _on_mouse_move(self, event):
        if self.dragging:
            pos = event.pos()
            # Calculate the world position based on the initial offset
            try:
                size = self.gl_widget.size()
                w, h = size.width(), size.height()
                min_x, max_x, min_y, max_y = self._layer_bounds
                dx = pos.x() - self._drag_offset[0]
                dy = pos.y() - self._drag_offset[1]
                # Convert pixel delta to world delta
                world_dx = dx / w * (max_x - min_x)
                world_dy = -dy / h * (max_y - min_y)
                new_x = self._drag_offset[2] + world_dx
                new_y = self._drag_offset[3] + world_dy
                self.drag_current_pos = (new_x, new_y)
                self.update_view(self.slider.value())
            except Exception as e:
                print(f"[DEBUG] Drag error: {e}")
            event.accept()
            return
        event.ignore()

    def _on_mouse_release(self, event):
        if self.dragging:
            self.dragging = False
            self._remove_drag_preview()
            self.update_view(self.slider.value())
            print(f"[DEBUG] New travel move: {self.drag_start_pos} -> {self.drag_current_pos}")
            event.accept()
            return
        event.ignore()

    def _draw_drag_preview(self):
        self._remove_drag_preview()
        if self.drag_start_pos and self.drag_current_pos:
            pts = np.array([
                [self.drag_start_pos[0], self.drag_start_pos[1], 0.3],
                [self.drag_current_pos[0], self.drag_current_pos[1], 0.3]
            ])
            # Only draw the preview if the drag is not a zero-length move
            if not (abs(self.drag_start_pos[0] - self.drag_current_pos[0]) < 1e-6 and abs(self.drag_start_pos[1] - self.drag_current_pos[1]) < 1e-6):
                n_dots = int(np.linalg.norm(pts[1, :2] - pts[0, :2]) / 0.5)
                n_dots = max(n_dots, 4)
                dots = np.linspace(0, 1, n_dots)
                self.drag_preview_lines = []
                for j in range(n_dots - 1):
                    seg_start = pts[0] * (1 - dots[j]) + pts[1] * dots[j]
                    seg_end = pts[0] * (1 - dots[j+1]) + pts[1] * dots[j+1]
                    if j % 2 == 0:
                        seg = np.array([seg_start, seg_end])
                        line = gl.GLLinePlotItem(pos=seg, color=(0,1,0,1), width=3, antialias=True)
                        self.gl_widget.addItem(line)
                        self.drag_preview_lines.append(line)

    def _remove_drag_preview(self):
        if hasattr(self, 'drag_preview_lines'):
            for line in self.drag_preview_lines:
                try:
                    self.gl_widget.removeItem(line)
                except Exception:
                    pass
            self.drag_preview_lines = []

    def _screen_to_world(self, pos):
        # Convert 2D screen position to 3D world coordinates (approximate, top-down)
        # This is a simple approximation for a top-down view
        size = self.gl_widget.size()
        w, h = size.width(), size.height()
        min_x, max_x, min_y, max_y = self._layer_bounds
        x = min_x + (max_x - min_x) * pos.x() / w
        y = min_y + (max_y - min_y) * (h - pos.y()) / h
        return (x, y)
