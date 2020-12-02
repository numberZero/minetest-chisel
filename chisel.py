#!/usr/bin/python3
"""
Minetest Chisel
Copyright (C) 2020 Vitaliy Lobachevskiy <numzer0@yandex.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as
published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import sys, os, os.path, traceback, time, types
if 'WAYLAND_DISPLAY' in os.environ:
	os.environ['PYOPENGL_PLATFORM'] = 'egl' # PyOpenGL такого не умеет, WTF?

from PySide2 import QtCore, QtWidgets, QtUiTools, QtGui
import OpenGL
from OpenGL.GL import *
from OpenGL.GL import shaders # не импортируется звёздочкой, т. к. это подмодуль
from math import *
from functools import partial
from copy import copy, deepcopy
import numpy as np
import random

app_dir = os.path.dirname(__file__)

def rand():
	while True:
		yield random.randrange(2)

class Part:
	indices = np.indices((16, 16, 16), dtype='int32').transpose().reshape((-1, 3)) # TODO произвольный размер

	def __init__(self, fill = 1):
		size = 16
		self.size = size
		self.data = np.full((size, size, size), fill, 'int32')
		#self._init_indices(size)

class GLPart(Part):
	index_buf = 0

	def __init__(self, *args, **kwargs):
		super(GLPart, self).__init__(*args, **kwargs)
		self.tex = 0

	@classmethod
	def _initGL_shared(cls):
		if cls.index_buf:
			return

	def initGL(self):
		self._initGL_shared()
		if self.tex:
			return
		self.tex = int(glGenTextures(1))
		glBindTexture(GL_TEXTURE_3D, self.tex) # создание 3D-текстуры
		glTexParameteri(GL_TEXTURE_3D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
		glTexParameteri(GL_TEXTURE_3D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
		glTexStorage3D(GL_TEXTURE_3D, 1, GL_R8I, 16, 16, 16)
		self.updateGL()

	def updateGL(self):
		glTextureSubImage3D(self.tex, 0, 0, 0, 0, 16, 16, 16, GL_RED_INTEGER, GL_INT, self.data)
		glTextureParameteriv(self.tex, GL_TEXTURE_BORDER_COLOR, (1, 2, 3, 4))

class Face:
	def __init__(self, u, v, w, name):
		self.u = u
		self.v = v
		self.w = w
		self.name = name

faces = [
	Face((1, 0, 0), (0, 1, 0), (0, 0, 1), "back"),
	Face((0, 0, 1), (1, 0, 0), (0, 1, 0), "top"),
	Face((0, 1, 0), (0, 0, 1), (1, 0, 0), "right"),
	Face((0, 1, 0), (1, 0, 0), (0, 0, -1), "front"),
	Face((1, 0, 0), (0, 0, 1), (0, -1, 0), "bottom"),
	Face((0, 0, 1), (0, 1, 0), (-1, 0, 0), "left"),
];

class Rotation:
	def __init__(self, yaw = 0.0, pitch = 0.0, roll = 0.0):
		self.yaw = yaw
		self.pitch = pitch
		self.roll = roll

	@property
	def matrix(self):
		yaw = self.yaw * (pi / 180.0)
		pitch = self.pitch * (pi / 180.0)
		roll = self.roll * (pi / 180.0)
		yc, ys = cos(yaw), sin(yaw)
		pc, ps = cos(pitch), sin(pitch)
		rc, rs = cos(roll), sin(roll)
		return \
			np.mat([[rc,-rs,0,0], [rs,rc,0,0], [0,0,1,0], [0,0,0,1]]) * \
			np.mat([[1,0,0,0], [0,pc,ps,0], [0,-ps,pc,0], [0,0,0,1]]) * \
			np.mat([[yc,0,-ys,0], [0,1,0,0], [ys,0,yc,0], [0,0,0,1]])

class ChiselView(QtWidgets.QOpenGLWidget):
	def __init__(self, *args, **kwargs):
		super(ChiselView, self).__init__(*args, **kwargs)
		self.rotate = Rotation()
		self.mouse = None
		self.scale = 1
		self.rotation_speed = 0
		self.setMouseTracking(True)

	def updateMouse(self, mouse = None):
		if not self.mouse:
			return
		try:
			h, w, _ = self.map.shape
			x, y = self.mouse
			key = tuple(self.map[h - y - 1, x])
		except IndexError:
			key = None
		mainWindow.hover(key)

	def updateFramebuffer(self):
		w = int(self.pw * self.scale)
		h = int(self.ph * self.scale)
		color, depth, id = glGenTextures(3)
		glBindTexture(GL_TEXTURE_2D, color)
		glBindTexture(GL_TEXTURE_2D, depth)
		glBindTexture(GL_TEXTURE_2D, id)
		glTextureStorage2D(color, 1, GL_RGBA8, w, h)
		glTextureStorage2D(depth, 1, GL_DEPTH_COMPONENT16, w, h)
		glTextureStorage2D(id, 1, GL_RGBA8UI, w, h)
		glTextureParameteri(id, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
		glTextureParameteri(id, GL_TEXTURE_MAG_FILTER, GL_NEAREST)

		glBindFramebuffer(GL_READ_FRAMEBUFFER, self.fb)
		glFramebufferTexture2D(GL_READ_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, color, 0)
		glFramebufferTexture2D(GL_READ_FRAMEBUFFER, GL_COLOR_ATTACHMENT1, GL_TEXTURE_2D, id, 0)
		glFramebufferTexture2D(GL_READ_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_TEXTURE_2D, depth, 0)

		glDeleteTextures(self.fbt)
		self.fbt = color, depth, id

	def startRotate(self, mouse_pos):
		self.mouse = None # это было для выделения
		self.user_rotation_start_pos = mouse_pos
		self.user_rotation_start_rotation = copy(self.rotate)

	def doRotate(self, mouse_pos):
		dx = mouse_pos.x() - self.user_rotation_start_pos.x()
		dy = mouse_pos.y() - self.user_rotation_start_pos.y()
		self.rotate.yaw = (self.user_rotation_start_rotation.yaw + self.rotation_speed * dx) % 360.0
		self.rotate.pitch = min(max(self.user_rotation_start_rotation.pitch + self.rotation_speed * dy, -90.0), 90.0)
		self.update()

	def stopRotate(self, mouse_pos):
		self.doRotate(mouse_pos)
		del self.user_rotation_start_pos
		del self.user_rotation_start_rotation

	def mouseMoveEvent(self, event: QtGui.QMouseEvent):
		if event.buttons() == 0:
			self.mouse = event.pos().x(), event.pos().y()
			self.updateMouse()
		elif event.buttons() == QtCore.Qt.MiddleButton:
			self.doRotate(event.pos())
		else:
			return super(ChiselView, self).mouseMoveEvent(event)

	def mousePressEvent(self, event: QtGui.QMouseEvent):
		if event.button() == QtCore.Qt.MiddleButton:
			self.startRotate(event.pos())
		elif event.button() == QtCore.Qt.LeftButton:
			mainWindow.dig()
			self.mouse = None
		else:
			self.mouse = None
			mainWindow.hover()
			return super(ChiselView, self).mousePressEvent(event)

	def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
		if event.button() == QtCore.Qt.MiddleButton:
			self.stopRotate(event.pos())
		if event.buttons() == 0:
			self.mouse = event.pos().x(), event.pos().y()
			self.updateMouse()
		return super(ChiselView, self).mouseReleaseEvent(event)

	def leaveEvent(self, event):
		super(ChiselView, self).leaveEvent(event)
		self.mouse = None
		mainWindow.hover()

	def initializeGL(self):
		mainWindow.initGL()
		with open(os.path.join(app_dir, 'part.vert.glsl'), 'rb') as text:
			vs = shaders.compileShader(text, GL_VERTEX_SHADER)
		with open(os.path.join(app_dir, 'part.geom.glsl'), 'rb') as text:
			gs = shaders.compileShader(text, GL_GEOMETRY_SHADER)
		with open(os.path.join(app_dir, 'part.frag.glsl'), 'rb') as text:
			fs = shaders.compileShader(text, GL_FRAGMENT_SHADER)
		self.shader = shaders.compileProgram(vs, gs, fs)
		self.fbt = []
		self.fb = glGenFramebuffers(1)

	def resizeGL(self, w, h):
		self.pw = w
		self.ph = h
		self.sw = w / min(w, h)
		self.sh = h / min(w, h)
		self.updateFramebuffer()

	def beforePaint(self):
		pass

	def paintGL(self):
		try:
			self.beforePaint()
			w = int(self.pw * self.scale)
			h = int(self.ph * self.scale)
			scale = 1.0
			m = np.diag([-1, 1, 1, 1])
			v = self.rotate.matrix
			p = np.diag((scale / self.sw, scale / self.sh, scale, 1.0))

			fb = glGetInteger(GL_DRAW_FRAMEBUFFER_BINDING)
			glBindFramebuffer(GL_FRAMEBUFFER, self.fb)
			glViewport(0, 0, w, h)

			glClearColor(0.0, 0.0, 0.0, 0.0)
			glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
			glEnable(GL_DEPTH_TEST)
			glEnable(GL_CULL_FACE)
			glEnable(GL_BLEND)
			glBlendFunc(GL_ONE, GL_ONE_MINUS_SRC_ALPHA)
			glDepthFunc(GL_LESS)
			glLineWidth(2.0)

			glMatrixMode(GL_PROJECTION)
			glLoadMatrixf((p * v).transpose())
			glMatrixMode(GL_MODELVIEW)
			glLoadMatrixf(m.transpose())

			glFramebufferTexture2D(GL_DRAW_FRAMEBUFFER, GL_COLOR_ATTACHMENT1, GL_TEXTURE_2D, 0, 0)
			glEnableClientState(GL_VERTEX_ARRAY)
			glEnableClientState(GL_COLOR_ARRAY)
			br, l = 0.8, 0.6
			glColorPointer(3, GL_FLOAT, 0, [(br, 0, 0), (br, 0, 0), (0, br, 0), (0, br, 0), (0, 0, br), (0, 0, br)])
			glVertexPointer(3, GL_FLOAT, 0, [(0, 0, 0), (l, 0, 0), (0, 0, 0), (0, l, 0), (0, 0, 0), (0, 0, l)])
			glDrawArrays(GL_LINES, 0, 6)
			glDisableClientState(GL_VERTEX_ARRAY)
			glDisableClientState(GL_COLOR_ARRAY)
			glFramebufferTexture2D(GL_DRAW_FRAMEBUFFER, GL_COLOR_ATTACHMENT1, GL_TEXTURE_2D, self.fbt[2], 0)
			#glDrawBuffers(2, [GL_NONE, GL_COLOR_ATTACHMENT1])
			glDrawBuffers(2, [GL_COLOR_ATTACHMENT0, GL_COLOR_ATTACHMENT1])
			glClearBufferiv(GL_COLOR, 1, mainWindow.dummy_key)

			glUseProgram(self.shader)

			glEnableVertexAttribArray(0)
			glUniformMatrix4fv(0, 1, True, p * v * m)
			glUniform1i(1, 0)
			glUniform4f(2, 0, 1, 0, 1)
			glVertexAttribIPointer(0, 3, GL_INT, 0, Part.indices)
			for part in mainWindow.parts:
				glBindTextureUnit(0, part.tex)
				glDrawArrays(GL_POINTS, 0, 16*16*16)

			glDrawBuffer(GL_COLOR_ATTACHMENT0)
			if mainWindow.hovered:
				glDepthFunc(GL_LEQUAL)
				glUniform4f(2, 1, 0, 0, 0.5)
				glBindTextureUnit(0, mainWindow.selection.tex)
				glDrawArrays(GL_POINTS, 0, 16*16*16)

			glDisableVertexAttribArray(0)
			glUseProgram(0)

			glBindFramebuffer(GL_DRAW_FRAMEBUFFER, fb)
			glReadBuffer(GL_COLOR_ATTACHMENT0)
			glBlitFramebuffer(0, 0, w, h, 0, 0, self.pw, self.ph, GL_COLOR_BUFFER_BIT, GL_LINEAR if self.scale > 1 else GL_NEAREST)

			img = np.ndarray((h, w, 4), 'uint8')
			glGetTextureImage(self.fbt[2], 0, GL_RGBA_INTEGER, GL_UNSIGNED_BYTE, img.size, img)
			self.map = img # FIXME scale
			glInvalidateFramebuffer(GL_READ_FRAMEBUFFER, 2, [GL_COLOR_ATTACHMENT0, GL_COLOR_ATTACHMENT1])
			self.updateMouse()

		except:
			traceback.print_exc()
			exit(1)

class WindowLoader(QtUiTools.QUiLoader):
	def __init__(self, root):
		super(WindowLoader, self).__init__()
		self.root = root

	def createWidget(self, className, parent, name):
		if not parent and self.root:
			return self.root
		return super(WindowLoader, self).createWidget(className, parent, name)

class ChiselWindow(QtWidgets.QMainWindow):
	view_names = ['Front', 'Top', 'Right', 'User']
	tool_names = ['1', 'U', 'V', 'W', 'X', 'Y', 'Z', 'UV', 'UW', 'VW', 'XY', 'XZ', 'YZ']
	dummy_key = (255, 255, 255, 255)

	def __init__(self):
		super(ChiselWindow, self).__init__()
		loader = WindowLoader(self)
		loader.registerCustomWidget(ChiselView)
		loader.load(os.path.join(app_dir, 'mainwindow.ui'))
		self.initialized = False
		self.parts = [GLPart(fill=1)]
		self.selection = GLPart(fill=0)
		self.hovered = None
		self.views = [getattr(self, f'view{name}') for name in self.view_names]
		self.tools = {}
		for name in self.tool_names:
			button = getattr(self, f'tool{name}')
			button.clicked.connect(partial(self.selectTool, name))
			self.tools[name] = button
		self.tool_name = self.tool_names[0]
		self.tools[self.tool_name].click()
		self.viewTop.rotate = Rotation(0.0, 90.0)
		self.viewFront.rotate = Rotation()
		self.viewRight.rotate = Rotation(90.0, 0.0)
		self.viewUser.rotate = Rotation(45.0, 30.0)
		self.viewUser.rotation_speed = 0.6

	def initGL(self):
		if self.initialized:
			return
		self.selection.initGL()
		for part in self.parts:
			part.initGL()
		self.initialized = True

	def selectTool(self, tool_name: str):
		self.tool_name = tool_name

	def update(self):
		super(ChiselWindow, self).update()
		for view in self.views:
			view.update()

	def hover(self, key = None):
		if key == self.dummy_key:
			key = None
		if key == self.hovered:
			return
		self.hovered = key
		self.selection.data.fill(0)
		if key is None:
			self.Hover.setText('none')
		else:
			x, y, z, p = key
			p, f = p & 0x1F, p >> 5
			face = faces[f]
			self.Hover.setText(f'{p}: ({x}, {y}, {z}) {face.name}')
			tool = self.tool_name
			if 'X' in tool:
				x = slice(None)
			if 'Y' in tool:
				y = slice(None)
			if 'Z' in tool:
				z = slice(None)
			if 'U' in tool:
				if face.u == (1, 0, 0):
					x = slice(None)
				elif face.u == (0, 1, 0):
					y = slice(None)
				else:
					z = slice(None)
			if 'V' in tool:
				if face.v == (1, 0, 0):
					x = slice(None)
				elif face.v == (0, 1, 0):
					y = slice(None)
				else:
					z = slice(None)
			if 'W' in tool:
				if face.w == (-1, 0, 0):
					x = slice(x, None)
				elif face.w == (0, -1, 0):
					y = slice(y, None)
				elif face.w == (0, 0, -1):
					z = slice(z, None)
				elif face.w == (1, 0, 0):
					x = slice(None, x + 1)
				elif face.w == (0, 1, 0):
					y = slice(None, y + 1)
				else:
					z = slice(None, z + 1)
			self.selection.data[z, y, x] = 1
		self.selection.updateGL()
		self.update()

	def dig(self):
		if not self.hovered:
			return
		x, y, z, p = self.hovered
		p, f = p & 0x1F, p >> 5
		part = self.parts[p]
		part.data *= 1 - self.selection.data
		part.updateGL()
		self.update()

	def place(self):
		pass

f = QtGui.QSurfaceFormat()
f.setRenderableType(f.OpenGL)
f.setVersion(4, 2)
#f.setSamples(4)
f.setOption(f.DeprecatedFunctions)
f.setOption(f.DebugContext)
f.setProfile(f.CompatibilityProfile)
QtGui.QSurfaceFormat.setDefaultFormat(f)

QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_ShareOpenGLContexts)
app = QtWidgets.QApplication(sys.argv)

mainWindow = ChiselWindow()

#angle = 45.0
#start_time = time.time()
#def rotateIt(self: ChiselView):
	#global angle
	#t = time.time() - start_time
	##angle = 45.0 + 60.0 * t
	#c = cos(angle * pi / 180.0)
	#s = sin(angle * pi / 180.0)
	#self.rotate = np.mat([[1,0,0,0], [0,0.866,0.500,0], [0,-0.500,0.866,0], [0,0,0,1]]) * np.mat([[c,0,-s,0], [0,1,0,0], [s,0,c,0], [0,0,0,1]])

#mainWindow.viewUser.beforePaint = types.MethodType(rotateIt, mainWindow.viewUser)

#timer = QtCore.QTimer(app)
#timer.timeout.connect(mainWindow.viewUser.update)
#timer.start()

mainWindow.show()

sys.exit(app.exec_())
