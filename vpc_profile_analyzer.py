import os
import math
import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
from PyQt5.QtCore import QObject, pyqtSignal, QTimer, QPointF
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QTableWidget, QTableWidgetItem, 
                            QTabWidget, QTextEdit, QComboBox, QSpinBox,
                            QDoubleSpinBox, QGroupBox, QCheckBox, QProgressBar)
from PyQt5.QtGui import QFont
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from qgis.core import (
    QgsProject, QgsPointCloudLayer, QgsGeometry, QgsPoint, QgsLineString,
    QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsRectangle,
    QgsPointCloudRequest, QgsPointCloud3DSymbol, QgsMessageLog,
    QgsFeature, QgsVectorLayer, QgsField, QgsFields, QgsWkbTypes,
    QgsSpatialIndex, QgsPointXY, QgsDistanceArea
)
from qgis.gui import QgsElevationProfileCanvas, QgsMapCanvas
from qgis.PyQt.QtCore import QVariant

@dataclass
class ProfilePoint:
    """Classe pour stocker les informations d'un point du profil"""
    x: float  # Position le long du profil
    y: float  # Coordonnée Y (latitude/northing)
    z: float  # Élévation
    distance: float  # Distance depuis le début du profil
    intensity: Optional[float] = None
    classification: Optional[int] = None
    rgb: Optional[Tuple[int, int, int]] = None
    original_coords: Optional[Tuple[float, float, float]] = None

class VPCProfileAnalyzer(QObject):
    """
    Classe principale pour l'analyse des points VPC dans un profil d'élévation
    """
    
    analysis_completed = pyqtSignal(dict)
    
    def __init__(self, iface):
        super().__init__()
        self.iface = iface
        self.canvas = iface.mapCanvas()
        
        # Profil d'élévation
        self.profile_canvas = None
        self.profile_points = []
        self.profile_line = None
        self.vpc_layer = None
        
        # Paramètres d'extraction
        self.buffer_distance = 5.0  # Distance de buffer autour de la ligne de profil
        self.sample_interval = 1.0  # Intervalle d'échantillonnage le long du profil
        self.min_points_per_sample = 1  # Minimum de points par échantillon
        
        # Interface utilisateur
        self.setup_ui()
        
    def setup_ui(self):
        """Configure l'interface utilisateur"""
        self.widget = QWidget()
        self.widget.setWindowTitle("Analyseur de Profil VPC")
        self.widget.resize(1200, 800)
        
        # Layout principal
        main_layout = QVBoxLayout(self.widget)
        
        # Contrôles supérieurs
        controls_layout = self.create_controls_layout()
        main_layout.addLayout(controls_layout)
        
        # Onglets pour les résultats
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # Onglet 1: Graphiques d'analyse
        self.create_analysis_tab()
        
        # Onglet 2: Données tabulaires
        self.create_data_tab()
        
        # Onglet 3: Statistiques
        self.create_stats_tab()
        
        # Onglet 4: Export
        self.create_export_tab()
        
        self.widget.show()
        
    def create_controls_layout(self):
        """Crée la zone de contrôles"""
        layout = QVBoxLayout()
        
        # Groupe de sélection
        selection_group = QGroupBox("Sélection et Paramètres")
        selection_layout = QHBoxLayout(selection_group)
        
        # Sélection de la couche VPC
        selection_layout.addWidget(QLabel("Couche VPC:"))
        self.layer_combo = QComboBox()
        self.update_layer_list()
        selection_layout.addWidget(self.layer_combo)
        
        # Distance de buffer
        selection_layout.addWidget(QLabel("Buffer (m):"))
        self.buffer_spin = QDoubleSpinBox()
        self.buffer_spin.setRange(0.1, 100.0)
        self.buffer_spin.setValue(5.0)
        self.buffer_spin.setSingleStep(0.5)
        selection_layout.addWidget(self.buffer_spin)
        
        # Intervalle d'échantillonnage
        selection_layout.addWidget(QLabel("Intervalle (m):"))
        self.interval_spin = QDoubleSpinBox()
        self.interval_spin.setRange(0.1, 50.0)
        self.interval_spin.setValue(1.0)
        self.interval_spin.setSingleStep(0.1)
        selection_layout.addWidget(self.interval_spin)
        
        layout.addWidget(selection_group)
        
        # Groupe d'actions
        actions_group = QGroupBox("Actions")
        actions_layout = QHBoxLayout(actions_group)
        
        # Bouton pour créer le profil
        self.create_profile_btn = QPushButton("Créer Profil d'Élévation")
        self.create_profile_btn.clicked.connect(self.create_elevation_profile)
        actions_layout.addWidget(self.create_profile_btn)
        
        # Bouton pour extraire les points
        self.extract_points_btn = QPushButton("Extraire Points du Profil")
        self.extract_points_btn.clicked.connect(self.extract_profile_points)
        self.extract_points_btn.setEnabled(False)
        actions_layout.addWidget(self.extract_points_btn)
        
        # Bouton d'analyse
        self.analyze_btn = QPushButton("Analyser Points")
        self.analyze_btn.clicked.connect(self.analyze_points)
        self.analyze_btn.setEnabled(False)
        actions_layout.addWidget(self.analyze_btn)
        
        # Barre de progression
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        actions_layout.addWidget(self.progress_bar)
        
        layout.addWidget(actions_group)
        
        return layout
        
    def create_analysis_tab(self):
        """Crée l'onglet des graphiques d'analyse"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Configuration matplotlib
        self.figure = Figure(figsize=(12, 8))
        self.canvas_plot = FigureCanvas(self.figure)
        layout.addWidget(self.canvas_plot)
        
        # Contrôles des graphiques
        plot_controls = QHBoxLayout()
        
        plot_controls.addWidget(QLabel("Type de graphique:"))
        self.plot_type_combo = QComboBox()
        self.plot_type_combo.addItems([
            "Profil d'élévation",
            "Distribution des points",
            "Intensité vs Élévation",
            "Classification",
            "Rugosité du terrain",
            "Analyse spectrale"
        ])
        self.plot_type_combo.currentTextChanged.connect(self.update_plot)
        plot_controls.addWidget(self.plot_type_combo)
        
        self.update_plot_btn = QPushButton("Mettre à jour")
        self.update_plot_btn.clicked.connect(self.update_plot)
        plot_controls.addWidget(self.update_plot_btn)
        
        layout.addLayout(plot_controls)
        
        self.tab_widget.addTab(tab, "Analyses Graphiques")
        
    def create_data_tab(self):
        """Crée l'onglet des données tabulaires"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Contrôles de filtrage
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filtrer par:"))
        
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["Tous", "Élévation", "Intensité", "Classification"])
        filter_layout.addWidget(self.filter_combo)
        
        self.filter_min = QDoubleSpinBox()
        self.filter_min.setRange(-1000, 10000)
        filter_layout.addWidget(self.filter_min)
        
        filter_layout.addWidget(QLabel("à"))
        
        self.filter_max = QDoubleSpinBox()
        self.filter_max.setRange(-1000, 10000)
        filter_layout.addWidget(self.filter_max)
        
        self.apply_filter_btn = QPushButton("Appliquer Filtre")
        self.apply_filter_btn.clicked.connect(self.apply_data_filter)
        filter_layout.addWidget(self.apply_filter_btn)
        
        layout.addLayout(filter_layout)
        
        # Tableau des données
        self.data_table = QTableWidget()
        layout.addWidget(self.data_table)
        
        self.tab_widget.addTab(tab, "Données")
        
    def create_stats_tab(self):
        """Crée l'onglet des statistiques"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Zone de texte pour les statistiques
        self.stats_text = QTextEdit()
        self.stats_text.setFont(QFont("Courier", 10))
        layout.addWidget(self.stats_text)
        
        # Contrôles des statistiques
        stats_controls = QHBoxLayout()
        
        self.detailed_stats_check = QCheckBox("Statistiques détaillées")
        self.detailed_stats_check.setChecked(True)
        stats_controls.addWidget(self.detailed_stats_check)
        
        self.update_stats_btn = QPushButton("Mettre à jour Statistiques")
        self.update_stats_btn.clicked.connect(self.update_statistics)
        stats_controls.addWidget(self.update_stats_btn)
        
        layout.addLayout(stats_controls)
        
        self.tab_widget.addTab(tab, "Statistiques")
        
    def create_export_tab(self):
        """Crée l'onglet d'export"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Options d'export
        export_group = QGroupBox("Options d'Export")
        export_layout = QVBoxLayout(export_group)
        
        # Formats disponibles
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Format:"))
        
        self.export_format_combo = QComboBox()
        self.export_format_combo.addItems(["CSV", "Excel", "GeoJSON", "Shapefile", "LAS"])
        format_layout.addWidget(self.export_format_combo)
        
        export_layout.addLayout(format_layout)
        
        # Options spécifiques
        self.include_stats_check = QCheckBox("Inclure les statistiques")
        self.include_stats_check.setChecked(True)
        export_layout.addWidget(self.include_stats_check)
        
        self.include_plots_check = QCheckBox("Inclure les graphiques")
        self.include_plots_check.setChecked(True)
        export_layout.addWidget(self.include_plots_check)
        
        # Boutons d'export
        export_buttons = QHBoxLayout()
        
        self.export_data_btn = QPushButton("Exporter Données")
        self.export_data_btn.clicked.connect(self.export_data)
        export_buttons.addWidget(self.export_data_btn)
        
        self.export_report_btn = QPushButton("Exporter Rapport Complet")
        self.export_report_btn.clicked.connect(self.export_complete_report)
        export_buttons.addWidget(self.export_report_btn)
        
        export_layout.addLayout(export_buttons)
        
        layout.addWidget(export_group)
        
        # Zone de logs
        log_group = QGroupBox("Logs d'Export")
        log_layout = QVBoxLayout(log_group)
        
        self.export_log = QTextEdit()
        self.export_log.setMaximumHeight(150)
        log_layout.addWidget(self.export_log)
        
        layout.addWidget(log_group)
        
        self.tab_widget.addTab(tab, "Export")
        
    def update_layer_list(self):
        """Met à jour la liste des couches VPC"""
        self.layer_combo.clear()
        self.layer_combo.addItem("Sélectionner une couche VPC")
        
        for layer in QgsProject.instance().mapLayers().values():
            if isinstance(layer, QgsPointCloudLayer):
                self.layer_combo.addItem(layer.name(), layer.id())
                
    def create_elevation_profile(self):
        """Crée une vue de profil d'élévation"""
        try:
            # Vérifier qu'une couche VPC est sélectionnée
            layer_id = self.layer_combo.currentData()
            if not layer_id:
                QgsMessageLog.logMessage("Veuillez sélectionner une couche VPC", "VPCProfileAnalyzer")
                return
                
            self.vpc_layer = QgsProject.instance().mapLayer(layer_id)
            
            # Créer le canvas de profil d'élévation
            if hasattr(self.iface, 'elevationProfileWidget'):
                # Utiliser le widget de profil intégré si disponible
                self.profile_canvas = self.iface.elevationProfileWidget().canvas()
            else:
                # Créer notre propre canvas de profil
                self.profile_canvas = QgsElevationProfileCanvas()
            
            # Obtenir la ligne de profil depuis la sélection ou permettre à l'utilisateur de la dessiner
            self.get_profile_line()
            
            if self.profile_line:
                self.extract_points_btn.setEnabled(True)
                QgsMessageLog.logMessage("Profil d'élévation créé avec succès", "VPCProfileAnalyzer")
                
        except Exception as e:
            QgsMessageLog.logMessage(f"Erreur lors de la création du profil: {str(e)}", "VPCProfileAnalyzer")
            
    def get_profile_line(self):
        """Obtient la ligne de profil depuis la sélection ou l'utilisateur"""
        # Pour cet exemple, nous utiliserons une ligne fictive
        # En réalité, vous pourriez obtenir cette ligne de plusieurs façons:
        # 1. Ligne sélectionnée dans une couche
        # 2. Ligne dessinée par l'utilisateur
        # 3. Ligne générée automatiquement
        
        # Exemple: ligne droite à travers l'étendue de la couche VPC
        if self.vpc_layer:
            extent = self.vpc_layer.extent()
            start_point = QgsPoint(extent.xMinimum(), extent.center().y())
            end_point = QgsPoint(extent.xMaximum(), extent.center().y())
            
            self.profile_line = QgsLineString([start_point, end_point])
            
    def extract_profile_points(self):
        """Extrait les points du VPC le long du profil"""
        if not self.vpc_layer or not self.profile_line:
            return
            
        try:
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 100)
            
            # Paramètres d'extraction
            self.buffer_distance = self.buffer_spin.value()
            self.sample_interval = self.interval_spin.value()
            
            # Créer un buffer autour de la ligne de profil
            profile_geometry = QgsGeometry(self.profile_line)
            buffered_geometry = profile_geometry.buffer(self.buffer_distance, 5)
            
            # Créer une requête pour le nuage de points
            request = QgsPointCloudRequest()
            request.setRectangle(buffered_geometry.boundingBox())
            
            # Extraire les points
            self.profile_points = []
            iterator = self.vpc_layer.dataProvider().query(request)
            
            total_distance = self.profile_line.length()
            point_count = 0
            
            while iterator.hasNext():
                point_data = iterator.next()
                
                # Coordonnées du point
                x = point_data['X']
                y = point_data['Y']
                z = point_data.get('Z', 0)
                
                point_geom = QgsGeometry.fromPointXY(QgsPointXY(x, y))
                
                # Vérifier si le point est dans la zone de buffer
                if buffered_geometry.contains(point_geom):
                    # Calculer la distance le long du profil
                    closest_point = profile_geometry.closestVertex(QgsPointXY(x, y))
                    distance_along_profile = profile_geometry.lineLocatePoint(closest_point[0])
                    
                    # Créer l'objet ProfilePoint
                    profile_point = ProfilePoint(
                        x=x,
                        y=y,
                        z=z,
                        distance=distance_along_profile,
                        intensity=point_data.get('Intensity'),
                        classification=point_data.get('Classification'),
                        original_coords=(x, y, z)
                    )
                    
                    self.profile_points.append(profile_point)
                    point_count += 1
                    
                    # Mise à jour de la barre de progression
                    progress = int((distance_along_profile / total_distance) * 100)
                    self.progress_bar.setValue(progress)
            
            self.progress_bar.setVisible(False)
            
            if self.profile_points:
                self.analyze_btn.setEnabled(True)
                QgsMessageLog.logMessage(f"{len(self.profile_points)} points extraits du profil", "VPCProfileAnalyzer")
            else:
                QgsMessageLog.logMessage("Aucun point trouvé dans la zone de profil", "VPCProfileAnalyzer")
                
        except Exception as e:
            self.progress_bar.setVisible(False)
            QgsMessageLog.logMessage(f"Erreur lors de l'extraction: {str(e)}", "VPCProfileAnalyzer")
            
    def analyze_points(self):
        """Analyse les points extraits du profil"""
        if not self.profile_points:
            return
            
        try:
            # Trier les points par distance le long du profil
            self.profile_points.sort(key=lambda p: p.distance)
            
            # Calculer les statistiques de base
            analysis_results = self.compute_basic_statistics()
            
            # Analyses avancées
            analysis_results.update(self.compute_terrain_analysis())
            analysis_results.update(self.compute_roughness_analysis())
            
            # Mettre à jour l'interface
            self.update_data_table()
            self.update_statistics()
            self.update_plot()
            
            self.analysis_completed.emit(analysis_results)
            
            QgsMessageLog.logMessage("Analyse des points terminée", "VPCProfileAnalyzer")
            
        except Exception as e:
            QgsMessageLog.logMessage(f"Erreur lors de l'analyse: {str(e)}", "VPCProfileAnalyzer")
            
    def compute_basic_statistics(self) -> Dict:
        """Calcule les statistiques de base"""
        if not self.profile_points:
            return {}
            
        elevations = [p.z for p in self.profile_points]
        distances = [p.distance for p in self.profile_points]
        intensities = [p.intensity for p in self.profile_points if p.intensity is not None]
        
        stats = {
            'point_count': len(self.profile_points),
            'profile_length': max(distances) - min(distances) if distances else 0,
            'elevation_stats': {
                'min': min(elevations) if elevations else 0,
                'max': max(elevations) if elevations else 0,
                'mean': np.mean(elevations) if elevations else 0,
                'std': np.std(elevations) if elevations else 0,
                'range': max(elevations) - min(elevations) if elevations else 0
            }
        }
        
        if intensities:
            stats['intensity_stats'] = {
                'min': min(intensities),
                'max': max(intensities),
                'mean': np.mean(intensities),
                'std': np.std(intensities)
            }
            
        return stats
        
    def compute_terrain_analysis(self) -> Dict:
        """Calcule l'analyse du terrain"""
        if len(self.profile_points) < 3:
            return {}
            
        # Calculer les pentes
        slopes = []
        for i in range(1, len(self.profile_points)):
            p1 = self.profile_points[i-1]
            p2 = self.profile_points[i]
            
            if p2.distance != p1.distance:
                slope = (p2.z - p1.z) / (p2.distance - p1.distance)
                slopes.append(math.degrees(math.atan(slope)))
                
        return {
            'terrain_analysis': {
                'slopes': slopes,
                'mean_slope': np.mean(slopes) if slopes else 0,
                'max_slope': max(slopes) if slopes else 0,
                'min_slope': min(slopes) if slopes else 0,
                'slope_std': np.std(slopes) if slopes else 0
            }
        }
        
    def compute_roughness_analysis(self) -> Dict:
        """Calcule l'analyse de rugosité"""
        if len(self.profile_points) < 5:
            return {}
            
        # Calculer l'indice de rugosité (déviation par rapport à une ligne de tendance)
        distances = np.array([p.distance for p in self.profile_points])
        elevations = np.array([p.z for p in self.profile_points])
        
        # Régression linéaire pour la tendance
        coeffs = np.polyfit(distances, elevations, 1)
        trend_line = np.polyval(coeffs, distances)
        
        # Calcul de la rugosité
        deviations = elevations - trend_line
        roughness_index = np.std(deviations)
        
        return {
            'roughness_analysis': {
                'roughness_index': roughness_index,
                'trend_slope': coeffs[0],
                'trend_intercept': coeffs[1],
                'max_deviation': np.max(np.abs(deviations)),
                'deviations': deviations.tolist()
            }
        }
        
    def update_data_table(self):
        """Met à jour le tableau des données"""
        if not self.profile_points:
            return
            
        # Configuration du tableau
        headers = ['Distance', 'X', 'Y', 'Z', 'Intensité', 'Classification']
        self.data_table.setColumnCount(len(headers))
        self.data_table.setHorizontalHeaderLabels(headers)
        self.data_table.setRowCount(len(self.profile_points))
        
        # Remplissage des données
        for i, point in enumerate(self.profile_points):
            self.data_table.setItem(i, 0, QTableWidgetItem(f"{point.distance:.2f}"))
            self.data_table.setItem(i, 1, QTableWidgetItem(f"{point.x:.2f}"))
            self.data_table.setItem(i, 2, QTableWidgetItem(f"{point.y:.2f}"))
            self.data_table.setItem(i, 3, QTableWidgetItem(f"{point.z:.2f}"))
            self.data_table.setItem(i, 4, QTableWidgetItem(str(point.intensity) if point.intensity else "N/A"))
            self.data_table.setItem(i, 5, QTableWidgetItem(str(point.classification) if point.classification else "N/A"))
            
    def update_statistics(self):
        """Met à jour l'affichage des statistiques"""
        if not self.profile_points:
            return
            
        stats = self.compute_basic_statistics()
        terrain_stats = self.compute_terrain_analysis()
        roughness_stats = self.compute_roughness_analysis()
        
        # Formatage du texte des statistiques
        stats_text = "=== STATISTIQUES DU PROFIL VPC ===\n\n"
        
        # Statistiques générales
        stats_text += f"Nombre de points: {stats['point_count']}\n"
        stats_text += f"Longueur du profil: {stats['profile_length']:.2f} m\n\n"
        
        # Statistiques d'élévation
        elev_stats = stats['elevation_stats']
        stats_text += "--- Élévations ---\n"
        stats_text += f"Minimum: {elev_stats['min']:.2f} m\n"
        stats_text += f"Maximum: {elev_stats['max']:.2f} m\n"
        stats_text += f"Moyenne: {elev_stats['mean']:.2f} m\n"
        stats_text += f"Écart-type: {elev_stats['std']:.2f} m\n"
        stats_text += f"Amplitude: {elev_stats['range']:.2f} m\n\n"
        
        # Statistiques d'intensité
        if 'intensity_stats' in stats:
            int_stats = stats['intensity_stats']
            stats_text += "--- Intensités ---\n"
            stats_text += f"Minimum: {int_stats['min']:.0f}\n"
            stats_text += f"Maximum: {int_stats['max']:.0f}\n"
            stats_text += f"Moyenne: {int_stats['mean']:.1f}\n"
            stats_text += f"Écart-type: {int_stats['std']:.1f}\n\n"
            
        # Analyse du terrain
        if 'terrain_analysis' in terrain_stats:
            terrain = terrain_stats['terrain_analysis']
            stats_text += "--- Analyse du Terrain ---\n"
            stats_text += f"Pente moyenne: {terrain['mean_slope']:.2f}°\n"
            stats_text += f"Pente maximum: {terrain['max_slope']:.2f}°\n"
            stats_text += f"Pente minimum: {terrain['min_slope']:.2f}°\n"
            stats_text += f"Variabilité des pentes: {terrain['slope_std']:.2f}°\n\n"
            
        # Analyse de rugosité
        if 'roughness_analysis' in roughness_stats:
            roughness = roughness_stats['roughness_analysis']
            stats_text += "--- Rugosité du Terrain ---\n"
            stats_text += f"Indice de rugosité: {roughness['roughness_index']:.3f} m\n"
            stats_text += f"Pente de tendance: {roughness['trend_slope']:.6f}\n"
            stats_text += f"Déviation maximum: {roughness['max_deviation']:.3f} m\n"
            
        self.stats_text.setPlainText(stats_text)
        
    def update_plot(self):
        """Met à jour les graphiques"""
        if not self.profile_points:
            return
            
        self.figure.clear()
        
        plot_type = self.plot_type_combo.currentText()
        
        if plot_type == "Profil d'élévation":
            self.plot_elevation_profile()
        elif plot_type == "Distribution des points":
            self.plot_point_distribution()
        elif plot_type == "Intensité vs Élévation":
            self.plot_intensity_elevation()
        elif plot_type == "Classification":
            self.plot_classification()
        elif plot_type == "Rugosité du terrain":
            self.plot_roughness()
        elif plot_type == "Analyse spectrale":
            self.plot_spectral_analysis()
            
        self.canvas_plot.draw()
        
    def plot_elevation_profile(self):
        """Graphique du profil d'élévation"""
        ax = self.figure.add_subplot(111)
        
        distances = [p.distance for p in self.profile_points]
        elevations = [p.z for p in self.profile_points]
        
        ax.plot(distances, elevations, 'b-', linewidth=0.5, alpha=0.7, label='Points')
        
        # Ligne de tendance
        if len(distances) > 1:
            z = np.polyfit(distances, elevations, 1)
            p = np.poly1d(z)
            ax.plot(distances, p(distances), 'r--', linewidth=2, label='Tendance')
            
        ax.set_xlabel('Distance le long du profil (m)')
        ax.set_ylabel('Élévation (m)')
        ax.set_title('Profil d\'Élévation du Nuage de Points VPC')
        ax.grid(True, alpha=0.3)
        ax.legend()
        
    def plot_point_distribution(self):
        """Graphique de distribution des points"""
        ax = self.figure.add_subplot(111)
        
        elevations = [p.z for p in self.profile_points]
        
        ax.hist(elevations, bins=30, alpha=0.7, color='skyblue', edgecolor='black')
        ax.set_xlabel('Élévation (m)')
        ax.set_ylabel('Nombre de points')
        ax.set_title('Distribution des