import dill
import types
import queue
import PySpin
import numpy as np
import multiprocessing as mp
from .dummy import DummyCameraPointer

def queued(f):
    """
    This decorator sends functions through the input queue and retrieves the
    result of the function call from the output queue
    """

    def wrapped(obj, error_message='Undefined error', **kwargs):
        """
        Keywords
        --------
        obj : MainProcess
            An instance of the MainProcess class
        error_message : str
            An error message that will be displayed if the function call fails
        """

        item = (dill.dumps(f), kwargs)
        obj._child.iq.put(item)
        result, output = obj._child.oq.get()
        if not result:
            raise CameraError(error_message)
        else:
            return result, output

    return wrapped

class CameraError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)

class ChildProcess(mp.Process):
    """
    """

    def __init__(self, device: int=0) -> None:
        """
        """

        super().__init__()

        self._device   = device
        self._nickname = f'Camera[{device}]'

        # io queues
        self.iq = mp.Queue()
        self.oq = mp.Queue()

        #
        self.started   = mp.Value('i', 0)
        self.acquiring = mp.Value('i', 0)

        return

    def start(self) -> None:
        """
        override the start method
        """

        self.started.value = 1

        super().start()

        return

    def join(self, timeout: float=5.0) -> None:
        """
        override the join method
        """

        self.started.value = 0

        super().join(timeout)

        return

    def run(self) -> None:
        """
        """

        try:

            # create instances of the system and cameras list
            system = PySpin.System.GetInstance()
            cameras = system.GetCameras()

            # return if no cameras detected
            # if len(cameras) == 0:
            #     result = False
            #     self.oq.put(result)
            #     return

            # loop through available cameras
            for camera in cameras:
                pass

            # instantiate the camera
            if type(self._device) == int:
                camera = cameras.GetByIndex(self._device)

            elif type(self._device) == str and self._device != 'dummy':
                camera = cameras.GetBySerial(self._device)

            elif type(self._device) == str and self._device == 'dummy':
                camera = DummyCameraPointer()

            #
            result = True
            self.oq.put(result)

        except PySpin.SpinnakerException:

            # clean-up
            try:
                if camera.IsStreaming():
                    camera.EndAcquisition()
                if camera.IsInitialized():
                    camera.DeInit()
                del camera
            except NameError:
                pass
            cameras.Clear()
            try:
                system.ReleaseInstance()
            except PySpin.SpinnakerException:
                pass
            del system

            # reset the started flag
            self.started.value = 0

            #
            result = False
            self.oq.put(result)

            return

        # main loop
        while self.started.value:

            try:
                # call the function
                dilled, kwargs = self.iq.get(block=False)
                f = dill.loads(dilled)
                result, output = f(self, camera, **kwargs)

                # output
                self.oq.put((result, output))

            except queue.Empty:
                continue

        # clean-up
        try:
            if camera.IsStreaming():
                camera.EndAcquisition()
            if camera.IsInitialized():
                camera.DeInit()
            del camera
        except NameError:
            pass
        cameras.Clear()
        try:
            system.ReleaseInstance()
        except PySpin.SpinnakerException:
            pass
        del system

        return

class MainProcess(object):
    """
    """

    def __init__(self, device: int=0, nickname: str=None, color: bool=False) -> None:
        """
        """

        super().__init__()

        # device index or serial no
        self._device = device

        # parameters (determined during initialization)
        self._framerate = None
        self._exposure  = None
        self._binsize   = None
        self._roi       = None

        # acquisition lock state
        self._locked = False

        # default class for the child process
        self._child = None

        #
        if nickname is None:
            self._nickname = f'camera[{self.device}]'
        else:
            self._nickname = nickname

        #
        self._color = color

        return

    def _spawn_child_process(self, cls : ChildProcess, **kwargs) -> None:
        """
        Create an instance of the child process and initialize the camera

        keywords
        --------
        cls : ChildProcess
            a child process class or subclass
        """

        # kill the child process if it already exists
        if self._child is not None:
            self._join_child_process()

        # create and start the child process
        self._child = cls(self._device, **kwargs)
        self._child.start()
        result = self._child.oq.get()
        if not result:
            self._child.join()
            self._child = None
            raise CameraError('Failed to spawn child process')

        @queued
        def f(child, camera, **kwargs):
            try:

                #
                camera.Init()

                # pixel format
                if kwargs['color'] is True:
                    format = PySpin.PixelFormat_RGB8
                else:
                    format = PySpin.PixelFormat_Mono8
                camera.PixelFormat.SetValue(format)

                # acquisition mode
                camera.AcquisitionMode.SetValue(PySpin.AcquisitionMode_Continuous)

                # buffer handling (default is newest only)
                camera.TLStream.StreamBufferHandlingMode.SetValue(PySpin.StreamBufferHandlingMode_NewestOnly)

                # set the exposure
                camera.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
                camera.AcquisitionFrameRateEnable.SetValue(False)
                camera.ExposureTime.SetValue(3000)

                # set the framerate
                camera.AcquisitionFrameRateEnable.SetValue(True)
                camera.AcquisitionFrameRate.SetValue(30)

                # set the binsize
                camera.BinningHorizontal.SetValue(2)
                camera.BinningVertical.SetValue(2)

                #
                x = camera.OffsetX.GetValue()
                y = camera.OffsetY.GetValue()
                w = camera.Width.GetValue()
                h = camera.Height.GetValue()

                #
                roi = (x, y, w, h)
                framerate = int(np.ceil(camera.AcquisitionFrameRate.GetValue()))
                exposure  = int(np.ceil(camera.ExposureTime.GetValue()))
                binsize   = (camera.BinningHorizontal.GetValue(), camera.BinningVertical.GetValue())

                #
                output = {
                    'framerate' : framerate,
                    'exposure'  : exposure,
                    'binsize'   : binsize,
                    'roi'       : roi,
                }

                return True, output

            except PySpin.SpinnakerException:
                return False, None

        #
        result, output = f(self, 'Failed to initialize camera', color=self.color)

        self._framerate = output['framerate']
        self._exposure  = output['exposure']
        self._binsize   = output['binsize']
        self._height    = output['roi'][3]
        self._width     = output['roi'][2]
        self._roi       = output['roi']

        return

    def _join_child_process(self) -> None:
        """
        """

        if self._child is None:
            raise CameraError('No active child process')

        if not self._child.started.value:
            raise CameraError('Child process is inactive')

        @queued
        def f(obj, camera, **kwargs):
            try:
                if camera.IsStreaming():
                    camera.EndAcquisition()
                camera.DeInit()
                return True, None
            except PySpin.SpinnakerException:
                return False, None

        # send the function through the queue
        result, output = f(self, 'Failed to release camera')

        # join the child process with the main process
        try:
            self._child.join(timeout=3)
            self._child = None

        except mp.TimeoutError:
            self._child.terminate()
            self._child = None
            raise CameraError('Child process is dead-locked')

    # framerate
    @property
    def framerate(self):
        """
        Camera framerate in frames per second
        """

        if self.locked:
            return self._framerate

        @queued
        def f(child, camera, **kwargs):
            try:
                output = camera.AcquisitionFrameRate.GetValue()
                return True, output
            except PySpin.SpinnakerException:
                return False, None

        result, output = f(self, "Camera framerate query failed")

        return output

    @framerate.setter
    def framerate(self, value):

        if self.locked:
            raise AcquisitionPropertyError(f'Camera is locked during acquisition')

        @queued
        def f(obj, camera, **kwargs):
            value = kwargs['value']
            if not camera.AcquisitionFrameRateEnable.GetValue():
                camera.AcquisitionFrameRateEnable.SetValue(True)
            min = camera.AcquisitionFrameRate.GetMin()
            max = camera.AcquisitionFrameRate.GetMax()
            if value == 'max':
                try:
                    max = camera.AcquisitionFrameRate.GetMax()
                    camera.AcquisitionFrameRate.SetValue(max)
                    return True, None
                except PySpin.SpinnakerException:
                    return False, None
            if not min <= value <= max:
                return False, None
            else:
                try:
                    camera.AcquisitionFrameRate.SetValue(value)
                    if int(np.around(camera.AcquisitionFrameRate.GetValue())) != value:
                        return False, None
                    else:
                        return True, None
                except PySpin.SpinnakerException:
                    return False, None

        kwargs = {'value': value}
        result, output = f(self, "Failed to set framerate", **{'value': value})

        return

    # exposure
    @property
    def exposure(self):
        """
        Camera exposure time in micro seconds
        """

        if self.locked:
            return self._exposure

        @queued
        def f(obj, camera, **kwargs):
            try:
                value = camera.ExposureTime.GetValue()
                return True, value
            except PySpin.SpinnakerException:
                return False, None

        result, output = f(self, "Exposure query failed")

        return output

    @exposure.setter
    def exposure(self, value):

        if self.locked:
            raise AcquisitionPropertyError(f'Camera is locked during acquisition')

        @queued
        def f(obj, camera, **kwargs):
            value = kwargs['value']
            try:
                min = camera.ExposureTime.GetMin()
                max = camera.ExposureTime.GetMax()
                if not min <= value <= max:
                    return False, None
                else:
                    camera.ExposureTime.SetValue(value)
                    return True, None

            except PySpin.SpinnakerException:
                return False, None

        result, output = f(self, "Failed to set camera exposure", **{'value': value})

        return

    # binsize
    @property
    def binsize(self):

        if self.locked:
            return self._binsize

        @queued
        def f(obj, camera, **kwargs):
            try:
                x = camera.BinningHorizontal.GetValue()
                y = camera.BinningVertical.GetValue()
                return True, (x, y)
            except PySpin.SpinnakerException:
                return False, None

        result, output = f(self, "Camera binsize query failed")

        return output

    @binsize.setter
    def binsize(self, value):

        # check the value of the target binsize

        # it can be a single integer
        if isinstance(value, int):
            if value not in [1, 2, 4]:
                raise AcquisitionPropertyError('Binsize must be 1, 2, or 4 pixels')
            value = (value, value)

        # it can be a list or tuple of two integers
        elif (type(value) == list or type(value) == tuple) and len(value) == 2:
            for item in value:
                if item not in [1, 2, 4]:
                    raise AcquisitionPropertyError('Binsize must be 1, 2, or 4 pixels')

        # it can't be anything else
        else:
            raise AcquisitionPropertyError(f'{value} is not a valid value for binsize')

        @queued
        def f(obj, camera, **kwargs):
            xbin, ybin = kwargs['value']
            try:
                xmin = camera.BinningHorizontal.GetMin()
                xmax = camera.BinningHorizontal.GetMax()
                ymin = camera.BinningVertical.GetMin()
                ymax = camera.BinningVertical.GetMax()
                if xmin >= xbin >= xmax or ymin >= ybin >= ymax:
                    return False, None
                else:
                    camera.BinningHorizontal.SetValue(xbin)
                    camera.BinningVertical.SetValue(ybin)
                    camera.OffsetX.SetValue(0)
                    camera.OffsetY.SetValue(0)
                    camera.Height.SetValue(camera.Height.GetMax())
                    camera.Width.SetValue(camera.Width.GetMax())
                    return True, None

            except PySpin.SpinnakerException:
                return False, None

        result, output = f(self, "Failed to set binsize", **{'value': value})

        return

    # roi
    @property
    def roi(self):

        if self.locked:
            return self._roi

        @queued
        def f(obj, camera, **kwargs):
            try:
                x = camera.OffsetX.GetValue()
                y = camera.OffsetY.GetValue()
                w = camera.Width.GetValue()
                h = camera.Height.GetValue()
                return True, (x, y, w, h)
            except PySpin.SpinnakerException:
                return False, None

        result, output = f(self, "Camera ROI query failed")

        return output

    @roi.setter
    def roi(self, value):

        if self.locked:
            raise AcquisitionPropertyError('Camera is locked during acquisition')

        if (type(value) != list and type(value) != tuple) or len(value) != 4:
            raise AcquisitionPropertyError(f'{value} is not a valid value for the ROI')

        @queued
        def f(obj, camera, **kwargs):
            x, y, w, h = kwargs['value']
            try:
                if (camera.Width.GetMax() - (x + w) <= 0) or (camera.Height.GetMax() - (y + h) <= 0):
                    return False, None
                else:
                    camera.OffsetX.SetValue(x)
                    camera.OffsetY.SetValue(y)
                    camera.Height.SetValue(h)
                    camera.Width.SetValue(w)
                    return True, None

            except PySpin.SpinnakerException:
                return False, None

        result, output = f(self, 'Failed to set ROI', **{'value': value})

        return output

    # width (read-only)
    @property
    def width(self):

        if self.locked:
            return self._width

        @queued
        def f(obj, camera, **kwargs):
            try:
                value = camera.Width.GetValue()
                return True, value
            except PySpin.SpinnakerException:
                return False, None

        result, output = f(self, "Camera width query failed")

        return output

    # height (read-only)
    @property
    def height(self):

        if self.locked:
            return self._height

        @queued
        def f(obj, camera, **kwargs):
            try:
                value = camera.Height.GetValue()
                return True, value
            except PySpin.SpinnakerException:
                return False, None

        result, output = f(self, 'Camera height query failed')

        return output

    # acquisition lock state
    @property
    def locked(self):
        return self._locked

    # device index or serial number
    @property
    def device(self):
        return self._device

    # color flag
    @property
    def color(self):
        return self._color

    # camera nickname
    @property
    def nickname(self):
        return self._nickname

    @nickname.setter
    def nickname(self, value):
        self._nickname = str(value)
