import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QGridLayout
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


class Calculator(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.current_input = ""
        self.result = 0
        self.operator = ""
        self.new_number = True
        self.drag_position = None

    def initUI(self):
        self.setWindowTitle('Calculatrice')
        self.setGeometry(300, 300, 320, 450)
        self.setFixedSize(320, 450)

        # Supprimer la barre de titre native
        self.setWindowFlags(Qt.FramelessWindowHint)

        # Layout principal
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Top bar custom
        self.create_custom_topbar(main_layout)

        # Écran d'affichage
        self.display = QLineEdit()
        self.display.setReadOnly(True)
        self.display.setAlignment(Qt.AlignRight)
        self.display.setStyleSheet("""
            QLineEdit {
                font-size: 24px;
                padding: 15px;
                border: none;
                background-color: #1a1a1a;
                color: #ffffff;
                margin: 10px;
                border-radius: 12px;
            }
        """)
        self.display.setText("0")
        main_layout.addWidget(self.display)

        # Grille des boutons
        button_layout = QGridLayout()

        # Définition des boutons
        buttons = [
            ('C', 0, 0, '#e74c3c'), ('±', 0, 1, '#9b59b6'), ('/', 0, 2, '#f39c12'), ('×', 0, 3, '#f39c12'),
            ('7', 1, 0, '#34495e'), ('8', 1, 1, '#34495e'), ('9', 1, 2, '#34495e'), ('-', 1, 3, '#f39c12'),
            ('4', 2, 0, '#34495e'), ('5', 2, 1, '#34495e'), ('6', 2, 2, '#34495e'), ('+', 2, 3, '#f39c12'),
            ('1', 3, 0, '#34495e'), ('2', 3, 1, '#34495e'), ('3', 3, 2, '#34495e'), ('=', 3, 3, '#27ae60'),
            ('0', 4, 0, '#34495e'), ('.', 4, 2, '#34495e')
        ]

        # Créer et ajouter les boutons
        for text, row, col, color in buttons:
            btn = QPushButton(text)
            btn.setFont(QFont('Arial', 16, QFont.Bold))
            btn.setMinimumSize(70, 50)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    color: white;
                    border: none;
                    border-radius: 15px;
                    font-size: 18px;
                    font-weight: bold;
                    margin: 2px;
                    box-shadow: 0 4px 8px rgba(0,0,0,0.3);
                }}
                QPushButton:hover {{
                    background-color: {self.darken_color(color)};
                    transform: translateY(-2px);
                    box-shadow: 0 6px 12px rgba(0,0,0,0.4);
                }}
                QPushButton:pressed {{
                    background-color: {self.darken_color(color, 0.8)};
                    transform: translateY(1px);
                    box-shadow: 0 2px 4px rgba(0,0,0,0.2);
                }}
            """)

            # Connecter les signaux
            if text.isdigit() or text == '.':
                btn.clicked.connect(lambda checked, t=text: self.number_clicked(t))
            elif text in ['+', '-', '×', '/']:
                btn.clicked.connect(lambda checked, t=text: self.operator_clicked(t))
            elif text == '=':
                btn.clicked.connect(self.equals_clicked)
            elif text == 'C':
                btn.clicked.connect(self.clear_clicked)
            elif text == '±':
                btn.clicked.connect(self.plus_minus_clicked)

            # Placer le bouton 0 sur deux colonnes
            if text == '0':
                button_layout.addWidget(btn, row, col, 1, 2)
            elif text != '.':  # Éviter d'ajouter le bouton . deux fois
                button_layout.addWidget(btn, row, col)
            else:
                button_layout.addWidget(btn, row, col)

        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)

        # Style de la fenêtre
        self.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                          stop:0 #667eea, stop:1 #764ba2);
                border-radius: 15px;
            }
        """)

    def create_custom_topbar(self, main_layout):
        """Créer une barre de titre personnalisée"""
        topbar = QWidget()
        topbar.setFixedHeight(40)
        topbar.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                          stop:0 #2C3E50, stop:0.5 #34495E, stop:1 #2C3E50);
                border-top-left-radius: 15px;
                border-top-right-radius: 15px;
                border-bottom: 1px solid rgba(255,255,255,0.1);
            }
        """)

        topbar_layout = QHBoxLayout()
        topbar_layout.setContentsMargins(15, 0, 15, 0)

        # Titre de l'application
        title_label = QPushButton("🧮 Calculatrice Pro")
        title_label.setStyleSheet("""
            QPushButton {
                color: #ECF0F1;
                font-size: 14px;
                font-weight: bold;
                border: none;
                text-align: left;
                padding: 5px;
                background: transparent;
            }
        """)
        title_label.setEnabled(False)  # Désactiver les interactions

        # Spacer pour pousser les boutons vers la droite
        topbar_layout.addWidget(title_label)
        topbar_layout.addStretch()

        # Bouton minimiser
        minimize_btn = QPushButton("−")
        minimize_btn.setFixedSize(30, 25)
        minimize_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(52, 152, 219, 0.8);
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(52, 152, 219, 1);
                transform: scale(1.05);
            }
            QPushButton:pressed {
                background-color: rgba(41, 128, 185, 1);
            }
        """)
        minimize_btn.clicked.connect(self.showMinimized)

        # Bouton fermer
        close_btn = QPushButton("×")
        close_btn.setFixedSize(30, 25)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(231, 76, 60, 0.8);
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(231, 76, 60, 1);
                transform: scale(1.05);
            }
            QPushButton:pressed {
                background-color: rgba(192, 57, 43, 1);
            }
        """)
        close_btn.clicked.connect(self.close)

        topbar_layout.addWidget(minimize_btn)
        topbar_layout.addSpacing(8)
        topbar_layout.addWidget(close_btn)

        topbar.setLayout(topbar_layout)
        main_layout.addWidget(topbar)

        # Permettre le déplacement de la fenêtre
        topbar.mousePressEvent = self.mousePressEvent
        topbar.mouseMoveEvent = self.mouseMoveEvent
        title_label.mousePressEvent = self.mousePressEvent
        title_label.mouseMoveEvent = self.mouseMoveEvent

    def darken_color(self, color, factor=0.9):
        """Assombrir une couleur pour l'effet hover"""
        color_map = {
            '#e74c3c': '#c0392b',
            '#9b59b6': '#8e44ad',
            '#f39c12': '#e67e22',
            '#34495e': '#2c3e50',
            '#27ae60': '#229954'
        }
        if factor < 1:
            return color_map.get(color, color)
        return color

    def number_clicked(self, number):
        if self.new_number:
            self.display.setText(number)
            self.new_number = False
        else:
            current_text = self.display.text()
            if number == '.' and '.' in current_text:
                return  # Éviter plusieurs points décimaux
            if current_text == "0" and number != '.':
                self.display.setText(number)
            else:
                self.display.setText(current_text + number)

    def operator_clicked(self, op):
        try:
            current_value = float(self.display.text())

            if self.operator and not self.new_number:
                # Effectuer le calcul précédent
                self.calculate()
                current_value = float(self.display.text())

            self.result = current_value
            self.operator = op
            self.new_number = True

        except ValueError:
            self.display.setText("Erreur")

    def equals_clicked(self):
        self.calculate()
        self.operator = ""
        self.new_number = True

    def calculate(self):
        try:
            current_value = float(self.display.text())

            if self.operator == '+':
                result = self.result + current_value
            elif self.operator == '-':
                result = self.result - current_value
            elif self.operator == '×':
                result = self.result * current_value
            elif self.operator == '/':
                if current_value == 0:
                    self.display.setText("Erreur")
                    return
                result = self.result / current_value
            else:
                return

            # Formater le résultat
            if result == int(result):
                self.display.setText(str(int(result)))
            else:
                self.display.setText(str(round(result, 10)))

        except (ValueError, ZeroDivisionError):
            self.display.setText("Erreur")

    def clear_clicked(self):
        self.display.setText("0")
        self.result = 0
        self.operator = ""
        self.new_number = True

    def plus_minus_clicked(self):
        try:
            current_value = float(self.display.text())
            new_value = -current_value

            if new_value == int(new_value):
                self.display.setText(str(int(new_value)))
            else:
                self.display.setText(str(new_value))

        except ValueError:
            pass

    def keyPressEvent(self, event):
        """Gérer les entrées clavier"""
        key = event.key()

        if key >= Qt.Key_0 and key <= Qt.Key_9:
            self.number_clicked(str(key - Qt.Key_0))
        elif key == Qt.Key_Period:
            self.number_clicked('.')
        elif key == Qt.Key_Plus:
            self.operator_clicked('+')
        elif key == Qt.Key_Minus:
            self.operator_clicked('-')
        elif key == Qt.Key_Asterisk:
            self.operator_clicked('×')
        elif key == Qt.Key_Slash:
            self.operator_clicked('/')
        elif key in [Qt.Key_Return, Qt.Key_Enter, Qt.Key_Equal]:
            self.equals_clicked()
        elif key in [Qt.Key_Escape, Qt.Key_C]:
            self.clear_clicked()
        elif key == Qt.Key_Backspace:
            current = self.display.text()
            if len(current) > 1:
                self.display.setText(current[:-1])
            else:
                self.display.setText("0")
                self.new_number = True

    def mousePressEvent(self, event):
        """Gérer le clic pour déplacer la fenêtre"""
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        """Gérer le déplacement de la fenêtre"""
        if event.buttons() == Qt.LeftButton and self.drag_position:
            self.move(event.globalPos() - self.drag_position)
            event.accept()


def main():
    app = QApplication(sys.argv)
    calculator = Calculator()
    calculator.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()