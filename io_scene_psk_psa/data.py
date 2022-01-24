from ctypes import *


class Vector3(Structure):
    _fields_ = [
        ('x', c_float),
        ('y', c_float),
        ('z', c_float),
    ]

    def __iter__(self):
        yield self.x
        yield self.y
        yield self.z

    def __repr__(self):
        return repr(tuple(self))


class Quaternion(Structure):
    _fields_ = [
        ('x', c_float),
        ('y', c_float),
        ('z', c_float),
        ('w', c_float),
    ]

    def __iter__(self):
        yield self.w
        yield self.x
        yield self.y
        yield self.z

    def __repr__(self):
        return repr(tuple(self))


class Section(Structure):
    _fields_ = [
        ('name', c_char * 20),
        ('type_flags', c_int32),
        ('data_size', c_int32),
        ('data_count', c_int32)
    ]

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.type_flags = 1999801