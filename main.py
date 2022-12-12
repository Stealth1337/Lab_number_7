import sys, random, math
from PyQt5 import QtGui, QtCore, uic
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QColorDialog, QFileDialog, QMessageBox
from PyQt5.QtGui import QPainter, QPainterPath, QBrush, QPen, QColor, QPolygon
from PyQt5.QtCore import Qt, QPoint, pyqtSignal, QRect, QMargins
from design import Ui_MainWindow
import logging
import xml.etree.ElementTree as ET

COLOR_SELECTED = Qt.red
COLOR_BORDER = Qt.gray
INITIAL_SIZE = 50
INITIAL_RADIUS = INITIAL_SIZE // 2
STEP_CHANGE_SIZE = 10 // 2


class Shape():
    _linked_widget = None
    _is_current = False

    def __init__(self, point, color, length=INITIAL_SIZE, activate=False):
        self._rect = QRect(0, 0, length, length)
        self._rect.moveCenter(point)
        self._activate = activate
        self._color = color
        self.canmove = True

    @property
    def rect(self):
        return self._rect

    @classmethod
    def get_linked_widget(cls):
        return cls._linked_widget

    @classmethod
    def set_linked_widget(cls, widget):
        cls._linked_widget = widget
        widget.clicked.connect(lambda: widget.window().selectShape(cls))

    @classmethod
    def set_is_current(cls, status):
        if cls.get_linked_widget():
            color = 'yellow' if status else 'none'
            cls.get_linked_widget().setStyleSheet("background-color: " + color)

    @property
    def color(self):
        return COLOR_SELECTED if self._activate else self._color

    @color.setter
    def color(self, color):
        self._color = color

    def draw(self, painter):
        pass

    def paint(self, painter):
        if not painter.isActive():
            return
        painter.save()
        painter.setPen(QPen(COLOR_BORDER, 0, Qt.SolidLine))
        painter.setBrush(QBrush(self.color, Qt.SolidPattern))
        self.draw(painter)
        painter.restore()

    def changeFlag(self):
        self._activate = not self._activate
        logger.info("Activated" if self._activate else "Deactivated")

    def getStatus(self):
        return self._activate

    def deactivate(self):
        self._activate = False

    def isSelected(self, point):
        pass

    def is_inner_canvas(self, canvas: QRect):
        return self._rect.united(canvas) == canvas

    def addMargins(self, size_margins):
        return QMargins(size_margins,
                        size_margins,
                        size_margins,
                        size_margins)

    def is_valid_size(self, shape_copy: QRect):
        if shape_copy.width() < 10 and shape_copy.height() < 10:
            return False
        return True

    def move_inplace(self, canvas: QRect, dx, dy):
        old_rect = self._rect
        self._rect = self._rect.translated(dx, dy)
        if not self.is_inner_canvas(canvas):
            self._rect = old_rect
            return False
        return True

    def changesize(self, canvas: QRect, dsize):
        old_rect = self._rect
        self._rect = self._rect + self.addMargins(dsize)
        if (not self.is_inner_canvas(canvas)) or (not self.is_valid_size(self._rect + self.addMargins(dsize))):
            self._rect = old_rect
            return False
        print(self._rect)
        return True

    def save(self) -> ET:
        element = ET.Element(self.__class__.__name__)
        element.set('color', self.color.name())
        rect = ET.SubElement(element, 'rect')
        rect.set('left', str(self.rect.x()))
        rect.set('top', str(self.rect.y()))
        rect.set('width', str(self.rect.width()))
        rect.set('height', str(self.rect.height()))
        return element


### CLASS CIRCLE ###=====
class CCircle(Shape):
    def draw(self, painter):
        painter.drawEllipse(self._rect)

    def isSelected(self, point):
        d = self._rect.center() - point
        return (d.x() ** 2 + d.y() ** 2) <= ((self._rect.width() // 2) ** 2)


### CLASS RECTANGLE ###
class Rectangle(Shape):
    def draw(self, painter):
        painter.drawRect(self._rect)

    def isSelected(self, point):
        return self._rect.contains(point)


### CLASS TRIANGLE ###
class Triangle(Shape):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rect.setHeight(int(round(self._rect.width() * math.sqrt(3) / 2)))
        self._poligon = QPolygon([
            QPoint(self._rect.center().x(), self._rect.top()),
            self._rect.bottomRight(),
            self._rect.bottomLeft()
        ])

    def draw(self, painter):
        painter.drawPolygon(self._poligon)

    def isSelected(self, point):
        return self._poligon.containsPoint(point, Qt.WindingFill)

    def move_inplace(self, canvas, dx, dy):
        if super().move_inplace(canvas, dx, dy):
            self._poligon.translate(dx, dy)

    def changesize(self, canvas: QRect, dsize):
        if super().changesize(canvas, dsize):
            self._poligon = QPolygon([
                QPoint(self._rect.center().x(), self._rect.top()),
                self._rect.bottomRight(),
                self._rect.bottomLeft()
            ])
            return True
        return False

    def save(self) -> ET:
        element = super().save()
        polygon = ET.SubElement(element, 'polygon')
        points = ET.SubElement(polygon, 'points')
        points.set('count_points', '3')
        for point in self._poligon:
            el_point = ET.SubElement(points, 'point')
            el_point.set('x', str(point.x()))
            el_point.set('y', str(point.y()))
        return element


### CLASS GROUP ###
class Group(Shape):

    def __init__(self):
        self._childrens = []
        self._rect = None
        self._activate = False
        self._color = Qt.black
        self.canmove = True

    def updateRect(self) -> QRect:
        self._rect = QRect(self._childrens[0].rect.x(),
                           self._childrens[0].rect.y(),
                           self._childrens[0].rect.width(),
                           self._childrens[0].rect.height())
        if self._childrens:
            for child in self._childrens:
                self._rect = child.rect.united(self._rect)

    def draw(self, painter):
        painter.drawRect(self._rect)
        for elem in self._childrens:
            elem.draw(painter)

    def deactivate(self):
        for elem in self._childrens:
            elem._activate = False
        self._activate = False

    def changeFlag(self):
        for elem in self._childrens:
            elem._activate = not elem._activate
        self._activate = not self._activate

    def addChild(self, child):
        self._childrens.append(child)
        self.updateRect()

    def isSelected(self, point):
        for shape in self._childrens:
            if shape.isSelected(point):
                return True
        return False

    def move_inplace(self, canvas: QRect, dx, dy):
        if super(Group, self).move_inplace(canvas, dx, dy):
            for elem in self._childrens:
                elem.move_inplace(canvas, dx, dy)

    def changesize(self, canvas: QRect, dsize) -> Shape:
        for elem in self._childrens:
            old_rect = elem._rect
            elem._rect = elem._rect + self.addMargins()
            if not elem.changesize(canvas, dsize):
                self.canmove = False
            else: self.canmove = True
        self.updateRect()
        return True

    def save(self) -> ET:
        element = super().save()
        group = ET.SubElement(element, 'group')
        group_elements = ET.SubElement(group, 'group_elements')
        group_elements.set('group_elements', f'{len(self._childrens)}')
        for element in group_elements:
            element = ET.SubElement(element, 'element')
            element.set('123', '123')
        return element


### MY STORAGE ###
class Storage:
    arr = []

    def __len__(self):
        return len(self.arr)

    def __getitem__(self, item) -> Shape:
        return self.arr[item]

    def __setitem__(self, item, value):
        self.arr[item] = value
        return 0

    def addItem(self, item):
        self.arr.append(item)

    def delItem(self, index):
        self.arr.pop(index)

    def getItem(self, index):
        return self.arr[index]

    def insertItem(self, item, index):
        self.arr.insert(index, item)

    def deact_all(self):
        for i in self.arr:
            i.deactivate()

    def deleteAllActive(self):
        for i in range(len(self.arr) - 1, -1, -1):
            if self.arr[i]._activate:
                self.arr.remove(self.arr[i])

    def getActiveItems(self):
        for i in self.arr:
            if i.getStatus():
                yield i

    def save(self, filename):

        root = ET.Element('storage')
        items = ET.SubElement(root, 'items')
        count_items = 0
        for elem in self:
            items.append(elem.save())
            count_items += 1
        items.set('count_elements', str(count_items))
        print(ET.indent(root, space='  '))
        result = ET.tostring(root, encoding='utf-8')
        with open(filename, 'wb') as f:
            f.write(result)


class Window(QMainWindow):
    MOVE_KEYS = [87, 65, 83, 68]
    CHANGE_SIZE_KEYS = [61, 45]
    STEP_MOVE = 5
    HEIGHT_HEADER = 80
    MINIMUM_WIDTH = 750
    MINIMUM_HEIGHT = HEIGHT_HEADER + 100
    INITIAL_COLOR = QColor(Qt.black)

    def __init__(self):
        super().__init__()
        self._currentColor = None
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.window_width = self.size().width()
        self.window_height = self.size().height()
        self.storage = Storage()
        CCircle.set_linked_widget(self.ui.circlebutton)
        Rectangle.set_linked_widget(self.ui.rectanlebutton)
        Triangle.set_linked_widget(self.ui.trianglebutton)
        self.ui.colorButton.clicked.connect(self.changeColor)
        self.ui.saveButton.clicked.connect(self.saveToFile)
        self.active_figure_class = CCircle
        self.active_figure_class.set_is_current(True)
        self.currentColor = self.INITIAL_COLOR
        self.ui.groupButton.clicked.connect(self.groupElements)

    @property
    def currentColor(self):
        return self._currentColor

    @currentColor.setter
    def currentColor(self, color: QColor):
        if color != self._currentColor:
            for elem in self.storage.getActiveItems():
                elem.color = color
            self.storage.deact_all()
            self._currentColor = color
            self.ui.colorButton.setStyleSheet(f'background: {color.name()}')

    def resizeEvent(self, a0):
        minimal_height = self.MINIMUM_HEIGHT
        minimal_width = self.MINIMUM_WIDTH
        for elem in self.storage:
            minimal_height = max(minimal_height, elem.rect.bottomRight().y())
            minimal_width = max(minimal_width, elem.rect.bottomRight().x())
        self.setMinimumSize(minimal_width, minimal_height)

    @property
    def canvasrect(self):
        return QRect(0, self.HEIGHT_HEADER, self.width(), self.height() - self.HEIGHT_HEADER)

    def check(self, point):
        for elem in reversed(self.storage):
            if elem.isSelected(point):
                elem.changeFlag()
                break
        else:
            shape = self.active_figure_class(point, self.currentColor)
            if shape.is_inner_canvas(self.canvasrect):
                self.storage.addItem(shape)

    def changeColor(self):
        color = QColorDialog.getColor(self.currentColor, self, 'Выберите цвет')
        if color.isValid():
            self.currentColor = color

    def selectShape(self, shape):
        if shape is not self.active_figure_class:
            self.active_figure_class.set_is_current(False)
            self.active_figure_class = shape
            self.active_figure_class.set_is_current(True)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        for shapes in self.storage:
            shapes.paint(painter)

    def mousePressEvent(self, event):
        modifier = QApplication.keyboardModifiers()
        if not modifier == Qt.ControlModifier:
            self.storage.deact_all()
        point = event.pos()
        self.check(point)
        self.ui.groupButton.setEnabled(sum(1 for _ in self.storage.getActiveItems()) > 1)
        self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            self.storage.deleteAllActive()
        elif event.key() in self.MOVE_KEYS:
            dx, dy = [
                (0, -self.STEP_MOVE),  # Qt.Key_W
                (-self.STEP_MOVE, 0),  # Qt.Key_A
                (0, self.STEP_MOVE),  # Qt.Key_S
                (self.STEP_MOVE, 0)  # Qt.Key_D
            ][self.MOVE_KEYS.index(event.key())]
            for shape in self.storage.getActiveItems():
                shape.move_inplace(self.canvasrect, dx, dy)
        elif event.key() in self.CHANGE_SIZE_KEYS:
            dsize = [STEP_CHANGE_SIZE, -STEP_CHANGE_SIZE][self.CHANGE_SIZE_KEYS.index(event.key())]
            for shape in self.storage.getActiveItems():
                shape.changesize(self.canvasrect, dsize)
        self.update()

    def groupElements(self):
        group = Group()
        for elem in self.storage:
            if elem.getStatus():
                group.addChild(elem)
        self.storage.deleteAllActive()
        self.storage.deact_all()
        self.storage.addItem(group)
        print(group._childrens)
        print(self.storage.arr)
        self.update()

    def saveToFile(self):
        filename, _ = QFileDialog.getSaveFileName(self, 'Сохранение фигур', filter='*.xml')
        if filename:
            msg = QMessageBox(self)
            msg.setWindowTitle("Сохранение файла")
            try:
                self.storage.save(filename)
            except BaseException as e:
                msg.setText("Ошибка сохранения")
                msg.setIcon(QMessageBox.Critical)
            else:
                msg.setText(f"Файл '{filename}' успешно сохранен")
            finally:
                msg.exec_()


def my_excepthook(type, value, tback):
    QtWidgets.QMessageBox.critical(
        window, "CRITICAL ERROR", str(value),
        QtWidgets.QMessageBox.Cancel
    )
    sys.__excepthook__(type, value, tback)


sys.excepthook = my_excepthook

if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    App = QApplication(sys.argv)
    window = Window()
    window.show()
    sys.exit(App.exec())
