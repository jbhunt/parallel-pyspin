import time
import queue
import PySpin
import numpy as np
import multiprocessing as mp

_PROPERTIES = {
    'FRAMERATE': {
        'minimum': 1,
        'maximum': 200,
        'initial': 30
    },
    'BINSIZE': {
        'initial': (2, 2)
    },
    'WIDTH': {
        'initial': 1440
    },
    'HEIGHT': {
        'initial': 1080
    },
    'OFFSET': {
        'initial': (0, 0)
    },
    'EXPOSURE': {
        'minimum': 1,
        'maximum': 999999,
        'initial': 3000
    }
}

class DummyProperty():
    """
    Mimics the properties of an actual camera pointer object
    """

    def __init__(self, parent, min, max, val):
        self.parent = parent
        self.min = min
        self.max = max
        self.val = val
        return

    def GetValue(self):
        return self.val

    def GetMax(self):
        return self.max

    def GetMin(self):
        return self.min

    def SetValue(self):
        if self.parent._initialized is False:
            raise PySpin.SpinnakerException('Camera is not initialized')

    def GetAccessMode(self):
        return PySpin.RW

class DummyAcquisitionProcess(mp.Process):
    """
    Mimics image acquisition and buffering
    """

    def __init__(self, buffersize=10, framerate=30, shape=(1280, 1440), color=False):
        """
        """

        super().__init__()

        self.framerate = framerate
        self.buffersize = buffersize
        self.width, self.height = shape
        self.color = color
        self.buffer = mp.Queue()
        self.started = mp.Value('i', 0)
        self.paused = mp.Value('i', 0)

        return

    def start(self):
        """Start acquisition"""
        self.started.value = 1
        super().start()
        return

    def run(self):
        while self.started.value:
            t0 = time.time()
            if self.color:
                size = (self.height, self.width, 3)
            else:
                size = (self.height, self.width)
            image = np.random.randint(low=0, high=255, size=size, dtype=np.uint8)
            while time.time() - t0 < (1 / self.framerate):
                continue
            if self.buffer.qsize() < self.buffersize:
                self.buffer.put(image)
            while self.paused.value:
                continue

        return

    def pause(self):
        """Pause acquisition"""
        self.paused.value = 1

    def unpause(self):
        """Unpause acquisition"""
        self.paused.value = 0

    def stop(self):
        """Stop acquisition"""
        self.started.value = 0

    def join(self, timeout=1):
        """Join the process"""

        # exit from the main loop
        if self.started.value:
            self.started.value = 0

        # unpause if paused
        if self.paused.value:
            self.paused.value = 0

        # empty out the buffer
        while self.buffer.qsize() != 0:
            self.buffer.get()

        # join
        super().join(timeout)

class DummyCameraPointer():
    """
    Mimics the camera pointer object (and some of its methods)
    """

    def __init__(self):
        """
        """

        self.Width = self.Width(self, val=_PROPERTIES['WIDTH']['initial'])
        self.Height = self.Height(self, val=_PROPERTIES['HEIGHT']['initial'])
        self.OffsetX = self.OffsetX(self, val=_PROPERTIES['OFFSET']['initial'][0])
        self.OffsetY = self.OffsetY(self, val=_PROPERTIES['OFFSET']['initial'][1])
        self.BinningVertical = self.BinningVertical(self, val=_PROPERTIES['OFFSET']['initial'][1])
        self.BinningHorizontal = self.BinningHorizontal(self, val=_PROPERTIES['OFFSET']['initial'][0])
        self.PixelFormat = self.PixelFormat(self)
        self.AcquisitionFrameRateEnable = self.AcquisitionFrameRateEnable(self)
        self.AcquisitionFrameRate = self.AcquisitionFrameRate(
            self,
            min=_PROPERTIES['FRAMERATE']['minimum'],
            max=_PROPERTIES['FRAMERATE']['maximum'],
            val=_PROPERTIES['FRAMERATE']['initial']
        )
        self.AcquisitionMode = self.AcquisitionMode(self)
        self.ExposureAuto = self.ExposureAuto(self)
        self.ExposureTime = self.ExposureTime(
            self,
            min=_PROPERTIES['EXPOSURE']['minimum'],
            max=_PROPERTIES['EXPOSURE']['maximum'],
            val=_PROPERTIES['EXPOSURE']['initial']
        )
        self.TLStream = self.TLStream(self)
        self.LineSelector = self.LineSelector(self)
        self.LineSource = self.LineSource(self)
        self.V3_3Enable = self.V3_3Enable(self)
        self.TriggerMode = self.TriggerMode(self)
        self.TriggerSource = self.TriggerSource(self)
        self.TriggerOverlap = self.TriggerOverlap(self)
        self.TriggerActivation = self.TriggerActivation(self)

        # private attributes
        self._initialized = False
        self._streaming = False
        self._p = None

        return

    def IsValid(self):
        return True

    def Init(self):
        self._initialized = True
        return

    def DeInit(self):
        self._initialized = False
        return

    def IsInitialized(self):
        return self._initialized

    def IsStreaming(self):
        return self._streaming

    def BeginAcquisition(self):
        if self._initialized is False:
            raise PySpin.SpinnakerException('Camera is not initialized')
        else:
            if self._p is not None:
                self._p.join()
                self._p = None
            framerate = self.AcquisitionFrameRate.GetValue()
            shape = (self.Width.GetValue(), self.Height.GetValue())
            buffersize = self.TLStream.StreamBufferCountManual.GetValue()
            if self.PixelFormat.GetValue() == PySpin.PixelFormat_Mono8:
                color = False
            else:
                color = True
            self._p = DummyAcquisitionProcess(buffersize, framerate, shape, color)
            self._p.start()
            self._streaming = True

    def EndAcquisition(self):
        if self._initialized is False:
            raise PySpin.SpinnakerException('Camera is not initialized')
        else:
            if self._p is not None:
                self._p.join()
                self._p = None
            self._streaming = False

    def GetNextImage(self, timeout=100):
        """
        Returns a PySpin.ImagePtr object created from a random numpy array
        """

        if self._streaming is False:
            raise PySpin.SpinnakerException('Camera is not streaming')

        try:
            image = self._p.buffer.get(timeout=timeout / 1000000)
            pointer = PySpin.Image_Create(self.Width.GetValue(), self.Height.GetValue(), 0, 0, self.PixelFormat.GetValue(), image)
            return pointer
        except queue.Empty:
            raise PySpin.SpinnakerException('Image queury timed out') from None

    class TriggerMode(DummyProperty):
        def __init__(self, parent, min=None, max=None, val=PySpin.TriggerMode_Off):
            super().__init__(parent, min, max, val)

        def SetValue(self, val):
            super().SetValue()
            if val == PySpin.TriggerMode_On:
                if self.parent._streaming:
                  self.parent._p.pause()
                self.val = val
            elif val ==  PySpin.TriggerMode_Off:
                if self.parent._streaming:
                    self.parent._p.unpause()
                self.val = val
            else:
                raise PySpin.SpinnakerException(f'{val} is an invalid value')
            return

    class Width(DummyProperty):

        def __init__(self, parent, min=1, max=1440, val=1440):
            super().__init__(parent, min, max, val)
            self._ceiling = max

        def SetValue(self, val):
            super().SetValue()
            if val < self.min:
                raise PySpin.SpinnakerException(f'{val} is too small')
            elif val > self.max:
                raise PySpin.SpinnakerException(f'{val} is too big')
            else:
                self.val = val
            return

    class Height(DummyProperty):

        def __init__(self, parent, min=1, max=1080, val=1440):
            super().__init__(parent, min, max, val)
            self._ceiling = max

        def SetValue(self, val):
            super().SetValue()
            if val < self.min:
                raise PySpin.SpinnakerException(f'{val} is too small')
            elif val > self.max:
                raise PySpin.SpinnakerException(f'{val} is too big')
            else:
                self.val = val
            return

    class OffsetX(DummyProperty):

        def __init__(self, parent, min=0, max=None, val=0):
            super().__init__(parent, min, max, val)
            self.max = self.parent.Width.GetMax() - 1
            return

        def SetValue(self, val):
            super().SetValue()
            if val < self.min:
                raise PySpin.SpinnakerException(f'{val} is too small')
            elif val > self.max:
                raise PySpin.SpinnakerException(f'{val} is too big')
            else:
                self.val = val
            return

    class OffsetY(DummyProperty):

        def __init__(self, parent, min=0, max=None, val=0):
            super().__init__(parent, min, max, val)
            self.max = self.parent.Height.GetMax() - 1
            return

        def SetValue(self, val):
            super().SetValue()
            if val < self.min:
                raise PySpin.SpinnakerException(f'{val} is too small')
            elif val > self.max:
                raise PySpin.SpinnakerException(f'{val} is too big')
            else:
                self.val = val
            return

    class BinningVertical(DummyProperty):

        def __init__(self, parent, min=1, max=4, val=1):
            super().__init__(parent, min, max, val)

        def SetValue(self, val):
            super().SetValue()
            if self.min <= val <= self.max and val in [1, 2, 4]:
                self.val = val
                height = int(self.parent.Height._ceiling / val)
                self.parent.Height.max = height
                self.parent.Height.SetValue(height)
                self.parent.OffsetY.max = self.parent.Height.GetMax() - 1
            else:
                raise PySpin.SpinnakerException(f'{val} is an invalid value')

    class BinningHorizontal(DummyProperty):

        def __init__(self, parent, min=1, max=4, val=1):
            super().__init__(parent, min, max, val)

        def SetValue(self, val):
            super().SetValue()
            if self.min <= val <= self.max and val in [1, 2, 3]:
                self.val = val
                width = int(self.parent.Width._ceiling / val)
                self.parent.Width.max = width
                self.parent.Width.SetValue(width)
                self.parent.OffsetX.max = self.parent.Width.GetMax() - 1
            else:
                raise PySpin.SpinnakerException(f'{val} is an invalid value')

    class AcquisitionFrameRateEnable(DummyProperty):

        def __init__(self, parent, min=None, max=None, val=False):
            super().__init__(parent, min, max, val)

        def SetValue(self, val):
            super().SetValue()
            if val is True:
                self.val = val
            elif val is False:
                self.val = val
            else:
                raise PySpin.SpinnakerException(f'{val} is not a valid value')

    class AcquisitionFrameRate(DummyProperty):

        def __init__(self, parent, min=1, max=200, val=30):
            super().__init__(parent, min, max, val)

        def SetValue(self, val):
            super().SetValue()
            if self.parent.AcquisitionFrameRateEnable.GetValue() is False:
                raise PySpin.SpinnakerException('Framerate is not enabled')
            if self.min <= val <= self.max:
                self.val = val
                maximum_exposure = 1 / val * 1000000 - 1
                if self.parent.ExposureTime.GetValue() > maximum_exposure:
                    self.parent.ExposureTime.max = maximum_exposure
                    self.parent.ExposureTime.val = maximum_exposure
            else:
                raise PySpin.SpinnakerException(f'{val} is not a valid value')

    class PixelFormat(DummyProperty):

        def __init__(self, parent, min=None, max=None, val=PySpin.PixelFormat_Mono8):
            super().__init__(parent, min, max, val)

        def SetValue(self, val):
            super().SetValue()
            if val not in [PySpin.PixelFormat_Mono8, PySpin.PixelFormat_RGB8]:
                raise PySpin.SpinnakerException(f'{val} is not a valid pixel format')
            else:
                self.val = val

    class ExposureAuto(DummyProperty):

        def __init__(self, parent, min=None, max=None, val=PySpin.ExposureAuto_Once):
            super().__init__(parent, min, max, val)

        def SetValue(self, val):
            super().SetValue()
            if val not in [PySpin.ExposureAuto_Continuous, PySpin.ExposureAuto_Once, PySpin.ExposureAuto_Off]:
                raise PySpin.SpinnakerException(f'{val} is not a valid value')
            else:
                self.val = val

    class ExposureTime(DummyProperty):

        def __init__(self, parent, min=100, max=None, val=3000):
            super().__init__(parent, min, max, val)
            self.max = 1 / self.parent.AcquisitionFrameRate.GetValue() * 1000000 - 1

        def SetValue(self, val):
            super().SetValue()
            if self.min <= val <= self.max:
                self.val = val
            else:
                raise PySpin.SpinnakerException(f'{val} is not a valid value')

    class AcquisitionMode(DummyProperty):

        def __init__(self, parent, min=None, max=None, val=PySpin.AcquisitionMode_SingleFrame):
            super().__init__(parent, min, max, val)

        def SetValue(self, val):
            super().SetValue()
            if val not in [PySpin.AcquisitionMode_Continuous, PySpin.AcquisitionMode_SingleFrame, PySpin.AcquisitionMode_MultiFrame]:
                raise PySpin.SpinnakerException(f'{val} is not a valid value')
            else:
                self.val = val

    class TLStream():

        def __init__(self, parent):
            self.StreamBufferHandlingMode = self.StreamBufferHandlingMode(parent)
            self.StreamBufferCountMode = self.StreamBufferCountMode(parent)
            self.StreamBufferCountManual = self.StreamBufferCountManual(parent)
            return

        class StreamBufferHandlingMode(DummyProperty):

            def __init__(self, parent, min=None, max=None, val=PySpin.StreamBufferHandlingMode_OldestFirst):
                super().__init__(parent, min, max, val)

            def SetValue(self, val):
                super().SetValue()
                if val not in [
                    PySpin.StreamBufferHandlingMode_NewestOnly,
                    PySpin.StreamBufferHandlingMode_OldestFirst,
                    PySpin.StreamBufferHandlingMode_NewestFirst,
                    PySpin.StreamBufferHandlingMode_NewestFirstOverwrite,
                    PySpin.StreamBufferHandlingMode_OldestFirstOverwrite,
                ]:
                    raise PySpin.SpinnakerException(f'{val} is not a valid value')
                else:
                    self.val = val

        class StreamBufferCountMode(DummyProperty):

            def __init__(self, parent, min=None, max=None, val=PySpin.StreamBufferCountMode_Auto):
                super().__init__(parent, min, max, val)

            def SetValue(self, val):
                super().SetValue()
                if val not in [
                    PySpin.StreamBufferCountMode_Auto, PySpin.StreamBufferCountMode_Manual
                ]:
                    raise PySpin.SpinnakerException(f'{val} is not a valid value')
                else:
                    self.val = val

        class StreamBufferCountManual(DummyProperty):

            def __init__(self, parent, min=1, max=1000, val=10):
                super().__init__(parent, min, max, val)

            def SetValue(self, val):
                super().SetValue()
                if self.min <= val <= self.max:
                    self.val = val
                else:
                    raise PySpin.SpinnakerException(f'{val} is not a valid value')

    class LineSelector(DummyProperty):
        def __init__(self, parent, min=None, max=None, val=PySpin.LineSelector_Line1):
            super().__init__(parent, min, max, val)

        def SetValue(self, val):
            super().SetValue()
            return

    class LineSource(DummyProperty):
        def __init__(self, parent, min=None, max=None, val=PySpin.LineSource_ExposureActive):
            super().__init__(parent, min, max, val)

        def SetValue(self, val):
            super().SetValue()
            return

    class V3_3Enable(DummyProperty):
        def __init__(self, parent, min=None, max=None, val=False):
            super().__init__(parent, min, max, val)

        def SetValue(self, val):
            super().SetValue()
            if val in [True, False]:
                self.val = val
            else:
                raise PySpin.SpinnakerException(f'{val} is an invalid value')
            return

    class TriggerSource(DummyProperty):
        def __init__(self, parent, min=None, max=None, val=PySpin.TriggerSource_Line3):
            super().__init__(parent, min, max, val)

        def SetValue(self, val):
            super().SetValue()
            if val in (
                PySpin.TriggerSource_Line0, PySpin.TriggerSource_Line1,
                PySpin.TriggerSource_Line2, PySpin.TriggerSource_Line3
            ):
                self.val = val
            else:
                raise PySpin.SpinnakerException(f'{val} is not a valid value')

            return

    class TriggerOverlap(DummyProperty):
        def __init__(self, parent, min=None, max=None, val=PySpin.TriggerOverlap_ReadOut):
            super().__init__(parent, min, max, val)

        def SetValue(self, val):
            super().SetValue()
            if val in (
                PySpin.TriggerOverlap_Off,
                PySpin.TriggerOverlap_ReadOut,
                PySpin.TriggerOverlap_PreviousFrame
            ):
                self.val = val
            else:
                raise PySpin.SpinnakerException(f'{val} is not a valid value')
            return

    class TriggerActivation(DummyProperty):
        def __init__(self, parent, min=None, max=None, val=PySpin.TriggerActivation_RisingEdge):
            super().__init__(parent, min, max, val)

        def SetValue(self, val):
            super().SetValue()
            if val in (
                PySpin.TriggerActivation_AnyEdge,
                PySpin.TriggerActivation_LevelHigh,
                PySpin.TriggerActivation_LevelLow,
                PySpin.TriggerActivation_FallingEdge,
                PySpin.TriggerActivation_RisingEdge,
            ):
                self.val = val
            else:
                raise PySpin.SpinnakerException(f'{val} is not a valid value')
            return
