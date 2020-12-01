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
import numpy as np
import random

def rand():
	while True:
		yield random.randrange(2)

class Part:
	indices = np.indices((16, 16, 16), dtype='int32').transpose().reshape((-1, 3))

	def __init__(self):
		self.data = np.full((16, 16, 16), 1, 'int32')
		#self.data = np.fromiter(rand(), 'int32', 16*16*16).reshape(16, 16, 16)

class GLPart(Part):
	index_buf = 0

	def __init__(self):
		super(GLPart, self).__init__()
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

part = GLPart()
sel = None

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

class ChiselView(QtWidgets.QOpenGLWidget):
	def __init__(self, *args, **kwargs):
		super(ChiselView, self).__init__(*args, **kwargs)
		self.rotate = np.identity(4)
		self.mouse = None
		self.scale = 1
		self.setMouseTracking(True)

	def updateMouse(self):
		global sel
		if not self.mouse:
			return
		try:
			x, y, z, p = self.img[self.img.shape[0] - self.mouse[1] - 1, self.mouse[0]]
		except IndexError:
			p = 255
		if p == 255:
			sel = None
			mainWindow.hover.setText('none')
			return
		p, f = p & 0x1F, p >> 5
		nsel = (p, x, y, z, f)
		if nsel != sel:
			sel = nsel
			facename = faces[f].name
			mainWindow.hover.setText(f'{p}: ({x}, {y}, {z}) {facename}')
			updateViews()

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

	def mouseMoveEvent(self, event):
		super(ChiselView, self).mouseMoveEvent(event)
		if event.buttons():
			return
		self.mouse = event.pos().x(), event.pos().y()
		self.updateMouse()

	def mousePressEvent(self, event):
		global sel, part
		if event.button() != QtCore.Qt.LeftButton:
			return super(ChiselView, self).mousePressEvent(event)
		if not sel:
			return
		self.mouse = None
		p, x, y, z, f = sel
		part.data[z, y, x] = 0
		part.updateGL()
		updateViews()

	def mouseReleaseEvent(self, event):
		global sel
		if event.button() != QtCore.Qt.LeftButton:
			return super(ChiselView, self).mouseReleaseEvent(event)
		self.mouse = event.pos().x(), event.pos().y()
		self.updateMouse()

	def leaveEvent(self, event):
		super(ChiselView, self).leaveEvent(event)
		self.mouse = None
		mainWindow.hover.setText('none')

	def initializeGL(self):
		with open('part.vert.glsl', 'rb') as text:
			vs = shaders.compileShader(text, GL_VERTEX_SHADER)
		with open('part.geom.glsl', 'rb') as text:
			gs = shaders.compileShader(text, GL_GEOMETRY_SHADER)
		with open('part.frag.glsl', 'rb') as text:
			fs = shaders.compileShader(text, GL_FRAGMENT_SHADER)
		self.shader = shaders.compileProgram(vs, gs, fs)
		self.fbt = []
		self.fb = glGenFramebuffers(1)
		part.initGL()

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
			v = self.rotate
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
			glClearBufferiv(GL_COLOR, 1, (255, 255, 255, 255))

			glUseProgram(self.shader)
			glBindTextureUnit(0, part.tex)

			glEnableVertexAttribArray(0)
			glUniformMatrix4fv(0, 1, True, p * v * m)
			glUniform1i(1, 0)
			glUniform4f(2, 0, 1, 0, 1)
			glVertexAttribIPointer(0, 3, GL_INT, 0, Part.indices)
			glDrawArrays(GL_POINTS, 0, 16*16*16)
			glDisableVertexAttribArray(0)

			glDrawBuffer(GL_COLOR_ATTACHMENT0)
			if sel:
				glDepthFunc(GL_LEQUAL)
				glUniform4f(2, 1, 0, 0, 0.5)
				glVertexAttribI3i(0, *sel[1:4])
				glDrawArrays(GL_POINTS, 0, 1)
			glUseProgram(0)

			glBindFramebuffer(GL_DRAW_FRAMEBUFFER, fb)
			glReadBuffer(GL_COLOR_ATTACHMENT0)
			glBlitFramebuffer(0, 0, w, h, 0, 0, self.pw, self.ph, GL_COLOR_BUFFER_BIT, GL_LINEAR if self.scale > 1 else GL_NEAREST)

			img = np.ndarray((h, w, 4), 'uint8')
			glGetTextureImage(self.fbt[2], 0, GL_RGBA_INTEGER, GL_UNSIGNED_BYTE, img.size, img)
			self.img = img # FIXME scale
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
	def __init__(self):
		super(ChiselWindow, self).__init__()
		loader = WindowLoader(self)
		loader.registerCustomWidget(ChiselView)
		loader.load('mainwindow.ui')

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

def updateViews():
	mainWindow.viewTop.update()
	mainWindow.viewRight.update()
	mainWindow.viewFront.update()
	mainWindow.viewUser.update()

mainWindow.viewTop.rotate = np.mat([[1,0,0,0], [0,0,1,0], [0,-1,0,0], [0,0,0,1]])
mainWindow.viewFront.rotate = np.mat([[1,0,0,0], [0,1,0,0], [0,0,1,0], [0,0,0,1]])
mainWindow.viewRight.rotate = np.mat([[0,0,-1,0], [0,1,0,0], [1,0,0,0], [0,0,0,1]])
mainWindow.viewUser.rotate = np.mat([[1,0,0,0], [0,0.866,0.500,0], [0,-0.500,0.866,0], [0,0,0,1]]) * np.mat([[0.707,0,-0.707,0], [0,1,0,0], [0.707,0,0.707,0], [0,0,0,1]])

angle = 45.0
start_time = time.time()
def rotateIt(self: ChiselView):
	global angle
	t = time.time() - start_time
	#angle = 45.0 + 60.0 * t
	c = cos(angle * pi / 180.0)
	s = sin(angle * pi / 180.0)
	self.rotate = np.mat([[1,0,0,0], [0,0.866,0.500,0], [0,-0.500,0.866,0], [0,0,0,1]]) * np.mat([[c,0,-s,0], [0,1,0,0], [s,0,c,0], [0,0,0,1]])

#mainWindow.viewUser.beforePaint = types.MethodType(rotateIt, mainWindow.viewUser)

#timer = QtCore.QTimer(app)
#timer.timeout.connect(mainWindow.viewUser.update)
#timer.start()

mainWindow.show()

sys.exit(app.exec_())
