from src.model.Node import Node, PathManager
from PySide2.QtGui import QIcon
from PySide2.QtCore import Signal, QObject
from PySide2.QtWidgets import QMenu, QAction, QMessageBox, QInputDialog, QLineEdit, QFileDialog
from src.view.NewFileDialog import NewFileDialog
from src.model.AssemblyFileNode import AssemblyFileNode, AssemblyFileProxy
from src.model.CFileNode import CFileNode, CFileProxy
from src.model.FileNode import FileNode, FileProxy
import os
import re
import shutil


class ProjectProxy(object):

    def __init__(self):
        self.path = None
        self.files = []
        self.parent = None

    def addFile(self, proxy):
        self.files.append(proxy)

    def getProjectPath(self):
        return os.path.join(self.parent.path, self.path)

    def getProjectCompileCommand(self):
        destination = os.path.join(self.getProjectPath(), "{}.out".format(self.path))
        cFiles = []
        sFiles = []
        for file in self.files:
            if isinstance(file, CFileProxy):
                cFiles.append(file.getFilePath())
            elif isinstance(file, AssemblyFileProxy):
                sFiles.append(file.getFilePath())
        print(self.files)
        command = ['gcc', '-g', '-m32', '-o', destination]
        if cFiles:
            command.extend(cFiles)
        if sFiles:
            command.extend(sFiles)
        return ' '.join(command)

    def getProjectDebugCommand(self):
        return "ddd {}.out".format(os.path.join(self.getProjectPath(), self.path))

    def getProjectRunCommand(self):
        return "{}.out".format(os.path.join(self.getProjectPath(), self.path))

class ProjectNode(Node):

    def __init__(self):
        super(ProjectNode, self).__init__()
        self.eventManager = ProjectEventManager()
        self.menu = QMenu()
        self.menu.setStyleSheet("background-color: #3E3E42; color: white;")
        self.proxy = ProjectProxy()
        self.saveAction = QAction(QIcon(os.path.join(PathManager.START_DIRECTORY, "resources/save_folder.png")), "Save project")
        self.deleteAction = QAction(QIcon(os.path.join(PathManager.START_DIRECTORY, "resources/remove_folder.png")), "Remove project")
        self.eraseAction = QAction(QIcon(os.path.join(PathManager.START_DIRECTORY, "resources/delete_folder.png")), "Delete project from disk")
        self.renameAction = QAction(QIcon(os.path.join(PathManager.START_DIRECTORY, "resources/rename_folder.png")), "Rename project")
        self.compileAction = QAction(QIcon(os.path.join(PathManager.START_DIRECTORY, "resources/compile.png")), "Compile project")
        self.runAction = QAction(QIcon(os.path.join(PathManager.START_DIRECTORY, "resources/run.png")), "Run project")
        self.debugAction = QAction(QIcon(os.path.join(PathManager.START_DIRECTORY, "resources/debug.png")), "Debug project")
        self.newFileAction = QAction(QIcon(os.path.join(PathManager.START_DIRECTORY, "resources/new_file.png")), "New file")
        self.importFileAction = QAction(QIcon(os.path.join(PathManager.START_DIRECTORY, "resources/import_file.png")), "Import file")
        self.menu.addAction(self.saveAction)
        self.menu.addAction(self.compileAction)
        self.menu.addAction(self.debugAction)
        self.menu.addAction(self.runAction)
        self.menu.addSeparator()
        self.menu.addAction(self.newFileAction)
        self.menu.addAction(self.importFileAction)
        self.menu.addSeparator()
        self.menu.addAction(self.renameAction)
        self.menu.addAction(self.deleteAction)
        self.menu.addAction(self.eraseAction)

        self.connectActions()

    def getContextMenu(self) -> QMenu:
        return self.menu

    def __str__(self):
        return self.proxy.path

    def connectFileEventHandlers(self, file: FileNode):
        file.eventManager.fileRemoveRequsted.connect(self.removeFile)
        file.eventManager.fileRename.connect(lambda oldPath, fileProxy: self.eventManager.fileRename.emit(oldPath, fileProxy))
        file.eventManager.fileSave.connect(lambda fileProxy: self.eventManager.fileSave.emit(fileProxy))

    def connectActions(self):
        self.newFileAction.triggered.connect(self.createNewFile)
        self.importFileAction.triggered.connect(self.importFile)
        self.deleteAction.triggered.connect(self.deleteProject)
        self.renameAction.triggered.connect(self.renameProject)
        self.eraseAction.triggered.connect(lambda: self.eventManager.projectDeleteFromDiskRequested.emit(self))
        self.compileAction.triggered.connect(lambda: self.eventManager.projectCompileRequested.emit(self.proxy))
        self.debugAction.triggered.connect(lambda: self.eventManager.projectDebugRequested.emit(self.proxy))
        self.runAction.triggered.connect(lambda: self.eventManager.projectRunRequested.emit(self.proxy))

    def renameProject(self):
        name, entered = QInputDialog.getText(None, "Rename project", "Enter new workspace name: ", QLineEdit.Normal, self.path)
        if entered:
            parentDir = os.path.abspath(os.path.join(self.proxy.getProjectPath(), os.pardir))
            newPath = os.path.join(parentDir, name)
            print(newPath)
            regex = re.compile('[@!#$%^&*()<>?/\|}{~:]')
            if " " in name or regex.search(name):
                msg = QMessageBox()
                msg.setStyleSheet("background-color: #2D2D30; color: white;")
                msg.setModal(True)
                msg.setIcon(QMessageBox.Critical)
                msg.setText("Project name cannot contain whitespace or special characters.")
                msg.setWindowTitle("Project rename error")
                msg.exec_()
                return
            if os.path.exists(newPath):
                msg = QMessageBox()
                msg.setStyleSheet("background-color: #2D2D30; color: white;")
                msg.setModal(True)
                msg.setIcon(QMessageBox.Critical)
                msg.setText("Folder with the same name already exists.")
                msg.setWindowTitle("Project rename error")
                msg.exec_()
                return
            os.rename(self.path, newPath)
            oldPath = self.path
            self.proxy.path = self.path = os.path.basename(newPath)
            self.setText(0, self.path)
            self.parent().saveWorkspace()
            self.eventManager.projectRename.emit(oldPath, self)

    def removeFile(self, file: FileNode):
        answer = QMessageBox.question(None, "Delete file",
                                      "Are you sure you want to delete file {} from the disk?".format(file.proxy.path),
                                      QMessageBox.Yes | QMessageBox.No)
        if not answer == QMessageBox.Yes:
            return
        self.proxy.files.remove(file.proxy)
        os.remove(file.proxy.getFilePath())
        self.eventManager.fileRemove.emit(file.proxy)
        self.removeChild(file)
        self.parent().saveWorkspace()

    def importFile(self):
        name, entered = QFileDialog.getOpenFileName(None, "Select file to import", ".", "Assembly files (*.S);;C files (*.c)")
        if entered:
            fileName = os.path.basename(name)
            filePath = os.path.join(self.proxy.getProjectPath(), fileName)
            regex = re.compile('[@!#$%^&*()<>?/\|}{~:]')
            if " " in filePath or regex.search(fileName):
                msg = QMessageBox()
                msg.setStyleSheet("background-color: #2D2D30; color: white;")
                msg.setModal(True)
                msg.setIcon(QMessageBox.Critical)
                msg.setText("File name cannot contain whitespace or special characters.")
                msg.setWindowTitle("File import error")
                msg.exec_()
                return
            if os.path.exists(filePath):
                msg = QMessageBox()
                msg.setStyleSheet("background-color: #2D2D30; color: white;")
                msg.setModal(True)
                msg.setIcon(QMessageBox.Critical)
                msg.setText("File with the same name already exists.")
                msg.setWindowTitle("File import error")
                msg.exec_()
                return
            node = None
            if fileName[-1] == "S":
                node = AssemblyFileNode()
                node.setIcon(0, QIcon(os.path.join(PathManager.START_DIRECTORY, "resources/s.png")))
            else:
                node = CFileNode()
                node.setIcon(0, QIcon(os.path.join(PathManager.START_DIRECTORY, "resources/c.png")))
            node.setText(0, fileName)
            node.path = fileName
            if isinstance(node, AssemblyFileNode):
                node.proxy = AssemblyFileProxy()
            elif isinstance(node, CFileNode):
                node.proxy = CFileProxy()
            node.proxy.path = fileName
            node.proxy.parent = self.proxy
            self.addChild(node)
            os.mknod(filePath)
            self.proxy.addFile(node.proxy)
            self.connectFileEventHandlers(node)
            shutil.copyfile(name, filePath)
            # with open(filePath, 'w') as file:
            #     with open(name, 'r') as inputFile:
            #         file.write(inputFile.read())

    def createNewFile(self):
        dialog = NewFileDialog()
        dialog.exec_()
        if dialog.result:
            rootPath = os.path.join(self.parent().path, self.path, dialog.result)
            regex = re.compile('[@!#$%^&*()<>?/\|}{~:]')
            if " " in dialog.result or regex.search(dialog.result):
                msg = QMessageBox()
                msg.setStyleSheet("background-color: #2D2D30; color: white;")
                msg.setModal(True)
                msg.setIcon(QMessageBox.Critical)
                msg.setText("File name cannot contain whitespace or special characters.")
                msg.setWindowTitle("File creation error")
                msg.exec_()
                return
            if os.path.exists(rootPath):
                msg = QMessageBox()
                msg.setStyleSheet("background-color: #2D2D30; color: white;")
                msg.setModal(True)
                msg.setIcon(QMessageBox.Critical)
                msg.setText("File with the same name already exists.")
                msg.setWindowTitle("File creation error")
                msg.exec_()
                return
            node = None
            if dialog.result[-1] == "S":
                node = AssemblyFileNode()
                node.setIcon(0, QIcon(os.path.join(PathManager.START_DIRECTORY, "resources/s.png")))
            else:
                node = CFileNode()
                node.setIcon(0, QIcon(os.path.join(PathManager.START_DIRECTORY, "resources/c.png")))
            node.setText(0, dialog.result)
            node.path = dialog.result
            if isinstance(node, AssemblyFileNode):
                node.proxy = AssemblyFileProxy()
            elif isinstance(node, CFileNode):
                node.proxy = CFileProxy()
            node.proxy.path = dialog.result
            node.proxy.parent = self.proxy
            self.addChild(node)
            os.mknod(rootPath)
            self.proxy.addFile(node.proxy)
            self.connectFileEventHandlers(node)


    def deleteProject(self):
        self.eventManager.projectRemoveRequested.emit(self)

    def loadProject(self, sourcePath=None):
        for proxy in self.proxy.files:
            file = None
            if isinstance(proxy, AssemblyFileProxy):
                file = AssemblyFileNode()
                file.setIcon(0, QIcon(os.path.join(PathManager.START_DIRECTORY, "resources/s.png")))
            elif isinstance(proxy, CFileProxy):
                file = CFileNode()
                file.setIcon(0, QIcon(os.path.join(PathManager.START_DIRECTORY, "resources/c.png")))
            if file:
                proxy.parent = self.proxy
                file.setText(0, proxy.path)
                file.path = proxy.path
                file.proxy = proxy
                self.addChild(file)
                self.connectFileEventHandlers(file)
        projectPath = self.proxy.getProjectPath() if not sourcePath else sourcePath
        for filePath in os.listdir(projectPath):
            if filePath not in [file.path for file in self.proxy.files]:
                node = None
                proxy = None
                if filePath.lower().endswith(".s"):
                    node = AssemblyFileNode()
                    node.setIcon(0, QIcon(os.path.join(PathManager.START_DIRECTORY, "resources/s.png")))
                    proxy = AssemblyFileProxy()
                elif filePath.lower().endswith(".c"):
                    node = CFileNode()
                    node.setIcon(0, QIcon(os.path.join(PathManager.START_DIRECTORY, "resources/c.png")))
                    proxy = CFileProxy()
                if node:
                    proxy.path = filePath
                    node.setText(0, filePath)
                    node.path = filePath
                    node.proxy = proxy
                    node.proxy.parent = self.proxy
                    self.addChild(node)
                    self.proxy.files.append(node.proxy)
                    self.connectFileEventHandlers(node)
                    if sourcePath:
                        shutil.copyfile(os.path.join(sourcePath, filePath), os.path.join(self.proxy.getProjectPath(), filePath))

class ProjectEventManager(QObject):

    projectCompileRequested = Signal(ProjectProxy)
    projectDebugRequested = Signal(ProjectProxy)
    projectRunRequested = Signal(ProjectProxy)
    projectRemoveRequested = Signal(ProjectNode)
    projectDeleteFromDiskRequested = Signal(ProjectNode)
    projectRename = Signal(str, ProjectNode)
    fileRemove = Signal(FileProxy)
    fileRename = Signal(str, FileProxy)
    fileSave = Signal(FileProxy)

    def __init__(self):
        super(ProjectEventManager, self).__init__()


