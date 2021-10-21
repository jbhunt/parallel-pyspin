import time
import queue
import PySpin
import numpy as np
import multiprocessing as mp
from scipy.ndimage import gaussian_filter as gaussian

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
    },
    'STREAM_BUFFER_COUNT': {
        'minimum': 1,
        'maximum': 100,
        'initial': 10
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
        self.buffer = mp.JoinableQueue()
        self.started = mp.Value('i', 0)
        self.acquiring = mp.Value('i', 0)

        return

    def start(self):
        """Start acquisition"""
        self.started.value = 1
        super().start()
        return

    def run(self):
        """
        """

        while self.started.value:
            while self.acquiring.value:

                #
                t0 = time.time()

                # generate noise
                if self.color:
                    size = (self.height, self.width, 3)
                else:
                    size = (self.height, self.width)
                image = np.random.randint(low=0, high=255, size=size, dtype=np.uint8)

                # Wait for the appropriate inter-frame interval to lapse
                while time.time() - t0 < (1 / self.framerate):
                    continue

                # Queue image
                if self.buffer.qsize() == self.buffersize:
                    discard = self.buffer.get()
                    self.buffer.task_done()
                self.buffer.put(image)

        return

    def stop(self):
        """Stop acquisition and join the dummy acquisition process"""

        #
        if self.acquiring.value == 1:
            self.acquiring.value = 0

        # Exit from the main acquisition loop
        if self.started.value == 1:
            self.started.value = 0

        # Flush the image buffer
        while self.buffer.qsize() != 0:
            discard = self.buffer.get()
            self.buffer.task_done()

        #
        self.buffer.join()

        return

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
        """
        """

        # Despawn the process
        if self._p is not None:
            self._p.stop()
            self._p.join(timeout=3)
            if self._p.is_alive():
                self._p.terminate()
            self._p = None

        # Spawn a new process
        kwargs = {
            'buffersize': 10,
            'framerate' : self.AcquisitionFrameRate.GetValue(),
            'shape'     : (self.Height.GetValue(), self.Width.GetValue()),
            'color'     : True if self.PixelFormat.GetValue() == PySpin.PixelFormat_RGB8 else False
        }
        self._p = DummyAcquisitionProcess(**kwargs)
        self._p.start()

        #
        self._initialized = True

        return

    def DeInit(self):
        """
        """

        # Despawn the process
        if self._p is not None:
            self._p.stop()
            self._p.join(timeout=3)
            if self._p.is_alive():
                print('Ooops')
                self._p.terminate()
            self._p = None

        #
        self._initialized = False

        return

    def IsInitialized(self):
        return self._initialized

    def IsStreaming(self):
        return self._streaming

    def BeginAcquisition(self):
        """
        """

        if self._initialized is False:
            raise PySpin.SpinnakerException('Camera is not initialized')

        #
        self._p.acquiring.value = 1

        #
        self._streaming = True

        return

    def EndAcquisition(self):
        """
        """

        if self._initialized is False:
            raise PySpin.SpinnakerException('Camera is not initialized')

        #
        self._p.acquiring.value = 0

        #
        self._streaming = False

        return

    def GetNextImage(self, timeout=100):
        """
        Keywords
        --------
        timeout
            Timeout (in ms)
        """

        if self._streaming is False:
            raise PySpin.SpinnakerException('Camera is not streaming')

        #
        try:
            noise = self._p.buffer.get(timeout=timeout / 1000)
            self._p.buffer.task_done()

        except queue.Empty:
            raise PySpin.SpinnakerException('No buffered images available') from None

        pointer = PySpin.Image_Create(self.Width.GetValue(), self.Height.GetValue(), 0, 0, self.PixelFormat.GetValue(), noise)

        return pointer

    class TriggerMode(DummyProperty):
        def __init__(self, parent, min=None, max=None, val=PySpin.TriggerMode_Off):
            super().__init__(parent, min, max, val)

        def SetValue(self, val):
            super().SetValue()
            if val == PySpin.TriggerMode_On:
                if self.parent._initialized:
                    self.parent._p.acquiring.value = 0
                self.val = val
            elif val ==  PySpin.TriggerMode_Off:
                if self.parent._initialized:
                    self.parent._p.acquiring.value = 1
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
            if self.min <= val <= self.max and val in [1, 2, 4]:
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
