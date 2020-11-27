import dill
import types
import queue
import PySpin
import logging
import numpy as np
import multiprocessing as mp

# logging setup
logging.basicConfig(format='%(levelname)s : %(message)s',level=logging.INFO)

# this is the acquisition flag shared among all cameras
_ACQUIRING = mp.Value('i', 0)

class AcquisitionPropertyError(Exception):
    """
    """

    def __init__(self, message):
        """
        """

        super().__init__(message)

        return

class ChildProcess(mp.Process):
    """
    """

    def __init__(self, device=0):
        """
        """

        super().__init__()

        self._device = device

        # io queues
        self.iq = mp.Queue()
        self.oq = mp.Queue()

        #
        self.started   = mp.Value('i', 0)
        self.acquiring = _ACQUIRING

        return

    def start(self):
        """
        override the start method
        """

        self.started.value = 1

        super().start()

    def join(self, timeout=0):
        """
        override the join method
        """

        self.started.value = 0

        super().join(timeout)

        return

    def run(self):
        """
        """

        try:

            # create instances of the system and cameras list
            system  = PySpin.System.GetInstance()
            cameras = system.GetCameras()

            #
            assert len(cameras) != 0

            # instantiate the camera
            if type(self._device) == str:
                camera = cameras.GetBySerial(self._device)

            if type(self._device) == int:
                camera = cameras.GetByIndex(self._device)

        except:

            # clean-up
            try:
                del camera
            except NameError:
                pass
            cameras.Clear()
            del cameras
            system.ReleaseInstance()
            del system

            # reset the started flag
            self.started = False

            return

        # main loop
        while self.started.value:

            try:

                # input
                item = self.iq.get(block=False)

                # call the function
                dilled, args, kwargs = item
                f = dill.loads(dilled)
                result = f(self, camera, *args, **kwargs)

                # output
                self.oq.put(result)

            except queue.Empty:
                continue

        # clean up
        try:
            del camera
        except NameError:
            pass
        cameras.Clear()
        del cameras
        system.ReleaseInstance()
        del system

        return

class MainProcess(object):
    """
    this class houses the interface with the child process
    """

    def __init__(self, device):
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
        self._childClass = ChildProcess

        return

    def _initialize(self):
        """
        """

        # create and start the child process
        self._child = self._childClass(self._device)
        self._child.start()

        def f(obj, camera, *args, **kwargs):
            try:

                #
                camera.Init()

                #
                camera.PixelFormat.SetValue(PySpin.PixelFormat_Mono8)
                camera.AcquisitionMode.SetValue(PySpin.AcquisitionMode_Continuous)
                camera.TLStream.StreamBufferHandlingMode.SetValue(PySpin.StreamBufferHandlingMode_NewestOnly)

                # set the exposure
                camera.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
                camera.AcquisitionFrameRateEnable.SetValue(False)
                camera.ExposureTime.SetValue(3000)

                # set the framerate
                camera.AcquisitionFrameRateEnable.SetValue(True)
                camera.AcquisitionFrameRate.SetValue(1)

                #
                x = camera.OffsetX.GetValue()
                y = camera.OffsetY.GetValue()
                w = camera.Width.GetValue()
                h = camera.Height.GetValue()

                #
                roi = (x, y, w, h)
                framerate = int(np.around(camera.AcquisitionFrameRate.GetValue()))
                exposure  = int(np.around(camera.ExposureTime.GetValue()))
                binsize   = (camera.BinningHorizontal.GetValue(), camera.BinningVertical.GetValue())

                #
                parameters = {
                    'framerate' : framerate,
                    'exposure'  : exposure,
                    'binsize'   : binsize,
                    'roi'       : roi,
                }

                return True, parameters

            except PySpin.SpinnakerException:
                return False, None

        item = (dill.dumps(f), [], {})
        self._child.iq.put(item)
        result, parameters = self._child.oq.get()

        # set all property values
        if result:
            logging.log(logging.INFO, f'camera[{self._device}] initialized')
            self._framerate = parameters['framerate']
            self._exposure  = parameters['exposure']
            self._binsize   = parameters['binsize']
            self._height    = parameters['roi'][3]
            self._width     = parameters['roi'][2]
            self._roi       = parameters['roi']

        else:
            logging.log(logging.ERROR, f'failed to initialize camera[{self._device}]')

        return

    def _release(self):
        """
        """

        if not self._child.started.value:
            logging.log(logging.DEBUG, 'no active child process')
            return

        def f(obj, camera, *args, **kwargs):
            try:
                if camera.IsStreaming():
                    camera.EndAcquisition()
                camera.DeInit()
                return True
            except PySpin.SpinnakerException:
                return False

        # send the function through the queue
        item = (dill.dumps(f), [], {})
        self._child.iq.put(item)

        # retrieve the result of the function call
        result = self._child.oq.get()

        # join the child process with the main process
        self._child.join()

        if result:
            logging.log(logging.INFO, f'camera[{self._device}] released')
        else:
            logging.log(logging.ERROR, f'failed to release camera[{self._device}]')

        return

    # framerate
    @property
    def framerate(self):

        def f(obj, camera, *args, **kwargs):
            try:
                value = camera.AcquisitionFrameRate.GetValue()
            except PySpin.SpinnakerException:
                value = None
            return value

        item = (dill.dumps(f), [], {})
        self._child.iq.put(item)
        value = int(np.around(self._child.oq.get()))

        #
        if value == None:
            logging.log(logging.ERROR, f'framerate query failed')
        if value != self._framerate:
            logging.log(logging.ERROR, f'actual camera framerate of {value} fps does not equal the target framerate of {self._framerate} fps')
            return

        return value

    @framerate.setter
    def framerate(self, value):

        if self._locked:
            raise AcquisitionPropertyError(f'acquisition lock is engaged')

        def f(obj, camera, *args, **kwargs):
            value = kwargs['value']
            if not camera.AcquisitionFrameRateEnable.GetValue():
                camera.AcquisitionFrameRateEnable.SetValue(True)
            min = camera.AcquisitionFrameRate.GetMin()
            max = camera.AcquisitionFrameRate.GetMax()
            if not min <= value <= max:
                return False
            else:
                try:
                    camera.AcquisitionFrameRate.SetValue(value)
                    if int(np.around(camera.AcquisitionFrameRate.GetValue())) != value:
                        return False
                    else:
                        return True
                except PySpin.SpinnakerException:
                    return False

        #
        kwargs = {'value' : value}
        item   = (dill.dumps(f), [], kwargs)
        self._child.iq.put(item)

        #
        result = self._child.oq.get()
        if result:
            self._framerate = value
            logging.log(logging.INFO, f'camera[{self._device}] framerate set to {value}')
        else:
            logging.log(logging.ERROR, f'failed to set camera[{self._device}] framerate to {value}')

        return

    # exposure
    @property
    def exposure(self):

        def f(obj, camera, *args, **kwargs):
            return camera.ExposureTime.GetValue()

        item = (dill.dumps(f), [], {})
        self._child.iq.put(item)
        value = int(np.around(self._child.oq.get()))

        #
        if value != self._exposure:
            logging.log(logging.ERROR, f'actual camera exposure of {value} us does not equal the target exposure of {self._exposure} us')
            return

        return value

    # binsize
    @property
    def binsize(self):

        def f(obj, camera, *args, **kwargs):
            x = camera.BinningHorizontal.GetValue()
            y = camera.BinningVertical.GetValue()
            return (x, y)

        item = (dill.dumps(f), [], {})
        self._child.iq.put(item)
        value = self._child.oq.get()

        #
        if value != self._binsize:
            logging.log(logging.ERROR, f'actual camera binsize of {value} pixels does not equal the target binsize of {self._binsize} pixels')
            return

        return value

    # roi
    @property
    def roi(self):

        def f(obj, camera, *args, **kwargs):
            x = camera.OffsetX.GetValue()
            y = camera.OffsetY.GetValue()
            w = camera.Width.GetValue()
            h = camera.Height.GetValue()
            return (x, y, w, h)

        item = (dill.dumps(f), [], {})
        self._child.iq.put(item)
        value = self._child.oq.get()

        #
        if value != self._roi:
            logging.log(logging.ERROR, f'actual camera roi parameters ({value}) do not equal the target parameters of {self._roi}')
            return

        # set the new width and height values
        x, y, w, h   = value
        self._width  = w
        self._height = h

        return value

    # width
    @property
    def width(self):
        return self._width

    # height
    @property
    def height(self):
        return self._height

    #
    @property
    def locked(self):
        return self._locked
