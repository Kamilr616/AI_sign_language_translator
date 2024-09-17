# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'gui.ui'
##
## Created by: Qt User Interface Compiler version 6.7.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QCheckBox, QFrame, QGridLayout,
    QLabel, QMainWindow, QPushButton, QSizePolicy,
    QSpinBox, QStatusBar, QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(900, 599)
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.startButton = QPushButton(self.centralwidget)
        self.startButton.setObjectName(u"startButton")
        self.startButton.setGeometry(QRect(730, 430, 75, 61))
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        self.startButton.setFont(font)
        self.pushButton2 = QPushButton(self.centralwidget)
        self.pushButton2.setObjectName(u"pushButton2")
        self.pushButton2.setGeometry(QRect(650, 240, 75, 41))
        self.pushButton2.setFont(font)
        self.label = QLabel(self.centralwidget)
        self.label.setObjectName(u"label")
        self.label.setGeometry(QRect(0, 10, 640, 480))
        self.label.setFrameShape(QFrame.Shape.Box)
        self.label2 = QLabel(self.centralwidget)
        self.label2.setObjectName(u"label2")
        self.label2.setGeometry(QRect(10, 500, 641, 71))
        font1 = QFont()
        font1.setPointSize(20)
        font1.setBold(True)
        self.label2.setFont(font1)
        self.checkBox = QCheckBox(self.centralwidget)
        self.checkBox.setObjectName(u"checkBox")
        self.checkBox.setGeometry(QRect(660, 210, 51, 20))
        font2 = QFont()
        font2.setPointSize(10)
        self.checkBox.setFont(font2)
        self.pushButton3 = QPushButton(self.centralwidget)
        self.pushButton3.setObjectName(u"pushButton3")
        self.pushButton3.setGeometry(QRect(790, 150, 71, 31))
        self.gridLayoutWidget = QWidget(self.centralwidget)
        self.gridLayoutWidget.setObjectName(u"gridLayoutWidget")
        self.gridLayoutWidget.setGeometry(QRect(762, 10, 121, 131))
        self.gridLayout = QGridLayout(self.gridLayoutWidget)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.label_2 = QLabel(self.gridLayoutWidget)
        self.label_2.setObjectName(u"label_2")

        self.gridLayout.addWidget(self.label_2, 0, 0, 1, 1)

        self.spinBox1 = QSpinBox(self.gridLayoutWidget)
        self.spinBox1.setObjectName(u"spinBox1")
        self.spinBox1.setFont(font2)
        self.spinBox1.setCursor(QCursor(Qt.CursorShape.SizeVerCursor))
        self.spinBox1.setWrapping(False)
        self.spinBox1.setMaximum(100)
        self.spinBox1.setValue(75)

        self.gridLayout.addWidget(self.spinBox1, 0, 1, 1, 1)

        self.label_4 = QLabel(self.gridLayoutWidget)
        self.label_4.setObjectName(u"label_4")

        self.gridLayout.addWidget(self.label_4, 2, 0, 1, 1)

        self.spinBox3 = QSpinBox(self.gridLayoutWidget)
        self.spinBox3.setObjectName(u"spinBox3")
        self.spinBox3.setFont(font2)
        self.spinBox3.setCursor(QCursor(Qt.CursorShape.SizeVerCursor))
        self.spinBox3.setMaximum(100)
        self.spinBox3.setValue(75)

        self.gridLayout.addWidget(self.spinBox3, 2, 1, 1, 1)

        self.spinBox2 = QSpinBox(self.gridLayoutWidget)
        self.spinBox2.setObjectName(u"spinBox2")
        self.spinBox2.setFont(font2)
        self.spinBox2.setCursor(QCursor(Qt.CursorShape.SizeVerCursor))
        self.spinBox2.setMaximum(100)
        self.spinBox2.setValue(75)

        self.gridLayout.addWidget(self.spinBox2, 1, 1, 1, 1)

        self.label_3 = QLabel(self.gridLayoutWidget)
        self.label_3.setObjectName(u"label_3")

        self.gridLayout.addWidget(self.label_3, 1, 0, 1, 1)

        self.gridLayoutWidget_2 = QWidget(self.centralwidget)
        self.gridLayoutWidget_2.setObjectName(u"gridLayoutWidget_2")
        self.gridLayoutWidget_2.setGeometry(QRect(650, 40, 101, 80))
        self.gridLayout_2 = QGridLayout(self.gridLayoutWidget_2)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.gridLayout_2.setContentsMargins(0, 0, 0, 0)
        self.label_5 = QLabel(self.gridLayoutWidget_2)
        self.label_5.setObjectName(u"label_5")

        self.gridLayout_2.addWidget(self.label_5, 0, 0, 1, 1)

        self.label_6 = QLabel(self.gridLayoutWidget_2)
        self.label_6.setObjectName(u"label_6")

        self.gridLayout_2.addWidget(self.label_6, 1, 0, 1, 1)

        self.spinBox4 = QSpinBox(self.gridLayoutWidget_2)
        self.spinBox4.setObjectName(u"spinBox4")
        self.spinBox4.setMaximum(105)
        self.spinBox4.setValue(70)

        self.gridLayout_2.addWidget(self.spinBox4, 0, 1, 1, 1)

        self.spinBox5 = QSpinBox(self.gridLayoutWidget_2)
        self.spinBox5.setObjectName(u"spinBox5")
        self.spinBox5.setMinimum(1)
        self.spinBox5.setMaximum(500)
        self.spinBox5.setValue(149)

        self.gridLayout_2.addWidget(self.spinBox5, 1, 1, 1, 1)

        self.pushButton4 = QPushButton(self.centralwidget)
        self.pushButton4.setObjectName(u"pushButton4")
        self.pushButton4.setGeometry(QRect(660, 150, 71, 31))
        MainWindow.setCentralWidget(self.centralwidget)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"Sign language translator", None))
        self.startButton.setText(QCoreApplication.translate("MainWindow", u"+", None))
        self.pushButton2.setText(QCoreApplication.translate("MainWindow", u"Speak", None))
        self.label.setText(QCoreApplication.translate("MainWindow", u"label", None))
        self.label2.setText(QCoreApplication.translate("MainWindow", u"TextLabel", None))
        self.checkBox.setText(QCoreApplication.translate("MainWindow", u"Auto", None))
        self.pushButton3.setText(QCoreApplication.translate("MainWindow", u"Reset NN", None))
        self.label_2.setText(QCoreApplication.translate("MainWindow", u"Detection", None))
#if QT_CONFIG(whatsthis)
        self.spinBox1.setWhatsThis("")
#endif // QT_CONFIG(whatsthis)
        self.spinBox1.setSpecialValueText("")
        self.spinBox1.setSuffix(QCoreApplication.translate("MainWindow", u"%", None))
        self.spinBox1.setPrefix("")
        self.label_4.setText(QCoreApplication.translate("MainWindow", u"Tracking", None))
#if QT_CONFIG(whatsthis)
        self.spinBox3.setWhatsThis("")
#endif // QT_CONFIG(whatsthis)
        self.spinBox3.setSuffix(QCoreApplication.translate("MainWindow", u"%", None))
        self.spinBox3.setPrefix("")
#if QT_CONFIG(whatsthis)
        self.spinBox2.setWhatsThis("")
#endif // QT_CONFIG(whatsthis)
        self.spinBox2.setSuffix(QCoreApplication.translate("MainWindow", u"%", None))
        self.spinBox2.setPrefix("")
        self.label_3.setText(QCoreApplication.translate("MainWindow", u"Presence ", None))
        self.label_5.setText(QCoreApplication.translate("MainWindow", u"Volume", None))
        self.label_6.setText(QCoreApplication.translate("MainWindow", u"Rate", None))
        self.spinBox4.setSuffix(QCoreApplication.translate("MainWindow", u"%", None))
        self.pushButton4.setText(QCoreApplication.translate("MainWindow", u"Reset TTS", None))
    # retranslateUi

