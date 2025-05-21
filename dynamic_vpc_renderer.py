import os
from qgis.PyQt.QtCore import QObject, pyqtSignal, QTimer
from qgis.PyQt.QtWidgets import QAction, QToolBar, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton, QSpinBox, QDoubleSpinBox
from qgis.core import (
    QgsProject, QgsMapLayer, QgsPointCloudLayer, QgsMapCanvas,
    QgsPointCloudRenderer, QgsPointCloudAttribute, QgsRectangle,
    QgsPointCloudRgbRenderer, QgsPointCloudClassifiedRenderer,
    QgsPointCloudCategory, QgsRendererCategory, QgsSymbol,
    QgsPointCloudStatistics, QgsApplication, QgsMessageLog
)
from qgis.gui import QgsMapCanvasItem
import numpy as np
from typing import Dict, List, Tuple, Optional

class DynamicVPCRenderer(QObject):
    """
    Classe principale pour le rendu dynamique des nuages de points VPC
    """
    
    def __init__(self, iface):
        super().__init__()
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.current_vpc_layer = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_renderer)
        self.timer.setSingleShot(True)
        
        # Paramètres de rendu
        self.render_attribute = 'Z'  # Attribut par défaut
        self.render_mode = 'graduated'  # 'graduated', 'classified', 'rgb'
        self.point_size = 2.0
        self.classes_count = 5
        
        # Interface utilisateur
        self.setup_ui()
        
        # Connexions aux signaux
        self.canvas.extentsChanged.connect(self.on_extent_changed)
        QgsProject.instance().layersAdded.connect(self.on_layers_added)
        
    def setup_ui(self):
        """Configure l'interface utilisateur"""
        # Création de la toolbar
        self.toolbar = self.iface.addToolBar("Rendu Dynamique VPC")
        
        # Widget principal
        self.widget = QWidget()
        layout = QHBoxLayout(self.widget)
        
        # Sélection de la couche VPC
        layout.addWidget(QLabel("Couche VPC:"))
        self.layer_combo = QComboBox()
        self.layer_combo.currentTextChanged.connect(self.on_layer_changed)
        layout.addWidget(self.layer_combo)
        
        # Sélection de l'attribut
        layout.addWidget(QLabel("Attribut:"))
        self.attribute_combo = QComboBox()
        self.attribute_combo.currentTextChanged.connect(self.on_attribute_changed)
        layout.addWidget(self.attribute_combo)
        
        # Mode de rendu
        layout.addWidget(QLabel("Mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(['graduated', 'classified', 'rgb'])
        self.mode_combo.currentTextChanged.connect(self.on_mode_changed)
        layout.addWidget(self.mode_combo)
        
        # Nombre de classes
        layout.addWidget(QLabel("Classes:"))
        self.classes_spin = QSpinBox()
        self.classes_spin.setRange(2, 20)
        self.classes_spin.setValue(5)
        self.classes_spin.valueChanged.connect(self.on_classes_changed)
        layout.addWidget(self.classes_spin)
        
        # Taille des points
        layout.addWidget(QLabel("Taille:"))
        self.size_spin = QDoubleSpinBox()
        self.size_spin.setRange(0.1, 10.0)
        self.size_spin.setValue(2.0)
        self.size_spin.setSingleStep(0.1)
        self.size_spin.valueChanged.connect(self.on_size_changed)
        layout.addWidget(self.size_spin)
        
        # Bouton de mise à jour manuelle
        self.update_button = QPushButton("Mettre à jour")
        self.update_button.clicked.connect(self.update_renderer)
        layout.addWidget(self.update_button)
        
        # Activation/désactivation du mode automatique
        self.auto_button = QPushButton("Auto: ON")
        self.auto_button.setCheckable(True)
        self.auto_button.setChecked(True)
        self.auto_button.clicked.connect(self.toggle_auto_mode)
        layout.addWidget(self.auto_button)
        
        self.toolbar.addWidget(self.widget)
        
        # Mise à jour de la liste des couches
        self.update_layer_list()
        
    def update_layer_list(self):
        """Met à jour la liste des couches VPC disponibles"""
        self.layer_combo.clear()
        self.layer_combo.addItem("Sélectionner une couche VPC")
        
        for layer in QgsProject.instance().mapLayers().values():
            if isinstance(layer, QgsPointCloudLayer):
                self.layer_combo.addItem(layer.name(), layer.id())
                
    def on_layers_added(self, layers):
        """Gestionnaire pour l'ajout de nouvelles couches"""
        self.update_layer_list()
        
    def on_layer_changed(self, layer_name):
        """Gestionnaire pour le changement de couche"""
        if layer_name == "Sélectionner une couche VPC":
            self.current_vpc_layer = None
            return
            
        layer_id = self.layer_combo.currentData()
        if layer_id:
            self.current_vpc_layer = QgsProject.instance().mapLayer(layer_id)
            self.update_attribute_list()
            
    def update_attribute_list(self):
        """Met à jour la liste des attributs disponibles"""
        self.attribute_combo.clear()
        
        if not self.current_vpc_layer:
            return
            
        attributes = self.current_vpc_layer.attributes()
        for attr in attributes:
            self.attribute_combo.addItem(attr.name())
            
        # Sélectionner Z par défaut si disponible
        z_index = self.attribute_combo.findText('Z')
        if z_index >= 0:
            self.attribute_combo.setCurrentIndex(z_index)
            
    def on_attribute_changed(self, attribute_name):
        """Gestionnaire pour le changement d'attribut"""
        self.render_attribute = attribute_name
        if self.auto_button.isChecked():
            self.schedule_update()
            
    def on_mode_changed(self, mode):
        """Gestionnaire pour le changement de mode de rendu"""
        self.render_mode = mode
        if self.auto_button.isChecked():
            self.schedule_update()
            
    def on_classes_changed(self, classes):
        """Gestionnaire pour le changement du nombre de classes"""
        self.classes_count = classes
        if self.auto_button.isChecked():
            self.schedule_update()
            
    def on_size_changed(self, size):
        """Gestionnaire pour le changement de taille des points"""
        self.point_size = size
        if self.auto_button.isChecked():
            self.schedule_update()
            
    def toggle_auto_mode(self, checked):
        """Active/désactive le mode automatique"""
        if checked:
            self.auto_button.setText("Auto: ON")
            self.schedule_update()
        else:
            self.auto_button.setText("Auto: OFF")
            self.timer.stop()
            
    def on_extent_changed(self):
        """Gestionnaire pour le changement d'étendue de la carte"""
        if self.auto_button.isChecked() and self.current_vpc_layer:
            self.schedule_update()
            
    def schedule_update(self):
        """Programme une mise à jour du rendu avec un délai"""
        self.timer.stop()
        self.timer.start(500)  # Délai de 500ms pour éviter trop de mises à jour
        
    def get_visible_points_statistics(self) -> Optional[Dict]:
        """Calcule les statistiques des points visibles dans l'étendue courante"""
        if not self.current_vpc_layer:
            return None
            
        try:
            # Obtenir l'étendue courante de la carte
            extent = self.canvas.extent()
            
            # Obtenir les statistiques pour l'attribut sélectionné
            request = self.current_vpc_layer.createReadRequest()
            request.setRectangle(extent)
            
            if self.render_attribute:
                # Calculer les statistiques pour l'attribut sélectionné
                stats = self.current_vpc_layer.statistics(self.render_attribute, request)
                
                return {
                    'min': stats.minimum(),
                    'max': stats.maximum(),
                    'mean': stats.mean(),
                    'std': stats.stDev(),
                    'count': stats.count()
                }
        except Exception as e:
            QgsMessageLog.logMessage(f"Erreur lors du calcul des statistiques: {str(e)}", "DynamicVPCRenderer")
            return None
            
    def create_graduated_renderer(self, stats: Dict) -> QgsPointCloudRenderer:
        """Crée un rendu gradué basé sur les statistiques"""
        if not stats or stats['count'] == 0:
            return None
            
        # Créer les intervalles
        min_val = stats['min']
        max_val = stats['max']
        
        if min_val == max_val:
            # Valeurs constantes, utiliser un rendu simple
            return self.create_single_color_renderer()
            
        intervals = np.linspace(min_val, max_val, self.classes_count + 1)
        
        # Créer les catégories avec une palette de couleurs
        categories = []
        colors = self.generate_color_palette(self.classes_count)
        
        for i in range(self.classes_count):
            lower = intervals[i]
            upper = intervals[i + 1]
            
            # Créer la catégorie
            category = QgsPointCloudCategory(
                lower,
                upper,
                colors[i],
                f"{lower:.2f} - {upper:.2f}"
            )
            categories.append(category)
            
        # Créer le rendu classifié
        renderer = QgsPointCloudClassifiedRenderer(self.render_attribute, categories)
        renderer.setPointSize(self.point_size)
        
        return renderer
        
    def create_single_color_renderer(self) -> QgsPointCloudRenderer:
        """Crée un rendu avec une couleur unique"""
        renderer = QgsPointCloudRgbRenderer()
        renderer.setPointSize(self.point_size)
        return renderer
        
    def generate_color_palette(self, count: int) -> List[Tuple[int, int, int]]:
        """Génère une palette de couleurs pour les classes"""
        colors = []
        
        # Palette viridis simplifiée
        viridis_colors = [
            (68, 1, 84),      # Violet foncé
            (59, 82, 139),    # Bleu foncé
            (33, 144, 140),   # Bleu-vert
            (93, 201, 99),    # Vert
            (253, 231, 37)    # Jaune
        ]
        
        # Interpoler les couleurs si nécessaire
        if count <= len(viridis_colors):
            step = len(viridis_colors) // count
            colors = viridis_colors[::step][:count]
        else:
            # Interpolation linéaire pour plus de couleurs
            for i in range(count):
                ratio = i / (count - 1) if count > 1 else 0
                idx = ratio * (len(viridis_colors) - 1)
                
                lower_idx = int(idx)
                upper_idx = min(lower_idx + 1, len(viridis_colors) - 1)
                
                if lower_idx == upper_idx:
                    colors.append(viridis_colors[lower_idx])
                else:
                    # Interpolation
                    weight = idx - lower_idx
                    r = int(viridis_colors[lower_idx][0] * (1 - weight) + viridis_colors[upper_idx][0] * weight)
                    g = int(viridis_colors[lower_idx][1] * (1 - weight) + viridis_colors[upper_idx][1] * weight)
                    b = int(viridis_colors[lower_idx][2] * (1 - weight) + viridis_colors[upper_idx][2] * weight)
                    colors.append((r, g, b))
                    
        return colors
        
    def update_renderer(self):
        """Met à jour le rendu de la couche VPC courante"""
        if not self.current_vpc_layer or not self.render_attribute:
            return
            
        try:
            # Obtenir les statistiques des points visibles
            stats = self.get_visible_points_statistics()
            
            if not stats:
                QgsMessageLog.logMessage("Impossible d'obtenir les statistiques", "DynamicVPCRenderer")
                return
                
            # Créer le nouveau rendu
            new_renderer = None
            
            if self.render_mode == 'graduated':
                new_renderer = self.create_graduated_renderer(stats)
            elif self.render_mode == 'classified':
                new_renderer = self.create_graduated_renderer(stats)  # Même logique pour l'instant
            elif self.render_mode == 'rgb':
                new_renderer = self.create_single_color_renderer()
                
            if new_renderer:
                # Appliquer le nouveau rendu
                self.current_vpc_layer.setRenderer(new_renderer)
                self.current_vpc_layer.triggerRepaint()
                
                # Log des informations
                QgsMessageLog.logMessage(
                    f"Rendu mis à jour - Points visibles: {stats['count']}, "
                    f"Min: {stats['min']:.2f}, Max: {stats['max']:.2f}, "
                    f"Moyenne: {stats['mean']:.2f}",
                    "DynamicVPCRenderer"
                )
                
        except Exception as e:
            QgsMessageLog.logMessage(f"Erreur lors de la mise à jour du rendu: {str(e)}", "DynamicVPCRenderer")

# Plugin principal
class DynamicVPCRendererPlugin:
    """Plugin principal pour QGIS"""
    
    def __init__(self, iface):
        self.iface = iface
        self.renderer = None
        
    def initGui(self):
        """Initialise l'interface graphique"""
        self.renderer = DynamicVPCRenderer(self.iface)
        
    def unload(self):
        """Nettoie les ressources lors de la désactivation"""
        if self.renderer:
            if hasattr(self.renderer, 'toolbar'):
                self.iface.removeToolBar(self.renderer.toolbar)
            self.renderer = None

# Pour l'utilisation en tant que script autonome
def run_script():
    """Fonction pour exécuter le script directement dans la console QGIS"""
    # Vérifier si QGIS est disponible
    try:
        from qgis.utils import iface
        if iface:
            global dynamic_vpc_renderer
            dynamic_vpc_renderer = DynamicVPCRenderer(iface)
            print("Rendu dynamique VPC initialisé avec succès!")
        else:
            print("Interface QGIS non disponible")
    except ImportError:
        print("QGIS non disponible - utiliser comme plugin")

if __name__ == '__main__':
    run_script()