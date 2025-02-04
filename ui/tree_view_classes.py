import core_files.image_editor as img
import core_files.conversions as conv
import core_files.statusbar as sts

from core_files import core
from PyQt5 import QtCore, QtGui, QtWidgets
from PIL.ImageQt import Image as ImageQt

log = sts.get_logger(__name__)


class Node(object):
    def __init__(self, id, parent=None):

        self._id = id
        self.name = ""
        self._children = []
        self._parent = parent
        self.image = None

        if parent is not None:
            parent.addChild(self)

    def typeInfo(self):
        return "NODE"

    def addChild(self, child):
        self._children.append(child)

    def insertChild(self, position, child):

        if position < 0 or position > len(self._children):
            return False

        self._children.insert(position, child)
        child._parent = self
        return True

    def removeChild(self, position):

        if position < 0 or position > len(self._children):
            return False

        child = self._children.pop(position)
        child._parent = None

        return True

    def setName(self, name):
        self._name = name

    def child(self, row):
        return self._children[row]

    def childCount(self):
        return len(self._children)

    def parent(self):
        return self._parent

    def row(self):
        if self._parent is not None:
            return self._parent._children.index(self)

    def log(self, tabLevel=-1):

        output = ""
        tabLevel += 1

        for i in range(tabLevel):
            output += "\t"

        output += "|------" + self._name + "\n"

        for child in self._children:
            output += child.log(tabLevel)

        tabLevel -= 1
        output += "\n"

        return output

    def __repr__(self):
        return self.log()

    def getId(self):
        return self._id

    def setId(self, val):
        self._id = val


class TableNode(Node):
    def __init__(self, id, parent=None):
        super(TableNode, self).__init__(id, parent)
        self.name = "Table "

    def typeInfo(self):
        return "table_node"


class OWNode(Node):
    '''
    Represent an OW in Qt.
    INPUTS: id, root, parent
    '''
    def __init__(self, id, root=None, parent=None):
        super(OWNode, self).__init__(id, parent)
        self.name = "Overworld "
        self.frames = 0
        self.root = root

        if parent is not None:
            self.setInfo()

    def typeInfo(self):
        return "ow_node"

    def setInfo(self):
        table_id = self._parent.getId()
        ow_id = self._id

        self.image = img.ImageManager(
            self.root).get_ow_frame(ow_id, table_id, 0)

        self.frames = self.root.getOW(table_id, ow_id).frames.get_num()


class TreeViewModel(QtCore.QAbstractItemModel):
    """INPUTS: Node, OWM root, QObject"""

    def __init__(self, model_root, root, parent=None):
        super(TreeViewModel, self).__init__(parent)
        self._rootNode = model_root
        self.root = root

        for table in range(len(root.tables_list)):
            # add the table nodes
            newTableNode = TableNode(table, self._rootNode)

            for ow in range(len(root.tables_list[table].ow_data_ptrs)):
                # add the ow nodes
                OWNode(ow, newTableNode, self.root)

    def rowCount(self, parent=QtCore.QModelIndex()):
        """
        INPUTS: QModelIndex
        OUTPUT: int
        """
        if not parent.isValid():
            parentNode = self._rootNode
        else:
            parentNode = parent.internalPointer()

        return parentNode.childCount()

    def columnCount(self, parent):
        """
        INPUTS: QModelIndex
        OUTPUT: int
        """
        return 3

    def data(self, index, role):
        """
        INPUTS: QModelIndex, int
        OUTPUT: QVariant, strings are cast to QString which is a QVariant
        """
        if not index.isValid():
            return None

        node = index.internalPointer()

        if role == QtCore.Qt.DisplayRole or role == QtCore.Qt.EditRole:
            if index.column() == 0:
                return node.name + str(node.getId())
            elif index.column() == 2:
                if isinstance(node, OWNode):
                    return node.frames

                return None

        if role == QtCore.Qt.DecorationRole:
            if index.column() == 1:
                typeInfo = node.typeInfo()

                if typeInfo == "ow_node":
                    return QtGui.QIcon(
                        QtGui.QPixmap.fromImage(ImageQt(node.image)))

    def setData(self, index, value, role=QtCore.Qt.EditRole):
        """INPUTS: QModelIndex, QVariant, int (flag)"""
        if index.isValid():

            node = index.internalPointer()

            # For the OWs
            if node.typeInfo() == "ow_node":
                if value is not None:
                    node.setId(value)
                else:
                    node.setInfo()

            # For the Tables
            if node.typeInfo() == "table_node":
                node.setId(value)

            return True

        return False

    def headerData(self, section, orientation, role):
        """
        INPUTS: int, Qt::Orientation, int
        OUTPUT: QVariant, strings are cast to QString which is a QVariant
        """
        if role == QtCore.Qt.DisplayRole:
            if section == 0:
                return "OWs Structure"
            elif section == 1:
                return "Preview"
            elif section == 2:
                return "Frames"

    def flags(self, index):
        """
        INPUTS: QModelIndex
        OUTPUT: int (flag)
        """
        return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable

    def parent(self, index):
        """
        INPUTS: QModelIndex
        OUTPUT: QModelIndex
        Should return the parent of the node with the given QModelIndex
        """
        node = self.getNode(index)
        parentNode = node.parent()

        if parentNode == self._rootNode:
            return QtCore.QModelIndex()

        return self.createIndex(parentNode.row(), 0, parentNode)

    def index(self, row, column, parent):
        """
        INPUTS: int, int, QModelIndex
        OUTPUT: QModelIndex
        Should return a QModelIndex that corresponds to the given row,
        column and parent node
        """
        parentNode = self.getNode(parent)

        if row >= parentNode.childCount():
            return QtCore.QModelIndex()

        childItem = parentNode.child(row)

        if childItem:
            return self.createIndex(row, column, childItem)
        else:
            return QtCore.QModelIndex()

    def getNode(self, index):
        """
        CUSTOM
        INPUTS: QModelIndex
        """
        if index.isValid():
            node = index.internalPointer()
            if node:
                return node

        return self._rootNode

    def insertRows(self, position, rows, parent=QtCore.QModelIndex()):
        """INPUTS: int, int, QModelIndex"""
        parentNode = self.getNode(parent)

        self.beginInsertRows(parent, position, position + rows - 1)
        childCount = parentNode.childCount()

        for row in range(rows):

            if parentNode.typeInfo() == "table_node":
                # Adding OWs
                ow = OWNode(position + row, self.root)
                success = parentNode.insertChild(position + row, ow)
                # Re-init the node, so it loads the frame
                self.setData(self.index(row + position, 0, parent), None)
            if parentNode.typeInfo() == "NODE":
                # Create the Table Node on the rootNode
                TableNode(childCount, self._rootNode)
                success = True

        # Only for the OWs, increase the name Id by one,
        # in case an OW was INSERTED
        if parentNode.typeInfo() == "table_node":
            for row in range(position + rows, childCount + rows):
                self.setData(self.index(row, 0, parent), row)

        self.endInsertRows()

        return success

    def removeRows(self, position, rows, parent=QtCore.QModelIndex()):
        """INPUTS: int, int, QModelIndex"""
        success = True
        if rows == 0:
            return

        parentNode = self.getNode(parent)
        self.beginRemoveRows(parent, position, position + rows - 1)

        for row in range(rows):
            success = parentNode.removeChild(position)

            if parentNode.typeInfo() == "table_node":
                # remove OW
                self.root.getTable(parentNode.getId()).remove_ow(position)
            elif parentNode.typeInfo() == "NODE":
                self.root.remove_table(position)

        for row in range(position, parentNode.childCount()):
            self.setData(self.index(row, 0, parent), row)

        self.endRemoveRows()

        return success

    def resetModel(self):

        self._rootNode = Node("root")
        self.beginResetModel()

        self.removeRows(0, self.tablesCount())

        for table in range(self.root.tables_num()):
            # add the table nodes
            newTableNode = TableNode(table, self._rootNode)

            for ow in range(len(self.root.getTable(table).ow_data_ptrs)):
                # add the ow nodes
                newOWNode = OWNode(ow, self.root, newTableNode)

        self.endResetModel()

    # OW/Table interacting functionsqt
    def insertOWs(self, ow_id, table_id, rows, ow_type, num_of_frames):
        parent = self.index(table_id, 0, QtCore.QModelIndex())
        parentNode = self.getNode(parent)

        for ow in range(rows):
            if ow_id == -1:
                ow_id = parentNode.childCount()
                self.root.getTable(parentNode.getId()).add_ow(ow_type,
                                                              num_of_frames)
            else:
                self.root.getTable(parentNode.getId()).insert_ow(ow_id,
                                                                 ow_type,
                                                                 num_of_frames)

        self.insertRows(ow_id, rows, parent)

    def removeOWs(self, ow_id, table_id, rows, ui):
        tableNode = self.index(table_id, 0, QtCore.QModelIndex())
        self.removeRows(ow_id, rows, tableNode)

        # Manually reset the selected Item in the View, removeRows
        # removeRows deletes the currentIndex in the selectionModel,
        # so the next one becomes current
        if not self.owsCount(table_id):
            return

        if ow_id == self.owsCount(table_id):
            ow_id -= 1

        model = ui.OWTreeView.selectionModel()
        model.setCurrentIndex(self.index(ow_id, 0, tableNode),
                              QtCore.QItemSelectionModel.Current)
        ui.item_selected(self.index(ow_id, 0, tableNode))

    def resizeOW(self, ow_id, table_id, ow_type, num_of_frames, ui):
        self.root.getTable(table_id).resize_ow(ow_id, ow_type, num_of_frames)
        tableNode = self.index(table_id, 0, QtCore.QModelIndex())
        owNode = self.index(ow_id, 0, tableNode)
        self.setData(owNode, None)
        ui.item_selected(self.index(ow_id, 0, tableNode))

    def insertTable(self, ow_ptrs, data_ptrs, frames_ptrs, frames_addr, ui):
        self.root.custom_table_import(ow_ptrs,
                                      data_ptrs,
                                      frames_ptrs,
                                      frames_addr)
        self.insertRows(-1, 1)

        ui.selected_table = self.tablesCount() - 1
        if ui.selected_table == -1:
            ui.selected_table = None

    def removeTable(self, table_id, ui):
        quit_msg = "Are you sure you want to delete the entire table?"
        reply = QtWidgets.QMessageBox.question(ui,
                                               'Message',
                                               quit_msg,
                                               QtWidgets.QMessageBox.Yes,
                                               QtWidgets.QMessageBox.No)

        if reply == QtWidgets.QMessageBox.No:
            return

        ui.statusbar.showMessage("Removing Table...")
        self.removeRows(table_id, 1, QtCore.QModelIndex())
        ui.statusbar.showMessage("Ready")
        n = self.root.tables_num()

        if n == 0:
            ui.selected_table = None
        else:
            ui.selected_table = table_id - 1
        ui.selected_ow = None

        from ui.ui_updater import update_gui
        update_gui(ui)

    def tablesCount(self):
        return self.rowCount()

    def owsCount(self, table_id):
        tableNode = self.index(table_id, 0, QtCore.QModelIndex())
        return self.rowCount(tableNode)

    def importOWFrames(self, image_obj, ow_id, table_id, ui):
        # Check if it needs to repoint the palette table
        free_slots = ui.sprite_manager.get_free_slots()
        if free_slots == 0:
            ui.sprite_manager.repoint_palette_table()
            ui.rom_info.palette_table_addr = ui.sprite_manager.table_addr

        ui.sprite_manager.import_sprites(image_obj, table_id, ow_id)

        tableNode = self.index(table_id, 0, QtCore.QModelIndex())
        owNode = self.index(ow_id, 0, tableNode)
        self.setData(owNode, None)
        ui.item_selected(self.index(ow_id, 0, tableNode))

        # ui.initPaletteIdComboBox()
        ui.paletteIDComboBox.addItem(
            conv.capitalized_hex(ui.sprite_manager.used_palettes[-1]))

        from ui.ui_updater import update_palette_info
        update_palette_info(ui)

    def importPokeSpr(self, image_obj, ow_id, table_id, ui):

        free_slots = ui.sprite_manager.get_free_slots()
        if free_slots == 0:
            ui.sprite_manager.repoint_palette_table()
            ui.rom_info.palette_table_addr = ui.sprite_manager.table_addr

        ow_type = self.root.getOW(ui.selected_table, ow_id).frames.get_type()
        frames_num = self.root.getOW(ui.selected_table, ow_id).frames.get_num()

        log.info("OW Type: {} | Num of Frames: {}".format(ow_type, frames_num))
        if (ow_type != core.T32x32) or (frames_num != 9):
            log.info(
                "Need to repoint the OW before importing the pokemon data")
            self.root.getTable(ui.selected_table).resize_ow(ow_id,
                                                            core.T32x32,
                                                            9)
            ui.root.__init__()

        ui.sprite_manager.import_pokemon(image_obj, table_id, ow_id)

        tableNode = self.index(table_id, 0, QtCore.QModelIndex())
        owNode = self.index(ow_id, 0, tableNode)
        self.setData(owNode, None)
        ui.item_selected(self.index(ow_id, 0, tableNode))

        ui.paletteIDComboBox.addItem(
            conv.capitalized_hex(ui.sprite_manager.used_palettes[-1]))

        from ui.ui_updater import update_palette_info
        update_palette_info(ui)

    def importOWSpr(self, image_obj, ow_id, table_id, ui):

        free_slots = ui.sprite_manager.get_free_slots()
        if free_slots == 0:
            ui.sprite_manager.repoint_palette_table()
            ui.rom_info.palette_table_addr = ui.sprite_manager.table_addr

        ow_type = self.root.getOW(table_id, ow_id).frames.get_type()
        frames_num = self.root.getOW(table_id, ow_id).frames.get_num()

        if (ow_type != 2) or (frames_num != 9):
            self.root.getTable(table_id).resize_ow(ow_id, 2, 9)
            ui.root.__init__()

        ui.sprite_manager.import_ow(image_obj, table_id, ow_id)

        tableNode = self.index(table_id, 0, QtCore.QModelIndex())
        owNode = self.index(ow_id, 0, tableNode)
        self.setData(owNode, None)
        ui.item_selected(self.index(ow_id, 0, tableNode))

        ui.paletteIDComboBox.addItem(
            conv.capitalized_hex(ui.sprite_manager.used_palettes[-1]))

        from ui.ui_updater import update_palette_info
        update_palette_info(ui)

    def paletteCleanup(self, ui):

        ui.sprite_manager.palette_cleanup()
        ui.initPaletteIdComboBox()

        if ui.selected_ow is not None and ui.selected_table is not None:
            tableNode = self.index(ui.selected_table, 0, QtCore.QModelIndex())
            owNode = self.index(ui.selected_ow, 0, tableNode)
            self.setData(owNode, None)
            ui.item_selected(self.index(ui.selected_ow, 0, tableNode))

        from ui.ui_updater import update_gui
        update_gui(ui)

    def initOW(self, table_id, ow_id):
        parent = self.index(table_id, 0, QtCore.QModelIndex())
        ow = self.index(ow_id, 0, parent)
        self.setData(ow, None)
