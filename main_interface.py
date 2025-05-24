import sys
import numpy as np
import serial
import time
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, QPushButton,
                             QVBoxLayout, QHBoxLayout, QGroupBox, QDial, QComboBox,
                             QSlider, QRadioButton, QButtonGroup, QFrame, QSizePolicy, 
                             QCheckBox, QDoubleSpinBox,QSplitter,QGridLayout,QMessageBox)
from PyQt5.QtCore import Qt, QTimer, QSize,pyqtSignal,QObject
from PyQt5.QtGui import QPainter, QFontMetrics, QFont, QColor, QPalette, QIcon
import pyqtgraph as pg
from scipy.fft import fft, fftfreq
from scipy.signal import find_peaks
import threading
from collections import deque
# Custom color palettes with professional colors
DARK_PALETTE = {
    'background': QColor(45, 45, 48),
    'base': QColor(30, 30, 30),
    'text': QColor(240, 240, 240),
    'highlight': QColor(0, 122, 204),
    'button': QColor(63, 63, 70),
    'button_text': QColor(240, 240, 240),
    'group_box': QColor(37, 37, 38),
    'plot_background': QColor(30, 30, 30),
    'grid': QColor(60, 60, 60),
    'accent': QColor(4, 234, 253 ),
    'autoScale':QColor(44, 27, 185),
   'fftButton':QColor(225, 164, 8 ),
    'warning': QColor(255, 136, 0),
    'error': QColor(255, 0, 0),
    'cursor1': QColor(0, 200, 83),
    'cursor2': QColor(255, 82, 82),
    'signal': QColor(253, 234, 4  ),        # Yellow signal color
    'fft': QColor(0, 105, 217)            # Blue for FFT
}

LIGHT_PALETTE = {
    'background': QColor(240, 240, 240),  # Very light gray background
    'base': QColor(255, 255, 255),       # Pure white for base
    'text': QColor(30, 30, 30),          # Dark gray for text (almost black)
    'highlight': QColor(0, 105, 217),     # Rich blue for highlights
    'button': QColor(230, 230, 230),      # Light gray buttons
    'button_text': QColor(50, 50, 50),    # Dark gray button text
    'group_box': QColor(250, 250, 250),   # Slightly off-white for group boxes
    'plot_background': QColor(245, 245, 245),  # Light gray plot background
    'grid': QColor(220, 220, 220),        # Light gray grid lines
    'accent': QColor(217, 83, 25),        # Orange accent color
    'autoScale':QColor(44, 27, 185),
    'fftButton':QColor(225, 164, 8 ),
    'warning': QColor(255, 136, 0),       # Orange warning
    'error': QColor(200, 30, 30),         # Darker red for errors
    'cursor1': QColor(25, 130, 60),       # Dark green cursor
    'cursor2': QColor(180, 40, 40),       # Dark red cursor
    'signal': QColor(217, 83, 25),        # Orange signal color
    'fft': QColor(0, 105, 217)            # Blue for FFT
}
class LabeledDial(QDial):
    def __init__(self, labels=None, parent=None):
        super().__init__(parent)
        self.labels = labels if labels else []
        self.setMinimumSize(100, 100)
        self.setMaximumSize(120, 120)
        self.setNotchesVisible(True)
        self.setWrapping(False)
        self.valueChanged.connect(self.update)
        
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        radius = min(self.width(), self.height()) / 2 - 20
        center = self.rect().center()
        
        font = QFont()
        font.setPointSize(8)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(self.palette().color(QPalette.Text))
        
        for i, label in enumerate(self.labels):
            angle = 225 - i * 270 / (len(self.labels) - 1)
            x = center.x() + 0.8 * radius * np.cos(np.radians(angle))
            y = center.y() - 0.8 * radius * np.sin(np.radians(angle))
            
            text_width = QFontMetrics(font).width(label)
            text_height = QFontMetrics(font).height()
            
            painter.drawText(int(x - text_width/2), int(y + text_height/2), label)


import serial
import threading
import time
import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal

class SerialReader(QObject):
    data_ready = pyqtSignal(list)
    
    def __init__(self, scope, port='COM3', baudrate=115200, buffer_size=10000):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.buffer_size = buffer_size
        self.running = False
        self.serial_port = None
        self.lock = threading.Lock()
        self.test_mode = False
        self.scope = scope
        self.last_valid_value = None  # Use 0.0 or another default starting value

    def run(self):
        self.running = True
        try:
            self.serial_port = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=0.1
            )
            print(f"Connected to {self.serial_port.port} at {self.serial_port.baudrate} baud")
        except Exception as e:
            print(f"Serial connection failed: {e}, entering test mode")
            self.test_mode = True
        
        if self.test_mode:
            self._run_test_mode()
        else:
            self._run_serial_mode()

    def _run_test_mode(self):
        test_freq = 100  # Hz
        test_amp = 5
        t = np.linspace(0, self.scope.DIVISIONS_X * self.scope.time_per_div, 
                        self.scope.max_points, endpoint=False)
        test_data = test_amp * np.sign(np.sin(2 * np.pi * test_freq * t))

        while self.running:
            self.data_ready.emit(test_data.tolist())
            time.sleep(self.scope.DIVISIONS_X * self.scope.time_per_div)

    def _run_serial_mode(self):
        last_values = [self.last_valid_value, self.last_valid_value]  # Store last two valid values
        interval = 0.1 # seconds (adjust to your desired sampling rate)
        next_time = time.perf_counter() + interval

        while self.running:
            try:
                now = time.perf_counter()
                if now < next_time:
                    time.sleep(next_time - now)  # precise wait
                next_time += interval  # schedule next read

                raw_data = self.serial_port.read_all().decode('ascii', errors='ignore')
                
                if not raw_data or len(raw_data.strip()) < 5:
                    continue

                values = []
                lines = raw_data.strip().split('\n')

                for line in lines:
                    try:
                        parts = line.strip().split('#')
                        if len(parts) < 2 or len(parts[0]) < 2 or len(parts[1]) < 2:
                            raise ValueError("Incomplete data")

                        raw1 = float(parts[0])
                        raw2 = float(parts[1])

                        value1 = raw1 * 3.3 / 4095
                        value2 = raw2 * (-3.3) / 4095

                        if raw1 <= 51:
                            value1 = 0
                        if raw2 <= 51:
                            value2 = 0

                        combined = value1 + value2

                        
                        threshold = 0.7

                        # Initialize on first valid value
                        if self.last_valid_value is None:
                            self.last_valid_value = combined
                            print(self.last_valid_value)
                            last_values = [combined, combined]
                        else:
                            diff1 = abs(combined - last_values[-1])
                            diff2 = abs(combined - last_values[-2])

                            if diff1 < threshold or diff2 < threshold:
                                self.last_valid_value = combined
                            else:
                                combined = self.last_valid_value

                            last_values.append(self.last_valid_value)
                            last_values = last_values[-2:]

                        values.append(combined)

                    except Exception:
                        values.append(self.last_valid_value)

                if values:
                    self.data_ready.emit(values)

            except Exception as e:
                print(f"Serial error: {e}")
                break



    def stop(self):
        self.running = False
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()



class OscilloscopeUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Digital Oscilloscope")
        self.setGeometry(100, 100, 1200, 800)
        
        # Initialize with dark theme
        self.current_theme = 'dark'
        self.colors = DARK_PALETTE
        
        
        # Initialize attributes
        self.DIVISIONS_X = 0.1
        self.DIVISIONS_Y = 8
        self.GRID_MAX_V = 4
        self.GRID_MIN_V = -4
        self.SAMPLE_RATE = 1000  # Samples per second
        self.MAX_VOLTS_DIV = 5.0
        self.MIN_VOLTS_DIV = 0.1
        self.MAX_TIME_DIV = 2.0
        self.MIN_TIME_DIV = 0.1
        # Initialize trigger state variables
        self.trigger_armed = True
        self.last_sample = 0.0
        self.trigger_position = 0
        self.time_offset = 0.0
        # Initialize critical variables
        self.volts_per_div = 1.0
        self.time_per_div = 0.1
        self.showing_fft = False
        self.x = np.array([])
        self.y = np.array([])
        self.curve = None
        self.fft_curve = None
        self.peak_markers = []
        
        # Serial communication setup
        self.serial_reader = None
        self.serial_thread = None
        self.serial_port = None
        self.serial_buffer = []
        self.max_points = int(self.DIVISIONS_X * self.time_per_div * self.SAMPLE_RATE)
        self.data_buffer = np.zeros(self.max_points)
        self.time_buffer = np.linspace(0, self.DIVISIONS_X * self.time_per_div, self.max_points)
        self.last_update_time = 0
        self.samples_since_last_update = 0

        # Main UI Setup
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # Main layout with 3 rows: plot, controls, measurements
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        self.main_layout.setSpacing(1)

        # Create components
        self.create_plot_area()
        self.create_control_panel()
        self.create_measurement_panel()
        self.create_advanced_panel()

        # Initial setup
        self.setup_plot_curve()
        self.update_timebase()
        self.setup_theme()
        # Connect signals
        self.fft_btn.clicked.connect(self.toggle_fft)
        self.autoscale_btn.clicked.connect(self.autoscale)
        self.theme_btn.clicked.connect(self.toggle_theme)
        
        # Start update timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_waveform)
        self.timer.start(100)  
        
        # Initialize serial connection
        self.init_serial()
  


    def setup_ui(self):
        """Reconfigure main layout using QSplitter for better resizing"""
        splitter = QSplitter(Qt.Vertical)
        
        # Top section (plot widget)
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.addWidget(self.plot_widget)
        
        # Bottom section (control panels)
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.addWidget(self.control_panel)
        bottom_layout.addWidget(self.measure_panel)
        bottom_layout.addWidget(self.advanced_panel)
        
        # Configure splitter behavior
        splitter.addWidget(top_widget)
        splitter.addWidget(bottom_widget)
        splitter.setStretchFactor(0, 3)  # Plot area gets 3/4 of space
        splitter.setStretchFactor(1, 1)  # Controls get 1/4 of space
        
        # Apply to central widget
        self.central_widget = QWidget()
        self.central_widget.setLayout(QVBoxLayout())
        self.central_widget.layout().addWidget(splitter)
        self.setCentralWidget(self.central_widget)
    def setup_theme(self):
        """Setup the current theme colors and styles"""
        palette = QPalette()
        
        if self.current_theme == 'dark':
            self.colors = DARK_PALETTE
            # Set palette for dark theme
            palette.setColor(QPalette.Window, self.colors['background'])
            palette.setColor(QPalette.WindowText, self.colors['text'])
            palette.setColor(QPalette.Base, self.colors['base'])
            palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
            palette.setColor(QPalette.ToolTipBase, Qt.white)
            palette.setColor(QPalette.ToolTipText, Qt.white)
            palette.setColor(QPalette.Text, self.colors['text'])
            palette.setColor(QPalette.Button, self.colors['button'])
            palette.setColor(QPalette.ButtonText, self.colors['button_text'])
            palette.setColor(QPalette.BrightText, Qt.red)
            palette.setColor(QPalette.Link, self.colors['highlight'])
            palette.setColor(QPalette.Highlight, self.colors['highlight'])
            palette.setColor(QPalette.HighlightedText, Qt.black)
            
            # Update button icons/text
            self.theme_btn.setIcon(QIcon.fromTheme("weather-clear-night"))
            self.theme_btn.setText(" Light Mode")
            
        else:
            self.colors = LIGHT_PALETTE
            # Set palette for professional light theme
            palette.setColor(QPalette.Window, self.colors['background'])
            palette.setColor(QPalette.WindowText, self.colors['text'])
            palette.setColor(QPalette.Base, self.colors['base'])
            palette.setColor(QPalette.AlternateBase, QColor(240, 240, 242))
            palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 255))
            palette.setColor(QPalette.ToolTipText, self.colors['text'])
            palette.setColor(QPalette.Text, self.colors['text'])
            palette.setColor(QPalette.Button, self.colors['button'])
            palette.setColor(QPalette.ButtonText, self.colors['button_text'])
            palette.setColor(QPalette.BrightText, Qt.red)
            palette.setColor(QPalette.Link, self.colors['highlight'])
            palette.setColor(QPalette.Highlight, self.colors['highlight'])
            palette.setColor(QPalette.HighlightedText, Qt.white)
            
            # Update button icons/text
            self.theme_btn.setIcon(QIcon.fromTheme("weather-clear"))
            self.theme_btn.setText(" Dark Mode")
        
        self.setPalette(palette)
        
        self.plot_widget.removeItem(self.timebase_text)
        self.plot_widget.removeItem(self.volts_div_text)
        # Update plot colors
        self.plot_widget.setBackground(self.colors['plot_background'])
        self.plot_widget.getAxis('left').setPen(pg.mkPen(color=self.colors['text'], width=1))
        self.plot_widget.getAxis('bottom').setPen(pg.mkPen(color=self.colors['text'], width=1))
        self.plot_widget.showGrid(x=True, y=True, alpha=0.2)
        self.timebase_text = pg.TextItem(text=self.timebase_text.toPlainText(), 
                                    color=self.colors['accent'], 
                                    anchor=(1, 1),
                                    
                                    fill=self.colors['plot_background'])
        self.volts_div_text = pg.TextItem(text=self.volts_div_text.toPlainText(), 
                                    color=self.colors['accent'], 
                                   
                                    fill=self.colors['plot_background'])
        # Set larger bold font
        font = QFont()
        font.setPointSize(12)
        font.setBold(False)
        self.timebase_text.setFont(font)
        self.volts_div_text.setFont(font)
        self.plot_widget.addItem(self.timebase_text)
        self.plot_widget.addItem(self.volts_div_text)
     
        # Update curve colors
        if hasattr(self, 'curve'):
            self.curve.setPen(pg.mkPen(self.colors['signal'], width=2))
        if hasattr(self, 'fft_curve'):
            if self.fft_curve is not None:
                self.fft_curve.setPen(pg.mkPen(self.colors['fft'], width=1))
        
        # Update text items
        if hasattr(self, 'timebase_text') and hasattr(self, 'volts_div_text'):
            self.timebase_text.setColor(self.colors['accent'])
            self.volts_div_text.setColor(self.colors['accent'])
            self.update_text_positions()
        
        # Update all group boxes with subtle shadows
        for group_box in self.findChildren(QGroupBox):
            group_box.setStyleSheet(f"""
                QGroupBox {{
                    background-color: {self.colors['group_box'].name()};
                    border: 1px solid {self.colors['grid'].name()};
                    border-radius: 5px;
                    margin-top: 10px;
                    padding-top: 15px;
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 3px;
                    color: {self.colors['text'].name()};
                    font-weight: bold;
                }}
            """)
        
        # Update button styles
        button_style = f"""
            QPushButton {{
                background-color: {self.colors['button'].name()};
                color: {self.colors['button_text'].name()};
                border: 1px solid {self.colors['grid'].name()};
                border-radius: 4px;
                padding: 5px;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: {self.colors['button'].darker(105).name()};
                border: 1px solid {self.colors['highlight'].name()};
            }}
            QPushButton:pressed {{
                background-color: {self.colors['button'].darker(115).name()};
            }}
        """
        self.setStyleSheet(button_style)
        
        # Special button styles
        if hasattr(self, 'run_stop_btn'):
            self.run_stop_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #4CAF50;
                    color: white;
                    font-weight: bold;
                }}
                QPushButton:checked {{
                    background-color: #F44336;
                }}
            """)
        
        if hasattr(self, 'autoscale_btn'):
            self.autoscale_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {self.colors['autoScale'].name()};
                    color: white;
                    font-weight: bold;
                }}
            """)
        
        if hasattr(self, 'fft_btn'):
            self.fft_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {self.colors['fftButton'].name()};
                    color: white;
                    font-weight: bold;
                }}
                QPushButton:checked {{
                    background-color: {QColor(self.colors['fftButton']).name()};
                }}
            """)
        
        # Force UI update
        self.update()
      
    def toggle_theme(self):
        """Toggle between light and dark theme"""
        self.current_theme = 'light' if self.current_theme == 'dark' else 'dark'
        self.setup_theme()
        
        # Update plot display
        if self.showing_fft:
            self.show_fft()
        else:
            self.update_waveform()

    def init_serial(self):
        """Initialize serial connection with error dialog"""
        try:
            # Initialize serial reader thread
            self.serial_reader = SerialReader(self,port='COM3', baudrate=115200)
            self.serial_thread = threading.Thread(target=self.serial_reader.run)
            self.serial_thread.daemon = True  # Thread will exit when main program exits
            
            # Connect signals
            self.serial_reader.data_ready.connect(self.on_serial_data)
            
            # Start the serial thread
            self.serial_thread.start()
            
            
            
        except Exception as e:
            error_msg = f"Failed to initialize serial connection:\n{e}"
            print(error_msg)
            
            
                
                # Create a dummy serial port for demonstration
            self.serial_port = None



    def create_plot_area(self):
        """Create the main oscilloscope display area"""
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setMinimumSize(400, 300)
        self.plot_widget.setBackground(self.colors['plot_background'])
        self.plot_widget.setMouseEnabled(x=False, y=False)
        self.plot_widget.setMenuEnabled(False)
        
        # Customize the plot appearance
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.getAxis('left').setPen(pg.mkPen(color=self.colors['text'], width=1))
        self.plot_widget.getAxis('bottom').setPen(pg.mkPen(color=self.colors['text'], width=1))
        
        # Add to layout with some stretch factor
        self.main_layout.addWidget(self.plot_widget, 5)

    def setup_plot_curve(self):
        """Initialize or reset the plot curve"""
        if self.curve is not None:
            self.plot_widget.removeItem(self.curve)
        self.curve = self.plot_widget.plot([], [], pen=pg.mkPen(self.colors['signal'], width=2))
        
        # Initialize text items for sensitivity display
        self.timebase_text = pg.TextItem(text="", 
                                    color=self.colors['accent'], 
                                    anchor=(1, 1),
                                    fill=self.colors['plot_background'])
        self.volts_div_text = pg.TextItem(text="", 
                                    color=self.colors['accent'], 
                                    
                                    fill=self.colors['plot_background'])
        # Adjust text offset from edges
        self.volts_div_text.setPos(
            self.plot_widget.width() - 5,  # 10px from right 
            self.plot_widget.height() - 5  # 10px from bottom
        )
        # Set larger bold font
        font = QFont()
        font.setPointSize(12)
        font.setBold(False)
        self.timebase_text.setFont(font)
        self.volts_div_text.setFont(font)
        
        self.plot_widget.addItem(self.timebase_text)
        self.plot_widget.addItem(self.volts_div_text)
        self.update_text_positions()




    def update_text_positions(self):
        """Update positions of the text items"""
        if hasattr(self, 'timebase_text') and hasattr(self, 'volts_div_text'):
            # Position timebase text at bottom right
            x_pos = self.DIVISIONS_X * self.time_per_div * 0.98  # 98% of width
            y_pos = self.GRID_MIN_V * 0.98  # Just above bottom
            self.timebase_text.setPos(x_pos, y_pos)
            
            # Position volts/div text at top left
            x_pos = self.DIVISIONS_X * self.time_per_div * 0.02  # 2% of width
            y_pos = self.GRID_MAX_V * 0.98  # Just below top
            self.volts_div_text.setPos(x_pos, y_pos)

    def create_control_panel(self):
        """Create control panel with knobs and buttons"""
        control_panel = QWidget()
        control_layout = QHBoxLayout(control_panel)
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(15)

        # Vertical controls
        vert_group = QGroupBox("VERTICAL")
        vert_layout = QVBoxLayout(vert_group)
        vert_layout.setSpacing(10)
        
        # Volts/div control
        volt_labels = [f"{v:.1f}" for v in np.linspace(self.MIN_VOLTS_DIV, self.MAX_VOLTS_DIV, 5)]
        self.ch1_volts_div = LabeledDial(labels=volt_labels)
        self.ch1_volts_div.setRange(int(self.MIN_VOLTS_DIV * 10), 
                                int(self.MAX_VOLTS_DIV * 10))
        self.ch1_volts_div.setValue(10)
        self.ch1_volts_div.valueChanged.connect(self.update_axes)
        
        volts_label = QLabel("Volts/Div")
        volts_label.setAlignment(Qt.AlignCenter)
        vert_layout.addWidget(volts_label)
        vert_layout.addWidget(self.ch1_volts_div, 0, Qt.AlignHCenter)

        # Offset control
        offset_label = QLabel("Offset (V)")
        offset_label.setAlignment(Qt.AlignCenter)
        vert_layout.addWidget(offset_label)
        
        self.ch1_offset = QDoubleSpinBox()
        self.ch1_offset.setRange(-10, 10)
        self.ch1_offset.setSingleStep(0.1)
        self.ch1_offset.setValue(0)
        self.ch1_offset.valueChanged.connect(self.update_axes)
        vert_layout.addWidget(self.ch1_offset)

        # Horizontal controls
        horiz_group = QGroupBox("HORIZONTAL")
        horiz_layout = QVBoxLayout(horiz_group)
        horiz_layout.setSpacing(10)
        
        time_labels = [f"{t:.1f}" for t in np.linspace(self.MIN_TIME_DIV, self.MAX_TIME_DIV, 5)]
        self.timebase_dial = LabeledDial(labels=time_labels)
        self.timebase_dial.setRange(int(self.MIN_TIME_DIV * 10), 
                                int(self.MAX_TIME_DIV * 10))
        self.timebase_dial.setValue(10)
        self.timebase_dial.valueChanged.connect(self.update_timebase)
        
        time_label = QLabel("Time/Div (s)")
        time_label.setAlignment(Qt.AlignCenter)
        horiz_layout.addWidget(time_label)
        horiz_layout.addWidget(self.timebase_dial, 0, Qt.AlignHCenter)

        # Time position control
        pos_label = QLabel("Position (s)")
        pos_label.setAlignment(Qt.AlignCenter)
        horiz_layout.addWidget(pos_label)
        
        self.time_pos = QDoubleSpinBox()
        self.time_pos.setRange(-10, 10)
        self.time_pos.setSingleStep(0.1)
        self.time_pos.setValue(0)
        self.time_pos.valueChanged.connect(self.update_timebase)
        horiz_layout.addWidget(self.time_pos)

        # Trigger controls
        trigger_group = QGroupBox("TRIGGER")
        trigger_layout = QVBoxLayout(trigger_group)
        trigger_layout.setSpacing(10)
        
        # Trigger mode
        self.trigger_mode = QComboBox()
        self.trigger_mode.addItems(["Auto", "Normal", "Single"])
        trigger_layout.addWidget(QLabel("Mode:"))
        trigger_layout.addWidget(self.trigger_mode)

        # Trigger edge
        self.trigger_edge = QComboBox()
        self.trigger_edge.addItems(["Rising", "Falling"])
        trigger_layout.addWidget(QLabel("Edge:"))
        trigger_layout.addWidget(self.trigger_edge)

        # Trigger level
        self.trigger_level = QDoubleSpinBox()
        self.trigger_level.setRange(-10, 10)
        self.trigger_level.setSingleStep(0.1)
        trigger_layout.addWidget(QLabel("Level (V):"))
        trigger_layout.addWidget(self.trigger_level)

        # Run/Stop button
        self.run_stop_btn = QPushButton("RUN")
        self.run_stop_btn.setCheckable(True)
        self.run_stop_btn.setChecked(True)
        self.run_stop_btn.toggled.connect(self.toggle_run)
        trigger_layout.addWidget(self.run_stop_btn)

        # Add groups to control panel with stretch factors
        control_layout.addWidget(vert_group, 1)
        control_layout.addWidget(horiz_group, 1)
        control_layout.addWidget(trigger_group, 1)
        
        self.main_layout.addWidget(control_panel)
    def apply_lowpass_filter(self, data, cutoff_freq=50, fs=1000, order=5):
        """Apply a low-pass Butterworth filter to remove high-frequency noise"""
        from scipy.signal import butter, lfilter
        
        nyq = 0.5 * fs
        normal_cutoff = cutoff_freq / nyq
        b, a = butter(order, normal_cutoff, btype='low', analog=False)
        filtered_data = lfilter(b, a, data)
        return filtered_data

    def apply_moving_average(self, data, window_size=5):
        """Apply simple moving average filter"""
        window = np.ones(window_size) / window_size
        return np.convolve(data, window, mode='same')
    def create_measurement_panel(self):
        """Create measurement display panel"""
        self.measure_panel = QWidget()
        layout = QHBoxLayout(self.measure_panel)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)

        # Time measurements with grid layout
        time_group = QGroupBox("Time Measurements")
        time_layout = QGridLayout(time_group)  

        # Create and configure labels 
        self.delta_t_label = QLabel("Δt: --")
        self.t_div_label = QLabel("Div: --")
        self.cursor1_time_label = QLabel("Cursor 1: -- s")
        self.cursor2_time_label = QLabel("Cursor 2: -- s")

        # Set alignment for all labels
        for label in [self.delta_t_label, self.t_div_label,
                    self.cursor1_time_label, self.cursor2_time_label]:
            label.setAlignment(Qt.AlignCenter)

        # Arrange in a 2x2 grid layout
        time_layout.addWidget(self.cursor1_time_label, 0, 0)  # Row 0, Column 0
        time_layout.addWidget(self.cursor2_time_label, 0, 1)  # Row 0, Column 1
        time_layout.addWidget(self.delta_t_label, 1, 0)       # Row 1, Column 0
        time_layout.addWidget(self.t_div_label, 1, 1)         # Row 1, Column 1

        # Configure grid spacing and margins
        time_layout.setHorizontalSpacing(10)  # Space between columns
        time_layout.setVerticalSpacing(5)     # Space between rows
        time_layout.setContentsMargins(5, 10, 5, 10)  # Left, Top, Right, Bottom

        # Make columns equally stretchable
        time_layout.setColumnStretch(0, 1)
        time_layout.setColumnStretch(1, 1)

        layout.addWidget(time_group, 1)

        # Voltage measurements
        volt_group = QGroupBox("Voltage Measurements")
        volt_group = QGroupBox("Voltage Measurements")
        volt_layout = QGridLayout(volt_group)  # Changed to QGridLayout

        # Create all labels
        self.cursor1_volt_label = QLabel("Cursor 1: -- V")
        self.cursor2_volt_label = QLabel("Cursor 2: -- V")
        self.delta_v_label = QLabel("ΔV: --")
        self.v_div_label = QLabel("Δdiv: --")
        self.v_pp_label = QLabel("Vpp: --")
        self.v_avg_label = QLabel("Avg: --")
        self.v_max_label = QLabel("Max: --")    
        self.v_min_label = QLabel("Min: --")    

        # Configure all labels
        all_labels = [
            self.cursor1_volt_label,
            self.cursor2_volt_label,
            self.delta_v_label,
            self.v_div_label,
            self.v_pp_label,
            self.v_avg_label,
            self.v_max_label,
            self.v_min_label
        ]

        for label in all_labels:
            label.setAlignment(Qt.AlignCenter)
            label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # Arrange in grid (2 columns, 4 rows)
        volt_layout.addWidget(self.cursor1_volt_label, 0, 0)  # Row 0, Col 0
        volt_layout.addWidget(self.cursor2_volt_label, 0, 1)  # Row 0, Col 1
        volt_layout.addWidget(self.delta_v_label, 1, 0)       # Row 1, Col 0
        volt_layout.addWidget(self.v_div_label, 1, 1)         # Row 1, Col 1
        volt_layout.addWidget(self.v_pp_label, 2, 0)          # Row 2, Col 0
        volt_layout.addWidget(self.v_avg_label, 2, 1)         # Row 2, Col 1
        volt_layout.addWidget(self.v_max_label, 3, 0)         # Row 3, Col 0
        volt_layout.addWidget(self.v_min_label, 3, 1)         # Row 3, Col 1

        # Set column stretch factors
        volt_layout.setColumnStretch(0, 1)  # First column takes equal space
        volt_layout.setColumnStretch(1, 1)  # Second column takes equal space

        # Add some vertical spacing
        volt_layout.setVerticalSpacing(5)
        volt_layout.setContentsMargins(5, 10, 5, 10)

        layout.addWidget(volt_group, 1)

        # Measurement controls
        measure_group = QGroupBox("Cursors")
        measure_layout = QVBoxLayout(measure_group)
        
        self.measure_btn = QPushButton("Enable Cursors")
        self.measure_btn.setCheckable(True)
        self.measure_btn.toggled.connect(self.toggle_measurement)
        measure_layout.addWidget(self.measure_btn)

        self.measure_type = QButtonGroup()
        self.time_radio = QRadioButton("Time")
        self.voltage_radio = QRadioButton("Voltage")
        self.time_radio.setChecked(True)
        self.measure_type.addButton(self.time_radio)
        self.measure_type.addButton(self.voltage_radio)
        
        radio_layout = QHBoxLayout()
        radio_layout.addWidget(self.time_radio)
        radio_layout.addWidget(self.voltage_radio)
        measure_layout.addLayout(radio_layout)
        
        layout.addWidget(measure_group, 1)

        self.main_layout.addWidget(self.measure_panel)
      

    def create_advanced_panel(self):
        """Create panel for advanced functions"""
        advanced_panel = QWidget()
        advanced_layout = QHBoxLayout(advanced_panel)
        advanced_layout.setContentsMargins(5, 5, 5, 5)
        advanced_layout.setSpacing(10)

        # Left side: Filter controls
        filter_group = QGroupBox("Signal Processing")
        filter_layout = QVBoxLayout(filter_group)
        
        # First row: Enable checkbox and filter type
        filter_row1 = QHBoxLayout()
        self.filter_enable = QCheckBox("Enable")
        self.filter_enable.setChecked(False)
        filter_row1.addWidget(self.filter_enable)
        
        self.filter_type = QComboBox()
        self.filter_type.addItems(["Low-pass", "Moving Average"])
        filter_row1.addWidget(self.filter_type)
        filter_layout.addLayout(filter_row1)
        
        # Second row: Parameter control
        filter_row2 = QHBoxLayout()
        filter_row2.addWidget(QLabel("Cutoff/Window:"))
        
        self.filter_param_slider = QSlider(Qt.Horizontal)
        self.filter_param_slider.setRange(1, 480)
        self.filter_param_slider.setValue(20)
        filter_row2.addWidget(self.filter_param_slider)
        
        self.filter_param_label = QLabel("20")
        filter_row2.addWidget(self.filter_param_label)
        filter_layout.addLayout(filter_row2)
        
        # Connect signal for real-time update
        self.filter_param_slider.valueChanged.connect(
            lambda v: self.filter_param_label.setText(str(v)))
        
        advanced_layout.addWidget(filter_group)

        # Middle: Display controls
        display_group = QGroupBox("Display")
        display_layout = QVBoxLayout(display_group)
        
        self.autoscale_btn = QPushButton("Autoscale")
        self.autoscale_btn.setFixedHeight(30)
        display_layout.addWidget(self.autoscale_btn)
        
        self.fft_btn = QPushButton("FFT")
        self.fft_btn.setCheckable(True)
        self.fft_btn.setFixedHeight(30)
        display_layout.addWidget(self.fft_btn)
        
        advanced_layout.addWidget(display_group)

        # Right side: Theme and other controls
        control_group = QGroupBox("Settings")
        control_layout = QVBoxLayout(control_group)
        
        self.theme_btn = QPushButton()
        self.theme_btn.setCheckable(False)
        self.theme_btn.setFixedHeight(30)
        control_layout.addWidget(self.theme_btn)
        
        self.save_btn = QPushButton("Save Data")
        self.save_btn.setFixedHeight(30)
        control_layout.addWidget(self.save_btn)
        
        advanced_layout.addWidget(control_group)

        # Apply consistent styling
        for btn in [self.autoscale_btn, self.fft_btn, self.theme_btn, self.save_btn]:
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        self.main_layout.addWidget(advanced_panel)

    def update_timebase(self):
        """Update timebase settings and recalculate buffers"""
        new_time_per_div = self.timebase_dial.value() / 10
        if abs(new_time_per_div - self.time_per_div) < 0.01 and not self.time_pos.hasFocus():
            return
            
        self.time_per_div = new_time_per_div
        total_time = self.DIVISIONS_X * self.time_per_div
        self.max_points = int(total_time * self.SAMPLE_RATE)
        
        # Resize buffers while preserving existing data
        old_data = self.data_buffer
        self.data_buffer = np.zeros(self.max_points)
        copy_len = min(len(old_data), len(self.data_buffer))
        self.data_buffer[-copy_len:] = old_data[-copy_len:]
        
        # Update time axis
        self.time_offset = self.time_pos.value()
        self.time_buffer = np.linspace(0, self.time_offset + total_time, self.max_points)
        self.update_axes()
    def on_serial_data(self, new_values):
        """Handle incoming serial data with dynamic buffer sizing"""
        if not new_values:
            return

        # Get current buffer parameters
        current_max_points = int(self.DIVISIONS_X * self.time_per_div * self.SAMPLE_RATE)
        
        # Resize buffer if needed
        if len(self.data_buffer) != current_max_points:
            self.data_buffer = np.zeros(current_max_points)
            self.time_buffer = np.linspace(0, self.DIVISIONS_X * self.time_per_div, current_max_points)
            self.max_points = current_max_points

        # Convert to numpy array and clip to buffer size
        new_data = np.array(new_values[-self.max_points:])
        
        # Handle buffer update
        if len(new_data) >= self.max_points:
            # If new data is larger than buffer, take the latest samples
            self.data_buffer[:] = new_data[-self.max_points:]
        else:
            # Roll buffer and add new data
            shift = len(new_data)
            self.data_buffer = np.roll(self.data_buffer, -shift)
            self.data_buffer[-shift:] = new_data

        # Update time buffer based on current settings
        self.time_buffer = np.linspace(0, self.DIVISIONS_X * self.time_per_div, self.max_points)
        
    def update_waveform(self):
        """Main update function - processes data and updates display"""
        # Update timebase if changed
        new_time_per_div = self.timebase_dial.value() / 10
        if abs(new_time_per_div - self.time_per_div) > 0.01:
            self.update_timebase()
        
        # Update vertical scale if changed
        new_volts_per_div = self.ch1_volts_div.value() / 10
        if abs(new_volts_per_div - self.volts_per_div) > 0.01:
            self.volts_per_div = new_volts_per_div
            self.update_axes()

        # Process current data buffer
        offset_volts = self.ch1_offset.value()
        
        # Apply filters if enabled
        if self.filter_enable.isChecked():
            if self.filter_type.currentText() == "Low-pass":
                cutoff = self.filter_param_slider.value()
                filtered_data = self.apply_lowpass_filter(
                    self.data_buffer, 
                    cutoff_freq=cutoff, 
                    fs=self.SAMPLE_RATE
                )
            else:  # Moving Average
                window_size = self.filter_param_slider.value()
                filtered_data = self.apply_moving_average(
                    self.data_buffer, 
                    window_size=window_size
                )
            display_data = filtered_data + offset_volts
        else:
            display_data = self.data_buffer + offset_volts

        # Update plot display
        if self.showing_fft:
            self.curve.hide()
            self.show_fft()
        else:
            self.curve.show()
            self.curve.setData(self.time_buffer, display_data)

        # Trigger handling
        if self.run_stop_btn.isChecked() and self.trigger_mode.currentText() != "Auto":
            trigger_level = self.trigger_level.value()
            edge = self.trigger_edge.currentText()
            triggered = False
            
            # Check entire buffer for trigger condition
            for i in range(1, len(display_data)):
                prev = display_data[i-1]
                current = display_data[i]
                
                if edge == "Rising" and prev < trigger_level <= current:
                    triggered = True
                    self.trigger_position = i
                    break
                elif edge == "Falling" and prev > trigger_level >= current:
                    triggered = True
                    self.trigger_position = i
                    break

            if self.trigger_mode.currentText() == "Single":
                if triggered and self.trigger_armed:
                    self.trigger_armed = False
                    # Capture single trigger
                    self.display_data = display_data[self.trigger_position:]
                elif not self.trigger_armed:
                    return
            elif not triggered:
                return

        # Update measurements if cursors are active
        if hasattr(self, 'measure_btn') and self.measure_btn.isChecked():
            self.update_measurement()
        
        # Store display data for measurements
        self.display_data = display_data
        self.last_update_time += self.timer.interval()
    def update_axes(self):
        """Update axis ranges and labels"""
        # Calculate the vertical range based on volts/div and number of divisions
        vertical_span = self.volts_per_div * self.DIVISIONS_Y
        self.GRID_MAX_V = vertical_span / 2
        self.GRID_MIN_V = -vertical_span / 2
        
        if not self.showing_fft:
            self.plot_widget.setYRange(self.GRID_MIN_V, self.GRID_MAX_V)
            self.plot_widget.setXRange(0, self.DIVISIONS_X * self.time_per_div)
            
            # Update the text items
            if hasattr(self, 'timebase_text') and hasattr(self, 'volts_div_text'):
                self.timebase_text.setText(f"{self.time_per_div:.1f} s/div")
                self.volts_div_text.setText(f"{self.volts_per_div:.1f} V/div")
                self.update_text_positions()
            
            # Hide axis labels since we're showing them on the plot
            self.plot_widget.setLabel('left', "")
            self.plot_widget.setLabel('bottom', "Time (S)")
            self.plot_widget.setTitle("Signal scope", size='12pt')
        else:
            self.plot_widget.setYRange(-60, 60)
            self.plot_widget.setXRange(0, 500)
            self.plot_widget.setLabel('left', "Magnitude (dB)")
            self.plot_widget.setLabel('bottom', "Frequency (Hz)")
            self.plot_widget.setTitle("Frequency Spectrum", size='12pt')
            
            # Hide the text items in FFT mode
            if hasattr(self, 'timebase_text') and hasattr(self, 'volts_div_text'):
                self.timebase_text.hide()
                self.volts_div_text.hide()

    def show_fft(self):
        """Compute and display FFT of the current buffer"""
        if len(self.data_buffer) == 0:
            return
        
        n = len(self.data_buffer)
        yf = fft(self.data_buffer - np.mean(self.data_buffer))  # Remove DC offset
        xf = fftfreq(n, 1/self.SAMPLE_RATE)[:n//2]
        
        # Safe log calculation with minimum value
        min_val = 1e-12
        yf_abs = np.maximum(np.abs(yf[0:n//2]), min_val)
        yf_db = 20 * np.log10(yf_abs)
        
        # Remove DC component
        xf = xf[1:]
        yf_db = yf_db[1:]
        
        # Update plot
        if self.fft_curve is None:
            self.fft_curve = self.plot_widget.plot(xf, yf_db, pen=pg.mkPen(self.colors['fft'], width=1))
        else:
            self.fft_curve.setData(xf, yf_db)
        
        # Clear previous markers
        for marker in self.peak_markers:
            self.plot_widget.removeItem(marker)
        self.peak_markers = []
        
        # Find and mark the fundamental frequency
        peaks, _ = find_peaks(yf_db, height=10)  # Only consider peaks above 10dB
        if len(peaks) > 0:
            peak_idx = peaks[0]
            freq = xf[peak_idx]
            mag = yf_db[peak_idx]
            
            # Add vertical line at peak frequency
            self.peak_marker = pg.InfiniteLine(pos=freq, angle=90, pen=pg.mkPen(self.colors['warning'], width=2))
            self.plot_widget.addItem(self.peak_marker)
            self.peak_markers.append(self.peak_marker)
            
            # Add text label at top
            text = pg.TextItem(text=f"{freq:.2f} Hz", color=self.colors['text'], anchor=(0.5, 1))
            text.setPos(freq, 55)
            self.plot_widget.addItem(text)
            self.peak_markers.append(text)

    def toggle_fft(self, checked):
        """Toggle FFT view"""
        self.showing_fft = checked
        if checked:
            self.fft_btn.setText("Signal scope")
            if hasattr(self, 'timebase_text') and hasattr(self, 'volts_div_text'):
                self.timebase_text.hide()
                self.volts_div_text.hide()
            self.show_fft()
        else:
            self.fft_btn.setText("FFT")
            if self.fft_curve is not None:
                self.plot_widget.removeItem(self.fft_curve)
                self.fft_curve = None
                if hasattr(self,"peak_marker"):
                    self.plot_widget.removeItem(self.peak_marker)
            if hasattr(self, 'timebase_text') and hasattr(self, 'volts_div_text'):
                self.timebase_text.show()
                self.volts_div_text.show()
            self.curve.setData(self.time_buffer, self.data_buffer + self.ch1_offset.value())
        
        self.update_axes()
      
    def autoscale(self):
        """Auto-scale vertical display"""
        if len(self.data_buffer) == 0:
            return
            
        # Find peak value in the buffer
        peak = max(abs(self.data_buffer))
        
        # Calculate required volts/div to fit the signal
        required_volts_div = peak / (self.DIVISIONS_Y / 2)  # Use half divisions to give some margin
        
        # Round to nearest standard value (0.1, 0.2, 0.5, 1, 2, 5)
        standard_values = [0.1, 0.2, 0.5, 1, 2, 5]
        volts_div = min(standard_values, key=lambda x: abs(x - required_volts_div))
        volts_div = max(self.MIN_VOLTS_DIV, min(self.MAX_VOLTS_DIV, volts_div))
        
        # Calculate optimal offset to center the signal
        if len(self.data_buffer) > 0:
            mean_val = np.mean(self.data_buffer)
            optimal_offset = -mean_val
            optimal_offset = max(-10, min(10, optimal_offset))
            self.ch1_offset.setValue(optimal_offset)
        
        self.ch1_volts_div.setValue(int(volts_div * 10))
        self.update_axes()

    def toggle_measurement(self, checked):
        """Toggle measurement cursors"""
        if checked:
            if hasattr(self, 'cursor1') and self.cursor1:
                self.plot_widget.removeItem(self.cursor1)
                self.plot_widget.removeItem(self.cursor2)
            
            if self.time_radio.isChecked():
                self.measurement_mode = 'time'
                self.cursor1 = pg.InfiniteLine(angle=90, movable=True, pen='g')
                self.cursor2 = pg.InfiniteLine(angle=90, movable=True, pen='r')
                xr = self.plot_widget.viewRange()[0]
                self.cursor1.setPos(xr[0] + 0.3*(xr[1]-xr[0]))
                self.cursor2.setPos(xr[0] + 0.7*(xr[1]-xr[0]))
            else:
                self.measurement_mode = 'amplitude'
                self.cursor1 = pg.InfiniteLine(angle=0, movable=True, pen='g')
                self.cursor2 = pg.InfiniteLine(angle=0, movable=True, pen='r')
                yr = self.plot_widget.viewRange()[1]
                self.cursor1.setPos(yr[0] + 0.3*(yr[1]-yr[0]))
                self.cursor2.setPos(yr[0] + 0.7*(yr[1]-yr[0]))
            
            self.plot_widget.addItem(self.cursor1)
            self.plot_widget.addItem(self.cursor2)
            self.cursor1.sigPositionChanged.connect(self.update_measurement)
            self.cursor2.sigPositionChanged.connect(self.update_measurement)
            self.update_measurement()
        else:
            if hasattr(self, 'cursor1') and self.cursor1:
                self.plot_widget.removeItem(self.cursor1)
                self.plot_widget.removeItem(self.cursor2)
            self.delta_t_label.setText("Δt: --")
          
            self.delta_v_label.setText("ΔV: --")
            self.v_div_label.setText("Divisions: --")

    def update_measurement(self):
        """Update measurement displays"""
        if not hasattr(self, 'cursor1') or not self.cursor1:
            return
            
        if self.time_radio.isChecked():
            t1 = self.cursor1.value()
            t2 = self.cursor2.value()
            delta_t = abs(t2 - t1)
            time_divisions = delta_t / self.time_per_div
            freq = 1/delta_t if delta_t != 0 else 0
            self.delta_t_label.setText(f"Δt = {delta_t:.3f} s")
            self.t_div_label.setText(f"Δdiv = {time_divisions:.2f}")
            self.cursor1_time_label.setText(f"Cursor 1: {t1:.3f} s")
            self.cursor2_time_label.setText(f"Cursor 2: {t2:.3f} s")
        else:
            v1 = self.cursor1.value()
            v2 = self.cursor2.value()
            delta_v = abs(v2 - v1)
            voltage_divisions = delta_v / self.volts_per_div
            vpp = 2 * max(abs(v1), abs(v2))  # Peak-to-peak estimation
            self.delta_v_label.setText(f"ΔV = {delta_v:.3f} V")
            self.v_div_label.setText(f"Δdiv = {voltage_divisions:.2f}")
            self.v_pp_label.setText(f"Vpp = {vpp:.3f} V")
            self.cursor1_volt_label.setText(f"Cursor 1: {v1:.3f} V")
            self.cursor2_volt_label.setText(f"Cursor 2: {v2:.3f} V")
            # Update global measurements
            if hasattr(self, 'display_data'):
                self.v_avg_label.setText(f"Avg: {np.mean(self.display_data):.3f} V")
                self.v_pp_label.setText(f"Vpp: {np.ptp(self.display_data):.3f} V")
                self.v_max_label.setText(f"Max: {self.display_data.max():.3f} V")
                self.v_min_label.setText(f"Min: {self.display_data.min():.3f} V")
    def toggle_run(self, checked):
        """Start/stop waveform updates"""
        if checked:
            self.run_stop_btn.setText("STOP")
            self.trigger_armed = True
            self.timer.start()
        else:
            self.run_stop_btn.setText("RUN")
            self.timer.stop()

    def closeEvent(self, event):
            """Clean up when closing the window"""
            # Stop the serial thread
            self.serial_reader.stop()
            self.serial_thread.join(timeout=1)
            
            # Close serial port if open
            if hasattr(self.serial_reader, 'serial_port') and self.serial_reader.serial_port:
                if self.serial_reader.serial_port.is_open:
                    self.serial_reader.serial_port.close()
                    
            event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Set application style for consistent look
    app.setStyle('Fusion')
    
    # Create and customize palette for dark theme
    palette = QPalette()
    palette.setColor(QPalette.Window, DARK_PALETTE['background'])
    palette.setColor(QPalette.WindowText, DARK_PALETTE['text'])
    palette.setColor(QPalette.Base, DARK_PALETTE['base'])
    palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ToolTipBase, Qt.white)
    palette.setColor(QPalette.ToolTipText, Qt.white)
    palette.setColor(QPalette.Text, DARK_PALETTE['text'])
    palette.setColor(QPalette.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ButtonText, Qt.white)
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Link, DARK_PALETTE['highlight'])
    palette.setColor(QPalette.Highlight, DARK_PALETTE['highlight'])
    palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(palette)
    
    osc = OscilloscopeUI()
    osc.show()
    sys.exit(app.exec_())