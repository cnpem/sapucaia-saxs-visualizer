"""
Visualizer GUI for the visualization and processing of SAXS data.

Developed for the Sapucaia Beamline at the National Synchrotron Light Laboratory
(LNLS), part of the Brazilian Center for Research in Energy and Materials (CNPEM).

The software provides tools for visualizing SAXS curves and calculating averaged
curves from compatible measurement datasets. Averaged curves can be saved as
DAT files for subsequent analysis.

The use of the standard DAT format provided by the Sapucaia Beamline is recommended
for compatibility with the data processing and visualization routines.
"""

__author__ = ["Joao Paulo Castro Zerba", "Julia Dias de Souza"]
__email__ = ["joao.zerba@lnls.br", "julia.dias@lnls.br"] 
__maintainer__ = "Joao Paulo Castro Zerba, Julia Dias de Souza"
__version__ = "1.0.0"
__license__ = "GPLv3"

from PyQt5.QtWidgets import (
    QWidget, QFileDialog, QVBoxLayout, QApplication, QCheckBox,
    QGroupBox, QMessageBox
)
from PyQt5.QtGui import QIcon
from PyQt5 import uic
from PyQt5.QtCore import QTimer
from pathlib import Path

from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar
)
import matplotlib.pyplot as plt
import matplotlib
import numpy as np
import pandas as pd
import sys
import os
import re
import RGB_codes

Ui_Form, QtBaseClass = uic.loadUiType('visualizer_540d.ui')

Int_data = {} 
completed_int_data = {} 

class VISUALIZER(QWidget, Ui_Form):
    """Graphical interface for processing and visualizing SAXS data."""

    def __init__(self, parent = None):
        """Initialize the VISUALIZER interface and its plotting settings."""

        super(VISUALIZER, self).__init__(parent)
        super(Ui_Form,self).__init__()

        self.setupUi(self)
        self.setWindowIcon(QIcon("images/visualizer_icon.png"))
        self.default_dir = Path.home()
        self.last_dir = self.default_dir

        self.init_plot_buttons()
        self.init_pyplot_graph()
        self.colors = RGB_codes.Import_colors()

        # Preserve the original scale state when updating the plot.
        self.xscale = False
        self.yscale = False

        self.deleted_curves_idx = []
        self.files = []


    def init_plot_buttons(self):
        """Initialize and connect the plot-related buttons and controls."""
        
        self.xScale_button.clicked.connect(self.update_xscale)
        self.yScale_button.clicked.connect(self.update_yscale)
        self.del_curves_button.clicked.connect(self.delete_curves)
        self.del_curves_button.setIcon(QIcon("images/delete.svg"))
        self.DAT_path_button.clicked.connect(self.select_files) 
        self.select_plot_checkbox.stateChanged.connect(self.select_deselect_curves)
        self.avg_button.clicked.connect(self.selected_avg_curves)


    def get_qrange_unit(self):
        """Retrieve the q-range measurement unit from the first data file header."""

        file1 = self.new_files[0]
        unit = []

        with open(file1, 'r', encoding="utf-8") as file:
            for i in range(2):  
                header = (file.readline())
                unit.append(header)
        dat_line = unit[1]
        self.x_unit = dat_line.split("X Unit = ")[1].split(",")[0]


    def init_pyplot_graph(self):
        """Initialize the Matplotlib figure, canvas, and navigation toolbar."""

        layout = self.layout_toolbar
        self.fig_width = 400
        self.fig_height = 400

        self.fig = plt.Figure(figsize=(self.fig_width, self.fig_height))
        self.canvas = FigureCanvas(self.fig)
        self.toolbar = NavigationToolbar(self.canvas, self)

        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)
        font = {
            'weight': 'normal',
            'size': 16
        }

        matplotlib.rc('font', **font)

        return layout
    

    def select_files(self):
        """Open a file dialog to select DAT files for plotting and processing."""

        self.files = []
        self.deleted_curves_idx = []

        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.ExistingFiles)
        dialog.resize(1000, 800)
        dialog.setNameFilter("DAT Files (*.dat)")
        dialog.setWindowTitle("Select .dat files.")
        dialog.setDirectory(str(self.last_dir))

        if not dialog.exec_():
            return
        
        self.new_files = dialog.selectedFiles()
        if not self.new_files:
            return

        self.last_dir = dialog.directory().absolutePath()
        self.lineEdit_work_folder.setText(str(self.last_dir))

        self.open_files()


    def open_files(self):
        """Load DAT files, extract q and intensity data, and prepare them for plotting."""

        for f in self.new_files:
            if f not in self.files:
                self.files.append(f)

        for file_path in self.files:
            try:
                data = np.loadtxt(file_path, dtype=np.float32)
                if data.shape[1] < 2:
                    continue
                x = data[:, 0]
                y = data[:, 1]
                std = data[:, 2]
                file_name = os.path.basename(file_path)
                Int_data[file_name] = [x, y]
                completed_int_data[file_name] = {"path": file_path,"q":x,"I":y,"std":std}
            except Exception as e:
                print(f"Error reading {file_path}: {e}")

        self.get_qrange_unit()

        if len(Int_data) == 0:
            return

        plot_data_list = [self.x_unit ,Int_data]
        self.data_list = completed_int_data 
        self.plot_tab(plot_data_list)
        self.radial_unity = self.x_unit


    def insert_ax(self):
        """Initialize the plot axes, configure scales and labels, and plot the loaded curves."""

        self.fig.clear()

        self.ax = self.canvas.figure.subplots()
        if  self.xScale_button.text() == "Linear X":
            self.ax.set_xscale('log')
        if  self.yScale_button.text() == "Linear Y":
            self.ax.set_yscale('log')
        if self.radial_unity == "q_A^-1":
            q_unity = "q (Å$^{-1}$)"
        if self.radial_unity == "q_nm^-1":
            q_unity = "q (nm$^{-1}$)"
        if self.radial_unity ==  "2th_deg":
            q_unity = "2θ (deg)"
        if self.radial_unity == "r_mm" :
            q_unity = "r (mm)"

        self.ax.set_xlabel(q_unity)
        self.ax.set_ylabel("Intensity (a. u.)")
        self.curve = []
        i=0
        
        for file_name in  self.Int_data.keys() :
            plot_temp, = self.ax.plot(self.Int_data[file_name][0],self.Int_data[file_name][1],
            color = (self.colors[self.C_index[i]][0]/255,self.colors[self.C_index[i]][1]/255,self.colors[self.C_index[i]][2]/255)) 
            self.curve.append(plot_temp) 
            i +=1

        self.fig.tight_layout()

        self.canvas.draw()
 

    def Color_indexes(self, Nc):
        """Generate color indexes for plotting multiple curves."""
        
        self.C_index = [0] * Nc
        ki = 0
        mt= 1
        colors_len = len(self.colors)

        for i in range(Nc):
            if ki + i > colors_len - 1:
                ki = - mt * colors_len
                mt += 1
            self.C_index[i] = ki + i  


    def plot_tab(self, plot_data_list ):
        """Update the plot with the loaded integration data and curve settings."""  
     
        self.radial_unity = plot_data_list[0]
        self.Int_data = plot_data_list[1]
        self.N_curves = len(self.Int_data.keys())

        self.Color_indexes(self.N_curves)

        self.createLayout_scrollArea()

        try: 
            self.ax.remove()
            self.insert_ax()
            self.toolbar.update()
            self.fig.tight_layout()
            self.canvas.draw()
        except:
            self.insert_ax()


    def update_xscale(self):
        """Toggle the x-axis between linear and logarithmic scales."""

        if self.xscale:
            self.ax.set_xscale('log')
            self.xscale = False
        else:
            self.ax.set_xscale('linear')
            self.xscale = True

        self.canvas.draw()
        
        if self.xScale_button.text() == 'Log X':
            self.xScale_button.setText('Linear X')
        else:
            self.xScale_button.setText('Log X')


    def update_yscale(self):
        """Toggle the y-axis between linear and logarithmic scales."""

        if self.yscale:
            self.ax.set_yscale('log')
            self.yscale = False
        else:
            self.ax.set_yscale('linear')
            self.yscale = True

        self.canvas.draw()

        if self.yScale_button.text() == 'Log Y':
            self.yScale_button.setText('Linear Y')
        else:
            self.yScale_button.setText('Log Y')


    def delete_curves(self):
        """Remove unchecked curves from the plot and processed data."""

        unchecked = []
        global Int_data

        for i in range(len(self.item)):
            if self.item[i].isChecked() == False and self.item[i].isHidden() == False:
                unchecked.append(self.item[i].text())
                self.item[i].hide()
                self.deleted_curves_idx.append(i)
                
        for key in unchecked:
            if key in Int_data:
                del Int_data[key]

        self.fig.tight_layout()
        self.update_alpha()


    def select_deselect_curves(self):
        """Select or deselect all curve checkboxes and update their appearance."""
            
        for i in range(len(self.item)):
            self.item[i].disconnect()

            if self.select_plot_checkbox.isChecked():
                self.item[i].setChecked(True)
            else:
                self.item[i].setChecked(False)

            self.item[i].stateChanged.connect(self.update_alpha)

        self.update_alpha()


    def createLayout_scrollArea(self):
        """Create and configure the scroll area for curve selection controls."""
        
        self.scrollarea.setFixedWidth(250)
        self.scrollarea.setWidgetResizable(True)

        widget = QWidget()
        self.scrollarea.setWidget(widget)
        self.layout_SArea = QVBoxLayout(widget)
        self.layout_SArea.addWidget(self.createLayout_group(self.N_curves))
        self.layout_SArea.addStretch(1)


    def createLayout_group(self, number):
        """Create curve selection checkboxes and add them to the display group."""

        sgroupbox = QGroupBox("Display", self)
        layout_groupbox = QVBoxLayout(sgroupbox)

        self.item = [0] * number
        i=0

        for key in self.Int_data.keys():
            self.item[i] = QCheckBox(key, sgroupbox)
            self.item[i].setStyleSheet("color:rgb(" + str(self.colors[self.C_index[i]][0]) +","+ str(self.colors[self.C_index[i]][1]) + ","+str(self.colors[self.C_index[i]][2])+");")
            self.item[i].setChecked(True)
            self.item[i].stateChanged.connect(self.update_alpha)
            layout_groupbox.addWidget(self.item[i])
            i += 1

        layout_groupbox.addStretch(1)

        return sgroupbox


    def update_alpha(self):
        """Update curve transparency according to their selection state."""

        for i in range(len(self.item)):
          
            if self.item[i].isChecked() == False or i in self.deleted_curves_idx:
        		
                self.curve[i].set_alpha(0)
            else:
                if i not in  self.deleted_curves_idx:
                    self.curve[i].set_alpha(1)

        self.canvas.draw()


    def selected_avg_curves(self):
        """Validate the selected curves and calculate their average when compatible files are selected."""

        self.avg_curves_tx = []
        self.similar_curves = []

        for item in self.item:
            if item.isChecked():
                self.avg_curves_tx.append(item.text())

        if len(self.avg_curves_tx) < 2:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Critical)
            msg.setWindowTitle("Error")
            msg.setText("Select at least 2 files!")

            QTimer.singleShot(1000, msg.accept)
            msg.exec_()
            return

        first_prefix = experiment_prefix(self.avg_curves_tx[0])

        for name in self.avg_curves_tx:
            if experiment_prefix(name) == first_prefix:
                self.similar_curves.append(name)

        if len(self.similar_curves) < 2:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Critical)
            msg.setWindowTitle("Error")
            msg.setText("At least 2 similar files are required to calculate the average!")

            QTimer.singleShot(2000, msg.accept)
            msg.exec_()
            return

        self.avg_file()


    def average(self):
        """Calculate the arithmetic mean intensity and propagated standard deviation for the selected curves."""

        dfs = []

        for file_name in self.similar_curves:
            d = self.data_list[file_name]
            dfs.append(pd.DataFrame({"q": d["q"],"I": d["I"],"std": d["std"]}))

        concatenated_df = pd.concat(dfs, ignore_index=True)
        grouped = concatenated_df.groupby("q")
        avg_I = grouped["I"].mean()

        avg_std = grouped["std"].apply(
            lambda x: np.sqrt(np.sum(x**2)) / len(x))

        avg_df = pd.DataFrame({
            "q": avg_I.index,
            "I": avg_I.values,
            "std": avg_std.values,})

        return avg_df


    def avg_header(self):
        """Generate the header for the averaged curve file based on the first selected file."""

        first_file_name = self.similar_curves[0]
        first_file_path = self.data_list[first_file_name]["path"]
        header = []

        with open(first_file_path, "r") as f:
            for line in f:
                if line.startswith("#"):
                    header.append(line.rstrip())
                else:
                    break

        new_header = header.copy()
        new_header[0] = re.sub(r"# Image Name = .*?, Mask Path","# AVERAGE, Images Names = " + ", ".join(self.similar_curves) + ", Mask Path",new_header[0])
    
        return new_header


    def avg_file(self):
        """Calculate and save the averaged curves and their metadata to a DAT file."""

        new_header = self.avg_header()
        average = self.average()
        result = average[["q", "I", "std"]].to_numpy()

        base_name = experiment_prefix(self.similar_curves[0])
        output_dir = os.path.dirname(self.data_list[self.similar_curves[0]]["path"])

        count = 0
        while True:
            title = f"{base_name}_average_{count:04d}.dat"
            output_path = os.path.join(output_dir, title)
            if not os.path.isfile(output_path):
                break
            count += 1

        np.savetxt(output_path, result, header="\n".join(new_header).replace("# ", "").replace("#", ""), comments="# ", fmt="%.15f")
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Saved")
        msg.setText((f"The average file \n"f"{title}\n"f"was saved.\n\n"f"Processed curves:\n"f"{', '.join(self.similar_curves)}"))
        QTimer.singleShot(2500, msg.accept)
        msg.exec_()
        return

        self.prepare_to_plot_avg(output_path)
        self.clear_list()


    def clear_list(self):
        """Clear the lists of selected curves."""

        self.similar_curves.clear()
        self.avg_curves_tx.clear()


    def prepare_to_plot_avg(self, new_avg_file):
        """Add the averaged curve to the plotting sequence."""

        self.new_files.append(new_avg_file)
        self.open_files()


def experiment_prefix(filename):
    """Extract the experiment prefix by removing the five-digit identifier generated by saxs_pipeline."""
    
    base = os.path.basename(filename)

    if base.endswith(".dat"):
        base = base[:-4]      

    crop = base.split("_")

    if crop[-1].isdigit() and len(crop[-1]) == 5:
        crop.pop()

    return "_".join(crop)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = VISUALIZER()
    window.show()
    sys.exit(app.exec_())